import json
import sys
import time
import types

import pytest

from godling import memory_hindsight
from godling.memory import NativeMemory, _words
from godling.memory2 import BrainMemory, _similar


def test_words():
    assert _words("The big Block_1 is here, ok") == {"block_1", "here"}


def test_native_memory_store_and_retrieve(tmp_path):
    mem = NativeMemory(tmp_path / "m")
    a = mem.store_experience("  The tower fell over by the mesa  ", tick=3, entities=["Block_1", "Block_1"])
    b = mem.store_experience("Ate a coconut", importance=5)
    assert (a, b) == (1, 2)
    assert mem.episodes[0]["text"] == "The tower fell over by the mesa" and mem.episodes[0]["entities"] == ["Block_1"]
    got = mem.retrieve(entities=["Block_1"], text="tower")
    assert got[0]["id"] == 1
    assert mem.retrieve(limit=1)[0]["id"] == 2  # more important
    assert mem.note("Towers fall in quakes", about="tower") == 3
    assert mem.episodes[-1]["kind"] == "lesson" and mem.episodes[-1]["entities"] == ["tower"]
    assert mem.note("plain") == 4 and mem.episodes[-1]["entities"] == []
    assert mem.recall_for(["Block_1"], "tower")["facts"] == []
    assert mem.consolidation_input() == {}
    mem.apply_consolidation({"x": ["y"]})
    mem.flush()
    assert len(mem.reflect_input()) == 4
    mem.invalidate(1, "wrong")
    assert all(ep["id"] != 1 for ep in mem.retrieve(entities=["Block_1"]))
    assert len(mem.reflect_input()) == 3
    reloaded = NativeMemory(tmp_path / "m")
    assert reloaded.episodes[0]["invalid"] == "wrong" and len(reloaded.episodes) == 4


def test_native_memory_state(tmp_path):
    mem = NativeMemory(tmp_path)
    mem.set_intentions(["  build a hut ", "", "eat"] + [f"i{n}" for n in range(10)])
    assert [i["text"] for i in mem.open_intentions()][:2] == ["build a hut", "eat"]
    assert len(mem.open_intentions()) == 6
    mem.state["intentions"][0]["status"] = "done"
    assert len(mem.open_intentions()) == 5
    mem.add_structure("tower", ["B1", "B2"], (1.234, 5.678), {"B1": (1.23456, 2, 3), "B2": (1, 2, 3)})
    mem.add_structure("loose", ["B3"], (0, 0), {"B3": (0, 0, 0)}, keep=False)
    assert mem.state["structures"]["tower"]["where"] == [1.2, 5.7]
    assert mem.state["structures"]["tower"]["positions"]["B1"] == [1.235, 2, 3]
    assert mem.protected_cubes() == {"B1", "B2"}
    mem.release_structure("tower")
    mem.release_structure("never")
    assert mem.protected_cubes() == set()
    before = mem.state["last_sleep"]
    time.sleep(0.01)
    mem.finish_sleep(" digest " * 1000, ["next"])
    assert len(mem.state["digest"]) == 2500 and mem.state["slept"] == 1 and mem.state["last_sleep"] > before
    assert mem.health() == {"episodes": 0, "intentions": 1, "structures": 1, "slept": 1}
    mem.save()
    again = NativeMemory(tmp_path)
    assert again.state["slept"] == 1 and "loose" in again.state["structures"]


def test_similar():
    assert _similar("blocks fall in quakes", "blocks fall in big quakes")
    assert not _similar("blocks fall", "fish swim")
    assert not _similar("", "x")


