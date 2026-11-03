//! The relay end to end, over real sockets: a stand-in world that speaks Clawblox's spectator stream (the whole island,
//! then what the test pushes), the relay in front of it, and viewers connecting as the page does.
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use axum::extract::ws::{Message, WebSocketUpgrade};
use axum::extract::State;
use axum::http::{HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::Router;
use futures_util::{SinkExt, StreamExt};
use godling_relay::island::Island;
use godling_relay::{run, Config};
use serde_json::{json, Value};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::broadcast;
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::HeaderValue;
use tokio_tungstenite::tungstenite::{Error as WsError, Message as WsMessage};
use tokio_tungstenite::{MaybeTlsStream, WebSocketStream};

const TOKEN: &str = "watch-only";
type Viewer = WebSocketStream<MaybeTlsStream<TcpStream>>;

#[derive(Clone, Debug)]
enum Push {
    Message(String),
    Close,
}

struct World {
    island: Mutex<Value>,
    tx: broadcast::Sender<Push>,
    connections: AtomicUsize,
}

impl World {
    fn push(&self, message: Value) {
        self.tx.send(Push::Message(message.to_string())).expect("the relay is connected");
    }
}

async fn world_stream(State(world): State<Arc<World>>, headers: HeaderMap, upgrade: WebSocketUpgrade) -> Response {
    if headers.get("x-spectator-token").and_then(|v| v.to_str().ok()) != Some(TOKEN) {
        return (StatusCode::UNAUTHORIZED, "Missing or invalid spectator token").into_response();
    }
    upgrade.on_upgrade(move |mut socket| async move {
        let mut rx = world.tx.subscribe();
        let first = world.island.lock().unwrap().to_string();
        world.connections.fetch_add(1, Ordering::SeqCst);
        if socket.send(Message::Text(first.into())).await.is_err() {
            return;
        }
        while let Ok(push) = rx.recv().await {
            match push {
                Push::Message(text) => {
                    if socket.send(Message::Text(text.into())).await.is_err() {
                        return;
                    }
                }
                Push::Close => {
                    let _ = socket.send(Message::Close(None)).await;
                    return;
                }
            }
        }
    })
}

fn island(tick: u64, ids: &[u64]) -> Value {
    let entities: Vec<Value> = ids.iter().map(|&id| json!({"id": id, "name": format!("Part_{id}"), "position": [id, 0, 0]})).collect();
    json!({"tick": tick, "server_time_ms": tick * 33, "game_status": "playing", "players": [], "entities": entities})
}

fn delta(tick: u64, entities: Value) -> Value {
    json!({"type": "spectator_delta", "tick": tick, "server_time_ms": tick * 33, "entities": entities})
}

async fn start_world(first: Value) -> (u16, Arc<World>) {
    let (tx, _) = broadcast::channel(256);
    let world = Arc::new(World { island: Mutex::new(first), tx, connections: AtomicUsize::new(0) });
    let router = Router::new().route("/spectate/ws", get(world_stream)).with_state(world.clone());
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    tokio::spawn(async move { axum::serve(listener, router).await.unwrap() });
    (port, world)
}

async fn start_relay(world_port: u16, tweak: impl FnOnce(&mut Config)) -> u16 {
    let mut config = Config {
        listen: "127.0.0.1:0".into(),
        upstream: format!("ws://127.0.0.1:{world_port}/spectate/ws"),
        token: TOKEN.into(),
        base_path: String::new(),
        origins: Vec::new(),
        max_viewers: 100,
        max_per_ip: 100,
        connects_per_minute: 6000,
        trusted_proxies: 0,
        buffer: 64,
        resume_frames: 50,
        updates_per_second: 0, // each world update as it comes, so the tests can follow them one by one
        status_every: Duration::from_secs(3600),
        ping_every: Duration::from_secs(20),
        silent_for: Duration::from_secs(60),
        send_within: Duration::from_secs(10),
        world_quiet: Duration::from_secs(10),
    };
    tweak(&mut config);
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    tokio::spawn(run(config, listener, std::future::pending()));
    port
}

async fn connect(port: u16, query: &str, origin: Option<&str>) -> Result<Viewer, WsError> {
    let mut request = format!("ws://127.0.0.1:{port}/spectate/ws{query}").into_client_request().unwrap();
    if let Some(origin) = origin {
        request.headers_mut().insert("Origin", HeaderValue::from_str(origin).unwrap());
    }
    tokio_tungstenite::connect_async(request).await.map(|(viewer, _)| viewer)
}

async fn viewer(port: u16, query: &str) -> Viewer {
    connect(port, query, None).await.expect("the relay lets a viewer in")
}

/// The next message, the relay's news included.
async fn next(viewer: &mut Viewer) -> Value {
    loop {
        let message = tokio::time::timeout(Duration::from_secs(5), viewer.next()).await.expect("a message within 5 s");
        if let WsMessage::Text(text) = message.expect("the stream goes on").expect("a good message") {
            return serde_json::from_str(text.as_str()).unwrap();
        }
    }
}

/// The next message from the world (the relay's news skipped).
async fn next_world(viewer: &mut Viewer) -> Value {
    loop {
        let message = next(viewer).await;
        if message["type"] != "relay" {
            return message;
        }
    }
}

/// Skip to the next whole island (a message without a type).
async fn whole(viewer: &mut Viewer) -> Value {
    loop {
        let message = next(viewer).await;
        if message.get("type").is_none() {
            return message;
        }
    }
}

fn without_relay_fields(mut message: Value) -> Value {
    let fields = message.as_object_mut().unwrap();
    fields.remove("relay_epoch");
    fields.remove("relay_seq");
    message
}

fn seq(message: &Value) -> u64 {
    message["relay_seq"].as_u64().expect("every message from the world carries its place")
}

async fn http_get(port: u16, path: &str) -> String {
    let mut stream = TcpStream::connect(("127.0.0.1", port)).await.unwrap();
    stream.write_all(format!("GET {path} HTTP/1.1\r\nHost: relay\r\nConnection: close\r\n\r\n").as_bytes()).await.unwrap();
    let mut response = String::new();
    stream.read_to_string(&mut response).await.unwrap();
    response.split("\r\n\r\n").nth(1).unwrap().to_string()
}

async fn relay_status(port: u16) -> Value {
    serde_json::from_str(&http_get(port, "/relay/status").await).unwrap()
}

#[tokio::test]
async fn a_late_viewer_is_handed_the_island_the_others_hold() {
    let (world_port, world) = start_world(island(1, &[1, 2])).await;
    let relay = start_relay(world_port, |_| {}).await;
    let mut early = viewer(relay, "").await;
    let first = whole(&mut early).await;
    let start = seq(&first);
    let mut held = Island::from_snapshot(without_relay_fields(first)).unwrap();
    let pushes = [
        delta(2, json!([{"id": 1, "p": [1.5, 0, 0], "r": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]}])),
        delta(3, json!([{"id": 3, "add": {"id": 3, "name": "Meteor_1", "position": [0, 40, 0]}}])),
        delta(4, json!([{"id": 2, "rm": true}, {"id": 3, "p": [0, 20, 0]}])),
        delta(5, json!([])),
    ];
    for (i, push) in pushes.iter().enumerate() {
        world.push(push.clone());
        let got = next_world(&mut early).await;
        assert_eq!(seq(&got), start + 1 + i as u64, "places count on one by one");
        assert_eq!(without_relay_fields(got.clone()), *push, "the world's message, untouched but for its place");
        held.apply(got.as_object().unwrap());
    }
    let mut late = viewer(relay, "").await;
    let handed = whole(&mut late).await;
    assert_eq!(seq(&handed), start + 4);
    let held: Value = serde_json::from_str(&held.to_json(0, 0)).unwrap();
    assert_eq!(without_relay_fields(handed), without_relay_fields(held), "the late viewer holds what the early one does");
    assert_eq!(world.connections.load(Ordering::SeqCst), 1, "two viewers, one connection to the world");
}

