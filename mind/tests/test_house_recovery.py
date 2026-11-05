"""Clearing a fallen piece out of the benchmark house (ADR-019): walk in by the doorway, pick up a loose block lying in
a cell inside, carry it out and set it down, walk back in, and the room is clear again. For each of the four cells
inside. The house's room is two cells wide: the body (two units wide) fits in a cell with a quarter unit to spare on
each side, so the spot it picks the block up from must be found from the body's real size and the walls round it."""
import math

import pytest

from godling import skills as sk
from godling.house import plan
from godling.skills import BODY_HEIGHT, BODY_RADIUS, STAND_MARGIN, Skills
from godling.structures import pieces_of, terrain_of
from godling.world import BODY_CENTRE_Y, PICKUP_RANGE
from helpers import block, ent, ground
from island import FakeTime, Island

C = 2.5
ROOM = [(0, 0), (0, 1), (1, 0), (1, 1)]
DOOR = (0, -1)


def benchmark():
    """The benchmark house (test_house.py house()): a room two by two at cells (0..1, 0..1), walls three blocks high
    all round it, corners too, the doorway south at (0, -1), the roof in layer 4 over all of it."""
    pieces = []
    for dx in range(-1, 3):
        for dz in range(-1, 3):
            if (dx, dz) in ROOM or (dx, dz) == DOOR:
                continue
            pieces += [block(f"Block_w{dx + 1}{dz + 1}{k}", dx * C, (k - 0.5) * C, dz * C) for k in (1, 2, 3)]
    logs = [("Log_S", 0, -1), ("Log_N", 0, 2), ("Log_W0", -1, 0), ("Log_E0", 2, 0), ("Log_W1", -1, 1), ("Log_E1", 2, 1)]
    pieces += [ent(name, (dx * C, 8.75, dz * C), (7.5, 2.5, 2.5)) for name, dx, dz in logs]
    return pieces + [block("Block_SE", 2 * C, 8.75, -C), block("Block_NE", 2 * C, 8.75, 2 * C)]


def room_to_spare(island, x, z):
    """How far the body's axis at (x, z) is from the nearest piece beside it, as the pieces lie now (all of them,
    held or not): walls and loose pieces that reach into the body's height, not the roof over its head."""
    gaps = []
    for e in island.ents.values():
        (px, py, pz), (sx, sy, sz) = e["position"], e["size"]
        if py - sy / 2 >= BODY_HEIGHT or py + sy / 2 <= 0.1 or e.get("attributes", {}).get("RenderRole") == "Ground":
            continue
        gaps.append(math.hypot(max(abs(x - px) - sx / 2, 0), max(abs(z - pz) - sz / 2, 0)))
    return min(gaps)


def inside(island):
    return any(abs(island.me[0] - cx * C) <= C / 2 and abs(island.me[2] - cz * C) <= C / 2 for cx, cz in ROOM)


@pytest.mark.parametrize("cell", ROOM)
def test_clearing_a_fallen_block_out_of_the_house(monkeypatch, cell):
    island = Island([ground(), *benchmark(), block("Block_fallen", cell[0] * C, 1.25, cell[1] * C)],
                    me=(0, BODY_CENTRE_Y, -10))
    island.solid_pieces = True  # the walls stop the body
    stood = []  # where the body stood as it took the block, and its room there, with the block still where it lay
    island.results["Pickup"] = lambda data: stood.append((island.me[0], island.me[2], room_to_spare(island, *island.me[::2]))) \
        or "PickupSuccess"
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island)
    snap = island.snap()
    assert not plan(pieces_of(snap), terrain_of(snap), ROOM, DOOR)["house"]  # a block in the room: no house
    # In by the doorway, to the cell just inside it; a block lying in that cell closes the way in (the walls either
    # side of the doorway meet it corner to corner), so that one is reached from the doorway.
    first = (0, 0) if cell != (0, 0) else DOOR
    walk = body.run("walk_to", {"x": first[0] * C, "z": first[1] * C})
    assert walk.ok and (inside(island) or first == DOOR), walk.summary
    # The block, from a spot where the whole body stands clear of the walls and the block.
    taken = body.run("pick_up", {"object": "Block_fallen"})
    assert taken.ok, taken.summary
    assert island.held == "Block_fallen" and stood
    assert stood[-1][2] >= BODY_RADIUS + STAND_MARGIN - 1e-6
    # Out of the doorway and set down clear of the house.
    out = body.run("put_down", {"x": 0, "z": -12.5})
    assert out.ok, out.summary
    assert island.held is None and island.ents["Block_fallen"]["position"][2] < -5
    # Back in: the room is clear, and it is a house again.
    back = body.run("walk_to", {"x": 0, "z": 0})
    assert back.ok and inside(island), back.summary
    snap = island.snap()
    found = plan(pieces_of(snap), terrain_of(snap), ROOM, DOOR)
    assert "the room is clear" in found["done"] and found["house"]


