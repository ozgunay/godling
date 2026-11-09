"""Native v2: a brain-like memory (ADR-002, D4).

- Working memory: the mind gets a small, cue-driven selection, not everything.
- Semantic memory: conclusions attached to a subject (an object, a place or a topic such as
  "stacking"), merged when they repeat, with a count of how often they were confirmed.
- Episodic memory: events with world ticks (inherited), recalled by cue.
- Sleep: facts are rewritten per subject (duplicates merged, contradictions resolved).
Procedural memory (protected proven skills) lives in learned.SkillLibrary.
"""
import json
import re
from pathlib import Path

from .files import write_atomic
from .memory import NativeMemory

MAX_FACTS_PER_SUBJECT = 6
ALWAYS_TOPICS = ("body", "reach", "stacking", "placing", "throwing", "world")


def _words(text):
    return {w for w in re.findall(r"[a-z0-9_.]+", text.lower()) if len(w) > 2}


def _similar(a, b):
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.5


class BrainMemory(NativeMemory):
    def __init__(self, root):
        self.facts_path = Path(root) / "facts.json"  # read first: opening the memory may retire some (RETIRED)
        self.facts = json.loads(self.facts_path.read_text()) if self.facts_path.exists() else {}
        super().__init__(root)

    def _retire_more(self, pattern):
        kept = {subject: [f for f in facts if not pattern.search(f["text"])] for subject, facts in self.facts.items()}
        if kept != self.facts:
            self.facts = kept
            write_atomic(self.facts_path, json.dumps(self.facts, indent=2))

    def save(self):
        super().save()
        write_atomic(self.facts_path, json.dumps(self.facts, indent=2))

    @staticmethod
    def _subject(about):
        return (about or "world").strip().lower()[:40]

    def note(self, text, about="", importance=3, tick=0):
        """Store the episode, and fold the conclusion into semantic memory under its subject."""
        episode = super().note(text, about, importance, tick)
        self._fold(about, text, tick)
        return episode

    def amend(self, text, about="house", tick=0, entities=()):
        """Also correct what it believes about the subject (a house it believes finished broke): the correction counts
        as more confirmed than any belief it corrects, so it is recalled first and never the one evicted, until sleep
        rewrites the subject's beliefs."""
        super().amend(text, about, tick, entities)
        self._fold(about, text, tick, first=True)

    def _fold(self, about, text, tick, first=False):
        subject = self._subject(about)
        facts = self.facts.setdefault(subject, [])
        top = max((f["seen"] for f in facts), default=0) + 1
        for fact in facts:
            if _similar(fact["text"], text):
                fact.update(text=text.strip()[:300], seen=top if first else fact["seen"] + 1, last_tick=tick)
                break
        else:
            facts.append({"text": text.strip()[:300], "seen": top if first else 1, "first_tick": tick, "last_tick": tick})
            if len(facts) > MAX_FACTS_PER_SUBJECT:
                facts.sort(key=lambda f: (f["seen"], f["last_tick"]))
                facts.pop(0)

    def recall_for(self, entities, text, limit=8):
        """Facts about what is in view or named in the cue, plus a few relevant episodes."""
        cues = _words(text) | {e.lower() for e in entities}
        wanted = [s for s in self.facts if s in cues or s in ALWAYS_TOPICS]
        lines = []
        for subject in sorted(wanted, key=lambda s: -max((f["seen"] for f in self.facts[s]), default=0)):
            for fact in sorted(self.facts[subject], key=lambda f: -f["seen"]):
                lines.append(f"{subject}: {fact['text']}" + (f" (confirmed {fact['seen']}x)" if fact["seen"] > 1 else ""))
        return {"facts": lines[:18], "episodes": self.retrieve(entities=entities, text=text, limit=min(limit, 4))}

    def consolidation_input(self):
        return {s: [f["text"] for f in facts] for s, facts in self.facts.items() if facts}

    def apply_consolidation(self, facts_by_subject):
        """Sleep rewrote these subjects' facts: duplicates merged, contradictions resolved."""
        for subject, texts in facts_by_subject.items():
            subject = self._subject(subject)
            old = {f["text"]: f for f in self.facts.get(subject, [])}
            self.facts[subject] = [
                {"text": str(t)[:300], "seen": old.get(t, {}).get("seen", 1), "first_tick": old.get(t, {}).get("first_tick", 0),
                 "last_tick": old.get(t, {}).get("last_tick", 0)}
                for t in texts if str(t).strip()][:MAX_FACTS_PER_SUBJECT]
            if not self.facts[subject]:
                del self.facts[subject]

    def health(self):
        return {**super().health(), "fact_subjects": len(self.facts), "facts": sum(len(v) for v in self.facts.values())}
