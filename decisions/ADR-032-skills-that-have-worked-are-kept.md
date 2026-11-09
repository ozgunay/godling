# ADR-032: A skill that has worked keeps its steps until it keeps failing or stops being used, under every memory engine

Date: 2026-11-09, revised the same day after the code review of PR #75. Status: built and tested in the mind's suite.
Not yet tested in a live run.

## Why
In the live run of 2026-11-08/09 (9.6 h, deepseek-flash, `--memory native`, the default), Godling taught itself 110
skills and forgot 81 of them. 11 of the forgotten skills had already worked at least once. Among them:
- `mend_at_home`, which had worked 71 times in 81 runs. It was forgotten at 07:08 UTC after its last two runs failed,
  both stopped on the way in by Godling's own step log.
- `enter_house`, which had worked 12 times in 15 runs, forgotten after two runs failed at a blocked doorway.
- `beam_z_on_step`, forgotten straight after it had worked, when the mind taught itself `arch_beam_z`.

The failures were almost always the situation, not the skill: a blocked way, hands that were full, a spot out of reach.
A skill's steps never change once it is learned. So once they have worked, they work again when the situation allows.
Forgetting cost more than the skill itself. In the same plan that forgot `enter_house`, the mind taught itself
`enter_house_via_door` in its place. That one never worked, and it was forgotten 16 minutes later. In the same way,
`beam_z_on_step` (2 of 3) gave way to `arch_beam_z`, which worked once in 7 runs.

The library can refuse to forget a skill, but under native memory that check was off:
`run_godling.py` built `SkillLibrary(..., protect_proven=args.memory != "native")`.

### Why it was set that way
ADR-002 (D4) brought in the "brain-like memory" arms, native2 and Hindsight, after run m-003. One part of that design
was procedural memory: "proven skills are protected: demoted, never silently forgotten". In m-003 the mind had
forgotten `stack_big` after 26 successes in 35 runs. The `native` arm was kept as it was, as the m-003 baseline of the
A/B comparison ("m-003's setup stays reproducible with `--memory native`"). So native went unprotected to keep the
comparison fair, not because a baseline should forget its skills.

That reason no longer holds:
- The comparison is over. ADR-005 chose Hindsight for the night runs.
- `native` stayed the default, and the live island runs on the default (`deploy/island-start.sh` passes no
  `--memory`). So the live Godling got the baseline's forgetting by accident.
- The baseline cannot be reproduced exactly anyway: the world, the body and the mind have all changed since m-003.
  `git checkout` of that time's code is the way to rerun it. ADR-002's rollback line now says so.

### Turning the old check on is not enough
The old check kept a skill only with 3 or more successes, and let it go once its last 3 runs had failed. Replayed on
the live run's 85 forget requests, it would have kept 2 of the 11 skills that had worked: `mend_at_home` and
`enter_house`. It would still have dropped `beam_z_on_step` straight after it worked. The 3-success floor is the
problem there. It would also let the mind forget `upright_named_log` from the run's final library: it had worked 19
times, then failed 13 times in a row (14 with an interruption). A fixed three failures in a row is too few for a skill with a long record. And
the record kept only the last five outcomes, so it could not count a longer streak at all.

## Decision
**A check in the library, refusing with the reason, the same for every memory engine.** It is not something Godling
has to learn. Across runs deepseek-flash has not learned this kind of thing (ADR-019, ADR-025). As with ADR-025, the
system prompt also states the rule as a fact, so the mind knows it before it asks.

**Rule:** a skill that has worked keeps its steps until either of these happens:
- it has failed, in a row since it last worked, as many times as it has ever worked, and at least 3 times; or
- it has gone 2 hours without working.

"Keeps its steps" means it can be neither forgotten nor taught other steps under its name. Some skills can go at once,
as before:
- A skill that has never worked. That matters: 74 of the run's 85 forget requests were skills that had never worked.
- A skill whose steps call a learned skill that is no longer there. It cannot work again.

What counts as a run:
- A run that attention cuts short (a passing ship, a quake, death) says nothing about the skill. It is not counted.
- A run that breaks, for example when the world fails under a helper, counts as a failed run. The body reports it the
  same way ("fix or forget it").

| Skill (live run, at the forget request) | Worked | Failed in a row | Needed | Idle | Old native | Old native2 | Now |
|---|---|---|---|---|---|---|---|
| `mend_at_home` | 71 of 81 | 2 | 71 | 6 min | forgotten | kept | **kept** |
| `enter_house` | 12 of 15 | 2 | 12 | 4 min | forgotten | kept | **kept** |
| `beam_z_on_step` | 2 of 3 | 0 | 3 | 2 min | forgotten | forgotten | **kept** |
| `move_piece` | 2 of 7 | 1 | 3 | 8 min | forgotten | forgotten | **kept** |
| `roof_log_named` | 1 of 4 | 3 | 3 | 12 min | forgotten | forgotten | forgotten |
| `log_step_at`, `sand_rung` | 1 of 5 each | 4 | 3 | 52-54 min | forgotten | forgotten | forgotten |
| `roof_log_z_from_step` | 1 of 5 | 4 | 3 | 193 min | forgotten | forgotten | forgotten |
| `roof_log_x_from_step` | 2 of 8 | 6 | 3 | 41 min | forgotten | forgotten | forgotten |
| `arch_beam_z` | 1 of 7 | 6 | 3 | 28 min | forgotten | forgotten | forgotten |
| `post_and_fasten` | 2 of 11 | 8 | 3 | 75 min | forgotten | forgotten | forgotten |

