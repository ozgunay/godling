# Godling's site: viewer accounts, credits and moderation in front of the screen

A small Django service (ADR-012, ADR-013). Viewers watch the island here, sign up and sign in, buy credits, and
their powers and notes go to the guest panel (`tools/guest_panel.py`) under their account's name. The accounts and
the admin's tools are borrowed from AgentOp (`C:/Work/agentop`); running it on a server is `deploy/`.

## What an account gets
- **Anyone can watch:** the screen and `/api/status` need no account.
- **Powers cost credits; notes are free.** Both need a signed-in account.
  - The panel hears them as the account (`user000042`, its username).
  - The site keeps each account's pace from the database: one power every 2 s and one note every 3 minutes, as the site rules say. The keyed panel defers to it and keeps only the island's own pace: one note a minute, a short queue.
  - A power's credits are taken first, and given back if the world refuses it. Every call is logged.
- **20 free credits** when the email is confirmed (the site rules, in the admin).
- **More credits** through Stripe Checkout (`/credits/`). Without Stripe keys, in development only, a test checkout stands in.
- **Notes can be reported.** Three viewers' reports (the site rules) hide a note from every screen and pause its sender's notes until a moderator looks.
- **Blocked words**, a list in the admin, refuse notes and usernames that hold them.
- **Signing up**, as AgentOp has it:
  - username, email and password;
  - the email must be confirmed before signing in;
  - one account per email;
  - nothing says who is registered;
  - allauth's rate limits apply.
- **Godling's account rules:**
  - Usernames are 3–18 characters, as a pop-up shows them.
  - Usernames cannot be reserved (`godling`, `sky`, `admin`, …) or offensive.
  - Disposable email domains are refused (the bundled 74k list, and the Disposable Domains table in the admin).

## The admin (`/admin/`)
What someone running the site changes lives in the database, not in settings or code (the user's wish).
- **Site rules**, one page: welcome credits, test mode (free powers), seconds between a viewer's powers and notes, note length, and the reports that hide a note.
- **Blocked words:** for notes, usernames or both; switched on and off in the list.
- **Powers and credit packs:**
  - Prices and packs are edited right in their lists, and the screen follows within seconds.
  - A power's page also holds what the screen says about it: the tooltip, its rule line, the pop-up's words, and whether it can hurt Godling.
  - Switched off, a power leaves the hotbar.
- **Power calls:** every power a viewer called: what, where, the price, and the world's answer.
- **Users:**
  - credits, notes sent, email confirmed and notes muted;
  - on each viewer's page, their credit ledger and the powers they called;
  - an **Adjust credits** button: any amount in or out, with a reason, kept in the ledger; a purse never goes below zero;
  - actions on many at once: grant 20 or 100 credits, mute or unmute notes, ban or unban.
- **Notes and reports:** hide or restore notes; mute, unmute or ban their senders.
- **Purses, entries and payments:** read-only records.
- **Disposable domains** (AgentOp's): activate and deactivate them; sync the online lists, import the bundled file, or paste a list.
- **Logs** (AgentOp's log viewer): the live run's world, mind, thoughts and panel logs (`GODLING_RUN_DIR`).

## Running it (WSL)
```bash
python3 -m venv ~/.venvs/godling-web && ~/.venvs/godling-web/bin/pip install -r web/requirements.txt
```
Start the world and the panel with a key (the panel then takes powers and notes only from this site):
```bash
export GODLING_PANEL_KEY=$(python3 -c "import secrets; print(secrets.token_hex(16))")
python3 tools/guest_panel.py --world http://localhost:8080 --port 8081 --run-dir ~/godling-runs/x
```
Then the site:
```bash
cd web && ~/.venvs/godling-web/bin/python manage.py migrate && ~/.venvs/godling-web/bin/python manage.py runserver 127.0.0.1:8000
```
Open http://localhost:8000/. In development, the confirmation emails are printed in the site's console. Tests:
`~/.venvs/godling-web/bin/python manage.py test`. For the admin: `manage.py createsuperuser`.

## Settings (environment)
| Variable | Default | What |
|---|---|---|
| `GODLING_DEBUG` | `1` | `0` in production |
| `GODLING_SECRET_KEY` | (dev key) | required when `GODLING_DEBUG=0` |
| `GODLING_HOSTS` | `localhost,127.0.0.1` | allowed hosts |
| `GODLING_TRUSTED_ORIGINS` | | CSRF trusted origins, e.g. `https://godling.example` |
| `GODLING_DB` | `web/db.sqlite3` | the SQLite database (development) |
| `GODLING_DB_HOST`, `_PORT`, `_NAME`, `_USER`, `_PASSWORD` | | Postgres (production) instead of SQLite |
| `GODLING_PANEL_URL` | `http://127.0.0.1:8081` | the guest panel |
| `GODLING_PANEL_KEY` | | the panel's `--key` |
| `GODLING_VIEW_URL` | | the island as the public reaches it: `https://<domain>/island?spectator_token=…` |
| `GODLING_RUN_DIR` | | the live run, for the admin's log viewer |
| `GODLING_CURRENCY` | `eur` | the credit packs' currency |
| `GODLING_STRIPE_SECRET_KEY`, `GODLING_STRIPE_WEBHOOK_SECRET` | | Stripe; without them, only the development test checkout |
| `GODLING_EMAIL_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_TLS`, `_SSL` | | SMTP; without a host, emails go to the console |
| `GODLING_FROM_EMAIL` | `Godling <noreply@localhost>` | the sender |
