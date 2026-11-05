"""The house check (house.py, ADR-019's first-house benchmark): the layouts the world's copy (main.lua houseAt) is held
to as well (world/tests/test_life.luau)."""
from godling.house import Grid, assess, houses, judge, layout, plan

C = 2.5
GROUND = [{"name": "Ground", "pos": [0, -0.5, 0], "size": [400, 1, 400]}]
ROOM = [(0, 0), (0, 1), (1, 0), (1, 1)]
DOOR = (0, -1)


def block(name, ix, iz, layer):
    """A block in cell (ix, iz), `layer` 1 on the ground."""
    return {"name": name, "pos": [ix * C, (layer - 0.5) * C, iz * C], "size": [C, C, C]}


def log(name, ix, iz, layer, along="x"):
    """A log lying flat, three cells long, centred on cell (ix, iz)."""
    return {"name": name, "pos": [ix * C, (layer - 0.5) * C, iz * C], "size": [3 * C, C, C] if along == "x" else [C, C, 3 * C]}


def column(prefix, ix, iz, high):
    return [block(f"{prefix}{k}", ix, iz, k) for k in range(1, high + 1)]


def house(walls=3, skip=(), short=(), roofless=False, roof_skip=()):
    """The benchmark house: a room two by two at cells (0..1, 0..1), walls three blocks high all round it, corners too,
    the doorway south at (0, -1), and the roof in layer 4 over all of it: across the north and south walls a log
    (centred x 0, so it lies over the doorway as its lintel) and a block, and over the room logs centred on the west and
    east walls, each resting on its middle and reaching one cell in."""
    pieces = []
    for ix in range(-1, 3):
        for iz in range(-1, 3):
            if (ix, iz) in ROOM or (ix, iz) == DOOR or (ix, iz) in skip:
                continue
            pieces += column(f"W{ix}{iz}_", ix, iz, walls - 1 if (ix, iz) in short else walls)
    if not roofless:
        roof = [log("Log_S", 0, -1, walls + 1), block("Block_SE", 2, -1, walls + 1), log("Log_N", 0, 2, walls + 1),
                block("Block_NE", 2, 2, walls + 1), log("Log_W0", -1, 0, walls + 1), log("Log_E0", 2, 0, walls + 1),
                log("Log_W1", -1, 1, walls + 1), log("Log_E1", 2, 1, walls + 1)]
        pieces += [p for p in roof if p["name"] not in roof_skip]
    return pieces


# Run hp-proj8's shelter as it stood at the end (mind/structures.jsonl): one cell inside, at (-90, -32.5), between a
# stack of three blocks north, an upright log south and a wall two blocks high west, the doorway east, and a log over
# it, north to south. It passed the first check, and is no house.
PROJ8 = [{"name": n, "pos": list(pos), "size": list(size)} for n, pos, size in (
    ("Block_5", (-95.0, 1.25, -32.5), (2.5, 2.5, 2.5)), ("Block_2", (-92.5, 1.25, -35.0), (2.5, 2.5, 2.5)),
    ("Block_12", (-92.5, 1.25, -32.5), (2.5, 2.5, 2.5)), ("Block_10", (-92.5, 1.25, -30.0), (2.5, 2.5, 2.5)),
    ("Block_6", (-90.0, 1.25, -30.0), (2.5, 2.5, 2.5)), ("Block_8", (-87.5, 1.25, -35.0), (2.5, 2.5, 2.5)),
    ("Block_1", (-95.0, 3.75, -32.5), (2.5, 2.5, 2.5)), ("Block_3", (-92.5, 3.75, -35.0), (2.5, 2.5, 2.5)),
    ("Block_4", (-92.5, 3.75, -32.5), (2.5, 2.5, 2.5)), ("Log_7", (-90.0, 3.75, -35.0), (2.5, 7.5, 2.5)),
    ("Block_11", (-90.0, 3.75, -30.0), (2.5, 2.5, 2.5)), ("Block_9", (-90.0, 6.25, -30.0), (2.5, 2.5, 2.5)),
    ("Log_17", (-90.0, 8.75, -32.5), (2.5, 2.5, 7.5)))]


