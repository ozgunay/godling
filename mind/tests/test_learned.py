import json

import pytest

from godling import skills as sk
from godling.learned import SkillError, SkillLibrary
from godling.skills import Skills
from helpers import block, ground
from island import FakeTime, Island


@pytest.fixture
def setup(monkeypatch, tmp_path):
    island = Island([ground(), block("Block_1", 5, 1.25, 0), block("Block_2", 5, 3.75, 0), block("Block_3", -8, 1.25, 0),
                     block("Stone_1", 0, 1.25, 9)])
    monkeypatch.setattr(sk, "time", FakeTime(island))
    logs = []
    library = SkillLibrary(tmp_path / "skills.json", log=lambda **k: logs.append(k))
    body = Skills(island, library=library, log=lambda **k: logs.append(k))
    return island, body, library, logs


def test_define_and_describe(setup, tmp_path):
    _, _, library, logs = setup
    assert library.describe() == ""
    spec = {"name": "fetch", "params": ["object"], "does": "x" * 300,
            "steps": [{"skill": "pick_up", "args": {"object": "$object"}}]}
    assert library.define(spec, tick=4) == "fetch"
    assert library.skills["fetch"]["status"] == "unproven" and len(library.skills["fetch"]["does"]) == 200
    assert logs[-1]["kind"] == "learn" and logs[-1]["version"] == 1
    library.define(spec)
    assert library.skills["fetch"]["version"] == 2
    assert library.describe().startswith("- fetch(object) [unproven, never run yet]:")
    assert json.loads((tmp_path / "skills.json").read_text())["fetch"]["version"] == 2
    assert SkillLibrary(tmp_path / "skills.json").skills["fetch"]["version"] == 2


@pytest.mark.parametrize("spec,why", [
    ({"name": "not a name", "steps": [{"skill": "jump"}]}, "not a usable skill name"),
    ({"name": "jump", "steps": [{"skill": "jump"}]}, "not a usable skill name"),
    ({"name": "empty", "steps": []}, "needs 1-12 steps"),
    ({"name": "long", "steps": [{"skill": "jump"}] * 13}, "needs 1-12 steps"),
    ({"name": "odd", "steps": [{"skill": "fly"}]}, "unknown skill 'fly'"),
])
def test_define_rejects(setup, spec, why):
    _, _, library, _ = setup
    with pytest.raises(SkillError, match=why):
        library.define(spec)


def test_define_rejects_self_calls(setup):
    _, _, library, _ = setup
    library.define({"name": "loop", "steps": [{"skill": "jump"}]})
    with pytest.raises(SkillError, match="cannot call itself"):
        library.define({"name": "loop", "steps": [{"skill": "loop"}]})


def test_forget_and_protection(tmp_path):
    logs = []
    library = SkillLibrary(tmp_path / "s.json", log=lambda **k: logs.append(k), protect_proven=True)
    assert library.forget("nothing") is None
    library.define({"name": "good", "steps": [{"skill": "jump"}]})
    library.skills["good"].update(successes=3, uses=4, recent=[True, False, True])
    refusal = library.forget("good")
    assert refusal.startswith("'good' was kept: it has worked 3 of 4 times") and logs[-1]["kind"] == "forget_refused"
    library.skills["good"]["recent"] = [False, False, False]
    assert library.forget("good") is None and "good" not in library.skills and logs[-1]["kind"] == "forget"
    plain = SkillLibrary(tmp_path / "t.json")
    plain.define({"name": "x", "steps": [{"skill": "jump"}]})
    plain.skills["x"]["successes"] = 9
    assert plain.forget("x") is None
    plain.log(kind="y")  # the default log takes anything


def test_execute_runs_steps_with_helpers(setup):
    island, body, library, logs = setup
    library.define({"name": "stack_it", "params": ["object"], "steps": [
        {"skill": "pick_up", "args": {"object": "$object"}},
        {"skill": "place_at", "args": {"x": {"x": {"top": "Block_1"}}, "y": {"add": [{"y": {"top": "Block_1"}}, 1.31]},
                                       "z": {"z": {"pos": "Block_1"}}}},
        {"skill": "jump", "args": {}, "repeat": 2}]})
    r = body.run("stack_it", {"object": "Block_3"})
    assert r.ok and r.summary.startswith("stack_it worked: pick_up: picked up Block_3 | place_at: Block_3 came to rest")
    assert r.facts == {"learned": True}
    spec = library.skills["stack_it"]
    assert spec["status"] == "proven" and spec["uses"] == 1 and spec["successes"] == 1 and spec["recent"] == [True]
    assert island.ents["Block_3"]["position"][1] == pytest.approx(6.31)  # on Block_2, the stack's top
    assert island.actions().count("Jump") == 2
    assert body.busy == set() and body._depth == 0
    assert any(l.get("learned") for l in logs if l["kind"] == "skill")
    assert library.describe().startswith("- stack_it(object) [proven, 1/1 runs succeeded]")


def test_execute_failures(setup):
    island, body, library, _ = setup
    library.define({"name": "fetch", "params": ["object"], "steps": [{"skill": "pick_up", "args": {"object": "$object"}}]})
    assert body.run("fetch", {}).summary == "missing arguments: object"
    r = body.run("fetch", {"object": "Nothing"})
    assert not r.ok and r.summary == "fetch failed: pick_up: there is no movable object called Nothing"
    library.define({"name": "bad", "steps": [{"skill": "jump", "args": {"x": "$nope"}}]})
    r = body.run("bad", {})
    assert not r.ok and "could not work out arguments (unknown parameter $nope)" in r.summary


def test_helpers(setup):
    island, body, library, _ = setup
    resolve = library.resolve_helpers
    assert resolve({"a": {"pos": "Block_1"}}, body) == {"a": [5, 1.25, 0]}
    assert resolve({"a": {"top": "Block_1"}}, body) == {"a": [5, 5.0, 0]}
    assert resolve({"a": {"add": [[1, 2], [3, 4]]}}, body) == {"a": [4.0, 6.0]}
    assert resolve({"a": {"add": [1, 2]}}, body) == {"a": 3.0}
    assert resolve({"a": [{"y": {"pos": "Block_2"}}, 7]}, body) == {"a": [3.75, 7]}
    assert resolve({"a": {"nearest_free": "cube"}}, body) == {"a": "Block_2"}  # Block_1 lies under Block_2
    assert resolve({"a": {"nearest_free": "stone"}}, body) == {"a": "Stone_1"}
    assert resolve({"a": {"two": 1, "keys": 2}}, body) == {"a": {"two": 1, "keys": 2}}
    for bad, why in (({"pos": "Nothing"}, "no object"), ({"top": "Nothing"}, "no object"),
                     ({"add": [[1], [1, 2]]}, "add needs two numbers"),
                     ({"nearest_free": "cheese"}, "nearest_free looks for one of"),
                     ({"nearest_free": "log"}, "no free log left")):
        with pytest.raises(SkillError, match=why):
            resolve({"a": bad}, body)


def test_run_resolves_helpers_in_plain_steps(setup):
    island, body, library, _ = setup
    r = body.run("pick_up", {"object": {"nearest_free": "stone"}})
    assert r.ok and island.held == "Stone_1"
