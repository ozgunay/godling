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
from godling.learned import SkillLibrary
from godling.memory import NativeMemory
from godling.skills import Interrupted, Skills
from godling.world import BODY_CENTRE_Y
from helpers import block, ent, ground
from island import FakeTime, Island


def roof(name, x, z):
    """A log lying high over the ground, its underside three blocks up: room under it to stand (the stand-in island
    has no physics, so it needs no walls to rest on)."""
    return ent(name, (x, 8.75, z), (7.5, 2.5, 2.5))


def weather(island, real=None, room=()):
    """The world's side of it (main.lua WEATHER), enough for the reflex: something held overhead, its underside from the
    crown up to ten above it (5.15 to 15.15 over the ground), shelters the body and keeps the rain off; inside a house
    (standing in one of the `room` cells, under its roof) it is warm. Out in the rain and soaked it is cold, and so it is
    at night but in a house; a fire within 7 warms. `real` names the roofs the world itself counts; by default every
    piece lying high enough. The island's clock carries Night (main.lua reckons it from the hour)."""
    def feel(i):
        x, z = i.me[0], i.me[2]
        under = any(5 < e["position"][1] - e["size"][1] / 2 < 15.15 and abs(x - e["position"][0]) <= e["size"][0] / 2
                    and abs(z - e["position"][2]) <= e["size"][2] / 2 and (real is None or e["name"] in real)
                    for e in i.ents.values())
        clock = i.clock or {}
        raining, night = clock.get("Rain", 0) >= 0.3, bool(clock.get("Night"))
        house = under and (round(x / 2.5), round(z / 2.5)) in set(room)
        i.attrs["Sheltered"] = "roof" if under else ""
        i.attrs["InHouse"] = house
        i.attrs["InRain"] = raining and not under
        i.attrs["ByFire"] = any(n.startswith("Fire_") and abs(x - e["position"][0]) <= 7 and abs(z - e["position"][2]) <= 7
                                for n, e in i.ents.items())
        i.attrs["Cold"] = not house and (night or (raining and not under and i.attrs.get("Wet", 0) >= 50))
    island.after_sleep = feel
    feel(island)
    return feel


@pytest.fixture
def make(monkeypatch):
    def build(entities=(), health=30, wet=80, rain=0.8, real=None, night=False, room=(), library=None):
        island = Island([ground()] + list(entities), clock={"Rain": rain, "Night": night},
                        attrs={"Health": health, "Hunger": 60, "Wet": wet})
        monkeypatch.setattr(sk, "time", FakeTime(island))
        logs, told, news = [], [], []
        body = Skills(island, log=lambda **k: logs.append(k), library=library)

        def on_reflex(text, salience, pending=True):
            told.append((text, salience))
            news.append(pending)
        body.on_reflex = on_reflex
        body.logs, body.told, body.news = logs, told, news
        island.feel = weather(island, real, room)
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
    # 76-CDE6: the body did nothing, so the step goes on (no agenda dropped for news it can do nothing about); the
    # mind hears it as news.
    island, body = make()
    result = body.run("walk_to", {"x": 5, "z": 0})
    told = ("You are cold and soaked in the rain, your health down to 30 of 100, with nothing over you at (0.0, 0.0), "
            "and your body knows no roof within 80 units to shelter under: out here the cold takes the rest of your "
            "health in about 12 minutes.")
    assert result.ok and near(island, 5.0, 0.0)
    assert body.told == [(told, 4)] and body.news == [True]
    # Said once: the steps go on, and it is not said again while the danger lasts.
    assert body.run("walk_to", {"x": 5, "z": 0}).ok and body.run("wait", {"seconds": 3}).ok
    island.attrs["Health"] = 12
    assert body.run("walk_to", {"x": 6, "z": 0}).ok and len(body.told) == 1
    # A roof built meanwhile is one it knows, at its next look (76-CLEAN15: every few seconds).
    island.ents["Log_R"] = roof("Log_R", 20, 0)
    island.now += sk.SHELTER_LOOK_AGAIN
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
    assert body.run("walk_to", {"x": 5, "z": 0}).ok and near(island, 5.0, 0.0)
    assert len(body.told) == 1 and "knows no roof within 80 units" in body.told[0][0]


