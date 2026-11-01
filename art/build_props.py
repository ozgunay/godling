"""Build the world props in Blender (background mode):

    blender --background --factory-startup --python art/build_props.py

Props in the same soft vinyl-toy style as Godling: a tree, a log and an axe; for quarrying a hammer, the
quarry outcrop, a rough stone cube and a long stone brick. Each is one mesh, exported on its own. The world's
renderer scales a model so its height matches the height of the part that carries it, so each model keeps
its part's proportions (and long axis; Blender Y becomes the model's Z).

Writes world/assets/{tree,stump,log,axe,hammer,quarry,stone,brick,boulder,ladder}.glb and art/props.blend.
"""
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, noise

ART = Path(__file__).resolve().parent
ASSETS = ART.parent / "world" / "assets"

PALETTE = {  # as seen on screen (sRGB)
    "bark": dict(color=(0.52, 0.34, 0.22), roughness=0.75),
    "leaf": dict(color=(0.38, 0.74, 0.36), roughness=0.6),
    "leaf_dark": dict(color=(0.27, 0.6, 0.31), roughness=0.6),
    "leaf_light": dict(color=(0.55, 0.83, 0.4), roughness=0.6),
    "heartwood": dict(color=(0.93, 0.76, 0.52), roughness=0.6),
    "ring": dict(color=(0.74, 0.53, 0.32), roughness=0.6),
    "handle": dict(color=(0.78, 0.56, 0.34), roughness=0.55),
    "grip": dict(color=(1.0, 0.45, 0.33), roughness=0.5),
    "steel": dict(color=(0.66, 0.7, 0.76), roughness=0.3, metallic=0.85),
    "edge": dict(color=(0.9, 0.93, 0.96), roughness=0.2, metallic=0.9),
    "iron": dict(color=(0.4, 0.42, 0.47), roughness=0.35, metallic=0.8),
    # Stone colours are lighter than they look right here: the world's renderer uses filmic tone mapping,
    # which darkens greys a lot, so mid greys came out charcoal in game.
    "rock": dict(color=(0.76, 0.73, 0.68), roughness=0.85),
    "rock_dark": dict(color=(0.63, 0.61, 0.58), roughness=0.85),
    "fresh_cut": dict(color=(0.93, 0.89, 0.81), roughness=0.7),
    "granite": dict(color=(0.7, 0.72, 0.76), roughness=0.8),
}


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
    return mat


def paint(obj, mat_name, smooth=True):
    obj.data.materials.append(material(mat_name))
    for poly in obj.data.polygons:
        poly.use_smooth = smooth
    return obj


def blob(centre, radius, mat_name, squash=1.0):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=14, radius=radius, location=centre)
    obj = bpy.context.active_object
    obj.scale = (1, 1, squash)
    return paint(obj, mat_name)


def join(objects, name):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    return obj


def tree():
    parts = []
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.24, radius2=0.14, depth=2.6, location=(0, 0, 1.3))
    parts.append(paint(bpy.context.active_object, "bark"))
    parts.append(blob((0, 0, 0.08), 0.3, "bark", squash=0.35))  # root flare
    for centre, radius, mat in [((0, 0, 3.05), 0.82, "leaf"), ((0.55, 0.2, 2.7), 0.55, "leaf_dark"),
                                ((-0.5, -0.25, 2.78), 0.58, "leaf_dark"), ((0.1, 0.35, 3.6), 0.52, "leaf_light"),
                                ((-0.22, -0.42, 3.45), 0.44, "leaf_light")]:
        parts.append(blob(centre, radius, mat))
    return join(parts, "Tree")


