#!/bin/sh
# Backups (ADR-018): the database every hour and the run every six hours, as encrypted, deduplicated restic snapshots
# in GODLING_BACKUP_REPOSITORY (an S3-compatible bucket, such as Cloudflare R2; without one, a volume on this server).
# Snapshots are named after the site (GODLING_DOMAIN), so two deployments sharing a bucket never prune or restore
# each other's. Each finished day of replay chunks is saved once, in a snapshot kept for good. Old database and run
# snapshots are forgotten daily, and the space they held freed weekly. Once a week a twentieth of the stored data is
# read back, the newest database snapshot is restored into a scratch database, and the newest run snapshot must hold
# the island's save. What each job last did is written for node-exporter (deploy/monitoring/alerts.yml, "backups").
#
#   backup serve                              the loop the backup service runs
#   backup db | run | prune | check           one job now; exits non-zero if it failed
#   backup snapshots                          what the repository holds of this site (times in UTC)
#   backup restore db [snapshot]              the database from a snapshot (default: the newest), beside the live one,
#                                             which it then replaces; the live one is kept under another name
#   backup restore run [snapshot] [--replay]  the run from a snapshot. Over a run that has replays, those are kept
#                                             unless --replay; a new server gets them back, every saved day of them
# GODLING_BACKUP_FROM names another site's snapshots to restore (a staging copy restoring production's).
# shellcheck shell=sh
set -eu

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }
now() { date +%s; }

export RESTIC_REPOSITORY="${GODLING_BACKUP_REPOSITORY:-/backups/repo}"
export RESTIC_PASSWORD="${GODLING_BACKUP_PASSWORD:?set GODLING_BACKUP_PASSWORD: without it no backup can be read}"
export RESTIC_CACHE_DIR=/cache/restic
export GOMAXPROCS="${GOMAXPROCS:-2}" # restic's threads: the world's simulation shares the server
export TZ=UTC
if [ -n "${GODLING_BACKUP_KEY_ID:-}" ]; then
  export AWS_ACCESS_KEY_ID="$GODLING_BACKUP_KEY_ID" AWS_SECRET_ACCESS_KEY="${GODLING_BACKUP_SECRET:-}"
fi
if [ -n "${GODLING_BACKUP_REGION:-}" ]; then # empty: restic asks the bucket (Amazon S3); R2 wants "auto"
  export AWS_DEFAULT_REGION="$GODLING_BACKUP_REGION"
fi
# The database as the site reaches it (web/godling_web/settings.py).
export PGHOST="${GODLING_DB_HOST:-postgres}" PGPORT="${GODLING_DB_PORT:-5432}"
export PGDATABASE="${GODLING_DB_NAME:-godling}" PGUSER="${GODLING_DB_USER:-godling}"
export PGPASSWORD="${GODLING_DB_PASSWORD:?set GODLING_DB_PASSWORD: the database is backed up with it}"
export PGOPTIONS="-c client_min_messages=warning" # not "database … does not exist, skipping"

HOST="${GODLING_DOMAIN:?set GODLING_DOMAIN: the snapshots of this site are named after it}"
FROM="${GODLING_BACKUP_FROM:-$HOST}" # whose snapshots a restore brings back

