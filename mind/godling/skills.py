"""L1 skills: deterministic motor programs. The mind picks skills; it never steers the body.

Every skill checks reach and clearance with the world's real constants, routes around loose
objects (walking through cubes scatters them), and verifies the outcome from a fresh observation.
"""
import heapq
import math
import time
from dataclasses import dataclass, field

from .house import OVER as ROOF_HIGHEST, SITE_ORDER, WALL_LINE, Site, cell_of, footprint, placement
from .house import _cells as cells_in
from .house import at as cell_at
from .speech import Voice
from .structures import PIECE_PREFIXES
from .structures import PIECE_PREFIXES as ROOF_KINDS  # building pieces: what a roof is made of (as the house check)
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
               "is taken away. Takes a few seconds; fastened pieces cannot be picked up. With something small in your "
               "hands, fasten binds it onto that object instead, if the two can be bound together."),
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
    "say": ({"text": "string"},
            "Say something aloud. The strangers who watch read it, but not your map: your body says it in plain words, "
            "leaving out places given as numbers and the numbers in names."),
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
LADDER_FOOT = 2.45  # out from a standing ladder's middle, the room its foot needs: climbing down, the world steps the
#                     body off 1.5 out and wants room for it there, 1.9 wide (main.lua climb, bodyFits)
LADDER_KEPT_CLEAR = "anything there closes the way up it. Set it a cell further off, or move the ladder first"
SITE_KEPT_CLEAR = "Your hands keep the site clear: a piece goes in a wall along its line, or off the site"
ON_THE_SITE = {  # where on the house's site (house.site_of) a piece would lie, in words
    "room": "in your house's room", "doorway": "in your house's doorway",
    "way out": "in the way out of your house's doorway",
    "wall": "in your house's wall, where only its own building pieces go",
    "strip": "beside your house's walls, on the ground a cell wide round them where you stand to build (only a "
             "block on its own, as a step, or a ladder goes there)"}
INTO = {"room": "in the room", "doorway": "in the doorway", "way out": "in the way out", "strip": "beside the walls"}
NEAR_RING = [(r, k) for r in (CUBE + 1.0, CUBE + 2.0, CUBE + 3.5, CUBE + 5.0) for k in range(8)]  # the reflex's spots
NEAR_TRIES = 16  # of those, how many it tries to set a piece down at
CARRY_CELLS = 12  # how far off (in cells) the body looks for clear floor to carry a piece to, with nowhere in reach
CARRY_TRIES = 12  # of the nearest spots there, how many it works out the way to
CARRY_GOES = 3  # and how many of those, nearest by the way there, it carries the piece to before it gives up
NEAR_SEARCH = 20000  # cells the way to somewhere near is searched over (a square some 70 across), not the whole island
PRESSING = 1.2  # from the body's axis to the edge of what presses on it: what snags it
SNAG_NEAR = 2.5  # with nothing pressing, the nearest thing this close is what it snagged on
RUB_TRIES = 30  # rubs one rub step keeps at, about half a minute (fire catches from the 12th, about the 20th on average)
RUB_HOT = 12  # main.lua RUB_HOT: from this many rubs in a row the wood is hot and smoking
TINDER_RANGE = 3.0  # main.lua TINDER_RANGE: tinder this close to the log catches from it
PEN_CELLS = 1600  # half-unit cells: floor the body can reach smaller than this (20 x 20 units) is a pen
LIFTABLE = SNAPPED_KINDS + ("Brick_", "Ladder_")  # what the body lifts aside to get out of a pen
GLANCE_IN_VIEW = 45  # degrees: something this close to straight ahead is already in view, no turn needed
GLANCE_HOLD = 0.4  # seconds the body keeps looking before it goes on
BRACE_LONGEST = 90  # seconds: a quake's rumble, shaking and fade take 33; the world lets go when it is over
LOOK_BEFORE_BRACE = 0.15  # the rumble reaches this strength 2 s in (main.lua); until then the body looks around
HEADROOM = BODY_HEIGHT + 0.1  # an underside lower than this over the floor is in the body's way, not over its head
# The shelter reflex (ADR-028): cold with nothing over it and its health below COLD_HEALTH, the body goes to the nearest
# roof it knows before it carries on. Once it has, it lets the mind take it out again (for food, say) until its health
# has fallen COLD_AGAIN further; the danger is over at WARM_AGAIN, or once it stands in the open, dry weather, not cold.
COLD_HEALTH = 35  # about 14 minutes from death by cold in the open (main.lua HARM.coldDrainSeconds)
COLD_AGAIN = 10
WARM_AGAIN = 50  # half: fed, it mends from here
COLD_DRAIN_SECONDS = 2400  # main.lua HARM.coldDrainSeconds: the cold takes a whole body's health in 40 minutes
SHELTER_REACH = 80.0  # how far it goes for a roof: under half a minute's walk in the rain
SHELTER_TRIES = 3  # roofs walked to in one go, when the one it reached keeps nothing off or it cannot get there
SHELTER_SETTLE = 1.2  # seconds for the world to say what is over the body (it looks twice a second, a house once)
SHELTER_REACHED = 1.0  # within this of the spot under a roof, the walk got there
SHELTER_RETRY = 60.0  # seconds before a roof it could not get to is tried again (the way to it may clear)
SHELTER_LOOK_AGAIN = 5.0  # seconds between searches once it has said it knows no roof
FELT_KEPT = 200  # spots where the body felt a roof over it, the latest kept
SHELTER_LETS = ("eat", "say")  # steps over at once that take the body nowhere: eating is what lets it mend


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


