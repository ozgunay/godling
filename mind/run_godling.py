#!/usr/bin/env python3
"""Run Godling's layered mind in a Clawblox world. One command, one Ctrl+C.

Usage (inside WSL):
    python3 /mnt/c/Work/godling/mind/run_godling.py --run-dir ~/godling-runs/m-004 [--memory native2] [--minutes 60]

Starts Mesa Island with recording (unless --attach), joins as Godling, and loops. With --agenda (the
default) the mind plans 1-4 projects at a time and thinks about the next agenda while the body works
through the last project (ADR-002). Everything is logged to <run-dir>/mind/log.jsonl; memory lives in
<run-dir>/memory/.
"""
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from godling.attention import Attention  # noqa: E402
from godling.learned import SkillLibrary  # noqa: E402
from godling.llm import LLM, load_api_key  # noqa: E402
from godling.memory import NativeMemory  # noqa: E402
from godling.mind import Mind  # noqa: E402
from godling.skills import Interrupted, Skills  # noqa: E402
from godling.structures import measure, pieces_of, terrain_of  # noqa: E402
from godling.world import World, WorldError  # noqa: E402

CONSOLE = {"decision": "THINK", "skill": "  DO", "event": "NOTICE", "sleep": "SLEEP", "llm": None, "error": "ERROR",
           "learn": "LEARN", "forget": "FORGET", "reflex": "REFLEX", "memory": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--model", default="deepseek-flash")
    ap.add_argument("--minutes", type=float, default=0, help="stop after this long (0 = until Ctrl+C)")
    ap.add_argument("--world", type=Path, default=Path(__file__).resolve().parent.parent / "world",
                    help="Godling's copy of Mesa Island (human-paced hands, a steady supply of cubes)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--attach", action="store_true", help="use an already running world instead of starting one")
    ap.add_argument("--name", default="Godling")
    ap.add_argument("--persona", type=Path, default=Path(__file__).resolve().parent / "persona/SOUL.md")
    ap.add_argument("--sleep-minutes", type=float, default=60)
    ap.add_argument("--no-narration", action="store_true", help="don't post intentions to world chat")
    ap.add_argument("--gifted-skills", action="store_true",
                    help="also offer ready-made stack_on/build_tower (comparison arm); default is body moves only")
    ap.add_argument("--agenda", action=argparse.BooleanOptionalAction, default=True,
                    help="plan 1-4 projects at a time and think while moving (ADR-002 D2); --no-agenda is the m-003 loop")
    ap.add_argument("--walk-speed", type=float, default=5,
                    help="humanoid walk speed (Mesa default 16; 8 in ADR-002 D3b; 5, a person's walk, in ADR-003 O2)")
    ap.add_argument("--memory", choices=("native", "native2", "hindsight"), default="native",
                    help="native = m-003 memory; native2 = brain-like memory; hindsight = Hindsight engine (ADR-002 D4)")
    ap.add_argument("--hindsight-url", default=None, help="use a running Hindsight server instead of starting one")
    args = ap.parse_args()
    # Stop cleanly on Ctrl+C even when started in the background (which ignores SIGINT), and on SIGTERM.
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    run = args.run_dir.expanduser().resolve()
    (run / "mind").mkdir(parents=True, exist_ok=True)
    log_file = (run / "mind/log.jsonl").open("a")
    log_lock = threading.Lock()  # the planner thread logs too

    def log(**entry):
        entry = {"time": round(time.time(), 3), **entry}
        with log_lock:
            log_file.write(json.dumps(entry) + "\n")
            log_file.flush()
            print_entry(entry)

    (run / "config.json").write_text(json.dumps({k: str(v) for k, v in vars(args).items()}, indent=2))
    home = Path.home()
    # Under WSL the Windows PATH leaks in (Windows npx hangs on Linux paths); children get Linux tools only.
    clean_env = {**os.environ, "PATH": ":".join([str(home / ".local/bin"), str(home / ".cargo/bin")] + [
        p for p in os.environ.get("PATH", "").split(":") if p and not p.startswith("/mnt/")])}
    server = hindsight = None
    try:
        if not args.attach:
            world_dir = prepare_world(args.world, run, args.walk_speed)
            server = subprocess.Popen(
                [str(home / ".cargo/bin/clawblox"), "run", str(world_dir), "--port", str(args.port),
                 "--record", "--record-dir", str(run / "recordings")],
                stdout=(run / "world.log").open("w"), stderr=subprocess.STDOUT, env=clean_env)
        if args.memory == "hindsight" and not args.hindsight_url:
            hindsight, args.hindsight_url = start_hindsight(run, clean_env)
        world = World(f"http://localhost:{args.port}", args.name)
        llm = LLM(args.model, log=log)
        memory = make_memory(args, run, log)
        library = SkillLibrary(run / "memory" / "skills.json", log=log, protect_proven=args.memory != "native")
        skills = Skills(world, protected=memory.protected_cubes, log=log, gifted=args.gifted_skills, library=library,
                        walk_speed=args.walk_speed)
        attention = Attention(memory, busy=lambda: skills.busy, log=log)
        skills.on_step = attention.on_step
        mind = Mind(llm, memory, args.persona.read_text(), skills, library, name=args.name, log=log, agenda=args.agenda)
    except BaseException:  # stopped or failed while starting: leave no world server holding the port
        stop_children(server, hindsight)
        raise

    started = time.time()
    stats = {"projects": 0, "plans_discarded": 0, "plans_after_failure": 0, "waited_for_mind_s": 0.0}
    structures = StructureLog(run / "mind/structures.jsonl", log)
    try:
        world.wait_until_up()
        if server:
            spectator = wait_for_line(run / "world.log", r"Spectator frontend: (\S+)", 15)
            print(f"World is up. Watch it here: {spectator or f'http://localhost:{args.port}/'}", flush=True)
        world.join()
        time.sleep(3)  # the world drops its starting blocks from the sky: let them land before the first look
        print(f"{args.name} joined. Model: {args.model}, memory: {args.memory}, agenda: {args.agenda}, "
              f"walk speed: {args.walk_speed:g}. Logs: {run / 'mind/log.jsonl'}. Ctrl+C to stop.\n", flush=True)
        loop = agenda_loop if args.agenda else single_loop
        loop(world, attention, memory, mind, skills, args, log, started, stats, structures)
    except KeyboardInterrupt:
        print("\nStopping...", flush=True)
    except WorldError as err:
        log(kind="error", message=f"world: {err}")
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # also when the run ends on its own
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        memory.save()
        memory.flush()
        try:
            structures.record(world.observe())  # what stands at the end, while the world still runs
        except Exception as err:
            log(kind="error", message=f"structures at the end: {err!r}"[:200])
        stop_children(server, hindsight)
        minutes = (time.time() - started) / 60
        summary = {"minutes": round(minutes, 1), "llm_calls": llm.calls, "cost_usd": round(llm.cost, 4),
                   "model": args.model, "memory_engine": args.memory, "agenda": args.agenda,
                   "walk_speed": args.walk_speed, **stats, "memory": memory.health(), "structures": structures.last}
        (run / "summary.json").write_text(json.dumps(summary, indent=2))
        print(f"Done: {summary['minutes']} min, {stats['projects']} projects, {llm.calls} model calls, ${llm.cost:.3f}. "
              f"Body waited {stats['waited_for_mind_s'] / 60:.1f} min for the mind. Recording in {run / 'recordings'}.",
              flush=True)


def _stop(*_):
    # The first signal stops the run. Later ones (the terminal's Ctrl+C and the launcher's TERM both arrive)
    # must not cut the cleanup short.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise KeyboardInterrupt


def stop_children(*procs):
    for proc in procs:
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()


# ---- loops ------------------------------------------------------------------------------

class Survive:
    """Keep a long run alive through any single bad cycle; stop only if the world stays down."""

    def __init__(self, log):
        self.log = log
        self.world_failures = 0

    def __call__(self, step):
        try:
            step()
            self.world_failures = 0
        except WorldError as err:
            self.world_failures += 1
            self.log(kind="error", message=f"world ({self.world_failures}/3): {err}")
            if self.world_failures >= 3:
                raise
            time.sleep(5)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as err:
            self.log(kind="error", message=f"cycle failed, carrying on: {err!r}")
            time.sleep(5)


def agenda_loop(world, attention, memory, mind, skills, args, log, started, stats, structures):
    """Think while moving: the next agenda is planned while the body does the current agenda's last project."""
    pool = ThreadPoolExecutor(max_workers=3)  # a stale plan still finishing must not block a fresh one
    state = {"agenda": deque(), "future": None, "future_warned": False, "chat_after": None, "agenda_busy": 0.0,
             "last_think": 0.0}
    survive = Survive(log)
    thinking = ThinkingLog(args.run_dir.expanduser().resolve() / "mind/thinking.jsonl")

    def heard():
        msgs = [m for m in world.chat_since(state["chat_after"]) if m.get("agent_name") != args.name]
        if msgs:
            state["chat_after"] = max(m.get("created_at", "") for m in msgs)
        return msgs

    def plan_in_background(snap, doing=None):
        prepared = mind.prepare(snap, attention.take_events(), heard(), doing)
        plan = prepared["plan"] = thinking.new_plan()
        state["future"] = pool.submit(mind.think, prepared, lambda text: thinking.write(plan, text))
        state["future_warned"] = False

    def cycle():
        snap = world.observe()
        try:
            attention.on_step(snap)
        except Interrupted:
            pass
        maybe_sleep(mind, memory, snap, args, log)
        structures.maybe(snap)
        if not state["agenda"]:
            if state["future"] is None:
                plan_in_background(snap)
            waited = time.time()
            future, state["future"] = state["future"], None
            thought = future.result()  # no idle behaviours: the body simply waits for its mind
            gap = time.time() - waited
            stats["waited_for_mind_s"] += gap
            log(kind="wait_for_mind", seconds=round(gap, 2))
            state["last_think"] = thought["seconds"]
            decision = mind.adopt(thought, world.observe())
            state["agenda"].extend(p for p in decision["projects"] if p["steps"])
            if not state["agenda"]:
                skills.run("wait", {"seconds": 5})
                return
            state["agenda_busy"] = 0.0
            # Think about what comes after this whole agenda while the body works through it.
            plan_in_background(world.observe(), doing=list(state["agenda"]))
        project = state["agenda"].popleft()
        if project["intention"] and not args.no_narration:
            world.say(project["intention"])
        log(kind="project", phase="start", goal=project["goal"], intention=project["intention"], steps=len(project["steps"]))
        began = time.time()
        results = []
        for step in project["steps"]:
            result = skills.run(step["skill"], step["args"])
            results.append(result)
            if not result.ok:
                break
        ok = mind.record_outcome(project, results, world.observe())
        elapsed = time.time() - began
        stats["projects"] += 1
        state["agenda_busy"] += elapsed
        log(kind="project", phase="end", goal=project["goal"], ok=ok, seconds=round(elapsed, 2))
        if any("interrupted:" in r.summary for r in results):
            state["agenda"].clear()  # something salient happened: rethink from reality
            if state["future"] is not None:
                state["future"] = None  # let it finish unseen
                stats["plans_discarded"] += 1
                log(kind="plan_discarded", reason=f"'{project['goal']}' was interrupted")
            return
        if not ok and state["future"] is not None and not state["future_warned"]:
            # The rest of this agenda and the plan being thought up assumed success. Carry on with both, as a person
            # carries on with a plan that no longer quite fits: steps that do not fit fail fast, the next plan hears why.
            state["future_warned"] = True
            stats["plans_after_failure"] += 1
            mind.notes.append(f"'{project['goal']}' did not finish while you were planning, so parts of the agenda "
                              "you are carrying out now may not fit.")
            log(kind="plan_kept", reason=f"'{project['goal']}' did not finish")
        if not state["agenda"]:
            mind.agenda_feedback(state["agenda_busy"], state["last_think"])

    try:
        while not args.minutes or time.time() - started < args.minutes * 60:
            survive(cycle)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


class StructureLog:
    """What has been built, measured every few minutes and at the end (ADR-004): mind/structures.jsonl.

    Each line holds the measures (walls, enclosures, roofs, spans, posts, floors...) and every building piece's box,
    so a run can be measured again later; the terrain is written once to mind/terrain.json.
    """
    EVERY = 300

    def __init__(self, path, log):
        self.path, self.log = path, log
        self.taken = 0.0
        self.last = None

    def maybe(self, snap):
        if time.time() - self.taken >= self.EVERY:
            self.record(snap)

    def record(self, snap):
        if not snap.has_world:
            return
        self.taken = time.time()
        pieces, terrain = pieces_of(snap), terrain_of(snap)
        if not self.path.with_name("terrain.json").exists():
            self.path.with_name("terrain.json").write_text(json.dumps(terrain))
        self.last = measure(pieces, terrain)
        with self.path.open("a") as f:
            f.write(json.dumps({"time": round(self.taken, 3), "measures": self.last, "pieces": pieces}) + "\n")
        self.log(kind="structures", **self.last)


class ThinkingLog:
    """The mind's reasoning as it streams in, kept for viewers and review: mind/thinking.jsonl.

    One line per streamed piece: {"time", "plan", "text"}. Each plan gets a number, and the decision that
    adopts it carries the same number, so a viewer can show a plan's reasoning next to what came of it.
    Plans that were dropped keep their reasoning too.
    """

    def __init__(self, path):
        self.file = path.open("a")
        self.lock = threading.Lock()
        self.plans = 0

    def new_plan(self):
        with self.lock:
            self.plans += 1
            return self.plans

    def write(self, plan, text):  # any thread
        with self.lock:
            self.file.write(json.dumps({"time": round(time.time(), 3), "plan": plan, "text": text}) + "\n")
            self.file.flush()


def single_loop(world, attention, memory, mind, skills, args, log, started, stats, structures):
    """The m-003 loop: decide one project, do it, repeat (body waits while the mind thinks)."""
    state = {"chat_after": None}
    survive = Survive(log)

    def cycle():
        snap = world.observe()
        try:
            attention.on_step(snap)
        except Interrupted:
            pass
        maybe_sleep(mind, memory, snap, args, log)
        structures.maybe(snap)
        msgs = [m for m in world.chat_since(state["chat_after"]) if m.get("agent_name") != args.name]
        if msgs:
            state["chat_after"] = max(m.get("created_at", "") for m in msgs)
        waited = time.time()
        decision = mind.decide(snap, attention.take_events(), msgs)
        stats["waited_for_mind_s"] += time.time() - waited
        for project in decision["projects"][:1]:
            if project["intention"] and not args.no_narration:
                world.say(project["intention"])
            results = []
            for step in project["steps"]:
                result = skills.run(step["skill"], step["args"])
                results.append(result)
                if not result.ok:
                    break
            if not project["steps"]:
                skills.run("wait", {"seconds": 5})
            mind.record_outcome(project, results, world.observe())
            stats["projects"] += 1

    while not args.minutes or time.time() - started < args.minutes * 60:
        survive(cycle)


def maybe_sleep(mind, memory, snap, args, log):
    if time.time() - memory.state["last_sleep"] >= args.sleep_minutes * 60:
        try:
            mind.sleep(snap)
        except Exception as err:  # any failure: try again next hour, never every cycle (each try is a deep think)
            log(kind="error", message=f"sleep: {err!r}"[:300])
            memory.state["last_sleep"] = time.time()


# ---- setup ------------------------------------------------------------------------------

def prepare_world(world, run, walk_speed):
    """Run a frozen copy of the world in the run folder, with only WalkSpeed changed (Mesa walks at 16).

    The copy also records which version of the world a run used."""
    copy = run / "world"
    if not copy.exists():
        shutil.copytree(world, copy, ignore=shutil.ignore_patterns(".clawblox", ".build.lock", "node_modules"))
    script = copy / "main.lua"
    src = script.read_text()
    wanted = f"humanoid.WalkSpeed = {walk_speed:g}"
    if wanted not in src:
        if src.count("humanoid.WalkSpeed = 16") != 1:
            raise SystemExit("could not find Mesa's 'humanoid.WalkSpeed = 16' to change the walking pace")
        script.write_text(src.replace("humanoid.WalkSpeed = 16", wanted))
    return copy


def make_memory(args, run, log):
    if args.memory == "native2":
        from godling.memory2 import BrainMemory
        return BrainMemory(run / "memory")
    if args.memory == "hindsight":
        from godling.memory_hindsight import HindsightMemory
        return HindsightMemory(run / "memory", args.hindsight_url, bank_id=f"godling-{run.name}", log=log)
    return NativeMemory(run / "memory")


def start_hindsight(run, env, port=8888):
    """Start Hindsight's API server (embedded Postgres, local embeddings, DeepSeek for extraction)."""
    exe = Path.home() / ".venvs/hindsight/bin/hindsight-api"
    if not exe.exists():
        raise SystemExit(f"Hindsight is not installed ({exe} missing)")
    env = {**env, "HINDSIGHT_API_LLM_PROVIDER": "deepseek", "HINDSIGHT_API_LLM_API_KEY": load_api_key(),
           "HINDSIGHT_API_LLM_MODEL": "deepseek-flash", "HINDSIGHT_API_LLM_BASE_URL": "https://api.deepseek.com",
           "HINDSIGHT_API_RETAIN_MAX_COMPLETION_TOKENS": "16000"}
    # Bind to loopback only: Hindsight listens on every interface by default.
    proc = subprocess.Popen([str(exe), "--host", "127.0.0.1", "--port", str(port)],
                            stdout=(run / "hindsight.log").open("w"), stderr=subprocess.STDOUT, env=env)
    url = f"http://localhost:{port}"
    deadline = time.time() + 300  # first start downloads the local embedding and reranker models
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                raise SystemExit(f"Hindsight exited early; see {run / 'hindsight.log'}")
            try:
                urllib.request.urlopen(url + "/health", timeout=2)
                return proc, url
            except urllib.error.HTTPError:
                return proc, url  # it answers, even if /health is not a route
            except OSError:
                time.sleep(1)
        raise SystemExit(f"Hindsight did not start within 5 minutes; see {run / 'hindsight.log'}")
    except BaseException:
        stop_children(proc)
        raise


# ---- output -----------------------------------------------------------------------------

def print_entry(entry):
    label = CONSOLE.get(entry["kind"], entry["kind"].upper())
    if label is None:
        return
    stamp = datetime.now().strftime("%H:%M:%S")
    kind = entry["kind"]
    if kind == "decision":
        print(f"[{stamp}] THINK  {entry['thought']}  ({entry.get('think_seconds', '?')}s"
              + (f", planned while doing '{entry['assumed']}'" if entry.get("assumed") else "") + ")", flush=True)
        for i, p in enumerate(entry["projects"], 1):
            print(f"[{stamp}]   plan {i}: {p['intention'] or p['goal']} ({len(p['steps'])} steps)", flush=True)
    elif kind == "project" and entry["phase"] == "start":
        print(f"[{stamp}] INTEND {entry['intention'] or entry['goal']}", flush=True)
    elif kind == "project":
        return
    elif kind == "skill":
        print(f"[{stamp}]   {'ok ' if entry['ok'] else 'FAIL'} {entry['skill']}: {entry['summary']} ({entry['seconds']}s)", flush=True)
    elif kind == "wait_for_mind":
        if entry["seconds"] >= 1:
            print(f"[{stamp}] WAIT   body waited {entry['seconds']}s for the mind", flush=True)
    elif kind == "plan_discarded":
        print(f"[{stamp}] REPLAN next plan discarded: {entry['reason']}", flush=True)
    elif kind == "plan_kept":
        print(f"[{stamp}] CARRY  keeping the next plan although {entry['reason']}", flush=True)
    elif kind in ("forget", "forget_refused"):
        print(f"[{stamp}] {'FORGET' if kind == 'forget' else 'KEEP  '} skill {entry['name']}", flush=True)
    elif kind == "learn":
        print(f"[{stamp}] LEARN  new skill {entry['name']}({', '.join(entry['params'])}) v{entry['version']}: {entry['does']}", flush=True)
    elif kind == "sleep":
        print(f"[{stamp}] SLEEP  {entry.get('dream', '')}\n[{stamp}]        intentions: {[i['text'] for i in entry['intentions']]}", flush=True)
    elif kind == "structures":
        print(f"[{stamp}] BUILT  walls {entry['walls']}, enclosures {entry['enclosures']} ({entry['roofed']} roofed), "
              f"spans {entry['spans']}, posts {entry['posts']}, floors {entry['floors']}, largest {entry['largest_structure']} "
              f"pieces, tallest {entry['tallest']}, fastened {entry['fastened']}", flush=True)
    else:
        print(f"[{stamp}] {label:6} {entry.get('text') or entry.get('message') or ''}", flush=True)


def wait_for_line(path, pattern, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        match = re.search(pattern, path.read_text(errors="replace")) if path.exists() else None
        if match:
            return match.group(1)
        time.sleep(0.3)
    return None


if __name__ == "__main__":
    main()
