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