Notes on the table:
- "Worked" is the record as it stood, interruptions included. Without them, `mend_at_home` is at 71 of 77: 4 of its 10
  failures were attention cutting it short.
- `post_and_fasten` failed 9 times in a row, but one of those was an interruption, so 8 count.
- The four it keeps had worked 87 times in 106 runs. The seven it lets go had worked 9 times in 45 runs, and each had
  failed at least three times in a row since it last worked.

At the end of the run, 18 skills in the library had worked.
- With the rule as first proposed, 3 of them had reached their count. The other 15 could go only by failing more, and
  a skill the mind no longer runs never fails again.
- With the idle limit, 8 could go if the mind asked: those 3, and 5 more that had not worked for 2 hours.

**Why this rule, and not "never forget a skill that has worked":**
- *The library must be able to shrink.*
  - Every skill is a line in every plan's prompt, and the live island runs for weeks on one memory.
  - About 3 skills an hour proved themselves in this run.
  - A count of failures alone cannot do it. A skill the mind stops using never fails again, so it would stay for good.
  - Hence the idle limit, the usual way to let go of what is no longer used (an idle timeout, or LRU eviction).
- *Why 2 hours of idle time is long enough.* 99% of the gaps between a proven skill's successes in the run were under
  85 minutes, and the longest was 4.3 hours. A skill in use stays.
- *Downtime never counts.* The idle clock runs from the skill's last success or from the library's load, whichever is
  later. So a restart after an outage starts the 2 hours again. Wall time is used, as for the house's stall
  (`HOUSE_STALL`) and sleep.
- *The count weighs the evidence on both sides.*
  - The more often a skill has worked, the more failures in a row it takes to say it no longer works.
  - Failures that come from the situation arrive in streaks, because the mind retries in the same spot.
  - Under this rule a short streak never removes a skill with a long record. A fixed number would: three blocked walks
    would have dropped `mend_at_home`.
- *It is how a failure threshold is usually set.* It resets on a success, as a circuit breaker does or a Kubernetes
  liveness probe does with `failureThreshold` 3, which is also our floor. The only change is that the threshold grows
  with the record.
- *Voyager*, whose skill library this one follows (the `learned.py` docstring), never drops a verified skill. It copes
  with a growing library by fetching only the relevant skills. That remains open here (see Not doing).

**The trade-off, stated plainly:**
- `post_and_fasten` is on the list of losses, and it would still be forgotten, after its third failure in a row.
- Of the nine failures in a row it was forgotten after:
  - seven were full hands, six of them holding Log_3 with nowhere to set it down;
  - one was a fastened log;
  - one was an interruption, which no longer counts.
- So a skill that has worked only once or twice can still be lost to a streak the situation caused.
- If that should never happen, the alternative is the absolute rule. Its cost is the prompt growth described above.

**Changing a skill that has worked: under a new name.**
- Teaching other steps under its name throws away the steps that worked. So it is refused, just as forgetting is, and
  the mind is told to use a new name.
- The first proposal advised "Redefine it with 'learn'". The review found that this wiped the record, and the next
  forget then went through.
- Teaching the same steps again keeps the record.
- Once the skill may go, other steps under its name are taught as before, with a new version and a new record.

## What changes
- `learned.py`
  - **Counting.** Each run of a learned skill counts `fails_in_a_row`: 0 after a success, one more after a failure.
    - `define()` writes it as 0.
    - A success also sets `worked_at`. Both are saved in `skills.json`.
    - A run that attention cut short changes nothing. Its result says "{skill} was interrupted" and carries
      `facts["interrupted"]`, so a skill calling it is not counted either.
  - **Records from older code.** Code from before ADR-032 kept the last five outcomes in `recent`, which is no longer
    written. A record that has `recent` was therefore last written by older code: saved before this change, or run by
    older code after a rollback.
    - At load, its count comes from `recent`. If `recent` holds a success, the count is the failures after it.
    - Otherwise the failures in `recent` come on top of any stored count. When `recent` is full (five), that is only a
      lower bound: the refusal then says "at least its last 5 runs failed". On the live memory, `cube_step_at` had
      really failed 12 times in a row.
    - Then `recent` is dropped.
  - **Refusals.**
    - `forget()` applies the rule. A refusal is logged as `forget_refused`, with `fails_in_a_row` and `needed`.
    - The mind reads the reason in its next plan, for example: "'mend_at_home' was kept: it has worked 71 of 81 times
      and only its last 2 runs failed. A skill that has worked is forgotten only after 71 failed runs in a row, or
      after 2 hours without working. To try other steps, teach them under a new name."
    - `define()` refuses other steps for a skill that keeps its steps, with the same numbers.
  - **Cycles.** `define()` refuses a cycle through other skills (a calls b, b calls a), not only a skill calling
    itself. Before, one run of such a pair recursed until Python stopped it, and every level counted a failure.
  - The `protect_proven` switch is gone, because the rule holds for every engine.
