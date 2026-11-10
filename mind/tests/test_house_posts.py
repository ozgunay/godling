"""Houses wider than two cells (ADR-033): posts inside hold up the roof, as RimWorld's columns do. A log three cells long
reaches one cell from what holds it up, so a room two cells wide is roofed from its walls and a wider one needs posts:
upright logs inside, standing from the floor to the roof, with the room on all four sides. The world's copy of the check
(main.lua houseAt) is held to the same post-and-beam house in world/tests/test_life.luau."""
import math
import re

import pytest

from godling import skills as sk
from godling.house import CELL, ROOF_AT, Grid, assess, houses, judge, layout, plan, ring, roof_layout, sides
from godling.skills import Skills
from godling.world import BODY_CENTRE_Y, PICKUP_RANGE, PLACE_RANGE
from helpers import ent, ground
from island import FakeTime, Island
from test_house import GROUND, block, log, names

C = CELL
INSIDE = [(x, z) for x in range(3) for z in range(3)]  # three by three
POST = (1, 1)  # in the middle, the room on all four sides of it
ROOM = [c for c in INSIDE if c != POST]
DOOR = (1, -1)  # south, in the middle of the side
PLANNED = {(POST, "z")}  # the house's own roof puts the log over the post along z (plan()["roof"])


def pt(c):
    return [c[0] * C, c[1] * C]


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
        "of it); it has a roof with one more post, at (2.5, 2.5)")
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


@pytest.mark.parametrize("width, depth, posts, door", SHAPES)
def test_the_guided_roof_over_walls_and_posts_rests_and_makes_a_house(width, depth, posts, door):
    inside = [(x, z) for x in range(width) for z in range(depth)]
    chosen = layout([pt(c) for c in inside], pt(door), [pt(c) for c in posts])
    assert chosen == (inside, door, sorted(posts)), chosen
    pieces, roof = built(inside, door, posts)
    supports = set(ring(inside)) - {door} | set(posts)
    grid = Grid(pieces, GROUND)
    for c, spans in grid.columns.items():  # no two roof pieces in one cell
        assert len([name for bottom, _, name in spans if bottom > 3 * C - 0.1]) <= 1, (c, spans)
    for beam in roof["logs"]:  # each log rests on its middle, on a wall or a post
        assert beam["centre"] in supports and beam["rests_on"] == [beam["centre"]], beam
    found = houses(pieces, GROUND)
    assert len(found) == 1 and found[0]["posts"] == sorted(posts) and found[0]["doors"] == [door], (
        assess(pieces, GROUND, names(pieces)))
    assert plan(pieces, GROUND, inside, door, posts)["house"]


def repairs(refusal):
    """The doorways and posts a refusal says would give the room a roof."""
    doors = re.search(r"the doorway at ((?:\(-?[\d.]+, -?[\d.]+\)(?:, | or )?)+)", refusal)
    posts = re.search(r"one more post, at ((?:\(-?[\d.]+, -?[\d.]+\)(?:, | or )?)+)", refusal)
    cells = lambda m: [[float(x), float(z)] for x, z in re.findall(r"\((-?[\d.]+), (-?[\d.]+)\)", m.group(1))] if m else []
    return cells(doors), cells(posts)


def test_each_wall_or_post_holds_one_log():
    # Three by four with one post, the doorway west at the south end: the walls either side of the doorway carry the
    # lintel, so the cell east of it, (0, 1), has only the post, whose log along x covers it; then the cell north of
    # the post, (1, 2), which only the post's log along z could cover, has nothing left. The refusal says so, and names
    # only doorways and posts that give the room a roof (82-AB5: it said the post "holds another log already" when the
    # greedy roof had none on it, and "stand another post beside it" where no post could stand).
    inside = [(x, z) for x in range(3) for z in range(4)]
    for door in ([-C, 0], [7.5, 0]):
        refused = layout([pt(c) for c in inside], door, [pt(POST)])
        assert refused.startswith("no way of laying the roof covers (2.5, 5.0): each wall or post holds one log"), refused
        assert "holds another log already" not in refused and "stand another post beside it" not in refused
        doors, posts = repairs(refused)
        assert doors or posts, refused
        for other in doors:
            assert not isinstance(layout([pt(c) for c in inside], other, [pt(POST)]), str), (other, refused)
        for extra in posts:
            assert not isinstance(layout([pt(c) for c in inside], door, [pt(POST), extra]), str), (extra, refused)
    assert not isinstance(layout([pt(c) for c in inside], [C, -C], [pt(POST)]), str)  # the doorway south


