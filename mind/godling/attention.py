"""L2 attention: notice what changed between observations and decide what is worth interrupting for.

v0 uses simple rules. `decide` is the slot for a fast decision model (Jev 1.14) in arm C.

Only visitors and real damage interrupt (ADR-003 O6): every interruption throws away the plan being
thought up. New objects and small shifts are noted for the next plan instead.

Noticing is also visible: events that happen somewhere get a glance, a turn of the body towards them between
steps, which never changes the plan (research report "God games lessons for Godling", batch 1).
"""
import math
import time
from collections import deque

from .skills import Interrupted
from .world import CUBE, death_cause, hdist

INTERRUPT_AT = 4  # salience 1-5
GLANCE_AT = 3  # events at least this salient, and somewhere, get a glance
GLANCES_KEPT = 3  # several things at once get a look each, the most salient first
GLANCE_STALE = 30  # seconds: an older event is no longer worth turning to
KNOCKED_AWAY = 0.8 * CUBE  # a kept block pushed this far sideways counts as damage, like one that fell
# For a death report (main.lua DEATH): how the body was, once every TRAIL_EVERY seconds, and what was noticed, over the
# last TRAIL_SECONDS, so the mind can work out for itself what led to it.
TRAIL_EVERY, TRAIL_SECONDS = 10, 600
NOTICED_KEPT = 8  # the latest things noticed before a death that the report names


def _at(pos):
    return {"at": [round(pos[0], 1), round(pos[2], 1)]}


def _sky(e, stage):
    """Sky events carry their kind, number and stage (warning, arrived), so a run's analysis can follow one."""
    sky_id = e.attrs.get("SkyId")
    return {"sky": e.attrs["SkyEvent"], "sky_id": int(sky_id) if sky_id is not None else None, "sky_stage": stage}


