"""Build Godling, the mascot, in Blender (background mode, no UI needed):

    blender --background --factory-startup --python art/build_godling.py

Original design: a chubby cream vinyl-toy figure with a rounded TV-like head, a dark screen face with two
glowing mint eyes, a small gold halo, and coral mitten-hands and boots.

Rig: the Mixamo skeleton from art/source, shrunk to chibi proportions (bone directions and rolls kept, so
the Mixamo clips still play on it). Every body part is rigid and moves with one bone: a toy, not skin. The
parts are joined into one mesh, each fully weighted to its bone, so the body draws in one call per material.

Budget (it has to run in phone browsers): about 5k triangles in all.

Clips (60 fps), from the Mixamo sources (see CLIPS): Idle and Walk (in place: the world moves the body); a
one-shot gesture for each action the world names (PickUp, PutDown, Throw, Chop, Mine, Carve, Spear, Shake,
Kindle, Cook, Eat, Fasten, Draw, Talk, WakeUp); loops for Jump, Fall and Climb. Strike (a two-handed overhead
swing, 1.0 s) is posed by hand on the same rig, as is Climb when its source is missing.

Writes world/assets/godling.glb and art/godling.blend.
"""
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

ART = Path(__file__).resolve().parent
ROOT = ART.parent
SOURCE = ART / "source"
OUT_GLB = ROOT / "world" / "assets" / "godling.glb"
OUT_BLEND = ART / "godling.blend"

# Chibi proportions: length factor per bone group (1 = Mixamo's adult proportions).
LEG, SPINE, NECK, ARM, HAND, HIPS = 0.42, 0.55, 0.4, 0.65, 0.6, 0.8  # arms long enough to reach past the head
IDLE_FRAMES = 30  # without happy_idle.fbx: source frames 1..30 of the pick-up clip, played forth and back
BENDING = ("Spine", "Spine1", "Spine2", "Neck", "Head")
FPS = 60

# Clips from Mixamo (art/source: skeleton only, 60 fps, all on the same character, so they share one skeleton).
# Each: name, source file (the first that exists, of several), source frames to keep (None: all), length in game
# in seconds (None: as it is), and options:
#   loop   plays round and round (Idle, Walk, Climb, Jump, Fall)
#   bend   keeps only this much of the back's bend: an adult's deep bend is a face-plant with Godling's big head
#   still  takes out the root's drift across the ground, so the clip ends where it began (the world moves the body)
#   cut    leaves out source frames a..b (the middle of a long hold) and closes the gap
#   ease   seconds to ease in from the standing pose and back out to it: a clip that starts or ends kneeling or
#          lying drops into it instead of snapping (the renderer cross-fades for only about 0.2 s)
#   settle keeps the hips at standing height on average (a ladder climb in place hangs the body up in the air)
#   face   turns the clip so the body faces forward on average (some are acted facing sideways or away)
#   upright tips the clip so the body stands upright on average (Mixamo's falls are acted lying flat in the air)
#   pingpong plays the kept frames forth and back: a seamless loop from part of a one-off motion
# The world names a gesture as it happens (player attributes Gesture and Gestures); the renderer plays the clip of
# that name once at its own speed, and falls back to PickUp or Strike if godling.glb has none. So a gesture whose
# file is missing is just left out. Lengths fit the world: a strike every 0.8 s at most, a lift in 1.0 s, a lowering
# in 1.2 s, a rub for fire every 4 s; frames keep the action itself, so the speed-up stays near 2x where the world
# allows.
CLIPS = [
    ("Idle", ("happy_idle.fbx",), None, None, dict(loop=True)),
    ("Walk", ("happy_walk.fbx", "walking.fbx"), None, None, dict(loop=True)),
    ("PickUp", ("picking_up.fbx",), (40, 370), 1.1, dict(bend=0.35, still=True)),
    ("PutDown", ("putting_down.fbx",), (170, 470), 1.2, dict(bend=0.35, still=True)),
    ("Throw", ("throw.fbx",), (15, 105), 1.0, dict(still=True)),
    ("Chop", ("chop.fbx",), (12, 118), 0.8, dict(still=True)),  # axe swung level, right to left
    ("Mine", ("mine.fbx",), (10, 115), 0.8, dict(still=True, bend=0.6)),  # axe (or hammer) brought down
    ("Carve", ("carve.fbx", "mine.fbx"), (10, 115), 0.8, dict(still=True, bend=0.6)),
    ("Spear", ("spear.fbx",), (20, 120), 0.8, dict(still=True, bend=0.6)),  # a bayonet stab
    ("Shake", ("shake.fbx",), (95, 200), 1.2, dict(still=True, bend=0.4, ease=(0.25, 0.3))),  # a shove at the trunk
    ("Kindle", ("kindle.fbx",), (30, 270), 2.5, dict(still=True, bend=0.4, ease=(0.4, 0.4))),  # kneel, work the ground
    ("Cook", ("cook.fbx",), (55, 480), 2.4, dict(still=True, bend=0.5, cut=(230, 395))),  # kneel, hands to the fire
    ("Eat", ("eat.fbx",), (125, 345), 2.0, dict(still=True)),  # a drink from the hand
    ("Fasten", ("fasten.fbx",), (40, 250), 2.0, dict(still=True, bend=0.45, face=True, ease=(0.35, 0.35))),  # kneel, pull tight
    ("Draw", ("draw.fbx",), (30, 150), 1.2, dict(still=True, bend=0.35, ease=(0.3, 0.3))),  # crouch, scratch the sand
    ("Talk", ("talk.fbx",), (15, 140), 1.6, dict(still=True)),  # asking, with both hands
    ("WakeUp", ("wake_up.fbx",), (250, 390), 2.2, dict(still=True, ease=(0.35, 0))),  # up from lying on the back
    ("Jump", ("jump.fbx",), (44, 72), None, dict(loop=True, still=True, settle=True, pingpong=True)),  # take-off
    ("Fall", ("fall.fbx",), (133, 205), None, dict(loop=True, still=True, upright=True, face=True)),  # flailing
    ("Climb", ("climb.fbx",), None, 1.0, dict(loop=True, still=True, settle=True, face=True)),  # a ladder, hand over hand
]

