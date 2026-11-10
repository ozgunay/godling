"""Skills the mind teaches itself (Voyager-style, but declarative and safe: no code execution).

A learned skill is a named sequence of steps over primitives or other learned skills. Step arguments
may use parameters ("$object") and a few perception helpers, resolved against a fresh observation
right before each step runs:
    {"pos": "$object"}          -> [x, y, z] centre of that object
    {"top": "$object"}          -> [x, y, z] of the top surface of the stack the object is in
    {"add": [a, b]}             -> element-wise sum of two vectors, e.g. {"add": [{"top": "$o"}, [0, 0.4, 0]]}
    {"x": vec} / {"y": vec} / {"z": vec} -> one coordinate of a vector
    {"nearest_free": "cube"}    -> name of the nearest cube nobody has claimed ("brick" and "stone" too) that the
                                   body can walk to; as pick_up's object, the one in the hands if it is one (ADR-027)
A step may carry "repeat": n (up to 12). A new skill is "unproven" until one full run succeeds.

A skill that has worked keeps its steps (it can be neither forgotten nor taught other steps) until it has failed, in a
row since it last worked, as many times as it has ever worked and at least three times, or has gone two hours without
working (ADR-032). A skill that never worked, or whose steps call a skill that is gone, can go at once. A run that
attention cuts short says nothing about the skill and is not counted.
"""
import json
import time
from pathlib import Path

from .files import write_atomic
from .skills import PRIMITIVES, Interrupted, Result, Stuck
from .world import PIECE_KINDS

MAX_STEPS = 12
NEAREST_TRIES = 6  # nearest_free: of the nearest pieces, how many it works out a way to before taking the nearest
MIN_FAILS_TO_FORGET = 3  # failures in a row since its last success before even a skill that worked once may go
# Seconds without working, counted from the skill's last success or the library's load (so downtime never counts),
# after which a skill that has worked may go. In the live run of 2026-11-08/09, 99% of the gaps between a proven
# skill's successes were under 85 minutes.
FORGET_WHEN_IDLE = 2 * 3600
KEPT_LAST = 5  # how many outcomes code from before ADR-032 kept in `recent`


class SkillError(ValueError):
    pass


def migrate(spec):
    """Code from before ADR-032 kept the last five outcomes in `recent`, not a count; this code never writes it.

    So a record with `recent` was last written by older code: saved before ADR-032, or run by older code after a
    rollback, which leaves a stored count behind. With a success in `recent` the count is exact; with none, the
    failures there come on top of any stored count, and when `recent` is full that is only a lower bound."""
    recent = spec.pop("recent", None)
    spec.setdefault("fails_in_a_row", 0)
    if recent is None:
        return
    if any(recent):
        spec["fails_in_a_row"] = len(recent) - 1 - max(i for i, ok in enumerate(recent) if ok)
        spec.pop("fails_at_least", None)
    else:
        spec["fails_in_a_row"] += len(recent)
        if len(recent) >= KEPT_LAST and spec["successes"]:
            spec["fails_at_least"] = True