def _night(hour):
    """main.lua WEATHER's night: 21:00 to 05:00, when it is cold."""
    return hour is not None and (hour >= 21 or hour < 5)


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
        self.observed_pieces = {}  # last observed geometry, including pieces currently out of sight
        self.pending = []  # events the mind has not seen yet
        self.interrupt, self.interrupt_salience = None, 0  # why the step now is interrupted, and how salient it was
        self.glances = []  # events worth turning to look at, with when they were seen
        self.trail = deque()  # (time, how the body was), one every TRAIL_EVERY seconds, for a death report
        self.noticed = deque()  # (time, text) of what was noticed lately, for a death report
        self.last_life = None  # (trail, noticed) as they were when the body died: what its death report tells
        self.death_pending = False  # a death seen by the body that the mind has not reflected on yet

    def on_step(self, snap):
        """Called by the skills on every observation; raises Interrupted for salient events."""
        if not snap.has_world:
            return
        now = time.time()
        new_death = ((self.prev is None and snap.deaths > 0
                      and snap.deaths != self.memory.state.get("last_reflected_death", 0))
                     or (self.prev is not None and snap.deaths > self.prev.deaths)
                     or (snap.dead and not (self.prev is not None and self.prev.dead)))
        if new_death:  # the whole dead interval can pass during one slow model call
            self.last_life = (list(self.trail), list(self.noticed))
            self.death_pending = True
            self.trail.clear()
            self.noticed.clear()
        if snap.health is not None and not snap.dead and (not self.trail or now - self.trail[-1][0] >= TRAIL_EVERY):
            self.trail.append((now, {"health": snap.health, "hunger": snap.hunger, "cold": snap.cold, "wet": snap.wet,
                                     "in_rain": snap.in_rain, "sheltered": snap.sheltered, "in_house": snap.in_house,
                                     "by_fire": snap.by_fire, "night": _night(snap.time_of_day)}))
        while self.trail and now - self.trail[0][0] > TRAIL_SECONDS:
            self.trail.popleft()
        while self.noticed and now - self.noticed[0][0] > TRAIL_SECONDS:
            self.noticed.popleft()
        if self.discovery is not None:
            self.discovery.see(snap)
            if self.prev is None:
                self.observed_pieces = {e.name: e for e in snap.movables() if e.name in self.discovery.visible}
        if self.prev is not None:
            for text, salience, entities, extra in self._diff(self.prev, snap):
                event = {"text": text, "salience": salience, "entities": entities, "tick": snap.tick, **extra}
                self._record(event, now)
                if salience >= GLANCE_AT and "at" in event and not extra.get("death"):  # the dead do not look about
                    self.glances.append((time.time(), event))
                if self.decide(event) and salience > self.interrupt_salience:  # the most salient names it
                    self.interrupt, self.interrupt_salience = text, salience
        self.prev = snap
        if self.interrupt:
            why, self.interrupt, self.interrupt_salience = self.interrupt, None, 0
            raise Interrupted(why)

    def decide(self, event):
        """Interrupt the current project for this event? (Jev slot: a Boolean question.)"""
        return event["salience"] >= INTERRUPT_AT

    def take_events(self):
        events, self.pending = self.pending, []
        return events

    def notice(self, text, salience=4, pending=True, **extra):
        """What it is told rather than sees (ADR-028): its body took shelter by itself, its house is lost. News for the
        next plan and for a death report, like what it sees; with `pending` false, only for a death report (the step
        the reflex stopped already carries the words to the mind). It interrupts nothing by itself: a reflex that tells
        it has already stopped the step in progress."""
        event = {"text": text, "salience": salience, "entities": list(extra.pop("entities", [])),
                 "tick": self.prev.tick if self.prev is not None else 0, **extra}
        self._record(event, time.time(), pending=pending)

    def _record(self, event, now, pending=True):
        """An event: news for the next plan, noticed for a death report (but a death itself), and logged."""
        if pending:
            self.pending.append(event)
        if not event.get("death"):
            self.noticed.append((now, event["text"]))
        self.log(kind="event", **event)

    def death_report(self, snap, doing=None):
        """What the mind is told once it is born again: what killed it, how its body was over the minutes before,
        what it was doing and what it noticed. Facts only: the lesson is the mind's own to draw (run_godling.py)."""
        lines = [f"You died of {death_cause(snap.died_of)}"
                 + (f" at ({snap.died_at[0]:.0f}, {snap.died_at[1]:.0f})" if snap.died_at else "") + "."]
        trail, noticed = self.last_life or (list(self.trail), list(self.noticed))
        if trail:
            last_t, last = trail[-1]
            picks = [trail[round(i * (len(trail) - 1) / 4)] for i in range(5)] if len(trail) >= 5 else trail
            ago = lambda t: f"{max(0, (last_t - t) / 60):.0f} min before"  # noqa: E731
            lines.append("Your health in the minutes before: " + ", ".join(
                f"{b['health']:.0f} ({ago(t)})" if t != last_t else f"{b['health']:.0f} at the last look"
                for t, b in picks) + ".")
            if last.get("hunger") is not None:
                lines.append(f"You were {last['hunger']:.0f}% fed at the last look"
                             + (f", {trail[0][1]['hunger']:.0f}% about {(last_t - trail[0][0]) / 60:.0f} min before"
                                if len(trail) > 1 and trail[0][1].get("hunger") is not None else "") + ".")
            how = [w for w, on in (("it was night", last.get("night")), ("you were cold", last.get("cold")),
                                   ("you were out in the rain", last.get("in_rain")),
                                   (f"you were soaked ({last.get('wet', 0):.0f}%)", (last.get("wet") or 0) >= 50),
                                   ("you stood inside your house", last.get("in_house")),
                                   ("you had a roof over you", last.get("sheltered") and not last.get("in_house")),
                                   ("a fire burned beside you", last.get("by_fire"))) if on]
            if not last.get("sheltered"):
                how.append("nothing was over you")
            lines.append("At the last look " + ", ".join(how) + ".")
        if doing:
            lines.append(f"You were busy with: {doing}.")
        noticed = noticed[-NOTICED_KEPT:]
        if noticed:
            end = trail[-1][0] if trail else time.time()
            lines.append("What you noticed in those minutes, oldest first:")
            lines += [f"- {text} ({max(0, (end - t) / 60):.0f} min before)" for t, text in noticed]
        lines.append(f"You have died {snap.deaths} time{'s' * (snap.deaths != 1)} in all.")
        return "\n".join(lines)

    def take_glance(self):
        fresh = [g for g in self.glances if time.time() - g[0] < GLANCE_STALE]
        fresh.sort(key=lambda g: -g[1]["salience"])  # stable: equal salience keeps the order things happened in
        self.glances = fresh[1:GLANCES_KEPT]
        return fresh[0][1] if fresh else None

    def _diff(self, before, after):
        out = []
        old = {e.name: e for e in before.movables()}
        new = {e.name: e for e in after.movables()}
        if self.discovery is not None:
            old = self.observed_pieces
            visible = {name: e for name, e in new.items() if name in self.discovery.visible}
            new = {name: e for name, e in {**old, **visible}.items()
                   if name in self.discovery.seen or name in visible}
            self.observed_pieces = new
        from_sky = {}  # one event per sky event, however many pieces it left
        for name in sorted(new.keys() - old.keys()):
            e = new[name]
            if e.attrs.get("SkyEvent"):
                from_sky.setdefault((e.attrs["SkyEvent"], e.attrs.get("SkyId")), []).append(e)
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
        if after.deaths > before.deaths:  # main.lua DEATH: nothing matters more
            where = {"at": [round(after.died_at[0], 1), round(after.died_at[1], 1)]} if after.died_at else {}
            what = (f"Your body lies where it fell; you will come back to life at the start in about "
                    f"{after.dead_for or 30:.0f}s" if after.dead else
                    "You have already come back to life at the start, whole but half fed")
            out.append((f"You died of {death_cause(after.died_of)}. {what}", 5, [],
                        {**where, "death": "died", "back": not after.dead}))  # back: born again already, unseen
        elif before.dead and not after.dead:
            out.append(("You have come back to life at the start, whole but half fed. What you carried lies where you "
                        "died" + (f", at ({after.died_at[0]:.0f}, {after.died_at[1]:.0f})" if after.died_at else ""),
                        4, [], {**_at(after.me), "death": "reborn"}))
        if after.struck > before.struck:  # main.lua THE STORM: a bolt on the body itself
            out.append((f"Lightning struck you: you are burned and hurt, your health is {after.health:.0f} of 100",
                        5, [], {**_at(after.me), "hit": "struck"}))  # its own timeline mark (replay.marks_of)
        elif after.hurts > before.hurts:  # real damage, to the body itself
            by = {"Lightning": "lightning striking close by", "Meteor": "a stone from the sky landing close by",
                  "Storm": "lightning striking close by"}
            out.append((f"You were hurt by {by.get(after.hurt_by, 'something')}: your health is "
                        f"{after.health:.0f} of 100", 4, [], {**_at(after.me), "hit": "hurt"}))
        if after.storm_phase == "warning" and before.storm_phase != "warning":  # a storm called down is coming
            spots = [f"({x:.0f}, {z:.0f})" for x, z in after.storm_spots]
            where = (", ".join(spots[:-1]) + " and " + spots[-1]) if len(spots) > 1 else "".join(spots)
            out.append(("Dark clouds are rolling in fast: a storm is coming"
                        + (f". The air crackles at {where}" if where else ""), 5, [],
                        {"sky": "Storm", "sky_id": int(after.storm_id or 0), "sky_stage": "warning"}))
        elif after.storm_phase == "storm" and before.storm_phase != "storm":
            out.append(("The storm breaks: rain pours down, and lightning is about to strike", 4, [],
                        {"sky": "Storm", "sky_id": int(after.storm_id or 0), "sky_stage": "arrived"}))
        elif before.storm_phase and not after.storm_phase:
            out.append(("The storm has passed", 3, [], {"sky": "Storm", "sky_id": int(before.storm_id or 0),
                                                         "sky_stage": "passed"}))
        if after.note_id and after.note_id != before.note_id and after.note_text:  # a viewer's note (main.lua sky.notes)
            out.append((f"A paper glider drifted down at ({after.note_at[0]:.0f}, {after.note_at[2]:.0f}) with a note "
                        f"from one of the strangers who watch you. It reads: \"{after.note_text}\"", 3, [],
                        {**_at(after.note_at), "sky": "Note", "sky_id": int(after.note_id), "sky_stage": "arrived",
                         "note": after.note_text}))
        if after.meteor_id and after.meteor_id != before.meteor_id:  # a meteor's blast (main.lua sky.meteor)
            did = after.meteor_did
            parts = [f"smashed {did['Smashed']} piece{'s' * (did['Smashed'] != 1)}" if did["Smashed"] else "",
                     f"threw {did['Thrown']}" if did["Thrown"] else "",
                     f"broke {did['Unfastened']} fastening{'s' * (did['Unfastened'] != 1)}" if did["Unfastened"] else "",
                     f"felled {did['Felled']} palm{'s' * (did['Felled'] != 1)}" if did["Felled"] else ""]
            what = ", ".join(p for p in parts if p) or "blasted only sand"
            out.append((f"A stone from the sky blasted at ({after.meteor_at[0]:.0f}, {after.meteor_at[2]:.0f}): it {what}"
                        + (", and the blast threw you down" if did["Hurt"] else "") + ". It left a crater.",
                        4, [], {**_at(after.meteor_at), "sky": "Meteor", "sky_id": int(after.meteor_id),
                                "sky_stage": "blast", **({"hit": "thrown"} if did["Hurt"] else {})}))
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
        if after.in_house and not before.in_house:  # ADR-019: the world says it is a house
            out.append(("You are inside a house now: warm and dry, and fed you mend twice as fast", 3, [], {}))
        if after.cold and not before.cold:
            out.append(("You have grown cold" + (": the night is chilly out here" if not after.in_rain
                                                 else ": the rain has soaked you through"), 3, [], {}))
        if after.drowning and not before.drowning:
            out.append(("You have slipped into the sea and cannot climb back out: the water is drowning you. If it "
                        "drowns you, you die, and come back to life at the start spot in the middle of the island",
                        5, [], {}))
        # Drowned counts up as the body dies of the sea (main.lua DEATH): the death notice above says so.
        if after.ashore > before.ashore:
            out.append((f"You hung on the edge of the beach over the sea, and found yourself back on the sand at "
                        f"({after.me[0]:.0f}, {after.me[2]:.0f})", 3, [], {}))
        if after.freed > before.freed:
            out.append((f"You were caught inside a piece, too low over your head or pressed into you, and found "
                        f"yourself pushed out of it to ({after.me[0]:.0f}, {after.me[2]:.0f})", 2, [], {}))
        before_names = {n for n, _ in before.others}
        for name, pos in after.others:
            if name not in before_names:
                out.append((f"Someone called {name} appeared at ({pos[0]:.0f}, {pos[2]:.0f})", 5, [], _at(pos)))
        return out
