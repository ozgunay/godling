"""What a house is (ADR-019, the first-house benchmark): one check for the build measure and for the mind, so they never
disagree. The world has its own copy of it in world/main.lua (houseAt), for whether the body stands in a house; the
tests hold the two to the same layouts.

A house is a structure:
- a room of clear cells, at least two by two, on one floor, where Godling can stand (a block in the room fails it);
- walls all round it, corners too, each filled from the floor up to the roof without a gap, but for one doorway;
- posts inside it, if it has any (ADR-033): cells the room closes round, filled from the floor up to the roof like the
  walls. They count as cells inside it (for "two by two"), not as room to stand in;
- the doorway on a side (not a corner), open from the floor up to the roof, onto open ground outside;
- a roof over all of it, the walls, the posts and the doorway too, its underside more than five above the room's floor
  (the body is exactly five tall, so on the world's grid that is three blocks up).
Shelter is something else: what the body feels where it stands (main.lua shelterOf). A roof keeps the rain off long
before it is a house.

Works on the building pieces and terrain as structures.py reads them (records with "pos" and "size", world-aligned),
cut into the world's grid of 2.5 cells.
"""
import json
import math
from collections import deque

from .world import CUBE

CELL = LAYER = CUBE
HEADROOM = 2 * LAYER  # the body's height: a roof must leave more room than this
CLEAR = HEADROOM + 0.05  # a cell is clear when nothing lies in it from its floor up to here
OVER = 15.0  # a roof is something over the cell no higher than this above its floor
FLAT = 0.6  # floors this close are one floor: a doorway is walked through, not climbed
GAP = 0.15  # pieces this close are touching: a column with no gap wider than this is filled
MOST = 64  # cells: a room bigger than this is open ground under something wide, not a house
SQUARE = 2  # the room holds a square of cells at least this many on a side
ROOF_AT = 3 * LAYER  # where the roof's underside goes when none is up yet: on walls three blocks high
EIGHT = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


def _cells(lo, hi):
    """Indices of the cells whose centres lie in [lo, hi)."""
    return range(math.ceil(lo / CELL - 1e-9), math.ceil(hi / CELL - 1e-9))


def _sides(c):
    return ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1))


def at(c):
    """A cell's centre in words."""
    return f"({c[0] * CELL:.1f}, {c[1] * CELL:.1f})"


def _list(cells, most=6):
    cells = sorted(cells)
    return ", ".join(at(c) for c in cells[:most]) + (f" and {len(cells) - most} more" if len(cells) > most else "")


def ring(room):
    """The cells round a room, corners too: where its walls and doorway stand."""
    room = set(room)
    return sorted({(c[0] + dx, c[1] + dz) for c in room for dx, dz in EIGHT} - room)


def sides(room):
    """The cells beside a room, side by side with one of its cells: where a doorway can be."""
    room = set(room)
    return sorted({n for c in room for n in _sides(c)} - room)


def squared(room):
    """Whether the room holds a square of cells SQUARE on a side."""
    room = set(room)
    return any(all((c[0] + i, c[1] + j) in room for i in range(SQUARE) for j in range(SQUARE)) for c in room)


def enclosed(room):
    """The cells a room closes round (ADR-033): not in it, and with no way out to open ground, side by side, but
    through the room. In a house these are its posts. A column against a wall is not one: it is part of the wall."""
    room = set(room)
    if not room:
        return []
    x0, x1 = min(c[0] for c in room) - 1, max(c[0] for c in room) + 1
    z0, z1 = min(c[1] for c in room) - 1, max(c[1] for c in room) + 1
    box = [(ix, iz) for ix in range(x0, x1 + 1) for iz in range(z0, z1 + 1)]
    out = {c for c in box if c[0] in (x0, x1) or c[1] in (z0, z1)}  # the edge of the box is outside the room
    queue = deque(out)
    while queue:
        for n in _sides(queue.popleft()):
            if x0 <= n[0] <= x1 and z0 <= n[1] <= z1 and n not in room and n not in out:
                out.add(n)
                queue.append(n)
    return sorted(c for c in box if c not in room and c not in out)


def outside_of(room, door):
    """The cell outside a doorway: beyond it, away from the room."""
    adjacent = [c for c in _sides(door) if c in set(room)]
    inner = adjacent[0] if len(adjacent) == 1 else None
    return None if inner is None else (2 * door[0] - inner[0], 2 * door[1] - inner[1])


