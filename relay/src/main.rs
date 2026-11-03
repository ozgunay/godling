//! `godling-relay`: the island's stream relay (ADR-015). Configured by its environment; see `relay/README.md`.
use godling_relay::{run, Config};

const HELP: &str = "godling-relay: one connection to the world's spectator stream, the same updates to every viewer.

Set by the environment:
  RELAY_LISTEN            where viewers connect (default 127.0.0.1:8082)
  RELAY_UPSTREAM          the world's stream (default ws://127.0.0.1:8080/spectate/ws)
  RELAY_SPECTATOR_TOKEN   the world's spectator token (or WORLD_SPECTATOR_TOKEN)
  RELAY_BASE_PATH         served under this path, as the world is (e.g. /island)
  RELAY_ORIGINS           page origins viewers may connect from, comma-separated (default: any)
  RELAY_MAX_VIEWERS       viewers at once (default 5000)
  RELAY_MAX_PER_IP        viewers from one address, an IPv6 /64 as one (default 64)
  RELAY_CONNECTS_PER_MINUTE  new sockets one address may open a minute after that burst (default 60)
  RELAY_TRUSTED_PROXIES   proxies of ours in front, whose X-Forwarded-For is believed (default 0)
  RELAY_BUFFER            frames a viewer may fall behind before a resync (default: eight seconds' worth)
  RELAY_RESUME_FRAMES     updates kept for viewers coming back (default: ten seconds' worth)
  RELAY_UPDATES_PER_SECOND  updates a second to viewers, the world's gathered (0 to 60, default 10; 0: one for each)

GET /metrics gives the counts in Prometheus' format; GET <base>/relay/status, the world and the viewers as JSON.";

#[tokio::main]
async fn main() {
    if std::env::args().any(|arg| arg == "--help" || arg == "-h") {
        println!("{HELP}");
        return;
    }
    let config = Config::from_env().unwrap_or_else(|err| {
        eprintln!("godling-relay: {err}");
        std::process::exit(2);
    });
    if config.token.is_empty() {
        eprintln!("[relay] no spectator token set: the world will refuse the stream unless it needs none");
    }
    let listener = tokio::net::TcpListener::bind(&config.listen).await.unwrap_or_else(|err| {
        eprintln!("godling-relay: cannot listen on {}: {err}", config.listen);
        std::process::exit(1);
    });
    println!(
        "[relay] following {} for at most {} viewers; they connect to ws://{}{}/spectate/ws",
        config.upstream, config.max_viewers, config.listen, config.base_path
    );
    if let Err(err) = run(config, listener, stopped()).await {
        eprintln!("godling-relay: {err}");
        std::process::exit(1);
    }
}

/// Ctrl+C, or the launcher's SIGTERM.
async fn stopped() {
    let interrupt = tokio::signal::ctrl_c();
    #[cfg(unix)]
    {
        let mut term = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()).expect("a SIGTERM handler");
        tokio::select! {
            _ = interrupt => {}
            _ = term.recv() => {}
        }
    }
    #[cfg(not(unix))]
    let _ = interrupt.await;
}
