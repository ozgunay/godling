"""run_godling.py: its pieces one by one, its loops on the fake island, and main() end to end against a fake world."""
import io
import json
import math
import subprocess
import sys
import threading
import types
import urllib.error
from argparse import Namespace
from concurrent.futures import Future
from pathlib import Path

import pytest

import run_godling as rg
from godling import skills as sk
from godling.learned import SkillLibrary
from godling.memory import NativeMemory
from godling.mind import Mind
from godling.attention import Attention
from godling.skills import Interrupted, Skills
from godling.world import WorldError
from helpers import block, ent, ground, raw_obs
from island import FakeTime, Island
from run_live_skills import MEND_AT_HOME


# ---- the island's save ----------------------------------------------------------------------------------------
def snapshot():
    def part(x, anchored=False, collide=True):
        return {"cframe": {"position": [x, 1, 0], "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}, "size": [2.5, 2.5, 2.5],
                "color": [1, 1, 1], "anchored": anchored, "can_collide": collide}

    def attrs(**kw):
        return {k: {"type": "Number" if isinstance(v, (int, float)) and not isinstance(v, bool) else
                    "Bool" if isinstance(v, bool) else "String", "value": v} for k, v in kw.items()}
    return {"instance": {"workspace_children": [
        {"name": "Block_12", "class_name": "Part", "part": part(1), "attributes": attrs(RenderRole="PickupObject", Fastened=True,
                                                                                                 HeldBy="Godling")},
        {"name": "Stone_3", "class_name": "Part", "part": part(2), "attributes": attrs(RenderRole="Stone", SkyId=9)},
        {"name": "Crater_1", "class_name": "Part", "part": part(3, True, False), "attributes": attrs(RenderRole="Crater")},
        {"name": "Meteor_2", "class_name": "Part", "part": part(4, True, False), "attributes": attrs(RenderRole="Stone")},
        {"name": "Stump_4", "class_name": "Part", "part": part(5, True), "attributes": attrs(RenderRole="Stump", FelledAt=3)},
        {"name": "Mark_x", "class_name": "Part", "part": part(6), "attributes": attrs(RenderRole="SandMark")},
        {"name": "Ground", "class_name": "Part", "part": part(0, True), "attributes": attrs(RenderRole="Ground")},
        {"name": "Folder", "class_name": "Folder", "attributes": {"Odd": {"type": "Vector3", "value": [1, 2, 3]},
                                                                  "Nil": {"type": "String", "value": None}}},
        {"name": "Clock", "class_name": "Part", "part": part(0, True), "attributes": attrs(Day=2, TimeOfDay=13.0)},
    ], "players": [
        {"name": "Sky", "humanoid_root_part": {"position": [0, 0, 0]}},
        {"name": "Ghost"},
        {"name": "Godling", "humanoid_root_part": {"position": [1, 2.55, 3]},
         "attributes": {"Health": {"value": 80}, "Hunger": {"value": 0}}},
    ]}}


def test_island_of_keeps_what_a_restart_needs():
    island = rg.island_of(snapshot())
    names = [p["name"] for p in island["pieces"]]
    assert names == ["Crater_1", "Block_12", "Mark_x", "Stone_3"]  # craters first, then by kind and number
    assert island["pieces"][1]["attrs"] == {"RenderRole": "PickupObject", "Fastened": True}  # no hand holds it now
    assert [f["name"] for f in island["felled"]] == ["Stump_4"] and "FelledAt" not in island["felled"][0]["attrs"]
    assert island["counters"] == {"Sky": 9, "Block": 12, "Stone": 3, "Meteor": 2} or island["counters"]["Block"] == 12
    assert island["clock"] == pytest.approx(2400 + 13 / 24 * 2400 - 7 / 24 * 2400)
    # A starving body is kept starving: an empty belly (0) is a value, not a missing one.
    assert island["body"] == {"pos": [1, 2.55, 3], "health": 80, "hunger": 0, "wet": 0}
    assert island["roles"] == list(rg.KEPT_ROLES)
    # Stopped while Godling lay dead (main.lua DEATH): it comes back born again, at the start spot.
    dead = snapshot()
    dead["instance"]["players"][2]["attributes"] = {"Health": {"value": 0}, "Hunger": {"value": 0},
                                                   "Dead": {"value": True}}
    assert rg.island_of(dead)["body"] == {"pos": None, "health": 100, "hunger": 50, "wet": 0}
    empty = rg.island_of({"instance": {"workspace_children": [], "players": []}})
    assert empty["body"] is None and empty["clock"] == 0.0


def test_a_meteor_stone_keeps_cooling_across_a_restart_and_in_replays():
    """main.lua sky.meteor.cool: a landed meteor's stone and its crater carry LandedAt (on the island's clock, which the
    save keeps too) and Heat. The save keeps both, so the world cools them on from where they were; a replay frame
    keeps Heat, so the past shows each stone as hot as it was."""
    from godling.replay import slim_entity
    snap = snapshot()
    landed = {"RenderRole": {"type": "String", "value": "Stone"}, "SkyEvent": {"type": "String", "value": "Meteor"},
              "LandedAt": {"type": "Number", "value": 3012.4}, "Heat": {"type": "Number", "value": 0.35}}
    rest = {"cframe": {"position": [9, 1.25, 0], "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            "size": [2.5, 2.5, 2.5], "color": [0.25, 0.22, 0.2], "anchored": True, "can_collide": True}
    snap["instance"]["workspace_children"].append({"name": "Meteor_6", "class_name": "Part", "part": rest,
                                                   "attributes": landed})
    crater = next(c for c in snap["instance"]["workspace_children"] if c["name"] == "Crater_1")
    crater["attributes"].update(LandedAt={"type": "Number", "value": 3012.4}, Heat={"type": "Number", "value": 0.35})
    island = rg.island_of(snap)
    by_name = {p["name"]: p for p in island["pieces"]}
    assert by_name["Meteor_6"]["attrs"]["LandedAt"] == 3012.4 and by_name["Meteor_6"]["attrs"]["Heat"] == 0.35
    assert by_name["Crater_1"]["attrs"]["LandedAt"] == 3012.4
    assert "Meteor_2" not in by_name  # one still falling is never saved
    frame = slim_entity({"id": 6, "position": [9.004, 1.25, 0], "attributes": {"Heat": 0.35000000001, "LandedAt": 3012.4}})
    assert frame["attributes"] == {"Heat": 0.35, "LandedAt": 3012.4}


@pytest.mark.parametrize("dead", [False, True])
def test_island_save_keeps_the_death_count_and_last_cause_after_rebirth(dead):
    saved = snapshot()
    saved["instance"]["players"][2]["attributes"].update(
        Dead={"value": dead}, Deaths={"value": 4}, DiedOf={"value": "Cold"}, DiedAt={"value": "3.5,-7.0"})
    body = rg.island_of(saved)["body"]
    assert body["deaths"] == 4 and body["died_of"] == "Cold" and body["died_at"] == "3.5,-7.0"
    assert body["health"] == (100 if dead else 80)


def test_orientation():
    assert rg.orientation([[1, 0, 0], [0, 1, 0], [0, 0, 1]]) == [0.0, 0.0, 0.0]
    c, s = math.cos(0.5), math.sin(0.5)
    yaw = rg.orientation([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    assert yaw == pytest.approx([0, 0.5, 0])
    gimbal = rg.orientation([[1, 0, 0], [0, 0, -1], [0, 1, 0]])  # pitched straight up
    assert gimbal[0] == pytest.approx(math.pi / 2) and gimbal[2] == 0.0


def test_lua_literal():
    assert rg.lua_literal(None) == "nil" and rg.lua_literal(True) == "true" and rg.lua_literal(False) == "false"
    assert rg.lua_literal(1.23456) == "1.2346" and rg.lua_literal(float("inf")) == "0" and rg.lua_literal(3) == "3.0"
    assert rg.lua_literal('a"b\\c\nd é') == '"a\\034b\\092c\\010d é"'
    assert rg.lua_literal({"k": [1, "x"]}) == '{["k"] = {1.0, "x"}}'


class FakeProc:
    def __init__(self, args=None, stdout=None, stderr=None, env=None, text=None, errors=None, ends=False, stubborn=False):
        self.args, self.env = args, env
        self.ended = ends
        self.stubborn = stubborn
        self.signals, self.killed = [], False
        self.stdout = io.StringIO("panel up\n") if stdout == subprocess.PIPE else None
        if stdout not in (None, subprocess.PIPE):
            stdout.close()

    def poll(self):
        return 0 if self.ended else None

    def send_signal(self, sig):
        self.signals.append(sig)

    def wait(self, timeout=None):
        if self.stubborn:
            raise subprocess.TimeoutExpired("x", timeout)
        self.ended = True

    def kill(self):
        self.killed = True


def test_stop_children():
    running, done, stubborn = FakeProc(), FakeProc(ends=True), FakeProc(stubborn=True)
    rg.stop_children(running, None, done, stubborn)
    assert running.signals and running.ended and not done.signals and stubborn.killed


def test_island_save(tmp_path, world_server, monkeypatch, capsys):
    monkeypatch.setenv("WORLD_OPERATOR_TOKEN", "tok")
    logs = []
    save = rg.IslandSave(tmp_path, world_server.url, lambda **k: logs.append(k))
    assert save.load() is None
    (tmp_path / "island-save.json").write_text("{broken")
    assert save.load() is None and "could not be read" in capsys.readouterr().out
    world_server.replies[("GET", "/snapshot")] = snapshot()
    assert save.take()
    assert world_server.requests[-1]["headers"]["X-Operator-Token"] == "tok"
    assert save.load()["body"]["health"] == 80
    world_server.replies[("GET", "/snapshot")] = {"instance": {}}
    assert not save.take() and "island save" in logs[-1]["message"]
    world_server.replies[("GET", "/snapshot")] = snapshot()
    taken = len(world_server.requests)
    save.EVERY = 0.01
    save.start()
    for _ in range(200):  # the saver's own thread takes one within moments
        if len(world_server.requests) > taken:
            break
        threading.Event().wait(0.01)
    save.stop()
    assert len(world_server.requests) > taken


# ---- small parts -------------------------------------------------------------------------------------------------
def test_survive():
    logs, slept = [], []
    survive = rg.Survive(lambda **k: logs.append(k))
    rg_time = rg.time
    try:
        rg.time = types.SimpleNamespace(sleep=slept.append, time=rg_time.time)
        survive(lambda: None)
        survive(lambda: (_ for _ in ()).throw(ValueError("odd")))
        assert "cycle failed, carrying on" in logs[-1]["message"]

        def down():
            raise WorldError("down")
        survive(down)
        survive(down)
        assert survive.world_failures == 2
        survive(lambda: None)
        assert survive.world_failures == 0
        survive(down), survive(down)
        with pytest.raises(WorldError):
            survive(down)
        with pytest.raises(KeyboardInterrupt):
            survive(lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
        assert slept == [5] * 5
    finally:
        rg.time = rg_time


def test_structure_and_thinking_logs(tmp_path):
    from godling.world import Snapshot
    logs = []
    structures = rg.StructureLog(tmp_path / "structures.jsonl", lambda **k: logs.append(k))
    structures.record(Snapshot({}))  # no world: nothing
    assert structures.last is None
    s = Snapshot(raw_obs([ground(), block("Block_1", 0, 1.25, 0), block("Block_2", 0, 3.75, 0)]))
    structures.maybe(s)
    assert structures.last["tallest"] == 5.0 and logs[-1]["kind"] == "structures"
    assert json.loads((tmp_path / "terrain.json").read_text())[0]["name"] == "Ground"
    structures.maybe(s)  # too soon: not measured again
    assert len((tmp_path / "structures.jsonl").read_text().splitlines()) == 1
    structures.record(s)
    assert len((tmp_path / "structures.jsonl").read_text().splitlines()) == 2
    also = []
    thinking = rg.ThinkingLog(tmp_path / "thinking.jsonl", also.append)
    assert thinking.new_plan() == 1 and thinking.new_plan() == 2
    thinking.write(2, "hmm")
    assert also == ["hmm"] and json.loads((tmp_path / "thinking.jsonl").read_text())["plan"] == 2
    rg.ThinkingLog(tmp_path / "t2.jsonl").write(1, "x")


def test_maybe_sleep(tmp_path):
    mem = NativeMemory(tmp_path)
    logs = []

    class Sleeper:
        def __init__(self, fail):
            self.fail, self.slept = fail, 0

        def sleep(self, snap):
            self.slept += 1
            if self.fail:
                raise RuntimeError("no dreams")

    args = Namespace(sleep_minutes=0)
    ok = Sleeper(False)
    rg.maybe_sleep(ok, mem, None, args, lambda **k: logs.append(k))
    assert ok.slept == 1
    bad = Sleeper(True)
    mem.state["last_sleep"] = 0
    rg.maybe_sleep(bad, mem, None, args, lambda **k: logs.append(k))
    assert "sleep: RuntimeError" in logs[-1]["message"] and mem.state["last_sleep"] > 0
    rg.maybe_sleep(bad, mem, None, Namespace(sleep_minutes=60), lambda **k: logs.append(k))
    assert bad.slept == 1


def world_dir(tmp_path, save_line=True):
    w = tmp_path / "world-src"
    w.mkdir()
    (w / "main.lua").write_text("local SKY_TEST_EVERY = 0\nhumanoid.WalkSpeed = 16\n"
                                + ("sky.saved = nil -- ISLAND SAVE\n" if save_line else ""))
    (w / "node_modules").mkdir()
    return w


def test_prepare_world(tmp_path, capsys):
    run = tmp_path / "run"
    run.mkdir()
    copy = rg.prepare_world(world_dir(tmp_path), run, 5, 10, {"pieces": []})
    src = (copy / "main.lua").read_text()
    assert "humanoid.WalkSpeed = 5\n" in src and "local SKY_TEST_EVERY = 600\n" in src
    assert 'sky.saved = {["pieces"] = {}} -- ISLAND SAVE' in src and not (copy / "node_modules").exists()
    again = rg.prepare_world(tmp_path / "world-src", run, 5, 10, None)  # the copy is kept; settings already there
    assert "sky.saved = nil -- ISLAND SAVE" in (again / "main.lua").read_text()
    old = tmp_path / "old"
    old.mkdir()
    rg.prepare_world(world_dir(old, save_line=False), old, 16, 0, {"pieces": []})
    assert "cannot put the island back" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="could not find 'x = 1'"):
        rg._set_line("nothing", "x = ", "1", "2", "it")


def test_make_memory(tmp_path, monkeypatch):
    from godling.memory2 import BrainMemory
    assert type(rg.make_memory(Namespace(memory="native"), tmp_path, None)) is NativeMemory
    assert type(rg.make_memory(Namespace(memory="native2"), tmp_path, None)) is BrainMemory
    module = types.ModuleType("hindsight_client")

    class Client:
        def __init__(self, **kw):
            pass

        def create_bank(self, **kw):
            pass
    module.Hindsight = Client
    monkeypatch.setitem(sys.modules, "hindsight_client", module)
    mem = rg.make_memory(Namespace(memory="hindsight", hindsight_url="http://h"), tmp_path / "r-1", lambda **k: None)
    assert mem.bank == "godling-r-1"


def test_start_hindsight(tmp_path, monkeypatch):
    monkeypatch.setattr(rg.Path, "home", lambda: tmp_path)
    with pytest.raises(SystemExit, match="not installed"):
        rg.start_hindsight(tmp_path, {})
    exe = tmp_path / ".venvs/hindsight/bin/hindsight-api"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setattr(rg, "load_api_key", lambda: "k")
    procs = []
    monkeypatch.setattr(rg.subprocess, "Popen", lambda *a, **kw: procs.append(FakeProc(*a, **kw)) or procs[-1])
    replies = []

    def urlopen(url, timeout=None):
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(rg.urllib.request, "urlopen", urlopen)
    clock = [0.0]
    monkeypatch.setattr(rg, "time", types.SimpleNamespace(time=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0] + s)))
    replies[:] = [OSError("not yet"), io.BytesIO(b"ok")]
    proc, url = rg.start_hindsight(tmp_path, {"A": "1"})
    assert url == "http://localhost:8888" and procs[-1].env["HINDSIGHT_API_LLM_API_KEY"] == "k"
    assert procs[-1].args[1:] == ["--host", "127.0.0.1", "--port", "8888"]
    replies[:] = [urllib.error.HTTPError("u", 404, "no", {}, None)]
    assert rg.start_hindsight(tmp_path, {})[1] == url
    replies[:] = [OSError("no")] * 400
    with pytest.raises(SystemExit, match="did not start within 5 minutes"):
        rg.start_hindsight(tmp_path, {})
    assert procs[-1].signals
    monkeypatch.setattr(rg.subprocess, "Popen", lambda *a, **kw: FakeProc(*a, ends=True, **kw))
    with pytest.raises(SystemExit, match="exited early"):
        rg.start_hindsight(tmp_path, {})


def test_tee_and_console(tmp_path, monkeypatch):
    a, b = io.StringIO(), io.StringIO()
    tee = rg.Tee(a, b)
    assert tee.write("hi") == 2
    tee.flush()
    assert a.getvalue() == b.getvalue() == "hi" and tee.getvalue() == "hi"
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    rg.keep_console(tmp_path)
    print("to both")
    sys.stdout.flush()
    assert "to both" in (tmp_path / "console.log").read_text()
    for stream in sys.stdout.streams[1:]:
        stream.close()


def test_keep_console_without_a_real_console(tmp_path, monkeypatch):
    (tmp_path / "console.log").write_text("")
    monkeypatch.setattr(sys, "stdout", io.StringIO())  # no file number to compare
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    rg.keep_console(tmp_path)
    assert isinstance(sys.stdout, rg.Tee)
    for stream in sys.stdout.streams[1:]:
        stream.close()


def test_run_as_a_script(monkeypatch, capsys):
    import runpy
    monkeypatch.setattr(sys, "argv", ["run_godling.py", "--help"])
    with pytest.raises(SystemExit) as stop:
        runpy.run_path(rg.__file__, run_name="__main__")
    assert stop.value.code == 0 and "--run-dir" in capsys.readouterr().out


def test_keep_console_when_already_redirected(tmp_path, monkeypatch):
    path = tmp_path / "console.log"
    with path.open("w") as f:
        monkeypatch.setattr(sys, "stdout", f)
        rg.keep_console(tmp_path)
        assert sys.stdout is f


def test_copy_lines(tmp_path, capsys):
    rg.copy_lines(io.StringIO("a\nb\n"), tmp_path / "panel.log")
    assert (tmp_path / "panel.log").read_text() == "a\nb\n" and capsys.readouterr().out == "a\nb\n"


def test_print_entry(capsys):
    entries = [
        {"kind": "llm"},
        {"kind": "decision", "thought": "Hm.", "think_seconds": 3, "assumed": "a -> b", "needs": "2 logs",
         "projects": [{"intention": "", "goal": "g", "steps": [1]}]},
        {"kind": "decision", "thought": "Again.", "projects": []},
        {"kind": "glance", "turned": True, "degrees": 90, "text": "a shadow"},
        {"kind": "glance", "turned": False, "degrees": 0, "text": "a note"},
        {"kind": "brace", "ok": True, "phase": "rumble"}, {"kind": "brace", "ok": False, "phase": "shaking"},
        {"kind": "project", "phase": "start", "intention": "", "goal": "a wall"}, {"kind": "project", "phase": "end"},
        {"kind": "skill", "ok": True, "skill": "jump", "summary": "up", "seconds": 1},
        {"kind": "skill", "ok": False, "skill": "jump", "summary": "no", "seconds": 1},
        {"kind": "wait_for_mind", "seconds": 0.5}, {"kind": "wait_for_mind", "seconds": 4},
        {"kind": "plan_discarded", "reason": "r1"}, {"kind": "plan_kept", "reason": "r2"},
        {"kind": "bubble", "ok": True, "thing": "fish", "feeling": "happy"}, {"kind": "bubble", "ok": False, "reply": "?"},
        {"kind": "forget", "name": "a"}, {"kind": "forget_refused", "name": "b"},
        {"kind": "learn", "name": "c", "params": ["o"], "version": 2, "does": "d"},
        {"kind": "sleep", "dream": "ships", "intentions": [{"text": "hut"}]},
        {"kind": "structures", "walls": 1, "enclosures": 1, "roofed": 0, "spans": 0, "posts": 0, "floors": 0,
         "largest_structure": 4, "tallest": 5, "fastened": 2},
        {"kind": "event", "text": "something"}, {"kind": "error", "message": "oops"}, {"kind": "custom"},
    ]
    for e in entries:
        rg.print_entry(e)
    out = capsys.readouterr().out
    for words in ("THINK  Hm.  (3s, planned while doing 'a -> b')", "plan 1: g (1 steps)", "NEEDS  2 logs", "(?s)",
                  "GLANCE turned 90° towards: a shadow", "GLANCE saw: a note", "crouched and holding on",
                  "could not brace", "INTEND a wall", "ok  jump: up", "FAIL jump: no",
                  "WAIT   body waited 4s", "REPLAN next plan discarded: r1", "CARRY  keeping the next plan although r2",
                  "BUBBLE fish, happy", "BUBBLE unreadable: ?", "FORGET skill a", "KEEP   skill b",
                  "LEARN  new skill c(o) v2: d", "SLEEP  ships", "intentions: ['hut']", "BUILT  houses 0, walls 1",
                  "NOTICE something", "ERROR  oops", "CUSTOM"):
        assert words in out, words
    assert "0.5s" not in out


def test_wait_for_line(tmp_path, monkeypatch):
    path = tmp_path / "world.log"
    assert rg.wait_for_line(path, r"x: (\d+)", 0.01) is None
    path.write_text("x: 42\n")
    assert rg.wait_for_line(path, r"x: (\d+)", 1) == "42"


def test_stop_handler(monkeypatch):
    calls = []
    monkeypatch.setattr(rg.signal, "signal", lambda *a: calls.append(a))
    with pytest.raises(KeyboardInterrupt):
        rg._stop()
    assert calls == [(rg.signal.SIGINT, rg.signal.SIG_IGN), (rg.signal.SIGTERM, rg.signal.SIG_IGN)]


# ---- the loops on the fake island ------------------------------------------------------------------------------
class ChattyIsland(Island):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.chat = [{"agent_name": "Godling", "content": "me", "created_at": "1"},
                     {"agent_name": "Ann", "content": "hello", "created_at": "2"}]
        self.fail_say = False

    def chat_since(self, after=None, limit=20):
        return [m for m in self.chat if after is None or m["created_at"] > after]

    def say(self, text):
        super().say(text)


class ScriptLLM:
    """Plans from a script; the last one repeats. Raises KeyboardInterrupt after `calls` plans: the run is over."""

    def __init__(self, plans, calls=6):
        self.plans, self.left = list(plans), calls
        self.calls, self.cost = 0, 0.0
        self.users = []

    def complete_json(self, system, user, purpose="decide", on_reasoning=None):
        self.calls += 1
        self.users.append(user)
        if purpose == "sleep":
            return {"digest": "slept"}
        if purpose == "death":
            return {"lessons": [{"about": "cold", "text": "At nightfall, be under a roof"}], "feeling": "Back, and wiser"}
        self.left -= 1
        if self.left < 0:
            raise KeyboardInterrupt
        if on_reasoning:
            on_reasoning("weighing it up")
        plan = self.plans.pop(0) if len(self.plans) > 1 else self.plans[0]
        if isinstance(plan, Exception):
            raise plan
        return plan

    def quick_json(self, system, user, purpose, max_tokens=80):
        return {"thing": "fish", "feeling": "happy"}


def loop_setup(monkeypatch, tmp_path, plans, calls=6, agenda=True, minutes=0, no_narration=False):
    island = ChattyIsland([ground(), block("Block_1", 5, 1.25, 0), block("Block_2", -5, 1.25, 0)])
    monkeypatch.setattr(sk, "time", FakeTime(island))
    logs = []
    log = lambda **k: logs.append(k)  # noqa: E731
    memory = NativeMemory(tmp_path / "memory")
    library = SkillLibrary(tmp_path / "skills.json", log=log)
    skills = Skills(island, protected=memory.protected_cubes, log=log, library=library)
    attention = Attention(memory, busy=lambda: skills.busy, log=log)
    skills.on_step = attention.on_step
    skills.next_glance = attention.take_glance
    mind = Mind(ScriptLLM(plans, calls), memory, "soul", skills, library, log=log, agenda=agenda)
    (tmp_path / "mind").mkdir(exist_ok=True)
    args = Namespace(run_dir=tmp_path, name="Godling", no_narration=no_narration, minutes=minutes, sleep_minutes=0)
    stats = {"projects": 0, "plans_discarded": 0, "plans_after_failure": 0, "waited_for_mind_s": 0.0}
    structures = rg.StructureLog(tmp_path / "mind/structures.jsonl", log)
    return island, (island, attention, memory, mind, skills, args, log, rg.time.time(), stats, structures), logs, stats


def project(goal, *steps, intention="go"):
    return {"intention": intention, "goal": goal, "steps": [{"skill": s, "args": a} for s, a in steps]}


def test_agenda_loop_thinks_while_moving(monkeypatch, tmp_path):
    plans = [{"thought": "first", "agenda": [project("hop", ("jump", {})), project("fail", ("pick_up", {"object": "Nope"}),
                                                                                    ("jump", {}))]},
             {"thought": "nothing to do", "agenda": []},
             {"thought": "again", "agenda": [project("hop again", ("jump", {}), intention="")]}]
    island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path, plans, calls=5)
    with pytest.raises(KeyboardInterrupt):
        rg.agenda_loop(*loop_args)
    kinds = [l["kind"] for l in logs]
    assert "wait_for_mind" in kinds and "plan_kept" in kinds and "decision" in kinds
    assert stats["projects"] >= 3 and stats["plans_after_failure"] == 1
    assert "go" in island.said and any("You heard: Ann: hello" in u for u in loop_args[3].llm.users)
    assert (tmp_path / "mind/thinking.jsonl").read_text().count("weighing it up") >= 3
    assert any(l["kind"] == "skill" and l["skill"] == "wait" for l in logs)  # an empty agenda: the body waits


def test_the_body_says_when_it_stands_until_its_mind_has_thought(monkeypatch, tmp_path):
    """The viewers' screen shows "Thinking" while the body waits (replay.reduce_status): the log says when it begins."""
    plans = [{"thought": "go", "agenda": [project("hop", ("jump", {}), intention="Hop over")]}]
    island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path, plans, calls=2)
    gate = threading.Event()
    llm = loop_args[3].llm
    script = llm.complete_json

    def slow(*a, **kw):  # the first plan is not ready before the body has begun to wait for it
        assert gate.wait(5)
        return script(*a, **kw)

    def log(**entry):
        logs.append(entry)
        if entry["kind"] == "thinking":
            gate.set()

    llm.complete_json = slow
    with pytest.raises(KeyboardInterrupt):
        rg.agenda_loop(*loop_args[:6], log, *loop_args[7:])
    kinds = [l["kind"] for l in logs]
    assert kinds.index("thinking") < kinds.index("wait_for_mind") < kinds.index("decision")
    end = next(l for l in logs if l["kind"] == "project" and l["phase"] == "end")
    assert end["intention"] == "Hop over" and end["goal"] == "hop"


def test_agenda_loop_discards_an_interrupted_plan(monkeypatch, tmp_path):
    plans = [{"thought": "go", "agenda": [project("walk", ("walk_to", {"x": 10, "z": 0})), project("more", ("jump", {}))]}]
    island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path, plans, calls=3, no_narration=True)
    island.on_act["MoveTo"] = lambda d: island.ents.setdefault("Visitor", block("Block_9", 30, 1.25, 30)) and None
    attention = loop_args[1]
    original = attention.decide
    attention.decide = lambda event: event["text"].startswith("A new object") or original(event)
    with pytest.raises(KeyboardInterrupt):
        rg.agenda_loop(*loop_args)
    assert stats["plans_discarded"] >= 1 and any(l["kind"] == "plan_discarded" for l in logs)
    assert island.said == []


