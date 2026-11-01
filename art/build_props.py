"""Build the world props in Blender (background mode):

    blender --background --factory-startup --python art/build_props.py

Props in the same soft vinyl-toy style as Godling: a tree, a log and an axe; for quarrying a hammer, the
quarry outcrop, a rough stone cube and a long stone brick. Each is one mesh, exported on its own. The world's
renderer scales a model so its height matches the height of the part that carries it, so each model keeps
its part's proportions (and long axis; Blender Y becomes the model's Z).

Writes world/assets/{tree,palm,stump,log,axe,hammer,quarry,stone,brick,boulder,ladder}.glb and art/props.blend.
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
    "hewn": dict(color=(0.86, 0.66, 0.43), roughness=0.7),
    "palm_bark": dict(color=(0.66, 0.58, 0.48), roughness=0.8),  # coconut palms: grey-brown, faintly ringed
    "palm_bark_dark": dict(color=(0.57, 0.49, 0.4), roughness=0.8),
    "fin": dict(color=(0.22, 0.45, 0.8), roughness=0.5),
    "eye_white": dict(color=(0.95, 0.95, 0.92), roughness=0.3),
    "eye_dark": dict(color=(0.05, 0.05, 0.07), roughness=0.2),
    "ball_white": dict(color=(0.97, 0.97, 0.95), roughness=0.5),
    "ball_cream": dict(color=(0.93, 0.91, 0.85), roughness=0.5),
    "raft_yellow": dict(color=(1.0, 0.8, 0.16), roughness=0.55),
    "raft_orange": dict(color=(0.98, 0.52, 0.16), roughness=0.6),
    "raft_floor": dict(color=(0.82, 0.55, 0.14), roughness=0.7),
    "rope": dict(color=(0.32, 0.32, 0.34), roughness=0.9),
    "palm_leaf": dict(color=(0.42, 0.7, 0.3), roughness=0.6),
    "palm_leaf_dark": dict(color=(0.3, 0.56, 0.25), roughness=0.6),
    "coconut": dict(color=(0.45, 0.3, 0.17), roughness=0.6),
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
    # Granite is mottled and warm: a uniform pale blue-grey read as frosted glass in game, a "ghost box".
    "granite": dict(color=(0.67, 0.65, 0.61), roughness=1.0),
    "granite_dark": dict(color=(0.53, 0.51, 0.48), roughness=1.0),
    "granite_light": dict(color=(0.79, 0.77, 0.72), roughness=1.0),
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


def blob(centre, radius, mat_name, squash=1.0, segments=16, rings=8):
    """A soft sphere. Smooth shading keeps it round with few faces; trees and palms are drawn many times a frame,
    shadows included, so small blobs (coconuts, caps, roots) get fewer still."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=centre)
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
    """A tree whose clear trunk is about 60% of its height and about a twelfth as thick as the tree is tall, so a
    tree 22-24 units tall holds the two 7.5-long, 2.5-thick logs it is felled into (Minecraft scale, ADR-005)."""
    parts = []
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.27, radius2=0.16, depth=3.4, location=(0, 0, 1.7))
    parts.append(paint(bpy.context.active_object, "bark"))
    parts.append(blob((0, 0, 0.08), 0.34, "bark", squash=0.35, segments=12, rings=6))  # root flare
    lift = 0.8
    for centre, radius, mat in [((0, 0, 3.05), 0.82, "leaf"), ((0.55, 0.2, 2.7), 0.55, "leaf_dark"),
                                ((-0.5, -0.25, 2.78), 0.58, "leaf_dark"), ((0.1, 0.35, 3.6), 0.52, "leaf_light"),
                                ((-0.22, -0.42, 3.45), 0.44, "leaf_light")]:
        parts.append(blob((centre[0], centre[1], centre[2] + lift), radius, mat))
    return join(parts, "Tree")


