"""The body keeps Godling's building site clear, and gets itself out when the site is tangled (ADR-027).

Live run 2026-11-08 22:10 to 2026-11-09 07:50 UTC: in the last hour 89 of the 95 failures came from the body. Godling
knew its site was choked (its digest: "Loose logs ... pen me in") and 13 of its plans were about clearing it. The body
defeated it:
- the hands-full reflex set things down on the site (29 over the run, 21 of them logs), on the walls' cells and the
  ground round them;
- a stray log lying across a wall cell counted as the house's own, so the body would not lift it, while setting a log in
  that cell was refused because the stray was there;
- with nowhere in reach to set a held log down, every pick-up failed and the log stayed in its hands (Log_7, 07:11 to
  07:19, 29 failures), and the wall skill it used 283 times reached past the log in its hands for another;
- a walk that stuck said only "stuck N short", and `nearest_free` picked the same unreachable log five times.

The house there, chosen 07:05: room cells x -90 and -87.5, z -20 and -17.5; doorway (-87.5, -22.5); way out
(-87.5, -25). In cells: room (-36..-35, -8..-7), doorway (-35, -9), way out (-35, -10).
"""
import math

import pytest

from godling import skills as sk
from godling.learned import SkillLibrary
from godling.memory import NativeMemory
from godling.mind import Mind
from godling.skills import Skills
from godling.world import BODY_CENTRE_Y, world_size
from helpers import block, ent, ground
from island import FakeTime, Island

C = 2.5
ROOM = [(-36, -8), (-36, -7), (-35, -8), (-35, -7)]
DOOR = (-35, -9)
EIGHT = [(dx, dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if dx or dz]
WALLS = {(cx + dx, cz + dz) for cx, cz in ROOM for dx, dz in EIGHT} - set(ROOM) - {DOOR}
# The ground a cell wide round the walls and the doorway, the way out with it: where the body stands to build them.
STRIP = {(cx + dx, cz + dz) for cx, cz in WALLS | {DOOR} for dx, dz in EIGHT} - WALLS - set(ROOM) - {DOOR}
SITE = set(ROOM) | WALLS | {DOOR} | STRIP
APPROACH = {(-36, -11), (-35, -11), (-34, -11)}  # straight on beyond the way out: the way in to the doorway


def flat_log(name, x, z, along="x", y=1.25):
    return ent(name, (x, y, z), (7.5, 2.5, 2.5) if along == "x" else (2.5, 2.5, 7.5))


def upright_log(name, x, z, bottom=0.0, **kw):
    return ent(name, (x, bottom + 3.75, z), (2.5, 7.5, 2.5), **kw)


def footprint(e):
    """The cells a piece lying as `e` lies reaches into, any part of it, turned as it lies."""
    (x, _, z), (sx, _, sz) = e["position"], world_size(e["size"], e.get("rotation"))
    def span(lo, hi):
        return range(math.floor(lo / C + 0.5 + 1e-9), math.ceil(hi / C - 0.5 - 1e-9) + 1)
    return {(ix, iz) for ix in span(x - sx / 2, x + sx / 2) for iz in span(z - sz / 2, z + sz / 2)}


def site_body(monkeypatch, tmp_path, entities, me, solid=False, floor=None):
    """The island with the house chosen there, and the body and the mind wired as run_godling.py wires them."""
    island = Island([*(floor or [ground()]), *entities], me=(me[0], BODY_CENTRE_Y, me[1]))
    island.solid_pieces = solid
    island.turns = True  # a log set down turned a quarter round lies along z, as in the world
    monkeypatch.setattr(sk, "time", FakeTime(island))
    mem, library, logs = NativeMemory(tmp_path / "mem"), SkillLibrary(tmp_path / "skills.json"), []
    body = Skills(island, library=library, protected=mem.protected_cubes, kept_in=mem.built_into,
                  reserved=mem.reserved_cells, log=lambda **k: logs.append(k))
    body.logs = logs
    mind = Mind(None, mem, "", body, library, house_project=True)
    mind._choose_house({"inside": [[c[0] * C, c[1] * C] for c in ROOM], "door": [DOOR[0] * C, DOOR[1] * C]},
                       island.snap())
    assert mem.state["house"]["inside"] == [list(c) for c in sorted(ROOM)]
    return island, body, mem, mind, library


# ---- c. a stray piece in a wall cell is in the way, not the house's own ---------------------------------------------
def test_a_stray_log_across_a_wall_cell_is_in_the_way_not_the_houses_own(monkeypatch, tmp_path):
    # Log_6 lay along z at (-92.5, -25): its north end in the house's south-west corner, the rest on the ground outside.
    # The house counted it as a course of that corner: "Log_6 is part of your house ..., which you are building; move
    # the house or give it up first", while putting a log down in the corner said "(-92.5, -22.5) is occupied by Log_6".
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [
        flat_log("Log_6", -92.5, -25, "z"),
        flat_log("Log_94", -87.5, -15),  # along the north wall, wholly in its cells: a course of it
        upright_log("Log_9", -92.5, -20),  # stood in the west wall
        flat_log("Log_held", 0, 30)], me=(-100, -25))
    house = mem.state["house"]
    assert "Log_6" in house["in_the_way"] and "Log_6" not in house["pieces"]
    assert {"Log_94", "Log_9"} <= set(house["pieces"]) and not {"Log_94", "Log_9"} & set(house["in_the_way"])
    # The house's next step says what lies across that corner, and does not count it as the wall standing there.
    found = mind.house_progress(island.snap())
    assert "(-92.5, -22.5) stands 0.0 (Log_6 lies across it, out of the walls' line)" in found["next"], found["next"]
    assert "Log_6" in mind.situation(island.snap(), [], []).split("Loose objects")[1].split("Stacks")[0]
    # So the body lifts it, and keeps what is in line.
    assert body.run("pick_up", {"object": "Log_94"}).summary.startswith("Log_94 is part of your house")
    r = body.run("pick_up", {"object": "Log_6"})
    assert r.ok and island.held == "Log_6", r.summary


