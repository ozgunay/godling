# ADR-033: Bigger houses: posts hold up a wider roof, and a bigger room mends faster

Date: 2026-11-09. Status: built and tested in the mind's and the world's suites, with the code review's fixes (Review
fixes, below). Not yet tested in a live run.

## Why
In the 9.6-hour live run (2026-11-08 22:10 to 2026-11-09 07:50 UTC) Godling built the smallest house there is, a room
two cells by two, and kept to it. The investigation found the reasons in the code:
- **The mind chooses the size, but the code capped the width.** The mind picks the room (`Mind._choose_house` →
  `house.layout`). The guided roof (ADR-019) lays logs three cells long, each centred on a wall and reaching one cell
  in, so a room could be at most two cells wide. Tried against `layout()`: 2×2 to 2×10 passed with the doorway on a
  short end; 3×3, 3×4 and 4×4 failed with every doorway. At 22:13 the mind had planned "a 4x4 house with roof".
- **Nothing could hold up the middle of a wider room.** The room had to be clear, so a post inside it failed the house
  check, in `house.judge` and in the world's copy (`houseAt` in `world/main.lua`): eight cells round a post hold no
  two by two.
- **A house gave the same at any size.** The prompt named only the two by two minimum, and a house warmed and mended
  the same whatever its size. So the smallest was the right choice, and the mind said so ("Already minimum", 22:24).
- A 2×2 house takes 21 pieces (walls of upright logs, one per wall cell), and each two cells more along it take 4 more.
  This one was finished at 00:19 and lost at 06:33 to an earthquake and a meteor; none of its pieces were fastened.

## Decisions
1. **Posts hold up a wider roof (post and beam).** This follows RimWorld, where a column holds up the roof within a
   radius of it. Here the radius is set by the logs: a log three cells long, resting on its middle, reaches one cell
   from what holds it up.
   - **What a post is.** A cell inside the house with the room on all four sides of it: the room closes round it, and
     there is no way from it to open ground side by side but through the room (`house.enclosed`). A column against a
     wall is not a post but part of the wall.
   - **How the house checks judge it.** A post must stand from the floor up to the roof without a gap, with the roof
     on it, as a wall must. It counts as a cell inside the house for the two by two, but not as room to stand in. Both
     checks do this: `house.judge` and the world's `houseAt`, which the tests hold to the same house.
   - **What the house checks do not look at.** Any built house with posts that passes is a house, however its roof was
     laid. This includes rooms the guided roof would refuse.
