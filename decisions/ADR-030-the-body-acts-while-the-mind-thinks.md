# ADR-030: The body acts while the mind thinks: a decision deadline, a reasoning effort, and no answer lost at the cap

Date: 2026-11-09. Status: built and tested in the mind's suite with a fake LLM. Not yet tried in a live run.

## Why
The live run of 2026-11-08 22:10 to 2026-11-09 07:50 UTC (9.6 h, deepseek-flash, `mind/log.jsonl`):
- **Decisions are slow, and the time is reasoning.** There were 219 decision calls. Their latency was 91 s at the
  median, 183 s at p90 and 247 s at most. Reasoning took 12.1k tokens at the median and 25k at p90. The answer
  itself took 1.1k tokens (2.3k at most). Reasoning is 93% of the output, and the reply streams at about 140 tokens a
  second, so a decision takes as long as its reasoning.
- **The body stood still for 91 minutes (16% of the run), waiting for its mind.** That is `waited_for_mind_s` 5,476 in
  `summary.json`. There were 193 waits, and 41 lasted over a minute (72 minutes between them). Most long waits came
  after an agenda whose projects failed within seconds: 15% of all projects failed in under 2 s. The body ran out of
  work long before the next plan, which was being thought up meanwhile, came in. Nine of the 41 came after an
  interruption or a death threw the plan in progress away. The body only watched and braced (`watch_while_thinking`:
  "no idle behaviours").
- **8 answers were lost at the cap.** Those decisions spent all 32,768 tokens reasoning, for 195 to 247 s each, and
  gave no answer. The retry ("That was not valid JSON") thought the whole plan up again, for another 12 to 97 s.
  Three more streams broke off without a finish (one after 223 s) and were retried the same way.
- **Decisions are 86% of the cost:** $3.05 of $3.52, and 88% of that is output, which is mostly reasoning. There were
  2,149 calls, but most of them (1,930) were the bubble's small ones.

What controls the thinking (DeepSeek's Chat Completions documentation, read 2026-11-09):
- **`reasoning_effort`**: none, low, high or max. Thinking is on by default at high. We never sent it, so decisions ran
  at high.
- **There is no reasoning budget.** `max_tokens` caps reasoning and answer together. We send 32,768; the default in
  thinking mode is 64K.
- **Temperature is ignored in thinking mode.** The 0.9 we send has no effect on decisions.
- **The prompt** was 10.4k tokens at the median: 7.5k in the first hour and 12k in the last. A prompt rebuilt from the
  run's memory has a system part of 20k characters (soul 1.3k, how you exist 4.8k, body moves 2.7k, learned skills
  5.1k, teaching 1.0k, island map 2.3k, how to answer 2.8k; the landmarks could not be rebuilt). Its situation is 12k
  characters, and 6.5k of those are the kept builds, each carrying a full "as a house" verdict.
  - **Only 2.2k tokens of each prompt (21%) came from the provider's cache.** The cached prefix ends where the learned
    skills begin, because their success counts change after every run of a skill.
  - **The prompt does not drive the thinking.** Over the 219 calls, prompt tokens and reasoning tokens correlate at
    0.09. Prompt tokens are about 11% of the decisions' cost.

