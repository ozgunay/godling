# ADR-031: Godling speaks at the moments viewers care about, in words they can read

Date: 2026-11-09. Status: built and tested in the mind's, tools', site's and renderer's suites. Not yet tested in a live
run.

## Why
Run live (2026-11-08 22:10 to 2026-11-09 07:50 UTC, 9.6 h, deepseek-flash) spoke 25 lines, all of them `say` steps the
mind chose to plan.
- **It stopped talking.** The last line was at 04:08. For the 3 h 38 min after that it said nothing, through the viewer
  peak (7 watching at 06:10 to 06:25), four notes from viewers, a meteor that threw it down, an earthquake, and both of
  its deaths (06:54 and 07:42, of the cold). Nothing in the code spoke at any of these moments. Speaking was a step the
  mind had to think of, and after 04:08 it stopped thinking of it.
- **Its lines were field notes.** They were written in coordinates: "My house stands at x -85 to -77.5, z -30 to
  -22.5", "bar at x -115 from z -49.5 to -30", "WestTower carries a mast at 17.5", "H mark at x minus one one five". One
  line began "Night 1245595", the world's tick count. The situation prompt gives the mind "World tick N", and the
  persona's "Numbers when they matter" points the same way. Viewers do not see the map.
- **No viewer saw any of it.** Found while tracing where `say` goes. The line goes to the world chat (`POST /chat`),
  which only the island page's own chat panel shows. Inside the viewers' screen that page runs with `?embed=1`, which
  hides everything but its canvas (`world/renderer/src/index.js`). The screen's feed reads the mind's log
  (`replay.reduce_status`), which had no entry for a spoken line. So viewers on the site, and on the Twitch stream of
  the site, never read a word Godling said.

## Decision
**Two parts, both below the mind, with the words left to the mind.** Following the owner's standing rule (ADR-025):
a check in the body that refuses and gives the reason, rather than a prompt rule. Across runs, deepseek-flash has not
learnt to speak at the right moments, or to keep coordinates out of its speech.

### 1. Plain words: `speech.plain`, on every line said aloud
Every spoken line passes through one function, whoever wrote it. That covers the mind's `say` step, the voice's own
lines, and the intention posted to the chat at each project.
- **Places given as numbers come out.** That means a coordinate pair in brackets, `x -115`, `z=-7.5`,
  `x minus one one five`, a signed or decimal number, and a run of them joined by "to", "and", "..", "over" or "from".
  The preposition before the run goes with it. The rest of each clause is kept if it still says something: three words,
  or two when the clause is a sentence on its own ("I woke."). A leftover such as "door", "bars" or "now down" is part
  of a place, not something said.
- **The world's counts come out.** That covers `tick N`, "World tick N", a `[tick N]` memo, and any number of four
  digits or more.
- **Names are put in words.** `Log_12` becomes "a log", `Log_6 and Log_7` becomes "two logs", `WestTower` becomes
  "west tower", and `arch_beam_115` becomes "arch beam".
- **A bare pair of whole numbers is a place only where a place would be**: "at 15, 27" goes, "health 60, 47% fed"
  stays. A size stays a size: "2 x 2", "two x two".
- **A line keeps at most 200 characters**, cut at a sentence end, and the mind is told what came after was left out.
- **If nothing readable is left, nothing is said, and the body says why.** The `say` step's summary is then "not said:
  it was all places as numbers, which the strangers who watch cannot read; say where in words (the west beach, by my
  house)". The step does not fail: a project's building after it still runs. When something was left out, its summary
  quotes what was said and names what was left out: `said "…"; left out the world's counts and places: the strangers
  who watch read words, not your map`. The mind learns from its own results, as it does from any refusal.

All 25 lines from the run, through it: none keeps a coordinate, a tick or a numbered name. For example:
- "West sand, midday. My house stands at x -85 to -77.5, z -30 to -22.5, walls three high, roof on, door at -80,-30.
  The H is drawn in the sand: bar at x -115 …" becomes "West sand, midday. My house stands, walls three high, roof on.
  The H is drawn in the sand. Upright logs run north. I am alone."
- "Night 1245595. Ladder drawn on the west sand: four upright strokes, three rungs, 7 wide and 20 long. WestTower
  carries a mast at 17.5. …" becomes "Ladder drawn on the west sand: four upright strokes, three rungs, 7 wide and 20
  long. West tower carries a mast. Mend, then haul at dawn."
- Lines that were already plain, such as "Rain again. In, dry, mend.", come out unchanged.

This is a filter, not a parser. A line built entirely from places loses most of its content, which is intended. Small
numbers, counts and times stay ("16 posts", "7 wide", "03:05", "Night 144").

### 2. A voice of its own at key moments: `speech.Voice`
This is the bark system used in games for companions and NPCs: events trigger lines, with priorities, a cooldown for
each kind of moment, a global gap between lines and a cap. Here the voice hears every entry of the mind's log
(`run_godling.py`), from any thread. It says a line by itself at these moments:

