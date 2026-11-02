//! The relay's one copy of the island and the stream every viewer shares (ADR-015).
//!
//! Every world message gets a place in the stream (`relay_seq`), counted on from the last; the island it applies to
//! has an `epoch`, which changes whenever the relay is handed a whole island again (a world restart, or the relay
//! reconnecting to it). A viewer arriving gets the whole island at the latest place; one coming back from a short
//! gap names the epoch and the last place it saw, and gets only what it missed, while the relay still holds it.
use std::collections::VecDeque;
use std::fmt::Write as _;
use std::io::Write as _;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, MutexGuard};
use std::time::{SystemTime, UNIX_EPOCH};

use axum::body::Bytes;
use axum::extract::ws::Utf8Bytes;
use flate2::write::GzEncoder;
use flate2::Compression;
use serde_json::{json, Map, Value};
use tokio::sync::broadcast;

use crate::island::{with_seq, Island};

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Kind {
    /// A world message in its place: a delta, or chat, speech and audio. What a returning viewer catches up on.
    Update,
    /// The whole island: a viewer replaces what it holds (a new world, or one that fell behind).
    Whole,
    /// The relay's own news (the world up or down, how many watch): never caught up on, never skipped.
    Status,
}

#[derive(Clone, Debug)]
pub struct Frame {
    pub seq: u64,
    pub kind: Kind,
    pub text: Utf8Bytes, // sent as it is to every viewer: made once, shared
    /// A whole island gzipped, made once too, for pages that ask (`?gz=1`): 276 KB becomes about 11.
    pub gz: Option<Bytes>,
}

impl Frame {
    fn whole(island: &Island, epoch: u64, seq: u64) -> Frame {
        let text = island.to_json(epoch, seq);
        let mut gz = GzEncoder::new(Vec::with_capacity(text.len() / 16), Compression::fast());
        let gz = gz.write_all(text.as_bytes()).and_then(|()| gz.finish()).ok().map(Bytes::from);
        Frame { seq, kind: Kind::Whole, text: text.into(), gz }
    }
}

/// What the relay counts, for `/metrics` and the alerts built on it (deploy/monitoring).
#[derive(Default)]
pub struct Counters {
    pub connections: AtomicU64,
    pub refused_origin: AtomicU64,
    pub refused_busy: AtomicU64,    // every seat taken
    pub refused_address: AtomicU64, // that address (block) holds its share of seats
    pub refused_rate: AtomicU64,    // connecting again too fast, from one block or from everyone
    pub dropped_slow: AtomicU64,    // fell behind too often
    pub dropped_silent: AtomicU64,  // answered no pings
    pub dropped_send: AtomicU64,    // a send that would not finish
    pub sent_bytes: AtomicU64,
    pub sent_frames: AtomicU64,
    pub world_messages: AtomicU64,
}

impl Counters {
    pub fn add(counter: &AtomicU64, n: u64) {
        counter.fetch_add(n, Ordering::Relaxed);
    }
}

struct Inner {
    island: Option<Island>,
    epoch: u64,
    seq: u64,
    world_up: bool,
    recent: VecDeque<Frame>, // the updates since the island was last whole, for viewers who come back
    whole: Option<Frame>,    // the island as one message, made at most once for each place in the stream
}

pub struct Hub {
    inner: Mutex<Inner>,
    tx: broadcast::Sender<Frame>,
    resume_frames: usize,
    viewers: AtomicUsize,
    resumes: AtomicU64, // viewers back from a gap who caught up without the whole island
    resyncs: AtomicU64,
    worlds: AtomicU64,
    pub counters: Counters,
}

/// What a viewer is handed on arriving: the live stream, what to send before it, and the place that leaves it at.
pub struct Joined {
    pub rx: broadcast::Receiver<Frame>,
    pub first: Vec<Frame>,
    pub seq: u64,
}

/// Counts a viewer as watching for as long as it is held.
pub struct Watching(Arc<Hub>);

impl Drop for Watching {
    fn drop(&mut self) {
        self.0.viewers.fetch_sub(1, Ordering::Relaxed);
    }
}

