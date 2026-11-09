# ADR-028: The mind is told when its house is lost, and a cold, hurt body takes shelter by reflex

Date: 2026-11-09. Status: built and tested in the mind's suite. Not yet tried in a live run.

## Why
Godling died of the cold twice in the 9.6-hour live run of 2026-11-08 22:10 to 2026-11-09 07:50 UTC. The evidence is
in that run's `mind/log.jsonl` and `console.log`.

- **The house broke, and nothing said so.** The house became a house at 00:19 with 19 pieces. An earthquake at 06:33
  and a meteor at 06:34:50 took it down to 3. The log shows `installed` dropping 19 → 3 → 2 → 1. But `house_progress`
  only set `house["built"] = None`. Becoming a house was logged; ceasing to be one was not, and the mind was not told.
  The 06:19 sleep digest still said "My house ... is the only warm dry place, where I mend at double rate". The house
  line went on counting from the old best score, so at 06:46 the mind read that the house had come "no further in
  381 minutes".
- **The first death.** At 06:36 the mind thought "The roof over the room still keeps me dry, so first mend". Its learned
  skill `mend_at_home` then waited three times thirty seconds, and every wait said "here you are out in the rain with
  nothing over your head, and cold". It ran that skill four times between 06:36 and 06:43. Its health fell from 51 to
  12, and it died of the cold at 06:54.
- **The second death.** At 07:31, with its health at 27 and soaked through, it decided "I will not walk 25 units to the
  one roofed cell at (-115,-17.5)" and laid a log instead. It died at 07:42.
- **How fast the cold kills.** In the open, the cold takes a whole body's health in 40 minutes (`main.lua`
  `HARM.coldDrainSeconds = 2400`). A roof or a fire halves that. Only a house keeps it off. At 35 health a body in the
  open has about 14 minutes.

## Decision
Two changes, both made in code. Neither is a rule in the prompt or something Godling has to learn. Deepseek-flash has
not learnt things like these across runs (ADR-019, ADR-025), and here it ignored the plain words of every step result.

### 1. The mind hears at once that its house is lost (`mind.py`)
On every look at its house (`house_progress`), the mind compares the house's own pieces (in its walls and roof) with
the pieces it had at the last look, and where each one stood. Two things count as a loss:
- The house was a house and no longer is.
- Pieces it had are gone: missing, or moved more than 0.5 from where they stood.

The mind then hears it, plainly, five ways:
- **News for attention.** `Mind.on_news` is wired to `Attention.notice`, a new method, at salience 5 for a lost house
  and 4 for lost pieces. The notice goes into "You noticed" in the next plan, and into a death report's "What you
  noticed". It is told, not seen, so it interrupts nothing by itself. The quake or meteor that broke the house has
  already interrupted the plan.
- **A note in the next plan:** "Your house at (-85.0, -30.0) is no longer a house: 16 of the 19 pieces in its walls
  and roof are gone or knocked out of place (...). It keeps neither the rain nor the cold off you now."
- **A line in every plan while it lasts.** Notes are delivered once, and a plan that is thrown away loses them. So the
  house line itself also says: "It stood as a house until N minutes ago; now it is no house, and keeps neither the
  cold off you nor, where its roof is gone, the rain."
- **Memory, and the digest corrected.** The notice is stored as an episode at importance 5 (kind `house`), so the
  next sleep writes it into the story. Until that sleep, `NativeMemory.amend` keeps it as an addendum shown right after
  the digest: "Since you wrote that: ...". The sleep prompt shows the addendum too, and the sleep clears it. With
  `--memory native2`, the notice also corrects the beliefs it holds about its house (`BrainMemory.amend`).
- **A log entry,** `kind="house"`, `phase="lost"`, with `was_house`, `had`, `pieces`, `gone` and the text.

The house's best score and stall clock restart from what still stands. Putting back what fell counts as progress
again, and no stall is measured from a score it had before the loss. When it is a house again, it hears that too,
the same ways, and the "lost" line goes.

What is not a loss: the first look at a layout. Older saved houses have no record of their pieces, and a house the mind
changed itself is its own doing. A piece still where it stood but now reckoned in the house's way is not a loss
either. Each loss is said once.

### 2. A cold, hurt body takes shelter by reflex (`skills.take_shelter`)
This works like the brace reflex (`skills.steady`). Between steps, while a step waits, and while the mind thinks, the
body checks itself. All of these must hold:
- Its health is below **35** (`COLD_HEALTH`): about 14 minutes from death by cold in the open.
- It is **chilled**: cold, or soaked to 50 out in the rain (`main.lua`: soaked that far in the rain, a body is cold).
- **Nothing is over it**: not `Sheltered`, not `InHouse`.
- It is alive, not drowning, and not in a quake (bracing comes first).

Then the step waits, and the body walks to the nearest roof it knows within 80 units. It knows a roof two ways:
- Spots where it **felt** a roof over it before. The body remembers these as it goes, and forgets each one when it
  stands there in the open.
- Cells under a building piece it **sees** lying high enough: its underside more than the body's height above the
  ground, and no more than 15 up (`main.lua` `shelterOf`), with nothing in between.

