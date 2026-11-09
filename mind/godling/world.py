"""HTTP client for a Clawblox world, and a compact reading of Mesa Island observations.

Physical constants come from the world's main.lua (Godling's copy in C:/Work/godling/world), so the mind
never has to guess them.
"""
import json
import math
import os
import time
import urllib.parse
import urllib.request

CUBE = 2.5  # a building block (main.lua BLOCK_SIZE, ADR-005: Minecraft scale; upstream 0.75)
GRID = CUBE  # placed blocks and logs settle into cells this wide (main.lua GRID)
SNAPPED_KINDS = ("Block_", "ImpactBlock_", "SupplyBlock_", "Stone_", "Meteor_", "Log_")


def grid(v):
    """The cell centre a placed block or log settles onto (main.lua: floor(v / GRID + 0.5) * GRID)."""
    return math.floor(v / GRID + 0.5) * GRID
PICKUP_RANGE = 6.0  # main.lua PICKUP_RANGE, measured from the body centre
PLACE_RANGE = 7.0  # main.lua PLACE_RANGE
HOLD_OFFSET_Y = 4.0  # held objects float this far above the body centre (main.lua HOLD_OFFSET)
BODY_CENTRE_Y = 2.55  # body centre when standing on flat ground (ground top is y=0)
WALK_SPEED = 16.0
LIFT_SECONDS = 1.0  # main.lua LIFT_SECONDS: a picked-up block rises into the hands
PLACE_SECONDS = 1.2  # main.lua PLACE_SECONDS: a placed block is lowered into place (upstream world: 0.3)
STRIKE_RANGE = 6.0  # main.lua STRIKE_RANGE: body centre to the target's nearest surface
SPEAR_THRUST = 2.5  # main.lua strike(): a spear's thrust at a fish reaches this much further
STRIKE_SECONDS = 1.0  # one swing (main.lua STRIKE_COOLDOWN is 0.8)
FASTEN_SECONDS = 2.5  # main.lua FASTEN_COOLDOWN
LADDER_HEIGHT = 3 * CUBE  # main.lua LADDER_SIZE.Y
TURN_RATE = 6.0  # main.lua TURN_RATE: radians per second when Face turns the body on the spot
SKY_PLAYER = "Sky"  # main.lua SKY_PLAYER: the guest panel's bodiless player, which is not someone on the island
SKY_MARKERS = ("SkyShadow", "SkyFlash", "SkyNote", "Blast", "Crater")  # seen, never touched; a crater is walked over
STEP = 0.45  # the highest step the legs take without a ladder
MOVABLE_KINDS = ("Block_", "ImpactBlock_", "SupplyBlock_", "Stone_", "Meteor_", "Brick_", "Log_", "Boulder_", "Ring_",
                 "Rock_", "Hammer_", "Axe_", "Ladder_", "Spear_", "Coconut_", "Catch_", "Volleyball", "Iron_")
GLOWS_ABOVE = 0.1  # main.lua sky.iron.GLOWS_ABOVE: a meteor's stone this hot (its Heat) glows, too hot to hold or work
TOOL_KINDS = ("Hammer_", "Axe_", "Spear_")
FOOD_KINDS = ("Coconut_", "Catch_")  # what can be eaten (main.lua FOOD)
BUILDING_KINDS = ("Log_", "Boulder_")  # building pieces besides blocks
# What "nearest_free" can look for: building pieces by kind (stones are cubes; bricks are long stones; a stone that
# fell from the sky is a stone too).
PIECE_KINDS = {"cube": lambda e: e.is_cube, "stone": lambda e: e.name.startswith(("Stone_", "Meteor_")),
               "log": lambda e: e.name.startswith("Log_"),
               "boulder": lambda e: e.name.startswith("Boulder_")}


class WorldError(RuntimeError):
    pass


CAUSES = {  # main.lua DEATH's DiedOf, in the mind's words
    "Hunger": "hunger", "Cold": "the cold", "HungerAndCold": "hunger and the cold together",
    "Lightning": "lightning", "Meteor": "a stone falling from the sky", "Storm": "lightning in a storm",
    "Sea": "drowning in the sea",
}


def death_cause(died_of):
    """What killed the body, in words (an unknown cause as the world named it)."""
    return CAUSES.get(died_of, str(died_of or "something").lower())


