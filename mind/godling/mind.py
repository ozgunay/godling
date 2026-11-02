"""L3 mind: remembers, reflects, imagines projects and narrates. It thinks about the past and the
future; the skills handle the body.

A decision is split in three so the mind can think while the body moves (ADR-002, D2):
  prepare() builds the prompt in the main thread, think() is only the LLM call (safe in a background
  thread), adopt() applies the reply's side effects (memories, skills, keeps) in the main thread, and
  only if the plan is actually used.
"""
import json
import time
from dataclasses import dataclass

from .learned import SkillError
from .discovery import SIGHT
from .world import CUBE, hdist

ANSWER_SHAPE = {
    "thought": "1-2 sentences: what you notice, remember or wonder (viewers see this)",
    "agenda": [{"intention": "one short line, what you are about to do (shown in chat)",
                "goal": "what you want to exist or happen", "why": "short reason",
                "steps": [{"skill": "a skill name", "args": {"...": "..."}}]}],
    "needs": "what your agenda is still short of, with counts, e.g. '3 logs for the gate lintel' (empty if nothing)",
    "remember": [{"about": "an object name, a place or a topic (e.g. Rock_1, Quarry, stacking)",
                  "text": "a conclusion worth keeping", "importance": "1-5"}],
    "learn": [{"name": "new_skill_name", "params": ["object"], "does": "what it achieves",
               "steps": [{"skill": "a skill", "args": {"...": "$object or a helper"}, "repeat": 1}]}],
    "forget": ["name of a learned skill that does not work"],
    "keep": [{"name": "a name for something you built", "cubes": ["Block_..."]}],
    "release": ["name of a kept structure you are willing to take apart"],
}

TEACHING = """## Teaching yourself skills
You start with only your body's basic moves. When you find a sequence that works, give it a name with
"learn" so you never have to work it out again; a learned skill can be used like any other step. Step
arguments may use your parameters ("$object") and these helpers, worked out at the moment the step runs:
  {"pos": "$object"} -> [x, y, z] centre of that object
  {"top": "$object"} -> [x, y, z] of the top surface of the stack that object is part of
  {"add": [a, b]}    -> add two vectors, e.g. {"add": [{"top": "$object"}, [0, 0.5, 0]]}
  {"x": vector}, {"y": vector}, {"z": vector} -> one coordinate
  {"nearest_free": "cube"} -> the nearest block nobody has claimed; also "stone" (quarried blocks), "log" or "boulder"
A step may have "repeat": n. Example: {"skill": "place_at", "args": {"x": {"x": {"pos": "$o"}}, "y": 3, "z": {"z": {"pos": "$o"}}}}
New skills are "unproven" until one full run succeeds. Fix or forget skills that keep failing."""

AGENDA_RULES = """Plan an agenda: 1-6 projects in order, each with 1-12 steps. While your body works through the agenda
you are already thinking about what comes after it, so give it enough to do: if your body runs out of
work before you finish thinking, it stands still. If a project fails, your body goes on with the next."""
MAX_STEPS = 12
# Measured (smoke s3, 2026-11-01): a planned step cost about as much thinking as it gave body time at the
# old pace, so longer step lists never got ahead of the body; a step that runs a repeating skill does.
# Human-paced hands and walking (ADR-003 O2) made each small step take about two seconds.
BUSY_HINT = ("A small step (walk, pick up, place) keeps your body busy for about two seconds. A step that runs "
             "one of your own skills, which can repeat steps and work out their targets as it goes, keeps your "
             "body busy far longer for the same thought.")

LOOSE_IN_VIEW = 14  # working memory: name the nearest loose things, count the rest


def island_map(snap, discovery=None, half=200, step=10):
    """A small map of the island for the mind (ADR-007): where the beach, the grass and the rock are. It knew only
    coordinates, and walked into the sea and drew lines across the grass looking for the beach (test run c1)."""
    rows = []
    for z in range(half, -half - 1, -step):
        row = []
        for x in range(-half, half + 1, step):
            if discovery is not None and not discovery.knows_ground(x, z):
                row.append("?")
                continue
            top, e = snap.surface(x, z)
            if top is None:
                row.append("~")
            elif e is not None and e.name == "Quarry":
                row.append("Q")
            elif e is not None and e.role == "Wreck":
                row.append("R")
            elif e is not None and e.role == "Mesa":
                row.append("^")
            elif e is not None and e.attrs.get("Surface") == "Sand":
                row.append(".")
            else:
                row.append(",")
        rows.append(f"{z:>5} " + "".join(row))
    rows.append("      " + "".join(("|" if x % 50 == 0 else " ") for x in range(-half, half + 1, step))
                + f"   x from {-half} (left) to {half} (right); z on the left")
    return "\n".join(rows)


