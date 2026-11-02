# SEC-001: the agent API stays private; the spectator token only watches

| Field | Value |
|---|---|
| Upstream SHA | `8be90a0` (v0.1.5-2), nacloos/clawblox, with [v0](v0-fix-cli-sandbox.patch) and [v1](v1-viewer-terrain-and-offline.patch) applied first |
| Patch | [v2-private-agent-api.patch](v2-private-agent-api.patch) (`src/bin/cli.rs` only) |
| Status | **Built and tested 2026-11-02** in WSL (Ubuntu 22.04): `cargo build --release`, then probed live on a scratch world (below) |
| Goes with | ADR-014; `mind/godling/world.py`, `mind/run_godling.py`, `tools/guest_panel.py`, `tools/god_bot.py` |

## What was wrong
Found in the security review of 2026-11-02, and confirmed on a scratch world:
- **The spectator token opened everything.** `GET /snapshot` accepted the spectator token, and a snapshot holds every player's session token. Every viewer's page carries the spectator token (it is in the island's link), so any viewer could take Godling's session from the snapshot and send `/input` as Godling (it answered 200).
- **Any name was free to claim.** `/join?name=X` had no check at all, and the world script trusts names: only the player named `Sky` may call the sky's powers (`main.lua` `sky.power`). Whoever reached the port while the Sky slot was free became the sky, and its notes skipped every guard the panel puts on them. Chat from any player goes into Godling's prompt as "You heard: …".
- **Every origin could read the agent API.** All routes answered CORS with `*`, and the server listened on `0.0.0.0`. A web page open in a browser on the same machine could join the world and read its answers.

## What it changes
1. **`/snapshot` takes only the operator token** (`X-Operator-Token`, `WORLD_OPERATOR_TOKEN`). The spectator token now opens only the watching side: the page, its files, `/spectate`, the stream and chat. The island save (`run_godling.py` `IslandSave`) already used the operator token.
2. **`/join` takes a join key** when `WORLD_AGENT_KEY` is set: `X-Agent-Key`, compared in constant time. Without it the world answers 401. Unset, joining stays open, as upstream.
3. **Loopback by default.** The server listens on `WORLD_HOST`, default `127.0.0.1`; WSL still forwards it to Windows' `localhost`. Listening anywhere else without `WORLD_AGENT_KEY` refuses to start.
4. **CORS only on the watching side.** The agent API (`join`, `input`, `observe`, `observe/image`, `reset`, `snapshot`, `audio`, `chat`, `chat/messages`) sends no CORS headers. The operator token is compared in constant time too.

Godling's launcher makes a fresh join key for every run and hands it to the world, the mind and the guest panel. It also writes the key to `<run>/world.key` (readable only by you) for tools that join later: `tools/god_bot.py --run-dir`, or `tools/guest_panel.py --run-dir`.

Clawblox's own agent mode (`clawblox run --agent …`) is not used by Godling. With a key set, its agents would need the key as well.

## Apply
On top of v0 and v1, in a clone at `8be90a0`:

```bash
git apply /path/to/godling/patches/v2-private-agent-api.patch && cargo install --path . --locked
```

## Tested
On a scratch world (port 8190, `WORLD_AGENT_KEY` and `WORLD_OPERATOR_TOKEN` set):
- `WORLD_HOST=0.0.0.0` without a key: refused to start (exit 1, with the reason).
- Default: listening on `127.0.0.1:8190`, and reachable from Windows at `localhost:8190`.
- `/join` without the key, or with a wrong one: 401. With the key: 200.
- `/snapshot` with the spectator token: 401. With the operator token: 200, sessions listed.
- `/spectate` with the spectator token: 200.
- A preflight to `/join` from another origin: no `Access-Control-Allow-Origin`. `/spectate`: `*`, as before.
- `godling.world.World` joined with the key from the environment, and was refused with an empty key.
