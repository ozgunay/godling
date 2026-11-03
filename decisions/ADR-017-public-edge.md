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
- **Gzipped islands**: a page that asks (`?gz=1`) gets the whole island as one gzipped binary message, made once for everyone: 276 KB becomes about 17. Updates stay text.
- **`/metrics`** in Prometheus' format: viewers and the cap, the world up or down, connections, refusals by reason (origin, busy, address, rate), viewers let go by reason, resumes, resyncs, bytes and messages sent. Not reachable from outside.

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

## What the stream costs, for later
Measured on the deployment's own stream (30 s, 917 updates through Caddy and the relay), beside ADR-016's load test, which found the live stream is most of what a viewer costs:

| The updates, a viewer | KB/s |
|---|---|
| As sent (JSON, 31 a second) | 84 |
| Gzipped once per update, the same bytes for everyone | 31 |
| permessage-deflate (a compressor per viewer, keeping its context) | 10 |
| Rounded to 0.001, then gzipped once per update | 24 |
| Rounded to 0.001, then permessage-deflate | 4.2 |

Gzipping once is nearly free (the relay already does it for the whole island, and the page inflates any gzipped message in order); per-viewer deflate saves most, at a compressor's CPU and memory for every viewer. Not changed here.

## Not done here
- **A real server**: `deploy/check.sh` from another machine, with DNS, Let's Encrypt and Cloudflare. The local run uses Caddy's own CA on `*.localhost`.
- **Cloudflare itself**: an account, the DNS, the firewall and Turnstile's keys are yours to set up (`deploy/README.md`).
- **The outside review**: people, not code. The gate holds live payments until then.
- **GitHub settings**: turn on Dependabot security updates and private vulnerability reporting in the repository's settings.
