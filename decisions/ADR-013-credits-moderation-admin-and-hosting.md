# ADR-013: Credits and Stripe, moderating notes, the admin, and running on one server

Date: 2026-11-02. Status: built and tested locally (Stripe mocked and through a test checkout; Docker not run).

## Why
The site (ADR-012) let accounts call powers and send notes for free, with no way to report a note. Everything ran on a development machine. You asked for what was missing: credits and payment, reports and moderation of notes, a production database and hosting, a public link for the island, and real email. You also asked for an admin where prices are changed and viewers seen, borrowing AgentOp's admin.

## Decisions (yours)
1. **Payments:** Stripe.
2. **Hosting:** one server with Docker Compose, as AgentOp runs.
3. **Free credits:** 20 when an account confirms its email.
4. **Moderation:** report after delivery. A note goes out at once; viewers report it; 3 reports hide it and pause its sender until a moderator looks.
5. **The admin:** prices adjustable, viewers visible, AgentOp's admin borrowed.

## What was built
### Credits (`web/apps/credits`)
- **Prices and credit packs are rows.** The admin edits them in their lists; the screen takes prices from the site each poll and dims a price the purse cannot pay.
  - The seeded prices: stone 4, log 4, regrow 6, lightning 40, meteor 300, earthquake 500.
  - The seeded packs: 100 credits for €5, 320 for €15, 1,100 for €50.
- **A purse per account, and a ledger.** Every change is an entry with the balance after it: bought, welcome, spent, given back, granted. Entries are never edited, and a balance never goes below zero.
- **A power is charged before the world is asked.** If the world refuses (no clear spot, too soon), the credits go back. "Test mode" (`GODLING_FREE_POWERS=1`) charges nothing.
- **Welcome credits:** 20 on confirming the email, once per account (a database constraint).

### Payments (Stripe Checkout)
- **Buying:** a pack opens Stripe's hosted checkout.
- **Crediting:** a signed webhook credits the pack once, however often Stripe repeats it. The return page asks Stripe itself if the webhook is late.
- **Development:** without Stripe keys, a test checkout stands in ("No money moves"). It is never there with debug off.

### Moderating notes (`web/apps/notes`)
- **Every note sent through the site is kept**, as the panel shows it (the panel now returns its cleaned text).
- **Reporting:** a note pop-up has a Report button for signed-in viewers who did not write it.
  - One report per viewer per note.
  - 3 viewers' reports (`GODLING_REPORTS_TO_HIDE`) hide the note from every screen's pop-ups and feed.
  - They also pause its sender's notes; the sender can still watch and call powers.
- **The admin:**
  - notes, reported ones first when sorted by reports;
  - actions to hide or restore notes, and to mute, unmute or ban their senders;
  - the reports list, with a reviewed tick.

### The admin (borrowed from AgentOp, and Godling's own)
- **From AgentOp:**
  - the user admin's shape;
  - the disposable-domain admin with its activate and deactivate actions and its three import views (sync the four online lists, import the bundled file, paste a list);
  - the log viewer, which here shows the live run's world, mind, thoughts and panel logs.
- **Godling's own:**
  - **Viewers:** with credits, notes sent, email confirmed and notes muted. Their credit ledger is on their page. Actions grant 20 or 100 credits, mute or unmute notes, and ban or unban. Staff are never banned from there.
  - **Powers and credit packs:** edited in their lists.
  - **Purses, entries and payments:** read-only.
  - **The header:** reads "Godling admin", with links to the logs and the site.

### Running on one server (`deploy/`)
- **Compose services:** Postgres 16, the site (gunicorn and whitenoise), the island (world, mind and panel in one image) and Caddy (HTTPS).
- **The island image** builds Clawblox from source at `8be90a0` with both patches, which apply cleanly to a fresh checkout.
- **The public island link:**
  - The world runs under the base path `/island` with a fixed spectator token, so the site's screen frames `https://<domain>/island?spectator_token=…`.
  - The world serves its page at `/island`, not `/island/` as it prints; the panel and the settings use the right one.
  - Caddy lets only watching through: the agent API answers 404 from outside.