#[tokio::test]
async fn a_returning_viewer_catches_up_without_the_whole_island() {
    let (world_port, world) = start_world(island(1, &[1])).await;
    let relay = start_relay(world_port, |_| {}).await;
    let mut leaving = viewer(relay, "").await;
    let first = whole(&mut leaving).await;
    let (epoch, start) = (first["relay_epoch"].as_u64().unwrap(), seq(&first));
    drop(leaving);
    let mut watcher = viewer(relay, "").await; // to know when the relay has the updates
    whole(&mut watcher).await;
    for tick in 2..5 {
        world.push(delta(tick, json!([{"id": 1, "p": [tick, 0, 0]}])));
        next_world(&mut watcher).await;
    }
    let mut back = viewer(relay, &format!("?epoch={epoch}&since={start}")).await;
    assert_eq!(next(&mut back).await["type"], "relay", "the news first");
    for i in 1..=3 {
        let got = next(&mut back).await;
        assert_eq!(got["type"], "spectator_delta", "only the updates it missed, no whole island");
        assert_eq!(seq(&got), start + i);
    }
    world.push(delta(5, json!([])));
    assert_eq!(seq(&next_world(&mut back).await), start + 4, "then the live stream, with nothing doubled");
}

#[tokio::test]
async fn an_unknown_place_gets_the_whole_island() {
    let (world_port, _world) = start_world(island(1, &[1, 2, 3])).await;
    let relay = start_relay(world_port, |_| {}).await;
    let mut first = viewer(relay, "").await;
    whole(&mut first).await;
    let mut stale = viewer(relay, "?epoch=1&since=0").await;
    assert_eq!(next(&mut stale).await["type"], "relay");
    let got = next(&mut stale).await;
    assert!(got.get("type").is_none(), "an epoch long gone: the whole island");
    assert_eq!(got["entities"].as_array().unwrap().len(), 3);
}

