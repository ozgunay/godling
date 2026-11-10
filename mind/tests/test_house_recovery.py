"""Clearing a fallen piece out of the benchmark house (ADR-019): walk in by the doorway, pick up a loose block lying in
a cell inside, carry it out and set it down, walk back in, and the room is clear again. For each of the four cells
inside. The house's room is two cells wide: the body (two units wide) fits in a cell with a quarter unit to spare on
each side, so the spot it picks the block up from must be found from the body's real size and the walls round it."""
import math

import pytest

from godling import skills as sk
from godling.house import plan, site_of
from godling.skills import BODY_HEIGHT, BODY_RADIUS, STAND_MARGIN, Skills
from godling.structures import pieces_of, terrain_of
from godling.world import BODY_CENTRE_Y, PICKUP_RANGE, turned_size
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
    # stays off the room, the doorway and the way out; with nowhere else in reach it carries it further off (ADR-027),
    # and with nowhere clear at all (here only the hammer's own corner of the strip is left) it keeps hold and says so.
    piece = (block("Block_held", 0, 1.25, 30) if held == "stone" else ent("Log_held", (0, 1.25, 30), (7.5, 2.5, 2.5)))
    island = Island([*platform(), *benchmark(), piece, ent("Hammer_1", (0, 0.2, -11), (0.6, 0.4, 2.0))],
                    me=(start[0] * C, BODY_CENTRE_Y, start[1] * C))
    island.held = piece["name"]
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island, reserved=lambda: site_of(ROOM, DOOR))
    r = body.run("pick_up", {"object": "Hammer_1"})
    if r.ok:
        assert island.held == "Hammer_1" and not footprint(island.ents[piece["name"]]) & RESERVED, r.summary
    else:
        assert island.held == piece["name"] and r.summary == (
            f"hands are full: holding {piece['name']}, and there is no clear floor near enough to set it down off your "
            "house's site")
    if start != (1, 1):  # from the doorway or the room, the strip beyond the way out is in reach
        assert r.ok


@pytest.mark.parametrize("name, size", [("Coconut_held", (0.9, 0.9, 0.9)), ("Axe_held", (0.4, 0.4, 1.0))])
def test_hands_full_keeps_unsnapped_objects_wholly_out_of_the_room(monkeypatch, name, size):
    island = Island([*platform(), *benchmark(), ent(name, (0, 1.25, 30), size),
                     ent("Hammer_1", (0, 0.2, -11), (0.6, 0.4, 2.0))],
                    me=(0, BODY_CENTRE_Y, -C))
    island.held = name
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island, reserved=lambda: site_of(ROOM, DOOR))
    r = body.run("pick_up", {"object": "Hammer_1"})
    assert r.ok and island.held == "Hammer_1", r.summary
    (x, _, z), (sx, _, sz) = island.ents[name]["position"], size
    for ix, iz in RESERVED:
        assert abs(x - ix * C) >= (sx + C) / 2 - 1e-9 or abs(z - iz * C) >= (sz + C) / 2 - 1e-9


def test_the_cells_a_house_needs_clear(tmp_path):
    from godling.memory import NativeMemory
    mem = NativeMemory(tmp_path / "mem")
    assert mem.reserved_cells() == {}
    mem.set_house({"inside": [list(c) for c in ROOM], "door": list(DOOR)})
    site = mem.reserved_cells()
    assert site.building and {c for c, kind in site.items() if kind in ("room", "doorway", "way out")} == RESERVED
    assert site[DOOR] == "doorway" and site[(0, -2)] == "way out" and all(site[c] == "room" for c in ROOM)
    # ADR-027: its walls, the ground a cell round them where the body stands to build them, and the way in to the
    # doorway, the three cells straight on beyond the way out.
    walls = {(x, z) for x in range(-1, 3) for z in range(-1, 3)} - set(ROOM) - {DOOR}
    assert {c for c, kind in site.items() if kind == "wall"} == walls
    assert {c for c, kind in site.items() if kind == "strip"} == (
        {(x, z) for x in range(-2, 4) for z in range(-2, 4)} - walls - set(ROOM) - {DOOR, (0, -2)})
    assert {c for c, kind in site.items() if kind == "approach"} == {(-1, -3), (0, -3), (1, -3)}
    # Once it stands, only its room, doorway and way out, for what the body sets aside (ADR-027 review).
    mem.state["house"]["built"] = 1.0
    site = mem.reserved_cells()
    assert not site.building and set(site) == RESERVED


