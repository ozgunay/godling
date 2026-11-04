"""The body's rarer paths: tight pens, stairs, failed step-offs, and the words it finds for where things lie."""
import pytest

from godling import skills as sk
from godling.skills import Skills, Stuck
from godling.world import BODY_CENTRE_Y, Entity
from helpers import block, ent, ground
from island import FakeTime, Island


@pytest.fixture
def make(monkeypatch):
    def build(entities=(), protected=(), bare=False, **kw):
        island = Island(([] if bare else [ground()]) + list(entities), **kw)
        monkeypatch.setattr(sk, "time", FakeTime(island))
        logs = []
        body = Skills(island, protected=lambda: set(protected), log=lambda **k: logs.append(k))
        body.logs = logs
        return island, body
    return build


def reflexes(body):
    return [l["text"] for l in body.logs if l["kind"] == "reflex"]


def ring(spacing, start=1):
    spots = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
    return [block(f"Block_{i}", x * spacing, 1.25, z * spacing) for i, (x, z) in enumerate(spots, start)]


def once(fn):
    """Runs fn on the first call only."""
    calls = []

    def wrapped(data):
        if not calls:
            calls.append(data)
            fn(data)
    return wrapped


# ---- what the body is told ------------------------------------------------------------------------------
def test_words_for_where_things_lie(make):
    island, body = make([block("Block_1", 0, 1.25, 0), block("Block_2", 5, 1.25, 0),
                         ent("Beam", (2.5, 3.0, 0), (7.5, 1, 1)), ent("Float", (20, 9, 0), (1, 1, 1))])
    snap = island.snap()
    assert body._resting_on(snap, snap.entities["Beam"]) == "across Block_1 and Block_2"
    assert body._resting_on(snap, snap.entities["Float"]) == "not resting on anything (still moving or tilted)"
    assert body._describe(snap, "Gone") == "Gone is gone (fell into the sea)"
    lone, body2 = make([block("Block_1", 0, 1.25, 0)])
    hits = body2._overlapping(lone.snap(), (0, 3.4, 0), (2.5, 2.5, 2.5))
    assert hits == ["Block_1 (its top is at y=2.500; the held object's bottom would be at y=2.150)"]
    assert body2._overlapping(lone.snap(), (0, 2.55, 50), (1, 1, 1)) == []


def test_on_step_watches_every_observation(make):
    island, body = make()
    seen = []
    body.on_step = seen.append
    body.run("walk_to", {"x": 5, "z": 0})
    assert seen


def test_falling_into_the_sea_is_not_replanned(make):
    island, body = make(bare=True, entities=[ent("Sand", (0, -0.5, 0), (6, 1, 6), role="Ground")])
    with pytest.raises(Stuck, match="fell off the edge"):
        body._move(10, 0)
    assert not any("another way" in t for t in reflexes(body))


def test_a_search_that_never_ends_gives_up(make):
    walls = [ent(f"Mesa_{i}", pos, size, role="Mesa") for i, (pos, size) in enumerate([
        ((60, 5, 8), (20, 10, 2)), ((60, 5, -8), (20, 10, 2)), ((68, 5, 0), (2, 10, 20)), ((52, 5, 0), (2, 10, 20))])]
    island, body = make(walls)
    assert body._route(island.snap(), (0, 0), (60, 0)) is None


def test_step_up_with_no_edge_there(make):
    island, body = make([block("Block_1", 10, 1.25, 0)])
    assert body._step_up(island.snap(), 10, 0, 99) is None


def test_no_foot_to_walk_to(make):
    island, body = make(bare=True, entities=[ent("Rock", (0, -0.5, 0), (0.8, 1, 0.8), role="Ground"),
                                             ent("Mesa_1", (20, 5, 0), (10, 10, 10), role="Mesa")])
    r = body.run("walk_to", {"x": 20, "z": 0})
    assert r.summary == "(20.0, 0.0) is on top of Mesa_1 (height 10.0); you cannot climb it and found no clear spot at its foot"


