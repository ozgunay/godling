"""Replay (ADR-016): the world's raw recordings packed into small chunks a browser plays on its own, and the screen's
tracks kept beside them (what Godling thought, needed and noticed, what viewers did, markers for the timeline).

The world records itself (`clawblox run --record`): one SQLite file per world start, holding a full snapshot of what
spectators see every second and a delta every tick, about 5 GB a day. The packer follows the newest file, rebuilds the
state tick by tick, and every 10 s writes one chunk of it at 10 frames a second: a keyframe and the changes after it,
gzipped (about 2.2 KB/s). Each viewer's browser fetches the chunks around its own playhead and plays them; the server
only serves files, and the live world is never touched (the recording is read, never written).

Under <run>/replay/:
    index.json                               the segments (one per world start) and the gaps between them
    chunks/<YYYY-MM-DD>/<HH>/<t0>.json.gz    10 s each, named by their start in UTC milliseconds
    tracks/<YYYY-MM-DD>/<HH>.jsonl           the mind's log entries the screen shows (decision, bubble, project, event,
                                             glance), as the guest panel reads them live
    marks/<YYYY-MM-DD>.jsonl                 markers for the timeline
    sky/<YYYY-MM-DD>.jsonl                   once a minute: the island's hour, day, rain and fog, to shade the timeline
    acts/<YYYY-MM-DD>.jsonl                  what viewers did, written by the guest panel
    state.json                               how far the packer has got

Usage: python3 -m godling.replay follow <run-dir>           keep packing as the world records, until SIGINT or SIGTERM
       python3 -m godling.replay pack <run-dir>             pack what is there, then stop
       python3 -m godling.replay check <run-dir> [samples]  replayed states against the raw recording, at random times
run_godling.py runs `follow` beside the world, in a process of its own, so packing never holds up Godling's mind.
"""
import datetime as dt
import gzip
import json
import math
import os
import queue
import random
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

FORMAT = 1  # of chunks, tracks and the index; a browser meeting a newer one says so rather than drawing it wrong
CHUNK_MS = 10_000
RATE = 10  # frames a second in replay (ADR-016 D3): the renderer smooths between them
FRAME_MS = 1000 // RATE
SKY_EVERY_MS = 60_000
MARK_APART = 20_000  # markers of one kind closer than this are one
FEED_KEPT = 8  # the guest panel's: lines of Godling's feed the screen gets
LEAD_HOURS = 48  # how far back to look for what the screen showed when a replay starts
KEEP_RAW_DAYS = float(os.environ.get("GODLING_REPLAY_RAW_DAYS", "3"))  # ADR-016 D4: raw recordings, for debugging
KEEP_EVERY = 600  # seconds between keeping jobs
DISK_WARN = 0.8  # warn when the disk is this full
ROWS_AT_ONCE = 1800  # recording rows read per step: about 30 s of the world
TRACKED = {"decision": ("thought", "needs"), "bubble": ("ok", "thing", "feeling"),
           "project": ("phase", "goal", "intention"), "event": ("text", "sky", "sky_stage", "sky_id"),
           "glance": ("text", "degrees", "turned")}
CHUNK_REL = re.compile(r"chunks/\d{4}-\d\d-\d\d/\d\d/\d{13}\.json\.gz")

try:  # the island image has the zstd tool; a development machine may have the module instead
    import zstandard
    _ZSTD = zstandard.ZstdDecompressor()
except ImportError:
    _ZSTD = None


# ---- time and places ------------------------------------------------------------------------------------------------

def utc_ms(text):
    """Milliseconds since 1970 from an RFC 3339 time such as Clawblox writes ("2026-11-02T21:11:35.790514128+00:00")."""
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?(Z|[+-]\d\d:\d\d)?$", str(text).strip())
    if not m:
        raise ValueError(f"not a time: {text!r}")
    zone = (m.group(3) or "+00:00").replace("Z", "+00:00")
    base = dt.datetime.fromisoformat(m.group(1) + zone)
    return int(base.timestamp() * 1000) + int(float("0" + (m.group(2) or ".0")) * 1000)


def day_hour(ms):
    t = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)
    return t.strftime("%Y-%m-%d"), t.strftime("%H")


def chunk_rel(t0):
    day, hour = day_hour(t0)
    return f"chunks/{day}/{hour}/{t0}.json.gz"


