"""Hindsight as Godling's memory engine (ADR-002, D4 arm B).

Hindsight (vectorize-io, MIT) extracts facts and entities from what we retain (with DeepSeek),
consolidates them into observations in the background, and recalls them with semantic + keyword +
graph + temporal search and a local reranker. Recall needs no LLM call.

Local state that is not "memory" in Hindsight's sense (kept structures, intentions, digest) stays in
the native store we inherit. If Hindsight fails, recall falls back to the native episodes.
"""
import time

from .memory import NativeMemory


def _get(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


class HindsightMemory(NativeMemory):
    def __init__(self, root, base_url, bank_id, log=None):
        super().__init__(root)
        from hindsight_client import Hindsight  # only needed for this arm (separate venv)

        self.client = Hindsight(base_url=base_url, timeout=30.0)
        self.bank = bank_id
        self.log = log or (lambda **kw: None)
        self.pending = []
        try:
            self.client.create_bank(bank_id=bank_id, name="Godling",
                                    mission="Remember what Godling, a builder living alone on an island, "
                                            "experienced, tried and learned about its world and itself.")
        except Exception as err:  # the bank may already exist on a resumed run
            self.log(kind="memory", text=f"hindsight create_bank: {err!r}"[:200])

    # ---- writes: buffered, then retained in one batch per project ----------------------
    def store_experience(self, text, kind="event", tick=0, entities=(), importance=2):
        episode = super().store_experience(text, kind, tick, entities, importance)
        about = ", ".join(sorted(set(entities))[:6])
        self.pending.append({"content": text.strip()[:1200],
                             "context": f"{kind} at world tick {tick}" + (f", about {about}" if about else "")})
        return episode

    def flush(self):
        if not self.pending:
            return
        items, self.pending = self.pending, []
        started = time.time()
        try:
            self.client.retain_batch(bank_id=self.bank, items=items, retain_async=True)
            self.log(kind="memory", op="retain", items=len(items), seconds=round(time.time() - started, 2))
        except Exception as err:
            self.log(kind="error", message=f"hindsight retain failed ({len(items)} items): {err!r}"[:300])

    # ---- reads: one recall per decision, no LLM -----------------------------------------
    def recall_for(self, entities, text, limit=8):
        query = (text[:600] + " | in view: " + ", ".join(list(entities)[:12])).strip()
        started = time.time()
        try:
            response = self.client.recall(bank_id=self.bank, query=query, budget="low", max_tokens=1500,
                                          types=["observation", "world", "experience"], prefer_observations=True)
        except Exception as err:
            self.log(kind="error", message=f"hindsight recall failed, using native: {err!r}"[:300])
            return super().recall_for(entities, text, limit)
        results = _get(response, "results", []) or []
        facts, episodes = [], []
        for item in results:
            words = (_get(item, "text") or "").strip()
            if not words:
                continue
            if _get(item, "type") == "experience":
                episodes.append({"tick": "?", "text": words})
            else:
                facts.append(words)
        self.log(kind="memory", op="recall", facts=len(facts), episodes=len(episodes),
                 seconds=round(time.time() - started, 2))
        return {"facts": facts[:18], "episodes": episodes[:4]}

    def health(self):
        return {**super().health(), "engine": "hindsight", "bank": self.bank}
