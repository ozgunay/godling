"""L2 attention: notice what changed between observations and decide what is worth interrupting for.

v0 uses simple rules. `decide` is the slot for a fast decision model (Jev 1.14) in arm C.

Only visitors and real damage interrupt (ADR-003 O6): every interruption throws away the plan being
thought up. New objects and small shifts are noted for the next plan instead.

Noticing is also visible: events that happen somewhere get a glance, a turn of the body towards them between
steps, which never changes the plan (research report "God games lessons for Godling", batch 1).
"""
import math
import time

from .skills import Interrupted
from .world import CUBE, hdist

INTERRUPT_AT = 4  # salience 1-5
GLANCE_AT = 3  # events at least this salient, and somewhere, get a glance
GLANCES_KEPT = 3  # several things at once get a look each, the most salient first
GLANCE_STALE = 30  # seconds: an older event is no longer worth turning to
KNOCKED_AWAY = 0.8 * CUBE  # a kept block pushed this far sideways counts as damage, like one that fell


def _at(pos):
    return {"at": [round(pos[0], 1), round(pos[2], 1)]}


def _sky(e, stage):
    """Sky events carry their kind, number and stage (warning, arrived), so a run's analysis can follow one."""
    sky_id = e.attrs.get("SkyId")
    return {"sky": e.attrs["SkyEvent"], "sky_id": int(sky_id) if sky_id is not None else None, "sky_stage": stage}


def _xz(e):
    return f"({e.pos[0]:.0f}, {e.pos[2]:.0f})"


def _bearing(frm, to):
    """Which way `to` lies from `frm`, in words (north is +z, as on the mind's map)."""
    dx, dz = to[0] - frm[0], to[2] - frm[2]
    names = ("east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east")
    return names[round(math.atan2(dz, dx) / (math.pi / 4)) % 8]


def _sky_arrival(kind, pieces):
    """One line for what one sky event left in the world (a gift, a meteor's stone, a lightning strike's logs)."""
    names = " and ".join(p.name for p in pieces)
    where = _xz(pieces[0])
    if kind == "Meteor":
        return f"A stone fell from the sky: {names} landed at {where}"
    if kind == "Lightning":
        return f"Lightning struck {pieces[0].attrs.get('FromTree', 'a tree')} and felled it: {names} lie at {where}"
    return f"A {kind.lower()} dropped from the sky: {names} landed at {where}"


