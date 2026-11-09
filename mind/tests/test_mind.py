import re

import pytest

from godling import mind as mind_module
from godling import skills as sk
from godling.discovery import Discovery
from godling.learned import SkillLibrary
from godling.memory import NativeMemory
from godling.memory2 import BrainMemory
from godling.mind import Mind, _how_it_feels, island_map
from godling.skills import Result, Skills
from godling.world import BODY_CENTRE_Y
from helpers import block, ent, ground, snap
from island import FakeTime, Island


class FakeLLM:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def complete_json(self, system, user, purpose="decide", on_reasoning=None):
        self.calls.append({"system": system, "user": user, "purpose": purpose})
        if on_reasoning:
            on_reasoning("thinking...")
        return self.replies.pop(0)


def scene():
    return [ground(attrs={"Surface": "Sand"}), ent("Grass_1", (40, 0, 0), (30, 1, 30), role="Ground"),
            ent("Quarry", (-40, 3, 40), (10, 6, 10), role="Quarry"),
            ent("Raft", (40, 1, -40), (6, 2, 4), role="Wreck"),
            ent("Peak_1", (-60, 10, -60), (20, 20, 20), role="Mesa", attrs={"Feature": "Peak"}),
            ent("Palm_2", (10, 5, 10), (2, 10, 2), role="Tree"), ent("Palm_10", (12, 5, 12), (2, 10, 2), role="Tree"),
            ent("Tree_x", (-12, 5, 12), (2, 10, 2), role="Tree"),
            block("Block_1", 5, 1.25, 0), block("Block_2", 5, 3.75, 0), block("Block_3", -5, 1.25, -5),
            block("Log_4", 3, 0.5, 3), ent("Fire_1", (2, 0.5, -2), (1, 1, 1)), ent("Fish_1", (0, 0.2, 20), (1, 0.5, 2)),
            ent("Mark_2", (1, 0, 1), (1, 0.1, 1), attrs={"Stroke": "0,0,1,1"}),
            ent("Mark_1", (1, 0, 1), (1, 0.1, 1), attrs={"Stroke": "2,2,3,3"})]


@pytest.fixture
def world(monkeypatch, tmp_path):
    island = Island(scene())
    monkeypatch.setattr(sk, "time", FakeTime(island))
    library = SkillLibrary(tmp_path / "skills.json")
    body = Skills(island, library=library)
    return island, body, library


def make_mind(world, tmp_path, llm, memory=None, **kw):
    island, body, library = world
    logs = []
    mem = memory or NativeMemory(tmp_path / "mem")
    mind = Mind(llm, mem, "I am a castaway.", body, library, log=lambda **k: logs.append(k), **kw)
    mind.logs = logs
    return mind


def test_island_map_and_feelings():
    s = snap(scene())
    m = island_map(s, half=60, step=20)
    rows = m.splitlines()
    assert rows[-1].strip().startswith("|") and "x from -60" in rows[-1]
    assert "Q" in m and "R" in m and "^" in m and "." in m and "," in m
    d = Discovery()
    assert set("".join(r[6:] for r in island_map(s, d, half=20, step=10).splitlines()[:-1])) == {"?"}
    assert "~" in island_map(snap([ent("Isle", (0, -0.5, 0), (5, 1, 5), role="Ground")]), half=20, step=10)
    assert _how_it_feels(snap([ground()])) == ""
    feels = _how_it_feels(snap([ground()], clock={"Rain": 0.5, "WindX": 0.8},
                               attrs={"InRain": True, "Wet": 80, "Cold": True, "Sheltered": "enclosed"}))
    assert feels == ("A storm wind is blowing. It is raining, and you are out in it: it slows your walking. You are soaked "
                     "through (80%). You stand under a roof with walls around you, which halves the cold; this is not a "
                     "house, which would keep it off. You are cold, and it is wearing your health down.")
    assert "You are wet (20%)" in _how_it_feels(snap([ground()], attrs={"Wet": 20, "Sheltered": "roof"}))
    # ADR-019: only a house keeps the cold off; a fire close by halves it, or warms by day.
    assert _how_it_feels(snap([ground()], attrs={"Sheltered": "roof", "InHouse": True, "ByFire": True})) == (
        "You are inside a house: warm and dry, mending twice as fast while fed. A fire close by warms you.")
    assert _how_it_feels(snap([ground()], attrs={"Cold": True, "ByFire": True})) == (
        "A fire close by halves the cold. You are cold, and it is wearing your health down.")
    assert _how_it_feels(snap([ground()], attrs={"Drowning": True})) == (
        "You are in the sea and cannot climb out: the water is drowning you. If it drowns you, you die, and come back "
        "to life at the start spot in the middle of the island.")


def test_prompts(world, tmp_path):
    island, body, library = world
    library.define({"name": "fetch", "params": ["object"], "steps": [{"skill": "pick_up", "args": {"object": "$object"}}]})
    mind = make_mind(world, tmp_path, FakeLLM())
    s = island.snap()
    system = mind.system_prompt(s)
    assert "I am a castaway." in system and "- fetch(object) [unproven" in system
    assert "- Palms (2, about 10 tall): Palm_2 (10, 10), Palm_10 (12, 12)" in system
    assert "- Trees (1, about 10 tall): Tree_x (-12, 12)" in system
    assert "- Peak: centre" in system and "- Quarry: centre" in system
    # ADR-019: what a house is, what keeps the cold off, and how fire is made, as plain facts of the world.
    assert "A house is a room at least two cells by\ntwo" in system and "walls all round it, corners too" in system
    assert "a roof over all of it, the walls and the doorway too" in system
    assert "Inside your house a fed body mends twice as fast." in system
    assert "hold your spear and rub it hard against a log lying on the ground" in system
    assert "a coconut's dry husk" in system
    assert "a log laid against a burning one takes the fire as it burns out" in system
    assert "Rain puts out a fire in the open, but not one under a roof." in system
    # a meteor's stone: what it is like, never what it is for (METEORIC IRON)
    assert ("It lands glowing hot and cools over about a day; cooled, it is dark, heavy and hard, and looks like "
            "metal") in " ".join(system.split())
    assert not re.search(r"\b(iron|harpoon|blade|edge)\b", system, re.IGNORECASE), "never what it is for"
    assert '"agenda"' in system
    one = make_mind(world, tmp_path, FakeLLM(), agenda=False)
    flat = one.system_prompt(s)
    assert '"project"' in flat and "Plan one project" in flat