# Mesh detail (segments, rings). Smooth shading hides the facets at the size Godling is seen.
BEAN = (16, 10)  # torso, mittens, boots
LIMB = (12, 8)
BEVEL_SEGMENTS = 4  # the head's rounded edges

# Colours as seen on screen (sRGB); converted to the linear values materials take.
PALETTE = {
    "cream": dict(color=(0.97, 0.94, 0.87), roughness=0.42),
    "coral": dict(color=(1.0, 0.45, 0.33), roughness=0.45),
    "screen": dict(color=(0.08, 0.1, 0.2), roughness=0.2),
    "eye": dict(color=(0.45, 1.0, 0.86), roughness=0.3, emission=4.0),
    "blush": dict(color=(1.0, 0.45, 0.45), roughness=0.4, emission=0.8),
    "gold": dict(color=(1.0, 0.78, 0.25), roughness=0.3, metallic=0.8, emission=0.6),
}


# ---- helpers ------------------------------------------------------------------------------

def linear(c):
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def material(name):
    spec = PALETTE[name]
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*linear(spec["color"]), 1)
    bsdf.inputs["Roughness"].default_value = spec["roughness"]
    bsdf.inputs["Metallic"].default_value = spec.get("metallic", 0.0)
    if spec.get("emission"):
        bsdf.inputs["Emission Color"].default_value = (*linear(spec["color"]), 1)
        bsdf.inputs["Emission Strength"].default_value = spec["emission"]
    return mat


def finish(obj, mat_name, smooth=True):
    obj.data.materials.append(material(mat_name))
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return obj


def ellipsoid(name, centre, radii, mat_name, rotation=None, segments=BEAN[0], rings=BEAN[1]):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1.0, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = radii
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = rotation or Vector((0, 0, 1)).rotation_difference(Vector((0, 0, 1)))
    obj.location = centre
    return finish(obj, mat_name)


def limb(name, a, b, radius, mat_name, overlap=0.6):
    """A bean-shaped limb segment from point a to point b."""
    direction = b - a
    rotation = Vector((0, 0, 1)).rotation_difference(direction.normalized())
    return ellipsoid(name, (a + b) / 2, (radius, radius, direction.length / 2 + radius * overlap), mat_name,
                     rotation, segments=LIMB[0], rings=LIMB[1])


def rounded_box(name, centre, size, bevel, mat_name):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=centre)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width = bevel
    mod.segments = BEVEL_SEGMENTS
    mod.limit_method = "NONE"
    mod.harden_normals = True  # flat faces stay flat under smooth shading
    return finish(obj, mat_name)


def smile(at):
    """The lower half of a thin ring, facing forward: a small glowing smile."""
    bpy.ops.mesh.primitive_torus_add(major_radius=0.032, minor_radius=0.0065, major_segments=16, minor_segments=4,
                                     location=(0, 0, 0), rotation=(math.radians(90), 0, 0))
    obj = bpy.context.active_object
    obj.name = "Smile"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 0.004], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.location = at
    return finish(obj, "eye")


