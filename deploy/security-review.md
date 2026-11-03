# Outside security review: the brief, and going live with money

Real money waits for this. With live Stripe keys (`sk_live_…`) the site refuses to start until `GODLING_SECURITY_REVIEW` names a review (ADR-016). This page is what to hand the reviewer, and what to do before and after.

## What Godling is
An autonomous AI agent living on a 3D island, streamed live. Viewers watch for free; with an account they spend credits (bought through Stripe) on sky powers (a stone, a meteor…) and send Godling short notes, which its mind (an LLM) reads.

## Scope
**In scope**
- **The site** (`web/`, Django): accounts (django-allauth: sign-up, email confirmation, sign-in, password reset), credits and the ledger, Stripe Checkout and its webhook (payments, refunds, disputes), powers and notes and their pacing, reports and moderation, the admin, Cloudflare Turnstile on sign-up.
- **The island's public side**: the spectator page and what Caddy lets through (`deploy/Caddyfile`), the stream relay (`relay/`, Rust), Clawblox's page as patched (`patches/v3`).
- **The world's private side**: that nothing outside reaches the agent API (`patches/v2`), the guest panel (`tools/guest_panel.py`) and its key.
- **Godling's mind and notes**: prompt injection through notes (`tools/guest_panel.py clean_note`, `mind/godling/mind.py`): can a note make Godling do or say what it should not, or reach anything beyond the island?
- **The deployment**: `deploy/` (Compose, the images, secrets in `.env`, Caddy, Cloudflare in front), the monitoring.

**Out of scope**: Stripe, Cloudflare and DeepSeek themselves; Clawblox's internals beyond our patches (its dependencies are audited: `patches/DEPS-001`).

## The picture
```
viewer ──HTTPS──▶ Cloudflare ──▶ Caddy ─┬─▶ site (Django) ──▶ Postgres, Redis, worker (Celery) ──▶ guest panel ──▶ world
                                        ├─▶ island page, chat ──▶ world (watching routes only; Caddy adds the token)
                                        └─▶ /island/spectate/ws ──▶ relay ──one connection──▶ world's stream
mind (DeepSeek) ◀──▶ world's agent API (loopback/Compose network, join key)
```

## What to look for, first
1. **Money**: credits for nothing (the test checkout, the webhook, races between buying, spending and refunds), a refund or a dispute that keeps the credits, powers that cost nothing when they should.
2. **Accounts**: takeover, enumeration, email confirmation bypass, rate limits behind Cloudflare and Caddy (allauth reads the address Caddy forwards).
3. **The admin**: who reaches it, two-factor, what staff with partial permissions can do.
4. **Cross-site**: XSS on the viewer screen and the admin (power texts, names, notes), CSRF on the JSON APIs, the island's origin isolation and framing.
5. **The island's edge**: anything of the agent API, the panel, the relay's status or metrics reachable from outside; the stream's limits (per address, IPv6 /64, connection pace); a spectator token anywhere public.
6. **Notes and the mind**: injection past `clean_note`; what Godling's body can do whatever its mind decides.
7. **The server**: secrets in images or logs, open ports, containers running as root, the island's headless Chromium (`--no-sandbox`, inside its container).

## How to run it for the review
- A staging copy of `deploy/` with **test keys**: Stripe test mode (`sk_test_…` and its webhook secret), Turnstile's test keys, any SMTP sink.
- `deploy/check.sh <site> <island>` from outside shows what the public reaches; `.github/workflows/` holds the tests and audits.
- Decision records: ADR-012 to ADR-016 (`decisions/`). Known and accepted: the ignored advisories in `patches/clawblox-audit-ignore.txt`; Chromium without its sandbox inside the island container; prompt injection can be reduced, not ruled out.

## What we ask back
A report with each finding's severity, how to reproduce it, and a fix; then a retest of the fixes.

## Going live, in order
1. The review is done and its findings are fixed and retested.
2. Set `GODLING_SECURITY_REVIEW` in `deploy/.env`: who reviewed, when, where the report is.
3. Cloudflare in front, its ranges in `GODLING_PROXY_RANGES`, the server's ports 80 and 443 open to Cloudflare only (`deploy/README.md`).
4. `GODLING_ALERT_EMAIL` set, and one alert seen arriving (stop the relay for two minutes).
5. Backups of `pgdata` and `runs` running, and one restored.
6. Stripe's live keys and live webhook secret in `deploy/.env`, the webhook endpoint created in live mode; `docker compose up -d`.
7. `deploy/check.sh` from outside: all checks pass.
