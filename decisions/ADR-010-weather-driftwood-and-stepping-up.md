# ADR-010: Weather and random events, fire by friction, driftwood, and stepping up a block

Date: 2026-11-02. Status: built and tested live.

## Why
You asked why Godling built no structures. In night run n7 (4.6 hours, on the code before ADR-009), the structure measure counted 16 posts, one gate and a largest structure of 12 pieces, but no walls, rooms or roofs. Three things held it back.
- **It had no reason to.** Its persona likes "things that can be seen from far away: towers, gates, rings, lines". Nothing in the world made a shelter useful.
  - Of 572 projects, 124 aimed at building, almost all of them posts, gates and pillars to be seen from the sea.
  - Its reasoning mentions walls 230 times, but almost always as obstacles that trapped it.
- **Material ran short or burned.** It felled 39 palms (78 logs) and burned 18 logs in fires. It never used the quarry, and it started with 12 blocks. A wall of 3 cells two high needs 6 pieces, and a hut needs many more.
- **Nothing above two blocks was in reach.** Placement reaches 6.25 from the ground, and the ladder seldom worked out. In a 20-minute run of the new code, 7 tower steps failed with "cannot get within reach of (x, 8.8, z)". A roof the body can stand under needs pieces at 8.75 or higher, because the body is exactly two blocks tall.

## Decisions (yours)
1. **Weather as the motive:** cold nights, and rain that slows the body and makes it uncomfortable.
2. **Material:** driftwood washes up on the beach.
3. **Height:** the body steps up onto anything one block high.

The persona is unchanged.

**After the first weather run** (30 minutes), Godling answered the cold with fires, not a roof, and burned the washed-up logs for warmth. You then decided:
4. **Rain puts out any fire.** No fire can be made while it rains.
5. **Fire as in the film.** The ready-made fire move is gone, and the warming rubs I had added are undone. The mind must work out how to make fire itself, and it is harder.
6. **Random events.** Rain among them, plus other events, and some rainy days in a row without a break.