def test_a_refusal_with_no_repair_says_so():
    # Five by six has no roof with lone posts: no other doorway and no one more post gives the room a roof.
    inside = [(x, z) for x in range(5) for z in range(6)]
    refused = layout([pt(c) for c in inside], [0, -C], [pt((1, 1)), pt((3, 1)), pt((2, 3))])
    assert isinstance(refused, str) and refused.endswith(
        "no other doorway, and no one more post, gives it a roof: make the room another size or shape"), refused


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


def test_the_post_cell_is_kept_clear_of_set_down_pieces(tmp_path):
    # 82-CDE4: the hands-full reflex is the only reader of the reserved cells. A block it set down in the post's cell was
    # kept as the post's base; the post is stood there by place_at and put_down, which do not read them.
    from godling.memory import NativeMemory
    mem = NativeMemory(tmp_path / "mem")
    mem.set_house({"inside": [list(c) for c in INSIDE], "door": list(DOOR), "posts": [list(POST)]})
    site = mem.reserved_cells()  # the house's site (ADR-027), its post's cell the post's (INT-1)
    assert site[POST] == "post" and {c for c, kind in site.items() if kind == "room"} == set(ROOM)
    assert site[DOOR] == "doorway" and site[(1, -2)] == "way out"
    mem.state["house"]["built"] = 1.0  # standing, the post's cell stays clear of what the hands set aside, as the room
    assert mem.reserved_cells()[POST] == "post"


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
    body = Skills(island, planned=lambda: PLANNED)
    r = body.run("place_at", {"x": 2.5, "y": 8.75, "z": 2.5, "turn": 90})
    assert r.ok, r.summary
    assert placed(island)[-1]["position"] == [2.5, 8.75, 2.5] and placed(island)[-1]["rotation"]["yaw"] == 90
    assert island.me[1] == pytest.approx(BODY_CENTRE_Y)  # on the floor
    assert any(abs(island.me[0] - c[0] * C) <= C / 2 and abs(island.me[2] - c[1] * C) <= C / 2 for c in ROOM)
    assert math.dist(island.me, (2.5, 8.75, 2.5)) <= PLACE_RANGE


def test_a_beam_overhead_is_set_from_the_floor_under_it(monkeypatch):
    # A log along z across the cell south of the post, its ends on the south wall and the post: wholly over the head, and
    # resting on both ends, it is set standing under its middle (6.2 from the hands), not from the edge of reach beside
    # it (82-SWEEP2: the test did not look where the body stood). The house's own roof lays none like it; the mind may.
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
    assert abs(island.me[0] - 2.5) <= C / 2 and abs(island.me[2]) <= 1.5 * C, island.me  # under the log
    assert math.dist(island.me, (2.5, 8.75, 0)) == pytest.approx(6.2, abs=0.4)


def test_an_unsupported_piece_is_not_set_over_the_head(monkeypatch):
    # 82-AB11: a block over the middle of a room with nothing under it would fall as soon as it is set; the body does
    # not stand under it to set it, as it does under a piece that will rest.
    island = Island([ground(), *[ent(p["name"], p["pos"], p["size"]) for p in walls(INSIDE, DOOR, high=2)],
                     ent("Block_held", (0, 1.25, -12), (2.5, 2.5, 2.5))], me=(0, BODY_CENTRE_Y, 0))
    island.solid_pieces = True
    island.held = "Block_held"
    where = []
    island.results["Place"] = lambda data: where.append(list(island.me)) or "PlaceSuccess"
    monkeypatch.setattr(sk, "time", FakeTime(island))
    Skills(island).run("place_at", {"x": 2.5, "y": 8.75, "z": 2.5})
    assert not any(abs(x - 2.5) < C / 2 + 1.0 and abs(z - 2.5) < C / 2 + 1.0 for x, _, z in where), where