# ---- tight pens ---------------------------------------------------------------------------------------------
def test_tight_pen_with_full_hands_rests_on_the_wall_and_takes_it_back(make):
    island, body = make(ring(3.8) + [block("Stone_9", 30, 1.25, 0)])
    island.solid_pieces = True
    island.held = "Stone_9"
    r = body.run("walk_to", {"x": 15, "z": 0})
    assert r.ok
    places = [d["position"] for a, d in island.acts if a == "Place"]
    assert places[0][1] == pytest.approx(2.5 + 1.25 + 0.02)  # rested on top of the wall first
    pickups = [d["position"] for a, d in island.acts if a == "Pickup"]
    assert pickups[0] == [0.0, 1.25, -3.8]  # then lifted the wall's nearest piece out of the way


def test_tight_pen_with_nowhere_to_rest(make):
    island, body = make(ring(3.8) + [block("Stone_9", 30, 1.25, 0)])
    island.solid_pieces = True
    island.held = "Stone_9"
    island.results["Place"] = "PlaceFailed:Occupied"
    r = body.run("walk_to", {"x": 15, "z": 0})
    assert not r.ok and "penned in by Block_" in r.summary


def test_pen_where_nothing_lifts(make):
    island, body = make(ring(3.8))
    island.solid_pieces = True
    island.results["Pickup"] = "PickupFailed:Heavy"
    r = body.run("walk_to", {"x": 15, "z": 0})
    assert not r.ok and "penned in" in r.summary


def test_pen_lift_needs_a_second_try_and_cannot_go_back(make):
    island, body = make(ring(3.8))
    island.solid_pieces = True
    island.on_act["Pickup"] = once(lambda d: setattr(island, "held", None))  # the first lift slips
    island.results["Place"] = ["PlaceFailed:Wobbly", "PlaceSuccess"]
    r = body.run("walk_to", {"x": 15, "z": 0})
    assert r.ok
    assert any("(it could not go back: place rejected: PlaceFailed:Wobbly)" in t for t in reflexes(body))


def test_pen_of_its_own_build_still_lets_it_out(make):
    # Every piece of the pen is something it built and keeps: the mind may not take them, but the reflex that
    # lifts one aside to step out (and sets it back) still may, even when the first lift slips.
    island, body = make(ring(3.8), protected={f"Block_{i}" for i in range(1, 9)})
    body.kept_in = lambda piece: "build at (0.0, 0.0)"
    island.solid_pieces = True
    island.on_act["Pickup"] = once(lambda d: setattr(island, "held", None))
    r = body.run("walk_to", {"x": 15, "z": 0})
    assert r.ok and any("penned in: lifted" in t for t in reflexes(body))
    asked = body.run("pick_up", {"object": "Block_1"})
    assert not asked.ok and "which you built; release that first" in asked.summary


# ---- beams ------------------------------------------------------------------------------------------------------
def posts(left=2, right=2):
    """Two posts of blocks two cells apart, at x -2.5 and 2.5, `left` and `right` blocks high."""
    return ([block(f"Block_{i + 1}", -2.5, 1.25 + 2.5 * i, 0) for i in range(left)]
            + [block(f"Block_{i + 11}", 2.5, 1.25 + 2.5 * i, 0) for i in range(right)])


def holding_log(make, things):
    island, body = make(things + [ent("Log_1", (0, 1.25, 12), (7.5, 2.5, 2.5))])
    island.me = [0, 2.55, 6]
    island.held = "Log_1"
    return island, body