class Grid:
    """The building pieces by cell, and the floor under each cell."""

    def __init__(self, pieces, terrain):
        self.terrain = terrain
        self.columns = {}  # (ix, iz) -> [(bottom, top, name)]
        self.supports = {}  # settled, aligned pieces covering a whole cell, for walls and roofs
        for p in pieces:
            (x, y, z), (sx, sy, sz) = p["pos"], p["size"]
            for ix in _cells(x - sx / 2, x + sx / 2):
                for iz in _cells(z - sz / 2, z + sz / 2):
                    span = (y - sy / 2, y + sy / 2, p["name"])
                    self.columns.setdefault((ix, iz), []).append(span)
                    if (p.get("anchored", True) and p.get("aligned", True) and p.get("settled", True)
                            and abs(ix * CELL - x) + CELL / 2 <= sx / 2 + GAP
                            and abs(iz * CELL - z) + CELL / 2 <= sz / 2 + GAP):
                        self.supports.setdefault((ix, iz), []).append(span)
        self.floors = {}

    def floor(self, c):
        if c not in self.floors:
            x, z = c[0] * CELL, c[1] * CELL
            tops = [t["pos"][1] + t["size"][1] / 2 for t in self.terrain
                    if abs(x - t["pos"][0]) <= t["size"][0] / 2 and abs(z - t["pos"][2]) <= t["size"][2] / 2]
            self.floors[c] = max(tops) if tops else None
        return self.floors[c]

    def filling(self, c, floor, up_to=CLEAR):
        """The pieces in the cell between its floor and `up_to` above it: what keeps Godling from standing there."""
        return [(b, name) for b, t, name in self.columns.get(c, ()) if b < floor + up_to and t > floor + GAP]

    def clear(self, c, floor, up_to=CLEAR):
        actual = self.floor(c)
        return actual is not None and abs(actual - floor) <= FLAT and not self.filling(c, floor, up_to)

    def standing(self, c, floor):
        """How high the pieces in the cell stand from its floor, stacked without a gap."""
        level = floor
        for b, t, _ in sorted(self.supports.get(c, ())):
            if b <= level + GAP:
                level = max(level, t)
        return level - floor

    def roof(self, c, floor):
        """The underside of what is over the cell with room under it to stand, or None."""
        over = [b for b, t, _ in self.supports.get(c, ()) if floor + CLEAR - 0.1 <= b <= floor + OVER]
        return min(over) if over else None


def judge(grid, room, floor):
    """How a room (a set of cells) stands as a house against the benchmark, part by part. Without a roof up yet it is
    judged against the roof it would have on walls three blocks high (ROOF_AT). Returns a dict:
      cells, ring, top (the roof's underside above the floor), square (two by two or more), filled (cells inside that
      are not clear), bare (cells inside with no roof over them), doors (the doorways that would do), gaps (the other
      openings to the ground: cells beside the room clear to stand in), short (the rest of the ring, standing lower than
      the roof), uncovered (cells of the ring with nothing over them at the roof), house (all of it holds).
    The ring holds the room's posts too (ADR-033: the cells it closes round, `posts`), judged as its walls are; they
    count as cells inside for the room's two by two."""
    room = sorted(set(room))
    posts = enclosed(room)
    around = sorted(set(ring(room)) | set(posts))
    undersides = [grid.roof(c, floor) for c in room]
    roofed = [u for u in undersides if u is not None]
    top = max(roofed) - floor if roofed else ROOF_AT
    filled = [c for c in room if not grid.clear(c, floor)]
    floorless = [c for c in room if grid.floor(c) is None]
    unlevel = [c for c in room if grid.floor(c) is not None and abs(grid.floor(c) - floor) > FLAT]
    hanging = [c for c in filled if grid.filling(c, floor)
               and min(b for b, _ in grid.filling(c, floor)) >= floor + LAYER - GAP]  # a roof too low
    bare = [c for c, u in zip(room, undersides) if u is None]

    def doorway(c):  # open from the floor to the roof, on one floor with the room, onto open ground
        out = outside_of(room, c)
        return grid.clear(c, floor, up_to=top - GAP) and out is not None and grid.clear(out, floor)
    near = [c for c in sides(room) if c not in posts]
    doors = [c for c in near if doorway(c)]
    gaps = [c for c in near if c not in doors and grid.clear(c, floor)]
    short = [c for c in around if c not in doors and c not in gaps and grid.standing(c, floor) < top - GAP]

    def covered(c):  # the roof over this cell of the ring: on top of the wall, or over the doorway
        if c in doors or c in gaps:
            u = grid.roof(c, floor)
            return u is not None and u <= floor + top + GAP
        return grid.standing(c, floor) >= top + LAYER - 2 * GAP
    uncovered = [c for c in around if not covered(c)]
    square = squared(room + posts)
    house = (square and len(room) <= MOST and not filled and not bare and len(doors) == 1 and not gaps
             and not short and not uncovered and top > HEADROOM)
    return {"cells": room, "posts": posts, "ring": around, "top": top, "square": square, "filled": filled,
            "hanging": hanging, "bare": bare, "floorless": floorless, "unlevel": unlevel,
            "doors": doors, "gaps": gaps, "short": short, "uncovered": uncovered, "floor": floor, "house": house}


