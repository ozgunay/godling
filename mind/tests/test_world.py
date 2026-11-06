import json

import pytest

from godling import world as w
from godling.world import BoxIndex, Entity, Feature, Snapshot, World, WorldError
from helpers import block, ent, ground, raw_obs, snap


def test_grid_rounds_to_the_cell_centre():
    assert w.grid(0) == 0
    assert w.grid(1.2) == 0
    assert w.grid(1.3) == 2.5
    assert w.grid(-1.3) == -2.5


def test_hdist_ignores_height():
    assert w.hdist((0, 0, 0), (3, 99, 4)) == 5


def test_world_size_turns_a_box_or_leaves_it():
    quarter = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]
    assert w.world_size((1, 2, 3), quarter) == (3, 2, 1)
    assert w.world_size((1, 2, 3), None) == (1, 2, 3)
    assert w.world_size((1, 2, 3), [[1, 0], [0, 1]]) == (1, 2, 3)  # not a 3x3 matrix


def test_turned_size():
    assert w.turned_size((7.5, 1, 1)) == (7.5, 1, 1)
    assert w.turned_size((7.5, 1, 1), turn=90) == (1, 1, 7.5)
    assert w.turned_size((7.5, 1, 1), turn=180) == (7.5, 1, 1)
    assert w.turned_size((7.5, 1, 1), upright=True) == (1, 7.5, 1)
    assert w.turned_size((7.5, 1, 2), turn=270, upright=True) == (2, 7.5, 1)


def test_entity_properties():
    e = Entity(ent("Block_1", (1, 1.25, 2)))
    assert e.movable and e.is_cube
    assert e.top == 2.5
    assert e.facing == (0.0, 1.0)  # no rotation known
    assert e.footprint_contains(2.2, 2)
    assert not e.footprint_contains(2.4, 2)
    assert e.footprint_contains(2.4, 2, margin=0.2)
    assert e.role == ""
    assert e.anchored and e.aligned
    tree = Entity(ent("Tree_1", role="Tree", size=(2, 10, 2)))
    assert not tree.movable and not tree.is_cube and tree.role == "Tree"


def test_entity_defaults_and_facing():
    bare = Entity({"position": [0, 0, 0]})
    assert bare.name == "?" and bare.local_size == (0, 0, 0) and bare.attrs == {}
    turned = Entity(ent("Ladder_1", rot=[[0, 0, 1], [0, 1, 0], [-1, 0, 0]], size=(2, 7.5, 0.4)))
    assert turned.facing == (1.0, 0.0)
    assert turned.size == pytest.approx((0.4, 7.5, 2))
    assert turned.aligned
    flat = Entity(ent("Ladder_2", rot=[[1, 0, 0], [0, 0, 1], [0, 1, 0]]))
    assert flat.facing == (0.0, 1.0)  # its thin side faces up: no horizontal direction


def test_box_index():
    index = BoxIndex([(0, 0, 1, 1, "a"), (10, 10, 3, 3, "b")])
    assert [b[4] for b in index.at(0.5, 0.5)] == ["a"]
    assert [b[4] for b in index.at(1, 0)] == ["a"]
    assert index.at(1, 0, strict=True) == []
    assert [b[4] for b in index.at(12, 8)] == ["b"]
    assert index.at(50, 50) == []


def test_feature_joins_its_parts():
    a = Entity(ent("Peak_1", (0, 5, 0), (10, 10, 10), role="Mesa", attrs={"Feature": "Peak"}))
    b = Entity(ent("Peak_2", (0, 12, 0), (4, 4, 4), role="Mesa", attrs={"Feature": "Peak"}))
    peak = Feature("Peak", [a, b])
    assert peak.top == 14 and peak.size == (10, 14, 10) and peak.pos == (0, 7, 0) and peak.role == "Mesa"
    assert peak.footprint_contains(4, 4) and not peak.footprint_contains(6, 0)


