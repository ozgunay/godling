"""Render upstream's DEFAULT_SYSTEM_PROMPT (src/agent_runner.rs) with concrete values.

Upstream never substitutes the ${...} placeholders, and the CLI uses the world's API.md as the
whole system prompt unless --system-prompt is given. This writes the paper-style default prompt
with only the placeholders filled in; the wording is upstream's, unchanged.
"""
import re
import sys
from pathlib import Path

repo, out, port, name = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
src = (repo / "src/agent_runner.rs").read_text(encoding="utf-8")
prompt = re.search(r'DEFAULT_SYSTEM_PROMPT: &str = r#"(.*?)"#;', src, re.S).group(1)
base = f"http://localhost:{port}"
values = {
    "WORLD_AGENT_NAME": name,
    "WORKSPACE_DIR": "/workspace",  # guest path inside Clawblox's bubblewrap
    "WORLD_BASE_URL": base,
    "SESSION_LINE": f"Join the world with: curl -s -X POST '{base}/join?name={name}'",
    "SKILL_CURL": "curl -s",
    "SKILL_URL": f"{base}/api.md",
}
rendered = re.sub(r"\$\{([A-Z_]+)\}", lambda m: values[m.group(1)], prompt)
leftover = re.findall(r"\$\{[A-Z_]+\}", rendered)
if leftover:
    sys.exit(f"unrendered placeholders: {leftover}")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(rendered, encoding="utf-8")
print(f"wrote {out} ({len(rendered)} bytes)")
