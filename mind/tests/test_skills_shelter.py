"""ADR-028: a cold, hurt body goes to shelter by reflex.

Live run 2026-11-08/09: with its house broken, the mind "mended" out in the rain while every step said so, and died of
the cold at 06:54; at 07:31, with its health at 27, it chose not to walk 25 units to the one roofed cell it knew, and
died at 07:42. As the body braces through a quake by itself (Skills.steady), it now takes shelter by itself when it is
chilled with nothing over it and its health is low, and tells the mind.
"""
from concurrent.futures import Future
import threading
import types

import pytest

import run_godling as rg
from godling import skills as sk
from godling.attention import Attention
from godling.memory import NativeMemory
from godling.skills import Interrupted, Skills
from godling.world import BODY_CENTRE_Y
from helpers import ent, ground
from island import FakeTime, Island


def roof(name, x, z):
    """A log lying high over the ground, its underside three blocks up: room under it to stand (the stand-in island
    has no physics, so it needs no walls to rest on)."""
    return ent(name, (x, 8.75, z), (7.5, 2.5, 2.5))


def weather(island, real=None):
    """The world's side of it (main.lua WEATHER), enough for the reflex: under a roof the body is sheltered and out of
    the rain; out in the rain and soaked it is cold. `real` names the roofs the world itself counts; by default every
    piece lying high enough."""
    def feel(i):
        x, z = i.me[0], i.me[2]
        under = any(e["position"][1] - e["size"][1] / 2 > 5 and abs(x - e["position"][0]) <= e["size"][0] / 2
                    and abs(z - e["position"][2]) <= e["size"][2] / 2 and (real is None or e["name"] in real)
                    for e in i.ents.values())
        raining = (i.clock or {}).get("Rain", 0) >= 0.3
        i.attrs["Sheltered"] = "roof" if under else ""
        i.attrs["InRain"] = raining and not under
        i.attrs["Cold"] = raining and not under and i.attrs.get("Wet", 0) >= 50
    island.after_sleep = feel
    feel(island)
    return feel


@pytest.fixture
def make(monkeypatch):
    def build(entities=(), health=30, wet=80, rain=0.8, real=None):
        island = Island([ground()] + list(entities), clock={"Rain": rain},
                        attrs={"Health": health, "Hunger": 60, "Wet": wet})
        monkeypatch.setattr(sk, "time", FakeTime(island))
        logs, told = [], []
        body = Skills(island, log=lambda **k: logs.append(k))
        body.on_reflex = lambda text, salience: told.append((text, salience))
        body.logs, body.told = logs, told
        island.feel = weather(island, real)
        return island, body
    return build


def at(island):
    return round(island.me[0], 1), round(island.me[2], 1)


def near(island, x, z):
    """Where the body stands, near enough: a walk stops within 0.6 of where it was sent (Skills._move)."""
    return abs(island.me[0] - x) <= 0.6 and abs(island.me[2] - z) <= 0.6


def test_a_cold_hurt_body_takes_shelter_before_it_carries_on(make):
    # Health 30, soaked in the rain with nothing overhead: the step it was given waits; the body goes to the nearest
    # roof it knows (the log at (20, 0) covers 16.25 to 23.75: its nearest cell is (17.5, 0)) and the mind hears why.
    island, body = make([roof("Log_R", 20, 0)])
    result = body.run("walk_to", {"x": -10, "z": 0})
    assert not result.ok
    told = ("You were cold and soaked in the rain, your health down to 30 of 100, with nothing over you at (0.0, 0.0): "
            "out there the cold would take the rest of it in about 12 minutes. Your body went by itself to the nearest "
            f"roof it knows, 18 units away, and stands under it at ({island.me[0]:.1f}, 0.0); here you are under a roof, "
            "out of the rain.")
    assert result.summary == f"interrupted: {told}"
    assert near(island, 17.5, 0.0) and island.attrs["Sheltered"] == "roof"
    assert body.told == [(told, 4)]
    reflex = [l for l in body.logs if l["kind"] == "reflex" and l.get("reflex") == "shelter"]
    assert len(reflex) == 1 and reflex[0]["ok"] and reflex[0]["to"] == [17.5, 0.0] and reflex[0]["health"] == 30
    # Sheltered, it carries on with what it is given.
    assert body.run("walk_to", {"x": 17.5, "z": 2}).ok


