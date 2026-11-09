# God powers and disasters: the plan

Date: 2026-11-02. Status: proposed. Phase 1 (the earthquake and bracing) is built and tested on the branch `claude/disasters-quake-brace` (§5). The renderer session has built its side (Brace loop, camera shake, dust) on its own branch. The art session has built Brace, Stagger, LookAround and GetUp into `godling.glb` on its branch `claude/godling-quake-clips`. Neither is committed yet.

This plan follows on from `reports/God games lessons for Godling.md` and from your answers in that conversation:
- Viewers buy god powers, so each must visibly change the world or Godling, and be fun to watch.
- Each needs cooldowns.
- An earthquake and a tsunami should knock down what Godling builds, on very good physics, with Godling anchoring itself to the ground and animations to match.

## 1. What exists already (main at 9751ced)
| Area | What is there | Where |
|---|---|---|
| Sky powers | Stone, Log, Regrow, Lightning, Meteor, called from the guest panel as the bodiless player `Sky` | `world/main.lua` `SKY_POWERS`, `tools/guest_panel.py` |
| Sky harm | Lightning takes 35 health within 7; a meteor's stone takes 45 within 6. A stone never lands on anyone. | ADR-009 |
| Random events | Showers, wet spells, thunderstorms, morning fog, a ship passing far out (driftwood until ADR-026) | ADR-010, ADR-026 |
| Survival | Hunger, health, fainting at the raft, coconuts, fish, a carved spear, fire by friction | ADR-007, ADR-010 |
| God bot | Calls a sky power at long random intervals during a run | `tools/god_bot.py` |
| Reflexes | A glance at what happens, between steps and while waiting for the mind | `skills.glance` |
| Animations | The world names each action: `Gesture` and `Gestures`, played once. Climb loops while `Climbing`; Jump and Fall loop by the body's state. | `main.lua` `gesture`, `renderer/src/models.js` |
| Settling | Blocks, logs and boulders that come to rest are squared into their cell and anchored (`Settled`). Lifting one wakes what rests on it. | ADR-005, `settleResting` |
| Physics | Rapier 0.25 in Clawblox, server side at 60 Hz. Luau has `ApplyImpulse`, `ApplyImpulseAtPosition`, `AssemblyLinearVelocity`, `VectorForce`, `GetMass`, and buoyancy for terrain water (4-unit voxels) | Clawblox `8be90a0` |

**What this means for disasters:** nothing on the island can fall over today, because every resting piece is anchored. A disaster has to wake pieces first, as lifting does, and let the physics decide what falls.

## 2. Principles
1. **Conditions, never decisions.** Viewers choose the power; the world chooses where and when it lands. The mind never learns who paid.
2. **Every power is watchable in three beats:** a warning (a shadow, a rumble, the sea drawing back), Godling's reaction (a glance, bracing, running), and a lasting change in the world.
3. **Every power leaves something:** material, food, fire, land, or a lesson in how to build.
4. **Harm follows ADR-009.**
   - The sky may hurt Godling when it is close.
   - A quake never takes health; it knocks Godling down if Godling is not braced.
   - A tsunami soaks Godling, and takes a little health only if it catches Godling unbraced.
   - Nothing ever kills Godling outright. At no health it faints, as now.
5. **Refunds are automatic:** a power that cannot happen is refunded (no palm to strike; no clear spot within 5 minutes).
6. **Prices are fixed:** no price that rises with demand. A power that is used up is queued, at most 3 deep.
7. **Destruction is a group decision.** It comes from a pot that many viewers fill, against a counter-pot ("Hold the ground"), so no single troll can wreck hours of work.

## 3. The powers
Prices use 1 credit = €0.05. Status: built, adapt (built but needs changing), or new. Phase is the build order in §10.

