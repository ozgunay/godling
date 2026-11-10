# Godling's layered mind

The mind thinks about the past and the future; the body handles walking and grasping. Design rationale:
[`../research/layered-mind-design.md`](../research/layered-mind-design.md).

| Layer | File | What it does |
|---|---|---|
| L3 mind | `godling/mind.py` | An LLM decides projects, narrates its intention, writes lessons, teaches itself skills, and sleeps hourly to consolidate memory. Its system prompt states plain facts of the body and the world, such as one log to a palm the axe fells (ADR-026) With `--think-deadline`, while a plan is late it gives the body a stop-gap: one short project, chosen at once without thinking, from what it has thought so far (ADR-030) |
| L2 attention | `godling/attention.py` | Notices new objects, damage to things it kept, visitors and sky events; interrupts for salient events (the Jev slot is `decide`); hands events that happen somewhere to the glance reflex; takes notice of what it is told rather than sees (`notice`: a reflex the body took, the house lost, ADR-028) |
| L1 body | `godling/skills.py` | Moves: walk_to (A* around mesas and objects), pick_up, put_down, place_at, throw, jump, say, wait. They know reach and overlap, not strategy, and keep a standing ladder's top and foot clear (ADR-025). A piece over the head is set from the floor under it, or right beside it as far as the hands reach, and a log resting on its middle (on a wall or a post) is set where it was aimed (ADR-033). Cold and hurt with nothing over it, the body takes shelter by itself (ADR-028). Between steps, and while it waits, the body glances: it turns towards what attention just noticed, without changing the plan |
| house | `godling/house.py` | What a house is, one check for the mind and the build measure (the world's copy is `houseAt` in `world/main.lua`): a room two by two or more, walls, one doorway and a roof (ADR-019); a room wider than two cells holds its roof on posts inside it (ADR-033). The house project's next step and its guided roof |
| voice | `godling/speech.py` | All it says aloud, in plain words: places given as numbers, the world's ticks and numbered names left out or put in words (a `say` with nothing readable left is not said, and the step's result says why; the project goes on). It also speaks by itself at the moments viewers care about: its death and rebirth, losing its house, a viewer's note, the sky hitting it, a big achievement; one short model call each, with a gap, cooldowns and a cap of 20 an hour (ADR-031). What it says shows in the viewers' feed |
| learned skills | `godling/learned.py` | Skills the mind defines from body moves: declarative, verified in the world before they count as "proven", persisted. Under every memory engine, a skill that has worked keeps its steps (no forgetting, no other steps under its name) until it has failed, in a row since it last worked, as many times as it has worked (at least 3), or has gone 2 hours without working; the library refuses other requests and tells the mind why. Runs that attention cuts short are not counted (ADR-032) |
| memory | `godling/memory.py` | Episodes (with world ticks), intentions, kept structures, digest; follows the plan's MemoryAdapter interface (§10.6). Opening a memory from before a change to the world retires, once, the lessons it made untrue (`RETIRED`; ADR-026: logs that wash up, two logs a palm) |
| house site | `godling/site.py` | Tells the world, with the input `HouseSite`, every cell the house the mind is building needs (what the body keeps clear, `reserved_cells`, with its walls and the cells round its way out), so the sky keeps viewers' gifts off them (ADR-029). Sent at each cycle when it changed, and right after a plan chooses, moves or gives up the house; it changes nothing the mind or the body does |
| world | `godling/world.py` | HTTP client for Clawblox and a compact reading of observations |
| LLM | `godling/llm.py` | DeepSeek (OpenAI-compatible endpoint), JSON replies, cost per call. A reply that thought but gave no whole answer (the token cap, a stream that ends or breaks early) is answered from the end of its reasoning, without thinking again, and that answer is never forced in turn (ADR-030) |

## Run (inside WSL)

```bash
python3 /mnt/c/Work/godling/mind/run_godling.py --run-dir ~/godling-runs/m-002
```

What happens:
- It starts Mesa Island with recording on port 8080, prints the spectator link, joins as Godling, and prints THINK / INTEND / DO / SAID / LEARN lines as it goes.
- **Ctrl+C** stops the mind and the world together.
- The DeepSeek key is read from `DEEPSEEK_API_KEY` or `~/.claude-deepseek/settings.json` (written by `tools/setup_deepseek.sh`).

Useful flags:
- `--model deepseek-v4-pro`: a stronger mind (about 5× the cost).
- `--minutes 60`: stop by itself after an hour.
- `--gifted-skills`: also offer ready-made `stack_on`/`build_tower` (the comparison arm).
- `--no-narration`: don't post intentions to world chat.
- `--no-voice`: no lines of its own at key moments (ADR-031); its `say` steps are still said in plain words. On, it costs about $0.0003 an hour (run live replayed) and at most about $0.005.
- `--attach`: use a world that's already running. If that world asks for a join key (`patches/v2`, ADR-014), export its `WORLD_AGENT_KEY` first. A run that starts its own world makes a fresh key and keeps it in `<run>/world.key`.
- `--guest-panel 8081`: also serve the guest panel at http://localhost:8081/. It shows the live view, what Godling thinks and needs, and buttons for the sky powers (stone, log, regrow, lightning, meteor). Free in test mode. It also runs on its own: `python3 tools/guest_panel.py --world http://localhost:8080 --run-dir <run>`.
- `--relay 8082`: stream the island to viewers through the relay (`relay/`, ADR-015; build it first with `cargo build --release` in `relay/`). The world gets a spectator token the relay shares, and the guest panel's island streams from the relay: one connection to the world however many watch, and pages that reconnect pick up where they left off. With `--attach`, export the world's `WORLD_SPECTATOR_TOKEN`.
- `--sky-test-minutes 10`: drop a meteor near Godling every 10 minutes, its shadow 40 s ahead, to measure reactions without anyone at the panel.
- **The house's site, kept clear** (ADR-027): while Godling builds a house, the hands set nothing down on purpose in
  its room, doorway or way out, nor on the ground a cell wide round its walls (but a block on its own, as a step, or a
  ladder), and in a wall only a building piece along the wall's line or stood on end; each refusal says why. What the
  body sets aside to free its hands goes nowhere on the site, nor on the way in to the doorway unless nothing else is
  clear; with nowhere clear in reach it carries the piece off the site and says where it went. A piece lying across a
  wall, out of its line, is in the house's way, not its own, and the house's next step names it. Once the house stands,
  only what is set aside keeps out of its room, doorway and way out. `nearest_free` as `pick_up`'s object takes the
  piece in the hands when it is of the kind asked, else the nearest the body can walk to; `pick_up` walks round what it
  goes to; a walk that sticks says what stopped it.
