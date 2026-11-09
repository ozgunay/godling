# ADR-027: A house's site is kept clear, and the body carries what it holds off a tangled site

Date: 2026-11-09. Status: built and tested in the mind's suite. Not yet tested in a live run.

## Why
This comes from the live run from 2026-11-08 22:10 to 2026-11-09 07:50 UTC (9.6 hours). The investigation of that run
found that in its last hour, 89 of the 95 failures came from the body. Godling knew that its site was choked: its
digest says "Loose logs … pen me in", and 13 of its plans were about clearing the site. The body defeated it in four
ways. The counts below are recounted from `mind/log.jsonl`, where each step that failed counts once.
1. **The hands-full reflex filled the site.** To free its hands, `_set_down_nearby` tries 32 spots 3.5 to 7.5 from the
   body, the farthest from the target first. It kept only the house's room, doorway and way out clear (ADR-019). Over
   the run it set 29 things down on the site of the house being built: 21 logs, 4 axes, 3 spears and a block. Of the
   logs, 20 went on the ground a cell round the walls and one across a wall. (The investigation counted 47 with a
   wider measure. Measured by the footprint on the walls and the strip a cell round them, it is 29.) On the stand-in
   island, the reflex laid a log at (-90.0, -12.5), along the outside of the north wall.
2. **A stray log became part of the house.** `house.plan` counted as the house's own any piece with a part in a wall
   cell below the roof. Log_6 lay along z with its north end in the south-west corner. `pick_up` said "Log_6 is part
   of your house at (-90.0, -20.0), which you are building; move the house or give it up first", while `put_down` in
   that corner said "(-92.5, -22.5) is occupied by Log_6". At 07:49, three of the ten pieces kept as the house were
   strays lying across a wall cell (Log_6, Log_7 and Log_13), and the house's "in the way" list was empty. Its next
   step counted the stray as wall: "(-92.5, -22.5) stands 2.5".
3. **A log in the hands jammed everything.** With no spot in reach, `pick_up` failed and the hands stayed full. Godling
   held Log_7 from 07:11:00 to 07:19:30, through 29 failed steps. Its wall skill `upright_log_at` (proven, used 283
   times) starts with `nearest_free`, which left out the log in its hands. So every wall step reached for another log
   and failed.
4. **The mind could not see what blocked it.** The house's "in the way" covered only its room, doorway and way out.
   31 failed steps said only "stuck N units short of (x, z)": a way round was known, and the body snagged on the way.
   `nearest_free` did not ask whether a piece could be reached, and picked the same unreachable log five times.

On the stand-in island, the pieces round the house at 07:49 give back the run's own failures. From the room, the
result was "stuck 5.6 units short of (-102.0, -12.5)". From the west side it was "hands are full: holding Log_held,
and there is no clear spot nearby to set it down outside your house's room, doorway and way out".

## Decision (the owner's standing preference)
**Checks in the body that refuse and give the reason, as ADR-025 does.** They are not rules in the prompt, and nothing
that deepseek-flash must learn, since it has not learnt such things across runs (ADR-019, ADR-025). The pattern comes
from colony games, where a stockpile is kept and work is hauled. A blueprint's cells stay clear, and so does the spot
its builder works from. What lies on a site is hauled off to clear ground before the work goes on, as RimWorld hauls
away what blocks a blueprint. The mind still decides where to build, in what order, and from what.

### a. Setting a piece down keeps the site clear
The site (`house.site_of`) is the house's room, its doorway, the way out of the doorway, and the strip of ground a
cell wide round its walls and doorway, where the body stands to build them. `memory.reserved_cells` now gives each of
these cells with what it is. The body's wiring is unchanged (`Skills(reserved=...)`, and a plain set of cells still
works). Every set-down is checked: the reflex, `put_down` and `place_at`, before the body walks anywhere. One is refused
when the piece, as it would lie, reaches into the site below the roof line (`house.WALL_LINE`, an underside lower than
6.25 above the floor, which is the walls' first three courses). The wall cells themselves take only a piece that stays
in them: a block, a log stood on end, or a log along the wall's line.
- "(-95.0, -15.0) is beside your house's walls, on the ground a cell wide round them where you stand to build (only a
  block on its own, as a step, goes there). Your hands keep the site clear: a piece goes in a wall along its line, or
  off the site"
- "(-92.5, -20.0) is across your house's wall at (-92.5, -20.0): Log_1 there would stick out of the walls' line, into
  (-95.0, -20.0) beside the walls and (-90.0, -20.0) in the room. Your hands keep the site clear: …"
- "… is in your house's room", "… in your house's doorway", "… in the way out of your house's doorway".

What the rule leaves alone:
- **The roof.** A piece whose underside is at the roof line or higher is laid over the walls and reaches out over the
  strip, as the house's roof logs do.
- **A ladder set down on purpose.** It stands against a wall, on the strip. ADR-025 governs ladders.
- **A block on its own, set down on purpose on the ground in the strip, as a step.** The house's roof step says to set
  the roof "from a step one block high outside the walls". Taking a stone off a wall's top reaches only from a step
  one cell out: from two cells out it is 6.22 from the body's centre, past the 6.0 reach. It is in the way, so the body
  may lift it, but the house's next step does not name it. The reflex never sets anything on the site.
- **The reflex that lifts a piece aside to get out of a pen,** because it puts the piece back where it was, and
  **`stack_on`** (offered only with `--gifted-skills`), as in ADR-025.

