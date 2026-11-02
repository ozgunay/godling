//! The relay's one connection to the world's spectator stream, kept up for as long as the relay runs. The world is
//! the only one that reads the game for viewers now; whatever their number, it sees one spectator.
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use futures_util::StreamExt;
use serde_json::Value;
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::HeaderValue;
use tokio_tungstenite::tungstenite::Message;

use crate::hub::Hub;

/// The world sends at least every fifth tick (about 165 ms) even when nothing moves: this long silent, it is gone.
const QUIET: Duration = Duration::from_secs(10);
const RETRY_FIRST: Duration = Duration::from_millis(500);
const RETRY_MOST: Duration = Duration::from_secs(10);

/// Follow the world's stream at `url` for good: connect, hand everything to the hub, and on any end tell the hub the
/// world is down and connect again, waiting longer each time (with jitter), up to RETRY_MOST.
pub async fn follow(hub: Arc<Hub>, url: String, token: String) {
    let mut wait = RETRY_FIRST;
    loop {
        match watch(&hub, &url, &token).await {
            Ok(true) => wait = RETRY_FIRST, // it brought an island: a later drop starts the waits over
            Ok(false) => {}
            Err(err) => eprintln!("[relay] the world's stream: {err}"),
        }
        hub.world_lost();
        tokio::time::sleep(jittered(wait)).await;
        wait = (wait * 2).min(RETRY_MOST);
    }
}

/// One connection, until it ends: Ok(true) if it brought an island.
async fn watch(hub: &Hub, url: &str, token: &str) -> Result<bool, String> {
    let mut request = url.into_client_request().map_err(|err| err.to_string())?;
    if !token.is_empty() {
        // In a header, not the address: it stays out of the world's request logs.
        let value = HeaderValue::from_str(token).map_err(|_| "the spectator token is not a valid header".to_string())?;
        request.headers_mut().insert("X-Spectator-Token", value);
    }
    let (mut stream, _) = tokio_tungstenite::connect_async(request).await.map_err(|err| err.to_string())?;
    let mut seen = false;
    loop {
        let message = match tokio::time::timeout(QUIET, stream.next()).await {
            Err(_) => return Err("the world went quiet".into()),
            Ok(None) => return Ok(seen),
            Ok(Some(Err(err))) => return Err(err.to_string()),
            Ok(Some(Ok(message))) => message,
        };
        let text = match &message {
            Message::Text(text) => text.as_str(),
            Message::Close(_) => return Ok(seen),
            _ => continue, // the library answers pings itself
        };
        let Ok(Value::Object(fields)) = serde_json::from_str::<Value>(text) else { continue };
        if let Some(error) = fields.get("error") {
            return Err(format!("the world says {error}")); // "World ended": it is stopping
        }
        match fields.get("type").and_then(Value::as_str) {
            Some("spectator_delta") => hub.update(text, Some(&fields)),
            Some(_) => hub.update(text, None), // chat, speech, audio: passed on in their place
            None => seen |= hub.world_seen(Value::Object(fields)), // the whole island, first on every connection
        }
    }
}

/// Between half the wait and all of it, so a world restart does not bring every relay back at the same instant.
fn jittered(wait: Duration) -> Duration {
    let nanos = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.subsec_nanos()).unwrap_or(0);
    wait.mul_f64(0.5 + f64::from(nanos % 1000) / 2000.0)
}
