#!/usr/bin/env python3
"""Baseline metrics for one Clawblox run (Godling plan P1, arm A).

Usage (inside WSL):
    python3 /mnt/c/Work/godling/tools/analyze_run.py ~/godling-runs/a-002 [--price IN,CACHE_WRITE,CACHE_READ,OUT]

Reads only. Sources:
  recordings/*.clawrec  SQLite written by `clawblox run --record` (server-side ground truth)
  agent/**/*.jsonl      Claude Code transcripts (think time, tokens, tool usage)
  agent/workspace/      memory files the agent maintains

Writes <run>/analysis/report.md and actions.csv, and prints the report.
"""
import argparse
import csv
import json
import math
import re
import shutil
import sqlite3
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ARGS = argparse.Namespace(price_key=None)

# USD per million tokens: input, cache write (5 min TTL), cache read, output.
PRICES = {
    "claude-opus-4": (5.00, 6.25, 0.50, 25.00),
    "claude-sonnet-4": (3.00, 3.75, 0.30, 15.00),
    "claude-haiku-4": (1.00, 1.25, 0.10, 5.00),
    "deepseek": (0.15, 0.15, 0.003, 0.60),
}
WORLD_ACTIONS = ("MoveTo", "Jump", "Stop", "Pickup", "Place", "Throw")
# Tolerate shell-escaped quotes (\"type\":\"MoveTo\") and plain-text output (LastActionResult: Ready).
ACTION_RE = re.compile(r'\\?"type\\?"\s*:\s*\\?"(' + "|".join(WORLD_ACTIONS) + r')\\?"')
RESULT_RE = re.compile(r'LastActionResult\\?"?\s*[:=]\s*\\?"?([A-Za-z]+(?::[A-Za-z]+)?)')
SCRIPT_ACTION_RE = re.compile(r"\b(act|observe|move\w*|pickup|place|throw|jump)\s*\(", re.I)
AUTO_CONTINUE = "Just continue doing whatever you want to do"  # Clawblox stop-hook message
GAP_BUCKETS = [(0, 2), (2, 5), (5, 10), (10, 30), (30, 60), (60, 300), (300, math.inf)]
MOVING_SPEED = 0.5  # studs per second; below this the character counts as standing still


def pct(values, p):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def fmt_s(v):
    if v is None:
        return "n/a"
    return f"{v:.1f}s" if v < 120 else f"{v / 60:.1f}min"


def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def zstd_decoder():
    try:
        from compression import zstd  # Python 3.14+

        return zstd.decompress
    except ImportError:
        pass
    try:
        import zstandard

        d = zstandard.ZstdDecompressor()
        return lambda blob: d.decompress(blob, max_output_size=256 * 1024 * 1024)
    except ImportError:
        pass
    if shutil.which("zstd"):
        return lambda blob: subprocess.run(
            ["zstd", "-dc"], input=blob, capture_output=True, check=True
        ).stdout
    return None


# --- server side -------------------------------------------------------------


def analyze_recording(path):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    meta = dict(db.execute("SELECT key, value FROM meta"))
    tick_rate = int(meta.get("tick_rate", 60))
    inputs = db.execute(
        "SELECT tick, time_ms, agent_id, input_type, data FROM inputs ORDER BY tick, time_ms"
    ).fetchall()
    first_ms, last_ms = db.execute("SELECT MIN(time_ms), MAX(time_ms) FROM checkpoints").fetchone()
    out = {
        "path": path,
        "meta": meta,
        "tick_rate": tick_rate,
        "inputs": inputs,
        "duration_s": ((last_ms or 0) - (first_ms or 0)) / 1000,
        "start_ms": first_ms or 0,
        "size_mb": path.stat().st_size / 1e6,
    }

    decode = zstd_decoder()
    if decode is None:
        out["motion"] = None
        return out
    samples = []
    for tick, time_ms, blob in db.execute("SELECT tick, time_ms, data FROM checkpoints ORDER BY tick"):
        obs = json.loads(decode(blob))
        for p in obs.get("players", []):
            samples.append((time_ms / 1000, p["id"], p["position"], (p.get("attributes") or {})))
    out["motion"] = motion_from_samples(samples)
    return out


