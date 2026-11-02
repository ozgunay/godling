# godling-relay

The island's stream relay (ADR-015): one connection to the world's spectator stream, the same updates to every viewer.
However many watch, the world works out its changes once.

## Build and test
```bash
cd relay && cargo build --release && cargo test
```
The binary is `target/release/godling-relay`. `mind/run_godling.py --relay 8082` starts it with the run's world (it
finds it there, on the PATH, or at `RELAY_BIN`). Deployed, it is a Compose service of its own (`deploy/Dockerfile.relay`):
the part of the island the whole internet talks to holds the spectator token and none of Godling's keys.

## Settings (environment)
| Variable | Default | |
|---|---|---|
| `RELAY_LISTEN` | `127.0.0.1:8082` | Where viewers connect. |
| `RELAY_UPSTREAM` | `ws://127.0.0.1:8080/spectate/ws` | The world's spectator stream. |
| `RELAY_SPECTATOR_TOKEN` | `WORLD_SPECTATOR_TOKEN` | The world's token, sent in a header. Only the relay holds it. |
| `RELAY_BASE_PATH` | none | Served under this path, as the world is (`/island` when deployed). |
| `RELAY_ORIGINS` | any | Page origins a viewer's socket may come from, comma-separated (any case). |
| `RELAY_MAX_VIEWERS` | 5000 | Viewers at once. |
| `RELAY_MAX_PER_IP` | 64 | Viewers from one address (a phone network puts many behind one); an IPv6 /64 counts as one. Also the burst of new sockets one address may open at once. |
| `RELAY_CONNECTS_PER_MINUTE` | 60 | New sockets one address may open a minute after that burst: each is handed the whole island. |
| `RELAY_TRUSTED_PROXIES` | 0 | Proxies of ours in front (Caddy: 1); the viewer's address is then read from their X-Forwarded-For. |
| `RELAY_BUFFER` | 256 | Frames a viewer may fall behind before it is handed the whole island again. |
| `RELAY_RESUME_FRAMES` | 300 | Updates kept for viewers coming back (ten seconds of the stream). |

## What a viewer gets
The stream Clawblox's page already speaks, so the page works through the relay unchanged:
- first the whole island (no `type`), with `relay_epoch` and `relay_seq`;
- then the world's messages in order (`spectator_delta`, `chat_message`, speech, audio), each with its `relay_seq`;
- and the relay's own news, `{"type":"relay","world":"up"|"down","viewers":n,…}`, on connecting, when the world goes
  down or comes back, and every five seconds.

A page coming back from a gap connects with `?epoch=<last relay_epoch>&since=<last relay_seq>`: while the relay still
holds the updates after that place, it sends only those; otherwise the whole island. Patched Clawblox's page
(`patches/v3`) does this by itself.

`GET /relay/status` gives the world, the epoch and place, the tick, the entities, how many watch, and how many came
back by resuming or had to be handed the whole island again.
