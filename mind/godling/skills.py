"""L1 skills: deterministic motor programs. The mind picks skills; it never steers the body.

Every skill checks reach and clearance with the world's real constants, routes around loose
objects (walking through cubes scatters them), and verifies the outcome from a fresh observation.
"""
import heapq
import math
import time
from dataclasses import dataclass, field

from .world import (BODY_CENTRE_Y, BUILDING_KINDS, CUBE, FASTEN_SECONDS, LADDER_HEIGHT, LIFT_SECONDS, PICKUP_RANGE,
                    PLACE_RANGE, PLACE_SECONDS, SKY_MARKERS, SNAPPED_KINDS, STEP, STRIKE_RANGE, STRIKE_SECONDS,
                    TOOL_KINDS, TURN_RATE, WALK_SPEED, WorldError, grid, hdist, turned_size)

# What the body can do. These know the body's own limits (reach, not walking through things)
# but no strategy: how to stack, aim or build has to be learned by the mind.
PRIMITIVES = {
    "walk_to": ({"x": "number", "z": "number"},
                "Walk to a point on the level you stand on, going around obstacles. A point on higher ground "
                "takes you to the foot of it."),
    "pick_up": ({"object": "name such as Block_3, Brick_2, Log_1, Hammer_1 or Ladder_1"},
                "Walk within reach of that object and pick it up. If your hands are full, you first set down "
                "what you hold beside you."),
    "put_down": ({"x": "number", "z": "number", "turn": "0 or 90 (optional)", "upright": "true or false (optional)"},
                 "Set the held object down at (x, z) on the floor you stand on. turn 90 turns it a quarter round; "
                 "upright stands a long piece on its end. A ladder always stands up."),
    "place_at": ({"x": "number", "y": "number", "z": "number", "turn": "0 or 90 (optional)",
                  "upright": "true or false (optional)"},
                 "Release the held object with its centre at exactly (x, y, z), turned and stood on end as asked. "
                 "The world says where it ended up."),
    "throw": ({"x": "number", "y": "number", "z": "number", "speed": "number 0-10"},
              "Throw the held object in direction (x, y, z). The world says where it landed."),
    "jump": ({}, "Jump."),
    "strike": ({"object": "what to strike, such as Quarry, Tree_2 or Brick_4"},
               "Walk within reach of it and strike it once with the tool in your hands. The world says what happened."),
    "fasten": ({"object": "a piece you have set down"},
               "Walk within reach and fasten that piece to everything it touches, so they hold together. Takes a "
               "few seconds; fastened pieces cannot be picked up."),
    "climb": ({"object": "a ladder that stands upright, such as Ladder_1"},
              "Walk to the ladder and climb it: up to whatever its top reaches, or back down when you are at the top."),
    "say": ({"text": "string"}, "Say something in the world chat; anyone nearby can read it."),
    "wait": ({"seconds": "number 1-30"}, "Stand still and watch the world."),
}
# Ready-made strategies, only offered with --gifted-skills (the comparison arm).
GIFTED = {
    "stack_on": ({"object": "name of a cube"},
                 "Put the held cube on top of the stack that cube belongs to."),
    "build_tower": ({"x": "number", "z": "number", "height": "integer 2-12"},
                    "Gather free cubes and stack them into a tower standing at (x, z)."),
}
CATALOG = {**PRIMITIVES, **GIFTED}


MAX_DROP = 2.6  # the highest drop the body hops down from; higher needs a ladder
GLANCE_IN_VIEW = 45  # degrees: something this close to straight ahead is already in view, no turn needed
GLANCE_HOLD = 0.4  # seconds the body keeps looking before it goes on


def _quarter(turn):
    """A piece is either turned a quarter round (90) or not (0)."""
    try:
        return 90 if round(float(turn)) % 180 == 90 else 0
    except (TypeError, ValueError):
        return 0


def _flag(value):
    return value is True or str(value).strip().lower() in ("true", "yes", "1")


def _rotation(turn, upright):
    """What the world's Place takes: a quarter turn about the vertical, and a long piece stood on its end."""
    return {"yaw": turn, "pitch": 0, "roll": 90 if upright else 0}


def _orientation(turn, upright):
    return (", stood on end" if upright else "") + (", turned a quarter round" if turn else "")


@dataclass
class Result:
    ok: bool
    skill: str
    summary: str
    facts: dict = field(default_factory=dict)
    seconds: float = 0.0


class Interrupted(Exception):
    pass


