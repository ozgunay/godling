# ADR-020: The sea drowns; the beach's edge gives the body back; the start spot moves to the middle meadow

Date: 2026-11-05. Status: built and tested; not yet deployed or measured live.

## Why
In the live run of 2026-11-05 Godling ended up in the sea, on stream, and could not get out. The run's logs and replay
show how (all times UTC):
- **21:56:09:** snagged by Log_3, the body's reflex stepped 2.5 units straight away from it (`_unstick`), to
  (-120.2, -44.8). That point is past the end of a sand strip, over open sea. The body dropped from y 2.45 to 1.68:
  its capsule caught on the sand's lip and hung there.
- **21:56–22:01:** two more steps away (from Log_25) moved it along the lip. Every walk failed "stuck N short": the
  body cannot climb back onto the sand from the lip.
- **22:01:34:** the next walk slid it off. It fell to y -1.85, beside the island's sheer edge. The ocean does not
  collide, and the sea has no floor near the shore.
- **From then on**, every action failed within a second: "fell off the edge into the sea". `_move_once` stops at
  y < 0.8 on its first look, so the body never took a step. The world had no drowning, so it would have stood there
  until hunger or the cold made it faint, about an hour. The cold took health from 95 to 66 meanwhile.
- **22:15:** the user had the run restarted (the old one is kept at `/runs/old/20261105-221535`).

The user also noticed that Godling keeps close to where it wakes. By the raft, that is the beach, whose edge is this
drop.

## Decisions
The user chose each of these.
1. **The sea drowns** (`main.lua` THE SEA, `sky.tickSea`):
   - In the sea means the feet are below the water's top, with no ground under the body or a lip just beside it.
   - There the body loses a whole body's health in 90 seconds (`DROWN_SECONDS`).
   - At none it faints as a starving body does: what it holds drops, and it wakes at the start spot, half fed and weak.
   - `Drowning` is set meanwhile, and is copied to the Clock for viewers (`GodlingDrowning`); `Drowned` counts the
     times; the world log says `DROWNED`.
2. **The beach's edge gives the body back.**
   - A body hanging on a lip counts as on the edge: no ground under its middle, and sand within 1.2 units whose top
     is at most 1.6 above its feet.
   - After 3 seconds there (`EDGE_SECONDS`), the world puts it on the nearest spot where the whole body stands on
     that floor and fits, as it frees a body caught inside a piece.
   - If there is nowhere safe to stand, it drowns while the rescue retries every 3 seconds. A later safe landing
     still gives it back to the shore and stops the drowning.
   - `Ashore` counts the times, and the log says `ASHORE`.
3. **The step-away reflex keeps to the floor** (`skills._unstick`).
   - It steps only where the whole body stays on its own floor, all the way.
   - If straight away is the sea or a drop, it turns 45°, then 90° along what snags it, never into it.
   - If no direction is safe, it stays put and says "no floor to step away onto".
4. **The mind is told.**
   - Falling in now says the body cannot climb out, that it is drowning, and that it will wake at the start spot.
   - Slipping in and having drowned are salience-5 notices: they stop the plan in progress. Being put back on the
     sand is a quieter one.
   - While in the sea, the body's feelings say so.
5. **The start spot is the middle of the island's widest open meadow**: (15, -27.5), the "middle" meadow that
   `make_island.py` already kept palm-free.
   - Godling starts there, and wakes there after fainting.
   - The raft and everything else stay where they were; the cell beside the raft stays reserved, so no palm moves.
   - The persona's first line now says Godling woke in a meadow in the middle of the island, with the raft on the
     west beach.
6. **Viewers see it.** The screen shows "Drowning" beside "Cold" (the guest panel, the replays and the viewer).

## What was not changed
- **The sea itself:** no seabed, and no climbing back out. A body in the water drowns, by the user's choice.
- **Other routes to the edge:** routes (`_route`) already keep to the floor. A straight walk with no route known
  could still reach the edge in principle; the lip rescue and drowning cover that.

## Tests
- **`world/tests/test_sea.luau`:**
  - the live run's lip at (-119.8, -44.8) is put back on the sand after 3 s, with ground under the body's whole rim;
  - standing or hopping by the water is left alone;
  - the live run's spot in the water at (-117.3, -50.2) drowns at about 1.1 health a second, shows on the Clock,
    faints and wakes at the start spot;
  - deep water drowns too;
  - the guest panel's parked body never drowns;
  - a climbing body is left to the world;
  - a lip with nowhere safe to stand still drowns the body until it faints;
  - a failed lip rescue retries when a safe landing appears, and the drowning stops ashore.
- **`mind/tests`:**
  - the step-away at a beach edge goes along the beach, refuses a strip too small to step on, and slips out of a gap
    on the landward side;
  - the sea's notices, the feelings line, the body's attributes, and the new "fell into the sea" words.
- **Viewer, panel and replays:** the "Drowning" state.