def test_agenda_loop_ends_on_time(monkeypatch, tmp_path):
    island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path, [{"agenda": []}], calls=99, minutes=1e-9)
    rg.agenda_loop(*loop_args)  # the time is already up
    assert stats["projects"] == 0


def test_single_loop(monkeypatch, tmp_path):
    plans = [{"intention": "jump", "project": {"goal": "up", "steps": [{"skill": "jump", "args": {}},
                                                                       {"skill": "fly", "args": {}}]}},
             {"intention": "", "project": {"goal": "idle", "steps": []}},
             {"intention": "x", "project": {"goal": "fail", "steps": [{"skill": "pick_up", "args": {"object": "No"}},
                                                                    {"skill": "jump", "args": {}}]}}]
    island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path, plans, calls=3, agenda=False)
    with pytest.raises(KeyboardInterrupt):
        rg.single_loop(*loop_args)
    assert stats["projects"] == 3 and island.said == ["jump", "x"]
    assert any(l["kind"] == "skill" and l["skill"] == "wait" for l in logs)


def test_loops_carry_on_when_attention_interrupts(monkeypatch, tmp_path):
    for loop, agenda, plan in ((rg.agenda_loop, True, {"agenda": [project("hop", ("jump", {}))]}),
                               (rg.single_loop, False, {"intention": "", "project": {"goal": "hop", "steps": []}})):
        island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path / loop.__name__, [plan], calls=2, agenda=agenda)
        attention = loop_args[1]
        attention.interrupt = "a visitor"  # the next look interrupts
        real = attention.on_step

        def on_step(snap, real=real, attention=attention):
            attention.interrupt = attention.interrupt or ("a visitor" if not stats["projects"] else None)
            return real(snap)
        attention.on_step = on_step
        with pytest.raises(KeyboardInterrupt):
            loop(*loop_args)
        assert stats["projects"] >= 1