@pytest.mark.parametrize("aim, turn, why", [
    ((0, 6.25, 0), 90, "along z, where its end at (0.0, -2.5) had nothing under it but the ground"),  # turned wrong
    ((2.5, 6.25, 0), 0, "along x, where its end at (0.0, 0.0) had nothing under it but the ground"),  # a cell off
])
def test_a_beam_is_set_on_the_supports_it_was_aimed_at(make, aim, turn, why):
    island, body = holding_log(make, posts())
    r = body.run("place_at", {"x": aim[0], "y": aim[1], "z": aim[2], "turn": turn})
    assert r.ok
    place = [d for a, d in island.acts if a == "Place"][-1]
    assert place["position"] == pytest.approx([0, 5.0 + 1.25 + 0.03, 0])
    assert place["rotation"] == pytest.approx(sk._rotation(0, False))
    assert r.summary.startswith("Log_1 came to rest at (0.00, 6.28, 0.00), across Block_2 and Block_12")
    assert f"(you aimed it at ({aim[0]:.1f}, 6.25, 0.0) {why}" in r.summary
    assert r.summary.endswith("; so your hands set it along x with its ends on Block_2 and Block_12 instead)")


def test_a_beam_aimed_right_goes_where_it_was_aimed(make):
    island, body = holding_log(make, posts())
    r = body.run("place_at", {"x": 0, "y": 6.25, "z": 0})
    assert [d for a, d in island.acts if a == "Place"][-1]["position"] == pytest.approx([0, 6.25, 0])
    assert r.ok and "across Block_2 and Block_12" in r.summary and "you aimed it" not in r.summary


def test_a_beam_that_falls_says_what_was_under_its_ends(make):
    # Posts of unequal height: nothing to set it on, and it tilts off the lower one.
    island, body = holding_log(make, posts(2, 1))
    island.on_act["Place"] = lambda d: island.ents["Log_1"].update(position=[0, 3.2, 0])
    r = body.run("place_at", {"x": 0, "y": 6.25, "z": 0})
    assert r.ok and "you aimed it" not in r.summary
    assert r.summary.endswith("; it did not stay up there: its end at (-2.5, 0.0) lay on Block_2 (top 5.00); its end at "
                              "(2.5, 0.0) hung 2.50 above Block_11 (top 2.50). A beam stays up only with both ends on "
                              "something of the same height")


def test_a_log_laid_on_the_ground_is_no_beam(make):
    island, body = holding_log(make, posts())
    r = body.run("place_at", {"x": 0, "y": 1.25, "z": -10, "turn": 90})
    assert r.ok and [d for a, d in island.acts if a == "Place"][-1]["position"] == pytest.approx([0, 1.25, -10])
    assert "aimed" not in r.summary and "stay up" not in r.summary


# ---- reaching high -------------------------------------------------------------------------------------------
def test_reach_high_skips_what_cannot_be_stood_on(make):
    things = [block("Block_1", -3, 1.25, 3), ent("Coconut_1", (10, 1, 0), (2, 2, 2)),
              block("Block_2", 12.5, 1.25, 2.5), block("Block_3", 12.5, 3.75, 2.5)]  # a block with one on top
    island, body = make(things)
    island.held = "Block_1"
    r = body.run("place_at", {"x": 12.5, "y": 10, "z": 0})
    assert not r.ok and "nothing one block high stands near it" in r.summary


def test_reach_high_but_the_step_does_not_help(make):
    island, body = make([block("Block_1", -3, 1.25, 3), block("Block_2", 10, 1.25, 0)])
    island.held = "Block_1"
    island.results["StepUp"] = "StepUpFailed:NoRoom"
    r = body.run("place_at", {"x": 12.5, "y": 9.5, "z": 0})
    assert not r.ok and "stepping up onto Block_2 did not bring it in reach" in r.summary


def test_place_from_a_little_short(make):
    island, body = make([block("Block_1", -3, 1.25, 3)])
    island.held = "Block_1"

    def short(data):  # the walk ends 3 short of where it was meant to, and the legs will go no further
        island.on_act.pop("Stop")
        island.me[0] -= 3.0
        island.frozen = True
    island.on_act["Stop"] = short
    r = body.run("place_at", {"x": 10, "y": 7.0, "z": 0})
    assert r.ok and r.summary.startswith("Block_1 came to rest at (10.00, 7.00, 0.00)")
    assert island.actions().count("MoveTo") >= 2


