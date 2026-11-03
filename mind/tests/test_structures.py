from godling.structures import measure, pieces_of, terrain_of
from helpers import block, ent, ground, snap


def cube(x, y, z, fastened=False, name=None):
    return {"name": name or f"B{x}_{y}_{z}", "pos": [x, y, z], "size": [2.5, 2.5, 2.5], "fastened": fastened}


GROUND = [{"name": "Ground", "pos": [0, -0.5, 0], "size": [200, 1, 200]}]


def layer(n):
    return 1.25 + 2.5 * n


def test_pieces_and_terrain_of_a_snapshot():
    s = snap([ground(), block("Block_1", 0, 1.25, 0, attrs={"Fastened": True}), block("Block_2", 0, 2.55 + 4, 0),
              ent("Hammer_1", (5, 0.5, 0), (1, 1, 3))])
    assert pieces_of(s) == [{"name": "Block_1", "pos": [0, 1.25, 0], "size": [2.5, 2.5, 2.5], "fastened": True}]
    assert terrain_of(s) == [{"name": "Ground", "pos": [0, -0.5, 0], "size": [400, 1, 400]}]


def test_nothing_built():
    m = measure([], GROUND)
    assert m["pieces"] == 0 and m["walls"] == 0 and m["tallest"] == 0 and m["highest"] == 0


def test_a_tower_on_bare_sea():
    pieces = [cube(0, layer(n), 0) for n in range(3)]
    m = measure(pieces, [])  # no terrain: the base is 0
    assert m["tallest"] == 7.5 and m["largest_structure"] == 3 and m["pieces_built_in"] == 3


def test_walled_room_with_a_roof_and_a_door():
    pieces = []
    for ix in range(5):  # a 5 x 5 ring of two-high walls, with a doorway at (2, 0)
        for iz in range(5):
            if ix in (0, 4) or iz in (0, 4):
                if (ix, iz) == (2, 0):
                    continue
                for n in range(2):
                    pieces.append(cube(ix * 2.5, layer(n), iz * 2.5, fastened=n == 1))
    for ix in range(1, 4):  # a roof over the room, three layers up
        for iz in range(1, 4):
            pieces.append(cube(ix * 2.5, layer(2), iz * 2.5))
    m = measure(pieces, GROUND)
    assert m["walls"] == 3 and m["wall_length"] == 37.5  # the doorway breaks the fourth side
    assert m["enclosures"] == 1 and m["enclosed_area"] == 9 * 6.25
    assert m["roofed"] == 1
    assert m["floors"] == 2 and m["floor_area"] == 24 * 6.25  # the roof, and the walls' tops
    assert m["fastened"] == 15
    assert m["highest"] == 7.5 and m["tallest"] == 5.0


def test_span_post_and_one_big_rock():
    pieces = [cube(0, layer(0), 0), cube(0, layer(1), 0), cube(10, layer(0), 0), cube(10, layer(1), 0),
              {"name": "Beam", "pos": [5, 5.5, 0], "size": [12.5, 1, 1], "fastened": False},
              {"name": "Post", "pos": [20, 3.75, 0], "size": [1, 7.5, 1], "fastened": False},
              {"name": "Boulder", "pos": [40, 3, 0], "size": [12, 6, 12], "fastened": False},
              {"name": "Short", "pos": [60, 0.5, 0], "size": [2, 1, 1], "fastened": False},
              {"name": "Tall", "pos": [70, 2.35, 0], "size": [4.6, 4.65, 1], "fastened": False}]
    m = measure(pieces, GROUND)
    assert m["spans"] == 1 and m["longest_gap"] == 5.0
    assert m["posts"] == 1
    assert m["floors"] == 0  # the boulder's top is one piece: not a floor
    assert m["walls"] == 0  # the boulder alone is no wall, and the piers are too short


def test_built_on_a_mesa_counts_from_its_top():
    mesa = {"name": "Mesa", "pos": [0, 5, 0], "size": [20, 10, 20]}
    pieces = [cube(0, 10 + layer(n), 0) for n in range(2)]
    m = measure(pieces, GROUND + [mesa])
    assert m["tallest"] == 5.0
