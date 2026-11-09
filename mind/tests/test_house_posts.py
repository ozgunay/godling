"""Houses wider than two cells (ADR-033): posts inside hold up the roof, as RimWorld's columns do. A log three cells long
reaches one cell from what holds it up, so a room two cells wide is roofed from its walls and a wider one needs posts:
upright logs inside, standing from the floor to the roof, with the room on all four sides. The world's copy of the check
(main.lua houseAt) is held to the same post-and-beam house in world/tests/test_life.luau."""
import math

import pytest

from godling import skills as sk
from godling.house import CELL, ROOF_AT, Grid, assess, houses, judge, layout, plan, ring, roof_layout, sides
from godling.skills import Skills
from godling.world import BODY_CENTRE_Y, PLACE_RANGE
from helpers import ent, ground
from island import FakeTime, Island

C = CELL
GROUND = [{"name": "Ground", "pos": [0, -0.5, 0], "size": [400, 1, 400]}]
INSIDE = [(x, z) for x in range(3) for z in range(3)]  # three by three
POST = (1, 1)  # in the middle, the room on all four sides of it
ROOM = [c for c in INSIDE if c != POST]
DOOR = (1, -1)  # south, in the middle of the side


def pt(c):
    return [c[0] * C, c[1] * C]


def block(name, ix, iz, layer):
    return {"name": name, "pos": [ix * C, (layer - 0.5) * C, iz * C], "size": [C, C, C]}


def log(name, ix, iz, layer, along="x"):
    """A log lying flat, three cells long, centred on cell (ix, iz)."""
    return {"name": name, "pos": [ix * C, (layer - 0.5) * C, iz * C],
            "size": [3 * C, C, C] if along == "x" else [C, C, 3 * C]}


def upright(name, ix, iz):
    """A log stood on end in cell (ix, iz): a post three blocks high."""
    return {"name": name, "pos": [ix * C, 1.5 * C, iz * C], "size": [C, 3 * C, C]}


def walls(inside, door, high=3):
    return [block(f"Block_w{c[0]}_{c[1]}_{k}", c[0], c[1], k) for c in ring(inside) if c != door for k in range(1, high + 1)]


def hut(post="log", roof_skip=()):
    """The post-and-beam house: a room three by three at cells (0..2, 0..2), walls three blocks high all round, the
    doorway south at (1, -1), a post at (1, 1), and the roof in layer 4: the lintel over the doorway; a log along z
    centred on the post, resting on its middle and reaching over (1, 0) and (1, 2); logs centred on the west and east
    walls reaching one cell in; and blocks on the walls left over."""
    pieces = walls(INSIDE, DOOR)
    if post == "log":
        pieces.append(upright("Log_post", *POST))
    elif post == "short":  # two blocks: a gap of a block under the roof
        pieces += [block("Block_p1", *POST, 1), block("Block_p2", *POST, 2)]
    roof = [log("Log_lintel", 1, -1, 4), log("Log_over_post", 1, 1, 4, "z"),
            log("Log_W0", -1, 0, 4), log("Log_W1", -1, 1, 4), log("Log_W2", -1, 2, 4),
            log("Log_E0", 3, 0, 4), log("Log_E1", 3, 1, 4), log("Log_N2", 2, 3, 4, "z")]
    roof += [block(f"Block_cap{c[0]}_{c[1]}", *c, 4) for c in ((-1, -1), (3, -1), (-1, 3), (0, 3), (1, 3), (3, 2), (3, 3))]
    return pieces + [p for p in roof if p["name"] not in roof_skip]


def names(pieces):
    return {p["name"] for p in pieces}


# ---- the check: a post inside is part of the house ----------------------------------------------------------------

def test_a_room_three_wide_with_a_post_is_a_house():
    pieces = hut()
    found = houses(pieces, GROUND)
    assert len(found) == 1, assess(pieces, GROUND, names(pieces))
    assert found[0]["cells"] == ROOM and found[0]["posts"] == [POST] and found[0]["doors"] == [DOOR]
    assert assess(pieces, GROUND, names(pieces)) == "a house: 9 cells inside, 1 of them a post, the doorway at (2.5, -2.5)"
    assert judge(Grid(pieces, GROUND), ROOM, 0.0)["house"]


