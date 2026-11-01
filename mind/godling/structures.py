"""Measure what has been built: walls, enclosures, roofs, spans, posts and floors at height (ADR-004).

Works on the building pieces in one observation (their world-aligned boxes) and the terrain under them. The
ground is cut into cells the width of a block (the world's grid); each cell gets the pieces standing in it, and
heights are measured from the terrain top under the cell, so building on a mesa counts the same as on the ground.

  wall       a straight run of at least 3 cells, each built at least two layers high, of at least 3 pieces
  enclosure  open cells walled in on every side (a gap one cell wide counts as a doorway)
  roof       an enclosure at least half covered by pieces lying two layers up or more
  span       a long piece lying on its two ends with a gap under its middle (a lintel, a beam, a bridge)
  post       a long piece stood on its end
  floor      a flat top at least two layers up, at least 4 cells wide, that one could stand on
"""
import math
from collections import deque

from .world import CUBE

CELL = CUBE  # a block's width: the grid
LAYER = CUBE  # a block's height
PIECE_PREFIXES = ("Block_", "ImpactBlock_", "SupplyBlock_", "Stone_", "Meteor_", "Brick_", "Log_", "Boulder_")


def pieces_of(snap):
    """The building pieces in a Snapshot as plain records (carried ones excluded)."""
    held = snap.held()
    return [{"name": e.name, "pos": [round(v, 3) for v in e.pos], "size": [round(v, 3) for v in e.size],
             "fastened": bool(e.attrs.get("Fastened"))}
            for e in snap.movables() if e.name.startswith(PIECE_PREFIXES) and e is not held]


def terrain_of(snap):
    return [{"name": t.name, "pos": list(t.pos), "size": list(t.size)} for t in snap.terrain()]


def _cells(lo, hi):
    """Indices of the cells whose centres lie in [lo, hi)."""
    return range(math.ceil(lo / CELL - 1e-9), math.ceil(hi / CELL - 1e-9))


