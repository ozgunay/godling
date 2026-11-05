# ADR-019: A house: one definition for the world, the mind and the measure; warmth in tiers; how fire is made

Date: 2026-11-04. Status: built and tested; measured in live runs on 2026-11-05 (see Results). One guided run built a roofed shelter that passed the first check, which proved too weak to mean a house; the house is now the stricter first-house benchmark (see The first-house benchmark).

## Why
With deepseek-flash, Godling carried blocks about and never built a house. Four 45-minute runs on the same persona
(one that wants a hut) showed why, and the first fixes (keeping what it builds, planning around its current agenda,
laying beams on their supports) took it as far as a wall four courses high with a roof beam on it. It still never once
stood sheltered. What was missing was a definition of a house:
- **Three different ideas of a house, none of them told to the mind.**
  - The world warmed a body with a roof over it and walls at chest height on three sides (`shelterOf`), or with a
    fire close by.
  - The build measure counted cells walled in on every side, roofed if half covered (`structures.py`).
  - The mind was told only "walls around you with a roof over you, or a fire close by, keep the cold off".
- **So DeepSeek made up a house each time:** a ring, a tower, a wall with a beam on top. In run hut4-roof the beam lay
  on two posts three high, with walls north and south: one block in the cell under it was all that kept that from
  being a warm spot. Nothing said so.
- **A house gave nothing a fire did not.** So once dawn ended the cold, the hut stopped mattering, and Godling went
  back to marks and rings.
- **Fire was a riddle.** The mind was told wood rubbed against wood grows hot "and something dry and fine beside it
  may catch". It never made fire in any of these runs.

## Decisions
The user chose each of these.
1. **What a house is.** At first: at least one clear interior cell, where Godling can stand (a block filling the room
   fails it); walls at least two blocks high all round it, but for one doorway Godling can walk through; a roof over
   every interior cell, with more than five units of headroom (the body is exactly five tall). Replaced by the
   first-house benchmark (below), after a shelter that was no house passed it.
2. **House and shelter are two facts.** A house is a structure: a build passes the check or not, wherever Godling
   is. Shelter is what the body feels where it stands (`Sheltered`): "roof", or "enclosed" (a roof with walls on three
   sides, a lean-to); standing inside a finished house is reported apart (`InHouse`). A lean-to keeps the rain off
   long before it is a house.
3. **One check, written once for the mind and the measure.** `mind/godling/house.py` judges a build. The build measure
   counts houses with it, and the mind is told, for each of its builds, that it is a house or what it is short of, in
   concrete words: "the doorway at (0.0, -2.5) is clear, the walls stand two blocks high, but the roof covers only 1
   of the 2 cells inside (none over (0.0, 2.5))". The world has its own copy (`houseAt` in `main.lua`), since only
   the world may say whether Godling is warm; the tests hold the two to the same layouts.
4. **Warmth in tiers, the house best.** The cold (at night, or soaked in the rain) drains health as before (all of it
   in 40 minutes) and stops healing. A roof over the head halves it; a fire within 7 halves it; both together, a
   quarter. Only inside a house is the body warm. A fire used to keep the cold off on its own; now a house is the
   lasting answer.
5. **A house heals.** Inside a house a fed body mends twice as fast (from none to whole in 15 minutes, not 30).
6. **How fire is made is common knowledge, so the mind is told it:** hold the spear and rub it hard against a log
   lying on the ground, with a coconut's dry husk right beside the log for tinder. The wood grows hot after a dozen
   rubs or so, and then the tinder may catch. A fire burns about ten minutes and uses its log up. Rain puts it out,
   and nothing catches in the rain or while the wood is damp after it.
7. **The mind is told the rest as facts of the world** (what a house is, what halves the cold and what keeps it off,
   that a house heals), and feels it: "You are inside a house: warm and dry, mending twice as fast while fed", or
   "You stand under a roof with walls around you, which halves the cold; this is not a house, which would keep it
   off". Walking and waiting say it too. This says what a house is, not how to build one: ADR-004's "no blueprints"
   stands.

## What changed
- `world/main.lua`: `houseAt`, the `house` level of `Sheltered`, a `ByFire` attribute, the cold's pace (`coldHalves`)
  and healing in a house (`houseHeals`).
