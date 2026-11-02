//! One viewer's socket: what it is missing first, then the shared stream. Viewers only watch: what they send is
//! read only to know they are still there, and anything over a few kilobytes closes the socket.
use std::collections::HashMap;
use std::net::{IpAddr, SocketAddr};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use axum::body::Bytes;
use axum::extract::ws::{Message, Utf8Bytes, WebSocket, WebSocketUpgrade};
use axum::extract::{ConnectInfo, Query, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use serde::Deserialize;
use tokio::sync::broadcast::error::RecvError;

use crate::hub::Kind;
use crate::App;

const MAX_IN: usize = 4 * 1024; // a viewer has nothing to say: pongs, and a close
const PING_EVERY: Duration = Duration::from_secs(20);
const SILENT_FOR: Duration = Duration::from_secs(60); // three pings unanswered: the phone is gone
const SEND_WITHIN: Duration = Duration::from_secs(10); // a send this slow means its buffers are full
const RESYNCS_KEPT: u32 = 3; // a viewer that falls behind this often cannot keep up: let it reconnect later

/// `?epoch=&since=`: where a returning viewer left off (the last `relay_epoch` and `relay_seq` it saw).
#[derive(Deserialize)]
pub struct Resume {
    epoch: Option<u64>,
    since: Option<u64>,
}

/// GET `/spectate/ws`: checks who may watch, then hands the socket over.
pub async fn stream(
    State(app): State<Arc<App>>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    Query(resume): Query<Resume>,
    upgrade: WebSocketUpgrade,
) -> Response {
    if !app.config.origins.is_empty() {
        // Browsers always send the page's origin: another site cannot show our stream as its own.
        let origin = headers.get(header::ORIGIN).and_then(|value| value.to_str().ok()).unwrap_or("");
        if !app.config.origins.iter().any(|allowed| allowed == origin) {
            return (StatusCode::FORBIDDEN, "This stream is watched from the island's own page.").into_response();
        }
    }
    let ip = client_ip(&headers, peer, app.config.trusted_proxies);
    let seat = match app.seats.take(ip) {
        Ok(seat) => seat,
        Err(code) => return (code, "Too many viewers right now: try again in a moment.").into_response(),
    };
    let resume = resume.epoch.zip(resume.since);
    upgrade
        .max_message_size(MAX_IN)
        .max_frame_size(MAX_IN)
        .on_upgrade(move |socket| watch(socket, app, seat, resume))
}

async fn watch(mut socket: WebSocket, app: Arc<App>, _seat: Seat, resume: Option<(u64, u64)>) {
    let (joined, _watching) = app.hub.join(resume);
    let (mut rx, mut seq) = (joined.rx, joined.seq);
    for frame in joined.first {
        if !send(&mut socket, frame.text).await {
            return;
        }
    }
    let mut ping = tokio::time::interval_at(tokio::time::Instant::now() + PING_EVERY, PING_EVERY);
    let mut heard = Instant::now();
    let mut resyncs = 0;
    loop {
        tokio::select! {
            frame = rx.recv() => match frame {
                Ok(frame) => {
                    if frame.kind != Kind::Status {
                        if frame.seq <= seq {
                            continue; // already in what this viewer was handed on arriving
                        }
                        seq = frame.seq;
                    }
                    if !send(&mut socket, frame.text).await {
                        return;
                    }
                }
                Err(RecvError::Lagged(_)) => {
                    resyncs += 1;
                    if resyncs > RESYNCS_KEPT {
                        return;
                    }
                    let (whole, at) = app.hub.resync();
                    seq = at;
                    if let Some(whole) = whole {
                        if !send(&mut socket, whole.text).await {
                            return;
                        }
                    }
                }
                Err(RecvError::Closed) => return,
            },
            incoming = socket.recv() => match incoming {
                Some(Ok(Message::Close(_))) | Some(Err(_)) | None => return,
                Some(Ok(_)) => heard = Instant::now(),
            },
            _ = ping.tick() => {
                if heard.elapsed() > SILENT_FOR {
                    return;
                }
                if !matches!(tokio::time::timeout(SEND_WITHIN, socket.send(Message::Ping(Bytes::new()))).await, Ok(Ok(()))) {
                    return;
                }
            }
        }
    }
}

async fn send(socket: &mut WebSocket, text: Utf8Bytes) -> bool {
    matches!(tokio::time::timeout(SEND_WITHIN, socket.send(Message::Text(text))).await, Ok(Ok(())))
}

/// The viewer's address: the connection's, or behind `trusted` proxies of ours (Caddy), the one they forwarded.
fn client_ip(headers: &HeaderMap, peer: SocketAddr, trusted: usize) -> IpAddr {
    if trusted > 0 {
        if let Some(forwarded) = headers.get("x-forwarded-for").and_then(|value| value.to_str().ok()) {
            let hops: Vec<&str> = forwarded.split(',').map(str::trim).collect();
            if hops.len() >= trusted {
                if let Ok(ip) = hops[hops.len() - trusted].parse() {
                    return ip;
                }
            }
        }
    }
    peer.ip()
}

/// How many may watch at once, in all and from one address.
pub struct Seats {
    per_ip: Mutex<HashMap<IpAddr, usize>>,
    taken: AtomicUsize,
    most: usize,
    most_per_ip: usize,
}

/// One viewer's place, given back when its socket ends.
pub struct Seat {
    seats: Arc<Seats>,
    ip: IpAddr,
}

impl Seats {
    pub fn new(most: usize, most_per_ip: usize) -> Seats {
        Seats { per_ip: Mutex::new(HashMap::new()), taken: AtomicUsize::new(0), most, most_per_ip }
    }

    fn take(self: &Arc<Self>, ip: IpAddr) -> Result<Seat, StatusCode> {
        let mut per_ip = self.per_ip.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        if self.taken.load(Ordering::Relaxed) >= self.most {
            return Err(StatusCode::SERVICE_UNAVAILABLE);
        }
        let here = per_ip.entry(ip).or_insert(0);
        if *here >= self.most_per_ip {
            return Err(StatusCode::TOO_MANY_REQUESTS);
        }
        *here += 1;
        self.taken.fetch_add(1, Ordering::Relaxed);
        Ok(Seat { seats: self.clone(), ip })
    }
}

impl Drop for Seat {
    fn drop(&mut self) {
        let mut per_ip = self.seats.per_ip.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        if let Some(here) = per_ip.get_mut(&self.ip) {
            *here -= 1;
            if *here == 0 {
                per_ip.remove(&self.ip);
            }
        }
        self.seats.taken.fetch_sub(1, Ordering::Relaxed);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::HeaderValue;

    #[test]
    fn the_address_behind_our_proxy() {
        let peer: SocketAddr = "172.18.0.5:41000".parse().unwrap();
        let mut headers = HeaderMap::new();
        assert_eq!(client_ip(&headers, peer, 1), peer.ip(), "no header: the connection's");
        headers.insert("x-forwarded-for", HeaderValue::from_static("6.6.6.6, 81.2.3.4"));
        assert_eq!(client_ip(&headers, peer, 1).to_string(), "81.2.3.4", "the hop Caddy added, not one a client sent");
        assert_eq!(client_ip(&headers, peer, 0), peer.ip(), "no proxy trusted: the header is ignored");
    }

    #[test]
    fn seats_in_all_and_per_address() {
        let seats = Arc::new(Seats::new(3, 2));
        let (a, b): (IpAddr, IpAddr) = ("1.1.1.1".parse().unwrap(), "2.2.2.2".parse().unwrap());
        let first = seats.take(a).unwrap();
        let _second = seats.take(a).unwrap();
        assert_eq!(seats.take(a).err(), Some(StatusCode::TOO_MANY_REQUESTS));
        let _third = seats.take(b).unwrap();
        assert_eq!(seats.take(b).err(), Some(StatusCode::SERVICE_UNAVAILABLE));
        drop(first);
        assert!(seats.take(a).is_ok(), "a seat given back is free again");
    }
}