def test_a_post_reaches_the_roof_and_carries_it():
    short = hut(post="short")
    assert houses(short, GROUND) == []
    assert assess(short, GROUND, names(short)) == "the post at (2.5, 2.5) does not reach the roof (7.5 up)"
    bare = hut(roof_skip=["Log_over_post"])
    assert houses(bare, GROUND) == []
    verdict = judge(Grid(bare, GROUND), ROOM, 0.0)
    assert not verdict["house"] and verdict["bare"] == [(1, 0), (1, 2)] and verdict["uncovered"] == [POST]


def test_a_wall_jutting_in_is_no_post():
    # A column against the wall is part of the wall, not a post: the room round it is a U, with no two by two in it.
    inside = [(x, z) for x in range(3) for z in range(2)]
    stub = (1, 1)  # against the north wall
    pieces = walls(inside, DOOR) + [upright("Log_stub", *stub)]
    verdict = judge(Grid(pieces, GROUND), [c for c in inside if c != stub], 0.0)
    assert verdict["posts"] == [] and not verdict["square"]


# ---- the layout the mind chooses ------------------------------------------------------------------------------------

def test_a_room_wider_than_two_cells_needs_a_post():
    no_post = layout([pt(c) for c in INSIDE], pt(DOOR))
    assert no_post == (
        "nothing holds up the roof over (2.5, 0.0), (2.5, 2.5): a log three blocks long reaches one cell from the wall or "
        "post it rests on, so every cell inside must lie beside a wall or a post (not the doorway or the walls either side "
        "of it); stand posts inside, or make the room at most two cells wide")
    assert layout([pt(c) for c in INSIDE], pt(DOOR), [pt(POST)]) == (INSIDE, DOOR, [POST])
    assert layout([pt(c) for c in INSIDE], pt(DOOR), "[[2.5, 2.5]]") == (INSIDE, DOOR, [POST])
    for door in sides(INSIDE):  # any doorway on a side
        assert not isinstance(layout([pt(c) for c in INSIDE], pt(door), [pt(POST)]), str), door