# Seconds between jobs; anything else falls back to the default, said in the log.
seconds() {
  case "$2" in
    '' | *[!0-9]*)
      log "GODLING_BACKUP_$1 is not a number of seconds ($2): $3 instead" >&2
      echo "$3"
      ;;
    *) echo "$2" ;;
  esac
}
DB_EVERY=$(seconds DB_EVERY "${GODLING_BACKUP_DB_EVERY:-3600}" 3600)
RUN_EVERY=$(seconds RUN_EVERY "${GODLING_BACKUP_RUN_EVERY:-21600}" 21600)
PRUNE_EVERY=$(seconds PRUNE_EVERY "${GODLING_BACKUP_PRUNE_EVERY:-86400}" 86400)
CHECK_EVERY=$(seconds CHECK_EVERY "${GODLING_BACKUP_CHECK_EVERY:-604800}" 604800)
KEEP="--keep-hourly 48 --keep-daily 14 --keep-weekly 8 --keep-monthly 12"
RUNS=/runs/live # the run, as the island has it
CHUNKS=/chunks  # the replay chunks' own volume (the island's /runs/live/replay/chunks)
STATE=/cache/state
METRICS=/metrics/godling_backup.prom
LOW="nice -n 10" # the backups give way to the world, the mind and the site
if command -v ionice > /dev/null 2>&1; then LOW="ionice -c 2 -n 7 $LOW"; fi

get() { cat "$STATE/$1" 2> /dev/null || true; }
put() { mkdir -p "$STATE" && echo "$2" > "$STATE/$1"; }

offsite() {
  case "$RESTIC_REPOSITORY" in
    /* | local:*) echo 0 ;;
    *) echo 1 ;;
  esac
}

# A long command, waited for so that a stop (TERM) reaches it: restic then removes its lock before it ends.
child=
run() {
  # shellcheck disable=SC2086 # LOW is a command and its options
  $LOW "$@" &
  child=$!
  rc=0
  wait "$child" || rc=$?
  child=
  return "$rc"
}

# Opens the repository. `make`: one that is not there yet is made (restic's exit 10); a restore never makes one. A
# wrong password (12), an unreachable bucket (which restic itself retries for 15 minutes) or anything else is said
# with restic's own words, and is a failure to try again.
ensure_repo() {
  if err=$(restic --no-lock cat config 2>&1 > /dev/null); then return 0; else rc=$?; fi
  if [ "$rc" -eq 10 ] && [ "${1:-}" = make ]; then
    log "making the repository at $RESTIC_REPOSITORY"
    restic init > /dev/null || return 1
  elif [ "$rc" -eq 10 ]; then
    log "there is no repository at $RESTIC_REPOSITORY: check GODLING_BACKUP_REPOSITORY"
    return 1
  elif [ "$rc" -eq 12 ]; then
    log "the repository at $RESTIC_REPOSITORY does not open with GODLING_BACKUP_PASSWORD"
    return 1
  else
    log "cannot open the repository at $RESTIC_REPOSITORY (restic exit $rc): $(echo "$err" | tr '\n' ' ' | cut -c1-300)"
    return 1
  fi
}

# Job state belongs to one repository and one site: another one starts with every job due.
repo_state() {
  where="$HOST $RESTIC_REPOSITORY"
  if [ "$(get repo)" != "$where" ]; then
    if [ -n "$(get repo)" ]; then log "backups now go to $RESTIC_REPOSITORY as $HOST: every job is due there"; fi
    rm -f "$STATE"/db_* "$STATE"/run_* "$STATE"/prune_* "$STATE"/check_* "$STATE"/chunks_* "$STATE/pruned"
    put repo "$where"
  fi
}

# "N KB added" and the snapshot's id, from restic's JSON summary.
summarize() {
  added=$(sed -n 's/.*"message_type":"summary".*"data_added":\([0-9]*\).*/\1/p' "$1" | tail -n 1)
  snap=$(sed -n 's/.*"message_type":"summary".*"snapshot_id":"\([0-9a-f]*\)".*/\1/p' "$1" | tail -n 1)
  log "$2: snapshot $(printf '%.8s' "${snap:-?}"), $((${added:-0} / 1024)) KB added"
}

# restic backup's exit 3: the snapshot was saved, but some files went or changed while being read.
saved() {
  if [ "$1" -eq 3 ]; then log "$2: some files changed or went while being read; the snapshot was saved"; fi
  [ "$1" -eq 0 ] || [ "$1" -eq 3 ]
}

# The jobs run inside `if` or `||`, where `set -e` does not hold, so each step says its own failure.