def walls_only(caps=()):
    """The benchmark house's walls, three blocks high, and no roof yet but the stones `caps` on top of those walls."""
    return [p for p in benchmark() if p["name"].startswith("Block_w")] + [
        block(f"Block_cap{dx + 1}{dz + 1}", dx * C, 8.75, dz * C) for dx, dz in caps]


def roof_step(island):
    snap = island.snap()
    return plan(pieces_of(snap), terrain_of(snap), ROOM, DOOR)


def test_the_lintel_named_by_its_axis_and_supports(monkeypatch):
    # Run hp-full2: the doorway's flank walls were capped with stones first; the lintel laid the right way then found
    # no room on them, and laid the wrong way, across the doorway from outside into the room, it rested on nothing and
    # fell into the doorway. The next step now says to take those caps off, then lay the lintel along the wall, and
    # which two walls carry it.
    steps = [block("Block_step", 0, 1.25, -7.5), block("Block_stepW", -5, 1.25, -5), block("Block_stepE", 5, 1.25, -5)]
    island = Island([ground(), *walls_only(caps=[(-1, -1), (1, -1)]), *steps,
                     ent("Log_lintel", (8, 1.25, -12), (7.5, 2.5, 2.5))], me=(0, BODY_CENTRE_Y, -12))
    monkeypatch.setattr(sk, "time", FakeTime(island))

    def place(data):  # as the world does: nothing is set where it would overlap another piece
        size = turned_size((7.5, 2.5, 2.5) if island.held.startswith("Log_") else (C, C, C), data["rotation"]["yaw"])
        (x, y, z) = data["position"]
        taken = [e for n, e in island.ents.items() if n != island.held
                 and all(abs(v - e["position"][i]) < (size[i] + e["size"][i]) / 2 - 0.1 for i, v in enumerate((x, y, z)))]
        return "PlaceFailed:Occupied" if taken else "PlaceSuccess"
    island.results["Place"] = place

    def turned(data):  # and a piece set down a quarter round lies that way round
        for e in island.ents.values():
            if e["position"] == list(data["position"]) and e["name"].startswith("Log_"):
                e["size"] = list(turned_size((7.5, 2.5, 2.5), data["rotation"]["yaw"]))
    island.on_act["Place"] = turned
    found = roof_step(island)
    assert found["next"].startswith(
        "the roof, every piece at height 8.75 (set from a step one block high outside the walls, never in the doorway "
        "or the way out): first take Block_cap00 and Block_cap20 off the tops of (-2.5, -2.5) and (2.5, -2.5) (reach up "
        "from a step one block high beside them): the doorway's lintel rests there; then over the doorway at (0.0, -2.5), a log along x (turn 0) centred on it, "
        "resting on the walls at (-2.5, -2.5) and (2.5, -2.5)"), found["next"]
    assert {"Block_cap00", "Block_cap20"} <= set(found["in_the_way"])  # free to lift off, though they sit on its walls
    body = Skills(island)
    assert body.run("pick_up", {"object": "Log_lintel"}).ok
    # As in the run: the right way, there is no room on the capped walls; the wrong way it rests on nothing.
    assert not body.run("place_at", {"x": 0, "y": 8.75, "z": -C, "turn": 0}).ok
    wrong = body.run("place_at", {"x": 0, "y": 8.75, "z": -C, "turn": 90})
    assert "not resting on anything" in wrong.summary, wrong.summary
    island.ents["Log_lintel"]["position"] = [0, 1.25, -C]  # and falls, as Log_7 did, through the doorway
    assert roof_step(island)["next"].startswith("clear the room: (0.0, 0.0) (Log_lintel fills it)")
    # As the step says: the caps off and set down out of the way, then the lintel along x on its two walls.
    for cap, (sx, sz) in (("Block_cap00", (-5, -5)), ("Block_cap20", (5, -5))):
        # Down to the ground first, then up onto the step beside that wall: from one step straight to another as
        # high the body walks off the first and stays on the ground beside the second.
        assert body.run("walk_to", {"x": sx * 2, "z": -10}).ok
        up = body.run("walk_to", {"x": sx, "z": sz})
        assert up.ok and island.me[1] > 4, up.summary
        assert body.run("pick_up", {"object": cap}).ok, cap
        assert body.run("put_down", {"x": 10 if cap.endswith("20") else -10, "z": -12}).ok
    assert body.run("pick_up", {"object": "Log_lintel"}).ok
    right = body.run("place_at", {"x": 0, "y": 8.75, "z": -C, "turn": 0})
    assert right.ok and "Block_w003" in right.summary and "Block_w203" in right.summary, right.summary
    after = roof_step(island)
    assert f"the doorway at (0.0, -2.5) is open up to the roof" in after["done"] and "lintel" not in after["next"]


