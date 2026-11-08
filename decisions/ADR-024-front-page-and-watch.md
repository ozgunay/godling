# ADR-024: A front page at /, the booklet; the screen moves to /watch

Date: 2026-11-08. Status: built and tested (the site's tests); served on a local site. Not yet deployed.

## Why
Until now the site's root was the screen: a drop-in from the stream or a link landed straight in the live HUD, with no
word on what Godling is, what runs it, or that viewers change its world and never its mind. PRODUCT.md asks that a
drop-in understand it in seconds, and a regular find depth.

## Decisions (the user's, 2026-11-08)
1. **A landing page, in the game's own style.** Three drafts were made (`web/prototypes/landing/`): a booklet, a
   title screen, and the mind log. The user chose **the booklet**: the game's instruction booklet, cut in the island's
   stone, in the screen's Block HUD look (DESIGN.md). They asked for one section of the title screen to join it:
   *It learns by doing* (the five-minute test), with the feed lines it shows.
2. **The booklet is the front page, at `/`; the screen moves to `/watch`.** Every *Watch live*, the sign-in's landing
   (`LOGIN_REDIRECT_URL`) and every *Back to the island* go to `/watch`. Signing out lands on the front page.

## How
- `apps.screen.views.landing` renders `templates/landing.html` with `apps/screen/static/landing/` (its stylesheet and
  a 15 KB portrait). The icons are the screen's own (`/icons.js`, world/viewer/icons.js), drawn in the page.
- **What can change is read, not written down:** the powers switched on (label, kind, harm, price, the first sentence
  of the tooltip) in hotbar order, the cheapest active credit pack, and the site rules (welcome credits, note length,
  test mode). The model the page names is `GODLING_MIND_MODEL` (deepseek-flash), set beside the island's `--model`;
  the hourly cost of thought shows only for deepseek-flash, whose price it is.
- **Old links keep working:** the screen's files stay at the root, so `/watch` finds `viewer.js` and `demo/` as `/`
  did. `/` with `?t=` (a moment of the past, ADR-016) or `?bottle=1` (back from signing in through the bottle) is sent
  on to `/watch` with the same query; `/watch/` goes to `/watch`.
- **Example lines are marked.** The feed lines on the *Reading its mind* page come from the screen's prototype and are
  labelled as samples; the five-minute test is the real one of 2026-11-01 (mind/README.md).
- **The stream** (RUNBOOK, *Making the game ready*): OBS's browser source is now `https://godling.world/watch`.
  `deploy/check.sh` checks both pages.
