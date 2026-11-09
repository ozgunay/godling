# ADR-013: Credits and Stripe, moderating notes, the admin, and running on one server

Date: 2026-11-02. Status: built and tested locally (Stripe mocked and through a test checkout; Docker not run).

## Why
The site (ADR-012) let accounts call powers and send notes for free, with no way to report a note. Everything ran on a development machine. You asked for what was missing: credits and payment, reports and moderation of notes, a production database and hosting, a public link for the island, and real email. You also asked for an admin where prices are changed and viewers seen, borrowing AgentOp's admin.

## Decisions (yours)
1. **Payments:** Stripe.
2. **Hosting:** one server with Docker Compose, as AgentOp runs.
3. **Free credits:** 20 when an account confirms its email. On 2026-11-09 you raised it to 600, still set in the admin (Site rules, *Welcome credits*).
4. **Moderation:** report after delivery. A note goes out at once; viewers report it; 3 reports hide it and pause its sender until a moderator looks.
5. **The admin:** prices adjustable, viewers visible, AgentOp's admin borrowed.

## What was built
### Credits (`web/apps/credits`)
- **Prices and credit packs are rows.** The admin edits them in their lists; the screen takes prices from the site each poll and dims a price the purse cannot pay.
  - The seeded prices: stone 4, log 4, regrow 6, lightning 40, meteor 300, earthquake 500.
  - The seeded packs: 100 credits for €5, 320 for €15, 1,100 for €50.
- **A purse per account, and a ledger.** Every change is an entry with the balance after it: bought, welcome, spent, given back, granted. Entries are never edited, and a balance never goes below zero.
- **A power is charged before the world is asked.** If the world refuses (no clear spot, too soon), the credits go back. "Test mode" (`GODLING_FREE_POWERS=1`) charges nothing.
- **Welcome credits:** 20 on confirming the email, once per account (a database constraint). 600 from 2026-11-09 (`rules` migration 0006: a site still giving 20 gives 600; a number set in the admin stays).

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

## Fixed after review (PR #17)
Eleven findings from your review of PR #17 at `1b781a4`, all fixed.

1. **The island image could not start the world.** The launcher looked for Clawblox in `~/.cargo/bin`, but the image puts it in `/usr/local/bin`. It now uses whichever is on the PATH, or `CLAWBLOX_BIN`.
2. **A restart reset the island.** It is now kept:
   - **Saving:** every five minutes and when the run stops (first thing, as a stopping container has seconds), the launcher reads the world's snapshot and keeps the island in `<run>/island-save.json`.
   - **What is kept:**
     - every piece that can be carried, built with or left by the sky, with where it lies, whether it is fastened, and its attributes;
     - felled trees;
     - the day and the hour;
     - the numbering, so a new stone is never named like one standing in a wall;
     - Godling's body: where it stood, its health, hunger and wetness.
   - **Putting it back:** at the next start, the launcher writes the save into the run's copy of `main.lua` (as it sets the walk speed). The world puts the island back before anyone joins (`sky.restore`).
   - **Not kept:** fish, fires, anything falling, an earthquake under way. Timers start afresh.
   - **Why not Clawblox's own `--resume`:** it was tried first.
     - It needed an engine patch: its Lua loader could not rebuild a function that refers to itself.
     - With the patch, a viewer's fresh stone still vanished seconds after resuming.
     - The world's timers use `os.clock()`, which starts from zero in a new process.
     - A resumed world also runs its old code.

     The world's own save has none of these problems, and a new world script puts back the same island.
3. **Two requests at once got past a viewer's pace.** The pace was checked from the last note or power call, which was written only after the island answered. The turn is now taken first, in one conditional update of the account's row (`last_note_at`, `last_power_at`). It is given back if nothing came of it: too few credits, or the island refused the note.
4. **Adding one disposable domain dropped the rest.** As in AgentOp, a table with any rows replaced the bundled list of about 74,000 domains. Now the bundled list always counts: the table adds domains, and a deactivated row unblocks one.
5. **Lookalike letters slipped past the blocked words.** The site checked the note as typed; the panel then turned `ｃｈｅａｐ ｇｏｌｄ` into `cheap gold`. The site now makes the same plain text first (`words.plain`), then checks it and sends exactly that. Usernames are checked the same way.
6. **Admin changes stayed stale in the other workers.** The cache was per process. It is now one table that every gunicorn worker shares, made by `migrate`. allauth's rate limits now count across workers too.
7. **Every viewer shared one sign-in rate limit.** allauth saw only Caddy's address. The site now trusts one proxy (`GODLING_TRUSTED_PROXIES=1` in Compose) and reads the viewer's address from `X-Forwarded-For`.
8. **Reports could reach the wrong note.** Pop-ups were matched to notes by name and words, and the panel had dropped `+` from names, so `mara+foo` showed as `marafoo`. Now:
   - each note is stored before it is sent;
   - its id travels with it through the panel, to the pop-up;
   - a report reaches that very note;
   - the panel keeps every character a username may hold.
9. **Staff who could only look could import domains.** The import views now need the add permission on the domain list. While fixing that, the same gap turned up in every admin action (grant credits, mute, ban, hide notes, switch domains), and those now need the change permission.
10. **Paid powers said "free while testing".** That line shows only in test mode now.
11. **Two log tabs had no file.** The launcher now also writes its console to `console.log` and the panel's output to `panel.log` in the run folder.

How the fixes were tested:
- **The site:** 53 tests, with new ones for:
  - two requests at once;
  - a turn given back;
  - lookalike letters;
  - a report reaching the shown note, and a refused note not kept;
  - the bundled domains kept;
  - the viewer's address behind Caddy;
  - imports and actions needing their permissions.
- **The island, two real runs of the launcher on one run folder** (test ports, the stock Clawblox build):
  - The first run was stopped as a container is.
  - All 20 pieces, a viewer's stone among them, were there at the end of the second run.
  - The second run's stone was numbered on (`Stone_2`).
  - The clock and Godling's hunger went on.
- **That save, put back again:** every piece within 5 cm and the same turn, and Godling's body where it stood.
- **A hand-made save:** a block fastened on another, a felled palm, a crater, a sand mark and a new log all came back. A starting block missing from the save stayed gone.

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
