"""The body's walks, reaches and builds on the fake island (functional tests of skills.py)."""
import pytest

from godling import skills as sk
from godling.skills import Skills, Stuck
from godling.world import BODY_CENTRE_Y
from helpers import block, ent, ground
from island import FakeTime, Island


@pytest.fixture
def make(monkeypatch):
    def build(entities=(), protected=(), gifted=False, bare=False, **kw):
        island = Island(([] if bare else [ground()]) + list(entities), **kw)
        monkeypatch.setattr(sk, "time", FakeTime(island))
        logs = []
        body = Skills(island, protected=lambda: set(protected), log=lambda **k: logs.append(k), gifted=gifted)
        body.logs = logs
        return island, body
    return build


def reflexes(body):
    return [l["text"] for l in body.logs if l["kind"] == "reflex"]


def at(island):
    return (round(island.me[0], 1), round(island.me[2], 1))


# ---- walking -------------------------------------------------------------------------------------
def test_walk_on_open_ground(make):
    island, body = make()
    r = body.run("walk_to", {"x": 10, "z": 5})
    assert r.ok and r.summary == "walked to (10.0, 5.0)" or r.summary.startswith("walked to (9.")
    assert abs(island.me[0] - 10) < 0.7 and abs(island.me[2] - 5) < 0.7


def test_walk_to_the_sea(make):
    island, body = make()
    assert body.run("walk_to", {"x": 900, "z": 0}).summary == "(900.0, 0.0) is open sea, not ground"


def test_walk_around_a_wall(make):
    wall = ent("Mesa_1", (6, 5, 0), (2, 10, 12), role="Mesa")
    island, body = make([wall])
    r = body.run("walk_to", {"x": 12, "z": 0})
    assert r.ok and abs(island.me[0] - 12) < 0.7
    moves = [d["position"] for a, d in island.acts if a == "MoveTo"]
    assert len(moves) >= 2 and any(abs(p[2]) > 6 for p in moves)  # went round its end


def test_walk_stops_beside_a_loose_piece(make):
    island, body = make([block("Block_1", 10, 1.25, 0)])
    r = body.run("walk_to", {"x": 10, "z": 2})
    assert r.ok and r.summary.endswith("; stopped beside Block_1 instead of walking into it")
    assert abs(island.me[2]) >= 2.5


def test_walk_under_a_low_roof_is_refused_politely(make):
    posts = [block(f"Block_{i}", x, 1.25, z) for i, (x, z) in enumerate([(7.5, -2.5), (12.5, -2.5)])]
    beam = ent("Log_1", (10, 3.0, 2.5), (7.5, 1, 1))  # its underside 2.5 up, over open floor
    island, body = make(posts + [beam])
    r = body.run("walk_to", {"x": 10, "z": 2.5})
    assert r.ok and "too low for you to stand under" in r.summary


def test_walk_snags_and_steps_away(make):
    island, body = make([ent("Mesa_1", (3, 5, 0), (2, 10, 2), role="Mesa")])
    island.me = [1.3, BODY_CENTRE_Y, 0]
    island.frozen = True
    stops = []
    island.on_act["Stop"] = lambda d: stops.append(island.now)
    with pytest.raises(Stuck, match="stuck"):
        body._move_once(-5, 0, 0.6)
    assert any(t.startswith("snagged by Mesa_1") for t in reflexes(body))
    assert len(stops) >= 2


def test_move_renews_long_walks(make):
    island, body = make(speed=2.0, attrs={"WalkSpeed": 2})
    snap = body._move_once(20, 0, 0.6)
    assert snap is not None and len([a for a in island.actions("MoveTo")]) >= 2


def test_move_falls_into_the_sea(make):
    island, body = make(bare=True, entities=[ent("Sand", (0, -0.5, 0), (6, 1, 6), role="Ground")])
    with pytest.raises(Stuck, match="fell off the edge"):
        body._move_once(10, 0, 0.6)


def test_move_replans_once_then_reports(make):
    island, body = make()
    island.frozen = True
    with pytest.raises(Stuck, match="stuck"):
        body._move(10, 0)
    assert any("looking for another way" in t for t in reflexes(body))


def test_unstick_cases(make):
    island, body = make()
    assert body._unstick(island.snap()) is False  # nothing to step away from
    island2, body2 = make([ent("Mesa_1", (20, 5, 0), (2, 10, 2), role="Mesa")])
    assert body2._unstick(island2.snap()) is False  # too far away to be what snags us
    # pressed into a block: out through its nearest face
    island3, body3 = make([ent("Mesa_1", (0.5, 5, 0), (4, 10, 4), role="Mesa")])
    assert body3._unstick(island3.snap())
    assert island3.acts[0][1]["position"][0] < 0
    # squeezed between two walls: slip out along the gap
    island4, body4 = make([ent("Mesa_1", (2, 5, 0), (2, 10, 6), role="Mesa"), ent("Mesa_2", (-2, 5, 0), (2, 10, 6),
                                                                                  role="Mesa")])
    assert body4._unstick(island4.snap())
    assert abs(island4.acts[0][1]["position"][0]) < 0.01 and abs(island4.acts[0][1]["position"][2]) > 2


def test_route_steps_out_of_clearance_first(make):
    island, body = make([ent("Mesa_1", (2.2, 5, 0), (2, 10, 10), role="Mesa")])
    snap = island.snap()
    route = body._route(snap, (0, 0), (10, 10))
    assert route[-1] == (10, 10) and len(route) >= 2


def test_route_none_when_closed_off(make):
    ring = [ent(f"Mesa_{i}", pos, size, role="Mesa") for i, (pos, size) in enumerate([
        ((0, 5, 8), (20, 10, 2)), ((0, 5, -8), (20, 10, 2)), ((8, 5, 0), (2, 10, 20)), ((-8, 5, 0), (2, 10, 20))])]
    island, body = make(ring)
    assert body._route(island.snap(), (0, 0), (20, 0)) is None
    assert body._closed_by(island.snap(), goal=(20, 0)).startswith("no way round: you are penned in by Mesa_")