class Skills:
    def __init__(self, world, protected=lambda: set(), on_step=None, log=None, gifted=False, library=None,
                 walk_speed=WALK_SPEED):
        self.world = world
        self.walk_speed = walk_speed  # must match the world's humanoid WalkSpeed (used for walk timeouts)
        self.protected = protected  # names of cubes the mind wants left alone
        self.on_step = on_step  # attention hook: called with each snapshot, may raise Interrupted
        self.next_glance = lambda: None  # attention hook: an event worth a look, taken between steps
        self.log = log or (lambda **kw: None)
        self.offered = {**PRIMITIVES, **(GIFTED if gifted else {})}
        self.library = library  # skills the mind taught itself (learned.SkillLibrary)
        self.busy = set()  # objects the current skill is handling; attention ignores their movement
        self._depth = 0

    # ---- entry point -------------------------------------------------------------------
    def run(self, skill, args):
        if self._depth == 0:
            self.glance()
        started = time.time()
        if self.library is not None and any(isinstance(v, dict) for v in args.values()):
            # Perception helpers ({"nearest_free": "cube"}, {"pos": ...}) work in any step, not only inside learned skills.
            try:
                args = self.library.resolve_helpers(args, self)
            except Exception as err:
                return Result(False, skill, f"could not work out arguments ({err})")
        if self.library is not None and skill in self.library.skills:
            try:
                return self.library.execute(self, skill, args)
            except Interrupted as why:
                return Result(False, skill, f"interrupted: {why}")
            except Exception as err:  # a broken self-taught skill must never take the body down
                self.log(kind="error", message=f"learned skill {skill} crashed: {err!r}")
                return Result(False, skill, f"{skill} broke while running ({err}); fix or forget it")
        fn = getattr(self, "skill_" + skill, None)
        allowed = skill in self.offered or (self._depth > 0 and skill in CATALOG)  # gifted skills may nest
        if not allowed or fn is None:
            return Result(False, skill, f"unknown skill '{skill}'")
        self._depth += 1
        if isinstance(args.get("object"), str):
            self.busy.add(args["object"])
        try:
            result = fn(**args)
        except Interrupted as why:
            result = Result(False, skill, f"interrupted: {why}")
        except (TypeError, ValueError) as err:
            result = Result(False, skill, f"bad arguments: {err}")
        except WorldError as err:
            result = Result(False, skill, f"world error: {err}")
        except Exception as err:  # never let a body bug end the run; report it like any failure
            self.log(kind="error", message=f"skill {skill} crashed: {err!r}")
            result = Result(False, skill, f"{skill} failed unexpectedly ({err})")
        finally:
            self._depth -= 1
            if self._depth == 0:
                self.busy.clear()
        result.seconds = round(time.time() - started, 2)
        self.log(kind="skill", skill=skill, args=args, ok=result.ok, summary=result.summary,
                 facts=result.facts, seconds=result.seconds)
        return result

    def glance(self):
        """Reflex: turn towards what attention just noticed, between steps (and while standing). It never changes
        the plan: the noticing is shown, and the mind hears of the event in its next plan as before."""
        event = self.next_glance()
        if not event:
            return
        try:
            snap = self.world.observe()
            x, z = event["at"]
            dx, dz = x - snap.me[0], z - snap.me[2]
            degrees = 0.0
            if snap.facing and math.hypot(dx, dz) > 0.5:
                fx, fz = snap.facing
                degrees = abs(math.degrees(math.atan2(fx * dz - fz * dx, fx * dx + fz * dz)))
            turned = math.hypot(dx, dz) > 0.5 and (snap.facing is None or degrees > GLANCE_IN_VIEW)
            if turned:
                self.world.act("Face", {"position": [x, BODY_CENTRE_Y, z]})
                time.sleep(math.radians(degrees or 180) / TURN_RATE + GLANCE_HOLD)
            self.log(kind="glance", text=event["text"], at=event["at"], turned=turned, degrees=round(degrees),
                     tick=snap.tick, **{k: event[k] for k in ("sky", "sky_id") if k in event})
        except WorldError as err:
            self.log(kind="error", message=f"glance: {err}")

    # ---- helpers -----------------------------------------------------------------------
    def _observe(self):
        snap = self.world.observe()
        if self.on_step:
            self.on_step(snap)
        return snap

    def _free_cubes(self, snap, exclude=()):
        """Cubes that may be taken: not kept, not held, and only the top of any loose stack."""
        return [p for p in self._free_pieces(snap, exclude) if p.is_cube]

    def _free_pieces(self, snap, exclude=()):
        """Building pieces (cubes and long stones) that may be taken: not kept, not held, not under a stack."""
        held = snap.held()
        blocked = set(self.protected()) | set(exclude) | ({held.name} if held else set())
        below_top = {n for _, names in snap.stacks() for n in names[:-1]}
        return [p for p in snap.movables() if (p.is_cube or p.name.startswith(BUILDING_KINDS))
                and p.name not in blocked | below_top and not p.attrs.get("Fastened")
                and snap.ground_top(p.pos[0], p.pos[2]) is not None]

    def _obstacles(self, snap, ignore=()):
        held = snap.held()
        return [e for e in snap.movables() if e.name not in ignore and e is not held]

    def _in_the_way(self, snap, ignore=()):
        """Loose things that stick up from the floor we stand on (what we stand on, or what lies below it, is not)."""
        level = self._level(snap)
        return [e for e in self._obstacles(snap, ignore) if e.top > level + STEP and e.pos[1] - e.size[1] / 2 < level + 3]

    def _level(self, snap):
        """Height of the surface we are standing on: the ground, a mesa, or pieces we built and climbed onto."""
        feet = snap.me[1] - BODY_CENTRE_Y
        level = snap.surface(snap.me[0], snap.me[2], below=feet + STEP)[0]
        return 0.0 if level is None else level

    def _walls(self, snap):
        """Terrain higher than our level: we cannot climb it, so routes go around it."""
        level = self._level(snap)
        return [t for t in snap.terrain() if t.top > level + 0.5]

    def _blocked_fn(self, snap, ignore=()):
        """Is the body unable to stand at (x, z)? Off our level, hugging a wall, or on a loose object.

        Walls get 1.6 units of clearance, not just the body's 1.0 radius: the character controller
        snags when it slides along a wall it is touching.
        """
        level = self._level(snap)
        walls = [(w.pos[0], w.pos[2], w.size[0] / 2 + 1.6, w.size[2] / 2 + 1.6) for w in self._walls(snap)]
        # Boxes, not circles: at block scale a circle clips a block's corners and the body snags on them.
        things = [(o.pos[0], o.pos[2], o.size[0] / 2 + 1.2, o.size[2] / 2 + 1.2) for o in self._in_the_way(snap, ignore)]
        floors = snap.standables(below=level + STEP)  # everything we could stand on from this level

        def blocked(x, z):
            if snap.ground_top(x, z) is None:  # open sea
                return True
            ground = max((top for cx, cz, hx, hz, top, _ in floors if abs(x - cx) <= hx and abs(z - cz) <= hz), default=None)
            if ground is None or abs(ground - level) > 0.3:  # off our floor: a drop, or a step too high
                return True
            if any(abs(x - wx) < hx and abs(z - wz) < hz for wx, wz, hx, hz in walls):
                return True
            return any(abs(x - ox) < hx and abs(z - oz) < hz for ox, oz, hx, hz in things)
        return blocked

    def _route(self, snap, start, goal, ignore=(), escaped=False):
        """Waypoints from start to goal (x, z): A* over 1-unit cells, then smoothed into straight legs."""
        blocked = self._blocked_fn(snap, ignore)

        def clear(a, b):
            steps = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.5))
            return not any(blocked(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
                           for i in range(1, steps))

        if clear(start, goal):
            return [goal]
        if not escaped and blocked(*start):
            # Standing inside the clearance kept around walls and things (pressed against a wall, boxed in by a
            # ladder): first step out to the nearest clear spot, then plan from there.
            for radius in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
                out = [(start[0] + radius * math.cos(k * math.pi / 8), start[1] + radius * math.sin(k * math.pi / 8))
                       for k in range(16)]
                out = [p for p in out if not blocked(*p)]
                if out:
                    escape = min(out, key=lambda p: math.dist(p, goal))
                    return [escape] + self._route(snap, escape, goal, ignore, escaped=True)
        s, g = (round(start[0]), round(start[1])), (round(goal[0]), round(goal[1]))
        frontier = [(math.dist(s, g), 0.0, s)]
        came, cost = {s: None}, {s: 0.0}
        while frontier:
            _, so_far, cell = heapq.heappop(frontier)
            if cell == g or len(came) > 40000:
                break
            if so_far > cost.get(cell, math.inf):
                continue
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nxt = (cell[0] + dx, cell[1] + dz)
                if nxt != g and blocked(*nxt):
                    continue
                c = so_far + math.hypot(dx, dz)
                if c < cost.get(nxt, math.inf):
                    cost[nxt], came[nxt] = c, cell
                    heapq.heappush(frontier, (c + math.dist(nxt, g), c, nxt))
        if g not in came:
            return [goal]  # no known way round; walk straight and let the stuck check report it
        cells, cell = [], g
        while cell is not None:
            cells.append(cell)
            cell = came[cell]
        cells = [start] + [(float(x), float(z)) for x, z in reversed(cells[:-1])] + [goal]
        path, i = [], 0
        while i < len(cells) - 1:  # keep only the corners: jump to the farthest cell still in clear sight
            j = len(cells) - 1
            while j > i + 1 and not clear(cells[i], cells[j]):
                j -= 1
            path.append(cells[j])
            i = j
        return path

    def _move(self, x, z, stop_within=0.6, ignore=(), replans=1):
        snap = self._observe()
        try:
            for wx, wz in self._route(snap, (snap.me[0], snap.me[2]), (x, z), ignore):
                snap = self._move_once(wx, wz, stop_within if (wx, wz) == (x, z) else 1.0)
        except Interrupted as why:
            if replans <= 0 or not str(why).startswith("stuck"):
                raise
            # Something moved or the body was pushed off its route: look again and find another way, once.
            self.log(kind="reflex", text=f"{why}; looking for another way")
            time.sleep(0.3)
            return self._move(x, z, stop_within, ignore, replans - 1)
        return snap

    def _move_once(self, x, z, stop_within, retry=True):
        # The humanoid walks on whatever surface it is on; MoveTo just needs some y.
        snap = self.world.act("MoveTo", {"position": [x, BODY_CENTRE_Y, z]})
        dist = hdist(snap.me, (x, 0, z))
        deadline = time.time() + dist / self.walk_speed * 2.5 + 3
        best, last_progress = dist, time.time()
        while dist > stop_within:
            time.sleep(0.12)
            snap = self._observe()
            if snap.me[1] < 0.8:
                self.world.act("Stop")
                raise Interrupted("fell off the edge into the sea")
            dist = hdist(snap.me, (x, 0, z))
            if dist < best - 0.05:
                best, last_progress = dist, time.time()
            if time.time() - last_progress > 1.2 or time.time() > deadline:
                self.world.act("Stop")
                if retry and self._unstick(snap):
                    return self._move_once(x, z, stop_within, retry=False)
                raise Interrupted(f"stuck {dist:.1f} units short of ({x:.1f}, {z:.1f})")
        return self.world.act("Stop")

    def _unstick(self, snap):
        """Reflex: when snagged, step straight away from the nearest wall, then let the caller retry."""
        walls = self._walls(snap)
        if not walls:
            return False
        me = snap.me

        def gap(w):
            return math.hypot(max(abs(me[0] - w.pos[0]) - w.size[0] / 2, 0), max(abs(me[2] - w.pos[2]) - w.size[2] / 2, 0))
        wall = min(walls, key=gap)
        if gap(wall) > 2.5:
            return False
        dx = me[0] - min(max(me[0], wall.pos[0] - wall.size[0] / 2), wall.pos[0] + wall.size[0] / 2)
        dz = me[2] - min(max(me[2], wall.pos[2] - wall.size[2] / 2), wall.pos[2] + wall.size[2] / 2)
        if math.hypot(dx, dz) < 0.05:  # pressed into the wall: out through its nearest face
            ox, oz = me[0] - wall.pos[0], me[2] - wall.pos[2]
            hx, hz = wall.size[0] / 2, wall.size[2] / 2
            _, (dx, dz) = min(((hx - ox, (1, 0)), (hx + ox, (-1, 0)), (hz - oz, (0, 1)), (hz + oz, (0, -1))))
        norm = math.hypot(dx, dz) or 1.0
        ex, ez = me[0] + dx / norm * 2.5, me[2] + dz / norm * 2.5
        self.log(kind="reflex", text=f"snagged by {wall.name}; stepping away to ({ex:.1f}, {ez:.1f})")
        self.world.act("MoveTo", {"position": [ex, BODY_CENTRE_Y, ez]})
        time.sleep(0.8)
        self.world.act("Stop")
        return True

    def _stand_point(self, snap, target, reach, min_radius, ignore=(), avoid=None):
        """A clear spot on our own level, within reach of `target` (x, y, z), and clear of `avoid` (the long thing
        we reach for: we stand beside it, not on it).

        Things on a mesa top near its edge can be reached from the ground below.
        """
        tx, ty, tz = target
        level = self._level(snap)
        blocked = self._blocked_fn(snap, ignore)
        me = snap.me
        best = None
        for radius in (min_radius + 0.4, min_radius + 1.0, min_radius + 1.8, min_radius + 2.6):
            for k in range(16):
                a = 2 * math.pi * k / 16
                sx, sz = tx + radius * math.cos(a), tz + radius * math.sin(a)
                if blocked(sx, sz):  # off our level, hugging a wall, or crowded by loose objects
                    continue
                if avoid is not None and avoid.footprint_contains(sx, sz, margin=1.3):
                    continue
                body = (sx, level + BODY_CENTRE_Y, sz)
                if math.dist(body, target) > reach - 0.4:
                    continue
                score = math.hypot(sx - me[0], sz - me[2])
                if best is None or score < best[0]:
                    best = (score, (sx, sz))
            if best:
                return best[1]
        return None

    def _settle(self, seconds=0.9):
        time.sleep(seconds)
        return self._observe()

    def _resting_on(self, snap, obj):
        """What `obj` is lying on, in words: other objects or mesas (a beam can lie across two), or the ground."""
        bottom = obj.pos[1] - obj.size[1] / 2

        def under(other):  # its top meets our bottom somewhere in our footprint, not just below our centre
            return (other.name != obj.name and abs(other.top - bottom) < 0.2
                    and abs(obj.pos[0] - other.pos[0]) < (obj.size[0] + other.size[0]) / 2 - 0.1
                    and abs(obj.pos[2] - other.pos[2]) < (obj.size[2] + other.size[2]) / 2 - 0.1)
        props = [e.name for e in snap.movables() + [t for t in snap.terrain() if t.role != "Ground"] if under(e)]
        if len(props) == 1:
            return f"on top of {props[0]}"
        if props:
            return f"across {', '.join(props[:-1])} and {props[-1]}"
        if any(t.role == "Ground" and t.footprint_contains(obj.pos[0], obj.pos[2]) and abs(t.top - bottom) < 0.2
               for t in snap.terrain()):
            return "on the ground"
        return "not resting on anything (still moving or tilted)"

    def _overlapping(self, snap, centre, size, ignore=()):
        """What a box at `centre` would intersect, described with the geometry that causes it."""
        hits = []
        bottom = centre[1] - size[1] / 2
        for e in snap.entities.values():
            if e.name in ignore or e.role == "Ocean" or e.role in SKY_MARKERS or e.name.startswith("Boundary"):
                continue
            # The world counts touching as overlap, so allow a hair of tolerance.
            if all(abs(centre[i] - e.pos[i]) < (size[i] + e.size[i]) / 2 + 0.01 for i in range(3)):
                label = "your own body" if e.name == "HumanoidRootPart" else ("the ground" if e.role == "Ground" else e.name)
                if label != "your own body" and 0 < e.top - bottom < 0.6:
                    label += f" (its top is at y={e.top:.3f}; the held object's bottom would be at y={bottom:.3f})"
                hits.append(label)
        return hits

    def _sink(self, snap, centre, size, name):
        """How far a box at `centre` would sink into the surfaces under it, if that is all that blocks it (else None)."""
        bottom = centre[1] - size[1] / 2
        depth = None
        for e in snap.entities.values():
            if e.name == name or e.role == "Ocean" or e.role in SKY_MARKERS or e.name.startswith("Boundary"):
                continue
            if all(abs(centre[i] - e.pos[i]) < (size[i] + e.size[i]) / 2 + 0.01 for i in range(3)):
                if e.name == "HumanoidRootPart" or not -0.01 <= e.top - bottom <= 0.06:
                    return None  # something really is in the way
                depth = max(depth or 0.0, e.top - bottom)
        return depth

    def _describe(self, snap, name):
        obj = snap.entities.get(name)
        if obj is None:
            return f"{name} is gone (fell into the sea)"
        return f"{name} came to rest at ({obj.pos[0]:.2f}, {obj.pos[1]:.2f}, {obj.pos[2]:.2f}), {self._resting_on(snap, obj)}"

    # ---- skills ------------------------------------------------------------------------
    def skill_walk_to(self, x, z):
        x, z = float(x), float(z)
        snap = self._observe()
        ground = snap.ground_top(x, z)
        if ground is None:
            return Result(False, "walk_to", f"({x:.1f}, {z:.1f}) is open sea, not ground")
        level = self._level(snap)
        rise, height = None, ground
        if ground > level + 0.5:
            covering = [t for t in self._walls(snap) if t.footprint_contains(x, z)]
            rise = max(covering, key=lambda t: t.top) if covering else None
        else:  # something built there, higher than a step up from here (a loose stone is just in the way)
            top, part = snap.surface(x, z)
            if part is not None and part.movable and top > level + 1.0:
                rise, height = part, top
        if rise is not None or ground > level + 0.5:
            mesa = rise.name if rise else "a mesa"
            where = (f"({x:.1f}, {z:.1f}) is inside the trunk of {mesa}" if rise and rise.role == "Tree"
                     else f"({x:.1f}, {z:.1f}) is on top of {mesa} (height {height:.1f})")
            # As a person would: walk as far as the foot of it, on the way back towards where we stand.
            blocked = self._blocked_fn(snap)
            steps = int(hdist(snap.me, (x, 0, z)) / 0.5)
            foot = next(((x + (snap.me[0] - x) * i / steps, z + (snap.me[2] - z) * i / steps)
                         for i in range(1, steps) if not blocked(x + (snap.me[0] - x) * i / steps,
                                                                 z + (snap.me[2] - z) * i / steps)), None) if steps > 1 else None
            if foot is None and rise and abs(snap.me[0] - rise.pos[0]) < rise.size[0] / 2 + 3 \
                    and abs(snap.me[2] - rise.pos[2]) < rise.size[2] / 2 + 3:
                foot = (snap.me[0], snap.me[2])  # every spot nearer the wall is too close for the router: we are at its foot
            if foot is None:
                return Result(False, "walk_to", f"{where}; you cannot climb it and found no clear spot at its foot")
            if hdist(snap.me, (foot[0], 0, foot[1])) < 0.6:  # already as close as legs can get: that is the walk done
                return Result(True, "walk_to", f"{where}, which you cannot climb; you are already at its foot")
            snap = self._move(*foot)
            return Result(True, "walk_to", f"{where}, which you cannot climb; walked to its foot at "
                                           f"({snap.me[0]:.1f}, {snap.me[2]:.1f})")
        floor = snap.surface(x, z, below=level + STEP)[0]
        if level > 0.3 and floor is not None and floor < level - 0.3:
            return self._hop_down(snap, x, z, level, floor)
        # The body never steps onto or against things: stop short of anything loose at the destination.
        note = ""
        near = [e for e in self._in_the_way(snap) if math.hypot(e.pos[0] - x, e.pos[2] - z) < 1.3 + max(e.size[0], e.size[2]) / 2]
        if near:
            e = min(near, key=lambda o: math.hypot(o.pos[0] - x, o.pos[2] - z))
            gap = 1.3 + max(e.size[0], e.size[2]) / 2 + 0.2
            dx, dz = snap.me[0] - e.pos[0], snap.me[2] - e.pos[2]
            norm = math.hypot(dx, dz) or 1.0
            x, z = e.pos[0] + dx / norm * gap, e.pos[2] + dz / norm * gap
            note = f"; stopped {gap:.1f} away from {e.name} instead of walking into it"
        snap = self._move(x, z)
        return Result(True, "walk_to", f"walked to ({snap.me[0]:.1f}, {snap.me[2]:.1f}){note}")

    def _approach(self, snap, target, reach, min_radius, ignore=(), avoid=None):
        """A spot on our floor within reach of `target`. From up on something, with nothing in reach up here and the
        target below, hop down towards it first, as a person would. Returns (spot or None, latest snapshot)."""
        stand = self._stand_point(snap, target, reach, min_radius, ignore, avoid)
        level = self._level(snap)
        if stand is None and level > 0.3 and target[1] < level + 1.0:
            floor = snap.surface(target[0], target[2], below=level - 0.3)[0]
            if floor is not None and level - floor <= MAX_DROP:
                if self._hop_down(snap, target[0], target[2], level, floor, walk_on=False).ok:
                    snap = self._observe()
                    stand = self._stand_point(snap, target, reach, min_radius, ignore, avoid)
        return stand, snap

    def _here(self, snap):
        """Where the body stands, in words, when it is not simply on the ground."""
        level = self._level(snap)
        if level <= 0.3:
            return "here"
        on = snap.surface(snap.me[0], snap.me[2], below=level + STEP)[1]
        return f"up here on {on.name if on else 'something'} (height {level:.1f})"

    def _hop_down(self, snap, x, z, level, floor, walk_on=True):
        """From up on something, a drop a person would hop down: walk to the edge on the way, step off, land, walk on."""
        on = snap.surface(snap.me[0], snap.me[2], below=level + STEP)[1]
        on = on.name if on else "something"
        drop = level - floor
        if drop > MAX_DROP:
            return Result(False, "walk_to", f"you are up on {on} at height {level:.1f}, and ({x:.1f}, {z:.1f}) is "
                                            f"{drop:.1f} lower: too far to hop down; you would have to climb down")
        # Hop off from the clear spot on this floor nearest to where we are going (not into a ladder or a wall).
        blocked = self._blocked_fn(snap)
        mx, mz = snap.me[0], snap.me[2]
        spots = [(mx + dx * 0.5, mz + dz * 0.5) for dx in range(-24, 25) for dz in range(-24, 25)]
        spots = [p for p in spots if not blocked(*p)]
        if not spots:
            return Result(False, "walk_to", f"you are up on {on} at height {level:.1f} with no clear edge to hop down from")
        edge = min(spots, key=lambda p: math.hypot(p[0] - x, p[1] - z))
        if hdist(snap.me, (edge[0], 0, edge[1])) > 0.6:
            snap = self._move(*edge)
        ox, oz = x - snap.me[0], z - snap.me[2]
        norm = math.hypot(ox, oz) or 1.0
        beyond = (snap.me[0] + ox / norm * 2.5, snap.me[2] + oz / norm * 2.5)
        self.world.act("MoveTo", {"position": [beyond[0], BODY_CENTRE_Y, beyond[1]]})  # step off the edge
        landed = False
        deadline = time.time() + 5
        while time.time() < deadline and not landed:
            time.sleep(0.15)
            landed = self._observe().me[1] < level + BODY_CENTRE_Y - 0.5 * drop
        self.world.act("Stop")
        time.sleep(0.5)
        if not landed:
            return Result(False, "walk_to", f"you are up on {on} at height {level:.1f} and could not step off its edge")
        if not walk_on:
            return Result(True, "walk_to", f"hopped down {drop:.1f} from {on}")
        snap = self._move(x, z)  # walk on from where we landed
        return Result(True, "walk_to", f"hopped down {drop:.1f} from {on} and walked to ({snap.me[0]:.1f}, {snap.me[2]:.1f})")

    def skill_pick_up(self, object):
        snap = self._observe()
        obj = snap.entities.get(object)
        if obj is None or not obj.movable:
            return Result(False, "pick_up", f"there is no movable object called {object}")
        if obj.attrs.get("Fastened"):
            return Result(False, "pick_up", f"{object} is fastened to what it touches; a hammer strike knocks it loose")
        held = snap.held()
        if held and held.name == object:
            return Result(True, "pick_up", f"already holding {object}", {"holding": object})
        note = ""
        if held:
            freed = self._set_down_nearby(snap, held, obj.pos)
            if freed is None:
                return Result(False, "pick_up", f"hands are full: holding {held.name}, and there is no clear spot nearby to set it down")
            note = f" (first {freed.summary.replace('put', 'set', 1)}, to free your hands)"
            snap = self._observe()
            obj = snap.entities.get(object)
            if obj is None:
                return Result(False, "pick_up", f"{object} vanished{note}")
        # Beside it: its narrow side sets how close we may stand; a long beam or ladder we stand beside, at its middle.
        stand, snap = self._approach(snap, obj.pos, PICKUP_RANGE, 1.6 + min(obj.size[0], obj.size[2]) / 2,
                                     ignore={object}, avoid=obj)
        if stand is None:
            return Result(False, "pick_up", f"no clear spot to reach {object} from {self._here(snap)} "
                                            f"(it may be up on something){note}")
        self._move(*stand, ignore={object})
        for attempt in range(2):
            snap = self._observe()
            obj = snap.entities.get(object)
            if obj is None:
                return Result(False, "pick_up", f"{object} vanished{note}")
            snap = self.world.act("Pickup", {"position": list(obj.pos)})
            outcome = snap.last_result
            if outcome == "PickupSuccess":
                # The block rises into the hands before the body moves on; only then does it read as held.
                snap = self._settle(LIFT_SECONDS + 0.2)
            held = snap.held()
            if outcome == "PickupSuccess" and held and held.name == object:
                return Result(True, "pick_up", f"picked up {object}{note}", {"holding": object})
            if outcome == "PickupSuccess" and held:
                return Result(True, "pick_up", f"picked up {held.name} instead of {object}{note}", {"holding": held.name})
            closer = self._stand_point(snap, obj.pos, PICKUP_RANGE, 1.2, ignore={object})
            if closer:
                self._move(*closer, ignore={object})
        return Result(False, "pick_up", f"pickup of {object} failed: {snap.last_result}{note}")

    def _set_down_nearby(self, snap, held, away_from):
        """Reflex, as a person does: set what is in your hands on clear ground beside you before taking something else."""
        level = self._level(snap)
        kept = [e for name, e in snap.entities.items() if name in set(self.protected())]
        spots = [(snap.me[0] + r * math.cos(k * math.pi / 4), snap.me[2] + r * math.sin(k * math.pi / 4))
                 for r in (CUBE + 1.0, CUBE + 2.0, CUBE + 3.5) for k in range(8)]
        # Out of the way: not on what we came for, not against anything we decided to keep.
        spots = [(x, z) for x, z in spots
                 if snap.ground_top(x, z) is not None and abs(snap.ground_top(x, z) - level) < 0.3
                 and hdist((x, 0, z), away_from) > CUBE + 0.5 and all(hdist((x, 0, z), e.pos) > CUBE for e in kept)]
        for x, z in sorted(spots, key=lambda p: -hdist((p[0], 0, p[1]), away_from))[:6]:
            result = self.skill_put_down(x, z)
            if result.ok:
                self.log(kind="reflex", text=f"hands full: {result.summary} to pick up something else")
                return result
        return None

    def skill_put_down(self, x, z, turn=0, upright=False):
        x, z, turn, upright = float(x), float(z), _quarter(turn), _flag(upright)
        snap = self._observe()
        held = snap.held()
        if not held:
            return Result(False, "put_down", "hands are empty")
        self.busy.add(held.name)
        ground = snap.ground_top(x, z)
        if ground is None:
            return Result(False, "put_down", f"({x:.1f}, {z:.1f}) is open sea; it would sink and be lost")
        ladder = held.name.startswith("Ladder_")  # the world stands a ladder up by itself
        if held.name.startswith(SNAPPED_KINDS):  # it will settle into the grid: plan for the cell it lands in
            x, z = grid(x), grid(z)
        size = turned_size(held.local_size, turn, upright and not ladder)
        half = max(size[0], size[2]) / 2
        level = self._level(snap)
        floor = snap.surface(x, z, below=level + STEP)[0]  # the ground, or a floor we built at our own level
        floor = ground if floor is None else floor
        covering = max((t for t in snap.terrain() if t.footprint_contains(x, z)), key=lambda t: t.top)
        if covering.role == "Tree":
            return Result(False, "put_down", f"({x:.1f}, {z:.1f}) is inside the trunk of {covering.name}")
        if not ladder:  # a ladder is meant to stand against something
            for t in snap.terrain():  # a mesa wall or a trunk right beside the spot leaves no room for the object
                if t.top > floor + 0.3 and abs(x - t.pos[0]) < t.size[0] / 2 + half and abs(z - t.pos[2]) < t.size[2] / 2 + half:
                    return Result(False, "put_down", f"({x:.1f}, {z:.1f}) is too close to {t.name} to set anything down")
            for e in self._obstacles(snap, ignore={held.name}):
                if (math.hypot(e.pos[0] - x, e.pos[2] - z) < half + max(e.size[0], e.size[2]) / 2 + 0.05
                        and e.top > floor + 0.05 and e.pos[1] - e.size[1] / 2 < floor + 3):
                    return Result(False, "put_down", f"({x:.1f}, {z:.1f}) is occupied by {e.name}")
        target = (x, floor + size[1] / 2 + (0.02 if ladder else 0.12), z)
        stand = self._stand_point(snap, target, PLACE_RANGE, 1.0 + half + 0.5, ignore={held.name})
        if stand is None:
            return Result(False, "put_down", f"no clear spot to reach ({x:.1f}, {z:.1f}) from")
        self._move(*stand, ignore={held.name})
        snap = self.world.act("Place", {"position": list(target), "rotation": _rotation(turn, upright)})
        if snap.last_result != "PlaceSuccess":
            why = snap.last_result
            if why == "PlaceFailed:Occupied":
                why = f"that space is taken by {', '.join(self._overlapping(snap, target, size, ignore={held.name})) or 'something'}"
            return Result(False, "put_down", f"place failed: {why}")
        snap = self._settle(PLACE_SECONDS + 0.4)
        landed = snap.entities.get(held.name)
        where = f"({landed.pos[0]:.1f}, {landed.pos[1]:.2f}, {landed.pos[2]:.1f})" if landed else "nowhere (lost)"
        how = " standing upright" if ladder else _orientation(turn, upright)
        return Result(True, "put_down", f"put {held.name} down{how} at {where}", {"object": held.name})

    def skill_stack_on(self, object):
        snap = self._observe()
        held = snap.held()
        if not held or not held.is_cube:
            return Result(False, "stack_on", "need to be holding a cube")
        self.busy.add(held.name)
        column = snap.column(object)
        if not column or column[0].name not in snap.entities:
            return Result(False, "stack_on", f"there is no cube called {object}")
        top = column[-1]
        before = len(column)
        target = (top.pos[0], top.pos[1] + CUBE + 0.06, top.pos[2])
        stand = self._stand_point(snap, target, PLACE_RANGE, 2.0, ignore={held.name} | {c.name for c in column})
        if stand is None:
            return Result(False, "stack_on", f"stack is too tall or crowded to reach (height {before})")
        self._move(*stand, ignore={held.name})
        snap = self.world.act("Place", {"position": list(target), "rotation": {"yaw": 0, "pitch": 0, "roll": 0}})
        if snap.last_result != "PlaceSuccess":
            return Result(False, "stack_on", f"place failed: {snap.last_result}")
        snap = self._settle(PLACE_SECONDS + 0.7)
        column = snap.column(column[0].name)
        names = [c.name for c in column]
        if held.name in names and names[-1] == held.name:
            return Result(True, "stack_on", f"stack is now {len(names)} high", {"height": len(names), "base": names[0]})
        landed = snap.entities.get(held.name)
        where = f"({landed.pos[0]:.1f}, {landed.pos[2]:.1f})" if landed else "out of the world"
        toppled = len(names) < before
        return Result(False, "stack_on",
                      f"{held.name} fell off and landed at {where}" + (f"; the stack toppled to {len(names)}" if toppled else ""),
                      {"height": len(names), "fell": held.name, "toppled": toppled})

    def skill_build_tower(self, x, z, height):
        x, z, height = float(x), float(z), max(2, min(12, int(height)))
        snap = self._observe()
        if snap.ground_top(x, z) is None:
            return Result(False, "build_tower", f"({x:.1f}, {z:.1f}) is open sea")
        base = next((c for c in snap.cubes() if hdist(c.pos, (x, 0, z)) < 0.6 * CUBE
                     and abs(c.pos[1] - (snap.ground_top(x, z) + CUBE / 2)) < 0.2), None)
        steps = []
        if base is None:
            free = self._free_cubes(snap)
            if not free:
                return Result(False, "build_tower", "no free cubes left to build with")
            first = min(free, key=lambda c: hdist(c.pos, snap.me))
            for skill, args in (("pick_up", {"object": first.name}), ("put_down", {"x": x, "z": z})):
                r = self.run(skill, args)
                steps.append(r.summary)
                if not r.ok:
                    return Result(False, "build_tower", f"could not lay the base: {r.summary}", {"height": 0})
            base_name = first.name
        else:
            base_name = base.name
        while True:
            snap = self._observe()
            column = snap.column(base_name)
            if len(column) >= height:
                return Result(True, "build_tower", f"tower at ({x:.1f}, {z:.1f}) stands {len(column)} high",
                              {"height": len(column), "cubes": [c.name for c in column]})
            names = [c.name for c in column]
            free = self._free_cubes(snap, exclude=set(names))
            if not free:
                return Result(False, "build_tower", f"ran out of free cubes at height {len(column)}",
                              {"height": len(column), "cubes": names})
            cube = min(free, key=lambda c: hdist(c.pos, snap.me))
            r = self.run("pick_up", {"object": cube.name})
            if not r.ok:
                return Result(False, "build_tower", f"stopped at height {len(column)}: {r.summary}",
                              {"height": len(column), "cubes": names})
            r = self.run("stack_on", {"object": base_name})
            if not r.ok:
                after = [c.name for c in self._observe().column(base_name)]
                return Result(False, "build_tower", f"stopped at height {len(after)}: {r.summary}",
                              {**r.facts, "height": len(after), "cubes": after})

    def skill_place_at(self, x, y, z, turn=0, upright=False):
        target = (float(x), float(y), float(z))
        turn, upright = _quarter(turn), _flag(upright)
        snap = self._observe()
        held = snap.held()
        if not held:
            return Result(False, "place_at", "hands are empty")
        if held.name.startswith("Ladder_"):  # a ladder stands on whatever is under it, upright
            result = self.skill_put_down(target[0], target[2], turn)
            return Result(result.ok, "place_at", result.summary, result.facts)
        self.busy.add(held.name)
        if held.name.startswith(SNAPPED_KINDS):  # it will settle into the grid: plan for the cell it lands in
            target = (grid(target[0]), target[1], grid(target[2]))
        size = turned_size(held.local_size, turn, upright)
        half = max(size[0], size[2]) / 2
        body = (snap.me[0], snap.me[1], snap.me[2])
        if math.dist(body, target) > PLACE_RANGE - 0.3 or hdist(body, target) < 1.0 + half + 0.3:
            stand = self._stand_point(snap, target, PLACE_RANGE, 1.0 + half + 0.5, ignore={held.name})
            if stand is None:
                return Result(False, "place_at", f"cannot get within reach of ({target[0]:.1f}, {target[1]:.1f}, {target[2]:.1f})")
            snap = self._move(*stand, ignore={held.name})
        snap = self.world.act("Place", {"position": list(target), "rotation": _rotation(turn, upright)})
        sink = self._sink(snap, target, size, held.name) if snap.last_result == "PlaceFailed:Occupied" else None
        if sink is not None:
            # Aimed a hair into the surface below (the world counts touching as overlap): rest it on that surface.
            target = (target[0], target[1] + sink + 0.03, target[2])
            snap = self.world.act("Place", {"position": list(target), "rotation": _rotation(turn, upright)})
        if snap.last_result != "PlaceSuccess":
            why = snap.last_result
            if why == "PlaceFailed:Occupied":
                blocking = self._overlapping(snap, target, size, ignore={held.name})
                why = f"that space is taken by {', '.join(blocking) or 'something'}"
            return Result(False, "place_at", f"place rejected: {why}", {"object": held.name})
        snap = self._settle(PLACE_SECONDS + 0.7)
        return Result(True, "place_at", self._describe(snap, held.name) + _orientation(turn, upright), {"object": held.name})

    def skill_throw(self, x, y, z, speed=6):
        snap = self._observe()
        held = snap.held()
        if not held:
            return Result(False, "throw", "hands are empty")
        self.busy.add(held.name)
        snap = self.world.act("Throw", {"direction": [float(x), float(y), float(z)], "speed": float(speed)})
        if snap.last_result != "ThrowSuccess":
            return Result(False, "throw", f"throw failed: {snap.last_result}")
        last, still = None, 0
        for _ in range(40):  # follow it until it stops moving (or leaves the world)
            time.sleep(0.15)
            snap = self._observe()
            obj = snap.entities.get(held.name)
            if obj is None or obj.pos[1] < -5:
                return Result(True, "throw", f"{held.name} flew into the sea and is gone", {"object": held.name, "lost": True})
            still = still + 1 if last and math.dist(last, obj.pos) < 0.02 else 0
            last = obj.pos
            if still >= 3:
                break
        return Result(True, "throw", self._describe(snap, held.name), {"object": held.name})

    def skill_jump(self):
        self.world.act("Jump")
        peak = 0.0
        for _ in range(8):
            time.sleep(0.1)
            snap = self._observe()
            peak = max(peak, snap.me[1])
        return Result(True, "jump", f"jumped; highest point {peak:.1f}, now at ({snap.me[0]:.1f}, {snap.me[1]:.1f}, {snap.me[2]:.1f})")

    def skill_strike(self, object):
        snap = self._observe()
        target = snap.entities.get(object)
        if target is None:
            return Result(False, "strike", f"there is nothing called {object}")
        held = snap.held()
        if not held or not held.name.startswith(TOOL_KINDS):
            return Result(False, "strike", "your hands hold no tool to strike with" + (f" ({held.name} is not one)" if held else ""))
        self.busy.add(held.name)
        # Aim at the nearest point of its surface, at body height, and stand within reach of it.
        level = self._level(snap)
        aim = tuple(min(max(c, p - s / 2), p + s / 2) for c, p, s in
                    zip((snap.me[0], level + BODY_CENTRE_Y, snap.me[2]), target.pos, target.size))
        if math.dist((snap.me[0], level + BODY_CENTRE_Y, snap.me[2]), aim) > STRIKE_RANGE - 0.5:
            stand, snap = self._approach(snap, aim, STRIKE_RANGE, 2.2, ignore={held.name})
            if stand is None:
                return Result(False, "strike", f"no clear spot to stand within reach of {object} from {self._here(snap)}")
            self._move(*stand, ignore={held.name})
        snap = self.world.act("Strike", {"name": object})
        outcome = snap.last_result or ""
        snap = self._settle(STRIKE_SECONDS)  # the swing
        kind, _, detail = outcome.partition(":")
        where = lambda name: (lambda p: f"({p.pos[0]:.1f}, {p.pos[2]:.1f})" if p else "somewhere nearby")(snap.entities.get(name))
        if kind == "StrikeHit":
            done, needed = (int(n) for n in detail.split("/"))
            return Result(True, "strike", f"struck {object} with {held.name} ({done} of {needed} strikes so far)",
                          {"strikes": done})
        if kind == "StrikeBroke":
            return Result(True, "strike", f"struck {object}; a stone broke off: {detail} lies at {where(detail)}",
                          {"made": detail})
        if kind == "StrikeFelled":
            logs = detail.split(",")
            return Result(True, "strike", f"{object} fell; " + " and ".join(f"{n} lies at {where(n)}" for n in logs)
                          + "; a stump is left", {"made": logs})
        if kind == "StrikeLoosened":
            return Result(True, "strike", f"struck {object}; it is knocked loose and no longer fastened", {"loosened": detail})
        if kind == "StrikeNoEffect":
            return Result(False, "strike", f"struck {object} with {held.name}; nothing came of it")
        why = {"StrikeFailed:NoTool": "your hands hold no tool", "StrikeFailed:OutOfRange": f"{object} is out of reach",
               "StrikeFailed:TooSoon": "the last swing was too recent",
               "StrikeFailed:NoTarget": f"there is nothing called {object}"}.get(outcome, outcome or "nothing happened")
        return Result(False, "strike", f"strike failed: {why}")

    def skill_fasten(self, object):
        snap = self._observe()
        piece = snap.entities.get(object)
        if piece is None or not piece.movable:
            return Result(False, "fasten", f"there is no piece called {object}")
        if piece is snap.held():
            return Result(False, "fasten", f"{object} is in your hands; set it down first")
        if piece.attrs.get("Fastened"):
            return Result(True, "fasten", f"{object} is already fastened")
        level = self._level(snap)
        body = (snap.me[0], level + BODY_CENTRE_Y, snap.me[2])
        if math.dist(body, piece.pos) > PLACE_RANGE - 0.5:
            stand, snap = self._approach(snap, piece.pos, PLACE_RANGE, 1.6 + min(piece.size[0], piece.size[2]) / 2,
                                         ignore={object}, avoid=piece)
            if stand is None:
                return Result(False, "fasten", f"no clear spot to reach {object} from {self._here(snap)}")
            self._move(*stand, ignore={object})
        snap = self.world.act("Fasten", {"name": object})
        outcome = snap.last_result or ""
        self._settle(FASTEN_SECONDS)
        if outcome.startswith("FastenSuccess:"):
            how = outcome.split(":")[1]
            if how == "fixed":
                return Result(True, "fasten", f"fastened {object} in place on what it rests on", {"object": object})
            return Result(True, "fasten", f"fastened {object} to the {how} loose piece{'s' if how != '1' else ''} it touches",
                          {"object": object, "joined": int(how)})
        why = {"FastenFailed:NothingTouching": f"{object} touches nothing to fasten it to",
               "FastenFailed:NotSetDown": f"{object} is still moving into place or in someone's hands",
               "FastenFailed:OutOfRange": f"{object} is out of reach", "FastenFailed:TooSoon": "you are still fastening",
               "FastenFailed:NotAPiece": f"{object} cannot be fastened"}.get(outcome, outcome or "nothing happened")
        return Result(False, "fasten", f"fasten failed: {why}")

    def skill_climb(self, object):
        snap = self._observe()
        ladder = snap.entities.get(object)
        if ladder is None or not object.startswith("Ladder_"):
            return Result(False, "climb", f"there is no ladder called {object}")
        if ladder is snap.held():
            return Result(False, "climb", f"{object} is in your hands; set it down where it should stand first")
        if hdist(snap.me, ladder.pos) > 2.4:
            # Come up to it on its open side, in front or behind, whichever is clear and nearer (a ladder stands
            # against something, and the body cannot get close to a wall).
            fx, fz = ladder.facing
            blocked = self._blocked_fn(snap, ignore={object})
            sides = [(ladder.pos[0] + fx * s * 1.9, ladder.pos[2] + fz * s * 1.9) for s in (1, -1)]
            sides = [p for p in sides if not blocked(*p)] or sides
            spot = min(sides, key=lambda p: hdist(snap.me, (p[0], 0, p[1])))
            try:
                self._move(*spot, stop_within=0.4, ignore={object})
            except Interrupted:  # bumping the ladder itself is close enough to climb it
                if hdist(self._observe().me, ladder.pos) > 2.6:
                    raise
        start = self._level(self._observe())
        snap = self.world.act("Climb", {"name": object})
        outcome = snap.last_result or ""
        if outcome.startswith("ClimbStarted:"):
            _, way, seconds = outcome.split(":")
            snap = self._settle(float(seconds) + 0.4)
            level = self._level(snap)
            on = snap.surface(snap.me[0], snap.me[2], below=level + STEP)[1]
            return Result(True, "climb", f"climbed {way} {object} from height {start:.1f} to {level:.1f}; you stand on "
                                         f"{on.name if on else 'the ground'} at ({snap.me[0]:.1f}, {snap.me[2]:.1f})",
                          {"level": round(level, 2)})
        why = {"ClimbFailed:NotSetUp": f"{object} is not standing up; put it down where it should stand",
               "ClimbFailed:TooFar": f"you are not close enough to {object}",
               "ClimbFailed:NotAtAnEnd": f"you are neither at the foot nor at the top of {object}",
               "ClimbFailed:NothingAtTop": f"the top of {object} reaches nothing to step onto",
               "ClimbFailed:NothingAtBottom": f"there is nothing to step onto at the foot of {object}",
               "ClimbFailed:NoLadder": f"{object} is not a ladder"}.get(outcome, outcome or "nothing happened")
        return Result(False, "climb", f"climb failed: {why}")

    def skill_say(self, text):
        self.world.say(str(text))
        return Result(True, "say", "said it")

    def skill_wait(self, seconds):
        end = time.time() + max(1.0, min(30.0, float(seconds)))
        while time.time() < end:
            time.sleep(1.0)
            self._observe()
            self.glance()
        return Result(True, "wait", f"waited {seconds}s")