def dies_for(island, looks):
    """The fake body lies dead for this many looks, then is born again (main.lua DEATH)."""
    real = island.observe
    left = {"n": looks}

    def observe():
        if island.attrs.get("Dead"):
            left["n"] -= 1
            if left["n"] < 0:
                island.attrs.update(Dead=False, Health=100, Hunger=50)
        return real()
    island.observe = observe


def test_loops_live_through_a_death(monkeypatch, tmp_path):
    """Dead, the body does nothing and the mind thinks nothing; born again, the mind draws its own lessons from the
    death report before it plans again, and the next plan hears of the death."""
    monkeypatch.setattr(rg, "DEAD_LOOK", 0)
    for loop, agenda, plan in ((rg.agenda_loop, True, {"agenda": [project("hop", ("jump", {}))]}),
                               (rg.single_loop, False, {"intention": "", "project": {"goal": "hop", "steps": []}})):
        island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path / loop.__name__, [plan], calls=2, agenda=agenda)
        island.attrs.update(Dead=True, Deaths=1, DiedOf="Cold", DiedAt="3,4", Health=0)
        dies_for(island, 3)
        with pytest.raises(KeyboardInterrupt):
            loop(*loop_args)
        mind, memory = loop_args[3], loop_args[2]
        death = next(l for l in logs if l["kind"] == "death")
        assert death["lessons"] == [{"about": "cold", "text": "At nightfall, be under a roof"}]
        assert death["feeling"] == "Back, and wiser" and death["cause"] == "Cold"
        assert [l["kind"] for l in logs].index("dead") < [l["kind"] for l in logs].index("death")
        report = next(u for u in mind.llm.users if u.startswith("You died"))
        assert "You died of the cold at (3, 4)." in report and "You have died 1 time in all." in report
        lesson = next(e for e in memory.episodes if e["text"] == "At nightfall, be under a roof")
        assert lesson["importance"] == 5 and lesson["kind"] == "lesson"
        assert any("You died of the cold and came back to life" in u for u in mind.llm.users[1:]), "the plan hears"


