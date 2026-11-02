"""Generate Godling's castaway island on the block grid (ADR-007).

The island is made of grid-aligned boxes, Minecraft-style: sand under the whole outline, grass on the inland, and rock
columns of whole-block heights for a mountain and hills. Everything else that has a place on the island (the raft and
the spawn beside it, the camp, the quarry, trees, palms) is placed here too, so one seed gives one consistent island.

    python tools/make_island.py            writes world/island.lua and research/island-preview.png

The world script pastes in world/island.lua between its ISLAND markers (this script does that too).
"""
import json
import math
import random
import struct
import zlib
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CELL = 2.5  # one block
SEED = 20261102

# The island: an ellipse of about 110 x 130 blocks with a ragged coast; the islet across a strait in the south-east.
# SCALE stretches the whole island (its shape stays the same): 1.2 since run n7 (the user's wish: a little bigger, with
# room to build).
SCALE = 1.2
RX, RZ = 112.0 * SCALE, 138.0 * SCALE
ISLET = (155.0 * SCALE, -128.0 * SCALE, 16.0 * SCALE)
HALF = 92  # cells each way from the centre that the map covers
# The mountain (Monuriki's peak, north-west) and two hills, in units: centre x, z, radius, height in blocks.
MOUNTAIN = (-42.0 * SCALE, 72.0 * SCALE, 72.0 * SCALE, 16)
HILLS = [(58.0 * SCALE, 52.0 * SCALE, 30.0 * SCALE, 5), (40.0 * SCALE, -78.0 * SCALE, 24.0 * SCALE, 3)]
# Open meadows where no palm grows, in cells: around the camp, by the quarry, and in the middle of the island.
MEADOW_RADIUS = {"camp": 13, "quarry": 9, "middle": 14}
GROVES, GROVE_RADIUS, PALMS_PER_GROVE = 9, 7, 7  # inland palms grow in groves, open grass between them


def hash01(ix, iz, salt):
    h = (ix * 374761393 + iz * 668265263 + salt * 2147483647 + SEED * 1442695041) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def value_noise(x, z, salt):
    ix, iz = math.floor(x), math.floor(z)
    fx, fz = x - ix, z - iz
    sx, sz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a, b = hash01(ix, iz, salt), hash01(ix + 1, iz, salt)
    c, d = hash01(ix, iz + 1, salt), hash01(ix + 1, iz + 1, salt)
    return (a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sz


def fbm(x, z, salt, octaves=4):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * value_noise(x * 2 ** o, z * 2 ** o, salt + o)
        norm += amp
        amp *= 0.5
    return total / norm  # 0..1


def cells():
    return [(i, j) for i in range(-HALF, HALF + 1) for j in range(-HALF, HALF + 1)]


def neighbours4(i, j):
    return ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1))


def make_land():
    land = set()
    for i, j in cells():
        x, z = i * CELL, j * CELL
        # Two scales of noise: lobes and bays, then a ragged edge; the south runs out into a long beach.
        x, z = x / SCALE, z / SCALE  # noise and shape at the original island's size
        d = (math.hypot(x / (RX / SCALE), z / (RZ / SCALE + (18 if z < 0 else 0))) + 0.42 * (fbm(x / 95, z / 95, 1) - 0.5)
             + 0.12 * (fbm(x / 28, z / 28, 12) - 0.5))
        x, z = x * SCALE, z * SCALE
        if d < 1.0:
            land.add((i, j))
        ix, iz, ir = ISLET
        if math.hypot(x - ix, z - iz) + 6 * SCALE * (fbm(x / 20 / SCALE, z / 20 / SCALE, 2) - 0.5) < ir:
            land.add((i, j))
    # Fill lakes: water the open sea cannot reach becomes land.
    sea, todo = set(), deque([(-HALF, -HALF)])
    while todo:
        c = todo.popleft()
        if c in sea or c in land or abs(c[0]) > HALF or abs(c[1]) > HALF:
            continue
        sea.add(c)
        todo.extend(neighbours4(*c))
    return {c for c in cells() if c not in sea}


