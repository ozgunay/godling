---
version: 1
slug: "web-templates-landing-html"
primary_target: "web/templates/landing.html"
related_targets: ["web/apps/screen/static/landing/landing.css"]
---

## Scope
The site's front page at `/` (Persuade). The screen moved to `/watch` (ADR-024). Same visual world as the screen
(DESIGN.md, the Block HUD); this surface extends it and does not change DESIGN.md.

## Audience and job
Drop-ins from the stream or a shared link, often on a phone: within one screen they learn that an AI castaway lives
alone on an island, that nobody controls it, and that they can watch it think; the action is *Watch live* (`/watch`).
Regulars and the curious read on: the mind's layers and the model (DeepSeek, `GODLING_MIND_MODEL`), what it learned,
the powers and prices (from the database), the rules of the sky, death and rebirth, the technical data.

## Direction contract
THESIS: the game's instruction booklet, cut in the island's stone; it refuses the usual hero-plus-feature-cards page.
OWN-WORLD: speckled stone slabs with an ink border and inset bevel, moss lips on blocks, white Tiny5 with the pixel
shadow, Silkscreen folios and running heads; gold for viewers and the sky, teal for noticing, red for harm.
STORY: a cover, then spreads: story, character sheet, Controls ("You do not control Godling."), the mind, It learns by
doing with Reading its mind, Sky powers with Rules of the sky, If Godling dies with Technical data; a back cover CTA.
FIRST VIEWPORT: the island still full-bleed (the phone still on phones); a mossy cover slab left with "Godling" at
6rem, the booklet subtitle under it, two lead lines, the gold *Watch the island* and *Open the booklet*, three seals;
Godling's portrait in a stone frame right (desktop only).
FORM: the booklet, the first of three drafts (web/prototypes/landing/a-booklet.html), chosen by the user; seed key
66f19a9e.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved
- Feed lines on *Reading its mind* are samples; swap in real lines from a run if wanted.
- The hourly cost of thought shows only for deepseek-flash.
