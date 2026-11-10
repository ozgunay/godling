import pytest

from godling import skills as sk
from godling.skills import Interrupted, Result, Skills, Stuck, _Box, _flag, _orientation, _quarter, _rotation
from godling.world import BODY_CENTRE_Y, WorldError
from helpers import block, ent, ground, snap
from island import FakeTime, Island


@pytest.fixture
def make(monkeypatch):
    def build(entities=(), gifted=False, library=None, protected=(), **kw):
        island = Island([ground()] + list(entities), **kw)
        monkeypatch.setattr(sk, "time", FakeTime(island))
        logs = []
        body = Skills(island, protected=lambda: set(protected), log=lambda **k: logs.append(k), gifted=gifted,
                      library=library)
        body.logs = logs
        return island, body
    return build


def texts(body, kind=None):
    return [l.get("text") or l.get("message") or l.get("summary") for l in body.logs if kind is None or l["kind"] == kind]


# ---- small helpers -----------------------------------------------------------------------
def test_small_helpers():
    assert _quarter(90) == 90 and _quarter("270") == 90 and _quarter(180) == 0 and _quarter("x") == 0
    assert _quarter(None) == 0
    assert _flag(True) and _flag(" Yes ") and _flag("1") and not _flag("no") and not _flag(None)
    assert _rotation(90, True) == {"yaw": 90, "pitch": 0, "roll": 90}
    assert _orientation(90, True) == ", stood on end, turned a quarter round" and _orientation(0, False) == ""
    box = _Box((0, 1, 0), (2, 2, 4))
    assert box.footprint_contains(1, 2) and not box.footprint_contains(1.5, 0) and box.footprint_contains(1.5, 0, 0.5)


def test_weather_here():
    dry = snap([ground()])
    assert sk._weather_here(dry) == ""
    rain = {"Rain": 0.5}
    assert sk._weather_here(snap([ground()], clock=rain, attrs={"Sheltered": "enclosed", "Cold": True})) == (
        "; here you are under a roof with walls round you, out of the rain, but still cold: a roof only halves it")
    assert sk._weather_here(snap([ground()], attrs={"Sheltered": "roof", "InHouse": True})) == (
        "; here you are inside a house, out of the rain and the cold")
    assert sk._weather_here(snap([ground()], clock=rain, attrs={"Sheltered": "roof"})).endswith("out of the rain")
    assert sk._weather_here(snap([ground()], clock=rain, attrs={"Sheltered": "roof", "Cold": True})).endswith(
        "still cold: a roof only halves it")
    assert sk._weather_here(snap([ground()], clock=rain)).endswith("nothing over your head")
    assert sk._weather_here(snap([ground()], attrs={"Cold": True})) == "; here you have nothing over your head, and cold"


# ---- dispatch ------------------------------------------------------------------------------
def test_run_unknown_and_gifted(make):
    island, body = make()
    assert body.run("fly", {}).summary == "unknown skill 'fly'"
    assert body.run("stack_on", {"object": "Block_1"}).summary == "unknown skill 'stack_on'"
    _, gifted = make(gifted=True)
    assert gifted.run("stack_on", {"object": "Block_1"}).summary == "need to be holding a cube"


def test_run_turns_errors_into_failures(make):
    island, body = make()
    island.errors["Jump"] = WorldError("gone")
    assert body.run("jump", {}).summary == "world error: gone"
    assert body.run("wait", {"seconds": "soon"}).summary.startswith("bad arguments")
    island.errors["Jump"] = RuntimeError("boom")
    assert body.run("jump", {}).summary == "jump failed unexpectedly (boom)"
    assert any("crashed" in t for t in texts(body, "error"))
    island.errors["Jump"] = Stuck("stuck here")
    assert body.run("jump", {}).summary == "stuck here"
    island.errors["Jump"] = Interrupted("a visitor")
    assert body.run("jump", {}).summary == "interrupted: a visitor"
    assert body.busy == set() and body._depth == 0
    skill_logs = [l for l in body.logs if l["kind"] == "skill"]
    assert skill_logs[-1]["ok"] is False and "seconds" in skill_logs[-1]


@pytest.mark.parametrize("skill, args", [("put_down", {"x": 5, "z": 0}),
                                         ("place_at", {"x": 5, "y": 1.25, "z": 0})])
def test_accepted_placement_survives_interrupted_settling(make, skill, args):
    island, body = make([block("Block_1", 3, 1.25, 3)])
    island.held = "Block_1"
    settled = []
    body.on_placed = settled.append

    def interrupt(snap):
        if island.actions("Place"):
            raise Interrupted("a stone falls nearby")
    body.on_step = interrupt
    result = body.run(skill, args)
    assert not result.ok and "interrupted: a stone falls nearby" in result.summary
    assert island.held is None and island.ents["Block_1"]["position"][0] == 5
    assert body.take_placed() == ["Block_1"] and settled == []


@pytest.mark.parametrize("skill, args", [("put_down", {"x": 5, "z": 0}),
                                         ("place_at", {"x": 5, "y": 1.25, "z": 0})])
