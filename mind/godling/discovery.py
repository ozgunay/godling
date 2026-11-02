"""What Godling has seen of the island (ADR-008).

The mind is no longer handed the whole map. What it knows is:
- the ground it has been within sight of;
- the landmarks it has seen (tall ones, such as the peak, from anywhere);
- the objects it has come near.

It learns the island by walking it. The body's legs still find their own way over ground the mind has not seen.
What it has seen is kept with its memory, so a restart of the mind does not forget the island.
"""
import json
import math
from pathlib import Path

from .world import hdist

SIGHT = 35.0  # how far Godling sees the ground and what lies on it
TALL = 20.0  # landmarks at least this high are seen from anywhere on the island
MAP_CELL = 10  # the mind's map: one character per 10 units


class Discovery:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.cells, self.names = set(), set()
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text())
            self.cells = {tuple(c) for c in data.get("cells", [])}
            self.names = set(data.get("names", []))
        self._unsaved = 0

    def see(self, snap):
        """Everything within sight of where the body stands now becomes known."""
        if not snap.has_world:
            return
        x0, z0 = snap.me[0], snap.me[2]
        reach = int(SIGHT // MAP_CELL) + 1
        ci, cj = round(x0 / MAP_CELL), round(z0 / MAP_CELL)
        for i in range(ci - reach, ci + reach + 1):
            for j in range(cj - reach, cj + reach + 1):
                if (i, j) not in self.cells and math.hypot(i * MAP_CELL - x0, j * MAP_CELL - z0) <= SIGHT:
                    self.cells.add((i, j))
                    self._unsaved += 1
        for e in snap.entities.values():
            if e.name not in self.names and (hdist(e.pos, snap.me) <= SIGHT or (e.role == "Mesa" and e.top >= TALL)):
                self.names.add(e.name)
                self._unsaved += 1
        if self._unsaved >= 25:
            self.save()

    def knows_ground(self, x, z):
        return (round(x / MAP_CELL), round(z / MAP_CELL)) in self.cells

    def knows(self, thing):
        """An entity, or a landmark made of parts (the Peak): known once any part of it has been seen."""
        parts = getattr(thing, "parts", None)
        return any(p.name in self.names for p in parts) if parts else thing.name in self.names

    def save(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"cells": sorted(self.cells), "names": sorted(self.names)}))
        self._unsaved = 0