def fcurves(action):
    """All F-curves of an action (Blender 5 keeps them in layers, strips and channel bags)."""
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def keep_frames(action, first, last):
    """Drop keys outside first..last and move the rest so the clip starts at frame 1."""
    shift = first - 1
    for fc in fcurves(action):
        for kp in reversed(list(fc.keyframe_points)):
            if not first <= kp.co.x <= last:
                fc.keyframe_points.remove(kp)
        for kp in fc.keyframe_points:
            for point in (kp.co, kp.handle_left, kp.handle_right):
                point.x -= shift
        fc.update()


def cut_frames(action, a, b):
    """Leave out the keys between frames a and b and close the gap, so frame b follows straight after frame a."""
    for fc in fcurves(action):
        for kp in reversed(list(fc.keyframe_points)):
            if a < kp.co.x < b:
                fc.keyframe_points.remove(kp)
        for kp in fc.keyframe_points:
            if kp.co.x >= b:
                for point in (kp.co, kp.handle_left, kp.handle_right):
                    point.x -= b - a - 1
        fc.update()


def retime(action, factor):
    """Play the clip `factor` times faster (keys move closer together, starting at frame 1)."""
    for fc in fcurves(action):
        for kp in fc.keyframe_points:
            for point in (kp.co, kp.handle_left, kp.handle_right):
                point.x = 1 + (point.x - 1) / factor
        fc.update()


def ping_pong(action, frames):
    """Frames 1..n, then back again: a seamless loop from a short stretch of motion."""
    for fc in fcurves(action):
        values = {round(kp.co.x): kp.co.y for kp in fc.keyframe_points}
        for k in range(1, frames):
            frame = frames + k
            source = frames - k
            if source in values:
                fc.keyframe_points.insert(frame, values[source], options={"FAST"})
        fc.update()


def use_clip(arm, action):
    arm.animation_data.action = action
    if hasattr(arm.animation_data, "action_slot") and action.slots:
        arm.animation_data.action_slot = action.slots[0]


def hips_location_curves(action):
    return [fc for fc in fcurves(action) if fc.data_path == 'pose.bones["mixamorig:Hips"].location']


def remove_drift(action, axes=(0, 1, 2)):
    """Walk in place: take out the steady travel of the hips, keep the bob and sway. The hips bone points up, so
    in its own space Y is up and X, Z run across the ground."""
    for fc in hips_location_curves(action):
        if fc.array_index not in axes:
            continue
        keys = list(fc.keyframe_points)
        (f0, v0), (f1, v1) = keys[0].co, keys[-1].co
        slope = (v1 - v0) / (f1 - f0)
        for kp in keys:
            for point in (kp.co, kp.handle_left, kp.handle_right):
                point.y -= slope * (point.x - f0)
        fc.update()


def settle_hips(action, standing):
    """Shift the hips' height so that on average they are where they are standing (Y is up in the bone's space)."""
    for fc in hips_location_curves(action):
        if fc.array_index != 1:
            continue
        keys = list(fc.keyframe_points)
        shift = standing - sum(kp.co.y for kp in keys) / len(keys)
        for kp in keys:
            for point in (kp.co, kp.handle_left, kp.handle_right):
                point.y += shift
        fc.update()


def turn_body(arm, action, rotation):
    """Turn the whole body by `rotation` (in the armature's space) about the hips, on every key of the clip."""
    rest = arm.pose.bones["mixamorig:Hips"].bone.matrix_local.to_quaternion()
    turn = rest.inverted() @ rotation @ rest  # the same turn, in the hips' own space
    path = 'pose.bones["mixamorig:Hips"].rotation_quaternion'
    curves = {fc.array_index: fc for fc in fcurves(action) if fc.data_path == path}
    frames = sorted({kp.co.x for fc in curves.values() for kp in fc.keyframe_points})
    for f in frames:
        turned = turn @ Quaternion([curves[i].evaluate(f) for i in range(4)])
        for i in range(4):
            curves[i].keyframe_points.insert(f, turned[i], options={"FAST", "REPLACE"})
    for fc in curves.values():
        fc.update()


def average_direction(arm, action, direction):
    """The sum over the clip's frames of direction(arm), a vector in the armature's space."""
    use_clip(arm, action)
    scene = bpy.context.scene
    first, last = (int(round(f)) for f in action.frame_range)
    total = Vector((0, 0, 0))
    for f in range(first, last + 1):
        scene.frame_set(f)
        total += direction(arm)
    return total