def palm():
    """A coconut palm in the spirit of a castaway beach (style reference: Cast Away's island): a slim, ringed,
    grey-brown trunk that leans out and curves back up near the top, a tuft of long arching fronds, and coconuts.
    It fits the same 2.5 x 20 x 2.5 part as the trees, with the trunk's foot at the part's centre."""
    parts = []
    trunk_h, lean, segments = 4.0, 0.85, 16
    # Leans out (+X) and curves back towards upright near the top, as beach palms do.
    spine = [Vector((lean * math.sin(0.5 * math.pi * (i / segments)) ** 1.3, 0, trunk_h * i / segments))
             for i in range(segments + 1)]
    radius = lambda t: 0.13 - 0.04 * t
    for i in range(segments):
        a, b = spine[i], spine[i + 1]
        axis = b - a
        bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=radius(i / segments) * 1.08,
                                        radius2=radius((i + 1) / segments) * 0.97, depth=axis.length * 1.05,
                                        location=(a + b) / 2, end_fill_type="NOTHING")  # ends hide in the next ring
        seg = bpy.context.active_object
        seg.rotation_mode = "QUATERNION"
        seg.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(axis.normalized())
        parts.append(paint(seg, "palm_bark" if i % 2 else "palm_bark_dark"))  # faint ring scars
    parts.append(blob((0, 0, 0.05), 0.2, "palm_bark_dark", squash=0.4, segments=10, rings=5))  # the foot in the sand
    top = spine[-1]
    fronds = [(math.radians(k * 36), 1.75, 0.55, 0.95, "palm_leaf" if k % 2 else "palm_leaf_dark", 0.26)
              for k in range(10)]
    fronds += [(math.radians(k * 72 + 18), 1.25, 0.8, 0.75, "palm_leaf", 0.24) for k in range(5)]
    fronds += [(math.radians(k * 120 + 40), 0.65, 1.1, 0.4, "leaf_light", 0.22) for k in range(3)]  # young, upright
    for angle, length, rise, droop, mat, width in fronds:
        parts.append(frond(top, angle, length, rise, droop, mat, width=width))
    for k in range(5):
        a = math.radians(15 + k * 72)
        parts.append(blob((top.x + 0.1 * math.cos(a), 0.1 * math.sin(a), top.z - 0.12 - 0.04 * (k % 2)), 0.075,
                          "coconut", segments=8, rings=5))
    return join(parts, "Palm")


# ---- survival pieces (castaway features) ----------------------------------------------------

SPEAR_BOX = ((-0.15, -2.25, -0.15), (0.15, 2.25, 0.15))  # its part 0.3 x 0.3 x 4.5, long along the model's Z
FISH_BOX = ((-0.65, -0.25, -0.175), (0.65, 0.25, 0.175))  # its part 1.3 x 0.35 x 0.5: a fish lying on its side


def _vertex_colours(mesh, colour_at, name="Col"):
    """Colour every vertex (linear values from colour_at(co)) and give the mesh a material that shows them."""
    attr = mesh.color_attributes.new(name, "FLOAT_COLOR", "POINT")
    for v in mesh.vertices:
        attr.data[v.index].color = (*colour_at(v.co), 1.0)
    mat = bpy.data.materials.new(mesh.name + "_vc")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    node = mat.node_tree.nodes.new("ShaderNodeVertexColor")
    node.layer_name = name
    mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6
    mesh.materials.append(mat)
    return mat