def test_where_the_world_finds_no_shelter_it_tries_the_next_roof(make):
    # The log at (10, 0) looks like a roof, but the world does not count it (say it is still settling): the body
    # walks there, finds the rain on it still, and goes on to the next roof, once each.
    island, body = make([roof("Log_A", 10, 0), roof("Log_B", -30, 0)], real={"Log_B"})
    result = body.run("walk_to", {"x": 5, "z": 0})
    assert result.summary.startswith("interrupted: You were cold") and "28 units away, and stands under it at (-27." in result.summary
    assert near(island, -27.5, 0.0)
    shelter = [l for l in body.logs if l.get("reflex") == "shelter"]
    assert shelter[-1]["tried"] == ["Log_A"]
    assert result.summary.endswith("Under Log_A the rain still reached it.")  # 76-SWEEP3: the mind hears which
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
    # 76-CDE1: the plan being thought was for the body out in the rain: the loop is told, so it drops that plan.
    assert rg.watch_while_thinking(future, island, attention, body) == "sheltered"
    assert near(island, 17.5, 0.0)
    assert [e["text"][:40] for e in attention.take_events()] == ["You were cold and soaked in the rain, yo"]


def test_body_height_and_constants():
    assert sk.COLD_HEALTH == 35 and sk.WARM_AGAIN == 50 and sk.COLD_AGAIN == 10 and BODY_CENTRE_Y


# ---- the review of PR #76 (decisions/ADR-028, "Review fixes") ----------------------------------------------------
def test_a_roof_it_could_not_get_under_is_tried_again_later(make):
    # 76-AB3: the walk did not get there (snagged: a stray log in the doorway, say). That is not the rain reaching it
    # under the roof, and the roof is not given up for the whole spell: it is tried again a minute later.
    island, body = make([roof("Log_R", 20, 0)])
    island.frozen = True  # the body goes nowhere
    assert body.run("jump", {}).ok  # it did not move: the step goes on
    (text, _), = body.told
    assert "could not get to Log_R" in text and "rain still reached" not in text
    island.frozen = False
    island.now += sk.SHELTER_RETRY + 1
    result = body.run("jump", {})
    assert result.summary.startswith("interrupted: You were cold") and near(island, 17.5, 0.0)


def test_a_roof_too_low_to_stand_under_is_no_shelter(make):
    # 76-CLEAN2: the reflex and walk_to keep the same headroom, so the reflex never sends the body to a roof walk_to
    # will not take it under (a log 5.07 up).
    island, body = make([ent("Log_Low", (12.5, 5.07 + 1.25, 0), (7.5, 2.5, 2.5))])
    assert body.run("jump", {}).ok
    assert "knows no roof within 80 units" in body.told[0][0]


def test_a_roof_higher_than_the_world_counts_is_no_shelter(make):
    island, body = make([ent("Log_High", (12.5, 16 + 1.25, 0), (7.5, 2.5, 2.5))])
    assert body.run("jump", {}).ok and "knows no roof" in body.told[0][0]


def test_a_body_bug_in_the_shelter_walk_never_escapes_run(make):
    # 76-CDE9: run() never raises for a body bug; the reflex's walk is no exception.
    island, body = make([roof("Log_R", 20, 0)])

    def broken(x, z):
        raise KeyError("a bug")
    body.skill_walk_to = broken
    assert body.run("jump", {}).ok
    assert any(l["kind"] == "error" and l["message"].startswith("shelter crashed: KeyError") for l in body.logs)


def test_when_the_roof_over_it_is_knocked_away_it_shelters_again(make):
    # 76-CDE3: the roof left the body, not the mind: it does not wait for its health to fall another ten.
    island, body = make([roof("Log_A", 20, 0), roof("Log_B", 30, 0)])
    assert not body.run("walk_to", {"x": -10, "z": 0}).ok and near(island, 17.5, 0.0)
    island.ents.pop("Log_A")  # a meteor
    island.feel(island)
    island.attrs["Health"] = 29
    assert body.run("jump", {}).summary.startswith("interrupted: You were cold") and near(island, 27.5, 0.0)


def test_drying_under_the_roof_does_not_end_the_danger(make):
    # 76-CDE2: by day, a body that dried below 50 under the roof is not yet cold in the rain; that is not the end of
    # the danger, so COLD_AGAIN still holds when it is soaked again.
    island, body = make([roof("Log_R", 20, 0)])
    assert not body.run("walk_to", {"x": -10, "z": 0}).ok
    island.attrs["Wet"] = 40  # dried under the roof while the mind thought
    assert body.run("walk_to", {"x": 0, "z": 0}).ok  # out for a coconut, in the rain, not yet cold
    assert body.run("jump", {}).ok
    island.attrs["Wet"] = 60
    island.feel(island)
    assert body.run("jump", {}).ok and len(body.told) == 1  # soaked again at 30: not until it is worse
    # The rain stops and it stands in the open, not cold: the danger is over.
    island.clock["Rain"], island.attrs["Wet"] = 0, 0
    island.feel(island)
    assert body.run("jump", {}).ok and body._chill is None


