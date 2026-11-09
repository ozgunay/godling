"""Replay (ADR-016): the world's raw recordings packed into small chunks a browser plays on its own, and the screen's
tracks kept beside them (what Godling thought, needed and noticed, what viewers did, markers for the timeline).

The world records itself (`clawblox run --record`): one SQLite file per world start, holding a full snapshot of what
spectators see every second and a delta every tick, about 5 GB a day. The packer follows the newest file, rebuilds the
state tick by tick, and every 10 s writes one chunk of it at 10 frames a second: a keyframe and the changes after it,
gzipped (about 2.2 KB/s). Each viewer's browser fetches the chunks around its own playhead and plays them; the server
only serves files. The live world is never held up: the packer reads the recording, and only trims rows it has packed
and no longer keeps (KEEP_RAW_DAYS), a few thousand at a time.

Under <run>/replay/:
    index.json                               the segments (one per world start) and the gaps between them
    chunks/<YYYY-MM-DD>/<HH>/<t0>.json.gz    10 s each, named by their start in UTC milliseconds
    tracks/<YYYY-MM-DD>/<HH>.jsonl           the mind's log entries the screen shows (TRACKED: decision, bubble,
                                             project, thinking, learn, sleep, event, glance…), as the guest panel
                                             reads them live
    marks/<YYYY-MM-DD>.jsonl                 markers for the timeline
    sky/<YYYY-MM-DD>.jsonl                   once a minute: the island's hour, day, rain and fog, to shade the timeline
    acts/<YYYY-MM-DD>.jsonl                  what viewers did, written by the guest panel
    state.json                               how far the packer has got

Usage: python3 -m godling.replay follow <run-dir>           keep packing as the world records, until SIGINT or SIGTERM
       python3 -m godling.replay pack <run-dir> [--stopped] pack what is there, then stop (--stopped: the world has
                                                            stopped, so its last recording is closed too)
       python3 -m godling.replay check <run-dir> [samples]  replayed states against the raw recording, at random times
run_godling.py runs `follow` beside the world, in a process of its own, so packing never holds up Godling's mind.
"""
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import random
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:  # a setting that is not a number: the default, rather than no packer (or no guest panel)
        return float(default)


FORMAT = 1  # of chunks, tracks and the index; a browser meeting a newer one says so rather than drawing it wrong
CHUNK_MS = 10_000
RATE = 10  # frames a second in replay (ADR-016 D3): the renderer smooths between them
FRAME_MS = 1000 // RATE
SKY_EVERY_MS = 60_000
MARK_APART = 20_000  # markers of one kind with no event of their own to tell them apart, closer than this, are one
FEED_KEPT = 8  # lines of Godling's feed the screen gets, live (the guest panel) and in replay
LEAD_HOURS = 48  # how far back to look for what the screen showed when a replay starts
LEAD_MOST = 300  # entries of the lead since the last decision at most (a mind that has not decided for hours)
KEEP_RAW_DAYS = _env_float("GODLING_REPLAY_RAW_DAYS", 3)  # ADR-016 D4: raw recordings, for debugging
KEEP_EVERY = 600  # seconds between keeping jobs
TRIM_BATCH = 5000  # rows deleted from the live recording at once: a few milliseconds of the world's write lock
TRIM_EVERY = 3600  # seconds between trims of the live recording
SAVE_EVERY = 5  # seconds: how often a long catch-up writes down how far it has got
GIVE_UP_AFTER = 5  # failed passes in a row before an old recording that will not pack is left (said in replay.log)
DISK_WARN = 0.8  # warn when the disk is this full
ROWS_AT_ONCE = 1800  # recording rows read per step: about 30 s of the world
TRACKED = {"decision": ("thought", "needs"), "bubble": ("ok", "thing", "feeling"),
           "project": ("phase", "goal", "intention", "ok", "stopgap"), "thinking": (), "plan_discarded": (),
           "learn": ("name", "does"), "sleep": ("dream",), "death": ("cause", "feeling"),
           "event": ("text", "sky", "sky_stage", "sky_id"), "glance": ("text", "degrees", "turned")}
CHUNK_REL = re.compile(r"chunks/\d{4}-\d\d-\d\d/\d\d/\d{13}\.json\.gz")
ASSET_URL = re.compile(r"^(?:[^?#]*/)?assets/([^/?#]+)$")  # /assets/x.glb, /island/assets/x.glb, …
# A viewer's words the world keeps on the Clock for the mind (the latest note's text, main.lua). Never in a chunk: a
# chunk is public and kept for good, so the past shows notes only through the site, which can still hide them.
PRIVATE_ATTRS = frozenset({"NoteText"})

try:  # zstd: Python 3.14's own module, the zstandard module, or else the zstd tool (the island image has it)
    from compression import zstd as _zstd_std  # type: ignore[import-not-found]

    def _unzstd_one(blob):
        return _zstd_std.decompress(blob)
except ImportError:
    try:
        import zstandard

        def _unzstd_one(blob):
            return zstandard.ZstdDecompressor().decompressobj().decompress(blob)
    except ImportError:
        _unzstd_one = None


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