def motion_from_samples(samples):
    by_player = defaultdict(list)
    for t, pid, pos, attrs in samples:
        by_player[pid].append((t, pos, attrs))
    moving = total = 0.0
    results = Counter()
    for rows in by_player.values():
        last_result = None
        for (t0, p0, _), (t1, p1, a1) in zip(rows, rows[1:]):
            dt = t1 - t0
            if dt <= 0 or dt > 5:
                continue
            total += dt
            if math.dist(p0, p1) / dt >= MOVING_SPEED:
                moving += dt
            r = a1.get("LastActionResult")
            if r and r != last_result:
                results[r] += 1
                last_result = r
    return {"duty_cycle": moving / total if total else None, "sampled_s": total, "result_changes": results}


# --- agent side --------------------------------------------------------------


def find_transcripts(agent_dir):
    seen = {}
    for p in agent_dir.rglob("*.jsonl"):
        if p.name == "events.jsonl" or "EPISODIC" in p.name.upper() or "workspace" in p.parts:
            continue
        try:
            with p.open(encoding="utf-8") as f:
                head = f.readline()
            if '"sessionId"' not in head and '"type"' not in head:
                continue
        except OSError:
            continue
        # The same transcript may exist live in sandbox-home and as a copy in session/.
        key = p.name
        if key not in seen or p.stat().st_size > seen[key].stat().st_size:
            seen[key] = p
    return sorted(seen.values())


def tool_result_text(block):
    c = block.get("content")
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c if isinstance(b, dict))
    return str(c or "")


def classify_tool(name, inp):
    if name != "Bash":
        return "workspace" if name in ("Read", "Write", "Edit", "Glob", "Grep", "NotebookEdit") else "other"
    cmd = inp.get("command", "")
    if "/input" in cmd:
        return "world:act"
    if "/observe/image" in cmd:
        return "world:look"
    if "/observe" in cmd or "/chat" in cmd or "/api.md" in cmd or "/join" in cmd:
        return "world:observe"
    # Agents often write their own helper library and drive the world from short scripts.
    if re.search(r"\b(python3?|node)\b", cmd) and SCRIPT_ACTION_RE.search(cmd):
        return "world:script"
    return "workspace"


def analyze_transcripts(paths):
    usage_by_msg = {}
    msg_first_ts = {}
    models = Counter()
    tools = Counter()
    tool_uses = {}
    results = Counter()
    events = []  # (ts, kind) in file order, kind in {"user", "assistant"}
    continues = 0
    for path in paths:
        for line in path.open(encoding="utf-8"):
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind, ts = o.get("type"), o.get("timestamp")
            # The phrase also sits in the system prompt, which api-request* lines and
            # prompt snapshots repeat; only count it where it was delivered to the agent.
            if (
                AUTO_CONTINUE in line
                and kind in ("user", "attachment", "system")
                and (o.get("attachment") or {}).get("type") != "prompt_snapshot"
            ):
                continues += 1
            if kind not in ("user", "assistant") or not ts:
                continue
            t = parse_ts(ts)
            msg = o.get("message") or {}
            content = msg.get("content")
            if kind == "assistant":
                mid = msg.get("id") or o.get("uuid")
                if mid not in msg_first_ts:
                    msg_first_ts[mid] = t
                    events.append((t, "assistant"))
                    models[msg.get("model", "?")] += 1
                if msg.get("usage"):
                    usage_by_msg[mid] = (msg.get("model", "?"), msg["usage"])
                for b in content if isinstance(content, list) else []:
                    if b.get("type") == "tool_use":
                        cat = classify_tool(b.get("name"), b.get("input") or {})
                        tools[cat] += 1
                        inp = b.get("input") or {}
                        n_actions = len(ACTION_RE.findall(inp.get("command") or json.dumps(inp)))
                        tool_uses[b.get("id")] = (cat, n_actions)
            else:
                events.append((t, "user"))
                for b in content if isinstance(content, list) else []:
                    if b.get("type") == "tool_result" and tool_uses.get(b.get("tool_use_id"), ("",))[0] == "world:act":
                        results.update(RESULT_RE.findall(tool_result_text(b)))

    # Think time: from the latest user/tool_result line to the next assistant message.
    think = []
    last_user = None
    for t, kind in sorted(events):
        if kind == "user":
            last_user = t
        elif last_user is not None:
            think.append(t - last_user)
            last_user = None

    tokens = Counter()
    cost = 0.0
    priced = True
    for model, u in usage_by_msg.values():
        if model.startswith("<"):  # Claude Code's own "<synthetic>" messages cost nothing
            continue
        tin = u.get("input_tokens", 0)
        cw = u.get("cache_creation_input_tokens", 0)
        cr = u.get("cache_read_input_tokens", 0)
        tout = u.get("output_tokens", 0)
        tokens.update({"input": tin, "cache_write": cw, "cache_read": cr, "output": tout})
        price = PRICES.get(ARGS.price_key) if ARGS.price_key else None
        if price is None:
            price = next((v for k, v in PRICES.items() if model.startswith(k)), None)
        if price is None:
            priced = False
            continue
        cost += (tin * price[0] + cw * price[1] + cr * price[2] + tout * price[3]) / 1e6

    span = (max(t for t, _ in events) - min(t for t, _ in events)) if events else 0
    return {
        "paths": paths,
        "models": models,
        "calls": len(usage_by_msg),
        "tokens": tokens,
        "cost": cost if priced else None,
        "think": think,
        "tools": tools,
        "actions_in_commands": sum(n for _, n in tool_uses.values()),
        "act_commands": sum(1 for c, _ in tool_uses.values() if c == "world:act"),
        "results": results,
        "continues": continues,
        "span_s": span,
    }


