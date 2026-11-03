---
name: Godling
description: The viewer screen over the live island, a block-game HUD built from Godling's own island stone, moss, gold and paper.
colors:
  ink: "#15191b"
  white: "#ffffff"
  mist: "#dfe6e8"
  fog: "#b9c5c9"
  gold: "#f6c945"
  gold-deep: "#c9951c"
  gold-ink: "#2a1d00"
  teal: "#45d6cf"
  heart: "#ec4b4f"
  heart-deep: "#a52a2f"
  paper: "#f6f3e8"
  paper-ink: "#2d2a22"
  paper-shade: "#d9d3bf"
  stone: "#50585b"
  stone-panel: "rgba(44, 49, 51, 0.92)"
  glass: "rgba(14, 17, 18, 0.62)"
  moss: "#63b544"
  moss-deep: "#3f8a2c"
  pip-empty: "#5c6366"
  night-well: "#0b0e10"
  refusal-pink: "#ffd0d1"
typography:
  display:
    fontFamily: "Tiny5, sans-serif"
    fontSize: "2.1rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.02em"
    fontFeature: "\"tnum\""
  headline:
    fontFamily: "Tiny5, sans-serif"
    fontSize: "1.65rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.02em"
  title:
    fontFamily: "Tiny5, sans-serif"
    fontSize: "1.3rem"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "0.02em"
  body:
    fontFamily: "Tiny5, sans-serif"
    fontSize: "1.12rem"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "0.02em"
  body-small:
    fontFamily: "Tiny5, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "0.02em"
  label:
    fontFamily: "Silkscreen, monospace"
    fontSize: "0.6rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.02em"
rounded:
  none: "0px"
spacing:
  bevel: "0.1875rem"
  xs: "0.25rem"
  sm: "0.45rem"
  md: "0.6rem"
  lg: "0.9rem"
  edge: "1.5rem"
  edge-phone: "0.75rem"
components:
  button-get:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.gold-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0.55rem 0.85rem"
  button-get-hover:
    backgroundColor: "#ffd95e"
    textColor: "{colors.gold-ink}"
  button-get-disabled:
    backgroundColor: "{colors.pip-empty}"
    textColor: "{colors.mist}"
  button-cancel:
    backgroundColor: "rgba(14, 17, 18, 0.7)"
    textColor: "{colors.white}"
    rounded: "{rounded.none}"
    padding: "0.5rem 0.7rem"
  slot:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.white}"
    rounded: "{rounded.none}"
    size: "5.6rem"
  camera-switch:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.white}"
    rounded: "{rounded.none}"
    padding: "0.55rem 0.85rem 0.45rem"
  panel-stone:
    backgroundColor: "{colors.stone-panel}"
    textColor: "{colors.white}"
    rounded: "{rounded.none}"
    padding: "0.6rem 0.9rem"
  paper-slip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.paper-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0.45rem 0.6rem"
  feed-line:
    backgroundColor: "rgba(14, 17, 18, 0.74)"
    textColor: "{colors.white}"
    typography: "{typography.title}"
    rounded: "{rounded.none}"
    padding: "0.4rem 0.7rem"
  input-name:
    backgroundColor: "rgba(14, 17, 18, 0.7)"
    textColor: "{colors.white}"
    rounded: "{rounded.none}"
    padding: "0.45rem 0.6rem"
  chip-kind:
    backgroundColor: "#2c3335"
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.25rem 0.4rem"
  chip-kind-harm:
    backgroundColor: "#7a1f22"
    textColor: "{colors.white}"
---

# Design System: Godling

## Overview

**Creative North Star: "The Island's Own Hotbar"**

The viewer screen is a block-game HUD made from the island Godling lives on. The 3D island fills the whole screen and the HUD floats over it in four corners and a bottom dock, letting every drag the HUD does not claim pass through to the camera. Its panels are slabs of slate island stone with a moss lip and a hard bevel, its type is white pixel lettering with a one-pixel shadow, and its pictures are authored 16-pixel drawings of the island's own things: a stone block, a log, a palm sapling, a coconut, a paper glider.