impl Hub {
    /// `buffer`: frames a viewer may fall behind before it is handed the whole island again. `resume_frames`: the
    /// updates kept for viewers who come back (300 is ten seconds of the world's stream).
    pub fn new(buffer: usize, resume_frames: usize) -> Hub {
        let (tx, _) = broadcast::channel(buffer.max(1));
        Hub {
            inner: Mutex::new(Inner { island: None, epoch: 0, seq: 0, world_up: false, recent: VecDeque::new(), whole: None }),
            tx,
            resume_frames,
            viewers: AtomicUsize::new(0),
            resumes: AtomicU64::new(0),
            resyncs: AtomicU64::new(0),
            worlds: AtomicU64::new(0),
            counters: Counters::default(),
        }
    }

    fn lock(&self) -> MutexGuard<'_, Inner> {
        self.inner.lock().unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    /// The world's whole island, as it sends it first on every connection: a new epoch, handed to every viewer.
    /// False if it was not an island.
    pub fn world_seen(&self, snapshot: Value) -> bool {
        let Some(island) = Island::from_snapshot(snapshot) else { return false };
        let mut inner = self.lock();
        inner.epoch = (inner.epoch + 1).max(now_ms());
        inner.seq += 1;
        inner.world_up = true;
        inner.recent.clear();
        let whole = Frame::whole(&island, inner.epoch, inner.seq);
        inner.island = Some(island);
        inner.whole = Some(whole.clone());
        let _ = self.tx.send(whole);
        let _ = self.tx.send(self.status(&inner));
        self.worlds.fetch_add(1, Ordering::Relaxed);
        true
    }

    /// A world message after the island: a delta (`delta`, applied here too) or one only passed on (chat, speech,
    /// audio). Ignored before the first island, which every connection to the world starts with.
    pub fn update(&self, message: &str, delta: Option<&Map<String, Value>>) {
        let mut inner = self.lock();
        let Some(island) = inner.island.as_mut() else { return };
        if let Some(delta) = delta {
            island.apply(delta);
        }
        let seq = inner.seq + 1;
        let Some(text) = with_seq(message, seq) else { return };
        inner.seq = seq;
        let frame = Frame { seq, kind: Kind::Update, text: text.into(), gz: None };
        inner.recent.push_back(frame.clone());
        while inner.recent.len() > self.resume_frames {
            inner.recent.pop_front();
        }
        let _ = self.tx.send(frame);
    }

    /// The world's stream ended: viewers keep the island they hold and are told it is down.
    pub fn world_lost(&self) {
        let mut inner = self.lock();
        if inner.world_up {
            inner.world_up = false;
            let _ = self.tx.send(self.status(&inner));
        }
    }

    /// Every few seconds: the news to everyone, with how many watch.
    pub fn tell_status(&self) {
        let inner = self.lock();
        let _ = self.tx.send(self.status(&inner));
    }

    /// A viewer arrives. `resume`: the epoch and the last place it saw, if it is coming back.
    pub fn join(self: &Arc<Self>, resume: Option<(u64, u64)>) -> (Joined, Watching) {
        self.viewers.fetch_add(1, Ordering::Relaxed);
        let watching = Watching(self.clone());
        let mut inner = self.lock();
        let rx = self.tx.subscribe(); // under the lock: nothing sent after this is in `first`, nothing before is lost
        let mut first = vec![self.status(&inner)];
        let resumable = resume.filter(|&(epoch, since)| epoch == inner.epoch && can_resume(&inner, since));
        match resumable {
            Some((_, since)) => {
                self.resumes.fetch_add(1, Ordering::Relaxed);
                first.extend(inner.recent.iter().filter(|frame| frame.seq > since).cloned());
            }
            None => first.extend(self.whole_now(&mut inner)),
        }
        (Joined { rx, first, seq: inner.seq }, watching)
    }

    /// A viewer fell further behind than the stream keeps: the whole island again, and the place it leaves it at.
    pub fn resync(&self) -> (Option<Frame>, u64) {
        self.resyncs.fetch_add(1, Ordering::Relaxed);
        let mut inner = self.lock();
        (self.whole_now(&mut inner), inner.seq)
    }

