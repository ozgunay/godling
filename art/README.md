# Godling art

Models for Godling's world, built by Python scripts in Blender. No hand-made files: change a script, run it
again.

| Model | File | Built by |
|---|---|---|
| Godling, the mascot (clips: Idle, Walk, PickUp, Strike, Climb) | `world/assets/godling.glb` | `build_godling.py` |
| Tree, stump, log, axe | `world/assets/tree.glb`, `stump.glb`, `log.glb`, `axe.glb` | `build_props.py` |
| Quarrying: hammer, quarry outcrop, stone cube, stone brick, boulder | `hammer.glb`, `quarry.glb`, `stone.glb`, `brick.glb`, `boulder.glb` | `build_props.py` |
| Ladder | `world/assets/ladder.glb` | `build_props.py` |

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
- Every body part is a rigid mesh riding one bone, like a toy. This is simple and robust, and needs no weight painting.

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
- **Tree:** about 3.6 m, trunk with a root flare, and a canopy of five soft green blobs.
- **Log:** lies along X, six times as long as thick (its part is a 3.0 × 0.5 × 0.5 cylinder), with bark sides and cut ends showing growth rings.
- **Stump:** what a felled tree leaves, 1.4 across its roots and 0.6 tall, with a ringed cut top.
- **Axe:** lies on its side like its 0.4 × 0.4 × 1.0 part, handle along the model's Z and blade up. It has a wooden handle, coral grip, and a steel head with a bright edge.
- **Boulder:** a heavy, lumpy rock with a few worn flat facets, round enough for its 1.6 ball part.
- **Hammer:** a stonemason's sledge lying on its side, 1.2 long (the model's Z), with a dark iron head and bright striking faces.
- **Quarry:** a rocky outcrop, 6 × 3.5 × 5, with pale freshly cut faces and a bench, and rubble and broken chunks at its foot.
- **Stone and brick:** rough-cut granite, 0.75 cube and 1.5 × 0.75 × 0.75 (long along X), chiselled with dents only, so they never poke out of their part.
- **Ladder:** two rails and 8 rungs along X, coral caps, standing upright. Its proportions are those of the 1.5 × 7.5 × 0.4 part (Minecraft scale, ADR-005).

At Minecraft scale (ADR-005) every part grew evenly except the ladder's, so only the ladder was rebuilt. `brick.glb` is no longer used by the world.

The world renderer fits each model to the *height* of the part carrying it (uniform scale) and centres it.
So each model has to share its part's proportions and long axis; a part 3×8×3 makes an 8-unit tree.

The renderer uses filmic tone mapping, which darkens greys a lot. So the stone colours are set much lighter
than they look right in these previews, otherwise they come out charcoal in the game. They were checked in
the game at the default camera.

## How the world uses them
- **`world/main.lua`:**
  - The character's root part carries `ModelUrl = asset://godling.glb`; the renderer reads the model from the root part, not from the character.
  - `noteReach` bumps the player's `Reaches` attribute on every pick-up and place.
  - Eight trees (`trees` table) are anchored parts, 1.4 wide and 7–9 tall, so they collide as their trunk only. They have `RenderRole = "Tree"` and `ModelUrl = asset://tree.glb`.
  - Cube deliveries keep clear of the trees.
- **`world/renderer/src/index.js`:** Godling has its own model handling (`createCharacterController`):
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
