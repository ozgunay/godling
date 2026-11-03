"""What Godling has seen of the island (ADR-008).

The mind is no longer handed the whole map. What it knows is:
- the ground it has seen;
- the landmarks it has seen (tall ones, such as the peak, from anywhere);
- the loose things it has seen, where it saw them last.

Sight reaches SIGHT units and does not pass through rock: the mountain and the hills hide what lies behind them.
Loose things out of sight are remembered where they were last seen. Looking again at that spot and not finding one
there means its whereabouts are unknown until it is seen again.

It learns the island by walking it. The body's legs still find their own way over ground the mind has not seen.
What it has seen is kept with its memory, so a restart of the mind does not forget the island.
"""
import json
import math
import time
from pathlib import Path

from .files import write_atomic
from .world import BODY_CENTRE_Y, BoxIndex, hdist

SIGHT = 35.0  # how far Godling sees the ground and what lies on it
TALL = 20.0  # landmarks at least this high are seen from anywhere on the island
MAP_CELL = 10  # the mind's map: one character per 10 units
EYE = 4.5  # eye height above the feet
LOOK_EVERY = 0.8  # seconds between looks, unless the body has moved on
SIGHT_STEP = 2.0  # how finely a line of sight is checked against the rock
FOG_HIDES = 0.6  # thick fog cuts sight to 0.4 of SIGHT


class Discovery:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.cells, self.names, self.seen = set(), set(), {}
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text())
            self.cells = {tuple(c) for c in data.get("cells", [])}
            self.names = set(data.get("names", []))
            self.seen = {n: tuple(p) for n, p in data.get("seen", {}).items()}
        self.visible = set()  # what was in sight at the last look
        self._unsaved = 0
        self._looked = None  # (when, where) of the last look
        self._rock = None  # (number of rock parts, index of them): what blocks sight

    def see(self, snap):
        """Everything in sight of where the body stands now becomes known, and loose things are seen where they are."""
        if not snap.has_world:
            return
        me = snap.me
        if self._looked and time.time() - self._looked[0] < LOOK_EVERY and hdist(me, self._looked[1]) < 2.0:
            return
        self._looked = (time.time(), me)
        eye = (me[0], me[1] - BODY_CENTRE_Y + EYE, me[2])
        rock = self._rock_index(snap)
        sight = SIGHT * (1 - FOG_HIDES * snap.fog)  # fog from the sea hides what is further off (ADR-010)
        reach = int(sight // MAP_CELL) + 1
        ci, cj = round(me[0] / MAP_CELL), round(me[2] / MAP_CELL)
        for i in range(ci - reach, ci + reach + 1):
            for j in range(cj - reach, cj + reach + 1):
                x, z = i * MAP_CELL, j * MAP_CELL
                if (i, j) not in self.cells and math.hypot(x - me[0], z - me[2]) <= sight:
                    ground = snap.ground_top(x, z)
                    if self._clear(rock, eye, (x, (ground or 0.0) + 0.5, z)):
                        self.cells.add((i, j))
                        self._unsaved += 1
        visible = set()
        for e in snap.entities.values():
            near = hdist(e.pos, me) <= sight and self._clear(rock, eye, (e.pos[0], e.top, e.pos[2]), e)
            towering = e.role == "Mesa" and e.top >= TALL and snap.fog < 0.5  # the peak, unless fog hides it
            if near or towering:
                visible.add(e.name)
                if e.name not in self.names:
                    self.names.add(e.name)
                    self._unsaved += 1
                if e.movable:
                    self.seen[e.name] = tuple(round(v, 2) for v in e.pos)
        for name, pos in list(self.seen.items()):
            # Its spot is in plain sight and it is not there: moved or gone, Godling does not know where.
            if name not in visible and hdist(pos, me) <= sight - 5 and self._clear(rock, eye, pos):
                del self.seen[name]
                self._unsaved += 1
        self.visible = visible
        if self._unsaved >= 25:
            self.save()

    @staticmethod
    def _clear(rock, eye, target, own=None):
        """Nothing of rock between the eye and the target, checked every SIGHT_STEP units along the line. A rock part
        looked at (`own`) does not hide itself."""
        steps = int(hdist(eye, target) / SIGHT_STEP)
        for k in range(1, steps):
            t = k / steps
            x, z = eye[0] + (target[0] - eye[0]) * t, eye[2] + (target[2] - eye[2]) * t
            if own is not None and own.footprint_contains(x, z):
                continue
            if any(top > eye[1] + (target[1] - eye[1]) * t for *_, top in rock.at(x, z)):
                return False
        return True

    def _rock_index(self, snap):
        rock = [e for e in snap.terrain() if e.role == "Mesa"]
        if self._rock is None or self._rock[0] != len(rock):  # the rock does not change: index it once
            self._rock = (len(rock), BoxIndex([(e.pos[0], e.pos[2], e.size[0] / 2, e.size[2] / 2, e.top) for e in rock]))
        return self._rock[1]

    def knows_ground(self, x, z):
        return (round(x / MAP_CELL), round(z / MAP_CELL)) in self.cells

    def knows(self, thing):
        """An entity, or a landmark made of parts (the Peak): known once any part of it has been seen."""
        parts = getattr(thing, "parts", None)
        return any(p.name in self.names for p in parts) if parts else thing.name in self.names

    def save(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_atomic(self.path, json.dumps({"cells": sorted(self.cells), "names": sorted(self.names),
                                                "seen": {n: list(p) for n, p in sorted(self.seen.items())}}))
        self._unsaved = 0
