# ADR-007: The castaway island, and surviving on it

Date: 2026-11-02 (night). Status: decided by you, built, tested live. A short run with the mind was under way at the time of writing.

## Why
You found the first castaway island (ADR-005) wrong in every way. There was no sand or shore, the map was small, you couldn't see Godling spawn by the raft, and the box shapes looked nothing like Cast Away. You then asked for Godling to start like Chuck Noland: first write HELP in the sand, then become a builder. You also wanted hunger, fish and a tool to catch them, fire, a volleyball like Wilson, and day and night.

## Decisions (yours)
1. **The look.**
   - Merge the other session's renderer, which draws sand, foam, sea and rock (local merge commit 573f613).
   - Build the land Minecraft-style from 2.5 blocks.
   - Make the island about 2.5x bigger.
   - Stop the night run on the old island.
2. **The castaway start.** Godling wants to be found first and can write in the sand with its foot. HELP with logs needs nothing new.
3. **Palms everywhere**, not broadleaf trees.
4. **Food.**
   - Fish and coconuts.
   - The spear is carved from a log with the axe.
   - At no health, Godling faints and wakes at the raft.
   - Hunger empties in about an hour.
5. **Fire.** It is for cooking and as a signal, and it is hard to make, like the film.
6. **Day and night.** Added.
7. **The volleyball.** Godling names it itself and talks to it.

## What was built
**The island** (`tools/make_island.py` writes the `ISLAND` block in `world/main.lua`, a copy in `world/island.lua`, and `research/island-preview.png`):
- **Shape.** 111 x 119 blocks: a ragged coast, sand all round, wider in the south, and a palm islet across a strait.
- **Rock.** A lopsided peak 16 blocks (40 units) high in the north-west, cut in 2-block terraces, plus two hills.
- **Parts.** Rock is grid-aligned columns (`Mesa`, `Surface` "Rock", `Feature` Peak, EastHill or SouthHill). Ground is sand under the whole outline, with grass 0.1 above it inland.
- **Where things are.** The raft is on the west beach and Godling spawns beside it. The camp (starting blocks, ladder, axe) is about 12 blocks inland. The quarry is against the peak's foot. 70 palms lean out to sea on the beach and any way inland.
- **Voxels.** Clawblox's voxel terrain was looked at and set aside: its voxels are 4 units, which don't fit our 2.5 grid, the ladder or the hop.

**The body, for hundreds of terrain parts:**
- `BoxIndex` buckets footprints on a 5-unit grid. Ground, surface and wall lookups check only nearby parts.
- Observing takes 7 ms with 563 entities, and a route across the island plans in 0.24 s.
- Landmarks group by `Feature`, so the mind sees "Peak", not hundreds of terraces. Trees and palms are one compact line each.
- The mind gets a small map of the island from above (one character per 10 units): it had walked into the sea and drawn across the grass looking for the beach.

**Writing in the sand:**
- `draw(x, z)` drags a foot from where Godling stands, leaving a groove on open sand only (`SandMark`, attribute `Stroke`).
- The mind is told the lines it has drawn.

**Survival:**
- **Hunger and health.** Hunger runs from 100 to 0 in 3600 s, then health from 100 to 0 in 1800 s. At none, Godling faints: it drops what it holds and wakes at the raft with hunger 50 and health 30 (`Faints` counts). The viewers' HP shows health.
- **Food.** `shake(palm)` drops its ripe coconut, one per palm every 5 minutes, worth 15. `eat()` eats what is held.
- **Spear.** `carve(log)` with the axe in hand takes 3 strokes and makes `Spear_n`.
- **Fish.** 12 fish swim the shallows along the shore. `strike(fish)` with the spear catches it 60% of the time, and the catch (`Catch_n`) lands on the sand. A missed fish darts away. A caught fish is replaced after 60 s.
- **Fire.** `kindle(log)` rubs at a log lying on the ground. Each try takes 4 s and catches 20% of the time. A fire burns 10 minutes and uses the log up.
- **Cooking.** `cook()` cooks a held raw fish within 6 of a fire: raw is worth 20, cooked 50.
- **Day and night.** A 40-minute day starts at 07:00. The hidden `Clock` part carries `TimeOfDay`. The renderer's sun follows it (a small change to `world/renderer/src/index.js`, bundle rebuilt), and the mind is told the hour.
- **The volleyball.** It washes up beside the raft with no name. The persona now says being alone weighs on Godling, and talking helps.
- **Persona.** It now opens: woke on the sand by the wreck, no one knows; first, to be found; then to make a life and build.

## Tested live
- **Writing.** An H was drawn on the beach, and a line onto grass was refused.
- **Food.** A shaken palm dropped a coconut, which was eaten. A second shake: no ripe coconut.
- **Spear and fish.** A palm was felled and a log carved into a spear in 3 strokes. A fish was speared from the shore, and the catch was eaten.
- **Fire and night.** A fire caught after about 14 s of tries. A fish was cooked over it and eaten. Night fell on schedule: dark sky, the fire beside Godling.
- **Fainting.** At a shortened test pace, Godling fainted and woke at the raft, half fed, with health 30.
- **Speed.** Long walks don't stall, observing took 7 ms, and a cross-island route planned in 0.24 s.
- No world errors.

Screenshots in `research/screenshots/2026-11-01-castaway-island/`: block-island, raft-and-sand-lines, night-fire.

## Asked of other sessions
- **The renderer session:** flames, smoke and light for fire; night lighting; fish against the sea; sand grooves.
- **The art session:** coconut, spear, fish (raw and cooked), and a volleyball without a face.
- Until then those render as plain boxes; the fire is a dull orange box.

## Not done
- A face on the volleyball once named.
- Rescue itself: nothing passes the island yet.
- Tides washing the sand lines away.