class Attention:
    def __init__(self, memory, busy=lambda: set(), log=None, discovery=None):
        self.memory = memory
        self.discovery = discovery  # what Godling has seen of the island grows with every look (ADR-008)
        self.busy = busy  # objects our own skills are handling right now: their movement is not news
        self.log = log or (lambda **kw: None)
        self.prev = None
        self.pending = []  # events the mind has not seen yet
        self.interrupt = None
        self.glances = []  # events worth turning to look at, with when they were seen

    def on_step(self, snap):
        """Called by the skills on every observation; raises Interrupted for salient events."""
        if not snap.has_world:
            return
        if self.discovery is not None:
            self.discovery.see(snap)
        if self.prev is not None:
            for text, salience, entities, extra in self._diff(self.prev, snap):
                event = {"text": text, "salience": salience, "entities": entities, "tick": snap.tick, **extra}
                self.pending.append(event)
                self.log(kind="event", **event)
                if salience >= GLANCE_AT and "at" in event:
                    self.glances.append((time.time(), event))
                if self.decide(event):
                    self.interrupt = text
        self.prev = snap
        if self.interrupt:
            why, self.interrupt = self.interrupt, None
            raise Interrupted(why)

    def decide(self, event):
        """Interrupt the current project for this event? (Jev slot: a Boolean question.)"""
        return event["salience"] >= INTERRUPT_AT

    def take_events(self):
        events, self.pending = self.pending, []
        return events

    def take_glance(self):
        fresh = [g for g in self.glances if time.time() - g[0] < GLANCE_STALE]
        fresh.sort(key=lambda g: -g[1]["salience"])  # stable: equal salience keeps the order things happened in
        self.glances = fresh[1:GLANCES_KEPT]
        return fresh[0][1] if fresh else None

    def _diff(self, before, after):
        out = []
        old = {e.name: e for e in before.movables()}
        new = {e.name: e for e in after.movables()}
        from_sky = {}  # one event per sky event, however many pieces it left
        for name in sorted(new.keys() - old.keys()):
            e = new[name]
            if e.attrs.get("SkyEvent"):
                from_sky.setdefault((e.attrs["SkyEvent"], e.attrs.get("SkyId")), []).append(e)
            elif e.attrs.get("Driftwood"):
                out.append((f"A log washed up on the beach: {name} lies at {_xz(e)}", 3, [name], _at(e.pos)))
            else:
                out.append((f"A new object, {name}, appeared at {_xz(e)}", 3, [name], _at(e.pos)))
        for (kind, _), pieces in from_sky.items():
            out.append((_sky_arrival(kind, pieces), 3, [p.name for p in pieces],
                        {**_at(pieces[0].pos), **_sky(pieces[0], "arrived")}))
        for e in after.landmarks():
            was = before.entities.get(e.name)
            if (was is not None and e.attrs.get("SkyEvent") == "Regrow"
                    and e.attrs.get("SkyId") != was.attrs.get("SkyId")):  # newly regrown, even straight after a felling
                out.append((f"{e.name} grew back from its stump in an instant at {_xz(e)}", 3, [e.name],
                            {**_at(e.pos), **_sky(e, "arrived")}))
        busy = set(self.busy()) | ({after.held().name} if after.held() else set())
        for name in old.keys() - new.keys():
            mine = name in self.memory.protected_cubes()
            out.append((f"{name} is gone from the world" + (" (it was part of something I built)" if mine else ""),
                        5 if mine else 3, [name], {}))
        for title, s in self.memory.state["structures"].items():
            # Compare with where each cube stood when kept, and report a displacement only once.
            home = s.setdefault("positions", {})
            fell, shifted, changed = [], [], False
            for c in s["cubes"]:
                if c in new and c in home:
                    was, now = home[c], new[c].pos
                    if hdist(was, now) > 0.5 or abs(was[1] - now[1]) > 0.3:
                        # Wherever our own skills carry a cube is its new home, not news.
                        if c not in busy:
                            damaged = was[1] - now[1] > CUBE / 2 or hdist(was, now) > KNOCKED_AWAY
                            (fell if damaged else shifted).append(c)
                        home[c] = [round(v, 3) for v in now]
                        changed = True
            if changed:
                self.memory.save()
            if fell:
                out.append((f"Part of my {title} was knocked down: {', '.join(fell)} fell or was knocked away", 5, fell,
                            _at(new[fell[0]].pos)))
            if shifted:
                out.append((f"Part of my {title} shifted a little: {', '.join(shifted)}", 3, shifted,
                            _at(new[shifted[0]].pos)))
        before_shadows = {e.name for e in before.sky_shadows()}
        for e in after.sky_shadows():
            if e.name not in before_shadows:
                lands = e.attrs.get("LandsIn")
                out.append((f"A dark shadow spreads on the ground at {_xz(e)}: something is falling from the sky "
                            "there" + (f", landing in about {lands:.0f}s" if lands else ""),
                            3, [e.name], {**_at(e.pos), **_sky(e, "warning")}))
        if after.hurts > before.hurts:  # real damage, to the body itself
            by = {"Lightning": "lightning striking close by", "Meteor": "a stone from the sky landing close by"}
            out.append((f"You were hurt by {by.get(after.hurt_by, 'something')}: your health is "
                        f"{after.health:.0f} of 100", 4, [], _at(after.me)))
        if after.quake_phase and not before.quake_phase:  # an earthquake: the rumble before the shaking
            out.append(("The ground is rumbling under you: an earthquake is coming", 5, [],
                        {"sky": "Earthquake", "sky_id": int(after.quake_id or 0), "sky_stage": "warning"}))
        elif before.quake_phase and not after.quake_phase:
            out.append(("The ground has stopped shaking", 4, [],
                        {"sky": "Earthquake", "sky_id": int(after.quake_id or 0), "sky_stage": "arrived"}))
        if (after.rain >= 0.3) != (before.rain >= 0.3):  # the weather turns (ADR-010)
            out.append(("It has started to rain" if after.rain >= 0.3 else "The rain has stopped", 3, [], {}))
        if (after.fog >= 0.5) != (before.fog >= 0.5):
            out.append(("Fog has rolled in from the sea; you cannot see far" if after.fog >= 0.5 else "The fog has lifted",
                        3, [], {}))
        fires_then = {n for n in before.entities if n.startswith("Fire_")}
        for name in sorted(fires_then - {n for n in after.entities if n.startswith("Fire_")}):
            out.append((f"{name} has gone out" + (": the rain put it out" if after.rain >= 0.3 else ""), 3, [name], {}))
        ship, was = after.entities.get("Ship"), before.entities.get("Ship")
        if ship is not None and was is None:  # as in the film: a ship far out at sea (ADR-010)
            out.append((f"A ship is passing far out at sea, to the {_bearing(after.me, ship.pos)} "
                        f"({ship.pos[0]:.0f}, {ship.pos[2]:.0f})", 4, ["Ship"], _at(ship.pos)))
        elif was is not None and ship is None:
            out.append(("The ship has sailed out of sight", 3, [], {}))
        if after.cold and not before.cold:
            out.append(("You have grown cold" + (": the night is chilly out here" if not after.in_rain
                                                 else ": the rain has soaked you through"), 3, [], {}))
        if after.freed > before.freed:
            out.append((f"You were caught inside a piece, too low over your head or pressed into you, and found "
                        f"yourself pushed out of it to ({after.me[0]:.0f}, {after.me[2]:.0f})", 2, [], {}))
        before_names = {n for n, _ in before.others}
        for name, pos in after.others:
            if name not in before_names:
                out.append((f"Someone called {name} appeared at ({pos[0]:.0f}, {pos[2]:.0f})", 5, [], _at(pos)))
        return out
