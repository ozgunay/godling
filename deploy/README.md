# Running Godling on one server

Docker Compose, as AgentOp runs (ADR-013). Four services:
- **`postgres`:** the site's database.
- **`site`:** accounts, credits, moderation, the admin and the viewer screen (gunicorn, with whitenoise for the admin's files).
- **`island`:** the world (Clawblox, built from source with `patches/`), Godling's mind and the guest panel, started by `mind/run_godling.py`. The run lives in a volume, so it continues across restarts: Godling's memory, and the island itself. Every five minutes and when the container stops, the launcher saves what stands (`island-save.json`); on the next start the world puts it back (ADR-013).
- **`caddy`:** HTTPS for the domain. It sends `/island…` to the world, serves replay chunks from the runs volume at `/replay/chunks/…`, and sends everything else to the site.

## What the public can reach
- **The site**, at `https://<domain>/`.
- **The island's spectator page**, at `https://<domain>/island?spectator_token=…`. Caddy passes only what watching needs: the page, its files, the spectator stream and chat. The world's agent API (`join`, `input`, `observe`, `reset`, `chat`, `snapshot`…) answers 404 from outside.
- **The island's past** (ADR-016): the replay chunks at `https://<domain>/replay/chunks/…`, or at the bucket's public address when one is set. They hold only the world as spectators see it.
- **Nothing else.** The guest panel (8081) is reachable only from the site, inside Compose's network, and only with `GODLING_PANEL_KEY`. Postgres is not published.

## Steps
1. **A Linux server** with Docker and the Compose plugin; 4 GB of memory or more for the world's build.
2. **DNS:** point the domain's A/AAAA records at it. Ports 80 and 443 must be open.
3. **Settings:**
   ```bash
   cd deploy && cp .env.example .env && nano .env
   ```
   Fill in the domain, four random secrets, the DeepSeek key, Stripe and SMTP (see `.env.example`).
4. **Start everything:**
   ```bash
   docker compose up -d --build
   ```
   The first build compiles the world, which takes a while.
5. **Make yourself staff:**
   ```bash
   docker compose exec site python manage.py createsuperuser
   ```
   The admin is `https://<domain>/admin/`.
6. **Stripe:**
   - In the Dashboard, add a webhook endpoint `https://<domain>/credits/stripe/webhook/` for `checkout.session.completed`, `checkout.session.expired`, `checkout.session.async_payment_succeeded` and `checkout.session.async_payment_failed`.
   - Put its signing secret in `GODLING_STRIPE_WEBHOOK_SECRET`.
   - Start with test keys (`sk_test_…`) and Stripe's test cards, then switch to live keys.
7. **Email:** set the SMTP details. Sign up once yourself to see a confirmation email arrive.

## Day to day
- **Logs:** `docker compose logs -f site island`, or the admin's Logs page: the world's, the mind's, the panel's and the replay packer's (`world.log`, `console.log`, `panel.log` and `replay.log` in the run folder).
- **Replays and disk** (ADR-016): the world records about 5 GB a day; the packer keeps raw recordings `GODLING_REPLAY_RAW_DAYS` days (3) and writes a warning to `replay.log` when the disk is 80% full. Replay chunks take about 0.2 GB a day; with a bucket set, they go there too and only the last two days stay on the server.
- **Prices, credit packs, viewers, notes and reports:** in the admin.
- **Updates:** `git pull && docker compose up -d --build`. The site migrates its database on start.
  - A run keeps the copy of the world script it started with (`/runs/live/world`). For a new world script, remove that copy before restarting: `docker compose exec island rm -rf /runs/live/world`. The island save is kept beside it, so the new script puts the same island back.
- **Backups:** the `pgdata` volume (`docker compose exec postgres pg_dump -U godling godling > backup.sql`) and the `runs` volume (Godling's memory, the island's save and the replays' tracks and markers).

## Tested so far
- **Tested without Docker** (in WSL), the same pieces as the images run:
  - the world under `/island` with a fixed spectator token;
  - the mind's and the panel's calls to it;
  - the site with the panel's key;
  - gunicorn with whitenoise, with debug off;
  - SMTP sending, to a local SMTP server.
- **Not built yet:** the images and the Caddy proxy. Docker's engine did not answer on the machine this was made on.
- **Not run against yet:** Postgres. The site runs on it through Django's own backend, with nothing database-specific.
