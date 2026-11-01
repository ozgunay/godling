#!/usr/bin/env python3
"""Guest panel: try Godling's sky powers yourself, a stand-in for the viewers' store.

Usage (next to a running world, inside WSL or on Windows):
    python3 tools/guest_panel.py --world http://localhost:8080 [--run-dir ~/godling-runs/x] [--port 8081]
    (without --run-dir, pass the spectator link the world printed as --view, or the live view stays empty)
or start it with a run: run_godling.py ... --guest-panel 8081

It joins the world as "Sky", a player with no body that only the world's sky powers listen to (world/main.lua), and
serves a page with the live view and one button per power. You choose what; the world chooses where: near Godling,
in view, clear of what it built. With --run-dir the page also shows what Godling is thinking, what it needs and what
it noticed. Powers are free here: prices, caps and payment come later.
"""
import argparse
import html
import json
import re
import sys
import threading
import time
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mind"))
from godling.world import SKY_PLAYER, World, WorldError  # noqa: E402

# name in main.lua's SKY_POWERS, button label, what it does, tier in the plan's price list
POWERS = [
    ("Stone", "Drop a stone", "A stone block drops from the sky near Godling.", "gift"),
    ("Log", "Drop a log", "A log beam drops from the sky near Godling.", "gift"),
    ("Regrow", "Regrow a tree", "The stump nearest Godling grows back at once.", "gift"),
    ("Lightning", "Lightning", "Strikes the tree nearest Godling and fells it into two logs.", "mid"),
    ("Meteor", "Meteor", "A shadow spreads near Godling; 40 s later a dark stone lands in it.", "mid"),
]
WHY_NOT = {
    "NoClearSpot": "No clear spot near Godling right now.",
    "NoStandingTree": "No standing tree left to strike.",
    "NoStump": "No stump to regrow: every tree is standing.",
    "NobodyHere": "Godling is not in the world.",
    "UnknownPower": "The world does not know that power (is it running an older copy of main.lua?).",
}
DONE = {
    "Stone": "dropped near Godling.",
    "Log": "dropped near Godling.",
    "Regrow": "a tree grew back.",
    "Lightning": "struck a tree.",
    "Meteor": "a shadow spreads near Godling; the stone lands in 40 s.",
}
LOG_TAIL_BYTES = 400_000


class Sky:
    """The guest panel's bodiless player. One call at a time; joins (again) when needed."""

    def __init__(self, base):
        self.world = World(base, SKY_PLAYER)
        self.lock = threading.Lock()

    def call(self, power):
        with self.lock:
            for attempt in range(2):
                try:
                    if not self.world.session:
                        self.world.join()
                    before = self.world.observe().last_result
                    result = self.world.act("Sky", {"power": power}).last_result
                    deadline = time.time() + 1.5
                    while result == before and time.time() < deadline:
                        time.sleep(0.1)
                        result = self.world.observe().last_result
                    return result
                except (WorldError, KeyError) as err:
                    self.world.session = None
                    if attempt:
                        return f"SkyFailed:World:{err}"
        return "SkyFailed:World"


def describe(power, result):
    """The world's answer in words, for the panel's log."""
    label = next((p[1] for p in POWERS if p[0] == power), power)
    if result.startswith("SkyDone:"):
        number = result.rsplit(":", 1)[1]
        return True, f"{label} #{number}: {DONE.get(power, 'done.')}"
    why = result.split(":", 1)[1] if ":" in result else result
    if why.startswith("World"):
        return False, f"{label}: could not reach the world ({why[6:] or 'no answer'}). If it says the game is full, " \
                      "the world needs max_players = 2 in world.toml."
    return False, f"{label}: {WHY_NOT.get(why, why)}"