#[tokio::test]
async fn a_world_restart_reaches_viewers_on_the_same_socket() {
    let (world_port, world) = start_world(island(1, &[1, 2])).await;
    let relay = start_relay(world_port, |_| {}).await;
    let mut watching = viewer(relay, "").await;
    let before = whole(&mut watching).await;
    *world.island.lock().unwrap() = island(100, &[9]);
    world.tx.send(Push::Close).unwrap();
    loop {
        let news = next(&mut watching).await;
        if news["type"] == "relay" && news["world"] == "down" {
            break;
        }
    }
    let after = whole(&mut watching).await;
    assert!(after["relay_epoch"].as_u64() > before["relay_epoch"].as_u64(), "a new world, a new epoch");
    assert!(seq(&after) > seq(&before));
    assert_eq!(after["tick"], 100);
    assert_eq!(after["entities"], json!([{"id": 9, "name": "Part_9", "position": [9, 0, 0]}]));
    let news = next(&mut watching).await;
    assert_eq!((news["type"].as_str(), news["world"].as_str()), (Some("relay"), Some("up")));
    assert_eq!(world.connections.load(Ordering::SeqCst), 2);
}

#[tokio::test]
async fn chat_and_speech_pass_through_in_their_place() {
    let (world_port, world) = start_world(island(1, &[1])).await;
    let relay = start_relay(world_port, |_| {}).await;
    let mut watching = viewer(relay, "").await;
    let start = seq(&whole(&mut watching).await);
    let chat = json!({"type": "chat_message", "agent_name": "Godling", "content": "A stone tower, then the roof.", "seq": 4});
    world.push(chat.clone());
    let got = next_world(&mut watching).await;
    assert_eq!(seq(&got), start + 1);
    assert_eq!(got["seq"], 4, "the message's own fields are left alone");
    assert_eq!(without_relay_fields(got), chat);
}

#[tokio::test]
async fn only_the_islands_page_and_a_few_sockets_per_address() {
    let (world_port, _world) = start_world(island(1, &[1])).await;
    let relay = start_relay(world_port, |config| {
        config.origins = vec!["http://island.test".into()];
        config.max_per_ip = 2;
    })
    .await;
    let refused = |result: Result<Viewer, WsError>| match result {
        Err(WsError::Http(response)) => response.status().as_u16(),
        Err(other) => panic!("refused another way: {other}"),
        Ok(_) => 101,
    };
    assert_eq!(refused(connect(relay, "", None).await), 403, "no origin");
    assert_eq!(refused(connect(relay, "", Some("https://elsewhere.example")).await), 403, "another site's page");
    let _one = connect(relay, "", Some("http://Island.TEST")).await.expect("a host name's case does not matter");
    let _two = connect(relay, "", Some("http://island.test")).await.unwrap();
    assert_eq!(refused(connect(relay, "", Some("http://island.test")).await), 429, "a third from the same address");
}