- `skills.py`: the two places that turn an interruption into a result now add `{"interrupted": True}`. Stuck is the
  body's own trouble, so it stays a plain failure.
- `mind.py`: the teaching section states the rule in one sentence.
- `run_godling.py`
  - The library is built the same way for native, native2 and Hindsight. native2 and Hindsight also move from the old
    check to this rule.
  - The `--memory` help says so.
  - The owner's long runs (`tools/long_runs.sh`) run a frozen copy of the code, so runs already going are not affected.

## Checked
- `mind/tests/test_learned.py`, using the live run's own records (`mind/tests/run_live_skills.py`, taken from its
  `log.jsonl` and final `skills.json`):
  - `mend_at_home` at 71 of 81 with 2 failures is kept, and the reason it gets is checked word for word.
  - `beam_z_on_step` is kept: worked twice, then either its last run worked or only its last run failed.
  - `cube_step_at` (10) and `upright_named_log` (19) are kept until the count reaches their successes, and their
    refusal says "at least its last 5 runs failed". After a success the count is exact again.
  - A skill that never worked goes, and so do `post_and_fasten`-like records: 2 of 11 then 8 failures, or 1 of 5 then 4.
  - The idle limit:
    - `top_west_tower`, which worked once and never ran again, goes once 2 hours have passed since the load, not
      before.
    - Each success starts the 2 hours again.
  - An attention interruption leaves the record as it was, for the skill and for a skill that calls it. Being stuck
    still counts as a failure.
  - A run that breaks (the world failing under a helper) counts as a failure, and the refusal says so.
  - Teaching the same steps again keeps the record.
  - Other steps under a kept skill's name are refused, a new name is fine, and once the skill may go the new steps are
    taught.
  - A composite whose inner skill is gone can go.
  - A cycle through another skill is refused.
  - A count left behind by older code is corrected from `recent`. `recent` is no longer written, and `define()` writes
    the count.
  - Driven through the body, the count resets on a success, goes past five, is saved, and makes the skill forgettable
    at exactly the threshold.
- `mind/tests/test_mind.py`:
  - A reply that forgets and re-teaches a kept skill gets both refusals, and the steps stay.
  - The system prompt states the rule.
- `mind/tests/test_run_godling.py`: the launcher with its default memory (native), as the live island runs it, keeps
  `mend_at_home` when the mind asks to forget it.
- Every test was written before its fix:
  - Against the code before this ADR, 7 of the first tests fail, the launcher test with the live run's own line
    `FORGET skill mend_at_home`.
  - Against the first version of this ADR (PR #75), the 15 tests added after the review all fail.
- The mind and tools suites pass (Windows, Python 3.14). `learned.py` has 100% line coverage. CI is not running
  (GitHub billing), so this was run locally.

## Not checked
- Not yet in a live run. Open questions there:
  - whether keeping these skills means fewer near-duplicate skills get taught;
  - how often the mind asks again to forget a skill it was refused;
  - how fast the library grows over days, with the idle limit.
- Each refused request costs no model call, but it adds a line to the next plan's notes.

## Not doing
- **Judging whether a run achieved its purpose.**
  - A run counts as working when its steps work. From 06:38 to 07:01 UTC, `mend_at_home` "worked" seven times while
    the house no longer sheltered Godling; each time the body said "out in the rain with nothing over your head".
  - The library cannot read a skill's `does` text, and its steps (the way into the house) were still right.
  - The cure is for the mind to hear that its house is broken. That is the house-broken notice, a separate change, not
    erasing the way in.
- **Showing a failing streak in the skill list** (for example "proven, 71/81, last 2 failed"). This would be the
  "demoted" half of ADR-002's procedural memory. The record is already shown, and each failure reaches the mind in its
  situation, so this is left for when a live run shows the mind keeps reaching for a skill that is failing.
- **Picking which skills go into the prompt by relevance**, as Voyager does. Only needed once the library outgrows the
  prompt.
- **Telling the situation's failures apart from the skill's**, beyond interruptions. No general test separates them.
  The rule instead gives a long record enough room.
- **Filling in old records' exact counts from the run's `log.jsonl`.** The count from `recent` errs only towards
  keeping, says "at least", and the idle limit bounds it. It is a one-time effect on the memory saved before this
  change.