def test_situation_lists_what_matters(world, tmp_path):
    island, body, library = world
    mem = BrainMemory(tmp_path / "brain")
    mem.note("Blocks fall in quakes", about="stacking")
    mem.store_experience("saw Block_3 move", entities=["Block_3"])
    mem.add_structure("tower", ["Block_1", "Block_2"], (5, 0), {"Block_1": (5, 1.25, 0), "Block_2": (5, 3.75, 0)})
    mem.state["digest"] = "I washed up here."
    mem.set_intentions(["build a hut"])
    island.attrs.update(Hunger=50, Health=90, Deaths=1, DiedOf="HungerAndCold", Wet=20)
    island.clock = {"TimeOfDay": 6.5}
    island.held = "Log_4"
    mind = make_mind(world, tmp_path, FakeLLM(), memory=mem)
    mind.notes = ["a note"]
    mind.failures = ["a: x", "b: y"]
    mind.think_s = 30
    text = mind.situation(island.snap(), [{"text": "A thing happened", "entities": ["Block_3"]}],
                          [{"agent_name": "Ann", "content": "hello"}], doing=[{"goal": "a wall"}])
    assert "It is 06:30, dawn." in text and "holding Log_4" in text
    assert ("You are 50% fed, with health 90 of 100; you have died 1 time, the last of hunger and the cold "
            "together.") in text
    assert "You are wet (20%)." in text and "Fires burning: Fire_1 (2.0, -2.0)." in text
    assert "Fish swimming in the shallows nearest you: Fish_1 (0.0, 20.0)." in text
    assert "Lines you drew in the sand (2, oldest first): (2, 2)-(3, 3); (0, 0)-(1, 1)." in text
    # A kept tower is shown as built, layer by layer, not as a stack to take from.
    assert "Stacks: none." in text and "tower (2 pieces): layer 1: (5.0, 0.0); layer 2: (5.0, 0.0)" in text
    assert "Block_3 (-5.0, 1.25, -5.0)" in text and "nobody else is here" in text
    assert "Right now your body is carrying out this agenda: 1) a wall." in text
    assert "You take about 30s to think up a plan." in text and "Notes: a note" in text
    assert "You noticed: A thing happened" in text and "You heard: Ann: hello" in text
    assert "Recent failures: a: x | b: y." in text
    assert "- stacking: Blocks fall in quakes" in text and "Memories that may matter" in text
    assert "Your story so far:\nI washed up here." in text and "Your intentions for later: build a hut" in text
    for hour, part in ((2, "night"), (9, "morning"), (12, "midday"), (15, "afternoon"), (19, "evening")):
        island.clock = {"TimeOfDay": hour}
        assert f", {part}." in mind.situation(island.snap(), [], [])


def test_situation_does_not_describe_drowning_as_hunger(world, tmp_path):
    island, _, _ = world
    island.attrs.update(Hunger=50, Health=100, Deaths=1, DiedOf="Sea", Drowned=1)
    mind = make_mind(world, tmp_path, FakeLLM())
    text = mind.situation(island.snap(), [], [])
    assert "you have died 1 time, the last of drowning in the sea" in text  # its cause, never hunger by default
    assert "hunger" not in text.split("you have died")[1].split(".")[0]