def test_brain_memory_folds_facts(tmp_path):
    mem = BrainMemory(tmp_path)
    mem.note("Blocks fall when the ground shakes", about="Stacking", tick=1)
    mem.note("Blocks fall when the ground shakes hard", about="stacking", tick=2)
    assert mem.facts["stacking"] == [{"text": "Blocks fall when the ground shakes hard", "seen": 2, "first_tick": 1,
                                      "last_tick": 2}]
    for n in range(7):
        mem.note(f"distinct fact number {n} alpha{n} beta{n}", about="", tick=n)
    assert len(mem.facts["world"]) == 6
    mem.note("Tree_4 has coconuts", about="Tree_4")
    recalled = mem.recall_for(["Tree_4"], "what about stacking?")
    assert recalled["facts"][0] == "stacking: Blocks fall when the ground shakes hard (confirmed 2x)"
    assert any(line.startswith("tree_4:") for line in recalled["facts"])
    assert len(recalled["episodes"]) <= 4
    assert mem.consolidation_input()["tree_4"] == ["Tree_4 has coconuts"]
    mem.apply_consolidation({"Stacking": ["Blocks fall when the ground shakes hard", "new one", " "],
                             "tree_4": []})
    assert [f["seen"] for f in mem.facts["stacking"]] == [2, 1]
    assert "tree_4" not in mem.facts
    health = mem.health()
    assert health["fact_subjects"] == 2 and health["facts"] == 8
    mem.save()
    assert json.loads((tmp_path / "facts.json").read_text())["stacking"][1]["text"] == "new one"
    assert BrainMemory(tmp_path).facts == mem.facts


class FakeHindsight:
    instances = []

    def __init__(self, base_url, timeout):
        self.base_url = base_url
        self.calls = []
        self.fail = set()
        self.recall_reply = {"results": []}
        FakeHindsight.instances.append(self)

    def _maybe_fail(self, name):
        self.calls.append(name)
        if name in self.fail:
            raise RuntimeError(f"{name} broke")

    def create_bank(self, **kw):
        self._maybe_fail("create_bank")

    def retain_batch(self, **kw):
        self._maybe_fail("retain_batch")
        self.retained = kw["items"]

    def recall(self, **kw):
        self._maybe_fail("recall")
        self.query = kw["query"]
        return self.recall_reply


@pytest.fixture
def hindsight(monkeypatch):
    module = types.ModuleType("hindsight_client")
    module.Hindsight = FakeHindsight
    monkeypatch.setitem(sys.modules, "hindsight_client", module)
    FakeHindsight.instances.clear()
    return FakeHindsight


def test_hindsight_memory(tmp_path, hindsight):
    logs = []
    mem = memory_hindsight.HindsightMemory(tmp_path, "http://h", "bank", log=lambda **kw: logs.append(kw))
    client = hindsight.instances[0]
    assert client.base_url == "http://h" and client.calls == ["create_bank"]
    mem.flush()  # nothing pending
    assert client.calls == ["create_bank"]
    mem.store_experience("saw a ship", kind="event", tick=5, entities=["Ship"])
    mem.store_experience("plain")
    mem.flush()
    assert client.retained[0] == {"content": "saw a ship", "context": "event at world tick 5, about Ship"}
    assert client.retained[1]["context"] == "event at world tick 0"
    assert logs[-1]["op"] == "retain" and mem.pending == []
    client.recall_reply = {"results": [{"text": "a fact", "type": "world"}, {"text": " ", "type": "world"},
                                       types.SimpleNamespace(text="an episode", type="experience")]}
    recalled = mem.recall_for(["Ship"], "where is the ship")
    assert recalled == {"facts": ["a fact"], "episodes": [{"tick": "?", "text": "an episode"}]}
    assert client.query == "where is the ship | in view: Ship"
    assert mem.health()["engine"] == "hindsight" and mem.health()["bank"] == "bank"


def test_hindsight_failures_fall_back(tmp_path, hindsight):
    logs = []
    module_client = hindsight

    class Failing(module_client):
        def __init__(self, base_url, timeout):
            super().__init__(base_url, timeout)
            self.fail = {"create_bank", "retain_batch", "recall"}

    sys.modules["hindsight_client"].Hindsight = Failing
    mem = memory_hindsight.HindsightMemory(tmp_path, "http://h", "bank", log=lambda **kw: logs.append(kw))
    assert "create_bank" in logs[0]["text"]
    mem.store_experience("saw a ship", entities=["Ship"])
    mem.flush()
    assert "retain failed (1 items)" in logs[-1]["message"]
    recalled = mem.recall_for(["Ship"], "ship")
    assert recalled["episodes"][0]["text"] == "saw a ship" and "recall failed" in logs[-1]["message"]