#[tokio::test]
async fn the_status_counts_viewers_and_says_when_the_world_will_not_stream() {
    let (world_port, _world) = start_world(island(7, &[1, 2])).await;
    let relay = start_relay(world_port, |_| {}).await;
    let mut a = viewer(relay, "").await;
    let mut b = viewer(relay, "").await;
    whole(&mut a).await;
    whole(&mut b).await;
    let status = relay_status(relay).await;
    assert_eq!((status["world"].as_str(), status["viewers"].as_u64()), (Some("up"), Some(2)));
    assert_eq!((status["tick"].as_u64(), status["entities"].as_u64()), (Some(7), Some(2)));

    // Every few seconds, everyone hears how many watch (here every 50 ms).
    let ticking = start_relay(world_port, |config| config.status_every = Duration::from_millis(50)).await;
    let mut d = viewer(ticking, "").await;
    whole(&mut d).await;
    let mut heard = 0;
    while heard < 3 {
        let news = next(&mut d).await;
        if news["type"] == "relay" && news["viewers"] == 1 {
            heard += 1;
        }
    }

    let wrong = start_relay(world_port, |config| config.token = "guessed".into()).await;
    let mut c = viewer(wrong, "").await;
    let news = next(&mut c).await;
    assert_eq!((news["type"].as_str(), news["world"].as_str()), (Some("relay"), Some("down")));
    assert!(tokio::time::timeout(Duration::from_millis(1500), whole(&mut c)).await.is_err(), "no island without the token");
    assert_eq!(relay_status(wrong).await["world"], "down");
}

/// The next message, binary or text, as bytes.
async fn next_raw(viewer: &mut Viewer) -> WsMessage {
    loop {
        let message = tokio::time::timeout(Duration::from_secs(5), viewer.next()).await.expect("a message within 5 s");
        let message = message.expect("the stream goes on").expect("a good message");
        if message.is_text() || message.is_binary() {
            return message;
        }
    }
}

/// What a scripted world does with one of the relay's connections.
#[derive(Clone, Copy, Debug)]
enum Visit {
    /// The whole island, then nothing more, the socket held open.
    Island,
    /// Things that are no island (a binary frame, a ping, words, a list), then the world's own error.
    Error,
    /// A close, before any island.
    CloseAtOnce,
    /// The connection dropped, with no close.
    Reset,
}

/// A world that answers the relay's connections in turn as `visits` says, and after them with the island for good.
async fn start_scripted_world(first: Value, visits: Vec<Visit>) -> (u16, Arc<AtomicUsize>) {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let connections = Arc::new(AtomicUsize::new(0));
    let counted = connections.clone();
    tokio::spawn(async move {
        let mut visits = visits.into_iter();
        loop {
            let (tcp, _) = listener.accept().await.unwrap();
            let visit = visits.next().unwrap_or(Visit::Island);
            counted.fetch_add(1, Ordering::SeqCst);
            let first = first.to_string();
            tokio::spawn(async move {
                let mut ws = tokio_tungstenite::accept_async(tcp).await.unwrap();
                match visit {
                    Visit::Island => {
                        let _ = ws.send(WsMessage::Text(first.into())).await;
                        while let Some(Ok(_)) = ws.next().await {}
                    }
                    Visit::Error => {
                        let error = json!({"error": "World ended"}).to_string();
                        for message in [WsMessage::Binary(vec![1, 2].into()), WsMessage::Ping(vec![].into()),
                                        WsMessage::Text("not json".into()), WsMessage::Text("[1]".into()),
                                        WsMessage::Text(error.into())] {
                            let _ = ws.send(message).await;
                        }
                        while let Some(Ok(_)) = ws.next().await {}
                    }
                    Visit::CloseAtOnce => {
                        let _ = ws.close(None).await;
                    }
                    Visit::Reset => drop(ws),
                }
            });
        }
    });
    (port, connections)
}