- `mind/godling/house.py`: the check, `houses` for the measure and `assess` for the mind.
- `mind/godling/structures.py` counts `houses`; the BUILT line leads with them.
- `mind/godling/mind.py`: the house rule, the warmth tiers and how fire is made in the system prompt; the feeling;
  each build's house verdict in "What you have built".
- `mind/godling/skills.py`: walking and waiting say "inside a house, out of the rain and the cold", or that a roof
  only halves the cold.

## Checked
- `mind/tests/test_house.py`: a one-cell hut is a house; without its roof, with a roof over one of two cells, with a
  low wall, with two gaps, with a block filling the room, and with a roof too low (5.0 up) it is not, and each says why.
- `world/tests/test_life.luau`, the same hut in the world script, at night: inside it the body is warm and mends
  twice as fast; with the north wall one block high it is "enclosed" and cold at half pace; a fire close by halves
  that again; out in the open a fire alone halves it.
- Live, in run hp-proj8 (see Results): a one-cell roofed shelter passed this check and the body walked in, but it
  was no house: pillars round one cell with a log over it, open at a corner, with a gap under the roof. The check was
  too weak, and is replaced by the first-house benchmark.

## Fire, made easier (after run hut5-house)
In hut5 Godling made the spear, set a coconut out for tinder and rubbed 30 times: the wood grew hot and smoked, and
nothing caught. The husk lay by the yard, more than 3 from the log, and the report said only "nothing beside it
caught", which read as bad luck. With tinder in place, one try of 30 rubs nearly always lights a fire. The user chose:
1. **Say why it did not catch.** Hot wood with no tinder within 3 of the log says where the nearest coconut lies and
   how far ("no tinder lay within 3 of Log_3 for a spark to catch: the nearest coconut, Coconut_2, is 5.6 away"). With
   a husk close enough, it says the husk only smoulders yet, and to rub on. The body works this out from what it sees;
   the world is unchanged.
2. **Feed a fire.** A log laid against a burning one, loose (not fastened, not carried), takes the fire as the first
   burns out, so one lighting can last the night (a fire lasts ten minutes on a log; a night is about thirteen). A
   fastened log never catches, so a built wall does not burn down.
3. **A roof keeps a fire lit.** Rain puts out a fire in the open, but not one with something solid held in place over
   it. Lighting is unchanged: nothing catches in the rain or on damp wood.

The mind is told 2 and 3 with the rest of how fire works. Tested in `world/tests/test_build.luau` (a log laid end to end
takes the fire for another ten minutes; a fastened one beside it does not; the rain leaves the roofed fire and puts out
the open one) and `mind/tests/test_skills_moves.py` (the three reports).

## One house, kept across plans (after run hut5-house)
In hut5 the plans followed the house rule, but each one started a house afresh: building went up at five sites in 45
minutes, and 20 pieces it had set next to others were picked up again. A plan saw what stood, not what it was for.
1. **The mind chooses a house once.** A reply may carry `"house": {"inside": [[x, z], ...], "door": [x, z]}`. The
   cells inside must touch side by side and the doorway lie beside them (`house.layout`); otherwise it is told why
   and nothing is set. It is kept in memory across plans, meals, weather and failures.
2. **Every plan hears how far it has come, first.** Right under where it stands: the cells and doorway, what is done,
   the next step in the order a builder takes them (walls two blocks high, a clear room and doorway, the roof), and
   what is built so far, by layer (`house.plan`, the same check as before, on the cells it chose).
3. **Its pieces are kept for it.** Pieces in its walls (three layers) and over its room are refused to `pick_up`, as a
   build's are, and left out of the loose things; what fills the room or blocks the doorway is not, so it can be
   cleared.
4. **Moving it needs a reason.** A change that keeps a cell of the old room (more cells, another doorway) is a
   revision. A house elsewhere, or giving it up (`"inside": []`), needs `"why"`: without it the house stays and the
   mind is told so. Every choice, revision, move, refusal and step forward is logged (`kind: "house"`).
5. **A stalled house is named.** After 15 minutes with nothing gained, the plan hears that the next step needs another
   way of doing it.
6. **Walking in is felt.** When the world first says the body stands in a house, it notices: "You are inside a house
   now: warm and dry, and fed you mend twice as fast".
7. **Fire: no rubbing without tinder.** `rub` on a log with no coconut within 3 does not start, and says where the
   nearest one lies (in hut5 it rubbed 30 times with the husk 5 away).

