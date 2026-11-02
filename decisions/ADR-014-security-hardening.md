# ADR-014: Security: a private agent API, a site that never waits on the island, and abuse-proof credits and reports

Date: 2026-11-02. Status: built and tested locally (the site's tests, a scratch world, the screen in a browser). The images were not built: Docker's engine was not running.

## Why
A security review of the project and of the accounts site (ADR-012, ADR-013) found one critical hole and a set of smaller ones. You asked for all of them fixed in one PR. For the major problem, you said to change the design where needed, the standard way.

- **Critical:** the spectator token every viewer's page carries also opened `/snapshot`, which lists every player's session. With it a viewer could act as Godling. And anyone who reached the world could join under any name, `Sky` included.
- **B1:** a power's words, typed in the admin, reached every viewer's page as HTML. The screen shares the admin's origin, so a staff member allowed only to edit powers could act as a superuser.
- **B2:** sign-in rate limits counted every viewer as Caddy's address. (Fixed in the PR #17 review: one proxy trusted, and a shared cache.)
- **B3:** three web processes; a power held one for up to 15 s behind the island's one-at-a-time sky; every viewer's poll went on to the panel. About a hundred viewers, or a few powers at once, stalled the site.
- **B4:** pacing could be raced. (Fixed in the PR #17 review: the turn is taken in one conditional update.)
- **B5:** accounts are cheap: `me+1@gmail.com` is a new account with 20 welcome credits and a report vote. Three reports from fresh accounts hid any note and muted its author, for any note id, with no limit.
- **B6:** a Stripe refund or chargeback left the credits in place.
- **B7:** debug defaulted to on (and, with no Stripe keys, opened a free checkout); HSTS lasted an hour; staff had no two-factor sign-in; the island shared the site's origin. (The import permissions were fixed in the PR #17 review.)
- **Also:** the island image had no Chromium, so Godling's first-person view (`/observe/image`) could not work there.

## Decisions
1. **The world's control plane is private, and keys say who may use it** (`patches/v2`, SEC-001). The industry's split: a public, read-only stream and a private, authenticated control API.
   - The spectator token is a stream key: it opens the watching side and nothing else.
   - The snapshot is the operator's alone.
   - Joining takes a key the launcher makes for every run.
   - The server listens on loopback unless told otherwise, and never beyond it without a key.
   - Only the watching side answers other origins.
2. **No web request waits on the island** (B3): the standard Django arrangement, as AgentOp runs it.
   - **Redis** is the shared cache: rate limits, the island's news, who is watching. It is also Celery's broker.
   - **A Celery worker** takes powers to the island, one at a time as the island takes them.
   - **Threaded gunicorn workers:** 3 processes × 8 threads.
   - **The news is shared:** fetched about once a second for every viewer, behind a short lock, so only one request fetches.
3. **The island gets its own origin** (B7): `island.<domain>`, which only the site may frame. Nothing on it can reach the site's cookies.
4. **One inbox, one welcome and one voice** (B5): accounts are keyed by the inbox their email delivers to. Making a second account stays allowed (no one is told an inbox is taken); farming it is not.
5. **Money follows Stripe** (B6): refunds take back their share, disputes hold everything until the bank decides, and spent credits become a debt the next credits pay.

## What was built
### The world (`patches/v2-private-agent-api.patch`, SEC-001)
- `/snapshot` needs `X-Operator-Token`.
- `/join` needs `X-Agent-Key` when `WORLD_AGENT_KEY` is set.
- `WORLD_HOST` defaults to `127.0.0.1`; `0.0.0.0` without a key refuses to start.
- No CORS on the agent API. Tokens are compared in constant time.
- **The launcher** (`run_godling.py`) makes `WORLD_AGENT_KEY` per run, passes it to the world, the mind and the panel, and writes `<run>/world.key` (mode 600) for `god_bot.py --run-dir` and `guest_panel.py --run-dir`.
  - The DeepSeek key no longer goes to the world, the panel or the browser; Hindsight is handed it on its own.
- **The guest panel:**
  - takes JSON only (no form or text post from another origin);
  - lets a slow client go after 10 s;
  - ignores a negative `Content-Length`;
  - parses Godling's log again only when it has grown.

### The site
- **B1:** the tooltip is built from text nodes. Checked in a browser with a power whose label, words and rule were markup: shown as words, nothing ran.
- **B3:**
  - `apps/screen/island.py`: the shared news, and who is watching. Counted across workers in 20 s windows, at most 8 pages per address, so a script inventing client ids cannot inflate the count.
  - `apps/screen/tasks.py` and `PowerCall.status`:
    - a power is queued, its price taken;
    - the worker relays it once and settles it;
    - the screen asks `api/power/<id>` every half second.
  - A call nobody took in a minute is given up and refunded. The worker skips such a call, so nothing is called after its refund.
  - A queue out of reach refunds at once.
  - Notes, which the panel only queues, get 5 s.
- **B5:**
  - `User.email_key`: the inbox, with `+tags` dropped, and Gmail's dots too.
  - `Welcome`: one gift per inbox, enforced by a unique key.
  - A report counts toward hiding only from an account at least a day old (`report_min_age_hours`), and one inbox counts once.
  - Reports come only from a viewer watching now, only on notes from the last 30 minutes, and at most 10 an hour (`reports_per_hour`). These are new site rules in the admin.
  - Hiding and the author's pause stay as you chose them (ADR-013).
- **B6:**
  - `charge.refunded`, `charge.dispute.created` and `charge.dispute.closed` are handled.
  - A payment keeps its PaymentIntent. An older payment is found through Stripe.
  - `Purse.owed` holds what could not be taken back. A `clawback` ledger entry records each taking.
- **B7:**
  - `GODLING_DEBUG` defaults to off.
  - HSTS lasts a year, subdomains included.
  - **Two-factor sign-in** (allauth MFA, an authenticator app and recovery codes):
    - staff must set it up before the admin opens;
    - the admin's sign-in is the site's own, with its rate limits and the code;
    - viewers may turn it on for themselves.
  - The site's container runs as a user, not root.
- **Deploy:**
  - `redis` and `worker` services;
  - Caddy serves two hosts: the island's with `frame-ancestors` for the site only, and its allowlist;
  - the island image has Chromium (`CLAWBLOX_CHROME`) and `patches/v2`;
  - the screen posts to the island's frame at the island's origin only.

## Tests
- **The site:** 68 tests, all passing (53 before). New ones:
  - the news fetched once for many polls;
  - watching capped per address, and the address read behind Caddy;
  - a queued power: asked after, settled once, given up and refunded, a late worker calling nothing, a queue out of reach;
  - reports: fresh accounts and one inbox not hiding a note, a viewer not watching, an old note, the hourly limit;
  - one welcome per inbox;
  - Stripe: refunds in parts, a debt paid by the next credits, a dispute won and lost, an older payment found through Stripe;
  - the admin: two-factor first, and the site's sign-in.
- **Checks:**
  - `check --deploy` leaves two warnings, both answered in settings: Caddy redirects to HTTPS, and preload is left off on purpose.
  - Compose validates with `docker compose config`.
  - Celery finds `apps.screen.tasks.call_power`.
- **The world:** SEC-001's probes, on a scratch world.

## Not done yet
- **The images and the two-host Caddy are untested:** Docker's engine was not running here. Postgres and Redis are untested too; the site uses Django's own backends.
- **Your installed Clawblox** (`~/.cargo/bin/clawblox`) does not have `patches/v2` until it is rebuilt. The mind works with either: an unpatched world ignores the key.
- **Usernames can still use lookalike letters** (a Cyrillic "о" in "Gоdling"). Limiting usernames to plain letters is a choice about who may sign up, left to you.
- **The live stream:** one socket per viewer, no reconnect, no limit on sockets. That is the WebSocket design, next.
