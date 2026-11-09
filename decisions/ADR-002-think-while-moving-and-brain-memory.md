# ADR-002: Think while moving, and a brain-like memory (native v2 vs Hindsight)

Status: **Proposed**, waiting for your confirmation of D3–D5 · Date: 2026-11-01 · Data: run m-003 (2 h 35 min, deepseek-flash) and one replayed decision

## Context: the measured problem

| Measurement | Value |
|---|---|
| Wall time with the body idle while the mind thinks | **89%** (139 of 155 min) |
| Body time per decision (all skills of a project) | **~2.6 s** on average |
| Thinking time per decision | ~22 s median (more with retries) |
| Tokens per decision (replay) | prompt 4,029 · **reasoning 3,294** · answer ~175 |
| Answers cut off by the 3,500-token output cap | yes (`finish_reason: length`): the "broken JSON" failures |
| Memory store after 2 h | 1,059 episodes, 720 raw "lessons", 5 intentions |

What the reasoning spends its tokens on (from the replayed reasoning text):
1. **Re-deriving world facts from raw coordinates.** Which object is on which mesa, heights, the rock's half-height, all of which it learned earlier.
2. **Re-reading and arbitrating** memories and intentions.
3. **Weighing 4–5 options.**
4. **Working out step coordinates.**

**Key arithmetic:** the body finishes a project in ~2.6 s; the mind needs ~22 s to choose one. Thinking while moving cannot hide 22 s behind 2.6 s. **Each thought has to buy much more body work**, and each thought has to start from conclusions rather than raw data.

## Decisions

### D1: Reasoning stays fully on (decided by you)
- Every mind call keeps DeepSeek's full reasoning, with no reasoning switch-off or effort limit.
- **Change:** raise the output cap from 3,500 to 16,000 tokens so reasoning can *finish* instead of cutting off the answer. This removes a failure mode; it does not limit thinking.
- Log `reasoning_tokens` per call.

### D2: Think while moving = pipelined planning plus an agenda (decided by you; design below)
- **Agenda.** One decision returns an ordered agenda of 1–4 projects meant to keep the body busy for about 20–40 s. The body runs them back to back.
- **Pipelining.** When the body starts the *last* project in the agenda, a background thread already asks the mind for the next agenda. It uses the current snapshot plus the expected outcome of the running project ("assume this succeeds").
- **At the handover:**
  - If the running project succeeded and the background plan is ready, its preconditions are checked (objects still exist, hands as expected) and it starts immediately.
  - If the project failed or was interrupted, the background plan is discarded and the mind replans with the real outcome.
- **No idle behaviours (your decision):** if the next plan isn't ready, the body simply waits.
- **Side effects are applied in the main thread when a plan is used,** not when it arrives: memory writes, learned skills, keeps. A discarded plan leaves no trace.
- **Salient events** (new object, damage, visitor) still interrupt. A background plan made before the event is discarded.
- *Expected effect:* thinking hides behind body work whenever an agenda lasts longer than one thought. That depends on D3.
- **Smoke-test amendment (2026-11-01).**
  - *Plan earlier.* The next agenda is now planned as soon as an agenda *starts*, not at its last project.
  - *Keep the plan after an ordinary failure.* Discarding threw away 16 of 41 plans in a 10-minute smoke, because about a third of projects fail. That doubled the cost to $0.76/h and lowered body busy from 25% to 20%. So a plain failure now keeps the background plan: steps that no longer fit fail fast, and the following plan is told what went wrong.
  - *Still discard on interruptions.* Only an *interruption* by a salient event still discards it.

### D3: Enough body work per thought (needs your confirmation)
With ~2.6 s of body work per project, an agenda would need ~8 projects to cover one 22 s thought. Two levers, both open:
- *Smoke-test amendment (2026-11-01).*
  - Asking for "30–60 s of work" still produced about 7.5 steps, about 7.5 s of work, since a step takes about 1 s.
  - Smoke s3 then asked for a step count tied to think time. Plans grew to about 38 steps, but thinking grew with them: p50 rose from 19 s to 41–53 s, reasoning from about 3k to 7–8k tokens, and 3 answers hit the 16k cap. Long blind plans also failed early, with only 47–76% of projects finishing.
  - So a planned step costs about as much thinking as it gives body time, and longer step lists cannot get ahead of the body.
  - Now:
    - no step count;
    - the mind is told this measured economy, and that a step running its *own* repeating skill lasts far longer;
    - after an ordinary failure the body carries on with the rest of the agenda.
  - Composing such skills is left for the agent to learn; none are gifted.
