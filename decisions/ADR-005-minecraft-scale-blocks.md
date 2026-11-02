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

## Settle and hold, full-block logs (after n2, your choice)
You saw stacks standing askew, logs that did not fit the cube style, and Godling stuck on LowStep.

What was wrong:
- **Askew stacks.** Pieces were set down square, but the body is an unstoppable character controller. Walking into a stack shoved it about 2 units and twisted it 8–35°.
- **Logs.** A log was half a block thick, so a block set on one sat half a layer off. The body also measured a log as a circle 7.5 across, so it stopped 5.3 away from one ("instead of walking into it") and refused clear spots beside it as "occupied".
- **Touching neighbours.** The world counted pieces that only touch as overlapping, and on the grid neighbours always touch. So a block could not be set right beside another, or at a log's end.
- **Stuck on LowStep.** Hopping down aimed straight at the target, into the ladder or the taller mesa. Setting down and placing never tried to hop down, so from a platform the ground was "no clear spot to reach".

What changed:
- **Settle and hold** (`main.lua`, `settleResting`). A block, stone or log that has been still for two checks (0.5 s apart) and lies on a face is squared to the nearest quarter turn, set into its grid cell if that is free, and held there (anchored, `Settled`). The body can no longer shove it. Leaning pieces are held as they lie.
- **Wake.** Lifting a piece wakes whatever rested on it (and what rested on that). They fall until they settle again, so a beam whose leg is taken away falls.
- **Fastening** fixes a piece where it is, like mortar. Unlike a settled piece, it stays even when what it rests on is taken away, and it cannot be lifted until a hammer knocks it loose. Nothing is welded any more.
- **Logs** are 7.5 x 2.5 x 2.5: three blocks long and one thick. Lying down they fill three cells of one layer; stood on end, three layers of one cell. The art session remodelled `log.glb` as squared timber (3:1:1) and fixed `stone.glb`, which read as glass.
- **Touching is not overlap**: the world's placement probe is 0.1 smaller than the piece.
- **Body** (`skills.py`):
  - walking up to a log stops just beside it;
  - "occupied" and "too close" checks use boxes;
  - placing stands beside a long piece's middle.
  - Hopping down tries real edges. For each clear spot and each direction off it, the landing must be lower ground within a hop and clear, and the step off must cross no wall or standing thing. Up to three edges are tried.
  - Setting down and placing hop down first when the target is below.
- **Mind:** logs are "three blocks long and one thick"; pieces are "fastened in place, like mortar".

Tested live:
- The starting pile settled (12 of 12).
- The body walked straight into a 3-high stack: the stack stayed at 0.0° and 0.00 off its cell.
- Lifting the bottom block dropped the two above, square, into its place.
- A felled log was 7.5 x 2.5 x 2.5 and settled square.
- A block set on a log lay at 3.75, level with the second layer.
- A wall row worked: blocks side by side, a second course, a log at the end, a block at the log's far end.
- A gate beam across two legs fell and leaned when one leg's top block was taken.
- A fastened block stayed in the air when the log under it was taken.
- From LowStep beside the ladder, Godling hopped down to pick up a block, climbed back, and hopped down to set it down.
- No world errors.

Screenshot: `research/screenshots/2026-11-01-settle-and-hold/wall-log-and-stone.jpg`.

## Stone yard and doorway routing (after n2, later the same evening)
In n2, Godling quarried 35 stones and used about 10. Stones popped out at loose spots and tumbled into a field. Godling boxed itself in and spent its last 15 minutes trying to get out. With settle and hold, such a pen would trap it for good.
- **Stone yard.** A stone lands square on the free ground cell nearest the struck face, in the ring of 24 cells around the quarry's foot, never onto the body. Godling works from outside the ring and still reaches the face. When the ring is full, the quarry answers "no stone can come off… carry some away first", and the blow is not counted.
- **The hammer's home** moved to (16, -34), outside the ring.
- **Routing on half-unit cells.** On whole units the router could not plan through half of all one-block doorways, those centred on a half unit. When no way round is known, the body still walks straight, and if it gets stuck it now names what hems it in.

Tested live:
- 63 strikes gave 21 stones, each in its own ring cell on the ground, square and settled. The next strike reported the yard full.
- Godling walked away and carried a stone off.
- A route through a doorway centred at x = 2.5 was planned and walked.
- No world errors.

## Wedged after climbing down (test run t1)
Godling set the ladder 1.25 behind a row of blocks, climbed onto Block_10 and climbed down. Climbing down picked the first side with ground at the foot. It never checked that a 2-wide body fits there, so the body landed half inside Block_10, squeezed between block and ladder. From then on every walk failed on its first step.
- **The world checks for room** (`bodyFits`): a step-off spot, up or down, must have room for the whole body. Spots a little further out are tried too. Climbing down happens on the side the body steps off to.
- **The body's way out of a tight spot** no longer runs into anything, or deeper into what it already presses against.
- **The unstick reflex** knows pieces and the ladder, not just mesa walls. Squeezed between two things, it slips out along the gap. It leaves alone what the walk is heading for (the ladder it is about to climb).
- **The router** stops searching once it is within 1.5 of a goal it cannot stand on exactly, such as a ladder's foot by a wall, and walks the rest straight. It no longer searches the whole island first.

