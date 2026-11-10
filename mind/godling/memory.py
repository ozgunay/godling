"""Native memory: episodes (the past), intentions (the future), structures and a digest.

Implements the plan's MemoryAdapter interface (§10.6: store_experience / retrieve / reflect /
invalidate / health) so Hindsight or Cognee can be swapped in later as a benchmark arm.
Episodes cite the world tick they came from; physical facts live in the skills, not here.
"""
import json
import math
import re
import time
from pathlib import Path

from .files import write_atomic
from .house import Site, at, site_of


def house_title(house):
    """How the body names the house the mind is building: "your house at (x, z)", by its first cell inside."""
    return f"your house at {at(house['inside'][0])}"


def _words(text):
    return {w for w in re.findall(r"[a-z0-9_]+", text.lower()) if len(w) > 3}


# Lessons a change to the world made untrue: (an id, what such a lesson says, why). A memory written before the change
# retires them once, when it is opened, so a resumed run never recalls them; the id is kept in its state, so a lesson
# learnt afterwards is never retired. What happened (a log that did wash up, a project) is kept: only lessons go.
RETIRED = (
    # ADR-026: no log washes up any more, and the axe fells a palm into one log, not two.
    ("adr-026-logs", re.compile(r"\blogs? (?:\w+ )?wash(?:es)? up\b|\bdriftwood\b"
                                r"|\b(?:palms?|fell\w*|axe)\b[^.]*\b(?:two|2) logs\b", re.IGNORECASE),
     "untrue since ADR-026: no log washes up, and the axe fells a palm into one log"),
)


