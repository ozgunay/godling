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
use futures_util::StreamExt;
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
        trusted_proxies: 0,
        buffer: 64,
        resume_frames: 50,
        status_every: Duration::from_secs(3600),
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

async fn relay_status(port: u16) -> Value {
    let mut stream = TcpStream::connect(("127.0.0.1", port)).await.unwrap();
    stream.write_all(b"GET /relay/status HTTP/1.1\r\nHost: relay\r\nConnection: close\r\n\r\n").await.unwrap();
    let mut response = String::new();
    stream.read_to_string(&mut response).await.unwrap();
    serde_json::from_str(response.split("\r\n\r\n").nth(1).unwrap()).unwrap()
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
    let _one = connect(relay, "", Some("http://island.test")).await.unwrap();
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

    let wrong = start_relay(world_port, |config| config.token = "guessed".into()).await;
    let mut c = viewer(wrong, "").await;
    let news = next(&mut c).await;
    assert_eq!((news["type"].as_str(), news["world"].as_str()), (Some("relay"), Some("down")));
    assert!(tokio::time::timeout(Duration::from_millis(1500), whole(&mut c)).await.is_err(), "no island without the token");
    assert_eq!(relay_status(wrong).await["world"], "down");
}
