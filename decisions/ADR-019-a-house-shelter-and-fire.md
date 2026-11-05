# ADR-019: A house: one definition for the world, the mind and the measure; warmth in tiers; how fire is made

Date: 2026-11-04. Status: built, tested in the simulated island and the world script. Live run pending.

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
1. **What a house is.** At least one clear interior cell, where Godling can stand (a block filling the room fails
   it). Walls at least two blocks high all round it, but for one doorway Godling can walk through. A roof over every
   interior cell, with more than five units of headroom (the body is exactly five tall).
2. **House and shelter are two facts.** A house is a structure: a build passes the check or not, wherever Godling
   is. Shelter is what the body feels where it stands (`Sheltered`): "roof", "enclosed" (a roof with walls on three
   sides, a lean-to) or "house" (standing in a house's interior). A lean-to keeps the rain off long before it is a
   house.
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
- Not yet: Godling building one and walking in. That is the live run's to show: the geometry passing the check, and
  the body walking in by the doorway and feeling "house".

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