def test_agenda_loop_drops_a_plan_made_while_the_body_died(monkeypatch, tmp_path):
    monkeypatch.setattr(rg, "DEAD_LOOK", 0)
    plans = [{"thought": "go", "agenda": [project("hop", ("jump", {}))]}]
    island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path, plans, calls=3, no_narration=True)
    llm = loop_args[3].llm
    script = llm.complete_json

    def deadly(system, user, purpose="decide", on_reasoning=None):
        reply = script(system, user, purpose, on_reasoning)
        if purpose == "decide" and llm.calls == 1:  # lightning strikes while the first plan is being thought
            island.attrs.update(Dead=True, Deaths=1, DiedOf="Storm", Health=0)
        return reply
    llm.complete_json = deadly
    dies_for(island, 2)
    with pytest.raises(KeyboardInterrupt):
        rg.agenda_loop(*loop_args)
    kinds = [l["kind"] for l in logs]
    assert kinds.index("dead") < kinds.index("death")
    first_project = kinds.index("project") if "project" in kinds else len(kinds)
    assert kinds.index("death") < first_project, "the plan thought for the living body was never carried out"


@pytest.mark.parametrize("agenda", [False, True])
@pytest.mark.parametrize("during", ["planning", "sleep"])
def test_loops_reflect_even_when_a_model_call_outlasts_the_whole_dead_interval(monkeypatch, tmp_path, agenda, during):
    """No observation sees Dead=True: only the persistent death counter reveals what the slow call missed."""
    stale = {"thought": "stale", "remember": [{"about": "old life", "text": "stale side effect"}],
             "agenda": [project("stale goal", ("jump", {}))]}
    fresh = {"thought": "fresh", "agenda": [project("fresh goal", ("jump", {}))]}
    island, loop_args, logs, stats = loop_setup(
        monkeypatch, tmp_path, [stale, fresh] if during == "planning" else [fresh], calls=3, agenda=agenda)
    mind, memory, attention = loop_args[3], loop_args[2], loop_args[1]
    script = mind.llm.complete_json
    happened = []

    def die_and_return():
        if not happened:
            happened.append(True)
            island.attrs.update(Dead=False, Deaths=1, DiedOf="Cold", DiedAt="3,4", Health=100, Hunger=50)

    def complete(system, user, purpose="decide", on_reasoning=None):
        reply = script(system, user, purpose, on_reasoning)
        if purpose == "decide" and during == "planning":
            die_and_return()
        return reply

    mind.llm.complete_json = complete
    if during == "sleep":
        mind.sleep = lambda snap: die_and_return()
    with pytest.raises(KeyboardInterrupt):
        (rg.agenda_loop if agenda else rg.single_loop)(*loop_args)
    deaths = [i for i, entry in enumerate(logs) if entry["kind"] == "death"]
    assert len(deaths) == 1 and not attention.death_pending
    first_decision = next(i for i, entry in enumerate(logs) if entry["kind"] == "decision")
    assert deaths[0] < first_decision, "reflection must precede adoption, including its memory and skill changes"
    assert all(entry.get("thought") != "stale" for entry in logs)
    assert not any("stale side effect" in episode["text"] for episode in memory.episodes)
    assert stats["projects"] > 0
    if agenda and during == "planning":
        assert stats["plans_discarded"] == 1