def rel_t0(rel):
    """The start (UTC ms) of the chunk a chunks/… path names."""
    return int(rel.rsplit("/", 1)[1].split(".", 1)[0])


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


_LINES = OrderedDict()  # path -> ((mtime, size), lines): hour and day files, read again only when they change
_LINES_LOCK = threading.Lock()  # the guest panel answers on many threads
_LINES_KEPT = 256


def _read_lines(path):
    """The JSON lines of a file (skipping one cut off by a crash), or none if it is missing. Kept while unchanged."""
    try:
        st = path.stat()
    except FileNotFoundError:
        return []
    key, stamp = str(path), (st.st_mtime_ns, st.st_size)
    with _LINES_LOCK:
        held = _LINES.get(key)
        if held and held[0] == stamp:
            _LINES.move_to_end(key)
            return held[1]
    lines = []
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    lines.append(json.loads(line))
                except ValueError:
                    continue
    except FileNotFoundError:
        return []
    with _LINES_LOCK:
        _LINES[key] = (stamp, lines)
        _LINES.move_to_end(key)
        while len(_LINES) > _LINES_KEPT:
            _LINES.popitem(last=False)
    return lines


# ---- the raw recording ----------------------------------------------------------------------------------------------

def unzstd(blobs):
    """Each zstd blob of a recording, as the JSON it holds. Without a module, one zstd process for the lot: frames one
    after another decompress to their contents one after another."""
    if not blobs:
        return []
    if _unzstd_one is not None:
        return [json.loads(_unzstd_one(b)) for b in blobs]
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
        # Autocommit, so rows_after can hold one read snapshot across its two reads with BEGIN … COMMIT.
        self.db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, timeout=10, check_same_thread=False,
                                  isolation_level=None)
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
        follow. Two indexed reads merged here (one sorted union would sort the whole rest of a long file each time), in
        one read snapshot, so a snapshot the world writes between them cannot hide the deltas before it."""
        self.db.execute("BEGIN")
        try:
            deltas = self.db.execute("select tick, time_ms, data from deltas where tick > ? order by tick limit ?",
                                     (tick, limit)).fetchall()
            more = len(deltas) == limit
            if more:
                snaps = self.db.execute("select tick, time_ms, data from checkpoints where tick > ? and tick <= ? "
                                        "order by tick", (tick, deltas[-1][0])).fetchall()
            else:
                snaps = self.db.execute("select tick, time_ms, data from checkpoints where tick > ? order by tick",
                                        (tick,)).fetchall()
        finally:
            self.db.execute("COMMIT")
        rows = sorted([(t, ms, True, d) for t, ms, d in snaps] + [(t, ms, False, d) for t, ms, d in deltas],
                      key=lambda r: (r[0], not r[2]))
        return [(r[0], r[1], r[2], doc) for r, doc in zip(rows, unzstd([r[3] for r in rows]))], more

    def close(self):
        self.db.close()


def trim_recording(path, before_ms, pause=0.05):
    """Delete a recording's rows older than `before_ms` (recording time), a few thousand at a time, while the world may
    still be writing it: each batch holds the write lock for milliseconds, and the world's writer waits that long. The
    file does not shrink, but its freed pages take the new rows, so it stops growing past what is kept."""
    db = sqlite3.connect(str(path), timeout=5, isolation_level=None)
    deleted = 0
    try:
        for table in ("deltas", "checkpoints", "inputs", "chat_messages"):
            while True:
                try:
                    n = db.execute(f"delete from {table} where rowid in "  # noqa: S608 (fixed table names)
                                   f"(select rowid from {table} where time_ms < ? limit ?)",
                                   (before_ms, TRIM_BATCH)).rowcount
                except sqlite3.OperationalError as err:
                    if "no such table" in str(err):
                        break
                    raise
                deleted += max(n, 0)
                if n < TRIM_BATCH:
                    break
                time.sleep(pause)
    finally:
        db.close()
    return deleted


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

def _num(v, digits):
    """A coordinate to `digits` places. The world writes a NaN or an infinity as null: kept as null, never a crash."""
    return round(v, digits) if isinstance(v, (int, float)) and math.isfinite(v) else None


def _asset(url):
    """A model's address without the place the world was served from: asset://name.glb, which the renderer resolves
    where its island serves models, so chunks kept for good still draw if that place changes (IT-11)."""
    if isinstance(url, str) and not url.startswith("asset://"):
        m = ASSET_URL.match(url)
        if m:
            return f"asset://{m.group(1)}"
    return url


def _round_attrs(attrs):
    out = {k: round(v, 3) if isinstance(v, float) and math.isfinite(v) else v for k, v in attrs.items()
           if k not in PRIVATE_ATTRS}
    if "ModelUrl" in out:
        out["ModelUrl"] = _asset(out["ModelUrl"])
    return out


def slim_entity(e):
    """An entity (or a player) as replay keeps it: positions to a hundredth, rotations and attributes to a thousandth,
    models by name."""
    out = dict(e)
    if isinstance(out.get("position"), list):
        out["position"] = [_num(v, 2) for v in out["position"]]
    if isinstance(out.get("rotation"), list):
        out["rotation"] = [[_num(v, 3) for v in row] if isinstance(row, list) else row for row in out["rotation"]]
    if out.get("attributes"):
        out["attributes"] = _round_attrs(out["attributes"])
    if "model_url" in out:
        out["model_url"] = _asset(out["model_url"])
    return out


def slim_players(players):
    return [slim_entity(p) for p in players or ()]


TOP_KEPT = ("players", "recent_events", "sounds", "game_status")  # what a frame repeats when it changed


class _Segment:
    """The recording being packed: its rebuilt state, the window of frames being gathered, and what came before."""

    def __init__(self, packer, rec, info):
        self.packer, self.rec, self.id = packer, rec, rec.id
        self.info = info  # its entry in state.json
        self.memo = {}  # entity id -> (the state's dict, its slim copy): unchanged entities are not copied again
        self.window_t0, self.frames, self.prev = None, [], None
        self.clock_id = None
        self.deaths = None  # the most deaths seen this world start (a missing count is none yet)
        self.last_wall = None
        self.bad_rows = 0
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
            try:
                if full:
                    self.state.reset(doc)
                else:
                    self.state.apply(doc)
            except Exception as err:  # noqa: BLE001 (one bad row is skipped; the next snapshot, within a second, mends it)
                self.bad_rows += 1
                if self.bad_rows <= 3:
                    self.packer.log(kind="error", message=f"replay packer: {self.id} tick {tick} skipped: {err!r}"[:300])
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
        # A chunk never changes once written (browsers keep it for good). One already there, here or up in the bucket,
        # is left as it is: after a restore (ADR-018) the packer may pack a window again from a recording since trimmed.
        up = self.packer.store.uploaded_until()
        if not (self.packer.root / rel).exists() and not (up is not None and t0 < up):
            _write_atomic(self.packer.root / rel,
                          gzip.compress(json.dumps(chunk, separators=(",", ":")).encode(), 9, mtime=0))
            self.packer.store.put(rel)
        self.info["end"] = chunk["t1"]
        self.info["chunks"] = self.info.get("chunks", 0) + 1
        self.window_t0, self.frames = None, []
        self.info["window"] = None


# ---- where chunks go ------------------------------------------------------------------------------------------------

class LocalStore:
    """Chunks stay in <run>/replay/chunks, served from there (the guest panel, or Caddy from the runs volume)."""
    url = None

    def put(self, rel):
        pass

    def uploaded_until(self):
        return None

    def keep(self):
        pass

    def stop(self):
        pass


class S3Store:
    """Chunks also go to S3-compatible object storage (ADR-016: Cloudflare R2, Hetzner, or Amazon S3; endpoint and keys
    from the environment). Viewers fetch a chunk from its public address once it is up (`uploaded_until`), and the
    island's own copy until then; the local copies of a day are deleted LOCAL_DAYS later, once all of it is up.

    New chunks go up first, then whatever is left from before (a backlog: the history when a bucket is first set, or an
    outage). A chunk that fails is tried again later, never dropped. `uploaded.json` keeps `below`, the oldest chunk not
    yet up (everything older is), or `upto`, the newest chunk when all are up."""
    LOCAL_DAYS = 2
    CORS = {"CORSRules": [{"AllowedOrigins": ["*"], "AllowedMethods": ["GET", "HEAD"], "AllowedHeaders": ["*"],
                           "MaxAgeSeconds": 86400}]}

    def __init__(self, root, log, bucket, endpoint, key_id, secret, public_url, prefix="", region="auto", client=None):
        if client is None:
            import boto3  # only here: a run without a bucket needs no boto3
            client = boto3.client("s3", endpoint_url=endpoint or None, aws_access_key_id=key_id,
                                  aws_secret_access_key=secret, region_name=region)
        self.root, self.log, self.bucket, self.prefix, self.s3 = root, log, bucket, prefix.strip("/"), client
        self.url = public_url.rstrip("/") + (f"/{self.prefix}" if self.prefix else "")
        self.mark_file = root / "uploaded.json"
        mark = json.loads(self.mark_file.read_text()) if self.mark_file.exists() else {}
        self.upto = mark.get("upto") or ""  # with no `below`: every chunk up to this one is up
        self.lock = threading.Condition()
        self.pending = set()  # put, not up yet
        self.fresh, self.backlog = deque(), deque()
        self.stopping = False
        below = mark.get("below")
        for path in sorted(root.glob("chunks/*/*/*.json.gz")):  # what an earlier run did not get up (or may not have)
            rel = path.relative_to(root).as_posix()
            if (rel >= below) if below else (rel > self.upto):
                self.pending.add(rel)
                self.backlog.append(rel)
        try:  # browsers fetch from the island's origin: the bucket must answer cross-origin reads
            self.s3.put_bucket_cors(Bucket=bucket, CORSConfiguration=self.CORS)
        except Exception as err:  # noqa: BLE001 (a key without the right to set it: say what the bucket needs)
            self.log(kind="error", message=f"replay bucket {bucket}: could not allow cross-origin reads ({err!r})"[:300]
                     + "; set a CORS rule on the bucket: GET and HEAD from any origin")
        self.thread = threading.Thread(target=self._run, name="replay-upload", daemon=True)
        self.thread.start()

    def put(self, rel):
        with self.lock:
            self.pending.add(rel)
            self.fresh.append(rel)
            self.lock.notify()

    def _below(self):
        return min(self.pending) if self.pending else None

    def uploaded_until(self):
        """Chunks starting before this (UTC ms) are in the bucket; later ones are fetched from the island."""
        with self.lock:
            below = self._below()
            if below:
                return rel_t0(below)
            return rel_t0(self.upto) + CHUNK_MS if self.upto else 0

    def _run(self):
        failures = 0
        while True:
            with self.lock:
                while not (self.fresh or self.backlog or self.stopping):
                    self.lock.wait()
                if self.stopping and not self.fresh:  # what is left goes up after the next start
                    return
                rel = (self.fresh or self.backlog).popleft()
            try:
                self.s3.put_object(Bucket=self.bucket, Key=f"{self.prefix}/{rel}" if self.prefix else rel,
                                   Body=(self.root / rel).read_bytes(), ContentType="application/gzip",
                                   CacheControl="public, max-age=31536000, immutable")
                failures = 0
            except FileNotFoundError:  # deleted here before it went up: nothing to send
                pass
            except Exception as err:  # noqa: BLE001 (the network or the bucket: back in the queue, tried again later)
                failures += 1
                if failures <= 3 or failures % 100 == 0:
                    self.log(kind="error", message=f"replay upload {rel} (failure {failures}): {err!r}"[:300])
                with self.lock:
                    self.backlog.append(rel)
                time.sleep(min(60, 2 ** min(failures, 6)))
                continue
            with self.lock:
                self.pending.discard(rel)
                self.upto = max(self.upto, rel)
                below = self._below()
                mark = {"below": below} if below else {"upto": self.upto}
            _write_atomic(self.mark_file, json.dumps(mark).encode())

    def keep(self):
        """Local days older than LOCAL_DAYS go, once every chunk in them is up."""
        cutoff = day_hour(time.time() * 1000 - self.LOCAL_DAYS * 86_400_000)[0]
        with self.lock:
            below = self._below()
            safe = below.split("/")[1] if below else "9999"  # a day before the oldest chunk not yet up
        for day in sorted((self.root / "chunks").glob("*")):
            if day.name < cutoff and day.name < safe:
                shutil.rmtree(day, ignore_errors=True)

    def stop(self):
        with self.lock:
            self.stopping = True
            self.lock.notify()
        self.thread.join(timeout=20)


def store_from_env(root, log):
    bucket = os.environ.get("GODLING_REPLAY_BUCKET", "")
    if not bucket:
        return LocalStore()
    public = os.environ.get("GODLING_REPLAY_PUBLIC_URL", "")
    if not public:
        log(kind="error", message="replay: GODLING_REPLAY_BUCKET is set but GODLING_REPLAY_PUBLIC_URL is not, so "
                                  "browsers could not fetch from it: chunks stay on the island")
        return LocalStore()
    return S3Store(root, log, bucket, os.environ.get("GODLING_REPLAY_ENDPOINT", ""),
                   os.environ.get("GODLING_REPLAY_KEY_ID", ""), os.environ.get("GODLING_REPLAY_SECRET", ""),
                   public, os.environ.get("GODLING_REPLAY_PREFIX", ""), os.environ.get("GODLING_REPLAY_REGION", "auto"))


# ---- the packer -----------------------------------------------------------------------------------------------------

def marks_of(entry, best):
    """Markers for the timeline from one entry of the mind's log (ADR-016 D8), as (marker, what it is about): the sky
    event's own id when the entry has one, so one event is one marker and two events are two. `best` keeps the most
    walls, roofs and enclosures seen, so a structure marker means a new one."""
    kind, text = entry.get("kind"), str(entry.get("text") or entry.get("summary") or "")
    if kind == "event":
        sky, stage = entry.get("sky"), entry.get("sky_stage")
        if sky:
            mark = str(sky).lower()
            # An earthquake is marked at its rumble, before the shaking; the rest when they arrive (a meteor's
            # warning is its shadow, 40 s before it lands).
            if (stage == "warning") == (mark == "earthquake"):
                return [(mark, f"{mark}:{entry['sky_id']}" if entry.get("sky_id") is not None else None)]
            return []
        for start, mark in (("It has started to rain", "rain"), ("Fog has rolled in", "fog"),
                            ("A ship is passing", "ship"), ("You were hurt", "hurt"),
                            ("Lightning struck you", "struck")):
            if text.startswith(start):
                return [(mark, None)]
        if " has gone out" in text:
            return [("fire-out", None)]
    elif kind == "skill" and entry.get("ok"):
        if "a flame caught" in text:
            return [("fire", None)]
        if text.startswith("speared "):
            return [("fish", None)]
    elif kind == "structures":
        out = []
        for key, mark in (("walls", "wall"), ("roofed", "roof"), ("enclosures", "enclosure")):
            n = entry.get(key) or 0
            if n > best.get(key, 0):
                best[key] = n
                out.append((mark, None))
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
        self.state.setdefault("sky_next", 0)
        self.cur = None
        self.stopping = threading.Event()
        self.thread = None
        self.kept_at = 0
        self.saved_at = 0
        self.warned_at = 0
        self.marks = []
        self.appended = set()  # files added to since this packer started (_append_new)
        self.marked = {}  # marker (or the event it is about) -> when it was set: one event often says itself twice
        self.index_was = None

    def start(self):
        self.thread = threading.Thread(target=self._run, name="replay-packer", daemon=True)
        self.thread.start()
        return self

    def stop(self):
        """Stop, after packing what the world wrote last (call it once the world has stopped)."""
        self.stopping.set()
        if self.thread is not None:
            self.thread.join(timeout=25)
        self.store.stop()

    def _run(self):
        while not self.stopping.is_set():
            try:
                self.pack_once()
            except Exception as err:  # noqa: BLE001 (pack_once guards each step; this is the last resort)
                self.log(kind="error", message=f"replay packer: {err!r}"[:300])
                self.cur = None
                self.stopping.wait(10)
            self.stopping.wait(2)
        try:
            self.pack_once(final=True)
        except Exception as err:  # noqa: BLE001
            self.log(kind="error", message=f"replay packer at the end: {err!r}"[:300])

    def _try(self, what, step, *args):
        """One step of a pass. A failing step is said and skipped, so the others still run: above all the keeping job,
        which frees the disk a failing step may be stuck on."""
        try:
            return step(*args)
        except Exception as err:  # noqa: BLE001 (the packer outlives one bad step; the live world never waits on it)
            self.log(kind="error", message=f"replay packer, {what}: {err!r}"[:300])
            return None

    def pack_once(self, final=False):
        recs = sorted((self.run / "recordings").glob("*.clawrec"))
        for i, path in enumerate(recs):
            info = self.state["segments"].setdefault(path.stem, {})
            if info.get("done"):
                continue
            newer = i < len(recs) - 1
            if final and newer and self.stopping.is_set():
                continue  # an old recording still being caught up waits for the next start; stopping stays quick
            try:
                self._pack(path, info, newer, final)
                info.pop("errors", None)
            except Exception as err:  # noqa: BLE001 (one recording that will not pack holds up neither the others nor keeping)
                self.cur = None
                info["errors"] = info.get("errors", 0) + 1
                self.log(kind="error", message=f"replay packer: {path.name}: {err!r}"[:300])
                if newer and info["errors"] >= GIVE_UP_AFTER:
                    info.update(done=True, broken=repr(err)[:200])
                    self.log(kind="error", message=f"replay packer: gave up on {path.name} after {GIVE_UP_AFTER} tries")
        self._try("the mind's log", self._tracks)
        self._try("markers", self._flush_marks)
        if final or time.time() - self.saved_at > SAVE_EVERY:
            self._try("saving", self._save)
        self._try("the index", self._write_index)
        if final or time.time() - self.kept_at > KEEP_EVERY:
            self._try("keeping", self._keep, recs)

    def _save(self):
        _write_atomic(self.root / "state.json", json.dumps(self.state).encode())
        self.saved_at = time.time()

    def _pack(self, path, info, newer, final):
        seg = self.cur
        if seg is None or seg.id != path.stem:
            if seg is not None:
                seg.rec.close()
                self.cur = None
            try:
                seg = _Segment(self, Recording(path), info)
            except (sqlite3.Error, ValueError, KeyError):
                if newer and not info.get("start"):  # an old recording with nothing in it (a world that never came up)
                    info["done"] = True
                return
            self.cur = seg
        while True:
            rows, more = seg.rec.rows_after(seg.tick)
            seg.step(rows)
            if time.time() - self.saved_at > SAVE_EVERY:  # a long catch-up keeps note of how far it has got
                self._try("markers", self._flush_marks)
                self._save()
            if not more:
                break
            if self.stopping.is_set() and not final:
                return
        if newer or final:
            seg.finish()
            info["done"] = True
            seg.rec.close()
            self.cur = None

    def seen_frame(self, t, ents, top, seg):
        """Called for every frame: the timeline's sky strip, and markers the world shows but the mind's log does not."""
        if seg.clock_id not in ents:
            seg.clock_id = next((i for i, e in ents.items() if "TimeOfDay" in (e.get("attributes") or {})), None)
        if t >= self.state["sky_next"] and seg.clock_id is not None:
            a = ents[seg.clock_id].get("attributes") or {}
            day, _ = day_hour(t)
            self._append_new(self.root / f"sky/{day}.jsonl", [{"t": t, "hour": a.get("TimeOfDay"), "day": a.get("Day"),
                                                                "rain": a.get("Rain") or 0, "fog": a.get("Fog") or 0}])
            self.state["sky_next"] = t - t % SKY_EVERY_MS + SKY_EVERY_MS
        # Deaths (main.lua DEATH): the world counts them on Godling (none until the first). The players' order is not
        # fixed, and the guest panel's bodiless Sky is one of them: the most deaths any player has. The mark carries
        # what killed it. (Older recordings counted faints instead; their marks, "faint", stay as they were packed.)
        players = top.get("players") or []
        deaths, cause = (0, "") if players else (None, "")  # a missing count is none yet: the first death is marked
        for p in players:
            a = p.get("attributes") or {}
            n = a.get("Deaths") or 0
            if isinstance(n, (int, float)) and n > deaths:
                deaths, cause = n, str(a.get("DiedOf") or "")
        if deaths is not None:
            if seg.deaths is not None and deaths > seg.deaths:
                self.marks.append({"t": t, "m": "death", **({"cause": cause} if cause else {})})
            seg.deaths = deaths

    def _tracks(self):
        """New lines of the mind's log: the ones the screen shows go to the tracks, and markers to the timeline."""
        path = self.run / "mind/log.jsonl"
        if not path.exists():
            return
        offset = self.state["log_offset"]
        with path.open("rb") as f:
            head = hashlib.sha1(f.readline(4096)).hexdigest()  # the log's first line: which log this is
            size = f.seek(0, 2)
            if size < offset:
                # Shorter than where the packer got to. The same log, put back by a restore (ADR-018), whose end the
                # packer had passed: on from its end. Any other log is a new one, from its start.
                offset = size if head == self.state.get("log_head") else 0
            f.seek(offset)
            data = f.read(8_000_000)
        self.state["log_head"] = head
        end = data.rfind(b"\n")
        if end < 0:
            self.state["log_offset"] = offset  # nothing new yet: on from here (a restored log's end, or a new log's start)
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
            if fields is not None and (kind != "bubble" or e.get("ok")):
                day, hour = day_hour(t)
                kept = {"time": round(t / 1000, 3), "kind": kind, **{k: e[k] for k in fields if k in e}}
                if kind == "decision":
                    kept["agenda"] = agenda_of(e)
                hours.setdefault(f"tracks/{day}/{hour}.jsonl", []).append(kept)
            for mark, about in marks_of(e, self.state["best"]):
                key = about or mark
                if about is not None and key in self.marked or \
                        about is None and t - self.marked.get(key, -MARK_APART) < MARK_APART:
                    continue
                self.marks.append({"t": t, "m": mark})
                self.marked[key] = t
        if len(self.marked) > 2000:  # events long past cannot come again
            self.marked = {k: v for k, v in self.marked.items() if v > max(self.marked.values()) - 86_400_000}
        for rel, entries in hours.items():
            self._append_new(self.root / rel, entries)
        self.state["log_offset"] = offset + end + 1
        self._flush_marks()
        self._save()  # at once: the tracks were appended, and must not be appended again after a restart

    def _flush_marks(self):
        by_day = {}
        for m in self.marks:
            by_day.setdefault(day_hour(m["t"])[0], []).append(m)
        for day, marks in by_day.items():
            self._append_new(self.root / f"marks/{day}.jsonl", marks)
        self.marks = []

    def _append_new(self, path, entries):
        """Appends, leaving out the first time in this run of the packer what the file already ends with. A backup
        reads the run's files one by one while they grow (ADR-018), so a restored state.json may be a little behind
        the tracks, markers and sky it was restored with, and the packer then reads those lines of the log again."""
        if path not in self.appended:
            self.appended.add(path)
            if entries and path.exists():
                with path.open("rb") as f:
                    f.seek(max(0, f.seek(0, 2) - 262_144))
                    tail = set(f.read().decode("utf-8", "replace").splitlines())
                entries = [e for e in entries if json.dumps(e, separators=(",", ":")) not in tail]
        _append(path, entries)

    def _write_index(self):
        segments = [{"id": sid, "start": info["start"], "end": info["end"], "live": not info.get("done")}
                    for sid, info in sorted(self.state["segments"].items()) if info.get("start") and info.get("end")]
        index = {"format": FORMAT, "chunk_ms": CHUNK_MS, "rate": RATE, "segments": segments}
        if self.store.url:  # chunks also in object storage: browsers fetch them there once they are up
            index.update(chunks_url=self.store.url, chunks_url_until=self.store.uploaded_until())
        if index != self.index_was:  # unchanged most passes: not written again
            _write_atomic(self.root / "index.json", json.dumps(index, separators=(",", ":")).encode())
            self.index_was = index

    def _keep(self, recs):
        """Raw recordings older than KEEP_RAW_DAYS go once they are packed. The one the world is writing never ends
        while the world runs, so its packed rows older than that are trimmed instead. A full disk is said."""
        self.kept_at = time.time()
        now = time.time()
        cutoff = now - KEEP_RAW_DAYS * 86_400
        for path in recs[:-1]:
            info = self.state["segments"].get(path.stem, {})
            if info.get("done") and path.stat().st_mtime < cutoff:
                for extra in (path, path.with_suffix(".replay.toml"), Path(f"{path}-wal"), Path(f"{path}-shm")):
                    extra.unlink(missing_ok=True)
                info["raw"] = "deleted"
        if recs:
            live = recs[-1]
            info = self.state["segments"].get(live.stem, {})
            rec_start = info.get("rec_start")
            if rec_start is None:
                rec = Recording(live)
                rec_start = info["rec_start"] = rec.start_ms
                rec.close()
            # Only what is packed (up to the window being gathered) and older than the days kept.
            before = min(cutoff * 1000, (info.get("window") or info.get("end") or 0) - CHUNK_MS) - rec_start
            if before > info.get("trimmed", 0) and now - info.get("trimmed_at", 0) > TRIM_EVERY:
                deleted = trim_recording(live, before)
                info.update(trimmed=before, trimmed_at=now)
                if deleted:
                    self.log(kind="keep", message=f"trimmed {deleted} rows older than {KEEP_RAW_DAYS:g} days from "
                                                  f"{live.name}")
        self.store.keep()
        usage = shutil.disk_usage(self.run)
        full = usage.used / usage.total if usage.total else 0
        if full >= DISK_WARN and now - self.warned_at > 3600:
            self.warned_at = now
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


