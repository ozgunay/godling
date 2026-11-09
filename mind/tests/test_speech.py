"""What Godling says aloud (ADR-031): plain words a viewer can read, and a voice of its own at the moments viewers care
about, with a rate limit.

Run live (2026-11-08/09, 9.6 h): its last spoken line was at 04:08 UTC, then 3 h 38 min of silence through the viewer
peak and both its deaths, and the lines it did speak were full of coordinates; one said "Night 1245595", the world's
tick count."""
import re

import pytest

from godling import speech
from godling.speech import Voice, plain
from godling.world import WorldError
from helpers import ground
from island import FakeTime, Island
from godling import skills as sk
from godling.skills import Skills

# Lines Godling said in run live, word for word (mind/log.jsonl, the say skill).
SPOKEN = [
    "I woke at (15, -27.5). Raft wreck on the west beach. I will raise something tall there so it can be seen from "
    "the water.",
    "Night 144. House stands; I am going in.",
    "West beach, midday. H mark at x minus one one five, bars at z minus forty five and minus forty two and a half. "
    "Gate posts at z minus twenty and minus fifteen. New posts going up at z minus ten, minus five, zero, with beams "
    "over them. I am here and I am building.",
    "West sand, midday. My house stands at x -85 to -77.5, z -30 to -22.5, walls three high, roof on, door at -80,-30. "
    "The H is drawn in the sand: bar at x -115 from z -49.5 to -30, crossbars at z -45 and -42.5. Upright logs run "
    "north along x -115, now down to z -30. I am alone.",
    "ring nearly closed, sea gate and a second arch on the x=-115 line, stone cut for the west tower",
    "line at x -115 going north: posts at z -10 and -5, beam at 8.75 over -7.5, and a beam over the SeaGate",
    "Godling here. I am well. I woke on this island with no name for it 270 minutes ago and no one knows I am here. I am "
    "covering the land with things that can be seen from far off: a line of posts at x=-115 running down to the sea, "
    "and a ring 25 units across around (-80,-27.5).",
    "03:05, storm and rain. The x=-115 gate line stands: seven posts, beams at 8.75 over z -20..-15, 2.5 and 7.5.",
    "Night 1245595. Ladder drawn on the west sand: four upright strokes, three rungs, 7 wide and 20 long. WestTower "
    "carries a mast at 17.5. Mend, then haul at dawn.",
    "Third stroke cut on the west sand at x -110. A mast goes up on the west tower. The wide ring is nearly closed.",
]
# What a viewer must never read in a spoken line: places as numbers, the world's counts, its numbered names.
INTERNAL = re.compile(r"\(|_\d|\d{4,}|\d\.\d|(?<![\w.])[-−]\d|\b[xyz]\s*=?\s*-?\d|\bminus\b|\btick\b", re.I)


@pytest.mark.parametrize("line", SPOKEN)
def test_no_spoken_line_keeps_a_place_given_as_numbers_a_tick_or_a_numbered_name(line):
    said, _ = plain(line)
    assert said and not INTERNAL.search(said), said
    assert len(said) <= speech.MOST


def test_what_viewers_read_of_the_lines_it_spoke():
    assert plain(SPOKEN[0]) == ("I woke. Raft wreck on the west beach. I will raise something tall there so it can be "
                                "seen from the water.", ["places"])
    assert plain(SPOKEN[1]) == ("Night 144. House stands; I am going in.", [])  # nothing internal: as it was
    assert plain(SPOKEN[3])[0] == ("West sand, midday. My house stands, walls three high, roof on. The H is drawn in "
                                   "the sand. Upright logs run north. I am alone.")
    assert plain(SPOKEN[5])[0] == "Line going north, and a beam over the sea gate."
    assert plain("Rain all night. Arcade at x -115: beams at 8.75, and I am trying a rail at 11.25 from a ladder.")[0] == (
        "Rain all night. I am trying a rail from a ladder.")
    assert plain(SPOKEN[8]) == ("Ladder drawn on the west sand: four upright strokes, three rungs, 7 wide and 20 long. "
                                "West tower carries a mast. Mend, then haul at dawn.", ["the world's counts", "places"])