- **D3a, bigger agendas (recommended):** ask for agendas worth ~30 s of work, with up to 4 projects and up to 8 steps each. That's 2–3× more work per thought, but plans made further ahead go stale more often.
- **D3b, human-paced walking:** walk speed 16 → 8 units/s in *our copy* of the world (upstream untouched). Real motion time per task doubles at zero token cost. This is not an idle behaviour; the body still only does what the mind chose, just at a human pace.

### D4: A brain-like memory: same model, two engines, compared on data (needs your confirmation)

The memory model, the same for both engines:

| Brain | Godling | Effect on thinking |
|---|---|---|
| Working memory (small) | A fixed-budget "situation" of ~1,200 tokens: goal, last outcome, nearby things | Less to reread |
| Semantic memory (neocortex, consolidated) | **Facts attached to things.** *"Rock_1: half-height ≈1.05 (learned, 3×)"*, *"LargeMesa top is out of reach"*. Duplicates merged, contradictions resolved during sleep | **Conclusions instead of re-deriving** (cause 1) |
| Episodic memory (hippocampus) | Events with world ticks, recalled by cue (objects in view, current goal, place) | Relevant past, not everything |
| Procedural memory (basal ganglia) | Learned skills. **Proven skills are protected**: demoted, never silently forgotten (the mind forgot `stack_big` at 26/35) | Fewer step details to work out (cause 4) |
| Prospective memory | Intentions plus the agenda (D2) | Fewer options to weigh each time (cause 3) |
| Sleep | Hourly consolidation: episodes → semantic facts, contradictions resolved, raw episodes compacted | Memory stays small and clean (cause 2) |

The two engines:
- **Arm A, native v2:** implemented in our code, in-process, with no extra service. Consolidation uses the existing hourly sleep call.
- **Arm B, Hindsight** (MIT, 57k stars):
  - `retain` stores episodes; DeepSeek extracts facts and entities, and consolidation into observations runs in the background.
  - `recall` (no LLM, ~100–600 ms vendor figure, `budget="low"`) supplies semantic facts and episodes each decision.
  - **Mental models** (standing answers such as "What do I know about stacking?", "What have I built and where?") are read with no LLM call at read time.
  - DeepSeek is supported natively (`HINDSIGHT_API_LLM_PROVIDER=deepseek`).
  - Embeddings and reranker run locally.
  - Install with `pip install hindsight-all` (embedded Postgres) in WSL. That avoids the 9 GB Docker image and the Norton certificate issue with containers.
- **Hindsight caveats:**
  - DeepSeek isn't on its tested-models list.
  - It has no explicit contradiction handling, and no forgetting; recency only affects ranking.
  - Each `retain` costs a DeepSeek extraction call, so retain is asynchronous and batched once per project.
  - `reflect` is a multi-call loop, too slow for each decision, so it's used only at sleep.

**Recommendation:** build the memory model once behind the existing `MemoryAdapter`, with native v2 and Hindsight as two engines, then compare them.

### D5: How we decide (needs your confirmation)
Three one-hour runs on deepseek-flash with reasoning fully on, on port 8090 while m-003 keeps running:

| Run | Pipelining + agenda | Memory |
|---|---|---|
| m-004 | yes | current memory (shows what D2/D3 alone achieve) |
| m-005 | yes | native v2 |
| m-006 | yes | Hindsight |

Metrics, all logged automatically:
- body-busy share and motion share (now 11% busy / 6% moving);
- reasoning tokens and latency per decision;
- placements per hour, and whether they hold up over the hour;
- plans discarded at handover;
- false beliefs noticed (corrections in memory);
- cost per hour.

**Rule:** if Hindsight isn't clearly better than native v2 on reasoning tokens or quality, native v2 wins (the plan's "simpler wins if equal").

## Not doing
- No idle behaviours (your decision).
- No reasoning limits (your decision).
- No Jev yet: attention isn't the bottleneck.

## Rollback
- Each change has a flag: `--agenda/--no-agenda`, `--memory native|native2|hindsight`.
- m-003's setup stays reproducible with `--no-agenda --memory native`.
  - *Amended by ADR-032 (2026-11-09):* except for learned skills. Every engine now keeps a skill that has worked, which
    m-003 did not. To rerun m-003 exactly, check out the code of that time.
