//! One viewer's socket: what it is missing first, then the shared stream. Viewers only watch: what they send is
//! read only to know they are still there, and anything over a few kilobytes closes the socket.
use std::collections::HashMap;
use std::net::{IpAddr, Ipv6Addr, SocketAddr};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use axum::body::Bytes;
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::{ConnectInfo, Query, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use serde::Deserialize;
use tokio::sync::broadcast::error::RecvError;

use crate::hub::{Counters, Frame, Kind};
use crate::App;

const MAX_IN: usize = 4 * 1024; // a viewer has nothing to say: pongs, and a close
const RESYNCS_KEPT: u32 = 3; // a viewer that falls behind this often cannot keep up: let it reconnect later

/// `?epoch=&since=`: where a returning viewer left off (the last `relay_epoch` and `relay_seq` it saw). `gz=1`: it
/// takes gzipped frames, the whole island and the updates (ADR-017).
#[derive(Deserialize)]
pub struct Resume {
    epoch: Option<u64>,
    since: Option<u64>,
    gz: Option<String>,
}

/// GET `/spectate/ws`: checks who may watch, then hands the socket over.
pub async fn stream(
    State(app): State<Arc<App>>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    Query(resume): Query<Resume>,
    upgrade: WebSocketUpgrade,
) -> Response {
    let counters = &app.hub.counters;
    if !app.config.origins.is_empty() {
        // Browsers always send the page's origin: another site cannot show our stream as its own. A host name has no
        // case, so neither does the match (a domain written with capitals in .env still matches the browser's).
        let origin = headers.get(header::ORIGIN).and_then(|value| value.to_str().ok()).unwrap_or("");
        if !app.config.origins.iter().any(|allowed| allowed.eq_ignore_ascii_case(origin)) {
            Counters::add(&counters.refused_origin, 1);
            return (StatusCode::FORBIDDEN, "This stream is watched from the island's own page.").into_response();
        }
    }
    let ip = client_ip(&headers, peer, app.config.trusted_proxies);
    let seat = match app.seats.take(ip, Instant::now()) {
        Ok(seat) => seat,
        Err(refusal) => {
            let (counter, code, words) = match refusal {
                Refusal::Busy => (&counters.refused_busy, StatusCode::SERVICE_UNAVAILABLE,
                                  "Too many viewers right now: try again in a moment."),
                Refusal::Address => (&counters.refused_address, StatusCode::TOO_MANY_REQUESTS, "Too many sockets from here."),
                Refusal::Rate => (&counters.refused_rate, StatusCode::TOO_MANY_REQUESTS, "Connecting too often: wait a moment."),
            };
            Counters::add(counter, 1);
            return (code, [(header::RETRY_AFTER, "10")], words).into_response();
        }
    };
    Counters::add(&counters.connections, 1);
    let gz = resume.gz.as_deref() == Some("1");
    let resume = resume.epoch.zip(resume.since);
    upgrade
        .max_message_size(MAX_IN)
        .max_frame_size(MAX_IN)
        .on_upgrade(move |socket| watch(socket, app, seat, resume, gz))
}

async fn watch(mut socket: WebSocket, app: Arc<App>, _seat: Seat, resume: Option<(u64, u64)>, gz: bool) {
    let counters = &app.hub.counters;
    let (joined, _watching) = app.hub.join(resume, gz);
    let (mut rx, mut seq) = (joined.rx, joined.seq);
    let (ping_every, silent_for, within) = (app.config.ping_every, app.config.silent_for, app.config.send_within);
    for frame in joined.first {
        if !send(&mut socket, &frame, gz, within, counters).await {
            return;
        }
    }
    let mut ping = tokio::time::interval_at(tokio::time::Instant::now() + ping_every, ping_every);
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
                    if !send(&mut socket, &frame, gz, within, counters).await {
                        return;
                    }
                }
                Err(RecvError::Lagged(_)) => {
                    resyncs += 1;
                    if resyncs > RESYNCS_KEPT {
                        Counters::add(&counters.dropped_slow, 1);
                        return;
                    }
                    let (whole, at) = app.hub.resync();
                    seq = at;
                    if let Some(whole) = whole {
                        if !send(&mut socket, &whole, gz, within, counters).await {
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
                if heard.elapsed() > silent_for {
                    Counters::add(&counters.dropped_silent, 1);
                    return;
                }
                if !matches!(tokio::time::timeout(within, socket.send(Message::Ping(Bytes::new()))).await, Ok(Ok(()))) {
                    Counters::add(&counters.dropped_send, 1);
                    return;
                }
            }
        }
    }
}

