# ADR-026: Fewer logs come into the world: no driftwood, lightning that seldom fells, one log from the axe

Date: 2026-11-09. Status: built and tested in the world's and the mind's suites. Not yet tested in a live run.

## Why
In the live run of 2026-11-08 (22:10 to 07:50 UTC, 9.6 hours) the island filled with loose logs. The world made 106
logs, 97 were still in the world at the end, and 58 lay loose. Nothing ever tidies a loose log away, so every log the
world makes stays.

Where they came from, read from the pieces' `SkyEvent` and `Driftwood` attributes in `island-save.json`:

| Source | Made | Left at the end | How |
|---|---|---|---|
| The weather's lightning | 52 | 47 | 26 palms, at 2 logs each: every bolt felled a palm |
| Godling's axe | 22 | 20 | 11 palms, at 2 logs each |
| Driftwood | 19 | 17 | capped at 6 on the beach, but Godling carried them off, so more washed up |
| Viewers' Log drops | 13 | 13 | |

The lightning was the weather's, not the viewers': the site's stats show no Lightning power call, and the one Storm
was called at the very end.
- **Every bolt felled a palm.** In heavy rain (0.85 or more) a bolt comes every 3 to 8 minutes of heavy rain, and
  `stormStrike` always took a standing palm 12 to 45 from Godling, or the nearest one beyond.
- **The same palms, over and over.** Palms regrow in 10 minutes. Godling kept to its house at about (-95, -35), and
  only two palms stand 12 to 45 from there: Palm_2 and Palm_14. Palm_14 was struck 6 times, and Palm_34 and Palm_36
  4 times each.

## Decision (the user's, 2026-11-09)
**Remove driftwood entirely, and lower every other source except the viewers' Log drops, which stay exactly as they
are.** This is only about how many logs come into the world. Tidying away loose logs, or a despawn rule, is for the
building-site work in another change.

## What changes
### Driftwood is gone
- The world no longer washes logs up (`tickDriftwood`, its timer and its `DRIFTWOOD` log line).
- The mind no longer has a "A log washed up on the beach" event. Its system prompt no longer says logs "sometimes wash
  up on the beach", so it does not go looking for them.
- A log an old save still marks `Driftwood` is an ordinary log. The world ignores the mark, and the mind reports it as
  "A new object … appeared", as it does any log.

### The weather's lightning seldom fells a palm
- **Its look and its danger are unchanged.** In heavy rain a bolt still comes every 3 to 8 minutes, 12 to 45 from
  Godling. It is the same bolt, with the same flash, and it hurts anyone within 7 by 35 (`HARM.lightning`).
- **A bolt fells a palm at most once in 25 minutes of heavy rain** (`FELL_GAP`). Like the bolts' own timer, the gap is
  counted only while the rain is heavy. A run's first storm may fell one.
- **The storms spare a palm they felled for 6 hours** (`PALM_REST`), even after it has grown back.
- **Any other bolt** strikes the open ground in the same ring, at least 4 from a standing palm (`PALM_CLEAR`; a palm
  that close would have taken it), or the sea. Ground keeps a `Scorch` for 4 minutes, as the viewers' Storm leaves one.
  The world logs `WEATHER lightning struck the ground at (x, z)`, or `… the sea …`. The mind is not told: a bolt marker
  carries no `SkyEvent`, as before.
- **No more falling back to the nearest palm beyond 45.** With no palm it may fell in the ring, the bolt strikes the
  ground.
- A palm that lightning does fell still comes down as two logs: the bolt splits it.

### The axe gives one log
- A palm felled with the axe gives one log, its trunk (`AXE_LOGS`), instead of two. It is still 4 blows (2 with an
  iron axe), and the palm still regrows in 10 minutes.
- The mind is told so, as a plain fact of the world: "logs, beams three blocks long and one thick: an axe fells a tree
  into one, and the tree grows back". Its body already reads however many logs a felling reports.

### Unchanged
- The viewers' Log drop.
- The viewers' Storm: a palm beside one of its spots still falls into two logs, as its paid description says. A
  meteor's blast still fells the palms within 4 into two logs each. Regrow is unchanged.

## The numbers, and why
- **Today's rate.** One palm per bolt, and a bolt every 3 to 8 minutes of heavy rain: 5.5 on average.
- **`FELL_GAP` = 25 minutes.**
  - At most one palm per 25 minutes of heavy rain: 22% of today's average rate, under the quarter that was asked for.
  - On average the next bolt after the gap comes about 2.9 minutes later (for gaps spread evenly over 3 to 8
    minutes, the wait is E[X²]/2E[X]). So about one palm per 27.9 minutes: 20% of today's.
  - A gap of 20 minutes would average 24%, but could reach 27.5%, over a quarter. One of 30 minutes would average 17%.