def test_numbered_names_become_plain_words():
    assert plain("Lightning struck Palm_64 and felled it: Log_6 and Log_7 lie at (-18, -75)")[0] == (
        "Lightning struck a palm and felled it: two logs lie.")
    assert plain("Bring Log_12 to the house, then fasten Block_3, Block_4 and Block_5.")[0] == (
        "Bring a log to the house, then fasten three blocks.")
    assert plain("arch_beam_115 failed twice")[0] == "Arch beam failed twice."
    assert plain("Gone: Log_W0, Log_W1 and Block_SE.")[0] == "Gone: two logs and a block."
    assert plain("ObservedGround_3_4 is sand.")[0] == "An observed ground is sand."
    assert plain("[tick 1245595] I slept, World tick 1245595.") == ("I slept.", ["the world's counts"])


def test_a_line_that_is_only_internals_is_not_said():
    assert plain("(-80, -27.5)") == ("", ["places"])
    assert plain("x -115, z -30 to -22.5") == ("", ["places"])
    assert plain("World tick 1245595") == ("", ["the world's counts"])
    assert plain("   ") == ("", [])
    assert plain(None) == ("", [])


def test_plain_words_stay_as_they_were_and_long_lines_end_at_a_sentence():
    assert plain("Rain again. In, dry, mend.") == ("Rain again. In, dry, mend.", [])
    assert plain("A room 2 x 2, the door south, and a zone to stand in.") == (
        "A room 2 x 2, the door south, and a zone to stand in.", [])  # sizes and words are not places
    assert plain("hi") == ("Hi.", [])
    assert plain('"Sixteen posts now"') == ("Sixteen posts now.", [])
    assert plain("42") == ("42.", [])
    long = " ".join(["The ring is nearly closed and the gate stands."] * 8)
    said, _ = plain(long)
    assert len(said) <= speech.MOST and said.endswith("stands.")
    said, _ = plain("word " * 80)
    assert len(said) <= speech.MOST and said.endswith("…")


# ---- the body's say ------------------------------------------------------------------------------------------------
@pytest.fixture
def body(monkeypatch):
    island = Island([ground()])
    monkeypatch.setattr(sk, "time", FakeTime(island))
    return island, Skills(island)


def test_say_speaks_plain_words_and_tells_the_mind_what_it_left_out(body):
    island, skills = body
    result = skills.run("say", {"text": SPOKEN[8]})
    assert result.ok and island.said == [plain(SPOKEN[8])[0]]
    assert result.summary == (f'said "{island.said[0]}"; left out the world\'s counts and places: the strangers who '
                              "watch read words, not your map")
    assert island.acts[-1] == ("Talk", {})


def test_say_refuses_a_line_with_nothing_a_viewer_can_read_and_says_why(body):
    """78-CDE2: the step does not fail, so what comes after it in the project (or a learned skill) still runs."""
    island, skills = body
    result = skills.run("say", {"text": "x -115, z -30 to -22.5"})
    assert result.ok and result.facts == {"said": False}
    assert island.said == [] and ("Talk", {}) not in island.acts
    assert result.summary == ("not said: it was all places as numbers, which the strangers who watch cannot read; say "
                              "where in words (the west beach, by my house)")


def test_said_lines_go_to_the_log_for_the_viewers_screen(monkeypatch):
    island, logs = Island([ground()]), []
    monkeypatch.setattr(sk, "time", FakeTime(island))
    skills = Skills(island, log=lambda **k: logs.append(k))
    assert skills.run("say", {"text": "Rain again."}).ok
    said = [l for l in logs if l["kind"] == "said"]
    assert said == [{"kind": "said", "words": "Rain again.", "moment": None, "left_out": []}]


# ---- the voice: key moments ----------------------------------------------------------------------------------------
class World:
    def __init__(self, fail=False):
        self.said, self.fail = [], fail

    def say(self, text):
        if self.fail:
            raise WorldError("chat down")
        self.said.append(text)