# ---- a. set-downs keep the site clear --------------------------------------------------------------------------------
@pytest.mark.parametrize("held", ["log", "stone"])
@pytest.mark.parametrize("me, want", [
    ((-95, -17.5), (-100, -20)),  # beside the west wall, reaching just past it
    ((-88.75, -18.75), (-60, -18.75)), ((-95, -17.5), (-120, -17.5)), ((-82.5, -17.5), (-55, -17.5)),
    ((-90, -12.5), (-90, 15)), ((-87.5, -25), (-87.5, -50))])  # in the room, beside each wall, in the way out
def test_the_hands_full_reflex_keeps_the_walls_and_the_ground_round_them_clear(monkeypatch, tmp_path, held, me, want):
    # Godling outside the west wall with a log in its hands, reaching for another. The reflex kept the room, the doorway
    # and the way out clear, but not the walls or the ground round them: it laid the log at (-90.0, -12.5), along the
    # north side of the north wall. With the ground round them kept clear, it laid what it held in the walls' empty
    # cells instead, a log along a wall or a stone in one, and the house kept it as its own (81-SWEEP1).
    piece = flat_log("Log_held", 0, 30) if held == "log" else block("Stone_held", 0, 1.25, 30)
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [piece, flat_log("Log_want", *want)], me=me)
    island.held = piece["name"]
    r = body.run("pick_up", {"object": "Log_want"})
    assert r.ok and island.held == "Log_want", r.summary
    assert not footprint(island.ents[piece["name"]]) & (SITE | APPROACH), (r.summary, island.ents[piece["name"]])
    mind.house_progress(island.snap())
    assert piece["name"] not in mem.state["house"]["pieces"]