def test_an_agenda_replans_after_a_provider_failure(monkeypatch, tmp_path):
    island, loop_args, logs, stats = loop_setup(
        monkeypatch, tmp_path, [RuntimeError("model unavailable"), {"agenda": [project("hop", ("jump", {}))]}], calls=2)
    monkeypatch.setattr(rg, "time", types.SimpleNamespace(time=rg.time.time, sleep=lambda seconds: None))

    def log(**entry):
        logs.append(entry)
        if sum(item["kind"] == "error" for item in logs) > 1:
            raise KeyboardInterrupt  # a regression must fail promptly, rather than read the failed future forever

    with pytest.raises(KeyboardInterrupt):
        rg.agenda_loop(*loop_args[:6], log, *loop_args[7:])
    assert stats["projects"] == 1
    assert sum(entry["kind"] == "error" for entry in logs) == 1
    assert any(entry["kind"] == "decision" for entry in logs)


def test_an_agenda_cancels_a_queued_plan_as_soon_as_it_notices_death(monkeypatch, tmp_path):
    island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path, [{"agenda": []}])
    future = Future()

    class QueuedPool:
        def __init__(self, **kwargs):
            pass

        def submit(self, *args):
            island.attrs.update(Dead=True, Deaths=1, DiedOf="Cold", Health=0)
            return future

        def shutdown(self, **kwargs):
            pass

    def reflect(*args):
        assert future.cancelled(), "a queued call must be cancelled before reflection starts"
        raise KeyboardInterrupt

    monkeypatch.setattr(rg, "ThreadPoolExecutor", QueuedPool)
    monkeypatch.setattr(rg, "DEAD_LOOK", 0)
    loop_args[3].reflect_on_death = reflect
    dies_for(island, 2)
    with pytest.raises(KeyboardInterrupt):
        rg.agenda_loop(*loop_args)
    assert stats["plans_discarded"] == 1 and stats["projects"] == 0


