"""The house check (house.py, ADR-019): the layouts the world's copy (main.lua houseAt) is held to as well
(world/tests/test_life.luau)."""
from godling.house import assess, houses, layout, plan

C = 2.5
GROUND = [{"name": "Ground", "pos": [0, -0.5, 0], "size": [400, 1, 400]}]


def block(name, ix, iz, layer):
    """A block in cell (ix, iz), `layer` 1 on the ground."""
    return {"name": name, "pos": [ix * C, (layer - 0.5) * C, iz * C], "size": [C, C, C]}


def log(name, ix, iz, layer, along="x"):
    """A log lying flat, three cells long, centred on cell (ix, iz)."""
    return {"name": name, "pos": [ix * C, (layer - 0.5) * C, iz * C], "size": [3 * C, C, C] if along == "x" else [C, C, 3 * C]}


def column(prefix, ix, iz, high):
    return [block(f"{prefix}{k}", ix, iz, k) for k in range(1, high + 1)]


def hut(roof=True, north=2, door_north=False):
    """A one-cell hut round cell (0, 0): posts three high west and east, a wall north, the doorway south, a log roof."""
    pieces = column("W", -1, 0, 3) + column("E", 1, 0, 3) + ([] if door_north else column("N", 0, 1, north))
    if roof:
        pieces.append(log("Roof", 0, 0, 4))
    return pieces


def names(pieces):
    return {p["name"] for p in pieces}


def test_a_hut_is_a_house():
    pieces = hut()
    found = houses(pieces, GROUND)
    assert len(found) == 1 and found[0]["cells"] == [(0, 0)] and found[0]["doors"] == [(0, -1)]
    assert assess(pieces, GROUND, names(pieces)) == "a house: 1 cell inside, the doorway at (0.0, -2.5)"


def test_without_a_roof():
    pieces = hut(roof=False)
    assert houses(pieces, GROUND) == []
    assert assess(pieces, GROUND, names(pieces)) == (
        "the doorway at (0.0, -2.5) is clear, the walls stand two blocks high, but there is no roof over the cell "
        "inside, at (0.0, 0.0)")


def test_a_roof_over_one_of_two_cells():
    # Cells (0, 0) and (0, 1) inside: walls round both, the doorway south, the roof over (0, 0) only.
    pieces = (column("W", -1, 0, 3) + column("E", 1, 0, 3) + column("V", -1, 1, 2) + column("U", 1, 1, 2)
              + column("N", 0, 2, 2) + [log("Roof", 0, 0, 4)])
    assert houses(pieces, GROUND) == []
    assert assess(pieces, GROUND, names(pieces)) == (
        "the doorway at (0.0, -2.5) is clear, the walls stand two blocks high, but the roof covers only 1 of the 2 "
        "cells inside (none over (0.0, 2.5))")


def test_a_low_wall_and_two_gaps():
    low = hut(north=1)
    assert houses(low, GROUND) == []
    assert assess(low, GROUND, names(low)) == (
        "the doorway at (0.0, -2.5) is clear, the roof covers the cell inside, but the wall is lower than two blocks "
        "at (0.0, 2.5)")
    open_ = hut(door_north=True)
    assert houses(open_, GROUND) == []
    assert assess(open_, GROUND, names(open_)) == (
        "the roof covers the cell inside, but the walls have 2 gaps, at (0.0, -2.5), (0.0, 2.5): a house has one "
        "doorway")


def test_a_room_filled_or_roofed_too_low():
    # hut4-roof: a beam across two posts, and a block left in the cell under it.
    filled = hut() + [block("Block_7", 0, 0, 1)]
    assert houses(filled, GROUND) == []
    assert assess(filled, GROUND, names(filled)) == (
        "there is no room to stand under its roof: (0.0, 0.0) under the roof is filled by Block_7")
    # A roof on walls two blocks high: its underside 5.0 up, exactly the body's height.
    low = column("W", -1, 0, 2) + column("E", 1, 0, 2) + column("N", 0, 1, 2) + [log("Roof", 0, 0, 3)]
    assert houses(low, GROUND) == []
    assert assess(low, GROUND, names(low)) == (
        "there is no room to stand under its roof: (0.0, 0.0) has Roof only 5.0 up, too low to stand under")


def test_a_wall_encloses_nothing():
    wall = column("A", 0, 0, 2) + column("B", 1, 0, 2) + column("C", 2, 0, 2)
    assert houses(wall, GROUND) == []
    assert assess(wall, GROUND, names(wall)) == "it encloses no space yet"
    assert assess(wall, GROUND, {"Nothing"}) == ""


def test_a_chosen_house_says_what_it_needs_next():
    room, door = layout([[0, 0]], [0, -2.5])
    assert (room, door) == ([(0, 0)], (0, -1))
    # Nothing built: walls first; nothing of it is its own yet.
    empty = plan([], GROUND, room, door)
    assert not empty["house"] and empty["pieces"] == [] and empty["score"] == 2
    assert empty["next"] == "walls two blocks high at (-2.5, 0.0), (0.0, 2.5), (2.5, 0.0)"
    # Walls up: the roof next, and its walls are its own.
    bare = plan(hut(roof=False), GROUND, room, door)
    assert bare["next"].startswith("a roof over (0.0, 0.0), with more than 5 of room under it")
    assert bare["done"] == ["the walls stand two blocks high", "the room is clear", "the doorway at (0.0, -2.5) is clear"]
    assert bare["pieces"] == ["E1", "E2", "E3", "N1", "N2", "W1", "W2", "W3"] and bare["score"] == 5
    # A block in the doorway or the room is in the way, not its own.
    blocked = plan(hut() + [block("Block_8", 0, -1, 1)], GROUND, room, door)
    assert blocked["next"] == "clear the doorway at (0.0, -2.5): Block_8 in it" and "Block_8" not in blocked["pieces"]
    assert blocked["in_the_way"] == ["Block_8"]
    filled = plan(hut() + [block("Block_7", 0, 0, 1)], GROUND, room, door)
    assert filled["next"] == "clear the room: (0.0, 0.0) (Block_7 fills it)" and "Block_7" not in filled["pieces"]
    done = plan(hut(), GROUND, room, door)
    assert done["house"] and done["score"] == 6 and "Roof" in done["pieces"]
    assert done["next"] == "none: it is a house. Walk in by the doorway at (0.0, -2.5) and stand inside"


def test_a_house_layout_must_hold_together():
    assert layout([[0, 0], [5, 0]], [0, -2.5]) == "the cells inside must touch one another side by side: (5.0, 0.0)"
    assert layout([[0, 0]], [0, -5]) == ("the doorway at (0.0, -5.0) must be a cell beside the room, not in it or "
                                         "away from it")
    assert layout([[0, 0]], [0, 0]).startswith("the doorway at (0.0, 0.0) must be a cell beside the room")
    assert layout([], [0, 0]) == "a house needs at least one cell inside"
    assert layout([["a", 0]], [0, 0]) == layout([[0, 0]], None) == (
        "the cells inside and the doorway must each be a point [x, z]")
    assert layout([[0, 0], [2.4, 0.3]], [-2.5, 0]) == ([(0, 0), (1, 0)], (-1, 0))  # points snap to their cells
    assert layout([{"x": 0, "z": 0}], {"x": -2.5, "z": 0}) == ([(0, 0)], (-1, 0))
    assert layout("[[0, 0], [2.5, 0]]", "[-2.5, 0]") == ([(0, 0), (1, 0)], (-1, 0))
    assert layout("the cells inside", [0, 0]) == layout({"x": 0}, [0, 0]) == (
        "the cells inside and the doorway must each be a point [x, z]")