def test_a_cap_is_set_from_a_step_where_one_stands(monkeypatch):
    # 82-CDE2: a cap on a wall, from inside the room, with a step outside: the body steps up, as it did before ADR-033,
    # rather than set it from the floor at the edge of its reach (6.67 of 7).
    two, door = [(0, 0), (0, 1), (1, 0), (1, 1)], (0, -1)
    island = Island([ground(), *[ent(p["name"], p["pos"], p["size"]) for p in walls(two, door)],
                     ent("Log_lintel", (0, 8.75, -C), (7.5, 2.5, 2.5)), ent("Block_step", (0, 1.25, 4 * C)),
                     ent("Block_cap", (12, 1.25, 12))], me=(0, BODY_CENTRE_Y, C))
    island.held = "Block_cap"
    monkeypatch.setattr(sk, "time", FakeTime(island))
    r = Skills(island).run("place_at", {"x": 0, "y": 8.75, "z": 2 * C})
    assert r.ok and "you stood on Block_step" in r.summary, r.summary


def test_a_lintel_aimed_a_cell_off_goes_across_the_doorway(monkeypatch):
    # 82-AB8: a lintel aimed on the west flank's middle rests there, but a cell along it lies across both flanks, over
    # the doorway: the hands set it there, as before ADR-033. Only a log the house's own plan puts on a middle stays.
    two, door = [(0, 0), (0, 1), (1, 0), (1, 1)], (0, -1)
    island = Island([ground(), *[ent(p["name"], p["pos"], p["size"]) for p in walls(two, door)],
                     ent("Log_lintel", (12.5, 1.25, -12.5), (7.5, 2.5, 2.5))], me=(0, BODY_CENTRE_Y, -10))
    island.held = "Log_lintel"
    monkeypatch.setattr(sk, "time", FakeTime(island))
    r = Skills(island).run("place_at", {"x": -C, "y": 8.75, "z": -C, "turn": 0})
    assert r.ok and placed(island)[-1]["position"] == pytest.approx([0, 8.78, -C]), r.summary
    assert "with its ends on Block_w-1_-1_3 and Block_w1_-1_3 instead" in r.summary
    # A log on the post's middle that the house does not plan there is moved the same way, onto the post and a wall.
    island = island_hut(roof=["Log_lintel"])
    monkeypatch.setattr(sk, "time", FakeTime(island))
    r = Skills(island).run("place_at", {"x": 2.5, "y": 8.75, "z": 2.5, "turn": 90})
    assert r.ok and placed(island)[-1]["position"] != [2.5, 8.75, 2.5], r.summary


def test_a_log_that_tips_off_its_middle_says_what_was_under_it(monkeypatch):
    # 82-CLEAN19: the report names what lay under the log's middle and words the rule as the prompt does.
    island = island_hut(roof=["Log_lintel"])
    island.on_act["Place"] = lambda d: island.ents["Log_roof"].update(position=[2.5, 1.25, 0])
    monkeypatch.setattr(sk, "time", FakeTime(island))
    r = Skills(island, planned=lambda: PLANNED).run("place_at", {"x": 2.5, "y": 8.75, "z": 2.5, "turn": 90})
    assert "it did not stay up there: its middle at (2.5, 2.5) lay on Log_post (top 7.50)" in r.summary, r.summary
    assert r.summary.endswith("A log stays up resting on its middle, or with both ends on something of the same height")