# The database as pg_dump's custom format (pg_restore can bring back all of it or part), streamed into restic: a dump
# that fails leaves no snapshot. Uncompressed, so restic finds what did not change; restic compresses it itself.
backup_db() {
  out=/cache/db.json
  run restic backup --json --quiet --host "$HOST" --tag db --stdin-filename godling.dump \
    --stdin-from-command -- pg_dump --format=custom --compress=0 --no-owner --no-privileges > "$out" || return 1
  summarize "$out" db
}

# The run: Godling's memory and logs, the island's save, the world script it runs, the replays' tracks, markers and
# state, and today's chunks (each finished day is saved on its own, below). Not the raw recordings (5 GB a day, and the
# chunks are made from them), the world's own log, the console (the same, and the spectator token), the agent key the
# launcher makes again at every start, or files being written (*.tmp).
backup_run() {
  out=/cache/run.json
  today="$CHUNKS/$(date -u +%Y-%m-%d)"
  if [ -d "$today" ]; then set -- "$RUNS" "$today"; else set -- "$RUNS"; fi
  rc=0
  run restic backup --json --quiet --host "$HOST" --tag run --exclude "$RUNS/recordings" \
    --exclude "$RUNS/world.log" --exclude "$RUNS/console.log" --exclude "$RUNS/world.key" \
    --exclude "$RUNS/replay/.packer.lock" --exclude '*.tmp' "$@" > "$out" || rc=$?
  saved "$rc" run || return 1
  summarize "$out" run
  chunk_days
}

