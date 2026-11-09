"""compare_runs.py, stack_timeline.py, god_bot.py and render_default_prompt.py: scripts, run as scripts."""
import json
import os
import re
import runpy
import sys
import types
from pathlib import Path

import pytest

from runs import cube, recording, standard_mind_log, standard_recording

TOOLS = Path(__file__).resolve().parents[1]


def run_script(name, monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", [name, *map(str, args)])
    monkeypatch.syspath_prepend(str(TOOLS))
    return runpy.run_path(str(TOOLS / name), run_name="__main__")


# ---- stack_timeline ---------------------------------------------------------------------------------------------
def test_stack_timeline(tmp_path, monkeypatch, capsys):
    run = tmp_path / "a-003"
    standard_recording(run)
    script = run_script("stack_timeline.py", monkeypatch, run)
    out = capsys.readouterr().out
    assert "=== a-003: " in out and "peak stack: 3 cubes" in out and "tallest" in out
    points = script["timeline"](run)
    assert points[0][1:] == (1, 0, 2) and max(p[1] for p in points) == 3
    assert script["tallest_stack"]([]) == (0, 0)
    assert script["cubes"]({"entities": [cube(0, 0, 0), cube(1, 1, 1, size=2)]}) == [[0, 0, 0]]


def test_stack_timeline_needs_a_decoder(tmp_path, monkeypatch):
    run = tmp_path / "r"
    standard_recording(run)
    script = run_script("stack_timeline.py", monkeypatch)  # no runs: nothing printed
    script["timeline"].__globals__["zstd_decoder"] = lambda: None
    with pytest.raises(SystemExit, match="needs a zstd decoder"):
        script["timeline"](run)


# ---- compare_runs ---------------------------------------------------------------------------------------------------
def compare_run(path, config=True, hindsight=False, mind=True):
    standard_recording(path)
    standard_mind_log(path, with_projects=mind)
    if config:
        (path / "config.json").write_text(json.dumps({"memory": "native2", "agenda": "True", "walk_speed": "5"}))
    if hindsight:
        (path / "hindsight.log").write_text(
            f"bank=godling-{path.name} llm_batch size=3 input_tokens=~1000\n"
            "llm call: scope=retain_extract_facts, input_tokens=500, output_tokens=100, total_tokens=600, cached_tokens=200\n"
            "llm call: scope=consolidate, input_tokens=300, output_tokens=50, total_tokens=350\n")
    return path


def test_compare_runs(tmp_path, monkeypatch, capsys):
    a = compare_run(tmp_path / "m-003", hindsight=True)
    b = compare_run(tmp_path / "m-004", config=False)
    run_script("compare_runs.py", monkeypatch, a, b)
    out = capsys.readouterr().out
    rows = {line.split("|")[0].strip(): [c.strip() for c in line.split("|")[1:]] for line in out.splitlines() if "|" in line}
    assert rows["setup"] == ["native2, agenda=True, walk=5", "native, agenda=False, walk=16"]
    assert rows["walls / enclosures / roofed"][0] == "2 / 1 / 1" and rows["pieces built in, by hour"][0] == "3 7"
    assert rows["+ memory engine $/h (est.)"][1] == "-" and rows["+ memory engine $/h (est.)"][0] != "-"
    assert rows["tallest stack"][0] == "3" and rows["placements by hour"][0]


def test_compare_runs_cuts_every_arm_to_the_same_minute(tmp_path, monkeypatch, capsys):
    """Review of #80 (80-AB11): `--minute 30` compares the arms at their 30th minute; rows from the recording that are
    not cut say so."""
    a = compare_run(tmp_path / "m-030")
    run_script("compare_runs.py", monkeypatch, "--minute", 30, a)
    rows = {line.split("|")[0].strip(): [c.strip() for c in line.split("|")[1:]]
            for line in capsys.readouterr().out.splitlines() if "|" in line}
    assert rows["minutes"] == ["30"] and rows["pieces built in, by hour"] == ["3"] and rows["placements by hour"] == ["7"]
    assert "tallest stack (whole run)" in rows and "first projects finished (after stop-gaps)" in rows
    assert rows["cost $/h by purpose"][0].startswith("decide ")


def test_compare_runs_without_measures(tmp_path, monkeypatch):
    run = tmp_path / "plain"
    standard_recording(run)
    from runs import mind_log
    mind_log(run, [{"time": 0, "kind": "decision", "projects": []}, {"time": 10, "kind": "skill", "skill": "wait",
                                                                      "ok": True, "seconds": 1}])
    (run / "hindsight.log").write_text("nothing logged\n")
    script = run_script("compare_runs.py", monkeypatch, run)
    row = script["stats"](run)
    assert row["walls / enclosures / roofed"] == "n/a" and row["waited for mind"] == "n/a"
    assert row["reasoning tokens/decision"] == "n/a" and row["steps planned/decision"] == "0.0"


# ---- god_bot -------------------------------------------------------------------------------------------------------
def test_god_bot(tmp_path, monkeypatch, capsys):
    calls = []
    answers = iter(["SkyRefused:NoStump", "SkyRefused:NoClearSpot", "SkyRefused:NoSafePalm",  # three tries, then on
                    "SkyDone:Meteor:2", "SkyFailed:World:down"])

    class FakeSky:
        def __init__(self, world):
            self.world = world

        def call(self, power):
            calls.append(power)
            return next(answers)
    clock = [1000.0]
    fake_time = types.SimpleNamespace(time=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0] + s),
                                      strftime=lambda f: "12:00:00")
    import guest_panel
    monkeypatch.setattr(guest_panel, "Sky", FakeSky)
    monkeypatch.setitem(sys.modules, "time", fake_time)  # the script imports time when it runs
    log = tmp_path / "god_bot.jsonl"
    try:
        run_script("god_bot.py", monkeypatch, "--world", "http://w", "--every", "30-30", "--first", "1", "--hours",
                   "1.2", "--log", log)
    finally:
        monkeypatch.delitem(sys.modules, "time")
        import importlib
        sys.modules["time"] = importlib.import_module("time") if "time" not in sys.modules else sys.modules["time"]
    out = capsys.readouterr().out
    assert "God bot: first event in 1 min, then every 30-30 min, for 1.2 h." in out
    assert re.search(r"GOD  [A-Za-z ]+ #2: ", out) and "GOD? " in out  # whichever power got the world's yes
    lines = [json.loads(l) for l in log.read_text().splitlines()]
    assert len(lines) == 5 and len(set(calls[:3])) == 3  # each try a different power
    assert lines[-1]["result"] == "SkyFailed:World:down"