/// The next message within `within`, or None when the stream has ended (or nothing came).
async fn next_within(viewer: &mut Viewer, within: Duration) -> Option<Value> {
    let until = tokio::time::Instant::now() + within;
    loop {
        match tokio::time::timeout_at(until, viewer.next()).await {
            Ok(Some(Ok(WsMessage::Text(text)))) => return Some(serde_json::from_str(text.as_str()).unwrap()),
            Ok(Some(Ok(WsMessage::Close(_)))) | Ok(Some(Err(_))) | Ok(None) | Err(_) => return None,
            Ok(Some(Ok(_))) => {}
        }
    }
}

#[tokio::test]
async fn a_page_that_asks_gets_the_whole_island_gzipped() {
    let ids: Vec<u64> = (1..=400).collect();
    let (world_port, world) = start_world(island(1, &ids)).await;
    let relay = start_relay(world_port, |_| {}).await;
    let mut plain = viewer(relay, "").await;
    let text = whole(&mut plain).await;
    let mut packed = viewer(relay, "?gz=1").await;
    let mut got = None;
    while got.is_none() {
        if let WsMessage::Binary(bytes) = next_raw(&mut packed).await {
            got = Some(bytes);
        }
    }
    let bytes = got.unwrap();
    assert_eq!(&bytes[..2], &[0x1f, 0x8b], "gzip");
    let mut json = String::new();
    std::io::Read::read_to_string(&mut flate2::read::GzDecoder::new(&bytes[..]), &mut json).unwrap();
    assert_eq!(serde_json::from_str::<Value>(&json).unwrap(), text, "the same island");
    assert!(bytes.len() * 5 < json.len(), "much smaller: {} bytes for {}", bytes.len(), json.len());
    world.push(delta(2, json!([{"id": 1, "p": [2, 0, 0]}])));
    match next_raw(&mut packed).await {
        WsMessage::Text(update) => assert!(update.as_str().contains("\"spectator_delta\""), "a small update stays text"),
        other => panic!("an update came as {other:?}"),
    }
}

fn inflated(bytes: &[u8]) -> Value {
    let mut json = String::new();
    std::io::Read::read_to_string(&mut flate2::read::GzDecoder::new(bytes), &mut json).unwrap();
    serde_json::from_str(&json).unwrap()
}

#[tokio::test]
async fn the_worlds_updates_go_out_gathered_ten_a_second() {
    let ids: Vec<u64> = (1..=50).collect();
    let (world_port, world) = start_world(island(1, &ids)).await;
    let relay = start_relay(world_port, |config| config.updates_per_second = 10).await;
    let mut plain = viewer(relay, "").await;
    let mut held = Island::from_snapshot(without_relay_fields(whole(&mut plain).await)).unwrap();
    let mut packed = viewer(relay, "?gz=1").await;
    let mut truth = Island::from_snapshot(island(1, &ids)).unwrap();
    for tick in 2..=31 {
        // Everything moves on every tick, as the world sends it 31 times a second.
        let moves: Vec<Value> = ids.iter().map(|&id| json!({"id": id, "p": [id as f64 + tick as f64 / 8.0, 0.5, -0.25]})).collect();
        let push = delta(tick, Value::Array(moves));
        truth.apply(push.as_object().unwrap());
        world.push(push);
        tokio::time::sleep(Duration::from_millis(33)).await;
    }
    let mut updates = 0;
    loop {
        let update = next_world(&mut plain).await;
        updates += 1;
        held.apply(update.as_object().unwrap());
        if update["tick"] == 31 {
            break;
        }
    }
    assert!((5..=20).contains(&updates), "30 world updates in a second went out as {updates}, not 30");
    let island = |island: &Island| -> Value { serde_json::from_str(&island.to_json(0, 0)).unwrap() };
    assert_eq!(island(&held), island(&truth), "and leave the viewer with the world's island");
    let mut gzipped = 0;
    loop {
        let (update, binary) = match next_raw(&mut packed).await {
            WsMessage::Binary(bytes) => (inflated(&bytes), true),
            WsMessage::Text(text) => (serde_json::from_str::<Value>(text.as_str()).unwrap(), false),
            _ => continue,
        };
        if update["type"] == "spectator_delta" {
            assert!(binary, "an update of fifty moves comes gzipped");
            gzipped += 1;
            if update["tick"] == 31 {
                break;
            }
        }
    }
    assert_eq!(gzipped, updates, "the page that asks gets the same updates, each gzipped");
}

