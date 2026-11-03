#!/bin/sh
# Backups (ADR-018): the database every hour and the run every six hours, as encrypted, deduplicated restic snapshots
# in GODLING_BACKUP_REPOSITORY (an S3-compatible bucket, such as Cloudflare R2; without one, a volume on this server).
# Old snapshots are pruned once a day. Once a week the repository is checked, and the newest database snapshot is
# restored into a scratch database. What each job last did is written for node-exporter to hand to Prometheus
# (deploy/monitoring/alerts.yml, "backups").
#
#   backup serve                    the loop the backup service runs
#   backup db | run | prune | check one job now
#   backup snapshots                what the repository holds
#   backup restore db [snapshot]    the database from a snapshot (default: the newest), over the live one (README)
#   backup restore run [snapshot]   the run from a snapshot, over the runs volume (README)
# shellcheck shell=sh
set -eu

export RESTIC_REPOSITORY="${GODLING_BACKUP_REPOSITORY:-/backups/repo}"
export RESTIC_PASSWORD="${GODLING_BACKUP_PASSWORD:?set GODLING_BACKUP_PASSWORD: without it no backup can be read}"
export RESTIC_CACHE_DIR=/cache/restic
if [ -n "${GODLING_BACKUP_KEY_ID:-}" ]; then
  export AWS_ACCESS_KEY_ID="$GODLING_BACKUP_KEY_ID" AWS_SECRET_ACCESS_KEY="${GODLING_BACKUP_SECRET:-}"
fi
export AWS_DEFAULT_REGION="${GODLING_BACKUP_REGION:-auto}"
export PGHOST="${PGHOST:-postgres}" PGUSER="${PGUSER:-godling}" PGDATABASE="${PGDATABASE:-godling}"
export PGPASSWORD="${GODLING_DB_PASSWORD:?set GODLING_DB_PASSWORD: the database is backed up with it}"
export PGOPTIONS="-c client_min_messages=warning" # not "database … does not exist, skipping"

DB_EVERY="${GODLING_BACKUP_DB_EVERY:-3600}"
RUN_EVERY="${GODLING_BACKUP_RUN_EVERY:-21600}"
PRUNE_EVERY="${GODLING_BACKUP_PRUNE_EVERY:-86400}"
CHECK_EVERY="${GODLING_BACKUP_CHECK_EVERY:-604800}"
RETRY=300 # a job that failed is tried again after this, not every minute
KEEP="--keep-hourly 48 --keep-daily 14 --keep-weekly 8 --keep-monthly 12"
HOST=godling # one name for every snapshot, whatever the container is called
RUN=/runs/live
STATE=/cache/state
METRICS=/metrics/godling_backup.prom

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }
now() { date +%s; }
get() { cat "$STATE/$1" 2>/dev/null || true; }
put() { mkdir -p "$STATE" && echo "$2" > "$STATE/$1"; }

offsite() {
  case "$RESTIC_REPOSITORY" in
    /* | local:*) echo 0 ;;
    *) echo 1 ;;
  esac
}

# The repository, made on first use. Exit code 10 is restic's "no repository there"; anything else (12, a wrong
# password; a bucket out of reach, which restic itself retries for 15 minutes) is a failure to try again, never a
# reason to make a new one.
ensure_repo() {
  rc=0
  restic cat config > /dev/null 2>&1 || rc=$?
  if [ "$rc" -eq 10 ]; then
    log "making the repository at $RESTIC_REPOSITORY"
    restic init
  elif [ "$rc" -eq 12 ]; then
    log "the repository at $RESTIC_REPOSITORY does not open with GODLING_BACKUP_PASSWORD"
    return 1
  elif [ "$rc" -ne 0 ]; then
    log "cannot reach the repository at $RESTIC_REPOSITORY (restic exit $rc): its address, its keys, or the network"
    return 1
  fi
}

# "added N bytes" from restic's JSON summary, and the snapshot's id.
summarize() {
  added=$(sed -n 's/.*"message_type":"summary".*"data_added":\([0-9]*\).*/\1/p' "$1" | tail -n 1)
  snap=$(sed -n 's/.*"message_type":"summary".*"snapshot_id":"\([0-9a-f]*\)".*/\1/p' "$1" | tail -n 1)
  put "$2_added" "${added:-0}"
  log "$2: snapshot $(printf '%.8s' "${snap:-?}"), $(( ${added:-0} / 1024 )) KB added"
}