def test_god_bot_without_a_log(monkeypatch, capsys, tmp_path):
    import guest_panel
    (tmp_path / "world.key").write_text("agent\n")
    monkeypatch.setenv("WORLD_AGENT_KEY", "")

    class FakeSky:
        def __init__(self, world):
            pass

        def call(self, power):
            return "SkyDone:Stone:1"
    monkeypatch.setattr(guest_panel, "Sky", FakeSky)
    clock = [0.0]
    monkeypatch.setitem(sys.modules, "time", types.SimpleNamespace(
        time=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0] + s), strftime=lambda f: "x"))
    try:
        run_script("god_bot.py", monkeypatch, "--first", "0", "--every", "10-20", "--hours", "0.5",
                   "--run-dir", str(tmp_path))
    finally:
        monkeypatch.delitem(sys.modules, "time")
    assert capsys.readouterr().out.count("GOD  ") >= 1
    assert os.environ["WORLD_AGENT_KEY"] == "agent"  # the run's world.key, to join with


# ---- render_default_prompt -----------------------------------------------------------------------------------------------
def test_render_default_prompt(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "clawblox"
    (repo / "src").mkdir(parents=True)
    (repo / "src/agent_runner.rs").write_text(
        'const DEFAULT_SYSTEM_PROMPT: &str = r#"You are ${WORLD_AGENT_NAME}. ${SESSION_LINE}. Docs: ${SKILL_CURL} '
        '${SKILL_URL}. Work in ${WORKSPACE_DIR} at ${WORLD_BASE_URL}."#;\n')
    out = tmp_path / "out" / "prompt.md"
    run_script("render_default_prompt.py", monkeypatch, repo, out, 8090, "Godling")
    text = out.read_text()
    assert text.startswith("You are Godling. Join the world with: curl -s -X POST 'http://localhost:8090/join?name=Godling'")
    assert "${" not in text and "wrote " in capsys.readouterr().out


def test_render_default_prompt_leftovers(tmp_path, monkeypatch):
    repo = tmp_path / "clawblox"
    (repo / "src").mkdir(parents=True)
    (repo / "src/agent_runner.rs").write_text('DEFAULT_SYSTEM_PROMPT: &str = r#"${WORLD_AGENT_NAME} ${UNKNOWN}"#;')
    with pytest.raises(KeyError):
        run_script("render_default_prompt.py", monkeypatch, repo, tmp_path / "p.md", 1, "x")


def test_render_default_prompt_refuses_what_it_cannot_fill(tmp_path, monkeypatch):
    repo = tmp_path / "clawblox"
    (repo / "src").mkdir(parents=True)
    (repo / "src/agent_runner.rs").write_text('DEFAULT_SYSTEM_PROMPT: &str = r#"I am ${WORLD_AGENT_NAME}."#;')
    with pytest.raises(SystemExit, match=r"unrendered placeholders: \['\$\{NAME\}'\]"):
        run_script("render_default_prompt.py", monkeypatch, repo, tmp_path / "p.md", 1, "${NAME}")
