"""Skills the mind teaches itself (Voyager-style, but declarative and safe: no code execution).

A learned skill is a named sequence of steps over primitives or other learned skills. Step arguments
may use parameters ("$object") and a few perception helpers, resolved against a fresh observation
right before each step runs:
    {"pos": "$object"}          -> [x, y, z] centre of that object
    {"top": "$object"}          -> [x, y, z] of the top surface of the stack the object is in
    {"add": [a, b]}             -> element-wise sum of two vectors, e.g. {"add": [{"top": "$o"}, [0, 0.4, 0]]}
    {"x": vec} / {"y": vec} / {"z": vec} -> one coordinate of a vector
    {"nearest_free": "cube"}    -> name of the nearest cube nobody has claimed ("brick" and "stone" too)
A step may carry "repeat": n (up to 12). A new skill is "unproven" until one full run succeeds.
"""
import json
import time
from pathlib import Path

from .files import write_atomic
from .skills import PRIMITIVES, Result
from .world import PIECE_KINDS

MAX_STEPS = 12


class SkillError(ValueError):
    pass


class SkillLibrary:
    def __init__(self, path, log=None, protect_proven=False):
        self.path = Path(path)
        self.log = log or (lambda **kw: None)
        # Procedural memory like a habit: a skill that has proven itself is not dropped on a whim.
        self.protect_proven = protect_proven
        self.skills = json.loads(self.path.read_text()) if self.path.exists() else {}

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
        previous = self.skills.get(name)
        self.skills[name] = {"params": params, "steps": steps, "does": str(spec.get("does", ""))[:200],
                             "status": "unproven", "uses": 0, "successes": 0, "defined_tick": tick,
                             "version": (previous or {}).get("version", 0) + 1}
        self.save()
        self.log(kind="learn", name=name, params=params, steps=steps, does=self.skills[name]["does"],
                 version=self.skills[name]["version"])
        return name

    def forget(self, name):
        """Drop a skill. With protect_proven, a skill with 3+ successes stays unless its last 3 runs failed.

        Returns a reason string when the skill was kept, so the mind learns why."""
        spec = self.skills.get(name)
        if spec is None:
            return None
        recent = spec.get("recent", [])
        if self.protect_proven and spec["successes"] >= 3 and not (len(recent) >= 3 and not any(recent[-3:])):
            self.log(kind="forget_refused", name=name, successes=spec["successes"], uses=spec["uses"])
            return (f"'{name}' was kept: it has worked {spec['successes']} of {spec['uses']} times. "
                    "Redefine it with 'learn' to improve it instead.")
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
        ok = True
        skills._depth += 1  # the whole learned skill is one action for attention's "busy" tracking
        try:
            ok = self._run_steps(skills, spec, bound, done)
        finally:
            skills._depth -= 1
            if skills._depth == 0:
                skills.busy.clear()
        spec["uses"] += 1
        spec["successes"] += ok
        spec["recent"] = (spec.get("recent", []) + [bool(ok)])[-5:]
        if ok and spec["status"] == "unproven":
            spec["status"] = "proven"
        self.save()
        summary = (f"{name} worked" if ok else f"{name} failed") + ": " + " | ".join(done[-6:])
        result = Result(ok, name, summary, {"learned": True}, round(time.time() - started, 2))
        skills.log(kind="skill", skill=name, args=args, ok=ok, summary=summary, facts=result.facts,
                   seconds=result.seconds, learned=True)
        return result

    def _run_steps(self, skills, spec, bound, done):
        for step in spec["steps"]:
            for _ in range(max(1, min(12, int(step.get("repeat", 1))))):
                try:
                    resolved = self._resolve(step.get("args", {}), bound, skills)
                except (SkillError, TypeError, ValueError, KeyError, IndexError) as err:
                    done.append(f"{step['skill']}: could not work out arguments ({err})")
                    return False
                r = skills.run(step["skill"], resolved)
                done.append(f"{step['skill']}: {r.summary}")
                if not r.ok:
                    return False
        return True

    def resolve_helpers(self, args, skills):
        """Resolve perception helpers in a step outside any learned skill (no parameters there)."""
        return self._resolve(args, {}, skills)

    def _resolve(self, value, bound, skills):
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
                free = [e for e in skills._free_pieces(snap) if PIECE_KINDS[kind](e)]
                if not free:
                    raise SkillError(f"no free {kind} left")
                return min(free, key=lambda c: (c.pos[0] - snap.me[0]) ** 2 + (c.pos[2] - snap.me[2]) ** 2).name
        return {k: self._resolve(v, bound, skills) for k, v in value.items()}