def test_a_room_log_named_by_its_bearing_wall_and_inward_cell(monkeypatch):
    # A log three cells long cannot reach across a room two cells wide: each one over the room is centred on a wall,
    # resting on its middle, and reaches one cell in. The step names the wall it rests on and the cell it reaches.
    island = Island([ground(), *walls_only(), ent("Log_S", (0, 8.75, -C), (7.5, 2.5, 2.5)),
                     block("Block_step", -7.5, 1.25, 0), ent("Log_room", (-12, 1.25, -8), (7.5, 2.5, 2.5))],
                    me=(-12, BODY_CENTRE_Y, -4))
    monkeypatch.setattr(sk, "time", FakeTime(island))
    found = roof_step(island)
    assert ("over (0.0, 0.0), a log along x (turn 0) centred on the wall at (-2.5, 0.0), resting on its middle and "
            "reaching in over (0.0, 0.0)") in found["next"], found["next"]
    body = Skills(island)
    assert body.run("pick_up", {"object": "Log_room"}).ok
    laid = body.run("place_at", {"x": -C, "y": 8.75, "z": 0, "turn": 0})
    assert laid.ok and "Block_w013" in laid.summary, laid.summary
    assert (0, 0) not in judge_bare(island)


def test_a_stone_capping_a_room_logs_bearing_wall_is_in_the_way(monkeypatch):
    # Room cell (0, 0) has one bearing wall, (-1, 0): its other side is the lintel's wall. A stone set on top of that
    # wall first left the log over (0, 0) no room there, and the stone was kept as the house's own, so the body would
    # not lift it: the house could never be finished. Like a cap on the lintel's walls, it is now in the way, named,
    # and once lifted off the log goes on.
    island = Island([ground(), *walls_only(caps=[(-1, 0)]), ent("Log_S", (0, 8.75, -C), (7.5, 2.5, 2.5)),
                     block("Block_step", -5, 1.25, -C), ent("Log_room", (-12, 1.25, -8), (7.5, 2.5, 2.5))],
                    me=(-12, BODY_CENTRE_Y, -4))
    monkeypatch.setattr(sk, "time", FakeTime(island))
    found = roof_step(island)
    assert "Block_cap01" in found["in_the_way"] and "Block_cap01" not in found["pieces"], found
    assert ("first take Block_cap01 off the top of (-2.5, 0.0) (reach up from a step one block high beside it): the "
            "log over (0.0, 0.0) rests there; then over (0.0, 0.0), a log along x (turn 0) centred on the wall at "
            "(-2.5, 0.0)") in found["next"], found["next"]
    body = Skills(island, kept_in=lambda p: "your house at (0.0, 0.0)" if p in found["pieces"] else None)
    assert body.run("walk_to", {"x": -5, "z": -C}).ok and island.me[1] > 4
    assert body.run("pick_up", {"object": "Block_cap01"}).ok
    assert body.run("put_down", {"x": -12, "z": 8}).ok
    assert body.run("pick_up", {"object": "Log_room"}).ok
    laid = body.run("place_at", {"x": -C, "y": 8.75, "z": 0, "turn": 0})
    assert laid.ok and "Block_w013" in laid.summary, laid.summary
    assert (0, 0) not in judge_bare(island)


def judge_bare(island):
    from godling.house import Grid, judge
    snap = island.snap()
    grid = Grid(pieces_of(snap), terrain_of(snap))
    return judge(grid, ROOM, 0.0)["bare"]