class LLM:
    def __init__(self, *replies):
        self.replies = list(replies) or [{"say": "So it goes."}]
        self.calls = []

    def quick_json(self, system, user, purpose, max_tokens=80):
        self.calls.append({"system": system, "user": user, "purpose": purpose})
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


class Clock:
    def __init__(self):
        self.now = 10_000.0

    def __call__(self):
        return self.now


def voice(*replies, world=None, on_said=None):
    clock, logs = Clock(), []
    v = Voice(world or World(), LLM(*replies), soul="I am Godling.", log=lambda **k: logs.append(k), clock=clock,
              on_said=on_said)
    v.hears_log = lambda: [l for l in logs if l["kind"] == "said"]
    return v, clock, logs


def event(text, **extra):
    return {"kind": "event", "text": text, "salience": 4, **extra}


DIED = event("You died of the cold. Your body lies where it fell; you will come back to life at the start in about 30s",
             death="died", at=[-80, -28])
REBORN = event("You have come back to life at the start, whole but half fed. What you carried lies where you died, at "
               "(-80, -28)", death="reborn")
NOTE = event('A paper glider drifted down at (-71, 14) with a note from one of the strangers who watch you. It reads: '
             '"Hello godling please stop building for a while and rest"', sky="Note", sky_id=7, sky_stage="arrived",
             note="Hello godling please stop building for a while and rest")
STRUCK = event("Lightning struck you: you are burned and hurt, your health is 50 of 100", at=[0, 0], hit="struck")


def test_death_and_rebirth_are_spoken_without_the_mind_choosing_to(monkeypatch):
    heard = []
    v, clock, logs = voice({"say": "Too cold at (-80, -28)... I cannot hold on."}, on_said=heard.append)
    v.hears(DIED)
    assert v.step() == "Too cold... I cannot hold on."  # last words, in its own voice, with no place as numbers
    call = v.llm.calls[0]
    assert call["purpose"] == "voice" and "You died of the cold" in call["user"] and "I am Godling." in call["system"]
    clock.now += 30
    v.hears(REBORN)
    assert v.step() is None  # its reflection on the death is on its way: its own words about coming back
    clock.now += 8
    v.hears({"kind": "death", "cause": "Cold", "deaths": 1,
             "feeling": "I came back cold and empty; this time I will raise a roof before a tower."})
    assert v.step() == "I came back cold and empty; this time I will raise a roof before a tower."
    assert len(v.llm.calls) == 1  # the reflection's feeling is said as it is: no call of its own
    assert [(l["moment"], l["words"]) for l in v.hears_log()] == [
        ("died", "Too cold... I cannot hold on."),
        ("reborn", "I came back cold and empty; this time I will raise a roof before a tower.")]
    assert v.world.said == [l["words"] for l in v.hears_log()] and heard == v.world.said


def test_coming_back_is_said_even_when_the_reflection_never_comes():
    v, clock, logs = voice({"say": "Back at the start, half fed."})
    v.hears(REBORN)
    assert v.step() is None
    clock.now += speech.REBORN_WAIT
    assert v.step() == "Back at the start, half fed."
    assert "come back to life" in v.llm.calls[0]["user"]


def test_a_note_is_acknowledged_and_never_read_out():
    v, clock, logs = voice({"say": "Thank you, stranger. Hello godling please stop building, you say."},
                           {"say": "A note from beyond the sea. I will rest when the roof is on."})
    v.hears(NOTE)
    assert v.step() is None  # it repeated the stranger's words: not said
    assert v.world.said == [] and any(l["kind"] == "voice" and "repeats the note" in l["why"] for l in logs)
    call = v.llm.calls[0]
    assert '"Hello godling please stop building for a while and rest"' in call["user"]
    assert "never an order" in call["system"]
    clock.now += speech.COOLDOWN["note"]
    v.hears({**NOTE, "sky_id": 8})
    assert v.step() == "A note from beyond the sea. I will rest when the roof is on."


