#!/usr/bin/env python3
"""God bot: now and then, the sky does something. A stand-in for the viewers during long runs (the user's wish: god
events, but rarely). It joins the world as the bodiless "Sky", like tools/guest_panel.py, calls one of the world's sky
powers at long random intervals, and logs what it did, so the run can be read against it afterwards.

    python3 tools/god_bot.py --world http://localhost:8092 [--every 25-55] [--first 10] [--hours 8.5]
                             [--log ~/godling-runs/<run>/god_bot.jsonl]

The world chooses where (near Godling, in view, clear of what it built); the bot only chooses what and when.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guest_panel import Sky, describe  # noqa: E402

# How often each power is chosen: the dramatic ones most, the gifts now and then.
WEIGHTS = {"Meteor": 3, "Lightning": 3, "Stone": 2, "Log": 2, "Regrow": 1}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--world", default="http://localhost:8092")
    ap.add_argument("--every", default="25-55", help="minutes between events: each wait is drawn from this range")
    ap.add_argument("--first", type=float, default=10, help="minutes before the first event")
    ap.add_argument("--hours", type=float, default=8.5, help="stop after this long")
    ap.add_argument("--log", help="append one JSON line per event here")
    args = ap.parse_args()
    lo, hi = (float(v) for v in args.every.split("-"))
    log = Path(args.log).expanduser() if args.log else None
    rng = random.Random()
    sky = Sky(args.world)
    end = time.time() + args.hours * 3600
    wait = args.first * 60
    print(f"God bot: first event in {args.first:g} min, then every {lo:g}-{hi:g} min, for {args.hours:g} h.", flush=True)
    while time.time() + wait < end:
        time.sleep(wait)
        tried = []
        for _ in range(3):  # a power that cannot happen now (no stump to regrow, no clear spot) gives way to another
            power = rng.choices([p for p in WEIGHTS if p not in tried],
                                weights=[w for p, w in WEIGHTS.items() if p not in tried])[0]
            tried.append(power)
            result = sky.call(power)
            ok, text = describe(power, result)
            print(f"[{time.strftime('%H:%M:%S')}] {'GOD ' if ok else 'GOD?'} {text}", flush=True)
            if log:
                with log.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"time": time.time(), "power": power, "ok": ok, "result": result}) + "\n")
            if ok or "World" in result:
                break
        wait = rng.uniform(lo, hi) * 60


if __name__ == "__main__":
    main()