def _write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _append(path, entries):
    if not entries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write("".join(json.dumps(e, separators=(",", ":")) + "\n" for e in entries))


def _read_lines(path):
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue  # a line cut off by a crash
    except FileNotFoundError:
        return


# ---- the raw recording ----------------------------------------------------------------------------------------------

def unzstd(blobs):
    """Each zstd blob of a recording, as the JSON it holds. Without the module, one zstd process for the lot: frames
    one after another decompress to their contents one after another."""
    if not blobs:
        return []
    if _ZSTD is not None:
        return [json.loads(_ZSTD.decompressobj().decompress(b)) for b in blobs]
    out = subprocess.run(["zstd", "-dcq"], input=b"".join(blobs), capture_output=True, check=True).stdout.decode()
    decoder, i, objs, n = json.JSONDecoder(), 0, [], len(out)
    while i < n:
        obj, i = decoder.raw_decode(out, i)
        objs.append(obj)
        while i < n and out[i].isspace():
            i += 1
    if len(objs) != len(blobs):
        raise ValueError(f"{len(blobs)} blobs held {len(objs)} documents")
    return objs


class Recording:
    """One .clawrec, read only: the world goes on writing it (SQLite readers never block its writer)."""

    def __init__(self, path):
        self.path = Path(path)
        self.id = self.path.stem
        self.db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, timeout=10, check_same_thread=False)
        self.start_ms = utc_ms(self.meta()["created_at"])

    def meta(self):
        return dict(self.db.execute("select key, value from meta"))

    def checkpoint_before(self, time_ms):
        """The last full snapshot at or before `time_ms` (recording time), or the first: (tick, time_ms, observation)."""
        row = (self.db.execute("select tick, time_ms, data from checkpoints where time_ms <= ? order by tick desc limit 1",
                               (time_ms,)).fetchone()
               or self.db.execute("select tick, time_ms, data from checkpoints order by tick limit 1").fetchone())
        return (row[0], row[1], unzstd([row[2]])[0]) if row else None

    def rows_after(self, tick, limit=ROWS_AT_ONCE):
        """Snapshots and deltas after `tick`, in order, as (tick, time_ms, is_snapshot, document), and whether more
        follow. Two indexed reads merged here: one sorted union would sort the whole rest of a long file each time."""
        deltas = self.db.execute("select tick, time_ms, data from deltas where tick > ? order by tick limit ?",
                                 (tick, limit)).fetchall()
        more = len(deltas) == limit
        if more:
            snaps = self.db.execute("select tick, time_ms, data from checkpoints where tick > ? and tick <= ? "
                                    "order by tick", (tick, deltas[-1][0])).fetchall()
        else:
            snaps = self.db.execute("select tick, time_ms, data from checkpoints where tick > ? order by tick",
                                    (tick,)).fetchall()
        rows = sorted([(t, ms, True, d) for t, ms, d in snaps] + [(t, ms, False, d) for t, ms, d in deltas],
                      key=lambda r: (r[0], not r[2]))
        return [(r[0], r[1], r[2], doc) for r, doc in zip(rows, unzstd([r[3] for r in rows]))], more

    def close(self):
        self.db.close()


class State:
    """The full spectator observation, rebuilt from snapshots and deltas (as Clawblox's recording.rs apply_delta)."""

    def __init__(self, obs):
        self.reset(obs)

    def reset(self, obs):
        self.top = {k: v for k, v in obs.items() if k != "entities"}
        self.ents = {e["id"]: e for e in obs.get("entities", ())}

    def apply(self, delta):
        for e in delta.get("entities", ()):
            i = e.get("id")
            if "add" in e:
                self.ents[i] = e["add"]
            elif e.get("rm"):
                self.ents.pop(i, None)
            elif i in self.ents:
                cur = dict(self.ents[i])  # a new dict for a changed entity: the packer's memo tells by identity
                if e.get("p") is not None:
                    cur["position"] = e["p"]
                if e.get("r") is not None:
                    cur["rotation"] = e["r"]
                self.ents[i] = cur
        for p in delta.get("players", ()):
            if "replace" in p:
                self.top["players"] = p["replace"]
            else:
                self.top["players"] = [
                    {**q, **({"position": p["p"]} if p.get("p") is not None else {}),
                     **({"health": p["health"]} if p.get("health") is not None else {})}
                    if q.get("id") == p.get("id") else q for q in self.top.get("players", ())]
        for key in ("sounds", "recent_events"):  # snapshots of their own: absent means unchanged
            if delta.get(key) is not None:
                self.top[key] = delta[key]


