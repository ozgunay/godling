# ADR-018: Backups: the database every hour and the run every six, encrypted, off the server, and restored every week

Date: 2026-11-03. Status: built; tested under Docker end to end, including a whole-server loss restored from the bucket alone. Not yet on a real server with a real bucket.

## Why
Going live needs backups running and one restore done (`deploy/security-review.md`, going live, step 5). Until now `deploy/README.md` only said which volumes to copy by hand. What a lost server would take with it:
- **The database**: accounts, the credits ledger (money), notes, reports. It changes with every purchase and power.
- **The run**: Godling's memory and mind logs, the island as it stands, the world script the run keeps, and the replays' past (ADR-016). None of it can be made again.

## Decisions
You said to start; each is the recommended choice, and any can change.
1. **restic**, for snapshots that are encrypted on the server before they leave, deduplicated (each uploads only what changed), and restorable whole or in part, from any S3-compatible bucket, an SFTP host or a local path. One small binary beside Postgres's own client in one image.
2. **What and how often:**
   - the database every hour, as `pg_dump`'s custom format;
   - the run every six hours: memory, mind logs, the island's save, the world copy, and the replays (tracks, markers, chunks).
   - Not the raw recordings (5 GB a day; the chunks are made from them, ADR-016), the world's log, or the agent key the launcher makes again at every start.
3. **Where: a private bucket of its own off the server, Cloudflare R2 recommended**, as for the replays (ADR-016 D10). The first 10 GB are free, and restores cost nothing. Hetzner's object storage or any S3 works the same.
   - Without a bucket, the backups go to a volume on the same server, so the service runs from the first start, and an alert says so until a bucket is set.
4. **Kept:** one an hour for 2 days, a day for 2 weeks, a week for 2 months, a month for a year.
5. **A weekly check that restores:**
   - a twentieth of the stored data read back;
   - the newest database snapshot restored into a scratch database, which must hold the live one's tables;
   - the newest run snapshot must hold the island's save.
6. **Alerts, through the monitoring of ADR-017.** The service writes what each job last did for node-exporter's textfile collector. Prometheus emails:
   - the database backup 3 hours late (critical);
   - the run's 18 hours late;
   - the weekly check failing for over 8 days;
   - the backups on this server for an hour;
   - the service reporting nothing (critical).
   A job that never finished well is late from when the service started.
7. **The password and `.env` are not in the backups.** Without the password nothing can be read, so it and `.env` belong in a password manager too.

## What was built
- **`deploy/backup.sh`**, run by the `backup` service from `deploy/Dockerfile.backup` (Postgres 16's client and restic 0.18):
  - `serve` is the loop;
  - `db`, `run`, `prune` and `check` are one job now;
  - `snapshots` lists what the bucket holds;
  - `restore db|run [snapshot]` brings one back.
  - The database is streamed from `pg_dump` into restic, so a failed dump leaves no snapshot. The repository is made only when restic says there is none (exit code 10); a wrong password or an unreachable bucket is a failure to try again in five minutes.
- **The `restore` service**, under a Compose profile so it never starts with the rest: the same image with the run writable. `docker compose run --rm restore db`, `restore run`.
- **node-exporter** reads `/textfile` (the backups' metrics volume). **Five alerts** are in `deploy/monitoring/alerts.yml`, with their tests in `alerts.test.yml`.
- **`deploy/README.md`, Backups:**
  - setting up the bucket;
  - restoring the database, the run, or everything onto a new server;
  - doing the new-server restore once before going live.

## Tested (3 November, Docker Desktop)
| Check | Result |
|---|---|
| The deployment from this branch, with an S3 stand-in (moto) as the bucket | The repository was made; the first database and run snapshots, the prune and the weekly check all passed in the first minute. The check restored the database into a scratch copy: 26 tables, 178 rows |
| Prometheus | The four jobs' times read through node-exporter, the backup rules loaded, nothing firing |
| A whole server lost | All the services, the database, the run, the replay chunks, and the backups' cache and metrics deleted, the bucket alone kept. `up -d postgres`, `run --rm restore db`, `run --rm restore run`, `up -d` |
| What came back | The viewer account made before the loss. The island save, Godling's memory and mind logs, the world script, and all 17 replay files (13 chunks) checksum-identical, owned by the island's user. "The island put back (20 pieces)", Godling joined, and the past was still replayable beside a new segment |
| The service after the loss | It found the bucket's repository (no new one), and added 305 KB for the next run snapshot |
| No bucket set | The snapshot went to the volume; the metric says not off-site |
| A wrong password | Said as such (exit 12), no repository made, tried again in five minutes |
| A bucket out of reach | restic retried for 15 minutes, then the job failed, the metric said so, and it was tried again five minutes later. Meanwhile the other jobs wait; the alerts go by the last success, so a long outage still emails |
| Three restore checks in a row | All pass, and no lock is left. A first version left one: a listing cut short by `grep -q` kept its lock, which blocked the next check for 30 minutes. Listings are now read whole, and without a lock |
| The alert rules | `promtool test rules`: each fires on what it is for, and only then. Samples must be a minute apart or closer, or a series goes stale before an alert's `for` ends |
| CI's checks | `docker compose config` with `GODLING_BACKUP_PASSWORD`, `promtool check config`, shellcheck |

## Left
- **A real bucket**, and the new-server restore done once from it on a staging copy (going live, step 5).
- **The backup password and `.env` in a password manager**: yours.
