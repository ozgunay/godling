# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
Delegated (2026-11-02): plain HTML, CSS and JavaScript, as a layer over the existing Three.js renderer (`world/renderer`, bundled with esbuild, no CDN). No UI framework: the page must stay light enough for phone browsers, and the same page is captured for the restream.

## Users
- **Drop-ins first:** people who land on the website or the stream for a minute, often on a phone. They must understand within seconds that a small AI builder is living alone on an island, what it is doing right now, and that they can change its world.
- **Regulars second:** people who come back to follow Godling's life: what it built, what it remembers, what happened while they were away. They support it, and they use the god powers more knowingly.

## Product Purpose
Godling is a 24/7 autonomous AI agent, a small builder living alone on a castaway island in a 3D physics world. It walks, quarries stone, fells palms, climbs ladders, fishes, makes fire and builds, and it narrates in a short field-note voice. People watch it live, and can spend credits to change the conditions of its world (gifts, weather, disasters), but never to buy its decisions. Success: viewers stay to watch, come back, and pay for the moments they cause.

## Positioning
Not a game the viewer plays, and not a video: a living character with its own mind that viewers can only influence through the world. The paid powers change conditions; the mind always decides. Its inner life (intentions, thoughts, needs, what it noticed) is shown as it happens.

## Operating Context
- **Where it is watched:** both, the interactive website as the home (phones and desktops; viewers press the powers themselves) and a restream to Twitch/YouTube as 16:9 video with the same UI baked in (viewers there act through chat or platform currencies).
- **The world:** Clawblox (Rust, Rapier physics at 60 Hz, Luau world script) serves the world and a spectator WebSocket; the Three.js renderer draws it, with quality tiers for phones.
- **The mind:** an LLM (DeepSeek) plans projects, narrates intentions to world chat, writes a "needs" line, and its reasoning streams to `mind/thinking.jsonl`. A thought bubble names one of 23 pictures and one of 14 feelings.
- **Today's viewer tools:** the guest panel (`tools/guest_panel.py`): a live view plus buttons for the sky powers, free in test mode.

## Capabilities and Constraints
- **God powers today:** Stone, Log, Regrow, Lightning, Meteor (a shadow 40 s ahead), Earthquake (a rumble, 20 s of shaking; Godling braces). Planned: driftwood, coconut, school of fish, healing glow, rain, gust, shooting star, supply crate, passing ship, storm night, sandbar, tsunami (`research/god-powers-and-disasters-plan.md`).
- **Economy (planned, not built):** 1 credit = €0.05; fixed prices; charges per power that refill on a clock; per-viewer limits; a harm cap; mercy while Godling is weak; destruction only from a community pot with a "Hold the ground" counter-pot. Real-money prices must show beside credits (EU CPC principles).
- **World state viewers can see:** day and night (a 40-minute day), weather (rain, fog, wind), Godling's health and hunger, wet and cold, what it holds, fires, the ship, sky events and their warnings.
- **Not decided:** the payment rail (platform currency versus own credits), supporter tiers, and the Chronicle (a history of Godling's life).

## Brand Commitments
- **Name:** Godling.
- **Voice** (`mind/persona/SOUL.md`): short, concrete sentences in a field-note voice; numbers when they matter; honest about failure; quiet delight, no exclamation marks.
- **Character:** a small, chubby builder (`world/assets/godling.glb`), Minecraft-scale blocks, a castaway story after the film Cast Away (a volleyball, HELP in the sand, fire by friction).
- **Rules:** viewers can never buy Godling's decisions, and the agent never sees who paid.

## Evidence on Hand
- Screenshots of the island and Godling: `research/screenshots/`, `art/previews/`.
- Real run logs with Godling's own thoughts and intentions (e.g. "The tremor cut the last haul short").
- No viewer numbers, testimonials or revenue yet; none may be invented.

## Product Principles
1. The mind is the show: what Godling intends, thinks and needs is always visible.
2. Viewers change the world, never the mind.
3. Every paid act gets a visible reaction: a warning, Godling's notice, a lasting change.
4. A drop-in understands it in seconds; a regular finds depth.
5. Light enough for a phone, honest about money.