# Each finished day of chunks, once, in a snapshot of its own that is never forgotten: chunks never change, so no
# backup reads the whole past again. A day the packer added to later (a catch-up) is saved again, uploading only what
# is new. With a replay bucket the island deletes its local days two days on, so this runs with every run backup.
chunk_days() {
  today=$(date -u +%Y%m%d)
  week_ago=$(date -u -d "@$(($(now) - 604800))" +%Y%m%d)
  for dir in "$CHUNKS"/????-??-??; do
    [ -d "$dir" ] || continue
    day=${dir##*/}
    num=$(echo "$day" | tr -d -)
    [ "$num" -lt "$today" ] || continue
    had=$(get "chunks_$day")
    if [ -n "$had" ] && [ "$num" -lt "$week_ago" ]; then continue; fi
    files=$(find "$dir" -type f -name '*.json.gz' | wc -l)
    [ "$had" != "$files" ] || continue
    rc=0
    run restic backup --quiet --host "$HOST" --tag chunks --tag "day=$day" "$dir" > /dev/null || rc=$?
    saved "$rc" "chunks of $day" || return 1
    put "chunks_$day" "$files"
    log "chunks: $day saved ($files)"
  done
}

# Old database and run snapshots forgotten daily (the days of chunks are kept for good), and the space they held
# freed weekly: freeing reads every index and tree, for a few MB a day.
prune() {
  last=$(get pruned)
  if [ -n "$last" ] && [ $(($(now) - last)) -lt 604800 ]; then free=""; else free="--prune"; fi
  # shellcheck disable=SC2086 # KEEP is a list of options; free is one or none
  run restic forget --quiet --host "$HOST" --tag db --tag run --group-by host,tags $KEEP $free || return 1
  if [ -n "$free" ]; then put pruned "$(now)"; fi
  log "prune: old snapshots forgotten${free:+, their space freed}"
}

# A snapshot of this site (FROM, for a restore) of one kind: its full id, from "latest" or the start of an id.
# restic's own --host and --tag apply only to "latest", so an id is checked here against the list of that kind.
resolve() {
  ids=$(restic --no-lock snapshots --json --host "$3" --tag "$1" | grep -o '"id":"[0-9a-f]*"' | cut -d'"' -f4) ||
    return 1
  if [ "$2" = latest ]; then
    id=$(echo "$ids" | tail -n 1)
  else
    id=$(echo "$ids" | grep "^$2" | tail -n 1)
  fi
  if [ -z "$id" ]; then
    log "no $1 snapshot of $3 matches \"$2\" (backup snapshots lists them)"
    return 1
  fi
  echo "$id"
}

when() { restic --no-lock snapshots --json "$1" | grep -o '"time":"[^"]*"' | head -n 1 | cut -d'"' -f4 | cut -c1-19; }

# The database of a snapshot into a database of its own name, in one transaction: all of it or none.
restore_into() {
  run restic --no-lock dump "$2" /godling.dump > "$3/godling.dump" || return 1
  { dropdb --if-exists "$1" && createdb "$1"; } || return 1
  if ! run pg_restore --single-transaction --exit-on-error --no-owner --no-privileges -d "$1" "$3/godling.dump"; then
    dropdb --if-exists "$1" || true
    return 1
  fi
  rm -f "$3/godling.dump"
}

# A twentieth of the stored data read back and checked, a different twentieth each week, so every part is read within
# twenty weeks. Then the newest database snapshot restored into a scratch database, which must hold the same tables as
# the live one; and the newest run snapshot must hold the island's save.
check() {
  slice=$(($(now) / 604800 % 20 + 1))
  run restic check --quiet --with-cache --read-data-subset="$slice/20" || return 1
  id=$(resolve db latest "$HOST") || return 1
  work=$(mktemp -d /cache/check.XXXXXX)
  scratch=godling_restore_check
  if ! restore_into "$scratch" "$id" "$work"; then
    rm -rf "$work"
    log "check: the newest database snapshot did not restore"
    return 1
  fi
  rm -rf "$work"
  tables="select string_agg(tablename, ' ' order by tablename) from pg_tables where schemaname = 'public'"
  live=$(psql -XAtc "$tables") || return 1
  restored=$(psql -XAt -d "$scratch" -c "$tables") || return 1
  dropdb --if-exists "$scratch" || true
  if [ "$live" != "$restored" ]; then
    log "check: the restored database's tables differ from the live one's (a new migration since? it passes after the next database backup)"
    return 1
  fi
  if [ -e "$RUNS/island-save.json" ]; then
    run_id=$(resolve run latest "$HOST") || return 1
    if ! restic --no-lock dump "$run_id" "$RUNS/island-save.json" | head -c 1 | grep -q '{'; then
      log "check: the newest run snapshot has no island save"
      return 1
    fi
  fi
  log "check: data slice $slice/20 read back well; the newest database snapshot restores ($(echo "$live" | wc -w) tables)"
}

# What each job last did, for node-exporter's textfile collector: written whole, then moved into place. A job is
# late from its last success (or from the service's start) plus three of its intervals; the weekly check a day after
# its week. The heartbeat is written every minute while the service runs.
write_metrics() {
  mkdir -p "$(dirname "$METRICS")"
  tmp=$(mktemp "$METRICS.XXXXXX")
  start=$(get started)
  {
    echo "# HELP godling_backup_last_success_timestamp_seconds When each backup job last finished well."
    echo "# TYPE godling_backup_last_success_timestamp_seconds gauge"
    for w in db run prune check; do
      v=$(get "${w}_ok")
      if [ -n "$v" ]; then echo "godling_backup_last_success_timestamp_seconds{what=\"$w\"} $v"; fi
    done
    echo "# HELP godling_backup_late_after_timestamp_seconds When each backup job counts as late, unless it finishes well first."
    echo "# TYPE godling_backup_late_after_timestamp_seconds gauge"
    for w in db run prune check; do
      v=$(get "${w}_ok")
      v=${v:-$start}
      [ -n "$v" ] || continue
      case "$w" in
        db) a=$((DB_EVERY * 3)) ;;
        run) a=$((RUN_EVERY * 3)) ;;
        prune) a=$((PRUNE_EVERY * 3)) ;;
        *) a=$((CHECK_EVERY + 86400)) ;;
      esac
      if [ "$a" -lt 3600 ]; then a=3600; fi
      echo "godling_backup_late_after_timestamp_seconds{what=\"$w\"} $((v + a))"
    done
    echo "# HELP godling_backup_offsite Whether the backups go off this server (1) or stay on it (0)."
    echo "# TYPE godling_backup_offsite gauge"
    echo "godling_backup_offsite $(offsite)"
    v=$(get heartbeat)
    if [ -n "$v" ]; then
      echo "# HELP godling_backup_heartbeat_timestamp_seconds The backup service's last sign of life (every minute)."
      echo "# TYPE godling_backup_heartbeat_timestamp_seconds gauge"
      echo "godling_backup_heartbeat_timestamp_seconds $v"
    fi
  } > "$tmp"
  chmod 644 "$tmp" # node-exporter reads it as another user
  mv "$tmp" "$METRICS"
}

