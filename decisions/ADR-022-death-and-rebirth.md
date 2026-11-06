# ADR-022: Death and rebirth, and learning from them

Date: 2026-11-06. Status: built and tested (world, mind, screen, renderer); checked on a local island in WSL. Not yet in
a live run.

## Why
At no health Godling fainted: it woke by the raft with 30 health and half fed, and the mind was told only "you have
fainted from hunger N times", whatever the cause. A faint cost little and taught nothing: the mind barely noticed it.
The user asked for real death: at zero health Godling dies, is born again at the start whole, knows that it died, and
learns to avoid it. With the Storm (ADR-023) able to leave Godling at half a heart, a death that follows (the cold of a
night out after a strike) is exactly the chain it should learn from.

## Decisions
The user chose these on 2026-11-06, with the guards proposed so that death teaches the right thing.
1. **At no health Godling dies.** What it holds drops where it fell. The body falls (the Stagger clip) and lies there
   30 seconds (`DEAD_SECONDS`), taking nothing in: inputs are refused ("Dead"), it is not hurt, not shaken by a quake,
   and its hunger stands still. Existing climbs, turns, braces and knock-downs stop; shore and trapped-body rescues
   leave the corpse where it died. Rebirth releases the body to move again.
2. **Born again at the start spot, whole but half fed.** Health 100, hunger 50: dying is never a meal (a guard: with a
   full belly a starving mind could learn that dying feeds it). It rises (WakeUp) in a short glow.
3. **The cost:** the time dead, the walk back to what it carried, a "Deaths" count on the screen, and a death mark (with
   its cause) on the replay timeline.
4. **The mind learns by itself.** Nothing tells it the lesson. Born again, it gets a death report, facts only: the cause,
   its health over the last minutes (one look every 10 s, kept 10 minutes), how it was at the last look (night, cold,
   soaked, in the rain, under a roof, in its house, by a fire), what it was doing, and what it noticed. It writes one to
   three lessons, kept at the highest importance (5, recalled first whenever the same danger shows), and the next plan
   hears of the death. Its basic facts now say plainly: with no health you die; dying is a failure.
5. **No thinking while dead.** The mind makes no DeepSeek calls while the body lies dead, and a plan thought up for the
   living body is dropped.
6. **Mercy follows death.** No disaster while Godling is weak (health under 30) or within 15 minutes of a death.

## How
- **World** (`main.lua` DEATH, a closure in place of `faint`): `death.die`, `death.tick` (from the survival tick), `rise`,
  `death.is`, `death.since`. The body carries `Dead`, `DeadFor` (seconds left), `DiedOf` (Hunger, Cold, HungerAndCold,
  Lightning, Meteor; later Storm and Sea), `DiedAt` and `Deaths`; the Clock mirrors them for the screen.
- **Save:** a body saved while dead comes back born again at the start spot. A starving body is saved starving (`0` is
  a value: before, an empty belly was saved full). Its death count, cause and coordinates survive the restart too.
- **Mind:** `Attention` keeps the trail and the noticed events, freezes them at death, raises "You died of ..." (salience
  5) and notes the rebirth; `live_through_death` (run_godling.py) waits, then `Mind.reflect_on_death`. Log kinds "dead"
  and "death" (the latter on the replay tracks, with the cause and the feeling). A death is latched even if a slow
  model call spans the whole dead interval; its old plan is discarded before adoption. Thought-bubble calls also
  wait until the body is alive, and discard replies that cross a death. Successful reflection is acknowledged in
  saved memory, so a restart learns from an unreflected death without repeating a completed reflection.
- **Screen:** "Died of hunger · back in 23 s" while dead, and "N deaths". The timeline marks `death` with its cause.
- **Renderer** (`deathlook.js`): the body holds the fall while `Dead`, fades over its last 3 s on its own copies of the
  model's materials, and comes back in a pale column of light with a ring at its feet. `models.js` now plays the first
  gesture of a body first seen before it ever gestured (before, a body's first fall could be skipped), and reconstructs
  the held fall when a page first sees an already dead body. Fading and rebirth light follow replay time, including
  pauses and seeks. Fading materials keep the renderer's lighting setup and release their copies when no longer used.

## Measure
Across runs: deaths per hour, by cause (`DIED` lines in world.log, `death` marks, `kind: "death"` in the mind's log). If
the learning works, deaths from the same cause should fall within a run, and the lessons should show in its plans.