# ---- what a replay frame holds --------------------------------------------------------------------------------------

def _round_attrs(attrs):
    return {k: round(v, 3) if isinstance(v, float) else v for k, v in attrs.items()}


def slim_entity(e):
    """An entity as replay keeps it: positions to a hundredth, rotations and attributes to a thousandth."""
    out = dict(e)
    if out.get("position") is not None:
        out["position"] = [round(v, 2) for v in out["position"]]
    if out.get("rotation") is not None:
        out["rotation"] = [[round(v, 3) for v in row] for row in out["rotation"]]
    if out.get("attributes"):
        out["attributes"] = _round_attrs(out["attributes"])
    return out


def slim_players(players):
    out = []
    for p in players or ():
        q = dict(p)
        if q.get("position") is not None:
            q["position"] = [round(v, 2) for v in q["position"]]
        if q.get("attributes"):
            q["attributes"] = _round_attrs(q["attributes"])
        out.append(q)
    return out


TOP_KEPT = ("players", "recent_events", "sounds", "game_status")  # what a frame repeats when it changed


class _Segment:
    """The recording being packed: its rebuilt state, the window of frames being gathered, and what came before."""

    def __init__(self, packer, rec, info):
        self.packer, self.rec, self.id = packer, rec, rec.id
        self.info = info  # its entry in state.json
        self.memo = {}  # entity id -> (the state's dict, its slim copy): unchanged entities are not copied again
        self.window_t0, self.frames, self.prev = None, [], None
        self.clock_id = None
        self.last_wall = None
        resume = info.get("window")  # the window being gathered when the packer last stopped: gather it again
        ck = rec.checkpoint_before((resume - rec.start_ms) if resume else 0)
        if ck is None:
            raise ValueError("no snapshot yet")
        self.tick = ck[0]
        self.state = State(ck[2])
        self.state.top.update(tick=ck[0], server_time_ms=ck[1])
        first = rec.start_ms + ck[1]
        # A segment starts at the window after its first moment, so two segments never share a window.
        self.next_sample = resume or int(math.ceil(first / CHUNK_MS) * CHUNK_MS)
        if resume is None:
            info.setdefault("start", self.next_sample)

    def step(self, rows):
        for tick, time_ms, full, doc in rows:
            wall = self.rec.start_ms + time_ms
            self._frames_before(wall)
            if full:
                self.state.reset(doc)
            else:
                self.state.apply(doc)
            self.state.top.update(tick=tick, server_time_ms=time_ms)
            self.tick, self.last_wall = tick, wall

    def finish(self):
        """The recording has ended: frames up to its last moment, and the last window, however short."""
        if self.last_wall is not None:
            self._frames_before(self.last_wall + FRAME_MS)
        self._flush()

    def _frames_before(self, wall):
        """The frames due before the moment `wall`: the state as it is holds for all of them."""
        while self.next_sample < wall:
            self._frame(self.next_sample)
            self.next_sample += FRAME_MS

    def _slim(self):
        ents = {}
        for i, e in self.state.ents.items():
            seen = self.memo.get(i)
            if seen is None or seen[0] is not e:
                seen = (e, slim_entity(e))
                self.memo[i] = seen
            ents[i] = seen[1]
        for i in [i for i in self.memo if i not in self.state.ents]:
            del self.memo[i]
        top = dict(self.state.top)
        top["players"] = slim_players(top.get("players"))
        return ents, top

    def _frame(self, t):
        if self.window_t0 is not None and t >= self.window_t0 + CHUNK_MS:
            self._flush()
        ents, top = self._slim()
        if self.window_t0 is None:
            self.window_t0 = t - t % CHUNK_MS
            self.info["window"] = self.window_t0
            frame = {"t": t, "full": {**top, "entities": list(ents.values())}}
        else:
            prev_ents, prev_top = self.prev
            changed = []
            for i, e in ents.items():
                p = prev_ents.get(i)
                if p is e:
                    continue
                if p is None or {k: v for k, v in e.items() if k not in ("position", "rotation")} != \
                        {k: v for k, v in p.items() if k not in ("position", "rotation")} or \
                        ("rotation" in e) != ("rotation" in p) or ("position" in e) != ("position" in p):
                    # Anything but where it is and how it turns (or a turn gone: a tool set down): the whole entity.
                    changed.append({"add": e})
                    continue
                u = {"id": i}
                if e.get("position") != p.get("position"):
                    u["p"] = e.get("position")
                if e.get("rotation") != p.get("rotation"):
                    u["r"] = e.get("rotation")
                if len(u) > 1:
                    changed.append(u)
            changed += [{"id": i, "rm": 1} for i in prev_ents if i not in ents]
            frame = {"t": t, "tick": top.get("tick"), "ms": top.get("server_time_ms")}
            if changed:
                frame["e"] = changed
            for key in TOP_KEPT:
                if top.get(key) != prev_top.get(key):
                    frame[key] = top.get(key)
        self.frames.append(frame)
        self.prev = (ents, top)
        self.packer.seen_frame(t, ents, top, self)

    def _flush(self):
        if not self.frames:
            return
        t0 = self.window_t0
        chunk = {"format": FORMAT, "segment": self.id, "t0": t0, "t1": self.frames[-1]["t"] + FRAME_MS, "rate": RATE,
                 "frames": self.frames}
        rel = chunk_rel(t0)
        path = self.packer.root / rel
        _write_atomic(path, gzip.compress(json.dumps(chunk, separators=(",", ":")).encode(), 9, mtime=0))
        self.packer.store.put(rel, path)
        self.info["end"] = chunk["t1"]
        self.info["chunks"] = self.info.get("chunks", 0) + 1
        self.window_t0, self.frames = None, []
        self.info["window"] = None