def face_forward(arm, action):
    """Turn the whole clip about the vertical so that on average the hips face forward (+Z in the armature's
    space): some sources are acted facing sideways or away. Returns the turn in degrees."""
    hips = arm.pose.bones["mixamorig:Hips"]
    ahead = hips.bone.matrix_local.to_quaternion().inverted() @ Vector((0, 0, 1))  # the hips' forward axis at rest
    total = average_direction(arm, action, lambda a: hips.matrix.to_3x3() @ ahead)
    angle = math.atan2(total.x, total.z)
    turn_body(arm, action, Quaternion((0, 1, 0), -angle))
    return math.degrees(angle)


def stand_upright(arm, action):
    """Tip the whole clip so that on average the body stands upright (hips to head along +Y in the armature's
    space): Mixamo's falls are acted lying flat in the air, which on Godling reads as a faint, not a fall.
    Returns the tip in degrees."""
    hips, head = arm.pose.bones["mixamorig:Hips"], arm.pose.bones["mixamorig:Head"]
    total = average_direction(arm, action, lambda a: (head.head - hips.head).normalized())
    tip = total.normalized().rotation_difference(Vector((0, 1, 0)))
    turn_body(arm, action, tip)
    return math.degrees(tip.angle)


def first_pose(action):
    """Each animated location and rotation at the clip's first frame: {data path: values}."""
    curves = {}
    for fc in fcurves(action):
        curves.setdefault(fc.data_path, {})[fc.array_index] = fc
    first = action.frame_range[0]
    return {path: [comps[i].evaluate(first) for i in sorted(comps)] for path, comps in curves.items()}


def ease_from(action, pose, seconds_in, seconds_out):
    """Blend the clip's start from `pose` and its end back to it, smoothly over the given seconds."""
    first, last = action.frame_range

    def weight(x):  # how much of `pose`
        w = 0.0
        if seconds_in:
            w = max(w, 1 - (x - first) / (seconds_in * FPS))
        if seconds_out:
            w = max(w, 1 - (last - x) / (seconds_out * FPS))
        w = min(1.0, max(0.0, w))
        return w * w * (3 - 2 * w)

    curves = {}
    for fc in fcurves(action):
        curves.setdefault(fc.data_path, {})[fc.array_index] = fc
    for path, comps in curves.items():
        if path not in pose:
            continue
        if path.endswith("rotation_quaternion") and len(comps) == 4:
            frames = sorted({kp.co.x for fc in comps.values() for kp in fc.keyframe_points})
            target = Quaternion(pose[path])
            for f in frames:
                w = weight(f)
                if not w:
                    continue
                q = Quaternion([comps[i].evaluate(f) for i in range(4)])
                t = target.copy()
                if q.dot(t) < 0:
                    t.negate()
                eased = q.slerp(t, w)
                for i in range(4):
                    comps[i].keyframe_points.insert(f, eased[i], options={"FAST", "REPLACE"})
        elif path.endswith("location"):
            for i, fc in comps.items():
                for kp in fc.keyframe_points:
                    shift = (pose[path][i] - kp.co.y) * weight(kp.co.x)
                    for point in (kp.co, kp.handle_left, kp.handle_right):
                        point.y += shift
        for fc in comps.values():
            fc.update()


def soften(action, bones, keep):
    """Keep only part of these bones' rotation away from the rest pose (slerp each key towards rest)."""
    for bone in bones:
        path = f'pose.bones["mixamorig:{bone}"].rotation_quaternion'
        curves = {fc.array_index: fc for fc in fcurves(action) if fc.data_path == path}
        if len(curves) != 4:
            continue
        frames = sorted({round(kp.co.x, 4) for kp in curves[0].keyframe_points})
        values = {f: Quaternion([curves[i].evaluate(f) for i in range(4)]) for f in frames}
        for f, q in values.items():
            softened = Quaternion().slerp(q, keep)
            for i in range(4):
                curves[i].keyframe_points.insert(f, softened[i], options={"FAST", "REPLACE"})
        for fc in curves.values():
            fc.update()


ARM_SPREAD, FOREARM_SPREAD = 0.3, 0.15  # how far each bone's direction is pushed out to Godling's side


