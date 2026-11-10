"""The house the mind is building, told to the world (ADR-029).

The world cannot tell a house from its pieces until it stands (main.lua houseAt): while it goes up, its room is open
grass and its walls are a few pieces. In the live run of 2026-11-08/09, logs viewers dropped from the sky landed on
its walls and round its room, and the clutter stopped Godling building. So the mind tells the world, with the input
HouseSite, every cell the house needs: its room, its walls all round (corners too), its doorway, the way out and the
cells round the way out (its apron). The sky keeps viewers' gifts off those cells (main.lua sky.aim.offSite). It tells
the world nothing new about building and places nothing: a site, as a colony game keeps a zone, not a step towards
guided construction.
"""
from .house import outside_of, sides, site_of
from .world import WorldError


def house_cells(memory):
    """Every cell (ix, iz) the house the mind is building needs, sorted; none without a house or the house project.

    One rule for the hands, the plan and the sky (house.site_of, ADR-027; INT-2 of the review): the house's room, walls,
    doorway and way out, the strip of ground a cell wide round the walls where the body stands to build them, and the
    way in beyond the way out; with what the body keeps clear (NativeMemory.reserved_cells) and the way out's apron
    (review of #79, 79-AB2), which the site already holds."""
    reserved = memory.reserved_cells()
    if not reserved:
        return []
    house = memory.state["house"]
    room, door = [tuple(c) for c in house["inside"]], tuple(house["door"])
    out = outside_of(room, door)
    apron = set(sides([out])) - {door} if out is not None else set()
    return sorted(set(reserved) | set(site_of(room, door)) | apron)


class HouseSite:
    """Keeps the world's house site the same as the mind's house. `sync` sends it when it changed, or when the world
    is another one (a new session: a world started afresh knows nothing), and is cheap otherwise. The first sync
    sends even no house, so whatever an earlier mind left in a world still running is cleared. A world that did not
    hear is told at the next sync."""

    def __init__(self, world, memory, log=None):
        self.world, self.memory, self.log = world, memory, log or (lambda **k: None)
        self.sent = None  # (session, cells) as the world last heard them

    def sync(self):
        cells = house_cells(self.memory)
        now = (getattr(self.world, "session", None), cells)
        if now == self.sent:
            return False
        try:
            self.world.act("HouseSite", {"cells": [list(c) for c in cells]})
        except WorldError as err:
            self.log(kind="error", message=f"house site: {err}"[:200])
            return False
        self.sent = now
        self.log(kind="house_site", cells=len(cells))
        return True