def test_where_a_post_can_stand():
    square = [pt(c) for c in INSIDE]
    assert layout(square, pt(DOOR), [[10, 10]]) == "the post at (10.0, 10.0) must be one of the cells inside"
    assert layout(square, pt(DOOR), [[2.5, 0]]) == (
        "the post at (2.5, 0.0) must have the room on all four sides of it: a post stands alone inside, clear of the "
        "walls and of other posts")
    wide = [pt((x, z)) for x in range(4) for z in range(4)]
    assert layout(wide, [2.5, -2.5], [[2.5, 2.5], [5, 2.5]]).startswith(
        "the post at (2.5, 2.5) must have the room on all four sides of it")
    plus = [pt(c) for c in ((1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (0, 0))]
    cut = layout(plus, [2.5, -2.5], [[2.5, 2.5]])
    assert isinstance(cut, str) and "posts must leave the room in one piece" in cut, cut
    assert layout(square, pt(DOOR), [["a", 0]]) == "the posts must each be a point [x, z] inside the house"
    assert layout(square, pt(DOOR), "two posts") == "the posts must each be a point [x, z] inside the house"
    assert layout(square, pt(DOOR), None) == layout(square, pt(DOOR))  # left out: no posts


def test_the_two_wide_rooms_need_no_posts():
    for length in range(2, 11):
        inside = [(x, z) for x in range(2) for z in range(length)]
        assert layout([pt(c) for c in inside], [0, -C]) == (inside, (0, -1), []), length


SHAPES = [  # (width, depth, posts, doorway): rooms whose roof rests on their walls and posts
    (2, 2, [], (0, -1)), (2, 6, [], (1, 6)), (3, 3, [(1, 1)], (1, -1)), (3, 3, [(1, 1)], (-1, 0)),
    (3, 4, [(1, 1)], (1, -1)), (3, 5, [(1, 1), (1, 3)], (-1, 0)), (3, 8, [(1, 1), (1, 3), (1, 5)], (1, -1)),
    (4, 4, [(1, 1), (2, 2)], (0, -1)), (4, 6, [(1, 1), (1, 3), (2, 2), (2, 4)], (0, -1)),
    (5, 5, [(1, 1), (1, 3), (2, 2), (3, 1), (3, 3)], (0, -1)), (4, 8, [(1, 1), (1, 4), (1, 6), (2, 2), (2, 5)], (0, -1)),
]


def built(inside, door, posts):
    """Every piece of a house laid as roof_layout lays its roof: walls and posts, the lintel, the logs and the caps."""
    room = [c for c in inside if c not in posts]
    wall_cells = [c for c in ring(inside) if c != door]
    roof = roof_layout(Grid([], []), room, door, wall_cells, 0, ROOF_AT, posts)
    assert not roof["unsupported"], roof
    pieces = walls(inside, door) + [upright(f"Post_{c[0]}_{c[1]}", *c) for c in posts]
    axis, _ = roof["lintel"]
    pieces.append(log("Lintel", *door, 4, axis))
    pieces += [log(f"Roof_{i}", *beam["centre"], 4, beam["axis"]) for i, beam in enumerate(roof["logs"])]
    pieces += [block(f"Cap_{c[0]}_{c[1]}", *c, 4) for c in roof["caps"]]
    return pieces, roof


def footprint(p):
    (x, _, z), (sx, _, sz) = p["pos"], p["size"]
    return {(ix, iz) for ix in range(round((x - sx / 2) / C + 0.5), round((x + sx / 2) / C + 0.5))
            for iz in range(round((z - sz / 2) / C + 0.5), round((z + sz / 2) / C + 0.5))}


@pytest.mark.parametrize("width, depth, posts, door", SHAPES)
def test_the_guided_roof_over_walls_and_posts_rests_and_makes_a_house(width, depth, posts, door):
    inside = [(x, z) for x in range(width) for z in range(depth)]
    chosen = layout([pt(c) for c in inside], pt(door), [pt(c) for c in posts])
    assert chosen == (inside, door, sorted(posts)), chosen
    pieces, roof = built(inside, door, posts)
    supports = set(ring(inside)) - {door} | set(posts)
    at_roof = [p for p in pieces if p["pos"][1] > 3 * C]
    taken = {}
    for p in at_roof:  # no two roof pieces in one cell
        for c in footprint(p):
            assert c not in taken, (p["name"], taken.get(c), c)
            taken[c] = p["name"]
    for beam in roof["logs"]:  # each log rests on its middle, or spans between two supports
        cx, cz = beam["centre"]
        ends = [(cx - 1, cz), (cx + 1, cz)] if beam["axis"] == "x" else [(cx, cz - 1), (cx, cz + 1)]
        assert beam["centre"] in supports or all(e in supports for e in ends), beam
        # A log on a post is set from the room beside the post, on the floor (the body's own test below).
        if beam["kind"] == "post":
            assert beam["centre"] in posts and any(n in beam["over"] for n in sides([beam["centre"]])), beam
    found = houses(pieces, GROUND)
    assert len(found) == 1 and found[0]["posts"] == sorted(posts) and found[0]["doors"] == [door], (
        assess(pieces, GROUND, names(pieces)))
    assert plan(pieces, GROUND, inside, door, posts)["house"]


def test_each_wall_or_post_holds_one_log():
    # Three by four with one post, the doorway west at the south end: the walls either side of the doorway carry the
    # lintel, so the cell east of it, (0, 1), has only the post, whose log along x covers it; then the cell north of
    # the post, (1, 2), which only the post's log along z could cover, has nothing left.
    inside = [(x, z) for x in range(3) for z in range(4)]
    refused = layout([pt(c) for c in inside], [-C, 0], [pt(POST)])
    assert refused == ("the roof over (2.5, 5.0) has nothing left to rest on: the post at (2.5, 2.5) beside it holds "
                       "another log already, and each wall or post holds one; stand another post beside it, or move "
                       "the doorway"), refused
    assert not isinstance(layout([pt(c) for c in inside], [C, -C], [pt(POST)]), str)  # the doorway south


def test_the_l_shaped_room_now_finds_a_roof_without_overlaps():
    # Before ADR-033 the roof was matched cell by cell and then found to overlap; the roof is now laid as a whole.
    shape = [(0, 0), (0, 1), (1, 0), (1, 1), (1, 2), (1, 3)]
    assert layout([pt(c) for c in shape], [-C, 0]) == (shape, (-1, 0), [])


# ---- the plan for a house with a post -------------------------------------------------------------------------------

def test_a_chosen_house_with_a_post_says_what_it_needs_next():
    empty = plan([], GROUND, INSIDE, DOOR, [POST])
    assert empty["next"].startswith(
        "walls three blocks high all round the room, corners too, but for the doorway at (2.5, -2.5), and the post "
        "inside at (2.5, 2.5) three blocks high (a log stood on end): "), empty["next"]
    assert "(2.5, 2.5) stands 0.0" in empty["next"]
    standing = walls(INSIDE, DOOR) + [upright("Log_post", *POST)]
    up = plan(standing, GROUND, INSIDE, DOOR, [POST])
    assert up["done"] == ["the walls stand three blocks high all round", "the post stands three blocks high",
                          "the room is clear", "the doorway at (2.5, -2.5) is open up to the roof"], up["done"]
    assert "Log_post" in up["pieces"] and "Log_post" not in up["in_the_way"]
    assert up["next"].startswith(
        "the roof, every piece at height 8.75 (over the walls, set from a step one block high outside them, never in "
        "the doorway or the way out; over the post, from the floor inside): over the doorway at (2.5, -2.5), a log "
        "along x (turn 0) centred on it"), up["next"]
    assert ("over (2.5, 0.0) and (2.5, 5.0), a log along z (turn 90) centred on the post at (2.5, 2.5), resting on its "
            "middle (set it standing on the floor beside the post)") in up["next"], up["next"]
    done = plan(hut(), GROUND, INSIDE, DOOR, [POST])
    assert done["house"] and done["next"] == "none: it is a house. Walk in by the doorway at (2.5, -2.5) and stand inside"
    assert {"Log_post", "Log_over_post"} <= set(done["pieces"])
    # Without its post the layout is not one the roof can rest on: the plan says so.
    assert "nothing holds up the roof over (2.5, 0.0), (2.5, 2.5)" in plan([], GROUND, INSIDE, DOOR)["next"]


def test_the_post_is_not_kept_clear(tmp_path):
    # The body keeps the room, the doorway and the way out clear when it frees its hands; the post's cell is for the
    # post.
    from godling.memory import NativeMemory
    mem = NativeMemory(tmp_path / "mem")
    mem.set_house({"inside": [list(c) for c in INSIDE], "door": list(DOOR), "posts": [list(POST)]})
    assert mem.reserved_cells() == set(ROOM) | {DOOR, (1, -2)}


# ---- the body sets the roof over a post from the floor inside --------------------------------------------------------

def island_hut(roof=(), me=(0, BODY_CENTRE_Y, 0)):
    """The post-and-beam house as island pieces, walls and post up, the roof pieces `roof` on, a log to lay lying out
    by the doorway; the body inside, holding the log."""
    pieces = [p for p in hut() if p["name"].startswith(("Block_w", "Log_post")) or p["name"] in roof]
    island = Island([ground(), *[ent(p["name"], p["pos"], p["size"]) for p in pieces],
                     ent("Log_roof", (2.5, 1.25, -12.5), (7.5, 2.5, 2.5))], me=me)
    island.solid_pieces = True
    island.held = "Log_roof"
    return island


def placed(island):
    return [d for a, d in island.acts if a == "Place"]


def test_the_log_over_a_post_is_set_from_the_floor_beside_it(monkeypatch):
    # From the floor, the body's centre is 6.2 below the roof's middle: its hands (7) reach 3.25 out at that height. A
    # body standing beside the post reaches the log's middle over the post; nothing one block high stands inside to
    # step up onto. The log is set as aimed, on the post's middle, not moved to rest on its ends.
    island = island_hut(roof=["Log_lintel"])
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island)
    r = body.run("place_at", {"x": 2.5, "y": 8.75, "z": 2.5, "turn": 90})
    assert r.ok, r.summary
    assert placed(island)[-1]["position"] == [2.5, 8.75, 2.5] and placed(island)[-1]["rotation"]["yaw"] == 90
    assert island.me[1] == pytest.approx(BODY_CENTRE_Y)  # on the floor
    assert any(abs(island.me[0] - c[0] * C) <= C / 2 and abs(island.me[2] - c[1] * C) <= C / 2 for c in ROOM)
    assert math.dist(island.me, (2.5, 8.75, 2.5)) <= PLACE_RANGE