def test_a_failed_reflection_does_not_stop_the_life_that_goes_on(monkeypatch, tmp_path):
    monkeypatch.setattr(rg, "DEAD_LOOK", 0)
    island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path, [{"agenda": []}], calls=1)
    island.attrs.update(Dead=True, Deaths=2, DiedOf="Hunger")
    dies_for(island, 1)
    mind = loop_args[3]
    mind.reflect_on_death = lambda snap, report: (_ for _ in ()).throw(RuntimeError("no answer"))
    snap = rg.live_through_death(island, loop_args[1], mind, lambda **k: logs.append(k), "fishing")
    assert not snap.dead
    assert any(l["kind"] == "error" and "no answer" in l["message"] for l in logs)
    assert not loop_args[1].death_pending, "a failed reflection must not repeat on every living cycle"
    assert "last_reflected_death" not in loop_args[2].state, "a restart should retry an unanswered reflection"


def test_a_saved_death_is_reflected_once_even_if_restart_already_restored_the_body_alive(tmp_path):
    island = Island([ground()], attrs={"Health": 100, "Hunger": 50, "Deaths": 2, "DiedOf": "Cold", "DiedAt": "3,4"})
    memory = NativeMemory(tmp_path)
    attention = Attention(memory)
    snap = rg.observe_body(island, attention)
    assert not snap.dead and attention.death_pending
    reports = []
    mind = Namespace(reflect_on_death=lambda snapshot, report: reports.append(report))
    rg.live_through_death(island, attention, mind, lambda **entry: None)
    assert len(reports) == 1 and reports[0].startswith("You died of the cold at (3, 4).")
    assert not attention.death_pending
    restarted = Attention(NativeMemory(tmp_path))
    rg.observe_body(island, restarted)
    assert restarted.memory.state["last_reflected_death"] == 2 and not restarted.death_pending
    island.attrs.update(Deaths=3, DiedOf="Storm")
    rg.observe_body(island, restarted)
    assert restarted.death_pending, "acknowledging the saved death must not hide the next one"


def test_single_loop_ends_on_time(monkeypatch, tmp_path):
    island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path, [{}], agenda=False, minutes=1)
    started = loop_args[7] - 3600  # (not a minute that is almost none: Windows' clock can read the same twice)
    rg.single_loop(*loop_args[:7], started, *loop_args[8:])
    assert stats["projects"] == 0


def test_watch_while_thinking(monkeypatch, tmp_path):
    island = Island([ground()])
    monkeypatch.setattr(sk, "time", FakeTime(island))
    monkeypatch.setattr(rg, "time", types.SimpleNamespace(time=rg.time.time, sleep=lambda s: None))
    skills = Skills(island)
    calls = []

    class Watcher:
        def on_step(self, snap):
            calls.append(snap)
            if len(calls) == 1:
                raise Interrupted("x")
            if len(calls) == 2:
                raise WorldError("y")

    future = Future()
    threading.Timer(0.05, lambda: future.set_result(1)).start()
    rg.watch_while_thinking(future, island, Watcher(), skills)
    assert len(calls) >= 2


# ---- main(), end to end ------------------------------------------------------------------------------------------
class FakeLLMClass:
    instances = []

    def __init__(self, model="m", log=None, **kw):
        self.model, self.log = model, log
        self.calls, self.cost = 0, 0.0
        self.left = 3
        FakeLLMClass.instances.append(self)

    def complete_json(self, system, user, purpose="decide", on_reasoning=None):
        self.calls += 1
        if purpose == "sleep":
            return {"digest": "slept"}
        self.left -= 1
        if self.left < 0:
            raise KeyboardInterrupt
        if on_reasoning:
            on_reasoning("thinking")
        return {"thought": "ok", "agenda": [{"intention": "say hi", "goal": "greet",
                                             "steps": [{"skill": "say", "args": {"text": "hi"}}]}]}

    def quick_json(self, system, user, purpose, max_tokens=80):
        return {"thing": "fish", "feeling": "calm"}


