# ADR-015: The island's stream relay, a page that reconnects, and a Live badge that tells the truth

Date: 2026-11-02. Status: built and tested against a stand-in world, a real scratch world and a real browser. Not yet built as a Docker image (Docker's engine does not answer on this machine).

## Why
There is exactly one WebSocket: Clawblox's spectator stream (`/spectate/ws`). Every viewer's island frame opened its own, and three things were wrong with that:
- **No reconnect.** When the socket closed (a world restart, a network blip, a phone asleep), the island froze on "Disconnected" until a reload. Even "Missing base state; reconnecting" only closed the socket.
- **The badge could lie.** The screen's Live/Offline came from the guest panel, so it said Live over a frozen island.
- **Every viewer cost the world.** Each socket keeps its own copy of the island and reads the game 30 times a second to work out its own changes. Measured on a scratch world (Godling walking, one meteor):
  - the first message is the whole island: 276 KB (11 KB gzipped), 712 entities;
  - then 30 deltas a second of about 2.5 KB: **75 KB/s per viewer**, about 0.6 Mbit/s;
  - a delta moves only about 12 entities, but each rotation is a 3x3 matrix of 8-digit numbers (most of the bytes), and the whole player list (500 B) goes along every time, though it changed in 27% of them.

  At 1,000 viewers that is 600 Mbit/s, and 1,000 diff loops inside Godling's world competing with the simulation.

The security review (ADR-014) added one more: every viewer's link carried the spectator token.

## Decisions (yours)
1. **A relay in front of the world**, as esports spectator feeds do (GOTV relays): the world streams to one relay, the relay serves everyone.
2. **In Rust**, after a benchmark on this machine (below): axum and tokio, the versions Clawblox builds with.
3. **Encryption is TLS at the edge** (Caddy, `wss://`); the stream itself is public, so nothing more.

## The benchmark (Python websockets against Rust)
The relay's own job: send the same message to N viewers 15 times a second for 15 s, one server process, the viewers in another (every message arrived, counted).

| Server | Viewers | Message | CPU per message | Share of one core | Late updates |
|---|---|---|---|---|---|
| Python (asyncio) | 1,000 | 2.6 KB | 6.2 µs | 9% | 0 |
| Python (uvloop) | 1,000 | 2.6 KB | 6.1 µs | 9% | 0 |
| Python + per-socket compression | 1,000 | 2.6 KB | 32.2 µs | 47% | 0 |
| Rust, 1 thread | 1,000 | 2.6 KB | 4.9 µs | 7% | 0 |
| Python (uvloop) | 5,000 | 2.6 KB | 6.6 µs | 48% | 0 |
| Rust, 1 thread | 5,000 | 2.6 KB | 4.9 µs | 36% | 0 |
| Python (uvloop) | 10,000 | 0.75 KB | 6.5 µs | 93% | 148 of 224 |
| Rust, 1 thread | 10,000 | 0.75 KB | 4.6 µs | 66% | 0 |
| Rust, 4 threads | 10,000 | 2.6 KB | 10.6 µs | 154% (of 4 cores) | 0 |

- Most of a message's cost is the kernel's (one send per viewer); Python adds about 1.5 µs. Cost follows the number of messages, not their size.
- The difference that decided it: one Python process is one core and falls behind near 8,000 viewers; Rust spreads over cores in one process.
- Also: tokio's broadcast channel reports a slow viewer (`Lagged`), where Python's `broadcast()` has no backpressure; Rust is memory-safe for a parser that faces the internet; Clawblox is Rust.
- Rust's tungstenite has no per-message deflate. That is the better design for fan-out anyway: compress each update once, for everyone (later).

## Encryption
- **`wss://` only, ended at Caddy**: certificates by itself, TLS 1.3, HSTS. What it protects is mostly integrity (nobody on the path can inject a fake blast, pop-up or note), and the personal parts (cookies, the CSRF token). The island itself is public, so end-to-end encryption would cost and protect nothing.
- **Inside the server**: plain traffic between Caddy, the relay and the world, on loopback and Compose's network. A hop to another machine would get WireGuard or mutual TLS.
- **No token in public links.** Browsers cannot set headers on a WebSocket, so a token ends up in the address, and addresses land in logs. The relay holds the spectator token (sent to the world in a header); Caddy adds it to the page's other requests.
- **Compression and secrets**: the broadcast carries notes and names (attacker-written) but no secrets, so compression is safe on it (CRIME/BREACH need both). Rule: no per-viewer secret ever goes on the shared stream.
- **Cost**: TLS encrypts at gigabytes a second per core; 10,000 viewers at 5 KB/s is 50 MB/s. Reconnect storms (handshakes) are the expensive part: jitter and TLS session resumption.

## What was built
### The relay (`relay/`, `godling-relay`)
- **One connection to the world.** It keeps the island by applying every delta exactly as Clawblox's page does (`applySpectatorDelta`, with v1's terrain). Godling's own eyes (the headless capture) still go to the world directly.
- **The same frames for everyone, made once.** Each world message gets its place, `relay_seq`, spliced into it without parsing it again; a whole island carries `relay_epoch` too. Clawblox's page ignores fields it does not know, so it works through the relay unchanged.
- **Late viewers** get the whole island at the latest place, built at most once per place.
- **Returning viewers** (`?epoch=&since=`) get only what they missed, from the last 300 updates (ten seconds). Another epoch, or a place no longer held: the whole island.
- **A world restart** reaches viewers on the socket they hold: `{"type":"relay","world":"down"}`, then the new island with a new epoch.
- **Slow viewers**: a viewer 256 frames behind gets the whole island again; after three, it is let go to reconnect.
- **Limits**: viewers in all (5,000) and per address (behind Caddy, from its X-Forwarded-For), an Origin list (any case), a 4 KB cap on what a viewer sends, pings and a 60 s silence limit, a 10 s send limit.
  - Per address, after the PR #20 review: 64 sockets, not 8, since a phone network puts many people behind one address; an IPv6 address counts by its /64, or one home would be countless addresses.
  - New sockets per address: a burst of 64, then 60 a minute. Each new socket is handed the whole island (about 276 KB), so opening and closing them in a loop would make the relay send that over and over. A page back from a gap mostly resumes instead.
