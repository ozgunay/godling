"""The house the mind is building, told to the world (ADR-029): the world keeps viewers' logs off its cells.

In the live run of 2026-11-08/09 the world knew nothing of the house until it stood, so logs dropped from the sky
landed on its walls and round its room (Log_94 on the north wall, at Godling's feet)."""
import pytest

import run_godling as rg
from godling.memory import NativeMemory
from godling.site import HouseSite, house_cells
from godling.world import WorldError

from test_run_godling import loop_setup, project

ROOM = [[-36, -8], [-36, -7], [-35, -8], [-35, -7]]  # the run's last house: its room and its doorway
DOOR = [-35, -9]


class Recorder:
    def __init__(self, fail=0):
        self.session, self.acts, self.fail = "s1", [], fail

    def act(self, action, data=None):
        if self.fail:
            self.fail -= 1
            raise WorldError("POST /input: connection refused")
        self.acts.append((action, data))


def memory_with_house(tmp_path, on=True):
    memory = NativeMemory(tmp_path / "memory")
    memory.house_project_enabled = on
    memory.set_house({"inside": ROOM, "door": DOOR, "since": 0, "best": -1, "best_at": 0, "pieces": []})
    return memory


def test_the_cells_a_house_needs_are_its_room_walls_doorway_and_way_out(tmp_path):
    cells = house_cells(memory_with_house(tmp_path))
    walls = {(x, z) for x in range(-37, -33) for z in range(-9, -5)} - {tuple(c) for c in ROOM}
    out = (-35, -10)  # the way out: south of the doorway
    apron = {(-36, -10), (-34, -10), (-35, -11)}  # beside it and beyond it (review of #79, 79-AB2)
    assert set(cells) == {tuple(c) for c in ROOM} | walls | {out} | apron
    assert len(cells) == 20 and tuple(DOOR) in cells and cells == sorted(cells)
    assert house_cells(memory_with_house(tmp_path, on=False)) == []  # the comparison arm without the house project
    memory = memory_with_house(tmp_path)
    memory.set_house(None)
    assert house_cells(memory) == []


def test_the_world_is_told_once_and_again_on_each_change(tmp_path):
    memory, world, logs = memory_with_house(tmp_path), Recorder(), []
    site = HouseSite(world, memory, log=lambda **k: logs.append(k))
    assert site.sync() is True
    assert world.acts == [("HouseSite", {"cells": [list(c) for c in house_cells(memory)]})]
    assert site.sync() is False and len(world.acts) == 1  # nothing new: nothing sent
    memory.set_house({**memory.state["house"], "inside": [[x + 4, z] for x, z in ROOM], "door": [-31, -9]})
    assert site.sync() is True and world.acts[-1][1]["cells"][0] == [-33, -9]  # moved: the new site
    memory.set_house(None)
    assert site.sync() is True and world.acts[-1] == ("HouseSite", {"cells": []})  # given up: nothing kept
    world.session = "s2"  # joined again (a world started afresh knows nothing): told again
    assert site.sync() is True and len(world.acts) == 4
    assert [l["cells"] for l in logs if l["kind"] == "house_site"] == [20, 20, 0, 0]


def test_the_site_is_the_cells_the_body_keeps_clear_and_the_walls(tmp_path, monkeypatch):
    """One rule for the cells a house needs (review of #79, 79-CLEAN2): the sky keeps what the body keeps clear
    (NativeMemory.reserved_cells), with the walls and the way out's apron on top, so a cell added there is kept too."""
    memory = memory_with_house(tmp_path)
    monkeypatch.setattr(memory, "reserved_cells", lambda: {(-35, -8), (-35, -9), (-35, -10), (-40, -8)})
    assert (-40, -8) in house_cells(memory)


def test_a_world_that_did_not_hear_is_told_at_the_next_look(tmp_path):
    memory, world, logs = memory_with_house(tmp_path), Recorder(fail=1), []
    site = HouseSite(world, memory, log=lambda **k: logs.append(k))
    assert site.sync() is False and world.acts == []
    assert logs[-1]["kind"] == "error" and "house site" in logs[-1]["message"]
    assert site.sync() is True and len(world.acts) == 1


def test_the_loops_tell_the_world_a_house_before_the_first_project_builds_it(monkeypatch, tmp_path):
    house = {"inside": [[10, 0], [12.5, 0], [10, 2.5], [12.5, 2.5]], "door": [12.5, -2.5], "why": "open grass"}
    for loop, agenda, plan in ((rg.agenda_loop, True, {"house": house, "agenda": [project("hop", ("jump", {}))]}),
                               (rg.single_loop, False, {"house": house, "intention": "",
                                                        "project": {"goal": "hop", "steps": [{"skill": "jump",
                                                                                              "args": {}}]}})):
        island, loop_args, logs, stats = loop_setup(monkeypatch, tmp_path / loop.__name__, [plan], calls=2,
                                                    agenda=agenda)
        loop_args[3].house_project = loop_args[2].house_project_enabled = True
        with pytest.raises(KeyboardInterrupt):
            loop(*loop_args)
        acts = [a for a, _ in island.acts]
        sites = [d["cells"] for a, d in island.acts if a == "HouseSite"]
        assert sites[0] == [], "at the start, whatever an earlier mind left there is cleared"
        assert len(sites[1]) == 20 and [4, 0] in sites[1] and [5, -2] in sites[1] and [5, -3] in sites[1]
        told = [i for i, (a, d) in enumerate(island.acts) if a == "HouseSite" and d["cells"]][0]
        assert "Jump" in acts[told:] and "Jump" not in acts[acts.index("HouseSite") + 1:told], loop.__name__