def _mesh_object(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def coconut():
    """A brown husked coconut for a 0.9 ball part: a slightly oval, three-ridged, fibrous husk."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    for v in bm.verts:
        p = v.co.normalized()
        ridge = 1 + 0.06 * math.cos(3 * math.atan2(p.z, p.y))  # three faint ridges along the long axis
        fibre = 1 + 0.035 * noise.noise(p * 7.0)
        point = 1 + 0.06 * max(0.0, p.x) ** 4  # one end comes to a soft point
        v.co = Vector((p.x * 0.97 * point, p.y, p.z)) * 0.45 * ridge * fibre  # about as long as the ball is wide
    obj = _mesh_object("Coconut", bm)
    husk, dark = linear((0.55, 0.36, 0.2)), linear((0.36, 0.22, 0.12))
    _vertex_colours(obj.data, lambda co: tuple(h + (d - h) * max(0.0, min(1.0, 0.5 + 2.2 * noise.noise(co * 9.0)))
                                               for h, d in zip(husk, dark)))
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def spear():
    """A rough fishing spear whittled from a branch, 4.5 long along Y (the model's Z), the point at +Y: an
    eight-sided shaft that wanders a little, a few knots, and a carved point of paler, freshly cut wood."""
    parts = []
    sides, rings, length, r = 8, 18, 4.1, 0.085  # + the 0.2 point = 4.3; the knots and the rest fit inside 4.5
    bm = bmesh.new()
    loops = []
    for i in range(rings + 1):
        t = i / rings
        y = -length / 2 + length * t
        bend = Vector((0.03 * math.sin(t * 5.0), 0, 0.025 * math.sin(t * 3.3 + 1)))
        radius = r * (1 - 0.15 * t)
        loops.append([bm.verts.new(Vector((math.cos(2 * math.pi * k / sides) * radius, y,
                                           math.sin(2 * math.pi * k / sides) * radius)) + bend) for k in range(sides)])
    for l0, l1 in zip(loops, loops[1:]):
        for k in range(sides):
            bm.faces.new((l0[k], l1[k], l1[(k + 1) % sides], l0[(k + 1) % sides]))
    bm.faces.new(list(reversed(loops[0])))  # the butt end, cut flat
    tip = bm.verts.new(Vector((0.03 * math.sin(5.0), length / 2 + 0.2, 0.025 * math.sin(4.3))))
    for k in range(sides):  # the carved point, flat-faceted
        bm.faces.new((loops[-1][k], tip, loops[-1][(k + 1) % sides]))
    obj = _mesh_object("SpearShaft", bm)
    obj.data.materials.append(material("handle"))
    obj.data.materials.append(material("heartwood"))
    for poly in obj.data.polygons:
        tipward = poly.center.y > length / 2 - 0.05
        poly.material_index = 1 if tipward else 0
        poly.use_smooth = not tipward
    parts.append(obj)
    for y, angle in ((-1.3, 30), (-0.2, 200), (0.9, 110)):  # knots where twigs were cut off
        a = math.radians(angle)
        parts.append(blob((math.cos(a) * r * 0.95, y, math.sin(a) * r * 0.95), 0.035, "bark", segments=8, rings=4))
    return join(parts, "Spear")


def fish(cooked=False):
    """A chubby reef fish lying on its side (its part is 1.3 long, 0.5 deep along Y, 0.35 thick along Z), head at +X:
    a rounded body, a forked tail, a dorsal fin and an eye. Raw: dark blue back to silver belly; cooked: browned with
    grill marks."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1.0)
    for v in bm.verts:
        x = v.co.x
        taper = 1 - 0.55 * max(0.0, -x) ** 1.6  # narrows towards the tail
        v.co = Vector((x * 0.48, v.co.y * 0.235 * taper, v.co.z * 0.16 * taper))
        v.co.x += 0.06
    body = _mesh_object("FishBody", bm)
    back, belly = ((0.6, 0.36, 0.18), (0.86, 0.62, 0.34)) if cooked else ((0.1, 0.3, 0.62), (0.9, 0.93, 0.97))
    back, belly = linear(back), linear(belly)
    mark = linear((0.3, 0.16, 0.08))

    def colour(co):
        t = max(0.0, min(1.0, 0.5 + co.y / 0.26))  # +Y is the back; a sharp line between back and belly
        c = tuple(b + (k - b) * t for b, k in zip(belly, back))
        if cooked and abs(math.sin(co.x * 22.0 - co.y * 9.0)) > 0.93:  # grill marks
            c = mark
        return c
    _vertex_colours(body.data, colour)
    for poly in body.data.polygons:
        poly.use_smooth = True
    fin_mat = "raft_orange" if cooked else "fin"
    parts = [body]
    # Tail: a forked fan. Dorsal fin: a low fan along the back. Both flat in the fish's plane (XY).
    def fan(name, root, tips, thickness=0.012):
        fb = bmesh.new()
        r0 = fb.verts.new(Vector(root) + Vector((0, 0, thickness)))
        r1 = fb.verts.new(Vector(root) - Vector((0, 0, thickness)))
        top = [fb.verts.new(Vector(t) + Vector((0, 0, thickness))) for t in tips]
        bot = [fb.verts.new(Vector(t) - Vector((0, 0, thickness))) for t in tips]
        for a, b in zip(range(len(tips)), range(1, len(tips))):
            fb.faces.new((r0, top[a], top[b]))
            fb.faces.new((r1, bot[b], bot[a]))
        return paint(_mesh_object(name, fb), fin_mat)
    parts.append(fan("Tail", (-0.4, 0, 0), [(-0.65, 0.22, 0), (-0.55, 0.06, 0), (-0.6, 0, 0), (-0.55, -0.06, 0),
                                              (-0.65, -0.22, 0)]))
    parts.append(fan("Dorsal", (0.12, 0.2, 0), [(-0.2, 0.2, 0), (-0.12, 0.25, 0), (0.0, 0.25, 0), (0.12, 0.24, 0),
                                                 (0.22, 0.2, 0)]))
    for side in (-1, 1):  # an eye on each side
        parts.append(blob((0.38, 0.06, side * 0.115), 0.04, "eye_white", squash=0.5, segments=8, rings=4))
        parts.append(blob((0.395, 0.06, side * 0.135), 0.022, "eye_dark", squash=0.5, segments=6, rings=4))
    return join(parts, "FishCooked" if cooked else "Fish")


def volleyball():
    """A plain white volleyball for a 1.1 ball part: the classic panels (each of a cube's six faces split into three
    strips, turned a quarter between neighbours) with soft grooves at the seams. No face and no brand mark."""
    n = 9  # cells per cube face edge; strips of three cells
    bm = bmesh.new()
    axes = [Vector(a) for a in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
    verts = {}
    for f, normal in enumerate(axes):
        u = Vector((normal.y, normal.z, normal.x))  # two directions across the face
        w = normal.cross(u)
        if f % 2:  # turn every other face a quarter so strips cross as on a real ball
            u, w = w, u
        grid = [[None] * (n + 1) for _ in range(n + 1)]
        for i in range(n + 1):
            for j in range(n + 1):
                p = (normal + u * (2 * i / n - 1) + w * (2 * j / n - 1)).normalized()
                seam = i % 3 == 0  # strip edges run along j
                key = tuple(round(c, 5) for c in p)
                if key not in verts:
                    verts[key] = bm.verts.new(p * 0.55 * (0.985 if seam else 1.0))
                grid[i][j] = verts[key]
        for i in range(n):
            for j in range(n):
                quad = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
                face = bm.faces.new(quad if (u.cross(w)).dot(normal) > 0 else tuple(reversed(quad)))
                face.material_index = (i // 3) % 2
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    obj = _mesh_object("Volleyball", bm)
    obj.data.materials.append(material("ball_white"))
    obj.data.materials.append(material("ball_cream"))
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


RAFT_LENGTH, RAFT_WIDTH, RAFT_HEIGHT = 5.0, 3.75, 1.25  # its part, {5, 1.25, 3.75} with X long


def _superellipse(t, a, b, n=4.0):
    """A rounded rectangle: the point at parameter t (0..2pi) of |x/a|^n + |y/b|^n = 1."""
    c, s = math.cos(t), math.sin(t)
    return Vector((a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s), 0))


def raft():
    """The busted yellow life raft a castaway washes up in: an inflatable ring, round at one end and collapsed flat
    and wrinkled at the other, a sagging floor, a collapsed canopy over the inflated end and a slack grab line."""
    tube = 0.42
    a, b = RAFT_LENGTH / 2 - tube * 1.3, RAFT_WIDTH / 2 - tube * 1.3
    steps, around = 64, 12
    path = [_superellipse(2 * math.pi * i / steps, a, b) for i in range(steps)]
    sag = lambda x: 0.32 + 0.68 * min(1.0, max(0.0, (x + a) / (1.4 * a)))  # 1 = full, low = deflated (-X end)
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(path):
        tangent = (path[(i + 1) % steps] - path[i - 1]).normalized()
        out = Vector((tangent.y, -tangent.x, 0))
        s = sag(p.x)
        rv, rh = tube * s, tube * (1 + 0.3 * (1 - s))  # a flat tube spreads sideways
        centre = Vector((p.x, p.y, rv))
        ring = []
        for j in range(around):
            th = 2 * math.pi * j / around
            wrinkle = 1 + (1 - s) * 0.12 * noise.noise(Vector((i * 0.7, j * 0.9, 3.0)))
            ring.append(bm.verts.new(centre + (out * math.cos(th) * rh + Vector((0, 0, math.sin(th) * rv))) * wrinkle))
        rings.append(ring)
    for i in range(steps):
        r0, r1 = rings[i], rings[(i + 1) % steps]
        for j in range(around):
            bm.faces.new((r0[j], r0[(j + 1) % around], r1[(j + 1) % around], r1[j]))
    mesh = bpy.data.meshes.new("RaftTube")
    bm.to_mesh(mesh)
    bm.free()
    tube_obj = bpy.data.objects.new("RaftTube", mesh)
    bpy.context.scene.collection.objects.link(tube_obj)
    parts = [paint(tube_obj, "raft_yellow")]
    parts.append(_raft_sheet("RaftFloor", a * 1.02, b * 1.02, lambda x, y: 0.05 + 0.03 * noise.noise(Vector((x * 2, y * 2, 1))),
                             "raft_floor", lambda x, y: True))
    # The canopy has fallen in over the inflated end: it rests on the tube and sags in the middle.
    def canopy(x, y):
        u, v = (x - a * 0.35) / (a * 0.75), y / (b * 1.05)
        dome = max(0.0, 1 - u * u - v * v)
        return tube * 2 * sag(x) + 0.28 * dome + 0.05 * noise.noise(Vector((x * 3, y * 3, 2)))
    parts.append(_raft_sheet("RaftCanopy", a + tube, b + tube, canopy, "raft_orange", lambda x, y: x > -a * 0.15))
    # A slack grab line looped along the outside of the tube.
    points = []
    for i in range(0, steps + 1):
        p = path[i % steps]
        tangent = (path[(i + 1) % steps] - path[i - 1]).normalized()
        out = Vector((tangent.y, -tangent.x, 0))
        s = sag(p.x)
        droop = 0.08 * abs(math.sin(i * math.pi / 6))
        points.append(p + out * tube * (1 + 0.3 * (1 - s)) * 1.02 + Vector((0, 0, tube * s * 1.1 - droop)))
    parts.append(_rope(points, 0.025, "rope"))
    return join(parts, "Raft")


def _raft_sheet(name, a, b, height, mat_name, keep, cells=20):
    """A sheet over the raft's rounded-rectangle plan, at the given height; faces outside `keep` are dropped."""
    bm = bmesh.new()
    grid = {}
    for i in range(cells + 1):
        for j in range(cells + 1):
            x, y = -a + 2 * a * i / cells, -b + 2 * b * j / cells
            if (abs(x / a) ** 4 + abs(y / b) ** 4) <= 1.0 and keep(x, y):
                grid[i, j] = bm.verts.new((x, y, height(x, y)))
    for i in range(cells):
        for j in range(cells):
            quad = [grid.get(k) for k in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))]
            if all(quad):
                bm.faces.new(quad)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return paint(obj, mat_name)


def _rope(points, radius, mat_name, around=5):
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(points):
        tangent = (points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]).normalized()
        side = tangent.cross(Vector((0, 0, 1))).normalized()
        up = side.cross(tangent).normalized()
        rings.append([bm.verts.new(p + (side * math.cos(2 * math.pi * k / around) + up * math.sin(2 * math.pi * k / around))
                                   * radius) for k in range(around)])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(around):
            bm.faces.new((r0[k], r0[(k + 1) % around], r1[(k + 1) % around], r1[k]))
    mesh = bpy.data.meshes.new("Rope")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Rope", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return paint(obj, mat_name)