def test_by_a_fire_on_a_dry_night_it_stays_by_the_fire(make):
    # 76-CDE4: a fire halves the cold as a roof does; walking from one to the other gains nothing.
    island, body = make([roof("Log_R", 20, 0), ent("Fire_1", (2, 0.5, 0), (1, 1, 1))], rain=0, wet=0, night=True)
    assert island.attrs["Cold"] and island.attrs["ByFire"]
    assert body.run("jump", {}).ok and near(island, 0.0, 0.0) and body.told == []


def test_a_walk_to_a_roof_named_by_helpers_is_let_go(make, tmp_path):
    # 76-CDE11: the step's helpers are worked out before it is judged a walk to a roof.
    island, body = make([roof("Log_R", 20, 0), roof("Log_Near", 5, 0)], library=SkillLibrary(tmp_path / "s.json"))
    step = {"x": {"x": {"pos": "Log_R"}}, "z": {"z": {"pos": "Log_R"}}}
    assert body.run("walk_to", step).ok and near(island, 20.0, 0.0) and body.told == []


def test_a_walk_back_to_a_roof_where_the_rain_reached_it_is_not_let_go(make):
    # 76-SWEEP3: Log_A kept nothing off; a walk back under it is no walk to shelter.
    island, body = make([roof("Log_A", 10, 0), roof("Log_B", -30, 0)], real={"Log_B"})
    assert not body.run("walk_to", {"x": 5, "z": 0}).ok and near(island, -27.5, 0.0)
    assert body.run("walk_to", {"x": 0, "z": 5}).ok  # the mind takes it out again
    island.attrs["Health"] = 18
    assert not body.run("walk_to", {"x": 10, "z": 0}).ok and near(island, -27.5, 0.0)


def learned(tmp_path, name, steps):
    library = SkillLibrary(tmp_path / "skills.json")
    library.define({"name": name, "params": [], "does": "x", "steps": steps})
    return library


def test_a_learned_walk_home_is_let_go(make, tmp_path):
    # 76-SWEEP1: as the live run's mend_at_home (81 runs): a learned skill is checked step by step, so its walk under
    # the house's roof goes ahead, as a walk_to does, and the wait under it is covered.
    library = learned(tmp_path, "mend_at_home", [{"skill": "walk_to", "args": {"x": 20, "z": 0}},
                                                 {"skill": "wait", "args": {"seconds": 5}}])
    island, body = make([roof("Log_R", 20, 0), roof("Log_Near", 5, 0)], library=library)
    assert body.run("mend_at_home", {}).ok and near(island, 20.0, 0.0) and body.told == []


def test_between_a_learned_skills_steps_the_body_is_checked(make, tmp_path):
    # 76-SWEEP2: health crosses 35 during a learned skill of walks (the live run's upright_log_at ran up to 120 s).
    steps = [{"skill": "walk_to", "args": {"x": x, "z": 0}} for x in (-10, 10, -10, 10, -10)]
    island, body = make([roof("Log_R", 30, 20)], health=35.5, library=learned(tmp_path, "pace", steps))

    def chilling(i):
        i.feel(i)
        if not i.attrs["Sheltered"]:
            i.attrs["Health"] -= 0.05
    island.after_sleep = chilling
    result = body.run("pace", {})
    assert not result.ok and "interrupted: You were cold" in result.summary and island.attrs["Sheltered"] == "roof"


def test_once_it_has_said_there_is_no_roof_it_looks_again_only_now_and_then(make):
    # 76-CLEAN15: not the whole search four times a second for the rest of the spell.
    island, body = make()
    looks = []
    search = body._shelters
    body._shelters = lambda *a: looks.append(1) or search(*a)
    assert body.run("jump", {}).ok and len(looks) == 1
    assert body.run("wait", {"seconds": 3}).ok and len(looks) == 1
    island.now += sk.SHELTER_LOOK_AGAIN
    assert body.run("jump", {}).ok and len(looks) == 2