def test_closed_by_explains(make):
    island, body = make([block("Block_1", 10, 1.25, 0), ent("Mesa_1", (30, 5, 0), (10, 10, 10), role="Mesa"),
                         ent("Mesa_2", (-30, 5, 0), (4, 10, 4), role="Mesa")])
    snap = island.snap()
    assert body._closed_by(snap) == "no way round was found"
    assert body._closed_by(snap, goal=(900, 0)) == "no way round: (900.0, 0.0) is not on the floor you stand on"
    assert body._closed_by(snap, goal=(30, 0)) == "no way round: (30.0, 0.0) lies inside Mesa_1"
    assert body._closed_by(snap, goal=(10, 0)) == "no way round: (10.0, 0.0) lies inside Block_1"
    assert body._closed_by(snap, goal=(12, 0)) == "no way round: the way to (12.0, 0.0) is closed off by Block_1"
    assert body._closed_by(snap, goal=(-60, 50)) == "no way round: the way to (-60.0, 50.0) is closed off"


def test_pen_with_no_floor_at_all(make):
    island, body = make([ent("Mesa_1", (0, 5, 0), (12, 10, 12), role="Mesa")])
    island.me = [0, 12.55, 0]  # on top, but its top is all clearance from its own sides? no: that is our floor
    walls = [ent(f"Mesa_{i}", (x, 15, z), (3, 30, 3), role="Mesa") for i, (x, z) in enumerate(
        [(2, 0), (-2, 0), (0, 2), (0, -2), (2, 2), (-2, -2), (2, -2), (-2, 2)], start=2)]
    island2, body2 = make(walls)
    assert body2._pen(island2.snap()) == set()
    assert body2._closed_by(island2.snap()) .startswith("no way round: you are penned in by")


# ---- stepping up and down -----------------------------------------------------------------------------
def test_step_up_onto_a_block_and_walk_on(make):
    island, body = make([ent("Mesa_1", (10, 1.25, 0), (6, 2.5, 6), role="Mesa")])
    r = body.run("walk_to", {"x": 11, "z": 0})
    assert r.ok and "stepped up onto Mesa_1" in r.summary
    assert island.me[1] == pytest.approx(2.5 + BODY_CENTRE_Y)


def test_step_up_failures_are_explained(make):
    for outcome, words in (("StepUpFailed:TooFar", "out of reach"), ("StepUpFailed:NoRoom", "no room for you"),
                           ("StepUpFailed:TooHigh", "more than a block higher"),
                           ("StepUpFailed:NothingToStepOn", "nothing to step on"),
                           ("StepUpFailed:Busy", "already climbing"), ("", "nothing happened")):
        island, body = make([ent("Mesa_1", (10, 1.25, 0), (6, 2.5, 6), role="Mesa")])
        island.results["StepUp"] = outcome
        r = body.run("walk_to", {"x": 10, "z": 0})
        assert not r.ok and words in r.summary


def test_step_up_onto_a_piece_and_wait_out_the_climb(make):
    island, body = make([block("Block_1", 10, 1.25, 0)])
    island.on_act["StepUp"] = lambda d: island.attrs.update(Climbing=True)
    island.after_sleep = lambda i: i.attrs.update(Climbing=False) if i.now > 1003 else None
    r = body.run("walk_to", {"x": 10, "z": 0})
    assert r.ok and r.summary.startswith("stepped up onto Block_1")


def test_cannot_climb_a_mesa_walks_to_its_foot(make):
    island, body = make([ent("Mesa_1", (20, 5, 0), (10, 10, 10), role="Mesa")])
    r = body.run("walk_to", {"x": 20, "z": 0})
    assert r.ok and "is on top of Mesa_1 (height 10.0), which you cannot climb; walked to its foot" in r.summary
    again = body.run("walk_to", {"x": 20, "z": 0})
    assert again.ok and ("already at its foot" in again.summary or "walked to its foot" in again.summary)


def test_inside_a_trunk(make):
    island, body = make([ent("Palm_1", (10, 5, 0), (2, 10, 2), role="Tree")])
    r = body.run("walk_to", {"x": 10, "z": 0})
    assert "inside the trunk of Palm_1" in r.summary


def test_walk_into_a_roofed_room_from_the_step_it_was_roofed_from(make):
    # Run hp-proj8: Godling laid its roof standing on a step block, then walked for the room inside, and was told the
    # room was "on top of" the roof, too high to climb: from up on the step, the floor under the roof was not its own.
    hut = [block(f"Block_{side}{k}", x, (k - 0.5) * 2.5, 0) for side, x in ((1, -2.5), (2, 2.5)) for k in (1, 2, 3)]
    hut += [block(f"Block_3{k}", 0, (k - 0.5) * 2.5, 2.5) for k in (1, 2)]
    roof = ent("Log_1", (0, 8.75, 0), (7.5, 2.5, 2.5))  # across the posts, its underside 7.5 over the room
    step = block("Block_40", 5, 1.25, -2.5)  # outside the walls, beside the doorway's corner
    island, body = make(hut + [roof, step], me=(5, 2.5 + BODY_CENTRE_Y, -2.5))
    r = body.run("walk_to", {"x": 0, "z": 0})
    assert r.ok and "cannot climb" not in r.summary, r.summary
    assert at(island) == pytest.approx((0, 0), abs=1.3) and island.me[1] == pytest.approx(BODY_CENTRE_Y)


def test_hop_down_from_a_platform(make):
    island, body = make([ent("Mesa_1", (0, 1.0, 0), (8, 2, 8), role="Mesa")], me=(0, 2 + BODY_CENTRE_Y, 0))
    island.results["StepDown"] = "StepDownFailed:NoRoom"  # no room right beside: walk to the edge and hop
    r = body.run("walk_to", {"x": 12, "z": 0})
    assert r.ok and r.summary.startswith("hopped down 2.0 from Mesa_1 and walked to")
    assert island.me[1] == pytest.approx(BODY_CENTRE_Y)


def test_step_down_beside(make):
    island, body = make([block("Block_1", 0, 1.25, 0)], me=(0, 2.5 + BODY_CENTRE_Y, 0))
    r = body.run("walk_to", {"x": 12, "z": 0})
    assert r.ok and r.summary.startswith("stepped down 2.5 from Block_1 and walked to")