def fit_bounds(obj, foot_centred=False, box=None):
    """Make the runtime size and centre this model by its whole outline.

    The runtime fits a model to its part using the bounds of the model's first mesh primitive only, and a model
    with several materials has one primitive per material. So a model whose first material covers only part of it
    was drawn wrong: the axe about 5x too big, the tree 1.44x too tall, the ladder centred on one rail. This puts a
    new first material holding just two specks of triangles at the corners of the whole outline, far too small to
    see, so the first primitive's bounds are the model's bounds. With foot_centred, the outline is also made
    symmetric about the origin in X and Y, so a tree or palm stands with its trunk's foot on its collider even when
    its crown leans."""
    mesh = obj.data
    xs, ys, zs = ([v.co[i] for v in mesh.vertices] for i in range(3))
    lo, hi = Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))
    if box:  # the part's own box (world coordinates), when the model sits inside it rather than filling it
        lo, hi = Vector(box[0]) - obj.location, Vector(box[1]) - obj.location
    if foot_centred:  # the foot stands at world (0, 0); the model's own origin is wherever its first piece was
        foot = -obj.location
        for i in (0, 1):
            reach = max(foot[i] - lo[i], hi[i] - foot[i])
            lo[i], hi[i] = foot[i] - reach, foot[i] + reach
    mats = list(mesh.materials)
    indices = [poly.material_index for poly in mesh.polygons]  # clearing the slots resets every face to slot 0
    mesh.materials.clear()
    bounds = bpy.data.materials.get("bounds") or bpy.data.materials.new("bounds")
    mesh.materials.append(bounds)
    for mat in mats:
        mesh.materials.append(mat)
    for poly, index in zip(mesh.polygons, indices):
        poly.material_index = index + 1
    bm = bmesh.new()
    bm.from_mesh(mesh)
    tiny = 1e-4
    for corner in (lo, hi):
        tri = [bm.verts.new(corner), bm.verts.new(corner + Vector((tiny, 0, 0))), bm.verts.new(corner + Vector((0, tiny, 0)))]
        bm.faces.new(tri).material_index = 0
    bm.to_mesh(mesh)
    bm.free()


