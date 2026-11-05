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
import math
import os
import re
import secrets
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
from godling.bubble import Bubble  # noqa: E402
from godling.learned import SkillLibrary  # noqa: E402
from godling.llm import LLM, load_api_key  # noqa: E402
from godling.discovery import Discovery  # noqa: E402
from godling.memory import NativeMemory  # noqa: E402
from godling.mind import Mind  # noqa: E402
from godling.skills import Interrupted, Skills  # noqa: E402
from godling.structures import measure, pieces_of, terrain_of  # noqa: E402
from godling.world import SKY_PLAYER, World, WorldError  # noqa: E402

# What a restart keeps (IslandSave; world/main.lua sky.restore puts it back): the pieces that can be carried, built
# with or left by the sky, by their RenderRole. Felled trees (Stump) are kept as well.
KEPT_ROLES = ("PickupObject", "Stone", "Log", "Tool", "Ladder", "Boulder", "Rock", "Coconut", "Catch", "Volleyball",
              "Crater", "SandMark")
DECOR_ROLES = ("Crater", "SandMark")  # anchored and walked through by design
NUMBERED = ("Block", "Stone", "Log", "Mark", "Coconut", "Spear", "Catch")  # name prefixes the world counts on from

CONSOLE = {"decision": "THINK", "skill": "  DO", "event": "NOTICE", "sleep": "SLEEP", "llm": None, "error": "ERROR",
           "learn": "LEARN", "forget": "FORGET", "reflex": "REFLEX", "memory": None, "thinking": None}


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
    ap.add_argument("--house-project", action=argparse.BooleanOptionalAction, default=True,
                    help="keep one house project across plans: its site, its progress and its pieces (ADR-019)")
    ap.add_argument("--walk-speed", type=float, default=5,
                    help="humanoid walk speed (Mesa default 16; 8 in ADR-002 D3b; 5, a person's walk, in ADR-003 O2)")
    ap.add_argument("--sky-test-minutes", type=float, default=0,
                    help="drop a stone from the sky near Godling this often, announced by a shadow 40 s before it "
                         "lands (a stand-in for viewer events, to measure reactions; 0 = off)")
    ap.add_argument("--bubble", action=argparse.BooleanOptionalAction, default=True,
                    help="show a Sims-style thought bubble over Godling, read from its thoughts by a small model call")
    ap.add_argument("--guest-panel", type=int, default=0, metavar="PORT",
                    help="also serve the guest panel on this port: call down sky powers yourself (0 = off)")
    ap.add_argument("--relay", type=int, default=0, metavar="PORT",
                    help="stream the island to viewers through godling-relay on this port (relay/, ADR-015): one "
                         "connection to the world however many watch (0 = off; with --attach, export the world's "
                         "WORLD_SPECTATOR_TOKEN)")
    ap.add_argument("--memory", choices=("native", "native2", "hindsight"), default="native",
                    help="native = m-003 memory; native2 = brain-like memory; hindsight = Hindsight engine (ADR-002 D4)")
    ap.add_argument("--hindsight-url", default=None, help="use a running Hindsight server instead of starting one")
    args = ap.parse_args()
    # Stop cleanly on Ctrl+C even when started in the background (which ignores SIGINT), and on SIGTERM.
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    run = args.run_dir.expanduser().resolve()
    (run / "mind").mkdir(parents=True, exist_ok=True)
    keep_console(run)
    log_file = (run / "mind/log.jsonl").open("a")
    log_lock = threading.Lock()  # the planner thread logs too
    bubble = None  # the thought bubble hears what happens (ADR-009)

    def log(**entry):
        entry = {"time": round(time.time(), 3), **entry}
        with log_lock:
            log_file.write(json.dumps(entry) + "\n")
            log_file.flush()
            print_entry(entry)
        if bubble is not None:
            if entry.get("kind") == "event":
                bubble.happens(entry.get("text", ""))
            elif entry.get("kind") == "skill":
                bubble.happens(f"{entry.get('skill')}: {str(entry.get('summary', ''))[:160]}")
            elif entry.get("kind") == "project" and entry.get("phase") == "start":
                bubble.does(entry.get("intention") or entry.get("goal"))

    (run / "config.json").write_text(json.dumps({k: str(v) for k, v in vars(args).items()}, indent=2))
    home = Path.home()
    # The world's snapshot route asks for this token (IslandSave); the world started below inherits it.
    os.environ.setdefault("WORLD_OPERATOR_TOKEN", secrets.token_urlsafe(24))
    # Joining the world asks for this key (patches/v2: a name is not free for anyone to claim, ADR-014). The world,
    # the guest panel and this mind inherit it; with --attach, export the attached world's own.
    os.environ.setdefault("WORLD_AGENT_KEY", secrets.token_urlsafe(24))
    if not args.attach:  # for tools that join this run's world later (tools/god_bot.py --run-dir): readable only by you
        key_file = run / "world.key"
        key_file.touch(mode=0o600)
        key_file.chmod(0o600)
        key_file.write_text(os.environ["WORLD_AGENT_KEY"])
    if args.relay:  # the relay follows the world's stream with the world's own spectator token
        os.environ.setdefault("WORLD_SPECTATOR_TOKEN", secrets.token_urlsafe(24))
    # Under WSL the Windows PATH leaks in (Windows npx hangs on Linux paths); children get Linux tools only. None of
    # them gets the DeepSeek key: Hindsight is handed it on its own (start_hindsight).
    clean_env = {**{k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"},
                 "PATH": ":".join([str(home / ".local/bin"), str(home / ".cargo/bin")] + [
                     p for p in os.environ.get("PATH", "").split(":") if p and not p.startswith("/mnt/")])}
    # Installed by cargo (~/.cargo/bin) on a development machine, or on the PATH (the island image: /usr/local/bin);
    # CLAWBLOX_BIN names another build.
    clawblox = (os.environ.get("CLAWBLOX_BIN") or shutil.which("clawblox", path=clean_env["PATH"])
                or str(home / ".cargo/bin/clawblox"))
    # Mounted under WORLD_BASE_PATH (deploy/: /island, so its spectator page can be public), the world's API is too.
    local_world = f"http://localhost:{args.port}" + os.environ.get("WORLD_BASE_PATH", "").rstrip("/")
    save = IslandSave(run, local_world, log)
    island = save.load()  # what the island was when the run last stopped: the world puts it back (main.lua)
    server = hindsight = panel = relay = packer = None
    try:
        if not args.attach:
            world_dir = prepare_world(args.world, run, args.walk_speed, args.sky_test_minutes, island)
            server = subprocess.Popen(
                [clawblox, "run", str(world_dir), "--port", str(args.port),
                 "--record", "--record-dir", str(run / "recordings")],
                stdout=(run / "world.log").open("w"), stderr=subprocess.STDOUT, env=clean_env)
        if args.relay:
            relay = start_relay(args.relay, args.port, run, clean_env)
        if args.memory == "hindsight" and not args.hindsight_url:
            hindsight, args.hindsight_url = start_hindsight(run, clean_env)
        world = World(local_world, args.name)
        llm = LLM(args.model, log=log)
        memory = make_memory(args, run, log)
        library = SkillLibrary(run / "memory" / "skills.json", log=log, protect_proven=args.memory != "native")
        skills = Skills(world, protected=memory.protected_cubes, log=log, gifted=args.gifted_skills, library=library,
                        walk_speed=args.walk_speed, kept_in=memory.built_into,
                        reserved=memory.reserved_cells)
        discovery = Discovery(run / "memory" / "discovery.json")  # the island as far as Godling has seen it
        attention = Attention(memory, busy=lambda: skills.busy, log=log, discovery=discovery)
        skills.on_step = attention.on_step
        skills.next_glance = attention.take_glance
        mind = Mind(llm, memory, args.persona.read_text(), skills, library, name=args.name, log=log, agenda=args.agenda,
                    discovery=discovery, house_project=args.house_project)
    except BaseException:  # stopped or failed while starting: leave no world server holding the port
        stop_children(relay, server, hindsight)
        raise

    started = time.time()
    stats = {"projects": 0, "plans_discarded": 0, "plans_after_failure": 0, "waited_for_mind_s": 0.0}
    structures = StructureLog(run / "mind/structures.jsonl", log)
    try:
        world.wait_until_up()
        spectator = None
        if server:
            spectator = wait_for_line(run / "world.log", r"Spectator frontend: (\S+)", 15)
            if spectator and args.relay:  # the page streams from the relay, on this host (patches/v3)
                spectator += ("&" if "?" in spectator else "?") + f"stream_port={args.relay}"
            restored = island and wait_for_line(run / "world.log", r"ISLAND restored: ([^\n]+)", 5)
            print(f"World is up{f', the island put back ({restored})' if restored else ''}. "
                  f"Watch it here: {spectator or local_world + '/'}", flush=True)
            save.start()
            # The recording, packed for replays as it grows (ADR-016), in a process of its own: catching up on a long
            # recording must never hold up Godling's mind.
            # A session of its own: Ctrl+C in a terminal reaches the world and the mind, and the packer only when
            # the world has stopped (stop_children below), so it packs the world's last seconds too.
            packer = subprocess.Popen([sys.executable, "-m", "godling.replay", "follow", str(run)],
                                      cwd=str(Path(__file__).resolve().parent), env=clean_env, start_new_session=True,
                                      stdout=(run / "replay.log").open("a"), stderr=subprocess.STDOUT)
        world.join()
        if args.bubble:
            bubble = Bubble(world, llm, log=log).start()
            mind.on_reasoning = bubble.thought
        if args.guest_panel:
            panel = subprocess.Popen([sys.executable, str(Path(__file__).resolve().parent.parent / "tools/guest_panel.py"),
                                      "--world", local_world, "--port", str(args.guest_panel),
                                      "--run-dir", str(run)] + (["--view", spectator] if spectator else []),
                                     env=clean_env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            threading.Thread(target=copy_lines, args=(panel.stdout, run / "panel.log"), name="panel-log",
                             daemon=True).start()
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
        if server is not None and server.poll() is None:
            save.stop()
            save.take()  # first: a container being stopped has seconds, not minutes
        if bubble is not None:
            bubble.stop()
        memory.save()
        memory.flush()
        try:
            structures.record(world.observe())  # what stands at the end, while the world still runs
        except Exception as err:
            log(kind="error", message=f"structures at the end: {err!r}"[:200])
        stop_children(panel, relay, server, hindsight)
        stop_children(packer)  # after the world: the last seconds it recorded are packed too
        minutes = (time.time() - started) / 60
        summary = {"minutes": round(minutes, 1), "llm_calls": llm.calls, "cost_usd": round(llm.cost, 4),
                   "model": args.model, "memory_engine": args.memory, "agenda": args.agenda,
                   "house_project": args.house_project,
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


class IslandSave:
    """The island as it stands, kept in <run>/island-save.json so a restart keeps it (ADR-013): the pieces that were
    carried, built with or left by the sky (where they lie, whether fastened, their attributes), the felled trees,
    the day, the numbering, and Godling's body.

    Read from the world's snapshot (GET /snapshot with the operator token) every few minutes and when the run stops;
    put back by the world itself at the next start (prepare_world writes it into the run's main.lua, sky.restore).
    Not Clawblox's --resume: it lost freshly made pieces seconds after resuming, and the world script's timers
    (os.clock) start again from zero in a new process. Godling's memories are in <run>/memory already; with this the
    island they speak of stays.
    """
    EVERY = 300  # seconds: at most five minutes of the island lost to a crash; a clean stop loses nothing

    def __init__(self, run, base, log):
        self.path = run / "island-save.json"
        self.base, self.log = base, log
        self.lock = threading.Lock()
        self.stopping = threading.Event()

    def load(self):
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as err:
            print(f"The island's save could not be read ({err}); the island starts afresh.", flush=True)
            return None

    def take(self):
        with self.lock:
            req = urllib.request.Request(self.base + "/snapshot",
                                         headers={"X-Operator-Token": os.environ["WORLD_OPERATOR_TOKEN"]})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    island = island_of(json.loads(resp.read()))
            except (OSError, ValueError, KeyError, TypeError, IndexError) as err:
                self.log(kind="error", message=f"island save: {err!r}"[:200])
                return False
            part = self.path.with_name(self.path.name + ".part")
            part.write_text(json.dumps(island))
            os.replace(part, self.path)  # only a whole save replaces the last good one
            return True

    def start(self):
        def every():
            while not self.stopping.wait(self.EVERY):
                self.take()
        threading.Thread(target=every, name="island-save", daemon=True).start()

    def stop(self):
        self.stopping.set()


def island_of(snapshot):
    """What a restart keeps, from a Clawblox snapshot (IslandSave)."""
    inst = snapshot["instance"]
    pieces, felled, counters = [], [], {"Sky": 0}
    for c in inst["workspace_children"]:
        name = c.get("name") or ""
        attrs = {k: v["value"] for k, v in (c.get("attributes") or {}).items()
                 if v.get("type") in ("String", "Number", "Bool") and v.get("value") is not None}
        prefix, _, number = name.rpartition("_")
        if prefix in NUMBERED and number.isdigit():
            counters[prefix] = max(counters.get(prefix, 0), int(number))
        if isinstance(attrs.get("SkyId"), (int, float)):
            counters["Sky"] = max(counters["Sky"], int(attrs["SkyId"]))
        part, role = c.get("part"), attrs.get("RenderRole")
        if not part or c.get("class_name") != "Part" or role not in KEPT_ROLES + ("Stump",):
            continue
        if role not in DECOR_ROLES and part["anchored"] and not part["can_collide"]:
            continue  # carried down by the sky and not landed yet (a meteor): it would hang in the air
        attrs.pop("FelledAt", None)  # a time on the old process's clock
        attrs.pop("HeldBy", None)  # in a hand that lets go when the world stops
        kept = {"name": name, "pos": part["cframe"]["position"], "turn": orientation(part["cframe"]["rotation"]),
                "size": part["size"], "color": part["color"], "anchored": part["anchored"],
                "collide": part["can_collide"], "attrs": attrs}
        (felled if role == "Stump" else pieces).append(kept)
    pieces.sort(key=lambda p: (p["attrs"].get("RenderRole") != "Crater", p["name"].rpartition("_")[0],
                               int(p["name"].rpartition("_")[2]) if p["name"].rpartition("_")[2].isdigit() else 0))
    clock = next((c.get("attributes") or {} for c in inst["workspace_children"] if c.get("name") == "Clock"), {})
    day, hour = clock.get("Day", {}).get("value", 1), clock.get("TimeOfDay", {}).get("value", 7)
    body = None
    for p in inst["players"]:
        hrp = p.get("humanoid_root_part") or {}
        if p.get("name") != SKY_PLAYER and hrp.get("position"):
            a = {k: v.get("value") for k, v in (p.get("attributes") or {}).items()}
            body = {"pos": hrp["position"], "health": a.get("Health") or 100, "hunger": a.get("Hunger") or 100,
                    "wet": a.get("Wet") or 0}
    return {"pieces": pieces, "felled": felled, "roles": list(KEPT_ROLES), "counters": counters,
            # main.lua tickClock: Day and TimeOfDay come from the seconds since the first morning (DAY 2400 s, 7 am)
            "clock": max(0.0, (day - 1) * 2400 + hour / 24 * 2400 - 7 / 24 * 2400), "body": body, "saved": time.time()}


def orientation(r):
    """A rotation matrix as Clawblox's CFrame:ToOrientation() gives it (rx, ry, rz), for CFrame.fromOrientation."""
    rx = math.asin(max(-1.0, min(1.0, -r[1][2])))
    if abs(math.cos(rx)) > 1e-6:
        return [rx, math.atan2(r[0][2], r[2][2]), math.atan2(r[1][0], r[1][1])]
    return [rx, math.atan2(-r[2][0], r[0][0]), 0.0]


def lua_literal(value):
    """A JSON-like value as a Lua table constructor (the save written into main.lua)."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(round(float(value), 4)) if math.isfinite(value) else "0"
    if isinstance(value, str):
        # Quote marks, backslashes and control characters as Lua's \ddd; other letters as they are (UTF-8).
        return '"' + "".join(f"\\{ord(c):03d}" if c in '"\\' or (ord(c) < 128 and not c.isprintable()) else c
                             for c in value) + '"'
    if isinstance(value, dict):
        return "{" + ", ".join(f"[{lua_literal(str(k))}] = {lua_literal(v)}" for k, v in value.items()) + "}"
    return "{" + ", ".join(lua_literal(v) for v in value) + "}"


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
    thinking = ThinkingLog(args.run_dir.expanduser().resolve() / "mind/thinking.jsonl", getattr(mind, "on_reasoning", None))

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
            if not future.done():  # the body stands until its mind has thought: the viewers' screen says so
                log(kind="thinking")
            watch_while_thinking(future, world, attention, skills)
            thought = future.result()
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
        log(kind="project", phase="end", goal=project["goal"], intention=project["intention"], ok=ok,
            seconds=round(elapsed, 2))
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


def watch_while_thinking(future, world, attention, skills):
    """No idle behaviours: the body waits for its mind. But it keeps watching, so what happens meanwhile still
    gets a glance, and the next plan hears of it."""
    while not future.done():
        try:
            attention.on_step(world.observe())
        except Interrupted:
            pass  # nothing to interrupt while standing; the event waits for the next plan
        except WorldError:
            pass  # the plan on its way is worth more than one missed look
        skills.steady()  # braced through an earthquake, if the ground rumbles
        skills.glance()
        time.sleep(0.25)


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

    def __init__(self, path, also=None):
        self.file = path.open("a")
        self.lock = threading.Lock()
        self.plans = 0
        self.also = also  # someone else reading along: the thought bubble

    def new_plan(self):
        with self.lock:
            self.plans += 1
            return self.plans

    def write(self, plan, text):  # any thread
        with self.lock:
            self.file.write(json.dumps({"time": round(time.time(), 3), "plan": plan, "text": text}) + "\n")
            self.file.flush()
        if self.also:
            self.also(text)


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

def prepare_world(world, run, walk_speed, sky_test_minutes=0, island=None):
    """Run a frozen copy of the world in the run folder, with only WalkSpeed (Mesa walks at 16), the sky test
    timer and the island as the run left it (IslandSave) changed.

    The copy also records which version of the world a run used."""
    copy = run / "world"
    skip = shutil.ignore_patterns(".clawblox", ".build.lock", "node_modules")
    if not copy.exists():
        shutil.copytree(world, copy, ignore=skip)
    else:  # an existing run keeps its world script, but draws with today's renderer and models: a copy made before
        # the replay player (ADR-016) would otherwise never play the past
        for part in ("renderer", "assets"):
            if (Path(world) / part).is_dir():
                shutil.copytree(Path(world) / part, copy / part, dirs_exist_ok=True, ignore=skip)
    script = copy / "main.lua"
    src = script.read_text()
    src = _set_line(src, "humanoid.WalkSpeed = ", "16", f"{walk_speed:g}", "the walking pace")
    src = _set_line(src, "local SKY_TEST_EVERY = ", "0", f"{sky_test_minutes * 60:g}", "the sky test timer")
    saved, n = re.subn(r"(?m)^sky\.saved = .* -- ISLAND SAVE$",
                       lambda _: f"sky.saved = {lua_literal(island)} -- ISLAND SAVE", src)
    if n != 1 and island:  # a run copied before the island was kept: it runs as it always did
        print("This run's copy of the world script cannot put the island back (no ISLAND SAVE line); "
              "the island starts afresh.", flush=True)
    script.write_text(saved if n == 1 else src)
    return copy


def _set_line(src, prefix, default, value, what):
    if prefix + value in src:
        return src
    if src.count(prefix + default) != 1:
        raise SystemExit(f"could not find '{prefix}{default}' in the world script to set {what}")
    return src.replace(prefix + default, prefix + value)


def make_memory(args, run, log):
    if args.memory == "native2":
        from godling.memory2 import BrainMemory
        return BrainMemory(run / "memory")
    if args.memory == "hindsight":
        from godling.memory_hindsight import HindsightMemory
        return HindsightMemory(run / "memory", args.hindsight_url, bank_id=f"godling-{run.name}", log=log)
    return NativeMemory(run / "memory")


def start_relay(port, world_port, run, env):
    """The island's stream relay (relay/, ADR-015) on `port`: it follows this world's spectator stream, with the world's
    token, and hands every viewer the same updates. It waits for the world itself, so it may start before the world is
    up. RELAY_LISTEN (deploy/: 0.0.0.0:8082) overrides where viewers connect; RELAY_BIN names another build."""
    exe = (os.environ.get("RELAY_BIN") or shutil.which("godling-relay", path=env["PATH"])
           or str(Path(__file__).resolve().parent.parent / "relay/target/release/godling-relay"))
    if not Path(exe).exists():
        raise SystemExit(f"godling-relay is not built ({exe} missing): cargo build --release in relay/")
    base = os.environ.get("WORLD_BASE_PATH", "").rstrip("/")
    env = {"RELAY_LISTEN": f"127.0.0.1:{port}", **env, "RELAY_UPSTREAM": f"ws://127.0.0.1:{world_port}{base}/spectate/ws",
           "RELAY_BASE_PATH": base, "RELAY_SPECTATOR_TOKEN": os.environ["WORLD_SPECTATOR_TOKEN"]}
    return subprocess.Popen([exe], stdout=(run / "relay.log").open("w"), stderr=subprocess.STDOUT, env=env)


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

class Tee:
    """Writes go to every stream; anything else is the first stream's."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
        return len(text)

    def flush(self):
        for stream in self.streams:
            stream.flush()

    def __getattr__(self, name):
        return getattr(self.streams[0], name)


def keep_console(run):
    """The console, also kept in <run>/console.log: the site's log viewer reads it there (web/apps/users/log_views.py),
    and in deploy/ the console otherwise goes only to the container's output. Not when the run was started with its
    output already going to that file (`run_godling.py … > console.log`)."""
    path = run / "console.log"
    try:
        if path.exists() and os.path.samestat(os.fstat(sys.stdout.fileno()), path.stat()):
            return
    except (OSError, ValueError, AttributeError):
        pass
    kept = path.open("a", errors="replace")
    sys.stdout, sys.stderr = Tee(sys.stdout, kept), Tee(sys.stderr, kept)


def copy_lines(stream, path):
    """A child's output on the console and in its own log (the guest panel's: <run>/panel.log)."""
    with path.open("a", errors="replace") as kept:
        for line in stream:
            kept.write(line)
            kept.flush()
            print(line, end="", flush=True)


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
        if entry.get("needs"):
            print(f"[{stamp}] NEEDS  {entry['needs']}", flush=True)
    elif kind == "glance":
        print(f"[{stamp}] GLANCE {'turned ' + str(entry['degrees']) + '° towards' if entry['turned'] else 'saw'}: "
              f"{entry['text']}", flush=True)
    elif kind == "brace":
        print(f"[{stamp}] BRACE  {'crouched and holding on' if entry['ok'] else 'could not brace'} "
              f"(the ground: {entry['phase']})", flush=True)
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
    elif kind == "bubble":
        print(f"[{stamp}] BUBBLE " + (f"{entry['thing']}, {entry['feeling']}" if entry["ok"] else f"unreadable: {entry['reply']}"),
              flush=True)
    elif kind in ("forget", "forget_refused"):
        print(f"[{stamp}] {'FORGET' if kind == 'forget' else 'KEEP  '} skill {entry['name']}", flush=True)
    elif kind == "learn":
        print(f"[{stamp}] LEARN  new skill {entry['name']}({', '.join(entry['params'])}) v{entry['version']}: {entry['does']}", flush=True)
    elif kind == "sleep":
        print(f"[{stamp}] SLEEP  {entry.get('dream', '')}\n[{stamp}]        intentions: {[i['text'] for i in entry['intentions']]}", flush=True)
    elif kind == "structures":
        print(f"[{stamp}] BUILT  houses {entry.get('houses', 0)}, walls {entry['walls']}, enclosures {entry['enclosures']} ({entry['roofed']} roofed), "
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