def test_situation_with_discovery_and_many_loose_things(world, tmp_path):
    island, body, library = world
    for i in range(20):
        island.ents[f"Stone_{i}"] = block(f"Stone_{i}", -15 + 3 * (i % 10), 1.25, -12 - 6 * (i // 10))
    island.ents["Fish_9"] = ent("Fish_9", (200, 0.2, 200), (1, 0.5, 2))
    d = Discovery()
    d.see(island.snap())
    d.seen["Block_9"] = (1, 1.25, 1)  # seen once, gone from sight since
    mind = make_mind(world, tmp_path, FakeLLM(), discovery=d)
    island.held = "Log_4"
    text = mind.situation(island.snap(), [], [], doing=None)
    assert "more further away" in text and "Block_9 (1.0, 1.25, 1.0) (last seen there)" in text
    marks = [f"Mark_{i}" for i in range(3, 46)]
    for i, name in enumerate(marks, 3):
        island.ents[name] = ent(name, (0, 0, 0), (1, 0.1, 1), attrs={"Stroke": f"{i},0,{i},1"})
    assert "(and 5 older)" in mind.situation(island.snap(), [], [])


def test_prepare_think_adopt(world, tmp_path):
    island, body, library = world
    reply = {"thought": "I will build.", "needs": "3 logs",
             "agenda": [{"intention": "stack", "goal": "a tower", "why": "to be seen",
                         "steps": [{"skill": "pick_up", "args": {"object": "Block_3"}}, {"skill": "fly", "args": {}},
                                   {"skill": "jump", "args": "bad"}, "junk"]}, "junk"],
             "remember": [{"about": "stacking", "text": "towers wobble", "importance": "5"}, {"text": ""}, "x"],
             "learn": [{"name": "hop", "steps": [{"skill": "jump"}]}, {"name": "bad name", "steps": []}, "junk"],
             "forget": ["hop_old"], "release": ["old"],
             "keep": [{"name": "pair", "cubes": ["Block_1", "Block_2", "Block_3", "Fish_1", "Nope"]},
                      {"name": "", "cubes": []}]}
    llm = FakeLLM(reply)
    mem = NativeMemory(tmp_path / "mem")
    mem.add_structure("old", ["Block_3"], (0, 0), {"Block_3": (0, 0, 0)})
    library.define({"name": "hop_old", "steps": [{"skill": "jump"}]})
    mind = make_mind(world, tmp_path, llm, memory=mem)
    mind.notes = ["delivered"]
    s = island.snap()
    prepared = mind.prepare(s, [], [], doing=[{"goal": "first"}, {"goal": "second"}])
    assert prepared["assumes"] == "first -> second" and mind.notes == []
    chunks = []
    thought = mind.think(prepared, on_reasoning=chunks.append)
    assert chunks == ["thinking..."] and thought["reply"] is reply
    decision = mind.adopt(thought, s)
    assert decision["thought"] == "I will build." and decision["needs"] == "3 logs" and decision["learned"] == ["hop"]
    assert decision["projects"] == [{"intention": "stack", "goal": "a tower", "why": "to be seen",
                                     "steps": [{"skill": "pick_up", "args": {"object": "Block_3"}}]}]
    assert any("'bad name' was rejected" in n for n in mind.notes)
    assert "hop_old" not in library.skills and "old" not in mem.state["structures"]
    assert mem.state["structures"]["pair"]["cubes"] == ["Block_1", "Block_2", "Block_3"]  # Fish_1 is too far off
    assert mem.episodes[-1]["text"] == "towers wobble" and mem.episodes[-1]["importance"] == 5
    assert mind.think_s == thought["seconds"]
    assert mind.logs[-1]["kind"] == "decision"
    thought2 = {**thought, "seconds": thought["seconds"] + 10}
    mind.adopt({**thought2, "reply": {}}, s)
    assert mind.think_s == pytest.approx(thought["seconds"] + 5)


def test_forget_refusals_become_notes(world, tmp_path):
    island, body, library = world
    library.define({"name": "good", "steps": [{"skill": "jump"}]})
    library.skills["good"].update(successes=5, uses=5)
    mind = make_mind(world, tmp_path, FakeLLM())
    mind.adopt({"reply": {"forget": ["good"]}, "seconds": 1, "prepared": {"assumes": None}}, island.snap())
    assert mind.notes and mind.notes[0].startswith("'good' was kept")


def test_forgetting_and_reteaching_a_skill_that_worked_in_one_reply_keeps_it(world, tmp_path):
    # Review of #75 (75-CDE1): the forget was refused, then 'learn' replaced the steps that had worked anyway.
    island, body, library = world
    library.define({"name": "good", "steps": [{"skill": "jump"}]})
    library.skills["good"].update(successes=5, uses=5)
    mind = make_mind(world, tmp_path, FakeLLM())
    mind.adopt({"reply": {"forget": ["good"], "learn": [{"name": "good", "steps": [{"skill": "say", "args": {}}]}]},
                "seconds": 1, "prepared": {"assumes": None}}, island.snap())
    assert library.skills["good"]["steps"] == [{"skill": "jump"}] and library.skills["good"]["successes"] == 5
    assert mind.notes[0].startswith("'good' was kept")
    assert mind.notes[1].startswith("Your attempt to learn 'good' was rejected: 'good' has worked 5 of 5 times")


def test_the_mind_is_told_when_a_skill_that_worked_may_go(world, tmp_path):
    # Review of #75 (75-CLEAN4): the rule was only in the refusal, while the prompt said to forget failing skills.
    island, _, _ = world
    prompt = " ".join(make_mind(world, tmp_path, FakeLLM()).system_prompt(island.snap()).split())
    assert ("A skill that has worked keeps its steps until it has failed as many times in a row as it has worked "
            "(at least 3) or gone 2 hours without working; to try other steps before then, teach them under a new "
            "name.") in prompt


def test_one_project_decisions(world, tmp_path):
    island, body, library = world
    reply = {"intention": "look", "project": {"goal": "see", "steps": [{"skill": "wait", "args": {"seconds": 1}}]}}
    mind = make_mind(world, tmp_path, FakeLLM(reply), agenda=False)
    decision = mind.decide(island.snap(), [], [])
    assert decision["projects"][0]["intention"] == "look" and decision["projects"][0]["steps"][0]["skill"] == "wait"
    mind2 = make_mind(world, tmp_path, FakeLLM({"intention": "x"}), agenda=False)
    assert mind2.decide(island.snap(), [], [])["projects"][0]["steps"] == []


def test_agenda_feedback(world, tmp_path):
    mind = make_mind(world, tmp_path, FakeLLM())
    mind.agenda_feedback(10, 30)
    assert mind.notes == ["Your last agenda kept your body busy for 10s, but you think for about 30s per plan, so your "
                          "body stood still."]
    mind.agenda_feedback(40, 30)
    assert len(mind.notes) == 1


def test_record_outcome(world, tmp_path):
    island, body, library = world
    mem = NativeMemory(tmp_path / "mem")
    mind = make_mind(world, tmp_path, FakeLLM(), memory=mem)
    s = island.snap()
    ok = mind.record_outcome({"goal": "a tower"}, [
        Result(True, "build_tower", "stands 3 high", {"height": 3, "cubes": ["Block_1", "Block_2", "Block_3"]})], s)
    assert ok and mind.failures == [] and mind.last_outcome.startswith("Project 'a tower' succeeded.")
    assert any(t.startswith("tower of 3 at (5.0, 0.0)") for t in mem.state["structures"])
    assert mem.episodes[-1]["importance"] == 3
    assert not mind.record_outcome({"goal": "a wall"}, [Result(False, "put_down", "no room", {"toppled": True})], s)
    assert mind.failures == ["a wall: put_down: FAILED - no room"] and mem.episodes[-1]["importance"] == 4
    assert not mind.record_outcome({"goal": "nothing"}, [], s)
    assert mind.failures[-1] == "nothing: no steps"
    assert not mind.record_outcome({"goal": ""}, [Result(False, "jump", "x")], s)
    assert len(mind.failures) == 2
    mind.record_outcome({"goal": "t"}, [Result(True, "build_tower", "x", {"cubes": ["Gone_1", "Gone_2", "Gone_3"]})], s)


def hut_island(monkeypatch, tmp_path):
    """A hut's first course round the cell (10, 0), two corners two high, one spare block far off, and a log."""
    cells = [(dx, dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (dx, dz) != (0, 0)]
    wall = [block(f"Block_{i}", 10 + dx * 2.5, 1.25, dz * 2.5) for i, (dx, dz) in enumerate(cells, 1)]
    wall += [block("Block_21", 7.5, 3.75, -2.5), block("Block_22", 12.5, 3.75, 2.5)]
    island = Island([ground(attrs={"Surface": "Sand"}), *wall, block("Block_30", -12, 1.25, 0),
                     ent("Log_1", (-20, 1.25, 10), (7.5, 2.5, 2.5))])
    monkeypatch.setattr(sk, "time", FakeTime(island))
    library = SkillLibrary(tmp_path / "skills.json")
    mem = NativeMemory(tmp_path / "mem")
    body = Skills(island, library=library, protected=mem.protected_cubes, kept_in=mem.built_into)
    mind = Mind(FakeLLM(), mem, "I am a castaway.", body, library)
    return island, body, library, mem, mind, [w["name"] for w in wall]


def built(mind, island, *names):
    """The body set these pieces down (as place_at and put_down tell it), and the project ended."""
    mind.skills.placed += names
    mind.record_outcome({"goal": "build"}, [], island.snap())


def test_what_it_builds_is_kept_and_shown(monkeypatch, tmp_path):
    island, body, library, mem, mind, wall = hut_island(monkeypatch, tmp_path)
    built(mind, island, *wall, "Block_30")  # Block_30 set down alone: material, not a build
    (title, build), = mem.state["structures"].items()
    assert title == "build at (10.0, 0.0)" and build["auto"] and sorted(build["cubes"]) == sorted(wall)
    assert library.resolve_helpers({"a": {"nearest_free": "cube"}}, body) == {"a": "Block_30"}
    text = mind.situation(island.snap(), [], [])
    assert "Loose objects (nearest first): Block_30 (-12.0, 1.25, 0.0), Log_1 (-20.0, 1.25, 10.0)." in text
    assert "Stacks: none." in text
    assert ("build at (10.0, 0.0) (10 pieces): layer 1: (7.5, -2.5), (7.5, 0.0), (7.5, 2.5), (10.0, -2.5), "
            "(10.0, 2.5), (12.5, -2.5), (12.5, 0.0), (12.5, 2.5); layer 2: (7.5, -2.5), (12.5, 2.5)") in text
    # A closed ring one block high (two corners higher): no house yet, and the check says why.
    assert (". As a house: the room inside is 1 cell, at (10.0, 0.0): a house's room holds at least two by two "
            "cells; there is no doorway: leave one cell on a side open up to the roof; the walls do not reach the roof "
            "(7.5 up) at (7.5, -2.5), (7.5, 0.0), (7.5, 2.5), (10.0, -2.5), (10.0, 2.5), (12.5, -2.5) and 2 more, "
            "corners too; there is no roof over (10.0, 0.0) inside") in text
    r = body.run("pick_up", {"object": "Block_2"})
    assert not r.ok and r.summary == ("Block_2 is part of build at (10.0, 0.0), which you built; release that first "
                                      "if you mean to take it apart")
    # It grows under the same name; a piece knocked away from it is material again.
    island.ents["Log_1"]["position"] = [10, 6.25, 0]  # a roof beam across the two corners' tops
    island.ents["Block_8"]["position"] = [30, 1.25, 30]
    built(mind, island, "Log_1")
    (title, build), = mem.state["structures"].items()
    assert title == "build at (10.0, 0.0)" and "Log_1" in build["cubes"] and "Block_8" not in build["cubes"]
    assert "Log_1 (10.0, 0.0) along x" in mind.situation(island.snap(), [], [])
    assert body.run("pick_up", {"object": "Block_8"}).ok
    # Released, it is material again, and stays so until it is built with anew.
    mind.adopt({"reply": {"release": [title]}, "seconds": 1, "prepared": {"assumes": None}}, island.snap())
    mind.record_outcome({"goal": "nothing"}, [], island.snap())
    assert mem.state["structures"] == {} and body.run("pick_up", {"object": "Block_2"}).ok


def test_a_flat_pile_is_material_and_learned_skills_build_too(monkeypatch, tmp_path):
    island, body, library, mem, mind, wall = hut_island(monkeypatch, tmp_path)
    # Run hut1 gathered its blocks side by side to take from: a pile, not a build, until something is stacked.
    built(mind, island, *wall[:3])  # three blocks of the first course, flat on the ground
    assert mem.state["structures"] == {} and body.run("pick_up", {"object": "Block_1"}).ok
    # Every block in run hut1 went down through one of its own skills (stack_block, haul_to): those count too.
    library.define({"name": "haul", "params": ["object"], "steps": [
        {"skill": "pick_up", "args": {"object": "$object"}}, {"skill": "put_down", "args": {"x": -15, "z": 5}}]})
    assert body.run("haul", {"object": "Block_30"}).ok
    assert body.take_placed() == ["Block_30"] and body.take_placed() == []  # Block_1 was only set aside first


def test_what_it_names_itself(monkeypatch, tmp_path):
    island, body, library, mem, mind, wall = hut_island(monkeypatch, tmp_path)
    keep = [{"name": "my gate", "cubes": ["Block_1", "Block_2"]}, {"name": "roof beam", "cubes": ["Log_1"]}]
    mind.adopt({"reply": {"keep": keep}, "seconds": 1, "prepared": {"assumes": None}}, island.snap())
    built(mind, island, *wall)
    assert sorted(mem.state["structures"]) == ["build at (10.0, 0.0)", "my gate", "roof beam"]
    assert mem.built_into("Block_1") == "build at (10.0, 0.0)" and mem.built_into("Log_1") is None
    text = mind.situation(island.snap(), [], [])
    assert "build at (10.0, 0.0), which you call my gate, (10 pieces): layer 1:" in text
    assert "roof beam (1 pieces): layer 1: Log_1 (-20.0, 10.0) along x" in text
    # A piece it named but built into nothing it may still take (run hut2: a log it called its roof beam, on the
    # sand); the helpers leave it alone, as before.
    assert library.resolve_helpers({"a": {"nearest_free": "cube"}}, body) == {"a": "Block_30"}
    assert body.run("pick_up", {"object": "Log_1"}).ok
    assert not body.run("pick_up", {"object": "Block_1"}).ok


def benchmark(x0=0, z0=0, high=3, roof=True):
    """The benchmark house (test_house.py house()) as island pieces, its room at cells (x0..x0+1, z0..z0+1): walls
    `high` blocks all round, corners too, the doorway south at (x0, z0 - 1), and the roof in the layer above."""
    pieces = []
    for dx in range(-1, 3):
        for dz in range(-1, 3):
            if (0 <= dx <= 1 and 0 <= dz <= 1) or (dx, dz) == (0, -1):
                continue
            pieces += [block(f"Block_w{dx + 1}{dz + 1}{k}", (x0 + dx) * 2.5, (k - 0.5) * 2.5, (z0 + dz) * 2.5)
                       for k in range(1, high + 1)]
    if roof:
        y = (high + 0.5) * 2.5
        logs = [("Log_S", 0, -1), ("Log_N", 0, 2), ("Log_W0", -1, 0), ("Log_E0", 2, 0), ("Log_W1", -1, 1), ("Log_E1", 2, 1)]
        pieces += [ent(name, ((x0 + dx) * 2.5, y, (z0 + dz) * 2.5), (7.5, 2.5, 2.5)) for name, dx, dz in logs]
        pieces += [block("Block_SE", (x0 + 2) * 2.5, y, (z0 - 1) * 2.5), block("Block_NE", (x0 + 2) * 2.5, y, (z0 + 2) * 2.5)]
    return pieces


def house_island(monkeypatch, tmp_path, pieces):
    island = Island([ground(attrs={"Surface": "Sand"}), *pieces, block("Block_30", -12, 1.25, 0),
                     ent("Log_1", (-20, 1.25, 10), (7.5, 2.5, 2.5))])
    island.me = [0, BODY_CENTRE_Y, -20]
    monkeypatch.setattr(sk, "time", FakeTime(island))
    library, mem, logs = SkillLibrary(tmp_path / "skills.json"), NativeMemory(tmp_path / "mem"), []
    body = Skills(island, library=library, protected=mem.protected_cubes, kept_in=mem.built_into)
    mind = Mind(FakeLLM(), mem, "I am a castaway.", body, library, log=lambda **k: logs.append(k), house_project=True)
    return island, body, mem, mind, logs


def test_one_house_kept_across_plans(monkeypatch, tmp_path):
    # Run hut5-house: four sites in 45 minutes, 19 pieces of its own building taken back. One house, chosen once.
    # Here its first course stands round a room two by two at (10..12.5, 0..2.5), two corners a block higher, and a
    # block lies in its doorway.
    course = benchmark(x0=4, high=1, roof=False)
    course += [block("Block_c1", 7.5, 3.75, -2.5), block("Block_c2", 15, 3.75, 5), block("Block_door", 10, 1.25, -2.5)]
    island, body, mem, mind, logs = house_island(monkeypatch, tmp_path, course)
    system = mind.system_prompt(island.snap())
    assert '"house": {' in system and "A house you build is one project, kept across all your plans" in system
    assert "Your house" not in mind.situation(island.snap(), [], [])

    def reply(house):
        mind.adopt({"reply": {"house": house}, "seconds": 1, "prepared": {"assumes": None}}, island.snap())
    reply({"inside": [[10, 0], [12.5, 0], [10, 2.5], [12.5, 2.5]], "door": [10, -2.5]})
    assert mem.state["house"]["inside"] == [[4, 0], [4, 1], [5, 0], [5, 1]] and mem.state["house"]["door"] == [4, -1]
    text = mind.situation(island.snap(), [], [])
    assert ("Your house, the one project you keep across your plans (chosen 0 minutes ago): inside (10.0, 0.0), (10.0, "
            "2.5), (12.5, 0.0), (12.5, 2.5), the doorway at (10.0, -2.5). Done: the room is clear. Next: walls three "
            "blocks high all round the room, corners too, but for the doorway at (10.0, -2.5): (7.5, -2.5) stands 5.0, "
            "(7.5, 0.0) stands 2.5,") in text
    assert "Built so far, kept for it (13 pieces): layer 1: (7.5, -2.5)," in text
    # Its walls are kept for it; the block in its doorway is not.
    r = body.run("pick_up", {"object": "Block_w002"[:-1] + "1"})
    assert not r.ok and r.summary == ("Block_w001 is part of your house at (10.0, 0.0), which you are building; move the "
                                      'house or give it up first ("house", with why) if you mean to take it apart')
    assert "Block_w001" not in mind.situation(island.snap(), [], []).split("Loose objects")[1].split("Stacks")[0]
    assert body.run("pick_up", {"object": "Block_door"}).ok
    # Elsewhere only with a reason; the same site it may change as it likes.
    elsewhere = {"inside": [[-12.5, 5], [-10, 5], [-12.5, 7.5], [-10, 7.5]], "door": [-12.5, 2.5]}
    reply(elsewhere)
    assert mem.state["house"]["inside"] == [[4, 0], [4, 1], [5, 0], [5, 1]]
    assert mind.notes[-1] == ("You did not move your house from (10.0, 0.0): a house moves only for a concrete reason "
                              'it cannot stand there; give it with "why".')
    reply({"inside": [[10, 0], [12.5, 0], [10, 2.5], [12.5, 2.5], [10, 5], [12.5, 5]], "door": [10, -2.5]})
    assert len(mem.state["house"]["inside"]) == 6 and mem.state["house"]["moves"] == 0
    reply({"inside": [[10, 0], [12.5, 0], [10, 2.5], [12.5, 2.5]], "door": [7.5, -2.5]})
    assert ("Your house was not set: the doorway at (7.5, -2.5) must be a cell beside the room on one of its sides"
            in mind.notes[-1])
    reply({"inside": [[10, 0], [12.5, 0], [10, 2.5], [12.5, 2.5]], "door": [10, -2.5]})  # two by two again
    assert len(mem.state["house"]["inside"]) == 4
    # Run hp-proj1: a block left in the room was part of a build it kept, so the body would not lift it out, and the
    # build's own house verdict named another room. What is in the house's way is free to move, and the house has one
    # account: its own line.
    island.ents["Block_30"]["position"] = [12.5, 1.25, 2.5]  # set down in the room, beside the east wall: built in
    built(mind, island, *[p["name"] for p in course if p["name"] != "Block_door"], "Block_30")
    text = mind.situation(island.snap(), [], [])
    assert mem.state["house"]["in_the_way"] == ["Block_30"] and "Block_30" not in mem.protected_cubes()
    assert ". It is where your house stands: what the house still needs is said above" in text and "As a house" not in text
    assert any("Block_30" in s["cubes"] for s in mem.state["structures"].values())
    assert mem.built_into("Block_30") is None  # no build keeps it from the body (reaching into a room two cells wide
    # is a body matter: from 1.6 off the walls and 1.2 off a loose piece, nowhere in the room is close enough)
    mem.release_structure(next(iter(mem.state["structures"])))
    # Stalled: it hears so after fifteen minutes with nothing gained.
    mem.state["house"]["best_at"] -= 16 * 60
    assert "It has come no further in 16 minutes: the next step needs another way of doing it." in mind.situation(
        island.snap(), [], [])
    reply({**elsewhere, "why": "the sand here is soft and the walls slide"})
    house = mem.state["house"]
    assert house["inside"] == [[-5, 2], [-5, 3], [-4, 2], [-4, 3]] and house["moves"] == 1 and house["pieces"] == []
    assert "(chosen 0 minutes ago, after moving it 1 time): inside (-12.5, 5.0)" in mind.situation(island.snap(), [], [])
    assert body.run("pick_up", {"object": "Block_w001"}).ok
    reply({"inside": []})
    assert mem.state["house"] == house and "You did not give up your house" in mind.notes[-1]
    reply({"inside": [], "why": "no stone is left on the island"})
    assert "house" not in mem.state
    assert [(l["phase"], l.get("why", "")) for l in logs if l["kind"] == "house"
            and l["phase"] not in ("progress", "installed")] == [
        ("chose", ""), ("refused", ""), ("revised", ""), ("rejected", ""), ("revised", ""),
        ("moved", "the sand here is soft and the walls slide"), ("refused", ""),
        ("abandoned", "no stone is left on the island")]
    # What stays built at the house is counted as it changes: the work that is not taken back.
    assert [l["pieces"] for l in logs if l["kind"] == "house" and l["phase"] == "installed"][:1] == [13]


def test_a_revised_house_is_measured_afresh(monkeypatch, tmp_path):
    # Its best so far was scored against the old layout: with the doorway moved onto a wall, the house scores less
    # than it did, and measured against that the work never counted as progress, until the stall note said it had come
    # no further.
    island, body, mem, mind, logs = house_island(monkeypatch, tmp_path, benchmark())
    room = [[0, 0], [2.5, 0], [0, 2.5], [2.5, 2.5]]
    mind._choose_house({"inside": room, "door": [0, -2.5]}, island.snap())
    mem.state["house"]["best_at"] -= 20 * 60
    mind._choose_house({"inside": room, "door": [-2.5, 0]}, island.snap())  # the doorway onto the west wall
    house = mem.state["house"]
    progress = [l for l in logs if l["kind"] == "house" and l["phase"] == "progress"]
    assert len(progress) == 2 and house["best"] == progress[-1]["score"] < progress[0]["score"]
    assert "come no further" not in mind.situation(island.snap(), [], [])


def test_a_chosen_house_that_stands(monkeypatch, tmp_path):
    island, body, mem, mind, logs = house_island(monkeypatch, tmp_path, benchmark())
    mind.adopt({"reply": {"house": {"inside": [[0, 0], [2.5, 0], [0, 2.5], [2.5, 2.5]], "door": [0, -2.5]}},
                "seconds": 1, "prepared": {"assumes": None}}, island.snap())
    assert [l["phase"] for l in logs if l["kind"] == "house"] == ["chose", "installed", "progress", "built"]
    assert [l["pieces"] for l in logs if l.get("phase") == "installed"] == [41]
    assert "Next: none: it is a house. Walk in by the doorway at (0.0, -2.5) and stand inside." in mind.situation(
        island.snap(), [], [])
    # Off, as in the comparison's other arm: no house in the reply's shape, and a "house" in a reply does nothing.
    mind.house_project = False
    assert '"house"' not in mind.system_prompt(island.snap())
    mem.set_house(None)
    mind.adopt({"reply": {"house": {"inside": [[0, 0], [2.5, 0], [0, 2.5], [2.5, 2.5]], "door": [0, -2.5]}},
                "seconds": 1, "prepared": {"assumes": None}}, island.snap())
    assert "house" not in mem.state


def test_planning_ahead_counts_the_agendas_pieces_as_taken(monkeypatch, tmp_path):
    # Run rp3: the plan made while the body raised a column took the column's blocks for a ring round it.
    island, body, library, mem, mind, wall = hut_island(monkeypatch, tmp_path)
    doing = [{"goal": "a column", "steps": [
        {"skill": "pick_up", "args": {"object": "Block_30"}}, {"skill": "place_at", "args": {"x": -10, "y": 1.25, "z": 5}},
        {"skill": "pick_up", "args": {"object": "Log_1"}}, {"skill": "put_down", "args": {"x": -10, "z": 10}},
        {"skill": "pick_up", "args": {"object": {"nearest_free": "cube"}}},
        {"skill": "place_at", "args": {"x": -10, "y": 3.75, "z": 5}}]},
        {"goal": "a look round", "steps": [{"skill": "walk_to", "args": {"x": 0, "z": 0}}]}]
    text = mind.situation(island.snap(), [], [], doing=doing)
    loose = next(line for line in text.splitlines() if line.startswith("Loose objects"))
    assert "Block_30" not in loose and "Log_1" not in loose and "Block_2" in loose
    assert ("Right now your body is carrying out this agenda: 1) a column; 2) a look round. On the way it sets "
            "Block_30 to (-10.0, 1.25, 5.0), Log_1 to (-10.0, 10.0) on the ground, and picks up 1 more piece as it "
            "goes. Plan what comes AFTER all of it, assuming it succeeds: those pieces will be where it puts them, "
            "not loose.") in text
    plain = mind.situation(island.snap(), [], [], doing=[{"goal": "a walk", "steps": []}])
    assert "1) a walk. Plan what comes AFTER all of it, assuming it succeeds." in plain


def test_learned_wall_skill_keeps_each_piece_before_the_next_pickup(monkeypatch, tmp_path):
    island, body, mem, mind, _ = house_island(monkeypatch, tmp_path, [block("Block_31", -17, 1.25, 0)])
    mind._choose_house({"inside": [[10, 0], [10, 2.5], [12.5, 0], [12.5, 2.5]], "door": [10, -2.5]}, island.snap())
    body.library.define({"name": "wall_pair", "steps": [
        {"skill": "pick_up", "args": {"object": {"nearest_free": "cube"}}},
        {"skill": "put_down", "args": {"x": 7.5, "z": 0}},
        {"skill": "pick_up", "args": {"object": {"nearest_free": "cube"}}},
        {"skill": "put_down", "args": {"x": 7.5, "z": 2.5}}]})
    result = body.run("wall_pair", {})
    assert result.ok, result.summary
    assert {tuple(island.ents[n]["position"][::2]) for n in ("Block_30", "Block_31")} == {(7.5, 0), (7.5, 2.5)}
    assert {"Block_30", "Block_31"} <= mem.protected_cubes()
    assert body.take_placed() == ["Block_30", "Block_31"]


def test_automatic_build_members_survive_placement_history_limit(world, tmp_path):
    island, body, _ = world
    mind = make_mind(world, tmp_path, FakeLLM())
    body.protected = mind.memory.protected_cubes
    body.kept_in = mind.memory.built_into
    built(mind, island, "Block_1", "Block_2")
    title = next(iter(mind.memory.state["structures"]))
    later = [block(f"Stone_{n}", -190 + 5 * (n % 39), 1.25, 30 + 5 * (n // 39)) for n in range(399)]
    island.ents.update({e["name"]: e for e in later})
    built(mind, island, *(e["name"] for e in later))
    assert len(mind.memory.state["placed"]) == 400 and "Block_1" not in mind.memory.state["placed"]
    assert mind.memory.state["structures"][title]["cubes"] == ["Block_1", "Block_2"]
    assert {"Block_1", "Block_2"} <= NativeMemory(mind.memory.root).protected_cubes()
    assert not body.run("pick_up", {"object": "Block_2"}).ok


def test_resuming_without_house_project_releases_only_its_ownership(monkeypatch, tmp_path):
    island, body, mem, mind, _ = house_island(monkeypatch, tmp_path, benchmark(x0=4, high=1, roof=False))
    mind._choose_house({"inside": [[10, 0], [10, 2.5], [12.5, 0], [12.5, 2.5]], "door": [10, -2.5]}, island.snap())
    mem.add_structure("chosen keeps", ["Log_1"], (-20, 10), {"Log_1": (-20, 1.25, 10)})
    mem.save()
    saved_house = mem.state["house"]
    resumed = NativeMemory(mem.root)
    body = Skills(island, library=body.library, protected=resumed.protected_cubes, kept_in=resumed.built_into,
                  reserved=resumed.reserved_cells)
    mind = Mind(FakeLLM(), resumed, "", body, body.library, house_project=False)
    assert '"house": {' not in mind.system_prompt(island.snap())
    assert resumed.reserved_cells() == set() and resumed.protected_cubes() == {"Log_1"}
    assert resumed.built_into("Block_w001") is None
    assert body.run("pick_up", {"object": "Block_w001"}).ok
    resumed.save()
    assert NativeMemory(resumed.root).state["house"] == saved_house


def test_house_geometry_is_observed_cached_and_revisited(monkeypatch, tmp_path):
    island, body, mem, mind, _ = house_island(monkeypatch, tmp_path, benchmark(x0=40))
    island.ents["Block_hidden"] = block("Block_hidden", 110, 1.25, 20)
    island.ents["Log_W1"]["anchored"] = True
    discovery = Discovery(tmp_path / "discovery.json")
    mind.discovery = discovery
    discovery.see(island.snap())
    mind._choose_house({"inside": [[100, 0], [100, 2.5], [102.5, 0], [102.5, 2.5]], "door": [100, -2.5]}, island.snap())
    unseen = mind.situation(island.snap(), [], [])
    assert "needs an inspection" in unseen and "Block_hidden" not in unseen and "Log_W1" not in unseen
    assert mem.state["house"]["pieces"] == []
    bare = {"inside": [[-100, 0], [-100, 2.5], [-97.5, 0], [-97.5, 2.5]], "door": [-100, -2.5]}
    island.me = [-100, BODY_CENTRE_Y, -10]
    discovery.see(island.snap())
    mind._choose_house({**bare, "why": "the first site is too far"}, island.snap())
    empty = mind.situation(island.snap(), [], [])  # nothing built there yet: nothing to have last observed
    assert "Next: walls three blocks high" in empty and "Last observed." not in empty, empty
    mind._choose_house({"inside": [[100, 0], [100, 2.5], [102.5, 0], [102.5, 2.5]], "door": [100, -2.5],
                        "why": "the stone is over there"}, island.snap())
    island.me = [100, BODY_CENTRE_Y, -10]
    discovery.see(island.snap())
    assert "Next: none: it is a house." in mind.situation(island.snap(), [], [])
    island.me = [-100, BODY_CENTRE_Y, -20]
    discovery.see(island.snap())
    island.ents["Block_hidden"]["position"] = [100, 1.25, 0]
    island.ents["Log_W1"].update(anchored=False, rotation=[[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    hidden = mind.situation(island.snap(), [], [])
    assert "Last observed." in hidden and "Next: none: it is a house." in hidden
    assert "Block_hidden fills it" not in hidden
    mem.save()
    discovery.save()
    restored = NativeMemory(mem.root)
    discovery = Discovery(discovery.path)
    body = Skills(island, library=body.library, protected=restored.protected_cubes, kept_in=restored.built_into)
    mind = Mind(FakeLLM(), restored, "", body, body.library, discovery=discovery, house_project=True)
    assert "Next: none: it is a house." in mind.situation(island.snap(), [], [])
    cached = mind._construction_view(island.snap()).entities["Log_W1"]
    assert cached.anchored and cached.size == (7.5, 2.5, 2.5)
    island.me = [100, BODY_CENTRE_Y, -10]
    discovery.see(island.snap())
    revisited = mind.situation(island.snap(), [], [])
    assert "Block_hidden fills it" in revisited and "Next: none: it is a house." not in revisited
    observed = mind._construction_view(island.snap()).entities["Log_W1"]
    assert not observed.anchored and observed.size == (2.5, 7.5, 2.5)
    assert "Block_hidden" not in restored.protected_cubes()


def test_uneven_house_site_keeps_planning_available(monkeypatch, tmp_path):
    raised = ent("Mesa_raised", (12.5, 0.5, 2.5), (2.4, 1, 2.4), role="Mesa")
    island, body, mem, mind, _ = house_island(monkeypatch, tmp_path, [raised])
    spec = {"inside": [[10, 0], [10, 2.5], [12.5, 0], [12.5, 2.5]], "door": [10, -2.5]}
    mind.adopt({"reply": {"house": spec}, "seconds": 1, "prepared": {"assumes": None}}, island.snap())
    assert "choose level ground" in mind.prepare(island.snap(), [], [])["user"]
    mind.adopt({"reply": {"house": {"inside": [], "why": "uneven floor"}}, "seconds": 1,
                "prepared": {"assumes": None}}, island.snap())
    assert "house" not in mem.state


def test_legacy_build_waits_for_inspection_then_releases_missing_members(world, tmp_path):
    island, _, _ = world
    mind = make_mind(world, tmp_path, FakeLLM())
    built(mind, island, "Block_1", "Block_2")
    title = next(iter(mind.memory.state["structures"]))
    mind.discovery = Discovery()
    mind.keep_builds(island.snap())
    assert title in mind.memory.state["structures"]
    island.ents.pop("Block_1")
    mind.discovery.see(island.snap())
    mind.keep_builds(island.snap())
    assert title not in mind.memory.state["structures"]


def test_sleep(world, tmp_path):
    island, body, library = world
    mem = BrainMemory(tmp_path / "brain")
    mind = make_mind(world, tmp_path, FakeLLM(), memory=mem)
    assert mind.sleep(island.snap()) is None  # nothing to consolidate
    mem.note("stones are heavy", about="stone")
    reply = {"digest": "A good day.", "intentions": ["a hut"], "dream": "of ships",
             "lessons": [{"about": "fire", "text": "rain puts it out"}, "plain lesson", {"about": "x", "text": ""}],
             "facts": {"stone": ["stones are heavy"]}}
    llm = FakeLLM(reply)
    mind.llm = llm
    assert mind.sleep(island.snap()) is reply
    assert "What you currently believe, by subject" in llm.calls[0]["user"] and llm.calls[0]["purpose"] == "sleep"
    assert mem.state["digest"] == "A good day." and mem.state["slept"] == 1
    assert "fire" in mem.facts and mem.facts["world"][0]["text"] == "plain lesson"
    assert mind.logs[-1]["kind"] == "sleep" and mind.logs[-1]["facts_rewritten"] == 1
    native = NativeMemory(tmp_path / "native")
    native.store_experience("a day")
    plain = make_mind(world, tmp_path, FakeLLM({"digest": "d"}), memory=native)
    plain.sleep(island.snap())
    assert "What you currently believe" not in plain.llm.calls[0]["user"] if plain.llm.calls else True


def test_knows_and_sees(world, tmp_path):
    island, body, library = world
    d = Discovery()
    d.see(island.snap())
    mind = make_mind(world, tmp_path, FakeLLM(), discovery=d)
    s = island.snap()
    assert mind._knows(s.entities["Block_1"]) and mind._sees(s.entities["Block_1"])
    mind.log(kind="x")
    assert Mind(FakeLLM(), NativeMemory(tmp_path / "z"), "", body, library).log(kind="y") is None
    assert mind_module.MAX_STEPS == 12 and BODY_CENTRE_Y


def test_reflect_on_death(world, tmp_path):
    """Born again, the mind draws its own lessons from the death report: kept at the highest importance, told to the
    next plan, and logged (with the feeling a viewer can read)."""
    island, body, library = world
    island.attrs.update(Deaths=2, DiedOf="Storm")
    llm = FakeLLM({"lessons": [{"about": "storm", "text": "When the sky darkens, get under the roof"}, "keep moving",
                               {"about": "x", "text": "  "}], "feeling": "The sky is not to be trusted"})
    mind = make_mind(world, tmp_path, llm)
    lessons = mind.reflect_on_death(island.snap(), "You died of lightning in a storm.")
    assert lessons == [{"about": "storm", "text": "When the sky darkens, get under the roof"},
                       {"about": "", "text": "keep moving"}]
    call = llm.calls[0]
    assert call["purpose"] == "death" and "You died of lightning in a storm." in call["user"]
    assert "I am a castaway." in call["system"]
    kept = {e["text"]: e for e in mind.memory.episodes}
    assert kept["When the sky darkens, get under the roof"]["importance"] == 5
    assert kept["keep moving"]["entities"] == ["death"], "a lesson without a subject is about death"
    assert mind.notes[-1] == ("You died of lightning in a storm and came back to life at the start; your lesson: "
                              "When the sky darkens, get under the roof.")
    assert mind.last_outcome == "You died of lightning in a storm, and have come back to life at the start."
    assert mind.logs[-1] == {"kind": "death", "cause": "Storm", "deaths": 2, "lessons": lessons,
                             "feeling": "The sky is not to be trusted"}
    quiet = make_mind(world, tmp_path, FakeLLM({}))
    assert quiet.reflect_on_death(island.snap(), "report") == []
    assert quiet.notes[-1] == "You died of lightning in a storm and came back to life at the start."


def test_situation_tells_what_a_meteors_stone_and_its_iron_look_like(world, tmp_path):
    """METEORIC IRON: the loose things and what is held carry what the eye tells of them (Entity.look)."""
    island, body, library = world
    island.ents["Meteor_2"] = ent("Meteor_2", (-6, 1.25, -6), role="Stone", attrs={"Heat": 0.5})
    island.ents["Meteor_1"] = ent("Meteor_1", (-9, 1.25, -6), role="Stone", attrs={"Heat": 0})
    island.ents["Iron_1"] = ent("Iron_1", (-6, 0.1, -3), (0.5, 0.2, 1.0), role="Iron")
    island.ents["Spear_1"] = ent("Spear_1", (-3, 2.5, 0), (0.3, 0.3, 4.5), role="Tool", attrs={"Edge": "Iron"})
    island.held = "Spear_1"
    mind = make_mind(world, tmp_path, FakeLLM())
    text = mind.situation(island.snap(), [], [])
    assert "holding Spear_1 (with an edge of dark metal bound on)." in text
    assert "Meteor_2 (glowing hot) (-6.0, 1.25, -6.0)" in text
    assert "Meteor_1 (dark, heavy, metallic) (-9.0, 1.25, -6.0)" in text
    assert "Iron_1 (a sliver of dark metal, hard, sharp-edged) (-6.0, 0.10, -3.0)" in text
    d = Discovery()
    d.see(island.snap())
    d.seen["Meteor_9"] = (40, 1.25, 40)  # seen once, gone from sight since: no look, it is not in sight
    seeing = make_mind(world, tmp_path, FakeLLM(), discovery=d)
    text = seeing.situation(island.snap(), [], [])
    assert "Meteor_2 (glowing hot)" in text and "Meteor_9 (40.0, 1.25, 40.0) (last seen there)" in text