def _rooms(grid, cells, floor_of, roofed_only, space=False):
    """Connected groups of clear cells among `cells` (only those with a roof over them, if `roofed_only`), without their
    doorways. With `space`, every cell that is not a wall two blocks high counts, clear or not: the room of a build, with
    whatever lies in it."""
    def room_like(c):
        if floor_of(c) is None:
            return False
        if space:
            return grid.standing(c, floor_of(c)) < 2 * LAYER - GAP
        return grid.clear(c, floor_of(c)) and (not roofed_only or grid.roof(c, floor_of(c)) is not None)
    left = {c for c in cells if room_like(c)}
    while left:
        seed = left.pop()
        floor = floor_of(seed)
        room, queue = {seed}, deque([seed])
        while queue:
            for n in _sides(queue.popleft()):
                if n in left and grid.floor(n) is not None and abs(grid.floor(n) - floor) <= FLAT:
                    left.discard(n)
                    room.add(n)
                    queue.append(n)
        yield _peel(grid, room, floor), floor


def _peel(grid, room, floor):
    """A room without its doorway: a clear cell sticking out of the room between two walls, beside a cell with more of
    the room round it, and leading out (no wall beyond it), is the doorway, not the room. A doorway clear up to the
    roof, with the roof over it, is as clear and as roofed as the room."""
    def wall(c):
        return grid.standing(c, floor) >= 2 * LAYER - GAP

    def doorway_shaped(c):
        inner = [n for n in _sides(c) if n in room]
        if len(inner) != 1 or sum(n in room for n in _sides(inner[0])) < 2:
            return False
        dx, dz = c[0] - inner[0][0], c[1] - inner[0][1]
        return (wall((c[0] + dz, c[1] + dx)) and wall((c[0] - dz, c[1] - dx))
                and not wall((c[0] + dx, c[1] + dz)))
    return set(room) - {c for c in room if doorway_shaped(c)}


def houses(pieces, terrain):
    """The houses among the pieces: the roofed rooms that pass the benchmark. The build measure counts these."""
    grid = Grid(pieces, terrain)
    roofed = {c for c, spans in grid.supports.items() if grid.floor(c) is not None
              and any(b > grid.floor(c) + GAP for b, _, _ in spans)}
    found = []
    for room, floor in _rooms(grid, roofed, grid.floor, roofed_only=True):
        verdict = judge(grid, room, floor) if room else None
        if verdict and verdict["house"]:
            found.append(verdict)
    return found