def test_rub_walks_up_to_the_log(make):
    island, body = make([ent("Spear_1", (-3, 0.5, 0), (1, 1, 3)), ent("Log_3", (15, 0.5, 0), (7.5, 1, 1))])
    island.held = "Spear_1"
    island.results["Rub"] = "StrikeRubCaught:Fire_1"
    r = body.run("rub", {"object": "Log_3"})
    assert r.ok and island.me[0] > 5


# ---- getting down ----------------------------------------------------------------------------------------------
def test_stairs_down_one_step_at_a_time(make):
    steps = [ent("Step_1", (0, 2.5, 0), (2, 5, 5), role="Mesa"), ent("Step_2", (5, 1.25, 0), (5, 2.5, 5), role="Mesa")]
    island, body = make(steps, me=(0, 5 + BODY_CENTRE_Y, 0))
    r = body.run("walk_to", {"x": 20, "z": 0})
    assert r.ok and r.summary.startswith("stepped down from Step_1; ")
    assert island.me[1] == pytest.approx(BODY_CENTRE_Y)


def test_step_down_refused_then_waits_out_the_climb(make):
    island, body = make([block("Block_1", 0, 1.25, 0)], me=(0, 2.5 + BODY_CENTRE_Y, 0))
    island.results["StepDown"] = ["StepDownFailed:NoRoom", "StepDownStarted"]
    island.on_act["StepDown"] = lambda d: island.attrs.update(Climbing=True)
    island.after_sleep = lambda i: i.attrs.update(Climbing=False) if i.now > 1002 else None
    r = body.run("walk_to", {"x": 12, "z": 0})
    assert r.ok and r.summary.startswith("stepped down 2.5 from Block_1")


def test_ladder_down_without_walking_on(make):
    ladder = ent("Ladder_1", (4.5, 3.75, 0), (2, 7.5, 0.4), rot=[[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
    island, body = make([ent("Mesa_1", (0, 3.5, 0), (8, 7, 8), role="Mesa"), ladder, block("Block_1", 12, 1.25, 0)],
                        me=(2, 7 + BODY_CENTRE_Y, 0))
    island.results["Climb"] = "ClimbStarted:down:2"
    island.on_act["Climb"] = lambda d: setattr(island, "me", [6.5, BODY_CENTRE_Y, 0])
    r = body.run("pick_up", {"object": "Block_1"})
    assert r.ok and island.held == "Block_1"
    assert any(t.startswith("no way to hop down from Mesa_1; climbing down Ladder_1") for t in reflexes(body))


def hop_platform(extra=()):
    return [ent("Mesa_1", (0, 1.0, 0), (8, 2, 8), role="Mesa")] + list(extra)


def test_hop_down_tries_other_edges(make):
    island, body = make(hop_platform(), me=(0, 2 + BODY_CENTRE_Y, 0))
    island.results["StepDown"] = "StepDownFailed:NoRoom"
    tries = []

    def stuck_at_first_edges(data):
        tries.append(data)
        if len(tries) <= 2:
            island.frozen = True
        else:
            island.frozen = False
    island.on_act["MoveTo"] = stuck_at_first_edges
    r = body.run("walk_to", {"x": 12, "z": 0})
    assert r.ok or "could not step off its edge" in r.summary


def test_hop_down_never_lands(make):
    island, body = make(hop_platform(), me=(0, 2 + BODY_CENTRE_Y, 0))
    island.results["StepDown"] = "StepDownFailed:NoRoom"
    island.frozen = True
    r = body.run("walk_to", {"x": 12, "z": 0})
    assert not r.ok and r.summary == "you are up on Mesa_1 at height 2.0 and could not step off its edge"


def test_ways_off_avoid_a_ladder_at_the_edge(make):
    ladder = ent("Ladder_1", (4.6, 3.75, 0), (0.4, 7.5, 2))
    island, body = make(hop_platform([ladder]), me=(0, 2 + BODY_CENTRE_Y, 0))
    ways = body._ways_off(island.snap(), (12, 0), 2.0)
    assert ways and all(not (3.5 < edge[0] and abs(edge[1]) < 2) for edge, land, below in ways[:3])
