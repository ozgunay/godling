# ADR-028: The mind is told when its house is lost, and a cold, hurt body takes shelter by reflex

Date: 2026-11-09 (reviewed the same day). Status: built and tested in the mind's suite. Not yet tried in a live run.

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

The mind then hears it, plainly, four ways:
- **News for attention.** `Mind.on_news` is wired to `Attention.notice`, a new method, at salience 5 for a lost house
  and 4 for lost pieces. The notice goes into "You noticed" in the next plan, and into a death report's "What you
  noticed". It is told, not seen, so it interrupts nothing by itself. The quake or meteor that broke the house has
  already interrupted the plan. For example: "Your house at (-85.0, -30.0) is no longer a house: 16 of the 19 pieces
  in its walls and roof are gone or knocked out of place (...). It no longer keeps the cold off you, nor the rain where
  its roof is gone." When the roof over its room still stands (something fell into the room, say), it says instead:
  "Its roof still keeps the rain off, but no longer the cold." Any roof keeps the rain off (`main.lua`).
- **A line in every plan while it lasts.** News is delivered once, and a plan that is thrown away loses it. So the
  house line itself also says: "It stood as a house until N minutes ago; now it is no house, and keeps neither the
  cold off you nor, where its roof is gone, the rain."
- **Memory, and the digest corrected.** The notice is stored as an episode at importance 5 (kind `house`), so the
  next sleep writes it into the story. Until that sleep, `NativeMemory.amend` keeps it as an addendum shown right after
  the digest: "Since you wrote that: ...". The sleep prompt shows the addendum too, and a sleep that writes a story
  clears it (one that writes none leaves the story and the addendum as they were). With `--memory native2`, the
  notice also corrects the beliefs it holds about its house (`BrainMemory.amend`): the correction counts as more
  confirmed than any of them, so it is recalled first and never the one evicted.
- **A log entry,** `kind="house"`, `phase="lost"`, with `was_house`, `had`, `pieces`, `gone` and the text.

When the house stops being a house, its best score and stall clock restart from what still stands: rebuilding counts
as progress, and no stall is measured from the house it was. A piece knocked off and put back is not progress, so a
partial loss leaves both as they were. When it is a house again, it hears that too, and the "lost" line goes.

What is not a loss:
- **The first look at a layout.** Older saved houses have no record of their pieces. A house the mind changed itself
  is its own doing: a revision on the same site drops the record, so its next look is a first look too.
- **A piece still where it stood** but now reckoned in the house's way.
- **A quake.** While the ground shakes, and until the pieces it woke have settled where they stood, the loss is not
  judged. The shaking wakes loose pieces (`main.lua`), and the house check does not count those.

Each loss is said once.