    /// For `/relay/status`: the world, the stream and the watchers.
    pub fn report(&self) -> Value {
        let inner = self.lock();
        json!({
            "world": if inner.world_up { "up" } else { "down" },
            "epoch": inner.epoch,
            "seq": inner.seq,
            "tick": inner.island.as_ref().and_then(Island::tick),
            "entities": inner.island.as_ref().map(Island::entity_count),
            "viewers": self.viewers.load(Ordering::Relaxed),
            "resumes": self.resumes.load(Ordering::Relaxed),
            "resyncs": self.resyncs.load(Ordering::Relaxed),
            "worlds": self.worlds.load(Ordering::Relaxed),
        })
    }

    fn whole_now(&self, inner: &mut Inner) -> Option<Frame> {
        if inner.whole.as_ref().is_some_and(|whole| whole.seq == inner.seq) {
            return inner.whole.clone();
        }
        let island = inner.island.as_ref()?;
        let whole = Frame::whole(island, inner.epoch, inner.seq);
        inner.whole = Some(whole.clone());
        Some(whole)
    }

    /// Prometheus' text format, for the monitoring (deploy/monitoring): what is happening now, and what has been
    /// counted since the relay started. `most` is the viewer cap, so alerts can tell how full it is.
    pub fn metrics(&self, most: usize) -> String {
        let (world_up, epoch, seq) = {
            let inner = self.lock();
            (u64::from(inner.world_up), inner.epoch, inner.seq)
        };
        let c = &self.counters;
        let load = |counter: &AtomicU64| counter.load(Ordering::Relaxed);
        let mut out = String::new();
        let mut put = |name: &str, kind: &str, help: &str, values: &[(&str, u64)]| {
            let _ = writeln!(out, "# HELP godling_relay_{name} {help}\n# TYPE godling_relay_{name} {kind}");
            for (labels, value) in values {
                let _ = writeln!(out, "godling_relay_{name}{labels} {value}");
            }
        };
        put("viewers", "gauge", "Viewers connected now.", &[("", self.viewers.load(Ordering::Relaxed) as u64)]);
        put("max_viewers", "gauge", "Viewers the relay takes at most.", &[("", most as u64)]);
        put("world_up", "gauge", "1 while the world's stream is followed.", &[("", world_up)]);
        put("epoch", "gauge", "The island's epoch: it changes on every new world.", &[("", epoch)]);
        put("seq", "gauge", "The latest place in the stream.", &[("", seq)]);
        put("connections_total", "counter", "Viewer sockets opened.", &[("", load(&c.connections))]);
        put("refused_total", "counter", "Viewer sockets refused, by reason.", &[
            ("{reason=\"origin\"}", load(&c.refused_origin)),
            ("{reason=\"busy\"}", load(&c.refused_busy)),
            ("{reason=\"address\"}", load(&c.refused_address)),
            ("{reason=\"rate\"}", load(&c.refused_rate)),
        ]);
        put("dropped_total", "counter", "Viewer sockets the relay let go, by reason.", &[
            ("{reason=\"slow\"}", load(&c.dropped_slow)),
            ("{reason=\"silent\"}", load(&c.dropped_silent)),
            ("{reason=\"send\"}", load(&c.dropped_send)),
        ]);
        put("resumes_total", "counter", "Viewers back from a gap who caught up without the whole island.",
            &[("", load(&self.resumes))]);
        put("resyncs_total", "counter", "Whole islands sent to viewers who fell behind.", &[("", load(&self.resyncs))]);
        put("sent_bytes_total", "counter", "Bytes sent to viewers.", &[("", load(&c.sent_bytes))]);
        put("sent_frames_total", "counter", "Messages sent to viewers.", &[("", load(&c.sent_frames))]);
        put("world_connections_total", "counter", "Connections to the world that brought an island.",
            &[("", load(&self.worlds))]);
        put("world_messages_total", "counter", "Messages from the world.", &[("", load(&c.world_messages))]);
        out
    }

    fn status(&self, inner: &Inner) -> Frame {
        let text = json!({
            "type": "relay",
            "world": if inner.world_up { "up" } else { "down" },
            "relay_epoch": inner.epoch,
            "relay_seq": inner.seq,
            "viewers": self.viewers.load(Ordering::Relaxed),
        });
        Frame { seq: inner.seq, kind: Kind::Status, text: text.to_string().into(), gz: None }
    }
}

/// Whether every update after `since` is still held.
fn can_resume(inner: &Inner, since: u64) -> bool {
    inner.island.is_some()
        && since <= inner.seq
        && (since == inner.seq || inner.recent.front().is_some_and(|first| first.seq <= since + 1))
}

