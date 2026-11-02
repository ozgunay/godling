# ADR-012: Viewer accounts, copied from AgentOp

Date: 2026-11-02. Status: built and tested in a scratch world (no real users yet).

## Why
Powers and notes came from anyone who opened the screen, under any name they typed (ADR-011). Limits were per browser, and a browser can be cleared. You asked for registration, borrowed from AgentOp, "which is pretty mature tested and I'm also using it in a live project".

## Decision (yours)
**Copy AgentOp's registration into Godling.** Godling gets its own small Django service with AgentOp's `users` app and django-allauth settings, and its own users. The other option was signing in with AgentOp accounts (OAuth); it would have tied Godling to AgentOp's live site.

**No wait for a new account's first note** (yours, after the first build). I had added an hour's wait, after AgentOp's account-age gate; you had it removed. A signed-in account sends notes at once, at most one every 3 minutes (the panel's pace).

## What was built (`web/`)
### Copied from AgentOp
- **The user model**, which signs in by email.
- **The `DisposableDomain` table**, with its admin and cache signal, and the bundled list of 74,631 domains.
- **The validators:** reserved usernames, a minimum length, normalised emails, and disposable domains refused.
- **The allauth adapter**, which applies those validators.
- **The allauth settings:**
  - sign in by email, and sign up with username, email and password;
  - mandatory email confirmation;
  - unique emails;
  - no telling who is registered;
  - sign out only by POST;
  - allauth's rate limits.

### Left in AgentOp
- profiles, followers and signup attribution;
- the Celery email queue (Godling sends directly; the console in development);
- its page templates.

### Changed for Godling
- **Django 5.2 LTS, not 6:** the WSL machine runs Python 3.10.
- **Usernames:**
  - 3–18 characters (what a pop-up shows);
  - Godling's reserved names (`godling`, `sky` — the guest panel's player — `island`, `world`, `viewer`, `screen`, and the routes);
  - offensive names refused, since every viewer sees a username.
- **Account pages:** they wear the screen's Block HUD look. One layout (`templates/allauth/layouts/base.html`) dresses every allauth page: a stone slab with a moss lip over a still of the island, Tiny5, paper fields and gold buttons.
- **The confirmation email** speaks of Godling.

### The screen behind accounts (`web/apps/screen`)
- **Serving:** the site serves `world/viewer` as it is, and sets the CSRF cookie the screen's posts need.
- **`/api/status`** is open to everyone. It relays the panel's status and adds `account`: signed in or not, the username, the sign-in, sign-up and sign-out links, and how long until a new account's first note.
- **`/api/power` and `/api/note`** need a signed-in account (401 otherwise) and a CSRF token.
  - They go to the panel with the account's client id (`user000042`) and username, never a name from the page. So the panel's pace limits hold per account, and the pop-ups show the account's name.
- **The panel trusts this site.** With `--key` (`GODLING_PANEL_KEY`) it takes powers and notes only from whoever sends the key (403 otherwise), and it must not be reachable from outside.
- **The screen** (`world/viewer/viewer.js`) shows the account beside the purse:
  - signed out: "Sign in" and "Create an account";
  - signed in: the username and "Sign out".
- **Behind the site:**
  - a refused power or note nudges that chip;
  - the note box drops its name field and says when a new account's first note can go.
- **Served by the panel alone** (development), the screen works as before.

## Tests
- **`manage.py test`, 10 tests:**
  - signing up sends a confirmation email;
  - signing in is refused until the email is confirmed, then works;
  - reserved, long and offensive usernames are refused, but "grapefan" is not;
  - disposable emails are refused;
  - the account pages wear the island;
  - the page sets the CSRF cookie, and the path guard holds;
  - status as signed out and signed in, and a page cannot pass itself off as an account;
  - signed out, powers and notes are refused;
  - a power goes to the panel as the account;
  - a note goes to the panel as the account, at once;
  - posts without a CSRF token are refused.
- **Live, in a scratch world** (world 8190, panel with a key 8191, site 8192, Chrome):
  - The panel refused a power without the key (403).
  - Signed out, a power said "Sign in to call powers and send notes."
  - A new account signed up and confirmed its email from the link in the site's console, then signed in.
  - The chip showed its name. A stone it called popped up as "tester9723 dropped a stone".
  - Its note was held for the hour then in place ("Next note in 59:42"). That wait is gone now; the tests cover a new account's note going out at once.
- **A bug the live test found:** links on the screen could not be clicked (the HUD lets clicks through to the island). Fixed.
