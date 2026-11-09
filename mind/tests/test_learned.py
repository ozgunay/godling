import json

import pytest

from godling import skills as sk
from godling.learned import SkillError, SkillLibrary
from godling.skills import Skills
from helpers import block, ground
from island import FakeTime, Island
from run_live_skills import BEAM_Z_ON_STEP, CUBE_STEP_AT, MEND_AT_HOME, POST_AND_FASTEN, UPRIGHT_NAMED_LOG


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
    library = SkillLibrary(tmp_path / "s.json", log=lambda **k: logs.append(k))
    assert library.forget("nothing") is None
    library.define({"name": "good", "steps": [{"skill": "jump"}]})
    library.skills["good"].update(successes=3, uses=4, recent=[True, False, True])
    refusal = library.forget("good")
    assert refusal.startswith("'good' was kept: it has worked 3 of 4 times") and logs[-1]["kind"] == "forget_refused"
    library.skills["good"]["recent"] = [False, False, False]
    assert library.forget("good") is None and "good" not in library.skills and logs[-1]["kind"] == "forget"
    SkillLibrary(tmp_path / "t.json").log(kind="y")  # the default log takes anything


# ---- forgetting a skill that has worked (ADR-032), with the live run's own records -----------------------------
def library_of(tmp_path, **records):
    """The library as the launcher builds it for every memory engine, over a saved skills.json."""
    (tmp_path / "skills.json").write_text(json.dumps(records))
    logs = []
    return SkillLibrary(tmp_path / "skills.json", log=lambda **k: logs.append(k)), logs


def test_a_proven_skill_with_a_few_failures_is_kept(tmp_path):
    # The live run's native memory forgot mend_at_home at 71 of 81, after two runs its own step log had blocked.
    library, logs = library_of(tmp_path, mend_at_home=MEND_AT_HOME)
    refusal = library.forget("mend_at_home")
    assert "mend_at_home" in library.skills and "mend_at_home" in json.loads((tmp_path / "skills.json").read_text())
    assert refusal == ("'mend_at_home' was kept: it has worked 71 of 81 times and only its last 2 runs failed. "
                       "A skill that has worked is forgotten only after 71 failed runs in a row. "
                       "Redefine it with 'learn' to improve it instead.")
    assert logs[-1] == {"kind": "forget_refused", "name": "mend_at_home", "successes": 71, "uses": 81,
                        "fails_in_a_row": 2, "needed": 71}


@pytest.mark.parametrize("record,since", [
    (BEAM_Z_ON_STEP, "its last run worked"),  # forgotten straight after it had worked
    ({**BEAM_Z_ON_STEP, "uses": 4, "recent": [False, True, True, False]}, "only its last run failed"),
])
def test_a_skill_that_worked_twice_is_kept_until_it_keeps_failing(tmp_path, record, since):
    library, _ = library_of(tmp_path, beam_z_on_step=record)
    refusal = library.forget("beam_z_on_step")
    assert "beam_z_on_step" in library.skills
    assert f"and {since}. A skill that has worked is forgotten only after 3 failed runs in a row." in refusal


@pytest.mark.parametrize("name,record,needed", [("cube_step_at", CUBE_STEP_AT, 10),
                                                ("upright_named_log", UPRIGHT_NAMED_LOG, 19)])
def test_a_well_proven_skill_outlasts_a_streak_that_would_drop_a_weak_one(tmp_path, name, record, needed):
    # In the final library: worked 10 (19) times, then its last five runs failed. Five such failures are not enough.
    library, logs = library_of(tmp_path, **{name: record})
    assert library.forget(name).startswith(f"'{name}' was kept: it has worked {record['successes']} of "
                                           f"{record['uses']} times and only its last 5 runs failed.")
    assert logs[-1]["needed"] == needed
    library.skills[name]["fails_in_a_row"] = needed  # as many failures in a row as it ever worked
    assert library.forget(name) is None and name not in library.skills and logs[-1] == {"kind": "forget", "name": name}


@pytest.mark.parametrize("record", [
    {**POST_AND_FASTEN, "fails_in_a_row": 9},  # 2 of 11, then 9 failures in a row
    {**POST_AND_FASTEN, "uses": 5, "successes": 1, "recent": [True, False, False, False, False]},  # 1 of 5, then 4
    {**POST_AND_FASTEN, "uses": 3, "successes": 0, "status": "unproven", "recent": [False, False, False]},
    {**POST_AND_FASTEN, "uses": 0, "successes": 0, "status": "unproven", "recent": []},
])
def test_a_skill_that_never_worked_or_has_stopped_working_can_go(tmp_path, record):
    library, logs = library_of(tmp_path, post_and_fasten=record)
    assert library.forget("post_and_fasten") is None and "post_and_fasten" not in library.skills
    assert "post_and_fasten" not in json.loads((tmp_path / "skills.json").read_text())
    assert logs[-1] == {"kind": "forget", "name": "post_and_fasten"}


def test_every_run_counts_the_failures_in_a_row_beyond_the_last_five(setup, tmp_path):
    island, body, library, logs = setup
    library.define({"name": "greet", "params": ["who"], "steps": [{"skill": "say", "args": {"text": {"pos": "$who"}}}]})
    for _ in range(6):
        assert body.run("greet", {"who": "Block_1"}).ok
    for _ in range(3):
        assert not body.run("greet", {"who": "Nothing"}).ok
    assert body.run("greet", {"who": "Block_1"}).ok  # one success and the count starts again
    assert library.skills["greet"]["fails_in_a_row"] == 0
    for _ in range(6):
        assert not body.run("greet", {"who": "Nothing"}).ok
    spec = library.skills["greet"]
    assert spec["recent"] == [False] * 5 and spec["fails_in_a_row"] == 6
    assert json.loads((tmp_path / "skills.json").read_text())["greet"]["fails_in_a_row"] == 6
    assert library.forget("greet").startswith("'greet' was kept: it has worked 7 of 16 times and only its last 6 runs")
    assert not body.run("greet", {"who": "Nothing"}).ok
    assert library.forget("greet") is None and "greet" not in library.skills


def test_a_record_saved_before_the_count_goes_on_from_its_last_five(setup):
    island, body, library, _ = setup
    library.skills["greet"] = {"params": ["who"], "steps": [{"skill": "say", "args": {"text": {"pos": "$who"}}}],
                               "does": "", "status": "proven", "uses": 2, "successes": 1, "recent": [True, False]}
    assert not body.run("greet", {"who": "Nothing"}).ok
    assert library.skills["greet"]["fails_in_a_row"] == 2 and library.skills["greet"]["recent"] == [True, False, False]
    assert library.forget("greet").startswith("'greet' was kept: it has worked 1 of 3 times and only its last 2 runs")


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