def ringed_cylinder(name, radius, depth, rotation=(0, 0, 0), location=(0, 0, 0), caps="both"):
    """A wooden cylinder: bark sides, and growth rings on its cut end(s)."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    for mat in ("bark", "heartwood", "ring"):
        obj.data.materials.append(material(mat))
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    ends = [f for f in bm.faces if len(f.verts) > 4]
    if caps == "top":
        ends = [max(ends, key=lambda f: f.calc_center_median().z)]
    for f in bm.faces:
        f.smooth = len(f.verts) <= 4
        f.material_index = 0
    # An outer band of heartwood, a darker ring, a light centre.
    for thickness, mat in ((radius * 0.15, 1), (radius * 0.25, 2), (radius * 0.12, 1)):
        for f in bmesh.ops.inset_individual(bm, faces=ends, thickness=thickness)["faces"]:
            f.material_index, f.smooth = mat if mat == 2 else 1, False
        for f in ends:
            f.material_index, f.smooth = 1, False
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def log():
    """A log lying along X, six times as long as it is thick, like its 3.0 x 0.5 x 0.5 cylinder part."""
    obj = ringed_cylinder("Log", 0.2, 2.4, rotation=(0, math.radians(90), 0))
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return obj


def stump():
    """What a felled tree leaves: 1.4 across with its roots, 0.6 tall (its part), a cut top showing the rings."""
    parts = [ringed_cylinder("StumpTrunk", 0.46, 0.5, location=(0, 0, 0.33), caps="top")]
    parts.append(blob((0, 0, 0.1), 0.56, "bark", squash=0.3))  # the flare where trunk meets ground
    for i in range(5):
        a = math.radians(i * 72 + 18)
        root = blob((math.cos(a) * 0.5, math.sin(a) * 0.5, 0.06), 0.2, "bark", squash=0.45)
        root.scale = (1.0, 0.55, 0.45)
        root.rotation_euler = (0, 0, a)
        parts.append(root)
    return join(parts, "Stump")


def boulder_ball():
    """A heavy round rock for a 1.6 ball part: lumpy, with a few worn flat facets, but round enough to roll."""
    facets = [((0.62, 0, 0), (1, 0.2, 0.1)), ((0, -0.62, 0.1), (-0.2, -1, 0.3)), ((-0.3, 0.3, 0.55), (-0.4, 0.4, 1))]
    return boulder((0, 0, 0.8), (0.82, 0.82, 0.8), 13.0, "rock_dark", cuts=facets, rough=0.8, cut_mat="rock")


def axe():
    """An axe lying on its side like its 0.4 x 0.4 x 1.0 part: handle along Y, the blade pointing up (Z)."""
    parts = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.035, depth=0.9, location=(0, -0.05, 0),
                                        rotation=(math.radians(90), 0, 0))
    parts.append(paint(bpy.context.active_object, "handle"))
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.043, depth=0.21, location=(0, -0.4, 0),
                                        rotation=(math.radians(90), 0, 0))  # just past the handle's end: no flicker
    parts.append(paint(bpy.context.active_object, "grip"))
    # Head: a block across the handle's end that flares into a blade on the upper side.
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.33, 0.08))
    head = bpy.context.active_object
    head.scale = (0.075, 0.15, 0.36)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bm = bmesh.new()
    bm.from_mesh(head.data)
    for v in bm.verts:
        if v.co.z > 0:  # blade side: thin and wide
            v.co.x *= 0.25
            v.co.y *= 1.55
    bm.to_mesh(head.data)
    bm.free()
    bevel = head.modifiers.new("bevel", "BEVEL")
    bevel.width, bevel.segments = 0.012, 3
    parts.append(paint(head, "steel", smooth=False))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.33, 0.26))  # bright cutting edge
    edge = bpy.context.active_object
    edge.scale = (0.022, 0.23, 0.014)
    parts.append(paint(edge, "edge", smooth=False))
    for ob in parts:
        ob.select_set(True)
    with bpy.context.temp_override(object=head, active_object=head, selected_objects=[head]):
        bpy.ops.object.modifier_apply(modifier="bevel")
    return join(parts, "Axe")


def hammer():
    """A stonemason's hammer lying on its side: 1.2 long (Y), 0.4 tall (the head), as its 0.4 x 0.4 x 1.2 part."""
    parts = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.045, depth=1.0, location=(0, -0.1, 0),
                                        rotation=(math.radians(90), 0, 0))
    parts.append(paint(bpy.context.active_object, "handle"))
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.055, depth=0.22, location=(0, -0.48, 0),
                                        rotation=(math.radians(90), 0, 0))
    parts.append(paint(bpy.context.active_object, "grip"))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.47, 0))
    head = bpy.context.active_object
    head.scale = (0.2, 0.22, 0.34)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = head.modifiers.new("bevel", "BEVEL")
    bevel.width, bevel.segments = 0.03, 3
    with bpy.context.temp_override(object=head, active_object=head, selected_objects=[head]):
        bpy.ops.object.modifier_apply(modifier="bevel")
    parts.append(paint(head, "iron", smooth=False))
    for z in (-0.185, 0.185):  # worn, bright striking faces at both ends of the head
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.085, depth=0.03, location=(0, 0.47, z))
        parts.append(paint(bpy.context.active_object, "edge", smooth=False))
    return join(parts, "Hammer")


