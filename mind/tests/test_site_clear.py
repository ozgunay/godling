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
from godling.world import BODY_CENTRE_Y
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


def flat_log(name, x, z, along="x", y=1.25):
    return ent(name, (x, y, z), (7.5, 2.5, 2.5) if along == "x" else (2.5, 2.5, 7.5))


def upright_log(name, x, z, bottom=0.0, **kw):
    return ent(name, (x, bottom + 3.75, z), (2.5, 7.5, 2.5), **kw)


def footprint(e):
    """The cells a piece lying as `e` lies reaches into, any part of it."""
    (x, _, z), (sx, _, sz) = e["position"], e["size"]
    def span(lo, hi):
        return range(math.floor(lo / C + 0.5 + 1e-9), math.ceil(hi / C - 0.5 - 1e-9) + 1)
    return {(ix, iz) for ix in span(x - sx / 2, x + sx / 2) for iz in span(z - sz / 2, z + sz / 2)}


def site_body(monkeypatch, tmp_path, entities, me, solid=False, floor=None):
    """The island with the house chosen there, and the body and the mind wired as run_godling.py wires them."""
    island = Island([*(floor or [ground()]), *entities], me=(me[0], BODY_CENTRE_Y, me[1]))
    island.solid_pieces = solid
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
def test_the_hands_full_reflex_keeps_the_walls_and_the_ground_round_them_clear(monkeypatch, tmp_path, held):
    # Godling outside the west wall with a log in its hands, reaching for another. The reflex kept the room, the doorway
    # and the way out clear, but not the walls or the ground round them: it laid the log at (-90.0, -12.5), along the
    # north side of the north wall.
    piece = flat_log("Log_held", 0, 30) if held == "log" else block("Stone_held", 0, 1.25, 30)
    island, body, mem, mind, _ = site_body(monkeypatch, tmp_path, [piece, flat_log("Log_want", -100, -20)],
                                           me=(-95, -17.5))
    island.held = piece["name"]
    r = body.run("pick_up", {"object": "Log_want"})
    assert r.ok and island.held == "Log_want", r.summary
    assert not footprint(island.ents[piece["name"]]) & SITE, (r.summary, sorted(footprint(island.ents[piece["name"]])))


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
    # The roof is laid over the walls and reaches out over the ground round them: not the site's business. It is set
    # from a step a block high (here the wall's own block is nearest).
    island.held = "Log_1"
    r = body.run("place_at", {"x": -92.5, "y": 8.75, "z": -20})
    assert r.ok and island.ents["Log_1"]["position"] == [-92.5, 8.75, -20], r.summary
    assert "you stood on Stone_1 to reach that high, and stepped back down" in r.summary, r.summary
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
    assert library.resolve_helpers({"a": {"nearest_free": "log"}}, body) == {"a": "Log_held"}
    assert library.resolve_helpers({"a": {"nearest_free": "stone"}}, body) == {"a": "Stone_1"}
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