class NativeMemory:
    def __init__(self, root):
        self.root = Path(root)
        self.house_project_enabled = True  # runtime policy, independent of the saved project
        self.root.mkdir(parents=True, exist_ok=True)
        self.episodes_path = self.root / "episodes.jsonl"
        self.state_path = self.root / "state.json"
        self.episodes = []
        if self.episodes_path.exists():  # a last line cut short (a crash, or a backup copied mid-write) is left out
            for line in self.episodes_path.read_text().splitlines():
                try:
                    self.episodes.append(json.loads(line))
                except ValueError:
                    continue
        self.state = {"digest": "", "intentions": [], "structures": {}, "last_sleep": time.time(), "slept": 0}
        if self.state_path.exists():
            self.state.update(json.loads(self.state_path.read_text()))
        self._retire()

    def _retire(self):
        """Retire the lessons RETIRED names that this memory has not retired yet (once per memory, not every start)."""
        done = set(self.state.get("retired", []))
        due = [r for r in RETIRED if r[0] not in done]
        if not due:
            return
        for name, pattern, why in due:
            for ep in self.episodes:
                if ep.get("kind") == "lesson" and not ep.get("invalid") and pattern.search(ep["text"]):
                    ep["invalid"] = why
            self._retire_more(pattern)
            done.add(name)
        self.state["retired"] = sorted(done)
        if self.episodes:
            write_atomic(self.episodes_path, "".join(json.dumps(ep) + "\n" for ep in self.episodes))
        write_atomic(self.state_path, json.dumps(self.state, indent=2))

    def _retire_more(self, pattern):
        """What else an engine keeps that `pattern` makes untrue (BrainMemory: its facts)."""

    # ---- MemoryAdapter ----------------------------------------------------------------
    def store_experience(self, text, kind="event", tick=0, entities=(), importance=2):
        episode = {"id": len(self.episodes) + 1, "time": time.time(), "tick": tick, "kind": kind,
                   "text": text.strip()[:600], "entities": sorted(set(entities)), "importance": int(importance)}
        self.episodes.append(episode)
        with self.episodes_path.open("a") as f:
            f.write(json.dumps(episode) + "\n")
        return episode["id"]

    def retrieve(self, entities=(), text="", limit=8):
        """Recency x importance x relevance, as in Generative Agents; no vector database."""
        now = time.time()
        want_entities, want_words = set(entities), _words(text)
        scored = []
        for ep in self.episodes:
            if ep.get("invalid"):
                continue
            age_h = (now - ep["time"]) / 3600
            relevance = 0.6 * len(want_entities & set(ep["entities"])) + 0.2 * len(want_words & _words(ep["text"]))
            score = ep["importance"] / 5 + math.exp(-age_h / 2) + relevance
            scored.append((score, ep))
        return [ep for _, ep in sorted(scored, key=lambda s: -s[0])[:limit]]

    # ---- what the mind uses (same for every engine) -----------------------------------
    def note(self, text, about="", importance=3, tick=0):
        """Something the mind decided to remember."""
        return self.store_experience(text, kind="lesson", tick=tick, entities=[about] if about else (),
                                     importance=importance)

    def recall_for(self, entities, text, limit=8):
        """What to put in the mind's working memory: conclusions (facts) and relevant episodes.

        The original engine has no consolidated facts: it returns recalled episodes only.
        """
        return {"facts": [], "episodes": self.retrieve(entities=entities, text=text, limit=limit)}

    def consolidation_input(self):
        """Facts to tidy during sleep (engines without a fact store return nothing)."""
        return {}

    def apply_consolidation(self, facts_by_subject):
        pass

    def flush(self):
        """Engines that batch writes (Hindsight) send them here; the native ones write immediately."""

    def reflect_input(self):
        """Episodes since the last sleep, for the mind to consolidate."""
        return [ep for ep in self.episodes if ep["time"] >= self.state["last_sleep"] and not ep.get("invalid")]

    def invalidate(self, episode_id, reason):
        for ep in self.episodes:
            if ep["id"] == episode_id:
                ep["invalid"] = reason
        write_atomic(self.episodes_path, "".join(json.dumps(ep) + "\n" for ep in self.episodes))

    def health(self):
        return {"episodes": len(self.episodes), "intentions": len(self.open_intentions()),
                "structures": len(self.state["structures"]), "slept": self.state["slept"]}

    # ---- the future and the self ------------------------------------------------------
    def open_intentions(self):
        return [i for i in self.state["intentions"] if i.get("status", "open") == "open"]

    def set_intentions(self, texts):
        self.state["intentions"] = [{"text": t.strip()[:200], "status": "open"} for t in texts if t.strip()][:6]

    def add_structure(self, name, cubes, where, positions, keep=True):
        """`positions` maps each cube to where it stood when kept; attention reports displacement from there."""
        self.state["structures"][name] = {"cubes": list(cubes), "where": [round(where[0], 1), round(where[1], 1)],
                                          "positions": {c: [round(v, 3) for v in positions[c]] for c in cubes},
                                          "keep": keep, "since": time.time()}

    def release_structure(self, name):
        """Let go of a kept structure. Its pieces are building material again, not something it built."""
        released = self.state["structures"].pop(name, None)
        if released:
            self.state["placed"] = [p for p in self.state.get("placed", []) if p not in released["cubes"]]

    def protected_cubes(self):
        """The pieces the body offers as no free material: what it built (Mind.keep_builds), the house's own and the
        steps beside its walls, but for what is in the house's way; and what the mind kept by name, wherever it lies
        (ADR-027: a woodpile beside the walls stays its own)."""
        house = (self.state.get("house") or {}) if self.house_project_enabled else {}
        kept = [s for s in self.state["structures"].values() if s.get("keep")]
        built = {c for s in kept if s.get("auto") for c in s["cubes"]}
        named = {c for s in kept if not s.get("auto") for c in s["cubes"]}
        return (((built | set(house.get("pieces", [])) | set(house.get("steps", [])))
                 - set(house.get("in_the_way", []))) | named)

    def built_into(self, piece):
        """The name of the build (Mind.keep_builds) or the house (Mind.house_project) a piece is built into, or None.
        Only these does the body refuse to pick up; a piece the mind kept by name it may still take (in run hut2 it
        named a log lying on the sand "camp roof beam", then could not lift it onto the roof)."""
        house = (self.state.get("house") or {}) if self.house_project_enabled else {}
        if piece in house.get("pieces", []):
            return house_title(house)
        if piece in house.get("in_the_way", []) or piece in house.get("steps", []):
            return None  # in its room or doorway: the house says clear it (run hp-proj1); a step is to lift (ADR-027)
        return next((title for title, s in self.state["structures"].items() if s.get("auto") and piece in s["cubes"]),
                    None)

    def reserved_cells(self):
        """The site of the house the mind is building (Mind.house_project), a house.Site of {cell: what it is}: its
        room, doorway and way out, its walls, the strip of ground a cell wide round them and the way in to the doorway
        (house.site_of). The body sets nothing down there but the walls' own pieces in their line, and sets nothing
        aside there at all (run hp-full2: three pieces it set down in the house stopped the house being finished;
        ADR-027: in the live run of 2026-11-08 the reflex set 29 things down at the site). Once the house stands, only
        its room, doorway and way out, and only for what the body sets aside: the rest is the mind's to use."""
        house = (self.state.get("house") or {}) if self.house_project_enabled else {}
        if not house.get("inside") or not house.get("door"):
            return Site()
        site = site_of([tuple(c) for c in house["inside"]], tuple(house["door"]),
                       [tuple(c) for c in house.get("posts", [])])  # a post's cell is the post's (ADR-033, INT-1)
        if house.get("built"):
            return Site({c: kind for c, kind in site.items() if kind in ("room", "doorway", "way out", "post")},
                        building=False)
        return site

    def planned_roof(self):
        """Where the guided roof of the house the mind is building puts its logs (house.plan "roof", kept by
        Mind.house_progress): {((ix, iz), axis)}. The hands set a log on its middle there as aimed (ADR-033)."""
        house = (self.state.get("house") or {}) if self.house_project_enabled else {}
        return {((c[0], c[1]), c[2]) for c in house.get("roof", [])}

    def set_house(self, house):
        """The house the mind is building (Mind.house_project), or None once it gives it up."""
        if house is None:
            self.state.pop("house", None)
        else:
            self.state["house"] = house

    def note_placed(self, pieces):
        """Pieces the body set down itself (place_at, put_down): what it builds with them is its own."""
        placed = [p for p in self.state.get("placed", []) if p not in pieces] + list(pieces)
        self.state["placed"] = placed[-400:]

    def amend(self, text, about="house", tick=0, entities=()):
        """Something that makes the story so far wrong (ADR-028: the house it calls finished broke): an episode the next
        sleep consolidates, and until then a line shown right after the digest."""
        self.store_experience(text, kind=about, tick=tick, entities=[about, *entities], importance=5)
        self.state["amendments"] = (self.state.get("amendments", []) + [text.strip()[:400]])[-4:]

    def finish_sleep(self, digest, intentions):
        if digest.strip():  # a sleep that wrote no story leaves the old one, and what has made it wrong since
            self.state["digest"] = digest.strip()[:2500]
            self.state["amendments"] = []  # the new story is written from them
        self.set_intentions(intentions)
        self.state["last_sleep"] = time.time()
        self.state["slept"] += 1

    def save(self):
        write_atomic(self.state_path, json.dumps(self.state, indent=2))