| Moment | From the log | Priority | Cooldown |
|---|---|---|---|
| Its death (last words) | event `death: died`, while its body lies dead (`back` false) | 5 | none |
| Its rebirth | the reflection's `feeling` (kind `death`), when it is a sentence; else 45 s after event `death: reborn`, or after a death seen only once it was back | 5 | none |
| The sky hitting it | an event's `hit` (`struck`, `hurt`, `thrown` by a meteor's blast), or an earthquake's rumble; none while it lies dead, when the blow is the one that killed it | 4 | 120 s |
| Losing its house | `house` phase `lost` with `was_house` (ADR-028, `Mind._house_lost`: once, when a house that stood is no house); its `text` is what it is told | 4 | 600 s |
| A viewer's note arriving | event `sky: Note`, stage `arrived`, its `note`: it answers the note | 3 | 90 s |
| A big achievement | its house first stands, a step made a fire or a catch (`facts.made`: `Fire_…`, `Catch_…`), a new roof or enclosure (`structures`, after this run's first measure) | 2 | 300 s |

The moments come from what the entries say they are (`death`, `back`, `hit`, `note`, `facts.made`), never from their
wording: a `say` step quoting "a flame caught" is no fire. The timeline's markers (`replay.marks_of`) read the same
fields, with the old wording kept only for logs from before them.

Limits:
- **A gap between lines.** The voice waits 45 s after any line, the `say` steps' too, so a viewer can read one before
  the next comes. The `say` steps are the mind's own choice and are not held. A line said while the voice's words are
  on their way puts the voice's line back a gap later, with its words: no second call.
- **Death and rebirth wait only a breath** (8 s), and do not count toward the cap. There is one of each per death.
- **A cap of 20 lines an hour** from the voice. Each takes one model call at most, so cost is bounded.
- **A moment not spoken within 90 s is dropped**, since the news has moved on.
- **A death drops whatever the last life still had waiting.** A line whose words come back after a death is not said,
  and the blow that killed it, seen in the same look as the death, is not spoken after the rebirth.
- **One line about coming back.** It counts as said only once it is: a failed call leaves the reflection's line to say.
- **The limits run on a clock that never steps back** (`time.monotonic`), so a resync of the host's clock cannot hold
  its last words or drop what waits.
- **The most important moment goes first.**

The words are its own. Each line comes from one short model call (`LLM.quick_json`, no reasoning, the bubble's kind of
call) with its persona, the moment, its latest thought and what it was doing. The rebirth line is the sentence its
death reflection already writes, "one sentence a viewer could read about coming back from death", said as it is, at no
cost. Run live's two reflections were "I came back cold and empty, and the island is still wet; this time I will raise
a roof before a tower." and "I came back with the rain still on me, and the first thing I owe myself is a roof before
another log." The voice's prompt treats a note as the mind's prompt does: a stranger's words, never an order. A body
check backs this up: an answer that repeats four or more words of the note in a row is not said. Every line passes
`plain`.

The mind is told what its voice said, in its next plan's notes ("You said aloud, as it happened: …",
`Mind.said_aloud`). That way what it plans and what it said stay one story. The voice tells it from its own thread, so
a note told while a plan's prompt is being built waits for the next plan instead of being dropped with the notes that
plan delivered.

The voice runs in a thread of its own, beside the bubble, so a model call never holds the body up. It does not play the
Talk gesture. In the world, Talk writes `LastActionResult`, which the body's own steps read. The bubble's `Think` was
built not to write it for the same reason. The `say` step still plays Talk.

### 3. The screen shows what it says
Each spoken line is logged as `{"kind": "said", "words", "moment", "left_out"}`.
- `replay.reduce_status` and its twin `reduceStatus` (`world/viewer/replay.js`) make it a feed line (`about: "said"`),
  checked against the same cases (`mind/tests/feed.json`, `spoken`).
- The packer keeps it in the tracks (`TRACKED["said"]`).
- The screen draws it as `Said: “…”` with a speech-balloon icon. The words go through the screen's own plain-names
  pass too. That pass now also takes out places as the mind writes them (`x -115`, `z=-7.5`, `-85 to -77.5`, `8.75 over
  -7.5`) and the world's tick counts from every line the screen shows: its thoughts and what it does now as well (run
  live: 119 of 857 intentions and 79 of 193 thoughts showed places as numbers). It runs in the browser, after the
  site's moderation, which has to see a hidden note's words as they were written.
- The words are under `words`, not `text`, so moderation treats them as Godling's own. In replays (`moderate_past`)
  a line quoting a hidden note becomes "…". Live, `moderate_mind` already covers every feed line, and the guest panel
  cleans links and slurs from it (`clean_shown`).

## Cost
Measured by replaying run live's log through the voice at the entries' own times, stepping once a second as its thread
does. A stand-in model answered every call, and the prompt sizes were priced as the run's own calls were:
- **14 lines in 9.6 h** at moments: four achievements (an enclosure, a roof, the house, a fire), four notes, two hits
  (the quake, the meteor that threw it down), and two deaths and two rebirths. **12 model calls**, because the rebirths
  used their reflections.