def test_hindsight_default_log(tmp_path, hindsight):
    mem = memory_hindsight.HindsightMemory(tmp_path, "http://h", "bank")
    mem.log(kind="x")  # the default log takes anything
    assert memory_hindsight._get({"a": 1}, "a") == 1 and memory_hindsight._get(object(), "a", 2) == 2


# Lessons from the 2026-11-08 run (run-live/memory/episodes.jsonl), written before ADR-026 changed the world.
STALE = ["Logs wash up on far beaches: Log_8 (55, 152), Log_12 (-22, 170). Only worth the walk if the near palms fail.",
         "Logs wash up on the sand near (-60,-2); Log_54 and Log_55 appeared overnight, so I can get logs without an axe.",
         "Felling a palm takes 4 strikes with the axe and leaves 2 logs plus a stump.",
         "Palm_36 at (-60,-2) took three axe strikes; the fourth fells it and leaves two logs and a stump.",
         "Fell palms for two logs each (four axe strikes) and take fallen coconuts.",
         "Driftwood is the easiest wood."]
STILL_TRUE = ["A log washed up on the west beach at (-120.4, 2.11, -38.1); lifting it gives a three-block beam.",
              "Laid flat a log covers three cells in a line, so two logs cover a four-cell row.",
              "At dawn two logs and one dark stone fell from the sky near the house: Log_56 (-82,-38)."]


def test_lessons_the_world_made_untrue_are_retired_once(tmp_path):
    """ADR-026: no log washes up any more, and the axe fells a palm into one log. A run resumed on memory from before
    never recalls the lessons that say otherwise; history (a log that did wash up) and other truths are kept, and a
    lesson learnt afterwards is never retired, even if it reads like an old one."""
    root = tmp_path / "m"
    old = NativeMemory(root)
    for text in STALE + STILL_TRUE:
        old.note(text, about="logs")
    old.store_experience("Project 'know the shore and where logs wash up' did not finish.", kind="project")
    old.state.pop("retired", None)  # as memory written before ADR-026 has it
    old.save()
    mem = NativeMemory(root)
    lessons = {ep["text"]: ep for ep in mem.episodes if ep["kind"] == "lesson"}
    for text in STALE:
        assert lessons[text]["invalid"].startswith("untrue since ADR-026"), text
    for text in STILL_TRUE:
        assert not lessons[text].get("invalid"), text
    assert not mem.episodes[-1].get("invalid"), "a project is what happened, not a lesson"
    recalled = [ep["text"] for ep in mem.retrieve(text="logs wash up palm axe two logs", limit=20)]
    assert not set(STALE) & set(recalled) and set(STILL_TRUE) <= set(recalled)
    assert "adr-026-logs" in json.loads((root / "state.json").read_text())["retired"]
    mem.note("Lightning felled Palm_3 into two logs.", about="logs")  # still true: lightning splits a palm
    again = NativeMemory(root)
    assert not again.episodes[-1].get("invalid"), "retired once, not every start"
    assert sum(bool(ep.get("invalid")) for ep in again.episodes) == len(STALE)


def test_a_fresh_memory_has_nothing_to_retire(tmp_path):
    mem = NativeMemory(tmp_path / "m")
    mem.note("Felling a palm with the axe gives one log, and lightning splits one into two logs.")
    assert not NativeMemory(tmp_path / "m").episodes[0].get("invalid")


def test_brain_memory_retires_facts_too(tmp_path):
    root = tmp_path / "m"
    (root).mkdir()
    (root / "facts.json").write_text(json.dumps({"logs": [
        {"text": STALE[2], "seen": 3, "first_tick": 1, "last_tick": 9},
        {"text": STILL_TRUE[1], "seen": 1, "first_tick": 2, "last_tick": 2}]}))
    mem = BrainMemory(root)
    assert [f["text"] for f in mem.facts["logs"]] == [STILL_TRUE[1]]
    assert [f["text"] for f in json.loads((root / "facts.json").read_text())["logs"]] == [STILL_TRUE[1]]