def coast_distance(land):
    dist, todo = {}, deque()
    for c in land:
        if any(n not in land for n in neighbours4(*c)):
            dist[c] = 1
            todo.append(c)
    while todo:
        c = todo.popleft()
        for n in neighbours4(*c):
            if n in land and n not in dist:
                dist[n] = dist[c] + 1
                todo.append(n)
    return dist


def make_heights(land, coast):
    heights = {}
    for i, j in land:
        x, z = i * CELL, j * CELL
        h = 0.0
        mx, mz, mr, mh = MOUNTAIN
        # Lopsided like Monuriki's: steep to the sea in the north-west, a long shoulder inland to the south-east.
        u, v = (x - mx) * 0.80 + (z - mz) * 0.60, -(x - mx) * 0.60 + (z - mz) * 0.80
        n = 1 / SCALE  # noise at the original island's size
        r = math.hypot(u / (mr * (1.25 if u > 0 else 0.8)), v / (mr * 0.85)) + 0.38 * (fbm(x * n / 34, z * n / 34, 3) - 0.5)
        if r < 1:
            h = max(h, mh * (1 - r) ** 1.05)
        for hx, hz, hr, hh in HILLS:
            r = math.hypot(x - hx, z - hz) / hr + 0.5 * (fbm(x * n / 22, z * n / 22, 5) - 0.5)
            if r < 1:
                h = max(h, hh * (1 - r ** 2))
        beach = beach_width(x, z)
        if coast[(i, j)] <= beach + 1:  # the beach stays flat; the mountain may come close on its own side only
            h = 0 if not (z > 60 * SCALE and x < -20 * SCALE) else min(h, max(0, coast[(i, j)] - 2))
        h = 2 * int(h / 2)  # terraces two blocks tall: big, readable steps, and few parts
        if h >= 2:
            heights[(i, j)] = h
    # Drop lone raised cells and one-cell slivers: they read as noise and trap the body.
    for _ in range(2):
        for c in list(heights):
            if sum(1 for n in neighbours4(*c) if heights.get(n, 0) >= heights[c]) < 2:
                lower = [heights.get(n, 0) for n in neighbours4(*c)]
                h = max(lower)
                if h >= 2:
                    heights[c] = h
                else:
                    del heights[c]
    return heights


def beach_width(x, z):
    """How many cells of sand run inland from the water here (wider on the long south beach)."""
    return 4 + int(3 * fbm(x / SCALE / 40, z / SCALE / 40, 6)) + (3 if z < -90 * SCALE else 0)


def beach_cells(land, coast):
    sand = set()
    for i, j in land:
        x, z = i * CELL, j * CELL
        if coast[(i, j)] <= beach_width(x, z) or math.hypot(x - ISLET[0], z - ISLET[1]) < ISLET[2] + 8 * SCALE:
            sand.add((i, j))
    return sand


def rectangles(cellset):
    """Greedy cover of a set of cells with axis-aligned rectangles: (i0, j0, i1, j1) inclusive."""
    left, rects = set(cellset), []
    for j in range(-HALF, HALF + 1):
        for i in range(-HALF, HALF + 1):
            if (i, j) not in left:
                continue
            i1 = i
            while (i1 + 1, j) in left:
                i1 += 1
            j1 = j
            while all((k, j1 + 1) in left for k in range(i, i1 + 1)):
                j1 += 1
            for k in range(i, i1 + 1):
                for m in range(j, j1 + 1):
                    left.discard((k, m))
            rects.append((i, j, i1, j1))
    return rects


def rect_box(r):
    i0, j0, i1, j1 = r
    return ((i0 + i1) / 2 * CELL, (j0 + j1) / 2 * CELL, (i1 - i0 + 1) * CELL, (j1 - j0 + 1) * CELL)