@pytest.mark.parametrize("case", ["healthy enough", "under a roof", "dry weather", "dead", "no health", "drowning"])
def test_no_reflex_when_it_is_not_needed(make, case):
    island, body = make([roof("Log_R", 20, 0)], health=40 if case == "healthy enough" else 30,
                        rain=0 if case == "dry weather" else 0.8, wet=0 if case == "dry weather" else 80)
    if case == "under a roof":
        island.ents["Log_R0"] = roof("Log_R0", 0, 0)
        island.feel(island)
    island.attrs.update({"dead": {"Dead": True}, "drowning": {"Drowning": True}}.get(case, {}))
    if case == "no health":
        island.attrs.pop("Health")
    assert body.run("walk_to", {"x": 5, "z": 0}).ok
    assert near(island, 5.0, 0.0) and body.told == []


def test_with_no_shelter_known_it_says_so_once(make):
    island, body = make()
    result = body.run("walk_to", {"x": 5, "z": 0})
    told = ("You are cold and soaked in the rain, your health down to 30 of 100, with nothing over you at (0.0, 0.0), "
            "and your body knows no roof within 80 units to shelter under: out here the cold takes the rest of your "
            "health in about 12 minutes.")
    assert result.summary == f"interrupted: {told}" and near(island, 0.0, 0.0)
    assert body.told == [(told, 4)]
    # Said once: the steps go on, and it is not said again while the danger lasts.
    assert body.run("walk_to", {"x": 5, "z": 0}).ok and body.run("wait", {"seconds": 3}).ok
    island.attrs["Health"] = 12
    assert body.run("walk_to", {"x": 6, "z": 0}).ok and len(body.told) == 1
    # A roof built meanwhile is one it knows.
    island.ents["Log_R"] = roof("Log_R", 20, 0)
    assert body.run("walk_to", {"x": 0, "z": 0}).summary.startswith("interrupted: You were cold")
    assert near(island, 17.5, 0.0)


def test_once_sheltered_it_lets_the_mind_go_out_until_it_is_worse(make):
    # The mind may send it out again (for food, say): the reflex pulls it in again only when its health has fallen
    # another ten, so it cannot loop between the mind's plan and the roof.
    island, body = make([roof("Log_R", 20, 0)])
    assert not body.run("walk_to", {"x": -10, "z": 0}).ok and near(island, 17.5, 0.0)
    assert body.run("walk_to", {"x": 0, "z": 0}).ok  # under the roof: on with the plan
    island.attrs["Health"] = 25
    assert body.run("walk_to", {"x": 2, "z": 0}).ok and near(island, 2.0, 0.0)
    island.attrs["Health"] = 20
    assert not body.run("walk_to", {"x": 4, "z": 0}).ok and near(island, 17.5, 0.0)
    assert len(body.told) == 2
    # Mended to half, the danger is over; the next time is a new one.
    island.attrs["Health"] = 50
    assert body.run("walk_to", {"x": 0, "z": 0}).ok
    island.attrs["Health"] = 33
    assert not body.run("walk_to", {"x": 4, "z": 0}).ok and len(body.told) == 3


def test_a_roof_it_remembers_that_is_gone_is_not_a_shelter(make):
    # It stood under its house's roof and felt it keep the rain off; then the house broke. The body does not walk back
    # to where the roof was (the mind thought "the roof over the room still keeps me dry" and died there).
    island, body = make([roof("Log_House", -20, 0)], health=80)
    assert body.run("walk_to", {"x": -20, "z": 0}).ok and island.attrs["Sheltered"] == "roof"
    assert body.run("wait", {"seconds": 2}).ok
    island.ents.pop("Log_House")
    assert body.run("walk_to", {"x": 0, "z": 0}).ok
    island.attrs["Health"] = 30
    result = body.run("walk_to", {"x": 5, "z": 0})
    assert "knows no roof within 80 units" in result.summary and near(island, 0.0, 0.0)


