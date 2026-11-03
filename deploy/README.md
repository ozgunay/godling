# Running Godling on one server

Docker Compose, as AgentOp runs (ADR-013, ADR-014, ADR-015, ADR-017, ADR-018). Eight services, three for the monitoring, and the backups:
- **`postgres`:** the site's database.
- **`redis`:** the shared cache (sign-in rate limits, the island's news, who is watching) and the worker's queue. It keeps nothing that matters across a restart.
- **`site`:** accounts, credits, moderation, the admin and the viewer screen (gunicorn with threads, whitenoise for the admin's files).
- **`worker`:** the site's Celery worker. It takes powers to the island one at a time, so no web request waits on the island.
- **`mailer`:** a second Celery worker, for the "mail" queue only. It emails viewers' feedback to the inbox the site rules name, so a slow mail server never holds back a power.
- **`island`:** the world (Clawblox, built from source with `patches/`), Godling's mind and the guest panel, started by `mind/run_godling.py`. The run lives in a volume, so it continues across restarts: Godling's memory, and the island itself. Every five minutes and when the container stops, the launcher saves what stands (`island-save.json`); on the next start the world puts it back (ADR-013).
- **`relay`:** the island's stream relay (`relay/`, `Dockerfile.relay`), which every viewer's socket reaches: one connection to the world, the same updates to everyone. A container of its own, holding the spectator token and nothing else, so the part of the island the whole internet talks to is kept apart from Godling's keys (the agent key, the operator token, the DeepSeek key).
- **`caddy`:** HTTPS for both domains. The site's domain goes to the site; the island's domain goes to the world (watching side only), its stream to the relay, and its replay chunks (`/replay/chunks/…`) to files in their own volume (`replay_chunks`, mounted inside the island's run), the only part of the run Caddy can read.
- **`prometheus`, `alertmanager`, `node-exporter`:** the monitoring (below): what the relay, Caddy and the server report, and an email when something is wrong.
- **`backup`:** encrypted snapshots of the database and the run, in a bucket off the server (below). `restore` is never started with the rest: it brings a snapshot back when asked.

## What the public can reach
- **The site**, at `https://<domain>/`.
- **The island's spectator page**, on its own origin: `https://<island domain>/island`. Only the site may frame it (`frame-ancestors`), and nothing on it can reach the site's cookies.
  - Caddy passes only what watching needs: the page, its files and chat to the world, and the stream to the relay (ADR-015). The world's agent API (`join`, `input`, `observe`, `reset`, `chat`, `snapshot`…) and its whole-island `/spectate` answer 404 from outside.
  - The stream relay is the world's one spectator: every viewer's socket is the relay's, from the island's own page only. From one address it takes at most 64 sockets (an IPv6 /64 counts as one address; a phone network puts many people behind one), and new ones at a steady pace after a first burst, since each is handed the whole island. However many watch, the world works out its changes once.
  - Inside Compose's network the world still asks for its keys: joining takes the agent key the launcher makes at every start, and the snapshot takes the operator token (`patches/v2`, ADR-014). The spectator token stays on the server: Caddy adds it to the page's requests, and the relay holds its own.
- **The island's past** (ADR-016): the replay chunks at `https://<island domain>/replay/chunks/…`, or at the bucket's public address when one is set. They hold only the world as spectators see it.
- **Nothing else.** The guest panel (8081) is reachable only from the site and its worker, inside Compose's network, and only with `GODLING_PANEL_KEY`. Postgres and Redis are not published. The monitoring's pages listen on the server's loopback only.
- **Check it from another machine** with `deploy/check.sh <domain> <island domain>`: HTTPS and the certificates, every path that must answer and every one that must not, the stream's door, and the open ports. It exits with the number of failures.

## Steps
1. **A Linux server** with Docker and the Compose plugin; 4 GB of memory or more for the world's build.
2. **DNS:** point both domains' A/AAAA records at it (e.g. `godling.example.com` and `island.godling.example.com`). Ports 80 and 443 must be open.
3. **Settings:**
   ```bash
   cd deploy && cp .env.example .env && nano .env
   ```
   Fill in the two domains, five random secrets (one is the backups' password), the DeepSeek key, Stripe and SMTP (see `.env.example`).
4. **Start everything:**
   ```bash
   docker compose up -d --build
   ```
   The first build compiles the world, which takes a while.
5. **Make yourself staff:**
   ```bash
   docker compose exec site python manage.py createsuperuser
   ```
   Then sign in at `https://<domain>/accounts/login/`: confirm your email from the message that arrives, and set up two-factor sign-in with an authenticator app at `https://<domain>/accounts/2fa/`. Save the recovery codes. The admin, `https://<domain>/admin/`, opens only with two-factor sign-in, and its sign-in is the site's own.
6. **Stripe:**
   - In the Dashboard, add a webhook endpoint `https://<domain>/credits/stripe/webhook/` for these events:
     - `checkout.session.completed`, `checkout.session.expired`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`;
     - `charge.refunded`, `charge.refund.updated`, and `refund.updated` and `refund.failed` where the Dashboard lists them;
     - `charge.dispute.created`, `charge.dispute.updated`, `charge.dispute.closed`.
   - Give the endpoint API version `2026-10-28.endive`, the one the `stripe` library in `web/requirements.txt` pins: events come in the endpoint's version, the site's own requests in the library's.
   - A refund takes back its share of the pack's credits, and a refund that fails gives it back. A dispute holds back all of them until the bank decides; a lost one takes back the disputed share. Credits already spent are owed, and come out of whatever the viewer gets next.
   - Events may arrive in any order or twice: each is applied once, refunds and disputes are read from Stripe as they are now, and only the difference moves credits. If Stripe cannot be reached, the site answers 503 and Stripe sends the event again.
   - A checkout Stripe charged less for than the pack, or in another currency, is **held**: no credits until staff let it stand (Payments in the admin, action "Let held payments stand") or refund it in Stripe. The admin's Stripe events list notes held payments and any paid checkout that matched no payment.
   - Test and live keys stay apart: events from the other mode are ignored.
   - Put its signing secret in `GODLING_STRIPE_WEBHOOK_SECRET`.
   - Start with test keys (`sk_test_…`) and Stripe's test cards, then switch to live keys.
7. **Email:** set the SMTP details. Sign up once yourself to see a confirmation email arrive.
8. **Alerts:** set `GODLING_ALERT_EMAIL`, then see one arrive: `docker compose stop relay`; within two minutes "RelayDown" is in your inbox. `docker compose start relay` brings it back, and the all-clear follows.
9. **Backups** to a bucket, and one restore tried (below).
10. **Cloudflare in front** (below), before you announce the site.
11. **Real money** waits for an outside security review: [`security-review.md`](security-review.md). With live Stripe keys the site does not start until `GODLING_SECURITY_REVIEW` names one.

## Cloudflare in front
Why (ADR-017): one server cannot absorb a flood, and its address should not be public. Cloudflare's free plan takes the floods, hides the server, passes the stream's WebSockets through, does not bill traffic, and gives Turnstile for the sign-up form. Godling's own limits (the relay's, allauth's, the site's pace and credits) still do the rest: Cloudflare is the outer wall, not the only one.
1. **Add the domain** to Cloudflare and set both names' DNS records to **Proxied** (the orange cloud).
2. **SSL/TLS mode: Full (strict).** Caddy keeps its own Let's Encrypt certificates; leave Cloudflare's "Always Use HTTPS" off, since Caddy redirects to HTTPS itself.
3. **Tell Caddy whom to believe.** Put Cloudflare's ranges in `.env`, then `docker compose up -d caddy`:
   ```bash
   echo "GODLING_PROXY_RANGES=$(curl -s https://www.cloudflare.com/ips-v4 https://www.cloudflare.com/ips-v6 | tr '\n' ' ')" >> .env
   ```
   Caddy then takes the viewer's address from Cloudflare's `CF-Connecting-IP`, only on connections from those ranges, and hands it on as the one address the site and the relay see. Without it, every viewer looks like Cloudflare, and they share one set of limits.
4. **Close the server to everyone else.** Allow ports 80 and 443 only from Cloudflare's ranges, in your hosting provider's firewall (Hetzner Cloud Firewall, AWS security groups…). A firewall on the server itself (ufw) does not hold here: Docker opens published ports past it. Keep SSH open to your own address.
5. **Turnstile** (Cloudflare dashboard → Turnstile → add a widget for the site's domain): put its site key and secret key in `GODLING_TURNSTILE_SITE_KEY` and `GODLING_TURNSTILE_SECRET_KEY`, then `docker compose up -d site`. The sign-up form then asks Cloudflare whether a person is signing up.
6. **Check** from outside: `deploy/check.sh <domain> <island domain>`, and the ports test now shows the server's address closed: try it with `CHECK_IP=<server address>`.

## Monitoring and alerts
- **Prometheus** reads the relay (viewers, refusals, resyncs, bytes sent), Caddy (requests, errors, sizes) and the server (CPU, memory, disk) every 15 s, and keeps 30 days.
- **Alerts** (`monitoring/alerts.yml`, tested by `monitoring/alerts.test.yml`): the relay down; the world's stream down; viewers near the relay's cap; connections refused in numbers (someone hammering); viewers falling behind; bandwidth above 20 MB/s; over 300 GB of stream a day; server errors above 5%; the disk under 10% free; memory or CPU worn thin; the backup service silent, a backup job late, or the backups still on this server.
- **Alertmanager** emails them through the site's SMTP to `GODLING_ALERT_EMAIL`, and again when they clear.
- **Their pages** are on the server's loopback only. From your machine: `ssh -L 9090:127.0.0.1:9090 -L 9093:127.0.0.1:9093 <server>`, then http://localhost:9090 (Prometheus: graphs, Status → Targets, Alerts) and http://localhost:9093 (Alertmanager: silencing an alert during work).

## Backups
The `backup` service (ADR-018) takes encrypted, deduplicated [restic](https://restic.net) snapshots, named after the site's domain (`GODLING_DOMAIN`), so two deployments sharing a bucket never prune or restore each other's:
- **The database** every hour (`pg_dump`), and **the run** every six hours: Godling's memory and logs, the island's save, the world script it runs, and the replays' tracks, markers, state and today's chunks. Not the raw recordings (the chunks are made from them), the world's own log or the console (the spectator token is in it), or the agent key the launcher makes again at every start.
- **Each finished day of replay chunks** once, in a snapshot of its own kept for good: chunks never change, so no backup reads the whole past again. This also keeps the days a replay bucket holds, which the island deletes from the server two days on.
- **Kept:** database and run snapshots one an hour for two days, one a day for two weeks, one a week for two months, one a month for a year. A snapshot uploads only what changed.
- **Checked every week:** a twentieth of the stored data is read back (a different twentieth each week), the newest database snapshot is restored into a scratch database, which must hold the same tables as the live one, and the newest run snapshot must hold the island's save.
- **Watched:** Prometheus hears from it every minute through node-exporter, and emails when it has not for 10 minutes, when a job is three of its intervals late (the weekly check, a day past its week), or while the backups are still on this server.
- **Gentle:** it runs at a low CPU and disk priority, and waits while a restore runs.
- **Not in them:** `deploy/.env`, and so not the backup password. Keep both in a password manager: without the password no backup can be read, and `.env` holds the keys to everything else.

**Setting it up**, before going live:
1. **A private bucket of its own**, not the replays' public one. Cloudflare R2: R2 → Create bucket; then Manage R2 API tokens → a token with Object Read & Write on that bucket. The bucket's S3 address is `https://<account id>.r2.cloudflarestorage.com`.
2. **In `.env`:** `GODLING_BACKUP_REPOSITORY=s3:https://<account id>.r2.cloudflarestorage.com/<bucket>` (with the `s3:`), `GODLING_BACKUP_REGION=auto`, the token's key id and secret in `GODLING_BACKUP_KEY_ID` and `GODLING_BACKUP_SECRET`, and a long random `GODLING_BACKUP_PASSWORD`. Without a bucket the backups go to a volume on this server, and an alert says so. Moving to a bucket later: every job runs again there at once.
3. `docker compose up -d backup`, then `docker compose logs backup`: the repository is made, then come the first snapshots and the first check.

**Restoring.** The newest snapshot, or the one whose id follows `db` or `run` (`docker compose exec backup backup snapshots` lists them, in UTC; an id of the other kind is refused). A restore reads only, so the backups wait while it runs and a key that may only read is enough.
- **The database**, after a mistake. It is restored beside the live one, in one go, and then takes its place; the live one is kept as `godling_before_<time>` until you drop it:
  ```bash
  docker compose stop site worker
  docker compose run --rm restore db
  docker compose start site worker
  ```
  Stripe payments, refunds and disputes since the snapshot are not in it, and Stripe will not send them again. The restore says the snapshot's time; then:
  ```bash
  docker compose exec site python manage.py reconcile_stripe --since <the snapshot's time>
  ```
- **The run** (Godling's memory and logs, the island's save, the world), with the island stopped. The run's replays stay as they are: they show what happened, and the packer goes on from them. `restore run <id> --replay` brings back the snapshot's replays too.
  ```bash
  docker compose stop island
  docker compose run --rm restore run
  docker compose start island
  ```
- **On a new server**, the old one gone: Docker, this repository, and `deploy/.env` from the password manager. Then:
  ```bash
  docker compose up -d postgres
  docker compose run --rm restore db
  docker compose run --rm restore run
  docker compose up -d --build
  docker compose exec site python manage.py reconcile_stripe --since <the database snapshot's time>
  ```
  The island comes back where it was ("the island put back" in `docker compose logs island`), the site with its accounts and credits, and the replays with every saved day of their past.
- **Once before going live,** do the new-server restore on a staging copy, from the real bucket but with a token that may only read it, and with `GODLING_BACKUP_FROM=<the real domain>` in staging's `.env` (staging's own domain names its own snapshots). Start staging with `docker compose up -d --build --scale backup=0`, so it takes no backups of its own ([`security-review.md`](security-review.md), going live).

## Day to day
- **Logs:** `docker compose logs -f site worker mailer island relay`, or the admin's Logs page: the world's, the mind's, the panel's and the replay packer's (`world.log`, `console.log`, `panel.log` and `replay.log` in the run folder). The relay's are in `docker compose logs relay`; how many watch, in its `/relay/status` (inside Compose's network: `docker compose exec site python -c "import urllib.request; print(urllib.request.urlopen('http://relay:8082/island/relay/status').read().decode())"`).
- **Replays and disk** (ADR-016): the world records about 5 GB a day. The packer keeps raw recordings `GODLING_REPLAY_RAW_DAYS` days (3): older recordings are deleted once packed, and the one being written is trimmed of its older rows once an hour. It writes a warning to `replay.log` when the disk is 80% full. Replay chunks take about 0.2 GB a day; with a bucket set, they go there too (it needs a CORS rule allowing GET and HEAD from any origin, which the packer sets if its key may), and a day stays on the server until it is all uploaded and two days old.
- **Updates and the renderer:** a run keeps its frozen copy of the world script, but each start copies in today's renderer and models, so the island's page always has the current replay player.
- **Prices, credit packs, viewers, notes and reports:** in the admin.
- **Updates:** `git pull && docker compose up -d --build`. The site migrates its database on start.
  - A run keeps the copy of the world script it started with (`/runs/live/world`). For a new world script, remove that copy before restarting: `docker compose exec island rm -rf /runs/live/world`. The island save is kept beside it, so the new script puts the same island back.
- **Backups:** `docker compose logs backup` for what it did, `docker compose exec backup backup snapshots` for what the bucket holds, and `docker compose exec backup backup db` (or `run`, `prune`, `check`) to run one now; it exits non-zero if it failed. Restoring is above.

## Tested so far
- **The whole deployment under Docker** (Docker Desktop, 3 November; these images, both names under `*.localhost` with Caddy's own CA, and Mailpit as the SMTP server):
  - `deploy/check.sh` from another container, through the published ports as a visitor comes: 55 checks pass. HTTP sent to HTTPS; TLS 1.3 with a trusted certificate naming each domain; TLS 1.1 refused; no certificate for any other name; HSTS, framing and sniffing headers; every open and closed path of the island; the stream's door (101 from the island's page, 403 from another site's or with no Origin); and the 65th socket from one address refused, though each claimed another address. The three failures are this machine's, not the deployment's: a Postgres of the host's own on 5432, and the monitoring's loopback ports, which Docker Desktop's gateway reaches. Caddy's local certificates last 12 hours, so `CHECK_CERT_DAYS=0`.
  - The viewers' screen in headless Chromium: "Live, 1 watching"; the island in its frame from its own origin; its stream at `wss://…/spectate/ws?gz=1`: the whole island as one gzipped message of 17 KB, then updates; no errors.
  - Prometheus reading all five targets with the twelve alerts loaded, and the relay counting exactly what `check.sh` did (two sockets refused for their origin, one for its address). `docker compose stop relay` emailed RelayDown after 2 minutes; `docker compose start relay`, and the all-clear followed.
  - The site and the worker on Postgres and Redis.
  - **Backups** (ADR-018), with an S3 stand-in as the bucket: the first snapshots, the prune and the weekly check in the first minute, and Prometheus reading what they did. Then a whole server lost and brought back from the bucket alone, with the steps above: the accounts, the island, Godling's memory and the replays came back as they were (checksums). After the review: a database restore beside a newer migration, swapped in with the old one kept; a run backed up while the island ran, then restored onto empty volumes, with the packer going on and no line repeated; the weekly check failing when it should. The full list is in ADR-018.
- **Tested without Docker** (in WSL), the same pieces as the images run:
  - the world under `/island` with a fixed spectator token;
  - the mind's and the panel's calls to it;
  - the world with `patches/v2`: joining without the key refused, the snapshot refused to the spectator token, no CORS on the agent API, loopback by default, and no start beyond loopback without a key;
  - the site with the panel's key, its tests with the worker's tasks run inline;
  - gunicorn with whitenoise, with debug off;
  - SMTP sending, to a local SMTP server.
- **Not yet:** a real server, with DNS, Let's Encrypt and Cloudflare in front: `deploy/check.sh` from another machine there.