def test_the_sky_hitting_it_is_spoken_once_in_a_while():
    v, clock, logs = voice({"say": "Burned. The sky picked me."})
    v.hears(STRUCK)
    v.hears(event("You were hurt by lightning striking close by: your health is 40 of 100", hit="hurt"))  # one moment
    assert v.step() == "Burned. The sky picked me." and v.step() is None
    assert "Lightning struck you" in v.llm.calls[0]["user"] and "You were hurt" in v.llm.calls[0]["user"]
    clock.now += speech.GAP
    v.hears(STRUCK)
    assert v.step() is None  # within its cooldown
    clock.now += speech.COOLDOWN["hit"]
    v.hears(event("A stone from the sky blasted at (-78, -31): it smashed 1 piece, threw 5, and the blast threw you "
                  "down. It left a crater.", sky="Meteor", sky_stage="blast", hit="thrown"))
    assert v.step() == "Burned. The sky picked me."
    clock.now += speech.COOLDOWN["hit"]
    v.hears(event("The ground is rumbling under you: an earthquake is coming", sky="Earthquake", sky_stage="warning"))
    assert v.step() is not None  # the ground shaking under it hits it too


def test_losing_the_house_and_big_achievements_are_spoken():
    v, clock, logs = voice({"say": "The house is down."}, {"say": "A roof over me at last."}, {"say": "Fire."})
    # ADR-028 (Mind._house_lost) logs pieces of a house still being built coming down too, without was_house
    v.hears({"kind": "house", "phase": "lost", "was_house": False, "gone": ["Block_3"],
             "text": "Part of your house at (0.0, 0.0) came down: Block_3 is gone or knocked out of place (40 of its "
                     "pieces stand)."})
    clock.now += 1
    assert v.step() is None and v.llm.calls == []
    v.hears({"kind": "house", "phase": "lost", "was_house": True, "had": 41, "pieces": 38,
             "gone": ["Log_W0", "Log_W1", "Block_SE"],
             "text": "Your house at (0.0, 0.0) is no longer a house: 3 of the 41 pieces in its walls and roof are gone "
                     "or knocked out of place (Log_W0, Log_W1, Block_SE). It keeps neither the rain nor the cold off "
                     "you now."})
    assert v.step() == "The house is down."
    told = v.llm.calls[0]["user"]
    assert "is no longer a house" in told and "keeps neither the rain nor the cold" in told
    assert "(0.0" not in told and "Log_W0" not in told  # the mind's sentence, told in plain words
    clock.now += speech.GAP
    v.hears({"kind": "house", "phase": "built", "inside": [[0, 0]], "door": [0, -2.5]})
    assert v.step() == "A roof over me at last."
    clock.now += speech.GAP
    v.hears({"kind": "skill", "skill": "rub", "ok": True, "summary": "rubbed Spear_2 against Log_60 14 times, and a "
             "flame caught: Fire_1 burns on Log_60", "facts": {"made": "Fire_1"}})
    assert v.step() is None  # an achievement within the cooldown of the last
    clock.now += speech.COOLDOWN["achievement"]
    v.hears({"kind": "skill", "skill": "rub", "ok": True, "summary": "a flame caught: Fire_2 burns on Log_61",
             "facts": {"made": "Fire_2"}})
    assert v.step() == "Fire."
    clock.now += speech.COOLDOWN["achievement"]
    v.hears({"kind": "structures", "roofed": 0, "enclosures": 0, "houses": 0, "walls": 2})  # the island as found
    v.hears({"kind": "structures", "roofed": 0, "enclosures": 1, "houses": 0, "walls": 3})
    assert v.step() == "Fire." and "closed in" in v.llm.calls[-1]["user"]  # its first enclosure
    clock.now += speech.COOLDOWN["achievement"]
    v.hears({"kind": "structures", "roofed": 0, "enclosures": 1, "houses": 0, "walls": 4})  # more walls: not big
    assert v.step() is None and len(v.llm.calls) == 4


