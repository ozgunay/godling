import pytest

from godling import attention as att
from godling.attention import Attention, _bearing, _sky_arrival
from godling.memory import NativeMemory
from godling.skills import Interrupted
from godling.world import Entity
from helpers import block, ent, ground, snap


class Seen:
    def __init__(self):
        self.snaps = []

    def see(self, s):
        self.snaps.append(s)


@pytest.fixture
def mem(tmp_path):
    return NativeMemory(tmp_path)


def test_bearing_and_arrivals():
    assert _bearing((0, 0, 0), (1, 0, 0)) == "east"
    assert _bearing((0, 0, 0), (0, 0, 1)) == "north"
    assert _bearing((0, 0, 0), (-1, 0, -1)) == "south-west"
    stone = Entity(ent("Meteor_1", (3, 1, 4)))
    log = Entity(ent("Log_2", (1, 1, 1), attrs={"FromTree": "Palm_3"}))
    gift = Entity(ent("Stone_1", (0, 1, 0)))
    assert _sky_arrival("Meteor", [stone]) == "A stone fell from the sky: Meteor_1 landed at (3, 4)"
    assert _sky_arrival("Lightning", [log]).startswith("Lightning struck Palm_3 and felled it: Log_2")
    assert "a tree" in _sky_arrival("Lightning", [gift])
    assert _sky_arrival("Gift", [gift, stone]) == "A gift dropped from the sky: Stone_1 and Meteor_1 landed at (0, 0)"


def test_no_world_and_first_look(mem):
    seen = Seen()
    a = Attention(mem, discovery=seen)
    a.on_step(snap([]))  # no world: nothing
    assert a.prev is None and seen.snaps == []
    first = snap([ground()])
    a.on_step(first)
    assert a.prev is first and seen.snaps == [first] and a.take_events() == []
    a.log(kind="x")  # the default log takes anything


def test_new_objects_and_sky_events(mem):
    logs = []
    a = Attention(mem, log=lambda **kw: logs.append(kw))
    a.on_step(snap([ground(), ent("Palm_1", (10, 5, 0), (2, 10, 2), role="Tree", attrs={"SkyId": 1})]))
    a.on_step(snap([
        ground(), block("Block_7", 5, 1.25, 5), block("Log_9", 8, 0.5, 0, attrs={"Driftwood": True}),
        block("Stone_2", 1, 1.25, 1, attrs={"SkyEvent": "Gift", "SkyId": 3}),
        block("Stone_3", 1, 1.25, 4, attrs={"SkyEvent": "Gift", "SkyId": 3}),
        block("Meteor_1", 9, 1.25, 9, attrs={"SkyEvent": "Meteor"}),
        ent("Palm_1", (10, 5, 0), (2, 10, 2), role="Tree", attrs={"SkyEvent": "Regrow", "SkyId": 2}),
        ent("SkyShadow_1", (2, 0, 2), (3, 0.1, 3), role="SkyShadow", attrs={"LandsIn": 4.2, "SkyEvent": "Meteor",
                                                                             "SkyId": 5}),
        ent("SkyShadow_2", (2, 0, 2), (3, 0.1, 3), role="SkyShadow", attrs={"SkyEvent": "Gift"}),
    ]))
    texts = [e["text"] for e in a.take_events()]
    assert "A new object, Block_7, appeared at (5, 5)" in texts
    assert "A log washed up on the beach: Log_9 lies at (8, 0)" in texts
    assert "A gift dropped from the sky: Stone_2 and Stone_3 landed at (1, 1)" in texts
    assert "A stone fell from the sky: Meteor_1 landed at (9, 9)" in texts
    assert "Palm_1 grew back from its stump in an instant at (10, 0)" in texts
    assert any("landing in about 4s" in t for t in texts)
    assert any(t.endswith("falling from the sky there") for t in texts)
    meteor = next(e for e in logs if e["text"].startswith("A stone fell"))
    assert meteor["sky"] == "Meteor" and meteor["sky_id"] is None and meteor["sky_stage"] == "arrived"
    glance = a.take_glance()
    assert glance["salience"] == 3 and "at" in glance
    assert len(a.glances) == 2  # GLANCES_KEPT - 1 left


def test_glances_go_stale(mem, monkeypatch):
    a = Attention(mem)
    now = [1000.0]
    monkeypatch.setattr(att.time, "time", lambda: now[0])
    a.glances = [(900.0, {"salience": 5}), (999.0, {"salience": 3}), (998.0, {"salience": 4})]
    assert a.take_glance()["salience"] == 4
    assert a.take_glance()["salience"] == 3
    assert a.take_glance() is None


