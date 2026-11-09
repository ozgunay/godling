# ADR-004: Real building: materials, mechanics and physics

Date: 2026-11-01. Status: decided and built the same day. See "What was built" at the end. Only the structure counter is still open.

## Why
- You want Godling to build real structures (walls, houses, bridges, log cabins), not single-column towers.
- Today it has one material, a 0.75 cube, and one way to build: put a cube on something. Every piece is placed at angle 0, nothing can be joined, and the body cannot stand on anything it built.
- So towers and rows are the only stable things it can make. Its own reasoning keeps hitting that ceiling, for example when it tried a staircase to get higher.

## What the engine (Clawblox) gives us
- **Shapes:** block, ball, cylinder, wedge and ring.
- **Physics per part:** weight (density), friction and bounce.
- **Joining:** `Weld` / `WeldConstraint`, which joins parts into one rigid body. There are no hinges, ropes or springs.
- **Placing:** the world's `Place` action already takes a rotation; the body always sends 0.
- **The world:** gravity is 10. Tree, log and axe models exist already (art session).

## Decisions (my recommendation first)
1. **Materials.** Godling learns from what each material does; none of them comes with instructions.
   - **Bricks:** 1.5 x 0.75 x 0.75 stone, heavy and grippy. Long pieces can overlap like real masonry, so a wall of staggered bricks holds together where a stack of cubes topples.
   - **Logs from trees:**
     - Godling picks up the axe and chops a tree: a few strokes of about 1.5 s each, with the PickUp-style animation.
     - The tree falls into 2 logs (cylinders 0.5 x 3.0, light wood) and leaves a stump that regrows in about 10 minutes, so the island never runs out.
     - Logs are beams: they span gaps, sit across door openings, and make log-cabin walls and roofs.
   - **Boulders:** 1.5–2 units, very heavy, for foundations and anchors. *Choose:* Godling can carry one at half walking speed (recommended), or only push it.
   - **More supply:**
     - Raise the threshold from "fewer than 6 loose cubes" to fewer than 12 pieces.
     - Drop a mix of cubes and bricks, with a boulder now and then.
2. **Mechanics.**
   - **Turn when placing:** `place_at` takes an optional turn (0 or 90 degrees, and for logs, lying or standing). Walls can then run in both directions and beams can cross.
   - **Fasten:** a new body move that welds the last-placed piece to everything it touches, like pegs or mortar. *Choose:*
     - (a) it costs time, about 3 s (recommended);
     - (b) it costs time and a peg cut from a log;
     - (c) no fastening at all, pure dry stacking.

     Fastened work stands up to bumps and lets beams and overhangs hold.
   - **Honest physics per material:** wood is light, stone heavy and grippy, cubes as now. The same placement behaves differently by material, which is something to learn.
   - **Standing on its own work:** the body can step up one block (0.75) and walk on flat tops it built. Stairs, platforms and upper floors then become reachable.
     - This needs a test first: whether the character controller steps up that far, and how the router plans across its own structures.
3. **No blueprints.** The mind is told only the new materials and moves, in one line each under "Your body's moves". How to build walls, roofs or bridges stays for it to work out (your "learns by itself" rule).
4. **Measure structures, not towers.** Count, per run and per hour:
   - walls: 3 or more pieces in a line, 2 or more high;
   - enclosures: walls on 3 or more sides of a space;
   - spans: a piece resting on two supports with a gap under it;
   - roofs: spans over an enclosure;
   - what is fastened, and what fell.

   These replace "tallest stack" as the headline numbers when comparing the memory arms.

## Order (each phase ends with a 10-minute smoke of two arms, then goes into the next night run)
- **Phase 1:**
  - turning on place;
  - bricks, and the bigger mixed supply;
  - fasten;
  - per-material physics;
  - the structure counter.
- **Phase 2:**
  - the axe;
  - chopping trees into logs;
  - trees regrowing.

  The art session already has the log and axe models and offered to do the chopping visuals.
- **Phase 3:**
  - stepping up and walking on its own structures;
  - boulders.

## Cost and risk
- Thinking cost should stay about the same: the same number of decisions, with a few more moves to choose from.
- Risk: more choice may mean more failed experiments at first. The structure counter will show whether real structures appear and keep appearing over hours.
- Fastening can make piles of junk permanent. Phase 1 will show whether to add a way to unfasten.

## What was built (your decisions, 2026-11-01)
You chose:
- quarrying with a hammer, rather than sky drops or clay and a kiln;
- a ladder for height, rather than a hop-and-stairs rule;
- all the building physics and mechanics at once;
- telling the mind only the basics.