def spread_arms(arm, action):
    """Hold the arms a little out from the body: an adult's arms swing close to the body, and Godling's chubby
    torso would swallow them (in the walk the hands crossed inside it). Every frame, each upper arm and forearm is
    turned a little towards its own side; a raised arm goes out beside the big head too, instead of into it."""
    use_clip(arm, action)
    scene = bpy.context.scene
    first, last = (int(round(f)) for f in action.frame_range)
    for f in range(first, last + 1):
        scene.frame_set(f)
        for side, x in (("Left", 1.0), ("Right", -1.0)):  # armature space: +X is Godling's left
            for bone, push in (("Arm", ARM_SPREAD), ("ForeArm", FOREARM_SPREAD)):
                pb = arm.pose.bones[f"mixamorig:{side}{bone}"]
                direction = (pb.matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
                aim(pb, direction + Vector((x * push, 0, 0)))
                pb.keyframe_insert("rotation_quaternion", frame=f)


def soften_hips(arm, action, keep):
    """Less forward pitch of the hips, with the thighs re-solved each frame so legs and feet stay put."""
    use_clip(arm, action)
    scene = bpy.context.scene
    hips = arm.pose.bones["mixamorig:Hips"]
    thighs = [arm.pose.bones[f"mixamorig:{side}UpLeg"] for side in ("Left", "Right")]
    first, last = (int(round(f)) for f in action.frame_range)
    for f in range(first, last + 1):
        scene.frame_set(f)
        legs = [t.matrix.copy() for t in thighs]
        hips.rotation_quaternion = Quaternion().slerp(hips.rotation_quaternion.copy(), keep)
        hips.keyframe_insert("rotation_quaternion", frame=f)
        bpy.context.view_layer.update()
        for thigh, matrix in zip(thighs, legs):
            thigh.matrix = matrix
            bpy.context.view_layer.update()
            thigh.keyframe_insert("rotation_quaternion", frame=f)


# ---- clips posed by hand ---------------------------------------------------------------------
# Directions are in the armature's own space: +Y is up, +Z is forward, +X is Godling's left. They are written
# for the left side, x meaning outward; the right side mirrors them. "bend" tips a spine bone forward (degrees).
# Godling's arms are short and its head is big: a hand raised straight up ends inside the head, so raised
# arms go up and outward, to show beside it.
def _both(pose):
    out = {}
    for bone, target in pose.items():
        if bone.startswith("_"):
            name = bone[1:]
            out["Left" + name] = target
            out["Right" + name] = (-target[0], target[1], target[2])
        else:
            out[bone] = target
    return out


STRIKE = [  # a two-handed overhead swing, 1.0 s: wind up high and back, bring it down in front, recover
    (1, {}),
    (20, _both({"Spine1": ("bend", -10), "_Arm": (0.9, 0.4, -0.25), "_ForeArm": (0.4, 0.85, -0.3)})),
    (31, _both({"Spine1": ("bend", 26), "_Arm": (-0.15, -0.3, 1), "_ForeArm": (-0.3, -0.75, 0.6)})),
    (42, _both({"Spine1": ("bend", 20), "_Arm": (-0.15, -0.4, 1), "_ForeArm": (-0.25, -0.85, 0.45)})),
    (61, {}),
]
_UP_HAND = {"Arm": (0.85, 0.45, 0.3), "ForeArm": (0.3, 0.85, 0.4)}  # reaching for the rung above
_LOW_HAND = {"Arm": (0.3, -0.2, 0.95), "ForeArm": (0.0, 0.7, 0.7)}  # gripping at chest height
_STEP_UP = {"UpLeg": (0, -0.35, 0.95), "Leg": (0, -1, -0.1)}  # knee up onto the next rung
_STEP_DOWN = {"UpLeg": (0, -1, 0.08), "Leg": (0, -1, 0.0)}


def _climb_phase(left_up):
    """Hand over hand: one hand high and the other low, the opposite knee up."""
    pose = {"Spine1": ("bend", 8)}
    for side, up in (("Left", left_up), ("Right", not left_up)):
        mirror = 1 if side == "Left" else -1
        for bone, (x, y, z) in (_UP_HAND if up else _LOW_HAND).items():
            pose[side + bone] = (x * mirror, y, z)
        for bone, direction in (_STEP_DOWN if up else _STEP_UP).items():
            pose[side + bone] = direction
    return pose


CLIMB = [(1, _climb_phase(True)), (31, _climb_phase(False)), (61, _climb_phase(True))]  # loops, 1.0 s
POSE_ORDER = ("Spine1", "LeftArm", "LeftForeArm", "RightArm", "RightForeArm", "LeftUpLeg", "LeftLeg",
              "RightUpLeg", "RightLeg")


def aim(pb, target):
    """Turn a pose bone about its head so it points along `target` (armature space)."""
    m = pb.matrix.copy()
    head = m.translation.copy()
    current = (m.to_3x3() @ Vector((0, 1, 0))).normalized()
    turn = current.rotation_difference(Vector(target).normalized()).to_matrix().to_4x4()
    pb.matrix = Matrix.Translation(head) @ turn @ Matrix.Translation(-head) @ m
    bpy.context.view_layer.update()


def bend(pb, degrees):
    current = (pb.matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
    aim(pb, Quaternion((1, 0, 0), math.radians(degrees)) @ current)


def posed_clip(arm, name, keys, base):
    """A clip keyed by hand on top of `base`'s first frame. Every bone is keyed, so no bone falls back to
    the T-pose while this clip plays alone."""
    use_clip(arm, base)
    bpy.context.scene.frame_set(1)
    rest = {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    use_clip(arm, action)
    for frame, pose in keys:
        for pb in arm.pose.bones:
            pb.matrix_basis = rest[pb.name]
        bpy.context.view_layer.update()
        for bone in POSE_ORDER:
            if bone in pose:
                pb = arm.pose.bones["mixamorig:" + bone]
                target = pose[bone]
                bend(pb, target[1]) if target[0] == "bend" else aim(pb, target)
        for pb in arm.pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=frame)
        arm.pose.bones["mixamorig:Hips"].keyframe_insert("location", frame=frame)
    return action


def scale_hips(action, factor):
    """Shorter legs: the hips rise and dip less."""
    for fc in hips_location_curves(action):
        for kp in fc.keyframe_points:
            for point in (kp.co, kp.handle_left, kp.handle_right):
                point.y *= factor
        fc.update()


def import_clip(path, name):
    bpy.ops.import_scene.fbx(filepath=str(path))
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE" and o.animation_data
               and o.animation_data.action and o.animation_data.action.name.startswith("Armature|"))
    action = arm.animation_data.action
    action.name = name
    action.use_fake_user = True
    return arm, action


# ---- build --------------------------------------------------------------------------------

def group_factor(bone_name):
    n = bone_name.replace("mixamorig:", "")
    if n == "Hips":
        return HIPS
    if n.startswith("Spine"):
        return SPINE
    if n == "Neck":
        return NECK
    if n.startswith("Head"):
        return 1.0
    if any(k in n for k in ("UpLeg", "Leg", "Foot", "Toe")):
        return LEG
    if any(k in n for k in ("Shoulder", "Arm")):
        return ARM
    return HAND  # hands and fingers


def shrink_skeleton(arm):
    """Chibi proportions: scale each bone's length and its children's offsets, keep directions and rolls."""
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    bones = arm.data.edit_bones
    orig = {b.name: (b.head.copy(), b.tail.copy()) for b in bones}
    new_head = {}
    def place(bone):
        head, tail = orig[bone.name]
        if bone.parent is None:
            new_head[bone.name] = Vector((head.x, head.y * LEG, head.z))  # armature space is Y-up
        else:
            p_head = orig[bone.parent.name][0]
            new_head[bone.name] = new_head[bone.parent.name] + (head - p_head) * group_factor(bone.parent.name)
        roll = bone.roll
        bone.use_connect = False
        bone.head = new_head[bone.name]
        bone.tail = new_head[bone.name] + (tail - head) * group_factor(bone.name)
        bone.roll = roll
        for child in bone.children:
            place(child)
    for root in [b for b in bones if b.parent is None]:
        place(root)
    bpy.ops.object.mode_set(mode="OBJECT")


def bone_world(arm, name, end="head"):
    bone = arm.data.bones[name]
    return arm.matrix_world @ (bone.head_local if end == "head" else bone.tail_local)


def join_and_skin(arm, parts):
    """One mesh for the whole body, each part fully weighted to its bone. It moves like rigid parts riding
    their bones, but draws in one call per material instead of one per part."""
    for part, bone_name in parts:
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = part
        part.select_set(True)
        for mod in list(part.modifiers):
            bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        group = part.vertex_groups.new(name=bone_name)
        group.add(range(len(part.data.vertices)), 1.0, "REPLACE")
    bpy.ops.object.select_all(action="DESELECT")
    for part, _ in parts:
        part.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name = "Body"
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE", keep_transform=True)  # the weights are already there
    return body


def build_body(arm):
    B = lambda n, end="head": bone_world(arm, "mixamorig:" + n, end)
    parts = []
    hips, spine2, neck, head = B("Hips"), B("Spine2", "tail"), B("Neck"), B("Head")
    # Torso: a soft bean from the hips up to the shoulders.
    parts.append((ellipsoid("Pelvis", hips + Vector((0, 0, 0.02)), (0.13, 0.105, 0.085), "cream"), "Hips"))
    parts.append((ellipsoid("Torso", (hips + spine2) / 2 + Vector((0, 0, 0.02)), (0.145, 0.12, 0.16), "cream"),
                  "Spine1"))
    # Head: a rounded TV-like box, its screen face looking forward (-Y), a halo above.
    centre = head + Vector((0, 0, 0.19))
    parts.append((rounded_box("Head", centre, (0.58, 0.48, 0.44), 0.11, "cream"), "Head"))
    front = centre.y - 0.24  # the head's flat front
    parts.append((rounded_box("Screen", Vector((centre.x, front + 0.006, centre.z - 0.005)), (0.40, 0.03, 0.27), 0.085,
                              "screen"), "Head"))
    face = front - 0.011  # the screen's surface
    for side in (-1, 1):
        parts.append((ellipsoid(f"Eye{'L' if side < 0 else 'R'}", Vector((centre.x + side * 0.08, face, centre.z + 0.02)),
                                (0.036, 0.008, 0.056), "eye", segments=12, rings=6), "Head"))
        parts.append((ellipsoid(f"Cheek{'L' if side < 0 else 'R'}", Vector((centre.x + side * 0.135, face, centre.z - 0.05)),
                                (0.026, 0.005, 0.016), "blush", segments=8, rings=5), "Head"))
    parts.append((smile(Vector((centre.x, face, centre.z - 0.035))), "Head"))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.17, minor_radius=0.02, major_segments=24, minor_segments=6,
                                     location=centre + Vector((0, 0.02, 0.33)), rotation=(math.radians(12), 0, 0))
    halo = finish(bpy.context.active_object, "gold")
    halo.name = "Halo"
    parts.append((halo, "Head"))
    parts.append((limb("Neck", neck, head + Vector((0, 0, 0.03)), 0.05, "cream"), "Neck"))
    # Arms and legs: beans, with coral mittens and boots.
    for side in ("Left", "Right"):
        parts.append((limb(f"{side}UpperArm", B(f"{side}Arm"), B(f"{side}ForeArm"), 0.05, "cream"), f"{side}Arm"))
        parts.append((limb(f"{side}Forearm", B(f"{side}ForeArm"), B(f"{side}Hand"), 0.045, "cream"),
                      f"{side}ForeArm"))
        hand = B(f"{side}Hand") + (B(f"{side}Hand", "tail") - B(f"{side}Hand")) * 0.6
        parts.append((ellipsoid(f"{side}Mitten", hand, (0.06, 0.05, 0.065), "coral"), f"{side}Hand"))
        parts.append((limb(f"{side}Thigh", B(f"{side}UpLeg"), B(f"{side}Leg"), 0.062, "cream"), f"{side}UpLeg"))
        parts.append((limb(f"{side}Shin", B(f"{side}Leg"), B(f"{side}Foot"), 0.058, "cream"), f"{side}Leg"))
        foot, toe = B(f"{side}Foot"), B(f"{side}ToeBase")
        boot_centre = Vector(((foot.x + toe.x) / 2, (foot.y + toe.y) / 2 - 0.01, 0.045))
        parts.append((ellipsoid(f"{side}Boot", boot_centre, (0.07, 0.105, 0.05), "coral"), f"{side}Foot"))
    join_and_skin(arm, [(part, "mixamorig:" + bone) for part, bone in parts])


