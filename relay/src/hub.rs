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

use crate::gather::Gathered;
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
    /// The same gzipped, made once too, for pages that ask (`?gz=1`): a whole island's 276 KB becomes about 17.
    /// None when gzip would not make it smaller.
    pub gz: Option<Bytes>,
}

impl Frame {
    fn whole(island: &Island, epoch: u64, seq: u64) -> Frame {
        let text = island.to_json(epoch, seq);
        let gz = gzipped(&text, Compression::fast());
        Frame { seq, kind: Kind::Whole, text: text.into(), gz }
    }
}

fn gzipped(text: &str, level: Compression) -> Option<Bytes> {
    let mut gz = GzEncoder::new(Vec::with_capacity(text.len() / 8), level);
    let gz = gz.write_all(text.as_bytes()).and_then(|()| gz.finish()).ok()?;
    (gz.len() < text.len()).then(|| Bytes::from(gz))
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
    pending: Gathered,       // the world's deltas since the last update sent (gather.rs)
    players: Option<Value>,  // the players last sent: viewers keep them until an update brings others
}

pub struct Hub {
    inner: Mutex<Inner>,
    tx: broadcast::Sender<Frame>,
    resume_frames: usize,
    gathering: bool, // deltas wait for flush(); else each goes out as it comes
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
    /// updates kept for viewers who come back (300 is thirty seconds at ten updates a second). `gathering`: the world's
    /// deltas wait for `flush`, which the relay calls RELAY_UPDATES_PER_SECOND times a second; else each goes out as it
    /// comes.
    pub fn new(buffer: usize, resume_frames: usize, gathering: bool) -> Hub {
        let (tx, _) = broadcast::channel(buffer.max(1));
        Hub {
            inner: Mutex::new(Inner {
                island: None,
                epoch: 0,
                seq: 0,
                world_up: false,
                recent: VecDeque::new(),
                whole: None,
                pending: Gathered::default(),
                players: None,
            }),
            tx,
            resume_frames,
            gathering,
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
        inner.pending = Gathered::default(); // deltas from before this island: it already holds what they did
        inner.players = None;
        let whole = Frame::whole(&island, inner.epoch, inner.seq);
        inner.island = Some(island);
        inner.whole = Some(whole.clone());
        let _ = self.tx.send(whole);
        let _ = self.tx.send(self.status(&inner));
        self.worlds.fetch_add(1, Ordering::Relaxed);
        true
    }

    /// A world delta: gathered, to go out with the others at the next `flush` (or at once, when not gathering).
    /// Ignored before the first island, which every connection to the world starts with.
    pub fn delta(&self, delta: &Map<String, Value>) {
        let mut inner = self.lock();
        if inner.island.is_none() {
            return;
        }
        inner.pending.add(delta);
        if !self.gathering {
            self.send_gathered(&mut inner);
        }
    }

    /// A world message only passed on (chat, speech, audio), as it is: after the deltas gathered before it.
    pub fn pass(&self, message: &str) {
        let mut inner = self.lock();
        if inner.island.is_none() {
            return;
        }
        self.send_gathered(&mut inner);
        let seq = inner.seq + 1;
        let Some(text) = with_seq(message, seq) else { return };
        inner.seq = seq;
        self.send_update(&mut inner, Frame { seq, kind: Kind::Update, text: text.into(), gz: None });
    }

    /// The deltas gathered since the last flush, out as one update.
    pub fn flush(&self) {
        let mut inner = self.lock();
        self.send_gathered(&mut inner);
    }

    fn send_gathered(&self, inner: &mut Inner) {
        if inner.pending.is_empty() {
            return;
        }
        let mut delta = std::mem::take(&mut inner.pending).finish();
        // The world sends its players (Godling's record) with every delta; viewers keep the last they were sent.
        if delta.get("players") == inner.players.as_ref() {
            delta.remove("players");
        } else if let Some(players) = delta.get("players") {
            inner.players = Some(players.clone());
        }
        let Some(island) = inner.island.as_mut() else { return };
        island.apply(&delta);
        inner.seq += 1;
        let seq = inner.seq;
        delta.insert("relay_seq".into(), seq.into());
        let text = Value::Object(delta).to_string();
        let gz = gzipped(&text, Compression::default());
        self.send_update(inner, Frame { seq, kind: Kind::Update, text: text.into(), gz });
    }

    fn send_update(&self, inner: &mut Inner, frame: Frame) {
        inner.recent.push_back(frame.clone());
        while inner.recent.len() > self.resume_frames {
            inner.recent.pop_front();
        }
        let _ = self.tx.send(frame);
    }

    /// The world's stream ended: what was gathered goes out, and viewers keep the island they hold and are told it is
    /// down.
    pub fn world_lost(&self) {
        let mut inner = self.lock();
        self.send_gathered(&mut inner);
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

    fn delta(tick: u64) -> Map<String, Value> {
        let value = json!({"type": "spectator_delta", "tick": tick, "entities": [{"id": 1, "p": [tick, 0, 0]}]});
        value.as_object().unwrap().clone()
    }

    fn parsed(frame: &Frame) -> Value {
        serde_json::from_str(frame.text.as_str()).unwrap()
    }

    fn inflated(gz: &[u8]) -> String {
        let mut text = String::new();
        std::io::Read::read_to_string(&mut flate2::read::GzDecoder::new(gz), &mut text).unwrap();
        text
    }

    #[test]
    fn gathered_deltas_go_out_as_one_update_at_the_flush() {
        let hub = Arc::new(Hub::new(16, 8, true));
        seen(&hub);
        let (mut joined, _w) = hub.join(None);
        let before = joined.seq;
        for tick in 2..5 {
            hub.delta(&delta(tick));
        }
        assert!(joined.rx.try_recv().is_err(), "nothing out before the flush");
        hub.flush();
        let update = joined.rx.try_recv().expect("one update");
        assert_eq!((update.kind, update.seq), (Kind::Update, before + 1));
        let update = parsed(&update);
        assert_eq!((update["tick"].as_u64(), update["relay_seq"].as_u64()), (Some(4), Some(before + 1)));
        assert_eq!(update["entities"], json!([{"id": 1, "p": [4, 0, 0]}]), "only where it got to");
        assert!(joined.rx.try_recv().is_err(), "one update for the three");
        hub.flush();
        assert!(joined.rx.try_recv().is_err(), "nothing gathered, nothing sent");
        let (late, _w) = hub.join(None);
        assert_eq!(parsed(&late.first[1])["entities"][0]["position"], json!([4, 0, 0]), "the island holds it too");
    }

    #[test]
    fn a_passed_message_goes_after_the_deltas_that_came_before_it() {
        let hub = Arc::new(Hub::new(16, 8, true));
        seen(&hub);
        let (mut joined, _w) = hub.join(None);
        hub.delta(&delta(2));
        hub.pass(r#"{"type":"chat_message","text":"hello"}"#);
        hub.delta(&delta(3));
        let first = parsed(&joined.rx.try_recv().unwrap());
        let second = parsed(&joined.rx.try_recv().unwrap());
        assert_eq!((first["type"].as_str(), first["tick"].as_u64()), (Some("spectator_delta"), Some(2)));
        assert_eq!(second["type"], "chat_message");
        assert_eq!(second["relay_seq"].as_u64(), Some(first["relay_seq"].as_u64().unwrap() + 1));
        assert!(joined.rx.try_recv().is_err(), "tick 3 waits for the flush");
        hub.world_lost();
        assert_eq!(parsed(&joined.rx.try_recv().unwrap())["tick"], 3, "the stream ending sends what was gathered");
    }

    #[test]
    fn players_go_out_only_when_they_changed() {
        let hub = Arc::new(Hub::new(16, 8, false));
        seen(&hub);
        let (mut joined, _w) = hub.join(None);
        let with = |tick: u64, health: u64| {
            let mut fields = delta(tick);
            fields.insert("players".into(), json!([{"name": "Godling", "health": health}]));
            fields
        };
        for (tick, health) in [(2, 100), (3, 100), (4, 90)] {
            hub.delta(&with(tick, health));
        }
        let sent: Vec<Value> = (0..3).map(|_| parsed(&joined.rx.try_recv().unwrap())["players"].clone()).collect();
        assert_eq!(sent, vec![json!([{"name": "Godling", "health": 100}]), Value::Null, json!([{"name": "Godling", "health": 90}])]);
        let (late, _w) = hub.join(None);
        assert_eq!(parsed(&late.first[1])["players"], json!([{"name": "Godling", "health": 90}]));
        seen(&hub);
        hub.delta(&with(5, 90));
        let after: Vec<Frame> = std::iter::from_fn(|| joined.rx.try_recv().ok()).collect();
        assert_eq!(parsed(after.last().unwrap())["players"], json!([{"name": "Godling", "health": 90}]), "a new island: sent again");
    }

    #[test]
    fn updates_are_gzipped_once_when_that_makes_them_smaller() {
        let hub = Arc::new(Hub::new(16, 8, false));
        seen(&hub);
        let (mut joined, _w) = hub.join(None);
        hub.delta(&delta(2));
        assert!(joined.rx.try_recv().unwrap().gz.is_none(), "a small update would only grow");
        let moves: Vec<Value> = (0..60).map(|id| json!({"id": id, "p": [id as f64 * 1.5, 2.25, -3.125]})).collect();
        let mut big = delta(3);
        big.insert("entities".into(), Value::Array(moves));
        hub.delta(&big);
        let update = joined.rx.try_recv().unwrap();
        let gz = update.gz.as_ref().expect("gzipped");
        assert!(gz.len() < update.text.len() / 2, "{} against {}", gz.len(), update.text.len());
        assert_eq!(inflated(gz), update.text.as_str(), "the same bytes, gzipped");
    }

    fn seen(hub: &Hub) {
        assert!(hub.world_seen(json!({"tick": 1, "entities": [{"id": 1, "position": [0, 0, 0]}]})));
    }

    fn kinds(joined: &Joined) -> Vec<Kind> {
        joined.first.iter().map(|frame| frame.kind).collect()
    }

    #[test]
    fn a_new_viewer_gets_the_whole_island_at_the_latest_place() {
        let hub = Arc::new(Hub::new(16, 8, false));
        seen(&hub);
        for tick in 2..5 {
            let fields = delta(tick);
            hub.delta(&fields);
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
        let hub = Arc::new(Hub::new(16, 3, false));
        seen(&hub);
        let epoch = hub.lock().epoch;
        let start = hub.lock().seq;
        for tick in 2..6 {
            let fields = delta(tick);
            hub.delta(&fields);
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
        let hub = Arc::new(Hub::new(16, 8, false));
        seen(&hub);
        let fields = delta(2);
        hub.delta(&fields);
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
        let hub = Arc::new(Hub::new(16, 8, false));
        hub.pass(r#"{"type":"chat_message"}"#);
        let (joined, _w) = hub.join(None);
        assert_eq!(kinds(&joined), vec![Kind::Status]);
        assert_eq!(hub.report()["world"], "down");
    }

    #[test]
    fn a_viewer_that_fell_behind_is_handed_the_island_where_the_stream_is() {
        let hub = Arc::new(Hub::new(16, 8, false));
        assert_eq!(hub.resync().0.map(|frame| frame.kind), None, "no island yet: nothing to hand");
        seen(&hub);
        let fields = delta(2);
        hub.delta(&fields);
        let now = hub.lock().seq;
        let (whole, at) = hub.resync();
        let whole = whole.expect("the island as it is now");
        assert_eq!((whole.kind, whole.seq, at), (Kind::Whole, now, now));
        let parsed: Value = serde_json::from_str(whole.text.as_str()).unwrap();
        assert_eq!(parsed["entities"][0]["position"], json!([2, 0, 0]));
        assert_eq!(hub.report()["resyncs"], 2);
    }

    #[test]
    fn a_panic_elsewhere_does_not_lock_the_hub_up() {
        let hub = Arc::new(Hub::new(16, 8, false));
        let held = hub.clone();
        let _ = std::thread::spawn(move || {
            let _inner = held.inner.lock().unwrap();
            panic!("a task died holding the hub (this panic is the test's)");
        })
        .join();
        assert!(hub.inner.is_poisoned());
        seen(&hub);
        assert_eq!(hub.report()["world"], "up", "the island is still kept, and told");
    }

    #[test]
    fn everyone_hears_how_many_watch() {
        let hub = Arc::new(Hub::new(16, 8, false));
        let (mut joined, _w) = hub.join(None);
        hub.tell_status();
        let news = joined.rx.try_recv().expect("the news");
        assert_eq!(news.kind, Kind::Status);
        let news: Value = serde_json::from_str(news.text.as_str()).unwrap();
        assert_eq!((news["type"].as_str(), news["viewers"].as_u64()), (Some("relay"), Some(1)));
    }

    #[test]
    fn watchers_are_counted_while_they_watch() {
        let hub = Arc::new(Hub::new(16, 8, false));
        let (_j1, w1) = hub.join(None);
        let (_j2, _w2) = hub.join(None);
        assert_eq!(hub.report()["viewers"], 2);
        drop(w1);
        assert_eq!(hub.report()["viewers"], 1);
    }
}
