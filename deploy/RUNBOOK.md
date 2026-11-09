# Running Godling: the runbook

What to do, in order, to start Godling's servers, to stop and start Godling itself, to update, to begin a fresh run, to make the game ready for a stream, and to find out what is wrong. [`README.md`](README.md) says how the deployment is built and set up the first time; this is for every day after that. The commands are typed in Cmder (or any terminal) on your own machine, then on the server.

## Where everything is
| What | Where | Notes |
|---|---|---|
| The server | Hetzner Cloud, project Godling: a CAX21 (Arm64, 4 vCPUs, 8 GB, 80 GB) in Falkenstein, Ubuntu 26.04 | `ssh root@<server address>`, with your SSH key only. The address is in the Hetzner console and your password manager, not in this repository: Cloudflare hides it (ADR-017) |
| Its firewall | Hetzner console → Firewalls → `godling` | Port 22 from your home address only; 80 and 443 from Cloudflare's addresses only. **When your home address changes, SSH times out: update the port 22 rule there** |
| The code on the server | `/opt/godling`, a clone of `main` with a read-only deploy key | Every `docker compose` command below runs in `/opt/godling/deploy` |
| The settings | `/opt/godling/deploy/.env` on the server (readable by root only), and a copy in your password manager | Never in git, never pasted in a chat. `nano /opt/godling/deploy/.env` to edit |
| The domain | godling.world at the registrar; DNS, TLS and the cache at Cloudflare | Both names proxied (orange). Never add a DNS-only (grey) record for the server |
| Replays and backups | Cloudflare R2: `godling-replays` (public at replays.godling.world) and `godling-backups` (private) | Each with a token of its own, in `.env` |
| Godling's mind | DeepSeek, `deepseek-flash`, with your API key | About $0.21 an hour while the island runs (about $5 a day): 80 calls in 17 minutes cost $0.12 |
| Email | Amazon SES, through SMTP | The site's confirmations and password resets, the feedback mailer, the monitoring's alerts |
| Payments | Stripe | Test keys until the outside security review ([`security-review.md`](security-review.md)) |
| The stream | OBS on your PC, to Twitch | Below, under *Making the game ready* |

## What runs
Twelve services (`docker compose ps`), all with `restart: unless-stopped`: after a server reboot, everything that was running comes back by itself, and anything you had stopped stays stopped.
- **The game:** `island` (the world, Godling's mind, the guest panel) and `relay` (the stream every viewer's socket reaches).
- **The site:** `site`, `worker`, `mailer`, `postgres`, `redis`.
- **The edge:** `caddy` (HTTPS, both domains).
- **Watching and keeping:** `prometheus`, `alertmanager`, `node-exporter`, `backup`. (`restore` is never started with the rest.)

Only `island` spends DeepSeek credits. Everything else can run for months on its own.

## Starting the servers
After a reboot nothing needs doing: `docker compose ps` shows everything Up within a minute or two. If the server was off, or something is stopped:
```bash
ssh root@<server address>
```
```bash
cd /opt/godling/deploy && docker compose up -d
```
`up -d` starts whatever is not running, **the island included**: if Godling should stay off, name the services instead:
```bash
docker compose up -d postgres redis site worker mailer relay caddy prometheus alertmanager node-exporter backup
```
Then `docker compose ps`: every service `Up`, `postgres` and `redis` `(healthy)`. The site answers at https://godling.world within about 30 s of `site` starting (it migrates its database first); the island's page, https://island.godling.world/island, shows Cloudflare's 502 until the island is up.

## Godling itself
Godling's life is the `island` service. Stopping it stops the DeepSeek spending; starting it continues the same life.

**Stop Godling** (to save tokens, or before work on the island):
```bash
docker compose stop island
```
The launcher saves the island and Godling's memory first ("Stopping…", then a `Done:` line with the run's length, calls and cost in `docker compose logs --tail 5 island`), so the container may still end with code 137 after its 30 s of grace: that is fine. Viewers then see the island's page fail (502) and the site's screen without the island. Everything else keeps running.

**Start Godling again**, where it left off:
```bash
docker compose start island
```
`docker compose logs -f island` shows "World is up, the island put back (N pieces…)", then "Godling joined", then its first `THINK`. The body comes back exactly where it was saved (`sky.restoreBody`), so a restart never moves Godling: since ADR-020 and ADR-022, a Godling in the sea drowns, dies and is born again at the start spot by itself.

**Restart it** (the same life, the same code): `docker compose restart island`.