/// A frame to one viewer: gzipped if the page asked for it and the frame has a gzipped copy (whole islands, updates
/// and big passed messages), else as text. Counted for the monitoring; a send that does not finish within `within`
/// lets the viewer go.
async fn send(socket: &mut WebSocket, frame: &Frame, gz: bool, within: Duration, counters: &Counters) -> bool {
    let (message, bytes) = match (&frame.gz, gz) {
        (Some(packed), true) => (Message::Binary(packed.clone()), packed.len()),
        _ => (Message::Text(frame.text.clone()), frame.text.len()),
    };
    let sent = matches!(tokio::time::timeout(within, socket.send(message)).await, Ok(Ok(())));
    if sent {
        Counters::add(&counters.sent_frames, 1);
        Counters::add(&counters.sent_bytes, bytes as u64);
    } else {
        Counters::add(&counters.dropped_send, 1);
    }
    sent
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

/// The address a limit counts by. An IPv6 address counts by its /64: one home or one server holds a whole /64, and
/// would otherwise be countless addresses. An IPv4 address written as IPv6 counts as the IPv4 address it is.
fn bucket(ip: IpAddr) -> IpAddr {
    match ip {
        IpAddr::V4(_) => ip,
        IpAddr::V6(v6) => match v6.to_ipv4_mapped() {
            Some(v4) => IpAddr::V4(v4),
            None => {
                let s = v6.segments();
                IpAddr::V6(Ipv6Addr::new(s[0], s[1], s[2], s[3], 0, 0, 0, 0))
            }
        },
    }
}

/// How many may watch at once, in all and from one address, and how fast one address may open sockets. Every new
/// socket is handed the whole island (hundreds of kilobytes), so opening and closing them in a loop would make the
/// relay send that over and over: each address has a bucket of `most_per_ip` openings, refilled at
/// `connects_per_minute`. A page that comes back from a gap mostly resumes, and spends one.
pub struct Seats {
    book: Mutex<HashMap<IpAddr, Address>>,
    taken: AtomicUsize,
    most: usize,
    most_per_ip: usize,
    refill_per_sec: f64,
}

/// One address: its sockets now, and the openings it has left (refilled as time passes).
struct Address {
    seats: usize,
    openings: f64,
    at: Instant,
}

/// Why a viewer is not let in: every seat taken, its address holding its share, or opening sockets too fast. Each has
/// its own counter in `/metrics` and its own words.
#[derive(Debug, PartialEq, Eq)]
pub enum Refusal {
    Busy,
    Address,
    Rate,
}

/// Addresses remembered before the idle ones (no socket, bucket full again) are forgotten.
const ADDRESSES_KEPT: usize = 4096;

/// One viewer's place, given back when its socket ends.
pub struct Seat {
    seats: Arc<Seats>,
    ip: IpAddr,
}

impl Seats {
    pub fn new(most: usize, most_per_ip: usize, connects_per_minute: usize) -> Seats {
        Seats {
            book: Mutex::new(HashMap::new()),
            taken: AtomicUsize::new(0),
            most,
            most_per_ip,
            refill_per_sec: connects_per_minute as f64 / 60.0,
        }
    }

    fn take(self: &Arc<Self>, ip: IpAddr, now: Instant) -> Result<Seat, Refusal> {
        let ip = bucket(ip);
        let burst = self.most_per_ip.max(1) as f64;
        let mut book = self.book.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        if self.taken.load(Ordering::Relaxed) >= self.most {
            return Err(Refusal::Busy);
        }
        if book.len() >= ADDRESSES_KEPT {
            let refill = self.refill_per_sec;
            book.retain(|_, a| a.seats > 0 || a.openings + now.duration_since(a.at).as_secs_f64() * refill < burst);
        }
        let here = book.entry(ip).or_insert(Address { seats: 0, openings: burst, at: now });
        here.openings = (here.openings + now.duration_since(here.at).as_secs_f64() * self.refill_per_sec).min(burst);
        here.at = now;
        if here.seats >= self.most_per_ip {
            return Err(Refusal::Address);
        }
        if here.openings < 1.0 {
            return Err(Refusal::Rate);
        }
        here.openings -= 1.0;
        here.seats += 1;
        self.taken.fetch_add(1, Ordering::Relaxed);
        Ok(Seat { seats: self.clone(), ip })
    }
}

impl Drop for Seat {
    fn drop(&mut self) {
        let mut book = self.seats.book.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        if let Some(here) = book.get_mut(&self.ip) {
            here.seats = here.seats.saturating_sub(1); // kept with its bucket: closing does not refill it
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
        assert_eq!(client_ip(&headers, peer, 3), peer.ip(), "fewer hops than proxies of ours: not ours");
        headers.insert("x-forwarded-for", HeaderValue::from_static("81.2.3.4, unknown"));
        assert_eq!(client_ip(&headers, peer, 1), peer.ip(), "a hop that is no address");
    }

    #[test]
    fn a_panic_elsewhere_does_not_lock_the_seats_up() {
        let seats = Arc::new(Seats::new(10, 2, 60));
        let held = seats.clone();
        let _ = std::thread::spawn(move || {
            let _book = held.book.lock().unwrap();
            panic!("a task died holding the seats (this panic is the test's)");
        })
        .join();
        assert!(seats.book.is_poisoned());
        let seat = seats.take("1.1.1.1".parse().unwrap(), Instant::now()).expect("seats are still given");
        assert_eq!(seats.taken.load(Ordering::Relaxed), 1);
        drop(seat);
        assert_eq!(seats.taken.load(Ordering::Relaxed), 0, "and given back");
    }

    #[test]
    fn idle_addresses_are_forgotten_once_many_are_kept() {
        let seats = Arc::new(Seats::new(usize::MAX, 2, 60));
        let now = Instant::now();
        for i in 0..ADDRESSES_KEPT as u32 - 1 {
            drop(seats.take(IpAddr::V4(i.into()), now).unwrap()); // came and went
        }
        let _watching = seats.take("10.9.9.9".parse().unwrap(), now).unwrap();
        assert_eq!(seats.book.lock().unwrap().len(), ADDRESSES_KEPT);
        let _new = seats.take("10.8.8.8".parse().unwrap(), now + Duration::from_secs(120)).unwrap();
        assert_eq!(seats.book.lock().unwrap().len(), 2, "the idle ones, their buckets full again, are forgotten");
    }

    #[test]
    fn seats_in_all_and_per_address() {
        let seats = Arc::new(Seats::new(3, 2, 6000));
        let now = Instant::now();
        let (a, b): (IpAddr, IpAddr) = ("1.1.1.1".parse().unwrap(), "2.2.2.2".parse().unwrap());
        let first = seats.take(a, now).unwrap();
        let _second = seats.take(a, now).unwrap();
        assert_eq!(seats.take(a, now).err(), Some(Refusal::Address));
        let _third = seats.take(b, now).unwrap();
        assert_eq!(seats.take(b, now).err(), Some(Refusal::Busy));
        drop(first);
        assert!(seats.take(a, now + Duration::from_secs(1)).is_ok(), "a seat given back is free again");
    }

    #[test]
    fn one_address_cannot_open_sockets_in_a_loop() {
        let seats = Arc::new(Seats::new(100, 4, 60)); // a burst of 4, then one a second
        let ip: IpAddr = "3.3.3.3".parse().unwrap();
        let now = Instant::now();
        for _ in 0..4 {
            drop(seats.take(ip, now).unwrap()); // opened and closed at once, as a loop would
        }
        assert_eq!(seats.take(ip, now).err(), Some(Refusal::Rate), "the burst is spent");
        assert!(seats.take(ip, now + Duration::from_millis(1100)).is_ok(), "one more a second later");
        assert_eq!(seats.take(ip, now + Duration::from_millis(1200)).err(), Some(Refusal::Rate));
    }

    #[test]
    fn an_ipv6_home_is_one_address() {
        let seats = Arc::new(Seats::new(100, 2, 6000));
        let now = Instant::now();
        let _one = seats.take("2001:db8:1:2::1".parse().unwrap(), now).unwrap();
        let _two = seats.take("2001:db8:1:2:ffff::9".parse().unwrap(), now).unwrap();
        let third = seats.take("2001:db8:1:2:abcd:1234:5678:9abc".parse().unwrap(), now);
        assert_eq!(third.err(), Some(Refusal::Address), "the same /64");
        assert!(seats.take("2001:db8:1:3::1".parse().unwrap(), now).is_ok(), "another /64");
        assert_eq!(bucket("::ffff:81.2.3.4".parse().unwrap()), "81.2.3.4".parse::<IpAddr>().unwrap());
    }
}