def names(pieces):
    return {p["name"] for p in pieces}


def test_the_benchmark_house_is_a_house():
    pieces = house()
    found = houses(pieces, GROUND)
    assert len(found) == 1 and found[0]["cells"] == ROOM and found[0]["doors"] == [DOOR] and found[0]["top"] == 7.5
    assert assess(pieces, GROUND, names(pieces)) == "a house: 4 cells inside, the doorway at (0.0, -2.5)"


def test_proj8s_shelter_is_no_house():
    assert houses(PROJ8, GROUND) == []
    verdict = assess(PROJ8, GROUND, names(PROJ8))
    assert verdict.startswith("the room inside is 1 cell, at (-90.0, -32.5): a house's room holds at least two by two "
                              "cells")
    assert ("the walls do not reach the roof (7.5 up) at (-92.5, -35.0), (-92.5, -32.5), (-92.5, -30.0), (-87.5, "
            "-35.0), (-87.5, -30.0), corners too") in verdict


def test_what_a_house_is_short_of():
    def short_of(pieces):
        assert houses(pieces, GROUND) == []
        return assess(pieces, GROUND, names(pieces))
    assert short_of(house(skip=[(2, 2)], roof_skip=["Block_NE"])) == (
        "the walls do not reach the roof (7.5 up) at (5.0, 5.0), corners too")
    assert short_of(house(short=[(-1, 0)])) == (
        "the walls do not reach the roof (7.5 up) at (-2.5, 0.0), corners too")  # a gap under the roof
    assert short_of(house(roof_skip=["Block_SE"])) == "the roof does not cover the walls and doorway at (5.0, -2.5)"
    assert short_of(house(skip=[(1, 2)])) == (
        "the walls are open at (2.5, 5.0) as well as the doorway at (0.0, -2.5): a house has one doorway")
    assert short_of(house() + [block("Block_x", 0, -2, 1)]) == (
        "the opening at (0.0, -2.5) is no doorway: a doorway is open up to the roof and leads onto open ground")
    assert short_of(house() + [block("Block_x", 1, 1, 1)]) == "the room is not clear at (2.5, 2.5)"
    assert short_of(house(roofless=True)).startswith(
        "there is no roof over (0.0, 0.0), (0.0, 2.5), (2.5, 0.0), (2.5, 2.5) inside; the roof does not cover the walls "
        "and doorway at ")
    # Walls two blocks high with the roof on them: its underside 5.0 up, exactly the body's height.
    assert short_of(house(walls=2)) == ("the roof over (0.0, 0.0), (0.0, 2.5), (2.5, 0.0), (2.5, 2.5) hangs too low to "
                                        "stand under: it needs more than 5 of room")


def test_a_wall_encloses_nothing():
    wall = column("A", 0, 0, 2) + column("B", 1, 0, 2) + column("C", 2, 0, 2)
    assert houses(wall, GROUND) == []
    assert assess(wall, GROUND, names(wall)) == "it encloses no space yet"
    assert assess(wall, GROUND, {"Nothing"}) == ""