def frond(base, angle, length, rise, droop, mat_name, steps=9, width=0.36):
    """One frond: a tapering, V-folded leaf that rises from the crown and droops, its edges notched into leaflets."""
    out = Vector((math.cos(angle), math.sin(angle), 0))
    side = Vector((-out.y, out.x, 0))
    bm = bmesh.new()
    rows = []
    for i in range(steps + 1):
        s = i / steps
        centre = base + out * (length * s) + Vector((0, 0, length * (rise * s - droop * s * s)))
        w = width * length * math.sin(math.pi * min(1.0, s * 1.05)) ** 0.7
        w *= 1.3 if i % 2 else 0.7  # leaflets
        fold = Vector((0, 0, -0.2 * w))
        rows.append([bm.verts.new(centre - side * w / 2 + fold), bm.verts.new(centre),
                     bm.verts.new(centre + side * w / 2 + fold)])
    for r0, r1 in zip(rows, rows[1:]):
        for j in range(2):
            bm.faces.new((r0[j], r0[j + 1], r1[j + 1], r1[j]))
    mesh = bpy.data.meshes.new("Frond")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Frond", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return paint(obj, mat_name)


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
    """A squared timber beam along X, exactly 3 : 1 : 1 like its 7.5 x 2.5 x 2.5 block part (ADR-005: a full block
    thick, three blocks long): four hewn faces, rough bark left along the corners, growth rings on both square
    ends. All four long faces are seen (a beam stood on end is rolled 90 degrees), so they are all alike."""
    length, side, wane = 1.19, 0.4, 0.065  # +2 x 0.005 of end rings makes it 1.2 long
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((length, side, side)), verts=bm.verts)
    corners = [e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).x) > length / 2]
    bark = bmesh.ops.bevel(bm, geom=corners, offset=wane, segments=2, affect="EDGES", profile=0.5)["faces"]
    bark = set(bark)
    long_edges = [e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).x) > length / 2]
    bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=8, use_grid_fill=False)
    for f in bm.faces:
        n = f.normal
        if abs(n.x) > 0.9:
            f.material_index, f.smooth = 2, False  # end grain
        elif abs(n.y) > 0.99 or abs(n.z) > 0.99:
            f.material_index, f.smooth = 0, False  # hewn face
        else:
            f.material_index, f.smooth = 1, True  # bark along the corner
    # Rough bark: the middle of each corner strip sinks in by varying amounts; the hewn faces stay flat at the
    # part's sides, so the beam keeps its exact size.
    edge_of_face = side / 2 - 1e-4
    for v in bm.verts:
        on_face = abs(v.co.y) >= edge_of_face or abs(v.co.z) >= edge_of_face or abs(v.co.x) >= length / 2 - 1e-4
        if not on_face:
            dent = 0.012 + 0.012 * noise.noise(Vector((v.co.x * 3.0, v.co.y * 9.0, v.co.z * 9.0)))
            v.co -= Vector((0, v.co.y, v.co.z)).normalized() * dent
    mesh = bpy.data.meshes.new("Log")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Log", mesh)
    bpy.context.scene.collection.objects.link(obj)
    for mat in ("hewn", "bark", "heartwood", "ring"):
        mesh.materials.append(material(mat))
    parts = [obj]
    # End grain: rings as thin discs stacked on each square end, the largest first.
    for sign in (-1, 1):
        for i, (radius, mat) in enumerate([(0.155, "ring"), (0.135, "heartwood"), (0.09, "ring"), (0.075, "heartwood"),
                                           (0.022, "ring")]):
            x = sign * (length / 2 + 0.001 * (i + 1))
            bpy.ops.mesh.primitive_circle_add(vertices=32, radius=radius, fill_type="NGON", location=(x, 0, 0),
                                              rotation=(0, math.radians(90), 0))
            parts.append(paint(bpy.context.active_object, mat, smooth=False))
    return join(parts, "Log")