def ladder():
    """A wooden ladder standing upright, shaped like its 1.5 x 7.5 x 0.4 part: 0.9 wide (X) per 4.5 tall (Z),
    0.17 deep (Y), with 8 rungs along X."""
    parts = []
    for x in (-0.39, 0.39):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 0, 2.25))
        rail = bpy.context.active_object
        rail.scale = (0.12, 0.16, 4.4)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bevel = rail.modifiers.new("bevel", "BEVEL")
        bevel.width, bevel.segments = 0.04, 3
        with bpy.context.temp_override(object=rail, active_object=rail, selected_objects=[rail]):
            bpy.ops.object.modifier_apply(modifier="bevel")
        parts.append(paint(rail, "handle"))
        for z in (0.04, 4.46):  # little coral caps on the feet and tops of the rails
            parts.append(blob((x, 0, z), 0.085, "grip", squash=0.55))
    for i in range(8):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.05, depth=0.74, location=(0, 0, 0.45 + i * 0.52),
                                            rotation=(0, math.radians(90), 0))
        parts.append(paint(bpy.context.active_object, "heartwood"))
    return join(parts, "Ladder")


def boulder(centre, radii, seed, mat_name, cuts=(), rough=1.0, cut_mat="fresh_cut"):
    """A soft lumpy rock; each cut (point, normal) slices it flat and caps the cut (fresh, pale stone by default)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    offset = Vector((seed, seed * 0.37, seed * 0.71))
    for v in bm.verts:
        bump = 1 + rough * (0.2 * noise.noise(v.co * 1.6 + offset) + 0.07 * noise.noise(v.co * 4.5 + offset))
        v.co = Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2])) * bump
    for point, normal in cuts:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        result = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(point), plane_no=Vector(normal),
                                        clear_outer=True)
        edges = [e for e in result["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        capped = bmesh.ops.holes_fill(bm, edges=edges, sides=0)["faces"]
        for f in capped:
            f.material_index = 1
    mesh = bpy.data.meshes.new("Boulder")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Boulder", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = centre
    mesh.materials.append(material(mat_name))
    mesh.materials.append(material(cut_mat))
    for poly in mesh.polygons:
        poly.use_smooth = poly.material_index == 0
    return obj


def quarry():
    """A rocky outcrop with freshly cut faces and rubble at its foot: 6 wide (X), 5 deep (Y), 3.5 tall (Z)."""
    # Cut planes only shave the outside of a rock: a quarried face where stone was taken, and a bench above it.
    parts = [
        boulder((0, 0.35, 1.45), (2.3, 1.8, 1.7), 1.0, "rock",
                cuts=[((0, -1.45, 0), (0, -1, 0.05)), ((0, 0, 1.25), (0, -0.55, 1)), ((2.0, 0, 0), (1, -0.15, 0.1))]),
        boulder((-1.8, -0.6, 0.85), (1.15, 1.05, 0.95), 4.0, "rock_dark", cuts=[((0, -0.8, 0), (-0.2, -1, 0.1))]),
        boulder((1.85, -0.95, 0.75), (1.05, 0.95, 0.8), 7.0, "rock", cuts=[((0, 0, 0.6), (0.15, -0.3, 1))]),
        boulder((0.3, 0.7, 2.85), (0.55, 0.5, 0.42), 9.0, "rock_dark"),
    ]
    rubble = [((-2.6, -1.9, 0.14), 0.2), ((-2.2, -2.3, 0.1), 0.13), ((-0.9, -2.2, 0.12), 0.17),
              ((0.6, -2.35, 0.1), 0.14), ((2.5, -2.1, 0.13), 0.19), ((2.8, -1.5, 0.1), 0.12),
              ((2.7, 1.0, 0.12), 0.16), ((-2.8, 0.8, 0.12), 0.17), ((-1.5, -2.45, 0.09), 0.11),
              ((1.4, -2.2, 0.11), 0.15), ((-2.9, -0.6, 0.1), 0.13), ((0.0, -2.4, 0.08), 0.1)]
    for i, (centre, size) in enumerate(rubble):
        parts.append(boulder(centre, (size * 1.25, size, size * 0.85), 20.0 + i, "rock_dark" if i % 2 else "rock",
                             cuts=[((0, 0, size * 0.45), (0.3, -0.4, 1))] if i % 3 == 0 else ()))
    # Broken-off chunks at the foot of the face: what the quarry gives.
    for i, (x, y, yaw) in enumerate([(-0.6, -1.95, 20), (0.35, -2.05, -15), (-0.1, -1.75, 50)]):
        chunk = rough_block(f"Chunk{i}", (0.42, 0.36, 0.3), 30.0 + i, mat_name="fresh_cut")
        chunk.location = (x, y, 0.15)
        chunk.rotation_euler = (0, 0, math.radians(yaw))
        parts.append(chunk)
    return join(parts, "Quarry")


def rough_block(name, size, seed, mat_name="granite"):
    """A rough-cut stone: a bevelled box with chiselled, uneven faces and chipped edges."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=min(size) * 0.1, segments=2, affect="EDGES",
                    profile=0.6)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if e.calc_length() > min(size) * 0.35], cuts=3,
                              use_grid_fill=True)
    half = Vector(size) / 2
    offset = Vector((seed, seed * 1.3, seed * 0.7))
    for v in bm.verts:
        n = noise.noise(v.co * 5.0 / min(size) + offset) + 0.5 * noise.noise(v.co * 13.0 / min(size) + offset)
        v.co -= v.normal * min(size) * 0.045 * (1.2 + n)  # dents, never bulges: the stone stays inside its part
        v.co = Vector((max(-half.x, min(half.x, v.co.x)), max(-half.y, min(half.y, v.co.y)),
                       max(-half.z, min(half.z, v.co.z))))
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mesh.materials.append(material(mat_name))
    for poly in mesh.polygons:
        poly.use_smooth = False
    return obj