def test_everyday_news_and_its_own_doings_are_not_moments():
    v, clock, logs = voice()
    for entry in (event("It has started to rain"), event("A new object, Coconut_1, appeared at (3, 4)"),
                  event("Lightning struck Palm_3 and felled it: Log_6 lies at (-18, -75)", sky="Lightning",
                        sky_stage="arrived"),
                  {"kind": "skill", "skill": "walk_to", "ok": True, "summary": "walked to (3, 4)"},
                  {"kind": "house", "phase": "progress", "score": 12}, {"kind": "decision", "thought": "Hm."}):
        v.hears(entry)
    clock.now += 600
    assert v.step() is None and v.llm.calls == []


def test_lines_keep_a_gap_and_the_most_important_goes_first():
    v, clock, logs = voice({"say": "Burned."}, {"say": "A note."})
    v.hears(NOTE)
    v.hears(STRUCK)
    assert v.step() == "Burned."  # the sky hitting it matters more than a note
    clock.now += 5
    assert v.step() is None  # too soon after the last line
    clock.now += speech.GAP
    assert v.step() == "A note."


def test_its_own_say_counts_for_the_gap_but_death_is_said_at_once():
    v, clock, logs = voice({"say": "Gone."})
    assert v.say("Sixteen posts now.") == ("Sixteen posts now.", "")
    v.hears(STRUCK)
    assert v.step() is None
    clock.now += speech.CLOSE
    v.hears(DIED)
    assert v.step() == "Gone."  # dying does not wait for the gap, only for a breath


def test_a_moment_not_said_in_time_is_let_go_and_a_death_drops_the_last_lifes():
    v, clock, logs = voice({"say": "Late."})
    v.hears(NOTE)
    clock.now += speech.STALE + 1
    assert v.step() is None and v.llm.calls == []
    v.hears({**NOTE, "sky_id": 9})
    v.hears(DIED)
    assert v.step() == "Late." and "You died" in v.llm.calls[-1]["user"]
    clock.now += speech.COOLDOWN["note"] + speech.GAP
    assert v.step() is None  # the note belonged to the life that ended


def test_a_reply_finished_after_a_death_is_not_said():
    v, clock, logs = voice()
    v.hears(STRUCK)
    original = v.llm.quick_json

    def die_meanwhile(*a, **kw):
        v.hears(DIED)
        return original(*a, **kw)
    v.llm.quick_json = die_meanwhile
    assert v.step() is None and v.world.said == []


def test_the_runs_log_comes_back_to_the_voice_without_a_deadlock():
    """run_godling.py hands every log entry to the voice, its own lines too, from whichever thread logs it."""
    import threading
    clock, logs = Clock(), []
    v = None

    def log(**entry):
        logs.append(entry)
        v.hears(entry)
    v = Voice(World(), LLM({"say": "Burned."}), log=log, clock=clock)
    original, died = v.llm.quick_json, []

    def die_once(*a, **kw):  # dies while the words come
        if not died:
            died.append(v.hears(DIED))
        return original(*a, **kw)
    v.llm.quick_json = die_once
    v.hears(STRUCK)
    done = []

    def two_steps():
        done.append(v.step())
        clock.now += speech.CLOSE
        done.append(v.step())
    worker = threading.Thread(target=two_steps, daemon=True)
    worker.start()
    worker.join(5)
    assert not worker.is_alive() and done == [None, "Burned."]
    assert [l["kind"] for l in logs] == ["voice", "said"]


def test_an_hour_has_at_most_so_many_lines():
    v, clock, logs = voice()
    said = 0
    for half_minute in range(240):  # two hours of the sky hitting it and notes coming down, twice a minute
        v.hears(STRUCK)
        v.hears({**NOTE, "sky_id": half_minute})
        said += v.step() is not None
        clock.now += 30
    assert said == 2 * speech.PER_HOUR and len(v.llm.calls) == said


