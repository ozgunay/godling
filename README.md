# Godling

A 24/7 autonomous AI agent living in a Clawblox 3D world. It walks, quarries stone, fells trees, climbs ladders and builds, and it learns its own skills. The mind runs on DeepSeek.

## Layout
| Folder | What is in it |
|---|---|
| `mind/` | The layered mind: LLM (L3), attention (L2), body skills (L1), memory arms. Run instructions are in [`mind/README.md`](mind/README.md). |
| `world/` | Godling's Mesa Island: the world script, the renderer and the models. The changes from upstream are in [`world/README.md`](world/README.md). |
| `art/` | Blender build scripts and sources for Godling and the props. See [`art/README.md`](art/README.md). |
| `tools/` | Long-run launcher and run analysis (`long_runs.sh`, `compare_runs.py`, `analyze_run.py`). |
| `decisions/` | Decision records, ADR-002 to ADR-005. |
| `research/` | Design notes and screenshots. |
| `patches/` | The local fix to Clawblox itself (BUG-001). |

## Running
Everything runs inside WSL (Ubuntu 22.04), because Clawblox's agent mode needs tmux.

1. Clawblox at commit `8be90a0` (github.com/nacloos/clawblox), with `patches/v0-fix-cli-sandbox.patch` applied:
   ```bash
   cd ~/clawblox && git checkout 8be90a0 && git apply /path/to/godling/patches/v0-fix-cli-sandbox.patch && cargo install --path . --locked
   ```
2. A DeepSeek key: run `tools/setup_deepseek.sh`, or set `DEEPSEEK_API_KEY`.
3. One run: `python3 mind/run_godling.py --run-dir ~/godling-runs/<name>`.
   An overnight run: `bash tools/long_runs.sh 8 <prefix> now hindsight`.

## Credits
`world/` starts from Clawblox's `worlds/mesa-island` (MIT, github.com/nacloos/clawblox). The two animations in `art/source/` are Mixamo files; they are for use in this project only and must not be shared on their own.
