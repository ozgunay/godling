# STREAM-001: the island page reconnects by itself, and resumes through the relay

| Field | Value |
|---|---|
| Upstream SHA | `8be90a0` (v0.1.5-2), nacloos/clawblox, with [v0](v0-fix-cli-sandbox.patch), [v1](v1-viewer-terrain-and-offline.patch) and [v2](v2-private-agent-api.patch) applied first |
| Patch | [v3-stream-reconnect.patch](v3-stream-reconnect.patch) (`frontend_runtime/dist/main.js` only) |
| Status | **Built and tested 2026-11-02** in WSL: `cargo build --release`, then in a browser through the relay (ADR-015) |
| Goes with | ADR-015; `relay/`, `world/renderer/src/index.js` (`onConnection`), `world/viewer/viewer.js` (the badge) |

## What was wrong
- When the spectator socket closed (a world restart, a network blip, a phone asleep), the island froze on "Disconnected" until a reload.
- On "Missing base spectator state; reconnecting" the page closed the socket, and nothing opened it again.
- A socket that died without closing (mobile networks) looked alive forever.

## What it changes
1. **The socket of the moment.** `ws` is no longer one socket for the page's life: `connectStream()` opens one and sets the page's handlers on it; replay keeps its single socket.
2. **Reconnecting**: after a random wait up to a cap that doubles (0.5 s to 30 s; full jitter, so a restart does not bring every viewer back at once), starting over after ten good seconds.
3. **A watchdog**: a stream silent 5 s is dropped and reopened (15 s while the relay says the world is down). The world sends at least every ~165 ms; the relay says how the world is every 5 s.
4. **Hidden pages** let their socket go after half a minute and reopen it when shown; coming back online reopens it at once.
5. **Resuming through the relay**: the page keeps the last `relay_epoch` and `relay_seq` it saw and reconnects with `?epoch=&since=`; the world ignores them. A delta that cannot be applied starts over from the whole island.
6. **The relay's news** (`{"type":"relay"}`) sets the status line ("The island is restarting…") and is passed on.
7. **The renderer hears the stream's state**: `renderer.onConnection({state, world})` when it has one (live, connecting, reconnecting, paused). Godling's renderer passes it to the viewers' screen.
8. **`?stream_port=`** points the socket at a relay on the page's own host (a local run, `run_godling.py --relay`); never another host.
9. **Gzipped islands** (ADR-016): the page asks for them (`gz=1`, when the browser has `DecompressionStream`) and inflates one before handling anything that came after it, so messages are still handled in order.
10. **A stalled page is not a dead stream** (ADR-016): a message's arrival is the heartbeat, however long handling it takes, and when the watchdog itself ran late (a long frame on a slow phone) it does not take the silence for a dead socket.

## Apply
On top of v0, v1 and v2, in a clone at `8be90a0`:

```bash
git apply /path/to/godling/patches/v3-stream-reconnect.patch && cargo install --path . --locked
```
The page is compiled into the binary, so it takes a rebuild.

## Tested
See ADR-015's tests: the relay stopped and started, the world restarted, and a socket dropped while the relay kept its epoch (it resumed from `since=3575`), all without a reload.