def test_a_piece_on_a_posts_top_is_lifted_from_the_floor_beside_it(monkeypatch):
    # 82-AB2: a block lying on the post's top where the post's log goes. The plan says to lift it off from the floor
    # beside the post; the hands reach up to its underside there (the world takes the nearest piece within 1.5 of where
    # the hands reach, from at most 6 away), though they cannot reach its middle.
    pieces = [p for p in hut() if p["name"].startswith(("Block_w", "Log_post", "Log_lintel"))]
    pieces.append(block("Block_on_post", *POST, 4))
    step = plan(pieces, GROUND, INSIDE, DOOR, [POST])
    assert "Block_on_post" in step["in_the_way"]
    assert ("first take Block_on_post off the top of (2.5, 2.5) (reach up from the floor beside the post): the log "
            "over (2.5, 0.0) and (2.5, 5.0) rests there; then over (2.5, 0.0) and (2.5, 5.0)") in step["next"], step["next"]
    island = Island([ground(), *[ent(p["name"], p["pos"], p["size"]) for p in pieces]], me=(0, BODY_CENTRE_Y, 0))
    island.solid_pieces = True
    monkeypatch.setattr(sk, "time", FakeTime(island))
    r = Skills(island).run("pick_up", {"object": "Block_on_post"})
    assert r.ok and island.held == "Block_on_post", r.summary
    assert island.me[1] == pytest.approx(BODY_CENTRE_Y)


def test_a_log_laid_elsewhere_over_a_cell_the_posts_log_needs_is_in_the_way():
    # 82-CDE3: a log along z on the north wall's middle over (1, 2), laid while the doorway was west, then the doorway
    # moved south. The cell south of the post has only the post's log, which reaches over (1, 2) too: the log already
    # there is named, and free to lift, not kept as the house's own.
    pieces = [p for p in hut() if p["name"] not in ("Log_over_post", "Block_cap1_3")] + [log("Log_N1", 1, 3, 4, "z")]
    step = plan(pieces, GROUND, INSIDE, DOOR, [POST])
    assert "Log_N1" in step["in_the_way"] and "Log_N1" not in step["pieces"], step
    assert "first take Log_N1 off" in step["next"], step["next"]


# ---- following the plan, piece by piece ------------------------------------------------------------------------------

AT = re.compile(r"\((-?\d+\.\d), (-?\d+\.\d)\)")


def follow(inside, door, posts, order, limit=80):
    """Build a house as the plan says, one piece at a time, taking its roof's needs in `order` ("first" or "last"):
    True once it is a house, or the step it got stuck on (82-AB1: a log laid as asked re-routed its cell to another
    wall, which then dropped out of the caps, and the plan ended with an empty roof step)."""
    pieces = []

    def add(p):
        p["name"] = f"{p['name']}_{len(pieces)}"
        pieces.append(p)
    for _ in range(limit):
        found = plan(pieces, GROUND, inside, door, posts)
        if found["house"]:
            return True
        step = found["next"]
        if step.startswith("walls three blocks"):
            for c in ring(inside):
                if c != door:
                    for k in (1, 2, 3):
                        add(block("Block_w", *c, k))
            for c in posts:
                add(upright("Log_post", *c))
            continue
        needs = step.split("): ", 1)[1].split("; ") if step.startswith("the roof") and "): " in step else []
        if not needs or not needs[0]:
            return step
        need = needs[0] if order == "first" else needs[-1]
        cells = [(round(float(x) / C), round(float(z) / C)) for x, z in AT.findall(need)]
        if need.startswith("a block on top"):
            add(block("Block_cap", *cells[0], 4))
        else:
            axis = re.search(r"a log along (x|z)", need).group(1)
            on = re.search(r"centred on the (?:wall|post) at (\(-?\d+\.\d, -?\d+\.\d\))", need)
            centre = cells[0] if need.startswith("over the doorway") else [
                (round(float(x) / C), round(float(z) / C)) for x, z in AT.findall(on.group(1))][0]
            add(log("Log_roof", *centre, 4, axis))
    return "too many steps"


@pytest.mark.parametrize("order", ["first", "last"])
@pytest.mark.parametrize("width, depth, posts, door", SHAPES)
def test_following_the_plan_piece_by_piece_finishes_the_house(width, depth, posts, door, order):
    inside = [(x, z) for x in range(width) for z in range(depth)]
    assert follow(inside, door, posts, order) is True


