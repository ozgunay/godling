# ADR-003: Body reflexes, a higher output cap, and the next levers

Date: 2026-11-01. Status:
- B1–B6 are done and tested.
- O1 is done: the long run restarted as m2.
- O2, O6 and O7 are done; see "Decided and built" below.
- O4 changed after you saw it (bubble rejected; side panel proposed).
- O3 and O5 are still open.

## Context
- The tuned ADR-002 smoke (s4) left 59% of projects failing.
- The long run m-004/m-005/m-006 (three memory arms, 8 h) started at 14:45 on the s4 code. It runs from a frozen copy in `~/godling-runs/m-code`, so work on the code can continue during it.
- Failure reasons in s4 plus the sleep preflight (258 projects, 151 failed):

| Failures | Reason |
|---:|---|
| 89 | `pick_up`: "hands are full". 72 of these came right after a failed project left a cube in hand: a cascade caused by ADR-002's "carry on with the next project". |
| 13 | `walk_to` onto a mesa, step or ridge: "you cannot climb" |
| 7 | `place_at` rejected for sinking 0.5–1 cm into the surface below (the world counts touching as overlap) |
| 6 | a perception helper (`{"nearest_free": "cube"}`) used in a plain agenda step, where only learned skills resolved them |

## Done (body level: the body knows its own limits, no strategy is added)
- **B1. Hands-full reflex.** `pick_up` with full hands first sets the held object down on clear ground beside the body, away from the target and from kept structures, then picks up. Asking to pick up the object already held counts as done.
- **B2. Helpers work in any step**, not only inside learned skills.
- **B3. Resting on the surface.** A placement that would sink up to 6 cm into the surface below is lifted to rest on it. A placement into a real obstacle is still refused.
- **B4. Walk to the foot.** `walk_to` a point on higher ground walks to its foot and says so. If the body is already at the foot, it fails as before.
- **B5. Output cap 16,000 → 32,768 tokens, HTTP timeout 120 → 360 s.** About 1 decision in 25 spent the whole 16k cap on reasoning and lost its answer. DeepSeek accepts caps up to 65,536. This follows D1: the cap only stops runaway output and never limits reasoning.
- **B6. Tooling.**
  - Long runs use a frozen code copy (`<prefix>-code`).
  - `compare_runs.py` estimates Hindsight's own DeepSeek cost per run, which the mind's cost does not include.
  - The sleep loop guard: a failing sleep retries hourly, never every cycle.

### Measured: smoke f (10 min, native and native2, B1–B3 only)

| | s4 native | s4 native2 | f native | f native2 |
|---|---|---|---|---|
| projects finished | 52% | 41% | 69% | 74% |
| body busy | 27% | 23% | 34% | 26% |
| moving | 19% | 19% | 25% | 21% |
| placements/h | 175 | 83 | 243 | 307 |
| tallest stack | 11 | 3 | 10 | 7 |
| cost $/h | 0.40 | 0.39 | 0.44 | 0.50 |

In smoke f, 10 of the remaining 22 failures were walks onto raised ground. B4 handles those; it was tested live in a scratch world, not yet in a smoke.

## Open decisions
- **O1. Restart the long run with B1–B5?**
  - The running m-004/m-005/m-006 measure the s4 code, which has the full-hands cascade. The comparison between memory arms stays fair, but every arm is held back by it.
  - Restarting costs about 20 minutes of run (about $0.40).
  - *Recommended:* restart.
- **O2. Human-paced handling (extends D3b).**
  - Picking up and placing would take about 1–1.5 s, like a person bending and reaching (now 0.2–1 s). Walking would slow from 8 to 5 units/s.
  - This adds body time to every planned step at no token cost, so the body moves more while the mind thinks.
  - It is not an idle behaviour: the body still does only what the mind chose.
- **O3. A separate DeepSeek API key for Hindsight.**
  - Its own calls (fact extraction, consolidation) add an estimated $0.2–0.3/h, but its log only gives a lower bound.
  - A second key would show its exact cost on the DeepSeek dashboard.
- **O4. Show the thinking to viewers.**
  - While the body waits for the mind, the world could show what the mind is weighing, taken from the reasoning DeepSeek streams back, shortened.
  - It is true content, not filler. It is extra work, and it is not yet known whether Clawblox's spectator view can show it.
- **O5. Graphiti as a 4th memory arm,** decided after the long run shows whether memory differences matter over hours.
- **O6. Interrupt less.**
  - In the 24-minute m-004…006 run there were 24 "knocked" alarms. 17 were real physics, not the body's own handling: a ring sliding down a thin column, towers settling, falling ImpactBlocks.
  - A new object appearing within 30 units also interrupts (salience 4).
  - Every interruption throws away the plan in progress, about 40 s of thinking: 3–8 per arm in 24 minutes.
  - Proposal: interrupt only for visitors and real damage (a structure lost height, a kept cube left the world). Small shifts and new objects become notes for the next plan.
