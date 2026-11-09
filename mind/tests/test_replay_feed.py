"""What the viewers' screen shows of Godling's mind (reduce_status), live and in replay: what it is doing now or that it
stands thinking, its thoughts and what came of its plans, and what it noticed. The screen's own reading of the tracks
(reduceStatus, world/viewer/replay.js) is held to the same cases (feed.json, world/renderer/test/feed.test.js)."""
import json
from pathlib import Path

from godling import replay

CASE = json.loads((Path(__file__).parent / "feed.json").read_text(encoding="utf-8"))
T = 1_793_700_000  # seconds, a whole hour


def test_the_screen_reads_the_mind_as_the_cases_say():
    entries = CASE["entries"]
    assert replay.reduce_status(entries, feed_kept=CASE["feed_kept"], world_kept=CASE["world_kept"]) == CASE["status"]
    for moment in ("after_the_first_start", "while_thinking", "at_the_start"):
        assert replay.reduce_status(entries[:CASE[moment]["upto"]])["now"] == CASE[moment]["now"], moment
    crowded = CASE["crowded"]
    assert replay.reduce_status(crowded["entries"], feed_kept=crowded["feed_kept"],
                                world_kept=crowded["world_kept"])["feed"] == crowded["feed"]


def test_a_stopgap_is_no_step_of_the_agenda():
    """Review of #80 (80-CDE14): the screen showed a stop-gap as "2 of 3" of the agenda an interruption had thrown away.
    The tracks keep the flag, so the viewers' screen can tell (reduceStatus, the same case)."""
    case = CASE["stopgap"]
    assert replay.reduce_status(case["entries"])["now"] == case["now"]
    assert "stopgap" in replay.TRACKED["project"]


def test_now_ends_with_its_project_and_a_think_ends_with_the_decision():
    start = {"time": 1, "kind": "project", "phase": "start", "goal": "a wall", "intention": "Build a wall"}
    end = {"time": 9, "kind": "project", "phase": "end", "goal": "a wall", "ok": True}
    assert replay.reduce_status([start])["now"] == {"time": 1, "text": "Build a wall", "step": 1, "of": 0}
    assert replay.reduce_status([start, end])["now"] is None
    assert replay.reduce_status([start, end])["feed"] == []  # a project that worked out says nothing of its own
    thinking = [{"time": 10, "kind": "thinking"}, {"time": 50, "kind": "decision", "thought": "", "needs": ""}]
    assert replay.reduce_status(thinking)["now"] is None


def test_the_world_never_crowds_godling_out():
    entries = [{"time": 1, "kind": "decision", "thought": "Hm.", "needs": ""}]
    entries += [{"time": 2 + i, "kind": "event", "text": f"Coconut_{i} appeared"} for i in range(20)]
    feed = replay.reduce_status(entries)["feed"]
    assert len(feed) == 1 + replay.FEED_KEPT // 2 and feed[0]["text"] == "Hm."
    assert feed[-1]["text"] == "Coconut_19 appeared"  # the newest of the world's lines
    assert len(replay.reduce_status(entries, feed_kept=5)["feed"]) == 1 + 2  # half of a shorter feed, as reduceStatus


def test_a_thought_is_not_said_again_after_a_line_of_its_own():
    thought = {"kind": "decision", "thought": "Same.", "needs": ""}
    entries = [{"time": 1, **thought}, {"time": 2, "kind": "learn", "name": "hop", "does": "hops"}, {"time": 3, **thought},
               {"time": 4, "kind": "decision", "thought": "Other.", "needs": ""}, {"time": 5, **thought}]
    assert [f["text"] for f in replay.reduce_status(entries)["feed"]] == ["Same.", "hops", "Other.", "Same."]