def test_kept_structures_damage_and_gone(mem):
    mem.add_structure("tower", ["Block_1", "Block_2", "Block_3", "Block_4"], (0, 0),
                      {"Block_1": (0, 1.25, 0), "Block_2": (0, 3.75, 0), "Block_3": (5, 1.25, 0), "Block_4": (9, 1.25, 0)})
    busy = {"Block_4"}
    a = Attention(mem, busy=lambda: busy)
    before = snap([ground(), block("Block_1", 0, 1.25, 0), block("Block_2", 0, 3.75, 0), block("Block_3", 5, 1.25, 0),
                   block("Block_4", 9, 1.25, 0), block("Block_5", 20, 1.25, 0), block("Block_6", 22, 1.25, 0)])
    a.on_step(before)
    after = snap([ground(), block("Block_1", 0.6, 1.25, 0), block("Block_2", 4, 1.25, 0),  # B1 shifted, B2 fell
                  block("Block_3", 5, 1.25, 0), block("Block_4", 12, 1.25, 0), block("Block_6", 22, 1.25, 0)])
    with pytest.raises(Interrupted, match="was knocked down"):
        a.on_step(after)
    texts = [e["text"] for e in a.take_events()]
    assert "Part of my tower was knocked down: Block_2 fell or was knocked away" in texts
    assert "Part of my tower shifted a little: Block_1" in texts
    assert "Block_5 is gone from the world" in texts
    assert not any("Block_4" in t for t in texts)  # carried by our own skills
    assert mem.state["structures"]["tower"]["positions"]["Block_4"] == [12, 1.25, 0]
    later = snap([ground(), block("Block_1", 0.6, 1.25, 0), block("Block_2", 4, 1.25, 0), block("Block_3", 5, 1.25, 0)])
    with pytest.raises(Interrupted, match="something I built"):
        a.on_step(later)


def test_held_cube_movement_is_not_news(mem):
    mem.add_structure("wall", ["Block_1"], (0, 0), {"Block_1": (5, 1.25, 0)})
    a = Attention(mem)
    a.on_step(snap([ground(), block("Block_1", 5, 1.25, 0)]))
    a.on_step(snap([ground(), block("Block_1", 0, 2.55 + 4.0, 0)]))  # now in our hands
    assert a.take_events() == []


def test_body_weather_and_sky_news(mem):
    a = Attention(mem)
    clock0 = {"NoteId": 1, "NoteText": "old", "MeteorId": 1, "Rain": 0, "Fog": 0}
    a.on_step(snap([ground(), ent("Fire_1", (0, 0.5, 9), (1, 1, 1)), ent("Fire_2", (3, 0.5, 9), (1, 1, 1))],
                   clock=clock0, others=[("Ann", (1, 0, 1))]))
    clock1 = {"NoteId": 2, "NoteText": "hello there", "NoteX": 3, "NoteZ": 4, "MeteorId": 2, "MeteorX": 5,
              "MeteorZ": 6, "MeteorSmashed": 1, "MeteorThrown": 2, "MeteorUnfastened": 3, "MeteorFelled": 2,
              "MeteorHurt": 1, "QuakePhase": "rumble", "QuakeId": 4, "Rain": 0.5, "Fog": 0.6}
    with pytest.raises(Interrupted):
        a.on_step(snap([ground(), ent("Ship", (300, 0, 0), (20, 10, 5))], clock=clock1,
                       attrs={"Hurts": 1, "Hurt": "Lightning", "Health": 70, "Cold": True, "InRain": True, "Freed": 1},
                       others=[("Ann", (1, 0, 1)), ("Bob", (7, 0, 8))]))
    texts = [e["text"] for e in a.take_events()]
    assert "You were hurt by lightning striking close by: your health is 70 of 100" in texts
    assert any(t.endswith('It reads: "hello there"') for t in texts)
    assert ("A stone from the sky blasted at (5, 6): it smashed 1 piece, threw 2, broke 3 fastenings, felled 2 palms, "
            "and the blast threw you down. It left a crater.") in texts
    assert "The ground is rumbling under you: an earthquake is coming" in texts
    assert "It has started to rain" in texts and "Fog has rolled in from the sea; you cannot see far" in texts
    assert "Fire_1 has gone out: the rain put it out" in texts and "Fire_2 has gone out: the rain put it out" in texts
    assert "A ship is passing far out at sea, to the east (300, 0)" in texts
    assert "You have grown cold: the rain has soaked you through" in texts
    assert any(t.startswith("You were caught inside a piece") for t in texts)
    assert "Someone called Bob appeared at (7, 8)" in texts
    clock2 = {"NoteId": 2, "NoteText": "hello there", "MeteorId": 3, "Rain": 0, "Fog": 0}
    with pytest.raises(Interrupted):
        a.on_step(snap([ground(), ent("Fire_3", (0, 0.5, 9), (1, 1, 1))], clock=clock2,
                       attrs={"Hurts": 2, "Health": 60, "Cold": False}))
    texts = [e["text"] for e in a.take_events()]
    assert "You were hurt by something: your health is 60 of 100" in texts
    assert "A stone from the sky blasted at (0, 0): it blasted only sand. It left a crater." in texts
    assert "The ground has stopped shaking" in texts
    assert "The rain has stopped" in texts and "The fog has lifted" in texts
    assert "The ship has sailed out of sight" in texts
    a.on_step(snap([ground()], clock={"Rain": 0}, attrs={"Cold": True}))
    texts = [e["text"] for e in a.take_events()]
    assert "Fire_3 has gone out" in texts and "You have grown cold: the night is chilly out here" in texts
    # The world says it stands in a house (ADR-019): once, as it walks in.
    a.on_step(snap([ground()], clock={"Rain": 0}, attrs={"Sheltered": "roof", "InHouse": True}))
    a.on_step(snap([ground()], clock={"Rain": 0}, attrs={"Sheltered": "roof", "InHouse": True}))
    texts = [e["text"] for e in a.take_events()]
    assert texts.count("You are inside a house now: warm and dry, and fed you mend twice as fast") == 1


def test_decide_is_the_interrupt_rule(mem):
    a = Attention(mem)
    assert a.decide({"salience": 4}) and not a.decide({"salience": 3})
