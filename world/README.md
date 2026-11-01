# Godling's Mesa Island

A copy of Clawblox's `worlds/mesa-island` (MIT, github.com/nacloos/clawblox at `8be90a0`), changed for Godling. Runs copy this folder into their run directory (`run_godling.py`, `prepare_world`). The only per-run change is the walk speed.

## Changes from upstream
- **Minecraft-scale blocks on a grid (ADR-005).**
  - `BLOCK_SIZE` is 2.5 (upstream 0.75): half the 5-tall body.
  - Placed blocks and logs snap to a grid of 2.5 cells (x and z).
  - The 12 starting blocks lie flat on the grid and are stone-heavy.
  - The rock's impact blocks are off.
  - Logs are three-block beams, and the ladder is three blocks tall.
  - The sizes below that predate ADR-005 have been rescaled in `main.lua`.
- **Human-paced body (ADR-003 O2).**
  - A picked-up block rises into the hands over `LIFT_SECONDS` (1.0 s). Upstream it snaps there.
  - A placed block is lowered into place over `PLACE_SECONDS` (1.2 s). Upstream it takes 0.3 s.
  - Walking pace is set per run (`--walk-speed`, default 5).
  - The jump is a person's hop: `JUMP_POWER` 15 lifts the body about 0.6. Upstream's jump is about 6.6.
  - The mind's `godling/world.py` mirrors these constants.
- **Building (ADR-004).** The ways up are ladders and building, not jumping.
  - **Quarry.** An outcrop (`Quarry`, 6 x 3.5 x 5 at (28, -40)), with `Hammer_1` lying next to it.
    - Each `Strike` with the hammer in hand counts toward the next stone. Every `STRIKES_PER_STONE` (3) strikes, a stone breaks off: a `Stone_n` cube (0.75) and a `Brick_n` (1.5 x 0.75 x 0.75) by turns.
    - Stones are heavy and grippy (density 2.6, friction 1.0). The quarry never runs out.
  - **Trees.** `Axe_1` lies by the grove.
    - `CHOPS_PER_TREE` (4) strikes with the axe fell a tree into two `Log_n` beams (light wood), lying along the fall. A stump is left.
    - Logs are square beams. Round ones rolled off what they were set on.
    - The tree grows back after `TREE_REGROW_SECONDS` (600).
  - **Placing.** `Place` takes a rotation, as upstream. The body uses it to turn pieces a quarter round and to stand long pieces on end.
  - **Fastening.** `Fasten {name}` holds a set-down piece in place, after a `FASTEN_COOLDOWN` (2.5 s) between fastenings.
    - If the piece touches anything fixed (the ground, a mesa, or a piece already fastened in place), it is pinned there (`Anchored`).
    - Otherwise it is welded to the loose pieces it touches (`WeldConstraint`, at most 6).
    - It never welds to a fixed part. In the first night run, blocks welded to `GroundCenter` made the engine move the ground: the island sank 5 units and Godling fell into the sea.
    - A fastened piece cannot be picked up. A hammer strike knocks it loose: unpinned, welds removed.
  - **Ladder.** `Ladder_1` (1.0 x 4.5 x 0.3) is carried lying flat.
    - Set down, it always stands upright (only its facing turns) and is anchored.
    - `Climb {name}` from its foot moves the body up and steps it off onto the highest surface the ladder reaches, on either side. From up on something along its height, `Climb` moves the body back down.
    - The engine has no climbing, so the world moves the anchored root part, and the player attribute `Climbing` is true meanwhile.
  - **Boulders.** `Boulder_1` and `Boulder_2`: balls 1.6 across, stone-heavy. Carrying one halves the walking pace (`BaseWalkSpeed` / 2).
  - **Keepsakes.** Tools, the ladder and the boulders turn up again at home if lost in the sea.
  - **Spawning.** New stones and logs appear at a free spot (`freeSpawn`), along the face or higher up so they drop onto the pile. They never appear inside another piece.
  - **Sky supply.** The cube supply from the sky (ADR-003 O7) is off (`SUPPLY_FROM_SKY = false`). The quarry replaces it; the code stays for viewer drops.