def leave_out_unused_bones(arm):
    """Mark the bones no body part hangs on (the fingers inside the mittens, the end bones) as not deforming, so
    the export leaves them and their animation out: they were more than half of godling.glb."""
    used = {group.name for obj in bpy.data.objects if obj.type == "MESH" for group in obj.vertex_groups}

    def needed(bone):
        return bone.name in used or any(needed(child) for child in bone.children)

    unused = [bone for bone in arm.data.bones if not needed(bone)]
    for bone in unused:
        bone.use_deform = False
    return len(unused)


def source_file(candidates):
    return next((SOURCE / f for f in candidates if (SOURCE / f).exists()), None)


def make_clip(arm, raw, name, frames, seconds, opts, standing):
    """One game clip from a Mixamo source: trimmed, kept on the spot, its bend softened, retimed. `standing` is the
    hips' height when standing, in the source's units."""
    action = raw.copy()
    action.name = name
    first, last = frames or (int(round(raw.frame_range[0])), int(round(raw.frame_range[1])))
    keep_frames(action, first, last)
    span = last - first
    if "cut" in opts:
        a, b = opts["cut"]
        cut_frames(action, a - first + 1, b - first + 1)
        span -= b - a - 1
    if opts.get("pingpong"):
        ping_pong(action, span + 1)
        span *= 2
    if opts.get("still"):
        remove_drift(action, axes=(0, 2))
    if opts.get("settle"):
        settle_hips(action, standing)
    if opts.get("upright"):
        print(f"UPRIGHT {name}: tipped {stand_upright(arm, action):.0f} degrees")
    if opts.get("face"):
        print(f"FACE {name}: turned {face_forward(arm, action):.0f} degrees")
    if "bend" in opts:
        soften(action, BENDING, opts["bend"])
        soften_hips(arm, action, opts["bend"])
    if seconds:
        retime(action, span / FPS / seconds)
    action.use_fake_user = True
    return action