def test_a_failed_call_or_chat_says_nothing_and_never_stops_the_run():
    v, clock, logs = voice(RuntimeError("provider down"))
    v.hears(STRUCK)
    assert v.step() is None and any(l["kind"] == "error" and "voice" in l["message"] for l in logs)
    v, clock, logs = voice({"nothing": "here"}, {"say": "x -115"})
    v.hears(STRUCK)
    assert v.step() is None
    clock.now += speech.COOLDOWN["hit"]
    v.hears(STRUCK)
    assert v.step() is None and len(v.llm.calls) == 2 and v.world.said == []  # nothing a viewer can read in it
    assert [l["why"] for l in logs if l["kind"] == "voice"][-1].startswith("it was all places as numbers")
    v, clock, logs = voice(world=World(fail=True))
    v.hears(STRUCK)
    assert v.step() is None and any(l["kind"] == "error" for l in logs)
    assert v.say("hello") == ("", "the world chat did not take it: chat down")


def test_no_model_no_moments_but_plain_words_still():
    clock, logs = Clock(), []
    v = Voice(World(), log=lambda **k: logs.append(k), clock=clock)
    v.hears(DIED)
    assert v.step() is None
    assert v.narrate("Walk west along z -30 to the raft") == "Walk west to the raft."
    assert v.narrate("(3, 4)") is None
    assert v.world.said == ["Walk west to the raft."] and logs == []  # an intention is no spoken line


def test_the_voice_runs_beside_the_body(monkeypatch):
    v, clock, logs = voice({"say": "Gone."})
    monkeypatch.setattr(speech, "EVERY", 0.01)
    v.hears(DIED)
    v.start()
    try:
        for _ in range(500):
            if v.world.said:
                break
            import time
            time.sleep(0.01)
    finally:
        v.stop()
    assert v.world.said == ["Gone."]


# ---- review of #78 -------------------------------------------------------------------------------------------------
def test_names_after_an_article_keep_all_their_words_and_sizes_stay_sizes():
    """78-AB4, 78-AB5."""
    assert plain("the arch_beam_115 failed")[0] == "The arch beam failed."
    assert plain("I did every walk_to twice.")[0] == "I did every walk to twice."
    assert plain("my west_tower_2 stands")[0] == "My west tower stands."
    assert plain("A room two x two, the door south.") == ("A room two x two, the door south.", [])
    assert plain("A wall at x minus ten.")[0] == "A wall."  # a spelled place is still a place


def test_a_bare_pair_is_a_place_after_a_preposition_and_a_sign_is_a_sign():
    """78-AB6, 78-CLEAN7."""
    assert plain("My house is at 15, 27 on the sand.") == ("My house is on the sand.", ["places"])
    assert plain("Door at 3, 4.") == ("", ["places"]) and plain("My house is at 15, 27.")[0] == "My house."
    assert plain("Set it at +3,4 now.") == ("Set it now.", ["places"])
    assert plain("Set it at (+3, 4) now.") == ("Set it now.", ["places"])
    assert plain("Health 60, 47% fed, and 20:33, 62% fed.") == ("Health 60, 47% fed, and 20:33, 62% fed.", [])


def test_a_line_cut_for_length_says_so():
    """78-AB11: the mind is told its line was cut, as it is told what else was left out."""
    long = " ".join(["The ring is nearly closed and the gate stands."] * 5)
    said, left = plain(long)
    assert said.endswith("stands.") and left == ["what came after the first 200 characters"]
    assert speech.left_out_note(left) == "left out what came after the first 200 characters"


def test_numbers_that_are_not_text_are_said_as_numbers():
    """78-CDE8: a say step's text may come as a number; 0 is a number, not nothing."""
    assert plain(0) == ("0.", []) and plain(None) == ("", [])


def test_the_voices_clock_never_steps_back():
    """78-CDE7: the gap, cooldowns and staleness are measured on a clock a host's resync cannot move."""
    import time
    assert Voice(World()).clock is time.monotonic