def test_a_beam_overhead_is_set_from_the_floor_under_it(monkeypatch):
    # A log along z across the cell south of the post, its ends on the south wall and the post: wholly over the head, it
    # is set standing under its middle (6.2 from the hands). The house's own roof lays none like it, but the mind may.
    island = Island([ground(), *[ent(p["name"], p["pos"], p["size"]) for p in walls(INSIDE, (-1, 1))],
                     ent("Log_post", upright("x", *POST)["pos"], (2.5, 7.5, 2.5)),
                     ent("Log_roof", (-12.5, 1.25, 2.5), (7.5, 2.5, 2.5))], me=(0, BODY_CENTRE_Y, 2.5))
    island.solid_pieces = True
    island.held = "Log_roof"
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island)
    r = body.run("place_at", {"x": 2.5, "y": 8.75, "z": 0, "turn": 90})
    assert r.ok, r.summary
    assert placed(island)[-1]["position"] == [2.5, 8.75, 0.0]
    assert island.me[1] == pytest.approx(BODY_CENTRE_Y)


# ---- the mind chooses a house with a post ---------------------------------------------------------------------------

def test_the_mind_chooses_a_house_with_a_post(monkeypatch, tmp_path):
    from test_mind import house_island
    island, body, mem, mind, logs = house_island(monkeypatch, tmp_path, [ent(p["name"], p["pos"], p["size"])
                                                                         for p in hut()])
    # Three by three without a post: refused, and told why.
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR)}, island.snap())
    assert "house" not in mem.state
    assert mind.notes[-1].startswith("Your house was not set: nothing holds up the roof over (2.5, 0.0), (2.5, 2.5)")
    # With the post: set, kept with its post, and it stands.
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR), "posts": [pt(POST)]}, island.snap())
    house = mem.state["house"]
    assert house["posts"] == [list(POST)] and house["built"] and "Log_post" in house["pieces"]
    assert [(l["phase"], l.get("posts")) for l in logs if l["kind"] == "house"][:2] == [("rejected", None), ("chose", [list(POST)])]
    line = mind._house_line(island.snap())
    assert "the doorway at (2.5, -2.5), posts at (2.5, 2.5). " in line and "Next: none: it is a house" in line, line
    # The post's cell is not kept clear for the room; the room's cells are.
    assert POST not in mem.reserved_cells() and (0, 0) in mem.reserved_cells()
    # The same house again is no change, with its posts or with "posts" left out; with no posts it is a revision the
    # roof cannot take, and refused.
    notes = len(mind.notes)
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR), "posts": [pt(POST)]}, island.snap())
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR)}, island.snap())
    assert len(mind.notes) == notes and len([l for l in logs if l["kind"] == "house" and l["phase"] == "chose"]) == 1
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR), "posts": []}, island.snap())
    assert mem.state["house"]["posts"] == [list(POST)] and mind.notes[-1].startswith("Your house was not set")