def test_put_down_and_place_at_keep_the_site_clear(monkeypatch, tmp_path):
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [
        block("Stone_1", -100, 1.25, -12.5), block("Stone_2", -100, 1.25, -7.5), block("Stone_3", -105, 1.25, -7.5),
        flat_log("Log_1", -102.5, -2.5), flat_log("Log_2", -102.5, 2.5),
        ent("Ladder_1", (-105, 3.77, -12.5), (2, 7.5, 0.4))],
        me=(-100, -17.5))

    def refused(skill, args, why):
        acts = len(island.acts)
        r = body.run(skill, args)
        assert not r.ok and why in r.summary, r.summary
        assert "MoveTo" not in island.actions()[acts:] and "Place" not in island.actions()[acts:]
        return r.summary
    # The ground a cell round the walls, where the body stands to build them, and the room, the doorway, the way out.
    island.held = "Log_1"
    said = refused("put_down", {"x": -95, "z": -15, "turn": 90}, "beside your house's walls")
    assert said.startswith("(-95.0, -15.0) is beside your house's walls, on the ground a cell wide round them")
    refused("place_at", {"x": -95, "y": 1.3, "z": -15, "turn": 90}, "beside your house's walls")
    # A log across a wall, sticking out of the walls' line, is refused.
    said = refused("put_down", {"x": -92.5, "z": -20}, "across your house's wall")
    assert said == ("(-92.5, -20.0) is across your house's wall at (-92.5, -20.0): Log_1 there would stick out of "
                    "the walls' line, into (-95.0, -20.0) beside the walls and (-90.0, -20.0) in the room. Your hands "
                    "keep the site clear: a piece goes in a wall along its line, or off the site")
    island.held = "Stone_1"
    refused("put_down", {"x": -90, "z": -20}, "in your house's room")
    refused("put_down", {"x": -87.5, "z": -22.5}, "in your house's doorway")
    refused("put_down", {"x": -87.5, "z": -25}, "in the way out of your house's doorway")
    # In a wall's cell a block goes, as a block of that wall; beside the walls, a block on its own, as a step to build
    # from (the house's roof is set from one), but nothing on top of it.
    assert body.run("put_down", {"x": -92.5, "z": -17.5}).ok
    assert island.ents["Stone_1"]["position"] == [-92.5, 1.37, -17.5]
    island.held = "Stone_2"
    assert body.run("put_down", {"x": -95, "z": -22.5}).ok
    for name in ("Stone_1", "Stone_2"):  # they settle on the ground, as the world's do
        island.ents[name]["position"][1] = 1.25
    island.held = "Stone_3"
    refused("place_at", {"x": -95, "y": 3.8, "z": -22.5}, "beside your house's walls")
    # A log turned along a wall, or stood on end in it, goes.
    island.held = "Log_1"
    r = body.run("put_down", {"x": -92.5, "z": -20, "turn": 90})
    assert not r.ok and "occupied by Stone_1" in r.summary  # along the west wall it would reach the block set there
    r = body.run("put_down", {"x": -85, "z": -20, "turn": 90})
    assert r.ok, r.summary
    island.held = "Log_2"
    r = body.run("put_down", {"x": -92.5, "z": -15, "upright": True})
    assert r.ok, r.summary
    # The roof is laid over the walls and reaches out over the ground round them: not the site's business. (How the
    # body gets up to it, from a step or from the floor, is the body's own: INT-7 of the review of #81.)
    island.held = "Log_1"
    r = body.run("place_at", {"x": -92.5, "y": 8.75, "z": -20})
    assert r.ok and island.ents["Log_1"]["position"] == [-92.5, 8.75, -20], r.summary
    assert "your hands keep the site clear" not in r.summary.lower()
    # A ladder stands against a wall, on the ground beside it.
    island.held = "Ladder_1"
    assert body.run("put_down", {"x": -95, "z": -12.5}).ok


# ---- b. with nowhere clear in reach, carry it off the site -----------------------------------------------------------
THE_SITE_AT_07_49 = [  # the pieces round the house as the mind last saw them (memory/state.json, 07:49 UTC)
    upright_log("Log_10", -90.0, -15.0, bottom=2.5, attrs={"Fastened": True}), flat_log("Log_105", -102.5, -12.5),
    flat_log("Log_106", -90.0, -5.0), flat_log("Log_12", -97.5, -15.0), flat_log("Log_13", -95.0, -17.5),
    upright_log("Log_2", -92.5, -15.0), flat_log("Log_20", -102.5, -20.0), flat_log("Log_21", -90.0, -22.5, y=8.75),
    flat_log("Log_25", -100.49, -25.71), flat_log("Log_6", -92.5, -25.0, "z"), flat_log("Log_7", -82.5, -17.5),
    upright_log("Log_8", -90.0, -22.5, attrs={"Fastened": True}),
    upright_log("Log_88", -85.0, -20.0, attrs={"Fastened": True}),
    upright_log("Log_9", -92.5, -20.0), flat_log("Log_94", -87.5, -15.0), flat_log("Log_97", -92.5, -10.0),
    flat_log("Log_98", -95.0, -25.0, "z"), flat_log("Log_99", -95.0, -7.5), block("Stone_2", -97.5, 1.25, -22.5)]


def test_the_site_at_07_49_names_what_is_in_its_way(monkeypatch, tmp_path):
    # At the end of the run the house kept ten logs as its own, three of them strays lying across a wall cell, and saw
    # nothing in its way.
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, THE_SITE_AT_07_49, me=(-110, -12.5))
    house = mem.state["house"]
    assert {"Log_6", "Log_7", "Log_13"} <= set(house["in_the_way"]), house  # across a wall cell, out of line
    assert {"Log_12", "Log_98"} <= set(house["in_the_way"]), house  # on the ground round the walls
    assert {"Log_2", "Log_8", "Log_9", "Log_88", "Log_94", "Log_10", "Log_21"} == set(house["pieces"]), house
    found = mind.house_progress(island.snap())
    assert "Log_12" in found["next"] and "Log_98" in found["next"], found["next"]


