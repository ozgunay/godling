#!/usr/bin/env python3
"""Tallest block stack over time, measured from a Clawblox recording (Mesa Island cubes).

Usage (inside WSL):  python3 stack_timeline.py ~/godling-runs/a-003 [~/godling-runs/a-004 ...]

A cube counts as stacked when another cube sits directly beneath it (same column, one cube
lower). Uses the recording's ~1 Hz full checkpoints, sampled every 30 s.
"""
import glob
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_run import zstd_decoder  # noqa: E402

CUBE = 0.75
SAMPLE_EVERY_S = 30


def cubes(obs):
    out = []
    for e in obs.get("entities", []):
        size = e.get("size") or [0, 0, 0]
        if all(abs(s - CUBE) < 0.05 for s in size):
            out.append(e["position"])
    return out


def tallest_stack(positions):
    below = {}
    for i, (x, y, z) in enumerate(positions):
        for j, (x2, y2, z2) in enumerate(positions):
            if i != j and abs(x - x2) < 0.45 and abs(z - z2) < 0.45 and 0.55 < y - y2 < 0.95:
                below[i] = j
                break
    best = 1 if positions else 0
    for i in range(len(positions)):
        height, j = 1, i
        while j in below and height <= len(positions):
            j = below[j]
            height += 1
        best = max(best, height)
    return best, len(below)


def timeline(run_dir):
    rec = sorted(glob.glob(str(Path(run_dir).expanduser() / "recordings/*.clawrec")), key=lambda p: Path(p).stat().st_size)[-1]
    db = sqlite3.connect(f"file:{rec}?mode=ro", uri=True)
    decode = zstd_decoder()
    if decode is None:
        sys.exit("needs a zstd decoder (apt install zstd)")
    rows = db.execute("SELECT time_ms, data FROM checkpoints ORDER BY time_ms").fetchall()
    t0, last = rows[0][0], -SAMPLE_EVERY_S * 1000
    points = []
    for t, blob in rows:
        if t - last < SAMPLE_EVERY_S * 1000:
            continue
        last = t
        pos = cubes(json.loads(decode(blob)))
        tallest, stacked = tallest_stack(pos)
        points.append(((t - t0) / 60000, tallest, stacked, len(pos)))
    return points


for run in sys.argv[1:]:
    pts = timeline(run)
    print(f"=== {Path(run).name}: {pts[-1][0]:.0f} min recorded")
    peak = max(pts, key=lambda p: p[1])
    print(f"peak stack: {peak[1]} cubes at {peak[0]:.1f} min; cubes left at end: {pts[-1][3]}")
    shown = -1
    for minute, tallest, stacked, n in pts:
        if int(minute // 5) != shown:  # one line per 5 minutes
            shown = int(minute // 5)
            print(f"  {minute:5.1f} min  tallest {tallest}  stacked cubes {stacked}  cubes {n}")