def test_a_failed_chat_post_of_an_intention_loses_nothing_but_the_post():
    """78-CDE11: narrate() keeps the project going when only the chat fails, as say() does."""
    clock, logs = Clock(), []
    v = Voice(World(fail=True), log=lambda **k: logs.append(k), clock=clock)
    assert v.narrate("Walk west to the raft") is None
    assert [l["kind"] for l in logs] == ["error"] and "chat down" in logs[0]["message"]


def test_a_line_said_while_the_voices_words_come_puts_its_line_back_a_gap_later():
    """78-CDE3: its say step lands while the model writes the voice's line: the voice waits its gap again, and says
    the words it already has, with no second call."""
    v, clock, logs = voice({"say": "Burned."})
    original = v.llm.quick_json

    def meanwhile(*a, **kw):
        clock.now += 2
        v.say("Sixteen posts now.")  # the body's say step, on its own thread
        return original(*a, **kw)
    v.llm.quick_json = meanwhile
    v.hears(STRUCK)
    assert v.step() is None and v.world.said == ["Sixteen posts now."]
    v.llm.quick_json = original
    clock.now += speech.GAP - 1
    assert v.step() is None
    clock.now += 1
    assert v.step() == "Burned." and len(v.llm.calls) == 1  # the words it had, not a second call
    assert v.world.said == ["Sixteen posts now.", "Burned."]


def test_a_death_seen_only_once_it_is_back_asks_for_no_last_words():
    """78-CDE4: the whole death passed during a long model call; the body already stands at the start."""
    v, clock, logs = voice({"say": "Back, and half fed."})
    v.hears(event("You died of the cold. You have already come back to life at the start, whole but half fed",
                  death="died", back=True))
    assert v.step() is None and v.llm.calls == []  # no last words from a body standing at the start
    clock.now += 8
    v.hears({"kind": "death", "cause": "Cold", "deaths": 1, "feeling": "I came back with the rain still on me."})
    assert v.step() == "I came back with the rain still on me."
    assert [l["moment"] for l in v.hears_log()] == ["reborn"]


def test_the_killing_blow_is_not_said_after_it_comes_back():
    """78-SWEEP1: attention logs the blow that killed it after the death, from the same look; it belongs to the life
    that ended."""
    v, clock, logs = voice({"say": "Gone."})
    v.hears(DIED)
    v.hears(event("You were hurt by lightning striking close by: your health is 0 of 100", hit="hurt"))
    assert v.step() == "Gone."
    clock.now += 30
    v.hears(REBORN)
    clock.now += 9
    v.hears({"kind": "death", "cause": "Lightning", "deaths": 1, "feeling": "Back."})
    assert v.step() == "Back."
    for _ in range(10):
        clock.now += speech.GAP
        assert v.step() is None
    assert [l["moment"] for l in v.hears_log()] == ["died", "reborn"]
    v.hears(STRUCK)  # alive again, the sky hitting it is news again
    assert v.step() == "Gone."


def test_a_failed_rebirth_call_leaves_the_reflections_line_to_say():
    """78-CDE6: the rebirth counts as said only once it is."""
    v, clock, logs = voice(RuntimeError("provider down"))
    v.hears(REBORN)
    clock.now += speech.REBORN_WAIT
    assert v.step() is None
    clock.now += 20
    v.hears({"kind": "death", "cause": "Cold", "deaths": 1, "feeling": "I came back cold."})
    assert v.step() == "I came back cold."


def test_only_one_line_about_coming_back():
    v, clock, logs = voice({"say": "Back at the start."})
    v.hears(REBORN)
    clock.now += speech.REBORN_WAIT
    assert v.step() == "Back at the start."
    clock.now += 20
    v.hears({"kind": "death", "cause": "Cold", "deaths": 1, "feeling": "I came back cold."})  # the slow reflection
    clock.now += speech.GAP
    assert v.step() is None and v.world.said == ["Back at the start."]


def test_a_feeling_that_is_no_sentence_is_not_said():
    """78-SWEEP2."""
    v, clock, logs = voice({"say": "Back."})
    for feeling in (None, ["I came back."], "", "  "):
        v.hears({"kind": "death", "cause": "Cold", "deaths": 1, "feeling": feeling})
        assert v.step() is None and v.world.said == []