def test_snapshot_reads_the_body_and_the_clock():
    clock = {"TimeOfDay": 13.5, "Rain": 0.4, "Fog": 0.2, "WindX": 0.3, "WindZ": 0.4, "Quake": 0.5,
             "QuakePhase": "shaking", "QuakeId": 3, "QuakeFell": 2, "NoteId": 7, "NoteText": ' hi  "you" ',
             "NoteX": 4, "NoteZ": 5, "MeteorId": 2, "MeteorX": 1, "MeteorZ": -1, "MeteorSmashed": 3,
             "MeteorThrown": 1.0}
    attrs = {"LastActionResult": "ok", "Hunger": 80, "Health": 90, "Faints": 1, "Hurts": 2, "Hurt": "Meteor",
             "Freed": 1, "Wet": 60, "Cold": True, "InRain": 1, "Sheltered": "roof", "WalkSpeed": 12,
             "ViewForwardX": 0.0, "ViewForwardZ": 1.0, "Bracing": True, "KnockedDown": 0}
    s = snap([ground()], attrs=attrs, clock=clock, others=[("Sky", (0, 0, 0)), ("Ann", (1, 2, 3))], tick=9)
    assert s.tick == 9 and s.has_world
    assert s.last_result == "ok" and s.hunger == 80 and s.health == 90 and s.faints == 1
    assert (s.hurts, s.hurt_by, s.freed) == (2, "Meteor", 1)
    assert (s.wet, s.cold, s.in_rain, s.sheltered, s.walk_speed) == (60, True, True, "roof", 12)
    assert s.facing == (0.0, 1.0)
    assert s.others == [("Ann", (1, 2, 3))]
    assert s.time_of_day == 13.5 and s.rain == 0.4 and s.fog == 0.2 and s.wind == pytest.approx(0.5)
    assert (s.quake, s.quake_phase, s.quake_id, s.quake_fell) == (0.5, "shaking", 3, 2)
    assert s.note_id == 7 and s.note_text == "hi 'you'" and s.note_at == (4, 0, 5)
    assert s.meteor_id == 2 and s.meteor_at == (1, 0, -1)
    assert s.meteor_did == {"Smashed": 3, "Thrown": 1, "Unfastened": 0, "Felled": 0, "Hurt": 0}
    assert s.bracing and not s.knocked_down


def test_snapshot_without_a_clock_or_world():
    s = Snapshot({})
    assert not s.has_world and s.me == (0, 0, 0) and s.facing is None
    assert s.time_of_day is None and s.rain == 0 and s.fog == 0 and s.wind == 0
    assert s.quake == 0 and s.quake_phase == "" and s.quake_id is None and s.note_text == ""
    assert s.note_at == (0, 0, 0) and s.meteor_id is None and s.faints == 0
    assert s.ground_top(0, 0) is None
    assert s.surface(0, 0) == (None, None)
    assert s.column("Nothing") == []


def test_snapshot_lookups():
    mesa = ent("Mesa_1", (20, 5, 0), (10, 10, 10), role="Mesa")
    peak_a = ent("Peak_1", (-30, 10, 0), (10, 20, 10), role="Mesa", attrs={"Feature": "Peak"})
    peak_b = ent("Peak_2", (-30, 22, 0), (4, 4, 4), role="Mesa", attrs={"Feature": "Peak"})
    tree = ent("Tree_1", (0, 5, 20), (2, 10, 2), role="Tree")
    shadow = ent("SkyShadow_1", (5, 0.05, 5), (3, 0.1, 3), role="SkyShadow")
    ladder = ent("Ladder_1", (2.5, 3.75, 0), (2, 7.5, 0.4))
    held = block("Block_9", 0, 2.55 + 4.0, 0)
    entities = [ground(), mesa, peak_a, peak_b, tree, shadow, ladder, held,
                block("Block_1", 5, 1.25, 0), block("Block_2", 5, 3.75, 0), block("Block_3", 5, 6.25, 0),
                block("Block_4", 5, 11.25, 0),  # a gap below it: its own column
                block("Block_5", -5, 1.25, 0)]
    s = snap(entities)
    assert {e.name for e in s.movables()} >= {"Ladder_1", "Block_1", "Block_9"}
    assert "Ladder_1" not in {e.name for e in s.cubes()}
    assert {e.name for e in s.terrain()} == {"Ground", "Mesa_1", "Peak_1", "Peak_2", "Tree_1"}
    assert s.terrain() is s.terrain()  # worked out once
    marks = s.landmarks()
    assert [getattr(m, "name") for m in marks][0] == "Peak" and {m.name for m in marks} == {"Peak", "Mesa_1", "Tree_1"}
    assert s.landmarks() is marks
    assert [e.name for e in s.sky_shadows()] == ["SkyShadow_1"]
    assert s.held().name == "Block_9" and s.held() is s.held()
    assert s.ground_top(20, 0) == 10 and s.ground_top(0, 0) == 0 and s.ground_top(500, 500) is None
    top, e = s.surface(5, 0)
    assert top == 12.5 and e.name == "Block_4"
    top, e = s.surface(5, 0, below=8)
    assert top == 7.5 and e.name == "Block_3"
    assert s.surface(900, 0) == (None, None)
    names = {sd[5].name for sd in s.standables()}
    assert "Block_9" not in names and "Ladder_1" not in names and "Block_1" in names
    assert {sd[5].name for sd in s.standables(below=1)} == {"Ground"}
    assert [c.name for c in s.column("Block_2")] == ["Block_1", "Block_2", "Block_3"]
    assert [c.name for c in s.column("Block_4")] == ["Block_4"]
    assert [c.name for c in s.column("Mesa_1")] == ["Mesa_1"]  # not a cube: itself
    assert s.stacks() == [((5.0, 0.0), ["Block_1", "Block_2", "Block_3"])]


