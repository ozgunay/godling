# ADR-021: A meteor's stone cools, falls fast, and is meteoric iron

Date: 2026-11-06. Status: built and tested (Luau, vitest, pytest), and checked in a local world in WSL with the
renderer in a browser. Not yet on the live island (it needs a restart, planned with PR #63 and the lightning work).

## Why
- A meteor's stone kept its glowing look forever, and its crater kept its scorch. Every old landing looked as fresh
  as the newest one.
- The stone was an ordinary building stone. The dearest power left Godling nothing it could use.
- On the live stream the meteor came down slowly: 25 units/s from 40 up, about 1.6 s of fall.

## Decisions (the user's)
1. **The stone cools over about one in-game day** (2400 s of the island's clock), and its crater's scorch fades with
   it.
   - It must survive restarts and show in replays.
   - The user did not choose warmth from hot stones, so there is none.
2. **The stone falls fast**: 80 units/s from 80 up, about 1 s.
3. **Cooled, the stone is meteoric iron (design A, from the research below), and it is too hot to hold while it
   glows.**
   - **Getting iron.** Hammer blows on a cooled meteorite knock flakes of iron off it: 15 blows a flake (the quarry
     needs 3 for a stone), 3 flakes a stone.
   - **Fitting it.** Fasten binds a flake onto a spear, an axe or the hammer as its iron edge. Either the flake is in
     the hands and the tool is set down, or the other way round.
   - **What an edge does:**
     - An iron-pointed spear catches 90% of the time (60% before) and reaches 1.5 further.
     - An iron axe fells a palm in 2 blows (4 before) and carves a spear in 1 (3 before).
     - An iron hammer breaks a quarry stone in 2 blows (3 before).
   - **Too hot.** While it glows (Heat above 0.1, about the first 68% of the day), the stone cannot be picked up or
     worked.
   - **Discovery by use.** The mind is told only what the stone and a flake are like ("dark, heavy and hard, and looks
     like metal"; "a sliver of dark metal, hard, sharp-edged"), never what they are for.
     - The fasten move says only that something small in the hands can be bound onto an object, if the two can be
       bound.
     - Godling finds the rest by trying.
   - **Considered, and not built:**
     - Fire from meteoric iron. Iron-nickel has too little carbon to throw sparks, the island has no flint, and fire
       stays hard by the user's choice.
     - The meteorite as a heavy hammerstone. Quarrying is already only 3 blows, and there are only 2 boulders.
     - Flakes coming off more easily while the stone is warm, as Hopewell smiths heated their iron.

## The research behind design A
- **Cape York, Greenland.** For centuries the Dorset, then the Thule and the Inughuit, hauled basalt hammerstones (some
  from 50 km off) to the iron masses. They knocked off flakes and set them into bone and ivory handles: harpoon blades,
  knives, chisels. The iron was traded about halfway to Alaska. Buchwald found meteoritic-iron blades on three of four
  Melville Bay tools he examined (Buchwald & Mosdal 1985, Meddelelser om Grønland; ScienceNordic, "Greenland's Iron
  Age came from space").
- **Bronze Age.** Iron from before smelting is meteoritic, judging by its nickel: Tutankhamun's dagger has about 10% Ni
  (Comelli et al. 2016), and so do Jambon's beads, daggers and axe (2017).
- **Hopewell, North America.** Iron from the Anoka meteorite was heated, cold-hammered into sheet and rolled into beads
  (McCoy et al. 2017).
- **Why it is valuable.** Cold-worked meteoric iron about doubles in hardness (kamacite 155 to 325 HV; Scientific
  Reports 2021). A stone axe takes about 75 more strokes than steel to fell a small tree (Putz et al. 2023, Forests).
- **What limits Godling** (main.lua as of main e920f48):
  - Tools never wear, and felling or quarrying takes 3–4 blows, so a sharper axe saves only seconds.
  - Fish are the best food (cooked 50, raw 20, a coconut 15). A spear catches 60% of the time, and a missed fish darts
    away.
  - So the iron point, which means more fish per walk to the beach, is the gain that matters.

## What changed
- **`world/main.lua`**
  - **Cooling** (`sky.meteor.cool`): `LandedAt` (the Clock's seconds) and `Heat` on the stone and its crater.
    - Heat is `(1 - age/day)^2`, in steps of 0.05, looked at every 2 s.
    - On a restart, cooling goes on from where it was; a stone saved before this change comes back cold.
  - **The fall**: `SKY_FALL_SPEED` 80, `SKY_DROP_HEIGHT` 80. The contact check now covers the whole of each beat's
    drop. Before, a slow beat could carry the stone past a wall's top.
  - **Meteoric iron** (`sky.iron`):
    - `glowing` and `isMeteorite`.
    - `chip`: hammer blows, `Blows` and `Flakes` on the stone, `Iron_n` flakes.
    - `pair` and `fit`: Fasten, and `Edge` "Iron" on the tool.
    - The edged blows in `breakStone`, `chopTree`, `carveLog` and `catchFish`, and the spear's reach in `strike`.
    - `PickupFailed:TooHot`.
- **Where the iron code lives.** The main chunk really is at Luau's 200 locals: a new top-level table would not
  compile. Unused constants take no register, so adding them proves nothing about the limit. So the `sky` table is
  declared earlier, ahead of the hands, and the iron code hangs on it as `sky.iron`.
- **Saving.** `mind/run_godling.py` keeps `Iron` pieces and numbers them on from the save.
- **The mind**
  - `world.py`: `Iron_` is a movable kind. `Entity.glowing`, and `Entity.look` (the few words that say what a thing
    is like).
  - `skills.py`:
    - New body reports: too hot, chipping, chipped, spent, bound on, already has an edge.
    - Picking up a glowing stone is refused before trying, and glowing stones are never taken as building material.
    - The fasten move's line now says it can bind something small onto an object.
  - `mind.py`: the basic facts in the prompt, and each loose thing's (and the held thing's) look.
- **The renderer**
  - `cooling.js`: the cracks glow yellow-orange, orange, then dull red, and go dark at Heat 0.1, where the stone can
    be held. The scorch fades by up to 65%.
  - `blast.js`: a hot stone smokes. A fast fall's trail is filled in all the way down.
  - `iron.js`:
    - A flake is a faceted sliver of worked iron.
    - An edged tool's working part (the axe's and hammer's `edge`, the spear's `heartwood` point) is worked iron.
    - An iron-pointed spear also gets a leaf-shaped blade over its point.
  - The look of every hot, edged or plain part is one instancing group each.

## Checked
- **Luau.**
  - `test_iron.luau`: too hot to hold or work; flakes after 15 blows, 3 in all, then spent; a fastened stone knocked
    loose first; binding both ways, one edge per tool, out of reach, not set down; the edged spear, axe and hammer;
    the save.
  - `test_sky.luau`: cooling; the fast fall; the wall top passed in one slow beat. That test fails on the old contact
    check.
- **vitest**: `cooling`, `iron`, `blast` (the trail on smooth and slow frames) and `index` (groups per heat step and
  per edge).
- **pytest**: the reports and refusals, the looks, the prompt's facts (and that it never says iron, harpoon, blade or
  edge), and the save.
- **Locally** (the world alone in WSL, cooling sped up in the run's copy, the mind's own body skills doing each step):
  - The stone appeared at y 77 and landed 1.1 s later.
  - Striking it while it glowed did nothing, and lifting it was refused.
  - Once dark, 15 blows gave `Iron_1` at its foot. Bound onto `Hammer_1`, and later onto a freshly carved `Spear_1`,
    the flake was used up and the tool showed its iron edge or point in the browser.
  - Before that: cooling from 1 to 0 in the planned steps, a restart at Heat 0.6 back at 0.55, and the recording that
    replays come from carrying every step.

## Not done
- Nothing tells the mind what an edge did. It finds out from its catches and blow counts, as it would by use.
- A flake has no model of its own in `art/` (the renderer draws it), and the axe's and hammer's iron edges are subtle,
  since their heads are already steel in the art.