2. **The mind chooses its posts.** A house in a reply may carry `"posts": [[x, z], ...]`, cells among those inside.
   `house.layout` refuses, saying why:
   - a post that is not one of the cells inside;
   - a post against a wall or against another post ("a post stands alone inside, clear of the walls and of other
     posts");
   - posts that cut the room in two;
   - a room whose roof cannot be laid (point 3).

   A reply that leaves `"posts"` out keeps the house's posts that still stand alone in its new cells; a reply that
   leaves the cells inside or the doorway out keeps those; only `"inside": []` gives the house up.
3. **The guided roof is laid as a whole.** `house.roof_layout` used to match each cell of the room to a wall, then
   check for overlaps afterwards. It now searches for a roof with every cell of the room under exactly one log and no
   two pieces in one cell:
   - The doorway's lintel goes first, as before.
   - Each cell of the room then gets a log, tried in order: one centred on a wall beside it, then one centred on a post
     beside it (which also reaches over the cell on the post's far side). The first roof that covers the whole room is
     the one used. A log already lying where one of these goes stays where it is.
   - The walls and posts left over get a block on top.

   When no roof can be laid, the refusal names the cell that is short, and the doorways and single posts more that
   would give the room a roof:
   - "nothing holds up the roof over (2.5, 0.0), (2.5, 2.5): a log three blocks long reaches one cell from the wall or
     post it rests on, so every cell inside must lie beside a wall or a post (not the doorway or the walls either side
     of it); it has a roof with one more post, at (2.5, 2.5)";
   - "no way of laying the roof covers (2.5, 5.0): each wall or post holds one log, and every way of laying them leaves
     none for it; it has a roof with the doorway at (0.0, -2.5), (2.5, -2.5) or (5.0, -2.5)";
   - with none: "...; no other doorway, and no one more post, gives it a roof: make the room another size or shape".

   The comparison covered rooms two cells wide (2×2 to 2×10, both ways round) and two L shapes, each with every
   doorway. For all 77 room-and-doorway pairs the old code accepted, the new roof and the plan's wording are the same
   as before. Six pairs the old code refused for overlapping pieces now have a roof.
4. **The body reaches a roof over a post from the floor inside.** From the floor, the body's centre is 6.2 below the
   roof's middle (8.75), and the hands reach 7. Two body changes in `skills.py`, each a fix to what the body believed:
   - **A log the house's roof puts on a middle is set there.** The body moves a raised log so that both its ends
     rest on something (`_beam_on_supports`). The old code moved a log aimed at the post's middle onto the post and the
     north wall, at (2.5, 8.8, 5.0), which left the cell south of the post with nothing to hold its roof. Now a log
     aimed with its middle on something is set there if the house's guided roof puts a log there (`plan()["roof"]`,
     kept in memory, `Skills(planned=memory.planned_roof)`), or if no cell along it lies across two supports. A lintel
     aimed on one flank is still moved across the doorway, as before.
   - **A piece that will rest wholly over the head may be set from under it, or from right beside it.** The body tries
     the old ways first: a spot beside the piece within the usual margin (0.4 short of the hands' 7), then a step
     outside. Then, only for a piece that will rest there (on its middle, or a log on both ends), it stands under it
     (6.2 from the hands), and last of all right beside it, as far as the hands reach less a quarter unit
     (`OVERHEAD_SLACK`). From beside a post the hands are 6.67 from the log's middle. Logs on the walls and caps still
     go up from a step where there is one.
   - **A piece over the head is lifted from below.** The world lifts the piece nearest where the hands reach, within
     1.5 of it, from at most 6 away (`findNearestBlock`, `PICKUP_RANGE`). `pick_up` now aims at the point below the
     piece, or below it and to a side, where it is still the nearest by a margin. So the hands reach up to a block on a
     post's top from the floor beside the post (5.3 away), where its middle is out of reach (6.2). This also lifts a
     stone off a ladder's top from the ground (ADR-025 said it was out of reach there).
5. **A bigger room mends faster.** Inside a house, a fed body mends twice as fast in a room of four cells to stand in.
   Each cell more adds a quarter, up to four times as fast in twelve cells or more (`HARM.houseHealsPerCell`,
   `houseHealsMost`). `houseAt` now returns the room's cells to stand in. The world gives the body `HouseRoom` and
   `HouseMends`, and the mind feels it: "You are inside a house: warm and dry, mending three times as fast while fed
   (its room has 8 cells to stand in)".
   - **Why this payoff.** It speaks to the reason found in the run, that a house gave the same at any size. It works the
     moment the house stands, needs nothing else to go right, and is one number from the check the world already
     makes. Games treat room the same way: RimWorld rates a room's space (cramped or spacious), and Valheim's comfort
     lengthens the rest a shelter gives. A bigger house also costs more pieces, more time, and more to lose to a quake
     or a meteor. That is the trade the mind now weighs.
   - **What it does not reward.** It counts room to stand in, not width. The cheapest way to the most mending is a
     long room two cells wide (2×6: 12 cells, 37 pieces, no posts). Posts make room for squarer, wider houses. Which
     to build is the mind's choice.
   - **Considered: a hearth.** A fire inside rooms of a minimum size was the other candidate. A fire's log in the room
     fails the house check today, and the logs laid against it to feed it would too. Allowing it means two copies of
     the check accepting burning logs and their fuel. It would also give little that a house does not already give
     (warmth), and only after the whole chain of making fire goes right. It is left for later.
6. **The mind is told the facts, not a method** (`mind.py`):
   - The house paragraph says: "A log stays up resting on its middle, or with its two ends on something, and no two
     pieces of a roof lie in one cell. So a log on a wall reaches one cell in, and a room two cells wide is roofed from
     its walls. A wider room needs posts inside it: a log stood on end, from the floor up to the roof, alone with the
     room on all four sides of it, holding a log on its middle over the cells either side. A post counts as a cell
     inside the house, not as room to stand in."
   - It also gives the payoff in point 5, and its cost: "A bigger house takes more to build: a room of four cells some
     twenty pieces, sixteen of them logs if its walls are logs; one of twelve cells nearly twice as many, some thirty
     logs" (the review's INT-9: PR #77 halves the logs a palm gives).
   - The body facts say the hands set "a piece of a fourth [block] only right over its head or right beside it".
   - The house shape gains `"posts"`.
   - The house line names the posts, and the plan's next step names them.

## Which rooms the guided roof can cover
With lone posts, and one piece per cell on the roof:

| room | posts | pieces | room to stand in | mends |
|---|---|---|---|---|
| 2×2 | 0 | 21 | 4 | 2× |
| 2×4 | 0 | 29 | 8 | 3× |
| 3×3 | 1, in the middle | 31 | 8 | 3× |
| 3×4 | 1 | 35 | 11 | 3.75× |
| 4×4 | 2, on a diagonal | 41 | 14 | 4× |
| 5×5 | 5 | 55 | 20 | 4× |

These are tested in `test_house_posts.py`, as are 3×5, 3×8, 4×6 and 4×8. A search over every lone-post pattern
also found layouts for 3×10, 4×7 and 5×7. It found none for 5×6 and 6×6, with any doorway. A room three cells wide
needs a post in its middle line every third cell, and the cell just inside the doorway needs a wall or a post beside it
other than the doorway's own. Posts side by side would allow 6×6, but only as a solid block of posts with the room
round it, which is no better a house, and the middle of the block could not be reached from the floor.

## Moves toward guided construction
- **The guided roof now covers posts.** The next step names each log over a post: its axis, the post it is centred on,
  and that it is set standing on the floor beside the post. This is the same kind of guidance as ADR-019's roof,
  extended to wider rooms.
- **The layout refuses rooms the guided roof cannot cover.** This is a check against the method, not only against
  physics: a roof the mind might lay another way (two layers, or beams with their ends on posts) is refused when the
  house is chosen. ADR-019 already did this for rooms two cells wide; it now names the cell that is short, and what
  would do.
- **The prompt hints at the method.** "A wider room needs posts inside it" is a fact of logs three cells long, but it
  points at the answer.
- **The refusals name what would work.** When the roof cannot be laid, the refusal names the other doorways and the
  single posts more that would give the room a roof (82-AB5). The mind still chooses, but from a list the body worked
  out.
- **The hands know the house's roof.** A log aimed on a middle where the guided roof puts one is set there, where any
  other log on a middle with two supports a cell along it is moved onto them (82-AB8).
- **What stays the mind's.** Where the house stands, its size and shape, where its posts go, the doorway, the order of
  the work and what it is built of. The body does not place posts for it or choose them, and the check judges what was
  built, not the plan.

## Review fixes (PR #82's code review, 2026-11-09)
Thirty-two findings; each id's outcome is in the review-fix PR.
- **A house built as the plan says is finished (82-AB1).** A log laid as asked made its wall's top "taken"; the next
  plan routed its cell to another wall, which then dropped out of the caps and was never asked for. Following the plan
  piece by piece, first need first, left even a 2×2 unfinished (and every shape in the table). The roof search now
  keeps the logs already lying where a log goes (and tries them first), and `test_following_the_plan_piece_by_piece`
  builds every shape both first need first and last need first.
- **A lintel aimed a cell off goes across the doorway again (82-AB8, 82-AB9)**, and only a log the house plans on a
  middle stays there (point 4).
- **Lifting a piece off a post's top from the floor (82-AB2)**: point 4, and the plan says "reach up from the floor
  beside the post".
- **What a reply leaves out (82-AB3, 82-SWEEP1)**: point 2.
- **The body never stands under a piece that would fall (82-AB11), and keeps the step for caps and the lintel where
  there is one (82-CDE2)**: point 4.
- **What lies where a log on a post goes is named in the way (82-CDE3)**, also over the other cell it reaches, and the
  hands-full reflex keeps the post's cell clear again (82-CDE4: it set a block there, which became the post's base).
- **The refusals name what works (82-AB5)**: point 3. The old one said a post "holds another log already" when the
  roof laid none on it, and advised a post beside the cell where none could stand, in all 160 refusals measured.
- **Smaller:** the room's cells as a whole number (82-AB6); the fall report names what was under the log's middle and
  says the rule as the prompt does (82-CLEAN19); a search cut short says so (82-CLEAN13); the stand-in island holds the
  hands to the world's reach (82-CDE9; one older test had set a block from 7.6 away); the docs (82-AB7).
- **Cleanups that change nothing:** one flood fill, one roof probe, one way of saying what fits, the roof issue
  cached per layout, one helper for the feeling, the walls/posts split, the shared test builders, one `houseRoom` in
  the world (82-CLEAN1 to 82-CLEAN15).
- **Not changed:** a room cell between a post and a wall leaves the body a band 0.1 wide to walk (82-CDE7), as a
  doorway does, which live bodies pass; the world test helpers (82-CLEAN6), since other open PRs edit those tests.

## What changed
- `mind/godling/house.py`:
  - `enclosed` (a room's posts); `judge` judges posts with the walls and counts them in the two by two;
  - `shortfalls` names a post that falls short; `assess` counts posts;
  - `layout(inside, door, posts)` returns `(inside, door, posts)`;
  - `roof_layout` is the search, and `guidance_issue` gives the refusals;
  - `plan(..., posts)`: the posts in the walls step and the pieces kept, logs over posts in the roof step;
  - `mending` gives the mending factor in words.
- `mind/godling/mind.py`: the prompt (the house, the payoff, the hands), `"posts"` in the house shape, kept in memory,
  and named in the house line; the feeling says how fast the body mends.
- `mind/godling/attention.py`: walking into a house says how fast the body mends there.
- `mind/godling/memory.py`: posts are not kept clear.
- `mind/godling/world.py`: `house_room`, `house_mends`.
- `mind/godling/skills.py`: `_on_its_middle`; overhead pieces in `place_at`; `slack` in the stand-point searches.
- `world/main.lua`:
  - `houseAt` finds posts and returns the room's cells;
  - mending scales with the room;
  - the body carries `HouseRoom` and `HouseMends`;
  - the `HOUSE` line gives the room's cells.

## Checked
- **Written first, and run against the old code:**
  - `mind/tests/test_house_posts.py`. All 24 of its tests failed on the old code, among them: "the room inside is 8
    cells, ...: a house's room holds at least two by two cells", and "cannot get within reach of (2.5, 8.8, 5.0)".
    The second is the log aimed at the post's middle, moved onto the post and the wall.
  - `world/tests/test_life.luau`, "a house three cells wide on a post inside". It failed on the old `houseAt`
    ("expected true, got false").
- **What the tests cover:**
  - A 3×3 house with a post is a house in both checks.
  - A post two blocks high, or without the roof on it, is not, and the mind is told why.
  - A column against a wall is no post.
  - The layout's refusals.
  - Every shape in the table is laid by the guided roof with nothing overlapping. Each log rests on its middle, and
    the built house passes both `houses()` and `plan()`.
  - The plan for a house with a post, step by step.
  - The post's cell is not kept clear.
  - The body sets a log on a post from the floor beside it, unmoved, and a beam overhead from the floor under it.
  - The mind chooses, keeps and revises a house with a post.
  - The world says 8 cells to stand in, and the body mends three times as fast.
- **Existing tests changed:**
  - `test_house.py`: `layout` returns three values. The L shape that overlapped now has a roof, and a short room
    gives the new refusal.
  - `test_mind.py`: the prompt and the feeling.
  - `test_skills_edges.py`: the "a cell off" beam case is now aimed a cell off in z. Aimed with its middle on a post,
    a log is now set there, balanced, not moved to lie across both posts (`test_a_beam_resting_on_its_middle_stays_where_it_was_aimed`).
- **Suites, run locally:** the mind and the tools (pytest), and the world script (all `world/tests/test_*.luau`). They
  were run locally because CI is not running.

## Not checked
- **Not yet in a live run.** Whether deepseek-flash builds bigger rooms for the payoff, finds a post pattern the roof
  takes, or puts up a log on a post from the floor.
- **The real world's physics.** Whether a log balanced on an upright log post stays up in Rapier, especially in a
  quake. ADR-019's logs balanced on walls stood through that run until the quake and the meteor.
- **Reach in the real world.** Whether the real body gets close enough beside a post: 6.67 of the 7 the world allows.
  This was tested on the stand-in island, which has no character controller.
- **The cost of `houseAt`'s box search on a big room.** It runs at most once a second, under a roof.
- **The site, the renderer and the relay.** Not touched, and their suites were not run.
