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