class SkillLibrary:
    def __init__(self, path, log=None):
        self.path = Path(path)
        self.log = log or (lambda **kw: None)
        self.skills = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.loaded_at = time.time()
        for spec in self.skills.values():
            migrate(spec)

    def save(self):
        write_atomic(self.path, json.dumps(self.skills, indent=2))

    # ---- teaching ---------------------------------------------------------------------
    def define(self, spec, tick=0):
        name = str(spec.get("name", "")).strip()
        if not name.isidentifier() or name in PRIMITIVES:
            raise SkillError(f"'{name}' is not a usable skill name")
        params = [str(p) for p in spec.get("params", [])]
        steps = spec.get("steps") or []
        if not 1 <= len(steps) <= MAX_STEPS:
            raise SkillError(f"a skill needs 1-{MAX_STEPS} steps")
        for step in steps:
            used = step.get("skill")
            if used not in PRIMITIVES and used not in self.skills:
                raise SkillError(f"step uses unknown skill '{used}'")
            if used == name:
                raise SkillError("a skill cannot call itself")
            if self._calls(used, name):
                raise SkillError(f"step uses '{used}', which calls '{name}': a skill cannot call itself, "
                                 "even through another skill")
        previous = self.skills.get(name)
        does = str(spec.get("does", ""))[:200]
        if previous and previous["params"] == params and previous["steps"] == steps:
            previous["does"] = does  # the same skill taught again: its record stands
        else:
            kept = previous and self._kept(previous)
            if kept:  # other steps under its name would throw away the steps that worked
                _, needed = kept
                raise SkillError(f"'{name}' has worked {previous['successes']} of {previous['uses']} times, so its "
                                 f"steps stay as they are until it has failed {needed} runs in a row or gone "
                                 f"{FORGET_WHEN_IDLE // 3600} hours without working: teach the new steps under a "
                                 "new name")
            self.skills[name] = {"params": params, "steps": steps, "does": does, "status": "unproven", "uses": 0,
                                 "successes": 0, "fails_in_a_row": 0, "defined_tick": tick,
                                 "version": (previous or {}).get("version", 0) + 1}
        self.save()
        self.log(kind="learn", name=name, params=params, steps=steps, does=self.skills[name]["does"],
                 version=self.skills[name]["version"])
        return name

    def _calls(self, start, target):
        """Whether learned skill `start` reaches `target` through the library's steps."""
        seen, todo = set(), [start]
        while todo:
            name = todo.pop()
            if name == target:
                return True
            if name in seen or name not in self.skills:
                continue
            seen.add(name)
            todo.extend(step.get("skill") for step in self.skills[name]["steps"])
        return False

    def _kept(self, spec):
        """(failed runs in a row, runs needed) while a skill that has worked keeps its steps (ADR-032), else None.

        A skill's steps never change once learned, so after they have worked, a failure says more about the situation
        (a blocked way, full hands) than about the skill. Unless a skill it calls is gone: then it cannot work again."""
        if not spec["successes"] or any(s.get("skill") not in PRIMITIVES and s.get("skill") not in self.skills
                                        for s in spec["steps"]):
            return None
        failed, needed = spec["fails_in_a_row"], max(MIN_FAILS_TO_FORGET, spec["successes"])
        idle = time.time() - max(spec.get("worked_at", 0.0), self.loaded_at)
        return (failed, needed) if failed < needed and idle < FORGET_WHEN_IDLE else None

    def forget(self, name):
        """Drop a skill, unless it has worked and keeps its steps (`_kept`). Returns the reason when the skill was
        kept, so the mind learns why."""
        spec = self.skills.get(name)
        if spec is None:
            return None
        kept = self._kept(spec)
        if kept:
            failed, needed = kept
            self.log(kind="forget_refused", name=name, successes=spec["successes"], uses=spec["uses"],
                     fails_in_a_row=failed, needed=needed)
            some = "at least" if spec.get("fails_at_least") else "only"
            since = ("its last run worked" if failed == 0 else "only its last run failed" if failed == 1
                     else f"{some} its last {failed} runs failed")
            return (f"'{name}' was kept: it has worked {spec['successes']} of {spec['uses']} times and {since}. "
                    f"A skill that has worked is forgotten only after {needed} failed runs in a row, or after "
                    f"{FORGET_WHEN_IDLE // 3600} hours without working. To try other steps, teach them under a new name.")
        self.skills.pop(name)
        self.save()
        self.log(kind="forget", name=name)
        return None

    def describe(self):
        lines = []
        for name, s in self.skills.items():
            rate = f"{s['successes']}/{s['uses']} runs succeeded" if s["uses"] else "never run yet"
            lines.append(f"- {name}({', '.join(s['params'])}) [{s['status']}, {rate}]: {s['does']}")
        return "\n".join(lines)

    # ---- doing ------------------------------------------------------------------------
    def execute(self, skills, name, args):
        started = time.time()
        spec = self.skills[name]
        bound = {p: args.get(p) for p in spec["params"]}
        missing = [p for p, v in bound.items() if v is None]
        if missing:
            return Result(False, name, f"missing arguments: {', '.join(missing)}")
        done = []
        ok = None  # True: it worked; False: it failed; None: attention cut it short, which says nothing about the skill
        skills._depth += 1  # the whole learned skill is one action for attention's "busy" tracking
        try:
            ok = self._run_steps(skills, spec, bound, done)
        except Exception as err:  # Skills.run reports it ("broke while running"); for the record, a failed run of it,
            ok = None if isinstance(err, Interrupted) and not isinstance(err, Stuck) else False  # unless attention
            raise
        finally:
            skills._depth -= 1
            if skills._depth == 0:
                skills.busy.clear()
            if ok is not None:
                self._count(spec, ok)
        outcome = "worked" if ok else "was interrupted" if ok is None else "failed"
        summary = f"{name} {outcome}: " + " | ".join(done[-6:])
        facts = {"learned": True, **({"interrupted": True} if ok is None else {})}
        result = Result(bool(ok), name, summary, facts, round(time.time() - started, 2))
        skills.log(kind="skill", skill=name, args=args, ok=bool(ok), summary=summary, facts=result.facts,
                   seconds=result.seconds, learned=True)
        return result

    def _count(self, spec, ok):
        spec["uses"] += 1
        spec["successes"] += ok
        spec["fails_in_a_row"] = 0 if ok else spec["fails_in_a_row"] + 1
        if ok:
            spec["worked_at"] = time.time()
            spec.pop("fails_at_least", None)
            spec["status"] = "proven"
        self.save()

    def _run_steps(self, skills, spec, bound, done):
        """True when every step worked, False at the first that failed, None when attention cut a step short."""
        for step in spec["steps"]:
            for _ in range(max(1, min(12, int(step.get("repeat", 1))))):
                try:
                    resolved = self._resolve_args(step["skill"], step.get("args", {}), bound, skills)
                except (SkillError, TypeError, ValueError, KeyError, IndexError) as err:
                    done.append(f"{step['skill']}: could not work out arguments ({err})")
                    return False
                r = skills.run(step["skill"], resolved)
                done.append(f"{step['skill']}: {r.summary}")
                if r.facts.get("interrupted"):
                    return None
                if not r.ok:
                    return False
        return True

    def resolve_helpers(self, args, skills, skill=None):
        """Resolve perception helpers in a step outside any learned skill (no parameters there)."""
        return self._resolve_args(skill, args, {}, skills)

    def _resolve_args(self, skill, args, bound, skills):
        """A step's arguments, one by one. pick_up's object may be the piece already in the hands (ADR-027)."""
        if not isinstance(args, dict):
            return self._resolve(args, bound, skills)
        return {k: self._resolve(v, bound, skills, holding=skill == "pick_up" and k == "object")
                for k, v in args.items()}

    def _resolve(self, value, bound, skills, holding=False):
        if isinstance(value, str) and value.startswith("$"):
            if value[1:] not in bound:
                raise SkillError(f"unknown parameter {value}")
            return bound[value[1:]]
        if isinstance(value, list):
            return [self._resolve(v, bound, skills) for v in value]
        if not isinstance(value, dict):
            return value
        if len(value) == 1:
            (op, arg), = value.items()
            snap = skills.world.observe()
            if op == "pos":
                obj = snap.entities.get(self._resolve(arg, bound, skills))
                if obj is None:
                    raise SkillError(f"no object {arg}")
                return list(obj.pos)
            if op == "top":
                column = snap.column(self._resolve(arg, bound, skills))
                if not column:
                    raise SkillError(f"no object {arg}")
                top = column[-1]
                return [top.pos[0], top.top, top.pos[2]]
            if op == "add":
                a, b = (self._resolve(v, bound, skills) for v in arg)
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    return float(a) + float(b)
                if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
                    return [float(p) + float(q) for p, q in zip(a, b)]
                raise SkillError(f"add needs two numbers or two vectors of the same length, got {a!r} and {b!r}")
            if op in ("x", "y", "z"):
                return float(self._resolve(arg, bound, skills)["xyz".index(op)])
            if op == "nearest_free":
                kind = self._resolve(arg, bound, skills)
                if kind not in PIECE_KINDS:
                    raise SkillError(f"nearest_free looks for one of {', '.join(PIECE_KINDS)}, not {kind!r}")
                held = snap.held()
                if holding and held is not None and PIECE_KINDS[kind](held):
                    # To pick up, the one in the hands is the nearest (ADR-027): in the live run of 2026-11-08 the wall
                    # skill upright_log_at, used 283 times, reached past the log in its hands for another, and with
                    # nowhere to set the held one down every wall step failed. As a target (pos, top) it is not one.
                    return held.name
                free = sorted((e for e in skills._free_pieces(snap) if PIECE_KINDS[kind](e)),
                              key=lambda c: (c.pos[0] - snap.me[0]) ** 2 + (c.pos[2] - snap.me[2]) ** 2)
                if not free:
                    raise SkillError(f"no free {kind} left")
                # The nearest the body can walk to, of the nearest few (in that run it took the same log it could not
                # reach five times); if none of those, the nearest, and pick_up says why.
                reachable = skills._walkable(snap)
                return next((e.name for e in free[:NEAREST_TRIES] if reachable(e)), free[0].name)
        return {k: self._resolve(v, bound, skills) for k, v in value.items()}