`--no-house-project` turns 1 to 5 off, for the comparison: everything else (the house rule, the fire changes) stays.
Tested in `mind/tests/test_house.py` (the next step at each stage, which pieces are its own, layouts that cannot be a
house) and `mind/tests/test_mind.py` (choose, keep, refuse, revise, move with a reason, give up, the stall notice, a
house that stands, and off).

**One account of the house (after the first project runs, hp-proj1 and hp-proj2).** Twenty minutes in, both were held
up by the older bookkeeping of builds. In proj1 a block lay in the room of its house, but the block was part of a
build it had kept, so the body refused four times to lift it out, while the house said to clear the room; and that
build's own house verdict named a different room, so the mind spent a plan working out which was its house. proj2
moved its house because a log in its doorway was held by such a build. Now what fills a chosen house's room or blocks
its doorway is free to move whatever build holds it, and a build where the house stands says so instead of judging a
house of its own. A point may also be given as `{"x": x, "z": z}`.

**Raise the roof's supports (after the restarted runs, hp-proj5 and hp-proj6; not in those runs' code).** Walls two
blocks high meet the walls' rule, but a roof lying on them leaves exactly the body's height, so it fails the headroom
rule: the walls a roof rests on must stand three high. The next step said only "a roof ... (it rests on walls three
blocks high)", which reads as done once the walls are two high. Now the house finds what its roof rests on (for each
cell inside, the two walls on opposite sides that a log across it reaches, never the doorway), and while those stand
lower than three blocks the next step is "raise the roof's supports to three blocks high (tops at 7.5): (-2.5, 0.0)
stands 5.0, ...". With them up it says where the roof lies and at what height its centre goes (8.75 on flat ground).
Raising a support counts as progress, so the stall notice does not fire while it is being done.

**Walking into a roofed room from a step.** In hp-proj8 Godling laid its roof standing on a step block, then walked
for the room and was told it lay "on top of" the roof: the roof's height was measured from the step, not from the
room's floor. `walk_to` now judges headroom from the floor where it is going, and hops down to it first
(`test_walk_into_a_roofed_room_from_the_step_it_was_roofed_from`). Found in the run, fixed after it.

## Guided construction
The house's next step teaches a way to build, not only what a house is: how high the walls stand, where the roof
pieces lie and at what height, and to set them from a step outside the walls, never in the doorway. That moves this
away from ADR-004's "no blueprints" towards guided construction. It is a deliberate choice: the goal is a simple house
that Godling builds, and without the method no run got past walls two blocks high. It names the parts and heights for
the house the mind chose, not a plan: where the house stands, its size and doorway, the order of the work and what it
is made of stay the mind's. A world with other building goals can keep the definition and drop the guidance
(`--no-house-project` drops both).

## Results (2026-11-05, deepseek-flash, the hut-wanting persona, 45 minutes a run)
Comparison at the same minute, with the house rule and the fire changes in every run:

| run | house kept | build sites | switches between them | own pieces taken back | furthest | house |
|---|---|---|---|---|---|---|
| hp-free1 | no | 5 | 15 | 24 | (none tracked) | no |
| hp-free2 | no | 5 | 17 | 17 | (none tracked) | no |
| hp-proj5 | yes | 2 | 3 | 9 | three of four walls two high | no |
| hp-proj6 | yes | 2 | 3 | 9 | walls two high, room and doorway clear, from minute 9 | no |
| hp-proj7 | yes, with the supports wording | 1 | 0 | 4 | walls and both supports three high, minute 23.5 | no |
| hp-proj8 | yes, with the supports wording | 2 | 3 | 8 | a roofed one-cell shelter, minute 40.3 | no (passed the old check) |

A site is where pieces went up (above the first layer, or stood on end), within 7.5 of its centre; "taken back" is a
piece it set beside another it had set, picked up again. Keeping one house cut switching between sites about five
fold and halved what it took back. With the old roof wording neither run raised its roof's supports: proj6 set a
single block over its room (it fell), put steps in its own doorway, and fastened a block hanging in its room;
proj5 tried to set the roof from the ground, out of reach. With the supports wording both runs raised them.

