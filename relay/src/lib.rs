//! Godling's island stream relay (ADR-015): one connection to the world's spectator stream, the same updates to every
//! viewer. Built on what Clawblox's page already speaks, so the page works through it unchanged: the first message is
//! the whole island, then `spectator_delta`s, chat, speech and audio, in order. The relay adds `relay_seq` (and on a
//! whole island, `relay_epoch`) so a page that reconnects can say where it left off, and `{"type":"relay"}` news:
//! the world up or down, and how many watch.
mod gather;
pub mod hub;
pub mod island;
mod upstream;
mod viewer;

use std::future::Future;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;

use axum::extract::State;
use axum::routing::get;
use axum::{Json, Router};
use tokio::net::TcpListener;

use crate::hub::Hub;
use crate::viewer::Seats;

const MOST_UPDATES_PER_SECOND: usize = 60;

/// Everything a deployment sets (`from_env`: `RELAY_*`).
#[derive(Clone, Debug)]
pub struct Config {
    /// Where viewers connect (RELAY_LISTEN, default 127.0.0.1:8082).
    pub listen: String,
    /// The world's spectator stream (RELAY_UPSTREAM, default ws://127.0.0.1:8080/spectate/ws).
    pub upstream: String,
    /// The world's spectator token (RELAY_SPECTATOR_TOKEN, else WORLD_SPECTATOR_TOKEN). Only the relay holds it.
    pub token: String,
    /// Served under this path, as the world is (RELAY_BASE_PATH, e.g. /island; default none).
    pub base_path: String,
    /// The page origins a viewer's socket may come from (RELAY_ORIGINS, comma-separated; empty: any).
    pub origins: Vec<String>,
    /// Viewers at once (RELAY_MAX_VIEWERS, default 5000) and from one address (RELAY_MAX_PER_IP, default 64: a phone
    /// network puts many people behind one address; an IPv6 address counts by its /64).
    pub max_viewers: usize,
    pub max_per_ip: usize,
    /// New sockets one address may open a minute, after a first burst of RELAY_MAX_PER_IP (RELAY_CONNECTS_PER_MINUTE,
    /// default 60): each new socket is handed the whole island.
    pub connects_per_minute: usize,
    /// Proxies of ours in front (RELAY_TRUSTED_PROXIES; deploy/: Caddy, 1): the viewer's address is then read from
    /// the X-Forwarded-For they add.
    pub trusted_proxies: usize,
    /// Frames a viewer may fall behind before it is handed the whole island again (RELAY_BUFFER, default eight
    /// seconds of the stream: 80 at ten updates a second).
    pub buffer: usize,
    /// Updates kept for viewers coming back from a gap (RELAY_RESUME_FRAMES, default ten seconds of the stream: 100).
    /// One further back than the whole island is big is handed the island instead.
    pub resume_frames: usize,
    /// Updates a second to viewers (RELAY_UPDATES_PER_SECOND, 0 to 60, default 10). The world sends 31; the relay
    /// gathers what they did into one (gather.rs), and the page draws between them, as far behind as two gaps. 0: one
    /// update for each of the world's, still rounded and without what viewers already hold.
    pub updates_per_second: usize,
    /// How often everyone hears how many watch.
    pub status_every: Duration,
    /// How often a viewer's socket is pinged (20 s), and how long a viewer may stay silent before it is let go (60 s:
    /// three pings unanswered, the phone is gone).
    pub ping_every: Duration,
    pub silent_for: Duration,
    /// A send to a viewer this slow (10 s) means its buffers are full: it is let go.
    pub send_within: Duration,
    /// The world sends at least every fifth tick (about 165 ms) even when nothing moves: this long silent (10 s), it
    /// is gone.
    pub world_quiet: Duration,
}

