"""What a house is (ADR-019, the first-house benchmark): one check for the build measure and for the mind, so they never
disagree. The world has its own copy of it in world/main.lua (houseAt), for whether the body stands in a house; the
tests hold the two to the same layouts.

A house is a structure:
- a room of clear cells, at least two by two, on one floor, where Godling can stand (a block in the room fails it);
- walls all round it, corners too, each filled from the floor up to the roof without a gap, but for one doorway;
- the doorway on a side (not a corner), open from the floor up to the roof, onto open ground outside;
- a roof over all of it, the walls and the doorway too, its underside more than five above the room's floor (the
  body is exactly five tall, so on the world's grid that is three blocks up).
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


def outside_of(room, door):
    """The cell outside a doorway: beyond it, away from the room."""
    inner = next((c for c in _sides(door) if c in set(room)), None)
    return None if inner is None else (2 * door[0] - inner[0], 2 * door[1] - inner[1])


class Grid:
    """The building pieces by cell, and the floor under each cell."""

    def __init__(self, pieces, terrain):
        self.terrain = terrain
        self.columns = {}  # (ix, iz) -> [(bottom, top, name)]
        for p in pieces:
            (x, y, z), (sx, sy, sz) = p["pos"], p["size"]
            for ix in _cells(x - sx / 2, x + sx / 2):
                for iz in _cells(z - sz / 2, z + sz / 2):
                    self.columns.setdefault((ix, iz), []).append((y - sy / 2, y + sy / 2, p["name"]))
        self.floors = {}

    def floor(self, c):
        if c not in self.floors:
            x, z = c[0] * CELL, c[1] * CELL
            tops = [t["pos"][1] + t["size"][1] / 2 for t in self.terrain
                    if abs(x - t["pos"][0]) <= t["size"][0] / 2 and abs(z - t["pos"][2]) <= t["size"][2] / 2]
            self.floors[c] = max(tops) if tops else 0.0
        return self.floors[c]

    def filling(self, c, floor, up_to=CLEAR):
        """The pieces in the cell between its floor and `up_to` above it: what keeps Godling from standing there."""
        return [(b, name) for b, t, name in self.columns.get(c, ()) if b < floor + up_to and t > floor + GAP]

    def clear(self, c, floor, up_to=CLEAR):
        return abs(self.floor(c) - floor) <= FLAT and not self.filling(c, floor, up_to)

    def standing(self, c, floor):
        """How high the pieces in the cell stand from its floor, stacked without a gap."""
        level = floor
        for b, t, _ in sorted(self.columns.get(c, ())):
            if b <= level + GAP:
                level = max(level, t)
        return level - floor

    def roof(self, c, floor):
        """The underside of what is over the cell with room under it to stand, or None."""
        over = [b for b, t, _ in self.columns.get(c, ()) if floor + CLEAR - 0.1 <= b <= floor + OVER]
        return min(over) if over else None


def judge(grid, room, floor):
    """How a room (a set of cells) stands as a house against the benchmark, part by part. Without a roof up yet it is
    judged against the roof it would have on walls three blocks high (ROOF_AT). Returns a dict:
      cells, ring, top (the roof's underside above the floor), square (two by two or more), filled (cells inside that
      are not clear), bare (cells inside with no roof over them), doors (the doorways that would do), gaps (the other
      openings to the ground: cells beside the room clear to stand in), short (the rest of the ring, standing lower than
      the roof), uncovered (cells of the ring with nothing over them at the roof), house (all of it holds)."""
    room = sorted(set(room))
    around = ring(room)
    undersides = [grid.roof(c, floor) for c in room]
    roofed = [u for u in undersides if u is not None]
    top = max(roofed) - floor if roofed else ROOF_AT
    filled = [c for c in room if not grid.clear(c, floor)]
    hanging = [c for c in filled if min(b for b, _ in grid.filling(c, floor)) >= floor + LAYER - GAP]  # a roof too low
    bare = [c for c, u in zip(room, undersides) if u is None]

    def doorway(c):  # open from the floor to the roof, on one floor with the room, onto open ground
        out = outside_of(room, c)
        return grid.clear(c, floor, up_to=top - GAP) and out is not None and grid.clear(out, floor)
    near = sides(room)
    doors = [c for c in near if doorway(c)]
    gaps = [c for c in near if c not in doors and grid.clear(c, floor)]
    short = [c for c in around if c not in doors and c not in gaps and grid.standing(c, floor) < top - GAP]

    def covered(c):  # the roof over this cell of the ring: on top of the wall, or over the doorway
        if c in doors or c in gaps:
            u = grid.roof(c, floor)
            return u is not None and u <= floor + top + GAP
        return grid.standing(c, floor) >= top + LAYER - 2 * GAP
    uncovered = [c for c in around if not covered(c)]
    house = (squared(room) and len(room) <= MOST and not filled and not bare and len(doors) == 1 and not gaps
             and not short and not uncovered and top > HEADROOM)
    return {"cells": room, "ring": around, "top": top, "square": squared(room), "filled": filled, "hanging": hanging,
            "bare": bare,
            "doors": doors, "gaps": gaps, "short": short, "uncovered": uncovered, "floor": floor, "house": house}


def _rooms(grid, cells, floor_of, roofed_only, space=False):
    """Connected groups of clear cells among `cells` (only those with a roof over them, if `roofed_only`), without their
    doorways. With `space`, every cell that is not a wall two blocks high counts, clear or not: the room of a build, with
    whatever lies in it."""
    def room_like(c):
        if space:
            return grid.standing(c, floor_of(c)) < 2 * LAYER - GAP
        return grid.clear(c, floor_of(c)) and (not roofed_only or grid.roof(c, floor_of(c)) is not None)
    left = {c for c in cells if room_like(c)}
    while left:
        seed = left.pop()
        floor = floor_of(seed)
        room, queue = {seed}, deque([seed])
        while queue and len(room) <= MOST:
            for n in _sides(queue.popleft()):
                if n in left and abs(grid.floor(n) - floor) <= FLAT:
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
    roofed = {c for c, spans in grid.columns.items() if any(b > grid.floor(c) + GAP for b, _, _ in spans)}
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
    if not v["square"]:
        out.append(f"the room inside is {n} cell{'s' if n != 1 else ''}, at {_list(v['cells'], 4)}: a house's room holds "
                   "at least two by two cells")
    standing_in = [c for c in v["filled"] if c not in v["hanging"]]
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
    if v["short"]:
        out.append(f"the walls do not reach the roof ({v['top']:.1f} up) at {_list(v['short'])}, corners too")
    if v["bare"]:
        out.append(f"there is no roof over {_list(v['bare'], 4)} inside")
    elif v["top"] <= HEADROOM and not v["hanging"]:
        out.append(f"the roof is only {v['top']:.1f} up, no higher than you")
    covered_short = [c for c in v["uncovered"] if c not in v["short"]]
    if covered_short:
        out.append(f"the roof does not cover the walls and doorway at {_list(covered_short)}")
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
        n = len(best["cells"])
        return f"a house: {n} cells inside, the doorway at {at(best['doors'][0])}"
    return "; ".join(shortfalls(best))


def cell_of(xz):
    """The cell a point [x, z] (or {"x": x, "z": z}) lies in."""
    if isinstance(xz, str):
        xz = json.loads(xz)
    if isinstance(xz, dict):
        xz = (xz["x"], xz["z"])
    return (round(float(xz[0]) / CELL), round(float(xz[1]) / CELL))


def layout(inside, door):
    """A house the mind chose, read from its reply: (the cells inside, the doorway's cell), or a reason it cannot be
    one. The cells inside must touch one another side by side and hold a square two by two; the doorway is a cell
    beside them, on a side, not a corner. A list written out as a string is read as one (run hp-proj4 sent
    "[[-107.5, -37.5], ...]", copying the shape's description)."""
    try:
        inside, door = (json.loads(v) if isinstance(v, str) else v for v in (inside, door))
        if not isinstance(inside, list):
            raise TypeError(inside)
        room = sorted({cell_of(c) for c in inside})
        door = cell_of(door)
    except (TypeError, ValueError, IndexError, KeyError):
        return "the cells inside and the doorway must each be a point [x, z]"
    if not room:
        return "a house needs cells inside"
    if len(room) > MOST:
        return f"{len(room)} cells inside is more than a house: at most {MOST}"
    joined, queue = {room[0]}, [room[0]]
    while queue:
        for n in _sides(queue.pop()):
            if n in room and n not in joined:
                joined.add(n)
                queue.append(n)
    if len(joined) < len(room):
        return "the cells inside must touch one another side by side: " + ", ".join(at(c) for c in room if c not in joined)
    if not squared(room):
        return f"the room must hold at least two by two cells, a square 5 across: {_list(room, 4)} does not"
    if door not in sides(room):
        return f"the doorway at {at(door)} must be a cell beside the room on one of its sides, not in it, at a corner or away"
    return room, door


def plan(pieces, terrain, inside, door):
    """How far a house the mind chose (cells from layout()) has come against the benchmark: what is done, what is still
    to do in the order a builder does it (the walls, the room and doorway, the roof), the next step in words, and the
    pieces that are its own: in its walls and roof, but not what fills the room, the doorway or the way out.
    Returns {"house", "next", "done", "score", "pieces", "in_the_way"}; the score counts what stands, so it grows as
    the house does."""
    grid = Grid(pieces, terrain)
    room = sorted(inside)
    floor = grid.floor(room[0])
    v = judge(grid, room, floor)
    top = v["top"]
    walls = [c for c in v["ring"] if c != door]
    low = [c for c in walls if grid.standing(c, floor) < top - GAP]
    out = outside_of(room, door)
    door_open = grid.clear(door, floor, up_to=top - GAP)
    out_open = out is not None and grid.clear(out, floor)
    capped = [c for c in walls if grid.standing(c, floor) >= top + LAYER - 2 * GAP]
    lintel = grid.roof(door, floor)
    lintel = lintel is not None and lintel <= floor + top + GAP
    bare = v["bare"]
    in_the_way = ({name for c in room for _, name in grid.filling(c, floor)}
                  | {name for _, name in grid.filling(door, floor, up_to=top - GAP)}
                  | ({name for _, name in grid.filling(out, floor)} if out is not None else set()))
    own = sorted(({name for c in walls for b, _, name in grid.columns.get(c, ()) if b < floor + top + LAYER}
                  | {name for c in room + [door] for b, _, name in grid.columns.get(c, ())
                     if floor + top - GAP <= b < floor + top + LAYER}) - in_the_way)
    centre = floor + top + LAYER / 2  # a roof piece one block thick lying on the walls
    done = ((["the walls stand three blocks high all round"] if not low else [])
            + (["the room is clear"] if not v["filled"] else [])
            + ([f"the doorway at {at(door)} is open up to the roof"] if door_open else [])
            + (["the roof is over the room"] if not bare else [])
            + (["the roof covers the walls and the doorway"] if len(capped) == len(walls) and lintel else []))
    if low:
        step = ("walls three blocks high all round the room, corners too, but for the doorway at " + at(door) + ": "
                + ", ".join(f"{at(c)} stands {grid.standing(c, floor):.1f}" for c in low[:8])
                + (f" and {len(low) - 8} more" if len(low) > 8 else ""))
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
    elif bare or len(capped) < len(walls) or not lintel:
        needs = []
        if bare:
            needs.append(f"over the room at {_list(bare, 4)}, logs laid on the walls, each centred on a wall so it "
                         "rests on its middle and reaches one cell in (a log three cells long cannot reach across a "
                         "room two cells wide)")
        uncapped = [c for c in walls if c not in capped]
        if uncapped:
            needs.append(f"on top of the walls at {_list(uncapped)}")
        if not lintel:
            needs.append(f"over the doorway at {at(door)}, a log along the wall resting on the walls either side")
        step = (f"the roof, every piece at height {centre:.2f} (set from a step one block high outside the walls, never in "
                "the doorway): " + "; ".join(needs))
    else:
        step = f"none: it is a house. Walk in by the doorway at {at(door)} and stand inside"
    score = ((len(walls) - len(low)) + (len(room) - len(v["filled"])) + door_open + out_open + (len(room) - len(bare))
             + len(capped) + bool(lintel))
    return {"house": v["house"] and v["doors"] == [door], "next": step, "done": done, "score": score, "pieces": own,
            "in_the_way": sorted(in_the_way)}
