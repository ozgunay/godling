# Godling art

Models for Godling's world, built by Python scripts in Blender. No hand-made files: change a script, run it
again.

| Model | File | Built by |
|---|---|---|
| Godling, the mascot (clips: Idle, Walk, a gesture for each action, Jump, Fall, Climb, Brace, Strike) | `world/assets/godling.glb` | `build_godling.py` |
| Tree, palm, stump, log, axe | `world/assets/tree.glb`, `palm.glb`, `stump.glb`, `log.glb`, `axe.glb` | `build_props.py` |
| Quarrying: hammer, quarry outcrop, stone cube, stone brick, boulder | `hammer.glb`, `quarry.glb`, `stone.glb`, `brick.glb`, `boulder.glb` | `build_props.py` |
| Ladder | `world/assets/ladder.glb` | `build_props.py` |
| Castaway: raft, coconut, spear, fish (raw and cooked), volleyball | `raft.glb`, `coconut.glb`, `spear.glb`, `fish.glb`, `fish_cooked.glb`, `volleyball.glb` | `build_props.py` |
| Meteor: the stone it leaves and its crater | `meteor.glb`, `crater.glb` | `build_props.py` |

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

**Clips** (60 fps) come from Mixamo, listed in `CLIPS` in `build_godling.py`.
- Every source is in `art/source`: skeleton only, 60 fps, all from the same Mixamo character, so all share one skeleton and drop straight onto Godling.
- Each entry gives a source file, the frames to keep, the length in game, and options:
  - `loop`: the clip repeats.
  - `bend`: keeps only part of the back's bend, because a deep bend makes the big-headed chibi face-plant. The thighs are re-solved so the feet stay planted.
  - `still`: removes the root's drift across the ground, because the world moves the body.
  - `cut`: leaves out the middle of a long hold (Cook's warming of hands), so the clip keeps its start and end at less speed-up.
  - `ease`: eases from the standing pose into the clip and back out of it. A clip that starts or ends kneeling or lying then drops into it, where the renderer's 0.2 s cross-fade would snap.
  - `settle`: keeps the hips at standing height on average (the in-place ladder climb hangs the body in the air).
  - `face`: turns the clip about the vertical so the body faces forward on average (the ladder climb is acted facing away).
  - `upright`: tips the clip so the body stands upright on average (Mixamo's falls are acted lying flat in the air, which on Godling reads as a faint).
  - `pingpong`: plays the kept frames forth and back, a seamless loop from part of a one-off motion (Jump's take-off).
- Frames are chosen so each clip keeps just the action and the speed-up stays near 2x where the world allows; the lift and lowering must fit 1.0–1.2 s, so they run about 5x.
- On every clip, `spread_arms` holds the arms a little out from the body. An adult's arm swing passes inside Godling's chubby torso, and a raised hand would vanish into the head.
- A clip whose file is missing is left out (the build prints `SKIP`).
- **Size:** the export leaves out the 45 bones no body part hangs on (the fingers inside the mittens, the end bones) and samples the clips at 30 fps. With 25 clips, `godling.glb` is about 900 KB; with every bone at 60 fps it was 2.3 MB, slow to load on a phone.
- **Idle** is `happy_idle.fbx`. **Walk** is `happy_walk.fbx`, downloaded with "In Place". The build prints the walk's stride speed for the renderer's `WALK_STRIDE_SPEED`; Happy Walk's is 0.667.
- **PickUp** is frames 40–370 of `picking_up.fbx`, retimed to 1.1 s, with its bend cut to 35%.
- **Gestures**, each timed to the world (a strike at most every 0.8 s, a lift 1.0 s, a lowering 1.2 s, a rub for fire every 4 s or more). The Mixamo animation behind each:
  - PutDown: Putting Down. Throw: Throw (from a standard pose).
  - Chop: Standing Melee Attack Horizontal (an axe, right to left). Mine and Carve: Standing Melee Attack Downward. Spear: Bayonet Stab.
  - Shake: Pushing (an object forward), a shove at the trunk.
  - Kindle: Kneeling Inspecting. Cook: Kneel (warming hands over a campfire). Fasten: Pull Plant (kneeling). Draw: Dig And Plant Seeds.
  - Eat: Drinking. Talk: Talking (asking a question with two hands). WakeUp: Getting Up (from the back).
  - For the earthquake: Stagger is Stumble Backwards (3 s, at its own speed): knocked back, it sits down hard and stays down until the world sends GetUp. GetUp is WakeUp from where it sits up, without easing in from standing, and turned to face forward. LookAround is Looking Around (the idle one), over the shoulder and back.
- **Loops:** Jump is Jump (in place), its take-off played forth and back. Fall is Falling (in the air), stood upright: flailing. Climb is Climbing Ladder, downloaded with "In Place". Brace is Crouching Idle ("Low Crouching Idle"), a hand at the ground, its bend cut to 80% so Godling's face still shows.
- **How the world plays them:** at each action the world sets the player's `Gesture` (a clip name) and bumps `Gestures`. The renderer plays that clip once. If `godling.glb` has no such clip, it falls back to PickUp (`Reaches`) or Strike (`Strikes`). Jump and Fall loop while the body's humanoid state is Jumping or Freefall, Climb while `Climbing` is true, and Brace while `Bracing` is true.
- **Strike**, and **Climb** while there is no `climb.fbx`, are posed by hand (`posed_clip`), each pose aiming Godling's own bones in a direction:
  - **Strike** (1.0 s) is a two-handed swing: wind up wide and high, come down in front with a bow, recover.
  - The posed **Climb** (1.0 s, loops) is hand over hand, the opposite knee stepping up.
- The arms are 0.65× an adult's.

Preview stills of any clip, four moments each:
```powershell
& $blender --background art\godling.blend --python art\render_preview.py -- godling Walk Chop
```

## Props
- **Tree:** a trunk with a root flare and a canopy of five soft green blobs.
  - The clear trunk is about 60% of the height, and the trunk is about a ninth as thick as the tree is tall.
  - So a tree part 22–26 tall and 2.5 wide holds the two 7.5 × 2.5 logs it is felled into (Minecraft scale).
- **Palm:** a coconut palm for the same 2.5 × 20 × 2.5 part as the trees. The style reference is Cast Away's island, as the user asked; it copies no artwork.
  - A slim grey-brown trunk that leans out (+X) and curves back up near the top.
  - Its rings are vertex colours: each segment shades from pale bark to a darker scar under the next, like overlapping leaf bases. Alternating pale and dark segments read as candy stripes.
  - A tuft of long arching fronds and coconuts.
  - The trunk's foot is at the part's centre: see "fit by the whole outline" below. Rotating the part turns the lean, so a beach cluster can lean every which way.
- **Log:** a squared timber beam along X, exactly 3 : 1 : 1 like its 7.5 × 2.5 × 2.5 block part (ADR-005: a full block thick and three long, since round logs rolled off what they were set on). It has four alike hewn faces, since a beam stood on end shows them all, rough bark left along the corners, and growth rings on both square ends.
- **Stump:** what a felled tree leaves, 1.4 across its roots and 0.6 tall, with a ringed cut top.
- **Axe:** lies on its side like its 0.4 × 0.4 × 1.0 part, handle along the model's Z and blade up. It has a wooden handle, coral grip, and a steel head with a bright edge.
- **Boulder:** a heavy, lumpy rock with a few worn flat facets, round enough for its ball part. It is flat-shaded, with chunky facets, shade towards the ground and a little moss on top.
- **Hammer:** a stonemason's sledge lying on its side, 1.2 long (the model's Z), with a dark iron head and bright striking faces.
- **Quarry:** a stratified outcrop that fills its 10 × 5 × 7.5 part.
  - Ledges of warm grey and tan rock, with moss on their tops, in the style of the terraced peaks.
  - Its front is quarried back into stepped benches with sheer, pale cut faces, with cut blocks and rubble at its foot.
  - The working face points to the model's −Z, south, out of the peak's foot the quarry is cut into.
- **Stone and brick:** cut stone blocks (`cut_stone`), a cube and a 2 : 1 : 1 brick.
  - Chamfered edges worn pale, each face dressed into a few flat facets, and a knocked corner or two.
  - They are chiselled with dents only, so they never poke out of their part.
  - Each facet has its own flat tone. The earlier softly mottled granite blurred into a "ghost box" in game.
- **Rock colours (`rock_colours`):** quarry, boulder and stones are painted per facet in face-corner vertex colours (`COLOR_0`), in one matte material.
  - Each face's tone comes from the material that tagged it while building (rock, rock_band, fresh_cut, …), varied a little per facet.
  - Tones darken towards the ground, and moss grows on faces that look up.
- **Raft:** the busted yellow life raft Godling starts beside, after the castaway film the user referenced. It fits its {5, 1.25, 3.75} part exactly: the outline is pinned to the part's box.
  - An inflatable ring, round at one end and collapsed flat and wrinkled at the other.
  - A sagging floor, a canopy fallen in over the inflated end, and a slack grab line.
- **Ladder:** two rails and 8 rungs along X, coral caps, standing upright. Its proportions are those of the 1.5 × 7.5 × 0.4 part (Minecraft scale, ADR-005).
- **Meteor:** the stone a meteor leaves, for its cube part (`Meteor_<n>`, a building stone like the others).
  - Charred, pitted rock, squared off enough to stack. Its faces bulge out to the part's faces at most, so it never pokes out of its part.
  - Glowing veins: the facets a wandering zero line of noise crosses, in an orange emissive material (`ember`), so they join up into cracks.
  - It is heavier than a stone (1280 facets, about 150 KB), for the veins to run smoothly; there are only ever a few.
- **Crater:** where a meteor struck, for its 8 × 0.6 × 8 part lying on the ground (`Crater_<n>`).
  - A dish of scorched sand inside a raised rim of thrown-up sand, dark rays of ash across the apron, and charred chunks of rock about it.
  - The ground is not dug, so the dish is only the rim's inside slope down to a near-flat burnt floor. The apron's foot is round, on the part's edge, at ground level.
  - Sand and soot are vertex colours, in the same matte material as the rocks.

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
`source/walking.fbx` and `source/picking_up.fbx` are Mixamo animations the user downloaded (skeleton only, no character mesh).
The others were downloaded from Mixamo the same way, on the same character (CH02), as the `CLIPS` table names them: FBX Binary, Without Skin, 60 fps, no keyframe reduction, "In Place" for the walk, the ladder climb and the earthquake clips. The Mixamo animation behind each file is listed under Gestures above. To change a gesture, download another animation with these settings under the same file name and rebuild.