def test_no_reaching_through_a_wall(monkeypatch):
    # The doorway closed too: the block lies in a room walled all round, and the body stands outside. The only spots it
    # could take the block from are inside the room; none outside, through a wall three blocks high, however near.
    island = Island([ground(), *benchmark(), block("Block_door", 0, 1.25, -C), block("Block_door2", 0, 3.75, -C),
                     block("Block_door3", 0, 6.25, -C), block("Block_fallen", 0, 1.25, 0)], me=(0, BODY_CENTRE_Y, -10))
    island.solid_pieces = True
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island)
    snap = island.snap()
    fallen = snap.entities["Block_fallen"]
    for spot in (body._stand_point(snap, fallen.pos, PICKUP_RANGE, 2.85, {"Block_fallen"}, fallen),
                 body._close_stand_point(snap, fallen.pos, PICKUP_RANGE, {"Block_fallen"}, fallen)):
        assert spot is not None and any(abs(spot[0] - cx * C) <= C / 2 and abs(spot[1] - cz * C) <= C / 2
                                        for cx, cz in ROOM)
    taken = body.run("pick_up", {"object": "Block_fallen"})  # and the body cannot walk in to it
    assert not taken.ok and island.held is None


def test_reaching_over_a_block_on_the_floor(monkeypatch):
    # Over a block lying on the floor the arms reach as before: only a wall two blocks high is in the way.
    island = Island([ground(), block("Block_low", 0, 1.25, 2.5), block("Block_far", 0, 1.25, 5)],
                    me=(0, BODY_CENTRE_Y, -2))
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island)
    reaches = body._reach_fn(island.snap(), (0, 1.25, 5), {"Block_far"}, 0.0)
    assert reaches(0, -2)  # across Block_low
    island.ents["Block_low2"] = block("Block_low2", 0, 3.75, 2.5)  # now a wall two blocks high between
    assert not body._reach_fn(island.snap(), (0, 1.25, 5), {"Block_far"}, 0.0)(0, -2)


def platform():
    """The house's footprint and a strip of floor south of its doorway, and sea round them: no other floor near, as
    round run hp-full2's house, crowded with steps and stones."""
    return [ent("Ground", (1.25, -0.5, 1.25), (10, 1, 10), role="Ground"),
            ent("Strip", (0, -0.5, -8.125), (5, 1, 8.75), role="Ground")]


def footprint(e):
    (x, _, z), (sx, _, sz) = e["position"], e["size"]
    return {(ix, iz) for ix in range(math.ceil((x - sx / 2) / C - 1e-9), math.ceil((x + sx / 2) / C - 1e-9))
            for iz in range(math.ceil((z - sz / 2) / C - 1e-9), math.ceil((z + sz / 2) / C - 1e-9))}


RESERVED = set(ROOM) | {DOOR, (0, -2)}  # the room, the doorway and the way out


@pytest.mark.parametrize("held", ["stone", "log"])
@pytest.mark.parametrize("start", [(0, -1), (0, 0), (1, 1)])
def test_hands_full_sets_nothing_down_in_the_house(monkeypatch, held, start):
    # Run hp-full2: to free its hands the body set a stone, another stone and a log down in the house it was
    # building, wherever floor was clear beside it. Now the whole of what it sets down, a log three cells long too,
    # stays off the room, the doorway and the way out; with nowhere else in reach it keeps hold and says so.
    piece = (block("Block_held", 0, 1.25, 30) if held == "stone" else ent("Log_held", (0, 1.25, 30), (7.5, 2.5, 2.5)))
    island = Island([*platform(), *benchmark(), piece, ent("Hammer_1", (0, 0.2, -11), (0.6, 0.4, 2.0))],
                    me=(start[0] * C, BODY_CENTRE_Y, start[1] * C))
    island.held = piece["name"]
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island, reserved=lambda: RESERVED)
    r = body.run("pick_up", {"object": "Hammer_1"})
    if r.ok:
        assert island.held == "Hammer_1" and not footprint(island.ents[piece["name"]]) & RESERVED, r.summary
    else:
        assert island.held == piece["name"] and r.summary == (
            f"hands are full: holding {piece['name']}, and there is no clear spot nearby to set it down outside your "
            "house's room, doorway and way out")
    if start != (1, 1):  # from the doorway or the room, the strip beyond the way out is in reach
        assert r.ok


def test_the_cells_a_house_needs_clear(tmp_path):
    from godling.memory import NativeMemory
    mem = NativeMemory(tmp_path / "mem")
    assert mem.reserved_cells() == set()
    mem.set_house({"inside": [list(c) for c in ROOM], "door": list(DOOR)})
    assert mem.reserved_cells() == RESERVED