Density is game-HUD density: small, constant, glanceable pieces at the edges, nothing that covers Godling in the middle of the frame. Colour is spent by meaning. Halo gold belongs to the viewers and the sky (what they can press, what they pay, who did what, what the sky did, the hour); lagoon teal belongs to what Godling noticed and to outcomes that spare it; heart red belongs to life and harm. The one warm, light surface is paper, and it carries only words a viewer wrote.

The surface brief refuses the stream sidebar of glass cards, and the build holds to it: no rounded corners, no backdrop blur, no soft drop shadows. The style is Godling's own and never a copy of a famous block game (user, 2026-11-02).

**Key Characteristics:**
- Full-bleed live island; HUD only at the edges, pointer-transparent except its controls.
- Square slabs of speckled stone with an ink border and an inset bevel; slots and the camera switch also carry a moss lip.
- White Tiny5 pixel type with a hard one-pixel shadow; Silkscreen for keys, times and small caps labels.
- Authored pixel icons on one palette with a shared one-pixel ink outline, scaled by whole numbers and rendered crisp.
- Colour by meaning: gold for viewers and the sky, teal for Godling's noticing, red for life and harm, paper for viewer words.

## Colors

A dark slate-and-ink HUD lit by three saturated signals (gold, teal, red) and one warm paper.

### Primary
- **Halo Gold** (gold): the viewers' and the sky's colour. Fills the only filled button style ("Fold and send", "Let the sky choose"), outlines a hovered, focused, open or aiming slot and the pressed camera button, and colours prices, the credit amount, the watcher count, the clock time, viewer names in pop-ups, the "Needs" label, tooltip titles, sky lines in the feed, and the selection highlight.
- **Gold Shadow** (gold-deep): the lower-right inner bevel of a gold button and its pressed state.
- **Gold Ink** (gold-ink): text on gold.

### Secondary
- **Lagoon Teal** (teal): what Godling noticed (notice lines in the feed), the aim ring when a gift will land at Godling's feet, the "At Godling: it lands at its feet" aim words, "free while testing", a sent note's confirmation, and a cooling slot's countdown.

### Tertiary
- **Heart Red** (heart): life and harm. The live dot, full hearts, the corner flag on harmful slots, "Shaking" on the clock, the meteor's aim ring, a full note counter.
- **Heart Shadow** (heart-deep): the live dot's border, the half-tone of hearts, the underline inside a harmful pop-up's tile.
- **Refusal Pink** (refusal-pink): text of a refusal said once above the hotbar and of a refused note.

### Neutral
- **Ink** (ink): every border, the icon outline, the pixel text shadow, kbd keycaps, the theme colour.
- **White** (white): all HUD text over stone and dark bands; the focus ring.
- **Mist** (mist): secondary text on stone (the "watching" label, pop-up verbs, hints, disabled button text).
- **Fog** (fog): times, quiet labels, the purse's small print, placeholders.
- **Island Stone** (stone): the solid body of slots and the camera switch under the moss lip.
- **Stone Panel** (stone-panel): the translucent body of every stone slab (live bar, clock, pop-ups, purse, aim bar, note composer, tooltip).
- **Moss** (moss) and **Deep Moss** (moss-deep): the moss lip on slots and camera buttons (a light band over a darker band), and the caret on paper.
- **Dark Band** (glass and the same base at 0.7 to 0.85 alpha): unbevelled reading bands behind feed lines, the needs objective, the hotbar tray, the said-once line and the camera hint, dark enough to read over a bright sky.
- **Paper** (paper), **Paper Ink** (paper-ink), **Paper Shade** (paper-shade): the note slip and the note textarea; paper-shade is the slip's inner bevel.
- **Empty Pip** (pip-empty): empty heart and coconut pips, a disabled button, the offline live dot.
- **Night Well** (night-well): the page and the frame behind the island before it loads.

### Named Rules
**The Signal Rule.** Gold, teal and red each mean one family of things: gold is viewers and the sky, teal is Godling noticing and outcomes that spare it, red is life and harm. A new element takes the colour of its meaning, never one for decoration.

**The Paper Rule.** Paper carries only words a viewer wrote: the note slip in a pop-up and the note being written. Paper text is ink on paper with no text shadow.

