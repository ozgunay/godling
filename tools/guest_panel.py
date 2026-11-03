#!/usr/bin/env python3
"""Guest panel: the viewers' screen (world/viewer), live, with Godling's sky powers and notes free to try.

Usage (next to a running world, inside WSL or on Windows):
    python3 tools/guest_panel.py --world http://localhost:8080 [--run-dir ~/godling-runs/x] [--port 8081]
    (without --run-dir, pass the spectator link the world printed as --view, or the live view stays empty)
or start it with a run: run_godling.py ... --guest-panel 8081

It joins the world as "Sky", a player with no body that only the world's sky powers listen to (world/main.lua), and
serves the Block HUD over the live view: one hotbar slot per power, a note box, and pop-ups on the right for what
viewers did. You choose what; the world chooses where: near Godling, in view, clear of what it built. With --run-dir
the screen also shows what Godling is thinking, what it needs and what it noticed. Powers are free here (test mode):
prices are shown, payment comes later.

Notes: anyone watching may send Godling a short note (NOTE_LIMIT characters, no links). Each viewer may send one
every --note-every seconds, and the island gets at most one every --note-gap seconds; the rest wait in a short queue.
A note reaches the world as a paper glider; the mind reads it and decides for itself. Godling never sees who sent it.

With --key, the panel takes powers and notes only from the accounts site (web/, ADR-012), which sends the key and
the signed-in viewer's name and client id; the panel must then not be reachable from outside.

Joining the world takes its agent key (patches/v2, ADR-014): started by run_godling.py the panel inherits it; next to
a world started some other way, export that world's WORLD_AGENT_KEY first.
"""
import argparse
import hmac
import json
import math
import mimetypes
import os
import re
import sys
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mind"))
from godling import replay  # noqa: E402
from godling.world import SKY_PLAYER, World, WorldError  # noqa: E402

# name in main.lua's SKY_POWERS, button label, what it does, tier in the plan's price list. Viewers may aim each but
# the earthquake and the note (main.lua sky.aim): only the meteor lands on Godling or on what it built.
POWERS = [
    ("Stone", "Drop a stone", "A stone block drops from the sky where you aim; aimed at Godling, at its feet.", "gift"),
    ("Log", "Drop a log", "A log beam drops from the sky where you aim; aimed at Godling, at its feet.", "gift"),
    ("Regrow", "Regrow a tree", "The stump nearest your aim grows back at once.", "gift"),
    ("Lightning", "Lightning", "Strikes the palm nearest your aim, if it stands well away from Godling and its walls, "
     "and fells it into two logs.", "mid"),
    ("Meteor", "Meteor", "A shadow spreads where you aim; 40 s later a stone blasts there, whatever stands in it: "
     "Godling, its walls, palms. It leaves a crater.", "big"),
    ("Earthquake", "Earthquake", "The ground rumbles, then shakes for 20 s. Loose pieces near Godling can fall; fastened "
     "ones hold. Godling braces itself.", "big"),
    ("Note", "Note", "A paper glider drifts down near Godling with a short note.", "note"),
]
WHY_NOT = {
    "NoClearSpot": "No clear spot near Godling right now.",
    "NoStandingTree": "No standing tree left to strike.",
    "NoSafePalm": "No palm there stands far enough from Godling and its walls to strike.",
    "TooFar": "Too far from Godling: aim within 60 of it.",
    "NotOnLand": "Aim at the island, not the sea.",
    "NoStump": "No stump to regrow: every tree is standing.",
    "NobodyHere": "Godling is not in the world.",
    "UnknownPower": "The world does not know that power (is it running an older copy of main.lua?).",
    "AlreadyShaking": "The ground is already shaking.",
    "GodlingIsWeak": "Godling is weak: no disasters while its health is under 30, or for 15 minutes after a faint.",
    "NothingBuiltYet": "Nothing built yet: an earthquake needs at least 15 pieces standing near Godling.",
    "EmptyNote": "The note was empty.",
}
DONE = {
    "Stone": "dropped near Godling.",
    "Log": "dropped near Godling.",
    "Regrow": "a tree grew back.",
    "Lightning": "struck a tree.",
    "Meteor": "a shadow spreads; the stone blasts there in 40 s.",
    "Earthquake": "the ground rumbles; the shaking starts in 8 s.",
    "Note": "a paper glider drifts down near Godling.",
}
LOG_TAIL_BYTES = 400_000
VIEWER = Path(__file__).resolve().parent.parent / "world/viewer"  # the page this panel serves
WATCHING_FOR = 20  # seconds: a viewer whose page has not asked for news this long has left
POWER_EVERY = 2  # seconds between one viewer's powers (the world's own cooldowns still hold)
NOTE_LIMIT = 140  # characters (the world caps a note at 160 too)
NOTE_QUEUE = 5  # notes waiting for their turn at most; past that, try again later
NAME_LIMIT = 18
POPUPS_KEPT = 12
FEED_KEPT = replay.FEED_KEPT  # lines of Godling's feed sent to the screen, live and in replay
# A stand-in for real moderation, which comes with accounts: no links or handles, no shouting, none of these words.
BLOCKED = re.compile(r"\b(fuck\w*|shit\w*|cunt\w*|bitch\w*|whore\w*|nigg\w*|fag\w*|retard\w*|rape\w*|kill yourself)",
                     re.IGNORECASE)
