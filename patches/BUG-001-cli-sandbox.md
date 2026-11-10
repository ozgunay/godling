# BUG-001 — Sandboxed Claude agent can't reach a local world (CLI)

| Field | Value |
|---|---|
| BUG ID | BUG-001 |
| Upstream SHA | `8be90a0` (v0.1.5-2), nacloos/clawblox |
| Fix branch | `v0-fix/cli-sandbox` in the WSL clone `~/clawblox` (uncommitted working-tree change) |
| Patch | [v0-fix-cli-sandbox.patch](v0-fix-cli-sandbox.patch): the whole fix branch (BUG-001 is 1 line in `src/agent.rs`; BUG-005 is below) |
| Status | **Fixed and verified 2026-10-31.** Smoke test passed |

## Reproduction steps

On Ubuntu 22.04 (WSL2), with bubblewrap 0.6.1, socat 1.7.4.1 and Claude Code 2.1.x:

```bash
clawblox run worlds/mesa-island --agent claude --sandbox --record --record-dir ~/godling-runs/a-002/recordings --agent-dir ~/godling-runs/a-002/agent
```

## Expected / observed

- **Expected:** the agent joins Mesa Island and acts, as it does without `--sandbox`.
- **Observed:** the agent reports that the sandbox network configuration blocks `localhost`/`127.0.0.1`, ends its turn, and never sends an `/input`.

## Root cause

- The CLI sets `WORLD_BASE_URL=http://localhost:<port>` and runs Claude with its **native sandbox** turned on.
- Claude's native sandbox gives commands a private network namespace with `no_proxy=localhost,127.0.0.1,…`. A request to `localhost` goes to the sandbox's *own* loopback, not the host's, so the world is unreachable whatever domain policy is set.
  - Tried first: honouring `WORLD_ALLOW_LOOPBACK` and allow-listing `localhost`. That produced the policy `{"allowedDomains":["localhost"],"deniedDomains":[]}`, but the agent still got "couldn't connect" (curl exit 7) with the world running.
- Upstream's Python API handles this in two ways. It can route the agent through a capability proxy at `http://world`. Or it can turn the native sandbox off (`claude_native_sandbox=False`) and rely on Clawblox's outer bubblewrap, which shares the host network.
- The CLI can do neither. `CLAWBLOX_CLAUDE_NATIVE_SANDBOX` is read with `env_value`, which only sees per-agent settings, and the CLI can't set those.

## Minimum code diff

`src/agent.rs`, `write_claude_sandbox_settings`: `env_value` → `effective_env_value` (which falls back to the process environment). One line changed. Without the variable set, behaviour is identical to upstream.

```bash
CLAWBLOX_CLAUDE_NATIVE_SANDBOX=0 clawblox run <world> --agent claude --sandbox …
```

## What the sandbox still enforces in this mode

- Clawblox's outer bubblewrap runs the agent as a mapped user. Writes are limited to its agent folder (`/workspace`, home, runtime) and system dirs are read-only.
- `/tmp` is a fresh tmpfs, and **`/mnt/c` is not mounted**. The only `/mnt` path visible is `/mnt/wsl/resolv.conf`, for DNS.
- **Not enforced:** network. The agent can reach the internet and any service on WSL's localhost. This matches the Python API's `claude_native_sandbox=False` mode, minus the capability proxy.

## Regression tests

- **Smoke test** (`smoke_sandbox_8092.sh`, run on port 8080): a home-dir copy of Mesa Island, a sandboxed Claude agent, and upstream's default prompt rendered.
  - **PASS:** the 1st agent action arrived after ~55 s, the 2nd after ~67 s (`MoveTo`, `Pickup → PickupFailed:NoBlock`). The character moved from x≈0.5 to x≈13.7.
- **Unit test:** none added. Setting process env vars in tests would race with upstream's parallel test runner.

## Remaining risk

- With network unfiltered, a prompt-injected or confused agent could make outbound requests.
- The proper upstream fix is to give the CLI the Python API's capability proxy (`http://world`). Report it upstream.

## Rollback

```bash
cd ~/clawblox && git checkout -- src/agent.rs && git switch --detach 8be90a0 && cargo install --path . --locked
```

---

# BUG-005 — Ctrl+C leaves the agent running (and spending tokens)

| Field | Value |
|---|---|
| Branch | same `v0-fix/cli-sandbox` |
| Files | `src/agent_runner.rs` (+~110 lines), `src/bin/cli.rs` (+~37 lines) |
| Status | **Fixed and verified 2026-10-31** (zero-token test, below) |

**Observed in run a-003:**
- After Ctrl+C, the world shut down, but the Claude agent kept running in its tmux session.
- It polled the dead world every 10–15 s, and every poll was a full-context model call.
- It only stopped when killed by hand.
- Separately, 3 helper processes from Claude's native sandbox (`bwrap --new-session`) survived even `tmux kill-session`.

