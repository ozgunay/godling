#!/usr/bin/env python3
"""Compare run_godling.py runs side by side (ADR-002 D5).

Usage (inside WSL):  python3 compare_runs.py [--minute N] ~/godling-runs/m-003 ~/godling-runs/m-004 ...

--minute N compares every run at its Nth minute (ADR-030): the mind's log and the placements are cut there; the rows
read from the recording's motion and stacks say "(whole run)".

Rows: body busy share, motion share, waiting for the mind, decision speed and reasoning tokens,
placements per hour (and per hour of the run, to see decay), tallest stack, cost.
"""
import glob
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import analyze_run as ar  # noqa: E402
from stack_timeline import timeline  # noqa: E402


def stats(run, minute=None):
    run = Path(run).expanduser()
    m = ar.analyze_mind_log(run / "mind/log.jsonl", until_s=None if minute is None else minute * 60)
    hours = m["span_s"] / 3600 or 1e-9
    whole = " (whole run)" if minute is not None else ""
    rec = sorted(glob.glob(str(run / "recordings/*.clawrec")), key=lambda p: Path(p).stat().st_size)[-1]
    r = ar.analyze_recording(Path(rec))
    db = sqlite3.connect(f"file:{rec}?mode=ro", uri=True)
    first = db.execute("SELECT MIN(time_ms) FROM inputs").fetchone()[0] or 0
    per_hour = Counter(int((t - first) // 3600000) for (t,) in db.execute("SELECT time_ms FROM inputs WHERE input_type='Place'")
                       if minute is None or t - first <= minute * 60000)
    stacks = timeline(run)
    cfg = json.loads((run / "config.json").read_text()) if (run / "config.json").exists() else {}
    return {
        "setup": f"{cfg.get('memory', 'native')}, agenda={cfg.get('agenda', 'False')}, walk={cfg.get('walk_speed', '16')}",
        "minutes": f"{m['span_s'] / 60:.0f}",
        "body busy": f"{m['busy_s'] / (m['span_s'] or 1):.0%}",
        "moving (motion duty)" + whole: f"{(r['motion'] or {}).get('duty_cycle') or 0:.0%}",
        "waited for mind": f"{m['waited_s'] / (m['span_s'] or 1):.0%}" if m["waited_s"] else "n/a",
        "decide latency p50": ar.fmt_s(ar.pct(m["decide_latency"], 50)),
        "decide latency p90": ar.fmt_s(ar.pct(m["decide_latency"], 90)),
        "waits over a minute": str(m["long_waits"]),
        "stop-gaps run / finished": f"{m['stopgaps']} / {m['stopgaps_ok']}",  # ADR-030
        "first projects finished (after stop-gaps)": "{} ({})".format(
            *(f"{ok / n:.0%}" if n else "n/a" for ok, n in (m["first_projects"]["otherwise"],
                                                             m["first_projects"]["after_stopgap"]))),
        "reasoning tokens/decision": f"{sum(m['reasoning']) / len(m['reasoning']):.0f}" if m["reasoning"] else "n/a",
        "decisions/h": f"{m['decisions'] / hours:.0f}",
        "projects/h": f"{m['projects'] / hours:.0f}",
        "projects finished": f"{m['projects_ok'] / (m['projects'] or 1):.0%}",
        "steps planned/decision": f"{sum(m['planned_steps']) / len(m['planned_steps']):.1f}" if m["planned_steps"] else "n/a",
        "plans discarded / kept": f"{m['discarded']} / {m['kept_after_failure']}",
        "answers cut off": str(m["cut_off"]),
        "answers given from the reasoning": str(m["answers_forced"]),
        "placements/h": f"{sum(per_hour.values()) / hours:.0f}",
        "placements by hour": " ".join(str(per_hour[h]) for h in sorted(per_hour)),
        "tallest stack" + whole: str(max((p[1] for p in stacks), default=0)),
        **structure_rows(m, hours),
        "cost $/h": f"{m['cost'] / hours:.2f}",
        "cost $/h by purpose": ", ".join(f"{k} {v / hours:.2f}" for k, v in sorted(m["cost_by"].items(),
                                                                                   key=lambda kv: -kv[1])),
        "house best score / stood": "n/a" if m["house_best"] is None else
        f"{m['house_best']} / {'yes' if m['house_built'] else 'no'}",
        "+ memory engine $/h (est.)": hindsight_cost(run, hours),
    }


def structure_rows(m, hours):
    """What stands at the end of the run (ADR-004 measures), and how much was built in, hour by hour."""
    s = m["structures"]
    if not s:
        return {k: "n/a" for k in ("walls / enclosures / roofed", "spans / posts / floors", "largest structure / fastened",
                                   "tallest / highest built", "pieces built in, by hour")}
    end = s[-1]
    first = s[0]["time"]
    by_hour = {}
    for e in s:  # the last measure in each hour of the run
        by_hour[int((e["time"] - first) // 3600)] = e["pieces_built_in"]
    return {
        "walls / enclosures / roofed": f"{end['walls']} / {end['enclosures']} / {end['roofed']}",
        "spans / posts / floors": f"{end['spans']} / {end['posts']} / {end['floors']}",
        "largest structure / fastened": f"{end['largest_structure']} / {end['fastened']}",
        "tallest / highest built": f"{end['tallest']} / {end['highest']}",
        "pieces built in, by hour": " ".join(str(by_hour[h]) for h in sorted(by_hour)),
    }


def hindsight_cost(run, hours):
    """Hindsight's own DeepSeek calls (fact extraction, consolidation) are not in the mind's cost.

    Its log gives input tokens per consolidation batch of this run's bank; output and cache shares
    come from the calls it logs in full ("slow llm call"). An estimate, at off-peak prices."""
    log = run / "hindsight.log"
    if not log.exists():
        return "-"
    text = log.read_text(errors="replace")
    batch_in = sum(int(n) for n in re.findall(rf"bank=godling-{re.escape(run.name)} llm_batch.*?input_tokens=~(\d+)", text))
    full = [tuple(int(v or 0) for v in t) for t in
            re.findall(r"llm call: scope=\w+.*?input_tokens=(\d+), output_tokens=(\d+), total_tokens=\d+(?:, cached_tokens=(\d+))?", text)]
    extract_in = sum(int(n) for n in re.findall(r"scope=retain_extract_facts.*?input_tokens=(\d+)", text))
    fin, fout, fcached = (sum(t[i] for t in full) for i in range(3)) if full else (1, 0, 0)
    tokens_in = batch_in + extract_in
    cached = tokens_in * fcached / fin
    cost = (tokens_in - cached) * 0.15e-6 + cached * 0.003e-6 + tokens_in * fout / fin * 0.60e-6
    return f"{cost / hours:.2f}"


args = sys.argv[1:]
minute = None
if args[:1] == ["--minute"]:
    minute, args = float(args[1]), args[2:]
runs = args
rows = [stats(r, minute) for r in runs]
keys = list(rows[0])
width = max(len(k) for k in keys)
print(" " * width + " | " + " | ".join(Path(r).name.ljust(18) for r in runs))
for k in keys:
    print(k.ljust(width) + " | " + " | ".join(str(row[k]).ljust(18) for row in rows))