LINK = re.compile(r"(https?:|www\.|\b[\w-]+\.(com|net|org|io|gg|tv|ly|me|co|xyz|ru)\b|@\w)", re.IGNORECASE)
# A note is words for Godling, never commands for the model behind it (clean_note). These are the shapes of talking to
# the model instead: role labels, "ignore your instructions", talk of prompts and modes, and markup characters.
STEERING = re.compile(r"(\b(system|assistant|developer|user)\s*[:>\]]|\b(ignore|disregard|forget|override)\b.{0,30}"
                      r"\b(instructions?|rules?|prompts?|previous|above|everything)\b|\b(system|hidden|your)\s+prompt|"
                      r"\bjailbreak|\bdeveloper mode|\byou are (now|no longer)\b|\bnew (instructions|rules)\b|"
                      r"\bact as\b|\bpretend (to be|you)\b|[{}<>`\[\]\\|#=*_~])", re.IGNORECASE)
QUOTES = re.compile("[“”„«»‹›\"]")  # any mark that could close the quote a note sits in


class Sky:
    """The guest panel's bodiless player. One call at a time; joins (again) when needed."""

    def __init__(self, base):
        self.world = World(base, SKY_PLAYER)
        self.lock = threading.Lock()

    def call(self, power, **extra):
        with self.lock:
            for attempt in range(2):
                try:
                    if not self.world.session:
                        self.world.join()
                    before = self.world.observe().last_result
                    result = self.world.act("Sky", {"power": power, **extra}).last_result
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

    def clock(self):
        """The Clock's attributes: the hour, the weather, and Godling's state, which the world copies there."""
        with self.lock:
            try:
                if not self.world.session:
                    self.world.join()
                clock = self.world.observe().entities.get("Clock")
                return dict(clock.attrs) if clock else {}
            except (WorldError, KeyError):
                self.world.session = None
                return None


def describe(power, result):
    """The world's answer in words, for the panel's log."""
    label = next((p[1] for p in POWERS if p[0] == power), power)
    if result.startswith("SkyDone:"):
        number = result.rsplit(":", 1)[1]
        return True, f"{label} #{number}: {DONE.get(power, 'done.')}"
    why = result.split(":", 1)[1] if ":" in result else result
    if why.startswith("TooSoon:"):  # disasters have a cooldown; the world says how long is left
        minutes, seconds = divmod(int(why.split(":")[1]), 60)
        return False, f"{label}: not yet; try again in {minutes}:{seconds:02d}."
    if why.startswith("World"):
        return False, f"{label}: could not reach the world ({why[6:] or 'no answer'}). If it says the game is full, " \
                      "the world needs max_players = 2 in world.toml."
    return False, f"{label}: {WHY_NOT.get(why, why)}"


_mind_seen = {"key": None, "out": {}}
_mind_lock = threading.Lock()


def mind_status(run_dir):
    """What Godling thinks, needs and noticed lately, from the tail of its log: its feed for the viewers' screen.

    Read again only when the log has grown: every page's poll asks for it, and reading the tail costs a 400 KB parse."""
    path = run_dir / "mind/log.jsonl" if run_dir else None
    if not path or not path.exists():
        return {}
    stat = path.stat()
    with _mind_lock:
        if _mind_seen["key"] == (str(path), stat.st_size, stat.st_mtime_ns):
            return _mind_seen["out"]
        out = _read_mind(path)
        _mind_seen.update(key=(str(path), stat.st_size, stat.st_mtime_ns), out=out)
        return out