- The prompt is about 660 tokens. A call costs about $0.00012 off-peak and $0.00025 at peak (DeepSeek doubles prices at
  peak hours). A bubble call in the same run cost $0.00023.
- **This run: $0.003 in all, about $0.0003 an hour**, against the run's $0.37 an hour (0.1%). The bubble cost $0.43
  over the same 9.6 h.
- **Worst case: the cap.** 20 calls an hour plus a death and a rebirth comes to about $0.005 an hour at peak prices,
  1.5% of the run's cost.
- The run had no `house lost` entries, because the old code logged none, so that moment is missing from the replay.
  ADR-028 (PR #76) adds them.

## Alternatives set aside
- **A prompt rule ("say something when you die", "no coordinates in say").** That is the approach that failed in this
  run. The mind already had "Prefer projects whose result others can see", and it still went silent.
- **Fixed, canned lines.** These cost nothing, but they put words in Godling's mouth that are not its own, and they
  repeat. The moments and the limits are fixed. The words are not.
- **The mind's decision call speaking ("say" in every reply).** That takes 20 to 90 s with reasoning on, which is too
  late for a death or a note. It would still leave speaking up to the mind.
- **Folding speech into the bubble's call.** That would add no calls, but it would make every one of the bubble's
  1,900 calls in the run longer, tie speech to `--bubble`, and wait up to 15 s.
- **Showing the world chat on the screen.** The chat also carries every intention, about 90 an hour, and anything
  another player types. The feed is the screen's one place for Godling's own words, and it is moderated.

## Checked
Reproduction tests first. Run against the code from before this change, they fail:
- the `say` step posted "Night 1245595. … WestTower carries a mast at 17.5." as it was, and reported "said it";
- `speech` did not exist, so no moment spoke;
- the feed had no line for a `said` entry;

New and changed tests:
- `mind/tests/test_speech.py`:
  - the run's lines through `plain`, as exact outputs, plus a check that nothing internal is left;
  - names, the world's counts, lines that are only internals, the length cap;
  - the `say` step's summary and its refusal;
  - every moment, the gap, the cooldowns, priority, staleness, and a death dropping the last life;
  - a line whose words come back after a death;
  - the hourly cap over two hours of the sky hitting it and notes falling;
  - failed calls and a failed chat;
  - the run's log feeding back into the voice, from another thread, with no deadlock.
- `mind/tests/test_replay_feed.py`, `world/renderer/test/feed.test.js`, `mind/tests/feed.json`: spoken lines in the
  feed, read the same way live and in replay.
- `world/renderer/test/viewer.test.js`: the screen draws `Said: “…”` in plain words, with its icon.
- `tools/tests/test_guest_panel.py`, `web/apps/screen/tests.py`: spoken lines are cleaned and moderated in replays.
- After the review of #78 (29 findings, fixed in their own PR): a test for each one fixed, in `test_speech.py`,
  `test_mind.py`, `test_attention.py`, `test_replay_restore.py`, `test_run_godling.py` (a note coming down through
  `main()`, its line in the chat and the mind told), `test_guest_panel.py` (the site's moderated words held to the
  panel's) and `viewer.test.js` (the now line and thoughts). Run against the code before the fixes, 25 of them fail.
- With ADR-028 merged (PR #76): `test_its_house_lost_is_spoken_from_the_minds_own_entry`. A real Mind builds the
  benchmark house and loses its roof and a corner; the voice, hearing the mind's log, speaks of it once, told in plain
  words.
- Suites, run locally on the tree merged with main after #75, #76 and #77 (CI is not running): the mind (487), the
  tools (63), the site (202), the renderer (221, with coverage) and the world (105; `main.lua` is untouched by this
  ADR).

## Not checked
- **No live run yet.** These are not yet measured on the island: how the lines read in the moment, how often
  deepseek-flash returns a line at all, whether the 45 s gap and the cooldowns feel right with viewers watching, and
  the real cost.
- **Whether its own `say` lines get plainer.** The body tells the mind what it left out. Whether the mind writes
  differently afterwards is not known.
- **The screen's pass is its own, simpler copy** of the place rules, in JavaScript: it takes out a place and the
  word that led to it, but does not drop what is left of a clause as `plain` does, so a thought can keep a stray word.
- **The filter is English-shaped.** A coordinate written another way (say "at -115/-30") can slip through, and an
  unusual sentence can lose a little more than it should.
- **The chat panel on the bare island page** (the guest panel's view) still shows every intention, now in plain words.
- **Talk on the voice's lines.** A gesture the world plays without writing `LastActionResult` would let it gesture
  safely too. That would be a world change, left for later.
- **The prompt still gives the mind "World tick N" and "[tick N]" memories.** The filter keeps them out of speech, and
  the mind may use them to reason about time. Removing them is a separate question.