hp-proj8, a roofed shelter, not a house: walls at minute 2, the supports step at 4; a block tried early as a roof
fell into the room and was fastened there, so at 19 it moved one cell over, giving that reason; supports and roof step
at 32; at 40.3 it stood on a block outside the corner and laid a log across the supports at 8.75 ("came to rest
across Block_9 and Log_7"). The old check passed, the 5-minute measure counted it at 40.8 and at the end, and at 41.8
it walked in: "You are inside a house now". Its first try to walk in, from the step, failed on the body bug above.
What stood was no house. Round the one cell inside (top of each cell; north up):

```
        x: -92.5   -90.0   -87.5
z -30.0     2.5    10.0      .      NW one block; N support three blocks with the roof log on it; NE corner empty
z -32.5     5.0   [room]     D      W wall two blocks; the room, 2.5 x 2.5; the doorway
z -35.0     5.0    10.0     2.5     SW two blocks; S support one upright log; SE one block
```

A nook as wide as the body, between pillars, open at a corner, with a 2.5-high gap between the west wall and the roof,
under one log 2.5 wide. From outside it reads as a lintel on two posts. It showed that Godling can follow the roof
method and that a roofed shelter can be walked into; the check that called it a house only asked for something two
blocks high on each of the room's four sides.

hp-proj7 did everything the wording said up to the roof (walls and both supports at 23.5, and the step it would use
set outside a corner, not in the doorway), then for 21 minutes could not get to its own house: five walks to the
room ended "the way is closed off by Block_4, Block_7, Block_8, Stone_5...", its own loose pieces round the site.

Fire: proj5 made fire (22 rubs) and proj1 did in its first try (15); the tinder check refused three rubs with no
coconut beside the log. Cost about $0.60 a run; with the runs restarted after the fixes above, about $4.30 in all.

## What still fails (for a body-level reproduction before more full runs)
- A piece set where nothing holds it falls into the room, and the mind then fastens it there (proj6 and proj8). The
  room is lost until a hammer knocks it loose; both moved their house rather than do that.
- Its own loose pieces close off the way to the house (proj7, 21 minutes), and walks and reaches stop short of
  pieces in the clutter: 8 to 18 times a run.
- Steps set in the doorway: proj6 three times, proj8 twice (it cleared them). The wording now says to set the step
  beside the supports; the body does not stop a doorway being filled.

## The first-house benchmark (replaces the first check)
proj8's shelter showed the first check was too weak: something two blocks high on each of a room's four sides, and a
roof over the room, let a nook between pillars count. The user set the target a house must meet:
- **A room at least two by two cells** (5 by 5), clear to stand in, on one walkable floor.
- **Walls all round it, corners too**, each filled from the floor up to the roof's underside without a gap.
- **One doorway, on a side** (never a corner), open from the floor up to the roof, onto open ground outside.
- **A roof over the whole footprint**, the walls and doorway too, its underside more than five above the room's
  floor. The body is exactly five tall and the grid is 2.5, so that is three blocks up: walls three high, the roof on
  them, the doorway open three high under a lintel.
- **Standing after it settles, and Godling walks in.**

One check, three copies held to the same layouts: `house.py` (the mind's next step and verdicts, and the build
measure's `houses`) and `houseAt` in `main.lua` (whether the body stands in a house). A doorway clear to the roof with
the roof over it is as clear and as roofed as the room, so a clear cell sticking out of the room between two walls,
leading out, is taken as the doorway, not the room. The world now reports shelter and the house apart: `Sheltered`
says what is over and round the body ("", "roof", "enclosed"), which still halves the cold while a house is being
built; `InHouse` says it stands inside a finished house, which alone keeps it warm; and the world log says `HOUSE`
each time the body walks into one. The mind hears the new rule, the next step names each wall short of three blocks,
then where the roof pieces go, and the pieces in place at the chosen house are logged as they change
(`kind: "house", phase: "installed"`), so a run can be measured by the work that stays, not only by time.

A log is three cells long and a room two cells wide is four from wall to wall, so no log reaches across it. The roof
over the room is logs centred on the walls, each resting on its middle and reaching one cell in, with a log over the
doorway resting on the walls either side.

**Checked by hand before any paid run.** The house was set into hp-proj8's island beside proj8's shelter, loose, and
left to the world's physics (`make_bench.py`, `bench_probe.py` in the session's scratch tools):
- All 41 pieces (33 in the walls, 8 in the roof) settled in their cells: the logs balanced on the walls held.
- The mind's check and the build measure count one house there (4 cells, the doorway at (-95, -50), the roof's
  underside 7.49 up), and not proj8's shelter, which they say is a room of one cell whose walls do not reach the roof
  at five cells, with no roof over its doorway.