- **Godling's look (art session; build scripts and previews in `art/`, details in `art/README.md`).**
  - The character uses `assets/godling.glb`, set as `ModelUrl` on the root part. It has Idle, Walk, PickUp, Strike and Climb clips.
  - Eight trees, `Tree_1`…`Tree_8`: anchored trunk colliders (1.4 x 7–9 x 1.4) with `RenderRole` "Tree", drawn with `assets/tree.glb`.
    - The mind treats trees and the quarry as terrain too high to climb (`godling/world.py`).
  - The `ART` table in `main.lua` maps objects to `assets/*.glb`: hammer, quarry, stone, brick, axe, log and ladder. Boulders have no model yet.
  - Player attributes for the renderer, with `LastActionResult` unchanged:
    - `Reaches` (pick-ups, placements and fastenings) plays PickUp;
    - `Strikes` plays Strike;
    - `Climbing` loops Climb.
- **Renderer (ADR-006).** Godling's own, in `renderer/src/`; it no longer uses the runtime's model helpers.
  - **No CDN.**
    - three.js r187 is bundled in: `npm install`, then `npm run build` (`build.mjs`).
    - The bundle `dist/renderer.bundle.js` is committed. Runs copy the world without `node_modules`, and the build step then keeps the committed bundle.
    - On native Windows `clawblox run` can't find `npm`, and in WSL `npm` may be Windows' own. Either way Clawblox falls back to the committed bundle, so rebuild after changing `src/`.
    - With Clawblox patched (`patches/VIEWER-001`), the page loads nothing from outside the server.
  - **Quality tiers** (`quality.js`): low, medium, high.
    - They set resolution, antialiasing, shadows, the sea's detail and the clouds.
    - The tier is chosen from the device (phone or PC, cores, memory).
    - A software-rendered or automated browser always gets low. That is how Clawblox's `/observe/image` captures Godling's view.
    - The resolution scales down by itself when frames run slow.
  - **Sky and sun** (`sky.js`): three.js's `Sky`.
    - One sun direction drives the light, shadows, fog, clouds and the sea's reflections.
    - By default the sun stands where the light always stood, so the art's checked colours hold.
    - `?time=18` shows that hour; `?dayMinutes=20` runs a day in 20 minutes. A day/night cycle in the world itself is not decided.
  - **Sea** (`sea.js`): it follows the camera to the horizon.
    - The vertex shader makes Gerstner waves.
    - Per pixel: a fresnel blend of water colour and sky, the sun's glint, and foam at the shore.
    - The shore comes from a distance map baked from the Ground and Mesa parts and the terrain.
    - The Ocean part only gives the sea level.
  - **Clouds** (`clouds.js`): Minecraft-style. A flat pixel layer on low, voxel puffs on medium and high.
  - **Drawing parts** (`instances.js`): all parts and static models are instanced, one draw call per kind of mesh.
  - **The castaway island's looks** (set by the world script; read in `index.js`):
    - `Ground` is drawn in the part's colour. With `Surface` "Sand" it is matte sand, where the sea draws its foam.
    - `Mesa` with `Surface` "Rock" is grey volcanic stone in block-high strata, with a moss cap on every step. Other mesas keep the tan stripes.
    - `Wreck` with no model is drawn as a deflated yellow life raft, from its part's size and colour. A `ModelUrl` (`raft.glb`) takes over when set.
  - **Models** (`models.js`): each loads once.
    - A prop's "bounds" material (two specks that set its box, from `art/build_props.py`) counts for fitting but is not drawn.
    - Animated ones (Godling) get their own mixer. The clips follow the attributes above, and Walk plays at the body's real speed.
    - In a first-person capture, the body the camera sits in is hidden, so its own head no longer fills Godling's view.
  - **Terrain** (`terrain.js`): Clawblox voxel terrain, drawn as blocks, when the patched server sends it.
  - **Checks.**
    - `?stats=1` shows frame rate, draw calls, triangles and the tier.
    - `?quality=low|medium|high` forces a tier.
    - `globalThis.__godlingRenderer` has the same counts for scripts.

The mind's thinking is not shown in the world. It goes to the run's `mind/thinking.jsonl`, for a separate viewer.

Everything else (physics, reach, the rock that spawns ImpactBlocks on impact) is upstream's.