def _track_file(root, t):
    return root / ("tracks/%s/%s.jsonl" % day_hour(t))


def read_index(run):
    path = Path(run) / "replay/index.json"
    index = json.loads(path.read_text()) if path.exists() else {"format": FORMAT, "chunk_ms": CHUNK_MS, "rate": RATE,
                                                                  "segments": []}
    index["now"] = int(time.time() * 1000)
    return index


def read_tracks(run, t_from, t_to):
    """The screen's tracks from `t_from` to `t_to` (ms): `entries` in that span, and `lead`, the entries before it that
    say what the screen showed at `t_from`: all of them since the last decision (what Godling was doing, and how far
    into its agenda), the last bubble and intention before that, and the lines of the feed."""
    root = Path(run) / "replay"
    entries = [dict(e) for h in _hours(t_from, t_to) for e in _read_lines(_track_file(root, h))
               if t_from <= e.get("time", 0) * 1000 <= t_to]  # copies: the lines read are kept for the next call
    lead, want, recent = [], {"decision", "bubble", "project"}, True
    # Twice the feed's length of Godling's lines (the reading skips a thought said twice in a row), and the world's lines
    # among them, up to the feed's length (it keeps half): a line of the world's older than all those is never kept.
    mind, world = 0, 0
    for h in list(_hours(t_from - LEAD_HOURS * 3_600_000, t_from))[::-1]:
        for e in reversed(_read_lines(_track_file(root, h))):
            if e.get("time", 0) * 1000 >= t_from:
                continue
            kind = e.get("kind")
            start = kind == "project" and e.get("phase") == "start"
            if kind in ("event", "glance"):
                line = world < FEED_KEPT
                world += kind == "event"
            else:
                line = (_makes_line(e) or kind == "plan_discarded") and mind < 2 * FEED_KEPT
                mind += _makes_line(e)
            if recent or kind in want and (kind != "project" or start) or line:
                lead.append(dict(e))
                if kind != "project" or start:
                    want.discard(kind)
            if kind == "decision" or len(lead) >= LEAD_MOST:
                recent = False
        if not want and not recent and mind >= 2 * FEED_KEPT:
            break
    lead.reverse()
    return {"format": FORMAT, "from": t_from, "to": t_to, "lead": lead, "entries": entries,
            "acts": read_acts(run, t_from, t_to)}


