#!/bin/bash
# A fresh run for Godling: a new island, an empty memory, new replays (RUNBOOK.md). The old run is kept, not deleted,
# at /runs/old/<UTC time>/{live,chunks} in the runs volume. The site's database (accounts, credits, notes) is not
# touched. Run on the server, in deploy/:
#   ./fresh-run.sh             stops the island, moves the run aside, starts the island on an empty run
#   ./fresh-run.sh --no-start  the same, but leaves the island stopped
# The one trap it exists for: the island runs as its own user, and a /runs/live made by Docker or root is root-owned,
# so the island cannot write it and crash-loops. The new run is made owned by that user.
set -euo pipefail
cd "$(dirname "$0")"
start=1
[ "${1:-}" = --no-start ] && start=0

project=$(docker compose config --format json | python3 -c 'import json, sys; print(json.load(sys.stdin)["name"])')
runs="${project}_runs"
chunks="${project}_replay_chunks"
uid=$(docker compose run --rm --no-deps -T --entrypoint id island -u)
gid=$(docker compose run --rm --no-deps -T --entrypoint id island -g)
stamp=$(date -u +%Y%m%d-%H%M%S)

echo "stopping the island (it saves the island and Godling's memory first)"
docker compose stop island
docker run --rm -v "$runs:/runs" -v "$chunks:/chunks" alpine:3 sh -euc "
  mkdir -p /runs/old/$stamp/chunks && chmod 700 /runs/old
  [ ! -e /runs/live ] || mv /runs/live /runs/old/$stamp/live
  for d in /chunks/* /chunks/.[!.]*; do [ ! -e \"\$d\" ] || mv \"\$d\" /runs/old/$stamp/chunks/; done
  mkdir -p /runs/live/replay/chunks
  chown -R $uid:$gid /runs/live
  echo \"the old run is kept at /runs/old/$stamp (\$(du -sh /runs/old/$stamp | cut -f1)); the new run is empty\""
if [ "$start" = 1 ]; then
  docker compose up -d island
  echo "the island is starting a new life: docker compose logs -f island"
else
  echo "the island is stopped: docker compose start island begins the new life"
fi