def shortfalls(v):
    """What a room is short of as a house, in the order a builder sees to them, in words (empty when it is one)."""
    out = []
    n = len(v["cells"])
    posts = v.get("posts", [])
    if not v["square"]:
        out.append(f"the room inside is {n} cell{'s' if n != 1 else ''}, at {_list(v['cells'], 4)}: a house's room holds "
                   "at least two by two cells" + (", its posts counted" if posts else ""))
    if v["floorless"]:
        out.append(f"there is no ground under {_list(v['floorless'], 4)}: choose a site with a real floor")
    if v["unlevel"]:
        out.append(f"the ground is not level with the room at {_list(v['unlevel'], 4)}: choose level ground")
    standing_in = [c for c in v["filled"] if c not in v["hanging"] + v["floorless"] + v["unlevel"]]
    if standing_in:
        out.append(f"the room is not clear at {_list(standing_in, 4)}")
    if v["hanging"]:
        out.append(f"the roof over {_list(v['hanging'], 4)} hangs too low to stand under: it needs more than 5 of room")
    if not v["doors"] and v["gaps"]:
        out.append(f"the opening at {_list(v['gaps'], 4)} is no doorway: a doorway is open up to the roof and leads onto "
                   "open ground")
    elif not v["doors"]:
        out.append("there is no doorway: leave one cell on a side open up to the roof")
    elif v["gaps"] or len(v["doors"]) > 1:
        openings = v["gaps"] + v["doors"][1:]
        out.append(f"the walls are open at {_list(openings, 4)} as well as the doorway at {at(v['doors'][0])}: a house "
                   "has one doorway")
    short_walls = [c for c in v["short"] if c not in posts]
    short_posts = [c for c in v["short"] if c in posts]
    if short_walls:
        out.append(f"the walls do not reach the roof ({v['top']:.1f} up) at {_list(short_walls)}, corners too")
    if short_posts:
        out.append(f"the post{'s' if len(short_posts) > 1 else ''} at {_list(short_posts)} "
                   f"{'do' if len(short_posts) > 1 else 'does'} not reach the roof ({v['top']:.1f} up)")
    if v["bare"]:
        out.append(f"there is no roof over {_list(v['bare'], 4)} inside")
    elif v["top"] <= HEADROOM and not v["hanging"]:
        out.append(f"the roof is only {v['top']:.1f} up, no higher than you")
    covered_short = [c for c in v["uncovered"] if c not in v["short"]]
    if [c for c in covered_short if c not in posts]:
        out.append(f"the roof does not cover the walls and doorway at {_list([c for c in covered_short if c not in posts])}")
    if [c for c in covered_short if c in posts]:
        out.append(f"the roof does not cover the post at {_list([c for c in covered_short if c in posts])}")
    return out


def assess(pieces, terrain, build):
    """How a build (names of its pieces) stands as a house, in words for the mind: that it is one, or what it is short
    of. The room judged is the clear space in the build's outline that comes nearest to a house."""
    grid = Grid(pieces, terrain)
    mine = [c for c, spans in grid.columns.items() if any(name in build for _, _, name in spans)]
    if not mine:
        return ""
    x0, x1 = min(c[0] for c in mine), max(c[0] for c in mine)
    z0, z1 = min(c[1] for c in mine), max(c[1] for c in mine)
    outline = [(ix, iz) for ix in range(x0 + 1, x1) for iz in range(z0 + 1, z1)]
    rooms = [judge(grid, room, floor) for room, floor in _rooms(grid, outline, grid.floor, False, space=True)
             if room and len(room) <= MOST]
    if not rooms:
        return "it encloses no space yet"
    best = min(rooms, key=lambda r: (not r["house"], len(shortfalls(r)), -len(r["cells"])))
    if best["house"]:
        n, k = len(best["cells"]) + len(best["posts"]), len(best["posts"])
        posts = f", {k} of them {'a post' if k == 1 else 'posts'}" if k else ""
        return f"a house: {n} cells inside{posts}, the doorway at {at(best['doors'][0])}"
    return "; ".join(shortfalls(best))


def mending(times):
    """How many times as fast a fed body mends in a house (main.lua HouseMends, ADR-033), in words: "twice", "2.5
    times". A world that does not say mends twice as fast, as before ADR-033."""
    times = times or 2
    return {2: "twice", 3: "three times", 4: "four times"}.get(times) or f"{times:g} times"


def cell_of(xz):
    """The cell a point [x, z] (or {"x": x, "z": z}) lies in."""
    if isinstance(xz, str):
        xz = json.loads(xz)
    if isinstance(xz, dict):
        xz = (xz["x"], xz["z"])
    return (round(float(xz[0]) / CELL), round(float(xz[1]) / CELL))


def _points(v):
    """A list of points, as the mind wrote it: a list, or a list written out as a string."""
    v = json.loads(v) if isinstance(v, str) else v
    if not isinstance(v, list):
        raise TypeError(v)
    return sorted({cell_of(c) for c in v})