def read_marks(run, t_from, t_to):
    root = Path(run) / "replay"
    marks = [m for d in _days(t_from, t_to) for m in _read_lines(root / f"marks/{d}.jsonl")
             if t_from <= m.get("t", 0) <= t_to]
    return sorted(marks, key=lambda m: m["t"])  # a catch-up writes them as it finds them, not in time order


def read_sky(run, t_from, t_to, every=SKY_EVERY_MS):
    """The island's hour and weather from `t_from` to `t_to`, one sample per `every` ms at most (a week's timeline needs
    far fewer than one a minute)."""
    root = Path(run) / "replay"
    out, last = [], None
    for d in _days(t_from, t_to):
        for s in _read_lines(root / f"sky/{d}.jsonl"):
            t = s.get("t", 0)
            if t_from <= t <= t_to and (last is None or t >= last + every):
                out.append(s)
                last = t
    return out


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


def agenda_of(decision):
    """How many projects a decision's agenda holds: the ones with steps, which the body carries out (run_godling)."""
    if isinstance(decision.get("agenda"), int):  # a decision in the tracks keeps only the count
        return decision["agenda"]
    return sum(1 for p in decision.get("projects") or [] if isinstance(p, dict) and p.get("steps"))


def _makes_line(e):
    """Whether this entry adds one of Godling's own lines to the feed, as reduce_status reads it."""
    kind = e.get("kind")
    return bool(kind == "decision" and e.get("thought") or kind == "learn" and e.get("name")
                or kind == "sleep" and e.get("dream")
                or kind == "project" and e.get("phase") == "end" and e.get("ok") is False)