def test_nothing_held():
    s = snap([ground(), block("Block_1", 3, 1.25, 0)])
    assert s.held() is None


def test_piece_kinds():
    s = snap([block("Block_1", 0, 1.25, 0), ent("Stone_1", size=(2.5, 2.5, 2.5)), ent("Log_1", size=(7.5, 1, 1)),
              ent("Boulder_1", size=(4, 4, 4)), ent("Meteor_1", size=(2.5, 2.5, 2.5))])
    kinds = {k: sorted(e.name for e in s.movables() if test(e)) for k, test in w.PIECE_KINDS.items()}
    assert kinds["cube"] == ["Block_1", "Meteor_1", "Stone_1"]
    assert kinds["stone"] == ["Meteor_1", "Stone_1"]
    assert kinds["log"] == ["Log_1"] and kinds["boulder"] == ["Boulder_1"]


def test_world_client_round_trip(world_server):
    obs = raw_obs([ground(), block("Block_1", 0, 1.25, 0)], tick=4)
    world_server.replies[("POST", "/join")] = {"session": "abc"}
    world_server.replies[("GET", "/observe")] = obs
    world_server.replies[("POST", "/input")] = obs
    world_server.replies[("POST", "/chat")] = {}
    world_server.replies[("GET", "/chat/messages")] = {"messages": [{"id": "1", "content": "hi"}]}
    world_server.replies[("GET", "/api.md")] = b"# api"
    world = World(world_server.url + "/", name="God ling")
    world.wait_until_up(seconds=5)
    assert world.join() == {"session": "abc"} and world.session == "abc"
    assert world_server.requests[-1]["query"] == "name=God%20ling"
    assert world.observe().tick == 4
    assert world.act("Jump").tick == 4
    sent = world_server.requests[-1]
    assert sent["body"] == {"type": "Jump", "data": {}} and sent["headers"]["X-Session"] == "abc"
    world.say("x" * 600)
    assert len(world_server.requests[-1]["body"]["content"]) == 480
    assert world.chat_since() == [{"id": "1", "content": "hi"}]
    assert world_server.requests[-1]["query"] == "limit=20"
    world.chat_since(after="1", limit=5)
    assert world_server.requests[-1]["query"] == "limit=5&after=1"


def test_world_act_falls_back_to_observe_when_input_returns_no_world(world_server):
    world_server.replies[("POST", "/input")] = {"ok": True}
    world_server.replies[("GET", "/observe")] = raw_obs([ground()], tick=8)
    world = World(world_server.url)
    assert world.act("Wait", {"seconds": 1}).tick == 8
    assert world_server.requests[0]["body"] == {"type": "Wait", "data": {"seconds": 1}}


def test_world_empty_replies_and_errors(world_server):
    world_server.replies[("GET", "/chat/messages")] = b""
    world = World(world_server.url)
    assert world.chat_since() == []
    with pytest.raises(WorldError, match="GET /nowhere"):
        world._request("GET", "/nowhere")  # 404


def test_wait_until_up_gives_up(monkeypatch):
    clock = iter(range(0, 100, 10))
    monkeypatch.setattr(w.time, "time", lambda: next(clock))
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    world = World("http://127.0.0.1:9")  # nothing listens there
    with pytest.raises(WorldError, match="did not come up within 30s"):
        world.wait_until_up(seconds=30)


def test_snapshot_raw_is_kept():
    raw = raw_obs([ground()])
    assert Snapshot(raw).raw is raw
    assert json.loads(json.dumps(raw))  # what the server sends is plain JSON


def test_a_meteors_stone_and_its_iron_as_the_eye_tells_them():
    """METEORIC IRON (main.lua sky.iron): what a thing is like, never what it is for."""
    hot = Entity(ent("Meteor_3", attrs={"Heat": 0.35, "RenderRole": "Stone"}))
    dark = Entity(ent("Meteor_4", attrs={"Heat": w.GLOWS_ABOVE, "RenderRole": "Stone"}))
    old = Entity(ent("Meteor_1", attrs={"RenderRole": "Stone"}))  # from before stones cooled: no Heat
    assert hot.glowing and not dark.glowing and not old.glowing
    assert hot.look == "glowing hot" and dark.look == old.look == "dark, heavy, metallic"
    flake = Entity(ent("Iron_2", size=(0.5, 0.2, 1.0), role="Iron"))
    assert flake.movable and "dark metal" in flake.look and not flake.glowing
    assert Entity(ent("Spear_1", role="Tool", attrs={"Edge": "Iron"})).look == "with an edge of dark metal bound on"
    assert Entity(ent("Spear_2", role="Tool")).look == "" and Entity(ent("Block_1")).look == ""
    assert Entity(ent("Block_2", attrs={"Heat": "hot"})).glowing is False