**World** (`C:\Work\godling\world`, details in its README):
- the quarry and hammer, with stones and bricks by turns, every 3 strikes;
- the axe: 4 strikes fell a tree into 2 logs, and the stump regrows in 10 minutes (one log since ADR-026);
- placing with a quarter turn or stood on end;
- fastening with welds, and a hammer knocks a piece loose;
- a ladder that stands up when set down, with world-driven climbing up and back down;
- boulders, which halve the walking pace while carried;
- a person's hop instead of the 6.6-unit leap;
- the sky supply turned off;
- tools, ladder and boulders return home if lost in the sea.

**Body** (`godling/skills.py`, `godling/world.py`):
- new moves: `strike(object)`, `fasten(object)` and `climb(object)`;
- `place_at` and `put_down` take optional `turn` (0/90) and `upright`;
- objects report their real, rotated extent, because observations carry each part's rotation matrix;
- the body stands and plans on whatever floor it is on (ground, mesa top or its own platform), and the router keeps it on that floor;
- walking off a raised floor is refused ("you would have to climb down");
- `nearest_free` takes "cube", "brick", "stone", "log" or "boulder".

**Mind** (`godling/mind.py`): five short sentences under "What your body knows about itself":
- the legs take only low steps, but a ladder can be climbed;
- what can be built with: stones and bricks from the quarry with a hammer, logs from trees with an axe, and boulders;
- that pieces can be turned, stood on end and fastened.

How to build is left for it to discover.

**Art** (from the art session): models for the hammer, quarry, stone, brick and ladder, and Strike and Climb clips. The boulder and stump models are requested.

**Tested live with the real body skills:**
- quarrying: Stone_1, then Brick_2;
- felling Tree_1 into 2 logs;
- a brick stood on end and a log turned 90°;
- fastening, refusing to pick up the fastened stone, and knocking it loose;
- the ladder set up against LowStep: climbing up (0 → 2.0), walking on top, being refused at LargeMesa and at the drop, climbing down;
- the boulder carried at half pace;
- the hop rises about 0.7.

**First smoke with the mind** (j, 10 min, native and native2): it found and used every mechanic from the basics alone.

| | native | native2 |
|---|---|---|
| trees felled | 2 | 1 |
| stones quarried | 1 | 1 |
| pieces stood upright (log posts) | 7 | – |
| fastenings | 12 | 8 |
| ladder set up / successful climbs | 1 / 4 (onto LowStep, height 2) | 1 / 2 |

- It taught itself skills such as `fell_tree`, `stand_log_post`, `build_on_lowstep` and `quarry_run`.
- Projects finished fell to 44–53%, from about 85% before building. That is exploring: felling before there is an axe in hand, fastening its own blocks and then trying to lift them, getting stuck walking.
- Body busy 57–66%, moving 33–38%, cost $0.46–0.48/h.

**Structure counter** (`godling/structures.py`, built 2026-11-01 evening). Building pieces are laid on cells a stone wide (0.75) and measured from the terrain under each cell:
- *walls:* straight runs of at least 3 cells that are at least 2 layers high and made of at least 3 pieces;
- *enclosures:* walled-in space, where a gap one cell wide counts as a doorway;
- *roofed:* an enclosure at least half covered 2 or more layers up;
- *spans:* a long piece lying on its two ends with at least 0.6 of gap under its middle;
- *posts:* long pieces stood on end;
- *floors:* flat tops at least 2 layers up, at least 4 cells and 2 pieces;
- *the largest group of touching pieces;*
- *fastened pieces;*
- *tallest stack, and highest built point.*

Recording and testing:
- The runner records every piece's box and the measures every 5 minutes and at the end, in `mind/structures.jsonl`, with the terrain in `mind/terrain.json`. Old runs can therefore be measured again.
- `compare_runs.py` shows what stands at the end, plus "pieces built in, by hour".
- Tested on hand-made structures: a hut with and without a door and roof, a log bridge, a brick post, a raised floor, a one-layer row, a lone boulder and a palisade. All 9 checks are right.

**Material and safety for long runs** (checked before the first night run):
- *Amount.* The quarry never runs out, and trees regrow every 10 minutes (up to about 96 logs an hour).
- *New pieces spawn at a free spot* along the quarry face, or higher so they drop onto the pile. They are never forced inside another piece, which made the physics fling pieces before. Tested with 4 stones in a row.
- *Hopping down.* Godling can hop down any drop of 2.6 or less, so it cannot strand itself on a platform. When something it wants is below it (to pick up, strike or fasten), it hops down first. Higher drops still need the ladder.
- *Getting stuck.* A walk that gets stuck looks again and tries another way once before giving up.
- *Starting blocks.* The world drops its 12 starting blocks from the sky. The mind now waits 3 s after joining, so its first look no longer sees "floating stone".

**Smoke k** (10 min, recorded with the counter, re-measured with the corrected one): one arm built a 10-piece stack 7.5 high and a post. The other fastened 12 pieces and stood up 2 posts. There were no walls or enclosures yet; the night run is the real test.