### 2. A cold, hurt body takes shelter by reflex (`skills.take_shelter`)
This works like the brace reflex (`skills.steady`). All the body's reflexes now run on one look at the world
(`Skills.reflexes`: brace, shelter, glance): between steps, while a step waits, and while the mind thinks, in both run
loops. A learned skill is checked step by step, inside it. The cold is killing the body (`Skills.cold_danger`) when
all of these hold:
- Its health is below **35** (`COLD_HEALTH`): about 14 minutes from death by cold in the open.
- It is **cold** (the world's own `Cold`: at night, or soaked to 50 out in the rain).
- **Nothing is over it**: not `Sheltered`, not `InHouse`.
- It is alive, not drowning, and not in a quake (bracing comes first).
- It is not warming itself by a fire in dry weather. A fire halves the cold as a roof does, so walking from one to the
  other gains nothing.

Then the step waits, and the body walks to the nearest roof it knows within 80 units. It knows a roof two ways:
- Spots where it **felt** a roof over it before. The body remembers these as it goes, and forgets each one when it
  stands there in the open.
- Cells under a building piece it **sees** lying high enough: its underside high enough to walk under, as `walk_to`
  reckons it, and no more than 15 up (`main.lua` `shelterOf`, `house.OVER`), with nothing in between.

Either way, the body first checks that the roof is still there, so a roof that is gone is no shelter. The broken house
is the case in point: the mind thought its roof was still there and died under where it had been.

**A house it has stood in comes before any plain roof in reach.** A house keeps the cold off and mends a fed body
(2 to 4 times as fast once its size counts, #82). A plain roof at night only halves the cold, and mends nothing.
Coming from outside, the nearest roofs are often the house's own eaves, or the doorway under its lintel. When the body
is already under a roof that is no house, and still cold, it walks on into a house it knows in reach. With none known,
it stays under the roof and says nothing. A house where it is not warm on arrival (no house there now) is not walked
to again while the danger lasts. This walk on is held back like any other: once it has taken the body into the house,
it lets the mind take it out again under a roof until its health has fallen another 10.

The world has the last word on arrival:
- **The rain still reaches it there.** That roof is not tried again while the danger lasts.
- **The walk did not get there** (snagged, a stray log in the doorway). That roof is tried again a minute later
  (`SHELTER_RETRY`), when the way may have cleared.

It tries at most three roofs in one go. The mind is told which failed and how, so that it does not go back to one.

When the reflex moved the body, the step it was about to take returns `interrupted: <what happened>`. The agenda is
dropped, and the mind plans afresh from under the roof, which is the path any salient interruption takes. When it
shelters the body while the mind thinks, the plan being thought is dropped the same way: it was made for where the body
stood. The step's result carries the words to the mind; attention keeps them for a death report.

> You were cold and soaked in the rain, your health down to 30 of 100, with nothing over you at (-80.0, -28.0): out
> there the cold would take the rest of it in about 12 minutes. Your body went by itself to the nearest roof it knows,
> 37 units away, and stands under it at (-115.0, -17.5); here you are under a roof, out of the rain.

**It cannot loop:**
- **No shelter known.** The body says so once ("... your body knows no roof within 80 units to shelter under: out here
  the cold takes the rest of your health in about 12 minutes"), as news, and goes on with the step: it did nothing,
  so nothing is dropped. It does not say it again while the danger lasts. It looks again every few seconds
  (`SHELTER_LOOK_AGAIN`), and a roof built meanwhile is one it knows.
- **The mind takes it out again.** It may need food: below half fed nothing mends, even under a roof. The reflex lets
  it go until its health has fallen another 10 (`COLD_AGAIN`). So within one spell of danger it steps in at most about
  four times, at 35, 25, 15 and 5, besides one more try a minute at a roof or house it could not get to. Each time,
  the mind is told. If the roof it sheltered under is knocked away from
  over it, that was not the mind, and it shelters again at once.
- **When the danger is over.** That is at health 50 (`WARM_AGAIN`), or once the body stands in the open in dry weather
  without being cold. Drying under the roof is not the end of it.
- **Steps it lets go:**
  - **A walk to a roof**, since the mind is already taking it there. The walk's helpers are worked out first. A walk
    back under a roof where the rain reached it is not let go.
  - **A learned walk home.** A learned skill's own steps are checked, so its walk under the roof goes ahead too.
  - **Eating and speaking.** They are over at once and take the body nowhere, and eating is what lets it mend.
- **The hourly sleep waits** while the cold is killing the body. It is a long model call on the body's own thread,
  and nothing would watch the body meanwhile.

This is how survival games do it. In RimWorld, needs that turn urgent break into a colonist's work: a freezing pawn
goes to a warm room by itself, then back to work. The reflex is not a strategy. Where to go next, whether to go out
again, making a fire, and rebuilding the house all stay the mind's.

### Guided construction
Neither change guides construction. The house notice says what was lost, not how to rebuild. The house line already
had its "Next:" step (ADR-019), and this change adds nothing to it. The reflex moves the body; it builds nothing.

## Review
The review of PR #76 found 34 issues; the review-fix PR stacked on it settles them. The behaviour above is after
those fixes. Two were left as they are, for these reasons:
- **The house's pieces are tracked twice.** Attention already reports damage to builds, and a house the body built is
  one of them. Keeping the house's pieces in a structure record attention checks would merge the two stores. But the
  house's pieces are not always a build (pieces the body did not place, a first course not yet stacked), so that is a
  redesign for later.
- **The tests' house builder and fake model are copied** from `test_mind.py`. Moving them into `helpers.py` means
  editing `test_mind.py` and `test_house_recovery.py`, which the bigger-houses work is changing at the same time.

## Checked
Run from the repository root on Windows (Python 3.14). CI is not running (GitHub billing), so these are local runs.
- `mind/tests/test_house_lost.py`: the live run's loss as a test. A finished house loses its roof and a corner. Checks:
  - `phase="lost"` is logged, with the pieces.
  - The news goes to attention, once.
  - The house line, in the next plan and the one after.
  - No stall carried over from before the loss.
  - The episode, and the digest's addendum, until a sleep rewrites the story; a sleep that writes no story keeps it.
  - The house heard of when built again.
  - Pieces lost from a house still being built: the stall it was in still counts.
  - A stray piece in the room leaves the roof keeping the rain off, and the notice says so.
  - A quake that only wakes the house's pieces is no loss.
  - No false alarm at a first look at an old finished house, or after the mind changes its own layout, or for a piece
    only set down in the room. Both of the first two are pinned: reading a missing record as empty, or keeping the old
    record across a revision, makes the test fail.
  - The beliefs `BrainMemory` holds about the house, with the correction first when they are full.
  - `Attention.notice`.
- `mind/tests/test_skills_shelter.py`: the reflex on the stand-in island, with a stand-in for the world's weather
  (rain, night, a fire, a house, the 15-unit cap) and, for the house, walls that stop the body.
  - It takes shelter before the step, and tells the mind.
  - It does nothing when healthy enough, under a roof, in dry weather, dead, without health, drowning, or by a fire on
    a dry night.
  - With no shelter known, it says so once and the step goes on; it looks again only now and then, and takes a roof
    built later.
  - After taking shelter, it lets the mind take it out until its health has fallen 10 more, also after drying under
    the roof; it shelters again at once if the roof over it is knocked away.
  - A remembered roof that is gone is no shelter; a roof too low to walk under, or too high to count, is none either.
  - A roof the world does not count is tried once, then the next, and named; a walk back under it is not let go.
  - A roof it could not get to is tried again a minute later.
  - At night it goes into the house it has stood in, not its doorway, and before a shed much nearer than the house.
  - Cold under a roof at night, it walks on into the house; under a roof with no house known, it stays; a house that
    keeps nothing warm now is not walked to again; once in, it lets the mind take it out until 10 more are gone.
  - It shelters inside a `wait`, between a learned skill's steps, and while the mind thinks, in both run loops, which
    then drop the plan being thought.
  - A walk to a roof (also one named by helpers), a learned walk home, eating and speaking are let go.
  - News on the way stops it; a bug in its walk never escapes `Skills.run`; a failed observation is logged.
  - The hourly sleep waits while the cold is killing the body.
- Against the code from before PR #76, 14 of its first 23 tests failed: every one that needs the notice or the reflex.
  Against PR #76 itself, 26 of the review fix's tests failed, each one a finding, and 3 more for the cross-PR finding
  INT-10.
- The mind and tools suites pass (`python -m pytest -q`). The world script is unchanged.

## Not checked
- **No live run has tried it yet.** In particular:
  - whether deepseek-flash plans differently once told that its house is lost;
  - how often the reflex steps in;
  - whether the plans it throws away cost more than they save.
- **The body's view of a roof can differ from the world's.** The world probes a column 1.2 wide over the body; the body
  looks at the cell's centre and at building pieces only, not rock. When they differ, the world's word is taken on
  arrival, at the cost of a walk.
- **At night a plain roof only halves the cold.** The reflex goes into a house it has stood in, but goes to a roof when
  it knows no house in reach, and a body sheltering there at night still loses health, at half the pace.
- **The brace reflex still has no watch during the hourly sleep**, as before ADR-028.
- **The world is unchanged.** It already gives `Health`, `Cold`, `InRain`, `Sheltered`, `InHouse` and `ByFire`, so
  there are no world tests.
- **A small extra cost.** Inside a learned skill, the reflex looks at the world once before each of its steps. Between
  top-level steps, while waiting and while thinking, it shares the brace reflex's look.
- **Not yet merged with the other fixes from this run:** a clear building site, thinking time, and the rest. The
  reflex's walk and the hands-full reflex have not been tried together.
