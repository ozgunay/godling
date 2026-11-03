# ADR-017: The public edge: limits that hold, Cloudflare in front, monitoring with alerts, dependency audits, and a review before real money

Date: 2026-11-02. Status: built; tested locally end to end (the deployment's images under Docker, with TLS, routes, the stream, alerts by email). Not yet run on a real server.

## Why
After ADR-015 the stream path scored about 7 out of 10: strong against snooping and tampering, weakest at staying up under a deliberate flood, and the deployment had never run. The gaps:
1. **IPv6 made the per-address limit useless**: the relay counted exact addresses, and one IPv6 subscriber holds a /64 (billions of them).
2. **Nothing paced reconnecting**: each new connection was handed the whole island (276 KB), so a script connecting and dropping in a loop made the server send megabytes a second.
3. **No front against floods**, **no monitoring**, **no dependency audits**, and **no outside review** before real money.

## Decisions (yours)
1. Fix the two relay gaps, build the images and check the routes and TLS (towards 8.5).
2. Add a DDoS-protecting front, monitoring with alerts (connection counts, resyncs, bandwidth), automatic dependency audits, and an outside review before real money (towards 9).
3. **Cloudflare**: yes, in front of both names, for floods, hiding the server and sign-up bots. Godling's own limits stay: Cloudflare is the outer wall, not the only one.

## What was built
### The relay (`relay/`)
- **Address blocks**: an IPv6 address counts by its /64; IPv4 inside IPv6 counts as that IPv4 address.
- **Pacing**: per block, at most 64 sockets at once (`RELAY_MAX_PER_IP`: a household or an office behind one address) and new sockets from a bucket of 64 that refills at 60 a minute (`RELAY_CONNECTS_PER_MINUTE`); 5000 viewers in all (`RELAY_MAX_VIEWERS`). Refused with 429 (or 503 when full) and `Retry-After`, and counted by reason. A page coming back from a gap mostly resumes, and pages back off on their own, so a relay coming back is spread out. Floods from many addresses are Cloudflare's to stop.
- **Gzipped islands**: a page that asks (`?gz=1`) gets the whole island as one gzipped binary message, made once for everyone: 276 KB becomes about 17.
- **Smaller updates** (below, "The live stream made smaller"): ten a second, each doing what the world's three did; rotations rounded to 0.001; nothing every viewer already holds; gzipped once for everyone. 74 KB a second a viewer becomes 3.1.
- **`/metrics`** in Prometheus' format: viewers and the cap, the world up or down, connections, refusals by reason (origin, busy, address, rate), viewers let go by reason, resumes, resyncs, bytes and messages sent. Not reachable from outside.

### The renderer (`world/renderer`)
- Its own state buffer (`buffer.js`): rotations turned between states, everything else from the older state until the newer one's moment, drawn two of the stream's measured gaps behind (200 ms at ten a second, 100 straight from the world), states kept for a time.
- Check hooks beside the others: `__godlingRenderer.state()`, the island as last drawn, and `delay()`.

### The page (`patches/v3`)
- Asks for and inflates gzipped islands, keeping messages in order.
- Takes a message's arrival as the heartbeat, and a page that was itself stalled (a long frame on a slow phone) no longer reconnects for "no news". Found by the browser test below: two software-rendered tabs at once made it reconnect twice.

### Cloudflare-ready (`deploy/Caddyfile`, the site)
- Caddy believes `CF-Connecting-IP` only from the ranges in `GODLING_PROXY_RANGES` (Cloudflare's), and hands every app exactly one address, the viewer's: the site and the relay keep trusting one proxy, and a client's own `X-Forwarded-For` counts for nothing.
- **Turnstile on sign-up** (`apps.users.turnstile`): on when its two keys are set; fake accounts are what spam notes and farm welcome credits.
- The steps (DNS proxied, Full (strict), the provider's firewall open to Cloudflare only, since Docker opens published ports past ufw) are in `deploy/README.md`.

### Monitoring (`deploy/monitoring`, three services)
- Prometheus reads the relay, Caddy (its metrics on an internal port) and the server (node exporter) every 15 s, 30 days kept.
- Twelve alerts, unit-tested with promtool: the relay down, the world's stream down, viewers near the cap, connections refused in numbers, viewers falling behind, slow viewers let go, bandwidth above 20 MB/s, over 300 GB of stream a day, server errors above 5%, the disk, memory, CPU.
- Alertmanager emails them through the site's SMTP to `GODLING_ALERT_EMAIL` (its config written from the environment at start; the password through a file, so any character works).
- Their pages listen on the server's loopback only (an SSH tunnel).

### Dependencies (`.github/`, `patches/v4`)
- **Checks** on every pull request, beside the test suites (`tests.yml`): the relay's clippy, and the deployment's configs as their own tools read them (Caddy, promtool, amtool, Compose). Every workflow's actions pinned to commits.
- **A dependency audit** every Monday and when a dependency changes: `cargo audit` on the relay and on the world as the image builds it, `pip-audit` on the site, `npm audit` on the renderer. **Dependabot** proposes updates weekly, grouped.
- The first audit found **34 known vulnerabilities in Clawblox's lock file** (TLS, HTTP/2, QUIC, tar, zstd; pinned months ago). `patches/v4` updates only those crates within what Clawblox allows: 29 gone; the 5 left do not reach the island and are ignored by name with their reasons (`patches/clawblox-audit-ignore.txt`, `patches/DEPS-001`).

### Before real money
- **The money gate**: with live Stripe keys the site does not start until `GODLING_SECURITY_REVIEW` names an outside review.
- **The brief** for the reviewer, and the go-live checklist: `deploy/security-review.md`. Reporting a vulnerability: `SECURITY.md`.
- **`deploy/check.sh`**: the deployment from outside (HTTPS, certificates, routes, the stream's door, ports), for the reviewer and for every change.

## Tests
- **The relay**: 20 unit tests, 5 against a scripted world, 18 end to end; among them, the whole island gzipped for a page that asks, an address that keeps reconnecting refused for a while, and `/metrics` counting what happened. Clippy with warnings as errors.
- **The world on `patches/v4`**, through the relay and straight: identical islands on all 343 ticks both saw, and two relay viewers identical on all 366 places in the stream.
- **The deployment under Docker**, end to end: `deploy/check.sh` from another container (55 checks pass; the three others are this machine's own ports), the viewers' screen in headless Chromium through Caddy and the relay, all five Prometheus targets up, and RelayDown emailed two minutes after the relay was stopped, then its all-clear. Details in `deploy/README.md` "Tested so far".
- **The configs** as their own tools read them: `caddy validate` (with and without Cloudflare's ranges), `promtool check config` and the alerts' unit tests, `amtool check-config`, `docker compose config`, actionlint and shellcheck.
- **The site**: 175 tests, among them Turnstile's (5) and the money gate's.
- **The smaller stream**: the relay's tests (29 unit, 5 of the program, 19 end to end), among them gathered deltas leaving the island exactly as the deltas one by one (40 random streams, gathered 2, 3 and 5 at a time), the players sent only when they change, chat after the deltas before it, and 31 world updates a second reaching a viewer as about ten, gzipped. The renderer's 102 tests. The measurements above.

## The live stream made smaller
ADR-016's load test found the live stream is most of what a viewer costs, and ADR-015 had planned for it ("Next": fewer updates, the player list only when it changes, rounded places, one compression per update for everyone; under 5 KB/s a viewer). Built in the relay (`relay/src/gather.rs`, `hub.rs`, `island.rs`) and the renderer (`world/renderer/src/buffer.js`), with no change to the world or Clawblox's page:
- **Ten updates a second** (`RELAY_UPDATES_PER_SECOND`, 0 to 60; 0 sends one for each of the world's). The world sends 31; the relay gathers what they did into one, as the page would have applied them one by one: the latest place of each thing that moved, what was added and removed, the latest players, sounds and terrain (a later value of the wrong kind never replaces an earlier one), every event once. Something removed and back, or added and gone, within one gathering goes out over two updates, so it is seen as the page would have seen it. The relay's own island takes each update, so a late viewer holds what the others do.
- **Only what viewers do not already hold**: a field (players, sounds, game status, terrain) or a place or rotation equal to what the relay's island holds is left out. The world sends its players with every delta, and a rotation whenever its f32 moved at all (the fish are re-aimed every Heartbeat), which after rounding is mostly not.
- **Rounded**: rotations and the players' numbers to 0.001, as the replay's chunks keep rotations and attributes; positions come from the world at 0.01. The whole island is rounded the same way when the relay receives it.
- **Gzipped once per update, for everyone**, for pages that ask (`gz=1`; patched Clawblox's page does), when that makes it smaller; passed messages over 1 KB (a chunk of speech) too.
- **Chat, speech and audio** go out right after the next update, so they never cut one short (each would have meant one more, unevenly spaced).
- **The renderer's own state buffer** (`buffer.js`), in place of Clawblox's, which eased positions only and showed everything else from the newer state: rotations are turned between the two states (slerp); what is there, attributes and a character's state are the older state's until the drawn moment reaches the newer one (so a blast shows when the falling stone is drawn arriving, not a whole gap before); the delay is two of the stream's measured gaps, at least 100 ms (200 at ten a second, 100 straight from the world or in a fast replay); states are kept for a time, not by count, so a fast replay still has two to draw between.
- **Dust** judges a landing by how far a piece fell, not by the speed it is seen at (an average over the stream's gap, which missed short drops).
- **Limits in seconds of the stream**: a viewer may fall eight seconds behind before it is handed the island again (`RELAY_BUFFER`, 80 at ten a second), and one coming back catches up on up to ten seconds (`RELAY_RESUME_FRAMES`, 100), unless what it missed weighs more than the whole island: then the island.

What a viewer receives, on the deployment under Docker, the world as before (40 s each):

| | Updates a second | KB/s |
|---|---|---|
| Before: every world delta, as JSON | 31 | 74 |
| Ten a second, rounded, players when changed (first version) | 10 | 13.4 as text, 5.0 gzipped |
| Now: also nothing viewers hold | 10 | 6.5 as text, **3.1 gzipped** |

The whole island on connecting: 16 KB gzipped (275 as text).

**Motion.**
- Positions: Godling walking, where he is drawn on every frame. In a browser (headless Chromium): no frame mid-walk on which he stood still, at 31 updates with 100 ms, ten with 100 ms, and ten with 200 ms. Clawblox's snapshot buffer replayed at 60 fps on recorded arrival times, with a phone's 4G added (most updates 20 to 60 ms on their way, one in twenty 100 to 250 ms):

  | | Standing still | Spread (lower is smoother) |
  |---|---|---|
  | 31 a second, 100 ms (before) | 0.5% | 1.17 |
  | Ten a second, 100 ms | 1.4% | 0.75 |
  | Ten a second, 200 ms | 0.1% | 0.77 |

- Rotations (found by the review: nothing turned them between states, so at ten a second a turn of Godling's came as snaps of up to 57°): his facing recorded from the relay over 60 s of walking and turning at ten a second, drawn at 60 fps. Through Clawblox's buffer he stood still on 155 of 173 frames mid-turn, with steps up to 75°; through the new one, on none of 256, the biggest step 12.6°. In headless Chromium (13 frames a second), the biggest step went from 124° to 67° (the frame rate's own limit for a turn of 10 rad/s).
- A replay at 4x (pushes on two draws of three): the new buffer eases every frame (Clawblox's, with 200 ms and eight states, stood still on a third of them).

**Compression per viewer** (permessage-deflate) is left out. On the stream before "nothing viewers hold" it would have made 5.0 KB/s about 1.8, for 0.4 of a core and up to 100 KB of memory a viewer at 5000 viewers; but the relay's WebSocket library (tungstenite, under axum) does not offer it, so it would mean another library for the viewers' side, and a cost for every socket held open, which is what a flood holds. At 3 KB/s, 1000 viewers around the clock are 8 TB a month; worth it only when the traffic bill says so.

**Reviewed** (PR #45, at the most thorough level: nine reviewers on separate angles, each finding checked by another): fifteen findings, all addressed here. The ones not reachable with today's world (an id removed and back within 100 ms, things living under 100 ms, values of the wrong kind, a mistyped update rate) are guarded anyway.

## Not done here
- **A real server**: `deploy/check.sh` from another machine, with DNS, Let's Encrypt and Cloudflare. The local run uses Caddy's own CA on `*.localhost`.
- **Cloudflare itself**: an account, the DNS, the firewall and Turnstile's keys are yours to set up (`deploy/README.md`).
- **The outside review**: people, not code. The gate holds live payments until then.
- **GitHub settings**: turn on Dependabot security updates and private vulnerability reporting in the repository's settings.
