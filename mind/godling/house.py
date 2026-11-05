"""What a house is (ADR-019): one check for the build measure and for the mind, so they never disagree. The world has
its own copy of it in world/main.lua (houseAt), for the shelter the body feels; the tests hold the two to the same
layouts.

A house is a structure: at least one clear interior cell, where Godling can stand; walls at least two blocks high
round it, but for one doorway Godling can walk through; and a roof over every interior cell with more than five
units of headroom (the body is exactly five tall). Clear means Godling can stand there: a block filling the room
fails it. Shelter is something else: what the body feels where it stands (main.lua shelterOf). A lean-to keeps the
rain off long before it is a house.

Works on the building pieces and terrain as structures.py reads them (records with "pos" and "size", world-aligned),
cut into the world's grid of 2.5 cells.
"""
import math
from collections import deque

from .world import CUBE

CELL = LAYER = CUBE
HEADROOM = 2 * LAYER  # the body's height: a roof must leave more room than this
CLEAR = HEADROOM + 0.05  # a cell is clear when nothing lies in it from its floor up to here
WALL = 2 * LAYER - 0.1  # a wall stands at least two blocks high
OVER = 15.0  # a roof is something over the cell no higher than this above its floor
FLAT = 0.6  # floors this close are one floor: a doorway is walked through, not climbed
MOST = 64  # cells: a room bigger than this is open ground under something wide, not a house


def _cells(lo, hi):
    """Indices of the cells whose centres lie in [lo, hi)."""
    return range(math.ceil(lo / CELL - 1e-9), math.ceil(hi / CELL - 1e-9))


def _sides(c):
    return ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1))


def at(c):
    """A cell's centre in words."""
    return f"({c[0] * CELL:.1f}, {c[1] * CELL:.1f})"


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

    def filling(self, c, floor):
        """The pieces in the cell between its floor and head height: what keeps Godling from standing there."""
        return [(b, name) for b, t, name in self.columns.get(c, ()) if b < floor + CLEAR and t > floor + 0.15]

    def clear(self, c, floor):
        return abs(self.floor(c) - floor) <= FLAT and not self.filling(c, floor)

    def standing(self, c, floor):
        """How high the pieces in the cell stand from its floor, stacked without a gap."""
        level = floor
        for b, t, _ in sorted(self.columns.get(c, ())):
            if b <= level + 0.15:
                level = max(level, t)
        return level - floor

    def roof(self, c, floor):
        """The underside of what is over the cell with room under it to stand, or None."""
        over = [b for b, t, _ in self.columns.get(c, ()) if floor + CLEAR - 0.1 <= b <= floor + OVER]
        return min(over) if over else None


def judge(grid, room, floor):
    """How a room (a set of clear cells on one floor) stands as a house. Returns a dict: the cells, its doorways
    (clear cells beside it), its low walls (beside it, filled but less than two blocks high), the cells inside with a
    roof over them, and whether it is a house."""
    side = {n for c in room for n in _sides(c) if n not in room}
    doors = sorted(n for n in side if grid.clear(n, floor))
    low = sorted(n for n in side if n not in doors and grid.standing(n, floor) < WALL)
    roofed = sorted(c for c in room if grid.roof(c, floor) is not None)
    return {"cells": sorted(room), "doors": doors, "low": low, "roofed": roofed, "floor": floor,
            "house": len(doors) == 1 and not low and len(roofed) == len(room)}


def _rooms(grid, cells, floor_of, roofed_only):
    """Connected groups of clear cells among `cells` (only those with a roof over them, if `roofed_only`)."""
    left = {c for c in cells if grid.clear(c, floor_of(c)) and (not roofed_only or grid.roof(c, floor_of(c)) is not None)}
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
        yield room, floor


def houses(pieces, terrain):
    """The houses among the pieces: the rooms that pass the check (a roof over every cell, walls two blocks high
    round it, one doorway). The build measure counts these."""
    grid = Grid(pieces, terrain)
    roofed = {c for c, spans in grid.columns.items() if any(b > grid.floor(c) + 0.15 for b, _, _ in spans)}
    found = []
    for room, floor in _rooms(grid, roofed, grid.floor, roofed_only=True):
        verdict = judge(grid, room, floor)
        if len(room) <= MOST and verdict["house"]:
            found.append(verdict)
    return found


def _blocked(grid, c):
    """Why a cell under something cannot be stood in, in words, or None: a piece over it with too little room under
    it, or a piece filling it under a roof (with a gap between, unlike a post the roof rests on)."""
    floor = grid.floor(c)
    stack = grid.standing(c, floor)
    over = sorted((b, name) for b, _, name in grid.columns.get(c, ()) if b > floor + stack + 0.15 and b <= floor + OVER)
    if not over:
        return None
    if over[0][0] < floor + CLEAR:
        return f"{at(c)} has {over[0][1]} only {over[0][0] - floor:.1f} up, too low to stand under"
    if stack > 0.15:
        below = min((b, name) for b, _, name in grid.columns[c] if b <= floor + 0.15)[1]
        return f"{at(c)} under the roof is filled by {below}"
    return None


