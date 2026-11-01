# Run analysis: godling-smoke

## World (server-side ground truth)
- Recording: `20261031_213900.clawrec` (0.8 MB, 42.9 MB/h), tick rate 60 Hz
- Duration: 69.7s
- Actions: **2** (103/h) — MoveTo 1, Pickup 1
- Gap between consecutive actions: p50 **12.5s**, p90 12.5s, p95 **12.5s**, max 12.5s
- Gaps ≤ 2 s (G5 target zone): 0%

| Gap | Count | Share | Time spent |
|---|---|---|---|
| 0–2s | 0 | 0% | 0.0s |
| 2–5s | 0 | 0% | 0.0s |
| 5–10s | 0 | 0% | 0.0s |
| 10–30s | 1 | 100% | 12.5s |
| 30–60s | 0 | 0% | 0.0s |
| 60–300s | 0 | 0% | 0.0s |
| >300s | 0 | 0% | 0.0s |

Longest idle stretches (minutes into the run):
- 12.5s starting at 0.9 min

- Motion duty cycle: **4%** of 45.6s sampled at ~1 Hz (speed ≥ 0.5 studs/s)
- Action results seen in world state: Ready 1, PickupFailed:NoBlock 1

## Agent (Claude Code transcript)
- Models: claude-opus-4-6 (15)
- Model calls: 15 (781/h); stop-hook continues: 0
- Think time per call: p50 **2.3s**, p95 2.9s
- Tokens: input 17, cache write 16,493, cache read 536,441, output 3,621
- Cache hit share of input: 97%
- Avg context per call: 36,863 tokens
- Estimated cost: **$0.46** ($24.06/h → $17,325/month if 24/7; cache writes at the 5-min rate, so a lower bound if 1 h caching is used)
- Tool calls: workspace 7 (39%), world:observe 7 (39%), world:act 3 (17%), world:look 1 (6%)
- World actions per action command: 1.00 (>1 means the agent batches actions in one shell call)
- Results returned to agent: PickupFailed:NoBlock 2, Ready 1

## Workspace memory
| File | Bytes | ~Tokens |
|---|---|---|
| SOUL.md | 619 | 154 |
| EPISODIC_MEMORY.md | 510 | 127 |
| SEMANTIC_MEMORY.md | 234 | 58 |
| view_initial.png | 56 | 14 |