def stump():
    """What a felled tree leaves: 1.4 across with its roots, 0.6 tall (its part), a cut top showing the rings."""
    parts = [ringed_cylinder("StumpTrunk", 0.46, 0.5, location=(0, 0, 0.33), caps="top")]
    parts.append(blob((0, 0, 0.1), 0.56, "bark", squash=0.3))  # the flare where trunk meets ground
    for i in range(5):
        a = math.radians(i * 72 + 18)
        root = blob((math.cos(a) * 0.5, math.sin(a) * 0.5, 0.06), 0.2, "bark", squash=0.45, segments=10, rings=6)
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
            parts.append(blob((x, 0, z), 0.085, "grip", squash=0.55, segments=8, rings=4))
    for i in range(8):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.05, depth=0.74, location=(0, 0, 0.45 + i * 0.52),
                                            rotation=(0, math.radians(90), 0))
        parts.append(paint(bpy.context.active_object, "heartwood"))
    return join(parts, "Ladder")


def boulder(centre, radii, seed, mat_name, cuts=(), rough=1.0, cut_mat="fresh_cut", detail=3):
    """A soft lumpy rock; each cut (point, normal) slices it flat and caps the cut (fresh, pale stone by default).
    `detail` 3 is a big rock (320 faces), 2 a pebble (80)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=detail, radius=1.0)
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
    """A rocky outcrop with freshly cut faces and rubble at its foot, shaped like its 10 x 5 x 7.5 part."""
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
                             cuts=[((0, 0, size * 0.45), (0.3, -0.4, 1))] if i % 3 == 0 else (), detail=2))
    # Broken-off chunks at the foot of the face: what the quarry gives.
    for i, (x, y, yaw) in enumerate([(-0.6, -1.95, 20), (0.35, -2.05, -15), (-0.1, -1.75, 50)]):
        chunk = rough_block(f"Chunk{i}", (0.42, 0.36, 0.3), 30.0 + i, mat_name="fresh_cut")
        chunk.location = (x, y, 0.15)
        chunk.rotation_euler = (0, 0, math.radians(yaw))
        parts.append(chunk)
    obj = join(parts, "Quarry")
    # Stretch to the part's proportions, 10 x 5 x 7.5 (wide : tall : deep = 2 : 1 : 1.5), so the rock fills its
    # collider instead of standing inside an invisible margin. The rocks are lumpy; 15-20% does not show.
    bpy.context.view_layer.update()
    dims = obj.dimensions.copy()
    obj.scale = (2.0 * dims.z / dims.x, 1.5 * dims.z / dims.y, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


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
    if mat_name == "granite":
        granite(mesh, size, offset)
    else:
        mesh.materials.append(material(mat_name))
    for poly in mesh.polygons:
        poly.use_smooth = False
    return obj


def granite(mesh, size, offset):
    """Mottled granite as vertex colours, blended smoothly across each face: soft patches of darker and lighter
    stone plus a fine speckle. Stays solid and stony in game (a uniform pale grey read as frosted glass)."""
    dark, mid, light = (linear(PALETTE[k]["color"]) for k in ("granite_dark", "granite", "granite_light"))
    colors = mesh.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    for v in mesh.vertices:
        patch = noise.noise(v.co * 2.6 / min(size) + offset * 1.7)
        speck = noise.noise(v.co * 16.0 / min(size) + offset)
        t = max(-1.0, min(1.0, patch * 2.2 + speck * 0.5))
        a, b, w = (mid, light, t) if t > 0 else (mid, dark, -t)
        colors.data[v.index].color = (*(p + (q - p) * w for p, q in zip(a, b)), 1.0)
    mat = bpy.data.materials.get("granite_vc") or bpy.data.materials.new("granite_vc")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    attr = nodes.get("Color Attribute") or nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Metallic"].default_value = 0.0
    mesh.materials.append(mat)


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
            "boulder.glb": boulder_ball(), "stump.glb": stump(), "palm.glb": palm(), "raft.glb": raft(),
            "coconut.glb": coconut(), "spear.glb": spear(), "fish.glb": fish(), "fish_cooked.glb": fish(cooked=True),
            "volleyball.glb": volleyball()}
    boxes = {"raft.glb": ((-RAFT_LENGTH / 2, -RAFT_WIDTH / 2, 0), (RAFT_LENGTH / 2, RAFT_WIDTH / 2, RAFT_HEIGHT)),
             "spear.glb": SPEAR_BOX, "fish.glb": FISH_BOX, "fish_cooked.glb": FISH_BOX}
    for filename, obj in made.items():
        fit_bounds(obj, foot_centred=filename in ("tree.glb", "palm.glb"), box=boxes.get(filename))
        obj.location = (0, 0, 0)
        export(obj, filename)
        dims = obj.dimensions
        print(f"SIZE {filename}: x {dims.x:.2f}, y {dims.y:.2f}, z {dims.z:.2f} (Blender; the model's Z is -y)")
    # Side by side for the preview render, each resting on the ground (a model's origin is wherever its first
    # piece was; the world's renderer centres models by their bounds, so this matters only here).
    layout = {"tree.glb": (0, 0), "log.glb": (1.6, -0.4), "axe.glb": (-1.3, -0.3), "quarry.glb": (7, 4),
              "hammer.glb": (4.2, -1.2), "stone.glb": (5.2, -1.6), "brick.glb": (6.6, -1.4), "ladder.glb": (-3.2, 1.2),
              "boulder.glb": (3.0, 2.0), "stump.glb": (-1.6, 2.6), "palm.glb": (-5.5, -2.0), "raft.glb": (-4.0, -7.0),
              "coconut.glb": (0.5, -4.0), "spear.glb": (2.0, -4.5), "fish.glb": (-1.0, -4.0),
              "fish_cooked.glb": (-1.0, -5.0), "volleyball.glb": (1.0, -5.5)}
    for filename, (x, y) in layout.items():
        obj = made[filename]
        obj.location = (x, y, 0)
        bpy.context.view_layer.update()
        obj.location.z -= min((obj.matrix_world @ Vector(corner)).z for corner in obj.bound_box)
    bpy.ops.wm.save_as_mainfile(filepath=str(ART / "props.blend"))


main()
