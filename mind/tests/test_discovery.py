import json

from godling import discovery as disc
from godling.discovery import Discovery
from godling.world import BODY_CENTRE_Y, Entity, Feature
from helpers import block, ent, ground, snap


def island(me=(0, BODY_CENTRE_Y, 0), extra=(), fog=0.0):
    return snap([ground(size=(200, 1, 200)),
                 ent("Hill_1", (15, 5, 0), (4, 10, 30), role="Mesa"),  # a ridge east of the body
                 ent("Peak_1", (-60, 15, 0), (10, 30, 10), role="Mesa"),  # tall: seen from anywhere
                 block("Block_1", 5, 1.25, 5),
                 block("Block_2", 25, 1.25, 0),  # behind the ridge
                 *extra], me=me, clock={"Fog": fog})


def test_sees_what_is_in_sight(tmp_path):
    d = Discovery(tmp_path / "seen.json")
    d.see(island())
    assert "Block_1" in d.visible and "Peak_1" in d.visible and "Hill_1" in d.visible
    assert "Block_2" not in d.visible  # the ridge hides it
    assert d.seen["Block_1"] == (5, 1.25, 5) and "Peak_1" not in d.seen  # only loose things are placed
    assert d.knows_ground(0, 0) and not d.knows_ground(90, 0)
    assert d.knows(Entity(ent("Block_1"))) and not d.knows(Entity(ent("Block_2")))
    peak = Feature("Peak", [Entity(ent("Peak_1", role="Mesa")), Entity(ent("Peak_9", role="Mesa"))])
    assert d.knows(peak)
    assert (tmp_path / "seen.json").exists()  # many new cells: saved
    data = json.loads((tmp_path / "seen.json").read_text())
    again = Discovery(tmp_path / "seen.json")
    assert again.cells == {tuple(c) for c in data["cells"]} and again.seen["Block_1"] == (5, 1.25, 5)


def test_looks_are_rate_limited_and_moved_things_are_forgotten(tmp_path, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(disc.time, "time", lambda: now[0])
    d = Discovery()
    d.see(island())
    assert "Block_1" in d.seen
    d.see(island(extra=[]))  # too soon and the body has not moved: no look
    moved = snap([ground(size=(200, 1, 200)), ent("Hill_1", (15, 5, 0), (4, 10, 30), role="Mesa")], clock={})
    now[0] += 5
    d.see(moved)  # Block_1's spot is in plain sight, and it is not there
    assert "Block_1" not in d.seen
    d.save()  # no path: nothing written
    d.see(snap([]))  # no world


def test_fog_hides_far_things_and_the_peak():
    d = Discovery()
    far = block("Block_9", -25, 1.25, 0)
    d.see(island(extra=[far], fog=1.0))
    assert "Block_9" not in d.visible and "Peak_1" not in d.visible


def test_a_rock_does_not_hide_itself():
    d = Discovery()
    d.see(island())
    assert "Hill_1" in d.visible
    rock = d._rock_index(island())
    assert d._rock_index(island()) is rock  # the same rock: indexed once


def test_a_rock_looked_at_does_not_hide_itself_on_the_way():
    from godling.world import BoxIndex
    hill = Entity(ent("Hill_1", (10, 5, 0), (6, 10, 6), role="Mesa"))
    rock = BoxIndex([(10, 0, 3, 3, 10)])
    assert not Discovery._clear(rock, (0, 4.5, 0), (14, 1, 0))
    assert Discovery._clear(rock, (0, 4.5, 0), (14, 1, 0), own=hill)