# The jobs run inside `if`, where `set -e` does not hold, so each step says its own failure.

# The database as pg_dump's custom format (pg_restore can bring back all of it or part), streamed into restic: a dump
# that fails leaves no snapshot. Uncompressed, so restic finds what an hour did not change and stores it once; restic
# compresses what it stores itself.
backup_db() {
  out=/cache/db.json
  restic backup --json --quiet --host "$HOST" --tag db --stdin-filename godling.dump \
    --stdin-from-command -- pg_dump --format=custom --compress=0 --no-owner --no-privileges > "$out" || return 1
  summarize "$out" db
}

# The run: Godling's memory and logs, the island's save, the world script it runs, and the replays (tracks, markers and
# chunks). Not the raw recordings (5 GB a day, and the chunks are made from them), the world's own log, or the agent
# key the launcher makes again at every start.
backup_run() {
  out=/cache/run.json
  restic backup --json --quiet --host "$HOST" --tag run \
    --exclude "$RUN/recordings" --exclude "$RUN/world.log" --exclude "$RUN/world.key" \
    --exclude "$RUN/replay/.packer.lock" "$RUN" > "$out" || return 1
  summarize "$out" run
}

prune() {
  # shellcheck disable=SC2086 # KEEP is a list of options
  restic forget --quiet --host "$HOST" --group-by host,tags $KEEP --prune || return 1
  kept=$(restic --no-lock snapshots --json --host "$HOST" | grep -o '"short_id"' | wc -l) || return 1
  log "prune: $kept snapshots kept"
}

# A twentieth of the stored data read back and checked; then the newest database snapshot restored into a scratch
# database, which must hold the same tables as the live one. The newest run snapshot must hold the island's save.
check() {
  restic check --quiet --read-data-subset=5% || return 1
  scratch=godling_restore_check
  dump=/cache/check.dump
  restic dump --host "$HOST" --tag db latest /godling.dump > "$dump" || return 1
  dropdb --if-exists "$scratch" && createdb "$scratch" || return 1
  restored_well=1
  pg_restore --no-owner --no-privileges --exit-on-error -d "$scratch" "$dump" || restored_well=0
  tables="select string_agg(tablename, ' ' order by tablename) from pg_tables where schemaname = 'public'"
  live=$(psql -XAtc "$tables") || restored_well=0
  restored=$(psql -XAt -d "$scratch" -c "$tables") || restored_well=0
  rows=$(psql -XAt -d "$scratch" -c "select coalesce(sum((xpath('/row/n/text()', query_to_xml(format(
    'select count(*) as n from %I.%I', schemaname, tablename), false, true, '')))[1]::text::bigint), 0)
    from pg_tables where schemaname = 'public'") || restored_well=0
  dropdb --if-exists "$scratch" || true
  rm -f "$dump"
  if [ "$restored_well" != 1 ]; then
    log "check: the newest database snapshot did not restore"
    return 1
  fi
  if [ "$live" != "$restored" ]; then
    log "check: the restored database's tables differ from the live one's"
    return 1
  fi
  # Read whole and without a lock: a reader cut short (grep -q) would leave its lock, and that blocks the next check.
  if [ -e "$RUN/island-save.json" ]; then
    listing=$(restic --no-lock ls --host "$HOST" --tag run latest "$RUN/island-save.json") || return 1
    case "$listing" in
      *island-save.json*) ;;
      *)
        log "check: the newest run snapshot has no island save"
        return 1
        ;;
    esac
  fi
  log "check: the data read back well; the newest database snapshot restores ($(echo "$live" | wc -w) tables, $rows rows)"
}