def test_a_chosen_house_says_what_it_needs_next():
    room, door = layout([[0, 0], [2.5, 0], [0, 2.5], [2.5, 2.5]], [0, -2.5])
    assert (room, door) == (ROOM, DOOR)
    empty = plan([], GROUND, room, door)
    assert not empty["house"] and empty["pieces"] == []
    assert empty["next"].startswith("walls three blocks high all round the room, corners too, but for the doorway at "
                                    "(0.0, -2.5): (-2.5, -2.5) stands 0.0, (-2.5, 0.0) stands 0.0, ")
    # Walls up: the roof next, where its pieces go and how high, over the room, the walls and the doorway.
    walls = plan(house(roofless=True), GROUND, room, door)
    assert walls["done"] == ["the walls stand three blocks high all round", "the room is clear",
                             "the doorway at (0.0, -2.5) is open up to the roof"]
    # In the order it is laid: the lintel first, on the walls either side of the doorway; then a log over each cell
    # inside, centred on a wall beside it and reaching in; then blocks on the walls left over.
    assert walls["next"] == (
        "the roof, every piece at height 8.75 (set from a step one block high outside the walls, never in the doorway or "
        "the way out): over the doorway at (0.0, -2.5), a log along x (turn 0) centred on it, resting on the walls at "
        "(-2.5, -2.5) and (2.5, -2.5); over (0.0, 0.0), a log along x (turn 0) centred on the wall at (-2.5, 0.0), "
        "resting on its middle and reaching in over (0.0, 0.0); over (0.0, 2.5), a log along x (turn 0) centred on the "
        "wall at (-2.5, 2.5), resting on its middle and reaching in over (0.0, 2.5); over (2.5, 0.0), a log along x "
        "(turn 0) centred on the wall at (5.0, 0.0), resting on its middle and reaching in over (2.5, 0.0); over (2.5, "
        "2.5), a log along z (turn 90) centred on the wall at (2.5, 5.0), resting on its middle and reaching in over "
        "(2.5, 2.5); a block on top of the walls at (-2.5, 5.0), (0.0, 5.0), (5.0, -2.5), (5.0, 2.5), (5.0, 5.0)")
    assert len(walls["pieces"]) == 33 and walls["score"] > empty["score"]
    # What lies in the room, the doorway or the way out is in the way, not its own.
    blocked = plan(house() + [block("Block_x", 0, -1, 1)], GROUND, room, door)
    assert blocked["next"] == "clear the doorway at (0.0, -2.5) up to the roof: Block_x in it"
    assert blocked["in_the_way"] == ["Block_x"] and "Block_x" not in blocked["pieces"]
    outside = plan(house() + [block("Block_y", 0, -2, 1)], GROUND, room, door)
    assert outside["next"] == "clear the way out of the doorway, at (0.0, -5.0): Block_y in it"
    filled = plan(house() + [block("Block_z", 1, 1, 1)], GROUND, room, door)
    assert filled["next"] == "clear the room: (2.5, 2.5) (Block_z fills it)"
    done = plan(house(), GROUND, room, door)
    assert done["house"] and done["score"] > walls["score"] and {"Log_S", "Log_W0", "Block_NE"} <= set(done["pieces"])
    assert done["next"] == "none: it is a house. Walk in by the doorway at (0.0, -2.5) and stand inside"


def test_a_house_layout_must_hold_together():
    assert layout([[0, 0]], [0, -2.5]).startswith("the room must hold at least two by two cells, a square 5 across")
    assert layout([[0, 0], [2.5, 0]], [0, -2.5]).startswith("the room must hold at least two by two cells")
    assert layout([[0, 0], [5, 0], [0, 2.5], [5, 2.5]], [0, -2.5]).startswith(
        "the cells inside must touch one another side by side")
    square = [[0, 0], [2.5, 0], [0, 2.5], [2.5, 2.5]]
    assert layout(square, [-2.5, -2.5]) == ("the doorway at (-2.5, -2.5) must be a cell beside the room on one of its "
                                            "sides, not in it, at a corner or away")
    assert layout(square, [0, 0]).startswith("the doorway at (0.0, 0.0) must be a cell beside the room")
    assert layout([], [0, 0]) == "a house needs cells inside"
    assert layout([["a", 0]], [0, 0]) == layout(square, None) == (
        "the cells inside and the doorway must each be a point [x, z]")
    assert layout([{"x": 0, "z": 0}, [2.4, 0.3], [0, 2.5], "[2.5, 2.5]"], {"x": 0, "z": -2.5}) == (ROOM, DOOR)
    assert layout("[[0, 0], [2.5, 0], [0, 2.5], [2.5, 2.5]]", "[0, -2.5]") == (ROOM, DOOR)
    assert layout("the cells inside", [0, 0]) == layout(square, {"x": 0}) == (
        "the cells inside and the doorway must each be a point [x, z]")