def mind_status(run_dir):
    """What Godling thinks, needs and noticed lately, from the tail of its log."""
    path = run_dir / "mind/log.jsonl" if run_dir else None
    if not path or not path.exists():
        return {}
    with path.open("rb") as f:
        f.seek(max(0, path.stat().st_size - LOG_TAIL_BYTES))
        lines = f.read().decode("utf-8", "replace").splitlines()[1:]
    out = {"thought": "", "needs": "", "intention": "", "noticed": []}
    noticed = deque(maxlen=10)
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("kind") == "decision":
            out["thought"], out["needs"] = e.get("thought", ""), e.get("needs", "")
        elif e.get("kind") == "project" and e.get("phase") == "start":
            out["intention"] = e.get("intention") or e.get("goal", "")
        elif e.get("kind") == "event":
            noticed.append({"time": e["time"], "text": e["text"], "sky": bool(e.get("sky")), "glance": None})
        elif e.get("kind") == "glance":
            seen = next((n for n in reversed(noticed) if n["text"] == e.get("text") and n["glance"] is None), None)
            if seen:
                seen["glance"] = e.get("degrees") if e.get("turned") else 0
    out["noticed"] = list(reversed(noticed))
    return out


def world_up(base):
    try:
        urllib.request.urlopen(base + "/api.md", timeout=1).read()
        return True
    except OSError:
        return False


def spectator_url(base, run_dir):
    """The live view needs the spectator token the world prints when it starts (run_godling.py logs it)."""
    log = run_dir / "world.log" if run_dir else None
    if log and log.exists():
        match = re.search(r"Spectator frontend: (\S+)", log.read_text(errors="replace"))
        if match:
            return match.group(1)
    return base + "/"


def serve(world, port, run_dir=None, view=None):
    base = world.rstrip("/")
    sky = Sky(base)
    results = deque(maxlen=30)
    view = view or spectator_url(base, run_dir)
    page = PAGE.replace("__VIEW__", html.escape(view, quote=True)).replace("__POWERS__", json.dumps(
        [{"name": n, "label": label, "does": does, "tier": tier} for n, label, does, tier in POWERS]))

    class Handler(BaseHTTPRequestHandler):
        def _send(self, body, kind="application/json", code=200):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                self._send(page, "text/html; charset=utf-8")
            elif self.path == "/status":
                self._send(json.dumps({"world": world_up(base), "results": list(results), **mind_status(run_dir)}))
            else:
                self._send("{}", code=404)

        def do_POST(self):
            if self.path != "/power":
                return self._send("{}", code=404)
            try:
                power = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}").get("power")
            except ValueError:
                power = None
            if power not in {p[0] for p in POWERS}:
                return self._send(json.dumps({"ok": False, "text": "Unknown power."}), code=400)
            ok, text = describe(power, sky.call(power))
            entry = {"time": time.time(), "power": power, "ok": ok, "text": text}
            results.appendleft(entry)
            self._send(json.dumps(entry))

        def log_message(self, *args):  # quiet: the run's own console is busy enough
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Guest panel: http://localhost:{port}/ (world {base})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Godling sky panel</title>
<style>
:root {
  --bg: #f4f1ea; --panel: #fffdf8; --ink: #22201c; --muted: #6d675d; --line: #e2dccf;
  --accent: #2f6f8f; --gift: #4c7a3f; --mid: #a0522d; --warn: #b3402a; --soft: #efe9dc;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #15140f; --panel: #1f1d18; --ink: #ece6d8; --muted: #a39b8b; --line: #34312a;
    --accent: #7fb6d1; --gift: #8fbf7a; --mid: #e09a6b; --warn: #ef8a72; --soft: #2a2721; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
header { display: flex; align-items: center; gap: 10px; padding: 10px 16px; border-bottom: 1px solid var(--line); }
header h1 { font-size: 16px; margin: 0; font-weight: 650; letter-spacing: .01em; }
header .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--muted); }
header .dot.up { background: var(--gift); }
header .note { margin-left: auto; color: var(--muted); font-size: 13px; }
main { display: grid; grid-template-columns: minmax(0, 1fr) 360px; height: calc(100vh - 45px); }
iframe { width: 100%; height: 100%; border: 0; background: #000; }
aside { overflow-y: auto; padding: 14px 16px 24px; border-left: 1px solid var(--line); background: var(--panel); }
h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin: 18px 0 8px; }
h2:first-child { margin-top: 0; }
.now p { margin: 0 0 6px; }
.needs { background: var(--soft); border-radius: 8px; padding: 8px 10px; font-weight: 600; }
.needs:empty { display: none; }
.empty { color: var(--muted); font-style: italic; }
.powers { display: grid; gap: 8px; }
.power { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 2px 10px; text-align: left;
  width: 100%; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--bg);
  color: var(--ink); font: inherit; cursor: pointer; }
