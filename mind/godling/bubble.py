"""The thought bubble (ADR-009): what Godling has in mind, pictured over its head as in The Sims, and how it feels.

A second, small model call reads the mind's latest thoughts as they stream in, what the body is doing and what just
happened, and names one thing (a picture the renderer knows) and one feeling (the cloud's tint). The mind's own
reasoning is untouched; this only reads it. The world keeps the two names on Godling (input Think) for the renderer.
"""
import threading
import time
from collections import deque

from .world import WorldError

EVERY = 15  # seconds between readings, when something new has been thought, done or noticed
TAIL = 2400  # characters of the latest reasoning a reading sees

# The pictures the renderer draws (main.lua THOUGHT_THINGS) and what each stands for, for the reader.
THINGS = {
    "coconut": "coconuts, food from the palms", "fish": "fish, catching fish", "cooked_fish": "a cooked fish, a meal",
    "fire": "fire, lighting or keeping one", "log": "logs, timber", "block": "stone blocks, building material",
    "boulder": "the heavy boulders", "axe": "the axe, felling", "hammer": "the hammer, the quarry",
    "spear": "the spear, carving one", "palm": "palm trees", "ladder": "the ladder, climbing",
    "raft": "the wrecked raft", "ball": "the volleyball, its companion", "help": "a HELP sign in the sand",
    "rescue": "being rescued, a ship, going home", "sea": "the sea", "lightning": "the sky's doings: lightning, "
    "falling stones", "tower": "a tower, stacking high", "wall": "a wall", "shelter": "a shelter, a hut, a home",
    "explore": "exploring, seeing more of the island", "night": "the night, the dark, sleep",
}
FEELINGS = ("happy", "proud", "hopeful", "curious", "calm", "determined", "focused", "tired", "lonely", "worried",
            "frustrated", "scared", "hungry", "sad")

SYSTEM = ("You read the thoughts of Godling, a castaway alone on an island, and choose what its thought bubble "
          "shows, as in The Sims: the one thing on its mind right now, as a picture, and how it feels about it.\n"
          "Things (pick exactly one key):\n" + "\n".join(f"- {k}: {v}" for k, v in THINGS.items())
          + "\nFeelings (pick exactly one): " + ", ".join(FEELINGS)
          + '\nReply with JSON only: {"thing": "...", "feeling": "..."}')


class Bubble:
    def __init__(self, world, llm, log=None, every=EVERY):
        self.world = world
        self.llm = llm
        self.log = log or (lambda **kw: None)
        self.every = every
        self.lock = threading.Lock()
        self.thoughts = deque(maxlen=TAIL)  # characters
        self.happened = deque(maxlen=5)
        self.doing = None
        self.fresh = False  # something new since the last reading
        self.shown = None
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="bubble", daemon=True)

    # ---- fed by the mind and the body (any thread) -----------------------------------
    def thought(self, text):
        with self.lock:
            self.thoughts.extend(text)
            self.fresh = True

    def does(self, intention):
        with self.lock:
            self.doing, self.fresh = intention, True

    def happens(self, text):
        with self.lock:
            self.happened.append(text[:200])
            self.fresh = True

    # ---- the reading ---------------------------------------------------------------------
    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.wait(self.every):
            try:
                self.read()
            except Exception as err:  # a missed bubble must never touch the run
                self.log(kind="error", message=f"bubble: {err!r}"[:200])

    def read(self):
        with self.lock:
            if not self.fresh:
                return None
            self.fresh = False
            thoughts, doing, happened = "".join(self.thoughts).strip(), self.doing, list(self.happened)
        snap = self.world.observe()
        body = []
        if snap.hunger is not None:
            body.append(f"{snap.hunger:.0f}% fed, health {snap.health:.0f} of 100")
        held = snap.held()
        body.append(f"holding {held.name}" if held else "hands empty")
        if snap.time_of_day is not None:
            body.append(f"the time is {int(snap.time_of_day):02d}:{int(snap.time_of_day % 1 * 60):02d}")
        user = (f"Its latest thoughts (most recent last):\n...{thoughts[-TAIL:]}\n\n"
                f"What its body is doing: {doing or 'waiting for its next plan'}\n"
                f"Its body: {', '.join(body)}\n"
                + (f"What just happened: {' | '.join(happened)}\n" if happened else ""))
        reply = self.llm.quick_json(SYSTEM, user, purpose="bubble")
        thing, feeling = str(reply.get("thing", "")).strip().lower(), str(reply.get("feeling", "")).strip().lower()
        if thing not in THINGS or feeling not in FEELINGS:
            self.log(kind="bubble", ok=False, reply=str(reply)[:120])
            return None
        try:
            self.world.act("Think", {"thing": thing, "feeling": feeling})
        except WorldError:
            return None
        self.shown = (thing, feeling)
        self.log(kind="bubble", ok=True, thing=thing, feeling=feeling)
        return self.shown
