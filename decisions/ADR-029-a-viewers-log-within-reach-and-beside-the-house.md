# ADR-029: A viewer's log comes in to Godling's reach, and lands beside its house

Date: 2026-11-09. Status: built and tested in the world's, the mind's, the screen's and the site's suites. Not yet
tried in a live run.

## Why
This comes from the live run of 2026-11-08 22:10 to 2026-11-09 07:50 UTC (its local copy: `run-live/`).

**Most log drops were refused.** Viewers called the Log 32 times, and the world refused 19 of them (`site-stats.json`,
`by_power_ok`). Every refusal in the sample was "Too far from Godling: aim within 60 of it". The credits came back
(`web/apps/screen/tasks.py` refunds every call the world did not do), but the viewer got nothing. Nothing had warned
them, either: the aiming ring (`world/renderer/src/aim.js`) followed the pointer anywhere on the island, and the limit
appeared only in the refusal. Even a viewer who aimed inside the limit could be refused, because Godling may walk on
while the call waits in the site's queue.

**Aimed logs landed on the house.** An aimed drop went to the nearest spot to the aim with 0.5 of room from other
pieces, or 3.5 from Godling's centre when aimed at Godling. An unaimed drop keeps 4 from every piece
(`SKY_SPOT_CLEARANCE`). The world knows a house only once it stands (`houseAt`). While a house goes up, its room is open
grass, and the world could not tell it from any other grass. The run's last house had its room at x −90 to −87.5,
z −20 to −17.5, with its walls round that. Logs 94, 97, 99, 105 and 106 landed in and around it. Log_94 landed at
(−89, −15), on the line of the north wall and at Godling's feet. After that:
- "penned in by Log_12, Log_10, Log_5, Log_94"
- "the way to (-87.5, -17.8) is closed off by Log_94, Log_88, Log_12, Log_7"
- "(-90.0, -16.0) lies inside Log_94"
- "snagged by Log_94", six times
- Log_99 at (−94, −7): "(-93.7, -7.0) lies inside Log_99"

**The owner's condition:** keep viewers' log drops as they are. Do not reduce how many land, and do not make them cost
more.

## Decision
### 1. The reach is shown, and an aim past it comes in to the edge
This is the usual way for an ability aimed at the ground. While the player aims, a range indicator shows round the
caster. An aim past the range is brought in to the edge along the line from the caster: League of Legends' Flash
works so, and so do most abilities there cast with "quick cast". Two other ways were set aside:
- Moving the caster into range, as Dota does, has no place here: viewers do not move Godling.
- Refusing the aim suits an action where the exact spot matters. A gift needs only to land near where the viewer
  aimed, and the refusal lost the viewer the gift.

**On the screen.** While a log is aimed, a ring of radius 60 (`REACH`) lies round Godling's feet and follows Godling
each frame (`aim.update`). It brightens when the pointer is past it. The reticle then sits on the ring, on the line from
Godling to the pointer and on top of whatever stands there. The aim bar says "Past Godling's reach: it lands on the
ring". The spot on the ring is what the screen sends.

**In the world.** `sky.aim.read` brings such an aim in to the edge as well (`within`), because Godling may walk between
the click and the call. The world log says so: `SKY Log aimed 84.0 from Godling, past its reach: brought in to ...`.

**The words.**
- The Log's tip has a rule, "Within 60 of Godling: an aim further out lands at the edge".
- Its description says "beside Godling's house and never on it".
- A site migration (`credits` 0010) changes only words that are still as seeded. Words written in the admin stay.

The remaining refusals (`NoClearSpot`, `NobodyHere`) are refunded as before.

### 2. Beside the house, not on it
**Clearance.** A log's middle keeps 4 from the middle of every piece lying in the world, just as an unaimed gift does.
This holds aimed or unaimed, and at Godling's feet too. A piece in someone's hands does not count. It moves with them,
and if it counted, a log aimed at Godling would always be refused while its hands were full.

**The house's cells.** The mind says which cells its house needs, with a new input, `HouseSite {cells}`. Two ways were
weighed:
- **The world works the house out from its pieces.** It cannot until the house stands, which is what `houseAt` checks.
  Guessing a room from half-built walls would put a second house planner in the world.
- **The mind tells the world** (chosen). The mind already knows what it is building (`memory.state["house"]`: its room
  and its doorway, ADR-019). `mind/godling/site.py` sends every cell the house needs:
  - its room
  - its walls all round, corners too (`house.ring`)
  - its doorway
  - the way out (`house.outside_of`)

  These are the cells the mind inspects for its site (`Mind._house_cells`). The world keeps a plain list of cells for
  each player, so it needs no house rules of its own: a bigger room or another doorway needs no change in the world.
  Building and colony games keep the cells of a blueprint or a zone reserved in the same way.

  The mind keeps the world in step, as one keeps a state in step between two programs:
  - It sends the site at the start of each cycle, but only when it changed or the world session is new.
  - It sends it again right after a plan chooses, moves or gives up the house, so the site is kept clear before the
    first project on it begins.
  - At the run's start it sends even an empty site. That clears whatever an earlier mind left in a world that kept
    running.
  - If a send fails, the next cycle sends it again.

  The world takes the site even while the body lies dead. It never sets `LastActionResult`, which the body's own steps
  read, and `Think` already works this way. It ignores nonsense, and anything over 400 cells.

