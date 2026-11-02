//! One viewer's socket: what it is missing first, then the shared stream. Viewers only watch: what they send is
//! read only to know they are still there, and anything over a few kilobytes closes the socket.
//!
//! Who may connect (`Admission`): a few sockets per address and a cap in all, and new connections paced per address
//! and in all, so a script that connects again and again cannot make the relay send the island over and over. An
//! IPv6 address counts by its /64, the block one subscriber holds: otherwise one person has billions of addresses.
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
const PING_EVERY: Duration = Duration::from_secs(20);
const SILENT_FOR: Duration = Duration::from_secs(60); // three pings unanswered: the phone is gone
const SEND_WITHIN: Duration = Duration::from_secs(10); // a send this slow means its buffers are full
const RESYNCS_KEPT: u32 = 3; // a viewer that falls behind this often cannot keep up: let it reconnect later
const PACE_KEPT: usize = 100_000; // address blocks remembered for pacing; past that, the ones back to full go

/// `?epoch=&since=`: where a returning viewer left off (the last `relay_epoch` and `relay_seq` it saw). `gz=1`: it
/// can take a whole island gzipped.
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
        // Browsers always send the page's origin: another site cannot show our stream as its own.
        let origin = headers.get(header::ORIGIN).and_then(|value| value.to_str().ok()).unwrap_or("");
        if !app.config.origins.iter().any(|allowed| allowed == origin) {
            Counters::add(&counters.refused_origin, 1);
            return (StatusCode::FORBIDDEN, "This stream is watched from the island's own page.").into_response();
        }
    }
    let block = block_of(client_ip(&headers, peer, app.config.trusted_proxies));
    let seat = match app.admission.take(block, Instant::now()) {
        Ok(seat) => seat,
        Err(refusal) => {
            let (counter, code, words) = match refusal {
                Refusal::Rate => (&counters.refused_rate, StatusCode::TOO_MANY_REQUESTS, "Connecting too often: wait a moment."),
                Refusal::Address => (&counters.refused_address, StatusCode::TOO_MANY_REQUESTS, "Too many sockets from here."),
                Refusal::Busy => (&counters.refused_busy, StatusCode::SERVICE_UNAVAILABLE, "Too many viewers right now: try again in a moment."),
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
    let (joined, _watching) = app.hub.join(resume);
    let (mut rx, mut seq) = (joined.rx, joined.seq);
    for frame in joined.first {
        if !send(&mut socket, &frame, gz, counters).await {
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
                    if !send(&mut socket, &frame, gz, counters).await {
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
                        if !send(&mut socket, &whole, gz, counters).await {
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
                    Counters::add(&counters.dropped_silent, 1);
                    return;
                }
                if !matches!(tokio::time::timeout(SEND_WITHIN, socket.send(Message::Ping(Bytes::new()))).await, Ok(Ok(()))) {
                    Counters::add(&counters.dropped_send, 1);
                    return;
                }
            }
        }
    }
}

/// A frame to one viewer: a whole island gzipped if the page asked for it, everything else as text.
async fn send(socket: &mut WebSocket, frame: &Frame, gz: bool, counters: &Counters) -> bool {
    let (message, bytes) = match (&frame.gz, gz) {
        (Some(packed), true) => (Message::Binary(packed.clone()), packed.len()),
        _ => (Message::Text(frame.text.clone()), frame.text.len()),
    };
    let sent = matches!(tokio::time::timeout(SEND_WITHIN, socket.send(message)).await, Ok(Ok(())));
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

/// The block an address counts as: itself for IPv4 (and IPv4 inside IPv6), its /64 for IPv6.
fn block_of(ip: IpAddr) -> IpAddr {
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

/// A token bucket: `burst` at once, then `per_second`.
#[derive(Clone, Copy)]
struct Pace {
    tokens: f64,
    at: Instant,
}

impl Pace {
    fn full(burst: f64, now: Instant) -> Pace {
        Pace { tokens: burst, at: now }
    }

    fn refill(&mut self, now: Instant, burst: f64, per_second: f64) {
        self.tokens = (self.tokens + now.saturating_duration_since(self.at).as_secs_f64() * per_second).min(burst);
        self.at = now;
    }

    fn take(&mut self, now: Instant, burst: f64, per_second: f64) -> bool {
        self.refill(now, burst, per_second);
        if self.tokens >= 1.0 {
            self.tokens -= 1.0;
            true
        } else {
            false
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub enum Refusal {
    Rate,
    Address,
    Busy,
}

/// Limits on who may watch (see the module's comment). Set from `Config`.
pub struct Limits {
    pub most: usize,
    pub most_per_block: usize,
    pub connect_burst: f64,         // per block
    pub connects_per_second: f64,   // per block
    pub all_connect_burst: f64,     // everyone together
    pub all_connects_per_second: f64,
}

pub struct Admission {
    limits: Limits,
    seats: Mutex<HashMap<IpAddr, usize>>,
    taken: AtomicUsize,
    paces: Mutex<HashMap<IpAddr, Pace>>,
    all: Mutex<Pace>,
}

/// One viewer's place, given back when its socket ends.
pub struct Seat {
    admission: Arc<Admission>,
    block: IpAddr,
}

impl Admission {
    pub fn new(limits: Limits) -> Admission {
        let all = Pace::full(limits.all_connect_burst, Instant::now());
        Admission { limits, seats: Mutex::new(HashMap::new()), taken: AtomicUsize::new(0), paces: Mutex::new(HashMap::new()),
                    all: Mutex::new(all) }
    }

    /// A seat for a viewer from `block`, or why not. Every try spends from the pace, refused or not: hammering is
    /// what the pace is for.
    fn take(self: &Arc<Self>, block: IpAddr, now: Instant) -> Result<Seat, Refusal> {
        let l = &self.limits;
        {
            let mut paces = self.paces.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
            if paces.len() >= PACE_KEPT {
                paces.retain(|_, pace| {
                    pace.refill(now, l.connect_burst, l.connects_per_second);
                    pace.tokens < l.connect_burst // a block back to full is the same as one never seen
                });
            }
            let pace = paces.entry(block).or_insert_with(|| Pace::full(l.connect_burst, now));
            if !pace.take(now, l.connect_burst, l.connects_per_second) {
                return Err(Refusal::Rate);
            }
        }
        if !self.all.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).take(now, l.all_connect_burst, l.all_connects_per_second) {
            return Err(Refusal::Rate);
        }
        let mut seats = self.seats.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        if self.taken.load(Ordering::Relaxed) >= l.most {
            return Err(Refusal::Busy);
        }
        let here = seats.entry(block).or_insert(0);
        if *here >= l.most_per_block {
            return Err(Refusal::Address);
        }
        *here += 1;
        self.taken.fetch_add(1, Ordering::Relaxed);
        Ok(Seat { admission: self.clone(), block })
    }
}

impl Drop for Seat {
    fn drop(&mut self) {
        let mut seats = self.admission.seats.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        if let Some(here) = seats.get_mut(&self.block) {
            *here -= 1;
            if *here == 0 {
                seats.remove(&self.block);
            }
        }
        self.admission.taken.fetch_sub(1, Ordering::Relaxed);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::http::HeaderValue;

    fn limits(most: usize, most_per_block: usize, burst: f64, per_second: f64) -> Limits {
        Limits { most, most_per_block, connect_burst: burst, connects_per_second: per_second, all_connect_burst: 1000.0,
                 all_connects_per_second: 1000.0 }
    }

    fn ip(text: &str) -> IpAddr {
        text.parse().unwrap()
    }

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
    fn an_ipv6_address_counts_by_its_64() {
        assert_eq!(block_of(ip("2001:db8:1:2:aaaa:bbbb:cccc:dddd")), ip("2001:db8:1:2::"));
        assert_eq!(block_of(ip("2001:db8:1:2::1")), block_of(ip("2001:db8:1:2:ffff::9")), "one subscriber's block");
        assert_ne!(block_of(ip("2001:db8:1:2::1")), block_of(ip("2001:db8:1:3::1")), "the next block is someone else");
        assert_eq!(block_of(ip("::ffff:81.2.3.4")), ip("81.2.3.4"), "IPv4 inside IPv6 is that IPv4 address");
        assert_eq!(block_of(ip("81.2.3.4")), ip("81.2.3.4"));
    }

    #[test]
    fn seats_in_all_and_per_block() {
        let admission = Arc::new(Admission::new(limits(3, 2, 100.0, 100.0)));
        let now = Instant::now();
        let (a, b) = (block_of(ip("2001:db8::1")), block_of(ip("2001:db8::2")));
        let first = admission.take(a, now).unwrap();
        let _second = admission.take(b, now).unwrap();
        assert_eq!(admission.take(a, now).err(), Some(Refusal::Address), "two addresses of one /64 share its seats");
        let _third = admission.take(ip("1.1.1.1"), now).unwrap();
        assert_eq!(admission.take(ip("2.2.2.2"), now).err(), Some(Refusal::Busy));
        drop(first);
        assert!(admission.take(a, now).is_ok(), "a seat given back is free again");
    }

    #[test]
    fn connecting_again_and_again_is_paced() {
        let admission = Arc::new(Admission::new(limits(1000, 1000, 3.0, 0.5)));
        let start = Instant::now();
        let mut held = Vec::new();
        for _ in 0..3 {
            held.push(admission.take(ip("9.9.9.9"), start).unwrap());
        }
        assert_eq!(admission.take(ip("9.9.9.9"), start).err(), Some(Refusal::Rate), "the burst spent");
        assert!(admission.take(ip("8.8.8.8"), start).is_ok(), "another address has its own");
        assert_eq!(admission.take(ip("9.9.9.9"), start + Duration::from_millis(1500)).err(), Some(Refusal::Rate));
        assert!(admission.take(ip("9.9.9.9"), start + Duration::from_secs(3)).is_ok(), "one more after two seconds");
    }

    #[test]
    fn everyone_together_is_paced_too() {
        let mut l = limits(1000, 1000, 100.0, 100.0);
        l.all_connect_burst = 2.0;
        l.all_connects_per_second = 1.0;
        let admission = Arc::new(Admission::new(l));
        let now = Instant::now();
        let _a = admission.take(ip("1.0.0.1"), now).unwrap();
        let _b = admission.take(ip("1.0.0.2"), now).unwrap();
        assert_eq!(admission.take(ip("1.0.0.3"), now).err(), Some(Refusal::Rate), "a crowd from many addresses");
    }
}
