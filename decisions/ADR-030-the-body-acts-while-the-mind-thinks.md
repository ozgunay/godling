# ADR-030: The body acts while the mind thinks: a decision deadline, a reasoning effort, and no answer lost at the cap

Date: 2026-11-09. Status: built and tested with a fake LLM, and revised after the review of #80 (its findings by
id below). Not yet tried in a live run.

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
forced from the thinking done so far (s1's "budget forcing").

**Nothing changes by default but the forced answer**, which is a fix: an answer is no longer lost at the cap. The
deadline, the effort and a lower budget are options until the experiment below has judged them. The owner does not
change live defaults on one run's evidence.

The deadline was first on by default, as "the body acting while it waits". The review of #80 (80-SWEEP4) showed it
is more than that. A stop-gap is a new kind of decision, made without thinking, and the review found it interacting
with the plan and the prompt in ways no live run has tried (80-CDE1, 80-AB10, 80-CDE3, all fixed below). So the
deadline stays off (`--think-deadline 0`) until arm B passes. The live deploy runs with no mind flags
(`GODLING_MIND_ARGS` is empty), so merging changes nothing on the island but the forced answer.

### 1. A decision deadline with a stop-gap (off by default; the experiment's arm B: `--think-deadline 20`)
- **When the body has stood idle for the deadline and the plan is not in, it takes a stop-gap.** The mind chooses one
  short project at once, with thinking off (`Mind.stopgap`). The prompt is the plan's own prompt, read again from the
  provider's cache. That prompt was written before the agenda ran, so the world as it is now follows it (80-CDE3):
  - how long ago the body ran out of work for this plan, counted from the first idle moment, not from the last
    stop-gap (80-AB4);
  - "Now:" where the body is, what it holds, how fed and well it is, and how the weather feels;
  - that the agenda it was carrying out has ended, if it was carrying one out;
  - the outcomes of the projects that ended since the plan's prompt was written. When none has ended, it says so,
    and never repeats older news (80-AB4);
  - what attention noticed that the plan has not heard of yet. These events are read, not taken: the next plan still
    gets them;
  - what the body already did meanwhile;
  - the last 6,000 characters of what the mind has thought so far for that plan.

  So the stop-gap carries on with the plan that is being thought up, and it is the mind's own choice.
- **The next stop-gap comes as soon as one ends**, if the plan is still not in, up to 3 per plan
  (`STOPGAPS_PER_PLAN`). After that the body waits, as before.
  - A stop-gap that fails costs one of the 3: a provider error, or a reply the body refuses. The body then waits
    another deadline before it asks again.
- **The body enforces the limits, not the prompt.**
  - **A stop-gap is taken as given, or not at all.** It is never cut short or edited (80-SWEEP1): a carry cut after
    its pick-up was reported as succeeded with the piece still held.
  - **It must be one project of at most 4 steps, each one of the body's own moves** (80-AB3). A learned skill can
    repeat and nest for minutes, and the plan would wait for it. Anything else is refused, and the log says why
    (`stopgap` phase none).
  - **It moves the body only.** What the reply would remember, learn, forget, keep or release, and its house choice,
    are ignored: they wait for the finished plan.
  - **Its outcome is remembered as an episode, but it is filler** (80-AB10). It never clears "Recent failures ... Try
    something different" and never becomes "What just happened". The next plan hears of it in the note about what
    the body did meanwhile.
  - It is narrated, and logged as a project with `stopgap: true`. The loop logs `chosen` only for a stop-gap it takes
    up (80-CDE9).
- **The late plan is used by this rule:**
  - **It is taken up when the stop-gap project under way ends**, never in its middle. The 4-move limit keeps that
    short.
  - **It is dropped only as before:** when the body dies, or when a planned project is interrupted by something
    salient.
  - **Something salient during a stop-gap ends the stop-gap and leaves the plan be** (80-CDE1), as it does while the
    body stands waiting. Until then, each stop-gap opened a window in which the plan was thrown away and thought up
    again. The idle wait never had that window.
  - **A plan is never dropped for being late.**
  - **A stop-gap that comes after the plan is dropped:** the plan comes first. A plan whose provider call fails has
    not come first: the stop-gap being chosen is still taken, and the failure is handled as before (80-AB7).
  - **The next plan is told what the body did meanwhile, standing and moving:** "While you thought up your last plan,
    your body stood still for Ns, then did on the spot, unplanned: ..." (80-SWEEP3).
- **With the deadline on, the plan's rules say so.** After "if your body runs out of work before you finish thinking,
  it stands still" comes: "If your body has stood still for 20s while you are still thinking, you give it a short
  project at once, without thinking, from what you have thought so far, and go on thinking." Off, the prompt is
  today's.
- **Time and counts.** The deadline and the idle time run on the monotonic clock (80-CDE12).
  - `waited_for_mind_s` still counts only the time the body stood idle.
  - Stop-gaps are not counted among the projects (80-CDE6). `summary.json` has `stopgaps` and `stopgap_s` of their
    own, and the analysis counts them apart.
  - The log's `stopgap` entries have the phases asked, chosen, none and dropped.
  - The viewers' screens show a stop-gap's intention without a step count (80-CDE14). Before, they showed "2 of 3" of
    an agenda that had been thrown away.
- `--think-deadline 0` is today's loop. The one-project loop (`--no-agenda`) has no deadline. A negative or infinite
  deadline is refused at the start (80-AB8).

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
  reasoning budget. The default stays today's 32,768 (`llm.DECIDE_TOKENS`, one constant for the client and the
  option). A budget below 1 is refused at the start (80-AB8): 0 used to be sent as the default while `summary.json`
  said 0.
