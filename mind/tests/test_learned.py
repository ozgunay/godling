import json
import types

import pytest

from godling import learned
from godling import skills as sk
from godling.learned import SkillError, SkillLibrary
from godling.skills import Interrupted, Skills, Stuck
from helpers import block, ground
from island import FakeTime, Island
from run_live_skills import (BEAM_Z_ON_STEP, CUBE_STEP_AT, MEND_AT_HOME, POST_AND_FASTEN, TOP_WEST_TOWER,
                             UPRIGHT_NAMED_LOG)

FORGET_WHEN_IDLE = 2 * 3600  # ADR-032 after the review of #75 (learned.FORGET_WHEN_IDLE)


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
    library.define({**spec, "steps": spec["steps"] * 2})  # other steps for a skill that never ran
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
    library.skills["good"].update(successes=3, uses=4)
    refusal = library.forget("good")
    assert refusal.startswith("'good' was kept: it has worked 3 of 4 times") and logs[-1]["kind"] == "forget_refused"
    library.skills["good"]["fails_in_a_row"] = 3
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
                       "A skill that has worked is forgotten only after 71 failed runs in a row, or after 2 hours "
                       "without working. To try other steps, teach them under a new name.")
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
    assert f"and {since}. A skill that has worked is forgotten only after 3 failed runs in a row, or" in refusal


@pytest.mark.parametrize("name,record,needed", [("cube_step_at", CUBE_STEP_AT, 10),
                                                ("upright_named_log", UPRIGHT_NAMED_LOG, 19)])
def test_a_well_proven_skill_outlasts_a_streak_that_would_drop_a_weak_one(tmp_path, name, record, needed):
    # In the final library: worked 10 (19) times, then its last five runs failed. Five such failures are not enough.
    library, logs = library_of(tmp_path, **{name: record})
    assert library.forget(name).startswith(f"'{name}' was kept: it has worked {record['successes']} of "
                                           f"{record['uses']} times and at least its last 5 runs failed.")
    assert logs[-1]["needed"] == needed
    library.skills[name]["fails_in_a_row"] = needed  # as many failures in a row as it ever worked
    assert library.forget(name) is None and name not in library.skills and logs[-1] == {"kind": "forget", "name": name}