## Typography

**Display Font:** Tiny5 (with sans-serif)
**Label/Mono Font:** Silkscreen (with monospace)

**Character:** Two pixel faces from the same world. Tiny5 carries every word of the HUD, mixed case, slightly tracked (0.02em across the stage); Silkscreen's small capitals mark keys, island times, counters and the facts in a tooltip.

The root size scales with the viewport so the HUD keeps its proportions on a 16:9 screen: `clamp(11px, min(0.834vw, 1.482vh), 18px)`, about 13.3px at the 1600x900 reference. On phones it is fixed at 13px.

### Hierarchy
- **Display** (400, 2.1rem, 1): the watcher count, tabular figures, in gold.
- **Headline** (400, 1.5 to 1.65rem, 1): the live bar ("LIVE" uppercase, tracked 0.08em) and the clock.
- **Title** (400, 1.25 to 1.4rem, 1.2 to 1.3): feed lines, the needs objective, pop-up heads, the note label, tooltip titles.
- **Body** (400, 1.05 to 1.2rem, 1.2 to 1.35): tooltip text, note text, paper slips, aim words, the said-once line, prices under slots.
- **Body small** (400, 0.95 to 1rem, 1 to 1.3): states beside the hearts, pop-up after-lines, hints, cooldown countdowns, purse print.
- **Label** (Silkscreen 400, 0.6 to 0.75rem, 1, tabular where numeric): kbd keys, feed times, the note counter, tooltip terms and the kind chip.

### Named Rules
**The One Weight Rule.** Tiny5 ships one weight. Hierarchy comes from size, colour and case, never from bold.

**The Shadowed Type Rule.** Every word over the island or on stone carries the pixel shadow; text on paper and on gold does not.

## Layout

The island is a full-bleed frame (100vw by 100dvh); the HUD is absolutely positioned over it.

- **Desktop:** edges at 1.5rem. Top centre: the live bar. Top left: the feed (five lines, older words fading to no less than 0.62 opacity while their band stays dark) with the needs objective under it, width `min(36rem, 50vw - 12rem)`. Top right: the clock above the camera switch, with the free-camera hint under them. Right, from 12.4rem down: pop-ups, 26rem wide, four at most. Bottom centre (1.1rem up): the dock, stacking the aim bar or note composer, the said-once line, the vitals row (hearts left, states centre, coconuts right) and the belt (the hotbar of seven 5.6rem slots plus the purse).
- **Phone (max-width 760px):** edges at 0.75rem, respecting safe-area insets. One top row of 3.1rem pieces: live bar left (the eye stands for "watching"), clock and icon-only camera buttons right. The feed shows three lines; one pop-up at a time sits over the feed and hides it, never over Godling. The dock spans the width: the slots share the row as squares (aspect-ratio 1) with icons at 62% and no keys, the purse goes above the hotbar as one line, and tooltips are not shown. Inputs drop to 16px so iOS does not zoom.
- **Rhythm:** gaps step through 0.12 to 1rem; panels pad 0.4 to 0.9rem. Line text clamps to two lines with a word-cut ellipsis.

## Elevation & Depth

Depth is drawn, not cast. Slabs are flat fills with a hard inset bevel: a light inner edge on the top and left, a dark inner edge on the bottom and right, all at the bevel width (0.1875rem), inside an ink border of the same width. There are no soft or offset drop shadows on boxes. Interaction depth is literal movement: a slot lifts 0.4rem when hovered, focused, open or aiming and sinks 0.1rem when pressed; a pressed gold button loses its light edge.