## Decision
These are the standard controls for a slow planner in a real-time loop, as robotics and game AI use them. A reactive
layer keeps acting while the deliberative one plans. A planner that misses its deadline gets a cheap fallback, and its
late result is used by a fixed rule. Reasoning has an effort setting and a budget, and past the budget an answer is
forced from the thinking done so far (s1's "budget forcing"). Only the first control changes what happens by default,
and it is the body acting while it waits. The thinking itself is unchanged by default: the owner does not change the
live reasoning defaults on one run's evidence.

### 1. A decision deadline with a stop-gap (on by default: `--think-deadline 20`)
- **When the body has stood idle for 20 s and the plan is not in, it takes a stop-gap.** The mind chooses one short
  project at once, with thinking off (`Mind.stopgap`). The prompt is the plan's own prompt, read again from the
  provider's cache, with four things added:
  - how long the body has stood idle;
  - what has happened since thinking began (the last project's outcome);
  - what the body already did meanwhile;
  - the last 6,000 characters of what the mind has thought so far for that plan.

  So the stop-gap carries on with the plan that is being thought up, and it is the mind's own choice.
- **The next stop-gap comes as soon as one ends**, if the plan is still not in, up to 3 per plan
  (`STOPGAPS_PER_PLAN`). After that the body waits, as before.
  - A stop-gap that fails (a provider error, or no usable project) costs one of the 3. The body waits another
    deadline before it asks again.
- **The body enforces the limits, not the prompt.** A stop-gap is the first project of the reply that has steps the
  body can do, cut to 4 steps.
  - **It moves the body only.** What the reply would remember, learn, forget, keep or release, and its house choice,
    are ignored: they wait for the finished plan.
  - It is narrated, and logged as an ordinary project with `stopgap: true`.
- **The late plan is used by this rule:**
  - **It is taken up when the stop-gap project under way ends**, never in its middle.
  - **It is dropped only as before:** when the body dies, or when a project, a stop-gap included, is interrupted by
    something salient. Then the world has changed under the plan, and the mind thinks again from reality (ADR-002).
  - **A plan is never dropped for being late.**
  - **A stop-gap that comes after the plan is dropped:** the plan comes first.
  - **The next plan is told what the body did meanwhile:** "While you thought up your last plan, your body did on the
    spot, unplanned: ...".
- **`waited_for_mind_s` still counts only the time the body stood idle.** `summary.json` adds `stopgaps` (stop-gap
  projects run) and `stopgap_s`. The log has `stopgap` entries with the phases asked, chosen, none and dropped.
- **`--think-deadline 0` gives today's loop.** The one-project loop (`--no-agenda`) has no deadline.

The 20 s deadline and the limit of 3 come from replaying the run's 193 waits through a simple model: a stop-gap call
takes about 4 s and its project about 20 s, the median project time in the run. On that model the body's idle time
falls from 5,571 s to about 3,070 s (−45%), for about 150 stop-gaps, which cost about $0.10. With no limit it falls to
about 2,360 s. With a 30 s deadline it falls to 3,460 s.
This is an estimate, not a measurement. The experiment below measures it.

**Guided construction: no move toward it.** The body is given no building method and no project of its own. The house
is not built for the mind. A stop-gap is chosen by the same model from the same prompt, only without thinking.

### 2. A reasoning effort (off by default: `--reasoning-effort low|high|max`)
- The effort is sent as DeepSeek's `reasoning_effort` for decisions only. Sleep and death reflections keep the
  provider's default.
- Unset, nothing is sent, so the request is today's (high). Whether low thinks well enough is the experiment's
  question.

### 3. A reasoning budget, and no answer lost at it (`--reasoning-budget 32768`, today's cap)
- **The budget is the decision's `max_tokens`**, for reasoning and answer together, since DeepSeek has no separate
  reasoning budget. The default stays today's 32,768.
- **The answer is no longer lost at the cap.** This is on always, as a fix. A reply that thought but gave no whole
  answer, because it hit the cap or its stream broke off, is asked once more (`LLM._answer_from`):
  - thinking off, with up to 4,096 tokens for the answer;
  - with the same prompt, then the last 12,000 characters of its reasoning and any answer it had begun, then "Answer
    now, from what you have thought".
  - The call is logged as `decide:answer`, and `summary.json` counts it in `answers_forced`.

  Only if that fails too is the question asked again with thinking, as before. A forced answer costs about $0.001
  and 10 s. The re-think it replaces cost about $0.004 and 49 s on average in the run, and lost the 200 s of thinking
  before it.
- With this in place, a lower budget no longer means lost answers. At 16,000, the earlier smokes lost 1 decision in
  25. That is why the cap went up to 32,768. A lower budget can now be tried (arm D).

### 4. The prompt: measured, not trimmed here
The measurement shows bloat but not a lever on think time. Prompt size and reasoning length are unrelated (r 0.09),
and prompt tokens are 11% of the cost. Two trims would pay, and neither is made here:
- **The "as a house" verdict on every kept build:** about 2k tokens at the run's end, and growing with every build.
  With the house project on, only the house needs it. That text belongs to the house work going on in parallel
  (ADR-028 and the bigger-house and building-site sessions), so it is left to them.
- **Ordering the system prompt for the cache** (static sections first) would make about 1.1k more tokens a cache hit.
  That saves about 1% of the cost, and it moves the answer instructions away from the end of the prompt. Not worth
  the change in behaviour.

The stop-gap and forced-answer calls are built on the plan's own prompt, so most of their input comes from the
provider's cache.

## The experiment the owner should run
The method: controlled arms, one thing varied per arm, all arms started in the same minute and compared at the same
elapsed minute, and the success criteria written down first.

**Setup.** Arms run side by side, each in its own run folder on its own port. Use 8230 to 8233, never 8090 to 8092 or
8888. All arms run the same code (one frozen copy) and the same model, deepseek-flash. Leave out the guest panel and
the sky test (`--sky-test-minutes 0`), and send no viewer events. All arms start from the same state: copy the live
run's `island-save.json` and `memory/` into each run folder. That gives a Godling in mid-life, with a house project
and 29 learned skills. Run 4 hours: at about 23 decisions an hour, each arm gets at least 60 decisions. Compare the
arms with `tools/compare_runs.py`, cut to the shortest arm's minute. The weather is not seeded, so note the storms
each arm had.

| Arm | Flags | Question |
|---|---|---|
| A, control | `--think-deadline 0` | today's loop (with the forced answer, a fix in every arm) |
| B, deadline | defaults (`--think-deadline 20`) | does the body stop idling, without worse work? |
| C, low effort | `--think-deadline 20 --reasoning-effort low` | does less thinking plan as well, faster and cheaper? |
| D, optional | `--think-deadline 20 --reasoning-budget 16000` | does a lower cap, answered from the reasoning, cut the long tail? |

**Metrics.** They come from `compare_runs.py` and `analyze_run.py`, which now report stop-gaps, answers given from the
reasoning, waits over a minute and decide latency at p90:
- **Idle:** waited for the mind (share of the run), and waits over a minute.
- **Speed:** decide latency p50 and p90, and reasoning tokens per decision.
- **Work:** projects finished (share), pieces built in by hour, the house's best score and whether it stood (`house`
  log entries), and the walls, enclosures and roofs at the end.
- **Stop-gaps:** how many ran, the share that finished, and the share of plans whose first project fails at its first
  step after a stop-gap, against plans that came without one. That is the cost of the plan not knowing what the
  stop-gap did.
- **The cap:** answers cut off, and answers given from the reasoning. Every cut-off decision should be followed by a
  `decide:answer`.
- **Cost:** $ per hour, split into decide, stopgap, decide:answer and bubble.

**Success criteria, B against A:**
1. **Idle:** B's waited-for-mind share is at most half of A's (A should show about 16%).
2. **Work:** B's projects-finished share is no more than 5 points below A's.
3. **Building:** B's pieces built in at the end are at least 90% of A's, and its house score is not lower.
4. **Duplicated work:** first projects after a stop-gap fail at their first step no more than 10 points more often
   than other first projects.
5. **Cost:** stop-gaps cost under $0.05 an hour.
6. **The cap:** no decision is left without an answer.

If B misses 2, 3 or 4, set `--think-deadline 0` as the default, and look at why the stop-gaps hurt before trying
again.

**Success criteria, C against B:**
1. **Speed:** decide latency p50 and reasoning tokens per decision are at most 60% of B's.
2. **Cost:** cost per hour is at least 30% lower.
3. **Work:** the projects-finished share is no more than 5 points below B's, pieces built in are at least 90% of B's,
   and the house score is not lower.

If C passes, confirm it in a second run before low becomes the default, in a PR of its own.

**D against B** (if run): latency p90 falls by at least a third, with B's criteria 2 and 3 held.

## Checked
- `mind/tests/test_llm.py`:
  - The effort is sent only when asked for, and thinking off is sent as `thinking: disabled`.
  - A reply cut off at the cap is answered from the end of its reasoning in one non-thinking call. A broken stream is
    answered the same way.
  - A forced answer that fails falls back to asking again, as before. A reply without thinking is never forced.
- `mind/tests/test_mind.py`:
  - A decision asks for the effort and the budget it was given, and nothing when unset.
  - The reasoning is kept as it streams.
  - A stop-gap's prompt is the plan's prompt plus the idle time, the outcome since, what was done meanwhile and the
    end of the thoughts.
  - A stop-gap is one project of at most 4 known steps. Its memories, skills, keeps and house are ignored.
- `mind/tests/test_run_godling.py`, the agenda loop with a fake late mind:
  - The body does a stop-gap instead of standing. A plan that comes in during the stop-gap is taken up when the
    stop-gap's project ends.
  - A stop-gap that comes after the plan is dropped.
  - Stop-gaps follow one another up to 3, and a failed one is waited out.
  - An interrupted stop-gap drops the plan.
  - With the deadline at 0 the body waits as before.
  - `main()` passes the effort and the budget through and writes the new summary fields. The console prints the new
    lines.
- `tools/tests/test_analyze_run.py`: the analysis counts stop-gaps, forced answers and long waits.
- Run against the code from before this change, the 15 new tests fail and the other 82 tests in those three files
  pass. For example: "At index 0 diff: ('decision', None, None) != ('stopgap', 'asked', None)": the body waited and
  no stop-gap came.
- The mind and tools suite passes: 434 tests (pytest, Windows Python 3.14). The world, site and renderer code is
  unchanged, so their suites were not run.

## Not checked
- **Not yet in a live run.** No real DeepSeek call has made a stop-gap or a forced answer, so these are untested
  against the live API:
  - that `thinking: disabled` with `json_object` answers a one-project agenda in about 4 s;
  - that the reasoning tail is enough for a good forced answer;
  - how long `reasoning_effort: low` thinks.
- **The 45% saving is a model of the run's waits, not a measurement.**
- **Whether stop-gaps duplicate work the late plan then repeats.** The plan does not know what the stop-gap did.
  Steps that no longer fit fail fast, as they do after a failed project today. The experiment measures it (B's
  criterion 4).