@pytest.mark.parametrize("record", [
    # 2 of 11, then 8 failures (not counting one interruption), in a record written by this code
    {**{k: v for k, v in POST_AND_FASTEN.items() if k != "recent"}, "fails_in_a_row": 8},
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
    assert "recent" not in spec and spec["fails_in_a_row"] == 6
    assert json.loads((tmp_path / "skills.json").read_text())["greet"]["fails_in_a_row"] == 6
    assert library.forget("greet").startswith("'greet' was kept: it has worked 7 of 16 times and only its last 6 runs")
    assert not body.run("greet", {"who": "Nothing"}).ok
    assert library.forget("greet") is None and "greet" not in library.skills


def test_a_record_saved_before_the_count_goes_on_from_its_last_five(setup, tmp_path):
    _, body, _, _ = setup
    body.library, _ = library_of(tmp_path, greet={
        "params": ["who"], "steps": [{"skill": "say", "args": {"text": {"pos": "$who"}}}], "does": "",
        "status": "proven", "uses": 2, "successes": 1, "recent": [True, False]})
    assert not body.run("greet", {"who": "Nothing"}).ok
    assert body.library.skills["greet"]["fails_in_a_row"] == 2 and "recent" not in body.library.skills["greet"]
    assert body.library.forget("greet").startswith("'greet' was kept: it has worked 1 of 3 times and only its last 2")


# ---- the review of #75 ---------------------------------------------------------------------------------------
@pytest.fixture
def clock(monkeypatch):
    now = [10_000.0]
    monkeypatch.setattr(learned, "time", types.SimpleNamespace(time=lambda: now[0]))
    return now


def test_a_skill_that_has_not_worked_for_two_hours_can_go(tmp_path, clock):
    # 75-AB1: top_west_tower worked once and was never run again, so no failure would ever let it go.
    library, _ = library_of(tmp_path, top_west_tower={**TOP_WEST_TOWER, "worked_at": 0.0})
    assert "after 2 hours without working" in library.forget("top_west_tower")  # its two hours start at the load
    clock[0] += FORGET_WHEN_IDLE - 1
    assert library.forget("top_west_tower") is not None
    clock[0] += 1
    assert library.forget("top_west_tower") is None and "top_west_tower" not in library.skills


def test_each_success_starts_the_two_hours_again(clock, setup):  # the clock first: the library notes its load time
    island, body, library, _ = setup
    library.define({"name": "hop", "steps": [{"skill": "jump"}]})
    assert body.run("hop", {}).ok
    clock[0] += FORGET_WHEN_IDLE - 1
    assert body.run("hop", {}).ok and library.skills["hop"]["worked_at"] == clock[0]
    clock[0] += FORGET_WHEN_IDLE - 1
    assert library.forget("hop") is not None
    clock[0] += 1
    assert library.forget("hop") is None


def test_an_interruption_says_nothing_about_the_skill(setup):
    # 75-AB2: 4 of mend_at_home's 10 failures in the live run were attention cutting it short (a ship, a quake, death).
    island, body, library, _ = setup
    library.define({"name": "hop", "steps": [{"skill": "jump"}]})
    library.define({"name": "hop_twice", "steps": [{"skill": "hop"}, {"skill": "hop"}]})
    assert body.run("hop", {}).ok
    island.errors["Jump"] = Interrupted("A ship is passing far out at sea")
    for _ in range(3):
        r = body.run("hop", {})
        assert not r.ok and r.facts == {"learned": True, "interrupted": True}
        assert r.summary == "hop was interrupted: jump: interrupted: A ship is passing far out at sea"
    r = body.run("hop_twice", {})
    assert not r.ok and r.facts["interrupted"] and "interrupted:" in r.summary  # the launcher's test still holds
    assert [library.skills[n]["uses"] for n in ("hop", "hop_twice")] == [1, 0]
    assert library.skills["hop"]["fails_in_a_row"] == 0 and library.forget("hop") is not None
    island.errors["Jump"] = Stuck("snagged on a log")  # the body's own trouble is a failure like any other
    assert not body.run("hop", {}).ok and library.skills["hop"]["fails_in_a_row"] == 1


def test_a_run_that_breaks_counts_as_a_failure(setup):
    # 75-AB8: the world failing under a helper raised out of the run, which then went uncounted.
    island, body, library, _ = setup
    library.define({"name": "look", "steps": [{"skill": "say", "args": {"text": {"pos": "Block_1"}}}]})
    assert body.run("look", {}).ok
    island.fail_observe = 50
    r = body.run("look", {})
    island.fail_observe = 0
    assert not r.ok and r.summary == "look broke while running (observe failed); fix or forget it"
    spec = library.skills["look"]
    assert (spec["uses"], spec["successes"], spec["fails_in_a_row"]) == (2, 1, 1)
    assert "and only its last run failed" in library.forget("look")


def test_teaching_the_same_steps_again_keeps_the_record(tmp_path):
    # 75-CDE1: re-learning a skill as it is used to wipe its record, and the next forget then went through.
    library, logs = library_of(tmp_path, mend_at_home=MEND_AT_HOME)
    library.define({"name": "mend_at_home", "steps": MEND_AT_HOME["steps"], "does": "goes in and mends"})
    spec = library.skills["mend_at_home"]
    assert (spec["successes"], spec["uses"], spec["status"], spec["version"]) == (71, 81, "proven", 1)
    assert spec["does"] == "goes in and mends" and logs[-1]["kind"] == "learn"
    assert library.forget("mend_at_home") is not None


def test_a_skill_that_has_worked_keeps_its_steps_until_it_may_go(tmp_path):
    # 75-CDE1: other steps under its name would throw away the steps that worked 71 times.
    library, _ = library_of(tmp_path, mend_at_home=MEND_AT_HOME)
    with pytest.raises(SkillError, match="'mend_at_home' has worked 71 of 81 times, so its steps stay as they are "
                                         "until it has failed 71 runs in a row or gone 2 hours without working: "
                                         "teach the new steps under a new name"):
        library.define({"name": "mend_at_home", "steps": [{"skill": "wait", "args": {"seconds": 30}}]})
    assert library.skills["mend_at_home"]["steps"] == MEND_AT_HOME["steps"]
    assert library.define({"name": "mend_in_shelter", "steps": [{"skill": "wait", "args": {"seconds": 30}}]})
    library.skills["mend_at_home"]["fails_in_a_row"] = 71
    library.define({"name": "mend_at_home", "steps": [{"skill": "wait", "args": {"seconds": 30}}]})
    assert library.skills["mend_at_home"]["status"] == "unproven" and library.skills["mend_at_home"]["version"] == 2


def test_the_refusal_points_to_a_new_name(tmp_path):
    library, _ = library_of(tmp_path, mend_at_home=MEND_AT_HOME)
    assert library.forget("mend_at_home").endswith("To try other steps, teach them under a new name.")


def test_a_skill_whose_inner_skill_is_gone_can_go(tmp_path):
    # 75-CDE2: a composite calling a skill that is no longer there cannot work again, whatever its record.
    inner = {**BEAM_Z_ON_STEP, "uses": 0, "successes": 0, "status": "unproven", "recent": []}
    outer = {**POST_AND_FASTEN, "steps": [{"skill": "inner", "args": {}}], "uses": 12, "successes": 10,
             "recent": [True]}
    library, _ = library_of(tmp_path, inner=inner, outer=outer)
    assert library.forget("outer") is not None
    assert library.forget("inner") is None
    assert library.forget("outer") is None and library.skills == {}


def test_define_rejects_a_cycle_through_another_skill(setup):
    # 75-CDE4: a -> b -> a recursed until RecursionError, adding about 166 failures to each in one run.
    _, _, library, _ = setup
    library.define({"name": "a", "steps": [{"skill": "jump"}]})
    library.define({"name": "b", "steps": [{"skill": "a"}]})
    with pytest.raises(SkillError, match="step uses 'b', which calls 'a': a skill cannot call itself"):
        library.define({"name": "a", "steps": [{"skill": "b"}]})
    assert library.skills["a"]["steps"] == [{"skill": "jump"}]


@pytest.mark.parametrize("record,count,since", [
    # 75-CDE5: older code (a rollback) ran it three more times and they worked, but left the count at 3.
    ({"fails_in_a_row": 3, "recent": [False, False, True, True, True]}, 0, "its last run worked"),
    # ... or it failed twice more under older code, after a count of 1.
    ({"fails_in_a_row": 1, "recent": [False, False]}, 3, "only its last 3 runs failed"),
])
def test_a_count_left_behind_by_older_code_is_counted_again(tmp_path, record, count, since):
    library, _ = library_of(tmp_path, beam_z_on_step={**BEAM_Z_ON_STEP, "uses": 9, "successes": 4, **record})
    assert library.skills["beam_z_on_step"]["fails_in_a_row"] == count
    assert "recent" not in library.skills["beam_z_on_step"]
    assert f"and {since}." in library.forget("beam_z_on_step")


def test_the_last_five_outcomes_are_no_longer_kept(setup, tmp_path):
    # 75-CLEAN1 and 75-CLEAN2: one record of the streak, written from the start.
    _, body, library, _ = setup
    library.define({"name": "hop", "steps": [{"skill": "jump"}]})
    assert library.skills["hop"]["fails_in_a_row"] == 0
    assert body.run("hop", {}).ok
    assert "recent" not in json.loads((tmp_path / "skills.json").read_text())["hop"]


def test_a_count_from_the_last_five_is_told_as_at_least(tmp_path, setup):
    # 75-SWEEP1: cube_step_at had really failed 12 times in a row; its saved record holds only the last 5.
    _, body, _, _ = setup
    library, _ = library_of(tmp_path, cube_step_at=CUBE_STEP_AT)
    assert "and at least its last 5 runs failed." in library.forget("cube_step_at")
    library.skills["cube_step_at"]["steps"] = [{"skill": "jump"}]
    body.library = library
    assert body.run("cube_step_at", {"stand_x": 0, "stand_z": 0}).ok
    library.skills["cube_step_at"]["steps"] = [{"skill": "pick_up", "args": {"object": "Nothing"}}]
    for _ in range(2):
        assert not body.run("cube_step_at", {"stand_x": 0, "stand_z": 0}).ok
    assert "and only its last 2 runs failed." in library.forget("cube_step_at")


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
    assert spec["status"] == "proven" and spec["uses"] == 1 and spec["successes"] == 1 and spec["fails_in_a_row"] == 0
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
