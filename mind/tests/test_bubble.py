import threading

import pytest

from godling import bubble as bubble_module
from godling.bubble import FEELINGS, SYSTEM, THINGS, Bubble
from godling.world import WorldError
from helpers import block, ground, snap


class FakeWorld:
    def __init__(self, snapshot, fail=False):
        self.snapshot = snapshot
        self.fail = fail
        self.acts = []

    def observe(self):
        return self.snapshot

    def act(self, action, data=None):
        if self.fail:
            raise WorldError("no")
        self.acts.append((action, data))


class FakeLLM:
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def quick_json(self, system, user, purpose):
        self.prompts.append(user)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def body(**attrs):
    clock = {"TimeOfDay": 6.5, "Rain": attrs.pop("rain", 0)}
    held = attrs.pop("held", False)
    entities = [ground()] + ([block("Log_1", 0, 2.55 + 4, 0)] if held else [])
    return snap(entities, attrs=attrs, clock=clock)


def test_system_prompt_lists_everything():
    assert all(k in SYSTEM for k in THINGS) and all(f in SYSTEM for f in FEELINGS)


def test_reading_only_when_something_is_new():
    world = FakeWorld(body(Hunger=50, Health=80))
    llm = FakeLLM({"thing": "Fish", "feeling": " hungry "})
    logs = []
    b = Bubble(world, llm, log=lambda **kw: logs.append(kw))
    assert b.read() is None and llm.prompts == []
    b.thought("I could catch a fish")
    b.does("walk to the sea")
    b.happens("x" * 300)
    assert b.read() == ("fish", "hungry")
    assert world.acts == [("Think", {"thing": "fish", "feeling": "hungry"})]
    prompt = llm.prompts[0]
    assert "I could catch a fish" in prompt and "walk to the sea" in prompt and "50% fed, health 80" in prompt
    assert "hands empty" in prompt and "the time is 06:30" in prompt and ("x" * 200 + "\n") in prompt
    assert logs[-1] == {"kind": "bubble", "ok": True, "thing": "fish", "feeling": "hungry"}
    assert b.read() is None  # nothing new since


def test_reading_describes_weather_and_load():
    world = FakeWorld(body(held=True, rain=0.5, InRain=True, Wet=70, Cold=True))
    llm = FakeLLM({"thing": "rain", "feeling": "cold"})
    b = Bubble(world, llm)
    b.thought("wet")
    b.read()
    prompt = llm.prompts[0]
    assert "holding Log_1" in prompt and "out in the rain" in prompt and "soaked" in prompt and "cold" in prompt
    assert "waiting for its next plan" in prompt and "What just happened" not in prompt
    world2 = FakeWorld(snap([ground()], clock={"Rain": 0.5}))
    b2 = Bubble(world2, llm)
    b2.thought("dry")
    b2.read()
    assert "under a roof" in llm.prompts[-1] and "the time is" not in llm.prompts[-1]


def test_unknown_names_and_world_errors():
    logs = []
    b = Bubble(FakeWorld(body()), FakeLLM({"thing": "spaceship", "feeling": "happy"}), log=lambda **kw: logs.append(kw))
    b.thought("?")
    assert b.read() is None and logs[-1]["ok"] is False
    b2 = Bubble(FakeWorld(body(), fail=True), FakeLLM({"thing": "fish", "feeling": "happy"}))
    b2.thought("?")
    assert b2.read() is None and b2.shown is None


def test_thread_runs_readings_and_survives_errors(monkeypatch):
    logs = []
    done = threading.Event()
    b = Bubble(FakeWorld(body()), FakeLLM(ValueError("model down")), every=0.01,
               log=lambda **kw: (logs.append(kw), done.set()))
    b.thought("x")
    assert b.start() is b
    assert done.wait(5)
    b.stop()
    b.thread.join(5)
    assert not b.thread.is_alive()
    assert "model down" in logs[0]["message"]
    assert bubble_module.EVERY == 15
    Bubble(FakeWorld(body()), FakeLLM({})).log(kind="x")  # the default log takes anything


def test_a_dead_body_makes_no_bubble_calls_and_reads_the_news_after_rebirth():
    world = FakeWorld(body(Dead=True, Deaths=1, Health=0))
    llm = FakeLLM({"thing": "shelter", "feeling": "determined"})
    bubble = Bubble(world, llm)
    bubble.thought("I need a roof before the cold night")
    assert bubble.read() is None and bubble.read() is None
    assert llm.prompts == [] and world.acts == []
    world.snapshot = body(Deaths=1, Health=100, Hunger=50)
    assert bubble.read() == ("shelter", "determined")
    assert "I need a roof" in llm.prompts[0]
    assert bubble.read() is None and len(llm.prompts) == 1


@pytest.mark.parametrize("still_dead", [False, True])
def test_a_bubble_answer_from_the_previous_life_is_not_shown(still_dead):
    world = FakeWorld(body(Deaths=2))
    llm = FakeLLM({"thing": "fish", "feeling": "hungry"})
    bubble = Bubble(world, llm)
    bubble.thought("Catch a fish")
    complete = llm.quick_json

    def died_while_reading(*args, **kwargs):
        reply = complete(*args, **kwargs)
        world.snapshot = body(Deaths=3, Dead=still_dead)
        return reply

    llm.quick_json = died_while_reading
    assert bubble.read() is None
    assert world.acts == [] and bubble.shown is None
    world.snapshot = body(Deaths=3)
    llm.quick_json = complete
    assert bubble.read() == ("fish", "hungry"), "the stale answer must leave the news pending"