@pytest.mark.parametrize("start", [(-88.75, -18.75), (-87.5, -25.0), (-95.0, -20.0)])
def test_tangled_at_07_49_the_body_carries_what_it_holds_off_the_site(monkeypatch, tmp_path, start):
    # Godling at the site holding a log from elsewhere, wanting Log_105 lying west of it. From the room the walk stuck
    # ("stuck 5.6 units short of (-102.0, -12.5)", naming nothing); from the west side, boxed in by Log_13, Log_98,
    # Log_9 and Stone_2, the hands were full with "no clear spot nearby". From the way out it got there before as well.
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, THE_SITE_AT_07_49 + [flat_log("Log_held", 0, 60)],
                                           me=start, solid=True)
    island.held = "Log_held"
    r = body.run("pick_up", {"object": "Log_105"})
    reflexes = [k.get("text") for k in body.logs if k.get("kind") == "reflex"]
    assert r.ok and island.held == "Log_105", (r.summary, reflexes)
    assert not footprint(island.ents["Log_held"]) & SITE, sorted(footprint(island.ents["Log_held"]))
    assert not footprint(island.ents["Log_held"]) & APPROACH  # 81-AB2: not across the way in to the doorway
    x, y, z = island.ents["Log_held"]["position"]
    assert "Log_held" in r.summary and f"({x:.1f}, {y:.2f}, {z:.1f})" in r.summary, r.summary


def test_with_nowhere_in_reach_the_body_carries_the_piece_off_the_site(monkeypatch, tmp_path):
    # In the room of a house one course high, the ground beyond the site only to the south, further off than the
    # reflex looks (7.5): every spot it tries is on the site. It carries the stone out of the doorway, to the nearest
    # clear ground beyond the site, and says where it went.
    walls = [block(f"Block_w{i}", c[0] * C, 1.25, c[1] * C) for i, c in enumerate(sorted(WALLS))]
    floor = [ent("Ground", (-88.75, -0.5, -18.75), (15, 1, 15), role="Ground"),
             ent("Ground_south", (-88.75, -0.5, -43.125), (15, 1, 33.75), role="Ground")]
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, walls + [flat_log("Log_want", -87.5, -45, "z")],
                                           me=(-88.75, -18.75), solid=True, floor=floor)
    island.held = "Stone_held"
    island.ents["Stone_held"] = block("Stone_held", 0, 1.25, 60)
    r = body.run("pick_up", {"object": "Log_want"})
    assert r.ok and island.held == "Log_want", r.summary
    assert not footprint(island.ents["Stone_held"]) & SITE
    assert "off your house's site" in r.summary


# ---- b. the wall skill goes on with the log in its hands -------------------------------------------------------------
UPRIGHT_LOG_AT = {  # run 2026-11-08's own wall skill, proven, used 283 times
    "name": "upright_log_at", "params": ["x", "z", "standx", "standz"],
    "does": "Picks the nearest free log, walks to a standing spot and stands the log upright in the wall cell (x, z)",
    "steps": [{"skill": "pick_up", "args": {"object": {"nearest_free": "log"}}},
              {"skill": "walk_to", "args": {"x": "$standx", "z": "$standz"}},
              {"skill": "put_down", "args": {"x": "$x", "z": "$z", "upright": True}}]}


def test_nearest_free_is_the_log_in_hand(monkeypatch, tmp_path):
    island, body, mem, mind, library = site_body(monkeypatch, tmp_path, [
        flat_log("Log_held", 0, 30), flat_log("Log_near", -100, -27.5), block("Stone_1", -105, 1.25, -30)],
        me=(-97.5, -22.5))
    island.held = "Log_held"
    assert library.resolve_helpers({"object": {"nearest_free": "log"}}, body, "pick_up") == {"object": "Log_held"}
    assert library.resolve_helpers({"object": {"nearest_free": "stone"}}, body, "pick_up") == {"object": "Stone_1"}
    # As a target it is not the one in the hands (81-CDE6): the top of the nearest free log is Log_near's.
    assert library.resolve_helpers({"a": {"top": {"nearest_free": "log"}}}, body) == {"a": [-100, 2.5, -27.5]}
    library.define(UPRIGHT_LOG_AT)
    r = body.run("upright_log_at", {"x": -92.5, "z": -22.5, "standx": -97.5, "standz": -22.5})
    assert r.ok, r.summary
    assert island.ents["Log_held"]["position"][::2] == [-92.5, -22.5] and island.held is None
    assert island.ents["Log_near"]["position"] == [-100, 1.25, -27.5]  # left where it lay


