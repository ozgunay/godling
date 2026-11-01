# ADR-005: Minecraft-scale building blocks on a grid

Date: 2026-11-01 (evening). Status: decided by you and built.

## Why
- Godling's body is 2 x 5 x 2. The building block was 0.75: a sixth of its height.
- At that size, a wall it can't see over needs 7 layers, and a small room about 100 stones. Each stone costs 3 hammer strikes and a carry, so in practice it built stacks, not houses.
- In Minecraft a block is about half the player's height, and a house takes 40–60 blocks.
- Free placement also left walls ragged and stacks wobbling.

## Decisions (yours)
1. **Blocks are 2.5 on every side.** Godling is 2 blocks tall, a one-block doorway (2.5) fits its 2-wide body, and a house is about 40–60 blocks.
2. **Placed blocks and logs snap to a grid.** Their x and z round to the nearest 2.5 cell. Height is as aimed, then physics settles the piece; fastening still holds it.
3. **The night run uses Hindsight only.** In the 5-hour m2 run (old world), Hindsight finished the most projects (69%, rising) and moved the most, at about twice native's cost.

## What changed
**World** (`C:\Work\godling\world\main.lua`):
- `BLOCK_SIZE` 2.5, with `GRID` the same. Blocks and logs snap in `placeBlock`.
- Blocks are stone-heavy; the light upstream blocks were easy for the body to shove off a stack.
- The 12 starting blocks lie flat on grid cells (4 x 3) instead of tumbling from the sky.
- Logs are beams three blocks long (7.5 x 1.25). The ladder is three blocks tall (7.5), and climbing steps off 1.5 from its centre to clear the 2-wide body.
- The quarry is 10 x 6 x 8, the boulders 2.6 across, and a held block floats 4.0 above the body centre (was 3.5).
- The quarry makes stone blocks only. A long brick (2 blocks) cannot bridge a doorway the way a 3-block log can.
- The thrown rock no longer spawns blocks: they would be free, huge, and spawn into each other.

**Body** (`godling/world.py`, `godling/skills.py`):
- `CUBE` 2.5 and `grid()`, mirroring the world's snap, so the body plans for the cell a piece will land in.
- Stack detection, the hold height, the ladder height, the set-down reflex spacing, the knocked-away distance and the "keep" grouping radius are all rescaled.
- To reach for a long beam or ladder, the body stands beside its middle; before, it planned from the longest side and could not reach at all.

**Counter** (`godling/structures.py`): cells and layers are now a block. Spans need a beam at least about 2 blocks long over a gap of at least 2.0; posts are at least about 2 blocks tall. The known-answer test passes at the new scale (9 of 9).

**Mind** (basic facts only):
- Godling is 2 by 5.
- A block is 2.5 and things settle into a grid of 2.5.
- Logs are beams three blocks long; the ladder is three blocks tall.
- It can hop down one block.

## Tested live
- A quarried stone is a 2.5 block.
- Set down at (10.3, -10.2), a block lands at (10, -10). A second block placed off the grid lands exactly on top.
- The ladder was picked up and set against the 2-block stack. Godling climbed onto the top block (height 5.0) and back down.
- Felling gives 7.5 beams.
- No world errors. The flat starting blocks count as no wall and no floor.

## Fixed after the first night run (n, stopped after 9 minutes)
The world broke within minutes: the pieces fell 5 units, a log rolled about on the ground, and Godling was gone.
- **The island sank.** Fastening welded blocks to `GroundCenter`, which is anchored, and the engine then moved the ground with them. Godling fell off the edge into the sea.
  - Fix: fastening never welds to a fixed part. A piece that touches anything fixed is pinned in place; otherwise it is welded to the loose pieces it touches. A hammer strike unpins it.
- **The log rolled.** Round logs rolled off whatever they were set on. Logs are now square beams.
- **The body said a bridged beam was "not resting on anything".** It looked only below the beam's centre, which is the gap. It now checks the whole underside and reports "across Block_2 and Block_4". Otherwise the mind would have learned that lintels and bridges don't work.
- **The body snagged on block corners.** Routes kept a circle of clearance round each piece; at block scale that clips the corners. Clearance is now a box.

Tested live: a gate (two 2-block legs one cell apart, a beam across, all fastened).
- The ground did not move.
- The beam lay flat across both legs and the counter saw a span.
- The body walked round the gate to the hammer.
- Knocked loose, the beam stayed on the legs.
- No world errors.

The night run restarted as **n2** (Hindsight, 8 hours).

Found while testing: the body is 5 tall and a 2-block opening is 5.0, so Godling cannot walk under a 2-block lintel. A doorway needs 3 blocks. The mind is not told; it is the kind of thing it should find out.

## Not built (possible next)
- Climbing one block without a ladder, like a Minecraft jump. That would let it build stairs.
- Slabs or stairs as pieces.