def test_too_high_to_hop_without_a_ladder(make):
    island, body = make([ent("Mesa_1", (0, 5, 0), (8, 10, 8), role="Mesa")], me=(0, 10 + BODY_CENTRE_Y, 0))
    r = body.run("walk_to", {"x": 20, "z": 0})
    assert not r.ok and "too far to hop down, and no ladder stands up here" in r.summary


def test_down_a_ladder_when_too_high(make):
    ladder = ent("Ladder_1", (4.5, 3.75, 0), (2, 7.5, 0.4), rot=[[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
    island, body = make([ent("Mesa_1", (0, 3.5, 0), (8, 7, 8), role="Mesa"), ladder], me=(2, 7 + BODY_CENTRE_Y, 0))
    island.results["Climb"] = "ClimbStarted:down:2"
    island.on_act["Climb"] = lambda d: setattr(island, "me", [6.5, BODY_CENTRE_Y, 0])
    r = body.run("walk_to", {"x": 20, "z": 0})
    assert r.ok and r.summary.startswith("climbed down Ladder_1 from Mesa_1; walked to")
    island.me = [2, 7 + BODY_CENTRE_Y, 0]
    island.results["Climb"] = "ClimbFailed:NotAtAnEnd"
    r = body.run("walk_to", {"x": 20, "z": 0})
    assert not r.ok and "climbing down Ladder_1 failed" in r.summary


def test_no_edge_to_hop_from(make):
    # a platform ringed by a taller wall: lower ground lies beyond it, but no edge leads there
    island, body = make([ent("Mesa_1", (0, 1.0, 0), (10, 2, 10), role="Mesa")] + [
        ent(f"Mesa_{i}", pos, size, role="Mesa") for i, (pos, size) in enumerate([
            ((0, 5, 5.5), (12, 10, 1)), ((0, 5, -5.5), (12, 10, 1)), ((5.5, 5, 0), (1, 10, 12)),
            ((-5.5, 5, 0), (1, 10, 12))], start=2)], me=(0, 2 + BODY_CENTRE_Y, 0))
    r = body.run("walk_to", {"x": 20, "z": 0})
    assert not r.ok and "no clear edge to hop down from" in r.summary


# ---- picking up and setting down ------------------------------------------------------------------------
def test_pick_up(make):
    island, body = make([block("Block_1", 10, 1.25, 0), ent("Mesa_1", (-30, 5, 0), (5, 10, 5), role="Mesa")])
    assert body.run("pick_up", {"object": "Nothing"}).summary == "there is no movable object called Nothing"
    assert body.run("pick_up", {"object": "Mesa_1"}).summary == "there is no movable object called Mesa_1"
    r = body.run("pick_up", {"object": "Block_1"})
    assert r.ok and r.summary == "picked up Block_1" and island.held == "Block_1"
    assert body.run("pick_up", {"object": "Block_1"}).summary == "already holding Block_1"


def test_pick_up_refusals(make):
    island, body = make([block("Block_1", 10, 1.25, 0, attrs={"Fastened": True}),
                         block("Log_1", 5, 1.25, 5, attrs={"Burning": True})])
    assert "fastened in place" in body.run("pick_up", {"object": "Block_1"}).summary
    assert "is burning" in body.run("pick_up", {"object": "Log_1"}).summary


def test_pick_up_with_full_hands_sets_down_first(make):
    island, body = make([block("Block_1", 10, 1.25, 0), block("Block_2", -3, 1.25, 0)])
    island.held = "Block_2"
    r = body.run("pick_up", {"object": "Block_1"})
    assert r.ok and "(first set Block_2 down" in r.summary and island.held == "Block_1"
    assert any(t.startswith("hands full:") for t in reflexes(body))


def test_pick_up_with_full_hands_and_no_room(make):
    island, body = make([block("Block_1", 10, 1.25, 0), block("Block_2", -3, 1.25, 0)])
    island.held = "Block_2"
    island.results["Place"] = "PlaceFailed:Occupied"
    r = body.run("pick_up", {"object": "Block_1"})
    assert not r.ok and "hands are full: holding Block_2" in r.summary


def test_pick_up_something_else_or_nothing(make):
    island, body = make([block("Block_1", 10, 1.25, 0), block("Block_3", 10.3, 1.25, 0.2)])
    island.on_act["Pickup"] = lambda d: setattr(island, "held", "Block_3")
    r = body.run("pick_up", {"object": "Block_1"})
    assert r.ok and r.summary == "picked up Block_3 instead of Block_1"
    island2, body2 = make([block("Block_1", 10, 1.25, 0)])
    island2.results["Pickup"] = "PickupFailed:OutOfRange"
    r = body2.run("pick_up", {"object": "Block_1"})
    assert not r.ok and r.summary == "pickup of Block_1 failed: PickupFailed:OutOfRange"
    assert len(island2.actions("Pickup")) == 2


def test_pick_up_vanishes(make):
    island, body = make([block("Block_1", 10, 1.25, 0)])
    island.on_act["MoveTo"] = lambda d: island.ents.pop("Block_1", None)
    assert body.run("pick_up", {"object": "Block_1"}).summary == "Block_1 vanished"
    island2, body2 = make([block("Block_1", 10, 1.25, 0), block("Block_2", -3, 1.25, 0)])
    island2.held = "Block_2"
    island2.on_act["Place"] = lambda d: island2.ents.pop("Block_1", None)
    assert body2.run("pick_up", {"object": "Block_1"}).summary.startswith("Block_1 vanished (first set Block_2")


def test_pick_up_out_of_reach_up_high(make):
    island, body = make([ent("Mesa_1", (20, 5, 0), (6, 10, 6), role="Mesa"), block("Block_1", 20, 11.25, 0)])
    r = body.run("pick_up", {"object": "Block_1"})
    assert not r.ok and "no clear spot to reach Block_1 from here (it may be up on something)" == r.summary


def test_pick_up_from_up_high_hops_down(make):
    island, body = make([ent("Mesa_1", (0, 1.0, 0), (6, 2, 6), role="Mesa"), block("Block_1", 12, 1.25, 0)],
                        me=(0, 2 + BODY_CENTRE_Y, 0))
    r = body.run("pick_up", {"object": "Block_1"})
    assert r.ok and island.held == "Block_1"


def test_pick_up_below_too_high(make):
    island, body = make([ent("Mesa_1", (0, 5, 0), (8, 10, 8), role="Mesa"), block("Block_1", 12, 1.25, 0)],
                        me=(0, 10 + BODY_CENTRE_Y, 0))
    r = body.run("pick_up", {"object": "Block_1"})
    assert not r.ok and "is below you, out of reach: you are up here on Mesa_1 (height 10.0)" in r.summary


def test_put_down(make):
    island, body = make([block("Block_1", 3, 1.25, 3), block("Block_2", 12.5, 1.25, 0),
                         ent("Palm_1", (-10, 5, 0), (2, 10, 2), role="Tree"),
                         ent("Mesa_1", (0, 5, -19), (6, 10, 6), role="Mesa")])
    assert body.run("put_down", {"x": 5, "z": 0}).summary == "hands are empty"
    island.held = "Block_1"
    assert body.run("put_down", {"x": 900, "z": 0}).summary == "(900.0, 0.0) is open sea; it would sink and be lost"
    assert body.run("put_down", {"x": -10, "z": 0}).summary == "(-10.0, 0.0) is inside the trunk of Palm_1"
    assert body.run("put_down", {"x": 0, "z": -16}).summary == "(0.0, -15.0) is too close to Mesa_1 to set anything down"
    assert body.run("put_down", {"x": 12.5, "z": 0}).summary == "(12.5, 0.0) is occupied by Block_2"
    r = body.run("put_down", {"x": 6, "z": 0, "turn": 90})
    assert r.ok and r.summary == "put Block_1 down, turned a quarter round at (5.0, 1.37, 0.0)"


def test_put_down_failures(make):
    island, body = make([block("Block_1", 3, 1.25, 3), block("Block_2", 6, 1.25, 6)])
    island.held = "Block_1"
    island.results["Place"] = "PlaceFailed:Occupied"
    assert body.run("put_down", {"x": 5, "z": 0}).summary == "place failed: that space is taken by your own body" \
        or body.run("put_down", {"x": 5, "z": 0}).summary.startswith("place failed: that space is taken by")
    island.results["Place"] = "PlaceFailed:Odd"
    assert body.run("put_down", {"x": 5, "z": 0}).summary == "place failed: PlaceFailed:Odd"
    island.results["Place"] = "PlaceSuccess"
    island.on_act["Place"] = lambda d: island.ents.pop("Block_1", None)
    assert body.run("put_down", {"x": 5, "z": 0}).summary == "put Block_1 down at nowhere (lost)"


def test_put_down_a_ladder_stands_it_up(make):
    island, body = make([ent("Ladder_1", (3, 0.2, 3), (2, 7.5, 0.4)), ent("Mesa_1", (10, 5, 0), (2, 10, 10),
                                                                         role="Mesa")])
    island.held = "Ladder_1"
    r = body.run("put_down", {"x": 8, "z": 0})
    assert r.ok and r.summary.startswith("put Ladder_1 down standing upright")


def test_put_down_out_of_reach_from_up_high(make):
    island, body = make([ent("Mesa_1", (0, 5, 0), (8, 10, 8), role="Mesa"), block("Block_1", 2, 11.25, 2)],
                        me=(0, 10 + BODY_CENTRE_Y, 0))
    island.held = "Block_1"
    r = body.run("put_down", {"x": 12.5, "z": 0})
    assert not r.ok and "below you, out of reach" in r.summary
    islet = [ent("Sand", (0, -0.5, 0), (20, 1, 20), role="Ground"), ent("Islet", (40, -0.5, 0), (3, 1, 3), role="Ground"),
             block("Block_1", 2, 1.25, 2)]
    island2, body2 = make(islet, bare=True)
    island2.held = "Block_1"
    r = body2.run("put_down", {"x": 40, "z": 0})
    assert not r.ok and r.summary == "no clear spot to reach (40.0, 0.0) from here"


def test_place_at(make):
    island, body = make([block("Block_1", 3, 1.25, 3), block("Block_2", 10, 1.25, 0)])
    assert body.run("place_at", {"x": 10, "y": 3.75, "z": 0}).summary == "hands are empty"
    island.held = "Block_1"
    r = body.run("place_at", {"x": 10, "y": 3.82, "z": 0})
    assert r.ok and r.summary.startswith("Block_1 came to rest at (10.00, 3.82, 0.00), on top of Block_2")


def test_place_at_sinks_onto_the_surface(make):
    island, body = make([block("Block_1", 3, 1.25, 3), block("Block_2", 10, 1.25, 0)])
    island.held = "Block_1"
    island.results["Place"] = ["PlaceFailed:Occupied", "PlaceSuccess"]
    r = body.run("place_at", {"x": 10, "y": 3.74, "z": 0, "upright": "yes"})
    assert r.ok and r.summary.endswith(", stood on end")
    assert island.acts[-1][1]["position"][1] == pytest.approx(3.74 + 0.01 + 0.03)


def test_place_at_rejected(make):
    island, body = make([block("Block_1", 3, 1.25, 3), block("Block_2", 7.5, 1.25, 0)])
    island.held = "Block_1"
    island.results["Place"] = "PlaceFailed:Occupied"
    r = body.run("place_at", {"x": 7.5, "y": 1.25, "z": 0})
    assert not r.ok and r.summary == "place rejected: that space is taken by the ground, Block_2"
    island.results["Place"] = "PlaceFailed:Far"
    assert body.run("place_at", {"x": 5, "y": 1.3, "z": 0}).summary == "place rejected: PlaceFailed:Far"


def test_place_a_ladder(make):
    island, body = make([ent("Ladder_1", (3, 0.2, 3), (2, 7.5, 0.4))])
    island.held = "Ladder_1"
    r = body.run("place_at", {"x": 5, "y": 3, "z": 0})
    assert r.ok and r.skill == "place_at" and "standing upright" in r.summary


def test_place_high_by_stepping_up(make):
    island, body = make([block("Block_1", -3, 1.25, 3), block("Block_2", 10, 1.25, 0), block("Block_3", 12.5, 1.25, 0),
                         block("Block_4", 12.5, 3.75, 0), block("Block_5", 12.5, 6.25, 0)])
    island.held = "Block_1"
    r = body.run("place_at", {"x": 12.5, "y": 8.82, "z": 0})
    assert r.ok and "; you stood on Block_2 to reach that high" in r.summary
    assert r.summary.endswith(", and stepped back down") or "stepped" in r.summary


def test_place_high_with_nothing_to_step_on(make):
    island, body = make([block("Block_1", -3, 1.25, 3)])
    island.held = "Block_1"
    r = body.run("place_at", {"x": 10, "y": 12, "z": 0})
    assert not r.ok and "nothing one block high stands near it to step up onto" in r.summary


# ---- stacking ---------------------------------------------------------------------------------------------
def test_stack_on_and_build_tower(make):
    cubes = [block(f"Block_{i}", x, 1.25, z) for i, (x, z) in enumerate([(10, 0), (-5, 5), (-5, -5), (5, -8)], 1)]
    island, body = make(cubes, gifted=True)
    r = body.run("build_tower", {"x": 10, "z": 0, "height": 3})
    assert r.ok and r.facts["height"] == 3 and r.summary == "tower at (10.0, 0.0) stands 3 high"


def test_build_tower_lays_the_base(make):
    island, body = make([block("Block_1", -5, 1.25, 5), block("Block_2", -5, 1.25, -5)], gifted=True)
    r = body.run("build_tower", {"x": 10, "z": 0, "height": 2})
    assert r.ok and r.facts["height"] == 2


def test_build_tower_runs_out(make):
    island, body = make([block("Block_1", -5, 1.25, 5)], gifted=True)
    r = body.run("build_tower", {"x": 10, "z": 0, "height": 2})
    assert not r.ok and r.summary == "ran out of free cubes at height 1"
    _, empty = make(gifted=True)
    assert empty.run("build_tower", {"x": 10, "z": 0, "height": 2}).summary == "no free cubes left to build with"
    assert empty.run("build_tower", {"x": 900, "z": 0, "height": 2}).summary == "(900.0, 0.0) is open sea"


def test_build_tower_stops_on_failures(make):
    island, body = make([block("Block_1", -5, 1.25, 5), block("Block_2", -5, 1.25, -5)], gifted=True)
    island.results["Pickup"] = "PickupFailed:Busy"
    r = body.run("build_tower", {"x": 10, "z": 0, "height": 2})
    assert not r.ok and r.summary.startswith("could not lay the base")
    island2, body2 = make([block("Block_1", 10, 1.25, 0), block("Block_2", -5, 1.25, -5)], gifted=True)
    island2.results["Pickup"] = "PickupFailed:Busy"
    assert body2.run("build_tower", {"x": 10, "z": 0, "height": 2}).summary.startswith("stopped at height 1: pickup")
    island3, body3 = make([block("Block_1", 10, 1.25, 0), block("Block_2", -5, 1.25, -5)], gifted=True)
    island3.results["Place"] = "PlaceFailed:Wobbly"
    r = body3.run("build_tower", {"x": 10, "z": 0, "height": 2})
    assert not r.ok and r.summary == "stopped at height 1: place failed: PlaceFailed:Wobbly"


def test_stack_on_cases(make):
    island, body = make([block("Block_1", 10, 1.25, 0), block("Block_2", -3, 1.25, 0)], gifted=True)
    island.held = "Block_2"
    assert body.run("stack_on", {"object": "Nothing"}).summary == "there is no cube called Nothing"
    island.on_act["Place"] = lambda d: island.ents["Block_2"].update(position=[14, 1.25, 0])
    r = body.run("stack_on", {"object": "Block_1"})
    assert not r.ok and r.summary == "Block_2 fell off and landed at (14.0, 0.0)"
    island.held = "Block_2"
    island.ents["Block_9"] = block("Block_9", 10, 3.75, 0)
    island.on_act["Place"] = lambda d: (island.ents.pop("Block_2"), island.ents.pop("Block_9"))
    r = body.run("stack_on", {"object": "Block_1"})
    assert not r.ok and r.facts["toppled"] and "out of the world; the stack toppled to 1" in r.summary


def test_stack_on_too_tall(make):
    tower = [block(f"Block_{i}", 10, 1.25 + 2.5 * i, 0) for i in range(6)]
    island, body = make(tower + [block("Block_9", -3, 1.25, 0)], gifted=True)
    island.held = "Block_9"
    assert body.run("stack_on", {"object": "Block_0"}).summary == "stack is too tall or crowded to reach (height 6)"


# ---- striking, rubbing, fastening -----------------------------------------------------------------------------
def tools(make, held="Axe_1", target=None, **kw):
    target = target or ent("Palm_1", (6, 5, 0), (2, 10, 2), role="Tree")
    island, body = make([ent(held, (-3, 0.5, 0), (1, 1, 3)), target], **kw)
    island.held = held
    return island, body


@pytest.mark.parametrize("outcome,ok,words", [
    ("StrikeHit:1/3", True, "(1 of 3 strikes so far)"),
    ("StrikeBroke:Stone_4", True, "a stone broke off: Stone_4 lies at somewhere nearby"),
    ("StrikeFelled:Log_1,Log_2", True, "Palm_1 fell; Log_1 lies at somewhere nearby and Log_2"),
    ("StrikeLoosened:Block_1", True, "knocked loose"),
    ("StrikeNoEffect", False, "nothing came of it"),
    ("StrikeCarving:2/4", True, "(2 of 4 strokes so far)"),
    ("StrikeCarved:Spear_1", True, "carved into Spear_1"),
    ("StrikeCaught:Catch_1", True, "the catch, Catch_1"),
    ("StrikeMissed", False, "it darted away"),
    ("StrikeRubWarm:3", True, "grows warm (3 rubs"),
    ("StrikeRubHot:13", True, "hot and smoking"),
    ("StrikeRubCaught:Fire_1", True, "a flame caught: Fire_1"),
    ("StrikeRubBurning", True, "already burning"),
    ("StrikeRubRain", False, "wet through"),
    ("StrikeRubDamp", False, "still damp"),
    ("StrikeYardFull", False, "carry some away first"),
    ("StrikeFailed:NoTool", False, "no tool"),
    ("StrikeFailed:OutOfRange", False, "out of reach"),
    ("StrikeFailed:TooSoon", False, "too recent"),
    ("StrikeFailed:NoTarget", False, "nothing called Palm_1"),
    ("", False, "nothing happened"),
])
def test_strike_outcomes(make, outcome, ok, words):
    island, body = tools(make)
    island.results["Strike"] = outcome
    r = body.run("strike", {"object": "Palm_1"})
    assert r.ok is ok and words in r.summary


def test_strike_refusals(make):
    island, body = tools(make)
    assert body.run("strike", {"object": "Nothing"}).summary == "there is nothing called Nothing"
    island.held = None
    assert body.run("strike", {"object": "Palm_1"}).summary == "your hands hold no tool to strike with"
    island.ents["Block_1"] = block("Block_1", -4, 1.25, 4)
    island.held = "Block_1"
    assert body.run("strike", {"object": "Palm_1"}).summary.endswith("(Block_1 is not one)")


def test_strike_a_fish(make):
    fish = ent("Fish_1", (12, 0.3, 0), (1, 0.5, 2))
    island, body = tools(make, held="Spear_1", target=fish)
    island.results["Strike"] = ["StrikeFailed:OutOfRange", "StrikeCaught:Catch_2"]
    island.ents["Catch_2"] = block("Catch_2", 9, 0.5, 0)
    r = body.run("strike", {"object": "Fish_1"})
    assert r.ok and "lies on the sand at (9.0, 0.0)" in r.summary


def test_strike_a_fish_too_far_out(make):
    sea = [ent("Sand", (0, -0.5, 0), (20, 1, 20), role="Ground"), ent("Spear_1", (-3, 0.5, 0), (1, 1, 3)),
           ent("Fish_1", (40, 0.3, 0), (1, 0.5, 2))]
    island, body = make(sea, bare=True)
    island.held = "Spear_1"
    assert body.run("strike", {"object": "Fish_1"}).summary == "Fish_1 is too far out in the water to reach from the shore"
    island.on_act["Strike"] = None
    sea2 = sea[:2] + [ent("Palm_9", (40, 5, 0), (2, 10, 2), role="Tree")]
    island2, body2 = make(sea2, bare=True)
    island2.held = "Spear_1"
    assert body2.run("strike", {"object": "Palm_9"}).summary.startswith("no clear spot to stand within reach of Palm_9")


def test_strike_a_fish_that_swims_off(make):
    fish = ent("Fish_1", (12, 0.3, 0), (1, 0.5, 2))
    island, body = tools(make, held="Spear_1", target=fish)
    island.on_act["Strike"] = lambda d: island.ents.pop("Fish_1")
    island.results["Strike"] = "StrikeFailed:OutOfRange"
    assert body.run("strike", {"object": "Fish_1"}).summary == "Fish_1 is gone"


def test_carve(make):
    island, body = tools(make, target=ent("Log_1", (6, 0.5, 0), (7.5, 1, 1)))
    assert body.run("carve", {"object": "Palm_1"}).summary == "there is no log called Palm_1"
    island.results["Strike"] = ["StrikeCarving:1/3", "StrikeCarving:2/3", "StrikeCarved:Spear_1"]
    r = body.run("carve", {"object": "Log_1"})
    assert r.ok and r.facts == {"made": "Spear_1"}
    island.results["Strike"] = "StrikeFailed:TooSoon"
    assert not body.run("carve", {"object": "Log_1"}).ok
    island.held = None
    assert body.run("carve", {"object": "Log_1"}).summary == "carving needs the axe in your hands"


def test_rub(make):
    log = ent("Log_3", (6, 0.5, 0), (7.5, 1, 1))
    island, body = tools(make, held="Spear_1", target=log)
    island.ents["Coconut_1"] = ent("Coconut_1", (6, 0.45, 2), (0.9, 0.9, 0.9))  # tinder beside the log
    island.results["Rub"] = ["RubFailed:TooSoon", "StrikeRubWarm:1", "StrikeRubHot:12", "StrikeRubCaught:Fire_1"]
    r = body.run("rub", {"object": "Log_3"})
    assert r.ok and r.summary.startswith("rubbed Spear_1 against Log_3 3 times, and a flame caught: Fire_1")
    for outcome, ok, words in (("StrikeRubBurning", True, "already burning"), ("StrikeRubRain", False, "wet through"),
                               ("StrikeRubDamp", False, "still damp"), ("RubNothing", False, "does nothing"),
                               ("RubFailed:OutOfRange", False, "out of reach"),
                               ("RubFailed:NoTarget", False, "cannot be rubbed"), ("", False, "nothing happened")):
        island.results["Rub"] = outcome
        r = body.run("rub", {"object": "Log_3"})
        assert r.ok is ok and words in r.summary
    island.results["Rub"] = "StrikeRubHot:14"
    assert body.run("rub", {"object": "Log_3"}).summary.endswith(
        "the dry husk of Coconut_1 beside it only smoulders yet; rub on and it may catch")
    island.results["Rub"] = "StrikeRubWarm:2"
    assert body.run("rub", {"object": "Log_3"}).summary.endswith("the wood grew warm, no more")
    # Run hut5: it rubbed 30 times with the husk 5 away. With no tinder beside the log it does not start, and says why.
    island.ents["Coconut_1"]["position"] = [6, 0.45, 6.1]
    rubs = island.actions().count("Rub")
    assert body.run("rub", {"object": "Log_3"}).summary == (
        "you did not start rubbing: no tinder lies within 3 of Log_3 for a spark to catch (the nearest coconut, "
        "Coconut_1, is 5.6 away); set a coconut right beside the log first")
    del island.ents["Coconut_1"]
    assert body.run("rub", {"object": "Log_3"}).summary.endswith(
        "(no coconut lies anywhere near); set a coconut right beside the log first")
    assert island.actions().count("Rub") == rubs
    # Hot wood whose tinder was carried off while it rubbed says so, and where the nearest lies.
    island.ents["Coconut_2"] = ent("Coconut_2", (6, 0.45, 6.1), (0.9, 0.9, 0.9))
    assert body._tinder_by(body._observe(), "Log_3") == (
        "no tinder lay within 3 of Log_3 for a spark to catch: the nearest coconut, Coconut_2, is 5.6 away")
    assert body.run("rub", {"object": "Nothing"}).summary == "there is nothing called Nothing"
    island.held = None
    assert body.run("rub", {"object": "Log_3"}).summary.startswith("your hands are empty")


def test_rub_out_of_reach(make):
    sea = [ent("Sand", (0, -0.5, 0), (20, 1, 20), role="Ground"), ent("Spear_1", (-3, 0.5, 0), (1, 1, 3)),
           ent("Log_3", (40, 0.5, 0), (7.5, 1, 1)), ent("Coconut_1", (40, 0.45, 1.5), (0.9, 0.9, 0.9))]
    island, body = make(sea, bare=True)
    island.held = "Spear_1"
    assert body.run("rub", {"object": "Log_3"}).summary.startswith("no clear spot to stand within reach of Log_3")


def test_fasten(make):
    island, body = make([block("Block_1", 10, 1.25, 0), block("Block_2", 3, 1.25, 3, attrs={"Fastened": True}),
                         block("Block_3", -3, 1.25, -3)])
    assert body.run("fasten", {"object": "Ground"}).summary == "there is no piece called Ground"
    assert body.run("fasten", {"object": "Block_2"}).summary == "Block_2 is already fastened"
    island.held = "Block_3"
    assert body.run("fasten", {"object": "Block_3"}).summary == "Block_3 is in your hands; set it down first"
    island.results["Fasten"] = "FastenSuccess:fixed"
    assert body.run("fasten", {"object": "Block_1"}).summary == "fastened Block_1 in place on what it rests on"
    island.results["Fasten"] = "FastenSuccess:1"
    assert body.run("fasten", {"object": "Block_1"}).summary == "fastened Block_1 to the 1 loose piece it touches"
    island.results["Fasten"] = "FastenSuccess:3"
    assert body.run("fasten", {"object": "Block_1"}).facts["joined"] == 3
    for outcome, words in (("FastenFailed:NothingTouching", "touches nothing"), ("FastenFailed:NotSetDown", "still moving"),
                           ("FastenFailed:OutOfRange", "out of reach"), ("FastenFailed:TooSoon", "still fastening"),
                           ("FastenFailed:NotAPiece", "cannot be fastened"), ("", "nothing happened")):
        island.results["Fasten"] = outcome
        assert words in body.run("fasten", {"object": "Block_1"}).summary


def test_fasten_out_of_reach(make):
    island, body = make([ent("Mesa_1", (20, 5, 0), (6, 10, 6), role="Mesa"), block("Block_1", 20, 11.25, 0)])
    assert body.run("fasten", {"object": "Block_1"}).summary.startswith("no clear spot to reach Block_1")


# ---- climbing and shaking -----------------------------------------------------------------------------------
def test_climb(make):
    ladder = ent("Ladder_1", (10, 3.75, 0), (2, 7.5, 0.4))
    island, body = make([ladder, ent("Mesa_1", (10, 3.5, -3), (6, 7, 4), role="Mesa")])
    assert body.run("climb", {"object": "Mesa_1"}).summary == "there is no ladder called Mesa_1"
    island.results["Climb"] = "ClimbStarted:up:2"
    island.on_act["Climb"] = lambda d: setattr(island, "me", [10, 7 + BODY_CENTRE_Y, -3])
    r = body.run("climb", {"object": "Ladder_1"})
    assert r.ok and r.summary.startswith("climbed up Ladder_1 from height 0.0 to 7.0; you stand on Mesa_1")
    island.on_act.pop("Climb")
    island.me = [10, BODY_CENTRE_Y, 1.9]
    for outcome, words in (("ClimbFailed:NotSetUp", "not standing up"), ("ClimbFailed:TooFar", "not close enough"),
                           ("ClimbFailed:NotAtAnEnd", "neither at the foot"), ("ClimbFailed:NothingAtTop", "reaches nothing"),
                           ("ClimbFailed:NothingAtBottom", "nothing to step onto at the foot"),
                           ("ClimbFailed:NoLadder", "not a ladder"), ("", "nothing happened")):
        island.results["Climb"] = outcome
        assert words in body.run("climb", {"object": "Ladder_1"}).summary
    island.held = "Ladder_1"
    assert "in your hands" in body.run("climb", {"object": "Ladder_1"}).summary


def test_climb_bumping_the_ladder(make):
    ladder = ent("Ladder_1", (10, 3.75, 0), (2, 7.5, 0.4))
    island, body = make([ladder])
    island.after_sleep = lambda i: setattr(i, "frozen", i.me[0] > 7.6)
    island.results["Climb"] = "ClimbFailed:TooFar"
    r = body.run("climb", {"object": "Ladder_1"})
    assert "not close enough" in r.summary or "stuck" in r.summary
    island2, body2 = make([ladder])
    island2.frozen = True
    assert body2.run("climb", {"object": "Ladder_1"}).summary.startswith("stuck")


def test_shake(make):
    island, body = make([ent("Palm_1", (8, 5, 0), (2, 10, 2), role="Tree"), block("Coconut_1", 7, 0.5, 2)])
    assert body.run("shake", {"object": "Coconut_1"}).summary == "there is no standing palm called Coconut_1"
    island.results["Shake"] = "ShakeCoconut:Coconut_1"
    assert body.run("shake", {"object": "Palm_1"}).summary == "shook Palm_1; Coconut_1 fell and lies at (7.0, 2.0)"
    island.results["Shake"] = "ShakeCoconut:Coconut_9"
    assert body.run("shake", {"object": "Palm_1"}).summary.endswith("lies at at its foot")
    for outcome, words in (("ShakeNothing", "no ripe coconut"), ("ShakeFailed:NotAPalm", "not a palm"),
                           ("ShakeFailed:OutOfRange", "out of reach"), ("", "nothing happened")):
        island.results["Shake"] = outcome
        assert words in body.run("shake", {"object": "Palm_1"}).summary


def test_shake_out_of_reach(make):
    sea = [ent("Sand", (0, -0.5, 0), (20, 1, 20), role="Ground"), ent("Palm_1", (40, 5, 0), (2, 10, 2), role="Tree")]
    island, body = make(sea, bare=True)
    assert body.run("shake", {"object": "Palm_1"}).summary.startswith("no clear spot to stand at Palm_1")


# ---- penned in -----------------------------------------------------------------------------------------------------
def pen(extra=()):
    ring = []
    for i, (x, z) in enumerate([(-2.5, -2.5), (0, -2.5), (2.5, -2.5), (-2.5, 0), (2.5, 0), (-2.5, 2.5), (0, 2.5),
                                (2.5, 2.5)], 1):
        ring.append(block(f"Block_{i}", x * 1.6, 1.25, z * 1.6))
    return ring + list(extra)


def test_lift_a_way_out_of_a_pen(make):
    island, body = make(pen())
    island.solid_pieces = True
    r = body.run("walk_to", {"x": 15, "z": 0})
    assert r.ok and abs(island.me[0] - 15) < 0.8
    assert any(t.startswith("penned in: lifted Block_") for t in reflexes(body))


def big_pen():
    """A ring of blocks round a wide floor on a strip of sand: room inside to set something down."""
    ring = [block(f"Block_{i}", x, 1.25, z) for i, (x, z) in enumerate(
        [(x, z) for x in (-5, -2.5, 0, 2.5, 5) for z in (-5, -2.5, 0, 2.5, 5) if abs(x) == 5 or abs(z) == 5], 1)]
    return [ent("Sand", (12.25, -0.5, 0), (35.5, 1, 11), role="Ground")] + ring


def test_lift_with_hands_full_sets_down_inside_first(make):
    island, body = make(big_pen() + [block("Stone_9", 30, 1.25, 0)], bare=True)
    island.solid_pieces = True
    island.held = "Stone_9"
    r = body.run("walk_to", {"x": 15, "z": 0})
    assert r.ok and abs(island.me[0] - 15) < 0.8
    assert any(t.startswith("hands full: put Stone_9 down") for t in reflexes(body))
    assert any(t.startswith("penned in: lifted Block_") for t in reflexes(body))


def test_lift_with_hands_full_rests_on_the_wall(make):
    island, body = make(pen([block("Stone_9", 30, 1.25, 0)]))
    island.solid_pieces = True
    island.held = "Stone_9"
    r = body.run("walk_to", {"x": 15, "z": 0})
    assert any(t.startswith("penned in: lifted Block_") for t in reflexes(body)) or not r.ok


def test_pen_closed_by_unliftable_rock(make):
    rock = [ent(f"Mesa_{i}", (x * 1.6, 5, z * 1.6), (2.5, 10, 2.5), role="Mesa") for i, (x, z) in enumerate(
        [(-2.5, -2.5), (0, -2.5), (2.5, -2.5), (-2.5, 0), (2.5, 0), (-2.5, 2.5), (0, 2.5), (2.5, 2.5)], 1)]
    island, body = make(rock)
    r = body.run("walk_to", {"x": 15, "z": 0})
    assert not r.ok and "no way round: you are penned in by Mesa_" in r.summary


def test_past_and_rest_on(make):
    piece = sk._Box((5, 1.25, 0), (2.5, 2.5, 2.5))
    assert Skills._past((0, 0), [(10, 0)], piece) == pytest.approx((8.5, 0))
    assert Skills._past((0, 0), [(0, 10)], piece) is None
    assert Skills._past((0, 0), [(5, 0)], piece) == (5, 0)  # ends inside it
    island, body = make([block("Block_1", 3, 1.25, 0), block("Block_2", 0, 1.25, 3)])
    island.held = "Block_2"
    island.results["Place"] = "PlaceFailed:Occupied"
    from godling.world import Entity
    assert body._rest_on(island.snap(), Entity(block("Block_2", 0, 6, 0)), [Entity(block("Block_1", 3, 1.25, 0))]) is None


# ---- steps for reaching high (ADR-019, the benchmark house's roof) ------------------------------------------------------
def test_walk_from_one_step_onto_another_as_high(make):
    # From up on one block to the top of another as high, with ground between: walking straight there walked off the
    # first and stayed on the ground beside the second. Down first, then up onto it.
    island, body = make([block("Block_A", 0, 1.25, 0), block("Block_B", 5, 1.25, 5)], me=(0, 2.5 + BODY_CENTRE_Y, 0))
    r = body.run("walk_to", {"x": 5, "z": 5})
    assert r.ok and island.me[1] == pytest.approx(2.5 + BODY_CENTRE_Y), r.summary
    assert "stepped up onto Block_B" in r.summary


def test_stepping_up_to_reach_a_roof_after_snags(make):
    # The roof's last log, over the room's far cell, from the east, beside a column of clutter (hp-roofcheck): the
    # body snagged stepping up onto the nearest block, and then tried one whose edge, but not its middle, was in reach
    # of the roof, and gave up. A step must reach from where the body stands on it, and a failed step-up is tried
    # again, and the next steps after it.
    from test_house_recovery import benchmark
    house = [p for p in benchmark() if p["name"] != "Log_E1"]
    clutter = [block(f"Block_c{i}", 7.5, 1.25, z) for i, z in enumerate((-2.5, 0, 2.5, 5, 7.5))]
    clutter += [block(f"Block_n{i}", x, 1.25, 7.5) for i, x in enumerate((-5, -2.5, 0, 2.5, 5))]
    island, body = make([*house, *clutter, ent("Log_room", (15, 1.25, 12), (7.5, 2.5, 2.5))], me=(12, BODY_CENTRE_Y, 14))
    island.held = "Log_room"
    island.results["StepUp"] = ["StepUpFailed:NoRoom", "StepUpFailed:NoRoom", "StepUpStarted"]  # two snags, then up
    r = body.run("place_at", {"x": 5, "y": 8.75, "z": 2.5, "turn": 0})
    assert r.ok and "came to rest at (5.00, 8.75, 2.50)" in r.summary, r.summary
    assert "Block_c4" not in r.summary  # its middle is 6.7 from the roof's middle: too far to set it from