- **The answer is no longer lost at the cap.** This is on always, as a fix. It covers a reply that thought but gave
  no whole answer: one that hit the cap, one whose stream ended early, and one whose connection broke mid-stream
  (IncompleteRead, a reset, a read timeout) after the reasoning began (80-AB2). Such a reply is asked once more
  (`LLM._answer_from`):
  - thinking off, with up to 4,096 tokens for the answer, at temperature 0.7 as the bubble's calls use (80-CLEAN1:
    one request builder for both; thinking on, the provider ignores the temperature);
  - with the same prompt, then the last 12,000 characters of its reasoning and any answer it had begun, then "Answer
    now, from what you have thought".
  - The call is logged as `decide:answer`. An `answer_forced` entry says whether it gave the answer, and
    `summary.json`'s `answers_forced` counts only answers given (80-CDE5).
- **Whether to force an answer is decided by the request.** A forced answer, or any reply asked without thinking, is
  never forced in turn (80-AB1). A provider that streams reasoning with thinking off cannot nest one forced call inside
  another.
- Only if the forced answer fails is the question asked again with thinking, as before. A forced answer costs about
  $0.001 and 10 s. The re-think it replaces cost about $0.004 and 49 s on average in the run, and lost the 200 s of
  thinking before it.
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

**Setup.**
- **Arms:** side by side, each in its own run folder on its own port. Use 8230 to 8233, never 8090 to 8092 or 8888.
- **The same everywhere:** one frozen copy of the code, the same model (deepseek-flash), and the same `--minutes 240`.
  Leave out the guest panel and the sky test (`--sky-test-minutes 0`), and send no viewer events.
- **The same start:** copy the live run's `island-save.json` and `memory/` into each run folder. That gives a Godling
  in mid-life, with a house project and 29 learned skills.
- **Length:** 4 hours. At about 23 decisions an hour, each arm gets at least 60 decisions.
- **Compare** with `python3 tools/compare_runs.py --minute 240 <arm A> <arm B> ...` (80-AB11). It cuts every arm's
  mind log and placements at that minute. The rows read from the recording's motion and stacks say "(whole run)".
- **Weather:** it is not seeded, so note the storms each arm had.

| Arm | Flags | Question |
|---|---|---|
| A, control | defaults (`--think-deadline 0`) | today's loop (with the forced answer, a fix in every arm) |
| B, deadline | `--think-deadline 20` | does the body stop idling, without worse work? |
| C, low effort | `--think-deadline 20 --reasoning-effort low` | does less thinking plan as well, faster and cheaper? |
| D, optional | `--think-deadline 20 --reasoning-budget 16000` | does a lower cap, answered from the reasoning, cut the long tail? |

**Metrics.** Every criterion's number comes from `compare_runs.py`, and `analyze_run.py` reports the same (80-SWEEP2):
- **Idle:** "waited for mind" (share of the run) and "waits over a minute".
- **Speed:** "decide latency p50" and "p90", and "reasoning tokens/decision".
- **Work:**
  - "projects finished": planned projects only; stop-gaps are counted apart (80-CDE6);
  - "pieces built in, by hour";
  - "house best score / stood";
  - the walls, enclosures and roofs at the end.
- **Stop-gaps:** "stop-gaps run / finished", and "first projects finished (after stop-gaps)". That row gives, for
  the first planned project of each plan, the share that finished, apart for plans taken up after stop-gaps. Those
  plans did not know what the stop-gaps did.
- **The cap:** "answers cut off" and "answers given from the reasoning".
- **Cost:** "cost $/h", and "cost $/h by purpose" (decide, stopgap, decide:answer, bubble, sleep, death).

**Success criteria, B against A:**
1. **Idle:** B's waited-for-mind share is at most half of A's (A should show about 16%).
2. **Work:** B's projects-finished share is no more than 5 points below A's.
3. **Building:** B's pieces built in at the end are at least 90% of A's, and its house score is not lower.
4. **Duplicated work:** the first projects of plans taken up after stop-gaps finish no more than 10 points less
   often than other first projects.