def measure(pieces, terrain):
    def base(ix, iz):
        x, z = ix * CELL, iz * CELL
        tops = [t["pos"][1] + t["size"][1] / 2 for t in terrain
                if abs(x - t["pos"][0]) <= t["size"][0] / 2 and abs(z - t["pos"][2]) <= t["size"][2] / 2]
        return max(tops) if tops else 0.0

    columns = {}  # (ix, iz) -> [(bottom, top, piece index)]
    for i, p in enumerate(pieces):
        (x, y, z), (sx, sy, sz) = p["pos"], p["size"]
        for ix in _cells(x - sx / 2, x + sx / 2):
            for iz in _cells(z - sz / 2, z + sz / 2):
                columns.setdefault((ix, iz), []).append((y - sy / 2, y + sy / 2, i))
    bases = {c: base(*c) for c in columns}

    # Per cell: the height stacked up from the terrain without a gap, and the pieces in that stack; the highest
    # top above the terrain, and the piece it belongs to.
    standing, stacked, top_of, top_piece = {}, {}, {}, {}
    for c, spans_ in columns.items():
        level, used = bases[c], set()
        for bottom, top, i in sorted(spans_):
            if bottom <= level + 0.15:
                level = max(level, top)
                used.add(i)
        standing[c], stacked[c] = level - bases[c], used
        _, top_of[c], top_piece[c] = max((t, t - bases[c], i) for _, t, i in spans_)

    wall_cells = {c for c, h in standing.items() if h >= 2 * LAYER - 0.1}

    # Walls: straight runs of wall cells along x or z, made of at least 3 pieces (one big boulder is no wall).
    walls, wall_length = 0, 0
    for axis in (0, 1):
        for c in wall_cells:
            prev = (c[0] - 1, c[1]) if axis == 0 else (c[0], c[1] - 1)
            if prev in wall_cells:
                continue  # not the start of a run
            run, nxt = [], c
            while nxt in wall_cells:
                run.append(nxt)
                nxt = (nxt[0] + 1, nxt[1]) if axis == 0 else (nxt[0], nxt[1] + 1)
            if len(run) >= 3 and len(set().union(*(stacked[r] for r in run))) >= 3:
                walls += 1
                wall_length += len(run)

    # Enclosures: flood from outside; what the flood cannot reach, behind walls and doorways, is enclosed.
    enclosures, enclosed_cells, roofs = 0, 0, 0
    if wall_cells:
        xs, zs = [c[0] for c in wall_cells], [c[1] for c in wall_cells]
        x0, x1, z0, z1 = min(xs) - 1, max(xs) + 1, min(zs) - 1, max(zs) + 1
        doors = {(ix, iz) for ix in range(x0, x1 + 1) for iz in range(z0, z1 + 1) if (ix, iz) not in wall_cells and (
            ((ix - 1, iz) in wall_cells and (ix + 1, iz) in wall_cells)
            or ((ix, iz - 1) in wall_cells and (ix, iz + 1) in wall_cells))}
        closed = wall_cells | doors
        outside, queue = {(x0, z0)}, deque([(x0, z0)])
        while queue:
            ix, iz = queue.popleft()
            for n in ((ix + 1, iz), (ix - 1, iz), (ix, iz + 1), (ix, iz - 1)):
                if x0 <= n[0] <= x1 and z0 <= n[1] <= z1 and n not in closed and n not in outside:
                    outside.add(n)
                    queue.append(n)
        inside = {(ix, iz) for ix in range(x0, x1 + 1) for iz in range(z0, z1 + 1)} - closed - outside
        while inside:  # each connected enclosed space
            seed = inside.pop()
            room, queue = {seed}, deque([seed])
            while queue:
                ix, iz = queue.popleft()
                for n in ((ix + 1, iz), (ix - 1, iz), (ix, iz + 1), (ix, iz - 1)):
                    if n in inside:
                        inside.discard(n)
                        room.add(n)
                        queue.append(n)
            enclosures += 1
            enclosed_cells += len(room)
            covered = sum(1 for c in room if any(b - bases.get(c, base(*c)) >= 2 * LAYER - 0.15
                                                 for b, _, _ in columns.get(c, ())))
            roofs += covered * 2 >= len(room)

    # Spans and posts: long pieces lying across a gap, or stood on their end.
    spans, posts, longest_gap = 0, 0, 0.0
    for p in pieces:
        (x, y, z), (sx, sy, sz) = p["pos"], p["size"]
        length = max(sx, sz)
        if sy >= 1.8 * LAYER and sy > length + 0.1:
            posts += 1
            continue
        if length < 1.8 * CELL or sy > length:
            continue
        bottom = y - sy / 2
        ux, uz = (1.0, 0.0) if sx >= sz else (0.0, 1.0)
        def support(px, pz):
            c = (round(px / CELL), round(pz / CELL))
            under = [t for b, t, _ in columns.get(c, ()) if t <= bottom + 0.15]
            return max(under + [base(*c)])
        mid = support(x, z)
        ends = [support(x + ux * (length / 2 - 0.4 * CELL) * s, z + uz * (length / 2 - 0.4 * CELL) * s) for s in (-1, 1)]
        if all(abs(e - bottom) <= 0.15 for e in ends) and bottom - mid >= 0.8 * LAYER:
            spans += 1
            longest_gap = max(longest_gap, bottom - mid)

    # Floors at height: flat tops two layers up or more, at least 4 connected cells.
    high = {c for c, h in top_of.items() if h >= 2 * LAYER - 0.1}
    floors, floor_cells, seen = 0, 0, set()
    for c in high:
        if c in seen:
            continue
        level = top_of[c] + bases[c]
        group, queue = {c}, deque([c])
        seen.add(c)
        while queue:
            ix, iz = queue.popleft()
            for n in ((ix + 1, iz), (ix - 1, iz), (ix, iz + 1), (ix, iz - 1)):
                if n in high and n not in seen and abs(top_of[n] + bases[n] - level) <= 0.12:
                    seen.add(n)
                    group.add(n)
                    queue.append(n)
        if len(group) >= 4 and len({top_piece[g] for g in group}) >= 2:  # built, not the top of one big rock
            floors += 1
            floor_cells += len(group)

    # Joined groups: pieces touching each other (within a hair), the biggest one, and how many are fastened.
    n = len(pieces)
    parent = list(range(n))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(n):
        (ax, ay, az), (asx, asy, asz) = pieces[i]["pos"], pieces[i]["size"]
        for j in range(i + 1, n):
            (bx, by, bz), (bsx, bsy, bsz) = pieces[j]["pos"], pieces[j]["size"]
            if (abs(ax - bx) <= (asx + bsx) / 2 + 0.08 and abs(ay - by) <= (asy + bsy) / 2 + 0.08
                    and abs(az - bz) <= (asz + bsz) / 2 + 0.08):
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    built = [g for g in groups.values() if len(g) >= 2]

    return {
        "pieces": n,
        "pieces_built_in": sum(len(g) for g in built),
        "largest_structure": max((len(g) for g in built), default=0),
        "fastened": sum(1 for p in pieces if p["fastened"]),
        "walls": walls,
        "wall_length": round(wall_length * CELL, 2),
        "enclosures": enclosures,
        "enclosed_area": round(enclosed_cells * CELL * CELL, 2),
        "roofed": roofs,
        "spans": spans,
        "longest_gap": round(longest_gap, 2),
        "posts": posts,
        "floors": floors,
        "floor_area": round(floor_cells * CELL * CELL, 2),
        # The tallest stack of at least two pieces; the highest top of anything built in (two or more pieces joined).
        "tallest": round(max((h for c, h in standing.items() if len(stacked[c]) >= 2), default=0.0), 2),
        "highest": round(max((top_of[c] for c in top_of if any(top_piece[c] in g for g in built)), default=0.0), 2),
    }