- Godling walked in by the doorway: the world said `InHouse` true (`Sheltered` "roof" by the doorway, "enclosed" in
  the far corner) and logged "HOUSE Godling stands inside a house at (-94.9, -47.9)"; out again, false. In proj8's
  shelter it said false, with `Sheltered` "enclosed".
- Tested in `mind/tests/test_house.py` (the house; proj8's shelter as it stood; a corner short, a wall short of the
  roof, a wall without the roof on it, a second opening, a blocked way out, a block in the room, no roof, a roof too
  low; the next step at each stage; layouts that cannot be a house) and `world/tests/test_life.luau` (in the house at
  night the body is warm and mends twice as fast; with a corner a block short it is under a roof, cold at half pace;
  the one-cell shelter is "enclosed" and no house).

**Found while checking it, and fixed: reaching into a room two cells wide.** `pick_up` tried four rings round the
block for a spot to stand on. In a room 5 by 5 with a block in one cell, every ring crosses a wall or the block,
though the free cells round it fit the body (two units wide) with a quarter unit to spare each side; so it said "no
clear spot to reach". Now, when the rings find nothing, every spot within reach is tried on a quarter-unit grid from
the block (the grid pieces settle on, so cell centres are on it), with the clearance kept anywhere: the body's
radius and `STAND_MARGIN` (0.2) from loose pieces, `WALL_CLEARANCE` (1.6) from rock; the roomiest spot is taken.
Both searches also require a straight reach to the target through nothing two blocks high, so the hands never take
a piece through a wall (they still reach over a block lying on the floor). A block in the cell just inside the
doorway closes the way in (the walls either side of the doorway meet it corner to corner): it is taken from the
doorway.

Reproduced first (`mind/tests/test_house_recovery.py`, for each of the four cells inside): walk in by the doorway,
pick the block up, carry it out and set it down, walk back in, and the house is whole again, with the body's whole
width clear of every wall and of the block where it lay. Three of the four failed before the fix. Then the same in
the real example world, one world per cell (`make_fallen.py`, `bench_recover.py`): each block settled in its cell
and the check said "clear the room"; each was picked up (from the doorway for the cell just inside it, from inside
for the rest), carried out and set down; Godling walked back in, the world said `InHouse` and logged `HOUSE`, and the
check counted the house. The body stood 1.19 to 1.25 from the nearest piece as it took the block: where it came to
rest, a few hundredths off the spot it chose, still 0.19 or more beyond its own radius.

**Does Godling notice a fallen block and clear it itself? (run hp-recover1, 2026-11-05).** One short paid trial
(deepseek-flash, the hut persona, at most 12 minutes and $0.25, stopped a minute after success). The settled
benchmark house with one block lying loose in its far cell, (-92.5, -45); the house already chosen in Godling's
memory, as a reply would have stored it, and nothing else remembered. It was told only what every plan is told: the
house's line, "Done: the walls stand three blocks high all round, the doorway ... is open up to the roof, the roof is
over the room, the roof covers the walls and the doorway. Next: clear the room: (-92.5, -45.0) (Block_48 fills it)",
and nothing more about the block. It succeeded, in 1.6 minutes and $0.012:
- Noticed it in its first plan (0.75 min): "the only thing stopping the house being a house is Block_48 sitting in
  the room"; the first project, "the house room clear and standable".
- Chose an effective way: pick it up, walk out by the doorway, set it down at (-97.5, -55): outside the footprint and
  clear of the doorway and the cell before it.
- Carried it out: picked up at 0.81 min, set down at 0.88; the house check passed (`built`).
- Came back: its next plan, made while the first ran ("once Block_48 is out I can stand inside at last"), walked it
  in at 1.63 min, and the world said it stood in a house.
After that it meant to "lay one log in the hearth" inside the room: the log, three cells long, did not fit the room
two cells wide and was set down outside, so the room stayed clear. A fire inside the house would fill a cell of the
room and undo the house; the full construction trial is where that shows, if anywhere.