def house(roof_on=True):
    """A house two by two at cells (0..1, 0..1), walls three blocks high round it, corners too, the doorway south at
    (0, -1), and its roof (as test_house_lost.house)."""
    pieces = [block(f"Block_w{dx + 1}{dz + 1}{k}", dx * 2.5, (k - 0.5) * 2.5, dz * 2.5)
              for dx in range(-1, 3) for dz in range(-1, 3) for k in (1, 2, 3)
              if not (0 <= dx <= 1 and 0 <= dz <= 1) and (dx, dz) != (0, -1)]
    if roof_on:
        logs = [("Log_S", 0, -1), ("Log_N", 0, 2), ("Log_W0", -1, 0), ("Log_E0", 2, 0), ("Log_W1", -1, 1), ("Log_E1", 2, 1)]
        pieces += [ent(name, (dx * 2.5, 8.75, dz * 2.5), (7.5, 2.5, 2.5)) for name, dx, dz in logs]
    return pieces


ROOM = [(0, 0), (1, 0), (0, 1), (1, 1)]


def test_at_night_it_goes_into_the_house_it_knows_not_its_doorway(make):
    # 76-CDE14: with real walls, a doorway roofed by its lintel is the nearest roof, one cell from the only warm place.
    # A house it has stood in comes first when it is not much further.
    island, body = make(house(), health=80, rain=0, wet=0, night=True, room=ROOM)
    island.solid_pieces = True
    assert body.run("walk_to", {"x": 0, "z": 0}).ok and island.attrs["InHouse"]  # it has been inside
    assert body.run("walk_to", {"x": 0, "z": -12}).ok and island.attrs["Cold"]
    island.attrs["Health"] = 30
    result = body.run("jump", {})
    assert result.summary.startswith("interrupted: You were cold") and "into a house it knows" in result.summary
    assert island.attrs["InHouse"] and not island.attrs["Cold"]


def loop_in_the_rain(monkeypatch, tmp_path, agenda):
    """run_godling's loops (test_run_godling.loop_setup) with the body cold and hurt in the rain, a roof 20 off, and
    the mind's first plan held back until the body has taken shelter (or two seconds have passed)."""
    from test_run_godling import loop_setup, project
    plans = [{"thought": "out in the rain", "agenda": [project("hop", ("jump", {}))]}]
    island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path, plans, calls=3, agenda=agenda, no_narration=True)
    island.ents["Log_R"] = roof("Log_R", 20, 0)
    island.clock = {"Rain": 0.8}
    island.attrs.update(Health=30, Hunger=60, Wet=80)
    island.feel = weather(island)
    skills, attention, llm = loop_args[4], loop_args[1], loop_args[3].llm
    sheltered, script = threading.Event(), llm.complete_json

    def on_reflex(text, salience, pending=True):
        attention.notice(text, salience, pending=pending)
        sheltered.set()
    skills.on_reflex = on_reflex

    def slow(system, user, purpose="decide", on_reasoning=None):
        if purpose == "decide":
            sheltered.wait(2)
        return script(system, user, purpose, on_reasoning)
    llm.complete_json = slow
    return island, loop_args, logs


@pytest.mark.parametrize("agenda", [True, False])
def test_a_plan_thought_for_the_body_out_in_the_rain_is_dropped(monkeypatch, tmp_path, agenda):
    # 76-CDE1 (the agenda loop) and 76-CDE10 (the one-project loop, whose thinking had no reflexes at all).
    island, loop_args, logs = loop_in_the_rain(monkeypatch, tmp_path, agenda)
    with pytest.raises(KeyboardInterrupt):
        (rg.agenda_loop if agenda else rg.single_loop)(*loop_args)
    kinds = [l["kind"] for l in logs]
    shelter = next(i for i, l in enumerate(logs) if l["kind"] == "reflex" and l.get("ok"))
    dropped = next(i for i, l in enumerate(logs) if l["kind"] == "plan_discarded"
                   and l["reason"] == "the body took shelter by itself")
    assert shelter < dropped < kinds.index("decision"), "the plan made for the body in the rain was never adopted"


def test_it_does_not_sleep_while_the_cold_is_killing_it(make):
    # 76-CDE10: the hourly sleep is a long model call on the body's thread, with no reflexes meanwhile.
    island, body = make()
    slept = []
    mind = types.SimpleNamespace(sleep=lambda snap: slept.append(snap))
    memory = types.SimpleNamespace(state={"last_sleep": 0})
    args = types.SimpleNamespace(sleep_minutes=60)
    rg.maybe_sleep(mind, memory, island.snap(), args, lambda **k: None, body)
    assert slept == []
    island.attrs["Health"] = 80
    rg.maybe_sleep(mind, memory, island.snap(), args, lambda **k: None, body)
    assert len(slept) == 1