# One job: its outcome kept, reported, and returned.
attempt() {
  job=$1
  shift
  repo_state
  put "${job}_try" "$(now)"
  rc=0
  if ensure_repo make; then
    restic unlock > /dev/null 2>&1 || true # locks left by a restic that was stopped halfway
    "$@" || rc=$?
  else
    rc=1
  fi
  if [ "$rc" -eq 0 ]; then put "${job}_ok" "$(now)"; else log "$job: failed"; fi
  write_metrics
  return "$rc"
}

# Due when its last success is as old as its interval, or it never succeeded. A failed job waits: five minutes for
# the backups, an hour for the prune and the check, which are heavy to do again.
due() {
  ok=$(get "$1_ok")
  try=$(get "$1_try")
  t=$(now)
  case "$1" in db | run) retry=300 ;; *) retry=3600 ;; esac
  if [ -n "$ok" ] && [ $((t - ok)) -lt "$2" ]; then return 1; fi
  if [ -n "$try" ] && [ "$try" -gt "${ok:-0}" ] && [ $((t - try)) -lt "$retry" ]; then return 1; fi
  return 0
}

serve() {
  ticker=
  trap 'log "stopping"; [ -z "$ticker" ] || kill "$ticker" 2> /dev/null; [ -z "$child" ] || { kill -TERM "$child" 2> /dev/null; wait "$child" 2> /dev/null; }; exit 0' TERM INT
  log "backups of $HOST to $RESTIC_REPOSITORY: the database every $((DB_EVERY / 60)) min, the run every $((RUN_EVERY / 60)) min"
  if [ "$(offsite)" = 0 ]; then
    log "these backups stay on this server: set GODLING_BACKUP_REPOSITORY to a bucket (deploy/README.md, Backups)"
  fi
  repo_state
  put started "$(now)"
  (while :; do
    put heartbeat "$(now)"
    write_metrics
    sleep 60
  done) &
  ticker=$!
  told=
  while :; do
    r=$(get restoring)
    if [ -n "$r" ] && [ $(($(now) - r)) -lt 21600 ]; then # a restore is running (or died within six hours)
      if [ -z "$told" ]; then log "a restore is running: the backups wait for it"; fi
      told=1
    else
      told=
      if due db "$DB_EVERY"; then attempt db backup_db || true; fi
      if due run "$RUN_EVERY"; then attempt run backup_run || true; fi
      if due prune "$PRUNE_EVERY"; then attempt prune prune || true; fi
      if due check "$CHECK_EVERY"; then attempt check check || true; fi
    fi
    sleep 60 &
    wait $! || true
  done
}