def analyze_mind_log(path, until_s=None):
    """Stats from the layered mind's own log (mind/log.jsonl), when the run used run_godling.py.

    `until_s`: only the run's first seconds, so arms are compared at the same elapsed minute (ADR-030, 80-AB11)."""
    entries = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    span = (entries[-1]["time"] - entries[0]["time"]) if len(entries) > 1 else 0
    if until_s is not None and entries:
        entries = [e for e in entries if e["time"] - entries[0]["time"] <= until_s]
        span = min(span, until_s)
    llm = [e for e in entries if e["kind"] == "llm"]
    skills = [e for e in entries if e["kind"] == "skill"]
    by_skill = {}
    for s in skills:
        ok, total = by_skill.get(s["skill"], (0, 0))
        by_skill[s["skill"]] = (ok + bool(s["ok"]), total + 1)
    ends = [e for e in entries if e["kind"] == "project" and e.get("phase") == "end"]
    busy = sum(e["seconds"] for e in ends)  # the body at work, on stop-gaps too
    if not ends:  # older runs (m-001..m-003) have no project entries: approximate with top-level skills
        busy = sum(s["seconds"] for s in skills if s.get("learned") or s["skill"] not in ("wait",))
    decide = [e for e in llm if e["purpose"] == "decide"]
    stopgaps = [e for e in ends if e.get("stopgap")]  # ADR-030: counted apart from the planned projects (80-CDE6)
    projects = [e for e in ends if not e.get("stopgap")]
    forced = [e for e in entries if e["kind"] == "answer_forced"]
    cost_by = Counter()
    for e in llm:
        cost_by[e["purpose"]] += e["cost"]
    house = [e for e in entries if e["kind"] == "house"]
    return {
        "span_s": span,
        "busy_s": min(busy, span),
        "waited_s": sum(e["seconds"] for e in entries if e["kind"] == "wait_for_mind"),
        "projects": len(projects) or sum(1 for e in entries if e["kind"] == "decision"),
        "projects_ok": sum(1 for e in projects if e.get("ok")),
        "discarded": sum(1 for e in entries if e["kind"] == "plan_discarded"),
        "kept_after_failure": sum(1 for e in entries if e["kind"] == "plan_kept"),
        "structures": [e for e in entries if e["kind"] == "structures"],  # ADR-004 measures, every 5 minutes
        "planned_steps": [sum(len(p.get("steps", [])) for p in e.get("projects") or [e.get("project") or {}])
                          for e in entries if e["kind"] == "decision"],  # m-003 and older logged one "project"
        "reasoning": [e.get("reasoning", 0) for e in decide if "reasoning" in e],
        "decide_latency": [e["latency"] for e in decide],
        "cut_off": sum(1 for e in llm if e.get("finish") == "length"),
        "answers_forced": sum(1 for e in forced if e.get("ok")),  # given from the reasoning (80-CDE5)
        "answers_forced_failed": sum(1 for e in forced if not e.get("ok")),
        "long_waits": sum(1 for e in entries if e["kind"] == "wait_for_mind" and e["seconds"] > 60),
        "stopgaps": len(stopgaps),
        "stopgaps_ok": sum(1 for e in stopgaps if e.get("ok")),
        "stopgap_s": sum(e["seconds"] for e in stopgaps),
        "stopgaps_dropped": sum(1 for e in entries if e["kind"] == "stopgap" and e.get("phase") == "dropped"),
        "calls": len(llm),
        "purposes": Counter(e["purpose"] for e in llm),
        "latency": [e["latency"] for e in llm],
        "tokens": Counter({"cache_hit": sum(e["cache_hit"] for e in llm), "cache_miss": sum(e["cache_miss"] for e in llm),
                           "output": sum(e["output"] for e in llm)}),
        "cost": sum(e["cost"] for e in llm),
        "cost_by": dict(cost_by),  # the experiment's criteria (ADR-030, 80-SWEEP2)
        "house_best": max((e["score"] for e in house if e.get("phase") == "progress"), default=None),
        "house_built": any(e.get("phase") == "built" for e in house),
        "first_projects": first_projects(entries),
        "decisions": sum(1 for e in entries if e["kind"] == "decision"),
        "events": sum(1 for e in entries if e["kind"] == "event"),
        "sleeps": sum(1 for e in entries if e["kind"] == "sleep"),
        "skills": by_skill,
    }