## The first full construction trial against the benchmark (run hp-full2, 2026-11-05)
A fresh island; the house project with the benchmark and its guidance; the body able to reach into the room;
deepseek-flash and the hut persona; at most 90 minutes and $1.50. It ran the 90 minutes ($0.48, 375 model calls) and
built no house.
- **The house it chose held all run** (2.1 min: a room two by two at (-100..-97.5, -37.5..-35), the doorway west),
  never moved, and the pieces installed and kept at it rose without a loss for the first 71 minutes: 13 at 11 min,
  27 at 28, 37 at 38, 44 at 71. The walls reached three blocks all round, corners and both doorway flanks too, by
  38 min; the roof covered 13 of the 16 cells of the footprint by the end, its stones set on the wall tops from steps
  it put down outside the walls, and one log laid along the north wall reaching into the room.
- **What stopped it: three pieces its own hands-full reflex set down in the house.** To free its hands, picking up
  the next thing, the body sets what it holds on clear floor beside it, and nothing kept the house's room, doorway or
  way out from being that floor: Stone_52 into room cell (-100, -35) at 53.7 min, Stone_41 into (-100, -37.5) at
  57.3, Log_7 into the room and doorway at 61.5.
  - Stone_52: noticed ("the room still has Stone_52 in it"), picked up and set down outside the footprint and the
    entrance at 69.8 min. Recovered.
  - Log_7: noticed ("Log_7 was the thing wedging my doorway shut") and picked up at 71.5 min, then laid again as
    the lintel turned the wrong way, across the doorway from outside into the room (east to west, where the
    doorway's wall runs north to south), so nothing held it up: it fell, leaning through the way out, the doorway
    and a cell of the room. An ineffective action: the guidance said "a log along the wall resting on the walls
    either side", without the axis or the two walls.
  - Stone_41: noticed and chosen in every plan from 59.5 min ("Clear the room first"), and tried twice, at 75.6 and
    80.0 min; both failed in execution: "no way round: the way ... is closed off": Log_7 shut the only way in.
- **Where the time went** (from the recording: the body's track, ten samples a second, split by what it did; 88.7
  minutes accounted): waiting for its next plan 25.1 min (28%: plans took about 57 to 83 s while it built the walls,
  117 to 136 s from 40 min, when the roof work began, and in the last 50 minutes the body stood waiting 23 of them);
  walking with a piece to the house 15.8 (18%); picking up a tool 13.6 (15%), of which 10.2 walking back to it
  (2,759 units: the hammer lies where the last stone was taken up, at the quarry) and 3.4 handling (about 3 s each,
  73 times); picking up a piece 11.0 (12%); quarry strikes 5.0 (6%, 61 stones broken off for 44 pieces kept);
  setting pieces 4.2 (5%). Quarrying several stones a hammer session would save the handling, two or three minutes;
  carrying one stone at a time keeps the walk back each time.

What it needs next, before another full trial: the guidance to name each roof log's axis and what it rests on (the
lintel: the two wall cells beside the opening; a log over the room: the wall cell it is centred on and the cell it
reaches in over), and the hands-full reflex to keep what it sets down out of the chosen house's room, doorway and
way out.

## The two causes fixed, each reproduced first, then checked together in a real world
**The hands-full reflex keeps the house clear.** To free its hands the body sets what it holds on clear floor beside
it. It now passes over any spot where the whole of the piece, as it would lie (a log three cells long, either way
round), covers the chosen house's room, doorway or way out (`memory.reserved_cells`), before choosing the spots to
try; with no safe spot in reach it keeps hold and says the house's cells were kept clear. Reproduced on a site with
no other floor near (`test_house_recovery.py`): before, a stone and a log, from the doorway, the room and its far
corner, went into the house all six times; after, five went beyond the way out and the sixth stayed in hand.