The mind is told this as a fact about its body, next to the house rule (`mind.SITE_RULE`).

### b. Carry it off instead of failing
When none of the reflex's spots will do, the body carries what it holds to the nearest clear floor beyond the site, and
says where it went. It looks up to 30 away, and of the 12 nearest spots it takes the one nearest by the way there:
"picked up Log_105 (first carried Log_held off your house's site and set it down at (-85.0, 1.37, -27.5), to free your
hands)". Penned in, it heads for the nearest spot, and the pen reflex lifts a way out first. That reflex used to rest
what the hands held on the nearest side of the pen. It now rests it first on a side low enough to take it back from
outside: rested on Log_9, three blocks high, the log lay out of reach and stayed up there. With nothing clear within 30,
the hands stay full and `pick_up` says "there is no clear floor near enough to set it down off your house's site".

`nearest_free` returns the piece in the hands when it is of the kind asked for. So `upright_log_at` goes on with the
log it holds.

Fixed on the way: `put_down` looked for ground before it snapped the spot to the grid. At the edge of the sand, the
snapped cell could be over the sea, and the reflex crashed ("bad arguments: max() iterable argument is empty").

### c. A stray piece in a wall cell is in the way, not the house's own
In `house.plan`, a piece in a wall cell with its underside below the roof line counts as one of the wall's courses
only when all of its cells are wall cells. Otherwise it is in the way. It is not kept, the body may lift it, it is
listed among the loose objects, and it does not count as the wall standing there. What lies on the strip is in the way
too. That also frees Log_12, which `keep_builds` had kept as part of a build because it touched the walls: what is in
the house's way outranks a build (`memory.built_into`, `memory.protected_cubes`). A house that stands has nothing in
its way. Log_94, lying along the north wall wholly in its cells, stays the house's own. So does an upright log in a
wall.

**This is a move toward guided construction.** The house's next step now names what lies across a wall and what lies
on the strip:
- "(-92.5, -22.5) stands 0.0 (Log_6 lies across it, out of the walls' line)"
- "…; lying on the ground a cell round the walls, where you stand to build them: Log_12 (-97.5, -15.0),
  Log_98 (-95.0, -25.0)"

The words state facts about the site, and give no instruction. The next step already named what fills the room or the
doorway (ADR-019). Lone blocks on the strip, which are steps, are not named.

### d. The body names what blocks the way
When a walk with a way round gets stuck, it now says what stopped it: what presses on the body, and what lies across
the way ahead ("stuck 20.0 units short of (0.0, 20.0); snagged by Log_99"). That includes the piece being walked up
to, because `pick_up`'s route leaves its target out of what it goes round. With no way left open, the walk gives the
existing "no way round" account. `nearest_free` takes the first of the six nearest pieces that the body can walk to
(on its own floor, going round everything). If it can reach none of them, it takes the nearest, and `pick_up` says why.
These searches are bounded (`NEAR_SEARCH`, a square some 70 across) so that they do not cover the whole island.

## Checked
- `mind/tests/test_site_clear.py`, 12 tests, on the stand-in island with the body and the mind wired as in
  `run_godling.py`. Run against the code from before this change, 11 of them fail with the run's own failures:
  - The stray is the house's own, and the 07:49 site's "in the way" list is empty.
  - The reflex lays the log (or stone) on the strip.
  - `put_down` sets a log on the strip.
  - From the room at 07:49 the result is "stuck 5.6 units short of (-102.0, -12.5)", and from the west side "hands are
    full … no clear spot nearby".
  - The room with walls one course high crashes on the sand's edge.
  - `nearest_free` reaches past the held log, and picks the log in the pit.
  - A stuck walk names nothing.

  The twelfth test starts from the way out at 07:49, where the old body got there too. It is a guard.
- Each case at 07:49 now ends with Log_105 in the hands and the held log off the site:
  - From the room, the body carries the log out by the doorway.
  - From the way out, it sets the log down in reach, beyond the site.
  - From the west side it is boxed in by Log_13, Log_98, Log_9 and Stone_2. It lifts Log_13 aside, steps out, sets it
    back, and carries the log off.
- The roof check still works under the rule: a roof log is set from a step a block high and the body steps back down.
- `test_house_recovery.py` now expects the new wording for "hands are full" and the site map from `reserved_cells`.
  `test_mind.py` now expects an empty map rather than an empty set.
- Timing on a crowded stand-in, with 500 terrain parts and 300 loose things: the boxed-in pick-up, carry included, took
  0.36 s of computing. `nearest_free`, passing over three logs in a pit, took 0.03 s.
- Every suite passes locally: the mind's (369 tests) and the world script's, which this change does not touch. CI is
  not running at the moment.

## Not checked
- Not yet in a live run.
- Whether deepseek-flash clears the strays and the strip once they are named and the body lets it, or builds on them.
- The world is unchanged. A viewer's dropped log, or a piece thrown onto the site by a blast, still lands there. The
  house then names it, and the body may lift it.
- `pick_up` still routes as if the piece it goes to were not there, so a way can still lead through that piece. A walk
  that sticks there now names the piece. This change does not alter the route.
- Setting the roof from two cells out (6.22 from the body's centre, inside the 7.0 place range) has been checked by
  arithmetic and on the stand-in, not in the world.
- Where the carry sets a piece down: the nearest clear floor beyond the site, which can be just past the way out, for
  example (-85.0, -27.5) at the 07:49 site.
