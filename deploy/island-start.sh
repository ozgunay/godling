#!/bin/sh
# The island: the world on 8080 (mounted at WORLD_BASE_PATH, /island), Godling's mind, the guest panel on 8081,
# which only the site reaches (GODLING_PANEL_HOST=0.0.0.0 with GODLING_PANEL_KEY), and the stream relay on 8082, which
# Caddy sends the island's stream to (RELAY_*, ADR-015). The run continues across
# restarts in GODLING_RUN_DIR (a volume). GODLING_MIND_ARGS adds run_godling.py options, e.g. "--model deepseek-pro".
set -e
: "${DEEPSEEK_API_KEY:?set DEEPSEEK_API_KEY: the mind thinks with DeepSeek}"
: "${GODLING_PANEL_KEY:?set GODLING_PANEL_KEY: the panel takes powers and notes only from the site}"
# shellcheck disable=SC2086
exec python3 /app/mind/run_godling.py --run-dir "${GODLING_RUN_DIR:-/runs/live}" --port 8080 --guest-panel 8081 \
    --relay 8082 ${GODLING_MIND_ARGS:-}
