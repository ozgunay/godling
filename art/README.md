# Godling art

Models for Godling's world, built by Python scripts in Blender. No hand-made files: change a script, run it
again.

| Model | File | Built by |
|---|---|---|
| Godling, the mascot (clips: Idle, Walk, PickUp, Strike, Climb) | `world/assets/godling.glb` | `build_godling.py` |
| Tree, palm, stump, log, axe | `world/assets/tree.glb`, `palm.glb`, `stump.glb`, `log.glb`, `axe.glb` | `build_props.py` |
| Quarrying: hammer, quarry outcrop, stone cube, stone brick, boulder | `hammer.glb`, `quarry.glb`, `stone.glb`, `brick.glb`, `boulder.glb` | `build_props.py` |
| Ladder | `world/assets/ladder.glb` | `build_props.py` |
| Castaway: raft, coconut, spear, fish (raw and cooked), volleyball | `raft.glb`, `coconut.glb`, `spear.glb`, `fish.glb`, `fish_cooked.glb`, `volleyball.glb` | `build_props.py` |

The survival pieces, with the way each one lies in its part:
- **Coconut:** a brown husk with three faint ridges, mottled with vertex colours, for a 0.9 ball part.
- **Spear:** an eight-sided whittled shaft that wanders a little, with knots and a paler carved point. It is 4.5 long along the model's Z, with the point at the part's local −Z (its LookVector), like the axe and hammer heads.
- **Fish:** a chubby reef fish, dark blue back to silver belly in vertex colours, with blue fins and eyes.
  - It lies on its side like its 1.3 × 0.35 × 0.5 part: head at +X, back towards local −Z.
  - A swimming fish rolls its part 90° about X, which puts the back up.
  - `fish_cooked.glb` is the same fish browned, with grill marks.
- **Volleyball:** a plain white ball with the classic crossing panels and soft seam grooves, for a 1.1 ball part. It has no face and no brand mark; Godling is to name it itself.

```powershell
$blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
& $blender --background --factory-startup --python art\build_godling.py
& $blender --background --factory-startup --python art\build_props.py
# preview stills in art\previews\
& $blender --background art\godling.blend --python art\render_preview.py -- godling
& $blender --background art\props.blend --python art\render_preview.py -- props
```

## Godling
An original design, not a copy of any mascot:
- a chubby cream vinyl-toy figure;
- a rounded TV-like head, with a dark screen face showing two glowing mint eyes, a smile and soft cheek glow;
- a small gold halo, because it is a "little god";
- coral mitten-hands and boots.

Being a god, it levitates what it carries above its head, which is how the world already holds objects.

**Rig.**
- The Mixamo skeleton from `source/` (65 bones), shrunk to chibi proportions:
  - legs ×0.42, spine ×0.55, arms ×0.5;
  - bone directions and rolls are kept, so Mixamo clips still play.
- Every body part is rigid and moves with one bone, like a toy. This is simple and robust, and needs no weight painting.
- The parts are joined into one mesh, each part fully weighted to its bone (`join_and_skin`). It moves exactly as before, but draws in one call per material (6) instead of one per part (23).

**Budget** (it has to run in phone browsers): about 4.6k triangles, down from 52k.
- Body parts are 16 × 10 spheres and limbs 12 × 8.
- The head and screen are rounded boxes: a 4-segment bevel with hardened normals instead of an 8-segment bevel under level-2 subdivision.
- At the size Godling is seen, the previews look the same as before.

**Clips** (60 fps). The runtime model controller picks Walk and Idle by name:
- **Walk:** `source/walking.fbx`, with its forward travel removed (the world moves the body). The bob and sway are kept and scaled to the shorter legs.
- **Idle:** frames 1–30 of `source/picking_up.fbx` (a calm stance), played forth and back.
- **PickUp:** frames 40–370 of `source/picking_up.fbx`, sped up 2.6× to 2.1 s.
  - The back and hips bend is cut to 35%: an adult's 90° scoop makes a big-headed chibi face-plant.
  - The thighs are re-solved every frame so the feet stay planted.
  - The runtime does not play this clip on its own; the world renderer has to trigger it on a pick-up.
- **Strike** and **Climb** have no Mixamo source. Each pose in them aims Godling's own bones in a direction (`posed_clip`), on top of Idle's stance:
  - **Strike** (1.0 s): a two-handed swing. The arms wind up wide and high, then come down in front with a 26° bow, then recover.
  - **Climb** (1.0 s, loops): hand over hand. One hand reaches up beside the head, the other grips at the chest, and the opposite knee steps up.
  - Every bone is keyed, so no bone falls back to the T-pose while either plays alone.
- The arms are 0.65× an adult's. At 0.5× a raised hand stayed hidden under the big head.

## Props
- **Tree:** a trunk with a root flare and a canopy of five soft green blobs.
  - The clear trunk is about 60% of the height, and the trunk is about a ninth as thick as the tree is tall.
  - So a tree part 22–26 tall and 2.5 wide holds the two 7.5 × 2.5 logs it is felled into (Minecraft scale).
- **Palm:** a coconut palm for the same 2.5 × 20 × 2.5 part as the trees. The style reference is Cast Away's island, as the user asked; it copies no artwork.
  - A slim, faintly ringed, grey-brown trunk that leans out (+X) and curves back up near the top.
  - A tuft of long arching fronds and coconuts.
  - The trunk's foot is at the part's centre: see "fit by the whole outline" below. Rotating the part turns the lean, so a beach cluster can lean every which way.