| Power | Tier | Price | Viewers see | Effect | Charges | Status, phase |
|---|---|---|---|---|---|---|
| Driftwood | gift | 4 cr | a log rides a wave onto the beach nearest Godling | wood | 4, +1 every 3 min | adapt (Log becomes the driftwood wash-up), 4 |
| Stone | gift | 4 cr | a stone thuds down near Godling | a block | 4, +1 every 3 min | built |
| Ripe coconut | gift | 6 cr | the nearest palm sways and drops one | food, 15 | 2, +1 every 15 min | new, 4 |
| Regrow a palm | gift | 6 cr | a stump springs up | palms to fell or shake | 3, +1 every 5 min | built |
| School of fish | gift | 10 cr | a shimmering school gathers in the shallows by Godling | 2 minutes of easy fishing | 1, every 10 min | new, 4 |
| Healing glow | gift | 20 cr | a golden shimmer round Godling | +10 health over a minute | 1, every 20 min | new, 4 |
| Lightning | wonder | 40 cr | a bolt fells the nearest palm | 2 logs; harm within 7 | 1, every 20 min | built |
| Meteor | wonder | 40 cr | a shadow for 40 s, then a dark stone | a rare stone; harm within 6 | 1, every 15 min | built |
| Rain shower | wonder | 27 cr | clouds, then 5 minutes of rain | coconuts ripen faster; fires go out | one weather at a time | new (start the existing shower now), 4 |
| Gust of wind | wonder | 30 cr | palms bend, sand blows | unfastened top pieces topple | 1 per hour | new, 4 |
| Shooting star | wonder | 60 cr | a streak at night; a glowing stone lands | a star stone, gift-only material | at night, 1 per night | new, 4 |
| Supply crate | big | 120 cr | a crate washes ashore | rope or a tool Godling cannot make | 1 every 2 hours | new, 4 |
| Passing ship | big | 500 cr, pooled | a horn, a ship on the horizon | if a fire burns or HELP is written, it drops supplies | daily, by day | adapt (the random ship), 4 |
| Storm night | big, harmful | 500 cr, pooled | clouds roll in 2 min ahead; 10 minutes of storm | knocks loose pieces, puts out fire; driftwood after | daily | adapt (the wet spell and thunderstorm), 4 |
| Rising sandbar | big | 500 cr, pooled | a strip of land rises from the sea | permanent building space | daily | new, 4 |
| **Earthquake** | big, destruction | 500 cr, pooled | a rumble, then 20 s of shaking | unfastened pieces topple by real physics | 1 per day (with the tsunami) | **new, 1** |
| **Tsunami** | big, destruction | 500 cr, pooled | the sea draws back for 60 s, then a wave | loose pieces near the shore are carried off; sand writing wiped | 1 per day (with the quake) | **new, 2** |

## 4. Cooldowns and limits
All limits sit in the world, where they cannot be bypassed. The store applies the per-viewer ones before a call reaches the world.