@pytest.mark.parametrize("width, depth, posts, door", [s for s in SHAPES if s[2]])
def test_the_body_sets_each_log_on_a_post_from_the_floor(monkeypatch, width, depth, posts, door):
    # 82-SWEEP3: for every shape, each log the roof puts on a post is set by the body standing on the floor inside,
    # within the world's reach, and stays where it was aimed.
    inside = [(x, z) for x in range(width) for z in range(depth)]
    room = [c for c in inside if c not in posts]
    roof = roof_layout(Grid([], []), room, door, [c for c in ring(inside) if c != door], 0, ROOF_AT, posts)
    beams = {(b["centre"], b["axis"]) for b in roof["logs"]}
    pieces = walls(inside, door) + [upright(f"Log_post{c[0]}_{c[1]}", *c) for c in posts]
    island = Island([ground(), *[ent(p["name"], p["pos"], p["size"]) for p in pieces]],
                    me=(room[0][0] * C, BODY_CENTRE_Y, room[0][1] * C))
    island.solid_pieces = True
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island, planned=lambda: beams)
    for i, beam in enumerate(b for b in roof["logs"] if b["kind"] == "post"):
        (cx, cz), axis = beam["centre"], beam["axis"]
        name = f"Log_roof{i}"
        island.ents[name] = ent(name, (cx * C, 30, cz * C), (7.5, 2.5, 2.5))  # a log as it lies: turned 90 along z
        island.held = name
        r = body.run("place_at", {"x": cx * C, "y": 8.75, "z": cz * C, "turn": 0 if axis == "x" else 90})
        assert r.ok and placed(island)[-1]["position"] == [cx * C, 8.75, cz * C], (beam, r.summary)
        assert island.me[1] == pytest.approx(BODY_CENTRE_Y), beam


def test_a_roof_search_cut_short_says_so(monkeypatch):
    # 82-CLEAN13: had the search's limit ever been met, its refusal read as a proven failure, with advice to add a post.
    from godling import house
    monkeypatch.setattr(house, "SEARCH", 1)
    house.roof_issue.cache_clear()
    north = [C, 3 * C]  # with the doorway north, laying the logs cell by cell, first way first, leaves a cell bare
    refused = layout([pt(c) for c in INSIDE], north, [pt(POST)])
    monkeypatch.undo()
    house.roof_issue.cache_clear()
    assert refused == "the roof is too much to work out for this room: make it smaller or simpler", refused
    assert layout([pt(c) for c in INSIDE], north, [pt(POST)]) == (INSIDE, (1, 3), [POST])


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
    # The hands-full reflex keeps the post's cell clear too (82-CDE4); the post is stood there by place_at.
    assert POST in mem.reserved_cells() and (0, 0) in mem.reserved_cells()
    # The same house again is no change, with its posts or with "posts" left out; with no posts it is a revision the
    # roof cannot take, and refused.
    notes = len(mind.notes)
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR), "posts": [pt(POST)]}, island.snap())
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR)}, island.snap())
    assert len(mind.notes) == notes and len([l for l in logs if l["kind"] == "house" and l["phase"] == "chose"]) == 1
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR), "posts": []}, island.snap())
    assert mem.state["house"]["posts"] == [list(POST)] and mind.notes[-1].startswith("Your house was not set")


