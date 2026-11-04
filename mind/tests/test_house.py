"""The house check (house.py, ADR-019): the layouts the world's copy (main.lua houseAt) is held to as well
(world/tests/test_life.luau)."""
from godling.house import assess, houses

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
