#!/usr/bin/env bash
# One-time setup: a separate Claude Code config folder that talks to DeepSeek instead of Anthropic.
#
# Clawblox copies $CLAUDE_CONFIG_DIR/settings.json into each agent's sandbox, and copies a login
# only if that folder has one. This folder never gets an Anthropic login, so the agent can't fall
# back to (or leak) your Claude subscription. Claude Code applies the "env" block itself.
#
# Usage (inside WSL):  bash /mnt/c/Work/godling/tools/setup_deepseek.sh
set -euo pipefail
dir="$HOME/.claude-deepseek"
mkdir -p "$dir"
chmod 700 "$dir"
read -rsp "Paste your DeepSeek API key (input hidden): " DEEPSEEK_KEY
echo
[ -n "$DEEPSEEK_KEY" ] || { echo "No key entered."; exit 1; }
umask 077
export DEEPSEEK_KEY SETTINGS="$dir/settings.json"
python3 - <<'PY'
import json, os, urllib.request, urllib.error

key = os.environ["DEEPSEEK_KEY"]
settings = {
    "env": {
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
        "ANTHROPIC_AUTH_TOKEN": key,
        "ANTHROPIC_MODEL": "deepseek-flash",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-flash",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-flash",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-flash",
        "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-flash",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
}
with open(os.environ["SETTINGS"], "w") as f:
    json.dump(settings, f, indent=2)
print(f"Wrote {os.environ['SETTINGS']} (readable only by you).")

# One tiny request to check the key (a fraction of a cent).
body = json.dumps({"model": "deepseek-flash", "max_tokens": 16,
                   "messages": [{"role": "user", "content": "Reply with the word OK."}]}).encode()
req = urllib.request.Request(
    "https://api.deepseek.com/anthropic/v1/messages", data=body, method="POST",
    headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    print(f"Key works: model={data.get('model')} reply={text.strip()!r}")
except urllib.error.HTTPError as err:
    print(f"Key check FAILED: HTTP {err.code} {err.read()[:200]!r}")
    raise SystemExit(1)
PY