# ---- d. the body names what blocks it, and takes a piece it can reach ------------------------------------------------
def test_a_walk_that_sticks_says_what_stopped_it(monkeypatch, tmp_path):
    # 31 failures in the run were a bare "stuck N short": a way round was known, and the body snagged on the way.
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [flat_log("Log_99", 2.5, 2.5, "z")], me=(0, 0))
    island.frozen = True  # snagged where it stands
    r = body.run("walk_to", {"x": 0, "z": 20})
    assert not r.ok and r.summary.startswith("stuck ") and "Log_99" in r.summary, r.summary


def test_nearest_free_takes_a_log_the_body_can_walk_to(monkeypatch, tmp_path):
    # The nearest log lies in a pit of rock with no way in; the next one lies in the open.
    rock = [ent(f"Mesa_{i}", pos, size, role="Mesa") for i, (pos, size) in enumerate((
        ((10, 5, -6), (14, 10, 2)), ((10, 5, 6), (14, 10, 2)), ((4, 5, 0), (2, 10, 10)), ((16, 5, 0), (2, 10, 10))))]
    island, body, mem, mind, library = site_body(monkeypatch, tmp_path, rock + [
        flat_log("Log_pit", 10, 0), flat_log("Log_open", -15, 0)], me=(0, 0))
    assert library.resolve_helpers({"a": {"nearest_free": "log"}}, body) == {"a": "Log_open"}


# ---- the review of #81 ---------------------------------------------------------------------------------------------
def three_high(skip=()):
    """The house's walls, three blocks high all round, corners too, but for the doorway; no roof yet."""
    return [block(f"Block_w{c[0]}_{c[1]}_{k}", c[0] * C, (k - 0.5) * C, c[1] * C)
            for c in sorted(WALLS) if c not in skip for k in (1, 2, 3)]


@pytest.mark.parametrize("on", [(-92.5, -17.5), (-90.0, -15.0), (-92.5, -20.0)])
def test_up_on_the_walls_the_reflex_lays_nothing_over_the_house(monkeypatch, tmp_path, on):
    # 81-AB9: up on the walls with no roof yet, a log in its hands, reaching for a block far off: the reflex took a spot
    # over the doorway or the room for roof work. Over the doorway the house read it as the lintel, kept it as its own,
    # and its roof step then ran dry. Setting aside is not building: nothing goes on the site, at any height. (The walls
    # are not yet counted as the house's own, as when the mind waits to inspect a site it remembers: counted, the reflex
    # keeps off them anyway, as off anything kept.)
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, three_high() + [
        flat_log("Log_held", 0, 60), block("Block_want", -60, 1.25, -18.75)], me=on)
    mem.state["house"]["pieces"] = []
    island.me[1] = 7.5 + BODY_CENTRE_Y
    island.held = "Log_held"
    r = body.run("pick_up", {"object": "Block_want"})
    log = island.ents["Log_held"]
    assert island.held == "Log_held" or not footprint(log) & (SITE | APPROACH), (r.summary, log["position"])


def test_tools_go_in_no_wall(monkeypatch, tmp_path):
    # 81-CDE2: from the room the reflex set a hammer in the east wall's empty cells. The house reads building pieces
    # only, so it named nothing there, and the wall's own log was refused "occupied by Hammer_1".
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [
        ent("Hammer_1", (0, 0.2, 60), (0.6, 0.4, 2.0)), flat_log("Log_want", -100, -20)], me=(-88.75, -18.75))
    island.held = "Hammer_1"
    r = body.run("pick_up", {"object": "Log_want"})
    assert r.ok and not footprint(island.ents["Hammer_1"]) & (SITE | APPROACH), (r.summary, island.ents["Hammer_1"])
    island.held = "Hammer_1"
    r = body.run("put_down", {"x": -85, "z": -20})
    assert not r.ok and "is in your house's wall, where only its own building pieces go" in r.summary, r.summary


