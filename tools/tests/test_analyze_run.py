import builtins
import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

import analyze_run as ar
from runs import standard_mind_log, standard_recording, mind_log, recording, body

TOOLS = Path(ar.__file__).resolve().parent


def test_numbers():
    assert ar.pct([], 50) is None
    assert ar.pct([1, 2, 3, 4], 50) == 2.5 and ar.pct([5], 95) == 5
    assert ar.fmt_s(None) == "n/a" and ar.fmt_s(3.25) == "3.2s" and ar.fmt_s(600) == "10.0min"
    assert ar.parse_ts("2026-11-01T10:00:00Z") == ar.parse_ts("2026-11-01T10:00:00+00:00")


def test_zstd_decoders(monkeypatch):
    real_import = builtins.__import__

    def without(*names):
        def fake(name, *a, **kw):
            if name in names:
                raise ImportError(name)
            return real_import(name, *a, **kw)
        return fake
    assert ar.zstd_decoder() is not None
    monkeypatch.setattr(builtins, "__import__", without("compression", "zstandard"))
    monkeypatch.setattr(ar.shutil, "which", lambda name: None)
    assert ar.zstd_decoder() is None
    monkeypatch.setattr(ar.shutil, "which", lambda name: "/usr/bin/zstd")
    runs = []
    monkeypatch.setattr(ar.subprocess, "run", lambda *a, **kw: runs.append((a, kw)) or
                        subprocess.CompletedProcess(a, 0, stdout=b"plain"))
    assert ar.zstd_decoder()(b"blob") == b"plain" and runs[0][1]["input"] == b"blob"
    import types
    fake_zstandard = types.ModuleType("zstandard")

    class Decompressor:
        def decompress(self, blob, max_output_size=0):
            return b"z:" + blob
    fake_zstandard.ZstdDecompressor = Decompressor
    monkeypatch.setitem(sys.modules, "zstandard", fake_zstandard)
    monkeypatch.setattr(builtins, "__import__", without("compression"))
    assert ar.zstd_decoder()(b"x") == b"z:x"
    fake_compression = types.ModuleType("compression")  # Python 3.14's own, here on any Python
    fake_compression.zstd = types.SimpleNamespace(decompress=lambda blob: b"c:" + blob)
    monkeypatch.setitem(sys.modules, "compression", fake_compression)
    monkeypatch.setattr(builtins, "__import__", real_import)
    assert ar.zstd_decoder()(b"x") == b"c:x"


def test_recording_and_motion(tmp_path, monkeypatch):
    rec = standard_recording(tmp_path)
    out = ar.analyze_recording(rec)
    assert out["tick_rate"] == 30 and len(out["inputs"]) == 40 and out["duration_s"] == 130
    motion = out["motion"]
    assert motion["sampled_s"] == 96 and motion["duty_cycle"] == 0.5  # one body walked, the other stood
    assert set(motion["result_changes"]) == {"PlaceSuccess", "PickupSuccess"}
    monkeypatch.setattr(ar, "zstd_decoder", lambda: None)
    assert ar.analyze_recording(rec)["motion"] is None
    assert ar.motion_from_samples([]) == {"duty_cycle": None, "sampled_s": 0.0, "result_changes": {}}


def transcript(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines) + "\n")
    return path