def layout(inside, door, posts=None):
    """A house the mind chose, read from its reply: (the cells inside, the doorway's cell, the posts' cells), or a
    reason it cannot be one. The cells inside must touch one another side by side and hold a square two by two; the
    doorway is a cell beside them, on a side, not a corner. A post (ADR-033) is one of the cells inside, standing alone
    with the room on all four sides of it; a room wider than two cells needs them to hold its roof up. A list written
    out as a string is read as one (run hp-proj4 sent "[[-107.5, -37.5], ...]", copying the shape's description)."""
    try:
        cells = _points(inside)
        door = cell_of(door)
    except (TypeError, ValueError, IndexError, KeyError):
        return "the cells inside and the doorway must each be a point [x, z]"
    try:
        posts = _points(posts) if posts not in (None, "") else []
    except (TypeError, ValueError, IndexError, KeyError):
        return "the posts must each be a point [x, z] inside the house"
    if not cells:
        return "a house needs cells inside"
    if len(cells) > MOST:
        return f"{len(cells)} cells inside is more than a house: at most {MOST}"
    stray = _apart(cells)
    if stray:
        return "the cells inside must touch one another side by side: " + ", ".join(at(c) for c in stray)
    for p in posts:
        if p not in cells:
            return f"the post at {at(p)} must be one of the cells inside"
        if any(n not in cells or n in posts for n in _sides(p)):
            return (f"the post at {at(p)} must have the room on all four sides of it: a post stands alone inside, clear "
                    "of the walls and of other posts")
    room = [c for c in cells if c not in posts]
    if _apart(room):
        return f"the posts must leave the room in one piece: {_list(_apart(room), 4)} would be cut off from the rest"
    if not squared(cells):
        return f"the room must hold at least two by two cells, a square 5 across: {_list(cells, 4)} does not"
    if door not in sides(cells):
        return f"the doorway at {at(door)} must be a cell beside the room on one of its sides, not in it, at a corner or away"
    issue = guidance_issue(room, door, posts)
    return issue if issue else (cells, door, posts)


def _apart(cells):
    """The cells not joined side by side to the first of them."""
    cells = sorted(cells)
    if not cells:
        return []
    joined, queue = {cells[0]}, [cells[0]]
    while queue:
        for n in _sides(queue.pop()):
            if n in cells and n not in joined:
                joined.add(n)
                queue.append(n)
    return [c for c in cells if c not in joined]


def _along(c, axis):
    """The cells either side of `c` along an axis: a log three long centred on `c` lies on these and `c`."""
    return ((c[0] - 1, c[1]), (c[0] + 1, c[1])) if axis == "x" else ((c[0], c[1] - 1), (c[0], c[1] + 1))


SEARCH = 20000  # ways of laying the roof tried before a layout is given up as one with no roof