def export(obj, filename):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(ob == obj)
    path = ASSETS / filename
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_apply=True,
                              export_animations=False, export_yup=True)
    print("WROTE", path, path.stat().st_size, "bytes")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    made = {"tree.glb": tree(), "log.glb": log(), "axe.glb": axe(), "hammer.glb": hammer(), "quarry.glb": quarry(),
            "stone.glb": rough_block("Stone", (0.75, 0.75, 0.75), 3.0),
            "brick.glb": rough_block("Brick", (1.5, 0.75, 0.75), 5.0), "ladder.glb": ladder(),
            "boulder.glb": boulder_ball(), "stump.glb": stump()}
    for filename, obj in made.items():
        obj.location = (0, 0, 0)
        export(obj, filename)
        dims = obj.dimensions
        print(f"SIZE {filename}: x {dims.x:.2f}, y {dims.y:.2f}, z {dims.z:.2f} (Blender; the model's Z is -y)")
    # Side by side for the preview render, each resting on the ground (a model's origin is wherever its first
    # piece was; the world's renderer centres models by their bounds, so this matters only here).
    layout = {"tree.glb": (0, 0), "log.glb": (1.6, -0.4), "axe.glb": (-1.3, -0.3), "quarry.glb": (7, 4),
              "hammer.glb": (4.2, -1.2), "stone.glb": (5.2, -1.6), "brick.glb": (6.6, -1.4), "ladder.glb": (-3.2, 1.2),
              "boulder.glb": (3.0, 2.0), "stump.glb": (-1.6, 2.6)}
    for filename, (x, y) in layout.items():
        obj = made[filename]
        obj.location = (x, y, 0)
        bpy.context.view_layer.update()
        obj.location.z -= min((obj.matrix_world @ Vector(corner)).z for corner in obj.bound_box)
    bpy.ops.wm.save_as_mainfile(filepath=str(ART / "props.blend"))


main()