def agent_run(run):
    agent = run / "agent"
    act = {"type": "tool_use", "id": "t1", "name": "Bash",
           "input": {"command": 'curl -X POST /input -d \'{"type":"MoveTo"}\' ; curl /input -d \'{"type":"Jump"}\''}}
    lines = [
        {"type": "user", "timestamp": "2026-11-01T10:00:00Z", "message": {"content": "start"}},
        {"type": "assistant", "timestamp": "2026-11-01T10:00:05Z",
         "message": {"id": "m1", "model": "claude-opus-4-5", "content": [act],
                     "usage": {"input_tokens": 100, "cache_creation_input_tokens": 50, "cache_read_input_tokens": 1000,
                               "output_tokens": 20}}},
        {"type": "assistant", "timestamp": "2026-11-01T10:00:06Z",
         "message": {"id": "m1", "model": "claude-opus-4-5", "content": [
             {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "curl /observe/image"}},
             {"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "curl /chat"}},
             {"type": "tool_use", "id": "t4", "name": "Bash", "input": {"command": "python3 -c 'act(1)'"}},
             {"type": "tool_use", "id": "t5", "name": "Bash", "input": {"command": "ls"}},
             {"type": "tool_use", "id": "t6", "name": "Read", "input": {}},
             {"type": "tool_use", "id": "t7", "name": "WebFetch", "input": {}}]}},
        {"type": "user", "timestamp": "2026-11-01T10:00:10Z", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": 'LastActionResult: "Moving"'}]},
            {"type": "tool_result", "tool_use_id": "t2", "content": "LastActionResult: Ready"},
            {"type": "tool_result", "tool_use_id": "t1", "content": None}]}},
        {"type": "assistant", "timestamp": "2026-11-01T10:00:30Z",
         "message": {"id": "m2", "model": "<synthetic>", "content": "x", "usage": {"input_tokens": 9}}},
        {"type": "assistant", "timestamp": "2026-11-01T10:01:00Z", "uuid": "u3",
         "message": {"model": "mystery-model", "usage": {"input_tokens": 9}}},
        {"type": "system", "timestamp": "2026-11-01T10:02:00Z", "content": ar.AUTO_CONTINUE},
        {"type": "attachment", "attachment": {"type": "prompt_snapshot"}, "text": ar.AUTO_CONTINUE},
        {"type": "assistant"},  # no timestamp
        "not json",
    ]
    transcript(agent / "sandbox-home" / "s1.jsonl", lines)
    transcript(agent / "session" / "s1.jsonl", lines[:2])  # a smaller copy of the same transcript
    transcript(agent / "events.jsonl", [{"type": "x"}])
    transcript(agent / "EPISODIC_x.jsonl", [{"type": "x"}])
    transcript(agent / "other.jsonl", [{"nothing": 1}])
    transcript(agent / "workspace" / "notes.jsonl", [{"type": "x"}])
    (agent / "workspace" / "MEMORY.md").write_text("m" * 400)
    return agent


def test_transcripts(tmp_path):
    agent = agent_run(tmp_path)
    paths = ar.find_transcripts(agent)
    assert [p.parent.name for p in paths] == ["sandbox-home"]
    out = ar.analyze_transcripts(paths)
    assert out["calls"] == 3 and out["models"]["claude-opus-4-5"] == 1 and out["continues"] == 1
    assert out["tools"] == {"world:act": 1, "world:look": 1, "world:observe": 1, "world:script": 1, "workspace": 2,
                            "other": 1}
    assert out["actions_in_commands"] == 2 and out["act_commands"] == 1
    assert out["results"] == {"Moving": 1}
    assert out["think"] == [5.0, 20.0] and out["span_s"] == 60
    assert out["cost"] is None  # one model has no price
    ar.ARGS.price_key = "deepseek"
    try:
        assert ar.analyze_transcripts(paths)["cost"] > 0
    finally:
        ar.ARGS.price_key = None
    assert ar.tool_result_text({"content": [{"text": "a"}, "junk", {"text": "b"}]}) == "a b"


def test_find_transcripts_skips_unreadable(tmp_path, monkeypatch):
    agent = tmp_path / "agent"
    transcript(agent / "a.jsonl", [{"type": "user"}])
    real_open = Path.open
    monkeypatch.setattr(Path, "open", lambda self, *a, **kw: (_ for _ in ()).throw(OSError("locked"))
                        if self.name == "a.jsonl" else real_open(self, *a, **kw))
    assert ar.find_transcripts(agent) == []


def test_mind_log_reactions_and_quakes(tmp_path):
    log = standard_mind_log(tmp_path)
    m = ar.analyze_mind_log(log)
    assert m["calls"] == 2 and m["purposes"] == {"decide": 1, "sleep": 1} and m["cut_off"] == 1
    assert m["projects"] == 2 and m["projects_ok"] == 1 and m["busy_s"] == 70 and m["waited_s"] == 30
    assert m["planned_steps"] == [1, 2] and m["reasoning"] == [400] and m["skills"]["pick_up"] == (1, 1)
    lines = "\n".join(ar.mind_report(m))
    assert "Model calls: 2" in lines and "Reasoning tokens per decision: avg 400" in lines
    old = ar.analyze_mind_log(standard_mind_log(tmp_path / "old", with_projects=False))
    assert old["projects"] == 2 and old["busy_s"] == 7  # the learned skill and the pick-up, not the wait
    assert "not logged" in "\n".join(ar.mind_report({**old, "reasoning": []}))
    world = tmp_path / "world.log"
    assert ar.analyze_quakes(log, world) is None
    r = ar.analyze_reactions(log, world)
    assert r["applied"] == 3 and r["world_applied"] is None and r["noticed"] == 1 and r["engaged"] == 1
    world.write_text("SKY Meteor #1 landed\nSKY Meteor #1 again\nSKY Lightning #2 struck\n"
                     "SKY Earthquake #3 over: woke 9, moved 4, fell 2\nSKY Earthquake #4 over: woke 1, moved 0, fell 0\n"
                     "QUAKE knocked Godling down\n")
    r = ar.analyze_reactions(log, world)
    assert r["world_applied"] == 4
    text = "\n".join(ar.reaction_report(r))
    assert "the world log shows 4" in text and "first glance p50 1.0s" in text
    q = ar.analyze_quakes(log, world)
    assert q["quakes"][3] == {"woke": 9, "moved": 4, "fell": 2, "braced_after_s": 2}
    assert q["quakes"][4]["braced_after_s"] is None and q["knockdowns"] == 1
    table = "\n".join(ar.quake_report(q))
    assert "| 3 | 9 | 4 | 2 | 2.0s |" in table and "| 4 | 1 | 0 | 0 | not braced |" in table
    assert ar.analyze_quakes(tmp_path / "none.jsonl", world)["quakes"][3]["braced_after_s"] is None
    (tmp_path / "w2.log").write_text("nothing")
    assert ar.analyze_quakes(log, tmp_path / "w2.log") is None
    quiet = mind_log(tmp_path / "quiet", [{"time": 1, "kind": "event", "text": "x"}])
    assert ar.analyze_reactions(quiet, world) is None
    noglance = dict(r, glance_after_s=[], world_applied=None)
    assert "first glance" not in "\n".join(ar.reaction_report(noglance))