fn now_ms() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_millis() as u64).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn delta(tick: u64) -> (String, Map<String, Value>) {
        let value = json!({"type": "spectator_delta", "tick": tick, "entities": [{"id": 1, "p": [tick, 0, 0]}]});
        (value.to_string(), value.as_object().unwrap().clone())
    }

    fn seen(hub: &Hub) {
        assert!(hub.world_seen(json!({"tick": 1, "entities": [{"id": 1, "position": [0, 0, 0]}]})));
    }

    fn kinds(joined: &Joined) -> Vec<Kind> {
        joined.first.iter().map(|frame| frame.kind).collect()
    }

    #[test]
    fn a_new_viewer_gets_the_whole_island_at_the_latest_place() {
        let hub = Arc::new(Hub::new(16, 8));
        seen(&hub);
        for tick in 2..5 {
            let (text, fields) = delta(tick);
            hub.update(&text, Some(&fields));
        }
        let (joined, _watching) = hub.join(None);
        assert_eq!(kinds(&joined), vec![Kind::Status, Kind::Whole]);
        let whole: Value = serde_json::from_str(joined.first[1].text.as_str()).unwrap();
        assert_eq!(whole["tick"], 4);
        assert_eq!(whole["entities"][0]["position"], json!([4, 0, 0]));
        assert_eq!(whole["relay_seq"], joined.seq);
    }

    #[test]
    fn a_returning_viewer_gets_only_what_it_missed_while_it_is_held() {
        let hub = Arc::new(Hub::new(16, 3));
        seen(&hub);
        let epoch = hub.lock().epoch;
        let start = hub.lock().seq;
        for tick in 2..6 {
            let (text, fields) = delta(tick);
            hub.update(&text, Some(&fields));
        }
        let (joined, _w) = hub.join(Some((epoch, start + 2)));
        assert_eq!(kinds(&joined), vec![Kind::Status, Kind::Update, Kind::Update]);
        assert_eq!(joined.first[1].seq, start + 3);
        let (joined, _w) = hub.join(Some((epoch, start + 4)));
        assert_eq!(kinds(&joined), vec![Kind::Status], "nothing missed");
        let (joined, _w) = hub.join(Some((epoch, start)));
        assert_eq!(kinds(&joined), vec![Kind::Status, Kind::Whole], "only the last 3 are held");
        let (joined, _w) = hub.join(Some((epoch + 1, start + 4)));
        assert_eq!(kinds(&joined), vec![Kind::Status, Kind::Whole], "another epoch");
        let (joined, _w) = hub.join(Some((epoch, start + 99)));
        assert_eq!(kinds(&joined), vec![Kind::Status, Kind::Whole], "a place the stream never reached");
        assert_eq!(hub.report()["resumes"], 2, "the two that caught up without the whole island");
    }

    #[test]
    fn a_new_world_starts_a_new_epoch_and_forgets_the_old_updates() {
        let hub = Arc::new(Hub::new(16, 8));
        seen(&hub);
        let (text, fields) = delta(2);
        hub.update(&text, Some(&fields));
        let first_epoch = hub.lock().epoch;
        let first_seq = hub.lock().seq;
        hub.world_lost();
        assert_eq!(hub.report()["world"], "down");
        seen(&hub);
        assert!(hub.lock().epoch > first_epoch);
        let (joined, _w) = hub.join(Some((first_epoch, first_seq)));
        assert_eq!(kinds(&joined), vec![Kind::Status, Kind::Whole]);
        assert_eq!(hub.report()["world"], "up");
    }

    #[test]
    fn nothing_before_the_first_island() {
        let hub = Arc::new(Hub::new(16, 8));
        hub.update(r#"{"type":"chat_message"}"#, None);
        let (joined, _w) = hub.join(None);
        assert_eq!(kinds(&joined), vec![Kind::Status]);
        assert_eq!(hub.report()["world"], "down");
    }

    #[test]
    fn watchers_are_counted_while_they_watch() {
        let hub = Arc::new(Hub::new(16, 8));
        let (_j1, w1) = hub.join(None);
        let (_j2, _w2) = hub.join(None);
        assert_eq!(hub.report()["viewers"], 2);
        drop(w1);
        assert_eq!(hub.report()["viewers"], 1);
    }
}
