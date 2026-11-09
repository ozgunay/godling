"""ADR-028: the mind hears at once when the house it built is lost.

Live run 2026-11-08/09: an earthquake at 06:33 and a meteor at 06:34:50 took the finished house from 19 pieces to 3.
Nothing said so: the sleep digest still called the house finished, the prompt said it had come "no further in 381
minutes", and at 06:36 the mind thought "The roof over the room still keeps me dry" while every step said it stood in
the rain. It died of the cold at 06:54.
"""
from godling import skills as sk
from godling.attention import Attention
from godling.learned import SkillLibrary
from godling.memory import NativeMemory
from godling.memory2 import BrainMemory
from godling.mind import Mind
from godling.skills import Skills
from godling.world import BODY_CENTRE_Y
from helpers import block, ent, ground
from island import FakeTime, Island

import pytest


class FakeLLM:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def complete_json(self, system, user, purpose="decide", on_reasoning=None):
        self.calls.append({"system": system, "user": user, "purpose": purpose})
        return self.replies.pop(0)


ROOM = [[0, 0], [2.5, 0], [0, 2.5], [2.5, 2.5]]
DOOR = [0, -2.5]
ROOF = ["Log_S", "Log_N", "Log_W0", "Log_E0", "Log_W1", "Log_E1", "Block_SE", "Block_NE"]


def house(high=3, roof=True):
    """A finished house two by two at cells (0..1, 0..1): walls `high` blocks all round, corners too, the doorway
    south at (0, -1), and a roof of logs and two caps in the layer above (the benchmark house of test_house.py)."""
    pieces = []
    for dx in range(-1, 3):
        for dz in range(-1, 3):
            if (0 <= dx <= 1 and 0 <= dz <= 1) or (dx, dz) == (0, -1):
                continue
            pieces += [block(f"Block_w{dx + 1}{dz + 1}{k}", dx * 2.5, (k - 0.5) * 2.5, dz * 2.5) for k in range(1, high + 1)]
    if roof:
        y = (high + 0.5) * 2.5
        logs = [("Log_S", 0, -1), ("Log_N", 0, 2), ("Log_W0", -1, 0), ("Log_E0", 2, 0), ("Log_W1", -1, 1), ("Log_E1", 2, 1)]
        pieces += [ent(name, (dx * 2.5, y, dz * 2.5), (7.5, 2.5, 2.5)) for name, dx, dz in logs]
        pieces += [block("Block_SE", 5, y, -2.5), block("Block_NE", 5, y, 5)]
    return pieces


@pytest.fixture
def make(monkeypatch, tmp_path):
    def build(pieces, memory=None):
        island = Island([ground(attrs={"Surface": "Sand"}), *pieces])
        island.me = [0, BODY_CENTRE_Y, -20]
        monkeypatch.setattr(sk, "time", FakeTime(island))
        library, logs, news = SkillLibrary(tmp_path / "skills.json"), [], []
        mem = memory or NativeMemory(tmp_path / "mem")
        body = Skills(island, library=library, protected=mem.protected_cubes, kept_in=mem.built_into)
        mind = Mind(FakeLLM(), mem, "I am a castaway.", body, library, log=lambda **k: logs.append(k),
                    house_project=True)
        mind.on_news = lambda text, salience: news.append((text, salience))
        return island, mem, mind, logs, news
    return build


def choose(mind, island):
    mind.adopt({"reply": {"house": {"inside": ROOM, "door": DOOR}}, "seconds": 1, "prepared": {"assumes": None}},
               island.snap())


def phases(logs):
    return [l["phase"] for l in logs if l["kind"] == "house" and l["phase"] not in ("installed", "progress")]


def test_the_mind_hears_at_once_that_its_house_is_lost(make):
    island, mem, mind, logs, news = make(house())
    choose(mind, island)
    assert phases(logs) == ["chose", "built"]
    mem.state["digest"] = "My house at (0,0) is finished, the only warm dry place; I mend there between jobs."
    mem.state["house"]["best_at"] -= 381 * 60  # finished long ago, and no further since: it was done
    # The quake and the meteor: the roof is smashed and thrown, and one corner of the walls knocked down.
    for name in ROOF:
        island.ents.pop(name)
    island.ents["Block_w003"]["position"] = [-12, 1.25, 6]
    mind.record_outcome({"goal": "sit out the quake under the roof"}, [], island.snap())

    lost = [l for l in logs if l["kind"] == "house" and l["phase"] == "lost"]
    assert len(lost) == 1
    assert lost[0]["was_house"] is True and lost[0]["had"] == 41 and lost[0]["pieces"] == 32
    assert lost[0]["gone"] == sorted(ROOF + ["Block_w003"])
    told = ("Your house at (0.0, 0.0) is no longer a house: 9 of the 41 pieces in its walls and roof are gone or knocked "
            "out of place (Block_NE, Block_SE, Block_w003, Log_E0, Log_E1, Log_N and 3 more). It keeps neither the rain "
            "nor the cold off you now.")
    assert lost[0]["text"] == told
    assert news == [(told, 5)]  # attention hears it as news (run_godling wires on_news to Attention.notice)

    # The next plan: told plainly, in the line about its house and in its notes; no stall from before the loss.
    text = mind.situation(island.snap(), [], [])
    line = next(l for l in text.splitlines() if l.startswith("Your house"))
    assert ("the doorway at (0.0, -2.5). It stood as a house until 0 minutes ago; now it is no house, and keeps neither "
            "the cold off you nor, where its roof is gone, the rain.") in line
    assert "come no further" not in text
    assert f"Notes: {told}" in text
    # Memory: an episode the next sleep consolidates, and the digest no longer left saying the house is finished.
    episode = mem.episodes[-1]
    assert episode["kind"] == "house" and episode["importance"] == 5 and episode["text"] == told
    assert f"Your story so far:\n{mem.state['digest']}\nSince you wrote that: {told}" in text
    # The plan after it still says so (notes are delivered once; the house line and the digest's addendum stay).
    mind.prepare(island.snap(), [], [])
    again = mind.situation(island.snap(), [], [])
    assert "It stood as a house until" in again and f"Since you wrote that: {told}" in again
    assert "Notes:" not in again
    # Said once: the next look finds nothing new.
    mind.record_outcome({"goal": "look"}, [], island.snap())
    assert phases(logs) == ["chose", "built", "lost"] and len(news) == 1

    # Sleep rewrites the story from it, and the addendum goes.
    mind.llm = FakeLLM({"digest": "The quake and a sky stone broke my house.", "intentions": ["rebuild the roof"]})
    mind.sleep(island.snap())
    assert f"Since you wrote that: {told}" in mind.llm.calls[0]["user"]
    assert mem.state["digest"] == "The quake and a sky stone broke my house." and "Since you wrote" not in mind.situation(
        island.snap(), [], [])

    # Built again: it hears that too, and the house line stops saying it is lost.
    for piece in house():
        island.ents[piece["name"]] = piece
    mind.record_outcome({"goal": "rebuild"}, [], island.snap())
    assert phases(logs) == ["chose", "built", "lost", "built"]
    assert "It stood as a house until" not in mind.situation(island.snap(), [], [])
    assert news[-1] == ("Your house at (0.0, 0.0) stands as a house again: it keeps the rain and the cold off you.", 4)
    assert "Since you wrote that: Your house at (0.0, 0.0) stands as a house again" in mind.situation(
        island.snap(), [], [])


