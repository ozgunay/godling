# ADR-027: A house's site is kept clear, and the body carries what it holds off a tangled site

Date: 2026-11-09, revised the same day after the review of #81. Status: built and tested in the mind's suite. Not
yet tested in a live run.

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
The site (`house.site_of`, a `house.Site`) is marked cell by cell:
- the house's room, its doorway and the way out of the doorway;
- its walls, the cells round the room but for the doorway;
- the strip of ground a cell wide round the walls and the doorway, where the body stands to build them;
- the approach, the three cells straight on beyond the way out, which is the way in to the doorway.

`memory.reserved_cells` gives the site, through the body's existing wiring (`Skills(reserved=...)`). Every set-down is
checked before the body walks anywhere, by one predicate that `put_down`, the hands-full reflex and its carry all use
(`Skills._set_down_spot`, with the ladder and site rules in `Skills._closes`). Where the piece would lie is decided by
`house.placement`, the same check `house.plan` uses, and is measured from the same floor (the ground under the room's
first cell).
- **What the hands set aside to free themselves** (the reflex and its carry) goes nowhere on the site, at any height:
  not in the room, the doorway, the way out, the walls or the strip. Setting aside is not building. The approach is a
  last resort, used only when nothing else is clear.
- **What is set down on purpose** (`put_down`, `place_at`) while the house is built is refused when, below the roof
  line (`house.WALL_LINE`: an underside lower than 6.25 above the floor, the walls' first three courses), it reaches
  into the room, the doorway, the way out or the strip, or lies across a wall out of the walls' line. In a wall's
  cells only a building piece goes: a block, a boulder, a log stood on end, or a log along the wall's line.

The refusals:
- "(-95.0, -15.0) is beside your house's walls, on the ground a cell wide round them where you stand to build (only a
  block on its own, as a step, or a ladder goes there). Your hands keep the site clear: a piece goes in a wall along
  its line, or off the site"
- "(-92.5, -20.0) is across your house's wall at (-92.5, -20.0): Log_1 there would stick out of the walls' line, into
  (-95.0, -20.0) beside the walls and (-90.0, -20.0) in the room. Your hands keep the site clear: …". The wall named
  is the cell aimed at, when that is a wall.
- "… is in your house's wall, where only its own building pieces go", for a hammer, say.
- "… is in your house's room", "… in your house's doorway", "… in the way out of your house's doorway".

What the rule leaves alone:
- **The roof.** A piece set down on purpose with its underside at the roof line or higher is laid over the walls and
  reaches out over the strip, as the house's roof logs do. How the body gets up to it, from a step or from the floor,
  is the body's own business.
- **A ladder set down on purpose on the strip.** It stands against a wall there. ADR-025 governs ladders. Anywhere
  else on the site a ladder is refused like anything else.
- **A block set down on purpose on its own on the strip, as a step.** It must be a building piece a cell across on
  every side, lying on the ground under it. The house's roof step says to set the roof "from a step one block high
  outside the walls". Taking a stone off a wall's top reaches only from a step one cell out: from two cells out it is
  6.22 from the body's centre, past the 6.0 reach. The house keeps a step as before (it is no free material, and
  `nearest_free` passes it over), but the body may lift it by name (`house.plan`'s "steps", `memory.built_into`).
- **A house that stands.** Once it stands (`house["built"]`), its site is only its room, doorway and way out, and only
  for what the hands set aside, which is the guard ADR-019 put in. Where the mind sets things down on purpose is then
  its own choice.
- **The reflex that lifts a piece aside to get out of a pen,** because it puts the piece back where it was, and
  **`stack_on`** (offered only with `--gifted-skills`), as in ADR-025.

The mind is told this as a fact about its body, next to the house rule (`mind.SITE_RULE`).

### b. Carry it off instead of failing
When none of the reflex's spots near it will do, the body carries what it holds to the nearest clear floor beyond the
site and says where it went. It looks up to 30 away. Of the 12 nearest spots, it takes the one nearest by the way
there, and all 12 ways are worked out on one shared map of the floor. It avoids the approach to the doorway unless
nothing else is clear: "picked up Log_105 (first carried Log_held off your house's site and set it down, turned a
quarter round at (-80.0, 1.37, -22.5), to free your hands)". It says "off your house's site" only when the site turned
spots away. Far from the house it says "further off".