def test_learned_skill_publishes_placement_before_its_next_step(make, tmp_path, skill, args):
    from godling.learned import SkillLibrary
    library = SkillLibrary(tmp_path / "skills.json")
    library.define({"name": "build_then_reuse", "params": [], "steps": [
        {"skill": "pick_up", "args": {"object": "Block_1"}},
        {"skill": skill, "args": args},
        {"skill": "pick_up", "args": {"object": "Block_1"}}]})
    island, body = make([block("Block_1", 3, 1.25, 3)], library=library)
    built = set()

    def keep(snap):
        assert snap.held() is None
        built.update(body.placed)
    body.on_placed = keep
    body.kept_in = lambda name: "a completed build" if name in built else None
    result = body.run("build_then_reuse", {})
    assert not result.ok and "which you built; release that first" in result.summary
    assert built == {"Block_1"} and body.take_placed() == ["Block_1"]
    assert island.held is None and island.ents["Block_1"]["position"][0] == 5


def test_gifted_stack_publishes_its_installed_piece(make):
    island, body = make([block("Block_1", 3, 1.25, 3), block("Block_2", 5, 1.25, 0)], gifted=True)
    island.held = "Block_1"
    snapshots = []
    body.on_placed = snapshots.append
    result = body.run("stack_on", {"object": "Block_2"})
    assert result.ok and snapshots[-1].entities["Block_1"].pos[1] > 3.5
    assert body.take_placed() == ["Block_1"]


def test_hands_full_staging_does_not_publish_a_build(make):
    island, body = make([block("Block_1", 3, 1.25, 3), block("Block_2", 5, 1.25, 0)])
    island.held = "Block_1"
    settled = []
    body.on_placed = settled.append
    result = body.run("pick_up", {"object": "Block_2"})
    assert result.ok and island.held == "Block_2", result.summary
    assert settled == [] and body.take_placed() == []


class FakeLibrary:
    def __init__(self, behaviour=None):
        self.skills = {"mine": {}}
        self.behaviour = behaviour

    def resolve_helpers(self, args, skills, skill=None):
        if args.get("bad"):
            raise ValueError("no such helper")
        return {k: (v["value"] if isinstance(v, dict) else v) for k, v in args.items()}

    def execute(self, skills, name, args):
        if self.behaviour:
            raise self.behaviour
        return Result(True, name, f"ran with {args}")


def test_run_with_a_library(make):
    island, body = make(library=FakeLibrary())
    assert body.run("mine", {"a": {"value": 3}}).summary == "ran with {'a': 3}"
    assert body.run("mine", {"bad": {"x": 1}}).summary == "could not work out arguments (no such helper)"
    for err, summary in ((Stuck("stuck"), "stuck"), (Interrupted("bell"), "interrupted: bell"),
                         (KeyError("k"), "mine broke while running ('k'); fix or forget it")):
        _, b = make(library=FakeLibrary(err))
        assert b.run("mine", {}).summary == summary


# ---- reflexes ------------------------------------------------------------------------------
def test_glance_turns_towards_news(make):
    island, body = make(attrs={"ViewForwardX": 1.0, "ViewForwardZ": 0.0})
    events = [{"text": "behind", "at": [-10, 0], "sky": "Meteor", "sky_id": 2}, {"text": "ahead", "at": [10, 0.5]},
              {"text": "here", "at": [0.2, 0]}]
    body.next_glance = lambda: events.pop(0) if events else None
    body.glance()
    assert island.acts[-1] == ("Face", {"position": [-10, BODY_CENTRE_Y, 0]})
    assert body.logs[-1]["turned"] and body.logs[-1]["degrees"] == 180 and body.logs[-1]["sky"] == "Meteor"
    body.glance()  # straight ahead: already in view
    assert body.logs[-1]["turned"] is False and len(island.actions("Face")) == 1
    body.glance()  # right where we stand
    assert body.logs[-1]["turned"] is False
    body.glance()  # nothing to look at
    assert len(body.logs) == 3
    blind, b2 = make()  # no facing known: always turns
    b2.next_glance = lambda: {"text": "x", "at": [5, 5]}
    b2.glance()
    assert b2.logs[-1]["turned"] and b2.logs[-1]["degrees"] == 0
    blind.fail_observe = 1
    b2.glance()
    assert texts(b2, "error") == ["glance: observe failed"]


def test_steady_braces_through_a_quake(make):
    island, body = make(clock={"QuakePhase": "rumble", "Quake": 0.05, "QuakeId": 3})
    body.steady()  # startled: it looks around first
    assert island.acts == []
    island.clock["Quake"] = 0.5
    seen = []

    def on_step(s):
        seen.append(s)
        raise Interrupted("news")

    body.on_step = on_step
    island.after_sleep = lambda i: i.attrs.update(Bracing=False) if i.now > 1004 else None
    body.steady()
    assert island.actions() == ["Brace"] and seen
    assert body.logs[0]["kind"] == "brace" and body.logs[0]["ok"] and body.logs[0]["sky_id"] == 3
    assert body.logs[-1]["text"].startswith("held on through the earthquake")
    island.clock = {}
    body.steady()  # still ground: nothing to do
    island.clock = {"QuakePhase": "shaking", "Quake": 0.8}
    island.attrs["Bracing"] = True
    body.steady()  # already braced
    assert island.actions() == ["Brace"]
    island.attrs["Bracing"] = False
    island.results["Brace"] = "BraceFailed"
    body.steady()
    assert body.logs[-1]["ok"] is False and "sky_id" not in body.logs[-1]
    island.fail_observe = 1
    body.steady()
    assert texts(body, "error") == ["brace: observe failed"]