# ---- where chunks go ------------------------------------------------------------------------------------------------

class LocalStore:
    """Chunks stay in <run>/replay/chunks, served from there (the guest panel, or Caddy from the runs volume)."""
    url = None

    def put(self, rel, path):
        pass

    def keep(self, root):
        pass

    def stop(self):
        pass


class S3Store:
    """Chunks also go to S3-compatible object storage (ADR-016: Cloudflare R2, Hetzner, or Amazon S3; endpoint and keys
    from the environment). Viewers fetch them from its public address; the local copies are kept LOCAL_DAYS for the
    newest replays and then deleted, once uploaded."""
    LOCAL_DAYS = 2

    def __init__(self, root, log, bucket, endpoint, key_id, secret, public_url, prefix="", region="auto"):
        import boto3  # only here: a run without a bucket needs no boto3
        self.root, self.log, self.bucket, self.prefix = root, log, bucket, prefix.strip("/")
        self.url = public_url.rstrip("/") + (f"/{self.prefix}" if self.prefix else "")
        self.s3 = boto3.client("s3", endpoint_url=endpoint or None, aws_access_key_id=key_id,
                               aws_secret_access_key=secret, region_name=region)
        self.cursor_file = root / "uploaded.txt"  # the newest chunk uploaded: everything before it is up too
        self.cursor = self.cursor_file.read_text().strip() if self.cursor_file.exists() else ""
        self.todo = queue.Queue()
        for path in sorted(root.glob("chunks/*/*/*.json.gz")):  # what the last run wrote but did not get up
            rel = path.relative_to(root).as_posix()
            if rel > self.cursor:
                self.todo.put(rel)
        self.thread = threading.Thread(target=self._run, name="replay-upload", daemon=True)
        self.thread.start()

    def put(self, rel, path):
        self.todo.put(rel)

    def _run(self):
        while True:
            rel = self.todo.get()
            if rel is None:
                return
            for attempt in range(8):
                try:
                    self.s3.put_object(Bucket=self.bucket, Key=f"{self.prefix}/{rel}" if self.prefix else rel,
                                       Body=(self.root / rel).read_bytes(), ContentType="application/gzip",
                                       CacheControl="public, max-age=31536000, immutable")
                    if rel > self.cursor:
                        self.cursor = rel
                        self.cursor_file.write_text(rel)
                    break
                except FileNotFoundError:
                    break
                except Exception as err:  # noqa: BLE001 (the network: try again, then give up on this one)
                    self.log(kind="error", message=f"replay upload {rel}: {err!r}"[:300])
                    time.sleep(min(60, 2 ** attempt))

    def keep(self, root):
        cutoff = day_hour(time.time() * 1000 - self.LOCAL_DAYS * 86_400_000)[0]
        uploaded_day = self.cursor.split("/")[1] if self.cursor.count("/") >= 2 else ""
        for day in sorted((root / "chunks").glob("*")):
            if day.name < cutoff and day.name < uploaded_day:
                shutil.rmtree(day, ignore_errors=True)

    def stop(self):
        self.todo.put(None)
        self.thread.join(timeout=30)