- **O7. Material is the real ceiling.**
  - The island has 12 cubes. All three arms built an 11–12-high spire within about 8 minutes, then turned to experiments (jumps, throws, rim placements).
  - In m-003 the free cubes were gone after about 90 minutes. Only ImpactBlocks dropping from the sky, many of them onto unreachable mesa tops, kept building going.
  - So placements per hour and tallest stack measure the world more than the mind.
  - For the product this is where the plan's paid viewer interventions fit: viewers drop material.
  - For the experiments: a slow, steady supply of reachable cubes, the same in every arm.

Done after the m2 start (in the dev code, not in m2): a walk that ends at the foot of raised ground counts as done even when the body was already there. A repeat walk had failed the whole project.

## Decided and built (after the m2 start; dev code only, m2 keeps its frozen copy)
- **Our own world: `C:\Work\godling\world`.** It is a copy of Mesa Island, and its README lists the changes. Every run freezes a copy of it in its run folder, and long runs freeze one in `<prefix>-code/world`.
- **O2. Human pace.**
  - Walking speed is 5 (`--walk-speed` default).
  - In the world script, a picked-up block rises into the hands over 1.0 s, and a placed block is lowered over 1.2 s (upstream: 0.3 s). The skills wait for both.
  - Measured in a scratch world: about 4–5 units/s walking, lifting 1.0 s, placing 1.2 s.
  - Bug found in smoke g: the body reads "holding" from where the block floats, which is only true once the block has risen. `pick_up` checked too early, retried, and got "already holding". 79 projects failed this way. It now checks after the lift.
- **O6. Interrupt less.**
  - A new object is now a note (salience 3).
  - A kept cube that shifted a little is a note. One that fell (dropped more than half a cube) or was knocked more than 2 units away still interrupts.
  - Visitors and kept cubes leaving the world still interrupt.
- **O7. Steady cubes.**
  - Every 120 s, if fewer than 6 cubes lie loose on open ground, a `SupplyBlock_n` drops from 14 up at a clear spot. The spot is well inside the island and away from mesas, other objects and the player.
  - The spots follow a fixed pseudo-random sequence.
  - Tested: 3 cubes arrived in about 30 s at a 10 s test interval.
  - The mind's world client now counts `SupplyBlock_` objects as movable. Without that they would have been invisible to it.
- **O4. Thinking.**
  - The thought bubble above the head was built and shown working, then rejected. You want a scrollable side panel with timing, like the reasoning panel next to the game in "Claude Plays Pokémon". The bubble is fully removed: the world's renderer is upstream's again.
  - Kept from that work: replies are streamed. Each plan's reasoning is written to `mind/thinking.jsonl` as it arrives (about one piece per second), and each decision carries its plan number, so a viewer can show a plan's reasoning next to its outcome.
  - The side panel itself is a proposal.

### Measured: smoke h (10 min, native and native2: O2 + O6 + O7 + the pick-up fix)

| | f native | f native2 | h native | h native2 |
|---|---|---|---|---|
| body busy | 30% | 24% | 85% | 33% |
| moving | 25% | 21% | 38% | 21% |
| waiting for the mind | 61% | 70% | 15% | 64% |
| think time p50 | 45 s | 49 s | 34 s | 50 s |
| reasoning tokens / decision | 6,828 | 7,545 | 5,357 | 9,017 |
| projects finished | 69% | 74% | 85% | 74% |
| placements/h | 217 | 277 | 431 | 135 |
| cost $/h | 0.44 | 0.49 | 0.39 | 0.54 |

- Failures fell from 70% (smoke g, before the pick-up fix) to 19%. What's left is ordinary: stuck walks and occupied spots.
- In the native arm, each plan was thought up while the body did the previous agenda; the body waited at most 2 s between agendas.
- native2 thought much longer per plan and was interrupted more. Ten minutes cannot tell whether that is the memory type or chance.
- native2 found and used both supply cubes that dropped.

## Proposal: the thinking side panel (replaces the bubble)
- **A local viewer page**, modelled on the reasoning panel beside the game in "Claude Plays Pokémon" and on agent trace timelines (Langfuse, LangSmith, Laminar).
  - Left: the live 3D world (the spectator view, embedded).
  - Right: a scrollable mind panel.
- **Timing strip.** Two lanes over time:
  - Mind: when each plan was being thought up.
  - Body: each project, done or failed, and any wait for the mind.
  - Clicking a span jumps to its entry.
- **Transcript.** Clock time on every entry:
  - each plan's reasoning, live as it streams, folded to a few lines with "show all";
  - the decision's thought and its projects, with outcome and duration;
  - noticed events, learned skills, sleeps and dreams.
  - It follows live, and you can scroll back freely; "Jump to live" returns.
- **Data.** It reads the run folder (`mind/log.jsonl` and `mind/thinking.jsonl`), so the same page also replays finished runs.
- **Later.** Scrubbing the strip could also move the 3D view to that moment, using the world's recording.
