#!/usr/bin/env bash
# Long runs of Godling, one arm per memory type, side by side. One Ctrl+C stops all of them.
#
# Usage (inside WSL):
#   bash /mnt/c/Work/godling/tools/long_runs.sh [hours, default 8] [run-name prefix, default m] [start at HH:MM, or now] [arms]
# arms: any of "native native2 hindsight" (default: all three), e.g. "hindsight" for one arm.
# With a start time it waits until then (the next time that clock time comes round), so it can be armed early.
# All arms share the same mind and world (agenda + pipelined planning, deepseek-flash with full reasoning,
# Godling's world); they differ only in memory. Names and ports per arm:
#   native -> <prefix>-004-native :8090   native2 -> <prefix>-005-native2 :8091   hindsight -> <prefix>-006-hindsight :8092
set -u
HOURS="${1:-8}"
PREFIX="${2:-m}"
START_AT="${3:-now}"
ARMS="${4:-native native2 hindsight}"
MINUTES=$(python3 -c "print(int(float('$HOURS') * 60))")
RUNS="$HOME/godling-runs"
# The arms run a frozen copy of the mind and the world (laid out as in the project, so the mind finds its
# world), so work on the code can go on during a long run, and the copy records which version ran.
CODE="$RUNS/$PREFIX-code"
MIND="$CODE/mind/run_godling.py"
HS_PY="$HOME/.venvs/hindsight/bin/python"
SLEEP="--sleep-minutes ${GODLING_SLEEP_MINUTES:-60}"  # hourly consolidation; set lower to test it

declare -A NAME=([native]=004-native [native2]=005-native2 [hindsight]=006-hindsight)
declare -A PORT=([native]=8090 [native2]=8091 [hindsight]=8092)
for arm in $ARMS; do
  [ -n "${NAME[$arm]:-}" ] || { echo "unknown arm '$arm' (native, native2, hindsight)"; exit 1; }
  if [ -e "$RUNS/$PREFIX-${NAME[$arm]}" ]; then echo "$RUNS/$PREFIX-${NAME[$arm]} exists; pick another prefix."; exit 1; fi
done
if [ -e "$CODE" ]; then echo "$CODE exists; pick another prefix."; exit 1; fi

if [ "$START_AT" != "now" ]; then
  start=$(date -d "$START_AT" +%s) || exit 1
  [ "$start" -le "$(date +%s)" ] && start=$(date -d "tomorrow $START_AT" +%s)
  echo "Armed: $ARMS start at $(date -d "@$start" '+%a %H:%M') and run $HOURS h. Ctrl+C cancels."
  sleep $(( start - $(date +%s) )) || exit 1
fi
# The ports (and Hindsight's 8888) must be free: wait for an earlier run to finish shutting down.
while ss -ltn | grep -q -E ':(8090|8091|8092|8888) '; do echo "Waiting for ports 8090-8092 and 8888 to be free..."; sleep 15; done
# Frozen at start time, so fixes made while the run was armed are in it. GODLING_SRC runs another checkout (a worktree).
SRC="${GODLING_SRC:-/mnt/c/Work/godling}"
mkdir -p "$CODE" && cp -r "$SRC/mind" "$SRC/world" "$CODE" \
  && rm -rf "$CODE"/mind/godling/__pycache__ "$CODE"/world/renderer/.build.lock || exit 1

PIDS=()
for arm in $ARMS; do
  py=python3
  [ "$arm" = hindsight ] && py="$HS_PY"
  "$py" "$MIND" --run-dir "$RUNS/$PREFIX-${NAME[$arm]}" --memory "$arm" --port "${PORT[$arm]}" --minutes "$MINUTES" $SLEEP \
    > "$RUNS/$PREFIX-${NAME[$arm]}.console" 2>&1 &
  PIDS+=($!)
done

stop() {
  echo
  echo "Stopping (waiting for a clean shutdown)..."
  kill -TERM "${PIDS[@]}" 2>/dev/null
}
trap stop INT TERM

echo "Started $ARMS for $HOURS h (until $(date -d "+$MINUTES minutes" '+%H:%M')). Ctrl+C stops all of them."
echo "Watch (spectator links appear in each console within a minute):"
for arm in $ARMS; do echo "  tail -f $RUNS/$PREFIX-${NAME[$arm]}.console"; done
sleep 45
for arm in $ARMS; do grep -h "Watch it here" "$RUNS/$PREFIX-${NAME[$arm]}.console" 2>/dev/null; done
wait "${PIDS[@]}" 2>/dev/null
wait "${PIDS[@]}" 2>/dev/null  # a trapped signal interrupts the first wait
echo
echo "Finished. Comparison:"
python3 /mnt/c/Work/godling/tools/compare_runs.py $(for arm in $ARMS; do echo "$RUNS/$PREFIX-${NAME[$arm]}"; done)