- **Log:** a squared timber beam along X, exactly 3 : 1 : 1 like its 7.5 × 2.5 × 2.5 block part (ADR-005: a full block thick and three long, since round logs rolled off what they were set on). It has four alike hewn faces, since a beam stood on end shows them all, rough bark left along the corners, and growth rings on both square ends.
- **Stump:** what a felled tree leaves, 1.4 across its roots and 0.6 tall, with a ringed cut top.
- **Axe:** lies on its side like its 0.4 × 0.4 × 1.0 part, handle along the model's Z and blade up. It has a wooden handle, coral grip, and a steel head with a bright edge.
- **Boulder:** a heavy, lumpy rock with a few worn flat facets, round enough for its 1.6 ball part.
- **Hammer:** a stonemason's sledge lying on its side, 1.2 long (the model's Z), with a dark iron head and bright striking faces.
- **Quarry:** a rocky outcrop, 6 × 3.5 × 5, with pale freshly cut faces and a bench, and rubble and broken chunks at its foot.
- **Stone and brick:** rough-cut granite, 0.75 cube and 1.5 × 0.75 × 0.75 (long along X), chiselled with dents only, so they never poke out of their part.
  - The granite is mottled with vertex colours (`COLOR_0`), soft patches blended across each face, and is fully matte.
  - A uniform pale blue-grey looked like frosted glass in game, a "ghost box". The faces were never flipped or transparent.
- **Raft:** the busted yellow life raft Godling starts beside, after the castaway film the user referenced. It fits its {5, 1.25, 3.75} part exactly: the outline is pinned to the part's box.
  - An inflatable ring, round at one end and collapsed flat and wrinkled at the other.
  - A sagging floor, a canopy fallen in over the inflated end, and a slack grab line.
- **Ladder:** two rails and 8 rungs along X, coral caps, standing upright. Its proportions are those of the 1.5 × 7.5 × 0.4 part (Minecraft scale, ADR-005).

At Minecraft scale (ADR-005) every part grew evenly except the ladder's, so only the ladder was rebuilt. `brick.glb` is no longer used by the world.

The world renderer fits each model to the *height* of the part carrying it (uniform scale) and centres it.
So each model has to share its part's proportions and long axis; a part 3×8×3 makes an 8-unit tree.

**Fit by the whole outline (`fit_bounds`).**
- The runtime takes that height and centre from the model's *first mesh primitive* only, and a glTF mesh has one primitive per material.
- Until this fix, models whose first material covered only part of them were drawn wrong in game:
  - the axe about 5.2× too big and the hammer about 4.4×;
  - the tree 1.44× too tall;
  - the ladder centred on one rail.
- Every prop now gets a first material, `bounds`, holding just two specks of triangles at the corners of its whole outline, too small to see.
- For the tree and the palm, that outline is also made symmetric about the trunk's foot, so a leaning crown doesn't pull the trunk off its collider.
- Godling uses its own controller in the renderer, which measures every part, so it needs none of this.

**Triangle budget.**
- Trees and palms are drawn many times a frame, shadows included, so keep them near 1.3k triangles each.
- Blobs are 16 × 8 spheres by default, and small ones (coconuts, caps, roots, quarry pebbles) fewer.
- Current counts, in triangles:

| Model | Triangles |
|---|---|
| palm | 1,370 |
| tree | 1,334 |
| stump | 1,002 |
| ladder | 1,050 |
| raft | 3,150 |
| quarry | 3,690 |
| stone | 434 |

The renderer uses filmic tone mapping, which darkens greys a lot. So the stone colours are set much lighter
than they look right in these previews, otherwise they come out charcoal in the game. They were checked in
the game at the default camera. The sky renderer (ADR-006) keeps that light by day at the default sun, so
these checks still hold.

For phones, keep a prop to a few thousand triangles and a few materials. Each material in a model is one
draw call per kind of prop, however many of that prop stand in the world.

## How the world uses them
- **`world/main.lua`:**
  - The character's root part carries `ModelUrl = asset://godling.glb`; the renderer reads the model from the root part, not from the character.
  - `noteReach` bumps the player's `Reaches` attribute on every pick-up and place.
  - Eight trees (`trees` table) are anchored parts, 1.4 wide and 7–9 tall, so they collide as their trunk only. They have `RenderRole = "Tree"` and `ModelUrl = asset://tree.glb`.
  - Cube deliveries keep clear of the trees.
- **`world/renderer/src/models.js`:** Godling has its own model handling (`createCharacterController`). The props are drawn instanced, one draw call per mesh (`instances.js`).
  - it is sized from the bounds of all its parts (the runtime helper sizes a model by its first mesh only);
  - the walk is played at the body's real speed, so the feet don't slide;
  - PickUp plays in about 1.1 s whenever `Reaches` goes up.
  - Strike plays whenever `Strikes` goes up.
  - Climb loops while `Climbing` is `true`.

  The trees, log and axe use the runtime's ordinary model helper.
- **`mind/godling/world.py`:** a "Tree" part counts as terrain far too high to climb, so the body's router keeps clear of trunks the way it does of mesa walls. Trees are also listed among the landmarks.

The log and the axe are not in the world yet; they wait for a way to fell trees.

## Sources
`source/walking.fbx` and `source/picking_up.fbx` are Mixamo animations the user downloaded (skeleton only,
no character mesh).
