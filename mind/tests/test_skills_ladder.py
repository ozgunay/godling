"""A standing ladder is the way up: the hands set nothing on it, just over its top, or at its foot (ADR-025).

On 2026-11-08 Godling set a stone on top of the ladder it was raising its walls with, and could not build on there.
"""
import pytest

from godling import skills as sk
from godling.skills import Skills
from godling.world import BODY_CENTRE_Y
from helpers import block, ent, ground
from island import FakeTime, Island

FACING_X = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]  # turned a quarter: thin along x, its rungs facing east and west


@pytest.fixture
def make(monkeypatch):
    def build(entities=(), **kw):
        island = Island([ground()] + list(entities), **kw)
        monkeypatch.setattr(sk, "time", FakeTime(island))
        logs = []
        body = Skills(island, log=lambda **k: logs.append(k))
        body.logs = logs
        return island, body
    return build


def ladder(x, z=0, name="Ladder_1"):
    """A ladder standing on the ground, three blocks tall, its rungs facing east and west."""
    return ent(name, (x, 3.77, z), (2, 7.5, 0.4), rot=FACING_X)


def wall_with_ladder():
    """The screenshot: a wall three blocks high along z at x = 5 (from 3.75 to 6.25), Ladder_1 against its west face.
    It is climbed from the west, so its foot is there."""
    wall = [block(f"Block_{i}", 5, 1.25 + 2.5 * layer, z)
            for i, (layer, z) in enumerate(((layer, z) for layer in range(3) for z in (-2.5, 0, 2.5)), 1)]
    return wall + [ladder(3.55)]


STEP_BESIDE = block("Block_10", 2.5, 1.25, 2.5)  # beside the ladder, clear of its foot: to stand on to reach higher


def test_no_stone_on_top_of_a_standing_ladder(make):
    island, body = make(wall_with_ladder() + [STEP_BESIDE, ent("Stone_1", (-8, 1.25, 8))])
    island.held = "Stone_1"
    r = body.run("place_at", {"x": 2.5, "y": 8.79, "z": 0})
    assert not r.ok and r.summary == ("(2.5, 8.8, 0.0) is on top of Ladder_1: anything there closes the way up it. "
                                      "Set it a cell further off, or move the ladder first")
    assert island.actions("Place") == [] and island.actions("MoveTo") == []
    # A block over its top, in the way of the climber's head, is refused too; higher than that is not its business.
    assert "on top of Ladder_1" in body.run("place_at", {"x": 2.5, "y": 11.0, "z": 0}).summary
    assert body.run("place_at", {"x": 2.5, "y": 3.77, "z": 0}).summary.startswith("(2.5, 3.8, 0.0) is where Ladder_1 "
                                                                                 "stands: anything there")
    # The wall it stands against may rise past its top.
    r = body.run("place_at", {"x": 5, "y": 8.79, "z": 0})
    assert r.ok and r.summary.startswith("Stone_1 came to rest at (5.00, 8.79, 0.00), on top of Block_8")


def test_nothing_at_the_foot_it_is_climbed_from(make):
    island, body = make(wall_with_ladder() + [STEP_BESIDE, ent("Stone_1", (-8, 1.25, 8))])
    island.held = "Stone_1"
    # Two cells out: the world's climber steps off 1.5 out from the ladder, and the body is two wide.
    r = body.run("put_down", {"x": 0, "z": 0})
    assert not r.ok and r.summary == ("(0.0, 0.0) is at the foot of Ladder_1, where you stand to climb it: anything "
                                      "there closes the way up it. Set it a cell further off, or move the ladder first")
    r = body.run("place_at", {"x": 0, "y": 1.27, "z": 0})
    assert not r.ok and r.summary.startswith("(0.0, 1.3, 0.0) is at the foot of Ladder_1")
    assert island.actions("Place") == []
    # Beside the ladder, and a cell further out, are clear of its foot.
    assert body.run("put_down", {"x": 2.5, "z": -2.5}).ok
    island.held = "Stone_1"
    assert body.run("put_down", {"x": -2.5, "z": 0}).ok
    # Its foot is the way up, not the way it leans: the wall behind it goes higher.
    island.held = "Stone_1"
    assert body.run("place_at", {"x": 5, "y": 8.79, "z": 2.5}).ok


def test_a_ladder_facing_north_and_south(make):
    # Its rungs face along z, against a mesa to the north; its foot reaches into the cell south of its own.
    mesa = ent("Mesa_1", (0, 3.5, -6.45), (10, 7, 10), role="Mesa")
    island, body = make([mesa, ent("Ladder_1", (0, 3.77, -0.6), (2, 7.5, 0.4)), ent("Stone_1", (-8, 1.25, 8))],
                        me=(-6, BODY_CENTRE_Y, 6))
    island.held = "Stone_1"
    assert body.run("put_down", {"x": 0, "z": 2.5}).summary.startswith("(0.0, 2.5) is at the foot of Ladder_1")
    assert body.run("put_down", {"x": 2.5, "z": 2.5}).ok


def test_a_ladder_against_nothing_keeps_its_top_but_not_its_foot(make):
    island, body = make([ladder(0), ent("Ladder_2", (10, 0.2, 0), (2, 0.4, 7.5)), ent("Stone_1", (-8, 1.25, 8))])
    island.held = "Stone_1"
    assert "on top of Ladder_1" in body.run("place_at", {"x": 0, "y": 8.79, "z": 0}).summary
    assert body.run("put_down", {"x": 2.5, "z": 0}).ok  # it leads nowhere, so nobody stands at its foot
    island.held = "Stone_1"
    r = body.run("place_at", {"x": 10, "y": 1.67, "z": 0})  # a ladder lying on the ground is only a thing lying there
    assert r.ok and "on top of Ladder_2" in r.summary


def test_freeing_the_hands_passes_over_the_foot_of_a_ladder(make):
    # A ladder up against a mesa to the west; its foot, on the east, is the farthest spot from what it reaches for.
    mesa = ent("Mesa_1", (-15.2, 3.5, 0), (10, 7, 30), role="Mesa")
    island, body = make([mesa, ladder(-10), block("Stone_1", -3, 1.25, 8), block("Block_2", 10, 1.25, 0)])
    island.held = "Stone_1"
    r = body.run("pick_up", {"object": "Block_2"})
    assert r.ok and island.held == "Block_2"
    x, _, z = island.ents["Stone_1"]["position"]
    assert (x, z) != (-7.5, 0) and r.summary.startswith("picked up Block_2 (first set Stone_1 down")


def test_a_stone_already_on_a_ladder_says_how_to_get_it_down(make):
    # The screenshot as it stands: the stone on top of the ladder, too high to reach from the ground.
    island, body = make(wall_with_ladder() + [block("Stone_1", 2.5, 8.77, 0)], me=(-5, BODY_CENTRE_Y, 0))
    r = body.run("pick_up", {"object": "Stone_1"})
    assert not r.ok and r.summary == ("no clear spot to reach Stone_1 from here (it lies on top of Ladder_1: "
                                      "pick up the ladder and it falls)")
    assert body.run("pick_up", {"object": "Ladder_1"}).ok  # the world lets what rested on it fall (test_build.luau)