- **`PALM_REST` = 6 hours.** That is three times the longest wet spell (2 hours), so no wet spell fells the same palm
  twice. A Godling that stays near its house sees each palm there felled at most once in 6 hours, however long it
  rains: at most twice in a run as long as this one, where Palm_14 fell 6 times.
- **`PALM_CLEAR` = 4.** A bolt on the ground right beside a palm would look as if it missed the palm. 4 is the meteor's
  felling reach, and a little more than the Storm's palm snap (3).

### Measured
In the world's test engine: the seeded weather of a 9.6-hour run, with Godling held still. It gave 144 minutes of
heavy rain; the live run had about 143. The probe was a scratch test, run against the code before and after.

| Where Godling stands | Code | Bolts | Palms felled | Most on one palm | Logs made |
|---|---|---|---|---|---|
| The island's middle (11 palms in reach) | before | 24 | 24 | 4 | 48, and 6 driftwood |
| | after | 24 | 5 | 1 | 10 |
| By the run's house (2 palms in reach) | before | 24 | 24 | 14 (Palm_2) | 48, and 6 driftwood |
| | after | 24 | 4 | 2 (Palm_14, 6 hours apart) | 8 |

In 3 hours of rain held heavy, the code before felled a palm at every one of 33 bolts. The code after felled 7 in the
middle and 2 by the house.

**A run like 2026-11-08 would now make about 34 logs instead of 106:**
- the weather's lightning, about 10 instead of 52;
- driftwood, 0 instead of 19;
- the axe, 11 instead of 22, if Godling fells the same 11 palms (it will likely fell more, with fewer logs about);
- the viewers' drops, 13, as before.

## What a house costs now
The benchmark house (`house.py`, ADR-019) is a room two cells by two, with walls three blocks high round it (11 wall
cells, corners too, and a doorway). Over it is a roof layer of 6 logs and 2 blocks.
- **All in logs:** 11 logs stood on end for the walls (one fills a wall cell three blocks high) and 6 for the roof,
  so 17 logs and 2 blocks at the least. The working figure is about 21, allowing for pieces set wrong or burned.
  - At one log a palm, that is **17 to 21 palms**, 68 to 84 blows of the axe. It was 9 to 11 palms.
- **Stone walls, log roof:** 33 quarry blocks (99 blows of the hammer) and 6 logs, so **6 palms**.
- **Supply is no limit.** The island has 94 palms, and each regrows 10 minutes after it is felled. 11 stand 12 to 45
  from the island's middle, and the inland groves hold 7 each. The storms' and the viewers' logs come on top.

The cost is the walking and the hauling, which the body does well. How deepseek-flash plans with scarcer logs is for a
live run to show.

## Not a move toward guided construction
These rules change what the world gives, not how Godling builds. Nothing says where or what to build. The new prompt
line is a plain fact of the world, like "a hammer breaks stone off the quarry".

## Tested
Each test below was written first, and failed on the code before:

| Test | Fails before the change with |
|---|---|
| `test_build`: an axe fells a palm into one log | `StrikeFelled:Log_1,Log_2` |
| `test_life`: the weather over nine days (no `DRIFTWOOD`, no `Driftwood` piece) | a log washed up |
| `test_life`: with no palm in range, the bolt strikes the sea or open ground. There it scorches, hurts a body 3 from it by 35, and leaves Godling 28.5 away unhurt | it fell back to the nearest palm beyond 45 |
| `test_life`: 3 hours of rain held heavy, island's middle. Bolts keep coming (22 at least); palms fell at least 25 minutes apart, at most a quarter as often as bolts, never the same one twice. By the run's house, Palm_2 and Palm_14 fall once each | 33 fellings |
| `test_life`: a palm the storms felled is spared 6 hours after it grows back, then may be struck again | no spared palm |
| `test_attention`: a log marked `Driftwood` is a new object | "A log washed up on the beach" |
| `test_mind`: the prompt never says logs wash up, and says the axe gives one | "which sometimes wash up on the beach" |

The viewers' Storm keeps its own test (`test_sky`: a palm beside a spot falls into two logs). Its bolt and scorch now
come from the same `sky.bolt` and `sky.storm.scorch` as the weather's.

## Not done
- **No live run has tried this yet.**
- **Restarts forget which palms the storms spare.** That is held in the world script, not in the island save. After a
  restart a palm could be felled sooner than 6 hours after the last time.
- **The viewers' Storm and the meteor still give two logs a palm.** Lowering them too would change a paid power's
  description: its text in `world/viewer/viewer.js`, and a data migration in `web/apps/credits`. That is the user's
  call.
- **Sample feed text.** `mind/tests/feed.json`, `world/renderer/test/viewer.test.js` and the landing prototypes in
  `web/prototypes/` still use "A log washed up on the beach" as sample text. They test the feed's format, not
  driftwood. The live landing page's sample line now reads "It has started to rain".