def test_a_house_reply_that_leaves_things_out(monkeypatch, tmp_path):
    from test_mind import house_island
    island, body, mem, mind, logs = house_island(monkeypatch, tmp_path, [ent(p["name"], p["pos"], p["size"])
                                                                         for p in hut()])
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR), "posts": [pt(POST)]}, island.snap())
    # 82-SWEEP1: a reply of only posts, or only a doorway, revises the house it has; only "inside": [] gives it up.
    notes = len(mind.notes)
    mind._choose_house({"posts": [pt(POST)], "why": "a post in the middle holds up the roof"}, island.snap())
    assert mem.state["house"]["inside"] == [list(c) for c in INSIDE] and len(mind.notes) == notes
    mind._choose_house({"door": [-C, C]}, island.snap())
    assert mem.state["house"]["door"] == [-1, 1] and mem.state["house"]["posts"] == [list(POST)], mind.notes[-1:]
    assert "revised" in [l["phase"] for l in logs if l["kind"] == "house"][-3:]
    # 82-AB3: posts left out carry over only where they still stand alone in the new room: growing the room keeps the
    # post, narrowing it to two cells drops it, and a house moved elsewhere has none.
    grown = [(x, z) for x in range(3) for z in range(4)]
    mind._choose_house({"inside": [pt(c) for c in grown], "door": pt(DOOR)}, island.snap())
    assert mem.state["house"]["posts"] == [list(POST)] and len(mem.state["house"]["inside"]) == 12, mind.notes[-1:]
    narrow = [(x, z) for x in range(2) for z in range(3)]
    mind._choose_house({"inside": [pt(c) for c in narrow], "door": [0, -C]}, island.snap())
    assert mem.state["house"]["posts"] == [] and len(mem.state["house"]["inside"]) == 6, mind.notes[-1:]
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR), "posts": [pt(POST)]}, island.snap())
    away = [[40 + x * C, 40 + z * C] for x in range(2) for z in range(2)]
    mind._choose_house({"inside": away, "door": [40, 37.5], "why": "the ground here floods"}, island.snap())
    assert mem.state["house"]["inside"][0] == [16, 16] and mem.state["house"]["posts"] == [], mind.notes[-1:]


# ---- the house's site knows its posts (INT-1: #81's site counted a post's cell as room) --------------------------------

def site_island(monkeypatch, tmp_path, entities, me=(0, 0)):
    """The three by three with its post chosen as the house, walls standing, and the body and the mind wired as
    run_godling.py wires them (the site, the planned roof)."""
    from godling.learned import SkillLibrary
    from godling.memory import NativeMemory
    from godling.mind import Mind
    pieces = [ent(p["name"], p["pos"], p["size"]) for p in walls(INSIDE, DOOR)]
    island = Island([ground(), *pieces, *entities], me=(me[0], BODY_CENTRE_Y, me[1]))
    island.turns = True
    monkeypatch.setattr(sk, "time", FakeTime(island))
    mem, library = NativeMemory(tmp_path / "mem"), SkillLibrary(tmp_path / "skills.json")
    body = Skills(island, library=library, protected=mem.protected_cubes, kept_in=mem.built_into,
                  reserved=mem.reserved_cells, planned=mem.planned_roof)
    mind = Mind(None, mem, "", body, library, house_project=True)
    mind._choose_house({"inside": [pt(c) for c in INSIDE], "door": pt(DOOR), "posts": [pt(POST)]}, island.snap())
    assert mem.state["house"]["posts"] == [list(POST)]
    return island, body, mem, mind


def test_the_site_rule_tells_of_the_post():
    # INT-8: the site rule said the room is kept clear, and the house paragraph that a wider room needs posts in it.
    from godling.mind import SITE_RULE
    assert "in a post's cell, its\npost" in SITE_RULE and "or across a post's cell, is not part of the house" in SITE_RULE


def test_the_site_marks_the_post_cell_as_the_posts(monkeypatch, tmp_path):
    from godling.house import site_of
    from godling.site import house_cells
    site = site_of(INSIDE, DOOR, [POST])
    assert site[POST] == "post" and all(site[c] == "room" for c in ROOM)
    assert {c for c, kind in site.items() if kind == "wall"} == set(ring(INSIDE)) - {DOOR}
    island, body, mem, mind = site_island(monkeypatch, tmp_path, [])
    assert mem.reserved_cells()[POST] == "post" and POST in house_cells(mem)