#[tokio::test]
async fn connecting_again_and_again_is_refused_for_a_while() {
    let (world_port, _world) = start_world(island(1, &[1])).await;
    let relay = start_relay(world_port, |config| {
        config.max_per_ip = 3; // also the burst of openings one address has
        config.connects_per_minute = 6;
    })
    .await;
    for _ in 0..3 {
        let mut quick = viewer(relay, "").await;
        whole(&mut quick).await;
        drop(quick); // in and out again, as a script hammering the relay would
    }
    match connect(relay, "", None).await {
        Err(WsError::Http(response)) => {
            assert_eq!(response.status().as_u16(), 429);
            assert!(response.headers().contains_key("retry-after"));
        }
        other => panic!("a fourth connection at once was let in: {}", other.is_ok()),
    }
    let metrics = http_get(relay, "/metrics").await;
    assert!(metrics.contains("godling_relay_refused_total{reason=\"rate\"} 1"), "{metrics}");
}

#[tokio::test]
async fn metrics_count_what_happened() {
    let (world_port, world) = start_world(island(1, &[1, 2])).await;
    let relay = start_relay(world_port, |config| config.origins = vec!["http://island.test".into()]).await;
    let _refused = connect(relay, "", None).await;
    let mut watching = connect(relay, "", Some("http://island.test")).await.unwrap();
    whole(&mut watching).await;
    world.push(delta(2, json!([])));
    next_world(&mut watching).await;
    let metrics = http_get(relay, "/metrics").await;
    for line in [
        "godling_relay_viewers 1",
        "godling_relay_max_viewers 100",
        "godling_relay_world_up 1",
        "godling_relay_connections_total 1",
        "godling_relay_refused_total{reason=\"origin\"} 1",
        "godling_relay_world_connections_total 1",
        "# TYPE godling_relay_sent_bytes_total counter",
    ] {
        assert!(metrics.lines().any(|l| l == line || l.starts_with(line)), "missing {line:?} in\n{metrics}");
    }
    let sent: u64 = metrics.lines().find_map(|l| l.strip_prefix("godling_relay_sent_bytes_total ")).unwrap().parse().unwrap();
    assert!(sent > 100, "bytes counted: {sent}");
}

/// Whether the relay ends this viewer's stream within `within` (whatever it still sends before).
async fn let_go(viewer: &mut Viewer, within: Duration) -> bool {
    tokio::time::timeout(within, async {
        loop {
            match viewer.next().await {
                None | Some(Err(_)) | Some(Ok(WsMessage::Close(_))) => return,
                Some(Ok(_)) => {}
            }
        }
    })
    .await
    .is_ok()
}

#[tokio::test]
async fn a_world_that_fails_every_way_is_followed_until_it_streams() {
    let visits = vec![Visit::Error, Visit::CloseAtOnce, Visit::Reset];
    let (world_port, connections) = start_scripted_world(island(3, &[1, 2]), visits).await;
    let relay = start_relay(world_port, |_| {}).await;
    let mut watching = viewer(relay, "").await;
    let island = loop {
        let message = next_within(&mut watching, Duration::from_secs(15)).await.expect("the island, in the end");
        if message.get("type").is_none() {
            break message;
        }
    };
    assert_eq!(island["tick"], 3, "none of what came before was taken for an island");
    assert_eq!(connections.load(Ordering::SeqCst), 4, "it came back after each failure");
}

