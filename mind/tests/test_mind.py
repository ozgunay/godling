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
                     "through (80%). You are cold, and it is wearing your health down. You stand under a roof with walls "
                     "around you.")
    assert "You are wet (20%)" in _how_it_feels(snap([ground()], attrs={"Wet": 20, "Sheltered": "roof"}))


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
    island.attrs.update(Hunger=50, Health=90, Faints=1, Wet=20)
    island.clock = {"TimeOfDay": 6.5}
    island.held = "Log_4"
    mind = make_mind(world, tmp_path, FakeLLM(), memory=mem)
    mind.notes = ["a note"]
    mind.failures = ["a: x", "b: y"]
    mind.think_s = 30
    text = mind.situation(island.snap(), [{"text": "A thing happened", "entities": ["Block_3"]}],
                          [{"agent_name": "Ann", "content": "hello"}], doing=[{"goal": "a wall"}])
    assert "It is 06:30, dawn." in text and "holding Log_4" in text
    assert "You are 50% fed, with health 90 of 100; you have fainted from hunger 1 time." in text
    assert "You are wet (20%)." in text and "Fires burning: Fire_1 (2.0, -2.0)." in text
    assert "Fish swimming in the shallows nearest you: Fish_1 (0.0, 20.0)." in text
    assert "Lines you drew in the sand (2, oldest first): (2, 2)-(3, 3); (0, 0)-(1, 1)." in text
    assert "2-high stack at (5, 0): Block_1, Block_2" in text and "tower at [5, 0] (2 cubes)" in text
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
    library.protect_proven = True
    library.define({"name": "good", "steps": [{"skill": "jump"}]})
    library.skills["good"].update(successes=5, uses=5)
    mind = make_mind(world, tmp_path, FakeLLM())
    mind.adopt({"reply": {"forget": ["good"]}, "seconds": 1, "prepared": {"assumes": None}}, island.snap())
    assert mind.notes and mind.notes[0].startswith("'good' was kept")


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
