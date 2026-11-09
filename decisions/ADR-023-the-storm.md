# ADR-023: The Storm takes Lightning's place: three aimed strikes that can hurt, never kill

Date: 2026-11-06. Status: built and tested (world, mind, panel, site, screen, renderer); checked on a local island in
WSL. Not yet in a live run.

## Why
Lightning cost 40 credits and only felled the palm nearest the aim into two logs (a Log costs 4). It could never
touch Godling: it struck only palms at least 9 from it, and its harm reached 7. So nothing happened to watch, and a
storm of the weather's own did the same for free. The user chose a storm on demand instead, with strikes the viewer
aims, and asked that a strike on Godling truly hurt it, visibly, but never kill it.

## Decisions (the user's, 2026-11-06)
1. **The Storm replaces Lightning on the panel, at 400 credits** (a disaster: it can hurt Godling). Lightning stays a
   power the world knows, and storms of the weather's own still strike palms near Godling, harmlessly, as before
   (since ADR-026 most of their bolts strike the ground instead).
2. **The viewer picks three strike spots**; the sky picks any left out (palms 12 to 45 from Godling, else open ground
   there). **The world picks when, and in which order.**
3. **The sequence:** 30 s of warning (the sky darkens, a gale, the three spots crackle on the ground, and Godling
   notices where), then about two and a half minutes of heavy rain (slowed, soaked, fires out), with the strikes 20 to
   50 s apart, each spot flaring 1.5 s before its bolt. No driftwood after.
4. **A strike on Godling** (within 2.5 of its spot as it strikes): health drops to half a heart (5), or stays lower if
   it was. Godling is knocked down, electrocuted for 1.5 s (a blue-white flicker, arcs crawling over it, a shake), then
   charcoal black for 60 s, with smoke at first, turning back to its own white over the last 10 s. The bolt ends on its
   head.
5. **Close by** (within 7): 35 health, never below half a heart, and a knock-down. **A palm** beside a spot (within 3)
   is felled into 2 logs: the strike still gives supplies. **Open ground** keeps a scorch for 4 minutes. **What Godling
   built is never broken.** **A roof over Godling takes the strike.**
6. **It never kills.** The disasters' mercy rule holds (not while health is under 30, nor within 15 minutes of a death,
   ADR-022), one storm at a time, at most one every 30 minutes; a refused call is refunded. A death can still follow, of
   the cold and the soaking after a strike: the chain the mind should learn from (ADR-022).

## How
- **World** (`main.lua` THE STORM, `sky.storm`, a closure: no new main-chunk local). `tickWeather` is a callable table
  with `hold(level)`, so a storm called down holds the rain at 1 (and the weather's own strikes wait). The Clock carries
  StormPhase, StormId and StormSpots; StormSpot parts (Charged before their bolt), SkyBolt markers as Lightning's, and
  Scorch parts. The body carries Struck (a count) and Scorched (seconds left), mirrored for the screen.
- **Mind:** "Dark clouds are rolling in fast: a storm is coming. The air crackles at (x, z), (x, z) and (x, z)"
  (salience 5); the storm breaking, and passing; "Lightning struck you: you are burned and hurt" (salience 5, its own
  timeline mark); close by, "hurt by lightning striking close by". The most salient event names an interruption.
- **Panel and site:** POWERS and texts; `/api/power` takes `spots` (up to three good [x, z]); a migration adds the Storm
  (400, Disaster, harms) in Lightning's slot and switches Lightning off; a PowerCall keeps its spots.
- **Screen:** the Storm in Lightning's slot; aiming takes three clicks, each marked on the island, "Let the sky choose
  the rest" sends those picked so far; a "Burnt" state while charred; timeline marks for a storm and a strike.
- **Renderer:** `stormspots.js` (crackling rings that flare), `bodylook.js` (death's fade and glow, now with the
  electrocution and the char), the Storm's aim ring (red on Godling), and Scorch drawn as a burn on the ground.
