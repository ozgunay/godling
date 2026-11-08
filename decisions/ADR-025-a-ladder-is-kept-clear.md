# ADR-025: A standing ladder is the way up: the hands keep its top and its foot clear

Date: 2026-11-08. Status: built and tested in the mind's and the world's suites. Not yet tested in a live run.

## Why
On 2026-11-08 Godling set a stone on top of the ladder it was using to raise its walls. After that it could not build
on there. There is no log of that run on disk, so this account comes from the screenshot and the code:
- A ladder that has been set up stands fixed in place (`main.lua`, Anchored), so the world lets a piece rest on its top.
- `place_at` only checked that the piece overlapped nothing. A stone aimed just above the ladder's top passed that
  check, and the body reported success: "Stone_1 came to rest at (2.50, 8.79, 0.00), on top of Ladder_1".
  `test_skills_ladder.py` gets exactly that report from the code before this change.
- The body contradicted itself. Its walking and floors already left ladders out (`Snapshot.standables`): a ladder
  was never something to stand or build on. But its hands let a stone sit on one.

## Decision (the user's, 2026-11-08)
**A check in the body. Not something Godling must learn, and not a rule in the prompt.** This is the same kind of
check as the existing refusals for an occupied spot or the house's reserved cells (ADR-019). The hands refuse, and say
why. The mind still decides where to build. Learning was set aside for four reasons:
- It is a trap. The ladder, which is the way back up to the stone, is the very thing that is blocked.
- Cause and effect are minutes apart, and the later failures name reach or the climb, not the stone.
- There is one right answer. Learning pays off where several answers are fine, such as where to build, in what order,
  and from what. Those stay the mind's (ADR-004).
- ADR-019 showed deepseek-flash, across runs, not learning to keep steps out of its doorway or not to fasten a
  fallen block in its room.

This is how games handle it: placement keeps free the spot an object is used from, as RimWorld does with a
workbench's interaction spot. It is a rule about the body, not a building method, so it does not move further toward
guided construction.

## What a standing ladder keeps clear
A ladder counts as standing when it is set up: 7.5 tall, and not in the hands.
1. **The ladder itself, and the space just over its top.** This covers its footprint from its foot up to one block
   above its top, where the climber's head goes. A piece aimed into it is refused: "(2.5, 8.8, 0.0) is on top of
   Ladder_1: anything there closes the way up it. Set it a cell further off, or move the ladder first". If the piece
   would overlap the ladder, the message says "where Ladder_1 stands".
2. **Its foot, on the side it is climbed from.** That is the low side, away from what the ladder reaches the top of,
   found as the world's climb finds it: something to step onto 1.5 or 2.2 out on the far side. The foot covers 2.45
   out from the ladder's middle, which is the room the world needs to step the body off when it climbs down (1.5 out,
   1.9 wide: `climb`, `bodyFits`). It is a body wide (2.0) across, and as high as the body (5.0). If the ladder stands
   pressed against a wall, this reaches into the next cell out by 0.15. In the world, that is enough to stop the climb
   down.
3. **What the rule leaves alone:**
   - **The landing at its top.** A wall may rise past the ladder's top, and a roof is laid on the supports there.
     Both are ordinary building.
   - **A ladder against nothing** keeps only its top, since nobody climbs it.
   - **A ladder lying on the ground** is only a thing lying there.
   - **Things lower than a step (0.45)**, which the legs step over.
   - **The reflex that lifts a piece aside to get out of a pen**, because it puts the piece back where it was.
   - **`stack_on`**, a ready-made skill offered only with `--gifted-skills` (the comparison arm). It adds to a stack
     that is already there, so it is not checked.

`put_down` and `place_at` both check this before the body walks anywhere. Freeing the hands to pick something else up
goes through `put_down`, so that reflex passes over a ladder's foot as well. The mind is told this as a fact about its
body: "your hands set nothing on a standing ladder or at its foot, since that would close the way up it".

## The way out of what is already there
The world already wakes whatever rests on a piece when that piece is picked up (`wakeRestingOn`), and a ladder is no
exception. Lift the ladder and the stone on it falls. Ladders are not building pieces (`structures.PIECE_PREFIXES`),
so no build or house holds one, and the body may pick it up. A piece lying on a ladder is out of reach from the
ground: its centre is 6.2 above the body's, and the reach is 6.0. When the mind tries to pick it up anyway, the
refusal now says what to do: "no clear spot to reach Stone_1 from here (it lies on top of Ladder_1: pick up the ladder
and it falls)".

## Checked
- `mind/tests/test_skills_ladder.py`, the screenshot as a test: a wall three blocks high, with a ladder against it.
  - A stone on its top, or one block over its top, is refused, with no walk and no Place sent.
  - The wall behind the ladder rises past its top, set from a step beside the ladder.
  - At its foot, two cells out, a stone is refused by `put_down` and by `place_at`. Beside the ladder, and a cell
    further out, are fine.
  - A ladder against nothing keeps only its top, and one lying down keeps nothing.
  - A ladder whose rungs face north and south gets the same check.
  - Freeing the hands passes over the foot.
  - A stone already lying on a ladder gets the hint, and the ladder can be picked up.

  Run against the body code from before this change, all of these tests fail. The first one gets the success report
  quoted under Why.
- `world/tests/test_build.luau`: picking up a set-up ladder unanchors a stone settled on its top.
- Every suite passes: the mind and the tools (pytest), and the world script.

## Not checked
- Not yet in a live run.
- Which failure exactly followed the stone on the ladder ("it can't put any stones near"), because no log of that run
  is on disk. Whether a stone on the ladder's top stops the climb up depends on how close the ladder stands to the
  wall. Pressed against the wall, the step-off spot on the wall's top stays clear of the stone. Standing at the middle
  of the cell in front, the world's room check for the body there meets the stone. The failures could equally have
  come from reach, and from finding somewhere to stand around the ladder.
