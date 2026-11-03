"""Run folders as run_godling.py and `clawblox run --record` leave them, built by hand for the tools' tests."""
import json
import sqlite3

import pytest


def compressor():
    try:
        from compression import zstd  # Python 3.14+
        return zstd.compress
    except ImportError:
        pass
    try:
        import zstandard
        return zstandard.ZstdCompressor().compress
    except ImportError:
        pytest.skip("needs a zstd compressor (Python 3.14, or pip install zstandard)")


def recording(path, checkpoints, inputs, meta=None):
    """A .clawrec: the meta table, the inputs, and zstd-compressed JSON checkpoints [(tick, time_ms, observation)]."""
    path.parent.mkdir(parents=True, exist_ok=True)
    compress = compressor()
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    db.execute("CREATE TABLE inputs (tick INTEGER, time_ms INTEGER, agent_id TEXT, input_type TEXT, data TEXT)")
    db.execute("CREATE TABLE checkpoints (tick INTEGER, time_ms INTEGER, data BLOB)")
    db.executemany("INSERT INTO meta VALUES (?, ?)", list((meta or {"tick_rate": "30", "game": "mesa"}).items()))
    db.executemany("INSERT INTO inputs VALUES (?, ?, ?, ?, ?)", inputs)
    db.executemany("INSERT INTO checkpoints VALUES (?, ?, ?)",
                   [(tick, t, compress(json.dumps(obs).encode())) for tick, t, obs in checkpoints])
    db.commit()
    db.close()
    return path


def body(x, result=None, pid="p1"):
    return {"id": pid, "position": [x, 2.5, 0], "attributes": {"LastActionResult": result} if result else {}}


def cube(x, y, z, size=0.75):
    return {"position": [x, y, z], "size": [size, size, size]}


def standard_recording(run):
    """A body walking (0.5 units a second) and stacking three cubes, with inputs every few seconds."""
    checkpoints = []
    for k in range(13):  # every 4 s
        t = k * 4_000
        stack = [cube(0, 0.375 + 0.75 * n, 0) for n in range(min(3, k // 4 + 1))]
        checkpoints.append((k * 300, t, {"players": [body(k * 2.0, "PlaceSuccess" if k % 3 else "PickupSuccess"),
                                                     body(0, None, "p2")],
                                         "entities": stack + [cube(9, 0.375, 9), {"position": [1, 1, 1]}]}))
    checkpoints.append((9999, 130_000, {"players": [body(26.0, pid="p1")], "entities": []}))  # a gap: not motion
    checkpoints.append((9999, 130_000, {"players": []}))
    inputs = [(k * 30, k * 1000 + (0 if k < 60 else 3_700_000), "a1", ("MoveTo", "Place", "Pickup")[k // 3 % 3], "{}")
              for k in range(0, 120, 3)]
    return recording(run / "recordings" / "r1.clawrec", checkpoints, inputs)


def mind_log(run, entries):
    path = run / "mind" / "log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n\n")
    return path


def standard_mind_log(run, with_projects=True):
    entries = [
        {"time": 0, "kind": "llm", "purpose": "decide", "latency": 10, "cache_hit": 100, "cache_miss": 50, "output": 20,
         "cost": 0.01, "reasoning": 400, "finish": "stop"},
        {"time": 5, "kind": "llm", "purpose": "sleep", "latency": 20, "cache_hit": 0, "cache_miss": 10, "output": 5,
         "cost": 0.002, "finish": "length"},
        {"time": 10, "kind": "decision", "thought": "A shadow on the sand!",
         "projects": [{"intention": "look at the meteor", "goal": "see", "steps": [{"skill": "walk_to"}]}]},
        {"time": 11, "kind": "decision", "project": {"steps": [1, 2]}},
        {"time": 12, "kind": "event", "text": "A dark shadow", "sky": "Meteor", "sky_id": 1, "sky_stage": "warning"},
        {"time": 13, "kind": "glance", "sky": "Meteor", "sky_id": 1, "turned": True, "degrees": 40},
        {"time": 40, "kind": "event", "text": "A stone fell", "sky": "Meteor", "sky_id": 1, "sky_stage": "arrived",
         "entities": ["Meteor_1"]},
        {"time": 60, "kind": "skill", "skill": "pick_up", "ok": True, "seconds": 5, "args": {"object": "Meteor_1"}},
        {"time": 70, "kind": "skill", "skill": "wait", "ok": True, "seconds": 3, "args": {"seconds": 3}},
        {"time": 80, "kind": "skill", "skill": "fasten", "ok": False, "seconds": 2, "learned": True, "args": {}},
        {"time": 90, "kind": "event", "text": "Lightning", "sky": "Lightning", "sky_id": 2, "sky_stage": "arrived",
         "entities": ["Log_9"]},
        {"time": 100, "kind": "event", "text": "Rumbling", "sky": "Earthquake", "sky_id": 3, "sky_stage": "warning"},
        {"time": 102, "kind": "brace", "ok": True, "sky_id": 3},
        {"time": 103, "kind": "brace", "ok": True, "sky_id": 3},
        {"time": 104, "kind": "brace", "ok": False, "sky_id": 4},
        {"time": 110, "kind": "event", "text": "A new object"},
        {"time": 120, "kind": "wait_for_mind", "seconds": 30},
        {"time": 130, "kind": "plan_discarded"}, {"time": 131, "kind": "plan_kept"},
        {"time": 140, "kind": "sleep"},
        {"time": 150, "kind": "structures", "pieces_built_in": 3, "walls": 1, "enclosures": 0, "roofed": 0, "spans": 0,
         "posts": 1, "floors": 0, "largest_structure": 3, "fastened": 1, "tallest": 5.0, "highest": 5.0},
        {"time": 3800, "kind": "structures", "pieces_built_in": 7, "walls": 2, "enclosures": 1, "roofed": 1, "spans": 1,
         "posts": 1, "floors": 1, "largest_structure": 7, "fastened": 3, "tallest": 7.5, "highest": 8.0},
    ]
    if with_projects:
        entries += [{"time": 3900, "kind": "project", "phase": "end", "ok": True, "seconds": 50},
                    {"time": 3950, "kind": "project", "phase": "end", "ok": False, "seconds": 20}]
    return mind_log(run, entries)