def reduce_status(entries, clean=lambda s: s, feed_kept=FEED_KEPT, world_kept=None):
    """What the screen shows of Godling's mind after these log entries, in order: the guest panel's reading of the log
    (mind_status). The viewers' screen reads replay's tracks the same way (reduceStatus, world/viewer/replay.js).

    `now` is what Godling is doing at this moment, with the time it began: a project ({"text": its intention, "step",
    "of": where it is in the agenda}), or {"thinking": True} while the body stands until its mind has thought; None
    between them. The feed holds its thoughts, what it could not finish, what it learned and dreamt (`about` says
    which), and what it noticed; at most `world_kept` of its lines (half, unless said) are the world's, so they never
    crowd Godling out."""
    world_kept = feed_kept // 2 if world_kept is None else world_kept
    out = {"thought": "", "needs": "", "intention": "", "now": None}
    feed, agenda, step, said = [], 0, 0, None  # said: the last thought in the feed, which is not said again

    def say(e, about, text, **more):
        feed.append({"time": e.get("time"), "who": "godling", "about": about, "text": text, **more})

    for e in entries:
        kind = e.get("kind")
        if kind == "decision":
            out["thought"], out["needs"] = clean(e.get("thought", "")), clean(e.get("needs", ""))
            if out["thought"] and out["thought"] != said:
                feed.append({"time": e.get("time"), "who": "godling", "text": out["thought"]})
                said = out["thought"]
            agenda, step, out["now"] = agenda_of(e), 0, None
        elif kind == "bubble" and e.get("ok"):
            out["bubble"] = {"thing": e.get("thing"), "feeling": e.get("feeling")}
        elif kind == "thinking":
            if not (out["now"] or {}).get("thinking"):  # thinking since the first time it said so
                out["now"] = {"time": e.get("time"), "thinking": True}
        elif kind == "project" and e.get("phase") == "start" and e.get("stopgap"):  # no step of the agenda (ADR-030)
            out["intention"] = clean(e.get("intention") or e.get("goal", ""))
            out["now"] = {"time": e.get("time"), "text": out["intention"]}
        elif kind == "project" and e.get("phase") == "start":
            out["intention"] = clean(e.get("intention") or e.get("goal", ""))
            step += 1
            out["now"] = {"time": e.get("time"), "text": out["intention"], "step": step, "of": agenda}
        elif kind == "project" and e.get("phase") == "end":
            doing = (out["now"] or {}).get("text") or ""
            if e.get("ok") is False and (e.get("intention") or doing or e.get("goal")):
                say(e, "failed", clean(e.get("intention") or doing or e.get("goal")))
            out["now"] = None
        elif kind == "plan_discarded":  # something happened that it stopped for, to think again
            if feed and feed[-1].get("about") == "failed":
                feed[-1]["about"] = "stopped"
        elif kind == "learn" and e.get("name"):
            say(e, "learned", clean(e.get("does") or ""), name=clean(e["name"]))
        elif kind == "sleep" and e.get("dream"):
            say(e, "dream", clean(e["dream"]))
        elif kind == "event":
            feed.append({"time": e.get("time"), "who": "sky" if e.get("sky") else "notice", "text": clean(e["text"]),
                         "glance": None})
        elif kind == "glance":
            seen = next((n for n in reversed(feed) if n["text"] == e.get("text") and n.get("glance", 0) is None), None)
            if seen:
                seen["glance"] = e.get("degrees") if e.get("turned") else 0
    kept, world = deque(), 0
    for line in reversed(feed):
        if line["who"] != "godling":
            if world >= world_kept:
                continue
            world += 1
        kept.appendleft(line)
        if len(kept) >= feed_kept:
            break
    latest = next((line for line in reversed(feed) if line["who"] == "godling" and "about" not in line), None)
    if latest is not None and not any(line is latest for line in kept):  # its newest thought always stays
        if len(kept) >= feed_kept:
            kept.popleft()
        kept.appendleft(latest)
    out["feed"] = list(kept)
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
    segments = [s for s in index["segments"] if (run / "recordings" / f"{s['id']}.clawrec").exists()]
    if not segments:
        print("nothing to check: no packed segment still has its raw recording")
        return False
    bad = 0
    for _ in range(samples):
        seg = random.choice(segments)
        rec = Recording(run / "recordings" / f"{seg['id']}.clawrec")
        first = rec.db.execute("select min(time_ms) from checkpoints").fetchone()[0] or 0
        # Only moments the raw recording still holds (the live one is trimmed of rows older than the days kept).
        t = random.randrange(max(seg["start"], rec.start_ms + first + CHUNK_MS), seg["end"] - FRAME_MS)
        path = run / "replay" / chunk_rel(t - t % CHUNK_MS)
        ents, players, at = _chunk_state(path, t)
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


def _lock(run):
    """One packer per run at a time (`follow`, or `pack` by hand): two would append the same tracks twice. The lock
    file is held while the process lives; None when another packer holds it."""
    path = Path(run) / "replay/.packer.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("a")
    try:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ImportError:  # not on Linux: no lock (the island and WSL are Linux)
        pass
    except OSError:
        f.close()
        return None
    return f


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("follow", "pack", "check"):
        sys.exit(__doc__)
    held = _lock(sys.argv[2]) if sys.argv[1] in ("follow", "pack") else True
    if held is None:
        sys.exit(f"another packer is already packing {sys.argv[2]}")
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
        # The newest recording is closed only when its world has stopped (--stopped); otherwise it is packed up to
        # now and left open for the world to go on writing.
        packer.pack_once(final="--stopped" in sys.argv[3:])
        packer.store.stop()
        print(json.dumps(read_index(sys.argv[2]), indent=1))
    else:
        sys.exit(0 if check(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 200) else 1)