Tested live in t1's layout: Godling climbed onto Block_10 and climbed down onto the open side at (14.5, 9.0), then walked off, picked a block up and set it down. The LowStep climb still works, a climb takes 5.7–6.6 s, and the world showed no errors.

**Stranded on a block (test run t2).** Godling stood on a block it had set on top of LargeMesa (6.5 high), holding the ladder. The hop down 2.5 onto the mesa top was refused with "no clear edge". The hop-down check counted the block underfoot as something in the way. Now only what sticks up above the floor underfoot counts.

Tested live:
- Godling hopped 2.5 off a block.
- It climbed back up, picked the ladder up from on top, leaned it back against the block from up there, climbed down and walked off.

## Bigger trees, terrain on the grid (your choice, late evening)
You asked, through the art session, for trees to match the big logs, and maybe the whole world at the same ratio. You chose "20 tall, spread out" and "snap the terrain to the grid, same island".
- **Trees** are 2.5 x 20 x 2.5, on grid cells about 10 apart, the south grove clear of the quarry yard.
  - A felled tree falls along the grid: two logs side by side, in the cells next to its stump. Logs that fell at a slant were pushed up to 16 units off by their slanted boxes and settled at 45°.
  - The stump is 2.5 x 1.25 x 2.5, and the body routes round it as terrain.
  - The art session made a taller tree model.
- **Mesas and the quarry** have whole-block heights: LowStep 2→2.5, LargeMesa 4→5, Ridge 3→2.5, TallMesa 6→5, HighShelf and TowerBase 7→7.5, Peak 11→10, quarry 6→5. Their faces lie on cell boundaries, so blocks set against them sit flush, and a mesa top is a block layer. The island keeps its size.
- **Spawn check:** pieces that only touch no longer count as overlapping, so new pieces are not pushed a cell further out.
- **Body:** reaching for something on the ground from too high up now says so plainly: "…below you, out of reach… too high to hop down; climb down first".

Tested live:
- Trees and stumps are the new sizes.
- Felling from the south and from the east put both logs square in the cells next to the stump.
- The body walked across the old trunk line and around the stump.
- A block sat flush against LowStep, and one on top of it lay at 3.75.
- LowStep (2.5) was climbed and hopped down.
- A quarried stone landed in the yard cell right against the quarry face.
- The new message showed on top of a 3-high column.
- No world errors.

## The castaway island (your choice: "reshape the island now")
You sent Cast Away references: the poster, a castaway-island map, and Monuriki, the Fiji island it was filmed on. You asked for the movie's palms and for Godling to spawn "near the yellow busted boat on the shore".
- **Layout.** The island keeps its size: a sand beach all round (widest in the south), grassy inland, a rocky peak in the north-west, a palm islet off the south-east.
- **Terrain on the grid.** The peak is terraces at 5 / 10 / 15 and a crag at 20, each one ladder-climb apart. All terrain faces lie on the block grid. The quarry is cut into the peak's foot, so its yard rings three sides (12 cells).
- **Trees.** Eight trees form a forest in the east. Ten palms line the beach; they are trees that give logs.
- **Spawn.** Godling spawns on the west beach beside the busted raft (`Raft`, `RenderRole` "Wreck", which the body routes round).
- **Roles.** Sand is `Ground` and rock is `Mesa` to the body, with a `Surface` attribute that the renderer paints by. The art session owns that look, the palm and the raft model.

Tested live:
- The spawn is beside the raft.
- The walk from the beach to the starting pile took 13 s.
- A quarried stone landed in the yard at the peak's foot.
- Godling climbed FlatRock and hopped down.
- It climbed the peak's base (5) and shoulder (10) with the ladder, came back down, lowered the ladder from the base and climbed down.
- A palm was felled into two square logs on the sand, and a block was set down on the beach.
- No world errors.

Screenshot: `research/screenshots/2026-11-01-castaway-island/overview.jpg`.

## After test run t3
t3 (30 min, before the island) was the first run to really build:

| | n2 | t3 |
|---|---|---|
| Walls | 0 | 1 |
| Largest structure | 6 pieces | 12 pieces |
| Tallest built | 7.5 | 15 |

But Godling stood still 78% of the time. Most plans failed at once, and the body waited for the next decision. The fixes:
- **Ladder down.** Stranded up high, where a hop is too far or there is no edge to hop from, the body climbs down a ladder standing at its level, then walks on or reaches for its target. In t3 it stood on its own piers while every plan that began on the ground failed (23 failures). The drop is now measured to the floor under the target, not the target's own top.
- **Setting things aside.** The hands-full reflex sets things on the floor actually underfoot, which may be a built platform, a little further out than before. It lays a log either way round.
- **Long walks.** The engine's MoveTo gives up after 8 s, as Roblox's does, so every walk longer than about 40 units stalled halfway. The body now renews it every 6 s; the 59-unit walk from the raft takes 11 s in one go.
- **The ring is gone** (you asked). The ladder stays.

Tested live:
- On a 2-high stack, walking to the ground took the ladder down.
- Reaching for a block in the pile took the ladder down and picked it up.
- Holding a log, picking up a block set the log down square first.
- No world errors.

Not handled yet: a thrown object no longer knocks settled pieces down. When viewers get to throw things at buildings, an impact should wake what it hits.

## Not built (possible next)
- Climbing one block without a ladder, like a Minecraft jump. That would let it build stairs.
- Slabs or stairs as pieces.