- **The rest of the wiring:**
  - The mind and the panel reach the world's API under the base path (`run_godling.py` reads `WORLD_BASE_PATH`).
  - The panel listens beyond localhost only with a key (`--host`; it refuses otherwise).
- **Settings for production:** Postgres when `GODLING_DB_HOST` is set, HTTPS behind the proxy, HSTS, and secure cookies.

### Real email
SMTP from the environment, as AgentOp does it. Port 587 with TLS, or 465 with SSL.

### Moved to the database (yours, after the first build)
You asked what else should move to the database; these four did. All are edited in the admin.
1. **Site rules (one row):** welcome credits, test mode, seconds between a viewer's powers and notes, note length (140 at most, the panel's cap), and the reports that hide a note.
   - They were settings (`GODLING_WELCOME_CREDITS`, `GODLING_FREE_POWERS`, `GODLING_REPORTS_TO_HIDE`) and panel constants.
   - The site now keeps each account's pace from the database. The panel, given a key, defers to it and keeps only the island's own pace: one note a minute, a short queue.
2. **Blocked words, for notes, usernames or both.**
   - They were two lists in code: the panel's note words, and the usernames' words.
   - They are read once and cached until the admin changes them. An empty or unreadable table still blocks the seeded words.
   - The panel keeps its own short list as a floor for when it runs alone.
3. **Each power's words on its row:** the tooltip, the rule line, the pop-up's words, its kind, and whether it can hurt Godling.
   - The screen takes them from the site with the price.
   - A power switched off leaves the hotbar.
   - On its own, the panel's screen keeps the words written in `viewer.js`.
4. **Every power called is logged:** who, what, where it was aimed, the price, the world's answer, and whether it was refunded. On a viewer's page, and in its own list.

Also: on each viewer's page, **Adjust credits** puts in or takes out any amount, with a reason, as a ledger entry ("Changed by staff"). A purse never goes below zero.

What stays in code, and why:
- **The world's rules** (cooldowns, damage, blast sizes, aim reach): the world cannot read the site's database, and each change needs a test run.
- **The prompt-injection filter:** security code, to be reviewed rather than edited live.
- **Godling's persona:** its identity, versioned with the rest.

## Tests
- **`manage.py test`, 45 tests:**
  - the rules row, and welcome credits and reports following it;
  - blocked words: the seed, staff adding and switching words off, a refused username, and an empty table still blocking;
  - pace, note length and blocked words on notes; one power at a time; test mode;
  - power texts in the status; every call logged, refunds marked;
  - adjusting credits in and out, never below zero; the rules edited on one page, with note length capped at 140;
  - the ledger, and the welcome credits once on confirming the email;
  - the test checkout, credited once;
  - Stripe Checkout (mocked): the webhook credits once, unpaid or expired checkouts credit nothing, a forged webhook is refused, and the return page asks Stripe when the webhook is late;
  - packs and prices come from the admin;
  - a power is charged, refused for too few credits, refunded when the world refuses, and free in test mode;
  - notes are kept, and muted accounts' notes are held;
  - 3 reports hide a note and pause its sender, and hidden notes vanish from pop-ups and the feed;
  - the public island link;
  - every admin list opens, and prices are edited in the list;
  - grants, mutes and bans, and hiding and restoring notes;
  - the log viewer, and staff-only access.
- **In a browser, the production shape without Docker** (world under `/island`, keyed panel, site):
  - A new account got 20 credits, and the meteor and earthquake prices showed dimmed.
  - It bought 320 through the test checkout, for 340 in all.
  - A stone cost 4 (336 left) and popped up under the account's name.
  - In the admin, the meteor went to 250, and the screen showed 250 a few seconds later.
  - The island rendered under `/island` with no failed requests.
  - No page errors.
- **Production serving:** gunicorn with whitenoise and debug off served the admin, its fingerprinted files and the screen. It sent HSTS behind an HTTPS proxy.
- **Email:** a confirmation email went through SMTP to a local server: subject, sender, recipient and link all there.
- **Not run:** the Docker images, Caddy, Postgres and real Stripe or SMTP accounts.
  - Docker's engine did not answer on this machine.
  - Stripe and SMTP need your accounts' keys in `deploy/.env`.