def test_report_and_main(tmp_path, monkeypatch, capsys):
    run = tmp_path / "run"
    standard_recording(run)
    recording(run / "recordings" / "r0.clawrec", [(0, 0, {"players": [body(0)]})], [])  # smaller: not the one used
    standard_mind_log(run)
    (run / "world.log").write_text("SKY Meteor #1\nSKY Earthquake #3 over: woke 1, moved 1, fell 1\n")
    agent_run(run)
    monkeypatch.setattr(sys, "argv", ["analyze_run.py", str(run), "--price", "1,1,1,1"])
    ar.main()
    text = (run / "analysis/report.md").read_text(encoding="utf-8")
    for words in ("# Run analysis: run", "## World (server-side ground truth)", "Gap between consecutive actions",
                  "Longest idle stretches", "Actions per hour: h0: 20, h1: 20", "Motion duty cycle:",
                  "Action results seen in world state", "## Agent (Claude Code transcript)", "Estimated cost: **$",
                  "Results returned to agent: Moving 1", "## Mind (layered", "## Reactions to sky events",
                  "## Earthquakes", "## Workspace memory", "| MEMORY.md | 400 | 100 |"):
        assert words in text, words
    assert (run / "analysis/actions.csv").read_text().startswith("tick,time_s,agent_id,type,data")
    assert "Written:" in capsys.readouterr().out
    assert ar.PRICES.pop("override") == (1.0, 1.0, 1.0, 1.0)


def test_report_edge_cases(tmp_path):
    rec = {"path": Path("r.clawrec"), "size_mb": 1.0, "tick_rate": 30, "duration_s": 0, "inputs": [(0, 0, "a", "Jump", "")],
           "start_ms": 0, "motion": None}
    text = ar.report(tmp_path, rec, {"calls": 0}, [])
    assert "Motion duty cycle: skipped" in text and "No Claude Code transcript found" in text
    still = {**rec, "motion": {"duty_cycle": None, "sampled_s": 0, "result_changes": {}}}
    assert "Motion duty cycle" not in ar.report(tmp_path, still, None, [])
    moving = {**rec, "motion": {"duty_cycle": 0.5, "sampled_s": 10, "result_changes": {}}}
    assert "Action results seen" not in ar.report(tmp_path, moving, None, [])
    from collections import Counter
    agent = {"calls": 1, "span_s": 0, "tokens": Counter(input=0, cache_write=0, cache_read=0, output=0), "think": [],
             "models": Counter(m=1), "continues": 0, "cost": None, "tools": Counter(), "actions_in_commands": 0,
             "act_commands": 0, "results": Counter()}
    text = ar.report(tmp_path, None, agent, [])
    assert "Cache: n/a" in text and "unknown model" in text


def test_main_with_nothing_recorded(tmp_path, monkeypatch, capsys):
    run = tmp_path / "empty"
    run.mkdir()
    monkeypatch.setattr(sys, "argv", ["analyze_run.py", str(run)])
    ar.main()
    assert (run / "analysis/report.md").read_text() == "# Run analysis: empty\n"
    assert not (run / "analysis/actions.csv").exists()


def test_run_as_a_script(tmp_path, monkeypatch):
    run = tmp_path / "x"
    run.mkdir()
    monkeypatch.setattr(sys, "argv", ["analyze_run.py", str(run)])
    runpy.run_path(str(TOOLS / "analyze_run.py"), run_name="__main__")
    assert (run / "analysis/report.md").exists()