def roof_layout(grid, room, door, walls, floor, top, posts=()):
    """Where each piece of the roof goes, as a builder lays it (ADR-019, after run hp-full2: a lintel laid across the
    doorway rested on nothing, and the doorway's flank walls had been capped first, so the right way round there was no
    room for it; posts and beams after ADR-033). A log is three cells long and stays up resting on its middle, or with
    both ends on something; a block stays up on top of something. In this order:
    - the doorway's lintel: a log along the wall, centred on the doorway, resting on the two wall cells beside it;
    - over the room, logs, each lying on cells nothing else lies on, every cell of the room under exactly one:
      - centred on a wall beside a cell, not the doorway or the lintel's walls, along the line from that wall to the
        cell, resting on its middle and reaching in over it (a log three cells long cannot reach across a room two
        cells wide);
      - centred on a post, resting on its middle and reaching over the cells either side of it;
      the first way that covers the whole room, trying them in that order, cell by cell (a beam across a cell with its
      ends on two supports would take two tops for one cell: no room needs one);
    - on the walls and posts left over, a block on top.
    Returns {"lintel": (axis, (support, support)), "logs": [{"centre", "axis", "kind" ("wall" or "post"), "over" (the
    room's cells under it)}], "caps": [wall and post cells], "unsupported": [room cells no log was laid over], "loose":
    [room cells with no wall or post to rest a log on], "stuck_by": [the supports of the first cell left without one]}."""
    room, posts = sorted(set(room)), sorted(set(posts))
    inner = next((c for c in _sides(door) if c in set(room)), None)
    if inner is None:
        return {"lintel": None, "logs": [], "caps": list(walls) + posts, "unsupported": list(room), "loose": [],
                "stuck_by": []}
    out_x = door[0] != inner[0]  # the doorway leads out along x: its wall runs along z
    lintel_axis = "z" if out_x else "x"
    flanks = tuple(sorted(_along(door, lintel_axis)))
    in_room, on_post, on_wall = set(room), set(posts), set(walls) - set(flanks)

    def free_at_roof(c):  # nothing yet on top of this cell, where the roof goes
        return not any(floor + top - GAP <= b < floor + top + LAYER - GAP for b, _, _ in grid.columns.get(c, ()))

    beams = []
    for s in sorted(on_wall | on_post):  # a log centred on a wall or a post, along the line to the room
        for axis in ("x", "z"):
            ends = _along(s, axis)
            over = [c for c in ends if c in in_room]
            if over:
                beams.append({"centre": s, "axis": axis, "kind": "post" if s in on_post else "wall", "over": over,
                              "cells": {s, *ends}})
    rank = {"wall": 0, "post": 1}

    def key(beam):  # walls first as before ADR-033, and those whose tops (and the cells beyond) are still free
        rest = [x for x in sorted(beam["cells"]) if x not in beam["over"] and x != beam["centre"]]
        return (rank[beam["kind"]], not free_at_roof(beam["centre"]), not all(free_at_roof(x) for x in rest),
                beam["centre"], beam["axis"])
    options = {c: sorted((b for b in beams if c in b["over"]), key=key) for c in room}
    used, covered, chosen, tried = set(flanks) | {door}, set(), [], [0]

    def lay(cells):
        if tried[0] >= SEARCH:
            return False
        tried[0] += 1
        left = [c for c in cells if c not in covered]
        if not left:
            return True
        c = left[0]
        for beam in options[c]:
            if beam["cells"] & used or any(x in covered for x in beam["over"]):
                continue
            used.update(beam["cells"])
            covered.update(beam["over"])
            chosen.append(beam)
            if all(any(not (b["cells"] & used) and not any(x in covered for x in b["over"]) for b in options[n])
                   for n in left if n not in covered) and lay(left):
                return True
            chosen.pop()
            covered.difference_update(beam["over"])
            used.difference_update(beam["cells"])
        return False

    loose = [c for c in room if not options[c]]
    stuck_by = []
    if loose or not lay(room):  # no way covers it all: laid cell by cell, first way first, to say where it runs short
        chosen, used, covered = [], set(flanks) | {door}, set()
        for c in room:
            beam = next((b for b in options[c] if not b["cells"] & used and not any(x in covered for x in b["over"])),
                        None) if c not in covered else None
            if beam:
                chosen.append(beam)
                used.update(beam["cells"])
                covered.update(beam["over"])
        stuck = next((c for c in room if c not in covered and options[c]), None)
        stuck_by = sorted({b["centre"] for b in options[stuck]}) if stuck else []
    logs = [{k: v for k, v in b.items() if k != "cells"} for b in sorted(chosen, key=lambda b: min(b["over"]))]
    taken = set(flanks) | {door} | {x for b in chosen for x in b["cells"]}
    caps = [w for w in list(walls) + posts if w not in taken]
    covered = {c for b in chosen for c in b["over"]}
    return {"lintel": (lintel_axis, flanks), "logs": logs, "caps": caps, "loose": loose,
            "unsupported": [c for c in room if c not in covered], "stuck_by": stuck_by}


def guidance_issue(room, door, posts=()):
    """The guided roof method needs the doorway's lintel resting on wall cells, and a log over every cell of the room,
    each resting on a wall or a post, none lying where another does."""
    inside = sorted(set(room) | set(posts))
    if outside_of(inside, door) is None:
        return f"the doorway at {at(door)} must have exactly one room cell beside it and lead straight outside"
    walls = [c for c in ring(inside) if c != door]
    roof = roof_layout(Grid([], []), room, door, walls, 0, ROOF_AT, posts)
    if any(c not in walls for c in roof["lintel"][1]):
        return f"the doorway at {at(door)} needs a wall cell on each side for its lintel"
    if not roof["unsupported"]:
        return ""
    if roof["loose"]:
        return (f"nothing holds up the roof over {_list(roof['loose'], 4)}: a log three blocks long reaches one cell "
                "from the wall or post it rests on, so every cell inside must lie beside a wall or a post (not the "
                "doorway or the walls either side of it); stand posts inside, or make the room at most two cells wide")
    # Every cell has something beside it, but they cannot all be used at once: say where it runs short, laying the logs
    # cell by cell as the plan would.
    stuck, held_by = next(c for c in roof["unsupported"] if c not in roof["loose"]), roof["stuck_by"]
    by = " and ".join(f"the {'post' if c in set(posts) else 'wall'} at {at(c)}" for c in held_by) or "what is beside it"
    return (f"the roof over {at(stuck)} has nothing left to rest on: {by} beside it hold{'s' if len(held_by) == 1 else ''} "
            "another log already, and each wall or post holds one; stand another post beside it, or move the doorway")


def _turn(axis):
    return f"along {axis} (turn {0 if axis == 'x' else 90})"