# What each job last did, for node-exporter's textfile collector: written whole, then moved into place.
write_metrics() {
  mkdir -p "$(dirname "$METRICS")"
  tmp="$METRICS.tmp"
  {
    echo "# HELP godling_backup_last_success_timestamp_seconds When each backup job last finished well."
    echo "# TYPE godling_backup_last_success_timestamp_seconds gauge"
    for w in db run prune check; do
      v=$(get "${w}_ok")
      if [ -n "$v" ]; then echo "godling_backup_last_success_timestamp_seconds{what=\"$w\"} $v"; fi
    done
    echo "# HELP godling_backup_last_failed Whether each backup job's last try failed."
    echo "# TYPE godling_backup_last_failed gauge"
    for w in db run prune check; do
      v=$(get "${w}_failed")
      if [ -n "$v" ]; then echo "godling_backup_last_failed{what=\"$w\"} $v"; fi
    done
    echo "# HELP godling_backup_added_bytes What the last snapshot of each kind added to the repository."
    echo "# TYPE godling_backup_added_bytes gauge"
    for w in db run; do
      v=$(get "${w}_added")
      if [ -n "$v" ]; then echo "godling_backup_added_bytes{what=\"$w\"} $v"; fi
    done
    echo "# HELP godling_backup_offsite Whether the backups go off this server (1) or stay on it (0)."
    echo "# TYPE godling_backup_offsite gauge"
    echo "godling_backup_offsite $(offsite)"
    v=$(get started)
    if [ -n "$v" ]; then
      echo "# HELP godling_backup_started_timestamp_seconds When the backup service started: a job that never finished well is late from here."
      echo "# TYPE godling_backup_started_timestamp_seconds gauge"
      echo "godling_backup_started_timestamp_seconds $v"
    fi
  } > "$tmp"
  mv "$tmp" "$METRICS"
}

# One job, its outcome kept and reported.
attempt() {
  job=$1
  shift
  put "${job}_try" "$(now)"
  if ensure_repo && "$@"; then
    put "${job}_ok" "$(now)"
    put "${job}_failed" 0
  else
    put "${job}_failed" 1
    log "$job: failed; tried again in $((RETRY / 60)) minutes"
  fi
  write_metrics
}

# Due when its last success is as old as its interval, or it has never succeeded; a failing job waits RETRY.
due() {
  ok=$(get "$1_ok")
  try=$(get "$1_try")
  t=$(now)
  if [ -n "$ok" ] && [ $((t - ok)) -lt "$2" ]; then return 1; fi
  if [ -n "$try" ] && [ "$try" -gt "${ok:-0}" ] && [ $((t - try)) -lt "$RETRY" ]; then return 1; fi
  return 0
}

serve() {
  trap 'log "stopping"; exit 0' TERM INT
  log "backups to $RESTIC_REPOSITORY: the database every $((DB_EVERY / 60)) min, the run every $((RUN_EVERY / 60)) min"
  if [ "$(offsite)" = 0 ]; then
    log "these backups stay on this server: set GODLING_BACKUP_REPOSITORY to a bucket (deploy/README.md, Backups)"
  fi
  restic unlock > /dev/null 2>&1 || true # a lock left by a backup stopped halfway
  put started "$(now)"
  write_metrics
  while :; do
    if due db "$DB_EVERY"; then attempt db backup_db; fi
    if due run "$RUN_EVERY"; then attempt run backup_run; fi
    if due prune "$PRUNE_EVERY"; then attempt prune prune; fi
    if due check "$CHECK_EVERY"; then attempt check check; fi
    sleep 60 &
    wait $!
  done
}

restore() {
  what=${1:-}
  snap=${2:-latest}
  case "$what" in
    db)
      # Over the live database, as it was at the snapshot: for a new server, or after a mistake. Stop the site and
      # the worker first (deploy/README.md).
      dump=/cache/restore.dump
      restic dump --host "$HOST" --tag db "$snap" /godling.dump > "$dump" || return 1
      pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error -d "$PGDATABASE" "$dump" || return 1
      rm -f "$dump"
      log "restore: the database is back as it was at snapshot $snap"
      ;;
    run)
      # Over the runs volume, with the island stopped (deploy/README.md). Files the snapshot does not hold are left.
      restic restore --host "$HOST" --tag run "$snap" --target / || return 1
      log "restore: the run is back as it was at snapshot $snap"
      ;;
    *)
      echo "usage: backup restore db|run [snapshot]" >&2
      return 2
      ;;
  esac
}

case "${1:-serve}" in
  serve) serve ;;
  db) attempt db backup_db ;;
  run) attempt run backup_run ;;
  prune) attempt prune prune ;;
  check) attempt check check ;;
  snapshots) restic --no-lock snapshots --host "$HOST" ;;
  restore) shift && ensure_repo && restore "$@" ;;
  *)
    echo "usage: backup serve | db | run | prune | check | snapshots | restore db|run [snapshot]" >&2
    exit 2
    ;;
esac