def first_projects(entries):
    """How often the first planned project of each plan finished: {"after_stopgap": (finished, of),
    "otherwise": (...)}. A plan taken up after stop-gaps did not know what they did (ADR-030, criterion B4)."""
    out = {"after_stopgap": [0, 0], "otherwise": [0, 0]}
    stopgap_since, waiting = False, None
    for e in entries:
        if e["kind"] == "decision":
            waiting, stopgap_since = ("after_stopgap" if stopgap_since else "otherwise"), False
        elif e["kind"] == "project" and e.get("phase") == "end":
            if e.get("stopgap"):
                stopgap_since = True
            elif waiting:
                out[waiting][0] += bool(e.get("ok"))
                out[waiting][1] += 1
                waiting = None
    return {k: tuple(v) for k, v in out.items()}


def mind_report(m):
    hours = m["span_s"] / 3600 or 1e-9
    t = m["tokens"]
    return [
        "## Mind (layered: run_godling.py)",
        f"- Model calls: {m['calls']} ({m['calls'] / hours:.0f}/h): " + ", ".join(f"{k} {v}" for k, v in m["purposes"].items()),
        f"- Latency per call: p50 **{fmt_s(pct(m['latency'], 50))}**, p95 {fmt_s(pct(m['latency'], 95))}",
        f"- Tokens: cache hit {t['cache_hit']:,}, cache miss {t['cache_miss']:,}, output {t['output']:,}",
        f"- Cost: **${m['cost']:.3f}** (${m['cost'] / hours:.2f}/h → ${m['cost'] / hours * 720:,.0f}/month if 24/7)",
        f"- Body busy (executing projects): **{m['busy_s'] / (m['span_s'] or 1):.0%}** of the run; "
        f"waited for the mind {m['waited_s'] / 60:.1f} min; plans discarded at handover: {m['discarded']}, "
        f"kept after a failure: {m['kept_after_failure']}",
        f"- Reasoning tokens per decision: avg {sum(m['reasoning']) / len(m['reasoning']):.0f}" if m["reasoning"] else
        "- Reasoning tokens per decision: not logged in this run",
        f"- Answers cut off by the output cap: {m['cut_off']}"
        + (f" ({m['answers_forced']} given from the reasoning so far, {m['answers_forced_failed']} attempt"
           f"{'s' if m['answers_forced_failed'] != 1 else ''} failed)"
           if m["answers_forced"] or m["answers_forced_failed"] else ""),
        f"- Waits for the mind over a minute: {m['long_waits']}; stop-gaps run while it thought: "
        f"{m['stopgaps']} ({m['stopgaps_ok']} finished, {m['stopgap_s'] / 60:.1f} min), dropped unused: "
        f"{m['stopgaps_dropped']}",
        "- First projects of a plan finished: {}/{}; after stop-gaps {}/{}".format(
            *m["first_projects"]["otherwise"], *m["first_projects"]["after_stopgap"]),
        f"- House: best score {m['house_best']}, {'stood' if m['house_built'] else 'never stood'}"
        if m["house_best"] is not None else "- House: no progress logged",
        "- Cost by purpose: " + ", ".join(f"{k} ${v:.3f}" for k, v in sorted(m["cost_by"].items(), key=lambda kv: -kv[1])),
        f"- Decisions: {m['decisions']}; projects run: {m['projects']} ({m['projects_ok']} finished); "
        f"events noticed: {m['events']}; sleeps: {m['sleeps']}",
        "- Skill success: " + ", ".join(f"{k} {ok}/{n}" for k, (ok, n) in sorted(m["skills"].items())),
        "",
    ]