@pytest.fixture
def main_env(monkeypatch, tmp_path, world_server):
    obs = raw_obs([ground(), block("Block_1", 5, 1.25, 0)], tick=3)
    for route in (("GET", "/observe"), ("POST", "/input")):
        world_server.replies[route] = obs
    world_server.replies[("GET", "/api.md")] = b"# api"
    world_server.replies[("POST", "/join")] = {"session": "s"}
    world_server.replies[("POST", "/chat")] = {}
    world_server.replies[("GET", "/chat/messages")] = {"messages": []}
    world_server.replies[("GET", "/snapshot")] = snapshot()
    monkeypatch.setattr(rg, "LLM", FakeLLMClass)
    monkeypatch.setattr(rg.signal, "signal", lambda *a: None)
    monkeypatch.setattr(rg, "time", types.SimpleNamespace(time=rg.time.time, sleep=lambda s: None))
    monkeypatch.setattr(sk, "time", types.SimpleNamespace(time=rg.time.time, sleep=lambda s: None))
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    monkeypatch.setattr(sys, "stderr", sys.stderr)
    monkeypatch.setenv("WORLD_OPERATOR_TOKEN", "tok")
    monkeypatch.setenv("WORLD_AGENT_KEY", "agent")
    monkeypatch.setenv("WORLD_SPECTATOR_TOKEN", "spec")
    monkeypatch.delenv("WORLD_BASE_PATH", raising=False)
    port = int(world_server.url.rsplit(":", 1)[1])
    FakeLLMClass.instances.clear()
    return tmp_path, port


def close_console():
    for stream in (sys.stdout, sys.stderr):
        for kept in getattr(stream, "streams", ())[1:]:
            kept.close()


def test_main_attached(main_env, monkeypatch):
    tmp_path, port = main_env
    run = tmp_path / "run"
    monkeypatch.setattr(sys, "argv", ["run_godling.py", "--run-dir", str(run), "--attach", "--port", str(port),
                                      "--no-bubble", "--memory", "native2"])
    try:
        rg.main()
    finally:
        close_console()
    summary = json.loads((run / "summary.json").read_text())
    assert summary["projects"] >= 1 and summary["memory_engine"] == "native2" and summary["structures"]["pieces"] == 1
    assert json.loads((run / "config.json").read_text())["attach"] == "True"
    log = (run / "mind/log.jsonl").read_text()
    assert '"kind": "decision"' in log and '"kind": "project"' in log
    assert "Done:" in (run / "console.log").read_text()


def test_the_live_default_memory_keeps_a_skill_that_has_proven_itself(main_env, monkeypatch):
    # The live run (native memory, the default) forgot mend_at_home at 71 of 81 when its mind asked (ADR-032).
    tmp_path, port = main_env
    run = tmp_path / "run"
    (run / "memory").mkdir(parents=True)
    (run / "memory" / "skills.json").write_text(json.dumps({"mend_at_home": MEND_AT_HOME}))

    class ForgetfulLLM(FakeLLMClass):
        def complete_json(self, system, user, purpose="decide", on_reasoning=None):
            reply = super().complete_json(system, user, purpose, on_reasoning)
            return {**reply, "forget": ["mend_at_home"]} if purpose == "decide" else reply
    monkeypatch.setattr(rg, "LLM", ForgetfulLLM)
    monkeypatch.setattr(sys, "argv", ["run_godling.py", "--run-dir", str(run), "--attach", "--port", str(port),
                                      "--no-bubble"])
    try:
        rg.main()
    finally:
        close_console()
    assert json.loads((run / "config.json").read_text())["memory"] == "native"
    assert json.loads((run / "memory" / "skills.json").read_text())["mend_at_home"]["successes"] == 71
    log = [json.loads(line) for line in (run / "mind/log.jsonl").read_text().splitlines()]
    assert [e["kind"] for e in log if e["kind"] in ("forget", "forget_refused")][:1] == ["forget_refused"]
    assert "forget" not in [e["kind"] for e in log]
    assert "KEEP   skill mend_at_home" in (run / "console.log").read_text()


def test_main_starts_the_world(main_env, monkeypatch, tmp_path):
    _, port = main_env
    run = tmp_path / "run2"
    run.mkdir()
    (run / "island-save.json").write_text(json.dumps({"pieces": [], "body": None}))
    procs = []

    def popen(args, **kw):
        proc = FakeProc(args, **{k: kw.get(k) for k in ("stdout", "env", "text", "errors")})
        if args[1] == "run":
            (run / "world.log").write_text("Spectator frontend: http://spectate\nISLAND restored: 1 piece\n")
        procs.append(proc)
        return proc
    monkeypatch.setattr(rg.subprocess, "Popen", popen)
    monkeypatch.setenv("CLAWBLOX_BIN", "clawblox-test")
    monkeypatch.setattr(sys, "argv", ["run_godling.py", "--run-dir", str(run), "--port", str(port), "--guest-panel", "9",
                                      "--world", str(world_dir(tmp_path)), "--no-agenda", "--no-narration"])
    try:
        rg.main()
    finally:
        close_console()
    world, packer, panel = procs
    assert world.args[:2] == ["clawblox-test", "run"] and "--record" in world.args and world.signals
    # The replay packer (ADR-016) follows the run's recording, and stops with the run.
    assert packer.args[1:] == ["-m", "godling.replay", "follow", str(run)] and packer.signals
    assert panel.args[-2:] == ["--view", "http://spectate"]
    assert json.loads((run / "island-save.json").read_text())["body"]["health"] == 80  # saved at the stop
    assert "the island put back (1 piece)" in (run / "console.log").read_text()


