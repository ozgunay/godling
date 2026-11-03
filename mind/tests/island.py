"""A small stand-in for Mesa Island, for the body's skills: no physics, a body that walks straight to where it was
sent at its pace (stepping down where the floor drops), and actions whose outcome a test sets.

Time is the island's own: the skills' clock and sleep are this island's, so a walk of a hundred units takes no time.
"""
import math

from godling.world import BODY_CENTRE_Y, HOLD_OFFSET_Y, Snapshot

DEFAULT_RESULTS = {"Pickup": "PickupSuccess", "Place": "PlaceSuccess", "Throw": "ThrowSuccess", "Brace": "Braced",
                   "StepUp": "StepUpStarted", "StepDown": "StepDownStarted"}


class FakeTime:
    def __init__(self, island):
        self.island = island

    def time(self):
        return self.island.now

    def sleep(self, seconds):
        self.island.sleep(seconds)


class Island:
    def __init__(self, entities=(), me=(0, BODY_CENTRE_Y, 0), clock=None, attrs=None, speed=16.0):
        self.ents = {e["name"]: e for e in entities}
        self.me = list(me)
        self.attrs = dict(attrs or {})
        self.clock = clock
        self.held = None
        self.goal = None
        self.speed = speed
        self.frozen = False  # the body goes nowhere: snagged
        self.solid_pieces = False  # loose pieces stop the body as rock does (a pen)
        self.now = 1000.0
        self.acts = []
        self.said = []
        self.results = {}  # action -> a result, a list of results (one per call, the last repeats) or fn(data)
        self.on_act = {}  # action -> fn(data): what else the world does
        self.after_sleep = None  # fn(island), called after every sleep
        self.fail_observe = 0  # observations that fail before they work again
        self.errors = {}  # action -> exception to raise

    # ---- what the client sees ---------------------------------------------------------
    def raw(self, result=""):
        ents = []
        for name, e in self.ents.items():
            if name == self.held:
                e = {**e, "position": [self.me[0], self.me[1] + HOLD_OFFSET_Y, self.me[2]]}
            ents.append(e)
        if self.clock is not None:
            ents.append({"id": 0, "name": "Clock", "position": [0, -50, 0], "size": [1, 1, 1],
                         "attributes": dict(self.clock)})
        attrs = {**self.attrs, "LastActionResult": result}
        return {"tick": int(self.now * 10), "player": {"position": list(self.me), "attributes": attrs},
                "other_players": [], "world": {"entities": ents}, "events": []}

    def snap(self, result=""):
        return Snapshot(self.raw(result))

    def observe(self):
        if self.fail_observe:
            from godling.world import WorldError
            self.fail_observe -= 1
            raise WorldError("observe failed")
        return self.snap()

    def say(self, text):
        self.said.append(text)

    def act(self, action, data=None):
        data = data or {}
        self.acts.append((action, data))
        if action in self.errors:
            raise self.errors[action]
        result = self.results.get(action, DEFAULT_RESULTS.get(action, ""))
        if isinstance(result, list):
            result = result.pop(0) if len(result) > 1 else result[0]
        if callable(result):
            result = result(data)
        handler = getattr(self, "_" + action, None)
        if handler:
            handler(data, result)
        if action in self.on_act:
            self.on_act[action](data)
        return self.snap(result)

    # ---- the world's side of each action ----------------------------------------------
    def _MoveTo(self, data, result):
        self.goal = (data["position"][0], data["position"][2])

    def _Stop(self, data, result):
        self.goal = None

    def _Pickup(self, data, result):
        if result != "PickupSuccess":
            return
        pos = data["position"]
        name = min((n for n in self.ents if n != self.held), default=None,
                   key=lambda n: math.dist(self.ents[n]["position"], pos))
        if name is not None:
            self.held = name

    def _Place(self, data, result):
        if result == "PlaceSuccess" and self.held:
            self.ents[self.held] = {**self.ents[self.held], "position": list(data["position"])}
            self.held = None

    def _Throw(self, data, result):
        if result == "ThrowSuccess" and self.held:
            d = data["direction"]
            self.ents[self.held] = {**self.ents[self.held], "position": [self.me[0] + d[0] * 3, 1.25, self.me[2] + d[2] * 3]}
            self.held = None

    def _StepUp(self, data, result):
        if result.startswith("StepUpStarted"):
            x, z = data["position"]
            self._put_body(x, z, up=True)

    def _StepDown(self, data, result):
        if result.startswith("StepDownStarted"):
            x, z = data["position"]
            self._put_body(x, z)

    def _Brace(self, data, result):
        if result == "Braced":
            self.attrs["Bracing"] = True

    # ---- the body's walk ---------------------------------------------------------------
    def floor_under(self, x, z, up=False):
        feet = self.me[1] - BODY_CENTRE_Y
        return self.snap().surface(x, z, below=feet + (3.0 if up else 0.5))[0]

    def _put_body(self, x, z, up=False):
        top = self.floor_under(x, z, up)
        self.me = [x, (top + BODY_CENTRE_Y) if top is not None else -2.0, z]

    def sleep(self, seconds):
        self.now += seconds
        if self.goal and not self.frozen:
            gx, gz = self.goal
            dx, dz = gx - self.me[0], gz - self.me[2]
            dist = math.hypot(dx, dz)
            step = min(dist, self.speed * seconds)
            nx, nz = self.me[0] + dx / dist * step, self.me[2] + dz / dist * step
            if dist > 1e-9 and not self._bumps(nx, nz):
                self._put_body(nx, nz)
            if step >= dist:
                self.goal = None
        if self.after_sleep:
            self.after_sleep(self)

    def _bumps(self, x, z, radius=0.6):
        """Rock stops the body, and loose pieces too if they are solid (not what it stands on or is already pressed
        into)."""
        snap = self.snap()
        feet = self.me[1] - BODY_CENTRE_Y
        held = snap.held()
        for e in snap.terrain() + (snap.movables() if self.solid_pieces else []):
            if e is held or e.top <= feet + 0.5 or e.pos[1] - e.size[1] / 2 > feet + 5:
                continue
            if e.footprint_contains(x, z, radius) and not e.footprint_contains(self.me[0], self.me[2], radius):
                return True
        return False

    def actions(self, name=None):
        return [a for a, _ in self.acts if name is None or a == name]
