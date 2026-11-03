# ADR-018: Backups: the database every hour and the run every six, encrypted, off the server, and restored every week

Date: 2026-11-03. Status: built and reviewed (PR #46). Tested under Docker end to end, including a whole-server loss restored from the bucket alone, and again after the review's fixes. Not yet on a real server with a real bucket.

## Why
Going live needs backups running and one restore done (`deploy/security-review.md`, going live, step 5). Until now `deploy/README.md` only said which volumes to copy by hand. A lost server would take two things with it:
- **The database**: accounts, the credits ledger (money), notes, reports. It changes with every purchase and power.
- **The run**: Godling's memory and mind logs, the island as it stands, the world script the run keeps, and the replays' past (ADR-016). None of it can be made again.

## Decisions
You said to start. Each of these is the recommended choice, and any of them can change.
1. **restic**: snapshots are encrypted on the server before they leave, and deduplicated, so each one uploads only what changed. They restore whole or in part, from any S3-compatible bucket or a local path. The image is Postgres's own with restic added. It has no ssh, so SFTP is not on offer.
2. **What, and how often:**
   - **The database** every hour, as `pg_dump`'s custom format.
   - **The run** every six hours: memory, mind logs, the island's save, the world copy, and the replays' tracks, markers, state and today's chunks.
   - **Each finished day of chunks** once, in a snapshot of its own that is kept for good. Chunks never change, so no backup reads the whole past again. These snapshots also keep the days a replay bucket holds, which the island deletes from the server after two days.
   - **Not backed up:**
     - the raw recordings (5 GB a day; the chunks are made from them, ADR-016);
     - the world's log;
     - the console, which holds the spectator token;
     - the agent key, which the launcher makes again at every start;
     - the packer's lock.
3. **Named after the site's domain** (`GODLING_DOMAIN`): restic's host is the domain, not the container's name.
   - Two deployments sharing a bucket never prune or restore each other's snapshots.
   - A staging copy restores production's snapshots with `GODLING_BACKUP_FROM=<production's domain>`. It uses a token that may only read, and runs with `--scale backup=0`.
4. **Where: a private bucket of its own, off the server.** Cloudflare R2 is recommended, as for the replays (ADR-016 D10): the first 10 GB are free, and restores cost nothing. Hetzner's object storage, or any S3 service, works the same way.
   - Without a bucket, the backups go to a volume on the same server. The service still runs from the first start, and an alert says the backups are on this server until a bucket is set.
   - The job state belongs to the repository it was written for. When the bucket is set later, every job runs again there at once.
5. **What is kept:**
   - Database and run snapshots: one an hour for 2 days, one a day for 2 weeks, one a week for 2 months, one a month for a year. Each kind is kept separately, per domain.
   - Old snapshots are forgotten daily. Their space is freed weekly, because freeing it rewrites data in the bucket.
6. **Restores read only.**
   - No lock is taken, so a key that may only read is enough, and a lock left by a lost server is in nobody's way. The backups wait while a restore runs.
   - An id of the wrong kind (a database snapshot given to `restore run`) is refused.
   - **The database** is restored beside the live one, in one transaction, and then takes its place. The live one is kept as `godling_before_<UTC time>`, so a failed or wrong restore leaves the site as it was.
   - **Stripe:** the payments, refunds and disputes made since the snapshot are not in a restored database, and Stripe will not send them again. `manage.py reconcile_stripe --since <time>` asks Stripe for them, and the restore prints the command with the snapshot's time.
   - **The run:** when the server still has its replays, they stay: they show what happened, and the packer goes on from them. `--replay` brings back the snapshot's replays too, and a new server always gets them, with every saved day of chunks.
7. **A run snapshot is taken while the island runs**, one file at a time, so the run is made safe to restore from any moment:
   - Godling's memory files are written whole: a temporary file, then a rename.
   - An episode cut short is skipped when the episodes are read.
   - When a restored log is shorter than where the packer had got to, the packer goes on from the log's end. A new log is read from its start. The packer tells the two apart by the log's first line.
   - Track and marker lines already at a file's end are not added again.
   - A chunk that exists, on the server or in the replay bucket, is never written again, so restoring an old run cannot overwrite days of good chunks.
8. **A weekly check that restores:**
   - one twentieth of the stored data is read back, a different twentieth each week;
   - the newest database snapshot is restored into a scratch database, which must hold the live one's tables;
   - the newest run snapshot must hold the island's save, which is read from the snapshot, not just listed.
   - A failed check is tried again after an hour, not every five minutes.
9. **Alerts, through the monitoring of ADR-017.**
   - The service writes a heartbeat every minute, and, for each job, the time it counts as late. Both reach Prometheus through node-exporter's textfile collector.
   - That collector keeps serving the last file it read after the service stops, so only the heartbeat's age shows that the service stopped.
   - Prometheus emails when:
     - the service has been silent for 10 minutes (critical);
     - the database backup is three of its intervals late (critical);
     - the run, the prune or the check is late: three intervals for the run and the prune, and for the check a day past its week;
     - the backups have been on this server for an hour.
   - The thresholds follow the intervals set in `.env`.
10. **Locks.**
    - Every job first removes stale locks.
    - The container keeps a fixed hostname, so restic recognises its own locks after a restart.
    - A stop reaches restic itself, which then removes its lock.
11. **Gentle on the world.**
    - Backups run at a low CPU and disk priority (`nice`, `ionice`, and a quarter of the other services' CPU weight).
    - Two CPU threads at most.
12. **The password and `.env` are not in the backups.** Without the password nothing can be read, so it and `.env` belong in a password manager too.

## What was built
- **`deploy/backup.sh`**, run by the `backup` service from `deploy/Dockerfile.backup` (the client of the server's Postgres, 16 then 18, and restic 0.18). It is checked by shellcheck in CI, as busybox's `sh` runs it. Its commands:
  - `serve` is the loop;
  - `db`, `run`, `prune` and `check` each run one job now, and exit non-zero if it failed;
  - `snapshots` lists this site's snapshots, in UTC;
  - `restore db|run [snapshot] [--replay]` brings one back.
- **How a backup fails:**
  - The database is streamed from `pg_dump` into restic, so a failed dump leaves no snapshot.
  - The repository is made only when restic says there is none, and never by a restore.
  - A wrong password, a missing repository and an unreachable bucket each have a message of their own. A job that fails is tried again in five minutes.
- **The `restore` service** sits under a Compose profile, so it never starts with the rest. It is the same image with the run writable, and it is built at every `run`, so a restore always uses today's script. `docker compose run --rm restore db`, `restore run`.
- **The chunks** sit at a path of their own in both services, not inside the run, so neither service creates folders in the island's volume.
- **`manage.py reconcile_stripe --since <time>`** (`web/apps/credits`) handles three cases:
  - paid checkouts the database lost are credited, once;
  - refunds take their share back;
  - disputes are brought up to date.
  Every step can run twice without harm.
- **The packer and Godling's memory**, as in decision 7: `mind/godling/replay.py`, and `mind/godling/files.py` for writing a file whole.
- **node-exporter** reads `/textfile` (the backups' metrics volume). **Four alerts** are in `deploy/monitoring/alerts.yml`. Their tests in `alerts.test.yml` run at one-minute samples.
- **`deploy/README.md`, Backups:**
  - setting up the bucket;
  - restoring the database, the run, or everything onto a new server;
  - doing the new-server restore once on a staging copy before going live.

## After the review of PR #46
The max-effort review found 15 issues. All but the last are fixed:
1. **The staging drill wrote into production's backups**, under the same host name. Snapshots are now named after the domain, and staging restores production's snapshots with `GODLING_BACKUP_FROM`, a read-only token and no backup service of its own.
2. **A database restore ran over the live database, step by step**, and could leave it half dropped. It now restores beside the live one in one transaction, then renames the two.
3. **A run snapshot taken while the island ran could double the replay history**, or catch a memory file half written. Fixed by decision 7.
4. **Restoring an old run could overwrite days of good chunks** with a frozen island. Existing chunks, local or in the bucket, are never written again, and the replays are kept by default.
5. **A stale lock could block the prune and the check for good**, and a restore on a new server. Every job now removes stale locks first, the hostname stays fixed, the stop reaches restic, and restores take no lock.
6. **The chunks were mounted inside the run**, so `backup` failed when it started before the island, and a restore left root-owned folders. The chunks are now at a path of their own.
7. **The restore image was never rebuilt by updates.** It now uses `pull_policy: build`.
8. **A restore by id ignored the snapshot's kind.** The id is now looked up among that kind's snapshots of this site.
9. **Switching to a bucket kept the old success times.** The job state is now tied to the repository and the domain.
10. **The island-save check could never fail.** It now reads the file from the snapshot.
11. **The alerts missed a stopped service**, the prune had no alert at all, and the thresholds were fixed numbers. Fixed by the heartbeat and the per-job late times.
12. **The one-off commands exited 0 when the job failed.** They now return the job's result.
13. **A database restore lost the Stripe purchases since the snapshot.** `reconcile_stripe` brings them back.
14. **The backup work grew with the island's history.** Each day of chunks is now saved once, the jobs run at low priority, and a failing check is retried hourly. One cost is left: the append-only mind logs are still read in full at every run snapshot.
15. **Someone with the server can delete the backups**, because it holds a read-write key and the password, and prunes from there. This is not changed. It is a decision for going live, put to the outside review (`security-review.md`, scope): a bucket lock, or a second copy the server cannot reach.

Smaller fixes from the same review:
- Each failure has its own message.
- The region is passed only when set, and the database connection uses the site's own `GODLING_DB_*` names.
- The intervals are checked when the service starts, and `backup` with no command prints its usage.
- restic's exit 3 counts as saved, and is logged. It means some files changed or went away while they were being read.
- Times are in UTC.
- The SFTP claim is gone.

## Tested (3 November, Docker Desktop)
| Check | Result |
|---|---|
| The deployment from this branch, with an S3 stand-in (moto) as the bucket | The repository was made. The first database and run snapshots, the prune and the weekly check all passed in the first minute |
| Fresh volumes, the backup service started before the island | It starts, since there is no mount inside the run. The first run backup fails until the island has made the run, and passes on its next try |
| Prometheus | The jobs' late times and the heartbeat read through node-exporter, the backup rules loaded, nothing firing |
| A whole server lost (before the review) | All the services, the database, the run, the replay chunks, and the backups' cache and metrics deleted, the bucket alone kept. `up -d postgres`, `run --rm restore db`, `run --rm restore run`, `up -d`. The viewer account, the island save, Godling's memory and mind logs, the world script and all 17 replay files came back checksum-identical, owned by the island's user |
| A database restore, after a newer migration | The live database had a new table with a foreign key to the users, and a user made after the snapshot. The restore went beside it, took its place, and kept the old one as `godling_before_20261103114901`. The site started on it: the new table and the later user gone, the earlier user there |
| A run backup while the island ran, then its volumes lost and restored | The run and the replays came back owned by the island's user. The island started on them, and the packer went on: 6 to 8 track lines, 9 to 12 sky lines, none repeated |
| The backups during a restore | "a restore is running: the backups wait for it", once |
| The weekly check | Passes on a good repository (26 tables). Fails, exit 1, for a newest run snapshot made without the island save, and for a restored database whose tables differ from the live one's |
| Chunk days | Each finished day saved once, in a snapshot of its own; today's chunks in the run snapshot |
| Locks | A restic killed by SIGKILL, and the container restarted mid-job: the next job cleared the stale lock and passed |
| A restore with an id of the other kind | Refused: "no run snapshot of bk.localhost matches" |
| A one-off job that fails | Exits 1 |
| `reconcile_stripe` without a Stripe key | Says there is no Stripe to ask, and exits non-zero |
| No bucket set | The snapshot goes to the volume, and the metric says it is not off-site |
| A wrong password | Said as such (exit 12), no repository made, tried again in five minutes |
| A bucket out of reach | restic retried for 15 minutes, then the job failed, the metric said so, and it was tried again five minutes later |
| The alert rules | `promtool test rules` at one-minute samples: each alert fires on what it is for, and only then. A mutation check: the tests fail when a rule is broken |
| The unit tests | The packer and the memory files after a restore (5 tests, `mind/tests/test_replay_restore.py`), and `reconcile_stripe` (4 tests, `web/apps/credits/test_reconcile.py`) |
| CI's checks | `docker compose config` with `GODLING_BACKUP_PASSWORD`, `promtool check config` and the rule tests, and shellcheck on `backup.sh` |

## Postgres 18 (3 November)
Dependabot moved the database to `postgres:18-alpine` alone. The 18 image refuses a volume at `/var/lib/postgresql/data` (it keeps its data in a folder per major version, `18/docker`), so a fresh server's database did not start; and the backup image's Postgres 16 `pg_dump` refuses a newer server. No server held data yet, so the move cost nothing:
- the volume mounts at `/var/lib/postgresql`, and the backup image is on `postgres:18-alpine`;
- Dependabot no longer proposes Postgres majors: the server and the backups' client move together, by hand, with `pg_upgrade` once there is data.

Tested on the production server (Hetzner CAX21, Arm) against the real R2 bucket: Postgres 18.6 started fresh in `/var/lib/postgresql/18/docker`, the site migrated (27 tables), the backup service made the repository, took the first database and run snapshots, and the weekly check restored the database snapshot (27 tables). `pg_dump` in the backup image is 18.6.

## Left
- **A real bucket**, and the new-server restore done once from it on a staging copy (going live, step 5). The bucket is set up (R2, `godling-backups`); the restore drill on a staging copy is still to do.
- **Whether the server may delete its own backups** (review finding 15): a bucket lock or a second copy. This is for the outside review.
- **The mind's logs** are read whole by every run snapshot. Rotating them would keep that small.
- **The backup password and `.env` in a password manager**: yours.