def plan(pieces, terrain, inside, door, posts=()):
    """How far a house the mind chose (cells from layout()) has come against the benchmark: what is done, what is still
    to do in the order a builder does it (the walls and posts, the room and doorway, the roof), the next step in words,
    and the pieces that are its own: in its walls, posts and roof, but not what fills the room, the doorway or the way
    out. Returns {"house", "next", "done", "score", "pieces", "in_the_way"}; the score counts what stands, so it grows as
    the house does."""
    grid = Grid(pieces, terrain)
    posts = sorted({tuple(p) for p in posts})
    inside = sorted({tuple(c) for c in inside})
    room = [c for c in inside if c not in posts]
    issue = "" if room else "choose cells for the room and a doorway"
    floors = {c: grid.floor(c) for c in inside}
    floorless = [c for c in inside if floors[c] is None]
    if floorless:
        issue = f"choose a site with a real floor: there is no ground under {_list(floorless, 4)}"
    elif room and max(floors.values()) - min(floors.values()) > FLAT:
        issue = f"choose level ground: the room's floor changes height across {_list(inside, 4)}"
    if issue:
        return {"house": False, "next": issue, "done": [], "score": 0, "pieces": [], "in_the_way": []}
    floor = grid.floor(room[0])
    v = judge(grid, room, floor)
    issue = guidance_issue(room, door, posts) if not (v["house"] and v["doors"] == [door]) else ""
    if issue:
        return {"house": False, "next": issue, "done": [], "score": 0, "pieces": [], "in_the_way": []}
    top = v["top"]
    walls = [c for c in v["ring"] if c != door and c not in posts]
    low = [c for c in walls if grid.standing(c, floor) < top - GAP]
    low_posts = [c for c in posts if grid.standing(c, floor) < top - GAP]
    out = outside_of(inside, door)
    door_open = grid.clear(door, floor, up_to=top - GAP)
    out_open = out is not None and grid.clear(out, floor)
    capped = [c for c in walls + posts if grid.standing(c, floor) >= top + LAYER - 2 * GAP]
    lintel = grid.roof(door, floor)
    lintel = lintel is not None and lintel <= floor + top + GAP
    bare = v["bare"]
    layout = roof_layout(grid, room, door, walls, floor, top, posts)
    axis, flanks = layout["lintel"]

    def at_roof(c):  # what sits on top of this cell, where the roof goes
        return sorted({name for b, _, name in grid.columns.get(c, ()) if floor + top - GAP <= b < floor + top + LAYER - GAP})
    # A stone capping one of the lintel's walls before the lintel is on leaves it no room: it is in the way.
    blockers = sorted({n for f in flanks for n in at_roof(f)} - set(at_roof(door))) if not lintel else []
    # So does one on the wall or post a room log rests on, or where its other end goes, while the cells it covers are
    # bare: left as the house's own, the body would never lift it and the log would never go on.
    beds = {}
    for beam in layout["logs"]:
        if any(c in bare for c in beam["over"]):
            cells = [x for x in (beam["centre"], *_along(beam["centre"], beam["axis"]))
                     if x not in beam["over"] and at_roof(x)]
            if cells:
                beds[id(beam)] = (cells, sorted({n for x in cells for n in at_roof(x)}))
    in_the_way = ({name for c in room for _, name in grid.filling(c, floor)}
                  | {name for _, name in grid.filling(door, floor, up_to=top - GAP)}
                  | ({name for _, name in grid.filling(out, floor)} if out is not None else set())
                  | set(blockers) | {n for _, found in beds.values() for n in found})
    own = sorted(({name for c in walls + posts for b, _, name in grid.columns.get(c, ()) if b < floor + top + LAYER}
                  | {name for c in room + [door] for b, _, name in grid.columns.get(c, ())
                     if floor + top - GAP <= b < floor + top + LAYER}) - in_the_way)
    centre = floor + top + LAYER / 2  # a roof piece one block thick lying on the walls
    one = len(posts) == 1
    done = ((["the walls stand three blocks high all round"] if not low else [])
            + ([f"the post{'' if one else 's'} {'stands' if one else 'stand'} three blocks high"]
               if posts and not low_posts else [])
            + (["the room is clear"] if not v["filled"] else [])
            + ([f"the doorway at {at(door)} is open up to the roof"] if door_open else [])
            + (["the roof is over the room"] if not bare else [])
            + ([f"the roof covers the walls{(', the post' if one else ', the posts') if posts else ''} and the doorway"]
               if len(capped) == len(walls) + len(posts) and lintel else []))
    if low or low_posts:
        step = ("walls three blocks high all round the room, corners too, but for the doorway at " + at(door)
                + (f", and the post{'' if one else 's'} inside at {_list(posts, 8)} three blocks high (a log stood on "
                   "end)" if posts else "") + ": "
                + "; ".join(filter(None, (
                    ", ".join(f"{at(c)} stands {grid.standing(c, floor):.1f}" for c in low[:8])
                    + (f" and {len(low) - 8} more" if len(low) > 8 else ""),
                    ", ".join(f"the post at {at(c)} stands {grid.standing(c, floor):.1f}" for c in low_posts)))))
    elif v["filled"]:
        step = "clear the room: " + ", ".join(
            f"{at(c)} ({name} {'hangs too low over it' if b >= floor + LAYER - GAP else 'fills it'})"
            for c in v["filled"][:3] for b, name in sorted(grid.filling(c, floor))[:1])
    elif not door_open:
        step = (f"clear the doorway at {at(door)} up to the roof: "
                + " and ".join(sorted({n for _, n in grid.filling(door, floor, up_to=top - GAP)})[:2]) + " in it")
    elif not out_open:
        names = sorted({n for _, n in grid.filling(out, floor)})[:2] if out is not None else []
        step = (f"clear the way out of the doorway, at {at(out)}" + (f": {' and '.join(names)} in it" if names else
                                                                     ": the ground there is not level with the room"))
    elif bare or len(capped) < len(walls) + len(posts) or not lintel:
        needs = []
        if not lintel:
            if blockers:
                needs.append(f"first take {' and '.join(blockers)} off the top{'s' if len(blockers) > 1 else ''} of "
                             f"{' and '.join(at(f) for f in flanks if at_roof(f))} (reach up from a step one block high "
                             "beside them): the doorway's lintel rests there")
            needs.append(f"{'then ' if blockers else ''}over the doorway at {at(door)}, a log {_turn(axis)} centred on it, "
                         f"resting on the walls at {at(flanks[0])} and {at(flanks[1])}")
        for beam in layout["logs"]:
            if not any(c in bare for c in beam["over"]):
                continue
            over = " and ".join(at(c) for c in beam["over"])
            if id(beam) in beds:
                cells, found = beds[id(beam)]
                needs.append(f"first take {' and '.join(found)} off the top{'s' if len(cells) > 1 else ''} of "
                             f"{' and '.join(at(x) for x in cells)} (reach up from "
                             + ("a step one block high beside " + ('them' if len(cells) > 1 else 'it')
                                if beam["kind"] == "wall" else "the floor inside")
                             + f"): the log over {over} rests there")
            then = "then " if id(beam) in beds else ""
            if beam["kind"] == "wall":
                needs.append(f"{then}over {over}, a log {_turn(beam['axis'])} centred on the wall at {at(beam['centre'])}, "
                             f"resting on its middle and reaching in over {over}")
            else:
                needs.append(f"{then}over {over}, a log {_turn(beam['axis'])} centred on the post at "
                             f"{at(beam['centre'])}, resting on its middle (set it standing on the floor beside the post)")
        uncapped = [c for c in layout["caps"] if c not in capped]
        if [c for c in uncapped if c not in posts]:
            needs.append(f"a block on top of the walls at {_list([c for c in uncapped if c not in posts])}")
        if [c for c in uncapped if c in posts]:
            needs.append(f"a block on top of the post at {_list([c for c in uncapped if c in posts])} (set it standing on "
                         "the floor beside it)")
        where = ("set from a step one block high outside the walls, never in the doorway or the way out" if not posts
                 else "over the walls, set from a step one block high outside them, never in the doorway or the way out; "
                      f"over the post{'' if one else 's'}, from the floor inside")
        step = f"the roof, every piece at height {centre:.2f} ({where}): " + "; ".join(needs)
    else:
        step = f"none: it is a house. Walk in by the doorway at {at(door)} and stand inside"
    score = ((len(walls) - len(low)) + (len(posts) - len(low_posts)) + (len(room) - len(v["filled"])) + door_open
             + out_open + (len(room) - len(bare)) + len(capped) + bool(lintel))
    return {"house": v["house"] and v["doors"] == [door], "next": step, "done": done, "score": score, "pieces": own,
            "in_the_way": sorted(in_the_way)}