NOTICED_WITHIN = 60  # seconds: a glance or a mention this soon counts as noticing
ENGAGED_WITHIN = 600  # seconds: using it, or naming it in an intention, this soon counts as engaging
SKY_WORDS = re.compile(r"\b(sky|shadow|meteor|lightning|fell from|falling|dropped|grew back)\b", re.I)


def analyze_reactions(mind_log, world_log):
    """Reactions to sky events (the guest panel's powers and --sky-test-minutes), in three
    stages: applied (the world did it: only this would decide a charge), noticed (a glance or a mention within a
    minute: the product's promise) and engaged (used what it left, or planned with it, within ten minutes: up to
    Godling). Named counts a thought or intention that mentions it."""
    entries = [json.loads(line) for line in mind_log.read_text().splitlines() if line.strip()]
    falls = {}  # sky_id -> {"kind", "start", "pieces"}
    for e in entries:
        if e["kind"] == "event" and e.get("sky"):
            fall = falls.setdefault(e["sky_id"], {"kind": e["sky"], "start": e["time"], "pieces": set()})
            if e.get("sky_stage") == "arrived":
                fall["pieces"].update(e.get("entities") or [])
    if not falls:
        return None
    world_applied = None
    if world_log.exists():
        world_applied = len(set(re.findall(r"SKY \w+ #(\d+)", world_log.read_text(errors="replace"))))
    glances = [e for e in entries if e["kind"] == "glance" and e.get("sky")]
    decisions = [e for e in entries if e["kind"] == "decision"]
    uses = [e for e in entries if e["kind"] == "skill"]
    out = {"applied": len(falls), "kinds": Counter(f["kind"] for f in falls.values()), "world_applied": world_applied,
           "noticed": 0, "named": 0, "engaged": 0, "glance_after_s": []}
    for sky_id, f in falls.items():
        start = f["start"]
        looked = [g["time"] - start for g in glances if g["sky_id"] == sky_id and 0 <= g["time"] - start <= NOTICED_WITHIN]
        said = [d for d in decisions if 0 <= d["time"] - start <= ENGAGED_WITHIN and SKY_WORDS.search(
            " ".join([d.get("thought", "")] + [p.get("intention", "") + " " + p.get("goal", "") for p in d.get("projects", [])]))]
        if looked or any(d["time"] - start <= NOTICED_WITHIN for d in said):
            out["noticed"] += 1
        if looked:
            out["glance_after_s"].append(min(looked))
        out["named"] += bool(said)
        near = [json.dumps(u.get("args")) for u in uses if 0 <= u["time"] - start <= ENGAGED_WITHIN]
        near += [json.dumps(d.get("projects")) for d in decisions if 0 <= d["time"] - start <= ENGAGED_WITHIN]
        out["engaged"] += any(name in text for name in f["pieces"] for text in near)
    return out


def reaction_report(r):
    n = r["applied"]
    world = f"; the world log shows {r['world_applied']}" if r["world_applied"] is not None else ""
    return [
        "## Reactions to sky events",
        f"- Applied: **{n}** (" + ", ".join(f"{k} {v}" for k, v in sorted(r["kinds"].items())) + f"){world}",
        f"- Noticed within {NOTICED_WITHIN} s: **{r['noticed']}/{n}**"
        + (f"; first glance p50 {fmt_s(pct(r['glance_after_s'], 50))} after the warning" if r["glance_after_s"] else ""),
        f"- Named in a thought or intention within {ENGAGED_WITHIN // 60} min: {r['named']}/{n}",
        f"- Engaged (used it or planned with it) within {ENGAGED_WITHIN // 60} min: {r['engaged']}/{n}",
        "",
    ]


QUAKE_RE = re.compile(r"SKY Earthquake #(\d+) over: woke (\d+), moved (\d+), fell (\d+)")