def place(land, sand, heights, coast):
    rng = random.Random(SEED)
    lowland = {c for c in land if c not in heights}
    grass = lowland - sand

    def at(i, j):
        return i * CELL, j * CELL

    # The raft: on the west beach, a step from the water; Godling washes up beside it.
    west = sorted((c for c in sand if coast[c] == 2 and -20 * SCALE <= c[1] <= -4 * SCALE and c[0] < 0), key=lambda c: c[0])
    raft = west[0]
    spawn = (raft[0] + 2, raft[1] - 2)
    # The camp: open grass about 12 blocks inland of the raft.
    def open_area(ci, cj, w, d, ground):
        return all((ci + a, cj + b) in ground for a in range(-1, w + 1) for b in range(-1, d + 1))
    camp = None
    for r in range(10, 40):
        for k in range(32):
            a = 2 * math.pi * k / 32
            ci, cj = raft[0] + round(r * math.cos(a)), raft[1] + round(r * math.sin(a))
            if ci > raft[0] and open_area(ci, cj, 8, 8, grass):
                camp = (ci, cj)
                break
        if camp:
            break
    pile = camp  # 4 x 3 starting blocks from here
    ladder = (camp[0] + 6, camp[1] + 5)
    axe = (camp[0] + 6, camp[1] - 1)
    # The quarry: 4 x 3 cells on the lowland against the mountain's foot, nearest the camp, with its yard free.
    best = None
    for i0, j0 in lowland:
        foot = [(i0 + a, j0 + b) for a in range(4) for b in range(3)]
        if not all(c in grass for c in foot):
            continue
        ring = [(i0 + a, j0 + b) for a in range(-1, 5) for b in range(-1, 4) if (i0 + a, j0 + b) not in foot]
        against = sum(1 for c in ring if c in heights)
        free = sum(1 for c in ring if c in grass)
        if against >= 4 and free >= 10:
            d = math.hypot(i0 - camp[0], j0 - camp[1])
            if best is None or d < best[0]:
                best = (d, (i0, j0))
    quarry = best[1]
    hammer = (quarry[0] + 6, quarry[1] - 2)
    # Boulders at the mountain's foot.
    foot_cells = sorted((c for c in grass if any(n in heights for n in neighbours4(*c))
                         and math.hypot(c[0] - quarry[0], c[1] - quarry[1]) > 8),
                        key=lambda c: math.hypot(c[0] - quarry[0], c[1] - quarry[1]))
    boulders = [foot_cells[0], foot_cells[len(foot_cells) // 3]]
    taken = set()
    for (ci, cj), (w, d) in ((pile, (4, 3)), (quarry, (4, 3))):
        taken |= {(ci + a, cj + b) for a in range(-2, w + 2) for b in range(-2, d + 2)}
    taken |= {spawn, raft, ladder, axe, hammer, *boulders}
    for c in (spawn, raft):
        taken |= {(c[0] + a, c[1] + b) for a in range(-3, 4) for b in range(-3, 4)}

    def scatter(pool, count, gap, salt):
        chosen, pool = [], sorted(pool)
        random.Random(SEED + salt).shuffle(pool)
        for c in pool:
            if c in taken or any(math.dist(c, o) < gap for o in chosen):
                continue
            chosen.append(c)
            if len(chosen) == count:
                break
        return chosen
    # Open meadows, where no palm grows: room to build by the camp and the quarry, and a wide one in the middle of the
    # island. Palms scattered over all the inland grass left no space to build (the user, after run n7).
    flat = [c for c in grass if coast[c] > 14 and all(n not in heights for n in neighbours4(*c))]
    mid = (sum(c[0] for c in grass) / len(grass), sum(c[1] for c in grass) / len(grass))
    middle = min(flat, key=lambda c: math.hypot(c[0] - mid[0], c[1] - mid[1]))
    meadows = {"camp": (camp[0] + 4, camp[1] + 4), "quarry": (quarry[0] + 2, quarry[1] + 1), "middle": middle}

    def in_meadow(c):
        return any(math.hypot(c[0] - m[0], c[1] - m[1]) <= MEADOW_RADIUS[k] for k, m in meadows.items())
    # Inland palms: in groves, with open grass between them; clear of walls.
    forest = [c for c in grass if coast[c] > 6 and all(n not in heights for n in neighbours4(*c)) and not in_meadow(c)]
    trees = []
    for k, grove in enumerate(scatter(forest, GROVES, 2.6 * GROVE_RADIUS, 7)):
        trees += scatter([c for c in forest if math.dist(c, grove) <= GROVE_RADIUS], PALMS_PER_GROVE, 2.6, 20 + k)
        taken |= set(trees)
    # Palms on the beach, in loose clusters, leaning out to sea.
    palm_pool = [c for c in sand if 2 <= coast[c] <= 4]
    palms = scatter(palm_pool, round(26 * SCALE), 3.2, 9)
    taken |= set(palms)
    rock = scatter(list(grass), 1, 1, 11)[0]

    def seaward_yaw(c):
        i, j = c  # a palm leans along its part's +X; yaw turns +X to (cos y, 0, -sin y)
        options = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}
        open_sea = {y: sum(1 for k in range(1, 9) if (i + dx * k, j + dz * k) not in land) for y, (dx, dz) in options.items()}
        return max(open_sea, key=lambda y: (open_sea[y], -y))
    # Palms everywhere, as on the Cast Away island (the user's wish): on the beach they lean out to sea, inland any way.
    lean = random.Random(SEED + 13)
    palms_out = [(p, seaward_yaw(p), 1) for p in palms] + [(t, lean.choice((0, 90, 180, 270)), 0) for t in trees]
    return {
        "raft": raft, "spawn": spawn, "pile": pile, "ladder": ladder, "axe": axe, "quarry": quarry,
        "hammer": hammer, "boulders": boulders, "trees": [], "palms": palms_out,
        "rock": rock, "at": at, "meadows": meadows,
    }


def feature_of(c, heights):
    x, z = c[0] * CELL, c[1] * CELL
    best, name = None, None
    for fname, (fx, fz, fr, _) in [("Peak", MOUNTAIN), ("EastHill", HILLS[0]), ("SouthHill", HILLS[1])]:
        d = math.hypot(x - fx, z - fz) / fr
        if best is None or d < best:
            best, name = d, fname
    return name


def lua_number(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def write_lua(land, sand, heights, spots):
    grass = (land - sand) - set()
    lines = ["-- ISLAND BEGIN: generated by tools/make_island.py (seed %d); edit the generator, not this block." % SEED,
             "local ISLAND = {"]
    lines.append("    sand = {  -- the whole outline, a hand below the grass")
    for r in rectangles(land):
        cx, cz, sx, sz = rect_box(r)
        lines.append("        {%s, %s, %s, %s}," % tuple(lua_number(v) for v in (cx, cz, sx, sz)))
    lines.append("    },")
    lines.append("    grass = {  -- the inland")
    for r in rectangles(land - sand):
        cx, cz, sx, sz = rect_box(r)
        lines.append("        {%s, %s, %s, %s}," % tuple(lua_number(v) for v in (cx, cz, sx, sz)))
    lines.append("    },")
    lines.append("    rock = {  -- columns of whole-block heights: {x, z, size x, size z, height in blocks, feature}")
    count = {}
    for h in sorted(set(heights.values())):
        level = {c for c, v in heights.items() if v == h}
        by_feature = {}
        for c in level:
            by_feature.setdefault(feature_of(c, heights), set()).add(c)
        for fname, group in sorted(by_feature.items()):
            for r in rectangles(group):
                cx, cz, sx, sz = rect_box(r)
                count[fname] = count.get(fname, 0) + 1
                lines.append('        {%s, %s, %s, %s, %d, "%s"},' % (lua_number(cx), lua_number(cz), lua_number(sx),
                                                                  lua_number(sz), h, fname))
    lines.append("    },")
    at = spots["at"]

    def pt(c):
        x, z = at(*c)
        return "{%s, %s}" % (lua_number(x), lua_number(z))
    lines.append("    trees = {%s}," % ", ".join(pt(c) for c in spots["trees"]))
    lines.append("    palms = {  -- {x, z, yaw, on sand}")
    for c, y, sandy in spots["palms"]:
        lines.append("        {%s, %s, %d, %s}," % (lua_number(at(*c)[0]), lua_number(at(*c)[1]), y, "true" if sandy else "false"))
    lines.append("    },")
    for key in ("raft", "spawn", "pile", "ladder", "axe", "hammer"):
        lines.append("    %s = %s," % (key, pt(spots[key])))
    lines.append("    loose_rock = %s,  -- where upstream's throwable Rock_1 lies" % pt(spots["rock"]))
    # Shallows for the fish: water one to three cells off the main island's shore (not round the islet).
    shallows = sorted(c for c in cells() if c not in land and math.hypot(c[0] * CELL - ISLET[0], c[1] * CELL - ISLET[1]) > ISLET[2] + 12
                      and any((c[0] + a, c[1] + b) in land for a in range(-3, 4) for b in range(-3, 4))
                      and not any((c[0] + a, c[1] + b) in land for a in (-1, 0, 1) for b in (-1, 0, 1)))
    shallows = shallows[::3]
    lines.append("    shallows = {%s},  -- where fish swim" % ", ".join("{%s, %s}" % (lua_number(i * CELL), lua_number(j * CELL))
                                                                  for i, j in shallows))
    bx, bz = at(spots["raft"][0] + 2, spots["raft"][1] + 2)
    lines.append("    volleyball = {%s, %s},  -- washed up beside the raft" % (lua_number(bx), lua_number(bz)))
    qx, qz = at(*spots["quarry"])
    lines.append("    quarry = {%s, %s},  -- the 4 x 3 quarry's first cell" % (lua_number(qx), lua_number(qz)))
    lines.append("    boulders = {%s}," % ", ".join(pt(c) for c in spots["boulders"]))
    lines.append("}")
    lines.append("-- ISLAND END")
    block = "\n".join(lines) + "\n"
    (ROOT / "world" / "island.lua").write_text(block, encoding="utf-8", newline="\n")
    main = ROOT / "world" / "main.lua"
    text = main.read_text(encoding="utf-8")
    if "-- ISLAND BEGIN" in text:
        start = text.index("-- ISLAND BEGIN")
        end = text.index("-- ISLAND END") + len("-- ISLAND END\n")
        text = text[:start] + block + text[end:]
        main.write_text(text, encoding="utf-8", newline="\n")
    return count


def write_png(path, land, sand, heights, spots):
    size = 2 * HALF + 1
    scale = 4
    w = h = size * scale
    sea, sand_c, grass_c = (40, 110, 170), (232, 214, 166), (108, 191, 79)
    pixels = [[sea] * w for _ in range(h)]

    def paint(i, j, color):
        px, py = (i + HALF) * scale, (HALF - j) * scale  # north up
        for a in range(scale):
            for b in range(scale):
                pixels[py + b][px + a] = color
    for c in land:
        paint(*c, sand_c if c in sand else grass_c)
    for c, v in heights.items():
        g = int(70 + 10 * v)
        paint(*c, (min(255, g + 40), min(255, g + 35), min(255, g + 30)))
    for c in spots["trees"]:
        paint(*c, (30, 100, 30))
    for c, _, _ in spots["palms"]:
        paint(*c, (0, 140, 60))
    for key, color in (("raft", (250, 200, 30)), ("spawn", (255, 60, 60)), ("pile", (120, 120, 120)),
                       ("ladder", (160, 110, 60)), ("axe", (200, 80, 0)), ("hammer", (20, 20, 20))):
        paint(*spots[key], color)
    qi, qj = spots["quarry"]
    for a in range(4):
        for b in range(3):
            paint(qi + a, qj + b, (200, 200, 200))
    raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in pixels)
    png = b"\x89PNG\r\n\x1a\n"
    for tag, data in ((b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)), (b"IDAT", zlib.compress(raw, 9)),
                      (b"IEND", b"")):
        png += struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    path.write_bytes(png)


def main():
    land = make_land()
    coast = coast_distance(land)
    sand = beach_cells(land, coast)
    heights = make_heights(land, coast)
    sand -= set(heights)
    spots = place(land, sand, heights, coast)
    count = write_lua(land, sand, heights, spots)
    out = ROOT / "research" / "island-preview.png"
    write_png(out, land, sand, heights, spots)
    xs = [c[0] for c in land]
    zs = [c[1] for c in land]
    summary = {
        "blocks across (x)": max(xs) - min(xs) + 1, "blocks long (z)": max(zs) - min(zs) + 1,
        "land cells": len(land), "beach cells": len(sand), "raised cells": len(heights),
        "highest (blocks)": max(heights.values()), "sand parts": len(rectangles(land)),
        "grass parts": len(rectangles(land - sand)), "rock parts": count, "trees": len(spots["trees"]),
        "palms": len(spots["palms"]), "raft": spots["at"](*spots["raft"]), "camp": spots["at"](*spots["pile"]),
        "quarry": spots["at"](*spots["quarry"]),
    }
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