def store_from_env(root, log):
    bucket = os.environ.get("GODLING_REPLAY_BUCKET", "")
    if not bucket:
        return LocalStore()
    return S3Store(root, log, bucket, os.environ.get("GODLING_REPLAY_ENDPOINT", ""),
                   os.environ.get("GODLING_REPLAY_KEY_ID", ""), os.environ.get("GODLING_REPLAY_SECRET", ""),
                   os.environ.get("GODLING_REPLAY_PUBLIC_URL", ""), os.environ.get("GODLING_REPLAY_PREFIX", ""),
                   os.environ.get("GODLING_REPLAY_REGION", "auto"))


# ---- the packer -----------------------------------------------------------------------------------------------------

def marks_of(entry, best):
    """Markers for the timeline from one entry of the mind's log (ADR-016 D8). `best` keeps the most walls, roofs and
    enclosures seen, so a structure marker means a new one."""
    kind, text = entry.get("kind"), str(entry.get("text") or entry.get("summary") or "")
    if kind == "event":
        sky, stage = entry.get("sky"), entry.get("sky_stage")
        if sky and stage != "warning":
            return [str(sky).lower()]
        for start, mark in (("It has started to rain", "rain"), ("Fog has rolled in", "fog"),
                            ("A ship is passing", "ship"), ("You were hurt", "hurt")):
            if text.startswith(start):
                return [mark]
        if " has gone out" in text:
            return ["fire-out"]
    elif kind == "skill" and entry.get("ok"):
        if "a flame caught" in text:
            return ["fire"]
        if text.startswith("speared "):
            return ["fish"]
    elif kind == "structures":
        out = []
        for key, mark in (("walls", "wall"), ("roofed", "roof"), ("enclosures", "enclosure")):
            n = entry.get(key) or 0
            if n > best.get(key, 0):
                best[key] = n
                out.append(mark)
        return out
    return []