#[tokio::test]
async fn a_world_gone_quiet_is_down_and_is_followed_again() {
    let (world_port, connections) = start_scripted_world(island(1, &[1]), vec![]).await;
    let relay = start_relay(world_port, |config| config.world_quiet = Duration::from_millis(300)).await;
    let mut watching = viewer(relay, "").await;
    let first = whole(&mut watching).await;
    loop {
        let news = next(&mut watching).await;
        if news["type"] == "relay" && news["world"] == "down" {
            break; // the world said nothing for 300 ms
        }
    }
    let again = whole(&mut watching).await;
    assert!(again["relay_epoch"].as_u64() > first["relay_epoch"].as_u64());
    assert!(connections.load(Ordering::SeqCst) >= 2);
}

#[tokio::test]
async fn a_token_that_cannot_be_a_header_never_reaches_the_world() {
    let (world_port, world) = start_world(island(1, &[1])).await;
    let relay = start_relay(world_port, |config| config.token = "watch\nonly".into()).await;
    let mut watching = viewer(relay, "").await;
    let news = next(&mut watching).await;
    assert_eq!((news["type"].as_str(), news["world"].as_str()), (Some("relay"), Some("down")));
    tokio::time::sleep(Duration::from_millis(700)).await; // a retry or two
    assert_eq!(world.connections.load(Ordering::SeqCst), 0);
    // With no token at all, it asks without one, and this world refuses.
    let none = start_relay(world_port, |config| config.token = String::new()).await;
    tokio::time::sleep(Duration::from_millis(300)).await;
    assert_eq!(relay_status(none).await["world"], "down");
    // And a world's address that is no address: it keeps trying, and says the world is down.
    let nowhere = start_relay(world_port, |config| config.upstream = "not an address".into()).await;
    tokio::time::sleep(Duration::from_millis(300)).await;
    assert_eq!(relay_status(nowhere).await["world"], "down");
}

#[tokio::test]
async fn a_viewer_is_pinged_and_let_go_once_it_stops_answering() {
    let (world_port, _world) = start_world(island(1, &[1])).await;
    let relay = start_relay(world_port, |config| {
        config.ping_every = Duration::from_millis(50);
        config.silent_for = Duration::from_millis(300);
    })
    .await;
    let mut watching = viewer(relay, "").await;
    whole(&mut watching).await;
    watching.send(WsMessage::Text("still here".into())).await.unwrap(); // only read to know it is there
    // Reading, the viewer answers each ping (the library does), so it stays well past 300 ms.
    let (mut pings, until) = (0, tokio::time::Instant::now() + Duration::from_millis(800));
    while let Ok(Some(message)) = tokio::time::timeout_at(until, watching.next()).await {
        if let Ok(WsMessage::Ping(_)) = message {
            pings += 1;
        }
    }
    assert!(pings >= 5, "pinged every 50 ms, and kept: {pings} pings");
    // Not reading, it answers nothing.
    tokio::time::sleep(Duration::from_millis(800)).await;
    assert!(let_go(&mut watching, Duration::from_secs(5)).await, "let go once it stopped answering");
    assert_eq!(relay_status(relay).await["viewers"], 0);
}