**The roof's next step names each log's axis and what it rests on** (`house.roof_layout`): the lintel first, a log
along the wall centred on the doorway, resting on the two wall cells beside it, with any stone already capping them
named as in the way and free to lift off, from a step; then over each cell of the room a log centred on a wall beside
it (not the doorway, not the lintel's walls), along the line to the cell, resting on its middle and reaching in over
it; then a block on the walls left over. Reproduced first: with the flanks capped the lintel laid along the wall was
refused for room, and laid across the doorway it rested on nothing and fell into it, as in hp-full2; as the step now
says, the caps lifted off and the lintel rested across its two walls with the doorway open; and a log over the room,
laid on its named wall, covered its named cell.

**Both together, in the real world** (`make_roofcheck.py`, `bench_roofcheck.py`): the benchmark house with its
lintel gone, both flank walls capped, the log over the far cell gone, a stone fallen in the room and clutter round
it, as hp-full2 left its house. In order: the caps lifted off from steps; the stone picked up in the room, and, the
lintel log taken up with the stone still in hand, the reflex set the stone down outside the room, doorway and way out
(as it did the two caps); the lintel laid along x came to rest across its two flank walls; the log over the far cell,
centred on its bearing wall, came to rest on it. The check then said "none: it is a house", and Godling walked in:
`InHouse` true, the house counted. Two body troubles were seen on the way, and are not fixed here: stepping up onto a
block to reach the roof snagged once (the place came good on the next try), and walking from one step straight onto
another as high, the body walks off the first and stays on the ground beside the second.

**Steps for reaching high, fixed (each reproduced first, in `tests/test_skills_moves.py`).** Seen while checking
the roof fixes in the real world:
- From up on one block to the top of another as high, with ground between, the body walked off the first and stayed
  on the ground beside the second. Now it steps down first and walks on from the ground, stepping up at the end.
- Stepping up to set the roof's last log, it tried two steps nearest first, judged reach from the edge of a step
  rather than where the body stands on it, and gave up after a snag. A step one cell across now has to reach from its
  middle, and leave the whole body clear of the piece being set (the world refused one place: "that space is taken by
  ... your own body", the head meeting the roof's underside); the body shuffles to the middle if it lands off it; up
  to four steps are tried, each twice if the step-up itself fails.
- It aimed to step up onto a block with a stone standing on it, at the end of a row it was coming along, and snagged
  on the row. The top a step-up counts now stops where something stands on it, and a block one cell across whose
  foot on the way is buried is come at from a side with clear floor.
In the real example world, fresh, with the body choosing its own steps: it walked from step to step, lifted both
caps, cleared the room, laid the lintel and the log over the far cell (snagging once on the way to its step, and
going up on the next try), and walked in: `InHouse`, the house counted.

## Review corrections

Missing or uneven terrain now produces a site verdict that leaves the mind able to plan again. The world and the
Python check require continuous, settled, grid-aligned material across each wall and roof cell. Their regression
layouts include sparse walls, tilted and moving material, fractional roof heights, missing ground and terrain seams.

Guided projects validate that every interior cell has a separate perimeter bearing for the current roof method.
The complete planned roof footprints must also be disjoint, including the lintel, inward beams and wall caps.
Unsupported layouts receive an explanation before construction begins; saved incomplete layouts request revision.
General recognition still accepts completed larger houses, up to 64 interior cells.

Ownership updates after each placement, including nested learned moves and gifted stacking. Accepted placements
remain recorded when attention interrupts settling. Temporary deposits to free the hands use the whole object's
footprint, including small tools and coconuts, and stay separate from installed work. Routing keeps valid paths
across connected platforms before attempting a descent.

Established builds survive trimming the material history. Disabling the house project releases its runtime
ownership while preserving the saved project. House feedback and build-damage notices use observed geometry;
hidden changes are learned when Godling revisits, and the construction observations persist across restarts.

## Second review (2026-11-05)

- **A cap on a room log's bearing wall is in the way, like one on the lintel's walls.** While a room cell is bare,
  whatever sits at the roof on the wall its log rests on, or beyond it where the log's outer end goes, is named in
  the next step ("first take ... off the top of ...: the log over ... rests there") and is free to lift. Before, it
  was kept as the house's own, so the body refused to lift it and the world refused the log: in a 2x2 room the two
  cells beside the doorway have one bearing wall each, so one stone set there first left the house unfinishable.
- **A fire takes on only a log lying loose beside it.** Fuel must lie on the burning log's floor and hold nothing
  up. A log in a wall's bottom course, a lintel or a roof beam, fastened or not, never catches, so a hearth by the
  house can't burn it down.
- **A log laid on a burning one is no roof over it.** The rain check skips anything resting directly on the log.
- **A revised house is measured afresh.** Changing the room or the doorway on the same site resets its best score,
  which was scored against the old layout. Before, a lower-scoring revision never logged progress, and the plan was
  soon told the house had stalled.
- The house line says "Last observed" only when there are pieces to have observed. The body names the house with
  `house.at`, the same as the mind. The close stand-point search reaches only as far as the hands do at the
  target's height. The world logs `HOUSE` each time the body walks into a house, as this record now says.