def test_drowning_on_the_carry_is_the_news(monkeypatch, tmp_path):
    # 81-AB1: the carry's walk slipped off the sand into the sea. It took the drowning for a spot it could not reach,
    # went on to the next, and the step said "hands are full ... no clear floor near enough".
    walls = [block(f"Block_w{i}", c[0] * C, 1.25, c[1] * C) for i, c in enumerate(sorted(WALLS))]
    floor = [ent("Ground", (-88.75, -0.5, -18.75), (15, 1, 15), role="Ground"),
             ent("Ground_south", (-88.75, -0.5, -43.125), (15, 1, 33.75), role="Ground")]
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, walls + [flat_log("Log_want", -87.5, -45, "z")],
                                           me=(-88.75, -18.75), solid=True, floor=floor)
    island.ents["Stone_held"] = block("Stone_held", 0, 1.25, 60)
    island.held = "Stone_held"

    def slip(data):
        island.me = [island.me[0], -2.0, island.me[2]]  # in the water: the edge is too high to climb back out
    island.on_act["MoveTo"] = slip
    r = body.run("pick_up", {"object": "Log_want"})
    assert not r.ok and "fell off the edge into the sea" in r.summary, r.summary


def pen(low_corner):
    """The body at (0, 0) in a pen one cell across. Block_N is the side to lift on the way to the goal (0, 20); the
    other sides and the south corners are logs stood on end, the north-west corner a block (low) or a log (tall)."""
    sides = [block("Block_N", 0, 1.25, 2.5), upright_log("Log_W", -2.5, 0), upright_log("Log_E", 2.5, 0),
             upright_log("Log_S", 0, -2.5), upright_log("Log_SW", -2.5, -2.5), upright_log("Log_SE", 2.5, -2.5),
             upright_log("Log_NE", 2.5, 2.5)]
    return sides + [block("Block_NW", -2.5, 1.25, 2.5) if low_corner else upright_log("Log_NW", -2.5, 2.5)]


@pytest.mark.parametrize("low_corner", [True, False])
def test_penned_in_the_body_rests_what_it_holds_clear_of_the_gap(monkeypatch, low_corner):
    # 81-AB4: resting the held log on the low corner laid it along x over the very side it was lifting, at the body's
    # height: the walk out stuck, the lift failed, and the next try rested Block_N up on a log out of reach.
    island = Island([ground(), *pen(low_corner), flat_log("Log_held", 0, 60)], me=(0, BODY_CENTRE_Y, 0))
    island.solid_pieces = island.turns = True
    island.held = "Log_held"
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island)
    r = body.run("walk_to", {"x": 0, "z": 20})
    assert r.ok and island.me[2] > 15, r.summary
    assert island.ents["Block_N"]["position"][1] < 2, island.ents["Block_N"]  # set back, not left up on a log
    if low_corner:  # rested where the hands can take it back from outside, and taken back
        assert island.held == "Log_held", (island.held, island.ents["Log_held"])


def test_a_step_beside_the_walls_is_no_free_material(monkeypatch, tmp_path):
    # 81-CDE1: the mind set a stone beside its walls to build the roof from, as the house's roof step says; the house
    # put it in its way, which made it free material, and nearest_free took it for the next stone. A woodpile the mind
    # kept by name, lying there, lost its keeping too.
    island, body, mem, mind, library = site_body(monkeypatch, tmp_path, three_high() + [
        block("Stone_step", -100, 1.25, -12.5), block("Stone_far", -110, 1.25, -12.5),
        flat_log("Log_pile", -95, -7.5, "z")], me=(-100, -17.5))
    mem.add_structure("woodpile", ["Log_pile"], (-95, -7.5), {"Log_pile": (-95, 1.25, -7.5)}, keep=True)
    island.held = "Stone_step"
    assert body.run("put_down", {"x": -95, "z": -17.5}).ok
    mind.house_progress(island.snap())
    house = mem.state["house"]
    assert house["steps"] == ["Stone_step"] and "Stone_step" not in house["in_the_way"], house
    assert {"Stone_step", "Log_pile"} <= mem.protected_cubes()
    assert library.resolve_helpers({"object": {"nearest_free": "stone"}}, body, "pick_up") == {"object": "Stone_far"}
    assert body.run("pick_up", {"object": "Stone_step"}).ok  # still the body's to lift


def roofed():
    """The house standing: its walls three blocks high, a block on top of each, and over the room and the doorway."""
    return three_high() + [block(f"Block_r{c[0]}_{c[1]}", c[0] * C, 8.75, c[1] * C)
                           for c in sorted(WALLS) + ROOM + [DOOR]]