Either way, the body first checks that the roof is still there, so a roof that is gone is no shelter. The broken house
is the case in point: the mind thought its roof was still there and died under where it had been. The world has the
last word. If the body arrives and the world says it is still out in the open, that roof is marked tried, and the body
goes on to the next. It tries at most three roofs in one go, and the same roof once while the danger lasts.

The step it was about to take returns `interrupted: <what happened>`. The agenda is dropped, and the mind plans afresh
from under the roof. That is the same path any salient interruption takes. The body tells the mind, through
`Skills.on_reflex` → `Attention.notice` and in the step's result:

> You were cold and soaked in the rain, your health down to 30 of 100, with nothing over you at (-80.0, -28.0): out
> there the cold would take the rest of it in about 12 minutes. Your body went by itself to the nearest roof it knows,
> 37 units away, and stands under it at (-115.0, -17.5); here you are under a roof, out of the rain.

**It cannot loop:**
- **No shelter known.** The body says so once ("... your body knows no roof within 80 units to shelter under: out here
  the cold takes the rest of your health in about 12 minutes") and goes on with the step. It does not say it again
  while the danger lasts. A roof built meanwhile is one it knows.
- **The mind takes it out again.** It may need food: below half fed nothing mends, even under a roof. The reflex lets
  it go until its health has fallen another 10 (`COLD_AGAIN`). So within one spell of danger it steps in at most about
  four times, at 35, 25, 15 and 5. Each time, the mind is told.
- **When the danger is over.** That is at health 50 (`WARM_AGAIN`), or once the body stands in the open without being
  chilled. The next spell of danger starts afresh.
- **Steps it lets go.** A walk to a roof goes ahead, since the mind is already taking it there. So do eating and
  speaking, which are over at once and take the body nowhere: eating is what lets it mend.

This is how survival games do it. In RimWorld, needs that turn urgent break into a colonist's work: a freezing pawn
goes to a warm room by itself, then back to work. The reflex is not a strategy. Where to go next, whether to go out
again, making a fire, and rebuilding the house all stay the mind's. The reflex picks the nearest roof, not the
warmest. A house it stood in comes first only between two equally near.

### Guided construction
Neither change guides construction. The house notice says what was lost, not how to rebuild. The house line already
had its "Next:" step (ADR-019), and this change adds nothing to it. The reflex moves the body; it builds nothing.

## Checked
Run from the repository root on Windows (Python 3.14). CI is not running (GitHub billing), so these are local runs.
- `mind/tests/test_house_lost.py`: the live run's loss as a test. A finished house loses its roof and a corner. Checks:
  - `phase="lost"` is logged, with the pieces.
  - The news goes to attention.
  - The note, and the house line, in the next plan and the one after.
  - No stall carried over from before the loss.
  - The episode, and the digest's addendum, until the sleep rewrites the story.
  - The house heard of when built again.
  - Pieces lost from a house still being built.
  - No false alarm at a first look, after the mind changes its own layout, or for a piece only set down in the room.
  - The beliefs `BrainMemory` holds about the house.
  - `Attention.notice`.
- `mind/tests/test_skills_shelter.py`: the reflex on the stand-in island, with a stand-in for the world's weather.
  - It takes shelter before the step, and tells the mind.
  - It does nothing when healthy enough, under a roof, in dry weather, dead, without health or drowning.
  - With no shelter known, it says so once, and takes a roof built later.
  - After taking shelter, it lets the mind take it out until its health has fallen 10 more.
  - A remembered roof that is gone is no shelter.
  - A roof the world does not count is tried once, then the next.
  - It shelters inside a `wait`, and while the mind thinks (`watch_while_thinking`).
  - A walk to a roof, eating and speaking are let go.
  - News on the way stops it.
  - A failed observation is logged.
- Against the code from before this change, 14 of the 23 new tests fail: every one that needs the notice or the
  reflex. The 9 that pass are the guards: the cases where the reflex must stay out of the way, and no false alarms.
  The core reproduction walks the cold body at health 30 off into the rain, as in the run.
- The mind suite passes (`python -m pytest mind/tests -q`), as do the world, site and renderer suites (see the PR).

## Not checked
- **No live run has tried it yet.** In particular:
  - whether deepseek-flash plans differently once told that its house is lost;
  - how often the reflex steps in;
  - whether the plans it throws away cost more than they save.
- **The body's view of a roof can differ from the world's.** The world probes a column 1.2 wide over the body; the body
  looks at the cell's centre and at building pieces only, not rock. When they differ, the world's word is taken on
  arrival, at the cost of a walk.
- **At night a roof only halves the cold.** The reflex goes to the nearest roof, not to a house or a fire, so a body
  sheltering at night still loses health, at half the pace.
- **The world is unchanged.** It already gives `Health`, `Cold`, `Wet`, `InRain`, `Sheltered` and `InHouse`, so there
  are no world tests.
- **A small extra cost.** The reflex adds one observation per top-level step, and none while it waits or thinks, where
  it reuses the look just taken.
- **Not yet merged with the other fixes from this run:** a clear building site, thinking time, and the rest. The
  reflex's walk and the hands-full reflex have not been tried together.