5. **Cost:** stop-gaps cost under $0.05 an hour.
6. **The cap:** answers given from the reasoning plus the re-thinks match the answers cut off. No decision is left
   without an answer: no "cycle failed" with "LLM call failed" in the log.

**If B passes**, turn the deadline on by default (`--think-deadline 20`) in a PR of its own. **If it misses 2, 3 or
4**, leave it off, and find out from the log why the stop-gaps hurt before trying again.

**Success criteria, C against B:**
1. **Speed:** decide latency p50 and reasoning tokens per decision are at most 60% of B's.
2. **Cost:** cost per hour is at least 30% lower.
3. **Work:** the projects-finished share is no more than 5 points below B's, pieces built in are at least 90% of B's,
   and the house score is not lower.

If C passes, confirm it in a second run before low becomes the default, in a PR of its own.

**D against B** (if run): latency p90 falls by at least a third, with B's criteria 2 and 3 held.

## Checked
- `mind/tests/test_llm.py`:
  - The effort is sent only when asked for, and thinking off is sent as `thinking: disabled` at temperature 0.7.
  - A reply cut off at the cap is answered from the end of its reasoning in one non-thinking call. So is a stream
    that ends early, and one whose connection breaks after the reasoning began. One that breaks before anything came
    is asked again.
  - A forced answer that fails falls back to asking again, as before, and is not counted. A forced answer is never
    forced again, and a reply without thinking is never forced.
- `mind/tests/test_mind.py`:
  - A decision asks for the effort and the budget it was given, and nothing when unset.
  - The reasoning is kept as it streams.
  - A stop-gap's prompt is the plan's prompt followed by the present: where the body is and what it holds, that the
    agenda has ended, the outcomes since, what was noticed, what was done meanwhile, how long ago the work ran out,
    and the end of the thoughts. With nothing ended yet, it says so.
  - A stop-gap is one project of at most 4 body moves, taken whole. Five steps, a learned skill, an unknown skill or
    arguments that are not an object are refused with the reason.
  - A stop-gap's memories, skills, keeps and house are ignored. Its outcome leaves the failures and what just happened
    alone.
  - The ask is built from the answer's shape. The plan's rules speak of stop-gaps only when they are on.
- `mind/tests/test_run_godling.py`, the agenda loop with a fake late mind:
  - The body does a stop-gap instead of standing, from the world as it is now. A plan that comes in during the
    stop-gap is taken up when the stop-gap's project ends.
  - A stop-gap that comes after the plan is dropped, and is never logged as chosen.
  - A stop-gap being chosen when the plan fails is taken.
  - Stop-gaps follow one another up to 3, and a failed one is waited out. Later asks say how long the plan has been
    awaited. The next plan hears how long the body stood and what it did.
  - An interrupted stop-gap keeps the plan.
  - A stop-gap after an agenda is told where the agenda left the body.
  - With the deadline at 0 the body waits as before.
  - `main()` defaults to no deadline, passes the effort and the budget through, refuses a budget of 0 or less and a
    negative or infinite deadline, and writes the new summary fields, with `answers_forced` read from the client. The
    console prints the new lines.
- `mind/tests/test_replay_feed.py` and `world/renderer/test/feed.test.js`, on one case in `feed.json`: a stop-gap on
  the screens has no step of an agenda.
- `tools/tests`: the analysis counts stop-gaps apart from projects. It also counts answers given from the reasoning,
  failed attempts, long waits, cost by purpose, the house's best score, and first projects after stop-gaps.
  `compare_runs.py --minute` cuts the arms to the same minute.
- **#80:** run against the code from before ADR-030, the 15 tests it added fail and the other 82 in those three files
  pass. For example: "At index 0 diff: ('decision', None, None) != ('stopgap', 'asked', None)": the body waited and
  no stop-gap came.
- **The review fixes:** run against #80's code, the 27 tests the fixes added or changed fail, and the other 422 tests
  in the mind and tools suite pass.
- **Suites:** the mind and tools suite passes (pytest, Windows Python 3.14), and so does the renderer's (vitest). The
  world and site code is unchanged, so their suites were not run.

## Not checked
- **Not yet in a live run.** No real DeepSeek call has made a stop-gap or a forced answer, so these are untested
  against the live API:
  - that `thinking: disabled` with `json_object` answers a one-project agenda in about 4 s;
  - that the reasoning tail is enough for a good forced answer;
  - how long `reasoning_effort: low` thinks.
- **The 45% saving is a model of the run's waits, not a measurement.** Limiting stop-gaps to body moves may lower it,
  if the mind would rather have used its learned skills.
- **Whether stop-gaps duplicate work the late plan then repeats.** The plan does not know what the stop-gap did.
  Steps that no longer fit fail fast, as they do after a failed project today. The experiment measures it (B's
  criterion 4).
