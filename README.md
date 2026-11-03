# Godling

A 24/7 autonomous AI agent living in a Clawblox 3D world. It walks, quarries stone, fells trees, climbs ladders and builds, and it learns its own skills. The mind runs on DeepSeek.

## Layout
| Folder | What is in it |
|---|---|
| `mind/` | The layered mind: LLM (L3), attention (L2), body skills (L1), memory arms. Run instructions are in [`mind/README.md`](mind/README.md). |
| `world/` | Godling's Mesa Island: the world script, the renderer and the models. The changes from upstream are in [`world/README.md`](world/README.md). |
| `world/viewer/` | The viewers' screen, the Block HUD over the live island: sky powers, notes for Godling, pop-ups of what viewers did, the watcher count, and (behind the site) the beta feedback bottle. `tools/guest_panel.py` serves it. The three HUD prototypes it was chosen from are in `prototypes/`. |
| `web/` | The public site: viewer accounts (copied from AgentOp's django-allauth setup), credits with Stripe, note reports, viewers' feedback and the admin, in front of the viewer screen. See [`web/README.md`](web/README.md), ADR-012 and ADR-013. |
| `relay/` | The island's stream relay, in Rust: one connection to the world's spectator stream, the same updates to every viewer, resuming after gaps. See [`relay/README.md`](relay/README.md) and ADR-015. |
| `deploy/` | Running it all on one server with Docker Compose: Postgres, the site, the island (world, mind, panel, relay) and Caddy for HTTPS, with the island's spectator page public under `/island`. See [`deploy/README.md`](deploy/README.md). |
| `art/` | Blender build scripts and sources for Godling and the props. See [`art/README.md`](art/README.md). |
| `tools/` | Long-run launcher, run analysis (`long_runs.sh`, `compare_runs.py`, `analyze_run.py`) and the guest panel (`guest_panel.py`), which serves the viewers' screen with sky powers and notes, free in test mode. |
| `decisions/` | Decision records, ADR-002 to ADR-017. |
| `ROADMAP.md` | The master plan's roadmap and where each phase stands, with the changes made to the plan since. |
| `research/` | Design notes and screenshots. |
| `reports/`, `research_notes/` | Research reports and the notes behind them (god games: what Godling can use). |
| `patches/` | The local changes to Clawblox itself (BUG-001, VIEWER-001, SEC-001, STREAM-001, DEPS-001). |
| `.github/` | Checks on every pull request (the relay, the site, the deployment's configs), a weekly dependency audit, and Dependabot. Reporting a vulnerability: [`SECURITY.md`](SECURITY.md). |

## Running
Everything runs inside WSL (Ubuntu 22.04), because Clawblox's agent mode needs tmux.

1. Clawblox at commit `8be90a0` (github.com/nacloos/clawblox), with the four patches applied in order:
   - `patches/v0-fix-cli-sandbox.patch` (BUG-001);
   - `patches/v1-viewer-terrain-and-offline.patch` (VIEWER-001): terrain for viewers, a viewer with no CDN, fresh world files;
   - `patches/v2-private-agent-api.patch` (SEC-001): joining takes the run's key, the spectator token only watches, the world listens on loopback;
   - `patches/v3-stream-reconnect.patch` (STREAM-001): the island page reconnects by itself, and resumes through the relay;
   - `patches/v4-dependency-updates.patch` (DEPS-001): the crates with known vulnerabilities updated, in the lock file only.

   The world still runs on Clawblox without v1, but its page then needs esm.sh for one icon set. Without v2 it runs too, but anyone who reaches its port, or has a viewer's link, can act as Godling (ADR-014). Without v3 the island freezes when its stream drops, until a reload. Without v4 the world carries 29 known vulnerabilities more.
   ```bash
   cd ~/clawblox && git checkout 8be90a0 && for p in v0-fix-cli-sandbox v1-viewer-terrain-and-offline v2-private-agent-api v3-stream-reconnect v4-dependency-updates; do git apply /path/to/godling/patches/$p.patch; done && cargo install --path . --locked
   ```
   For the stream relay (`--relay`): `cd relay && cargo build --release`.
2. A DeepSeek key: run `tools/setup_deepseek.sh`, or set `DEEPSEEK_API_KEY`.
3. One run: `python3 mind/run_godling.py --run-dir ~/godling-runs/<name>`.
   An overnight run: `bash tools/long_runs.sh 8 <prefix> now hindsight`.

## Credits
`world/` starts from Clawblox's `worlds/mesa-island` (MIT, github.com/nacloos/clawblox). The two animations in `art/source/` are Mixamo files; they are for use in this project only and must not be shared on their own.