def test_every_word_viewers_see_is_cleaned():
    entries = [
        {"time": 1, "kind": "decision", "thought": "t", "needs": "n", "projects": [{"steps": [1]}, {"steps": []}, "odd"]},
        {"time": 2, "kind": "project", "phase": "start", "goal": "g", "intention": "i"},
        {"time": 3, "kind": "project", "phase": "end", "goal": "g", "intention": "i", "ok": False},
        {"time": 4, "kind": "learn", "name": "n", "does": "d"},
        {"time": 5, "kind": "learn", "name": "m", "does": None},
        {"time": 6, "kind": "sleep", "dream": "dr"},
        {"time": 7, "kind": "project", "phase": "start", "goal": "g2", "intention": "i2"},
    ]
    out = replay.reduce_status(entries, clean=lambda s: f"<{s}>")
    assert out["now"] == {"time": 7, "text": "<i2>", "step": 2, "of": 1}
    assert [(f.get("about"), f["text"], f.get("name")) for f in out["feed"]] == [
        (None, "<t>", None), ("failed", "<i>", None), ("learned", "<d>", "<n>"), ("learned", "<>", "<m>"),
        ("dream", "<dr>", None)]


def log_line(t, kind, **e):
    return json.dumps({"time": t, "kind": kind, **e}) + "\n"


def test_the_tracks_keep_what_the_screen_shows(tmp_path):
    run = tmp_path / "run"
    (run / "mind").mkdir(parents=True)
    (run / "mind/log.jsonl").write_text("".join([
        log_line(T, "thinking"),
        log_line(T + 1, "decision", thought="Go.", needs="", plan=3,
                 projects=[{"intention": "a", "goal": "A", "steps": [{"skill": "jump"}]}, {"intention": "b", "steps": []}]),
        log_line(T + 2, "project", phase="start", goal="A", intention="a", steps=1),
        log_line(T + 3, "skill", skill="jump", ok=False, summary="fell", facts={}),
        log_line(T + 4, "project", phase="end", goal="A", intention="a", ok=False, seconds=2),
        log_line(T + 5, "plan_discarded", reason="'A' was interrupted"),
        log_line(T + 6, "learn", name="hop", params=[], steps=[{"skill": "jump"}], does="hops", version=1),
        log_line(T + 7, "sleep", digest="secret", intentions=[], dream="ships", facts_rewritten=0),
        log_line(T + 8, "llm", purpose="decide"), log_line(T + 9, "reflex", text="snagged"),
        log_line(T + 10, "bubble", ok=False, reply="?"),
    ]))
    replay.Packer(run, store=replay.LocalStore())._tracks()
    tracked = [json.loads(x) for f in sorted((run / "replay/tracks").rglob("*.jsonl")) for x in f.read_text().splitlines()]
    assert [e["kind"] for e in tracked] == ["thinking", "decision", "project", "project", "plan_discarded", "learn", "sleep"]
    assert tracked[1] == {"time": T + 1, "kind": "decision", "thought": "Go.", "needs": "", "agenda": 1}
    assert tracked[3] == {"time": T + 4, "kind": "project", "phase": "end", "goal": "A", "intention": "a", "ok": False}
    assert tracked[5] == {"time": T + 6, "kind": "learn", "name": "hop", "does": "hops"}
    assert tracked[6] == {"time": T + 7, "kind": "sleep", "dream": "ships"}  # never the digest