def _fmt_pos(p):
    return f"({p[0]:.1f}, {p[2]:.1f})"


def _fmt_pos3(p):
    return f"({p[0]:.1f}, {p[1]:.2f}, {p[2]:.1f})"


def _how_it_feels(snap):
    """The weather on the body, as the body feels it (ADR-010): rain, being soaked, the cold, and what shelters it."""
    parts = []
    if snap.rain >= 0.3:
        parts.append("It is raining" + (", and you are out in it: it slows your walking" if snap.in_rain else ""))
    if snap.wet >= 15:
        parts.append(f"You are {'soaked through' if snap.wet >= 70 else 'wet'} ({snap.wet:.0f}%)")
    if snap.cold:
        parts.append("You are cold, and it is wearing your health down")
    if snap.sheltered:
        parts.append("You stand under a roof" + (" with walls around you" if snap.sheltered == "enclosed" else ""))
    return ". ".join(parts) + "." if parts else ""


@dataclass
class _Seen:
    """A loose thing as the mind knows it: where it is, or where it was last seen (`old`)."""
    name: str
    pos: tuple
    old: bool


class Mind:
    def __init__(self, llm, memory, soul, skills, library, name="Godling", log=None, agenda=True, discovery=None):
        self.llm = llm
        self.discovery = discovery  # what Godling has seen of the island; None: it knows everything (ADR-008)
        self.memory = memory
        self.soul = soul
        self.skills = skills
        self.library = library
        self.name = name
        self.log = log or (lambda **kw: None)
        self.agenda = agenda
        self.started = time.time()
        self.last_outcome = "You just woke up."
        self.failures = []  # recent failed goals, to break loops
        self.notes = []  # feedback for the next decision (rejected skills, refused forgets)
        self.think_s = None  # running estimate of how long a plan takes to think up

    def _knows(self, thing):
        return self.discovery is None or self.discovery.knows(thing)

    def _sees(self, thing):
        return self.discovery is None or thing.name in self.discovery.visible

    # ---- prompts ----------------------------------------------------------------------
    def system_prompt(self, snap):
        body = "\n".join(f"- {name}({', '.join(f'{k}: {v}' for k, v in args.items())}): {does}"
                         for name, (args, does) in self.skills.offered.items())
        learned = self.library.describe() or "(none yet)"
        marks = [e for e in snap.landmarks() if self._knows(e)]
        lines = [f"- {e.name}: centre {_fmt_pos(e.pos)}, top at height {e.top:.1f}, footprint {e.size[0]:.0f} x {e.size[2]:.0f}"
                 for e in marks if e.role != "Tree"]
        trees = sorted((e for e in marks if e.role == "Tree"), key=lambda e: (e.name.split("_")[0], int(e.name.split("_")[-1])
                                                                              if e.name.split("_")[-1].isdigit() else 0))
        for kind in sorted({e.name.split("_")[0] for e in trees}):  # dozens of trees and palms: one line each kind
            group = [e for e in trees if e.name.split("_")[0] == kind]
            lines.append(f"- {kind}s ({len(group)}, about {group[0].top:.0f} tall): "
                         + ", ".join(f"{e.name} ({e.pos[0]:.0f}, {e.pos[2]:.0f})" for e in group))
        landmarks = "\n".join(lines)
        shape = ANSWER_SHAPE if self.agenda else {
            **{k: v for k, v in ANSWER_SHAPE.items() if k != "agenda"}, "intention": ANSWER_SHAPE["agenda"][0]["intention"],
            "project": {k: v for k, v in ANSWER_SHAPE["agenda"][0].items() if k != "intention"}}
        plan_rule = AGENDA_RULES if self.agenda else "Plan one project with 1-8 steps."
        return f"""{self.soul}

## How you exist
You are {self.name}. You live on an island in a 3D physics world. You decide WHAT to do; your
body carries it out. Think about your past (what happened, what it means) and your future (what you
want to make next). You do not know how this world's physics works yet: find out by trying things,
watch what happens, and write down what you learn.

What your body knows about itself: it is 2 units wide and 5 tall, reaches things a few units away and
walks around obstacles. Its legs step up onto anything one block high and hop down a drop of one block;
anything higher needs a ladder that stands against something. It walks on anything flat it gets onto.
You can build. A building block is 2.5 units on every side, half your height, and whatever you set down
settles into a grid of cells 2.5 apart. Things you can build with: stone blocks, which a hammer breaks
off the quarry; logs, beams three blocks long and one thick, which an axe fells from trees (they grow back) and
which sometimes wash up on the beach; boulders, which are very heavy. The ladder is three blocks tall.
Pieces you set down can be turned a quarter round or stood on end, and fastened in place, like mortar.
Your body grows hungry. With nothing left in you, you lose health, and with no health you faint. Lightning, or a
stone falling from the sky, hurts you if you are close when it strikes. Fed at least half full, you heal. You eat what
you hold. Coconuts grow on the palms; fish swim in the shallows off the beach. Cooked fish fills you far more than raw.
Fire is hard to make: wood rubbed hard and long against wood grows hot, and something dry and fine beside it may
catch. Rain puts fires out, and nothing catches while it rains or while the wood is still damp after it.
Days turn into nights; nights are dark and cold. The weather turns: showers, spells of rain that last for days,
thunderstorms, fog some mornings. Rain soaks you and slows your walking. Being cold wears your health down and stops
you healing. A roof over your head keeps the rain off; walls around you with a roof over you, or a fire close by,
keep the cold off.
Now and then the ground shakes. Loose pieces can fall; fastened pieces hold where they are, and a wide base stands
better than a thin one. When the ground rumbles, your body braces by itself until it is still.
Everything else about the world, and how to build well, is yours to discover.

## Your body's moves
{body}

## Skills you taught yourself
{learned}

{TEACHING}

## Fixed landmarks
{landmarks}

## The island as far as you have seen it (north up; one character is 10 units; ~ sea, . sand, , grass, ^ rock,
Q quarry, R raft, ? not seen yet). You know only what you have been near: walk to see more.
{island_map(snap, self.discovery)}

## How to answer
{plan_rule}
Reply with ONE json object shaped like this (omit empty lists):
{json.dumps(shape, indent=1)}
Rules: only skills listed above (body moves or your own), numbers for coordinates. Remember conclusions,
not play-by-play; attach each to what it is about. Prefer projects whose result others can see. If
something failed, change your approach instead of repeating it. When something you noticed (a shadow, a
stone from the sky, damage, a visitor, the weather) changes what you do, name it in a few words in your
thought and in that project's intention."""

    def situation(self, snap, events, chat, doing=None):
        held = snap.held()
        protected = self.memory.protected_cubes()
        seen = self.discovery.seen if self.discovery is not None else None
        known_stacks = [(xz, names) for xz, names in snap.stacks() if seen is None or any(n in seen for n in names)]
        stacked = {n for _, names in known_stacks for n in names}
        if seen is None:
            loose = [_Seen(e.name, e.pos, False) for e in snap.movables() if e.name not in stacked and e is not held]
        else:  # what is in sight as it is now, the rest where it was last seen (ADR-008)
            live = snap.entities
            loose = [_Seen(n, live[n].pos if n in self.discovery.visible and n in live else p,
                           n not in self.discovery.visible) for n, p in seen.items()
                     if n not in stacked and not (held and n == held.name)]
        loose.sort(key=lambda e: hdist(e.pos, snap.me))
        loose_txt = ", ".join(f"{e.name} {_fmt_pos3(e.pos)}" + (" (last seen there)" if e.old else "")
                              + (" [kept]" if e.name in protected else "") for e in loose[:LOOSE_IN_VIEW])
        if len(loose) > LOOSE_IN_VIEW:
            loose_txt += f", and {len(loose) - LOOSE_IN_VIEW} more further away"
        stacks = "; ".join(f"{len(names)}-high stack at {xz}: {', '.join(names)}" for xz, names in known_stacks) or "none"
        kept = "; ".join(f"{title} at {s['where']} ({len(s['cubes'])} cubes)" for title, s in self.memory.state["structures"].items()) or "none"
        others = ", ".join(f"{n} at {_fmt_pos(p)}" for n, p in snap.others) or "nobody else is here"
        cue_entities = [e.name for e in loose[:LOOSE_IN_VIEW]] + [n for _, names in known_stacks for n in names[-1:]]
        cue_entities += [e.name for e in snap.landmarks() if hdist(e.pos, snap.me) < 25 and self._knows(e)]
        cue_entities += [n for ev in events for n in ev.get("entities", [])]
        cue_text = self.last_outcome + " " + " ".join(p["goal"] for p in doing or [])
        recalled = self.memory.recall_for(cue_entities, cue_text)
        lines = [
            f"Awake for {int((time.time() - self.started) / 60)} minutes. World tick {snap.tick}.",
            f"You are at {_fmt_pos(snap.me)}, holding {held.name if held else 'nothing'}.",
            *([f"You are {snap.hunger:.0f}% fed, with health {snap.health:.0f} of 100"
               + (f"; you have fainted from hunger {snap.faints} time{'s' if snap.faints != 1 else ''}" if snap.faints else "")
               + "."] if snap.hunger is not None else []),
            *([_how_it_feels(snap)] if _how_it_feels(snap) else []),
            f"Others: {others}.",
            f"Loose objects (nearest first): {loose_txt or 'none'}.",
            f"Stacks: {stacks}.",
            f"Things you decided to keep: {kept}.",
            f"What just happened: {self.last_outcome}",
        ]
        if snap.time_of_day is not None:
            h = snap.time_of_day
            part = ("night" if h < 5 or h >= 21 else "dawn" if h < 7 else "morning" if h < 11 else "midday" if h < 14
                    else "afternoon" if h < 18 else "evening")
            lines.insert(1, f"It is {int(h):02d}:{int((h % 1) * 60):02d}, {part}.")
        fires = [e for e in snap.entities.values() if e.name.startswith("Fire_") and self._sees(e)]
        if fires:
            lines.insert(4, "Fires burning: " + ", ".join(f"{e.name} {_fmt_pos(e.pos)}" for e in fires) + ".")
        fish = sorted((e for e in snap.entities.values() if e.name.startswith("Fish_")), key=lambda e: hdist(e.pos, snap.me))
        if fish and hdist(fish[0].pos, snap.me) < SIGHT:  # fish are not things to pick up, so say where they swim
            lines.insert(4, "Fish swimming in the shallows nearest you: "
                         + ", ".join(f"{e.name} {_fmt_pos(e.pos)}" for e in fish[:5] if hdist(e.pos, snap.me) < SIGHT) + ".")
        strokes = sorted((e for e in snap.entities.values() if e.name.startswith("Mark_") and e.attrs.get("Stroke")),
                         key=lambda e: int(e.name.split("_")[1]))
        if strokes:  # what it wrote in the sand, so it can read it back
            shown = ["({}, {})-({}, {})".format(*e.attrs["Stroke"].split(",")) for e in strokes[-40:]]
            lines.insert(6, f"Lines you drew in the sand ({len(strokes)}, oldest first): " + "; ".join(shown)
                         + (f" (and {len(strokes) - 40} older)" if len(strokes) > 40 else "") + ".")
        if doing:
            plan = "; ".join(f"{i}) {p['goal']}" for i, p in enumerate(doing, 1))
            lines.append(f"Right now your body is carrying out this agenda: {plan}. "
                         "Plan what comes AFTER all of it, assuming it succeeds.")
        if self.agenda and self.think_s:
            lines.append(f"You take about {self.think_s:.0f}s to think up a plan. {BUSY_HINT}")
        if self.notes:
            lines.append("Notes: " + " ".join(self.notes))
        if events:
            lines.append("You noticed: " + "; ".join(e["text"] for e in events[-8:]))
        if chat:
            lines.append("You heard: " + " | ".join(f"{m.get('agent_name', '?')}: {m.get('content', '')[:200]}" for m in chat[-6:]))
        if len(self.failures) >= 2:
            lines.append(f"Recent failures: {' | '.join(self.failures[-3:])}. Try something different.")
        if recalled["facts"]:
            lines.append("What you know (your own conclusions):\n" + "\n".join(f"- {f}" for f in recalled["facts"]))
        if recalled["episodes"]:
            lines.append("Memories that may matter:\n" + "\n".join(f"- [tick {m['tick']}] {m['text']}" for m in recalled["episodes"]))
        if self.memory.state["digest"]:
            lines.append("Your story so far:\n" + self.memory.state["digest"])
        intentions = self.memory.open_intentions()
        if intentions:
            lines.append("Your intentions for later: " + "; ".join(i["text"] for i in intentions))
        return "\n".join(lines)

    # ---- thinking ---------------------------------------------------------------------
    def prepare(self, snap, events, chat, doing=None):
        """Main thread: build the prompt (reads memory). Returns what think() needs."""
        prepared = {"system": self.system_prompt(snap), "user": self.situation(snap, events, chat, doing),
                    "tick": snap.tick, "assumes": " -> ".join(p["goal"] for p in doing) if doing else None}
        self.notes = []  # delivered in this prompt
        return prepared

    def think(self, prepared, on_reasoning=None):
        """Any thread: the LLM call only. `on_reasoning` receives the reasoning in pieces as it streams in."""
        started = time.time()
        reply = self.llm.complete_json(prepared["system"], prepared["user"], purpose="decide", on_reasoning=on_reasoning)
        return {"reply": reply, "prepared": prepared, "seconds": round(time.time() - started, 2)}

    def adopt(self, thought, snap):
        """Main thread: apply the reply's side effects and return the decision (a list of projects)."""
        reply, tick = thought["reply"], snap.tick
        self.think_s = thought["seconds"] if self.think_s is None else (self.think_s + thought["seconds"]) / 2
        for name in reply.get("forget") or []:
            refusal = self.library.forget(str(name))
            if refusal:
                self.notes.append(refusal)
        taught = []
        for spec in reply.get("learn") or []:
            if not isinstance(spec, dict):
                continue
            try:
                taught.append(self.library.define(spec, tick=tick))
            except (SkillError, TypeError, ValueError) as err:
                self.notes.append(f"Your attempt to learn '{spec.get('name')}' was rejected: {err}.")
        raw = reply.get("agenda") if isinstance(reply.get("agenda"), list) else [
            {**(reply.get("project") or {}), "intention": reply.get("intention", "")}]
        known = set(self.skills.offered) | set(self.library.skills)
        projects = []
        for item in raw[:6]:
            if not isinstance(item, dict):
                continue
            steps = [{"skill": s["skill"], "args": s.get("args", {})} for s in (item.get("steps") or [])[:MAX_STEPS]
                     if isinstance(s, dict) and s.get("skill") in known and isinstance(s.get("args", {}), dict)]
            projects.append({"intention": str(item.get("intention", ""))[:200], "goal": str(item.get("goal", ""))[:200],
                             "why": str(item.get("why", ""))[:200], "steps": steps})
        for item in reply.get("remember") or []:
            if isinstance(item, dict) and item.get("text"):
                self.memory.note(str(item["text"]), about=str(item.get("about", "")), tick=tick,
                                 importance=int(str(item.get("importance", 3))[:1] or 3))
        for name in reply.get("release") or []:
            self.memory.release_structure(str(name))
        for item in reply.get("keep") or []:
            cubes = [c for c in item.get("cubes", []) if c in snap.entities]
            if item.get("name") and cubes:
                # A structure is one physical cluster; drop names that are lying somewhere else.
                where = snap.entities[cubes[0]].pos
                cubes = [c for c in cubes if hdist(snap.entities[c].pos, where) < 6 * CUBE]
                self.memory.add_structure(str(item["name"]), cubes, (where[0], where[2]),
                                          {c: snap.entities[c].pos for c in cubes})
        self.memory.save()
        self.memory.flush()
        # What the agenda is short of: one line for the viewers' side panel, so they can tell what a gift would mean.
        decision = {"thought": str(reply.get("thought", ""))[:400], "projects": projects,
                    "needs": str(reply.get("needs") or "")[:160], "learned": taught,
                    "think_seconds": thought["seconds"], "assumed": thought["prepared"]["assumes"],
                    "plan": thought["prepared"].get("plan")}  # links to its reasoning in thinking.jsonl
        self.log(kind="decision", **decision)
        return decision

    def agenda_feedback(self, busy_s, think_s):
        """Let the mind calibrate how much work to plan: how long its last agenda really kept the body busy."""
        if busy_s < think_s * 0.9:
            self.notes.append(f"Your last agenda kept your body busy for {busy_s:.0f}s, but you think for about "
                              f"{think_s:.0f}s per plan, so your body stood still.")

    def decide(self, snap, events, chat):
        """The old one-project-at-a-time decision, used with --no-agenda."""
        return self.adopt(self.think(self.prepare(snap, events, chat)), snap)

    def record_outcome(self, project, results, snap):
        lines = [f"{r.skill}: {'ok' if r.ok else 'FAILED'} - {r.summary}" for r in results]
        ok = bool(results) and all(r.ok for r in results)
        self.last_outcome = f"Project '{project['goal']}' " + ("succeeded. " if ok else "did not finish. ") + " / ".join(lines)
        if not ok and project["goal"]:
            self.failures = (self.failures + [f"{project['goal']}: {lines[-1] if lines else 'no steps'}"])[-5:]
        elif ok:
            self.failures = []
        entities = {v for r in results for v in r.facts.values() if isinstance(v, str)}
        entities |= {c for r in results for c in r.facts.get("cubes", [])}
        height = max((r.facts.get("height", 0) for r in results), default=0)
        importance = 4 if (height >= 5 or any(r.facts.get("toppled") for r in results)) else (3 if ok else 2)
        self.memory.store_experience(self.last_outcome, kind="project", tick=snap.tick, entities=entities, importance=importance)
        for r in results:
            if r.skill == "build_tower" and len(r.facts.get("cubes", [])) >= 3:
                where = snap.entities.get(r.facts["cubes"][0])
                cubes = [c for c in r.facts["cubes"] if c in snap.entities]
                if where and cubes:
                    self.memory.add_structure(f"tower of {len(cubes)} at {_fmt_pos(where.pos)}", cubes,
                                              (where.pos[0], where.pos[2]), {c: snap.entities[c].pos for c in cubes})
        self.memory.save()
        self.memory.flush()
        return ok

    def sleep(self, snap):
        """Consolidate: episodes -> digest and intentions; facts rewritten per subject (merge, resolve)."""
        episodes = self.memory.reflect_input()
        if not episodes:
            return None
        listing = "\n".join(f"- [tick {e['tick']}] ({e['kind']}, importance {e['importance']}) {e['text']}" for e in episodes[-120:])
        facts = self.memory.consolidation_input()
        facts_txt = ""
        if facts:
            facts_txt = ("\nWhat you currently believe, by subject:\n"
                         + "\n".join(f"- {s}: " + " | ".join(t) for s, t in facts.items())
                         + '\n\nAlso rewrite your beliefs: "facts": {"subject": ["at most 3 clear, non-contradictory '
                           'conclusions"]} for every subject that needs merging or correcting. Drop beliefs '
                           'that experience proved wrong.')
        user = f"""It is time to sleep and consolidate your memory.
Your story so far:
{self.memory.state['digest'] or '(nothing yet; this is your first sleep)'}

What happened since you last slept:
{listing}
{facts_txt}

Reply with ONE json object: {{"digest": "your updated story so far, at most 12 sentences, keep what matters
and drop noise", "lessons": [{{"about": "subject", "text": "durable lesson"}}], "intentions": ["up to 5 things
you want to make or try next, concrete"], "dream": "one sentence a viewer could read about tonight's sleep"{', "facts": {...}' if facts else ''}}}"""
        reply = self.llm.complete_json(f"{self.soul}\n\nYou are {self.name}.", user, purpose="sleep")
        if isinstance(reply.get("facts"), dict):
            self.memory.apply_consolidation(reply["facts"])
        for lesson in reply.get("lessons") or []:
            about, text = (lesson.get("about", ""), lesson.get("text", "")) if isinstance(lesson, dict) else ("", str(lesson))
            if text:
                self.memory.note(str(text), about=str(about), tick=snap.tick, importance=4)
        self.memory.finish_sleep(str(reply.get("digest", "")), [str(i) for i in reply.get("intentions") or []])
        self.memory.save()
        self.memory.flush()
        self.log(kind="sleep", digest=self.memory.state["digest"], intentions=self.memory.state["intentions"],
                 dream=str(reply.get("dream", ""))[:300], facts_rewritten=len(reply.get("facts") or {}))
        return reply