Penned in, it heads for the nearest spot, and the pen reflex lifts a way out first. That reflex rests what the hands
hold on a side of the pen while it lifts. It rests it first on a side low enough to take it back from outside, but
never at the body's height over the piece it is about to lift, or across the way out past it. With nowhere else, it
rests it on the nearest side, as before. If the lifted piece cannot go back, it is set aside, carried off if need be,
so the hands are free to take back what they rested.

With nothing clear within 30, the hands stay full, and `pick_up` says "there is no clear floor near enough to set it
down off your house's site", adding the walk that stuck, if one did. When the walk ends in the sea, that is what the
step reports. If the hands came free on the way (a lift rested the piece somewhere), `pick_up` goes on and says where
the piece lies. If what is in the hands is not what it set out to set down, `put_down` and `place_at` refuse, saying so.

`nearest_free`, as `pick_up`'s object, is the piece in the hands when it is of the kind asked for. So `upright_log_at`
goes on with the log it holds. As a target (`pos`, `top`), it is the nearest piece that is not in the hands.

Fixed on the way: `put_down` looked for ground before it snapped the spot to the grid. At the edge of the sand, the
snapped cell could be over the sea, and the reflex crashed ("bad arguments: max() iterable argument is empty").

### c. A stray piece in a wall cell is in the way, not the house's own
`house.placement` decides where a piece lies. In a wall cell, a piece with its underside below the roof line counts as
one of the wall's courses only when all of its cells are wall cells. Otherwise it is in the way: it is not kept, the
body may lift it, it is listed among the loose objects, and it does not count as the wall standing there.

What lies on the strip is in the way too, apart from a lone step. That also frees Log_12, which `keep_builds` had kept
as part of a build because it touched the walls: what is in the house's way outranks a build (`memory.built_into`,
`memory.protected_cubes`). It does not outrank what the mind kept by name. A woodpile it named on the strip stays its
own.

A house that stands has nothing in its way. Log_94, lying along the north wall wholly in its cells, stays the house's
own, and so do an upright log and a boulder in a wall.

**This is a move toward guided construction.** The house's next step now names what lies across a wall and what lies
on the strip:
- "(-92.5, -22.5) stands 0.0 (Log_6 lies across it, out of the walls' line)"
- "…; lying on the ground a cell round the walls, where you stand to build them: Log_12 (-97.5, -15.0),
  Log_98 (-95.0, -25.0)"

The words state facts about the site, and give no instruction. The next step already named what fills the room or the
doorway (ADR-019). Steps on the strip are not named.

### d. The body names what blocks the way
When a walk with a way round gets stuck, it now says what stopped it:
- what presses on the body, the same thing the unstick reflex names (`Skills._pressing`);
- what lies across the leg it was walking, not across the straight line to its goal, which the route may have gone
  round.

For example: "stuck 20.0 units short of (0.0, 20.0); snagged by Log_99". With no way left open, the walk gives the
existing "no way round" account. That search is bounded (`NEAR_SEARCH`, a square some 70 across).

`pick_up` routes round the piece it goes to when there is a way round, and through it only when there is not. Before,
its route could cut the piece's corner and snag there.

`nearest_free` takes the first of the six nearest pieces that the body can walk to, on its own floor and going round
everything, all six worked out on one map of the floor. If the body can reach none of them, it takes the nearest, and
`pick_up` says why.

## The review of #81
A code review of the first version (37 findings) led to the second version described above. These are the changes,
with the finding each answers:
- **What is set aside goes nowhere on the site, at any height** (81-AB9, 81-SWEEP1, 81-CDE2). Up on the walls, the
  reflex had laid a log over the doorway at roof height, where the house read it as the lintel and kept it. Lower
  down, it had laid logs and stones in empty wall cells, which the house kept as its own, and tools there, which the
  house cannot see.
- **The approach to the doorway is a last resort for the carry** (81-AB2). Carried from the room, a log had been laid
  straight beyond the way out.
- **A house that stands leaves its ground to the mind** (81-CDE5).
- **Narrower allowances on the strip:** a ladder only there (81-AB5), and a step only when it is a block on the ground
  under it (81-AB6, 81-CDE9).
- **A step stays kept, and so does what the mind named** (81-CDE1).
- **A drowning on the carry is reported** (81-AB1), as are hands emptied on the way (81-AB3) and a different piece in
  the hands (81-CDE8). The pen reflex rests clear of the gap it opens (81-AB4).