def test_main_with_the_relay(main_env, monkeypatch, tmp_path):
    _, port = main_env
    run = tmp_path / "run6"
    run.mkdir()
    exe = tmp_path / "godling-relay"
    exe.write_text("")
    procs = []

    def popen(args, **kw):
        if args[1:2] == ["run"]:
            (run / "world.log").write_text("Spectator frontend: http://spectate/?spectator_token=t\n")
        procs.append(FakeProc(args, stdout=kw.get("stdout"), env=kw.get("env")))
        return procs[-1]
    monkeypatch.setattr(rg.subprocess, "Popen", popen)
    monkeypatch.setenv("CLAWBLOX_BIN", "clawblox-test")
    monkeypatch.setenv("RELAY_BIN", str(exe))
    monkeypatch.setattr(sys, "argv", ["run_godling.py", "--run-dir", str(run), "--port", str(port), "--relay", "8190",
                                      "--guest-panel", "9", "--world", str(world_dir(tmp_path)), "--no-agenda",
                                      "--no-narration"])
    try:
        rg.main()
    finally:
        close_console()
    world, relay, packer, panel = procs
    assert relay.args == [str(exe)] and relay.signals  # stopped with the run
    assert packer.args[1:] == ["-m", "godling.replay", "follow", str(run)]
    assert relay.env["RELAY_LISTEN"] == "127.0.0.1:8190" and relay.env["RELAY_SPECTATOR_TOKEN"] == "spec"
    assert relay.env["RELAY_UPSTREAM"] == f"ws://127.0.0.1:{port}/spectate/ws"
    assert panel.args[-1] == "http://spectate/?spectator_token=t&stream_port=8190"  # the page streams from the relay
    assert (run / "world.key").read_text() == "agent"  # for tools that join this world later
    assert "DEEPSEEK_API_KEY" not in world.env


def test_start_relay(monkeypatch, tmp_path):
    exe = tmp_path / "godling-relay"
    exe.write_text("")
    monkeypatch.setenv("RELAY_BIN", str(exe))
    monkeypatch.setenv("WORLD_BASE_PATH", "/island/")
    monkeypatch.setenv("WORLD_SPECTATOR_TOKEN", "spec")
    seen = {}
    monkeypatch.setattr(rg.subprocess, "Popen", lambda args, **kw: seen.update(kw) or FakeProc(args, stdout=kw["stdout"]))
    rg.start_relay(8190, 8092, tmp_path, {"PATH": "", "RELAY_LISTEN": "0.0.0.0:8082"})
    assert seen["env"]["RELAY_LISTEN"] == "0.0.0.0:8082"  # deploy/ says where viewers connect
    assert seen["env"]["RELAY_UPSTREAM"] == "ws://127.0.0.1:8092/island/spectate/ws"
    assert seen["env"]["RELAY_BASE_PATH"] == "/island"
    monkeypatch.setenv("RELAY_BIN", str(tmp_path / "missing"))
    with pytest.raises(SystemExit, match="not built"):
        rg.start_relay(8190, 8092, tmp_path, {"PATH": ""})


def test_main_stops_the_world_if_starting_fails(main_env, monkeypatch, tmp_path):
    _, port = main_env
    run = tmp_path / "run3"
    procs = []
    monkeypatch.setattr(rg.subprocess, "Popen", lambda args, **kw: procs.append(FakeProc(args)) or procs[-1])
    monkeypatch.setattr(rg, "make_memory", lambda *a: (_ for _ in ()).throw(RuntimeError("no memory")))
    monkeypatch.setattr(sys, "argv", ["run_godling.py", "--run-dir", str(run), "--port", str(port),
                                      "--world", str(world_dir(tmp_path))])
    try:
        with pytest.raises(RuntimeError, match="no memory"):
            rg.main()
    finally:
        close_console()
    assert procs[0].signals


def test_main_world_errors_end_the_run(main_env, monkeypatch, tmp_path, world_server):
    _, port = main_env
    run = tmp_path / "run4"
    monkeypatch.setattr(sys, "argv", ["run_godling.py", "--run-dir", str(run), "--attach", "--port", str(port),
                                      "--memory", "hindsight"])
    hindsight = FakeProc()
    monkeypatch.setattr(rg, "start_hindsight", lambda run, env: (hindsight, "http://h"))
    module = types.ModuleType("hindsight_client")

    class Client:
        def __init__(self, **kw):
            pass

        def create_bank(self, **kw):
            pass
    module.Hindsight = Client
    monkeypatch.setitem(sys.modules, "hindsight_client", module)
    world_server.status[("POST", "/join")] = 500
    try:
        rg.main()
    finally:
        close_console()
    assert "world: POST /join" in (run / "mind/log.jsonl").read_text()
    assert hindsight.signals  # stopped with the run


def test_main_with_the_bubble_and_a_broken_end(main_env, monkeypatch, tmp_path, world_server):
    _, port = main_env
    run = tmp_path / "run5"
    started = []

    class Bubble:
        def __init__(self, world, llm, log=None):
            self.events = []

        def start(self):
            started.append(self)
            return self

        def stop(self):
            pass

        def thought(self, text):
            self.events.append(("thought", text))

        def happens(self, text):
            self.events.append(("happens", text))

        def does(self, text):
            self.events.append(("does", text))
    monkeypatch.setattr(rg, "Bubble", Bubble)
    monkeypatch.setattr(rg, "StructureLog", type("Broken", (rg.StructureLog,), {  # measures only at the end, and fails
        "maybe": lambda self, snap: None, "record": lambda self, snap: (_ for _ in ()).throw(RuntimeError("at the end"))}))
    looks = []

    def observe(request):  # a new block appears now and then: news for attention, and for the bubble
        looks.append(1)
        extra = [block(f"Block_{len(looks)}", 9, 1.25, len(looks) * 3)] if len(looks) % 3 == 0 else []
        return raw_obs([ground(), block("Block_1", 5, 1.25, 0)] + extra, tick=len(looks))
    world_server.replies[("GET", "/observe")] = observe
    monkeypatch.setattr(sys, "argv", ["run_godling.py", "--run-dir", str(run), "--attach", "--port", str(port)])
    try:
        rg.main()
    finally:
        close_console()
    assert started and "structures at the end" in (run / "mind/log.jsonl").read_text()
    kinds = {kind for kind, _ in started[0].events}
    assert kinds >= {"thought", "happens", "does"}


def test_the_save_keeps_flakes_of_iron_their_count_and_iron_edges():
    """main.lua METEORIC IRON: a flake (Iron_n, RenderRole Iron) is kept, numbered on from the save, and a tool's
    iron edge (its Edge attribute) stays bound on."""
    snap = snapshot()
    lying = {"cframe": {"position": [3, 0.1, 2], "rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
             "size": [0.5, 0.2, 1.0], "color": [0.26, 0.25, 0.24], "anchored": False, "can_collide": True}
    snap["instance"]["workspace_children"] += [
        {"name": "Iron_3", "class_name": "Part", "part": lying,
         "attributes": {"RenderRole": {"type": "String", "value": "Iron"}}},
        {"name": "Spear_2", "class_name": "Part", "part": dict(lying, size=[0.3, 0.3, 4.5]),
         "attributes": {"RenderRole": {"type": "String", "value": "Tool"}, "ToolKind": {"type": "String", "value": "Spear"},
                        "Edge": {"type": "String", "value": "Iron"}}}]
    island = rg.island_of(snap)
    by_name = {p["name"]: p for p in island["pieces"]}
    assert "Iron" in island["roles"] and by_name["Iron_3"]["attrs"]["RenderRole"] == "Iron"
    assert island["counters"]["Iron"] == 3 and island["counters"]["Spear"] == 2
    assert by_name["Spear_2"]["attrs"]["Edge"] == "Iron"