def _read_mind(path):
    with path.open("rb") as f:
        f.seek(max(0, path.stat().st_size - LOG_TAIL_BYTES))
        lines = f.read().decode("utf-8", "replace").splitlines()[1:]
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return replay.reduce_status(entries, clean_shown, FEED_KEPT)  # read the same way in replays (ADR-016)


def replay_tracks(run_dir, t_from, t_to):
    """The screen's tracks for a replay (ADR-016), with what viewers see of Godling's mind cleaned as it is live."""
    tracks = replay.read_tracks(run_dir, t_from, t_to)
    for e in tracks["lead"] + tracks["entries"]:
        for key in ("thought", "needs", "intention", "goal", "text", "name", "does", "dream"):
            if key in e:
                e[key] = clean_shown(e[key])
    return tracks


def span(query, most_ms):
    """`from` and `to` (UTC ms) of a replay request, at most `most_ms` apart and not past tomorrow, or None."""
    try:
        t_from, t_to = int(query.get("from", [""])[0]), int(query.get("to", [""])[0])
    except ValueError:
        return None
    return (t_from, t_to) if 0 <= t_from <= t_to <= time.time() * 1000 + 86_400_000 and t_to - t_from <= most_ms         else None


def world_up(base):
    try:
        urllib.request.urlopen(base + "/api.md", timeout=1).read()
        return True
    except OSError:
        return False


def island_url(url):
    """A world mounted under a base path (deploy/: /island) prints its page as /island/?… but serves it at /island?…"""
    parts = urllib.parse.urlsplit(url)
    if parts.path not in ("", "/") and parts.path.endswith("/"):
        parts = parts._replace(path=parts.path.rstrip("/"))
    return urllib.parse.urlunsplit(parts)


def spectator_url(base, run_dir):
    """The live view needs the spectator token the world prints when it starts (run_godling.py logs it)."""
    log = run_dir / "world.log" if run_dir else None
    if log and log.exists():
        match = re.search(r"Spectator frontend: (\S+)", log.read_text(errors="replace"))
        if match:
            return island_url(match.group(1))
    return island_url(base + "/")


def clean_note(text):
    """A viewer's note as Godling will read it, or (None, why not).

    The first guard against a note that speaks to the model rather than to Godling (prompt injection): one plain line,
    no lookalike letters or hidden characters, no mark that could close the quote it arrives in, nothing shaped like
    an instruction to a model. The others: the mind reads a note only as a stranger's quoted words, under a standing
    rule (mind.py); its body can only do island things, whatever it decides; what viewers see of it passes clean_shown.
    """
    text = unicodedata.normalize("NFKC", str(text or ""))  # fullwidth and other lookalike letters to plain ones
    text = "".join(" " if unicodedata.category(c) in ("Cc", "Zl", "Zp") else c for c in text
                   if unicodedata.category(c) != "Cf")  # line breaks to spaces; zero-width and direction marks dropped
    text = QUOTES.sub("'", re.sub(r"\s+", " ", text).strip())
    if not text:
        return None, "Write something first."
    if len(text) > NOTE_LIMIT:
        return None, f"Notes are {NOTE_LIMIT} characters at most."
    if LINK.search(text):
        return None, "No links or handles in notes."
    if BLOCKED.search(text):
        return None, "That note would not be kind to send."
    if STEERING.search(text):
        return None, "Notes are words for Godling, not commands for its mind: plain words, no symbols."
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 12 and sum(c.isupper() for c in letters) > 0.7 * len(letters):
        return None, "No need to shout: Godling reads quietly."
    return text, ""


def clean_shown(text):
    """What viewers see of Godling's mind, held back if a note talked it into repeating a link or a slur."""
    text = str(text or "")
    return "…" if LINK.search(text) or BLOCKED.search(text) else text


def clean_name(name):
    # Keeps every character an account's username may hold (Django's: letters, digits, @ . + - _), so a pop-up
    # names the account as it is: mara+foo never shows as marafoo, someone else's name.
    name = re.sub(r"[^\w .@+\-]", "", str(name or "")).strip()[:NAME_LIMIT]
    return name or "Someone"


