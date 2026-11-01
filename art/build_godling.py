"""Build Godling, the mascot, in Blender (background mode, no UI needed):

    blender --background --factory-startup --python art/build_godling.py

Original design: a chubby cream vinyl-toy figure with a rounded TV-like head, a dark screen face with two
glowing mint eyes, a small gold halo, and coral mitten-hands and boots.

Rig: the Mixamo skeleton from art/source, shrunk to chibi proportions (bone directions and rolls kept, so
the Mixamo clips still play on it). Every body part is rigid and moves with one bone: a toy, not skin. The
parts are joined into one mesh, each fully weighted to its bone, so the body draws in one call per material.

Budget (it has to run in phone browsers): about 5k triangles in all.

Clips (60 fps): Idle (a calm stance), Walk (in place: the world moves the body), PickUp (reach down and
lift, sped up to about 2 s) from the Mixamo sources; Strike (a two-handed overhead swing, 1.0 s) and Climb
(hand over hand, a 1.0 s loop) posed by hand on the same rig.

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
PICKUP_FROM, PICKUP_TO, PICKUP_SPEEDUP = 40, 370, 2.6  # source frames of the actual reach-and-lift
IDLE_FRAMES = 30  # source frames 1..30 of the pick-up clip are a calm stance; played forth and back

PICKUP_BEND = 0.35  # an adult's pick-up bends the back ~90°: with a big head that is a face-plant
BENDING = ("Spine", "Spine1", "Spine2", "Neck", "Head")

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


def remove_drift(action):
    """Walk in place: take out the steady forward travel of the hips, keep the bob and sway."""
    for fc in hips_location_curves(action):
        keys = list(fc.keyframe_points)
        (f0, v0), (f1, v1) = keys[0].co, keys[-1].co
        slope = (v1 - v0) / (f1 - f0)
        for kp in keys:
            for point in (kp.co, kp.handle_left, kp.handle_right):
                point.y -= slope * (point.x - f0)
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


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 60

    arm, walk = import_clip(SOURCE / "walking.fbx", "Walk")
    arm.name = "Godling"
    other, raw = import_clip(SOURCE / "picking_up.fbx", "PickUpSource")
    bpy.data.objects.remove(other, do_unlink=True)

    pick = raw.copy()
    pick.name = "PickUp"
    keep_frames(pick, PICKUP_FROM, PICKUP_TO)
    soften(pick, BENDING, PICKUP_BEND)
    soften_hips(arm, pick, PICKUP_BEND)
    retime(pick, PICKUP_SPEEDUP)
    idle = raw.copy()
    idle.name = "Idle"
    keep_frames(idle, 1, IDLE_FRAMES)
    ping_pong(idle, IDLE_FRAMES)
    remove_drift(walk)
    for action in (walk, pick, idle):
        scale_hips(action, LEG)
        action.use_fake_user = True
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
    strike = posed_clip(arm, "Strike", STRIKE, idle)
    climb = posed_clip(arm, "Climb", CLIMB, idle)

    # One NLA track per clip, so the exporter writes them all as separate animations.
    for action in (idle, walk, pick, strike, climb):
        track = arm.animation_data.nla_tracks.new()
        track.name = action.name
        strip = track.strips.new(action.name, 1, action)
        strip.name = action.name
        if hasattr(strip, "action_slot") and action.slots:
            strip.action_slot = action.slots[0]
        track.mute = True
    use_clip(arm, idle)

    OUT_GLB.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    bpy.ops.export_scene.gltf(filepath=str(OUT_GLB), export_format="GLB", export_apply=True,
                              export_animations=True, export_animation_mode="NLA_TRACKS",
                              export_force_sampling=True, export_yup=True)
    print("WROTE", OUT_GLB, OUT_GLB.stat().st_size, "bytes")
    for action in (idle, walk, pick, strike, climb):
        print("CLIP", action.name, tuple(action.frame_range))


main()