- **Smaller fixes:**
  - `nearest_free` hands over the held piece only as `pick_up`'s object (81-CDE6).
  - A stuck walk names what was on the leg it walked (81-AB8), searched with a bound (81-AB13).
  - The carry's wording follows the site (81-SWEEP2).
  - `pick_up` routes round its target (81-CLEAN18).
- **One check where there were several:**
  - One site predicate, `house.placement`, for the plan and the hands (81-CLEAN17, 81-CLEAN3, 81-CLEAN6, 81-CLEAN7,
    81-CLEAN11).
  - One set-down check and one keep-clear hook (81-CLEAN1, 81-CLEAN19).
  - One set-aside routine for the near ring and the carry (81-CLEAN4, 81-CLEAN8, 81-CLEAN10, 81-CLEAN16).
  - One "what presses on the body" helper (81-CLEAN2), and one stand radius for `pick_up` (81-CLEAN9).
  - The plain-set path is gone (81-CLEAN5).
- **Shared work:** a shared floor map for many routes from one start (81-CLEAN12, 81-CLEAN15), the ladders and
  nearby things looked up once (81-CLEAN13), and `_route`'s escape step looking only near (81-CLEAN14). On the
  reviewers' crowded stand-in (the 07:49 site, 500 terrain parts and 300 loose rocks), the hands-full search, with
  every put-down refused so that it searches all it would, went from 361 to 64 ms from the room and from 61 to 25 ms
  from the west side. `nearest_free` went from 150 to 117 ms; most of that is the routes themselves.

## Checked
- `mind/tests/test_site_clear.py`, 46 tests, on the stand-in island with the body and the mind wired as in
  `run_godling.py`. The stand-in's `Place` now turns a piece as the world does, when a test asks (`Island.turns`);
  without that, a log set down turned a quarter round kept its unturned box.
  - The first version's tests: run against the code from before ADR-027, 11 of the 12 fail with the run's own
    failures:
    - The stray is the house's own, and the 07:49 site's "in the way" list is empty.
    - The reflex lays the log, or the stone, on the strip.
    - `put_down` sets a log on the strip.
    - From the room at 07:49 the result is "stuck 5.6 units short of (-102.0, -12.5)", and from the west side "hands
      are full … no clear spot nearby".
    - The room with walls one course high crashes on the sand's edge.
    - `nearest_free` reaches past the held log, and picks the log in the pit.
    - A stuck walk names nothing.

    The twelfth test starts from the way out at 07:49, where the old body got there too. It is a guard.
  - The review's tests: run against the first version, 32 of the 46 fail. The 14 that pass there are the first
    version's own tests and these guards: the pen with a tall corner, the failed put-back at 07:49, a ladder on the
    strip, and a stone as a step.
- Each case at 07:49 ends with Log_105 in the hands, and the held log off the site and off the approach:
  - From the room, the body carries the log out by the doorway.
  - From the way out, it sets the log down in reach, beyond the site.
  - From the west side it is boxed in by Log_13, Log_98, Log_9 and Stone_2. It lifts Log_13 aside, steps out, sets it
    back, and carries the log off.
- The roof check still works under the rule: a roof log is set at its height over a wall and the strip.
- `test_house_recovery.py`'s run hp-full2 tests are wired with `site_of`, as `run_godling.py` wires the body, and its
  site map test covers the walls, the approach and a standing house. `test_skills.py`'s stand-in library takes the
  step's skill.
- Every suite passes locally: the mind's and the tools' (465 tests), and the world script's, which this change does
  not touch. CI is not running at the moment.

## Not checked
- Not yet in a live run.
- Whether deepseek-flash clears the strays and the strip once they are named and the body lets it, or builds on them.
- The world is unchanged. A viewer's dropped log, or a piece thrown onto the site by a blast, still lands there. The
  house then names it, and the body may lift it.
- Setting the roof from two cells out (6.22 from the body's centre, inside the 7.0 place range) has been checked by
  arithmetic and on the stand-in, not in the world.
- Routing `pick_up` round its target has been tried on the stand-in only. Where the target itself closes the only way
  to a spot beside it, the route goes through it as before.
- Up on the walls with full hands and nothing clear at its own height, the reflex now keeps hold and says so. The
  first version set the piece down on top of the walls, as roof work.
