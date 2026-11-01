"""Render preview stills of a built model (Blender, background):

    blender --background art/godling.blend --python art/render_preview.py -- godling
    blender --background art/props.blend --python art/render_preview.py -- props

Writes art/previews/<name>_<view>.png.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ART = Path(__file__).resolve().parent
name = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "preview"
scene = bpy.context.scene


def setup():
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 48
    scene.render.resolution_x = scene.render.resolution_y = 900
    scene.render.film_transparent = False
    world = bpy.data.worlds.get("Preview") or bpy.data.worlds.new("Preview")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.62, 0.78, 0.92, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    scene.world = world
    sun = bpy.data.objects.get("PreviewSun")
    if not sun:
        sun = bpy.data.objects.new("PreviewSun", bpy.data.lights.new("PreviewSun", "SUN"))
        scene.collection.objects.link(sun)
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    if not bpy.data.objects.get("PreviewGround"):
        bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
        ground = bpy.context.active_object
        ground.name = "PreviewGround"
        mat = bpy.data.materials.new("PreviewGround")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.33, 0.8, 0.62, 1)
        ground.data.materials.append(mat)


def bounds():
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for ob in scene.objects:
        if ob.type != "MESH" or ob.name.startswith("Preview") or ob.hide_render:
            continue
        ev = ob.evaluated_get(depsgraph)
        for corner in ev.bound_box:
            p = ev.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    return lo, hi


def shoot(view, azimuth_deg, elevation_deg=12):
    lo, hi = bounds()
    centre = (lo + hi) / 2
    size = max(hi - lo)
    cam = bpy.data.objects.get("PreviewCam")
    if not cam:
        cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
        scene.collection.objects.link(cam)
    cam.data.lens = 60
    distance = size * 2.4
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    cam.location = centre + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * distance
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    out = ART / "previews" / f"{name}_{view}.png"
    scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    print("PREVIEW", out)


def clip(action_name, frame):
    arm = next((o for o in scene.objects if o.type == "ARMATURE"), None)
    action = bpy.data.actions.get(action_name)
    if arm and action:
        arm.animation_data.action = action
        if hasattr(arm.animation_data, "action_slot") and action.slots:
            arm.animation_data.action_slot = action.slots[0]
        scene.frame_set(frame)


setup()
if name == "godling":
    clip("Idle", 1)
    shoot("front", 20)
    shoot("side", 90)
    clip("Walk", 16)
    shoot("walk", 35)
    for frame in (20, 40, 70):
        clip("PickUp", frame)
        shoot(f"pickup{frame}", 35)
    for frame in (20, 31):
        clip("Strike", frame)
        shoot(f"strike{frame}", 40)
    for frame in (1, 31):
        clip("Climb", frame)
        shoot(f"climb{frame}", 30)
else:
    shoot("all", 25, 18)
    models = [o for o in scene.objects if o.type == "MESH" and not o.name.startswith("Preview")]
    for model in models:
        for other in models:
            other.hide_render = other is not model
        shoot(model.name.lower(), 30, 20)
    for model in models:
        model.hide_render = False
