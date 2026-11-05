"""L1 skills: deterministic motor programs. The mind picks skills; it never steers the body.

Every skill checks reach and clearance with the world's real constants, routes around loose
objects (walking through cubes scatters them), and verifies the outcome from a fresh observation.
"""
import heapq
import math
import time
from dataclasses import dataclass, field

from .world import (BODY_CENTRE_Y, BUILDING_KINDS, CUBE, FASTEN_SECONDS, LADDER_HEIGHT, LIFT_SECONDS, PICKUP_RANGE,
                    PLACE_RANGE, PLACE_SECONDS, SKY_MARKERS, SNAPPED_KINDS, SPEAR_THRUST, STEP, STRIKE_RANGE, STRIKE_SECONDS,
                    TOOL_KINDS, TURN_RATE, WALK_SPEED, BoxIndex, WorldError, grid, hdist, turned_size)

# What the body can do. These know the body's own limits (reach, not walking through things)
# but no strategy: how to stack, aim or build has to be learned by the mind.
PRIMITIVES = {
    "walk_to": ({"x": "number", "z": "number"},
                "Walk to a point on the level you stand on, going around obstacles. A point on something one block "
                "higher you step up onto; higher ground takes you to the foot of it."),
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
    "strike": ({"object": "what to strike, such as Quarry, Palm_2, Log_4 or Fish_3"},
               "Walk within reach of it and strike it once with the tool in your hands: an axe fells a palm or carves "
               "a log, a hammer breaks stone off the quarry, a spear takes a fish. The world says what happened."),
    "rub": ({"object": "what to rub against, such as Log_3"},
            "Walk within reach and rub what you hold hard against it, over and over, for up to half a minute or until "
            "something comes of it."),
    "fasten": ({"object": "a piece you have set down"},
               "Walk within reach and fasten that piece where it is, like mortar, so it stays even if what it rests on "
               "is taken away. Takes a few seconds; fastened pieces cannot be picked up."),
    "climb": ({"object": "a ladder that stands upright, such as Ladder_1"},
              "Walk to the ladder and climb it: up to whatever its top reaches, or back down when you are at the top."),
    "shake": ({"object": "a palm, such as Palm_3"}, "Walk to the palm and shake it. A ripe coconut may fall."),
    "carve": ({"object": "a log, such as Log_2"},
              "With the axe in your hands, carve that log into a spear. Takes a few strokes."),
    "eat": ({}, "Eat what you hold, if it is food."),
    "cook": ({}, "Cook the fish you hold over a fire beside you."),
    "draw": ({"x": "number", "z": "number"},
             "Drag your foot through the sand from where you stand to (x, z), at most 20 away, leaving a line in it. "
             "Only open sand takes a line; lines can make shapes or letters."),
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
BODY_HEIGHT = 5.0  # the engine's capsule: exactly two blocks
BODY_RADIUS = 1.0  # the engine's capsule is two units wide
STAND_MARGIN = 0.2  # kept between the body and a loose piece beside it, beyond its radius
WALL_CLEARANCE = 1.6  # kept from rock: the character controller snags when it slides along a wall it touches
STEP_UP = 2.6  # main.lua STEP_UP_MAX: the body steps up onto anything one block high (ADR-010)
RUB_TRIES = 30  # rubs one rub step keeps at, about half a minute (fire catches from the 12th, about the 20th on average)
RUB_HOT = 12  # main.lua RUB_HOT: from this many rubs in a row the wood is hot and smoking
TINDER_RANGE = 3.0  # main.lua TINDER_RANGE: tinder this close to the log catches from it
PEN_CELLS = 1600  # half-unit cells: floor the body can reach smaller than this (20 x 20 units) is a pen
LIFTABLE = SNAPPED_KINDS + ("Brick_", "Ladder_")  # what the body lifts aside to get out of a pen
GLANCE_IN_VIEW = 45  # degrees: something this close to straight ahead is already in view, no turn needed
GLANCE_HOLD = 0.4  # seconds the body keeps looking before it goes on
BRACE_LONGEST = 90  # seconds: a quake's rumble, shaking and fade take 33; the world lets go when it is over
LOOK_BEFORE_BRACE = 0.15  # the rumble reaches this strength 2 s in (main.lua); until then the body looks around


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


def _weather_here(snap):
    """How the weather finds the body where it now stands, when it rains or the body is cold (ADR-010). Walking and
    waiting say it, so a step meant to keep dry or warm shows whether it did: run n8's own shelter_wait reported
    success 119 times, and not once was the body out of the rain."""
    if snap.rain < 0.3 and not snap.cold and not snap.in_house:
        return ""
    if snap.in_house:  # ADR-019: only a house keeps the cold off
        return "; here you are inside a house, out of the rain and the cold"
    if snap.sheltered in ("roof", "enclosed"):
        return ("; here you are under a roof" + (" with walls round you" if snap.sheltered == "enclosed" else "")
                + ", out of the rain" + (", but still cold: a roof only halves it" if snap.cold else ""))
    return ("; here you are out in the rain with nothing over your head" if snap.rain >= 0.3
            else "; here you have nothing over your head") + (", and cold" if snap.cold else "")


class _Box:
    """Where a piece is about to lie: enough of an Entity for `_stand_point(avoid=...)`."""

    def __init__(self, centre, size):
        self.pos, self.size = centre, size

    def footprint_contains(self, x, z, margin=0.0):
        return abs(x - self.pos[0]) <= self.size[0] / 2 + margin and abs(z - self.pos[2]) <= self.size[2] / 2 + margin


@dataclass
class Result:
    ok: bool
    skill: str
    summary: str
    facts: dict = field(default_factory=dict)
    seconds: float = 0.0


class Interrupted(Exception):
    pass


class Stuck(Interrupted):
    """The body's own trouble (snagged, hemmed in, slipped into the sea): the step fails like any other. Only what
    attention notices interrupts the plan; being stuck threw away the plan being thought up, and the body then
    waited for a fresh one: 78 of the 85 minutes it waited in run n7."""


class Skills:
    def __init__(self, world, protected=lambda: set(), on_step=None, log=None, gifted=False, library=None,
                 walk_speed=WALK_SPEED, kept_in=lambda piece: None, reserved=lambda: set()):
        self.world = world
        self.walk_speed = walk_speed  # must match the world's humanoid WalkSpeed (used for walk timeouts)
        self.protected = protected  # names of cubes the mind wants left alone
        self.kept_in = kept_in  # the name of the build a piece is built into (memory.built_into), or None
        self.reserved = reserved  # grid cells (ix, iz) to keep clear: the house's room, doorway and way out
        self._kept_clear = False  # the last hands-full reflex passed over spots in those cells
        self.placed = []  # pieces set down since the mind last asked (take_placed), by any skill, learned ones too
        self.on_step = on_step  # attention hook: called with each snapshot, may raise Interrupted
        self.next_glance = lambda: None  # attention hook: an event worth a look, taken between steps
        self.log = log or (lambda **kw: None)
        self.offered = {**PRIMITIVES, **(GIFTED if gifted else {})}
        self.library = library  # skills the mind taught itself (learned.SkillLibrary)
        self.busy = set()  # objects the current skill is handling; attention ignores their movement
        self._depth = 0
        self._lifting = False  # in the middle of lifting a way out of a pen (no second one inside it)

    # ---- entry point -------------------------------------------------------------------
    def run(self, skill, args):
        if self._depth == 0:
            self.steady()
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
            except Stuck as why:
                return Result(False, skill, str(why))
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
        except Stuck as why:
            result = Result(False, skill, str(why))
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

    def steady(self):
        """Reflex: when the ground rumbles, crouch and hold on wherever the body stands, and stay braced until the
        ground is still (main.lua EARTHQUAKE). A braced body cannot be knocked down. The mind is not asked: it hears
        of the quake in its next plan."""
        try:
            snap = self.world.observe()
            if not snap.quake_phase or snap.bracing:
                return
            if snap.quake_phase == "rumble" and snap.quake < LOOK_BEFORE_BRACE:
                return  # startled, it looks around first (the world plays LookAround); the shaking is 8 s away
            started = time.time()
            braced = self.world.act("Brace").last_result == "Braced"
            self.log(kind="brace", ok=braced, phase=snap.quake_phase, tick=snap.tick,
                     **({"sky": "Earthquake", "sky_id": int(snap.quake_id)} if snap.quake_id else {}))
            if not braced:
                return
            while time.time() - started < BRACE_LONGEST:
                time.sleep(0.5)
                snap = self.world.observe()
                if self.on_step:
                    try:
                        self.on_step(snap)  # attention keeps watching: what falls is news for the next plan
                    except Interrupted:
                        pass
                if not snap.bracing:
                    break
            self.log(kind="reflex", text=f"held on through the earthquake for {time.time() - started:.0f}s")
        except WorldError as err:
            self.log(kind="error", message=f"brace: {err}")

    def take_placed(self):
        """The pieces the body set down (place_at, put_down) since the last call, at any depth: inside a learned
        skill too, where most building happens (run hut1: every block went down through stack_block or haul_to)."""
        placed, self.placed = self.placed, []
        return placed

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
                and p.name not in blocked | below_top and not p.attrs.get("Fastened") and not p.attrs.get("Burning")
                and snap.ground_top(p.pos[0], p.pos[2]) is not None]

    def _obstacles(self, snap, ignore=()):
        held = snap.held()
        return [e for e in snap.movables() if e.name not in ignore and e is not held]

    def _in_the_way(self, snap, ignore=(), level=None):
        """Loose things that stick up from the floor we stand on (what we stand on, or what lies below it, is not),
        and things overhead lower than the body is tall: a beam across two-block posts leaves no room under it."""
        level = self._level(snap) if level is None else level
        return [e for e in self._obstacles(snap, ignore)
                if e.top > level + STEP and e.pos[1] - e.size[1] / 2 < level + BODY_HEIGHT + 0.1]

    def _level(self, snap):
        """Height of the surface we are standing on: the ground, a mesa, or pieces we built and climbed onto."""
        feet = snap.me[1] - BODY_CENTRE_Y
        level = snap.surface(snap.me[0], snap.me[2], below=feet + STEP)[0]
        return 0.0 if level is None else level

    def _walls(self, snap, level=None):
        """Terrain higher than our level: we cannot climb it, so routes go around it."""
        level = self._level(snap) if level is None else level
        return [t for t in snap.terrain() if t.top > level + 0.5]

    def _blocked_fn(self, snap, ignore=(), level=None):
        """Is the body unable to stand at (x, z)? Off our level, hugging a wall, or on a loose object.

        Walls get 1.6 units of clearance, not just the body's 1.0 radius: the character controller
        snags when it slides along a wall it is touching. `level` asks about another floor than ours.
        """
        level = self._level(snap) if level is None else level
        walls = BoxIndex([(w.pos[0], w.pos[2], w.size[0] / 2 + WALL_CLEARANCE, w.size[2] / 2 + WALL_CLEARANCE)
                          for w in self._walls(snap, level)])
        # Boxes, not circles: at block scale a circle clips a block's corners and the body snags on them.
        clear = BODY_RADIUS + STAND_MARGIN
        things = BoxIndex([(o.pos[0], o.pos[2], o.size[0] / 2 + clear, o.size[2] / 2 + clear)
                           for o in self._in_the_way(snap, ignore, level)])

        def blocked(x, z):
            # Off our floor (open sea, a drop, a step too high), hugging a wall, or on a loose object.
            ground = snap.surface(x, z, below=level + STEP)[0]  # the highest thing we could stand on from this level
            if ground is None or abs(ground - level) > 0.3:
                return True
            return bool(walls.at(x, z, strict=True) or things.at(x, z, strict=True))
        return blocked

    def _route(self, snap, start, goal, ignore=(), escaped=False):
        """Waypoints from start to goal (x, z), or None when no way round is known: A* over half-unit cells, then
        smoothed into straight legs. Half units, because a one-block doorway between grid cells is only just wider
        than the clearance the body keeps, and on whole units half the doorways fall between cells."""
        blocked = self._blocked_fn(snap, ignore)

        def clear(a, b):
            steps = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.5))
            return not any(blocked(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
                           for i in range(1, steps))

        if clear(start, goal):
            return [goal]
        if not escaped and blocked(*start):
            # Standing inside the clearance kept around walls and things (pressed against a wall, boxed in by a
            # ladder): first step out to the nearest clear spot, then plan from there. The step out must not run
            # into anything, or deeper into what we already press against: picking the way out by its end alone
            # walked the body into a ladder over and over (test run t1).
            hard = [(o.pos[0], o.pos[2], o.size[0] / 2 + 0.9, o.size[2] / 2 + 0.9)
                    for o in self._in_the_way(snap, ignore) + self._walls(snap)]

            def depth(p, box):  # how far p is inside a box (0 or less: outside)
                return min(box[2] - abs(p[0] - box[0]), box[3] - abs(p[1] - box[1]))

            def open_line(a, b):
                return not any(depth(p, box) > max(0.0, depth(a, box)) + 0.01 for box in hard
                               for p in ((a[0] + (b[0] - a[0]) * i / 8, a[1] + (b[1] - a[1]) * i / 8) for i in range(1, 9)))
            for radius in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
                out = [(start[0] + radius * math.cos(k * math.pi / 8), start[1] + radius * math.sin(k * math.pi / 8))
                       for k in range(16)]
                out = [p for p in out if not blocked(*p) and open_line(start, p)]
                if out:
                    escape = min(out, key=lambda p: math.dist(p, goal))
                    rest = self._route(snap, escape, goal, ignore, escaped=True)
                    return None if rest is None else [escape] + rest
        res = 0.5
        s, g = (round(start[0] / res), round(start[1] / res)), (round(goal[0] / res), round(goal[1] / res))
        known = {}

        def free(cell):
            if cell not in known:
                known[cell] = not blocked(cell[0] * res, cell[1] * res)
            return known[cell]
        # A goal inside the clearance we keep (the foot of a ladder against a wall) is reached by walking its last
        # stretch straight: stop the search once within 1.5 of it, instead of searching the whole island for it.
        goal_free, reached = free(g), None
        frontier = [(math.dist(s, g), 0.0, s)]
        came, cost = {s: None}, {s: 0.0}
        while frontier:
            _, so_far, cell = heapq.heappop(frontier)
            if cell == g or (not goal_free and math.dist(cell, g) * res <= 1.5):
                reached = cell
                break
            if len(came) > 120000:
                break
            if so_far > cost.get(cell, math.inf):
                continue
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nxt = (cell[0] + dx, cell[1] + dz)
                if nxt != g and not free(nxt):
                    continue
                c = so_far + math.hypot(dx, dz)
                if c < cost.get(nxt, math.inf):
                    cost[nxt], came[nxt] = c, cell
                    heapq.heappush(frontier, (c + math.dist(nxt, g), c, nxt))
        if reached is None:
            return None
        cells, cell = [], reached
        while cell is not None:
            cells.append(cell)
            cell = came[cell]
        cells = [start] + [(x * res, z * res) for x, z in reversed(cells[:-1])] + [goal]
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
        route = self._route(snap, (snap.me[0], snap.me[2]), (x, z), ignore)
        if route is None and not self._lifting:
            pen = self._pen(snap, ignore)
            if pen is not None and self._lift_through(snap, (x, z), ignore, pen):
                snap = self._observe()
                route = self._route(snap, (snap.me[0], snap.me[2]), (x, z), ignore)
        try:
            for wx, wz in route or [(x, z)]:  # no way round known: walk straight, and the stuck check reports it
                snap = self._move_once(wx, wz, stop_within if (wx, wz) == (x, z) else 1.0, ignore=ignore)
        except Stuck as why:
            if not str(why).startswith("stuck"):
                raise
            if replans <= 0:
                if route is None:  # say what pens the body in, or closes off the goal, so the mind can clear a way
                    raise Stuck(f"{why}; {self._closed_by(self._observe(), ignore, (x, z))}") from None
                raise
            # Something moved or the body was pushed off its route: look again and find another way, once.
            self.log(kind="reflex", text=f"{why}; looking for another way")
            time.sleep(0.3)
            return self._move(x, z, stop_within, ignore, replans - 1)
        return snap

    def _pen(self, snap, ignore=()):
        """The floor the body can walk to from where it stands, as half-unit cells, when that is a small closed pen;
        None when it is open further than that. Run n7 told the mind "you are hemmed in" whenever a goal could not be
        reached, also when only the goal was closed off (it lay inside a block) and the body stood in the open."""
        blocked = self._blocked_fn(snap, ignore)
        known = {}

        def free(cell):
            if cell not in known:
                known[cell] = not blocked(cell[0] * 0.5, cell[1] * 0.5)
            return known[cell]
        ox, oz = round(snap.me[0] / 0.5), round(snap.me[2] / 0.5)
        start = next((c for r in range(5) for k in range(16 if r else 1)  # pressed against something: just beside it
                      for c in [(ox + round(r * math.cos(k * math.pi / 8)), oz + round(r * math.sin(k * math.pi / 8)))]
                      if free(c)), None)
        if start is None:
            return set()  # no free floor around the body at all
        seen, todo = {start}, [start]
        while todo:
            ix, iz = todo.pop()
            for n in ((ix + 1, iz), (ix - 1, iz), (ix, iz + 1), (ix, iz - 1)):
                if n not in seen and free(n):
                    seen.add(n)
                    if len(seen) > PEN_CELLS:
                        return None
                    todo.append(n)
        return seen

    def _pen_sides(self, snap, pen, ignore=()):
        """What closes a pen: the pieces and walls whose edges its floor runs up against, nearest first."""
        me = snap.me

        def borders(e, clearance):
            if not pen:
                return e.footprint_contains(me[0], me[2], margin=clearance + 1.5)
            hx, hz = e.size[0] / 2 + clearance + 0.6, e.size[2] / 2 + clearance + 0.6
            return any(abs(ix * 0.5 - e.pos[0]) <= hx and abs(iz * 0.5 - e.pos[2]) <= hz for ix, iz in pen)
        sides = [e for e in self._in_the_way(snap, ignore) if borders(e, 1.2)]
        sides += [w for w in self._walls(snap) if borders(w, 1.6)]
        return sorted(sides, key=lambda e: hdist(e.pos, me))

    def _closed_by(self, snap, ignore=(), goal=None):
        """Why no way round was found, in words: what pens the body in, or what closes off the place it goes to."""
        pen = self._pen(snap, ignore)
        if pen is not None:
            names = [e.name for e in self._pen_sides(snap, pen, ignore)][:5]
            return "no way round: you are penned in" + (f" by {', '.join(names)}" if names else "")
        if goal is None:
            return "no way round was found"
        x, z = goal
        level = self._level(snap)
        floor = snap.surface(x, z, below=level + STEP)[0]
        if floor is None or abs(floor - level) > 0.3:
            return f"no way round: ({x:.1f}, {z:.1f}) is not on the floor you stand on"
        around = self._in_the_way(snap, ignore) + self._walls(snap)
        inside = [e for e in around if e.footprint_contains(x, z)]
        if inside:
            return f"no way round: ({x:.1f}, {z:.1f}) lies inside {inside[0].name}"
        near = [e.name for e in sorted((e for e in around if e.footprint_contains(x, z, margin=3.0)),
                                       key=lambda e: hdist(e.pos, (x, 0, z)))][:5]
        return f"no way round: the way to ({x:.1f}, {z:.1f}) is closed off" + (f" by {', '.join(near)}" if near else "")

    def _lift_through(self, snap, goal, ignore, pen):
        """Reflex, as a person does: penned in by its own pieces, the body lifts one out of the way, steps out
        through the gap and sets it back where it was. What it held it first rests on the pen's wall (or sets down
        inside, if the pen has room), and takes back from outside when it can reach it."""
        level = self._level(snap)
        protected = set(self.protected())
        movables = snap.movables()

        def bare(e):  # nothing rests on it, so lifting it brings nothing down
            return not any(o is not e and abs(o.pos[1] - o.size[1] / 2 - e.top) < 0.3
                           and abs(o.pos[0] - e.pos[0]) < (o.size[0] + e.size[0]) / 2 - 0.1
                           and abs(o.pos[2] - e.pos[2]) < (o.size[2] + e.size[2]) / 2 - 0.1 for o in movables)
        sides = [e for e in self._pen_sides(snap, pen, ignore) if e.movable and e.name.startswith(LIFTABLE)
                 and not e.attrs.get("Fastened") and not e.attrs.get("Burning")
                 and abs(e.pos[1] - e.size[1] / 2 - level) < 0.3 and bare(e)]
        sides.sort(key=lambda e: (e.name in protected, hdist(e.pos, snap.me)))  # what it decided to keep, last
        for piece in sides[:6]:
            path = self._route(snap, (snap.me[0], snap.me[2]), goal, set(ignore) | {piece.name})
            out = self._past((snap.me[0], snap.me[2]), path, piece) if path else None
            if out is None:
                continue
            held = snap.held()
            self._lifting = True
            try:
                on_wall = None  # what it held, rested on the pen's wall while its hands lift the way out
                if held and (len(pen) < 40 or self._set_down_nearby(snap, held, piece.pos) is None):
                    on_wall = self._rest_on(snap, held, [e for e in sides if e is not piece])
                    if on_wall is None:
                        return False
                if not self._lift(piece):
                    return False
                self._move(*out)
                turn = 90 if piece.size[2] > piece.size[0] + 0.1 else 0
                upright = piece.size[1] > max(piece.size[0], piece.size[2]) + 0.1
                back = self.skill_place_at(piece.pos[0], piece.pos[1], piece.pos[2], turn, upright)
                if not back.ok:  # it stays out of its place, but not in the hands
                    snap = self._observe()
                    if snap.held():
                        self._set_down_nearby(snap, snap.held(), piece.pos)
                if on_wall and self._observe().held() is None:
                    self.skill_pick_up(on_wall)  # and take back what it rested on the wall, from outside
                self.log(kind="reflex", text=f"penned in: lifted {piece.name} out of the way, stepped out "
                                             + ("and set it back" if back.ok else f"(it could not go back: {back.summary})"))
                return True
            except Stuck:
                return False
            finally:
                self._lifting = False
        return False

    def _lift(self, piece):
        """Pick up a piece the body stands beside, without first looking for room around it: in a pen there is none."""
        snap = self.world.act("Pickup", {"position": list(piece.pos)})
        if snap.last_result == "PickupSuccess":
            held = self._settle(LIFT_SECONDS + 0.2).held()
            if held and held.name == piece.name:
                return True
        return self.skill_pick_up(piece.name).ok

    def _rest_on(self, snap, held, walls):
        """Rest what the hands hold on top of one of `walls` (bare pieces beside the body). Its name, or None."""
        for wall in sorted(walls, key=lambda e: hdist(e.pos, snap.me)):
            top = (wall.pos[0], wall.top + held.local_size[1] / 2 + 0.02, wall.pos[2])
            if self.world.act("Place", {"position": list(top), "rotation": _rotation(0, False)}).last_result == "PlaceSuccess":
                self._settle(PLACE_SECONDS + 0.4)
                return held.name
        return None

    @staticmethod
    def _past(start, path, piece):
        """The first point along `path` clear beyond `piece`, once the path has gone through where it lies."""
        through, prev = False, start
        for wp in path:
            steps = max(1, int(math.dist(prev, wp) / 0.5))
            for i in range(1, steps + 1):
                p = (prev[0] + (wp[0] - prev[0]) * i / steps, prev[1] + (wp[1] - prev[1]) * i / steps)
                if piece.footprint_contains(*p, margin=1.2):
                    through = True
                elif through and not piece.footprint_contains(*p, margin=2.2):
                    return p
            prev = wp
        return path[-1] if through else None

    def _move_once(self, x, z, stop_within, retry=True, ignore=()):
        # The humanoid walks on whatever surface it is on; MoveTo just needs some y.
        snap = self.world.act("MoveTo", {"position": [x, BODY_CENTRE_Y, z]})
        sent = time.time()
        dist = hdist(snap.me, (x, 0, z))
        pace = snap.walk_speed or self.walk_speed  # a heavy load and the rain slow the walk (main.lua WalkSpeed)
        deadline = time.time() + dist / pace * 2.5 + 3
        best, last_progress = dist, time.time()
        while dist > stop_within:
            time.sleep(0.12)
            if time.time() - sent > 6:  # the engine's MoveTo gives up after 8 s, as Roblox's does: renew it on long walks
                self.world.act("MoveTo", {"position": [x, BODY_CENTRE_Y, z]})
                sent = time.time()
            snap = self._observe()
            if snap.me[1] < 0.8:
                self.world.act("Stop")
                raise Stuck("fell off the edge into the sea")
            dist = hdist(snap.me, (x, 0, z))
            if dist < best - 0.05:
                best, last_progress = dist, time.time()
            if time.time() - last_progress > 1.2 or time.time() > deadline:
                self.world.act("Stop")
                if retry and self._unstick(snap, ignore):  # not away from what we are walking up to
                    return self._move_once(x, z, stop_within, retry=False, ignore=ignore)
                raise Stuck(f"stuck {dist:.1f} units short of ({x:.1f}, {z:.1f})")
        return self.world.act("Stop")

    def _unstick(self, snap, ignore=()):
        """Reflex: when snagged, step straight away from what snags us (a wall, a piece, a ladder), then let the
        caller retry. Squeezed between two things on opposite sides, slip out along the gap between them."""
        walls = self._walls(snap) + self._in_the_way(snap, ignore)
        if not walls:
            return False
        me = snap.me

        def gap(w):
            return math.hypot(max(abs(me[0] - w.pos[0]) - w.size[0] / 2, 0), max(abs(me[2] - w.pos[2]) - w.size[2] / 2, 0))

        def away(w):
            dx = me[0] - min(max(me[0], w.pos[0] - w.size[0] / 2), w.pos[0] + w.size[0] / 2)
            dz = me[2] - min(max(me[2], w.pos[2] - w.size[2] / 2), w.pos[2] + w.size[2] / 2)
            if math.hypot(dx, dz) < 0.05:  # pressed into it: out through its nearest face
                ox, oz = me[0] - w.pos[0], me[2] - w.pos[2]
                hx, hz = w.size[0] / 2, w.size[2] / 2
                _, (dx, dz) = min(((hx - ox, (1, 0)), (hx + ox, (-1, 0)), (hz - oz, (0, 1)), (hz + oz, (0, -1))))
            norm = math.hypot(dx, dz) or 1.0
            return dx / norm, dz / norm
        wall = min(walls, key=gap)
        if gap(wall) > 2.5:
            return False
        touching = [w for w in walls if gap(w) <= 1.2] or [wall]
        pushes = [away(w) for w in touching]
        dx, dz = sum(p[0] for p in pushes), sum(p[1] for p in pushes)
        if math.hypot(dx, dz) < 0.3:  # pushed equally from opposite sides: along the gap instead
            dx, dz = -pushes[0][1], pushes[0][0]
        norm = math.hypot(dx, dz) or 1.0
        ex, ez = me[0] + dx / norm * 2.5, me[2] + dz / norm * 2.5
        self.log(kind="reflex", text=f"snagged by {', '.join(w.name for w in touching)}; stepping away to ({ex:.1f}, {ez:.1f})")
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
        reaches = self._reach_fn(snap, target, ignore, level)
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
                if math.dist(body, target) > reach - 0.4 or not reaches(sx, sz):
                    continue
                score = math.hypot(sx - me[0], sz - me[2])
                if best is None or score < best[0]:
                    best = (score, (sx, sz))
            if best:
                return best[1]
        return self._close_stand_point(snap, target, reach, ignore, avoid)

    def _reach_fn(self, snap, target, ignore, level):
        """Can the hands reach `target` from a spot (x, z) in a straight line? Not through anything two blocks high or
        more standing between: a wall (the arms reach over a block lying on the floor, not over a wall)."""
        tx, tz = target[0], target[2]
        high = [(o.pos[0], o.pos[2], o.size[0] / 2, o.size[2] / 2)
                for o in self._in_the_way(snap, ignore, level) + self._walls(snap, level)
                if o.top >= level + 2 * CUBE - 0.2 and o.pos[1] - o.size[1] / 2 < level + BODY_HEIGHT
                and not o.footprint_contains(tx, tz)]  # what the target lies in or on is what the hands reach into
        columns = BoxIndex(high)

        def reaches(x, z):
            steps = max(1, int(math.hypot(tx - x, tz - z) / 0.25))
            return not any(columns.at(x + (tx - x) * i / steps, z + (tz - z) * i / steps, strict=True)
                           for i in range(1, steps))
        return reaches

    def _close_stand_point(self, snap, target, reach, ignore=(), avoid=None):
        """Where the whole body fits within reach of `target`, when no spot on the rings round it is clear. In a
        house's room two cells wide (ADR-019), a block lying in a cell inside leaves only the free cells round it, a
        quarter unit wider than the body on each side, and every ring crosses a wall or the block. So every spot within
        reach is tried, on a quarter-unit grid from the target (the grid pieces settle on, so cell centres are on it),
        with the clearance kept anywhere else: the body's radius and STAND_MARGIN from loose pieces and from `avoid`,
        WALL_CLEARANCE from rock. The hands must reach the target in a straight line, not through anything two blocks
        high. Of the spots left, the one with most room to spare is taken, the nearest to us among equals."""
        tx, ty, tz = target
        level = self._level(snap)
        blocked = self._blocked_fn(snap, ignore)
        clear = BODY_RADIUS + STAND_MARGIN
        near = reach + 2 * CUBE
        boxes = [(w.pos[0], w.pos[2], w.size[0] / 2, w.size[2] / 2, WALL_CLEARANCE, w.top)
                 for w in self._walls(snap, level) if hdist(w.pos, target) < near + max(w.size[0], w.size[2]) / 2]
        boxes += [(o.pos[0], o.pos[2], o.size[0] / 2, o.size[2] / 2, clear, o.top)
                  for o in self._in_the_way(snap, ignore, level) if hdist(o.pos, target) < near]
        if avoid is not None:
            boxes.append((avoid.pos[0], avoid.pos[2], avoid.size[0] / 2, avoid.size[2] / 2, clear, level))
        reaches = self._reach_fn(snap, target, ignore, level)

        def spare(x, z):  # room beyond the clearance to the nearest box
            return min((math.hypot(max(abs(x - bx) - hx, 0), max(abs(z - bz) - hz, 0)) - c for bx, bz, hx, hz, c, _ in boxes),
                       default=CUBE)
        best, step = None, 0.25
        n = int(reach / step)
        for i in range(-n, n + 1):
            for k in range(-n, n + 1):
                sx, sz = tx + i * step, tz + k * step
                if math.dist((sx, level + BODY_CENTRE_Y, sz), target) > reach - 0.4 or blocked(sx, sz):
                    continue
                room = spare(sx, sz)
                if room < 0 or not reaches(sx, sz):
                    continue
                score = (min(round(room, 2), 0.5), -math.hypot(sx - snap.me[0], sz - snap.me[2]))
                if best is None or score > best[0]:
                    best = (score, (sx, sz))
        return best[1] if best else None

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

    # ---- beams: a long piece laid flat, up off the ground -----------------------------------------------
    # A roof, a lintel or a bridge is a log across two supports. It stays up only if both its ends lie on something
    # of the same height; in runs hut1-hut3 seven of seventeen raised logs fell or tilted, set a cell off their
    # posts, turned the wrong way, or across posts of unequal height, and the report said only "not resting on
    # anything". Now the hands find the supports, as a person feels for the post under the beam's end: aimed within a
    # cell or a quarter turn of two supports of the same height, the log is set on them. And when one falls anyway,
    # the report says what was under each end.
    @staticmethod
    def _beam_ends(centre, size):
        """The centres of the end cells of a long piece lying flat (along x or along z)."""
        half = (max(size[0], size[2]) - CUBE) / 2
        x, _, z = centre
        return ((x - half, z), (x + half, z)) if size[0] >= size[2] else ((x, z - half), (x, z + half))

    def _under_ends(self, snap, centre, size):
        """What lies under each end of a beam at `centre`: [(x, z, top, entity)], the highest thing no higher than its
        bottom (top and entity None over the sea)."""
        bottom = centre[1] - size[1] / 2
        return [(x, z, *snap.surface(x, z, below=bottom + 0.25)) for x, z in self._beam_ends(centre, size)]

    @staticmethod
    def _ends_text(ends, bottom):
        words = []
        for x, z, top, e in ends:
            where = f"its end at ({x:.1f}, {z:.1f})"
            if e is None or e.role == "Ground":
                words.append(f"{where} had nothing under it but the ground")
            elif top < bottom - 0.3:
                words.append(f"{where} hung {bottom - top:.2f} above {e.name} (top {top:.2f})")
            else:
                words.append(f"{where} lay on {e.name} (top {top:.2f})")
        return "; ".join(words)

    def _raised_beam(self, snap, target, size, upright):
        """Whether this is a long piece laid flat, up off the ground (a beam), rather than one lying on the ground."""
        if upright or max(size[0], size[2]) < CUBE + 0.1:
            return False
        floor = snap.ground_top(target[0], target[2]) or 0.0
        return target[1] - size[1] / 2 > floor + CUBE / 2

    def _beam_on_supports(self, snap, held, target, turn, size):
        """Where to set a beam so that both its ends rest on something of the same height: where it was aimed if they
        do there, else the nearest of a cell either way or a quarter turn that does (nothing in the way). Supports may
        be at most one layer below where it was aimed. Returns (target, turn, size, what it did, in words)."""
        bottom = target[1] - size[1] / 2

        def rests(centre, sz):
            ends = self._under_ends(snap, centre, sz)
            tops = [top for _, _, top, e in ends]
            if any(e is None or e.role == "Ground" for _, _, _, e in ends):
                return None
            if max(tops) - min(tops) > 0.3 or min(tops) < bottom - CUBE - 0.3:
                return None
            return ends

        if rests(target, size):
            return target, turn, size, ""
        other = 0 if turn == 90 else 90
        options = [(turn, dx, dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        options += [(other, dx, dz) for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))]
        for t, dx, dz in options:
            sz = turned_size(held.local_size, t, False)
            ends = rests((target[0] + dx * CUBE, target[1], target[2] + dz * CUBE), sz)
            if not ends:
                continue
            centre = (target[0] + dx * CUBE, max(top for _, _, top, _ in ends) + sz[1] / 2 + 0.03, target[2] + dz * CUBE)
            if self._overlapping(snap, centre, sz, ignore={held.name}):
                continue
            props = ends[0][3].name if ends[0][3] is ends[1][3] else f"{ends[0][3].name} and {ends[1][3].name}"
            aimed = (f"you aimed it at ({target[0]:.1f}, {target[1]:.2f}, {target[2]:.1f}) along "
                     f"{'z' if turn == 90 else 'x'}, where " + self._ends_text(self._under_ends(snap, target, size), bottom))
            moved = f"so your hands set it along {'z' if t == 90 else 'x'} with its ends on {props} instead"
            return centre, t, sz, f" ({aimed}; {moved})"
        return target, turn, size, ""

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
            floor = snap.surface(x, z, below=level + STEP)[0]
            overhead = (part is not None and floor is not None and floor <= level + 0.3
                        and part.pos[1] - part.size[1] / 2 - floor > STEP)
            # A roof or a lintel over the floor there is something to walk under, not to climb (run n8's body never got
            # under one: it was told the spot was "on top of" the roof). Too low to stand under is said further on.
            # Judged from the floor there, not the level we stand on: up on the step a roof was laid from, the room's
            # floor lies below us (run hp-proj8), and the walk hops down to it first.
            if part is not None and part.movable and top > level + 1.0 and not overhead:
                rise, height = part, top
        if rise is not None or ground > level + 0.5:
            mesa = rise.name if rise else "a mesa"
            where = (f"({x:.1f}, {z:.1f}) is inside the trunk of {mesa}" if rise and rise.role == "Tree"
                     else f"({x:.1f}, {z:.1f}) is on top of {mesa} (height {height:.1f})")
            # A step is terrain or a building piece, a block or so high: not the ball, a coconut or a tool (the first
            # smoke run stepped up onto the volleyball).
            steppable = rise is None or rise.role in ("Mesa", "Ground", "Quarry") or (
                rise.movable and rise.name.startswith(SNAPPED_KINDS + ("Brick_",)))
            if steppable and 1.5 <= height - level <= STEP_UP + 0.05:
                stepped = self._step_up(snap, x, z, height)
                if stepped is not None:
                    if not stepped.ok or hdist(self._observe().me, (x, 0, z)) < 1.0:
                        return stepped
                    on = self.skill_walk_to(x, z)  # and on across the top
                    return Result(on.ok, "walk_to", f"{stepped.summary}, then {on.summary}")
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
        near = [e for e in self._in_the_way(snap) if e.footprint_contains(x, z, margin=1.3)]
        if near:
            # Stop just outside it, on the side nearest the spot asked for: beside a long log, not a log's length away.
            e = min(near, key=lambda o: math.hypot(o.pos[0] - x, o.pos[2] - z))
            hx, hz = e.size[0] / 2 + 1.5, e.size[2] / 2 + 1.5
            exits = [(e.pos[0] + hx, z), (e.pos[0] - hx, z), (x, e.pos[2] + hz), (x, e.pos[2] - hz)]
            x, z = min(exits, key=lambda p: (round(math.hypot(p[0] - x, p[1] - z), 1), hdist(snap.me, (p[0], 0, p[1]))))
            bottom = e.pos[1] - e.size[1] / 2
            under = bottom - level
            beneath = snap.surface(e.pos[0], e.pos[2], below=bottom + 0.05)[0]  # what it rests on, if anything
            if under > STEP and (beneath is None or bottom - beneath > STEP):
                # Overhead with open floor beneath, but lower than the body is tall (run n8 built its hut roof so).
                note = (f"; {e.name} is overhead there with its underside {under:.1f} up, too low for you to stand under "
                        f"(you are {BODY_HEIGHT:g} tall), so you stopped beside it")
            else:
                note = f"; stopped beside {e.name} instead of walking into it"
        snap = self._move(x, z)
        return Result(True, "walk_to", f"walked to ({snap.me[0]:.1f}, {snap.me[2]:.1f}){note}" + _weather_here(snap))

    def _step_up(self, snap, x, z, top):
        """Walk to the foot of what stands one block higher at (x, z) and step up onto it, at the edge nearest us.
        A Result, or None when there is no edge to step onto from here (the caller then stops at its foot)."""
        level = self._level(snap)
        me = snap.me
        steps = max(1, int(hdist(me, (x, 0, z)) / 0.25))
        line = [(x + (me[0] - x) * i / steps, z + (me[2] - z) * i / steps) for i in range(steps + 1)]
        k = -1  # how far its top runs from (x, z) back towards us: other tops further on (a pile) are not its edge
        while k + 1 < len(line) and abs((snap.surface(*line[k + 1], below=top + 0.3)[0] or -99) - top) < 0.3:
            k += 1
        if k < 0:
            return None
        onto = line[max(0, k - 4)]  # a unit inside its edge: the whole body fits on it there
        blocked = self._blocked_fn(snap)
        foot = next((p for p in line[k + 1:] if not blocked(*p)), None)
        what = snap.surface(*onto, below=top + 0.3)[1]
        name = what.name if what is not None else "it"
        if what is not None and what.movable:  # onto the middle of a piece: beside a taller one (a stair) it fits there
            onto = tuple(min(max(c, p - max(s / 2 - 1.0, 0)), p + max(s / 2 - 1.0, 0))
                         for c, p, s in ((onto[0], what.pos[0], what.size[0]), (onto[1], what.pos[2], what.size[2])))
        if foot is not None and hdist(me, (foot[0], 0, foot[1])) > 0.6:
            snap = self._move(*foot)
        if hdist(snap.me, (onto[0], 0, onto[1])) > 2.6:  # the foot the router keeps clear is a little far: closer
            try:
                snap = self._move_once(onto[0], onto[1], 2.3)
            except Stuck:
                snap = self._observe()
        snap = self.world.act("StepUp", {"position": [onto[0], onto[1]]})
        outcome = snap.last_result or ""
        if not outcome.startswith("StepUpStarted"):
            why = {"StepUpFailed:TooFar": "its edge was out of reach", "StepUpFailed:NoRoom": "there is no room for you on it",
                   "StepUpFailed:TooHigh": "it is more than a block higher than your feet",
                   "StepUpFailed:NothingToStepOn": "there was nothing to step on",
                   "StepUpFailed:Busy": "you were already climbing"}.get(outcome, outcome or "nothing happened")
            return Result(False, "walk_to", f"could not step up onto {name} at ({onto[0]:.1f}, {onto[1]:.1f}): {why}")
        deadline = time.time() + 3
        while time.time() < deadline and self._observe().raw.get("player", {}).get("attributes", {}).get("Climbing"):
            time.sleep(0.15)
        snap = self._observe()
        return Result(True, "walk_to", f"stepped up onto {name}, now standing at height {self._level(snap):.1f} "
                                       f"at ({snap.me[0]:.1f}, {snap.me[2]:.1f})")

    def _approach(self, snap, target, reach, min_radius, ignore=(), avoid=None):
        """A spot on our floor within reach of `target`. From up on something, with nothing in reach up here and the
        target below, hop down towards it first, as a person would. Returns (spot or None, latest snapshot)."""
        stand = self._stand_point(snap, target, reach, min_radius, ignore, avoid)
        level = self._level(snap)
        if stand is None and level > 0.3 and target[1] < level + 1.0:
            # The floor we would stand on down there: under the target, not the target's own top.
            floor = snap.surface(target[0], target[2], below=min(level, target[1]) - 0.3)[0]
            if floor is not None:  # hop down, or take a ladder down where the drop is too high
                if self._hop_down(snap, target[0], target[2], level, floor, walk_on=False).ok:
                    snap = self._observe()
                    stand = self._stand_point(snap, target, reach, min_radius, ignore, avoid)
        return stand, snap

    def _step_up_to_reach(self, snap, target, spot, held):
        """Step up onto something a block high near `target` (x, y, z), from where the hands reach it: what a person
        does to set a stone above their head. Returns (where to stand or None, latest snapshot, how, or why not)."""
        level = self._level(snap)

        def hands(x, z, floor):
            return math.dist((x, floor + BODY_CENTRE_Y, z), target)
        steps = []
        for e in snap.movables() + snap.terrain():
            if e.name == held or not 1.5 <= e.top - level <= STEP_UP + 0.05:
                continue
            if not (e.role in ("Mesa", "Quarry") or (e.movable and e.name.startswith(SNAPPED_KINDS + ("Brick_",)))):
                continue
            # Stand on its top as near the target as the whole body fits, a unit inside its edges; on a block right
            # beside the spot, that would press the body against what stands there: then on the block's middle.
            x, z = (min(max(t, c - max(s / 2 - 1.0, 0)), c + max(s / 2 - 1.0, 0))
                    for t, c, s in ((target[0], e.pos[0], e.size[0]), (target[2], e.pos[2], e.size[2])))
            if spot.footprint_contains(x, z, margin=1.15):
                x, z = e.pos[0], e.pos[2]
            if spot.footprint_contains(x, z, margin=1.15) or hands(x, z, e.top) > PLACE_RANGE - 0.5:
                continue
            if abs((snap.surface(x, z)[0] or -99) - e.top) > 0.3:  # something else stands on it there
                continue
            steps.append((hdist(snap.me, (x, 0, z)), x, z, e))
        if not steps:
            return None, snap, ("; it is above your reach from there, and nothing one block high stands near it to "
                                "step up onto")
        why = ""
        for _, x, z, e in sorted(steps, key=lambda s: s[0])[:2]:
            self.log(kind="reflex", text=f"({target[0]:.1f}, {target[1]:.1f}, {target[2]:.1f}) is above reach: "
                                         f"stepping up onto {e.name}")
            walked = self.skill_walk_to(x, z)
            snap = self._observe()
            floor = self._level(snap)
            if abs(floor - e.top) < 0.4 and hands(snap.me[0], snap.me[2], floor) <= PLACE_RANGE - 0.1:
                return (snap.me[0], snap.me[2]), snap, f"; you stood on {e.name} to reach that high"
            why = (f"; it is above your reach from the ground, and stepping up onto {e.name} did not bring it in "
                   f"reach: {walked.summary}")
        return None, snap, why

    def _here(self, snap):
        """Where the body stands, in words, when it is not simply on the ground."""
        level = self._level(snap)
        if level <= 0.3:
            return "here"
        on = snap.surface(snap.me[0], snap.me[2], below=level + STEP)[1]
        return f"up here on {on.name if on else 'something'} (height {level:.1f})"

    def _out_of_reach(self, snap, target, what, otherwise):
        """Why `what` at `target` cannot be reached, when the plain reason is that we stand too high above it."""
        level = self._level(snap)
        floor = snap.surface(target[0], target[2], below=min(level, target[1]) - 0.3)[0] if level > 0.3 else None
        if floor is not None and level - floor > MAX_DROP and target[1] < level:
            return (f"{what} is below you, out of reach: you are {self._here(snap)}, {level - floor:.1f} above the "
                    f"floor there, too high to hop down; climb down first")
        return otherwise

    def _ways_off(self, snap, goal, level):
        """Ways to hop off the floor we stand on, best first: (edge spot, landing spot, landing height). The landing is
        lower by no more than a hop and clear to stand on, and the step off runs into no wall and no standing thing
        (a ladder set against the edge). Best: nearest to us, landing nearest the goal (x, z)."""
        blocked_here = self._blocked_fn(snap)
        mx, mz = snap.me[0], snap.me[2]
        spots = [(mx + dx * 0.5, mz + dz * 0.5) for dx in range(-16, 17) for dz in range(-16, 17)]
        spots = [p for p in spots if not blocked_here(*p)]
        # Only what sticks up above our floor is in the way of stepping off. The block we stand on is our floor, not an
        # obstacle (counting it left Godling with "no clear edge" on a block, test run t2); what lies lower we land on.
        in_way = BoxIndex([(e.pos[0], e.pos[2], e.size[0] / 2 + 1.0, e.size[2] / 2 + 1.0) for e in self._walls(snap, level)]
                          + [(o.pos[0], o.pos[2], o.size[0] / 2 + 1.0, o.size[2] / 2 + 1.0) for o in self._obstacles(snap)
                             if o.top > level + STEP and o.pos[1] - o.size[1] / 2 < level + 4.5])
        below_fns = {}
        ways = []
        for sx, sz in spots:
            for k in range(8):
                lx, lz = sx + 2.8 * math.cos(k * math.pi / 4), sz + 2.8 * math.sin(k * math.pi / 4)
                below = snap.surface(lx, lz, below=level + STEP)[0]
                if below is None or below > level - 0.5 or level - below > MAX_DROP:
                    continue  # not an edge here, the sea, or too far down
                key = round(below, 1)
                if key not in below_fns:
                    below_fns[key] = self._blocked_fn(snap, level=below)
                if below_fns[key](lx, lz):
                    continue
                path = [(sx + (lx - sx) * i / 6, sz + (lz - sz) * i / 6) for i in range(1, 6)]
                if any(in_way.at(px, pz, strict=True) for px, pz in path):
                    continue
                score = math.hypot(sx - mx, sz - mz) + math.hypot(lx - goal[0], lz - goal[1])
                ways.append((score, (sx, sz), (lx, lz), below))
        ways.sort(key=lambda w: w[0])
        return [w[1:] for w in ways]

    def _step_down(self, snap, goal, level):
        """Down off what we stand on, a block or less, onto clear floor right beside us: the world takes the body over
        the edge (StepDown, ADR-010). The landing nearest the goal first. True once the body is down."""
        me, fns, spots = snap.me, {}, []
        for r in (2.0, 2.4, 2.75):
            for k in range(16):
                lx, lz = me[0] + r * math.cos(k * math.pi / 8), me[2] + r * math.sin(k * math.pi / 8)
                below = snap.surface(lx, lz, below=level + STEP)[0]
                if below is None or below > level - 0.5 or level - below > MAX_DROP:
                    continue  # not lower here, the sea, or too far down
                key = round(below, 1)
                if key not in fns:
                    fns[key] = self._blocked_fn(snap, level=below)
                if not fns[key](lx, lz):
                    spots.append((math.hypot(lx - goal[0], lz - goal[1]), lx, lz))
        for _, lx, lz in sorted(spots)[:4]:
            if not (self.world.act("StepDown", {"position": [lx, lz]}).last_result or "").startswith("StepDownStarted"):
                continue  # no room for the body there after all
            deadline = time.time() + 3
            while time.time() < deadline and self._observe().raw.get("player", {}).get("attributes", {}).get("Climbing"):
                time.sleep(0.15)
            if self._level(self._observe()) < level - 0.4:
                return True
        return False

    def _ladder_down(self, snap, level):
        """The nearest ladder standing with its top at our level: the way down where a hop is too far."""
        held, best = snap.held(), None
        for e in snap.movables():
            if not e.name.startswith("Ladder_") or e is held or e.size[1] < 5:  # set up, a ladder stands 7.5 tall
                continue
            bottom, top = e.pos[1] - e.size[1] / 2, e.pos[1] + e.size[1] / 2
            if bottom + 0.9 < level <= top + 0.6 and (best is None or hdist(e.pos, snap.me) < hdist(best.pos, snap.me)):
                best = e
        return best

    def _hop_down(self, snap, x, z, level, floor, walk_on=True):
        """From up on something, a drop a person would hop down: walk to the edge on the way, step off, land, walk on.
        Too high to hop, but with a ladder standing against what we are on, climb down it instead, as a person would
        (in test run t3 Godling stood on its own piers while every plan that began on the ground failed at once)."""
        on = snap.surface(snap.me[0], snap.me[2], below=level + STEP)[1]
        on = on.name if on else "something"
        drop = level - floor
        if self._step_down(snap, (x, z), level):  # onto any lower floor beside us: the ground, or a stair's next step
            if not walk_on:
                return Result(True, "walk_to", f"stepped down from {on}")
            if drop <= MAX_DROP:
                snap = self._move(x, z)  # walk on from where we landed
                return Result(True, "walk_to", f"stepped down {drop:.1f} from {on} and walked to "
                                               f"({snap.me[0]:.1f}, {snap.me[2]:.1f})")
            onward = self.skill_walk_to(x, z)  # still higher than the goal: down the next step
            return Result(onward.ok, "walk_to", f"stepped down from {on}; {onward.summary}", onward.facts)
        ways = self._ways_off(snap, (x, z), level) if drop <= MAX_DROP else []
        if not ways:  # too high to hop, or no edge here to hop from: a ladder, if one stands up here
            ladder = self._ladder_down(snap, level)
            if ladder is None:
                if drop > MAX_DROP:
                    return Result(False, "walk_to", f"you are up on {on} at height {level:.1f}, and ({x:.1f}, {z:.1f}) "
                                                    f"is {drop:.1f} lower: too far to hop down, and no ladder stands up here")
                return Result(False, "walk_to", f"you are up on {on} at height {level:.1f} with no clear edge to hop down from")
            self.log(kind="reflex", text=f"no way to hop down from {on}; climbing down {ladder.name} first")
            climbed = self.skill_climb(ladder.name)
            if not climbed.ok or climbed.facts.get("level", level) > level - 0.3:
                return Result(False, "walk_to", f"you are up on {on} at height {level:.1f}, too high to hop down, and "
                                                f"climbing down {ladder.name} failed: {climbed.summary}")
            note = f"climbed down {ladder.name} from {on}"
            if not walk_on:
                return Result(True, "walk_to", note)
            onward = self.skill_walk_to(x, z)
            return Result(onward.ok, "walk_to", f"{note}; {onward.summary}", onward.facts)
        landed, tried = False, []
        for edge, land, below in ways:  # best first; a blocked step-off gets two other tries elsewhere on the edge
            if len(tried) == 3 or landed:
                break
            if any(math.dist(edge, t) < 2.0 for t in tried):
                continue
            tried.append(edge)
            try:
                if hdist(self._observe().me, (edge[0], 0, edge[1])) > 0.6:
                    self._move(*edge)
            except Stuck:
                continue
            self.world.act("MoveTo", {"position": [land[0], BODY_CENTRE_Y, land[1]]})  # step off the edge
            deadline = time.time() + 3
            while time.time() < deadline and not landed:
                time.sleep(0.15)
                landed = self._observe().me[1] < level + BODY_CENTRE_Y - 0.5 * (level - below)
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
            return Result(False, "pick_up", f"{object} is fastened in place; a hammer strike knocks it loose")
        if obj.attrs.get("Burning"):  # a log on fire is the fire's now (run n7 kept reaching for them)
            return Result(False, "pick_up", f"{object} is burning; it cannot be picked up until the fire is out")
        build = None if self._lifting else self.kept_in(object)
        if build:
            # What it built is its own: its plans took its own builds apart for material (runs rp3 and hut1).
            # Lifting a piece aside to step out of a pen is a reflex, and puts the piece back.
            if build.startswith("your house"):  # kept for the house it is building (Mind.house_project)
                return Result(False, "pick_up", f"{object} is part of {build}, which you are building; move the house or "
                                                "give it up first (\"house\", with why) if you mean to take it apart")
            return Result(False, "pick_up", f"{object} is part of {build}, which you built; release that first if you "
                                            "mean to take it apart")
        held = snap.held()
        if held and held.name == object:
            return Result(True, "pick_up", f"already holding {object}", {"holding": object})
        note = ""
        if held:
            freed = self._set_down_nearby(snap, held, obj.pos)
            if freed is None:
                return Result(False, "pick_up", f"hands are full: holding {held.name}, and there is no clear spot nearby to "
                                                "set it down" + (" outside your house's room, doorway and way out"
                                                                 if self._kept_clear else ""))
            note = f" (first {freed.summary.replace('put', 'set', 1)}, to free your hands)"
            snap = self._observe()
            obj = snap.entities.get(object)
            if obj is None:
                return Result(False, "pick_up", f"{object} vanished{note}")
        # Beside it: its narrow side sets how close we may stand; a long beam or ladder we stand beside, at its middle.
        stand, snap = self._approach(snap, obj.pos, PICKUP_RANGE, 1.6 + min(obj.size[0], obj.size[2]) / 2,
                                     ignore={object}, avoid=obj)
        if stand is None:
            return Result(False, "pick_up", self._out_of_reach(
                snap, obj.pos, object, f"no clear spot to reach {object} from {self._here(snap)} "
                                       f"(it may be up on something)") + note)
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
        """Reflex, as a person does: set what is in your hands on clear floor beside you before taking something else.
        The floor we stand on, which may be a platform we built (looking only at the ground there failed, test run t3);
        a long log may lie either way round."""
        level = self._level(snap)
        kept = [e for name, e in snap.entities.items() if name in set(self.protected())]
        spots = [(snap.me[0] + r * math.cos(k * math.pi / 4), snap.me[2] + r * math.sin(k * math.pi / 4))
                 for r in (CUBE + 1.0, CUBE + 2.0, CUBE + 3.5, CUBE + 5.0) for k in range(8)]

        def on_our_floor(x, z):
            top = snap.surface(x, z, below=level + STEP)[0]
            return top is not None and abs(top - level) < 0.3
        # Out of the way: not on what we came for, not against anything we decided to keep.
        spots = [(x, z) for x, z in spots
                 if on_our_floor(x, z)
                 and hdist((x, 0, z), away_from) > CUBE + 0.5 and all(hdist((x, 0, z), e.pos) > CUBE for e in kept)]
        long = max(held.local_size) > CUBE + 0.1 and not held.name.startswith("Ladder_")
        reserved = set(self.reserved())
        self._kept_clear = False

        def clear_of_reserved(x, z, turn):  # the whole of it as it would lie, not only where its middle goes
            if not reserved:
                return True
            if held.name.startswith(SNAPPED_KINDS):
                x, z = grid(x), grid(z)
            size = turned_size(held.local_size, turn, False)
            cells = {(ix, iz) for ix in range(math.ceil((x - size[0] / 2) / CUBE - 1e-9), math.ceil((x + size[0] / 2) / CUBE - 1e-9))
                     for iz in range(math.ceil((z - size[2] / 2) / CUBE - 1e-9), math.ceil((z + size[2] / 2) / CUBE - 1e-9))}
            if cells & reserved:
                self._kept_clear = True
                return False
            return True
        # The house's room, doorway and way out stay clear (run hp-full2), before the nearest few are tried.
        tries = [(x, z, turn) for x, z in sorted(spots, key=lambda p: -hdist((p[0], 0, p[1]), away_from))
                 for turn in ((0, 90) if long else (0,)) if clear_of_reserved(x, z, turn)]
        for x, z, turn in tries[:16]:
            result = self.skill_put_down(x, z, turn)
            if result.ok:
                if self.placed and self.placed[-1] == held.name:
                    self.placed.pop()  # set down to free the hands, not built with
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
        hx, hz = size[0] / 2, size[2] / 2
        level = self._level(snap)
        floor = snap.surface(x, z, below=level + STEP)[0]  # the ground, or a floor we built at our own level
        floor = ground if floor is None else floor
        covering = max((t for t in snap.terrain() if t.footprint_contains(x, z)), key=lambda t: t.top)
        if covering.role == "Tree":
            return Result(False, "put_down", f"({x:.1f}, {z:.1f}) is inside the trunk of {covering.name}")
        if not ladder:  # a ladder is meant to stand against something
            for t in snap.terrain():  # a mesa wall or a trunk right beside the spot leaves no room for the object
                if t.top > floor + 0.3 and abs(x - t.pos[0]) < t.size[0] / 2 + hx and abs(z - t.pos[2]) < t.size[2] / 2 + hz:
                    return Result(False, "put_down", f"({x:.1f}, {z:.1f}) is too close to {t.name} to set anything down")
            for e in self._obstacles(snap, ignore={held.name}):  # boxes: side by side in neighbouring cells is fine
                if (abs(e.pos[0] - x) < hx + e.size[0] / 2 - 0.05 and abs(e.pos[2] - z) < hz + e.size[2] / 2 - 0.05
                        and e.top > floor + 0.05 and e.pos[1] - e.size[1] / 2 < floor + 3):
                    return Result(False, "put_down", f"({x:.1f}, {z:.1f}) is occupied by {e.name}")
        target = (x, floor + size[1] / 2 + (0.02 if ladder else 0.12), z)
        stand, snap = self._approach(snap, target, PLACE_RANGE, 1.0 + min(hx, hz) + 0.5, ignore={held.name},
                                     avoid=_Box(target, size))
        if stand is None:
            return Result(False, "put_down", self._out_of_reach(
                snap, target, f"({x:.1f}, {z:.1f})", f"no clear spot to reach ({x:.1f}, {z:.1f}) from {self._here(snap)}"))
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
        if not self._lifting:  # set back after stepping out of a pen: not newly built
            self.placed.append(held.name)
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
        beam = not self._lifting and self._raised_beam(snap, target, size, upright)
        snapped = ""
        if beam:  # a log up off the ground: onto the supports its ends are aimed at, within a cell or a quarter turn
            target, turn, size, snapped = self._beam_on_supports(snap, held, target, turn, size)
        spot = _Box(target, size)
        body = (snap.me[0], snap.me[1], snap.me[2])
        stepped, floor = "", None
        if math.dist(body, target) > PLACE_RANGE - 0.3 or spot.footprint_contains(body[0], body[2], margin=1.3):
            stand, snap = self._approach(snap, target, PLACE_RANGE, 1.0 + min(size[0], size[2]) / 2 + 0.5,
                                         ignore={held.name}, avoid=spot)
            if stand is None and target[1] > self._level(snap) + BODY_HEIGHT:
                # Above the hands from this floor: step up onto something a block high beside it first, as a person
                # would (in run n8 a third layer laid from the ground failed about half the time).
                floor = (snap.me[0], snap.me[2], self._level(snap))  # to step back down to after
                stand, snap, stepped = self._step_up_to_reach(snap, target, spot, held.name)
            if stand is None:
                where = f"({target[0]:.1f}, {target[1]:.1f}, {target[2]:.1f})"
                return Result(False, "place_at", self._out_of_reach(
                    snap, target, where, f"cannot get within reach of {where} from {self._here(snap)}" + stepped))
            if hdist(snap.me, (stand[0], 0, stand[1])) > 0.3:
                snap = self._move(*stand, ignore={held.name})
            if math.dist(snap.me, target) > PLACE_RANGE - 0.05:  # stopped a little short, and high up the reach is short
                try:
                    snap = self._move_once(*stand, 0.2, ignore={held.name})
                except Stuck:
                    snap = self._observe()
        under = self._under_ends(snap, target, size) if beam else None  # to say why, if it does not stay up
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
        said = self._describe(snap, held.name) + _orientation(turn, upright) + snapped
        now = snap.entities.get(held.name)
        if beam and now is not None and (now.pos[1] < target[1] - 0.6 or "not resting" in said):
            said += (f"; it did not stay up there: {self._ends_text(under, target[1] - size[1] / 2)}. A beam stays up "
                     "only with both ends on something of the same height")
        if stepped:  # and back down again, as a person would: the mind never asked to stand up there
            down = self._hop_down(snap, floor[0], floor[1], self._level(snap), floor[2], walk_on=False)
            said += stepped + (", and stepped back down" if down.ok else f"; {down.summary}")
        if not self._lifting:
            self.placed.append(held.name)
        return Result(True, "place_at", said, {"object": held.name})

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
        moving = object.startswith("Fish_")  # a fish swims on: aim where it is now, and again if it slips out of reach
        reach = STRIKE_RANGE + (SPEAR_THRUST if moving and held.name.startswith("Spear_") else 0)
        for _ in range(4 if moving else 1):
            snap = self._observe()
            target = snap.entities.get(object)
            if target is None:
                return Result(False, "strike", f"{object} is gone")
            # Aim at the nearest point of its surface, at body height, and stand within reach of it.
            level = self._level(snap)
            aim = tuple(min(max(c, p - s / 2), p + s / 2) for c, p, s in
                        zip((snap.me[0], level + BODY_CENTRE_Y, snap.me[2]), target.pos, target.size))
            if math.dist((snap.me[0], level + BODY_CENTRE_Y, snap.me[2]), aim) > reach - 0.5:
                stand, snap = self._approach(snap, aim, reach, 2.2, ignore={held.name})
                if stand is None and reach > STRIKE_RANGE:  # out on the water: from the sand, a spear's length further off
                    stand, snap = self._approach(snap, aim, reach, 2.2 + SPEAR_THRUST, ignore={held.name})
                if stand is None:
                    if moving:
                        return Result(False, "strike", f"{object} is too far out in the water to reach from the shore")
                    return Result(False, "strike", f"no clear spot to stand within reach of {object} from {self._here(snap)}")
                self._move(*stand, ignore={held.name})
            snap = self.world.act("Strike", {"name": object})
            outcome = snap.last_result or ""
            if not (moving and outcome == "StrikeFailed:OutOfRange"):
                break
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
        if kind == "StrikeCarving":
            done, needed = (int(n) for n in detail.split("/"))
            return Result(True, "strike", f"carved at {object} with {held.name} ({done} of {needed} strokes so far)",
                          {"strokes": done})
        if kind == "StrikeCarved":
            return Result(True, "strike", f"{object} is carved into {detail}, which lies at {where(detail)}", {"made": detail})
        if kind == "StrikeCaught":
            return Result(True, "strike", f"speared {object}; the catch, {detail}, lies on the sand at {where(detail)}",
                          {"made": detail})
        if kind == "StrikeMissed":
            return Result(False, "strike", f"missed {object}; it darted away")
        # A stick worked against a log (ADR-010): the wood heats with rubs in a row; only the world knows what catches.
        if kind == "StrikeRubWarm":
            return Result(True, "strike", f"rubbed {held.name} against {object}; the wood grows warm ({detail} rubs "
                                          f"in a row)", {"rubs": int(detail)})
        if kind == "StrikeRubHot":
            return Result(True, "strike", f"rubbed {held.name} against {object}; the wood is hot and smoking "
                                          f"({detail} rubs in a row), but no flame", {"rubs": int(detail)})
        if kind == "StrikeRubCaught":
            return Result(True, "strike", f"rubbed {held.name} against {object}, and a flame caught: {detail} burns "
                                          f"on {object}", {"made": detail})
        if kind == "StrikeRubBurning":
            return Result(True, "strike", f"{object} is already burning")
        if kind == "StrikeRubRain":
            return Result(False, "strike", f"rubbed at {object}, but in the rain the wood is wet through and nothing "
                                           f"warms")
        if kind == "StrikeRubDamp":
            return Result(False, "strike", f"rubbed at {object}, but the wood is still damp from the rain and will not "
                                           f"warm")
        if kind == "StrikeYardFull":
            return Result(False, "strike", f"struck {object}, but no stone can come off: every spot round its foot "
                                           f"already holds a loose stone; carry some away first")
        why = {"StrikeFailed:NoTool": "your hands hold no tool", "StrikeFailed:OutOfRange": f"{object} is out of reach",
               "StrikeFailed:TooSoon": "the last swing was too recent",
               "StrikeFailed:NoTarget": f"there is nothing called {object}"}.get(outcome, outcome or "nothing happened")
        return Result(False, "strike", f"strike failed: {why}")

    def skill_rub(self, object):
        """Rub what the hands hold against `object`, a rub at a swing's pace, until a flame catches, nothing more can
        come of it, or RUB_TRIES rubs have gone by (run n8 never thought of striking a log with a spear to rub it)."""
        snap = self._observe()
        target = snap.entities.get(object)
        if target is None:
            return Result(False, "rub", f"there is nothing called {object}")
        held = snap.held()
        if not held:
            return Result(False, "rub", "your hands are empty: there is nothing to rub with")
        if target.name.startswith("Log_") and not target.attrs.get("Burning"):
            husk, gap = self._tinder_near(snap, object)
            if husk is None or gap > TINDER_RANGE:  # in run hut5 it rubbed 30 times with the husk 5 away
                where = (f"the nearest coconut, {husk.name}, is {gap:.1f} away" if husk is not None
                         else "no coconut lies anywhere near")
                return Result(False, "rub", f"you did not start rubbing: no tinder lies within {TINDER_RANGE:.0f} of "
                                            f"{object} for a spark to catch ({where}); set a coconut right beside the "
                                            "log first")
        self.busy.add(held.name)
        level = self._level(snap)
        body = (snap.me[0], level + BODY_CENTRE_Y, snap.me[2])
        aim = tuple(min(max(c, p - s / 2), p + s / 2) for c, p, s in zip(body, target.pos, target.size))
        if math.dist(body, aim) > STRIKE_RANGE - 0.5:
            stand, snap = self._approach(snap, aim, STRIKE_RANGE, 2.2, ignore={held.name, object}, avoid=target)
            if stand is None:
                return Result(False, "rub", f"no clear spot to stand within reach of {object} from {self._here(snap)}")
            self._move(*stand, ignore={held.name, object})
        rubs, heat = 0, 0
        while rubs < RUB_TRIES:
            outcome = self.world.act("Rub", {"name": object}).last_result or ""
            kind, _, detail = outcome.partition(":")
            if kind == "RubFailed" and detail == "TooSoon":
                time.sleep(0.3)
                continue
            rubs += 1
            if kind in ("StrikeRubWarm", "StrikeRubHot"):
                heat = int(detail)
                time.sleep(0.85)
                continue
            if kind == "StrikeRubCaught":
                return Result(True, "rub", f"rubbed {held.name} against {object} {rubs} times, and a flame caught: "
                                           f"{detail} burns on {object}", {"made": detail})
            why = {"StrikeRubBurning": f"{object} is already burning",
                   "StrikeRubRain": "in the rain the wood is wet through and nothing warms",
                   "StrikeRubDamp": "the wood is still damp from the rain and will not warm",
                   "RubNothing": f"rubbing {held.name} against {object} does nothing",
                   "RubFailed:OutOfRange": f"{object} is out of reach",
                   "RubFailed:NoTarget": f"{object} cannot be rubbed"}.get(outcome, outcome or "nothing happened")
            return Result(kind == "StrikeRubBurning", "rub", why)
        if heat >= RUB_HOT:
            return Result(False, "rub", f"rubbed {held.name} against {object} {rubs} times in a row; the wood grew hot "
                                        f"and smoked, but {self._tinder_by(self._observe(), object)}", {"rubs": rubs})
        return Result(False, "rub", f"rubbed {held.name} against {object} {rubs} times; the wood grew warm, no more",
                      {"rubs": rubs})

    @staticmethod
    def _tinder_near(snap, log):
        """The coconut nearest the log, and how far it lies from the log's nearest point as the world measures it
        (main.lua rubLog, TINDER_RANGE); (None, None) with no coconut about or no such log."""
        wood = snap.entities.get(log)
        held = snap.held()
        husks = [e for e in snap.movables() if e.name.startswith("Coconut_") and e is not held]
        if wood is None or not husks:
            return None, None

        def gap(e):
            near = [min(max(c, p - s / 2), p + s / 2) for c, p, s in zip(e.pos, wood.pos, wood.size)]
            return math.dist(near, e.pos)
        husk = min(husks, key=gap)
        return husk, gap(husk)

    @classmethod
    def _tinder_by(cls, snap, log):
        """Why hot wood did not catch, as the body sees it: no tinder close enough (and where the nearest lies), or a
        husk beside it that only smoulders yet. In run hut5 the husk lay a few steps off by the yard, and "nothing
        beside it caught" read as bad luck: the mind never moved it."""
        husk, gap = cls._tinder_near(snap, log)
        if husk is None:
            return "no tinder lay beside it for a spark to catch: no coconut lies anywhere near"
        if gap <= TINDER_RANGE:
            return f"the dry husk of {husk.name} beside it only smoulders yet; rub on and it may catch"
        return (f"no tinder lay within {TINDER_RANGE:.0f} of {log} for a spark to catch: the nearest coconut, {husk.name}, "
                f"is {gap:.1f} away")

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
                return Result(False, "fasten", self._out_of_reach(
                    snap, piece.pos, object, f"no clear spot to reach {object} from {self._here(snap)}"))
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
                self._move(*spot, stop_within=0.7, ignore={object})
            except Stuck:  # bumping the ladder itself is close enough to climb it
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

    def skill_draw(self, x, z):
        """A foot dragged through the sand: the world leaves the line at once; the body walks along it."""
        x, z = float(x), float(z)
        snap = self._observe()
        start = (snap.me[0], snap.me[2])
        snap = self.world.act("Draw", {"to": [x, z]})
        outcome = snap.last_result or ""
        if not outcome.startswith("DrawSuccess:"):
            length = math.hypot(x - start[0], z - start[1])
            why = {"DrawFailed:NotSand": "the line would cross something that is not open sand (grass, rock, a tree, "
                                         "the sea); only the beach takes a line",
                   "DrawFailed:Length": f"a line runs from 0.5 to 20 long, and ({x:.1f}, {z:.1f}) is {length:.1f} away",
                   "DrawFailed:BeachFull": "the beach holds no more lines",
                   "DrawFailed:BadTarget": "that is not a place"}.get(outcome, outcome or "nothing happened")
            return Result(False, "draw", f"draw failed: {why}")
        mark = outcome.split(":", 1)[1]
        try:
            self._move_once(x, z, 0.6)  # open beach: straight along the line, as the foot drags
        except Stuck:
            pass  # the line is drawn either way
        return Result(True, "draw", f"drew a line in the sand from ({start[0]:.1f}, {start[1]:.1f}) to ({x:.1f}, {z:.1f})",
                      {"mark": mark})

    def skill_shake(self, object):
        snap = self._observe()
        palm = snap.entities.get(object)
        if palm is None or not object.startswith("Palm_") or palm.role != "Tree":
            return Result(False, "shake", f"there is no standing palm called {object}")
        level = self._level(snap)
        aim = tuple(min(max(c, p - s / 2), p + s / 2) for c, p, s in
                    zip((snap.me[0], level + BODY_CENTRE_Y, snap.me[2]), palm.pos, palm.size))
        if math.dist((snap.me[0], level + BODY_CENTRE_Y, snap.me[2]), aim) > STRIKE_RANGE - 0.5:
            stand, snap = self._approach(snap, aim, STRIKE_RANGE, 2.2)
            if stand is None:
                return Result(False, "shake", f"no clear spot to stand at {object} from {self._here(snap)}")
            self._move(*stand)
        snap = self.world.act("Shake", {"name": object})
        outcome = snap.last_result or ""
        snap = self._settle(1.6)  # the coconut drops
        if outcome.startswith("ShakeCoconut:"):
            name = outcome.split(":", 1)[1]
            nut = snap.entities.get(name)
            where = f"({nut.pos[0]:.1f}, {nut.pos[2]:.1f})" if nut else "at its foot"
            return Result(True, "shake", f"shook {object}; {name} fell and lies at {where}", {"made": name})
        if outcome == "ShakeNothing":
            return Result(False, "shake", f"shook {object}; it has no ripe coconut right now")
        why = {"ShakeFailed:NotAPalm": f"{object} is not a palm",
               "ShakeFailed:OutOfRange": f"{object} is out of reach"}.get(outcome, outcome or "nothing happened")
        return Result(False, "shake", f"shake failed: {why}")

    def skill_carve(self, object):
        snap = self._observe()
        if snap.entities.get(object) is None or not object.startswith("Log_"):
            return Result(False, "carve", f"there is no log called {object}")
        held = snap.held()
        if not held or not held.name.startswith("Axe_"):
            return Result(False, "carve", "carving needs the axe in your hands")
        stroke = None
        for _ in range(4):  # the world needs a few strokes
            stroke = self.skill_strike(object)
            if not stroke.ok or "made" in stroke.facts:
                break
        return Result(stroke.ok and "made" in stroke.facts, "carve", stroke.summary, stroke.facts)

    def skill_cook(self):
        held = self._observe().held()
        if not held:
            return Result(False, "cook", "your hands are empty")
        snap = self.world.act("Cook", {})
        outcome = snap.last_result or ""
        if outcome.startswith("CookSuccess:"):
            return Result(True, "cook", f"cooked {held.name} over the fire", {"cooked": held.name})
        why = {"CookFailed:NotFish": f"{held.name} is not a fish to cook", "CookFailed:Cooked": f"{held.name} is cooked already",
               "CookFailed:NoFire": "no fire burns beside you"}.get(outcome, outcome or "nothing happened")
        return Result(False, "cook", f"cook failed: {why}")

    def skill_eat(self):
        held = self._observe().held()
        if not held:
            return Result(False, "eat", "your hands are empty")
        snap = self.world.act("Eat", {})
        outcome = snap.last_result or ""
        if outcome.startswith("EatSuccess:"):
            return Result(True, "eat", f"ate {held.name}; you are now {outcome.split(':')[1]}% fed", {"ate": held.name})
        why = {"EatFailed:NotFood": f"{held.name} is not something you can eat",
               "EatFailed:EmptyHands": "your hands are empty"}.get(outcome, outcome or "nothing happened")
        return Result(False, "eat", f"eat failed: {why}")

    def skill_say(self, text):
        self.world.say(str(text))
        try:
            self.world.act("Talk", {})  # the body talks along (the renderer's Talk clip)
        except WorldError:
            pass  # an older world without Talk: the words are said all the same
        return Result(True, "say", "said it")

    def skill_wait(self, seconds):
        end = time.time() + max(1.0, min(30.0, float(seconds)))
        snap = None
        while time.time() < end:
            time.sleep(1.0)
            snap = self._observe()
            self.steady()
            self.glance()
        return Result(True, "wait", f"waited {seconds}s" + _weather_here(snap or self._observe()))
