# ADR-009: Getting unstuck, a bigger island with meadows, sky harm, sight, and a thought bubble

Date: 2026-11-02. Status: built and tested live.

## Why
Run n7 (the first run with discovery) showed four problems:
- **Most of the body's waiting came from being stuck.** The body waited for the mind 85 of 169 minutes, although the mind already plans the next agenda while the body works (ADR-002). 78 of those minutes followed a plan being thrown away. Of the 151 interruptions that threw plans away, 147 were the body's own "stuck".
- **The body built itself into places it could not leave.** 165 of 400 projects (41%) were attempts to get free. In the worst case, Godling threw a log across two 2-block stacks while standing between them. The engine's body is a capsule exactly 5.0 tall, two blocks, so the log settled 0.05 into its head and pinned it for over half an hour.
- **"Hemmed in" was often wrong.** The body reported it whenever a goal could not be reached, even when only the goal was closed off (it lay inside a block) and the body stood in the open.
- **Fire seldom caught.** Of the kindle failures, 11 were rubbing a log that was already burning, and 8 gave up after six rubs at a flat 1 in 5.

You asked for the rest:
- **Sky events that hurt.**
- **Sight that the mountain blocks**, with things remembered where they were last seen.
- **A bigger island**, with empty areas to build in.
- **A thought bubble as in The Sims**, read by a second small model call, showing a picture of the thing with a mood-tinted rim.

## What was built
### Getting unstuck
- **Stuck is a failure, not an interruption** (`skills.Stuck`). Only what attention notices (damage, visitors) still interrupts and throws away the plan being thought up. A stuck step fails like any other, and the plan in the making is kept.
- **The world frees a pinned body** (`freeTrappedBodies`, main.lua). A body found inside a held piece on two looks in a row, 0.5 s apart, is moved to the nearest spot where it fits. The check covers from just above the feet to just over the crown: with anything touching its head, the character controller cannot move at all.
- **Beams overhead count.** The router treats as in the way anything whose underside is lower than the body is tall. A beam on two-block posts is a wall to walk round; a doorway needs three-block posts.
- **True pens and closed-off goals are told apart.** The body flood-fills the floor it can reach (`_pen`). If that floor is small and closed, it says what pens it in, and lifts its way out: it lifts a bare piece of the pen wall, steps through the gap and sets the piece back. If its hands are full, it first rests what it holds on the wall and takes it back from outside. Otherwise it says why the goal cannot be reached: it is not on this floor, it lies inside a piece, or it is closed off by named pieces.

### Fire
- **The wood warms with each rub.** A rub catches 1 time in 10 at first, rising by 6 points each rub in a row, so the sixteenth always catches. Left alone for 30 s, the wood is cold again.
- **The body keeps rubbing** for up to 18 rubs.
- **A log already burning counts as done.**

### Sky harm and healing
- **Lightning hurts.** It strikes a palm, and anyone within 7 units of the trunk loses 35 health.
- **Falling stones hurt.** A stone from the sky hurts anyone within 6 units of where it lands: 45 health. It still never lands on anyone; it waits for its shadow to be clear within 3 units.
- **Fed, the body heals.** At least half fed, it mends from nothing to whole in about 30 minutes. At no health it faints, as from hunger.
- **The mind is told the basics and notices it.** It knows that the sky hurts when close and that it heals when fed. It notices being hurt (salience 4) and being pushed out of a piece.
- **The guest panel's "Sky" player no longer starves.** In n7 it fainted three times, and each faint parked it by the raft.

### Sight and memory (ADR-008, continued)
- **Rock blocks sight.** The mountain and the hills hide ground and things behind them. The line of sight from the eyes (4.5 above the feet) is checked against the rock every 2 units.
- **Things are remembered where they were last seen.** Loose things out of sight are shown to the mind at their last-seen place, marked "(last seen there)". When that spot is in plain sight and the thing is not there, its whereabouts become unknown.
- **The mind is shown only what it has seen.** Stacks appear once seen, and fires only while in sight.

### The island
- **About 20% bigger in each direction**, with its shape unchanged: 134 x 142 blocks, up from about 112 x 118.
- **Inland palms grow in nine groves**, with open grass between them. No palms grow in three meadows:
  - around the camp, radius 13 blocks;
  - by the quarry, radius 9;
  - in the middle of the island, radius 14.
- **Counts:** 31 beach palms and 63 in groves.
- **The world's boundary** is 240, and **the mind's map** covers ±200.

### The thought bubble
- **The mind side** (`mind/godling/bubble.py`) reads every 15 s, when something new has been thought, done or noticed. A small call to deepseek-flash, with reasoning off, reads the last 2400 characters of the streaming reasoning, the current intention, the body's state and what just happened. It names one thing from a fixed list of 23 pictures and one feeling from 14.
  - The mind's own reasoning is untouched.
  - A reading takes about 0.8 s and costs about $0.0001, so about $0.02 an hour.
- **The world** (input `Think`) keeps `Thought`, `Feeling` and a `Thoughts` counter on the player. It never touches LastActionResult.
- **The renderer** (`world/renderer/src/bubble.js`) draws a white Sims cloud over the head.
  - The picture is rendered once from the island's own models: a coconut, a fish, a cooked fish, a log, a stone block, a boulder, the tools, a palm, the ladder, the raft and the ball. A tower, a wall and a shelter are made of stones and a log.
  - What has no model is drawn by hand: fire, the HELP sign, a ship, the sea, lightning, a little map (exploring) and the night.
  - The rim is green for glad feelings, red for troubled ones, grey in between.
  - Each new thought pops up, stays 10 s and fades. It is hidden in Godling's own first-person view.
- **The run** uses `--bubble` (on by default); `--no-bubble` turns it off.

## Tested live
All on a test world beside the running night run.
- **Pin:** a lintel set over the body's head in a gate of two 2-block posts. The body was freed after 2.5 s, clear of the lintel.
- **Routing:** the walk to the far side of that gate and back went round it, in 3 s each way.
- **Fire:** caught after 13–25 s of rubbing. Rubbing the burning log again was ok.
- **Lightning:** a palm struck 4 units away took health from 100 to 65.
- **Meteor:** a stone landing 4.5 away took health from 65 to 22.
- **Healing:** +1.1 health in 20 s while fed.
- **Bubble:** a reading of a hungry thought gave "coconut, hungry" in 0.8 s, and the world held it.

A 20-minute smoke run with everything together, on the bigger island, compared with night run n7:

| | n7 (old code) | smoke run (new code) |
|---|---|---|
| Body busy | 47% | 90% |
| Waiting for the mind | 50% of the run | 1.7 of 20 min |
| Plans thrown away | 99 | 0 |
| Fire lit | 16/37 | 9/9 |
| Stuck or penned failures | 147 | 0 |

The bubble updated 74 times, and the run cost $0.32 an hour with it. The bubble showed the right things (towers, blocks, logs, the HELP sign, fire, the ball), but its feelings were mostly the neutral "determined" and "focused".

## Not done
- **The bigger island moves everything.** The camp, raft and quarry have new places, and runs before this one used the old island.
- **The bubble's feelings are mostly neutral.** A prompt that asks the reader for the feeling under the thoughts was drafted but not applied.
