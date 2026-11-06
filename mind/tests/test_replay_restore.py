"""The replay packer after a run is restored from a backup (ADR-018). A backup copies the run's files one by one while
they grow, so the packer's state may be ahead of the mind's log it comes back with, or a little behind the tracks; and
an old run snapshot points the packer at windows it packed long ago. None of that may double the replays' history or
change a chunk already written. Also: Godling's memory files are written whole."""
import json
from types import SimpleNamespace

from godling import replay
from godling.files import write_atomic
from godling.memory import NativeMemory

T = 1_793_700_000_000  # ms, a whole 10 s


def line(t, thought):
    return json.dumps({"time": t / 1000, "kind": "decision", "thought": thought, "needs": ""}) + "\n"


def tracked(run):
    return [json.loads(x) for f in sorted((run / "replay/tracks").rglob("*.jsonl")) for x in f.read_text().splitlines()]


def packer(run):
    return replay.Packer(run, store=replay.LocalStore())


def test_a_log_restored_shorter_than_where_the_packer_got_to_goes_on_from_its_end(tmp_path):
    run = tmp_path / "run"
    (run / "mind").mkdir(parents=True)
    log = run / "mind/log.jsonl"
    log.write_text(line(T, "first") + line(T + 1000, "second"))
    p = packer(run)
    p._tracks()
    log.write_text(line(T, "first") + line(T + 1000, "second") + line(T + 2000, "third"))
    p._tracks()
    assert [e["thought"] for e in tracked(run)] == ["first", "second", "third"]
    # The backup copied the log before "third", and state.json after it: restored, the log is behind the offset.
    log.write_text(line(T, "first") + line(T + 1000, "second"))
    p = packer(run)
    p._tracks()
    assert [e["thought"] for e in tracked(run)] == ["first", "second", "third"]  # nothing read again
    with log.open("a") as f:
        f.write(line(T + 5000, "after the restore"))
    p._tracks()
    assert [e["thought"] for e in tracked(run)] == ["first", "second", "third", "after the restore"]


def test_a_new_log_is_read_from_its_start(tmp_path):
    run = tmp_path / "run"
    (run / "mind").mkdir(parents=True)
    log = run / "mind/log.jsonl"
    log.write_text(line(T, "old one") + line(T + 1000, "old two"))
    p = packer(run)
    p._tracks()
    log.write_text(line(T + 9000, "new"))  # another log, shorter than the offset
    p._tracks()
    assert [e["thought"] for e in tracked(run)] == ["old one", "old two", "new"]


def test_lines_the_tracks_already_end_with_are_not_added_again(tmp_path):
    run = tmp_path / "run"
    (run / "mind").mkdir(parents=True)
    log = run / "mind/log.jsonl"
    log.write_text(line(T, "first") + line(T + 1000, "second"))
    packer(run)._tracks()
    # The backup copied state.json before the packer saved past "second": it reads "second" again.
    state = json.loads((run / "replay/state.json").read_text())
    state["log_offset"] = len(line(T, "first"))
    (run / "replay/state.json").write_text(json.dumps(state))
    packer(run)._tracks()
    assert [e["thought"] for e in tracked(run)] == ["first", "second"]


def test_a_chunk_already_written_is_never_written_again(tmp_path):
    run = tmp_path / "run"
    p = packer(run)
    rel = replay.chunk_rel(T)
    path = p.root / rel
    path.parent.mkdir(parents=True)
    path.write_bytes(b"the chunk as it was packed first")
    put = []
    p.store = SimpleNamespace(put=put.append, uploaded_until=lambda: None)
    segment = SimpleNamespace(frames=[{"t": T, "full": {}}], window_t0=T, id="seg", packer=p, info={})
    replay._Segment._flush(segment)
    assert path.read_bytes() == b"the chunk as it was packed first" and put == []
    assert segment.info["end"] == T + replay.FRAME_MS  # the segment still moves on
    # Up in the bucket already (and gone from here): not uploaded again either.
    path.unlink()
    p.store = SimpleNamespace(put=put.append, uploaded_until=lambda: T + 10_000)
    segment = SimpleNamespace(frames=[{"t": T, "full": {}}], window_t0=T, id="seg", packer=p, info={})
    replay._Segment._flush(segment)
    assert not path.exists() and put == []


def test_memory_files_are_written_whole_and_a_cut_short_episode_is_left_out(tmp_path):
    write_atomic(tmp_path / "x.json", '{"a": 1}')
    assert json.loads((tmp_path / "x.json").read_text()) == {"a": 1} and not list(tmp_path.glob("*.tmp"))
    mem = NativeMemory(tmp_path / "m")
    mem.store_experience("A full one")
    with mem.episodes_path.open("a") as f:
        f.write('{"id": 2, "text": "cut sho')  # a backup copied it mid-write
    assert [e["text"] for e in NativeMemory(tmp_path / "m").episodes] == ["A full one"]


def test_a_death_is_marked_on_the_timeline_with_its_cause(tmp_path):
    """main.lua DEATH: the world counts deaths on Godling only from the first; the guest panel's Sky has none."""
    p = packer(tmp_path)
    seg = SimpleNamespace(clock_id=None, deaths=None)
    sky = {"name": "Sky", "attributes": {}}
    for t, godling in ((1000, {}), (2000, {"Health": 50}), (3000, {"Deaths": 1, "DiedOf": "Cold", "Dead": True}),
                       (4000, {"Deaths": 1, "DiedOf": "Cold"}), (5000, {"Deaths": 2})):
        p.seen_frame(t, {}, {"players": [sky, {"name": "Godling", "attributes": godling}]}, seg)
    p.seen_frame(6000, {}, {}, seg)  # a frame without players changes nothing
    assert p.marks == [{"t": 3000, "m": "death", "cause": "Cold"}, {"t": 5000, "m": "death"}]
    assert seg.deaths == 2


def test_a_storm_and_a_strike_on_godling_are_marked():
    storm = {"kind": "event", "sky": "Storm", "sky_stage": "warning", "sky_id": 4}
    assert replay.marks_of(storm, {}) == []  # marked when it breaks, as a meteor when it lands
    assert replay.marks_of({**storm, "sky_stage": "arrived"}, {}) == [("storm", "storm:4")]
    struck = {"kind": "event", "text": "Lightning struck you: you are burned and hurt, your health is 5 of 100"}
    assert replay.marks_of(struck, {}) == [("struck", None)]