def test_steady_gives_up_after_the_longest_quake(make):
    island, body = make(clock={"QuakePhase": "shaking", "Quake": 0.9})
    body.steady()
    assert 1000 + sk.BRACE_LONGEST <= island.now <= 1000 + sk.BRACE_LONGEST + 1


# ---- the simple skills -------------------------------------------------------------------------
def test_jump_say_wait(make):
    island, body = make()
    assert body.run("jump", {}).summary.startswith("jumped; highest point 2.5")
    assert body.run("say", {"text": 42}).summary == 'said "42."' and island.said == ["42."]
    assert island.acts[-1] == ("Talk", {})
    island.errors["Talk"] = WorldError("old world")
    assert body.run("say", {"text": "hi"}).ok
    wait = body.run("wait", {"seconds": 0})
    assert wait.summary == "waited 0s" and island.now >= 1001
    island.clock = {"Rain": 0.6}
    assert body.run("wait", {"seconds": 99}).summary.endswith("out in the rain with nothing over your head")


def test_eat_and_cook(make):
    island, body = make([block("Catch_1", 3, 1.25, 0)])
    assert body.run("eat", {}).summary == "your hands are empty"
    assert body.run("cook", {}).summary == "your hands are empty"
    island.held = "Catch_1"
    island.results["Eat"] = "EatSuccess:85"
    assert body.run("eat", {}).summary == "ate Catch_1; you are now 85% fed"
    for outcome, words in (("EatFailed:NotFood", "not something you can eat"), ("EatFailed:EmptyHands", "empty"),
                           ("", "nothing happened"), ("Odd", "Odd")):
        island.results["Eat"] = outcome
        assert words in body.run("eat", {}).summary
    island.results["Cook"] = "CookSuccess:Catch_1"
    assert body.run("cook", {}).facts == {"cooked": "Catch_1"}
    for outcome, words in (("CookFailed:NotFish", "not a fish"), ("CookFailed:Cooked", "cooked already"),
                           ("CookFailed:NoFire", "no fire"), ("", "nothing happened")):
        island.results["Cook"] = outcome
        assert words in body.run("cook", {}).summary


def test_draw(make):
    island, body = make()
    island.results["Draw"] = "DrawSuccess:Mark_1"
    r = body.run("draw", {"x": 5, "z": 0})
    assert r.ok and r.facts == {"mark": "Mark_1"} and island.me[0] == pytest.approx(5, abs=0.7)
    island.frozen = True
    assert body.run("draw", {"x": 9, "z": 0}).ok  # the line is drawn even if the walk snags
    island.frozen = False
    for outcome, words in (("DrawFailed:NotSand", "not open sand"), ("DrawFailed:Length", "from 0.5 to 20 long"),
                           ("DrawFailed:BeachFull", "no more lines"), ("DrawFailed:BadTarget", "not a place"),
                           ("", "nothing happened")):
        island.results["Draw"] = outcome
        assert words in body.run("draw", {"x": 1, "z": 1}).summary


def test_throw(make):
    island, body = make([block("Stone_1", 3, 1.25, 0)])
    assert body.run("throw", {"x": 1, "y": 1, "z": 0}).summary == "hands are empty"
    island.held = "Stone_1"
    island.results["Throw"] = "ThrowFailed:Weak"
    assert body.run("throw", {"x": 1, "y": 1, "z": 0}).summary == "throw failed: ThrowFailed:Weak"
    island.results["Throw"] = "ThrowSuccess"
    r = body.run("throw", {"x": 1, "y": 1, "z": 0, "speed": 8})
    assert r.ok and "Stone_1 came to rest at (3.00, 1.25, 0.00), on the ground" == r.summary
    island.held = "Stone_1"
    island.on_act["Throw"] = lambda d: island.ents.pop("Stone_1")
    r = body.run("throw", {"x": 1, "y": 1, "z": 0})
    assert r.facts["lost"] and "flew into the sea" in r.summary


def test_throw_follows_a_rolling_stone(make):
    island, body = make([block("Stone_1", 3, 1.25, 0)])
    island.held = "Stone_1"
    rolls = iter(range(100))
    island.after_sleep = lambda i: i.ents["Stone_1"].update(position=[3 + next(rolls) * 0.1, 1.25, 0]) \
        if i.held is None else None
    r = body.run("throw", {"x": 1, "y": 0, "z": 0})
    assert r.ok and island.now >= 1000 + 40 * 0.15 - 1e-6  # followed it the whole while


def test_eat_requires_hands(make):
    island, body = make()
    assert not body.run("eat", {}).ok