**Watch it think:** `docker compose logs -f island` (THINK, INTEND, each action's `ok` or `FAIL`, REFLEX, BUBBLE), or the admin's Logs page. How many are watching: `docker compose exec site python -c "import urllib.request; print(urllib.request.urlopen('http://relay:8082/island/relay/status').read().decode())"` (`viewers`, `world: up`, `tick`).

## Updating the code
On the server:
```bash
cd /opt/godling && git pull && cd deploy
```
Then rebuild and restart what changed. A plain `docker compose up -d --build` rebuilds and restarts **everything, the island included**, so:
- **The site, the relay, the edge or the backups changed** (`web/`, `relay/`, `deploy/`), and Godling should keep running or stay off: name them.
  ```bash
  docker compose up -d --build site worker mailer relay backup caddy
  ```
  The site migrates its database on start; the stream relay reconnects viewers by itself.
- **The world or the mind changed** (`world/`, `mind/`, `patches/`, `tools/`): the island must restart, so do it when a pause is acceptable (the island is away for about a minute, the first build on a fresh server for about 7).
  - **A new world script** (`world/main.lua` or `world/assets`) does not reach a run by itself: a run keeps the copy of the world script it started with, in `/runs/live/world`. Remove that copy first; the island's save stays beside it, so the same island is put back under the new script.
    ```bash
    docker compose exec island rm -rf /runs/live/world
    ```
    (with the island stopped: `docker compose run --rm --no-deps --entrypoint sh island -c 'rm -rf /runs/live/world'`)
  - Then:
    ```bash
    docker compose up -d --build island
    ```
  The renderer (`world/renderer`) needs no step: every start copies in today's renderer, and open pages pick a new one up by themselves (PR #66).
- **A setting in `.env` changed:** `docker compose restart` does **not** re-read `.env`. Recreate the services that use the setting:
  ```bash
  docker compose up -d --no-deps site worker mailer
  ```
  (email settings: those three and `alertmanager`; Cloudflare's ranges: `caddy`; the replay bucket or `GODLING_MIND_ARGS`: `island`; the backups: `backup`.)

Afterwards, `docker compose ps`, and `docker compose logs --since 5m <service>` for anything that restarts.

## A fresh run: a new island and an empty memory
When Godling should start its life over (a new world, or a run gone wrong). The old run is kept on the server, not deleted, and the site's database (accounts, credits, notes) is not touched.
```bash
./fresh-run.sh
```
[`fresh-run.sh`](fresh-run.sh) stops the island, moves `/runs/live` and the replay chunks to `/runs/old/<UTC time>/` in the runs volume, makes an empty run owned by the island's user, and starts the island. `./fresh-run.sh --no-start` leaves it stopped. By hand, the one trap: the island runs as user `island` (uid 1000), and a `/runs/live` that Docker or root makes is root-owned, so the island cannot write it and crash-loops.
- The old runs are plain folders: `docker run --rm -v godling_runs:/r alpine:3 du -sh /r/old/*`. Delete one when you are sure: `docker run --rm -v godling_runs:/r alpine:3 rm -rf /r/old/<time>`.
- The old run's replay chunks stay in the R2 bucket and in the backups' snapshots until those are forgotten (ADR-018); the new run does not use them.
- A fresh run with the old island kept instead (a new world script, the same pieces): not this; see *Updating the code*.

## Making the game ready
Before a stream, or after any work on the server, in this order:
1. **The server answers.** `ssh root@<server address>`. If it times out, your home address has changed: Hetzner console → Firewalls → `godling` → the port 22 rule → your new address (`curl -4 ifconfig.me` from your PC, or https://api.ipify.org).
2. **Everything is up.** `docker compose ps`: twelve `Up`, two `(healthy)`, nothing `Restarting`. `df -h /`: under 80% (the replay packer warns in `replay.log` from there).
3. **Godling is alive.** `docker compose logs --since 5m island | grep -E "THINK|INTEND|ok |FAIL"` shows thinking and actions in the last minutes, with mostly `ok`. In the relay's status (above): `"world":"up"`, the `tick` rising at about 62 a second.
4. **The site, from outside.** https://godling.world shows the booklet (the front page, ADR-024), and its *Watch live* opens https://godling.world/watch with "Live"; the island shows in its frame and moves. In a private window, sign up with a throwaway address: the confirmation email arrives, you can sign in, drop a stone, send a note. The test power and the note show on the island and in the feed.
5. **The rules and the prices,** in the admin (https://godling.world/admin/, two-factor sign-in):
   - **Site rules:** *Free powers* (test mode) **off** when credits are real; welcome credits (600, what a new account gets on confirming its email; a change counts from then on); the pace of powers and notes; *Feedback email* set, so bug reports reach you.
   - **Powers:** the prices and texts viewers see (Stone 4, Log 4, Regrow 6, Meteor 300, Earthquake 500, Storm 400); *Lightning* is off, the Storm took its place (ADR-023).
   - **Credit packs**, and **Payments** with nothing held.
6. **Nothing is alerting.** `curl -s 127.0.0.1:9090/api/v1/alerts | python3 -m json.tool | grep -c '"state": "firing"'` prints 0. (The pages themselves: `ssh -L 9090:127.0.0.1:9090 -L 9093:127.0.0.1:9093 root@<server address>`, then http://localhost:9090/alerts and http://localhost:9093.)
7. **The backups are fresh.** `docker compose exec backup backup snapshots`: a `db` snapshot within the hour and a `run` snapshot within six.
8. **The whole deployment, as the internet sees it,** from your PC in WSL or Git Bash: `CHECK_ORIGIN=<server address> deploy/check.sh godling.world island.godling.world`. All checks pass; a failing one names what to change (two are Cloudflare settings: Always Use HTTPS off, Minimum TLS Version 1.2).
9. **The stream.** OBS on your PC: a *Browser* source at `https://godling.world/watch` (the screen; the front page is the booklet), 1920×1080, "Shutdown source when not visible" off; a *Text (GDI+)* line "This is an AI. Nobody controls it." at the top and "Play along at godling.world" at the bottom; Settings → Output: your graphics card's encoder, 6000 Kbps, keyframe interval 2 s; Advanced: automatically reconnect. Twitch: the title says it is an AI trying to survive alone on an island, category *Science & Technology*, tags AI, AIAgent, Survival, Simulation; the panels and a pinned chat message say the same and name godling.world. Your PC must stay awake for as long as it streams (about 3 GB of upload an hour).
10. **Real money** waits for the review: [`security-review.md`](security-review.md), going live.

## When something is wrong
| You see | What it is | What to do |
|---|---|---|
| `ssh` times out | Your home address changed; the firewall only knows the old one | Hetzner console → Firewalls → `godling` → port 22 → your new address. The console's `>_` button opens a terminal regardless |
| godling.world shows Cloudflare's 521, 522 or 526 | Caddy is down, cannot reach the site, or its certificate failed | `docker compose ps caddy`; `docker compose logs --since 10m caddy \| grep -i error`. 526: Caddy's Let's Encrypt renewal failed, usually because plain HTTP does not reach it (Cloudflare's Always Use HTTPS must be off) |
| Caddy restarts over and over, "parsing CIDR expression" | `GODLING_PROXY_RANGES` in `.env` is malformed (two ranges run together) | Redo the ranges with the README's command (Cloudflare in front, step 3), then `docker compose up -d --no-deps caddy` |
| The island's page is 502; the screen has no island | The island is stopped, starting, or crash-looping | `docker compose ps island`; `docker compose logs --tail 50 island`. "Permission denied" on `/runs/live/…`: the run is root-owned; `docker run --rm -v godling_runs:/r alpine:3 chown -R 1000:1000 /r/live`, then `docker compose start island` |
| Godling does nothing, or every action fails | Read the last `FAIL` lines and `REFLEX`es in `docker compose logs --tail 100 island`; in the sea it drowns and is reborn by itself (ADR-020, ADR-022) | If it stays stuck, `docker compose restart island` keeps its place; a fresh run (above) is the last resort |
| Viewers see an old renderer or a stale page after an update | Cloudflare's browser cache (4 h by default) | Pages reload themselves on a new build (PR #66); for the cache itself, Cloudflare → Caching → Browser Cache TTL → *Respect Existing Headers*, or purge everything once |
| No confirmation emails | The SMTP settings, or SES's sending limits | `docker compose exec site python manage.py sendtestemail you@example.com`; `docker compose logs --since 10m site mailer \| grep -i -E "smtp\|mail"`; SES console → Account dashboard for the limits and bounces |
| An alert email: a backup job late, the service silent, the disk | What the email says; `docker compose logs backup`; `df -h /` | `docker compose exec backup backup db` (or `run`, `check`) runs one now and says why it fails. Disk: `du -sh $(docker volume inspect -f '{{.Mountpoint}}' godling_runs)/live/*`; raw recordings are kept `GODLING_REPLAY_RAW_DAYS` days |
| A mistake in the database, or a lost server | The backups | [`README.md`](README.md), Backups: `restore db`, `restore run`, the new-server restore, and `reconcile_stripe` afterwards |
| The run's files, without the island container | They are on the host | `ls $(docker volume inspect -f '{{.Mountpoint}}' godling_runs)/live/`: `world.log`, `console.log`, `replay.log`, `island-save.json`, `mind/`, `memory/` |

## Costs, for the record
- **The server:** €12.69 a month (CAX21), billed by the hour; the IPv4 address is included.
- **Godling's mind:** about $0.21 an hour, $5 a day, $150 a month at `deepseek-flash`, while the island runs. Stop the island when nobody should be watching.
- **R2:** the first 10 GB a month are free; replays grow about 0.2 GB a day, backups much less. Downloads cost nothing.
- **Cloudflare, Twitch:** free. **SES:** cents per thousand emails.