### Shadow Vocabulary
- **Stone bevel** (`inset var(--bevel) var(--bevel) 0 rgba(255,255,255,0.08), inset calc(var(--bevel)*-1) calc(var(--bevel)*-1) 0 rgba(0,0,0,0.32)`): every stone slab.
- **Block bevel** (`inset var(--bevel) 0 0 rgba(255,255,255,0.13), inset calc(var(--bevel)*-1) calc(var(--bevel)*-1) 0 rgba(0,0,0,0.3)`): slots, pop-up tiles and the camera switch, under the moss lip.
- **Gold bevel** (`inset var(--bevel) var(--bevel) 0 rgba(255,255,255,0.45), inset calc(var(--bevel)*-1) calc(var(--bevel)*-1) 0 var(--gold-deep)`): the gold button; pressed it keeps only `inset var(--bevel) var(--bevel) 0 var(--gold-deep)`.
- **Paper bevel** (`inset calc(var(--bevel)*-1) calc(var(--bevel)*-1) 0 #d9d3bf` on a slip, `inset var(--bevel) var(--bevel) 0 #d9d3bf` on the textarea): paper sits proud, the writing field sits sunk.
- **Pixel shadow** (`text-shadow: 0.1rem 0.1rem 0 rgba(21,25,27,0.9)`): text only, the block-game outline that keeps white pixel type legible over sky and sea.

### Named Rules
**The Drawn Depth Rule.** Depth is an inset bevel or a real lift, never a blurred box shadow and never backdrop blur.

## Shapes

Everything is square: there is no border-radius anywhere in the HUD. Every slab, slot, button, field, chip and keycap has an ink border at bevel width (keycaps use a hairline in pip-empty). The recurring silhouette is the island block: a speckled stone face (an 8-pixel speckle tile at 1.5rem) with a moss lip (a 0.375rem light band over a 0.1875rem dark band; 0.3rem and 0.15rem on the camera switch). Harm is a shape, too: a heart-red right triangle (0.75rem) in a harmful slot's top-right corner, and a heart-deep band along the bottom of a harmful pop-up tile. A cooldown is a conic sweep of dark glass over the slot's face, below the lip.

Icons are 16-pixel grids (smaller for pips) drawn in code, every filled pixel ringed by a one-pixel ink outline, merged into crisp SVG rects and scaled by whole numbers (2 or 3 screen pixels per grid pixel), rendered pixelated.

## Components

### Buttons
- **Shape:** square, ink border at bevel width.
- **Gold button:** gold with gold-ink text, gold bevel, padding 0.55rem 0.85rem. Hover brightens to #ffd95e; active swaps to the pressed bevel; disabled turns empty-pip grey with mist text and a faint bevel, and its label states the wait ("Next note in 2:41").
- **Cancel:** a dark band at 0.7 alpha with white text, darkening to 0.95 on hover.
- **Focus:** a 0.25rem white outline, offset 0.125rem, on every button, input and textarea.