## What was built
### Weather (`main.lua` WEATHER)
- **Showers** come every 20–50 minutes and last 4–10. The first comes 8–15 minutes into a run. The Clock carries `Rain`, from 0 to 1, building up and dying away over 20 s.
- **Rain on the body.** Out in the rain (`InRain`), the walk slows to 0.65 of its pace. That combines with a heavy load (`WalkSpeed`, read by the body's walking timeouts). The body also gets soaked: `Wet` rises from 0 to 100 in 2 minutes and dries in 5, or 4 times faster beside a fire.
- **Cold.** At night (21:00–05:00), or soaked in the rain, a body out in the open is `Cold`. Cold drains health at 100 per 40 minutes (about a third over a night) and stops healing.
- **Shelter** (`Sheltered`):
  - "roof": a held piece within 10 above the crown keeps the rain off.
  - "enclosed": a roof and walls on three sides or more keep the cold off. So does a fire within 7.
  - Terrain counts too, such as a nook against the mountain.
- **The mind** is told the basics in its system prompt: nights are cold; rain soaks and slows; cold wears health down; a roof keeps rain off; walls with a roof, or a fire, keep the cold off.
  - Its situation says how its body feels: raining and out in it, wet or soaked, cold, under a roof.
  - It notices rain starting and stopping and growing cold.
  - The thought bubble's reader sees "out in the rain", "soaked" and "cold". It has a rain picture and a "cold" feeling with a red rim.
- **The renderer** (`rain.js`) shows falling streaks that move with the camera, 1,500–5,000 by quality tier. While it rains, the light is dimmer, the fog greyer and the clouds heavier. `?rain=1` forces rain for a look.

### Fire by friction (decisions 4 and 5)
- **No fire move.** The body's `kindle` move and the world's `Kindle` input are gone.
- **Rubbing.** Striking a log with the Spear (a stick, carved from a log with the axe) rubs it.
  - Each rub in a row heats the wood (`Heat`). A pause of more than 10 s lets it cool.
  - From the 12th rub on, the wood is hot and smoking. It can catch only if a coconut (its husk, as Chuck's tinder was) lies within 3 of the log. The chance is 4% at the 12th rub and grows by 4% each rub after, so about 20 rubs on average.
  - The coconut burns away, and the fire burns on the log.
- **Rain.**
  - Nothing warms while it rains, or for 5 minutes after, while the wood is damp.
  - Rain puts every fire out. The log stays, charred.
- **What the mind sees.** Its strike reports "the wood grows warm (n rubs in a row)", "hot and smoking, but no flame", or "a flame caught". It is never told about the tinder.
- **What the mind is told:** fire is hard to make; wood rubbed hard and long against wood grows hot, and something dry and fine beside it may catch; rain puts fires out, and nothing catches in the rain or while the wood is damp.

### Random events (decision 6)
- **Wet spells.** Two or three in-game days of rain without a break, 80–120 minutes real time. The rain swells and eases between 0.6 and 1 as it goes.
  - The first comes 1.5–2.5 hours into a run, then one every 4–7 hours. Ordinary showers come in between.
- **Thunderstorms.** In heavy rain (0.85 or more), lightning strikes a standing palm 12–45 from Godling every 3–8 minutes. It is the same strike as the guest panel's Lightning: it fells the palm, and it hurts anyone within 7.
- **Fog.** On some mornings (35%), fog comes in from the sea at 04:30 and lifts by 08:30–10:00. The Clock carries `Fog`.
  - Godling's sight shrinks to 0.4 of its usual reach, and the peak cannot be seen from afar.
  - The renderer closes the view in with milky fog. `?fog=1` forces it.
- **A ship passes.** The first comes 1–2 hours into a run, then every 2.5–5 hours. It sails 215 out along the horizon for five minutes, never across the islet.
  - The mind notices "A ship is passing far out at sea, to the …" (salience 4) and "The ship has sailed out of sight".
  - Nothing comes of it yet.
- **What the mind notices:** fog rolling in and lifting, fires going out ("the rain put it out"), the ship, and the lightning (as a sky event).
- **Wind** (added after you saw the screenshots, and asked how games do it).
  - The world keeps a wind that veers slowly: a breeze (0.25) in fair weather, 0.55 in rain, a gale (1.0) in a storm. The Clock carries `WindX`/`WindZ`. The wind moves nothing in the world; the mind feels "A storm wind is blowing".
  - The renderer (`wind.js`) eases it in and adds gusts, wilder in a gale.
  - It sways the palms as games sway foliage. In the vertex shader the bend grows with height (the square of it), so trunks stay rooted and crowns lean up to 2.4 in a gale. A slow gust wave sweeps across the grove with position, and the fronds flutter faster on top.
  - The rain streaks stretch along each drop's velocity, so the wind slants them. They drive in at nearly 40° in a storm.
  - The streaks are longer, brighter and denser, so the rain shows by day. `?wind=1` forces a gale.

### Driftwood
- **A log washes up** every 3 minutes, on open sand a little up the beach from the water and clear of other pieces, lying along the shore. It stops while 6 lie on the beach.
- **It is marked `Driftwood`.** The mind notices "A log washed up on the beach", and is told that logs sometimes wash up.

### Stepping up and down a block
- **The world steps the body** onto something at most one block (2.6) above its feet, right beside it, if the body fits there (`StepUp`). The same move takes it down onto floor at most one block below (`StepDown`).
- **It moves like the ladder:** the world moves the body up or down and over the edge in 0.6 s.
- **`walk_to` uses it.** A point on something one block higher is stepped up onto at the edge nearest the body, then the body walks on across the top. Hopping down tries a step down first, and walks off an edge only if that fails.
  - Without the step down, a body on a step just under a lintel it had laid could not walk off the edge, and hung on it.
- **The mind is told** its legs step up onto anything one block high and hop down one block, and that higher needs a ladder.

### Housekeeping
- **The world script now wraps its newer sections in `do … end` blocks.** That keeps it under Luau's limit of 200 locals in one function; the new sections pushed it over, and the world would not start.

## Tested live
On a test world with short timings: rain at 30 s, night at 40 s, driftwood every 20 s.

| Check | Result |
|---|---|
| Driftwood | logs washed up all round the island, and the mind noticed each one |
| Rain | rain 1.0 in the open; pace 5 → 3.25; soaked to 100% in 2 minutes |
| Cold at night, in the open | health 100 → 85.5 in 6 minutes |
| Noticed | "It has started to rain", "You have grown cold: the rain has soaked you through" |
| Step up | stepped up onto a block from beside it, and from 30 units away past the starting pile |
| Hop down | hopped down and went round a gate |
| Gate | from a step block, laid a log across two upright logs at 8.75: a gate 7.5 high. It then stepped down and walked round |
| Under the gate | posts on two sides, the step behind and the lintel overhead counted as "enclosed": out of the rain, not cold, pace back to 5, drying (99 → 92%) and healing (86.9 → 88) |
| Back in the open | soaked, cold and slowed again |

## After night run n8: shelter that never sheltered
The art session analysed n8 (stopped after 6 h 15 min). Godling was never once out of the rain, and the cold made it faint 5 times, although it thought about shelter constantly (8,528 mentions of roof, hut or shelter) and its own `shelter_wait` reported success 119 of 130 times. Three causes:
- **Its shelter test could not fail.** `shelter_wait` was "walk there, wait 30 s, wait 30 s". Walking and waiting succeed, and their reports never said whether it was still in the rain.
- **Its hut roof was too low.** It reasoned that an underside 5.0 up was "the lowest roof I can stand under, since I'm 5 tall". The body is exactly 5.0 tall and needs more room than that, so it always stopped beside the roof. That also explains much of why the world had to free it from inside pieces 36 times.
- **The body could not walk under any roof.** `walk_to` treated a spot under a roof as "on top of" the roof, which it cannot climb.

Fixed:
- **Walking and waiting say how the weather finds the body there** when it rains or the body is cold: "out in the rain with nothing over your head, and cold", "under a roof, out of the rain", or "under a roof with walls round you, out of the rain and the cold".
- **Walking under something overhead that is too low says so:** "Log_4 is overhead there with its underside 5.0 up, too low for you to stand under (you are 5 tall)".
- **A roof over the body's own floor is something to walk under, not to climb.**
- **The mind is told the body fact:** to stand under something it needs more room than its own height; an underside two blocks up is too low.

Tested live, in rain:
- **A log across two 2-block stacks:** "too low … out in the rain … and cold".
- **A log across two 3-block stacks** (laid from a step): the body walked under it, and both the walk and the wait reported "under a roof with walls round you, out of the rain and the cold".

### Fire, fishing and reaching up (also after n8)
In n8 the mind never made fire or fished, and laying a third layer from the ground failed about half the time.
- **A `rub` move.** Striking a log with the spear was the only way to rub it, and nothing told the mind so.
  - `rub` works what the hands hold against a thing, over and over, for up to 30 rubs (about half a minute), until something comes of it.
  - The world takes it as a `Rub` input. The fire rules are unchanged: the spear against a log heats it, and a coconut within 3 is still the only tinder. Anything else rubbed comes to nothing.
  - Its reports: "the wood grew warm, no more", "grew hot and smoked, but nothing beside it caught", or "a flame caught: Fire_1 burns on Log_3".
  - The mind is still not told about the tinder.
- **What `strike` is for.** Its description now says what each tool does with it: an axe fells a palm or carves a log, a hammer breaks stone off the quarry, a spear takes a fish.
- **A spear reaches further.** Fish swim 6–8 off the sand, but from the beach an arm's strike reaches only about 5.4 out, so a fish was almost never in reach.
  - A spear (4.5 long) thrust at a fish now reaches 2.5 further than an arm, in the world and in the body's planning.
- **Stepping up to reach.** From the floor it stands on, the body's hands reach a third layer but not a fourth (8.75).
  - When `place_at` finds no spot to reach from, and the target is more than the body's height above its floor, the body looks for something one block high near the target. It steps up onto it, places the piece, and steps back down.
  - Its report says "you stood on Block_6 to reach that high". If there is nothing to step on, it says "it is above your reach from there, and nothing one block high stands near it to step up onto".
  - The final walk before placing now closes in when the body stops a little short, instead of letting the world reject the place as out of range.
- **The mind is told:** its hands set pieces at most three blocks above the floor it stands on; higher, it steps up onto something a block high beside the spot.

Tested live:

| Check | Result |
|---|---|
| Rub a log, no coconut near | 30 rubs in 27 s: "hot and smoked, but nothing beside it caught" |
| Rub a standing palm | "does nothing" |
| Rub a log, a coconut beside it | a flame after 24 rubs (21 s) |
| Spear fish from the shore (before) | 0 of 4: "too far out in the water" |
| Spear fish from the shore (after) | 3 caught in 8 strikes: 2 misses (the 60% chance), and one fish stayed too far out |
| Third layer from the ground | placed |
| Fourth layer, nothing to step on | refused, with the reason |
| Fourth layer, a block beside the stack (either side) | stepped up, placed at 8.75, stepped back down |
| Roof log across two 3-block stacks, from the ground, in rain | stepped up and laid it; the body then sheltered under it |