**Root cause:**
- `clawblox run --agent` starts the agent in tmux, but its shutdown path never stops it.
- Upstream's own `stop_agent()` exists; only the CLI never calls it.
- `tmux kill-session` only signals the pane's session, so processes that detach themselves (`setsid`, `bwrap --new-session`, `nohup … &`) escape it.

**Fix:**
1. Once the agent has started, the CLI keeps its stop options.
2. After the server shuts down, it calls the new `stop_agent_and_descendants()`. That does three things:
   - records the agent pane's whole process tree;
   - runs upstream's `stop_agent()` (Ctrl+C in the pane, 5 s grace, kill the tmux target, collect the transcript, log `agent.stop`);
   - sends SIGTERM, then SIGKILL after 3 s, to every recorded process.
3. On Linux it also kills every process sharing the sandbox's private user namespace (`bwrap --unshare-user`), which catches orphans that left the tree.

The recovery watchdog is a thread inside `clawblox`, so it ends with the process.

**Test** (`test_ctrlc_cleanup.sh`): a fake `claude` that leaves behind a `setsid` child, a background job, a `nohup` orphan (re-parented out of the tree) and itself. After Ctrl+C:
- **PASS:** all 4 are gone.
- **PASS:** the tmux session is gone.
- The server log shows "Stopping agent 'agent'... Agent stopped."
- `events.jsonl` ends with `agent.stop: stopped`.

---

# DeepSeek wiring (no code change)

- Clawblox strips `ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_API_KEY` from the sandbox, and copies `$CLAUDE_CONFIG_DIR/.credentials.json` (default `~/.claude`) into it.
- It does **not** strip `ANTHROPIC_BASE_URL`. Setting only that would send your Anthropic subscription token to DeepSeek.
- Safe route: `tools/setup_deepseek.sh` creates `~/.claude-deepseek/settings.json`. That file holds an `env` block (base URL, key, `deepseek-flash` for every model slot, nonessential traffic off), is readable only by you, and the folder never holds an Anthropic login.
- Run with `CLAUDE_CONFIG_DIR=$HOME/.claude-deepseek … --model deepseek-flash`.

**Zero-token wiring test** (fake claude, dummy key):
- **PASS:** the DeepSeek env block reached `sandbox-home/.claude/settings.json`.
- **PASS:** no `.credentials.json` in the sandbox.
- **PASS:** `--model deepseek-flash` was passed to claude.

---

## Related upstream findings (not patched; work around them)

| ID | Finding | Workaround used in the baseline |
|---|---|---|
| BUG-002 | **The CLI's agent system prompt is only the world's `API.md`.** `cli.rs` passes `agent_skill_md` as the prompt, so upstream's `DEFAULT_SYSTEM_PROMPT` (autonomous being, memory files, SOUL.md, auto-continue note) is never used. The agent treats "Begin" as a request from a user ("How can I help you today?"). | `--system-prompt` with upstream's default prompt, rendered by `tools/render_default_prompt.py` (wording unchanged). |
| BUG-003 | **`DEFAULT_SYSTEM_PROMPT` placeholders (`${WORKSPACE_DIR}`, `${WORLD_BASE_URL}`, `${SESSION_LINE}`, `${SKILL_CURL}`, `${SKILL_URL}`) are never substituted** anywhere in the code. | Rendered with `/workspace`, `http://localhost:8080`, a join hint, `curl -s`, `…/api.md`. |
| BUG-004 | **Claude hook scripts (`stop.sh` etc.) need Linux `node`,** which isn't a documented requirement. Without it, auto-continue fails inside the sandbox, and only the 180 s idle watchdog nudges the agent. | `sudo apt install -y nodejs` (v12.22.9 is enough). |
| BUG-006 | **Agent vision silently broken on WSL.** `/observe/image` launches Playwright's headless Chromium, which needs `libnss3`/`libnspr4` (not installed, not documented). The endpoint returns the text `Capture browser exited before exposing DevTools endpoint`, which agents save as `view.png`. In runs a-003 and a-004, **0 images ever reached the model** (Opus asked 2 times, DeepSeek 6 times); both agents worked purely from the JSON observation. | `sudo apt install -y libnss3 libnspr4`. Note it in run metadata, because a run with vision isn't comparable to the earlier blind runs. |
| NOTE-1 | Mesa's `API.md` hard-codes `http://localhost:8080`, and the agent follows it even when the world runs on another port. | Run Mesa on 8080 only. |
| NOTE-2 | Agent folders under `/tmp` silently lose their prompt and hooks inside the sandbox (fresh tmpfs). | Keep run folders under `~/godling-runs/`. |
| NOTE-3 | Reusing an `--agent-dir` after an aborted start fails with "Session ID … already in use". (The tmux session outliving Ctrl+C is fixed by BUG-005.) | Use a fresh folder per run. |
| NOTE-4 | Upstream removed the persona and memory templates on 2026-08-19 (`c3a9f4c`). The prompt still references `SOUL.md`, so the agent writes its own. | Baseline runs start with an empty workspace. |