def test_the_post_is_stood_through_the_body_and_only_the_post_goes_there(monkeypatch, tmp_path):
    # INT-1: #81's site took the post's cell for room, so the hands refused the post the plan asked for ("is in your
    # house's room"). A log stood on end goes there now, or blocks; anything else is refused, and what lies across it is
    # in the way.
    island, body, mem, mind = site_island(monkeypatch, tmp_path, [
        ent("Log_post", (-10, 1.25, -10), (7.5, 2.5, 2.5)), ent("Log_flat", (-15, 1.25, -10), (7.5, 2.5, 2.5)),
        ent("Axe_1", (-20, 0.2, -10), (0.4, 0.4, 1.0))], me=(0, 0))
    island.held = "Axe_1"
    r = body.run("put_down", {"x": 2.5, "z": 2.5})
    assert not r.ok and "is in your house's post's cell, where only the post goes" in r.summary, r.summary
    island.held = "Log_flat"
    r = body.run("put_down", {"x": 2.5, "z": 2.5})
    assert not r.ok and "across your house's post at (2.5, 2.5): Log_flat there would stick out of the post's cell" in (
        r.summary), r.summary
    island.held = "Log_post"
    r = body.run("place_at", {"x": 2.5, "y": 3.75, "z": 2.5, "upright": True})
    assert r.ok and island.held is None and island.ents["Log_post"]["position"] == [2.5, 3.75, 2.5], r.summary
    found = mind.house_progress(island.snap())
    assert "the post stands three blocks high" in found["done"] and "Log_post" in found["pieces"], found


def test_a_log_lying_across_the_post_cell_is_in_the_way(monkeypatch, tmp_path):
    pieces = walls(INSIDE, DOOR) + [log("Log_across", *POST, 1, "x")]
    step = plan(pieces, GROUND, INSIDE, DOOR, [POST])
    assert "Log_across" in step["in_the_way"] and "Log_across" not in step["pieces"], step
    assert ("the post at (2.5, 2.5) stands 0.0 (Log_across lies across it, out of the post's cell)") in step["next"], (
        step["next"])


def test_the_hands_full_reflex_sets_nothing_in_the_post_cell(monkeypatch, tmp_path):
    # Standing beside the post's cell with a block in hand, the body frees its hands off the whole site, the post's
    # cell too (82-CDE4).
    island, body, mem, mind = site_island(monkeypatch, tmp_path, [
        ent("Block_held", (-30, 1.25, -30), (2.5, 2.5, 2.5)), ent("Block_want", (2.5, 1.25, -12.5), (2.5, 2.5, 2.5))],
        me=(0, 2.5))
    island.held = "Block_held"
    r = body.run("pick_up", {"object": "Block_want"})
    assert r.ok and island.held == "Block_want", r.summary
    x, _, z = island.ents["Block_held"]["position"]
    assert (round(x / C), round(z / C)) not in set(INSIDE) | set(ring(INSIDE)), (x, z)


def test_a_three_by_three_with_a_post_is_built_through_the_body(monkeypatch, tmp_path):
    # Walls standing and the lintel on: the body stands the post, then sets the post's log on its middle from the floor
    # beside it, and the plan sees both done. The rest of the roof goes on as in a room two wide.
    island, body, mem, mind = site_island(monkeypatch, tmp_path, [
        ent("Log_lintel", (2.5, 8.75, -2.5), (7.5, 2.5, 2.5)), ent("Log_post", (-10, 1.25, -10), (7.5, 2.5, 2.5)),
        ent("Log_roof", (-15, 1.25, -10), (7.5, 2.5, 2.5))], me=(0, 0))
    island.solid_pieces = True
    island.held = "Log_post"
    assert body.run("place_at", {"x": 2.5, "y": 3.75, "z": 2.5, "upright": True}).ok
    mind.house_progress(island.snap())
    assert ((1, 1), "z") in mem.planned_roof()
    island.held = "Log_roof"
    r = body.run("place_at", {"x": 2.5, "y": 8.75, "z": 2.5, "turn": 90})
    assert r.ok and island.ents["Log_roof"]["position"] == [2.5, 8.75, 2.5], r.summary
    found = mind.house_progress(island.snap())
    assert "the post stands three blocks high" in found["done"] and "Log_roof" in found["pieces"], found
    assert "centred on the post" not in found["next"], found["next"]