def test_once_the_house_stands_its_ground_is_the_minds(monkeypatch, tmp_path):
    # 81-CDE5: the house stood, and still every put_down beside its walls was refused, for the rest of the run.
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, roofed() + [flat_log("Log_wood", -110, -10)],
                                           me=(-100, -20))
    assert mind.house_progress(island.snap())["house"] and mem.state["house"]["built"]
    island.held = "Log_wood"
    r = body.run("put_down", {"x": -95, "z": -17.5, "turn": 90})
    assert r.ok, r.summary
    # What the body sets aside still keeps out of its room, doorway and way out.
    site = mem.reserved_cells()
    assert not site.building and set(site) == set(ROOM) | {DOOR, (-35, -10)}


def test_a_stuck_walk_names_what_is_on_the_leg_it_walked(monkeypatch, tmp_path):
    # 81-AB8: snagged where nothing touched it, on a route going round a mesa to the goal behind it, it named the mesa:
    # on the straight line to the goal, but not on the leg it walked.
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [ent("Mesa_0", (5, 5, 0), (4, 10, 6), role="Mesa")],
                                           me=(0, 0))
    island.frozen = True
    r = body.run("walk_to", {"x": 20, "z": 0})
    assert not r.ok and r.summary.startswith("stuck") and "Mesa_0" not in r.summary, r.summary


def test_hands_emptied_on_the_way_it_goes_on_to_pick_up(monkeypatch):
    # 81-AB3: on the way to set the held block down, a lift out of a pen rested it out of reach and emptied the hands;
    # pick_up still said "hands are full: holding Block_2", and did not take what its free hands could.
    island = Island([ground(), block("Block_1", 10, 1.25, 0), block("Block_2", -3, 1.25, 0)])
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island)
    island.held = "Block_2"
    island.results["Place"] = lambda data: "PlaceSuccess" if island.held else "PlaceFailed:NothingHeld"

    def rest_it(data):
        if island.held == "Block_2":
            island.ents["Block_2"] = {**island.ents["Block_2"], "position": [-3, 8.77, 0]}
            island.held = None
    island.on_act["MoveTo"] = rest_it
    r = body.run("pick_up", {"object": "Block_1"})
    assert r.ok and island.held == "Block_1", r.summary
    assert "Block_2 left your hands on the way and lies at (-3.0, 8.77, 0.0)" in r.summary, r.summary


def test_a_put_back_that_fails_on_the_carry_frees_the_hands_for_what_was_rested(monkeypatch, tmp_path):
    # 81-CDE8: boxed in at 07:49, the carry's walk lifts Log_13 out of the way, and the world will not take it back
    # where it lay. Set aside (carried off, if nothing near will do), it leaves the hands free to take back what they
    # rested, and the carry then sets down the piece it says it does.
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, THE_SITE_AT_07_49 + [flat_log("Log_held", 0, 60)],
                                           me=(-95.0, -20.0), solid=True)
    island.held = "Log_held"
    lay = list(island.ents["Log_13"]["position"])
    island.results["Place"] = lambda data: ("PlaceFailed:Occupied" if island.held == "Log_13"
                                            and math.dist(data["position"], lay) < 0.5 else "PlaceSuccess")
    r = body.run("pick_up", {"object": "Log_105"})
    assert r.ok and island.held == "Log_105", r.summary
    for name in ("Log_held", "Log_13"):  # neither left on the site, nor up on the pen's sides
        assert not footprint(island.ents[name]) & (SITE | APPROACH), (name, island.ents[name], r.summary)
    x, y, z = island.ents["Log_held"]["position"]
    assert f"({x:.1f}, {y:.2f}, {z:.1f})" in r.summary, r.summary


def test_put_down_says_what_left_the_hands_on_the_way(monkeypatch):
    # 81-CDE8: put_down worded its result from the piece it held before it walked. When a lift out of a pen on the way
    # left another piece in the hands, it set that one down and said it had set down the first, where the first lay.
    island = Island([ground(), block("Block_1", 10, 1.25, 0), block("Block_2", -3, 1.25, 0)])
    monkeypatch.setattr(sk, "time", FakeTime(island))
    body = Skills(island)
    island.held = "Block_1"

    def swap(data):
        if island.held == "Block_1":
            island.ents["Block_1"] = {**island.ents["Block_1"], "position": [5, 1.25, 5]}
            island.held = "Block_2"
    island.on_act["MoveTo"] = swap
    r = body.run("put_down", {"x": 20, "z": 0})
    assert not r.ok and r.summary == "Block_1 left your hands on the way and lies at (5.0, 1.25, 5.0); you hold Block_2"
    assert island.held == "Block_2"


