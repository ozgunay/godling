# Godling's layered mind

The mind thinks about the past and the future; the body handles walking and grasping. Design rationale:
[`../research/layered-mind-design.md`](../research/layered-mind-design.md).

| Layer | File | What it does |
|---|---|---|
| L3 mind | `godling/mind.py` | An LLM decides projects, narrates its intention, writes lessons, teaches itself skills, and sleeps hourly to consolidate memory |
| L2 attention | `godling/attention.py` | Notices new objects, damage to things it kept, and visitors; interrupts for salient events (the Jev slot is `decide`) |
| L1 body | `godling/skills.py` | Moves: walk_to (A* around mesas and objects), pick_up, put_down, place_at, throw, jump, say, wait. They know reach and overlap, not strategy |
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
- `--attach`: use a world that's already running.

Analyze afterwards:
```bash
python3 /mnt/c/Work/godling/tools/analyze_run.py ~/godling-runs/m-002
```
It reports the world-side numbers plus the mind's calls, cost and skill success. Raw logs: `<run>/mind/log.jsonl`. Memory and learned skills: `<run>/memory/`.

## Test results so far (2026-11-01, deepseek-flash)

| Run | Setup | What happened | Cost |
|---|---|---|---|
| Body only, no LLM | `build_tower` scripted | 12-high tower in 30 s; routing, mesa refusal and reaching from below all pass (7/7) | $0 |
| m-test3, 5 min | body moves only, no physics hints | Worked out block height from experience (0.37 → 1.12 → 1.87), built a 12-block tower, found its reach limit (~9 units) by testing, taught itself 7 skills (one proven, broken ones forgotten) | $0.028 |
