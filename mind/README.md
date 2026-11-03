# Godling's layered mind

The mind thinks about the past and the future; the body handles walking and grasping. Design rationale:
[`../research/layered-mind-design.md`](../research/layered-mind-design.md).

| Layer | File | What it does |
|---|---|---|
| L3 mind | `godling/mind.py` | An LLM decides projects, narrates its intention, writes lessons, teaches itself skills, and sleeps hourly to consolidate memory |
| L2 attention | `godling/attention.py` | Notices new objects, damage to things it kept, visitors and sky events; interrupts for salient events (the Jev slot is `decide`); hands events that happen somewhere to the glance reflex |
| L1 body | `godling/skills.py` | Moves: walk_to (A* around mesas and objects), pick_up, put_down, place_at, throw, jump, say, wait. They know reach and overlap, not strategy. Between steps, and while it waits, the body glances: it turns towards what attention just noticed, without changing the plan |
| learned skills | `godling/learned.py` | Skills the mind defines from body moves: declarative, verified in the world before they count as "proven", persisted |
| memory | `godling/memory.py` | Episodes (with world ticks), intentions, kept structures, digest; follows the plan's MemoryAdapter interface (§10.6) |
| world | `godling/world.py` | HTTP client for Clawblox and a compact reading of observations |
| LLM | `godling/llm.py` | DeepSeek (OpenAI-compatible endpoint), JSON replies, cost per call |

## Run (inside WSL)

```bash
python3 /mnt/c/Work/godling/mind/run_godling.py --run-dir ~/godling-runs/m-002
```

What happens:
- It starts Mesa Island with recording on port 8080, prints the spectator link, joins as Godling, and prints THINK / INTEND / DO / LEARN lines as it goes.
- **Ctrl+C** stops the mind and the world together.
- The DeepSeek key is read from `DEEPSEEK_API_KEY` or `~/.claude-deepseek/settings.json` (written by `tools/setup_deepseek.sh`).

Useful flags:
- `--model deepseek-v4-pro`: a stronger mind (about 5× the cost).
- `--minutes 60`: stop by itself after an hour.
- `--gifted-skills`: also offer ready-made `stack_on`/`build_tower` (the comparison arm).
- `--no-narration`: don't post intentions to world chat.
- `--attach`: use a world that's already running. If that world asks for a join key (`patches/v2`, ADR-014), export its `WORLD_AGENT_KEY` first. A run that starts its own world makes a fresh key and keeps it in `<run>/world.key`.
- `--guest-panel 8081`: also serve the guest panel at http://localhost:8081/. It shows the live view, what Godling thinks and needs, and buttons for the sky powers (stone, log, regrow, lightning, meteor). Free in test mode. It also runs on its own: `python3 tools/guest_panel.py --world http://localhost:8080 --run-dir <run>`.
- `--relay 8082`: stream the island to viewers through the relay (`relay/`, ADR-015; build it first with `cargo build --release` in `relay/`). The world gets a spectator token the relay shares, and the guest panel's island streams from the relay: one connection to the world however many watch, and pages that reconnect pick up where they left off. With `--attach`, export the world's `WORLD_SPECTATOR_TOKEN`.
- `--sky-test-minutes 10`: drop a meteor near Godling every 10 minutes, its shadow 40 s ahead, to measure reactions without anyone at the panel.
- **The brace reflex** (`skills.steady`): when the Clock says the ground is rumbling, the body looks around for about 2 s (the world plays LookAround), then sends `Brace` and holds on until the world lets go. It runs between steps, while waiting, and while the mind thinks. The rumble is a salience-5 event, so the step in progress stops; the mind is told how quakes work and hears of one in its next plan. `analyze_run.py` reports each quake: pieces woken, moved and fallen, how soon the body braced, and knock-downs.

Each decision also carries a `needs` line (what the agenda is short of, with counts) for the panel. `analyze_run.py` reports reactions to sky events: applied, noticed (a glance or mention within a minute), named in a thought or intention, and engaged.

Analyze afterwards:
```bash
python3 /mnt/c/Work/godling/tools/analyze_run.py ~/godling-runs/m-002
```
It reports the world-side numbers plus the mind's calls, cost and skill success. Raw logs: `<run>/mind/log.jsonl`. Memory and learned skills: `<run>/memory/`.

Replays (ADR-016): beside the world, `python3 -m godling.replay follow <run>` packs its recording into `<run>/replay/` as it grows (its log: `<run>/replay.log`); the guest panel and the site serve it, and the viewers' screen plays it (Rewind). `python3 -m godling.replay check <run>` compares replayed moments with the raw recording.

## Test results so far (2026-11-01, deepseek-flash)

| Run | Setup | What happened | Cost |
|---|---|---|---|
| Body only, no LLM | `build_tower` scripted | 12-high tower in 30 s; routing, mesa refusal and reaching from below all pass (7/7) | $0 |
| m-test3, 5 min | body moves only, no physics hints | Worked out block height from experience (0.37 → 1.12 → 1.87), built a 12-block tower, found its reach limit (~9 units) by testing, taught itself 7 skills (one proven, broken ones forgotten) | $0.028 |