- `--think-deadline 20`: when the body has stood idle this long waiting for its next plan, it takes a stop-gap. That is one short project, at most 4 of the body's own moves, which the mind chooses at once, without thinking, from the plan's prompt, the world as it is now and what it has thought so far. A longer one, or one with a learned skill, is refused, never cut. The next comes as soon as one ends, up to 3 per plan. A stop-gap moves the body only: what it would remember, learn or keep waits for the plan, and it never clears the plan's recent failures. The plan, when it comes, is taken up when the stop-gap's project ends. It is dropped only on a death or an interruption of a planned project, as before; something salient during a stop-gap ends only the stop-gap. The shelter reflex is the exception: when it walks the body under a roof, during the wait or a stop-gap, the plan is dropped (ADR-028), and no stop-gap is asked while the cold is a danger. Off (`0`) by default until the experiment in ADR-030 has judged it: the body waits, as before.
- `--reasoning-effort low|high|max`: how hard each decision thinks (DeepSeek `reasoning_effort`). Unset: the provider's default, high.
- `--reasoning-budget 32768` (the default): the tokens a decision may spend on reasoning and answer together. A decision that reaches it is answered from what it has thought so far.
- **The shelter reflex** (`skills.take_shelter`, ADR-028): cold with nothing over it and its health below 35 (but not by a fire on a dry night), the body walks to the nearest roof it knows within 80 units (one it felt over it, or a piece it sees lying high enough, checked to be there still; a house it has stood in comes before any plain roof) before it carries on. Cold under a roof at night, it walks on into a house it knows. The step returns `interrupted: ...`, so the agenda is dropped and the mind plans from under the roof, told why. It runs with the other reflexes on one look (`skills.reflexes`): between steps, between a learned skill's own steps, while waiting, and while the mind thinks, when the plan being thought is dropped too. Where the rain still reaches it, it tries the next roof (three at most); a roof it could not get to is tried again a minute later. With none known it says so once, as news, and the step goes on. After it took shelter it lets the mind take it out again until its health has fallen 10 more (at once if the roof over it is knocked away); the danger is over at 50, or once it stands in the open in dry weather, not cold. Walks to a roof, a learned walk home, eating and speaking are let go, and the hourly sleep waits while the cold is killing it. Logged as `kind="reflex", reflex="shelter"`.
- **A lost house is told** (`Mind.house_progress`, ADR-028): when the house stops being a house, or pieces it had are gone, the mind hears it at once: news for attention, a line about the house in every plan while it lasts, an episode for the next sleep and an addendum after the digest ("Since you wrote that: ...") until then. A quake that only wakes the house's pieces is no loss. Logged as `kind="house", phase="lost"`.
- **The brace reflex** (`skills.steady`): when the Clock says the ground is rumbling, the body looks around for about 2 s (the world plays LookAround), then sends `Brace` and holds on until the world lets go. It runs between steps, while waiting, and while the mind thinks. The rumble is a salience-5 event, so the step in progress stops; the mind is told how quakes work and hears of one in its next plan. `analyze_run.py` reports each quake: pieces woken, moved and fallen, how soon the body braced, and knock-downs.

Each decision also carries a `needs` line (what the agenda is short of, with counts) for the panel. `analyze_run.py` reports reactions to sky events: applied, noticed (a glance or mention within a minute), named in a thought or intention, and engaged.

Analyze afterwards:
```bash
python3 /mnt/c/Work/godling/tools/analyze_run.py ~/godling-runs/m-002
```
It reports the world-side numbers plus the mind's calls, cost and skill success. Raw logs: `<run>/mind/log.jsonl`. Memory and learned skills: `<run>/memory/`.

Replays (ADR-016): beside the world, `python3 -m godling.replay follow <run>` packs its recording into `<run>/replay/` as it grows (its log: `<run>/replay.log`); the guest panel and the site serve it, and the viewers' screen plays it (Rewind). `python3 -m godling.replay check <run>` compares replayed moments with the raw recording.

## Test results so far (2026-11-01, deepseek-flash)

| Run | Setup | What happened | Cost |
|---|---|---|---|
| Body only, no LLM | `build_tower` scripted | 12-high tower in 30 s; routing, mesa refusal and reaching from below all pass (7/7) | $0 |
| m-test3, 5 min | body moves only, no physics hints | Worked out block height from experience (0.37 → 1.12 → 1.87), built a 12-block tower, found its reach limit (~9 units) by testing, taught itself 7 skills (one proven, broken ones forgotten) | $0.028 |