def test_a_house_requires_ground_and_reports_uneven_ground_without_crashing():
    pieces = house()
    assert houses(pieces, []) == []
    missing = plan(pieces, [], ROOM, DOOR)
    assert not missing["house"] and "choose a site with a real floor" in missing["next"]
    uneven = GROUND + [{"name": "Raised", "pos": [2.5, 0.5, 2.5], "size": [2.5, 1, 2.5]}]
    verdict = judge(Grid(pieces, uneven), ROOM, 0)
    assert verdict["unlevel"] == [(1, 1)] and verdict["hanging"] == [] and not verdict["house"]
    result = plan(pieces, uneven, ROOM, DOOR)
    assert not result["house"] and result["next"].startswith("choose level ground")


def test_equal_height_ground_seams_are_a_real_floor():
    terrain = [{"name": "West", "pos": [-98.75, -0.5, 0], "size": [200, 1, 400]},
               {"name": "East", "pos": [101.25, -0.5, 0], "size": [200, 1, 400]}]
    assert len(houses(house(), terrain)) == 1


def test_sparse_unsettled_and_narrow_material_cannot_complete_a_house():
    for change in ("sparse", "unanchored", "unsettled", "tilted", "narrow"):
        pieces = house()
        for p in pieces:
            if p["name"].startswith("W"):
                if change == "sparse":
                    p["size"][1] = 0.5
                elif change == "unanchored":
                    p["anchored"] = False
                elif change == "unsettled":
                    p["settled"] = False
                elif change == "tilted":
                    p["aligned"] = False
                else:
                    p["size"][0] = 0.5
        assert houses(pieces, GROUND) == [], change
        assert not plan(pieces, GROUND, ROOM, DOOR)["house"], change
    pieces = house()
    next(p for p in pieces if p["name"] == "Log_W0")["anchored"] = False
    assert houses(pieces, GROUND) == []


def test_fractional_roof_heights_use_continuous_wall_fill():
    pieces = house()
    for p in pieces:
        if p["name"].startswith("W"):
            p["pos"][1] *= 0.84
            p["size"][1] *= 0.84
        else:
            p["pos"][1] -= 1.2
    assert len(houses(pieces, GROUND)) == 1
    assert plan(pieces, GROUND, ROOM, DOOR)["house"]


def test_guided_layouts_require_supported_roof_and_a_straight_doorway():
    large = [(x, z) for x in range(3) for z in range(3)]
    rejected = layout([[x * C, z * C] for x, z in large], [0, -C])
    assert isinstance(rejected, str) and "no wall support" in rejected
    persisted = plan([], GROUND, large, DOOR)
    assert not persisted["house"] and "revise the room" in persisted["next"]
    for length in range(2, 9):
        rectangle = [[x * C, z * C] for x in range(2) for z in range(length)]
        assert not isinstance(layout(rectangle, [0, -C]), str)
    concave = [[0, 0], [0, C], [C, 0], [C, C], [2 * C, 0], [2 * C, C], [2 * C, 2 * C], [C, 2 * C]]
    invalid = layout(concave, [0, 2 * C])
    assert isinstance(invalid, str) and "exactly one room cell" in invalid
    overlapping = [[0, 0], [0, C], [C, 0], [C, C], [C, 2 * C], [C, 3 * C]]
    rejected = layout(overlapping, [-C, 0])
    assert isinstance(rejected, str) and "roof pieces overlap" in rejected
    persisted = plan([], GROUND, [(round(x / C), round(z / C)) for x, z in overlapping], (-1, 0))
    assert "revise the room or doorway" in persisted["next"]


def test_a_complete_larger_house_uses_the_same_verdict_even_without_guided_roof_supports():
    room = [(x, z) for x in range(3) for z in range(3)]
    pieces = []
    for x in range(-1, 4):
        for z in range(-1, 4):
            if (x, z) not in room and (x, z) != DOOR:
                pieces.extend(column(f"W{x}{z}_", x, z, 3))
            pieces.append(block(f"Roof{x}_{z}", x, z, 4))
    assert len(houses(pieces, GROUND)) == 1
    assert plan(pieces, GROUND, room, DOOR)["house"]