def analyze_quakes(mind_log, world_log):
    """Earthquakes: what each shook loose and brought down (from the
    world log), how soon the body braced after the rumble, and knock-downs."""
    if not world_log.exists():
        return None
    text = world_log.read_text(errors="replace")
    quakes = {int(m[0]): {"woke": int(m[1]), "moved": int(m[2]), "fell": int(m[3])} for m in QUAKE_RE.findall(text)}
    if not quakes:
        return None
    entries = [json.loads(line) for line in mind_log.read_text().splitlines() if line.strip()] if mind_log.exists() else []
    rumbles = {e["sky_id"]: e["time"] for e in entries if e["kind"] == "event" and e.get("sky") == "Earthquake"
               and e.get("sky_stage") == "warning"}
    braces = {}
    for e in entries:
        if e["kind"] == "brace" and e.get("ok") and e.get("sky_id") in rumbles:
            braces.setdefault(e["sky_id"], e["time"] - rumbles[e["sky_id"]])
    for sky_id, q in quakes.items():
        q["braced_after_s"] = braces.get(sky_id)
    return {"quakes": quakes, "knockdowns": text.count("QUAKE knocked")}


def quake_report(q):
    lines = ["## Earthquakes", "| # | Pieces woken | Moved | Fell | Braced after the rumble |", "|---|---|---|---|---|"]
    for sky_id, x in sorted(q["quakes"].items()):
        braced = fmt_s(x["braced_after_s"]) if x["braced_after_s"] is not None else "not braced"
        lines.append(f"| {sky_id} | {x['woke']} | {x['moved']} | {x['fell']} | {braced} |")
    return lines + [f"- Knocked down (not braced when the shaking began): {q['knockdowns']}", ""]


# --- report ------------------------------------------------------------------