1. **Charges per power.** Each power has a bank of charges that refills on a clock. Cheap powers keep several charges; big ones keep one (like Populous: The Beginning's spell charges). The world publishes each power's charges and next refill so the panel can draw bars ("2 left, next in 1:40").
2. **Per viewer** (the store): one purchase per 60 seconds, and one harmful power per 30 minutes.
3. **Breathing room:** after a wonder or a big event lands, other wonders and big events wait 90 seconds. Gifts are not held back.
4. **Harm cap:** at most 2 harmful events per hour in total (gust, storm, rain on a lit fire). Destruction counts separately: at most 1 per day.
5. **Mercy:** harmful and destructive powers are refused while Godling's health is under 30, or within 15 minutes of a faint. The panel shows "Godling is weak".
6. **Something to test:** destruction needs at least 15 settled building pieces within the quake's reach. Otherwise it is refused as "nothing built yet".
7. **Time windows:** a shooting star only at night, the ship only by day, a coconut only when a palm has one ripe.
8. **Hold until safe:** an event waits while Godling stands where it would land, as the meteor already does.
9. **Food cap:** gifts can feed at most about 60 of the 100 hunger lost per hour. Godling still has to forage.
10. **Refund:** anything not applied within 5 minutes is refunded.

Test mode (the guest panel today) keeps every rule, with one exception: disasters may come every 10 minutes instead of once a day, so they can be tried. Test worlds may shorten timers further.

## 5. The earthquake (phase 1)
### Sequence
| Phase | Time | What happens |
|---|---|---|
| Rumble | 8 s | Light shaking (intensity 0.15). The Clock carries `Quake` and `QuakePhase` = "rumble". The mind notices "The ground is rumbling" (salience 5), and the body braces. |
| Shaking | 20 s | Full strength (a peak of about 0.65 g by default). Woken pieces get the ground's motion; whatever cannot hold falls. |
| Fade | 5 s | Intensity fades to 0. |
| After | | Pieces come to rest and settle again (the existing settling squares them into cells). The world reports how many moved and fell. The mind notices "The ground has stopped shaking: N pieces fell", and its existing damage notes name what fell from its kept structures. |

### The physics: the ground's motion, applied to everything loose
- **The method.** A quake is the ground accelerating back and forth: `a(t)`. Shaking hundreds of island parts would be heavy and would flood the viewers' updates. Physically it is the same to hold the ground still and push every loose piece the opposite way.
  - Each tick, each woken piece gets the impulse `-a(t) × mass × dt` at its own centre (`ApplyImpulseAtPosition`).
  - Welded assemblies get the sum of their parts' impulses: their true mass, at their true centre of mass.
  - Friction, rocking and toppling then come from Rapier, not from a script. A tall, thin column rocks over; a wide wall slides a little and stands.
- **The motion.** `a(t)` is horizontal, along a direction that slowly turns. It is the sum of three sines with random phases, scaled so its peak is `intensity × ACCEL`.
- **Tuned in tests** (2026-11-02). Each run used test structures in the camp meadow:
  - a loose column 5 high (A);
  - the same column, fastened (B);
  - a freestanding wall 3 wide and 3 high (C);
  - loose columns 2, 3 and 4 high (E2–E4).

  Pieces that fell, out of each structure:

  | Shaking | A (5) | B fastened (5) | C wall (9) | E2 (2) | E3 (3) | E4 (4) |
  |---|---|---|---|---|---|---|
  | 0.42 g peak, 1.1–3.1 Hz | 0 (rocked 1.1) | 0 | 0 | | | |
  | 0.64 g, 0.45–1.5 Hz | 0 | 0 | 0 | | | |
  | **0.65 g, 0.45–1.5 Hz, along the wall (the default)** | **2** | **0** | **2** | **0** | **0** | **0** |
  | 0.65 g, across the wall | 0 | 0 | 6 | 0 | 2 | 0 |
  | 0.72 g, diagonal | 0 | 0 | 8 | 0 | 0 | 0 |
  | 0.87 g, three directions | 0–1 | 0 | 5–6 | 1–2 | 2 | 0–2 |

  - Fast shaking only rattles; slow swings topple.
  - Loose blocks are not glued, so near 0.9 g they slide off one another and short stacks lose their tops as easily as tall ones. The plan's guess that "thin falls first" is not what happens with loose blocks.
  - A freestanding wall is weakest across its thin side, as real walls are.
  - **Fastened pieces never moved in any of the 9 runs.**
  - The server stayed at 62 ticks a second while shaking.
- **The default:** about 0.65 g at 0.45, 0.8 and 1.5 Hz.
  - A loose wall loses its top row when shaken along it, and most of itself when shaken across.
  - A loose tower is less sure to fall. The 5-high column lost its top two in one direction and stood in the other. The renderer session's 6-high test tower stood. In the real run, 4 of 35 pieces fell.
  - If towers should fall more often, a stronger tier is the lever; the table shows what more strength does.

### What wakes, and what never moves
- **Woken:** settled, unfastened blocks, logs and stones within 60 of Godling. They are unanchored and marked `Settled` false, as lifting does, at most 200 pieces, nearest first.
- **Never moved:**
  - fastened pieces (they hold to the ground: the reward for fastening);
  - terrain, mesas and rock;
  - the ladder once set up;
  - boulders (they hold where they lie, as decided in ADR-009);
  - anything held;
  - **the column under a body's feet**, found by walking down from the piece Godling stands on. Nothing gives way under Godling.
- **After the shaking,** settling re-anchors everything that came to rest, squared into its cell, exactly as now.

### Godling's body
- **Brace** (a new world input). The body crouches and holds on: `Bracing` is true, walking stops, and a knock-down cannot happen. The world lets go 1.5 s after the shaking ends; the Brace loop blends back into Idle.
- **Knocked down.** A body that is not braced, and not on a ladder, when full shaking starts is knocked down once:
  - a `Stagger` gesture;
  - no walking for 2.5 s;
  - then `GetUp`, from sitting, where Stagger leaves it.
  - No health is taken.
- **The reflex** (L1). As soon as the rumble is noticed, the step in progress is interrupted (salience 5). The world plays `LookAround`, and about 2 s into the rumble the body braces wherever it stands, 6 s before the shaking. On a ladder, the climb finishes first: the world carries a climbing body, so the quake cannot move it. The body watches until the ground is still, then the mind plans from what is left.
- **What the mind is told** (system prompt): "Now and then the ground shakes. Loose pieces can fall; fastened pieces on a wide base hold. When it rumbles, your body braces by itself."

### Gates
- One destruction event a day.
- The mercy rule (§4).
- At least 15 settled pieces within reach.
- Refused while another quake or tsunami is under way.
- The god bot never calls it.

### What is measured (`analyze_run.py`)
- Pieces woken, moved and fallen per quake.
- Time from the rumble to `Bracing`.
- Knock-downs.
- Whether the mind named the quake.
- The time until the tallest structure is back to its height before the quake.
- Server tick time during the shaking. Target: still 60 Hz.

## 6. The tsunami (phase 2)
### Sequence
| Phase | Time | What happens |
|---|---|---|
| Drawback | 60 s | The sea level (the Ocean part) sinks 1.5 over 20 s, baring the beach. "The sea is drawing back from the beach" (salience 5). |
| Wave | about 30 s | A crest comes in from the sea, from the side nearest Godling, at 12 units/s. It is 1 to 2 blocks high and runs inland until it has climbed its own height or travelled 60. |
| Backwash | 20 s | The water runs back out; the sea level returns. |

### The physics: one wave function, shared by the server and the renderer
- **The wave** is a solitary wave travelling along direction `d`: height `η(s, t) = H·sech²((s − s0 − c·t)/W)`. The flow under it runs along `d` with speed about `c·η/(h0 + η)`, and backwards in the backwash.
- **The world publishes** `WaveOrigin`, `WaveDir`, `WaveCrest` (updated 10 times a second), `WaveHeight` and `WavePhase` on the Clock. The renderer draws the same function, so what is seen and what is pushed agree.
- **Pieces in the water** (bottom below `η`) are woken if settled and unfastened, then get two pushes each tick:
  - buoyancy `ρw·g·Vsub`: logs (density 0.6) float, stones (2.6) do not;
  - drag `k·A·(u − v)`: logs drift with the flow, stones tumble only where the flow is strong.
  - Fastened pieces hold.
- **The wave also** wipes sand writing (`SandMark`) under it, puts out fires, and strands fish briefly.
- **Not used:** Clawblox's terrain-water buoyancy. Its 4-unit voxels do not fit the 2.5 grid, and moving voxel water every tick is heavy. A full fluid simulation is too heavy for a 24/7 server and phones, and would look no different at block scale.

### Godling's body
- **The mind is told:** "When the sea draws back from the beach, a great wave follows. High ground is safe."
- **Running** to high ground is the mind's decision, which is the fun part.
- **Bracing:** if the crest is within 15 of a body standing below the wave's height, the body braces (the same reflex). Braced, it holds, is soaked (`Wet` 100, so cold follows by the weather rules) and keeps what it holds.
- **Caught unbraced:** carried up to 6 with the flow, knocked down, soaked, and 10 health taken.
- **On high ground:** it watches (a glance).

## 7. Animations (the contract between the world, the renderer and the art)
| Clip | Kind | Played when | Fallback until it exists | Source idea |
|---|---|---|---|---|
| Brace | loop | player attribute `Bracing` is true | Idle | Mixamo "Crouching Idle" or "Kneeling Idle", arms out |
| Stagger | one-shot gesture | knocked down by a quake or wave | nothing (Fall plays if airborne) | Mixamo "Stumble Backwards" |
| LookAround | one-shot gesture | the rumble starts; the sea draws back | nothing | Mixamo "Looking Around" |
| GetUp | one-shot gesture | getting up after a knock-down, from sitting (WakeUp starts from standing, for the raft) | WakeUp | built by the art session |
| Wave, ShieldEyes, Run | later | the ship; lightning; fleeing | | phase 4 |

**Renderer** (the renderer session, `world/renderer`):
- a Brace loop from `Bracing`, like Climb from `Climbing`;
- camera shake from the Clock's `Quake` (0 to 1), smaller on the low tier;
- optionally, dust where woken pieces move fast;
- phase 2: the wave, the drawback, a flood sheet over land and spray, all from the Clock's wave attributes.

## 8. Who builds what
| Who | What |
|---|---|
| This session (world, mind, panel, analysis) | Phase 1: the quake driver, Brace, knock-down, mind events and the reflex, a panel button, gates, measures and tests. Phase 2: the wave physics and body rules. Phase 3: charges and limits. |
| The renderer session ("Game engine capability for project scope") | The Brace loop, camera shake, dust; the wave visuals. |
| The art pipeline (`art/build_godling.py`, currently changed in the main checkout) | Brace, Stagger, LookAround clips. |
| The main Godling session (uncommitted work in `C:\Work\godling`) | Told about this branch: the quake lives in its own section of `main.lua`, with small hooks in the input handler, the main loop and `SKY_POWERS`. |

## 9. Risks
- **Rapier stability** with many woken stacks: jitter or pieces flung away. Waking is limited to 200 pieces, and the impulse is capped per tick.
- **Load:** a Lua loop over up to 200 pieces at 60 Hz for 33 s. Measure the tick time.
- **Network:** moving pieces send updates to every viewer for about 30 s. It is acceptable at this count; measure it on the low tier.
- **Merging** with the main session's uncommitted `main.lua` and `mind/` work. Keep the quake in its own `do`-style section, with hooks of a line or two.
- **Tuning:** whether the tipping targets above are met is a test result, not a promise. The constants are in one place.

## 10. Phases and how each is accepted
1. **Earthquake and Brace** (built). Results in scratch worlds with test structures:

   | Check | Result |
   |---|---|
   | Loose pieces fall, by physics | yes: see §5's table |
   | A fastened column stands | yes, in all 9 runs |
   | Nothing under Godling's feet moves | yes: the block it stood on was held ("1 hold a body up") |
   | Godling braces at the rumble | yes, within 0.5 s, and held on for 33 s |
   | Unbraced, it is knocked down and gets up | yes |
   | Everything settles back into cells | yes: all 20 test pieces settled or fastened again |
   | Tick rate while shaking | 62 per second, as before |
   | In a real 6.4-minute run (deepseek-flash, $0.049) | the rumble stopped the step in progress, the body braced 0.1 s later and was not knocked down; 35 pieces were woken, 4 fell and 2 moved. The next plan began "The tremor cut the last haul short", and the one after "The shaking has passed." |

   The original targets ("a 5-high column falls", "a 3-wide wall keeps two rows") were guesses. Loose blocks don't behave that way (§5), so the table records what does happen.
2. **Tsunami.** Accepted on the same kind of checks: logs float and drift, stones mostly stay, sand writing is wiped, high ground stays dry, and a braced Godling holds.
3. **Charges and limits.** All of §4 in the world, with the panel drawing charges and refill timers.
4. **The rest of the catalog,** cheapest first: coconut, school of fish, rain, gust, shooting star, healing glow, crate, ship on demand, storm night, sandbar.

## 11. Decided by default, open to change
1. **Lightning does not leave a fire.** ADR-010 decided fire must be earned. Lightning that lit fires would undo that, so it stays a felling.
2. **A tsunami that catches Godling unbraced takes 10 health,** in line with ADR-009's sky harm.
3. **Destruction comes only when paid** (or from the panel in test mode). It is never a random event and never from the god bot.
4. **One quake strength to start** (a peak of about 0.65 g). §5's table shows what stronger tiers would do.
