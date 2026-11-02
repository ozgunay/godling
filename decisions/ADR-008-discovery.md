# ADR-008: Godling discovers the island by walking it

Date: 2026-11-02 (morning). Status: built and tested live; first run n7.

## Why
To show Godling where the beach was, the mind's prompt had been given a map of the whole island (ADR-007). You pointed out that this gives the island away. Godling should have to walk around to discover it.

## What was built
`mind/godling/discovery.py`, fed by every observation through attention:
- **Ground.** Map cells (10 units) within sight (35 units) of where the body has stood become known.
- **Landmarks** become known once seen. Tall ones (20 or higher: the peak) are seen from anywhere, as a mountain would be. Palms are known one by one.
- **Objects** (blocks, tools, coconuts, the volleyball) enter the mind's view once Godling has been near them. Their positions are then shown as they are now.
- **The mind's map** marks unseen cells "?". Its heading says: you know only what you have been near; walk to see more.
- **Persistence.** What has been seen is kept in `memory/discovery.json`, so a restart of the mind does not forget the island.
- **The body is unchanged.** Its legs still route over ground the mind has not seen; only the mind's knowledge is limited.

## Tested live
- At the raft, Godling knew a patch of beach and grass, the raft, the near palms, the starting blocks, the volleyball and the peak; the rest of the map was "?".
- Walking to the camp and the quarry revealed that strip and the quarry. It then knew 17 of the 19 loose objects.
- A reload from disk gave the same knowledge.

## Not done
Both done since, in ADR-009: rock now blocks the line of sight, and things are remembered where they were last seen.