def clean_client(client):
    client = str(client or "")
    return client if re.fullmatch(r"[A-Za-z0-9]{6,40}", client) else ""


class Island:
    """What the panel knows and keeps: the latest look at the Clock, who is watching, what viewers did, the notes queue."""

    def __init__(self, sky, note_every, note_gap, trusted=False, run_dir=None):
        self.sky = sky
        self.run_dir = run_dir  # what viewers did is kept there for replays (ADR-016)
        self.note_every, self.note_gap = note_every, note_gap
        # Behind the accounts site (--key), the site keeps each viewer's pace from its database (its rules, which the
        # admin edits); the panel keeps only the island's own: one note at a time, a short queue.
        self.trusted = trusted
        self.lock = threading.Lock()
        self.clock, self.clock_at = None, 0
        self.seen = {}  # client -> when its page last asked for news
        self.last_power = {}  # client -> when it last called a power
        self.last_note = {}  # client -> when it last sent a note
        self.notes = deque()  # (client, name, text) waiting for their turn
        self.note_sent = 0  # when the last note went down to the island
        self.popups = deque(maxlen=POPUPS_KEPT)
        self.count = 0

    def watching(self, client=""):
        now = time.time()
        with self.lock:
            if client:
                self.seen[client] = now
            for c in [c for c, t in self.seen.items() if now - t > WATCHING_FOR]:
                del self.seen[c]
            return len(self.seen)

    def popup(self, kind, name, power, text, ok=True, ref=None):
        """What viewers did, for everyone's pop-ups on the right; a refusal goes back only to whoever pressed.
        A note's pop-up carries the site's id for it (`ref`), so viewers report that very note."""
        with self.lock:
            self.count += 1
            entry = {"id": self.count, "time": time.time(), "kind": kind, "name": name, "power": power, "text": text,
                     "ok": ok, **({"ref": ref} if ref is not None else {})}
            if ok:
                self.popups.append(entry)
        if ok and self.run_dir:
            try:
                replay.record_act(self.run_dir, entry)
            except OSError as err:
                print(f"Guest panel: could not keep a viewer's act for replays: {err}", flush=True)
        return entry

    def power(self, client, name, power, at=None):
        now = time.time()
        with self.lock:
            if not self.trusted and now - self.last_power.get(client, 0) < POWER_EVERY:
                return {"ok": False, "text": "One power at a time: give the last one a moment."}
            self.last_power[client] = now
        result = self.sky.call(power, **({"at": {"x": at[0], "z": at[1]}} if at else {}))
        ok, text = describe(power, result)
        entry = self.popup("power", name, power, text, ok)
        too_soon = re.search(r"TooSoon:(\d+)", result)
        return {**entry, "wait": int(too_soon.group(1))} if too_soon else entry

    def note(self, client, name, raw, ref=None):
        text, why = clean_note(raw)
        if text is None:
            return {"ok": False, "text": why}
        now = time.time()
        with self.lock:
            wait = 0 if self.trusted else self.note_every - (now - self.last_note.get(client, 0))
            if wait > 0:
                minutes, seconds = divmod(math.ceil(wait), 60)
                return {"ok": False, "text": f"One note at a time: you can send another in {minutes}:{seconds:02d}.",
                        "wait": math.ceil(wait)}
            if len(self.notes) >= NOTE_QUEUE:
                return {"ok": False, "text": "The sky is full of notes right now. Try again in a minute."}
            self.last_note[client] = now
            self.notes.append((client, name, text, ref))
            soon = max(0, self.note_gap - (now - self.note_sent)) + (len(self.notes) - 1) * self.note_gap
        return {"ok": True, "text": "Folded into a glider. " + (
            "It drifts down now." if soon < 2 else f"It drifts down in about {math.ceil(soon)} s."),
            "wait": self.note_every, "note": text}  # as it will pop up, for the accounts site's moderation

    def tick(self):
        """Once a second: look at the Clock, and send the next note down when its turn has come."""
        clock = self.sky.clock()
        with self.lock:
            if clock is not None:
                self.clock, self.clock_at = clock, time.time()
            nxt = self.notes[0] if self.notes and time.time() - self.note_sent >= self.note_gap else None
        if nxt:
            _, name, text, ref = nxt
            result = self.sky.call("Note", text=text)
            with self.lock:
                if not result.endswith(("NoClearSpot", "NobodyHere")) and not result.startswith("SkyFailed:World"):
                    self.notes.popleft()  # sent, or refused for good: either way its turn is over
                self.note_sent = time.time()
            if result.startswith("SkyDone:"):
                self.popup("note", name, "Note", text, ref=ref)

    def status(self, client):
        c = self.clock or {}
        clock = {"hour": c.get("TimeOfDay"), "day": c.get("Day"), "rain": c.get("Rain") or 0, "fog": c.get("Fog") or 0,
                 "wind": math.hypot(c.get("WindX") or 0, c.get("WindZ") or 0), "quake": c.get("QuakePhase") or ""}
        godling = None
        if c.get("GodlingHealth") is not None:
            godling = {"health": c.get("GodlingHealth"), "hunger": c.get("GodlingHunger"), "wet": c.get("GodlingWet") or 0,
                       "cold": bool(c.get("GodlingCold")), "bracing": bool(c.get("GodlingBracing")),
                       "knockedDown": bool(c.get("GodlingKnockedDown"))}
        with self.lock:
            mine = self.last_note.get(client, 0)
            notes = {"limit": NOTE_LIMIT, "every": self.note_every, "queue": len(self.notes),
                     "wait": max(0, math.ceil(self.note_every - (time.time() - mine))) if mine else 0}
            popups = list(self.popups)
        return {"clock": clock, "godling": godling, "notes": notes, "popups": popups}