def stride_speed(arm, walk):
    """How fast the Walk clip's planted foot slides back, in model units per second: the speed the body must move
    for the feet not to slide (the renderer's WALK_STRIDE_SPEED)."""
    use_clip(arm, walk)
    scene = bpy.context.scene
    first, last = (int(round(f)) for f in walk.frame_range)
    speeds = []
    for side in ("Left", "Right"):
        toe = arm.pose.bones[f"mixamorig:{side}ToeBase"]
        track = []
        for f in range(first, last + 1):
            scene.frame_set(f)
            track.append(arm.matrix_world @ toe.head)
        low = min(p.z for p in track)
        for a, b in zip(track, track[1:]):
            if a.z < low + 0.01 and b.z < low + 0.01:
                speeds.append((b.xy - a.xy).length * FPS)
    speeds.sort()
    return speeds[len(speeds) // 2] if speeds else 0.0


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = FPS

    arm, old_walk = import_clip(SOURCE / "walking.fbx", "WalkingSource")  # the skeleton every clip shares
    arm.name = "Godling"
    raws = {"walking.fbx": old_walk}
    for _, candidates, *_ in CLIPS:
        path = source_file(candidates)
        if path and path.name not in raws:
            other, raws[path.name] = import_clip(path, path.stem + "Source")
            bpy.data.objects.remove(other, do_unlink=True)

    standing = next(fc for fc in hips_location_curves(old_walk) if fc.array_index == 1).keyframe_points[0].co.y
    clips = []
    for name, candidates, frames, seconds, opts in CLIPS:
        path = source_file(candidates)
        if not path:
            print("SKIP", name, "(no source in art/source:", ", ".join(candidates) + ")")
            continue
        if name == "Walk" and path.name == "walking.fbx":
            action = old_walk.copy()
            action.name = "Walk"
            remove_drift(action)
        else:
            action = make_clip(arm, raws[path.name], name, frames, seconds, opts, standing)
        spread_arms(arm, action)
        if "ease" in opts and clips and clips[0].name == "Idle":
            ease_from(action, first_pose(clips[0]), *opts["ease"])
        clips.append(action)
    names = [a.name for a in clips]
    if "Idle" not in names:  # a calm stance from the start of the pick-up clip, played forth and back
        idle = raws["picking_up.fbx"].copy()
        idle.name = "Idle"
        keep_frames(idle, 1, IDLE_FRAMES)
        ping_pong(idle, IDLE_FRAMES)
        clips.insert(0, idle)
    for action in clips:
        scale_hips(action, LEG)
        action.use_fake_user = True
    for raw in raws.values():
        bpy.data.actions.remove(raw)

    arm.animation_data.action = None
    for pb in arm.pose.bones:  # parts are built and attached in the rest pose
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    shrink_skeleton(arm)
    arm.data.pose_position = "REST"
    build_body(arm)
    arm.data.pose_position = "POSE"
    idle = next(a for a in clips if a.name == "Idle")
    clips.append(posed_clip(arm, "Strike", STRIKE, idle))  # what the renderer plays for a strike with no clip of its own
    if "Climb" not in names:
        clips.append(posed_clip(arm, "Climb", CLIMB, idle))

    # One NLA track per clip, so the exporter writes them all as separate animations.
    for action in clips:
        track = arm.animation_data.nla_tracks.new()
        track.name = action.name
        strip = track.strips.new(action.name, 1, action)
        strip.name = action.name
        if hasattr(strip, "action_slot") and action.slots:
            strip.action_slot = action.slots[0]
        track.mute = True
    stride = stride_speed(arm, next(a for a in clips if a.name == "Walk"))
    use_clip(arm, idle)

    unused = leave_out_unused_bones(arm)

    OUT_GLB.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    # Sampled at 30 fps (frame step 2): the renderer interpolates between keys, and it halves the clips' size.
    bpy.ops.export_scene.gltf(filepath=str(OUT_GLB), export_format="GLB", export_apply=True,
                              export_animations=True, export_animation_mode="NLA_TRACKS",
                              export_force_sampling=True, export_frame_step=2, export_def_bones=True,
                              export_yup=True)
    print("WROTE", OUT_GLB, OUT_GLB.stat().st_size, "bytes", f"({unused} unused bones left out)")
    for action in clips:
        first, last = action.frame_range
        print(f"CLIP {action.name}: frames {first:.0f}-{last:.0f}, {(last - first) / FPS:.2f} s")
    print(f"WALK_STRIDE_SPEED {stride:.3f} model units per second")


main()