def report(run_dir, rec, agent, workspace):
    lines = [f"# Run analysis: {run_dir.name}", ""]
    if rec:
        hours = rec["duration_s"] / 3600 or 1e-9
        inputs = rec["inputs"]
        times = [r[1] / 1000 for r in inputs]
        gaps = [b - a for a, b in zip(times, times[1:])]
        types = Counter(r[3] for r in inputs)
        lines += [
            "## World (server-side ground truth)",
            f"- Recording: `{rec['path'].name}` ({rec['size_mb']:.1f} MB, {rec['size_mb'] / hours:.1f} MB/h), tick rate {rec['tick_rate']} Hz",
            f"- Duration: {fmt_s(rec['duration_s'])}",
            f"- Actions: **{len(inputs)}** ({len(inputs) / hours:.0f}/h) — "
            + ", ".join(f"{k} {v}" for k, v in types.most_common()),
        ]
        if gaps:
            lines += [
                f"- Gap between consecutive actions: p50 **{fmt_s(pct(gaps, 50))}**, p90 {fmt_s(pct(gaps, 90))}, "
                f"p95 **{fmt_s(pct(gaps, 95))}**, max {fmt_s(max(gaps))}",
                f"- Gaps ≤ 2 s (G5 target zone): {sum(g <= 2 for g in gaps) / len(gaps):.0%}",
                "",
                "| Gap | Count | Share | Time spent |",
                "|---|---|---|---|",
            ]
            for lo, hi in GAP_BUCKETS:
                sel = [g for g in gaps if lo <= g < hi]
                label = f"{lo}–{hi:g}s" if hi != math.inf else f">{lo}s"
                lines.append(f"| {label} | {len(sel)} | {len(sel) / len(gaps):.0%} | {fmt_s(sum(sel))} |")
            top = sorted(zip(gaps, times), reverse=True)[:5]
            lines += ["", "Longest idle stretches (minutes into the run):"]
            lines += [
                f"- {fmt_s(g)} starting at {(t - rec['start_ms'] / 1000) / 60:.1f} min" for g, t in top
            ]
            per_hour = Counter(int((t - rec["start_ms"] / 1000) // 3600) for t in times)
            if len(per_hour) > 1:
                lines += ["", "Actions per hour: " + ", ".join(f"h{h}: {per_hour[h]}" for h in sorted(per_hour))]
        m = rec.get("motion")
        lines.append("")
        if m is None:
            lines.append("- Motion duty cycle: skipped (install `zstd` or `pip install zstandard`)")
        elif m["duty_cycle"] is not None:
            lines.append(
                f"- Motion duty cycle: **{m['duty_cycle']:.0%}** of {fmt_s(m['sampled_s'])} sampled at ~1 Hz (speed ≥ {MOVING_SPEED} studs/s)"
            )
            if m["result_changes"]:
                lines.append(
                    "- Action results seen in world state: "
                    + ", ".join(f"{k} {v}" for k, v in m["result_changes"].most_common(8))
                )
        lines.append("")

    if agent and agent["calls"]:
        hours = agent["span_s"] / 3600 or 1e-9
        t = agent["tokens"]
        total_in = t["input"] + t["cache_write"] + t["cache_read"]
        think = agent["think"]
        lines += [
            "## Agent (Claude Code transcript)",
            f"- Models: " + ", ".join(f"{k} ({v})" for k, v in agent["models"].most_common()),
            f"- Model calls: {agent['calls']} ({agent['calls'] / hours:.0f}/h); stop-hook continues: {agent['continues']}",
            f"- Think time per call: p50 **{fmt_s(pct(think, 50))}**, p95 {fmt_s(pct(think, 95))}",
            f"- Tokens: input {t['input']:,}, cache write {t['cache_write']:,}, cache read {t['cache_read']:,}, output {t['output']:,}",
            f"- Cache hit share of input: {t['cache_read'] / total_in:.0%}" if total_in else "- Cache: n/a",
            f"- Avg context per call: {total_in / agent['calls']:,.0f} tokens",
        ]
        if agent["cost"] is not None:
            lines.append(
                f"- Estimated cost: **${agent['cost']:.2f}** (${agent['cost'] / hours:.2f}/h → ${agent['cost'] / hours * 720:,.0f}/month if 24/7; "
                "cache writes at the 5-min rate, so a lower bound if 1 h caching is used)"
            )
        else:
            lines.append("- Estimated cost: unknown model — rerun with --price IN,CW,CR,OUT")
        tools = agent["tools"]
        n = sum(tools.values()) or 1
        lines += [
            "- Tool calls: " + ", ".join(f"{k} {v} ({v / n:.0%})" for k, v in tools.most_common()),
            f"- World actions per action command: {agent['actions_in_commands'] / max(agent['act_commands'], 1):.2f} "
            "(>1 means the agent batches actions in one shell call)",
        ]
        if agent["results"]:
            lines.append(
                "- Results returned to agent: " + ", ".join(f"{k} {v}" for k, v in agent["results"].most_common(8))
            )
        lines.append("")
    elif agent is not None:
        lines += ["## Agent", "- No Claude Code transcript found under the agent directory.", ""]

    mind_log = run_dir / "mind" / "log.jsonl"
    if mind_log.exists():
        lines += mind_report(analyze_mind_log(mind_log))
        reactions = analyze_reactions(mind_log, run_dir / "world.log")
        if reactions:
            lines += reaction_report(reactions)
        quakes = analyze_quakes(mind_log, run_dir / "world.log")
        if quakes:
            lines += quake_report(quakes)

    if workspace:
        lines += ["## Workspace memory", "| File | Bytes | ~Tokens |", "|---|---|---|"]
        lines += [f"| {name} | {size:,} | {size // 4:,} |" for name, size in workspace]
        lines.append("")
    return "\n".join(lines)


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--price", help="override USD per M tokens: IN,CACHE_WRITE,CACHE_READ,OUT")
    ARGS = ap.parse_args()
    ARGS.price_key = None
    if ARGS.price:
        PRICES["override"] = tuple(float(x) for x in ARGS.price.split(","))
        ARGS.price_key = "override"

    run_dir = ARGS.run_dir.expanduser().resolve()
    recs = sorted((run_dir / "recordings").glob("*.clawrec"), key=lambda p: p.stat().st_size)
    rec = analyze_recording(recs[-1]) if recs else None
    agent_dir = run_dir / "agent"
    agent = analyze_transcripts(find_transcripts(agent_dir)) if agent_dir.is_dir() else None
    ws = agent_dir / "workspace"
    workspace = sorted(
        ((str(p.relative_to(ws)), p.stat().st_size) for p in ws.rglob("*") if p.is_file()),
        key=lambda x: -x[1],
    ) if ws.is_dir() else []

    text = report(run_dir, rec, agent, workspace)
    out = run_dir / "analysis"
    out.mkdir(exist_ok=True)
    (out / "report.md").write_text(text, encoding="utf-8")
    if rec:
        with (out / "actions.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["tick", "time_s", "agent_id", "type", "data"])
            for tick, time_ms, agent_id, typ, data in rec["inputs"]:
                w.writerow([tick, f"{time_ms / 1000:.3f}", agent_id, typ, data])
    print(text)
    print(f"\nWritten: {out / 'report.md'}")


if __name__ == "__main__":
    main()