- **`/relay/status`**: the world, epoch, place, tick, entities, viewers (an honest watcher count), resumes, resyncs.

### The page (`patches/v3-stream-reconnect.patch`, Clawblox's `main.js`)
- Reconnects by itself: a random wait up to a cap that doubles (0.5 s to 30 s), starting over after ten good seconds.
- A stream silent 5 s (15 s while the relay says the world is down) is dropped and reopened: phones and mobile networks lose sockets without a close.
- Hidden half a minute, the page lets its socket go and reopens it when shown; coming back online reopens it at once.
- Through the relay it resumes from its last epoch and place. "Missing base state" now really reconnects, from the whole island.
- `?stream_port=` points the socket at a relay on the page's own host (a local run), never another host.

### The renderer and the screen
- A whole island clears the renderer's easing buffer, so nothing slides across a gap.
- The renderer passes the stream's state to the screen (`onConnection` → `godling-stream`). The badge reads Live, Connecting, Reconnecting, Restarting or Paused from the island itself; the panel's word stands only until the island has spoken.

### Running it
- Locally: `run_godling.py --relay 8082` starts the relay with the world's token and points the screen's island at it.
- Deployed: the island image applies v3, and the relay is a Compose service of its own (`deploy/Dockerfile.relay`: one binary, its own user, its own container). Caddy sends `/island/spectate/ws` to the relay and adds the token to the page's other requests; `/island/spectate` (a whole island per call, which the page never asks for) is closed. The public link is `https://<island domain>/island`.
  - Its own container since the PR #20 review: the relay is the part of the island the whole internet talks to. In the island's container it ran as the same user as the world and the mind, and could have read their keys (the agent key, the operator token, the DeepSeek key) from `/proc`. Now it holds the spectator token and nothing else.
- The admin's log viewer shows `relay.log`.

## Tests
- **The relay**: 12 unit tests (applying deltas, places and epochs, the resume window, watcher counts, seats, the address behind Caddy) and 7 end to end over real sockets with a stand-in world: a late viewer holds what the early one does, a returning viewer catches up without the whole island, an unknown place gets the whole island, a world restart reaches viewers on the same socket, chat passes through untouched, Origin and per-address limits, a wrong token. Clippy clean with warnings as errors.
- **Against a real world** (scratch, port 8190, Godling walking): a viewer straight to the world and one through the relay held identical islands on all 385 ticks both saw; one joining 8 s late, on all 230. No gaps in the places; the relay added no latency (arrivals a median 5 ms earlier, its own 33 ms beat). Restarting the world: the relay viewer was told it was down and handed the new island (709 entities) on the same socket.
- **In a browser** (the viewers' screen on 8192, its island through the relay on 8191):
  - the relay stopped: the badge read Reconnecting; started again: back to Live, no reload;
  - the world restarted: Live, Restarting at 0.4 s, Live at 5.8 s, no reload;
  - the page's socket dropped while the relay kept its epoch (headless Chromium): it came back with `epoch=…&since=3575`, and the relay counted a resume, not a whole island.
- **The image's recipe**: all four patches apply to a fresh clone at `8be90a0` in the Dockerfile's order; the relay exits 3 ms after SIGINT with a viewer connected.
- **Not tested**: building the images and Caddy's routes, as in ADR-013 (no Docker engine here).

## Next
- **Bandwidth** (the real bill): send viewers 15 updates a second from the relay's own copy (the renderer then draws 150 ms behind), the player list only when it changes, then a compact format (quaternions, rounded positions) and one compression per update for everyone. Target: under 5 KB/s per viewer. *Built in ADR-017, at ten a second and 200 ms: 5.0 KB/s.*
- **The screen's live data on the same socket**: the relay fetches the shared part of the status once a second and pushes it, retiring the 1.5 s polling of every viewer; its viewer count replaces the panel's.
- **Tickets**, if hotlinking or abuse shows up: short-lived, one use, from the site.