#[tokio::test]
async fn viewers_whose_connections_are_reset_are_let_go() {
    let (world_port, _world) = start_world(island(1, &[1])).await;
    let relay = start_relay(world_port, |config| config.ping_every = Duration::from_millis(1)).await;
    let mut viewers = Vec::new();
    for _ in 0..24 {
        let mut watching = viewer(relay, "").await;
        whole(&mut watching).await;
        viewers.push(watching);
    }
    assert_eq!(relay_status(relay).await["viewers"], 24);
    // Each drops its connection with a reset, not a close: the relay finds out by reading, or by its next ping.
    for watching in viewers {
        if let MaybeTlsStream::Plain(tcp) = watching.get_ref() {
            tcp.set_zero_linger().unwrap();
        }
        drop(watching);
    }
    let gone = tokio::time::timeout(Duration::from_secs(5), async {
        while relay_status(relay).await["viewers"] != 0 {
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
    })
    .await;
    assert!(gone.is_ok(), "every one let go");
}

#[tokio::test]
async fn a_viewer_that_falls_behind_is_handed_the_island_again_until_it_cannot_keep_up() {
    let (world_port, world) = start_world(island(1, &[1])).await;
    let relay = start_relay(world_port, |config| config.buffer = 2).await;
    let mut slow = viewer(relay, "").await;
    whole(&mut slow).await;
    let pad = "x".repeat(512 * 1024);
    let (mut handed_again, mut ended, mut last_seq) = (0, false, 0);
    for _ in 0..12 {
        // Not reading while the world says a lot: its socket fills, and the stream runs on without it.
        for _ in 0..64 {
            world.push(json!({"type": "chat_message", "content": pad}));
        }
        tokio::time::sleep(Duration::from_millis(400)).await;
        // Reading again: what its socket held, then the whole island, and the stream on from there.
        loop {
            match tokio::time::timeout(Duration::from_secs(1), slow.next()).await {
                Err(_) => break, // read up: the next round
                Ok(Some(Ok(WsMessage::Text(text)))) => {
                    let message: Value = serde_json::from_str(text.as_str()).unwrap();
                    if message["type"] == "relay" {
                        continue;
                    }
                    let whole = message.get("type").is_none();
                    assert!(seq(&message) > last_seq || whole, "nothing twice, nothing back in time");
                    last_seq = seq(&message);
                    handed_again += usize::from(whole);
                }
                Ok(Some(Ok(_))) => {}
                Ok(_) => {
                    ended = true;
                    break;
                }
            }
        }
        if ended {
            break;
        }
    }
    assert!(handed_again >= 1, "handed the whole island again");
    assert!(ended, "let go in the end: it cannot keep up");
    assert_eq!(relay_status(relay).await["resyncs"], 3, "three times handed the island, the fourth time let go");
}

#[tokio::test]
async fn a_viewer_that_cannot_take_the_island_it_is_handed_again_is_let_go() {
    // A big island (12 MB), so handing it again needs the viewer to read.
    let big = json!({"tick": 1, "entities": [{"id": 1, "pad": "x".repeat(12 * 1024 * 1024)}]});
    let (world_port, world) = start_world(big).await;
    let relay = start_relay(world_port, |config| {
        config.buffer = 2;
        config.send_within = Duration::from_secs(1);
    })
    .await;
    let mut slow = viewer(relay, "").await;
    whole(&mut slow).await;
    let pad = "x".repeat(1024 * 1024);
    for _ in 0..40 {
        world.push(json!({"type": "chat_message", "content": pad})); // its socket fills; the stream runs on
    }
    tokio::time::sleep(Duration::from_millis(300)).await;
    next(&mut slow).await; // one message read: room for the send that was stuck, so it falls behind...
    tokio::time::sleep(Duration::from_millis(2000)).await; // ...and is handed the island, which it does not read
    assert_eq!(relay_status(relay).await["viewers"], 0);
}

#[tokio::test]
async fn a_viewer_too_slow_to_take_a_send_is_let_go() {
    let (world_port, world) = start_world(island(1, &[1])).await;
    let relay = start_relay(world_port, |config| config.send_within = Duration::from_millis(200)).await;
    let mut reading = viewer(relay, "").await;
    let first = whole(&mut reading).await;
    let (epoch, start) = (first["relay_epoch"].as_u64().unwrap(), seq(&first));
    let pad = "x".repeat(1024 * 1024);
    for _ in 0..48 {
        world.push(json!({"type": "chat_message", "content": pad}));
        next_world(&mut reading).await;
    }
    // Back from a gap, a viewer is handed what it missed first: here 48 MB, too much for one that never reads.
    let _stuck = viewer(relay, &format!("?epoch={epoch}&since={start}")).await;
    tokio::time::sleep(Duration::from_millis(1000)).await;
    assert_eq!(relay_status(relay).await["viewers"], 1, "only the one that reads");
    // And the one that read, once it stops: a send of the stream's own takes too long.
    for _ in 0..48 {
        world.push(json!({"type": "chat_message", "content": pad}));
    }
    tokio::time::sleep(Duration::from_millis(1000)).await;
    assert_eq!(relay_status(relay).await["viewers"], 0, "let go when a send took too long");
}