def test_pieces_lost_from_a_house_being_built(make):
    island, mem, mind, logs, news = make(house(roof=False))
    choose(mind, island)
    assert phases(logs) == ["chose"] and mem.state["house"]["installed"] == 33
    best = mem.state["house"]["best"]
    island.ents.pop("Block_w003")
    island.ents["Block_w013"]["position"] = [-12, 1.25, 6]
    mind.record_outcome({"goal": "a wall"}, [], island.snap())
    lost = [l for l in logs if l.get("phase") == "lost"]
    assert len(lost) == 1 and lost[0]["was_house"] is False and lost[0]["gone"] == ["Block_w003", "Block_w013"]
    told = ("Part of your house at (0.0, 0.0) came down: Block_w003 and Block_w013 are gone or knocked out of place "
            "(31 of its pieces stand).")
    assert news == [(told, 4)] and mind.notes == [told]
    assert mem.episodes[-1]["text"] == told and not mem.state.get("amendments"), "the digest never said it was finished"
    # Its progress is measured from what still stands: putting a piece back is progress again.
    assert mem.state["house"]["best"] < best
    island.ents["Block_w013"]["position"] = [-2.5, 6.25, 0]
    mind.record_outcome({"goal": "a wall"}, [], island.snap())
    assert [l for l in logs if l.get("phase") == "progress"][-1]["score"] == mem.state["house"]["best"]


def test_no_false_alarms(make):
    island, mem, mind, logs, news = make(house(roof=False))
    choose(mind, island)
    # A house kept from before this was told has no record of its pieces: the first look only takes note of them.
    for key in ("had", "had_for"):
        mem.state["house"].pop(key, None)
    island.ents.pop("Block_w003")
    mind.record_outcome({"goal": "x"}, [], island.snap())
    # Its layout changed on the same site: pieces counted afresh, nothing lost.
    mind.adopt({"reply": {"house": {"inside": ROOM, "door": [-2.5, 0]}}, "seconds": 1, "prepared": {"assumes": None}},
               island.snap())
    mind.record_outcome({"goal": "x"}, [], island.snap())
    # Something set down in the room was never part of it.
    island.ents["Block_x"] = block("Block_x", 0, 1.25, 0)
    mind.record_outcome({"goal": "x"}, [], island.snap())
    assert "lost" not in phases(logs) and news == []


def test_brain_memory_corrects_its_beliefs_about_the_house(make, tmp_path):
    mem = BrainMemory(tmp_path / "brain")
    mem.note("my house is finished and keeps the cold off", about="house")
    island, mem, mind, logs, news = make(house(), memory=mem)
    choose(mind, island)
    for name in ROOF:
        island.ents.pop(name)
    mind.record_outcome({"goal": "x"}, [], island.snap())
    assert any("is no longer a house" in f["text"] for f in mem.facts["house"])


def test_attention_takes_notice_of_what_it_is_told(tmp_path):
    logs = []
    attention = Attention(NativeMemory(tmp_path / "mem"), log=lambda **k: logs.append(k))
    attention.notice("Your house at (0.0, 0.0) is no longer a house.", 5)
    assert attention.take_events() == [{"text": "Your house at (0.0, 0.0) is no longer a house.", "salience": 5,
                                         "entities": [], "tick": 0}]
    assert [text for _, text in attention.noticed] == ["Your house at (0.0, 0.0) is no longer a house."]
    assert logs[-1]["kind"] == "event" and logs[-1]["salience"] == 5
    # Told, not seen: it interrupts nothing by itself (the reflex that tells it stops the step itself).
    attention.notice("You were cold and hurt, and your body took shelter by itself.", 4)
    attention.on_step(Island([ground()]).snap())
    attention.on_step(Island([ground()]).snap())