.power:hover { border-color: var(--accent); }
.power:disabled { opacity: .55; cursor: progress; }
.power b { font-weight: 650; }
.power small { grid-column: 1 / -1; color: var(--muted); }
.tag { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; padding: 1px 7px; border-radius: 99px;
  border: 1px solid currentColor; }
.tag.gift { color: var(--gift); } .tag.mid { color: var(--mid); }
ul { list-style: none; margin: 0; padding: 0; }
li { padding: 6px 0; border-bottom: 1px solid var(--line); font-size: 14px; }
li time { color: var(--muted); font-variant-numeric: tabular-nums; margin-right: 6px; }
li.fail { color: var(--warn); }
li .seen { color: var(--accent); font-size: 12px; margin-left: 4px; }
li.sky { font-weight: 550; }
@media (max-width: 820px) {
  main { grid-template-columns: 1fr; height: auto; }
  iframe { height: 56vh; }
  aside { border-left: 0; border-top: 1px solid var(--line); }
}
</style>
</head>
<body>
<header><span class="dot" id="dot"></span><h1>Godling sky panel</h1>
<span class="note">Test mode: powers are free</span></header>
<main>
  <iframe src="__VIEW__" title="The island, live"></iframe>
  <aside>
    <h2>Godling now</h2>
    <div class="now"><p id="intention" class="empty">Waiting for its first plan.</p><p id="thought"></p>
      <p class="needs" id="needs"></p></div>
    <h2>Sky powers</h2>
    <div class="powers" id="powers"></div>
    <h2>Your sky log</h2>
    <ul id="results"><li class="empty">Nothing called down yet.</li></ul>
    <h2>What Godling noticed</h2>
    <ul id="noticed"><li class="empty">Nothing yet. Start the panel with --run-dir to see this.</li></ul>
  </aside>
</main>
<script>
const POWERS = __POWERS__;
const $ = (id) => document.getElementById(id);
const clock = (t) => new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
function li(text, cls, time, extra) {
  const el = document.createElement('li');
  if (cls) el.className = cls;
  if (time) { const t = document.createElement('time'); t.textContent = clock(time); el.append(t); }
  el.append(text);
  if (extra) { const s = document.createElement('span'); s.className = 'seen'; s.textContent = extra; el.append(s); }
  return el;
}
for (const p of POWERS) {
  const b = document.createElement('button');
  b.className = 'power';
  b.innerHTML = '<b></b><span class="tag"></span><small></small>';
  b.querySelector('b').textContent = p.label;
  b.querySelector('.tag').textContent = p.tier;
  b.querySelector('.tag').classList.add(p.tier);
  b.querySelector('small').textContent = p.does;
  b.onclick = async () => {
    b.disabled = true;
    try {
      const r = await fetch('/power', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ power: p.name }) });
      await r.json();
    } finally { b.disabled = false; refresh(); }
  };
  $('powers').append(b);
}
async function refresh() {
  let s;
  try { s = await (await fetch('/status')).json(); } catch { $('dot').className = 'dot'; return; }
  $('dot').className = s.world ? 'dot up' : 'dot';
  if (s.intention !== undefined) {
    $('intention').textContent = s.intention || 'Waiting for its first plan.';
    $('intention').className = s.intention ? '' : 'empty';
    $('thought').textContent = s.thought || '';
    $('needs').textContent = s.needs ? 'Needs: ' + s.needs : '';
    const n = $('noticed');
    n.replaceChildren(...(s.noticed.length ? s.noticed.map((e) => li(e.text, e.sky ? 'sky' : '', e.time,
      e.glance === null ? '' : (e.glance ? 'turned to look' : 'saw it'))) : [li('Nothing yet.', 'empty')]));
  }
  if (s.results.length) $('results').replaceChildren(...s.results.map((r) => li(r.text, r.ok ? '' : 'fail', r.time)));
}
refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="http://localhost:8080")
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--run-dir", type=Path, default=None, help="show what Godling thinks, needs and noticed")
    ap.add_argument("--view", default=None, help="the spectator link the world printed (found in the run's world.log "
                                                 "with --run-dir)")
    args = ap.parse_args()
    serve(args.world, args.port, args.run_dir.expanduser().resolve() if args.run_dir else None, args.view)


if __name__ == "__main__":
    main()