# Restores. The backups wait meanwhile (`restoring`, in the cache both services share). Read-only: no lock is taken,
# so a key that may only read works, and a lock left by a lost server stands in nobody's way.
restore() {
  what=${1:-}
  snap=${2:-latest}
  opt=${3:-}
  case "$what" in db | run) ;; *)
    echo "usage: backup restore db|run [snapshot] [--replay]" >&2
    return 2
    ;;
  esac
  ensure_repo || return 1
  id=$(resolve "$what" "$snap" "$FROM") || return 1
  at=$(when "$id")
  put restoring "$(now)"
  work=$(mktemp -d /cache/restore.XXXXXX)
  trap 'rm -rf "$work"; rm -f "$STATE/restoring"' EXIT
  log "restore: the $what of $FROM as it was at $at UTC (snapshot $(printf '%.8s' "$id"))"
  if [ "$what" = db ]; then
    restore_db "$id" "$work" || return 1
    log "restore: done. Stripe payments, refunds and disputes since then are not in it; bring them in with:"
    log "  docker compose exec site python manage.py reconcile_stripe --since ${at}Z"
  else
    restore_run "$id" "$opt" || return 1
  fi
}

# Beside the live database first, then in its place: the live one, if any, is kept as <name>_before_<UTC time>.
restore_db() {
  new="${PGDATABASE}_restored"
  restore_into "$new" "$1" "$2" || return 1
  old="${PGDATABASE}_before_$(date -u +%Y%m%d%H%M%S)"
  there=$(psql -XAt -d postgres -c "select 1 from pg_database where datname = '$PGDATABASE'") || return 1
  tries=0
  while :; do
    psql -Xq -d postgres -c "select pg_terminate_backend(pid) from pg_stat_activity
      where datname in ('$PGDATABASE', '$new') and pid <> pg_backend_pid()" > /dev/null || return 1
    if [ "$there" != 1 ] || psql -Xq -d postgres -c "alter database \"$PGDATABASE\" rename to \"$old\"" 2> /dev/null; then
      break
    fi
    tries=$((tries + 1))
    if [ "$tries" -ge 5 ]; then
      log "restore: the live database stays in use; stop the site and the worker (docker compose stop site worker)"
      return 1
    fi
    sleep 2
  done
  psql -Xq -d postgres -c "alter database \"$new\" rename to \"$PGDATABASE\"" || return 1
  if [ "$there" = 1 ]; then
    log "restore: the database before it is kept as $old; once you are sure: docker compose exec postgres dropdb -U $PGUSER $old"
  fi
}

# Over a run that has replays, they are kept (they show what happened, and the packer goes on from them): only
# Godling's memory, logs, the island's save and the world come back. Otherwise, or with --replay, the replays too:
# the snapshot's own, then every saved day of chunks.
restore_run() {
  if [ -e "$RUNS/replay/index.json" ] && [ "$2" != --replay ]; then
    log "restore: this run's replays are kept (restore run $(printf '%.8s' "$1") --replay brings them back too)"
    run restic --no-lock restore "$1" --target / --exclude "$RUNS/replay" --exclude "$CHUNKS" || return 1
  else
    run restic --no-lock restore "$1" --target / || return 1
    days=$(restic --no-lock snapshots --json --host "$FROM" --tag chunks | grep -o '"id":"[0-9a-f]*"' | cut -d'"' -f4) ||
      return 1
    n=0
    for day in $days; do
      run restic --no-lock restore "$day" --target / > /dev/null || return 1
      n=$((n + 1))
    done
    log "restore: the replays came back with it ($n saved days of chunks)"
  fi
  log "restore: the run is back"
}

usage() {
  echo "usage: backup serve | db | run | prune | check | snapshots | restore db|run [snapshot] [--replay]" >&2
}

case "${1:-}" in
  serve) serve ;;
  db) attempt db backup_db ;;
  run) attempt run backup_run ;;
  prune) attempt prune prune ;;
  check) attempt check check ;;
  snapshots)
    ensure_repo
    restic --no-lock snapshots --host "$FROM"
    echo "(times in UTC)"
    ;;
  restore)
    shift
    restore "$@"
    ;;
  *)
    usage
    exit 2
    ;;
esac