### Hotbar and slots (signature)
Seven slots in a dark tray (0.78 alpha) whose bottom padding (2.1rem) holds the prices: Stone, Log, Regrow, Lightning, Meteor, Earthquake, Note. Each slot is an island block holding its icon at scale 3, its number key top-left in Silkscreen, its cooldown countdown bottom-right in teal, and its price under it in gold ("4 cr"; the note's "free" in paper). Hover, focus, open and aiming lift it 0.4rem with a 0.25rem gold outline; a call in flight bobs its icon. Harmful slots carry the red corner flag. A cooling slot greys its icon and sweeps a conic shadow by the share of the wait left. Number keys 1 to 7 focus the slots.

### Vitals
Ten hearts and ten coconuts, each filling in halves (full, half, empty pip), hearts left and coconuts right above the hotbar (coconuts fill from the right, so a half coconut keeps its right half; full, half and empty pips share one silhouette, and a full pip's rim is a colour that still reads on a dark sky), with states between them (Knocked down, Bracing, Cold, Wet) as small icon-and-word pairs.

### Cards / Containers (stone slabs)
- **Corner Style:** square.
- **Background:** speckle over stone-panel.
- **Shadow Strategy:** stone bevel (see Elevation & Depth).
- **Border:** ink at bevel width.
- **Internal Padding:** 0.55 to 0.9rem.
Used for the live bar, clock, purse, pop-ups, aim bar, note composer and tooltip.

### Live bar
"LIVE" with a red dot that blinks in two steps (1.6s), a stone divider, the eye icon, the watcher count in gold and "watching" in mist. Offline it greys the dot, reads "Offline" and drops the count.

### Camera switch
Two block buttons (Follow Godling; Free camera with W A S D keycaps). The pressed one has a 0.25rem gold outline; the other is desaturated (0.6) and dimmed (0.85) until hovered. In free mode a hint fades in beneath. On phones they are icon-only.

### Feed and needs
Each line is a dark band: a Silkscreen island time, a speaker icon (Godling, the sky, a notice) and up to two lines of Tiny5. Godling's own words are in quotes and white; sky lines are gold; notice lines are teal; the waiting line is mist. The needs objective is a bordered dark band with an icon chosen from the need, "Needs" in gold, and the first need.

### Pop-ups
Stone slabs that slide in from the right (2.5rem, unblurring, 420ms) and out (380ms), each with a block tile holding the power's icon, "**name** did what" (name in gold, verb in mist) and an after-line in fog. A note's pop-up replaces the after-line with a paper slip quoting the note. They stay 9s (notes 14s).

### Inputs / Fields
- **Note textarea:** paper with paper-ink text, sunk paper bevel, moss caret, 140 characters with a Silkscreen counter that turns red when full; Enter sends.
- **Name field:** a dark band (0.7 alpha) with white text, gold caret, fog placeholder.
- **Hint line:** mist, teal when the note was sent, refusal pink when it was refused.

### Tooltip and kind chip
A 23rem stone slab placed above the hovered slot (desktop only): icon and gold title, a kind chip at the right (Gift, Wonder, Words on #2c3335; Disaster on #7a1f22) in Silkscreen, the description, then a definition list (Silkscreen terms in #a8b6ba, Tiny5 values): price in credits and euros, the rule for harmful powers, and the wait.

### Aim bar and the aim ring
A stone bar over the hotbar while a power is aimed: the power's icon and what a click will do (teal for "lands at its feet", pale red #ffb3b5 for "the blast will hit it"), a gold "Let the sky choose" button and Cancel. On the island the renderer draws the matching ring: gold by default, pale gold (#fff1a8) for lightning, moss for regrow, teal when a gift is aimed at Godling, and heart red for the meteor with its 7-unit blast radius and its 2.5-unit smash filled.

### Said-once line
A dark band (0.85 alpha) above the hotbar that rises in (240ms) with a refusal or a nudge and leaves after 6s; refusals are refusal pink.

### Motion
One easing for everything that moves (ease-out, `cubic-bezier(0.16, 1, 0.3, 1)`): 160ms slot lift, 240ms hints and the said-once line, 420ms pop-ups. Blinks and bobs are stepped or short. Under reduced motion, animations stop and transitions drop to 1ms with no blur.

## Do's and Don'ts

### Do:
- **Do** build every HUD surface as a square slab with an ink border at bevel width (0.1875rem) and an inset bevel; give pressable blocks the moss lip.
- **Do** set HUD text in Tiny5 at weight 400 with the pixel shadow; use Silkscreen for keys, island times, counters and tooltip terms.
- **Do** draw new icons in the icon DSL (`world/viewer/icons.js`): a 16-pixel grid, the PALETTE colours, the shared one-pixel outline, whole-number scales, pixelated rendering.
- **Do** colour by meaning: gold for viewers and the sky, teal for Godling's noticing and outcomes that spare it, red for life and harm, paper for viewer words.
- **Do** show the price under each slot in credits ("4 cr") and the euro price in the tooltip.
- **Do** mark a harmful power wherever it appears: the red corner flag on its slot, the heart-deep band in its pop-up tile, the red kind chip, the red aim ring.
- **Do** put a dark band or a slab behind any text over the island.
- **Do** keep the middle of the frame clear for Godling, on phones too.
- **Do** honour reduced motion and keep inputs at 16px on phones.

### Don't:
- **Don't** round a corner anywhere in the HUD.
- **Don't** use backdrop blur, frosted glass cards or soft drop shadows; the brief refuses the stream sidebar of glass cards.
- **Don't** use bold or synthetic weights on Tiny5.
- **Don't** use icon fonts, emoji or smooth-scaled raster icons; every picture is an authored pixel icon.
- **Don't** put viewer-written words on anything but paper, or system words on paper.
- **Don't** copy a famous block game's art or HUD; the style is Godling's own (user, 2026-11-02).