A log's whole outline, as it will lie, keeps off those cells (`sky.aim.keeper`). Touching a cell is not landing on it.
This holds for unaimed logs too, which until now kept clear of pieces but not of an empty room.

**Landing as often as before.** The stricter rule must not turn landings into refusals:
- The search round the aim goes out to 20 (`SNAP_FAR`) instead of 12.
- A log lies along x or along z, whichever fits first.
- The cheap checks run first, and the pieces are gathered once for each drop, because the search tries hundreds of
  spots.

**Not guided construction.** The world tells the mind nothing new, and places nothing for it. The site serves only to
keep the sky's gifts off it. Godling still chooses where to build, and still fetches each log.

### Only the log
The owner asked for the other powers to stay as they are. The stone gift shares this code (`sky.aim.gift`) but keeps its
old rules, because `KEEPS` holds only the log:
- A stone aimed past 60 is still refused.
- It lands with 0.5 of room.
- The screen shows no ring for it.

Giving the stone the same rules would take one entry in each of `KEEPS` (`main.lua`) and `LOOKS` (`aim.js`). That is the
owner's call.

## Checked
CI is not running (GitHub billing), so every suite was run locally.

**World: `world/tests/test_drops.luau`** (new). It turns the run into tests:

| Case | New code | Old code |
| --- | --- | --- |
| A log aimed 90 out | lands within 12 of where the line from Godling crosses the ring | `TooFar` |
| A stone aimed 90 out | still `TooFar` | `TooFar` |
| A log aimed 30 out | lands where it was aimed | lands where it was aimed |
| A log aimed 3.2 beside a block | lands at least 4 from the block | lands at the aim, 3.2 from it |
| A log aimed at Godling, with a stone in its hands | still lands at its feet, 3.5 out | the same |
| A two-by-two house, walls half built (below) | on no house cell, at least 4 from every wall | on the room's cell |
| A crowd of pieces 5 apart, out to 13 from the aim | lands past the crowd, within 20 | `NoClearSpot` |
| `HouseSite` (below) | as listed | the input is unknown |

The house case drops logs aimed at the room, the doorway and the way out. It drops one aimed at Godling standing in its
room by the north wall (Log_94's case), and four unaimed ones. None lands on a house cell, every one is at least 4 from
the walls, and the one aimed at the room lands within 20 of the aim.

`HouseSite` is kept and leaves `LastActionResult` alone. Nonsense and too many cells are ignored, an empty list clears
the site, it is taken while Godling is dead, and the guest panel cannot set one.

All five tests fail on the old `main.lua`, each for the reason in the last column.

**World: `world/tests/test_sky.luau`**, two expectations changed:
- In the crowd test, a log now lands past the crowd instead of being refused.
- An unaimed log in a stone's spot is "moved or turned" until it fits.

**Mind: `mind/tests/test_house_site.py`** (new). For the run's last house the cells are 17: room, walls, doorway and
way out. The site is sent once, again on each change, empty when the house is given up, and again for a new session.
After a `WorldError` it is sent at the next sync. Both loops first clear the site, then send the house's cells after
the plan that chose it and before its first project. The test cannot run on the old code, which has no
`godling.site`.

**Renderer: `world/renderer/test/aim.test.js`.**
- The ring has radius 60, lies round Godling, and follows Godling.
- A pointer about 76 out gives the spot on the ring, on the line from Godling, at the top of a block standing there
  (height 3). A click sends that spot, with `beyond` set.
- A stone gets no ring and no bringing in.
- With Godling out of sight there is no ring and no bringing in.

**Screen: `world/renderer/test/viewer.test.js`.** The tip's rule and description, the aim bar's words, and the posted
spot are checked; the stone's words are unchanged. Both new renderer and screen tests fail on the old code.

**Site: `LogReachTests`.** The seeded description and rule are checked, words written in the admin stay, and the
migration goes back.

## Not checked
- **No live run has tried this yet.** Still to see:
  - whether viewers stop aiming past the ring once it shows;
  - how often the wider search still ends in `NoClearSpot` round a cluttered building site;
  - how the ring looks on the follow camera, above all on a phone. It lies flat at Godling's feet and is drawn over
    everything, hills included.
- **Godling's own clutter.** The body may still set its own pieces down beside the house. Another fix deals with the
  building site.
- **Older worlds.** With a `main.lua` from before this change, the input `HouseSite` is answered `InvalidAction` and
  does nothing.