def test_a_fresh_fact_keeps_its_moment_fresh():
    """78-AB1: a hit merged into a moment waiting out its cooldown is as new as the hit."""
    v, clock, logs = voice({"say": "Burned."})
    v.hears(STRUCK)
    assert v.step() == "Burned."
    clock.now += 25
    v.hears(STRUCK)  # waits out the cooldown
    clock.now += 85
    v.hears(event("You were hurt by lightning striking close by: your health is 30 of 100", hit="hurt"))
    clock.now += 10  # 120 s after the last line; the first wait began 95 s ago, the newest hit 10 s ago
    assert v.step() == "Burned." and "your health is 30 of 100" in v.llm.calls[-1]["user"]


def test_moments_come_from_what_the_entries_say_they_are_not_their_wording():
    """78-CLEAN11, 78-CDE1: a say step quoting "a flame caught" is no fire, and a hit is a hit by its field."""
    v, clock, logs = voice({"say": "Fire."})
    v.hears({"kind": "skill", "skill": "say", "ok": True, "summary": 'said "I rubbed and a flame caught."', "facts": {}})
    v.hears(event("Lightning struck you: you are burned", at=[0, 0]))  # an old line, with no hit field
    clock.now += 1
    assert v.step() is None and v.llm.calls == []
    v.hears({"kind": "skill", "skill": "strike", "ok": True, "summary": "speared Fish_2; the catch, Catch_1, lies...",
             "facts": {"made": "Catch_1"}})
    assert v.step() == "Fire." and "speared a fish" in v.llm.calls[-1]["user"]


# ---- with ADR-028 merged ------------------------------------------------------------------------------------------
def test_its_house_lost_is_spoken_from_the_minds_own_entry(monkeypatch, tmp_path):
    """The house-lost moment, end to end on the merged tree: a real Mind builds the benchmark house, loses its roof and
    a corner (as run live's quake and meteor did), and logs ADR-028's entry (Mind._house_lost); the voice, hearing the
    mind's log as run_godling.py wires it, speaks of it once, told it in plain words."""
    from godling.learned import SkillLibrary
    from godling.memory import NativeMemory
    from godling.mind import Mind
    from godling.world import BODY_CENTRE_Y
    from test_house_lost import DOOR, ROOF, ROOM, FakeLLM as MindLLM, house
    v, clock, logs = voice({"say": "My house is down; the rain comes in."})
    island = Island([ground(attrs={"Surface": "Sand"}), *house()])
    island.me = [0, BODY_CENTRE_Y, -20]
    monkeypatch.setattr(sk, "time", FakeTime(island))
    library, mem = SkillLibrary(tmp_path / "skills.json"), NativeMemory(tmp_path / "mem")
    body = Skills(island, library=library, protected=mem.protected_cubes, kept_in=mem.built_into)
    mind = Mind(MindLLM(), mem, "I am a castaway.", body, library, log=lambda **k: v.hears(k), house_project=True)
    mind.adopt({"reply": {"house": {"inside": ROOM, "door": DOOR}}, "seconds": 1, "prepared": {"assumes": None}},
               island.snap())
    assert v.step() is not None  # its house first standing: an achievement
    clock.now += speech.COOLDOWN["achievement"]
    for name in ROOF:
        island.ents.pop(name)
    island.ents["Block_w003"]["position"] = [-12, 1.25, 6]
    mind.record_outcome({"goal": "sit out the quake under the roof"}, [], island.snap())
    mind.record_outcome({"goal": "look at what is left"}, [], island.snap())  # still lost: no second moment
    assert v.step() == "My house is down; the rain comes in."
    told = v.llm.calls[-1]["user"]
    assert "is no longer a house" in told and "(0.0" not in told and "Block_NE" not in told
    clock.now += speech.COOLDOWN["house_lost"]
    assert v.step() is None
    assert [l["moment"] for l in v.hears_log()] == ["achievement", "house_lost"]