class _Around:
    """What lies round the spots the hands try to set a piece down at, looked up once for many spots (ADR-027 review):
    the floor the body stands on, rock and trunks and loose things (each in a BoxIndex, ADR-007, padded by the held
    piece's half length any way round), and the standing ladders. Within `reach` of `centre` (x, z)."""

    def __init__(self, skills, snap, held, centre, reach):
        def near(e, more=0.0):
            return (abs(e.pos[0] - centre[0]) <= reach + more + e.size[0] / 2
                    and abs(e.pos[2] - centre[1]) <= reach + more + e.size[2] / 2)
        pad = max(held.local_size) / 2 + 0.1
        self.level = skills._level(snap)
        self.ladders = [e for e in skills._standing_ladders(snap) if near(e, 2 * CUBE)]  # their foot reaches out
        self.rock = BoxIndex([(t.pos[0], t.pos[2], t.size[0] / 2 + pad, t.size[2] / 2 + pad, t)
                              for t in snap.terrain() if near(t)])
        self.things = BoxIndex([(e.pos[0], e.pos[2], e.size[0] / 2 + pad, e.size[2] / 2 + pad, e)
                                for e in skills._obstacles(snap, ignore={held.name}) if near(e)])


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
                 walk_speed=WALK_SPEED, kept_in=lambda piece: None, reserved=lambda: None, voice=None):
        self.world = world
        self.walk_speed = walk_speed  # must match the world's humanoid WalkSpeed (used for walk timeouts)
        self.protected = protected  # names of cubes the mind wants left alone
        self.kept_in = kept_in  # the name of the build a piece is built into (memory.built_into), or None
        self.reserved = reserved  # the site of the house being built (memory.reserved_cells, a house.Site), or None
        self.placed = []  # pieces set down since the mind last asked (take_placed), by any skill, learned ones too
        self.on_placed = lambda snap: None  # refresh ownership before the next step, including inside learned skills
        self._setting_aside = False  # freeing the hands is not building with the piece
        self.on_step = on_step  # attention hook: called with each snapshot, may raise Interrupted
        self.next_glance = lambda: None  # attention hook: an event worth a look, taken between steps
        self.log = log or (lambda **kw: None)
        self.voice = voice or Voice(world, log=self.log)  # what it says aloud, in plain words (ADR-031)
        self.offered = {**PRIMITIVES, **(GIFTED if gifted else {})}
        self.library = library  # skills the mind taught itself (learned.SkillLibrary)
        self.busy = set()  # objects the current skill is handling; attention ignores their movement
        self._depth = 0
        self._lifting = False  # in the middle of lifting a way out of a pen (no second one inside it)
        # Attention hook: what a reflex did. `pending`: news for the next plan; otherwise only kept for a death report,
        # when the step it stopped carries the words to the mind itself.
        self.on_reflex = lambda text, salience, pending=True: None
        self.felt = {}  # cell -> (x, z, in a house): where the body felt a roof over it (ADR-028)
        self._chill = None  # one spell of danger from the cold: where it took shelter, what failed it, what it said

    # ---- entry point -------------------------------------------------------------------
    def run(self, skill, args):
        # Inside a learned skill, the cold is checked before each of its own steps too.
        urgent = self.reflexes(skill, args) if self._depth == 0 else self.take_shelter(skill, args)
        if urgent:  # an urgent need breaks into the work: the step waits, and the mind plans from where it is
            self.log(kind="skill", skill=skill, args=args, ok=False, summary=f"interrupted: {urgent}", facts={},
                     seconds=0.0)
            return Result(False, skill, f"interrupted: {urgent}", {"sheltered": True})  # told apart (ADR-030)
        started = time.time()
        if self.library is not None and any(isinstance(v, dict) for v in args.values()):
            # Perception helpers ({"nearest_free": "cube"}, {"pos": ...}) work in any step, not only inside learned skills.
            try:
                args = self.library.resolve_helpers(args, self, skill)
            except Exception as err:
                return Result(False, skill, f"could not work out arguments ({err})")
        if self.library is not None and skill in self.library.skills:
            try:
                return self.library.execute(self, skill, args)
            except Stuck as why:
                return Result(False, skill, str(why))
            except Interrupted as why:  # cut short by attention: not the skill failing (ADR-032)
                return Result(False, skill, f"interrupted: {why}", {"interrupted": True})
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
        except Interrupted as why:  # cut short by attention: not the skill failing (ADR-032)
            result = Result(False, skill, f"interrupted: {why}", {"interrupted": True})
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

    def steady(self, snap=None):
        """Reflex: when the ground rumbles, crouch and hold on wherever the body stands, and stay braced until the
        ground is still (main.lua EARTHQUAKE). A braced body cannot be knocked down. The mind is not asked: it hears
        of the quake in its next plan. `snap` is an observation just made, if there is one. Returns the last
        observation (after the quake, if it braced), or None if the world could not be seen."""
        try:
            snap = snap or self.world.observe()
            if not snap.quake_phase or snap.bracing:
                return snap
            if snap.quake_phase == "rumble" and snap.quake < LOOK_BEFORE_BRACE:
                return snap  # startled, it looks around first (the world plays LookAround); the shaking is 8 s away
            started = time.time()
            braced = self.world.act("Brace").last_result == "Braced"
            self.log(kind="brace", ok=braced, phase=snap.quake_phase, tick=snap.tick,
                     **({"sky": "Earthquake", "sky_id": int(snap.quake_id)} if snap.quake_id else {}))
            if not braced:
                return snap
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
            return snap
        except WorldError as err:
            self.log(kind="error", message=f"brace: {err}")
            return None

    def reflexes(self, skill=None, args=None, snap=None, carried=True):
        """The body's reflexes, on one look at the world, between steps, while it waits and while the mind thinks:
        braced through a quake (steady), under a roof when the cold is killing it (take_shelter), and a glance at what
        attention noticed. Returns what the shelter reflex said when it moved the body, which stops the step in
        progress (or the plan being thought); else None. `carried`: the caller hands those words on to the mind."""
        snap = self.steady(snap)
        urgent = self.take_shelter(skill, args, snap=snap, carried=carried)
        if not urgent:
            self.glance()
        return urgent

    def sheltering(self):
        """Whether the body took shelter by itself from a danger of the cold that is not over yet (ADR-028): no
        stop-gap takes it out again meanwhile (ADR-030). The mind's own plans may, as before."""
        return self._chill is not None and self._chill.get("took") is not None

    @staticmethod
    def cold_danger(snap):
        """Whether the cold is killing the body (ADR-028): alive and cold with nothing over it, its health below
        COLD_HEALTH, not drowning and not in a quake (bracing comes first). A fire beside it in dry weather halves the
        cold as a roof would, so there it is not in danger enough to leave the fire."""
        return (snap.has_world and snap.health is not None and not snap.dead and snap.cold
                and not (snap.in_house or snap.sheltered) and snap.health < COLD_HEALTH and not snap.drowning
                and not snap.quake_phase and not (snap.by_fire and not snap.in_rain))

    @staticmethod
    def cold_under_a_roof(snap):
        """Whether the cold is killing the body under a roof that is no house (at night a roof only halves it)."""
        return (snap.has_world and snap.health is not None and not snap.dead and snap.cold and bool(snap.sheltered)
                and not snap.in_house and snap.health < COLD_HEALTH and not snap.drowning and not snap.quake_phase)

    def take_shelter(self, skill=None, args=None, snap=None, carried=True):
        """Reflex (ADR-028), like bracing: when the cold is killing it (cold_danger), the body goes to the nearest roof
        it knows before it carries on with `skill`: one it felt over it before or one it sees, which the world must
        then find keeps the rain off; a house it has stood in comes before any plain roof. Cold under a roof that is no
        house, it walks on into a house it knows, if it knows one in reach. As in survival games (in RimWorld a freezing
        pawn goes to a warm room by itself), an urgent need breaks into the work; what to do next stays the mind's.
        Returns what it did, in words for the
        mind, when it moved the body; None when the step goes on (it may still have news for the mind: that it knows
        no roof, said once). Let go: a walk to a roof (the mind is already taking it there), a learned skill (its steps
        are checked one by one), and a step that takes it nowhere and is over at once (SHELTER_LETS).
        `snap` is an observation just made, if there is one; `carried`: the caller hands the words to the mind (as a
        step's result), so attention keeps them only for a death report."""
        if self.library is not None and skill in self.library.skills:
            return None  # its own steps are checked one by one (run), and a walk home among them is let go
        try:
            snap = snap or self.world.observe()
        except WorldError as err:
            self.log(kind="error", message=f"shelter: {err}")
            return None
        self._feel(snap)
        if snap.health is None or snap.dead or not snap.has_world:
            return None
        covered = snap.in_house or bool(snap.sheltered)
        bout = self._chill
        if snap.health >= WARM_AGAIN or not (covered or snap.cold or snap.in_rain):
            self._chill = None  # the danger is over (not merely dried under the roof): the next one is a new one
            return None
        if bout is not None and bout["at"] is not None and not covered and hdist(snap.me, bout["at"]) <= 1.0:
            bout["took"] = bout["at"] = None  # the roof it sheltered under left it, not the mind: not at fault
        indoors = self.cold_under_a_roof(snap)  # under a roof already: only a house is worth going on to
        if not (self.cold_danger(snap) or indoors) or skill in SHELTER_LETS:
            return None
        bout = self._chill = bout or {"took": None, "at": None, "tried": set(), "unreached": {}, "said": False,
                                      "looked": None}
        left_there = bout["at"] is not None and hdist(snap.me, bout["at"]) <= 1.0  # where the reflex took it
        if bout["took"] is not None and snap.health > bout["took"] - COLD_AGAIN and not (indoors and left_there):
            return None  # it took shelter, and the mind has taken it out again: not until it is worse
        if skill == "walk_to" and self._walks_under_a_roof(snap, args, bout):
            return None
        if not indoors and bout["said"] and time.time() - bout["looked"] < SHELTER_LOOK_AGAIN:
            return None  # it has said it knows no roof: it looks again now and then, for one built meanwhile
        try:
            spots = self._shelters(snap, bout, houses_only=indoors)
            if indoors and not spots:
                return None  # no house it knows in reach: under this roof it stays, and nothing is said
            return self._seek_shelter(snap, bout, carried, spots, indoors)
        except WorldError as err:
            self.log(kind="error", message=f"shelter: {err}")
        except Exception as err:  # a body bug in the walk must never take the step down (as in run)
            self.log(kind="error", message=f"shelter crashed: {err!r}")
        return None

    def _walks_under_a_roof(self, snap, args, bout):
        """Whether a walk_to step goes under a roof the body has not found the rain reaching it under."""
        if not isinstance(args, dict):
            return False
        try:
            if self.library is not None and any(isinstance(v, dict) for v in args.values()):
                args = self.library.resolve_helpers(args, self)
            roof = self._roof_over(snap, float(args["x"]), float(args["z"]))
        except Exception:  # noqa: BLE001 (arguments the step itself will refuse)
            return False
        return roof is not None and roof not in bout["tried"]

    def _seek_shelter(self, snap, bout, carried, spots, indoors=False):
        """Walk to the spots (`_shelters`) in turn until the world says the body is sheltered (or, `indoors`, in a
        house), and say what came of it."""
        bout["looked"] = time.time()
        health, start = snap.health, (snap.me[0], snap.me[2])
        at = f"({start[0]:.1f}, {start[1]:.1f})"
        opening = (f"cold under a roof that keeps only half the cold off, your health down to {health:.0f} of 100, at "
                   f"{at}" if indoors else
                   f"{'cold and soaked in the rain' if snap.in_rain else 'cold'}, your health down to {health:.0f} of "
                   f"100, with nothing over you at {at}")
        minutes = health / 100 * COLD_DRAIN_SECONDS / 60 * (2 if snap.by_fire else 1) * (2 if indoors else 1)
        rained, unreached, here = [], [], None
        for far, name, (x, z) in spots[:SHELTER_TRIES]:
            try:
                walked = self.skill_walk_to(x, z).summary
            except Stuck as why:
                walked = str(why)
            except Interrupted as why:
                text = (f"You were {opening}. Your body set off for the roof at ({x:.1f}, {z:.1f}), {far:.0f} units "
                        f"away, but stopped: {why}.")
                self._tell(text, carried, ok=False, health=health, to=[round(x, 1), round(z, 1)], tried=rained)
                return text
            here = self.world.observe()
            reached = hdist(here.me, (x, 0, z)) <= SHELTER_REACHED
            if reached and not (here.in_house or (here.sheltered and not indoors)):
                time.sleep(SHELTER_SETTLE)  # the world looks twice a second, for a house once a second
                here = self.world.observe()
            self._feel(here)
            if here.in_house or (here.sheltered and not indoors):
                bout["took"], bout["at"] = health, here.me
                where, how = ("into a house it knows", "in") if here.in_house else ("to the nearest roof it knows", "under")
                text = (f"You were {opening}: {'there' if indoors else 'out there'} the cold would take the rest of it "
                        f"in about {minutes:.0f} minutes. Your body went by itself {where}, {far:.0f} units away, and "
                        f"stands {how} it at "
                        f"({here.me[0]:.1f}, {here.me[2]:.1f}){_weather_here(here)}.{self._failed(rained, unreached)}")
                self._tell(text, carried, ok=True, health=health, to=[round(x, 1), round(z, 1)], tried=rained)
                return text
            if reached:  # the world keeps nothing off there (or no house is there now): not again while it lasts
                bout["tried"].add(name)
                rained.append(name)
            else:  # the way there may clear (a stray log in the doorway): tried again in a minute
                bout["unreached"][name] = time.time()
                unreached.append((name, walked))
        failed = self._failed(rained, unreached, indoors)
        if here is not None and hdist(here.me, (start[0], 0, start[1])) > SHELTER_REACHED:
            text = (f"You were {opening}. Your body went to find {'a house to be warm in' if indoors else 'a roof to shelter under'}"
                    f", and found none {'warm' if indoors else 'it could stand under'} within {SHELTER_REACH:.0f} units:"
                    f"{failed} {'There' if indoors else 'Out here'} the cold takes the rest of your health in about "
                    f"{minutes:.0f} minutes.")
            self._tell(text, carried, ok=False, health=health, to=None, tried=rained)
            return text  # it moved: the plan made for where it stood is stale
        if bout["said"]:
            return None
        bout["said"] = True
        text = (f"You are {opening}, and your body knows no roof within {SHELTER_REACH:.0f} units to shelter under: out "
                f"here the cold takes the rest of your health in about {minutes:.0f} minutes.{failed}")
        self._tell(text, False, ok=False, health=health, to=None, tried=rained)
        return None  # it did nothing: the step goes on, and the mind hears it as news

    @staticmethod
    def _failed(rained, unreached, indoors=False):
        """What the roofs it tried came to, in words: the mind may otherwise go back to one."""
        return ((f" Under {' and '.join(rained)} " + ("it was no warmer: no house is there now." if indoors
                                                       else "the rain still reached it.") if rained else "")
                + "".join(f" It could not get to {name}: {why}." for name, why in unreached))

    def _tell(self, text, carried, **facts):
        self.log(kind="reflex", reflex="shelter", text=text, **facts)
        self.on_reflex(text, 4, pending=not carried)

    def _feel(self, snap):
        """Where the body feels a roof over it, it knows a shelter; where it stands in the open, that there is none."""
        if not snap.has_world or snap.dead:
            return
        cell = cell_of((snap.me[0], snap.me[2]))
        self.felt.pop(cell, None)
        if snap.in_house or snap.sheltered:
            self.felt[cell] = (snap.me[0], snap.me[2], snap.in_house)
            if len(self.felt) > FELT_KEPT:
                self.felt.pop(next(iter(self.felt)))

    @staticmethod
    def _roof_over(snap, x, z):
        """The name of the piece over (x, z) that would keep the rain off a body standing there (main.lua shelterOf:
        something held overhead, within ten above the crown), with room under it to stand as walk_to reckons it
        (HEADROOM); or None. As the body sees it: the world has the last word."""
        floor = snap.ground_top(x, z)
        if floor is None:
            return None
        over = None
        for *_, top, e, terrain in snap._standable_index().at(x, z, strict=True):
            if terrain or not e.anchored or not e.name.startswith(ROOF_KINDS) or top <= floor + STEP:
                continue
            bottom = e.pos[1] - e.size[1] / 2
            if bottom < floor + HEADROOM:
                return None  # in the way: no room to stand there
            if bottom <= floor + ROOF_HIGHEST and (over is None or bottom < over[0]):
                over = (bottom, e.name)
        return over[1] if over else None

    def _shelters(self, snap, bout, houses_only=False):
        """The roofs the body knows within reach, but those the rain reached it under in this spell of danger and
        those it could not get to in the last minute: one spot under each, from where it felt a roof over it and the
        cells under pieces lying high over the ground. A house it has stood in comes first, nearest first, then the
        other roofs, nearest first: a house warms and mends, a plain roof at night only halves the cold (its own
        eaves are nearer than its room to a body coming from outside). `houses_only`: the houses alone.
        [(distance, roof, (x, z))]"""
        now = time.time()
        skip = bout["tried"] | {n for n, t in bout["unreached"].items() if now - t < SHELTER_RETRY}
        spots = [spot for spot in self.felt.values() if spot[2] or not houses_only]
        held = snap.held()
        for e in ([] if houses_only else snap.movables()):
            if (e is held or not e.anchored or not e.name.startswith(ROOF_KINDS)
                    or hdist(e.pos, snap.me) > SHELTER_REACH + max(e.size[0], e.size[2]) / 2
                    or e.pos[1] - e.size[1] / 2 < (snap.ground_top(e.pos[0], e.pos[2]) or 0.0) + HEADROOM):
                continue  # most pieces lie on the ground
            for ix in cells_in(e.pos[0] - e.size[0] / 2, e.pos[0] + e.size[0] / 2):
                for iz in cells_in(e.pos[2] - e.size[2] / 2, e.pos[2] + e.size[2] / 2):
                    spots.append((ix * CUBE, iz * CUBE, False))
        best = {}
        for x, z, in_house in spots:
            far = math.hypot(x - snap.me[0], z - snap.me[2])
            name = self._roof_over(snap, x, z) if far <= SHELTER_REACH else None
            if name is None or name in skip:
                continue
            rank = (not in_house, far)
            if name not in best or rank < best[name][0]:
                best[name] = (rank, far, (x, z))
        return [(far, name, xz) for name, (_, far, xz) in sorted(best.items(), key=lambda b: b[1][0])]

    def take_placed(self):
        """The pieces the body set down (place_at, put_down) since the last call, at any depth: inside a learned
        skill too, where most building happens (run hut1: every block went down through stack_block or haul_to)."""
        placed, self.placed = self.placed, []
        return placed

    # ---- helpers -----------------------------------------------------------------------
    def _observe(self):
        snap = self.world.observe()
        self._feel(snap)
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
                and not p.glowing and snap.ground_top(p.pos[0], p.pos[2]) is not None]

    def _obstacles(self, snap, ignore=()):
        held = snap.held()
        return [e for e in snap.movables() if e.name not in ignore and e is not held]

    def _in_the_way(self, snap, ignore=(), level=None):
        """Loose things that stick up from the floor we stand on (what we stand on, or what lies below it, is not),
        and things overhead lower than the body is tall: a beam across two-block posts leaves no room under it."""
        level = self._level(snap) if level is None else level
        return [e for e in self._obstacles(snap, ignore)
                if e.top > level + STEP and e.pos[1] - e.size[1] / 2 < level + HEADROOM]

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

    def _route(self, snap, start, goal, ignore=(), escaped=False, limit=120000, blocked=None):
        """Waypoints from start to goal (x, z), or None when no way round is known: A* over half-unit cells, then
        smoothed into straight legs. Half units, because a one-block doorway between grid cells is only just wider
        than the clearance the body keeps, and on whole units half the doorways fall between cells. `blocked`: a map
        of where the body cannot stand (_blocked_fn, with `ignore`), shared by several routes from one start."""
        blocked = blocked or self._blocked_fn(snap, ignore)

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
            out_to = 5.0 + 0.9  # the farthest step out, and the room kept round what it may run into
            hard = [(o.pos[0], o.pos[2], o.size[0] / 2 + 0.9, o.size[2] / 2 + 0.9)
                    for o in self._in_the_way(snap, ignore) + self._walls(snap)
                    if abs(o.pos[0] - start[0]) <= o.size[0] / 2 + out_to and abs(o.pos[2] - start[1]) <= o.size[2] / 2 + out_to]

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
                    rest = self._route(snap, escape, goal, ignore, escaped=True, limit=limit, blocked=blocked)
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
            if len(came) > limit:  # cells searched: past this, no way round is known
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

    def _move(self, x, z, stop_within=0.6, ignore=(), replans=1, around=()):
        """Walk to (x, z). `ignore`: what the walk may go through (the piece in the hands). `around`: what it goes up to
        (pick_up's target): the route goes round it when there is a way round it, and through it only when there is
        not; the body never steps away from it when it snags (ADR-027 review: a route through the piece it went to
        snagged on its corner)."""
        snap = self._observe()
        start = (snap.me[0], snap.me[2])
        route = self._route(snap, start, (x, z), ignore) if around else None
        through = set(ignore) | set(around)
        if route is None:
            route = self._route(snap, start, (x, z), through)
        if route is None and not self._lifting:
            pen = self._pen(snap, through)
            if pen is not None and self._lift_through(snap, (x, z), through, pen):
                snap = self._observe()
                route = self._route(snap, (snap.me[0], snap.me[2]), (x, z), through)
        leg = (x, z)
        try:
            for leg in route or [(x, z)]:  # no way round known: walk straight, and the stuck check reports it
                snap = self._move_once(*leg, stop_within if leg == (x, z) else 1.0, ignore=through)
        except Stuck as why:
            if not str(why).startswith("stuck"):
                raise
            if replans <= 0:
                if route is None:  # say what pens the body in, or closes off the goal, so the mind can clear a way
                    raise Stuck(f"{why}; {self._closed_by(self._observe(), through, (x, z))}") from None
                raise Stuck(f"{why}; {self._what_stopped(self._observe(), through, (x, z), leg)}") from None
            # Something moved or the body was pushed off its route: look again and find another way, once.
            self.log(kind="reflex", text=f"{why}; looking for another way")
            time.sleep(0.3)
            return self._move(x, z, stop_within, ignore, replans - 1, around)
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

    def _what_stopped(self, snap, ignore, goal, leg=None):
        """Why a walk with a way round stuck short of `leg` (the waypoint it walked to) on its way to `goal`, in words:
        what closes the way now, if nothing is left open, else what presses on the body where it stopped and what lies
        across the leg on from there, as the route keeps clear of them. What the walk goes up to is named as well: the
        body snags on it too. In the live run of 2026-11-08, 31 failures said only "stuck N short"."""
        me = (snap.me[0], snap.me[2])
        if self._route(snap, me, goal, ignore, limit=NEAR_SEARCH) is None:
            return self._closed_by(snap, ignore, goal)
        leg = goal if leg is None else leg
        far = math.dist(me, leg)
        on = [(me[0] + (leg[0] - me[0]) * d / far, me[1] + (leg[1] - me[1]) * d / far)
              for d in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0) if far and d <= far]
        pressing = sorted(self._pressing(snap), key=lambda e: self._gap(me, e))
        across = [e for e in self._in_the_way(snap)
                  if any(e.footprint_contains(x, z, margin=BODY_RADIUS + STAND_MARGIN) for x, z in on)]
        across += [w for w in self._walls(snap) if any(w.footprint_contains(x, z, margin=WALL_CLEARANCE) for x, z in on)]
        names = list(dict.fromkeys(e.name for e in pressing + sorted(across, key=lambda e: self._gap(me, e))))[:4]
        return f"snagged by {', '.join(names)}" if names else "nothing you can see stood in the way there"

    @staticmethod
    def _gap(me, e):
        """How far a point (x, z) is from the edge of `e`'s footprint (0 inside it)."""
        return math.hypot(max(abs(me[0] - e.pos[0]) - e.size[0] / 2, 0), max(abs(me[1] - e.pos[2]) - e.size[2] / 2, 0))

    def _pressing(self, snap, ignore=()):
        """What presses on the body where it stands, rock first and then loose things: whose edge is within PRESSING of
        its axis, or else the nearest within SNAG_NEAR. The unstick reflex steps away from them, and a walk that sticks
        names them, so the two name the same thing."""
        me = (snap.me[0], snap.me[2])
        near = self._walls(snap) + self._in_the_way(snap, ignore)
        nearest = min(near, key=lambda e: self._gap(me, e), default=None)
        return ([e for e in near if self._gap(me, e) <= PRESSING]
                or ([nearest] if nearest is not None and self._gap(me, nearest) <= SNAG_NEAR else []))

    @staticmethod
    def _shared(blocked):
        """A map of where the body cannot stand (_blocked_fn) that remembers what it was asked, for routes from one
        start to many goals."""
        known = {}

        def cached(x, z):
            key = (round(x, 3), round(z, 3))
            if key not in known:
                known[key] = blocked(x, z)
            return known[key]
        return cached

    @staticmethod
    def _pickup_radius(obj):
        """How close pick_up's stand point is to what it lifts: its narrow side sets how close the body may stand."""
        return 1.6 + min(obj.size[0], obj.size[2]) / 2

    def _walkable(self, snap):
        """Whether the body can walk from where it stands to a spot within reach of a piece, to lift it, going round
        it as round anything else: a test for nearest_free's candidates, which share one map of the floor."""
        me = (snap.me[0], snap.me[2])
        blocked = self._shared(self._blocked_fn(snap))

        def reachable(obj):
            stand = self._stand_point(snap, obj.pos, PICKUP_RANGE, self._pickup_radius(obj), ignore={obj.name},
                                      avoid=obj)
            return stand is not None and (math.dist(me, stand) < 0.6 or self._route(
                snap, me, stand, limit=NEAR_SEARCH, blocked=blocked) is not None)
        return reachable

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
                 and not e.attrs.get("Fastened") and not e.attrs.get("Burning") and not e.glowing
                 and abs(e.pos[1] - e.size[1] / 2 - level) < 0.3 and bare(e)]
        sides.sort(key=lambda e: (e.name in protected, hdist(e.pos, snap.me)))  # what it decided to keep, last
        for piece in sides[:6]:
            path = self._route(snap, (snap.me[0], snap.me[2]), goal, set(ignore) | {piece.name})
            out = self._past((snap.me[0], snap.me[2]), path, piece) if path else None
            if out is None:
                continue
            held = snap.held()
            # Lifting a way out is not setting aside, though it may happen on the way to set something aside: what it
            # lifts goes back where it was (ADR-027 review: the carry's walk out of a pen had the put-back refused).
            setting_aside, self._setting_aside = self._setting_aside, False
            self._lifting = True
            try:
                on_wall = None  # what it held, rested on the pen's wall while its hands lift the way out
                if held and (len(pen) < 40 or not self._set_down_nearby(snap, held, piece.pos, carry=False).ok):
                    way = self._along((snap.me[0], snap.me[2]), path, out)
                    on_wall = self._rest_on(snap, held, [e for e in sides if e is not piece], piece, way)
                    if on_wall is None:
                        return False
                if not self._lift(piece):
                    return False
                self._move(*out)
                turn = 90 if piece.size[2] > piece.size[0] + 0.1 else 0
                upright = piece.size[1] > max(piece.size[0], piece.size[2]) + 0.1
                back = self.skill_place_at(piece.pos[0], piece.pos[1], piece.pos[2], turn, upright)
                if not back.ok:  # it stays out of its place, but not in the hands: set aside, or carried off, so the
                    snap = self._observe()  # hands are free to take back what they rested on the wall (ADR-027 review)
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
                self._lifting, self._setting_aside = False, setting_aside
        return False

    def _lift(self, piece):
        """Pick up a piece the body stands beside, without first looking for room around it: in a pen there is none."""
        snap = self.world.act("Pickup", {"position": list(piece.pos)})
        if snap.last_result == "PickupSuccess":
            held = self._settle(LIFT_SECONDS + 0.2).held()
            if held and held.name == piece.name:
                return True
        return self.skill_pick_up(piece.name).ok

    def _rest_on(self, snap, held, walls, lifted=None, way=()):
        """Rest what the hands hold on top of one of `walls` (bare pieces beside the body), either way round. Its name,
        or None. First on one low enough for the hands to take it back from the ground outside: on a house's wall three
        blocks high it lies over the body's reach, and stays up there (ADR-027, the site of the live run at 07:49 on
        2026-11-09). But never at the body's height over the piece about to be `lifted`, or across the `way` out past
        it (points the body will walk through): there it closes the very gap the lift opens (ADR-027 review). With
        nowhere else, on the nearest, as before."""
        level = self._level(snap)

        def out_of_reach(wall):
            return wall.top + held.local_size[1] / 2 - (level + BODY_CENTRE_Y) > PICKUP_RANGE - 0.5

        def closes(wall, turn):
            if wall.top >= level + BODY_HEIGHT:
                return False  # over the body's head
            size = turned_size(held.local_size, turn, False)
            box = _Box((wall.pos[0], 0, wall.pos[2]), size)
            over = lifted is not None and (abs(wall.pos[0] - lifted.pos[0]) < (size[0] + lifted.size[0]) / 2
                                           and abs(wall.pos[2] - lifted.pos[2]) < (size[2] + lifted.size[2]) / 2)
            return over or any(box.footprint_contains(x, z, margin=BODY_RADIUS + STAND_MARGIN) for x, z in way)
        rests = [(wall, turn) for wall in sorted(walls, key=lambda e: (out_of_reach(e), hdist(e.pos, snap.me)))
                 for turn in (0, 90) if not closes(wall, turn)]
        for wall, turn in rests or [(wall, 0) for wall in sorted(walls, key=lambda e: hdist(e.pos, snap.me))]:
            top = (wall.pos[0], wall.top + held.local_size[1] / 2 + 0.02, wall.pos[2])
            if self.world.act("Place", {"position": list(top), "rotation": _rotation(turn, False)}).last_result == "PlaceSuccess":
                self._settle(PLACE_SECONDS + 0.4)
                return held.name
        return None

    @staticmethod
    def _along(start, path, until, step=0.5):
        """Points every `step` along `path` from `start`, up to `until` (a point on it)."""
        points, prev = [], start
        for wp in path:
            n = max(1, int(math.dist(prev, wp) / step))
            for i in range(1, n + 1):
                points.append((prev[0] + (wp[0] - prev[0]) * i / n, prev[1] + (wp[1] - prev[1]) * i / n))
                if math.dist(points[-1], until) < step:
                    return points
            prev = wp
        return points

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
            if snap.me[1] < 0.8:  # in the water: the island's edge is too high to climb back onto (main.lua THE SEA)
                self.world.act("Stop")
                raise Stuck("fell off the edge into the sea: you cannot climb back out, and the water is drowning you; "
                            "if it drowns you, you die, and come back to life at the start spot in the middle of the "
                            "island")
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
            return self._gap((me[0], me[2]), w)

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
        if gap(wall) > SNAG_NEAR:
            return False
        touching = self._pressing(snap, ignore)
        names = ", ".join(w.name for w in touching)
        pushes = [away(w) for w in touching]
        dx, dz = sum(p[0] for p in pushes), sum(p[1] for p in pushes)
        squeezed = math.hypot(dx, dz) < 0.3
        if squeezed:  # pushed equally from opposite sides: along the gap instead, either way
            dx, dz = -pushes[0][1], pushes[0][0]
        norm = math.hypot(dx, dz) or 1.0
        # Only onto our own floor, all the way and with the whole body: stepping straight away from Log_3 walked Godling
        # off the end of the west beach, where it hung on the sand's lip over the sea and then slipped in (live run,
        # 2026-11-05). If straight away is not floor, turn a little, then sideways along what snags it; never back into it.
        level = self._level(snap)

        def floor(x, z):
            ground = snap.surface(x, z, below=level + STEP)[0]
            return ground is not None and abs(ground - level) <= 0.3

        def safe(ux, uz):
            if any(ux * px + uz * pz < -0.01 for px, pz in pushes):  # into something that snags it
                return False
            return all(floor(me[0] + ux * d + ox, me[2] + uz * d + oz) for d in (0.5, 1.0, 1.5, 2.0, 2.5)
                       for ox, oz in ((0, 0), (BODY_RADIUS, 0), (-BODY_RADIUS, 0), (0, BODY_RADIUS), (0, -BODY_RADIUS)))
        for turn in (0, 45, -45, 90, -90) + ((180,) if squeezed else ()):
            c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
            ux, uz = (dx * c - dz * s) / norm, (dx * s + dz * c) / norm
            if safe(ux, uz):
                break
        else:
            self.log(kind="reflex", text=f"snagged by {names}; no floor to step away onto (the sea or a drop)")
            return False
        ex, ez = me[0] + ux * 2.5, me[2] + uz * 2.5
        self.log(kind="reflex", text=f"snagged by {names}; stepping away to ({ex:.1f}, {ez:.1f})")
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
        # Only out as far as the hands reach at the target's height: from up high (a roof) that is a few units, not all
        # of the reach (run hp-full2 hit 34 blocked walks and reaches, each a search like this one).
        rise = ty - (level + BODY_CENTRE_Y)
        n = int(math.sqrt(max((reach - 0.4) ** 2 - rise ** 2, 0)) / step)
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

    # ---- a standing ladder: the way up, kept clear (ADR-025) ----------------------------------------------------
    # A set-up ladder stands fixed, so the world lets a piece rest on its top, and the hands checked only that nothing
    # overlapped. On 2026-11-08 Godling set a stone on top of the ladder it was raising its walls with, and could not
    # build on there. A builder keeps a ladder's top and foot free, as games keep the spot an object is used from free
    # (RimWorld's interaction spot): the hands set nothing on a standing ladder or just over its top, nor at its foot
    # on the side it is climbed from, and say why. What it stands against may rise past its top: a wall goes higher,
    # and a roof is laid there.
    @staticmethod
    def _standing_ladders(snap):
        held = snap.held()
        return [e for e in snap.movables() if e.name.startswith("Ladder_") and e is not held and e.size[1] >= 5]

    @staticmethod
    def _ladder_feet(snap, ladder):
        """Where the body stands to climb a standing ladder, as boxes (x, z, half x, half z): out from its rungs on the
        low side, away from what it reaches the top of (main.lua climb). None for a ladder that reaches nothing: []."""
        fx, fz = ladder.facing
        bottom, top = ladder.pos[1] - ladder.size[1] / 2, ladder.top

        def highest(side, out):
            return snap.surface(ladder.pos[0] + fx * side * out, ladder.pos[2] + fz * side * out, below=top + 0.5)[0]
        feet = []
        for side in (1, -1):
            leans = any(t is not None and t >= bottom + 0.9 for t in (highest(-side, 1.5), highest(-side, 2.2)))
            floor = highest(side, 1.5)
            if leans and floor is not None and floor < bottom + 0.9:
                out, across = LADDER_FOOT / 2, max(ladder.size[0], ladder.size[2], 2 * BODY_RADIUS) / 2
                x, z = ladder.pos[0] + fx * side * out, ladder.pos[2] + fz * side * out
                feet.append((x, z, out, across) if abs(fx) >= abs(fz) else (x, z, across, out))
        return feet

    def _crowds_a_ladder(self, snap, centre, size, ladders=None):
        """Where a piece set at `centre`, its world-aligned box `size`, would close the way up a standing ladder, in
        words ("on top of Ladder_1"), or "". Things lower than a step, which the legs step over, do not. `ladders`: the
        standing ladders near, looked up once for many spots."""
        cx, cy, cz = centre
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        for ladder in self._standing_ladders(snap) if ladders is None else ladders:
            lx, lz = ladder.pos[0], ladder.pos[2]
            bottom, top = ladder.pos[1] - ladder.size[1] / 2, ladder.top
            if cy + hy <= bottom + STEP:
                continue
            if (abs(cx - lx) < hx + ladder.size[0] / 2 - 0.05 and abs(cz - lz) < hz + ladder.size[2] / 2 - 0.05
                    and cy - hy < top + CUBE - 0.05):  # on it, or over its top where the climber's head goes
                return f"on top of {ladder.name}" if cy - hy > top - 0.3 else f"where {ladder.name} stands"
            if cy - hy < bottom + BODY_HEIGHT and any(abs(cx - x) < hx + half_x - 0.05 and abs(cz - z) < hz + half_z - 0.05
                                                      for x, z, half_x, half_z in self._ladder_feet(snap, ladder)):
                return f"at the foot of {ladder.name}, where you stand to climb it"
        return ""

    def _ladder_under(self, snap, obj):
        """The standing ladder `obj` lies on top of, or None."""
        bottom = obj.pos[1] - obj.size[1] / 2
        return next((e for e in self._standing_ladders(snap) if e is not obj and abs(e.top - bottom) < 0.3
                     and abs(obj.pos[0] - e.pos[0]) < (obj.size[0] + e.size[0]) / 2 - 0.05
                     and abs(obj.pos[2] - e.pos[2]) < (obj.size[2] + e.size[2]) / 2 - 0.05), None)

    # ---- the house's site, kept clear (ADR-027) ------------------------------------------------------------------
    # In the live run of 2026-11-08 the hands-full reflex set 29 things down at the house's site, on its walls and the
    # ground round them, and in the last hour Godling could not build there. A builder keeps a site clear, as colony
    # games keep a blueprint's cells and the spot its builder stands on free, and haul off what lies there: the hands set
    # nothing down in the house's room, doorway or way out, nor on the ground a cell wide round its walls, and in a
    # wall's cells only a building piece that stays in the walls' line. They say why. The roof, laid over the walls and
    # out past them, is not the site's business, nor is a ladder set against a wall, nor a block set beside it as a
    # step. What the hands set aside to free themselves goes nowhere on the site at all.
    def _site(self):
        """The site of the house the mind is building (memory.reserved_cells, a house.Site), or an empty one."""
        site = self.reserved()
        if site is not None and not isinstance(site, dict):
            raise TypeError(f"the house's site is a house.Site of cells and what they are, not {type(site).__name__}")
        return site if isinstance(site, Site) else Site(site or {})

    def _on_the_site(self, snap, centre, size, held, aside=False):
        """Where on the house's site a piece set at `centre`, its world-aligned box `size`, would lie, in words ("in
        your house's room"), or "" where the hands may set it.
        - Set aside to free the hands (`aside`: the hands-full reflex and its carry), nowhere on the site, its walls and
          the way in to its doorway too, at any height: setting aside is not building (ADR-019; ADR-027 review: on top
          of the walls the reflex laid a log across the doorway, and the house took it for the lintel; in a wall's
          empty cells it laid logs and stones, and the house kept them as its own).
        - Set down on purpose while the house is built, nothing off the walls' line below the roof line
          (house.placement, the house's own check), and in a wall's cells only a building piece. Beside the walls, a
          ladder may stand, and a block on its own on the ground there, as a step to build from.
        - Set down on purpose once the house stands, anywhere: the house is the mind's to use."""
        site = self._site()
        if not site or not (aside or site.building):
            return ""
        if aside:  # the way in to the doorway is no place for it either, but the last resort (_set_down_nearby)
            on = [site[c] for c in footprint(centre, size, margin=1e-9) if site.get(c, "approach") != "approach"]
            return ON_THE_SITE[min(on, key=SITE_ORDER.index)] if on else ""
        cells = footprint(centre, size)
        room = sorted(c for c, kind in site.items() if kind == "room")
        floor = (snap.ground_top(room[0][0] * CUBE, room[0][1] * CUBE) if room else None) or 0.0  # as house.plan's
        bottom = centre[1] - size[1] / 2
        lies = placement(site, cells, bottom, floor)
        if lies is None:
            in_a_wall = bottom < floor + WALL_LINE and any(site.get(c) == "wall" for c in cells)
            return ON_THE_SITE["wall"] if in_a_wall and not held.name.startswith(PIECE_PREFIXES) else ""
        kind, where = lies
        if kind == "across":
            aimed = (round(centre[0] / CUBE), round(centre[2] / CUBE))
            into = " and ".join(f"{cell_at(c)} {INTO[site[c]]}" for c in sorted(cells) if site.get(c) in INTO)
            return (f"across your house's wall at {cell_at(aimed if aimed in where else where[0])}: {held.name} there "
                    f"would stick out of the walls' line" + (f", into {into}" if into else ""))
        if kind == "strip":
            if held.name.startswith("Ladder_"):
                return ""  # set against a wall, beside it: ADR-025 keeps its own top and foot clear
            ground = snap.ground_top(centre[0], centre[2])
            if (held.name.startswith(PIECE_PREFIXES) and all(abs(side - CUBE) <= 0.1 for side in size)
                    and ground is not None and bottom < ground + 0.3):
                return ""  # a block on its own on the ground beside the walls: a step to build from
        return ON_THE_SITE[kind]

    def _closes(self, snap, held, centre, size, aside=False, ladders=None):
        """What a piece set at `centre`, its world-aligned box `size`, would close that the hands keep clear, as the
        rest of a refusal ("is on top of Ladder_1: anything there closes the way up it. ..."), or "": the way up a
        standing ladder (ADR-025) and the house's site (ADR-027), one hook for every set-down. `aside`: set aside to free
        the hands. The reflex that lifts a piece out of a pen puts it back where it was, and is not asked."""
        if self._lifting and not aside:
            return ""
        if not held.name.startswith("Ladder_"):
            crowds = self._crowds_a_ladder(snap, centre, size, ladders)
            if crowds:
                return f"is {crowds}: {LADDER_KEPT_CLEAR}"
        on = self._on_the_site(snap, centre, size, held, aside)
        return f"is {on}. {SITE_KEPT_CLEAR}" if on else ""

    def _set_down_spot(self, snap, held, x, z, turn=0, upright=False, aside=False, around=None):
        """Where `held`, set down at (x, z) on the floor the body stands on, would lie, and why the hands could not set
        it there: the open sea, a trunk, rock beside it, something lying there, or what they keep clear (_closes).
        Nothing is sent to the world, so put_down asks it, and so do the hands-full reflex and its carry of every spot
        they try: one check for all three (ADR-027 review). `around`: what lies round the spots (_Around), looked up
        once for many. Returns (why, or "", (x, z, the centre it would have or None, its world-aligned size))."""
        ladder = held.name.startswith("Ladder_")  # the world stands a ladder up by itself
        if held.name.startswith(SNAPPED_KINDS):  # it will settle into the grid: plan for the cell it lands in
            x, z = grid(x), grid(z)  # first: at the sand's edge, the cell it lands in can be over the sea
        size = turned_size(held.local_size, turn, upright and not ladder)
        hx, hz = size[0] / 2, size[2] / 2
        nowhere = (x, z, None, size)
        ground = snap.ground_top(x, z)
        if ground is None:
            return f"({x:.1f}, {z:.1f}) is open sea; it would sink and be lost", nowhere
        around = around or _Around(self, snap, held, (x, z), max(held.local_size) / 2 + 0.1)
        floor = snap.surface(x, z, below=around.level + STEP)[0]  # the ground, or a floor we built at our own level
        floor = ground if floor is None else floor
        rock = [box[4] for box in around.rock.at(x, z)]
        covering = max((t for t in rock if t.footprint_contains(x, z)), key=lambda t: t.top, default=None)
        if covering is not None and covering.role == "Tree":
            return f"({x:.1f}, {z:.1f}) is inside the trunk of {covering.name}", nowhere
        if not ladder:  # a ladder is meant to stand against something
            for t in rock:  # a mesa wall or a trunk right beside the spot leaves no room for the object
                if t.top > floor + 0.3 and abs(x - t.pos[0]) < t.size[0] / 2 + hx and abs(z - t.pos[2]) < t.size[2] / 2 + hz:
                    return f"({x:.1f}, {z:.1f}) is too close to {t.name} to set anything down", nowhere
            for e in (box[4] for box in around.things.at(x, z)):  # boxes: side by side in neighbouring cells is fine
                if (abs(e.pos[0] - x) < hx + e.size[0] / 2 - 0.05 and abs(e.pos[2] - z) < hz + e.size[2] / 2 - 0.05
                        and e.top > floor + 0.05 and e.pos[1] - e.size[1] / 2 < floor + 3):
                    return f"({x:.1f}, {z:.1f}) is occupied by {e.name}", nowhere
        target = (x, floor + size[1] / 2 + (0.02 if ladder else 0.12), z)
        closes = self._closes(snap, held, target, size, aside, around.ladders)
        return (f"({x:.1f}, {z:.1f}) {closes}" if closes else ""), (x, z, target, size)

    @staticmethod
    def _left_hands(snap, held):
        """Words for a piece that left the hands on the way (a lift out of a pen rested it somewhere): where it lies,
        and what the hands hold instead."""
        now, lies = snap.held(), snap.entities.get(held.name)
        return (f"{held.name} left your hands on the way"
                + (f" and lies at ({lies.pos[0]:.1f}, {lies.pos[1]:.2f}, {lies.pos[2]:.1f})" if lies else "")
                + (f"; you hold {now.name}" if now else ""))

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
        # Up on something, to a spot as high across lower floor (from one step to another): walking straight there
        # walks off this one and stays on the ground beside that one. Down first, then up onto it.
        gap = self._gap_between(snap, (x, z), level) if level > 0.3 and floor is not None else None
        if gap is not None and self._route(snap, (snap.me[0], snap.me[2]), (x, z)) is None:
            down = self._hop_down(snap, x, z, level, gap, walk_on=False)
            if not down.ok:
                return down
            on = self.skill_walk_to(x, z)
            return Result(on.ok, "walk_to", f"{down.summary}, then {on.summary}")
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

    def _gap_between(self, snap, goal, level):
        """The floor lower than ours that the straight way from here to `goal` crosses, or None when the way stays on
        the floor we stand on (one platform, or pieces side by side)."""
        steps = max(1, int(hdist(snap.me, (goal[0], 0, goal[1])) / 0.5))
        for i in range(1, steps):
            px = snap.me[0] + (goal[0] - snap.me[0]) * i / steps
            pz = snap.me[2] + (goal[1] - snap.me[2]) * i / steps
            under = snap.surface(px, pz, below=level + STEP)[0]
            if under is None or under < level - 0.3:
                return under if under is not None else (snap.ground_top(px, pz) or 0.0)
        return None

    def _step_up(self, snap, x, z, top):
        """Walk to the foot of what stands one block higher at (x, z) and step up onto it, at the edge nearest us.
        A Result, or None when there is no edge to step onto from here (the caller then stops at its foot)."""
        level = self._level(snap)
        me = snap.me
        steps = max(1, int(hdist(me, (x, 0, z)) / 0.25))
        line = [(x + (me[0] - x) * i / steps, z + (me[2] - z) * i / steps) for i in range(steps + 1)]
        k = -1  # how far its top runs from (x, z) back towards us: other tops further on (a pile) are not its edge,
        # nor is top with something standing on it, where there is no room for the body (hp-roofcheck: a stone set
        # down on the near end of a row of blocks)
        while k + 1 < len(line) and abs((snap.surface(*line[k + 1], below=top + 0.3)[0] or -99) - top) < 0.3 \
                and (snap.surface(*line[k + 1])[0] or -99) < top + 0.3:
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
        if what is not None and what.movable and max(what.size[0], what.size[2]) <= CUBE + 0.1:
            # A piece one cell across, its foot on the way from here buried (hp-roofcheck: the way to the step ran along
            # a row of blocks beside it, and snagged on them twice over): come at it from a side with clear floor.
            out = what.size[0] / 2 + BODY_RADIUS + STAND_MARGIN + 0.1
            if foot is None or hdist((foot[0], 0, foot[1]), what.pos) > out + 0.5:
                sides = sorted(((what.pos[0] + dx * out, what.pos[2] + dz * out)
                                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))),
                               key=lambda p: hdist(me, (p[0], 0, p[1])))
                for p in sides:
                    if not blocked(*p) and (hdist(me, (p[0], 0, p[1])) < 0.6
                                            or self._route(snap, (me[0], me[2]), p) is not None):
                        foot, onto = p, (what.pos[0], what.pos[2])
                        break
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
            # On a top one cell across, the body (two wide) stands at its middle: the hands must reach from there
            # (hp-roofcheck: a block whose edge but not its middle reached the roof), and the whole body be clear of
            # what is being set, whose underside its head meets (hp-roofcheck: "taken by ... your own body").
            if max(e.size[0], e.size[2]) <= CUBE + 0.1:
                x, z = e.pos[0], e.pos[2]
                if hands(x, z, e.top) > PLACE_RANGE - 0.6 or spot.footprint_contains(x, z, margin=BODY_RADIUS + 0.15):
                    continue
            if abs((snap.surface(x, z)[0] or -99) - e.top) > 0.3:  # something else stands on it there
                continue
            steps.append((hdist(snap.me, (x, 0, z)), x, z, e))
        if not steps:
            return None, snap, ("; it is above your reach from there, and nothing one block high stands near it to "
                                "step up onto")
        why = ""
        for _, x, z, e in sorted(steps, key=lambda s: s[0])[:4]:
            for attempt in range(2):  # a step-up that snags is tried once more (hp-roofcheck: the next try went up)
                self.log(kind="reflex", text=f"({target[0]:.1f}, {target[1]:.1f}, {target[2]:.1f}) is above reach: "
                                             f"stepping up onto {e.name}" + (", again" if attempt else ""))
                walked = self.skill_walk_to(x, z)
                snap = self._observe()
                floor = self._level(snap)
                if abs(floor - e.top) < 0.4 and hdist(snap.me, (x, 0, z)) > 0.15:
                    try:  # landed off the middle of the step: to it, a short shuffle on the top
                        snap = self._move_once(x, z, 0.1)
                    except Stuck:
                        snap = self._observe()
                    floor = self._level(snap)
                if (abs(floor - e.top) < 0.4 and hands(snap.me[0], snap.me[2], floor) <= PLACE_RANGE - 0.1
                        and not spot.footprint_contains(snap.me[0], snap.me[2], margin=BODY_RADIUS + 0.05)):
                    return (snap.me[0], snap.me[2]), snap, f"; you stood on {e.name} to reach that high"
                why = (f"; it is above your reach from the ground, and stepping up onto {e.name} did not bring it in "
                       f"reach: {walked.summary}")
                if abs(floor - e.top) < 0.4:
                    break  # up on it, and still out of reach: no use trying again
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
        if obj.glowing:  # a meteor's stone, still glowing from its fall (main.lua sky.iron)
            return Result(False, "pick_up", f"{object} is still glowing hot from its fall: too hot to hold")
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
            snap = self._observe()
            now = snap.held()
            if freed.ok:
                note = f" (first {freed.facts['aside']}, to free your hands)"
            elif now is None:  # the hands came free on the way: a lift out of a pen rested it (ADR-027 review)
                note = f" ({self._left_hands(snap, held)})"
            else:
                return Result(False, "pick_up", f"hands are full: holding {now.name}, and {freed.summary}")
            obj = snap.entities.get(object)
            if obj is None:
                return Result(False, "pick_up", f"{object} vanished{note}")
        # Beside it: its narrow side sets how close we may stand; a long beam or ladder we stand beside, at its middle.
        stand, snap = self._approach(snap, obj.pos, PICKUP_RANGE, self._pickup_radius(obj), ignore={object}, avoid=obj)
        if stand is None:
            on = self._ladder_under(snap, obj)  # set there before the hands kept ladders clear (ADR-025)
            up = (f"it lies on top of {on.name}: pick up the ladder and it falls" if on else "it may be up on something")
            return Result(False, "pick_up", self._out_of_reach(
                snap, obj.pos, object, f"no clear spot to reach {object} from {self._here(snap)} ({up})") + note)
        self._move(*stand, around={object})
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
        if snap.last_result == "PickupFailed:TooHot":
            return Result(False, "pick_up", f"{object} is still glowing hot from its fall: too hot to hold{note}")
        return Result(False, "pick_up", f"pickup of {object} failed: {snap.last_result}{note}")

    def _set_down_nearby(self, snap, held, away_from, carry=True):
        """Reflex, as a person does: set what is in the hands on clear floor beside you before taking something else,
        and with nowhere clear in reach carry it further off, as a hauler in a colony game carries what lies on a
        blueprint off to clear ground (ADR-027: in the live run of 2026-11-08 Godling held Log_7 from 07:11 to 07:19,
        through 29 failures, with nowhere in reach to set it down).
        - First the near spots (NEAR_RING, 3.5 to 7.5 out), the farthest from what it goes to take first, on the floor
          the body stands on, which may be a platform it built (looking only at the ground there failed, test run t3).
          A long log may lie either way round.
        - Then, with `carry`, the cells within CARRY_CELLS (_carry_spots).
        Nowhere on the house's site, its walls and the way in to its doorway too, at any height (run hp-full2: three
        pieces it set down in the house stopped the house being finished; ADR-027), nor against what the mind keeps. A
        Result: ok, with facts["aside"] saying what it did ("set Log_2 down at (...)"), or not, saying why ("there is
        no clear floor near enough to set it down off your house's site")."""
        me = (snap.me[0], snap.me[2])
        protected = set(self.protected())
        kept = [e for name, e in snap.entities.items() if name in protected]
        turns = (0, 90) if max(held.local_size) > CUBE + 0.1 and not held.name.startswith("Ladder_") else (0,)
        around = _Around(self, snap, held, me, (CARRY_CELLS * CUBE if carry else NEAR_RING[-1][0]) + 2 * CUBE)
        kept_off, stuck = [], []
        site = self._site()

        def usable(x, z, turn):
            """None where it may not go; else 1 on the way in to the house's doorway, tried last of all (ADR-027
            review: carried from the room, logs were laid straight beyond the way out), else 0. It goes on our floor,
            off the site, clear of what is kept, where the hands would set it."""
            if held.name.startswith(SNAPPED_KINDS):
                x, z = grid(x), grid(z)
            top = snap.surface(x, z, below=around.level + STEP)[0]
            if top is None or abs(top - around.level) >= 0.3 or any(hdist((x, 0, z), e.pos) <= CUBE for e in kept):
                return None
            size = turned_size(held.local_size, turn, False)
            centre = (x, around.level + size[1] / 2, z)
            if self._on_the_site(snap, centre, size, held, aside=True):
                kept_off.append((x, z))
                return None
            if self._set_down_spot(snap, held, x, z, turn, aside=True, around=around)[0]:
                return None
            return int(any(site.get(c) == "approach" for c in footprint(centre, size, margin=1e-9)))

        def set_at(x, z, turn):
            setting_aside, self._setting_aside = self._setting_aside, True
            try:
                return self.skill_put_down(x, z, turn)
            except Stuck as why:
                if not str(why).startswith("stuck"):
                    raise  # in the sea, drowning: that is the news, not the hands (ADR-027 review)
                stuck.append(str(why))
                return Result(False, "put_down", str(why))
            finally:
                self._setting_aside = setting_aside

        def gone():  # what it held left the hands on the way (a lift out of a pen rested it): no use trying on
            now = self._observe()
            return None if now.held() is not None and now.held().name == held.name else \
                Result(False, "put_down", self._left_hands(now, held))
        ring = [(me[0] + r * math.cos(k * math.pi / 4), me[1] + r * math.sin(k * math.pi / 4)) for r, k in NEAR_RING]
        ring = sorted((p for p in ring if hdist((p[0], 0, p[1]), away_from) > CUBE + 0.5),
                      key=lambda p: -hdist((p[0], 0, p[1]), away_from))
        near = [(x, z, turn, usable(x, z, turn)) for x, z in ring for turn in turns]
        near = [(x, z, turn) for x, z, turn, _ in sorted((s for s in near if s[3] is not None), key=lambda s: s[3])]
        near = near[:NEAR_TRIES]

        def far():  # worked out only once nothing near will do
            return self._carry_spots(snap, held, away_from, turns, usable) if carry else []
        for spots, carried in ((lambda: near, False), (far, True)):
            for x, z, turn in spots():
                result = set_at(x, z, turn)
                if result.ok:
                    return self._aside(held, result, carried, bool(kept_off))
                left = gone()
                if left is not None:
                    return left
        why = "there is no clear floor near enough to set it down" + (" off your house's site" if kept_off else "")
        return Result(False, "put_down", why + (f" ({stuck[-1]})" if stuck else ""))

    def _carry_spots(self, snap, held, away_from, turns, usable):
        """Where the hands-full reflex carries a piece with nowhere clear in reach (_set_down_nearby): the cells within
        CARRY_CELLS the hands would set it at, the nearest CARRY_TRIES of them; of those, the ones the body can walk to,
        by the length of the walk there (one map of the floor for all the walks), and not where it would crowd what the
        hands go to take next. Penned in, with no way to any of them yet, the nearest: the walk lifts a way out first.
        [(x, z, turn)], at most CARRY_GOES."""
        me = (snap.me[0], snap.me[2])
        level = self._level(snap)
        ox, oz = round(me[0] / CUBE), round(me[1] / CUBE)
        cells = sorted((math.hypot(ix * CUBE - me[0], iz * CUBE - me[1]), ix * CUBE, iz * CUBE)
                       for ix in range(ox - CARRY_CELLS, ox + CARRY_CELLS + 1)
                       for iz in range(oz - CARRY_CELLS, oz + CARRY_CELLS + 1))
        spots = []  # (last resort, x, z, turn)
        for far, x, z in cells:
            if far > CARRY_CELLS * CUBE or len(spots) >= CARRY_TRIES:
                break
            if hdist((x, 0, z), away_from) > 2 * CUBE + 1.0:
                for turn in turns:
                    rank = usable(x, z, turn)
                    if rank is not None and len(spots) < CARRY_TRIES:
                        spots.append((rank, x, z, turn))
        blocked = self._shared(self._blocked_fn(snap, {held.name}))
        ways = []
        for rank, x, z, turn in spots:
            size = turned_size(held.local_size, turn, False)
            target = (x, level + size[1] / 2, z)
            stand = self._stand_point(snap, target, PLACE_RANGE, 1.0 + min(size[0], size[2]) / 2 + 0.5,
                                      ignore={held.name}, avoid=_Box(target, size))
            path = None if stand is None else ([stand] if math.dist(me, stand) < 0.6 else self._route(
                snap, me, stand, {held.name}, limit=NEAR_SEARCH, blocked=blocked))
            if path:
                ways.append((rank, sum(math.dist(a, b) for a, b in zip([me] + path, path)), x, z, turn))
        return ([way[2:] for way in sorted(ways)][:CARRY_GOES]
                or [spot[1:] for spot in sorted(spots, key=lambda spot: spot[0])][:CARRY_GOES])

    def _aside(self, held, result, carried, off_site):
        """The hands-full reflex's account of a set-down (put_down's `result`), in facts["aside"]: "set Log_2 down at
        (...)", or for the carry "carried Log_2 off your house's site and set it down at (...)", "off your house's site"
        only when the site turned spots away (ADR-027 review: far from the house it said so as well)."""
        at = result.facts.get("at")
        where = f"({at[0]:.1f}, {at[1]:.2f}, {at[2]:.1f})" if at else "nowhere (lost)"
        how = result.facts.get("how", "")
        aside = (f"carried {held.name} {'off your house' + chr(39) + 's site' if off_site else 'further off'} and set it "
                 f"down{how} at {where}" if carried else f"set {held.name} down{how} at {where}")
        said = aside if carried else result.summary
        self.log(kind="reflex", text=f"hands full{', and nowhere clear in reach' if carried else ''}: {said} to pick "
                                     "up something else")
        return Result(True, "put_down", aside, {**result.facts, "aside": aside})

    def skill_put_down(self, x, z, turn=0, upright=False):
        x, z, turn, upright = float(x), float(z), _quarter(turn), _flag(upright)
        snap = self._observe()
        held = snap.held()
        if not held:
            return Result(False, "put_down", "hands are empty")
        self.busy.add(held.name)
        why, (x, z, target, size) = self._set_down_spot(snap, held, x, z, turn, upright, aside=self._setting_aside)
        if why:
            return Result(False, "put_down", why)
        ladder = held.name.startswith("Ladder_")
        stand, snap = self._approach(snap, target, PLACE_RANGE, 1.0 + min(size[0], size[2]) / 2 + 0.5,
                                     ignore={held.name}, avoid=_Box(target, size))
        if stand is None:
            return Result(False, "put_down", self._out_of_reach(
                snap, target, f"({x:.1f}, {z:.1f})", f"no clear spot to reach ({x:.1f}, {z:.1f}) from {self._here(snap)}"))
        snap = self._move(*stand, ignore={held.name})
        if snap.held() is None or snap.held().name != held.name:  # a lift out of a pen on the way rested it elsewhere
            return Result(False, "put_down", self._left_hands(snap, held))
        snap = self.world.act("Place", {"position": list(target), "rotation": _rotation(turn, upright)})
        if snap.last_result != "PlaceSuccess":
            why = snap.last_result
            if why == "PlaceFailed:Occupied":
                why = f"that space is taken by {', '.join(self._overlapping(snap, target, size, ignore={held.name})) or 'something'}"
            return Result(False, "put_down", f"place failed: {why}")
        if not self._lifting and not self._setting_aside:
            self.placed.append(held.name)  # accepted by the world, even if settling is interrupted
        snap = self._settle(PLACE_SECONDS + 0.4)
        if not self._lifting and not self._setting_aside:
            self.on_placed(snap)
        landed = snap.entities.get(held.name)
        where = f"({landed.pos[0]:.1f}, {landed.pos[1]:.2f}, {landed.pos[2]:.1f})" if landed else "nowhere (lost)"
        how = " standing upright" if ladder else _orientation(turn, upright)
        return Result(True, "put_down", f"put {held.name} down{how} at {where}",
                      {"object": held.name, "at": list(landed.pos) if landed else None, "how": how})

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
        if not self._lifting and not self._setting_aside:
            self.placed.append(held.name)
        snap = self._settle(PLACE_SECONDS + 0.7)
        if not self._lifting and not self._setting_aside:
            self.on_placed(snap)
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
        closes = self._closes(snap, held, target, size, self._setting_aside)  # the lift puts back what it took
        if closes:
            where = f"({target[0]:.1f}, {target[1]:.1f}, {target[2]:.1f})"
            return Result(False, "place_at", f"{where} {closes}", {"object": held.name})
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
                if snap.held() is None or snap.held().name != held.name:  # a lift on the way rested it elsewhere
                    return Result(False, "place_at", self._left_hands(snap, held), {"object": held.name})
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
        if not self._lifting and not self._setting_aside:
            self.placed.append(held.name)  # accepted by the world, even if settling is interrupted
        snap = self._settle(PLACE_SECONDS + 0.7)
        if not self._lifting and not self._setting_aside:
            self.on_placed(snap)
        said = self._describe(snap, held.name) + _orientation(turn, upright) + snapped
        now = snap.entities.get(held.name)
        if beam and now is not None and (now.pos[1] < target[1] - 0.6 or "not resting" in said):
            said += (f"; it did not stay up there: {self._ends_text(under, target[1] - size[1] / 2)}. A beam stays up "
                     "only with both ends on something of the same height")
        if stepped:  # and back down again, as a person would: the mind never asked to stand up there
            down = self._hop_down(snap, floor[0], floor[1], self._level(snap), floor[2], walk_on=False)
            said += stepped + (", and stepped back down" if down.ok else f"; {down.summary}")
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
        if kind == "StrikeTooHot":
            return Result(False, "strike", f"struck {object}, but it is still glowing hot from its fall; the blow does "
                                           f"nothing to it yet")
        if kind == "StrikeChipping":
            done, needed = (int(n) for n in detail.split("/"))
            return Result(True, "strike", f"struck {object} with {held.name}; it rings like metal, and a sliver is "
                                          f"loosening ({done} of {needed} blows so far)", {"strikes": done})
        if kind == "StrikeChipped":
            return Result(True, "strike", f"struck {object}; a sliver of dark metal came off: {detail}, hard, with a "
                                          f"sharp edge, lies at {where(detail)}", {"made": detail})
        if kind == "StrikeSpent":
            return Result(False, "strike", f"struck {object}; nothing more comes off it: what is left is too thick "
                                           f"and round to loosen")
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
        if outcome.startswith("FastenEdge:"):  # a flake of iron and a tool (main.lua sky.iron.fit)
            _, tool, flake = outcome.split(":")
            return Result(True, "fasten", f"bound {flake} onto {tool}: the sliver of metal is {tool}'s edge now",
                          {"object": tool, "bound": flake})
        if outcome.startswith("FastenFailed:HasEdge:"):
            tool = outcome.split(":")[2]
            return Result(False, "fasten", f"{tool} already has an edge of metal bound on; there is no room for another")
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
        """Said in plain words, whoever chose them (ADR-031): run live spoke "bar at x -115 from z -49.5 to -30" and
        "Night 1245595". What a viewer cannot read is left out and the mind is told so; a line with nothing left is
        not said, and the mind is told why. Not said is no failed step: the project's building after it still runs
        (78-CDE2)."""
        said, why = self.voice.say(text)
        if not said:
            return Result(True, "say", f"not said: {why}", {"said": False})
        try:
            self.world.act("Talk", {})  # the body talks along (the renderer's Talk clip)
        except WorldError:
            pass  # an older world without Talk: the words are said all the same
        return Result(True, "say", f'said "{said}"' + (f"; {why}: the strangers who watch read words, not your map"
                                                       if why else ""))

    def skill_wait(self, seconds):
        end = time.time() + max(1.0, min(30.0, float(seconds)))
        snap = None
        while time.time() < end:
            time.sleep(1.0)
            snap = self._observe()
            urgent = self.reflexes(snap=snap)
            if urgent:
                return Result(False, "wait", f"interrupted: {urgent}")
        return Result(True, "wait", f"waited {seconds}s" + _weather_here(snap or self._observe()))