def test_where_the_world_finds_no_shelter_it_tries_the_next_roof(make):
    # The log at (10, 0) looks like a roof, but the world does not count it (say it is still settling): the body
    # walks there, finds the rain on it still, and goes on to the next roof, once each.
    island, body = make([roof("Log_A", 10, 0), roof("Log_B", -30, 0)], real={"Log_B"})
    result = body.run("walk_to", {"x": 5, "z": 0})
    assert result.summary.startswith("interrupted: You were cold") and "28 units away, and stands under it at (-27." in result.summary
    assert near(island, -27.5, 0.0)
    shelter = [l for l in body.logs if l.get("reflex") == "shelter"]
    assert shelter[-1]["tried"] == ["Log_A"]
    # Out again and worse: it does not try the roof the world did not count a second time.
    assert body.run("walk_to", {"x": 9, "z": 0}).ok
    island.attrs["Health"] = 18
    assert not body.run("walk_to", {"x": 9, "z": 3}).ok and near(island, -27.5, 0.0)


def test_it_takes_shelter_while_it_waits(make):
    # Run live 06:36: "mend_at_home" waited out in the rain, three times thirty seconds, in a house that had no roof.
    island, body = make([roof("Log_R", 20, 0)], health=36)
    island.after_sleep = lambda i: (i.feel(i), i.attrs.update(Health=i.attrs["Health"] - 0.05))
    result = body.run("wait", {"seconds": 30})
    assert result.summary.startswith("interrupted: You were cold and soaked in the rain, your health down to 35 of 100")
    assert near(island, 17.5, 0.0)


def test_a_walk_to_a_roof_is_let_go(make):
    island, body = make([roof("Log_R", 20, 0), roof("Log_Near", 5, 0)])
    assert body.run("walk_to", {"x": 20, "z": 0}).ok and near(island, 20.0, 0.0) and body.told == []


def test_eating_and_speaking_are_let_go(make):
    # Over at once and going nowhere, they cost it nothing in the cold; fed at least half, it mends.
    island, body = make([roof("Log_R", 20, 0)])
    assert body.run("eat", {}).summary == "your hands are empty"  # the eating itself answered, not the reflex
    assert body.run("say", {"text": "so cold"}).ok and near(island, 0.0, 0.0) and body.told == []


def test_news_on_the_way_stops_it(make):
    island, body = make([roof("Log_R", 20, 0)])
    seen = []

    def on_step(snap):
        seen.append(snap)
        if len(seen) == 2:
            raise Interrupted("A dark shadow spreads on the ground at (10, 0)")
    body.on_step = on_step
    result = body.run("walk_to", {"x": -10, "z": 0})
    assert result.summary.startswith("interrupted: You were cold and soaked in the rain, your health down to 30 of 100")
    assert result.summary.endswith("Your body set off for the roof at (17.5, 0.0), 18 units away, but stopped: A dark "
                                   "shadow spreads on the ground at (10, 0).")
    assert not near(island, 17.5, 0.0)


def test_observe_failures_are_logged(make):
    island, body = make([roof("Log_R", 20, 0)])
    island.fail_observe = 1
    assert body.take_shelter() is None
    assert [l["message"] for l in body.logs if l["kind"] == "error"] == ["shelter: observe failed"]


def test_it_takes_shelter_while_the_mind_thinks(make, monkeypatch, tmp_path):
    island, body = make([roof("Log_R", 20, 0)])
    monkeypatch.setattr(rg, "time", types.SimpleNamespace(time=rg.time.time, sleep=lambda s: None))
    attention = Attention(NativeMemory(tmp_path / "mem"))
    body.on_reflex = attention.notice
    future = Future()
    threading.Timer(0.05, lambda: future.set_result(1)).start()
    rg.watch_while_thinking(future, island, attention, body)
    assert near(island, 17.5, 0.0)
    assert [e["text"][:40] for e in attention.take_events()] == ["You were cold and soaked in the rain, yo"]


def test_body_height_and_constants():
    assert sk.COLD_HEALTH == 35 and sk.WARM_AGAIN == 50 and sk.COLD_AGAIN == 10 and BODY_CENTRE_Y
