# Running Godling on one server

Docker Compose, as AgentOp runs (ADR-013, ADR-014, ADR-015). Seven services:
- **`postgres`:** the site's database.
- **`redis`:** the shared cache (sign-in rate limits, the island's news, who is watching) and the worker's queue. It keeps nothing that matters across a restart.
- **`site`:** accounts, credits, moderation, the admin and the viewer screen (gunicorn with threads, whitenoise for the admin's files).
- **`worker`:** the site's Celery worker. It takes powers to the island one at a time, so no web request waits on the island.
- **`island`:** the world (Clawblox, built from source with `patches/`), Godling's mind and the guest panel, started by `mind/run_godling.py`. The run lives in a volume, so it continues across restarts: Godling's memory, and the island itself. Every five minutes and when the container stops, the launcher saves what stands (`island-save.json`); on the next start the world puts it back (ADR-013).
- **`relay`:** the island's stream relay (`relay/`, `Dockerfile.relay`), which every viewer's socket reaches: one connection to the world, the same updates to everyone. A container of its own, holding the spectator token and nothing else, so the part of the island the whole internet talks to is kept apart from Godling's keys (the agent key, the operator token, the DeepSeek key).
- **`caddy`:** HTTPS for both domains. The site's domain goes to the site; the island's domain goes to the world (watching side only), its stream to the relay, and its replay chunks (`/replay/chunks/…`) to files in the runs volume.

## What the public can reach
- **The site**, at `https://<domain>/`.
- **The island's spectator page**, on its own origin: `https://<island domain>/island`. Only the site may frame it (`frame-ancestors`), and nothing on it can reach the site's cookies.
  - Caddy passes only what watching needs: the page, its files and chat to the world, and the stream to the relay (ADR-015). The world's agent API (`join`, `input`, `observe`, `reset`, `chat`, `snapshot`…) and its whole-island `/spectate` answer 404 from outside.
  - The stream relay is the world's one spectator: every viewer's socket is the relay's, from the island's own page only. From one address it takes at most 64 sockets (an IPv6 /64 counts as one address; a phone network puts many people behind one), and new ones at a steady pace after a first burst, since each is handed the whole island. However many watch, the world works out its changes once.
  - Inside Compose's network the world still asks for its keys: joining takes the agent key the launcher makes at every start, and the snapshot takes the operator token (`patches/v2`, ADR-014). The spectator token stays on the server: Caddy adds it to the page's requests, and the relay holds its own.
- **The island's past** (ADR-016): the replay chunks at `https://<island domain>/replay/chunks/…`, or at the bucket's public address when one is set. They hold only the world as spectators see it.
- **Nothing else.** The guest panel (8081) is reachable only from the site and its worker, inside Compose's network, and only with `GODLING_PANEL_KEY`. Postgres and Redis are not published.

## Steps
1. **A Linux server** with Docker and the Compose plugin; 4 GB of memory or more for the world's build.
2. **DNS:** point both domains' A/AAAA records at it (e.g. `godling.example.com` and `island.godling.example.com`). Ports 80 and 443 must be open.
3. **Settings:**
   ```bash
   cd deploy && cp .env.example .env && nano .env
   ```
   Fill in the two domains, four random secrets, the DeepSeek key, Stripe and SMTP (see `.env.example`).
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
   - A refund takes back its share of the pack's credits, and a refund that fails gives it back. A dispute holds back all of them until the bank decides; a lost one takes back the disputed share. Credits already spent are owed, and come out of whatever the viewer gets next.
   - Events may arrive in any order or twice: each is applied once, refunds and disputes are read from Stripe as they are now, and only the difference moves credits. If Stripe cannot be reached, the site answers 503 and Stripe sends the event again.
   - A checkout Stripe charged less for than the pack, or in another currency, is **held**: no credits until staff let it stand (Payments in the admin, action "Let held payments stand") or refund it in Stripe. The admin's Stripe events list notes held payments and any paid checkout that matched no payment.
   - Test and live keys stay apart: events from the other mode are ignored.
   - Put its signing secret in `GODLING_STRIPE_WEBHOOK_SECRET`.
   - Start with test keys (`sk_test_…`) and Stripe's test cards, then switch to live keys.
7. **Email:** set the SMTP details. Sign up once yourself to see a confirmation email arrive.

## Day to day
- **Logs:** `docker compose logs -f site worker island relay`, or the admin's Logs page: the world's, the mind's, the panel's and the replay packer's (`world.log`, `console.log`, `panel.log` and `replay.log` in the run folder). The relay's are in `docker compose logs relay`; how many watch, in its `/relay/status` (inside Compose's network: `docker compose exec site python -c "import urllib.request; print(urllib.request.urlopen('http://relay:8082/island/relay/status').read().decode())"`).
- **Replays and disk** (ADR-016): the world records about 5 GB a day; the packer keeps raw recordings `GODLING_REPLAY_RAW_DAYS` days (3) and writes a warning to `replay.log` when the disk is 80% full. Replay chunks take about 0.2 GB a day; with a bucket set, they go there too and only the last two days stay on the server.
- **Prices, credit packs, viewers, notes and reports:** in the admin.
- **Updates:** `git pull && docker compose up -d --build`. The site migrates its database on start.
  - A run keeps the copy of the world script it started with (`/runs/live/world`). For a new world script, remove that copy before restarting: `docker compose exec island rm -rf /runs/live/world`. The island save is kept beside it, so the new script puts the same island back.
- **Backups:** the `pgdata` volume (`docker compose exec postgres pg_dump -U godling godling > backup.sql`) and the `runs` volume (Godling's memory, the island's save and the replays' tracks and markers).

## Tested so far
- **Tested without Docker** (in WSL), the same pieces as the images run:
  - the world under `/island` with a fixed spectator token;
  - the mind's and the panel's calls to it;
  - the world with `patches/v2`: joining without the key refused, the snapshot refused to the spectator token, no CORS on the agent API, loopback by default, and no start beyond loopback without a key;
  - the site with the panel's key, its tests with the worker's tasks run inline;
  - gunicorn with whitenoise, with debug off;
  - SMTP sending, to a local SMTP server.
- **Not built yet:** the images and the Caddy proxy.
- **Not run against yet:** Postgres and Redis. The site runs on them through Django's own backends, with nothing database-specific.