def serve(world, port, run_dir=None, view=None, note_every=180, note_gap=60, key="", host="127.0.0.1"):
    base = world.rstrip("/")
    island = Island(Sky(base), note_every, note_gap, trusted=bool(key), run_dir=run_dir)
    powers = {p[0] for p in POWERS if p[0] != "Note"}  # a note comes through /api/note, with its text checked

    def keep_looking():
        while True:
            try:
                island.tick()
            except Exception as err:  # noqa: BLE001 (the panel outlives one bad look)
                print(f"Guest panel: {err}", flush=True)
            time.sleep(1)

    threading.Thread(target=keep_looking, daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        timeout = 10  # seconds a connection may sit idle: a client that trickles its request in is let go

        def _send(self, body, kind="application/json", code=200, headers=None):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            for name, value in {"Cache-Control": "no-store", **(headers or {})}.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)

        def _json(self, value, code=200):
            self._send(json.dumps(value), code=code)

        def _body(self):
            try:
                size = max(0, min(int(self.headers.get("Content-Length") or 0), 4096))
                body = json.loads(self.rfile.read(size) or b"{}")
                return body if isinstance(body, dict) else {}
            except ValueError:
                return {}

        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            if url.path == "/api/status":
                client = clean_client((urllib.parse.parse_qs(url.query).get("client") or [""])[0])
                self._json({"world": time.time() - island.clock_at < 5, "view": island_url(view) if view else spectator_url(base, run_dir),
                            "watching": island.watching(client), "testMode": True, "now": time.time(),
                            "mind": mind_status(run_dir), **island.status(client)})
                return
            if url.path.startswith(("/api/replay/", "/replay/")):
                return self._replay(url)
            path = (VIEWER / (urllib.parse.unquote(url.path).lstrip("/") or "index.html")).resolve()
            if not path.is_relative_to(VIEWER) or not path.is_file():
                return self._send("Not here.", "text/plain", 404)
            kind = "text/javascript" if path.suffix == ".js" else mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self._send(path.read_bytes(), kind + ("; charset=utf-8" if kind.startswith("text/") else ""))

        def _replay(self, url):
            """Replays (ADR-016): the index, the screen's tracks, the timeline's markers and sky, and the chunks."""
            if not run_dir:
                return self._json({"ok": False, "text": "No replays without --run-dir."}, 404)
            query = urllib.parse.parse_qs(url.query)
            if url.path == "/api/replay/index":  # chunks from here; with a bucket, those up before chunks_url_until there
                return self._json({**replay.read_index(run_dir), "chunks": "replay"})
            if url.path == "/api/replay/tracks":
                got = span(query, 3 * 3_600_000)
                return self._json(replay_tracks(run_dir, *got) if got else {"ok": False}, 200 if got else 400)
            if url.path in ("/api/replay/marks", "/api/replay/sky"):
                got = span(query, 8 * 86_400_000)
                if not got:
                    return self._json({"ok": False}, 400)
                if url.path.endswith("marks"):
                    return self._json(replay.read_marks(run_dir, *got))
                try:  # a long timeline needs far fewer samples than one a minute
                    every = max(replay.SKY_EVERY_MS, int((query.get("every") or ["0"])[0]))
                except ValueError:
                    every = replay.SKY_EVERY_MS
                return self._json(replay.read_sky(run_dir, *got, every))
            chunk = replay.chunk_file(run_dir, url.path.removeprefix("/replay/"))
            if chunk is None:  # a chunk not written yet: not to be kept, and readable by the island's page
                return self._send("Not here.", "text/plain", 404, {"Access-Control-Allow-Origin": "*"})
            # Written once and never changed: kept for good. The island's page fetches them; they hold nobody's data.
            self._send(chunk.read_bytes(), "application/gzip", 200, {"Cache-Control": "public, max-age=31536000, immutable",
                                                                    "Access-Control-Allow-Origin": "*"})

        def do_POST(self):
            url = urllib.parse.urlsplit(self.path)
            body = self._body()  # read first: a reply to an unread request reaches Windows callers as a reset connection
            if key and not hmac.compare_digest(self.headers.get("X-Godling-Key", ""), key):
                return self._json({"ok": False, "text": "Sign in on the site to call powers and send notes."}, 403)
            # JSON only: a browser asks first before sending JSON to another origin, and this panel never says yes,
            # so a web page elsewhere cannot call powers here (a plain-text or form post would not ask).
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                return self._json({"ok": False, "text": "Send JSON."}, 415)
            client, name = clean_client(body.get("client")), clean_name(body.get("name"))
            if not client:
                return self._json({"ok": False, "text": "Reload the page."}, 400)
            if url.path == "/api/power":
                if body.get("power") not in powers:
                    return self._json({"ok": False, "text": "Unknown power."}, 400)
                at = body.get("at")  # where the viewer aimed, [x, z] on the island; none lets the world choose
                ok_at = (isinstance(at, list) and len(at) == 2 and all(isinstance(v, (int, float)) and math.isfinite(v)
                                                                      and abs(v) < 2000 for v in at))
                return self._json(island.power(client, name, body["power"], [round(v, 2) for v in at] if ok_at else None))
            if url.path == "/api/note":
                ref = body.get("ref") if key and type(body.get("ref")) is int else None  # the site's id for the note
                return self._json(island.note(client, name, body.get("text"), ref))
            self._json({}, 404)

        def log_message(self, *args):  # quiet: the run's own console is busy enough
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Guest panel: http://localhost:{port}/ (world {base})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="http://localhost:8080")
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--run-dir", type=Path, default=None, help="show what Godling thinks, needs and noticed")
    ap.add_argument("--view", default=None, help="the spectator link the world printed (found in the run's world.log "
                                                 "with --run-dir)")
    ap.add_argument("--note-every", type=int, default=180, help="seconds between one viewer's notes")
    ap.add_argument("--note-gap", type=int, default=60, help="seconds between any two notes reaching the island")
    ap.add_argument("--key", default=os.environ.get("GODLING_PANEL_KEY", ""),
                    help="powers and notes only from whoever sends this key (the accounts site, web/; ADR-012); "
                         "default $GODLING_PANEL_KEY, empty for none")
    ap.add_argument("--host", default=os.environ.get("GODLING_PANEL_HOST", "127.0.0.1"),
                    help="the address to listen on (deploy/: 0.0.0.0, inside the island container, with --key); "
                         "default $GODLING_PANEL_HOST or 127.0.0.1")
    args = ap.parse_args()
    if args.host not in ("127.0.0.1", "localhost") and not args.key:
        ap.error("listening beyond this machine needs --key: the panel trusts whoever calls it")
    key_file = args.run_dir.expanduser() / "world.key" if args.run_dir else None
    if key_file and key_file.exists() and not os.environ.get("WORLD_AGENT_KEY"):
        os.environ["WORLD_AGENT_KEY"] = key_file.read_text().strip()  # the run's world asks for it (ADR-014)
    serve(args.world, args.port, args.run_dir.expanduser().resolve() if args.run_dir else None, args.view,
          args.note_every, args.note_gap, args.key, args.host)


if __name__ == "__main__":
    main()
