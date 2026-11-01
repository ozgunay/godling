"""L2 attention: notice what changed between observations and decide what is worth interrupting for.

v0 uses simple rules. `decide` is the slot for a fast decision model (Jev 1.14) in arm C.

Only visitors and real damage interrupt (ADR-003 O6): every interruption throws away the plan being
thought up. New objects and small shifts are noted for the next plan instead.
"""
from .skills import Interrupted
from .world import CUBE, hdist

INTERRUPT_AT = 4  # salience 1-5
KNOCKED_AWAY = 0.8 * CUBE  # a kept block pushed this far sideways counts as damage, like one that fell


class Attention:
    def __init__(self, memory, busy=lambda: set(), log=None):
        self.memory = memory
        self.busy = busy  # objects our own skills are handling right now: their movement is not news
        self.log = log or (lambda **kw: None)
        self.prev = None
        self.pending = []  # events the mind has not seen yet
        self.interrupt = None

    def on_step(self, snap):
        """Called by the skills on every observation; raises Interrupted for salient events."""
        if not snap.has_world:
            return
        if self.prev is not None:
            for text, salience, entities in self._diff(self.prev, snap):
                event = {"text": text, "salience": salience, "entities": entities, "tick": snap.tick}
                self.pending.append(event)
                self.log(kind="event", **event)
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

    def _diff(self, before, after):
        out = []
        old = {e.name: e for e in before.movables()}
        new = {e.name: e for e in after.movables()}
        for name in new.keys() - old.keys():
            e = new[name]
            out.append((f"A new object, {name}, appeared at ({e.pos[0]:.0f}, {e.pos[2]:.0f})", 3, [name]))
        busy = set(self.busy()) | ({after.held().name} if after.held() else set())
        for name in old.keys() - new.keys():
            mine = name in self.memory.protected_cubes()
            out.append((f"{name} is gone from the world" + (" (it was part of something I built)" if mine else ""),
                        5 if mine else 3, [name]))
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
                out.append((f"Part of my {title} was knocked down: {', '.join(fell)} fell or was knocked away", 5, fell))
            if shifted:
                out.append((f"Part of my {title} shifted a little: {', '.join(shifted)}", 3, shifted))
        before_names = {n for n, _ in before.others}
        for name, pos in after.others:
            if name not in before_names:
                out.append((f"Someone called {name} appeared at ({pos[0]:.0f}, {pos[2]:.0f})", 5, []))
        return out