@pytest.mark.parametrize("where, why", [((-87.5, -22.5), "in your house's doorway"),
                                        ((-87.5, -25.0), "in the way out of your house's doorway"),
                                        ((-90.0, -20.0), "in your house's room"), ((-95.0, -17.5), "")])
def test_a_ladder_stands_beside_the_walls_only(monkeypatch, tmp_path, where, why):
    # 81-AB5: a ladder went anywhere on the site, the doorway too, where the house cannot see it (it reads building
    # pieces only).
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [ent("Ladder_1", (-105, 3.77, -12.5), (2, 7.5, 0.4))],
                                           me=(-100, -20))
    island.held = "Ladder_1"
    r = body.run("put_down", {"x": where[0], "z": where[1]})
    assert (r.ok and not why) or (not r.ok and why and why in r.summary), r.summary


@pytest.mark.parametrize("name, size, ok", [("Axe_1", (0.6, 0.4, 2.0), False), ("Coconut_1", (0.9, 0.9, 0.9), False),
                                            ("Stone_1", (2.5, 2.5, 2.5), True)])
def test_only_a_block_goes_beside_the_walls_as_a_step(monkeypatch, tmp_path, name, size, ok):
    # 81-AB6: the step's allowance let anything a cell across lie beside the walls: an axe, a coconut.
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [ent(name, (-110, size[1] / 2, -10), size)],
                                           me=(-100, -20))
    island.held = name
    r = body.run("put_down", {"x": -95, "z": -17.5})
    assert r.ok == ok and (ok or "beside your house's walls" in r.summary), r.summary


def test_a_step_on_ground_a_little_higher_is_still_a_step(monkeypatch, tmp_path):
    # 81-CDE9: the step's "on the ground" was measured from the room's floor, not the ground under the step: a block on
    # sand 0.4 higher beside the walls was refused as no step.
    floor = [ground(), ent("Ground_rise", (-95, -0.1, -17.5), (2.5, 1, 2.5), role="Ground")]
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [block("Stone_1", -110, 1.25, -10)], me=(-100, -20),
                                           floor=floor)
    island.held = "Stone_1"
    r = body.run("put_down", {"x": -95, "z": -17.5})
    assert r.ok, r.summary


def test_a_boulder_goes_in_a_wall_cell(monkeypatch, tmp_path):
    # 81-CLEAN17: a boulder (2.6 across) centred in a wall cell reaches 0.05 into every cell round it. The hands refused
    # it as sticking out of the walls' line, naming the corner, while the house kept one lying there as its own.
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [ent("Boulder_1", (-110, 1.3, -10), (2.6, 2.6, 2.6))],
                                           me=(-100, -20))
    island.held = "Boulder_1"
    r = body.run("put_down", {"x": -92.5, "z": -20})
    assert r.ok, r.summary
    mind.house_progress(island.snap())
    assert "Boulder_1" in mem.state["house"]["pieces"]


def test_far_from_the_house_the_carry_does_not_say_its_site(monkeypatch, tmp_path):
    # 81-SWEEP2: 168 from the house, with the near spots all taken, the carry said it carried the log "off your
    # house's site".
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [flat_log("Log_held", 0, 30),
                                                                   flat_log("Log_want", 60, 90)], me=(60, 60))
    island.held = "Log_held"
    island.results["Place"] = ["PlaceFailed:Occupied"] * 16 + ["PlaceSuccess"]  # the near spots are all taken
    r = body.run("pick_up", {"object": "Log_want"})
    assert r.ok and "carried Log_held further off" in r.summary and "house" not in r.summary, r.summary


def test_pick_up_goes_round_what_it_walks_up_to(monkeypatch):
    # 81-CLEAN18: pick_up routed as if its target were not there, cut the log's corner on the way round to its far side,
    # snagged, and had to look for another way.
    island = Island([ground(), flat_log("Log_A", 0, 5), *[block(f"Block_{i}", x, 1.25, 2.5)
                                                         for i, x in enumerate((-2.5, 0, 2.5))]],
                    me=(0, BODY_CENTRE_Y, -2))
    island.solid_pieces = True
    monkeypatch.setattr(sk, "time", FakeTime(island))
    logs = []
    body = Skills(island, log=lambda **k: logs.append(k))
    r = body.run("pick_up", {"object": "Log_A"})
    assert r.ok and island.held == "Log_A", r.summary
    assert not [k for k in logs if k.get("kind") == "reflex" and "looking for another way" in k.get("text", "")]