impl Config {
    pub fn from_env() -> Result<Config, String> {
        let var = |name: &str, default: &str| std::env::var(name).unwrap_or_else(|_| default.to_string());
        let number = |name: &str, default: usize| -> Result<usize, String> {
            std::env::var(name).map_or(Ok(default), |v| v.trim().parse().map_err(|_| format!("{name} is not a number")))
        };
        let token = std::env::var("RELAY_SPECTATOR_TOKEN").or_else(|_| std::env::var("WORLD_SPECTATOR_TOKEN")).unwrap_or_default();
        let origins = var("RELAY_ORIGINS", "").split(',').map(str::trim).filter(|o| !o.is_empty()).map(String::from).collect();
        let updates_per_second = number("RELAY_UPDATES_PER_SECOND", 10)?;
        if updates_per_second > MOST_UPDATES_PER_SECOND {
            return Err(format!("RELAY_UPDATES_PER_SECOND is at most {MOST_UPDATES_PER_SECOND} (the world sends 31)"));
        }
        // The frames a viewer may lag and come back over, as seconds of the stream at its rate (the world's 31 at 0).
        let rate = if updates_per_second == 0 { 31 } else { updates_per_second };
        Ok(Config {
            listen: var("RELAY_LISTEN", "127.0.0.1:8082"),
            upstream: var("RELAY_UPSTREAM", "ws://127.0.0.1:8080/spectate/ws"),
            token: token.trim().to_string(),
            base_path: var("RELAY_BASE_PATH", "").trim_end_matches('/').to_string(),
            origins,
            max_viewers: number("RELAY_MAX_VIEWERS", 5000)?,
            max_per_ip: number("RELAY_MAX_PER_IP", 64)?,
            connects_per_minute: number("RELAY_CONNECTS_PER_MINUTE", 60)?,
            trusted_proxies: number("RELAY_TRUSTED_PROXIES", 0)?,
            buffer: number("RELAY_BUFFER", 8 * rate)?,
            resume_frames: number("RELAY_RESUME_FRAMES", 10 * rate)?,
            updates_per_second,
            status_every: Duration::from_secs(5),
            ping_every: Duration::from_secs(20),
            silent_for: Duration::from_secs(60),
            send_within: Duration::from_secs(10),
            world_quiet: Duration::from_secs(10),
        })
    }
}

pub struct App {
    config: Config,
    hub: Arc<Hub>,
    seats: Arc<Seats>,
}

/// Follow the world and serve viewers on `listener` until `shutdown` completes.
pub async fn run(config: Config, listener: TcpListener, shutdown: impl Future<Output = ()> + Send + 'static) -> std::io::Result<()> {
    let hub = Arc::new(Hub::new(config.buffer, config.resume_frames, config.updates_per_second > 0));
    if config.updates_per_second > 0 {
        let gathered = hub.clone();
        // from_env allows 1 to 60; a Config made in code is held to a period of at least a millisecond.
        let every = Duration::from_millis(1000 / config.updates_per_second.min(1000) as u64);
        tokio::spawn(async move {
            let mut ticker = tokio::time::interval(every);
            ticker.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
            loop {
                ticker.tick().await;
                gathered.flush();
            }
        });
    }
    tokio::spawn(upstream::follow(hub.clone(), config.upstream.clone(), config.token.clone(), config.world_quiet));
    let news = hub.clone();
    let every = config.status_every;
    tokio::spawn(async move {
        let mut ticker = tokio::time::interval(every);
        loop {
            ticker.tick().await;
            news.tell_status();
        }
    });
    let base = config.base_path.clone();
    let seats = Arc::new(Seats::new(config.max_viewers, config.max_per_ip, config.connects_per_minute));
    let app = Arc::new(App { config, hub, seats });
    let router = Router::new()
        .route(&format!("{base}/spectate/ws"), get(viewer::stream))
        .route(&format!("{base}/relay/status"), get(status))
        .route("/metrics", get(metrics))
        .with_state(app);
    axum::serve(listener, router.into_make_service_with_connect_info::<SocketAddr>())
        .with_graceful_shutdown(shutdown)
        .await
}

/// GET `/relay/status`: the world, the stream, and how many watch (for the screen's watcher count and the admin).
async fn status(State(app): State<Arc<App>>) -> Json<serde_json::Value> {
    Json(app.hub.report())
}

/// GET `/metrics`: Prometheus' text format, scraped by the monitoring inside Compose's network (deploy/monitoring).
/// Like the status, Caddy never passes it on from outside.
async fn metrics(State(app): State<Arc<App>>) -> ([(axum::http::HeaderName, &'static str); 1], String) {
    ([(axum::http::header::CONTENT_TYPE, "text/plain; version=0.0.4")], app.hub.metrics(app.config.max_viewers))
}