def test_a_replay_starts_where_the_screen_was(tmp_path):
    """The lead of a replay's tracks says what the screen showed at its start, as the whole of the past would."""
    run = tmp_path / "run"
    (run / "mind").mkdir(parents=True)
    lines, t = [], T
    for n in range(30):  # agendas of three, a failure in each, now and then a long think, and the world's doings
        lines.append(log_line(t, "thinking"))
        lines.append(log_line(t + 20, "decision", thought=f"Plan {n}.", needs=f"{n} logs",
                              projects=[{"intention": f"p{n}.{i}", "steps": [1]} for i in range(3)]))
        for i in range(3):
            t += 30
            lines.append(log_line(t, "project", phase="start", goal="", intention=f"p{n}.{i}"))
            lines.append(log_line(t + 1, "bubble", ok=True, thing="tower", feeling="focused"))
            lines.append(log_line(t + 2, "event", text=f"Log_{n}{i} washed up"))
            lines.append(log_line(t + 3, "glance", text=f"Log_{n}{i} washed up", turned=bool(i), degrees=30))
            lines.append(log_line(t + 9, "project", phase="end", goal="", intention=f"p{n}.{i}", ok=i != 1))
        if n % 7 == 0:
            lines.append(log_line(t + 10, "learn", name=f"skill_{n}", does="does a thing"))
        t += 40
    (run / "mind/log.jsonl").write_text("".join(lines))
    replay.Packer(run, store=replay.LocalStore())._tracks()
    tracked = [json.loads(x) for f in sorted((run / "replay/tracks").rglob("*.jsonl")) for x in f.read_text().splitlines()]
    for at in (T + 5, T + 1955, T + 2000, T + 2033, T + 2041, T + 3500, t + 60):
        before = [e for e in tracked if e["time"] < at]
        lead = replay.read_tracks(run, at * 1000, at * 1000 + 60_000)["lead"]
        assert len(lead) < len(before) or at < T + 100
        assert replay.reduce_status(lead) == replay.reduce_status(before), at
    lead = lambda at: replay.read_tracks(run, at * 1000, at * 1000 + 60_000)["lead"]  # noqa: E731
    assert replay.reduce_status(lead(T + 1955))["now"] == {"time": T + 1950, "thinking": True}
    assert replay.reduce_status(lead(T + 2041))["now"] == {"time": T + 2040, "text": "p15.2", "step": 3, "of": 3}


def test_lines_that_never_show_do_not_count_as_lines():
    assert replay._makes_line({"kind": "decision", "thought": "Go."})
    assert not replay._makes_line({"kind": "decision", "thought": ""})  # an agenda with no thought: no line
    assert not replay._makes_line({"kind": "learn", "does": "hops"})
    assert replay._makes_line({"kind": "sleep", "dream": "ships"}) and not replay._makes_line({"kind": "sleep"})
    assert replay._makes_line({"kind": "project", "phase": "end", "ok": False})
    assert not replay._makes_line({"kind": "project", "phase": "end", "ok": True})


def test_a_quiet_island_does_not_send_the_lead_back_two_days(tmp_path, monkeypatch):
    """The lead stops once it has Godling's lines: the world's older than those are never kept, however few it has."""
    run = tmp_path / "run"
    (run / "mind").mkdir(parents=True)
    lines = [log_line(T - 30 * 3600, "event", text="A wave rolled in")]  # the island's only event, a day ago
    lines += [log_line(T + 60 * n, "decision", thought=f"Plan {n}.", needs="") for n in range(30)]
    lines += [log_line(T + 1750, "project", phase="start", goal="", intention="Rest"),
              log_line(T + 1760, "bubble", ok=True, thing="sea", feeling="calm")]
    (run / "mind/log.jsonl").write_text("".join(lines))
    replay.Packer(run, store=replay.LocalStore())._tracks()
    read = []
    original = replay._read_lines
    monkeypatch.setattr(replay, "_read_lines", lambda path: read.append(path.name) or original(path))
    at = (T + 1800) * 1000
    lead = replay.read_tracks(run, at, at + 60_000)["lead"]
    assert len(lead) == 2 + 2 * replay.FEED_KEPT and lead[-3]["thought"] == "Plan 29."
    assert all(e["kind"] != "event" for e in lead)
    assert len(read) <= 3  # the span's hour, and the lead's hour or two, never two days of hours


def test_a_mind_long_silent_does_not_make_all_of_its_silence_the_lead(tmp_path, monkeypatch):
    monkeypatch.setattr(replay, "LEAD_MOST", 20)
    run = tmp_path / "run"
    (run / "mind").mkdir(parents=True)
    lines = [log_line(T, "decision", thought="Quiet now.", needs="")]
    lines += [log_line(T + 1 + i, "event", text=f"Wave {i} rolled in") for i in range(100)]
    (run / "mind/log.jsonl").write_text("".join(lines))
    replay.Packer(run, store=replay.LocalStore())._tracks()
    lead = replay.read_tracks(run, (T + 200) * 1000, (T + 300) * 1000)["lead"]
    assert 20 <= len(lead) <= 21 and lead[0]["thought"] == "Quiet now."
    feed = replay.reduce_status(lead)["feed"]
    assert feed[0]["text"] == "Quiet now." and feed[-1]["text"] == "Wave 99 rolled in"
