# ADR-032: A skill that has worked is kept until it keeps failing, under every memory engine

Date: 2026-11-09. Status: built and tested in the mind's suite. Not yet tested in a live run.

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
  `git checkout` of that time's code is the way to rerun it.

### Turning the old check on is not enough
The old check kept a skill only with 3 or more successes, and let it go once its last 3 runs had failed. Replayed on
the live run's 85 forget requests, it would have kept 2 of the 11 skills that had worked: `mend_at_home` and
`enter_house`. It would still have dropped `beam_z_on_step` straight after it worked. The 3-success floor is the
problem there. It would also let the mind forget `cube_step_at` (10 successes) and `upright_named_log` (19 successes)
from the run's final library, whose last five runs had failed. A fixed three failures in a row is too few for a skill
with a long record. And the record kept only the last five outcomes, so it could not count a longer streak at all.

## Decision
**A check in the library, refusing with the reason, the same for every memory engine.** This is not a rule in the
prompt and not something Godling has to learn. Across runs deepseek-flash has not learned this kind of thing (ADR-019,
ADR-025).

**Rule:** a skill that has worked is forgotten only after it has failed, in a row since it last worked, as many times
as it has ever worked, and at least 3 times. A skill that has never worked can be forgotten at once, as before. That
matters: 74 of the run's 85 forget requests were skills that had never worked.

| Skill (live run, at the forget request) | Worked | Failed in a row | Needed | Old native | Old native2 | Now |
|---|---|---|---|---|---|---|
| `mend_at_home` | 71 of 81 | 2 | 71 | forgotten | kept | **kept** |
| `enter_house` | 12 of 15 | 2 | 12 | forgotten | kept | **kept** |
| `beam_z_on_step` | 2 of 3 | 0 | 3 | forgotten | forgotten | **kept** |
| `move_piece` | 2 of 7 | 1 | 3 | forgotten | forgotten | **kept** |
| `roof_log_named` | 1 of 4 | 3 | 3 | forgotten | forgotten | forgotten |
| `log_step_at`, `roof_log_z_from_step`, `sand_rung` | 1 of 5 each | 4 | 3 | forgotten | forgotten | forgotten |
| `roof_log_x_from_step` | 2 of 8 | 6 | 3 | forgotten | forgotten | forgotten |
| `arch_beam_z` | 1 of 7 | 6 | 3 | forgotten | forgotten | forgotten |
| `post_and_fasten` | 2 of 11 | 9 | 3 | forgotten | forgotten | forgotten |

The four it keeps had worked 87 times in 106 runs. The seven it still lets go had worked 9 times in 45 runs, and
each had failed at least three times in a row since it last worked.

**Why this rule, and not "never forget a skill that has worked":**
- *The library must still be able to shrink.* Every skill is a line in every plan's prompt, and the live island runs
  for weeks on one memory. About 3 skills an hour proved themselves in this run. With no way out, a skill that worked
  once by luck would stay in the prompt forever.
- *It weighs the evidence on both sides.* The more often a skill has worked, the more failures in a row it takes to
  say it no longer works. Failures that come from the situation arrive in streaks, because the mind retries in the
  same spot. Under this rule a short streak never removes a skill with a long record. A fixed number would: three
  blocked walks would have dropped `mend_at_home`.
- *It is how a failure threshold is usually set.* It resets on a success, as a circuit breaker does or a Kubernetes
  liveness probe does with `failureThreshold` 3, which is also our floor. The only change is that the threshold grows
  with the record. It is one sentence, so the refusal can state it exactly.
- *Voyager*, whose skill library this one follows (the `learned.py` docstring), never drops a verified skill. It copes
  with a growing library by fetching only the relevant skills. That remains open here (see Not doing).

**The trade-off, stated plainly:** `post_and_fasten` is on the list of losses, and it would still be forgotten,
after its third failure in a row. All nine of those failures were "hands are full: holding Log_3, and there is no clear
spot nearby". So a skill that has worked only once or twice can still be lost to a long streak caused by the
situation. If that should never happen, the alternative is the absolute rule. It is a one-line change in `forget()`,
and its cost is the prompt growth described above.

**The way to change a skill stays open.** The refusal says "Redefine it with 'learn' to improve it instead".
Redefining keeps the name, replaces the steps and starts a new record (unproven). This was already so, and it is the
mind's deliberate choice.

## What changes
- `learned.py`
  - Each run of a learned skill now counts `fails_in_a_row`: 0 after a success, one more after a failure. It is
    saved in `skills.json`, so it survives restarts.
  - Records saved before this change have only their last five outcomes (`recent`). Their count starts from the
    failures at the end of `recent`. That is a lower bound, so in doubt a skill is kept.
  - `forget()` applies the rule. A refusal is logged as `forget_refused`, now with `fails_in_a_row` and `needed`. The
    mind reads the reason in its next plan, for example: "'mend_at_home' was kept: it has worked 71 of 81 times and
    only its last 2 runs failed. A skill that has worked is forgotten only after 71 failed runs in a row. Redefine it
    with 'learn' to improve it instead."
  - The `protect_proven` switch is gone, because the rule holds for every engine.
- `run_godling.py`: the library is built the same way for native, native2 and Hindsight. native2 and Hindsight also
  move from the old check to this rule. The owner's long runs (`tools/long_runs.sh`) run a frozen copy of the code, so
  runs already going are not affected.
- The system prompt does not change. As with ADR-025, the refusal is how the mind finds out.

## Checked
- `mind/tests/test_learned.py`, using the live run's own records (`mind/tests/run_live_skills.py`, taken from its
  `log.jsonl` and final `skills.json`):
  - `mend_at_home` at 71 of 81 with 2 failures is kept, and the reason it gets is checked word for word.
  - `beam_z_on_step` is kept: worked twice, then either its last run worked or only its last run failed.
  - `cube_step_at` (10) and `upright_named_log` (19), whose last five runs failed, are kept until the count reaches
    their successes.
  - A skill that never worked goes, and so do `post_and_fasten`-like records: 2 of 11 then 9 failures, or 1 of 5 then 4.
  - Driven through the body, the count resets on a success, goes past the five outcomes kept in `recent`, is saved,
    and makes the skill forgettable at exactly the threshold.
  - An old record without the count goes on counting from its last five outcomes, without counting a failure twice.
- `mind/tests/test_run_godling.py`: the launcher with its default memory (native), as the live island runs it, keeps
  `mend_at_home` when the mind asks to forget it.
- Against the code from before this change, 7 of these tests fail, the launcher test with the live run's own line,
  `FORGET skill mend_at_home`. The 4 "can go" cases pass before and after.
- The whole mind suite passes (Windows, Python 3.14). CI is not running (GitHub billing), so this was run locally.

## Not checked
- Not yet in a live run. Open questions there:
  - whether keeping these skills means fewer near-duplicate skills get taught;
  - how often the mind asks again to forget a skill it was refused;
  - how fast the library grows over days.
- Each refused request costs no model call, but it adds a line to the next plan's notes.

## Not doing
- **Showing a failing streak in the skill list** (for example "proven, 71/81, last 2 failed"). This would be the
  "demoted" half of ADR-002's procedural memory. The record is already shown, and each failure reaches the mind in its
  situation, so this is left for when a live run shows the mind keeps reaching for a skill that is failing.
- **Picking which skills go into the prompt by relevance**, as Voyager does. Only needed once the library outgrows the
  prompt.
- **Telling the situation's failures apart from the skill's.** No general test separates them. The rule instead gives
  a long record enough room.