class Packer:
    """Follows <run>/recordings and the mind's log, and keeps <run>/replay up to date. One thread; start() and stop()."""

    def __init__(self, run, log=None, store=None):
        self.run = Path(run)
        self.root = self.run / "replay"
        self.root.mkdir(parents=True, exist_ok=True)
        self.log = log or (lambda **kw: None)
        self.store = store if store is not None else store_from_env(self.root, self.log)
        state_file = self.root / "state.json"
        self.state = json.loads(state_file.read_text()) if state_file.exists() else {}
        self.state.setdefault("segments", {})
        self.state.setdefault("log_offset", 0)
        self.state.setdefault("best", {})
        self.cur = None
        self.stopping = threading.Event()
        self.thread = None
        self.kept_at = 0
        self.warned_at = 0
        self.sky_next = 0
        self.faints = None
        self.marks = []
        self.marked = {}  # marker -> when it was last set: one event often says itself twice (a landing, a blast)

    def start(self):
        self.thread = threading.Thread(target=self._run, name="replay-packer", daemon=True)
        self.thread.start()
        return self

    def stop(self):
        """Stop, after packing what the world wrote last (call it once the world has stopped)."""
        self.stopping.set()
        if self.thread is not None:
            self.thread.join(timeout=60)
        self.store.stop()

    def _run(self):
        while not self.stopping.is_set():
            try:
                self.pack_once()
            except Exception as err:  # noqa: BLE001 (the packer outlives one bad step; the live world never waits on it)
                self.log(kind="error", message=f"replay packer: {err!r}"[:300])
                self.cur = None
                self.stopping.wait(10)
            self.stopping.wait(2)
        try:
            self.pack_once(final=True)
        except Exception as err:  # noqa: BLE001
            self.log(kind="error", message=f"replay packer at the end: {err!r}"[:300])

    def pack_once(self, final=False):
        recs = sorted((self.run / "recordings").glob("*.clawrec"))
        for i, path in enumerate(recs):
            info = self.state["segments"].setdefault(path.stem, {})
            if info.get("done"):
                continue
            self._pack(path, info, closing=final or i < len(recs) - 1)
        self._tracks()
        self._flush_marks()
        self._write_index()
        if final or time.time() - self.kept_at > KEEP_EVERY:
            self._keep(recs)
        _write_atomic(self.root / "state.json", json.dumps(self.state).encode())

    def _pack(self, path, info, closing):
        seg = self.cur
        if seg is None or seg.id != path.stem:
            if seg is not None:
                seg.rec.close()
            try:
                seg = _Segment(self, Recording(path), info)
            except (sqlite3.Error, ValueError, KeyError):
                if closing:  # a recording with nothing in it (a world that never came up)
                    info["done"] = True
                return
        while True:
            rows, more = seg.rec.rows_after(seg.tick)
            seg.step(rows)
            if not more or self.stopping.is_set() and not closing:
                break
        if closing:
            seg.finish()
            info["done"] = True
            seg.rec.close()
            self.cur = None
        else:
            self.cur = seg

    def seen_frame(self, t, ents, top, seg):
        """Called for every frame: the timeline's sky strip, and markers the world shows but the mind's log does not."""
        if seg.clock_id not in ents:
            seg.clock_id = next((i for i, e in ents.items() if "TimeOfDay" in (e.get("attributes") or {})), None)
        if t >= self.sky_next and seg.clock_id is not None:
            a = ents[seg.clock_id].get("attributes") or {}
            day, _ = day_hour(t)
            _append(self.root / f"sky/{day}.jsonl", [{"t": t, "hour": a.get("TimeOfDay"), "day": a.get("Day"),
                                                       "rain": a.get("Rain") or 0, "fog": a.get("Fog") or 0}])
            self.sky_next = t - t % SKY_EVERY_MS + SKY_EVERY_MS
        players = top.get("players") or []
        faints = (players[0].get("attributes") or {}).get("Faints") if players else None
        if isinstance(faints, (int, float)):
            if self.faints is not None and faints > self.faints:
                self.marks.append({"t": t, "m": "faint"})
            self.faints = faints

    def _tracks(self):
        """New lines of the mind's log: the ones the screen shows go to the tracks, and markers to the timeline."""
        path = self.run / "mind/log.jsonl"
        if not path.exists():
            return
        offset = self.state["log_offset"]
        if path.stat().st_size < offset:  # a new log
            offset = 0
        with path.open("rb") as f:
            f.seek(offset)
            data = f.read(8_000_000)
        end = data.rfind(b"\n")
        if end < 0:
            return
        hours = {}
        for line in data[:end].decode("utf-8", "replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            t = e.get("time")
            if not isinstance(t, (int, float)):
                continue
            t = int(t * 1000)
            kind = e.get("kind")
            fields = TRACKED.get(kind)
            if fields and (kind != "project" or e.get("phase") == "start") and (kind != "bubble" or e.get("ok")):
                day, hour = day_hour(t)
                hours.setdefault(f"tracks/{day}/{hour}.jsonl", []).append(
                    {"time": round(t / 1000, 3), "kind": kind, **{k: e[k] for k in fields if k in e}})
            for mark in marks_of(e, self.state["best"]):
                if t - self.marked.get(mark, -MARK_APART) >= MARK_APART:
                    self.marks.append({"t": t, "m": mark})
                    self.marked[mark] = t
        for rel, entries in hours.items():
            _append(self.root / rel, entries)
        self.state["log_offset"] = offset + end + 1

    def _flush_marks(self):
        by_day = {}
        for m in self.marks:
            by_day.setdefault(day_hour(m["t"])[0], []).append(m)
        for day, marks in by_day.items():
            _append(self.root / f"marks/{day}.jsonl", marks)
        self.marks = []

    def _write_index(self):
        segments = [{"id": sid, "start": info["start"], "end": info["end"], "live": not info.get("done")}
                    for sid, info in sorted(self.state["segments"].items()) if info.get("start") and info.get("end")]
        index = {"format": FORMAT, "chunk_ms": CHUNK_MS, "rate": RATE, "updated": int(time.time() * 1000),
                 "segments": segments}
        if self.store.url:  # chunks also in object storage: browsers fetch them from there
            index["chunks_url"] = self.store.url
        _write_atomic(self.root / "index.json", json.dumps(index, separators=(",", ":")).encode())

    def _keep(self, recs):
        """Raw recordings older than KEEP_RAW_DAYS go once they are packed (never the newest); a full disk is said."""
        self.kept_at = time.time()
        cutoff = time.time() - KEEP_RAW_DAYS * 86_400
        for path in recs[:-1]:
            info = self.state["segments"].get(path.stem, {})
            if info.get("done") and path.stat().st_mtime < cutoff:
                for extra in (path, path.with_suffix(".replay.toml"), Path(f"{path}-wal"), Path(f"{path}-shm")):
                    extra.unlink(missing_ok=True)
                info["raw"] = "deleted"
        self.store.keep(self.root)
        usage = shutil.disk_usage(self.run)
        full = usage.used / usage.total if usage.total else 0
        if full >= DISK_WARN and time.time() - self.warned_at > 3600:
            self.warned_at = time.time()
            self.log(kind="alarm", message=f"the disk under {self.run} is {full:.0%} full "
                                           f"({usage.free / 1e9:.1f} GB free): replay and recordings need room")


# ---- reading it back (the guest panel and the site serve these) -----------------------------------------------------

def _hours(t_from, t_to):
    t = t_from - t_from % 3_600_000
    while t <= t_to:
        yield t
        t += 3_600_000


def _days(t_from, t_to):
    t = t_from - t_from % 86_400_000
    while t <= t_to:
        yield day_hour(t)[0]
        t += 86_400_000


def read_index(run):
    path = Path(run) / "replay/index.json"
    index = json.loads(path.read_text()) if path.exists() else {"format": FORMAT, "chunk_ms": CHUNK_MS, "rate": RATE,
                                                                  "segments": []}
    index["now"] = int(time.time() * 1000)
    return index


def read_tracks(run, t_from, t_to):
    """The screen's tracks from `t_from` to `t_to` (ms): `entries` in that span, and `lead`, the entries before it that
    say what the screen showed at `t_from` (the last thought, bubble and intention, and the feed)."""
    root = Path(run) / "replay"
    entries = [e for h in _hours(t_from, t_to) for e in _read_lines(root / ("tracks/%s/%s.jsonl" % day_hour(h)))
               if t_from <= e.get("time", 0) * 1000 <= t_to]
    lead, want = [], {"decision", "bubble", "project"}
    feed = 0
    for h in list(_hours(t_from - LEAD_HOURS * 3_600_000, t_from))[::-1]:
        for e in reversed(list(_read_lines(root / ("tracks/%s/%s.jsonl" % day_hour(h))))):
            if e.get("time", 0) * 1000 >= t_from:
                continue
            kind = e.get("kind")
            if kind in want or kind in ("decision", "event", "glance") and feed < FEED_KEPT:
                lead.append(e)
                want.discard(kind)
                feed += kind in ("decision", "event")
        if not want and feed >= FEED_KEPT:
            break
    lead.reverse()
    return {"format": FORMAT, "from": t_from, "to": t_to, "lead": lead, "entries": entries,
            "acts": read_acts(run, t_from, t_to)}


def read_marks(run, t_from, t_to):
    root = Path(run) / "replay"
    return [m for d in _days(t_from, t_to) for m in _read_lines(root / f"marks/{d}.jsonl") if t_from <= m["t"] <= t_to]


def read_sky(run, t_from, t_to):
    root = Path(run) / "replay"
    return [s for d in _days(t_from, t_to) for s in _read_lines(root / f"sky/{d}.jsonl") if t_from <= s["t"] <= t_to]


def read_acts(run, t_from, t_to):
    root = Path(run) / "replay"
    return [a for d in _days(t_from, t_to) for a in _read_lines(root / f"acts/{d}.jsonl")
            if t_from <= a.get("time", 0) * 1000 <= t_to]


def record_act(run, entry):
    """What a viewer did (a guest panel pop-up), kept for replays."""
    _append(Path(run) / f"replay/acts/{day_hour(entry['time'] * 1000)[0]}.jsonl", [entry])


def chunk_file(run, rel):
    """The chunk file for a request's path, or None: only real chunk names, never anything else in the run."""
    if not CHUNK_REL.fullmatch(rel or ""):
        return None
    path = Path(run) / "replay" / rel
    return path if path.is_file() else None


def reduce_status(entries, clean=lambda s: s, feed_kept=FEED_KEPT):
    """What the screen shows of Godling's mind after these log entries, in order: the guest panel's reading of the log,
    live (mind_status) and in replay alike."""
    out = {"thought": "", "needs": "", "intention": ""}
    feed = deque(maxlen=feed_kept)
    for e in entries:
        kind = e.get("kind")
        if kind == "decision":
            out["thought"], out["needs"] = clean(e.get("thought", "")), clean(e.get("needs", ""))
            if out["thought"] and (not feed or feed[-1]["text"] != out["thought"]):
                feed.append({"time": e.get("time"), "who": "godling", "text": out["thought"]})
        elif kind == "bubble" and e.get("ok"):
            out["bubble"] = {"thing": e.get("thing"), "feeling": e.get("feeling")}
        elif kind == "project" and e.get("phase") == "start":
            out["intention"] = clean(e.get("intention") or e.get("goal", ""))
        elif kind == "event":
            feed.append({"time": e.get("time"), "who": "sky" if e.get("sky") else "notice", "text": clean(e["text"]),
                         "glance": None})
        elif kind == "glance":
            seen = next((n for n in reversed(feed) if n["text"] == e.get("text") and n.get("glance", 0) is None), None)
            if seen:
                seen["glance"] = e.get("degrees") if e.get("turned") else 0
    out["feed"] = list(feed)
    return out


# ---- checking it (RP-03) --------------------------------------------------------------------------------------------

def _chunk_state(path, t):
    """Entities and players at the last frame at or before `t`, rebuilt from a chunk the way a browser does."""
    chunk = json.loads(gzip.decompress(path.read_bytes()))
    ents, players, at = None, None, None
    for f in chunk["frames"]:
        if f["t"] > t:
            break
        if "full" in f:
            ents = {e["id"]: e for e in f["full"]["entities"]}
            players = f["full"].get("players")
        else:
            for e in f.get("e", ()):
                if "add" in e:
                    ents[e["add"]["id"]] = e["add"]
                elif e.get("rm"):
                    ents.pop(e["id"], None)
                else:
                    ents[e["id"]] = {**ents[e["id"]], **({"position": e["p"]} if "p" in e else {}),
                                     **({"rotation": e["r"]} if "r" in e else {})}
            if "players" in f:
                players = f["players"]
        at = f["t"]
    return ents, players, at


def check(run, samples=200):
    """Replayed states against the raw recording at random times: the same entities, attributes and players, and
    positions within a hundredth (RP-03). Prints what differs; True when nothing does."""
    run = Path(run)
    index = read_index(run)
    bad = 0
    for _ in range(samples):
        seg = random.choice([s for s in index["segments"] if (run / "recordings" / f"{s['id']}.clawrec").exists()])
        t = random.randrange(seg["start"], seg["end"] - FRAME_MS)
        path = run / "replay" / chunk_rel(t - t % CHUNK_MS)
        ents, players, at = _chunk_state(path, t)
        rec = Recording(run / "recordings" / f"{seg['id']}.clawrec")
        tick, time_ms, obs = rec.checkpoint_before(at - rec.start_ms)
        state = State(obs)
        while True:
            rows, more = rec.rows_after(tick, 400)
            done = False
            for r_tick, r_ms, full, doc in rows:
                if rec.start_ms + r_ms > at:
                    done = True
                    break
                state.reset(doc) if full else state.apply(doc)
                tick = r_tick
            if done or not more:
                break
        rec.close()
        raw = {i: slim_entity(e) for i, e in state.ents.items()}
        diff = [i for i in set(raw) | set(ents) if raw.get(i) != ents.get(i)]
        pdiff = slim_players(state.top.get("players")) != players
        if diff or pdiff:
            bad += 1
            print(f"  {seg['id']} at {at}: {len(diff)} entities differ{' and the players' if pdiff else ''}"
                  f" (e.g. {diff[:3]})")
    print(f"checked {samples} moments: {samples - bad} the same, {bad} different")
    return bad == 0


def _say(**entry):
    print(json.dumps({"time": round(time.time(), 3), **entry}), flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("follow", "pack", "check"):
        sys.exit(__doc__)
    if sys.argv[1] == "follow":
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        packer = Packer(sys.argv[2], log=_say).start()
        _say(kind="start", message=f"packing {sys.argv[2]}/recordings for replays")
        while not stop.wait(3600):
            pass
        packer.stop()  # the world has stopped first (run_godling.py): its last seconds are packed too
        _say(kind="stop", message="packed")
    elif sys.argv[1] == "pack":
        packer = Packer(sys.argv[2], log=lambda **e: print(e, flush=True))
        packer.pack_once(final=True)
        packer.store.stop()
        print(json.dumps(read_index(sys.argv[2]), indent=1))
    else:
        sys.exit(0 if check(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 200) else 1)