def assess(pieces, terrain, build):
    """How a build (names of its pieces) stands as a house, in words for the mind: that it is one, or what it is short
    of. The room judged is the clear space in the build's outline that comes nearest to a house."""
    grid = Grid(pieces, terrain)
    mine = [c for c, spans in grid.columns.items() if any(name in build for _, _, name in spans)]
    if not mine:
        return ""
    x0, x1 = min(c[0] for c in mine), max(c[0] for c in mine)
    z0, z1 = min(c[1] for c in mine), max(c[1] for c in mine)
    outline = [(ix, iz) for ix in range(x0, x1 + 1) for iz in range(z0, z1 + 1)]
    rooms = [judge(grid, room, floor) for room, floor in _rooms(grid, outline, grid.floor, roofed_only=False)
             if len(room) <= MOST]
    blocked = [why for why in (_blocked(grid, c) for c in outline) if why]
    best = min(rooms, key=lambda r: (not r["house"], abs(len(r["doors"]) - 1) + len(r["low"])
                                     + len(r["cells"]) - len(r["roofed"]), -len(r["roofed"]), -len(r["cells"])),
               default=None)
    if best and best["house"]:
        n = len(best["cells"])
        return f"a house: {n} cell{'s' if n != 1 else ''} inside, the doorway at {at(best['doors'][0])}"
    if blocked and (best is None or not best["roofed"]):  # the roof is up, but nobody could stand under it
        return "there is no room to stand under its roof: " + "; ".join(blocked[:2])
    if best is None or x1 - x0 < 2 and z1 - z0 < 2:
        return "it encloses no space yet"
    n, r = len(best["cells"]), len(best["roofed"])
    good, short = [], []
    if len(best["doors"]) == 1:
        good.append(f"the doorway at {at(best['doors'][0])} is clear")
    elif best["doors"]:
        short.append(f"the walls have {len(best['doors'])} gaps, at {', '.join(at(d) for d in best['doors'][:4])}: a "
                     "house has one doorway")
    else:
        short.append("there is no doorway to walk in by")
    if best["low"]:
        short.append(f"the wall is lower than two blocks at {', '.join(at(c) for c in best['low'][:4])}")
    elif len(best["doors"]) == 1:
        good.append("the walls stand two blocks high")
    if r == n:
        good.append(f"the roof covers the {'cell' if n == 1 else f'{n} cells'} inside")
    elif r == 0:
        short.append(f"there is no roof over the {'cell' if n == 1 else f'{n} cells'} inside, at "
                     f"{', '.join(at(c) for c in best['cells'][:4])}")
    else:
        bare = [c for c in best["cells"] if c not in best["roofed"]]
        short.append(f"the roof covers only {r} of the {n} cells inside (none over {', '.join(at(c) for c in bare[:4])})")
    return (", ".join(good) + ", but " if good else "") + "; ".join(short)


def cell_of(xz):
    """The cell a point [x, z] lies in."""
    return (round(float(xz[0]) / CELL), round(float(xz[1]) / CELL))


def layout(inside, door):
    """A house the mind chose, read from its reply: (the cells inside, the doorway's cell), or a reason it cannot be
    one. The cells inside must touch one another, side by side, and the doorway lie beside them."""
    try:
        room = sorted({cell_of(c) for c in inside})
        door = cell_of(door)
    except (TypeError, ValueError, IndexError, KeyError):
        return "the cells inside and the doorway must each be a point [x, z]"
    if not room:
        return "a house needs at least one cell inside"
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
    if door in room or not any(n in room for n in _sides(door)):
        return f"the doorway at {at(door)} must be a cell beside the room, not in it or away from it"
    return room, door


def plan(pieces, terrain, inside, door):
    """How far a house the mind chose (cells from layout()) has come: what stands, what is still to do in the order
    a builder does it (walls, a clear room and doorway, the roof), the next step in words, and the pieces that are
    its own: in its walls and over its room, but not what fills the room or blocks the doorway.
    Returns {"house", "next", "done", "score", "pieces"}; the score counts what stands, so it grows as the house does."""
    grid = Grid(pieces, terrain)
    room = sorted(inside)
    floor = grid.floor(room[0])
    side = {n for c in room for n in _sides(c) if n not in room}
    walls = sorted(side - {door})
    low = [n for n in walls if grid.standing(n, floor) < WALL]
    filled = [c for c in room if not grid.clear(c, floor)]
    blocked_door = not grid.clear(door, floor)
    bare = [c for c in room if grid.roof(c, floor) is None]
    in_the_way = {name for c in room + [door] for _, name in grid.filling(c, floor)}
    own = sorted(({name for n in walls for b, _, name in grid.columns.get(n, ()) if b < floor + 3 * LAYER}
                  | {name for c in room for b, _, name in grid.columns.get(c, ()) if b >= floor + CLEAR - 0.1})
                 - in_the_way)
    done = (["the walls stand two blocks high"] if not low else []) + (["the room is clear"] if not filled else [])         + ([f"the doorway at {at(door)} is clear"] if not blocked_door else [])         + (["the roof covers the room"] if not bare else [])
    if low:
        step = f"walls two blocks high at {', '.join(at(n) for n in low[:6])}" + (" and more" if len(low) > 6 else "")
    elif filled:
        step = "clear the room: " + ", ".join(
            f"{at(c)} ({name} {'hangs too low over it' if b >= floor + LAYER - 0.15 else 'fills it'})"
            for c in filled[:3] for b, name in sorted(grid.filling(c, floor))[:1])
    elif blocked_door:
        step = f"clear the doorway at {at(door)}: " + " and ".join(sorted({n for _, n in grid.filling(door, floor)})[:2])             + " in it"
    elif bare:
        step = (f"a roof over {', '.join(at(c) for c in bare[:6])}, with more than 5 of room under it (it rests on "
                "walls three blocks high, set from a step beside them)")
    else:
        step = f"none: it is a house. Walk in by the doorway at {at(door)} and stand inside"
    score = (len(walls) - len(low)) + (len(room) - len(filled)) + (not blocked_door) + (len(room) - len(bare))
    return {"house": not (low or filled or blocked_door or bare), "next": step, "done": done, "score": score,
            "pieces": own}