def hdist(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def world_size(size, rotation):
    """The axis-aligned size of a part turned by `rotation` (a 3x3 matrix); `size` itself if it is not turned."""
    if (isinstance(rotation, (list, tuple)) and len(rotation) == 3
            and all(isinstance(row, (list, tuple)) and len(row) == 3 for row in rotation)):
        return tuple(sum(abs(rotation[i][j]) * size[j] for j in range(3)) for i in range(3))
    return size


def turned_size(size, turn=0, upright=False):
    """The axis-aligned size of a piece placed with a quarter turn and/or stood on end (its length is along x)."""
    sx, sy, sz = size
    if upright:
        sx, sy = sy, sx
    if round(float(turn)) % 180 == 90:
        sx, sz = sz, sx
    return (sx, sy, sz)


class Entity:
    __slots__ = ("id", "name", "pos", "size", "local_size", "rot", "role", "attrs", "anchored")

    def __init__(self, raw):
        self.id = raw.get("id")
        self.name = raw.get("name", "?")
        self.pos = tuple(raw["position"])
        self.local_size = tuple(raw.get("size") or (0, 0, 0))
        self.rot = raw.get("rotation")
        self.size = world_size(self.local_size, self.rot)
        self.attrs = raw.get("attributes") or {}
        self.role = self.attrs.get("RenderRole", "")
        self.anchored = raw.get("anchored", True)  # older recordings omitted this field

    @property
    def aligned(self):
        """Whether its bounding box represents grid-aligned material, rather than a tilted piece."""
        if self.rot is None:
            return True
        return (isinstance(self.rot, (list, tuple)) and len(self.rot) == 3
                and all(isinstance(row, (list, tuple)) and len(row) == 3 for row in self.rot)
                and all(sum(abs(v) >= 0.99 for v in row) == 1
                        and all(abs(v) <= 0.01 or abs(v) >= 0.99 for v in row) for row in self.rot))

    @property
    def movable(self):
        return self.name.startswith(MOVABLE_KINDS)

    @property
    def is_cube(self):
        return all(abs(s - CUBE) < 0.05 for s in self.size)

    @property
    def glowing(self):
        """A meteor's stone still glowing from its fall (main.lua sky.meteor.cool, sky.iron): too hot to hold or work."""
        heat = self.attrs.get("Heat")
        return isinstance(heat, (int, float)) and heat > GLOWS_ABOVE

    @property
    def look(self):
        """What the eye tells of it beyond its name, in a few words, or "" (METEORIC IRON: what it is like, never what
        it is for)."""
        if self.name.startswith("Meteor_"):
            return "glowing hot" if self.glowing else "dark, heavy, metallic"
        if self.name.startswith("Iron_"):
            return "a sliver of dark metal, hard, sharp-edged"
        if self.attrs.get("Edge") == "Iron":
            return "with an edge of dark metal bound on"
        return ""

    @property
    def top(self):
        return self.pos[1] + self.size[1] / 2

    @property
    def facing(self):
        """The horizontal direction its thin side faces (its local z axis), e.g. a ladder's front; (0, 1) if unknown."""
        try:
            fx, fz = self.rot[0][2], self.rot[2][2]
        except (TypeError, IndexError):
            return (0.0, 1.0)
        norm = math.hypot(fx, fz)
        return (fx / norm, fz / norm) if norm > 0.1 else (0.0, 1.0)

    def footprint_contains(self, x, z, margin=0.0):
        return (abs(x - self.pos[0]) <= self.size[0] / 2 + margin
                and abs(z - self.pos[2]) <= self.size[2] / 2 + margin)


INDEX_CELL = 5.0  # bucket size for "what covers this point" lookups


class BoxIndex:
    """Footprint boxes (x, z, half x, half z, ...) bucketed on a coarse grid. The castaway island is hundreds of
    terrain parts, and routing asks what covers a point thousands of times per walk (ADR-007)."""

    def __init__(self, boxes):
        self.buckets = {}
        for box in boxes:
            cx, cz, hx, hz = box[:4]
            for i in range(math.floor((cx - hx) / INDEX_CELL), math.floor((cx + hx) / INDEX_CELL) + 1):
                for k in range(math.floor((cz - hz) / INDEX_CELL), math.floor((cz + hz) / INDEX_CELL) + 1):
                    self.buckets.setdefault((i, k), []).append(box)

    def at(self, x, z, strict=False):
        """The boxes whose footprint contains (x, z); `strict` leaves out those it only touches."""
        bucket = self.buckets.get((math.floor(x / INDEX_CELL), math.floor(z / INDEX_CELL)), ())
        if strict:
            return [b for b in bucket if abs(x - b[0]) < b[2] and abs(z - b[1]) < b[3]]
        return [b for b in bucket if abs(x - b[0]) <= b[2] and abs(z - b[1]) <= b[3]]


class Feature:
    """Terrain parts that make one landmark, such as the Peak's terraces, taken together."""

    def __init__(self, name, parts):
        lo = [min(p.pos[k] - p.size[k] / 2 for p in parts) for k in range(3)]
        hi = [max(p.pos[k] + p.size[k] / 2 for p in parts) for k in range(3)]
        self.name = name
        self.parts = parts
        self.size = tuple(hi[k] - lo[k] for k in range(3))
        self.pos = tuple((hi[k] + lo[k]) / 2 for k in range(3))
        self.top = hi[1]
        self.role = parts[0].role

    def footprint_contains(self, x, z, margin=0.0):
        return any(p.footprint_contains(x, z, margin) for p in self.parts)


class Snapshot:
    """One observation, with the lookups the skills and the mind need."""

    def __init__(self, raw):
        self.raw = raw
        self.tick = raw.get("tick", 0)
        player = raw.get("player") or {}
        self.me = tuple(player.get("position") or (0, 0, 0))
        attrs = player.get("attributes") or {}
        self.last_result = attrs.get("LastActionResult", "")
        self.hunger = attrs.get("Hunger")  # 100 full, 0 starving (main.lua SURVIVAL)
        self.health = attrs.get("Health")
        # Death (main.lua DEATH): it lies dead for a while, then is born again at the start spot. DiedOf names the cause.
        self.dead, self.deaths = bool(attrs.get("Dead")), attrs.get("Deaths") or 0
        self.died_of, self.dead_for = attrs.get("DiedOf") or "", attrs.get("DeadFor") or 0
        at = str(attrs.get("DiedAt") or "").split(",")
        self.died_at = (float(at[0]), float(at[1])) if len(at) == 2 else None
        self.hurts, self.hurt_by = attrs.get("Hurts") or 0, attrs.get("Hurt")  # what the sky did to the body last
        self.freed = attrs.get("Freed") or 0  # times the world moved the body out from inside a piece
        # The sea (main.lua THE SEA): in the water and drowning now; times it drowned (and woke at the start spot); times
        # the world put it back on the sand after it hung on the beach's edge.
        self.drowning = bool(attrs.get("Drowning"))
        self.drowned, self.ashore = attrs.get("Drowned") or 0, attrs.get("Ashore") or 0
        # Weather on the body (main.lua WEATHER): soaked 0-100, cold, out in the rain, and what shelters it.
        self.wet, self.cold, self.in_rain = attrs.get("Wet") or 0, bool(attrs.get("Cold")), bool(attrs.get("InRain"))
        self.sheltered = attrs.get("Sheltered") or ""  # what is over and round it: "", "roof" or "enclosed"
        self.in_house = bool(attrs.get("InHouse"))  # it stands inside a finished house (main.lua houseAt, ADR-019)
        # That house's room to stand in, in cells, and how many times as fast a fed body mends there (ADR-033).
        self.house_room, self.house_mends = attrs.get("HouseRoom") or 0, attrs.get("HouseMends") or 0
        self.by_fire = bool(attrs.get("ByFire"))
        self.walk_speed = attrs.get("WalkSpeed")  # the pace now: a heavy load and the rain slow it
        fx, fz = attrs.get("ViewForwardX"), attrs.get("ViewForwardZ")  # which way the body faces
        self.facing = (fx, fz) if isinstance(fx, (int, float)) and isinstance(fz, (int, float)) else None
        self.others = [(p.get("name", "?"), tuple(p.get("position", (0, 0, 0))))
                       for p in raw.get("other_players") or [] if p.get("name") != SKY_PLAYER]
        ents = ((raw.get("world") or {}).get("entities")) or []
        self.entities = {e.name: e for e in (Entity(r) for r in ents)}
        self.events = raw.get("events") or []
        self._terrain = self._landmarks = self._index = None  # worked out once per snapshot, on first use
        clock = self.entities.get("Clock")
        self.time_of_day = clock.attrs.get("TimeOfDay") if clock else None  # hours, 0-24 (main.lua day and night)
        self.rain = (clock.attrs.get("Rain") or 0) if clock else 0  # 0 dry .. 1 pouring
        self.fog = (clock.attrs.get("Fog") or 0) if clock else 0  # 0 clear .. 1 thick (ADR-010)
        self.wind = math.hypot(clock.attrs.get("WindX") or 0, clock.attrs.get("WindZ") or 0) if clock else 0  # 0 .. 1 gale
        # An earthquake (main.lua EARTHQUAKE): its strength 0-1, its phase ("rumble", "shaking", "fade" or "" when the
        # ground is still), its number, and how many pieces the last one brought down.
        self.quake = (clock.attrs.get("Quake") or 0) if clock else 0
        self.quake_phase = (clock.attrs.get("QuakePhase") or "") if clock else ""
        self.quake_id = clock.attrs.get("QuakeId") if clock else None
        self.quake_fell = (clock.attrs.get("QuakeFell") or 0) if clock else 0
        # The latest note from someone watching (main.lua sky.notes): its number, its text and where its glider landed.
        self.note_id = clock.attrs.get("NoteId") if clock else None
        self.note_text = " ".join(str(clock.attrs.get("NoteText") or "").replace('"', "'").split()) if clock else ""
        self.note_at = (clock.attrs.get("NoteX") or 0, 0, clock.attrs.get("NoteZ") or 0) if clock else (0, 0, 0)
        # The latest meteor's blast (main.lua sky.meteor): its number, where, and what it did.
        a = clock.attrs if clock else {}
        self.meteor_id = a.get("MeteorId")
        self.meteor_at = (a.get("MeteorX") or 0, 0, a.get("MeteorZ") or 0)
        self.meteor_did = {k: int(a.get("Meteor" + k) or 0) for k in ("Smashed", "Thrown", "Unfastened", "Felled", "Hurt")}
        self.bracing, self.knocked_down = bool(attrs.get("Bracing")), bool(attrs.get("KnockedDown"))
        # A storm called down (main.lua THE STORM): its phase ("warning", "storm", or "" when there is none), its
        # number, and the spots where the air crackles; on the body, how often a strike hit it and how long it stays
        # charred.
        self.storm_phase, self.storm_id = str(a.get("StormPhase") or ""), a.get("StormId")
        self.storm_spots = []
        for spot in str(a.get("StormSpots") or "").split(";"):
            xz = spot.split(",")
            if len(xz) == 2:
                try:
                    self.storm_spots.append((float(xz[0]), float(xz[1])))
                except ValueError:
                    pass
        self.struck, self.scorched = attrs.get("Struck") or 0, attrs.get("Scorched") or 0
        self._held, self._held_known = None, False

    @property
    def has_world(self):
        return bool(self.entities)

    def movables(self):
        return [e for e in self.entities.values() if e.movable]

    def cubes(self):
        return [e for e in self.movables() if e.is_cube]

    def terrain(self):
        """Fixed ground the body stands on or must go around. A tree counts as terrain far too high to climb, so
        routes keep clear of its trunk the way they keep clear of a mesa's walls; so does a stump, half a block high."""
        if self._terrain is None:
            self._terrain = [e for e in self.entities.values()
                             if e.role in ("Mesa", "Ground", "Tree", "Quarry", "Stump", "Wreck")]
        return self._terrain

    def landmarks(self):
        """What the island has to see and go to. Terrain parts of one feature (the Peak's terraces) count as one."""
        if self._landmarks is None:
            single, groups = [], {}
            for e in self.entities.values():
                if e.role not in ("Mesa", "Tree", "Quarry", "Wreck"):
                    continue
                feature = e.attrs.get("Feature")
                if feature:
                    groups.setdefault(feature, []).append(e)
                else:
                    single.append(e)
            self._landmarks = [Feature(name, parts) for name, parts in sorted(groups.items())] + single
        return self._landmarks

    def sky_shadows(self):
        """Shadows of things about to fall from the sky (main.lua sky events); nothing stands on them."""
        return [e for e in self.entities.values() if e.role == "SkyShadow"]

    def held(self):
        """The object floating above our head, if any (holding is implicit in Mesa)."""
        if not self._held_known:
            anchor = (self.me[0], self.me[1] + HOLD_OFFSET_Y, self.me[2])
            self._held = next((e for e in self.movables() if math.dist(e.pos, anchor) < 0.8), None)
            self._held_known = True
        return self._held

    def _standable_index(self):
        if self._index is None:
            held = self.held()
            terrain = self.terrain()
            pieces = [m for m in self.movables() if m is not held and not m.name.startswith("Ladder_")]
            self._index = BoxIndex([(e.pos[0], e.pos[2], e.size[0] / 2, e.size[2] / 2, e.top, e, is_terrain)
                                    for group, is_terrain in ((terrain, True), (pieces, False)) for e in group])
        return self._index

    def ground_top(self, x, z):
        """Height of the walkable surface at (x, z): the highest terrain part covering it."""
        tops = [b[4] for b in self._standable_index().at(x, z) if b[6]]
        return max(tops) if tops else None  # None means open ocean

    def standables(self, below=None):
        """Things to stand on: terrain, and pieces lying still (not carried, not a ladder), as
        (x, z, half x, half z, top, entity). With `below`, only those whose top is no higher than that."""
        held = self.held()
        parts = self.terrain() + [m for m in self.movables() if m is not held and not m.name.startswith("Ladder_")]
        return [(e.pos[0], e.pos[2], e.size[0] / 2, e.size[2] / 2, e.top, e) for e in parts
                if below is None or e.top <= below]

    def surface(self, x, z, below=None):
        """The highest thing to stand on at (x, z), as (top, entity); (None, None) over open sea."""
        best = (None, None)
        covering = self._standable_index().at(x, z)
        if not any(b[6] for b in covering):  # no terrain under it: open sea
            return best
        for _, _, _, _, top, e, _ in covering:
            if (below is None or top <= below) and (best[0] is None or top > best[0]):
                best = (top, e)
        return best

    def column(self, name):
        """The contiguous stack of cubes that contains `name`, bottom to top."""
        base = self.entities.get(name)
        if base is None:
            return []
        held = self.held()
        same = sorted((c for c in self.cubes() if hdist(c.pos, base.pos) < 0.6 * CUBE and c is not held),
                      key=lambda c: c.pos[1])
        chains, chain = [], []
        for c in same:
            if chain and not 0.73 * CUBE < c.pos[1] - chain[-1].pos[1] < 1.27 * CUBE:
                chains.append(chain)
                chain = []
            chain.append(c)
        chains.append(chain)
        return next((ch for ch in chains if any(c.name == name for c in ch)), [base])

    def stacks(self):
        """Columns of two or more cubes: [(base_xz, [names bottom to top])]."""
        seen, out = set(), []
        for c in sorted(self.cubes(), key=lambda c: c.pos[1]):
            if c.name in seen:
                continue
            col = self.column(c.name)
            seen.update(x.name for x in col)
            if len(col) >= 2:
                out.append(((round(col[0].pos[0], 1), round(col[0].pos[2], 1)), [x.name for x in col]))
        return out


class World:
    def __init__(self, base_url="http://localhost:8080", name="Godling", timeout=10, key=None):
        self.base = base_url.rstrip("/")
        self.name = name
        self.timeout = timeout
        self.session = None
        # The world's join key (patches/v2, ADR-014): run_godling.py makes one per run and its children inherit it.
        self.key = key if key is not None else os.environ.get("WORLD_AGENT_KEY", "")

    def _request(self, method, path, body=None, headers=None):
        headers = {"Content-Type": "application/json", **(headers or {})}
        if self.session:
            headers["X-Session"] = self.session
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except OSError as err:
            raise WorldError(f"{method} {path}: {err}") from err
        return json.loads(raw) if raw else None

    def wait_until_up(self, seconds=60):
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                urllib.request.urlopen(self.base + "/api.md", timeout=2).read()
                return
            except OSError:
                time.sleep(0.5)
        raise WorldError(f"world at {self.base} did not come up within {seconds}s")

    def join(self):
        reply = self._request("POST", "/join?name=" + urllib.parse.quote(self.name),
                              headers={"X-Agent-Key": self.key} if self.key else None)
        self.session = reply["session"]
        return reply

    def observe(self):
        return Snapshot(self._request("GET", "/observe"))

    def act(self, action, data=None):
        snap = Snapshot(self._request("POST", "/input", {"type": action, "data": data or {}}))
        return snap if snap.has_world else self.observe()

    def say(self, text):
        self._request("POST", "/chat", {"content": text[:480]})

    def chat_since(self, after=None, limit=20):
        query = {"limit": limit}
        if after:
            query["after"] = after
        reply = self._request("GET", "/chat/messages?" + urllib.parse.urlencode(query)) or {}
        return reply.get("messages") or []
