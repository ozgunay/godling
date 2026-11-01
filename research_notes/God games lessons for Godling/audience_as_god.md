# Audience as God: Paid and Point-Based Viewer Interventions, and Learning Inhabitants

Scope: stream integrations and games where an audience spends money or points to change conditions for a character or colony it does not control (RimWorld Twitch mods, Crowd Control, platform currencies, Twitch Plays, Choice Chamber, Darwin Project, Rival Peak, AI-agent streams), plus creature-raising games with a learning inhabitant (Black & White, Creatures). State as of 2026-11-01. WorldBox, The Universim, Deisim, Reus 2 and Populous are covered elsewhere and excluded here.

Conventions: "(code default)" means a value read directly from the mod's source code on GitHub during this session. Dates in brackets give the age of a fact. "Estimate" or "inference" marks numbers I derived myself.

---

## 1. RimWorld Twitch integrations (Twitch Toolkit, its forks, Puppeteer) and the AI storyteller

### Takeaway
Twitch Toolkit runs on a free currency that viewers earn by watching. An active chatter earns about 30 coins every 2 minutes, scaled by their karma. Prices go from about 80 coins (a traveler group) to 6,500 (Toxic Fallout), so the cheap-to-doom ratio is roughly 1:80. Paid events are rationed three ways: a global per-event cap that resets every 15 in-game days, optional caps per karma type, and a karma system that cuts the earning rate of anyone who keeps buying harmful events. The base game's storyteller paces threats using "raid points" computed from colony wealth and colonist count, with adaptation and recovery gaps. The audience layer sits on top of that pacing rather than replacing it.

### Cited Findings

**Twitch Toolkit (upstream: hodlhodl1132/twitchtoolkit; repo created 2019-02-27, last push 2023-06-15, AGPL-3.0)**
- Repository metadata: created 2019-02-27, last pushed 2023-06-15. Forks such as javatunix/twitchtoolkit exist, with 115 commits. Viewer commands are `!balance`/`!coins`, `!buyevent`, `!buyitem`, `!karma`, `!purchaselist`. Admin commands include `!karmaround` (simulates a coin reward round), `!givecoins`, `!giveallcoins` (negative amounts take coins), `!togglestore`, `!togglecoins` and `!resetviewers` (needs two confirmations). — [hodlhodl1132/twitchtoolkit (GitHub API metadata)](https://github.com/hodlhodl1132/twitchtoolkit); [javatunix fork README](https://github.com/javatunix/twitchtoolkit)
- **Coin economy (code defaults):** StartingBalance = 150. CoinInterval = 2 (minutes). CoinAmount = 30. MinimumPurchasePrice = 60. Coins can optionally be synced with StreamElements or StreamLabs loyalty points (SyncStreamElements / SyncStreamLabs, both off by default). — [ToolkitSettings.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Settings/ToolkitSettings.cs)
- **Coin reward formula (code):** each round a viewer gets `ceil((CoinAmount + role bonuses) × (karma/100) × role multipliers × activity factor)`. Role bonuses: subscribers +10 coins and ×1.25, VIPs +5 and ×1.15, moderators +3 and ×1.05. With ChatReqsForCoins = true, the activity factor halves the reward if the viewer has not chatted for more than 30 minutes (TimeBeforeHalfCoins) and sets it to zero after 60 minutes (TimeBeforeNoCoins). — [Viewers.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Viewers.cs); [ToolkitSettings.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Settings/ToolkitSettings.cs)
- **Karma (code defaults):** StartingKarma = 100, KarmaCap = 140, KarmaMinimum = 10. BanViewersWhoPurchaseAlwaysBad = true. Optional gifting thresholds: you need at least 100 karma to send a gift and at least 33 to receive one. KarmaDecay is off by default (period 5). — [ToolkitSettings.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Settings/ToolkitSettings.cs)
- **Karma update rule (code):** each purchase is tagged Good, Neutral, Bad or Doom. The change is `price / divisor × curve`. Which divisor applies depends on the buyer's karma tier, measured as karma/cap with breakpoints at more than 0.55, more than 0.36 and more than 0.06.
  - Top tier divisors: Good 16, Neutral 36, Bad 24. A 1,500-coin Bad raid therefore costs roughly 62 karma before the curve factor.
  - Lower tiers use smaller divisors (Tier 3: Good 10, Neutral 24, Bad 18), so both rewards and punishments get larger.
  - Doom purchases subtract `price / 67 × (KarmaCap/100)`. The code has a ban branch for buyers whose karma tier is below 0.061.
  - Because karma multiplies coin income (karma/100), a griefer's earning rate collapses after a few harmful purchases. — [Store_Karma.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Store/Store_Karma.cs); [ToolkitSettings.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Settings/ToolkitSettings.cs)
- **Event caps and cooldowns (code defaults):**
  - EventsHaveCooldowns = true. Every store event has an `eventCap`, the number of purchases allowed within EventCooldownInterval = 15 in-game days.
  - The purchase log is global, not per viewer. A blocked buyer gets the chat reply "wait N days to purchase."
  - Optional global caps per karma type (MaxEvents, off by default): within MaxEventsPeriod = 5 days, at most 3 Bad (Doom counts against the Bad cap), 10 Good, 10 Neutral and 10 care packages. — [ToolkitSettings.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Settings/ToolkitSettings.cs); [Purchase_Handler.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Store/Purchase_Handler.cs); [Store_Component.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Store/Store_Component.cs)
- **Default store price list (code, StoreIncidents.xml; 74 entries; price / eventCap per 15 days / karma type):**
  - Weather: Clear weather 400/1 Good. Rain 350/1 Good. Rainy thunderstorm 250/1 Neutral. Foggy rain 300/1 Neutral. Fog 300/1 Neutral. Gentle snow 350/1 Neutral. Hard snow 450/1 Bad. Dry thunderstorm 450/1 Bad. Vomit rain 650/1 Neutral.
  - Hazards: Flashstorm 400/2 Bad. Heat wave 750/2 Bad. Cold snap 800/2 Bad. Solar flare 500/2 Bad. Eclipse 450/1 Bad. Tornado 800/1 Bad. Tornados 2,600/1 Bad. Blight 700/1 Bad. Psychic drone 400/1 Bad. Mad animal 200/2 Bad. Alphabeavers 600/1 Bad.
  - Doom: Volcanic winter 3,200/1. Toxic fallout 6,500/1.
  - Gifts and visitors: Aurora 200/1 Good. Animal tame 150/1. Ambrosia sprout 150/1. Inspiration 150/2. Meteorite 150/4 Neutral. Traveler group 80/3. Visitor group 200/3. Trader caravan 275/2. Orbital trader 350/2. Resource pod 300/1. Transport pod crash 600/1. Thrumbo passes 500/3. Party 400/3. Military aid 700/2. Revive random pawn 1,200/2.
  - Variable-price threats ("StoreIncidentVariables", maxWager 10,000): Raid, Drop raid, Sapper raid and Manhunter pack 1,500/2. Siege, Mechanoid raid and Infestation 2,500/2. Predators 2,500/1. Random or specific disease 1,000/2.
  - Pawn manipulation: Buy pawn (join colony) 1,500/2. Level pawn 1,500/2. Add trait 3,500/5. Remove trait 5,500/5. Items are priced individually, with a cap of 20. — [StoreIncidents.xml](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Defs/StoreIncidents/StoreIncidents.xml)
- **Voting storytellers (code defaults):** Toolkit can also let chat vote among VoteOptions = 3 candidate events for VoteTime = 2 (minutes). Optional timed storytelling fires every 10 (TimeBetweenStorytellingEvents). Built-in vote packs have mean-time-between (MTB) values: HodlBot 1 day (enabled by default), ToryTalker 2 days, UristBot 6 days, plus Milasandra and Mercurius (off by default). Voting Tory Talker and HodlBot events can also be bought directly for 750 and 600 coins. Subscribers get +1 extra vote. — [ToolkitSettings.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Settings/ToolkitSettings.cs); [StoreIncidents.xml](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Defs/StoreIncidents/StoreIncidents.xml)
- **Viewer-named colonists:** EnableViewerQueue = true and ViewerNamedColonistQueue = true. Joining the queue is free by default (ChargeViewersForQueue = false). — [ToolkitSettings.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Settings/ToolkitSettings.cs)
- **Pricing UI caveat:** setting the price on one event sets it for all of that event's variants (for example, a "buy pawn" price applies to every race). A pawn-join price has to go on the "joins colony" event, not on "spawn pawn". — [Steam Workshop discussion](https://steamcommunity.com/workshop/filedetails/discussion/2009500580/2145343824280853831)
- **Add-on: Toolkit – ChannelPoints** converts Twitch Channel Point redemptions into Toolkit coins. The amount per reward is set in the mod to match the Twitch reward. — [swemoney/Toolkit---ChannelPoints](https://github.com/swemoney/Toolkit---ChannelPoints)
- **Maintenance risk [2024]:** Steam comments report that viewers stopped earning coins after the RimWorld 1.5 update. — [Steam comments](https://steamcommunity.com/sharedfiles/filedetails/comments/3013874066)

**RimWorld Interactive Chat Services ("CAP"/RICS, ekudram; wiki last edited 2026-05-10), a 2025–26 successor-style mod**
- **Coins:** start at 100. Active viewers get 15 coins every 2 minutes, plus flat extras of +5 for subscribers, +3 for VIPs and +2 for moderators.
- **Karma:** starts at 100, minimum 0, recommended maximum 200 (configurable up to 1,000).
- **Karma decay:** 5% of current karma every 30 real minutes, only while the game is running.
- **Karma per purchase:** +0.35 per coin spent on store items. Base event changes are Good +5, Neutral +1, Bad −12 and Doom −25, plus `event price × 0.05` (so +5 per 100 coins). The UI caps the multiplier at 5.0.
- **Platforms:** the wiki sidebar has YouTube and "Kick (Beta)" settings pages. That points to multi-platform support, but this is an inference from the sidebar, not a stated fact. — [RICS wiki: Economy settings](https://github.com/ekudram/-cap-RimworldInteractiveChatServices/wiki/SettingsEnconomy)

**Puppeteer (GitHub: pardeike/puppeteer; MIT; created Dec 2019, last push June 2021)**
- Each viewer controls one colonist through a website (puppeteer.rimworld.live) after logging in with Twitch. YouTube login was "under review."
- Viewers can see the colonist's stats, change its appearance, set schedules and work priorities, and issue commands on a web map. The map refreshes only "a few times per second."
- Viewers wait in a queue, and the streamer assigns a queued viewer to a colonist.
- **Death rules:** deaths caused by viewers are compensated with a respawn ticket (the number of tickets is configurable, and with none left deaths are permanent). Deaths caused by the streamer are permanent. Any streamer interaction starts a configurable cooldown during which deaths count as the streamer's fault. Placing or removing the respawn "portal" also starts a cooldown. — [pardeike/puppeteer README](https://github.com/pardeike/puppeteer); [ecosyste.ms metadata](https://awesome.ecosyste.ms/projects/github.com%2Fpardeike%2Fpuppeteer)

**RimWorld base-game AI storyteller (the "director")**
- **Personalities:** Cassandra Classic follows a rising curve: push, then breathing room, then push again. Phoebe Chillax leaves long gaps between disasters but hits as hard at high difficulty. Randy Random has random events that "can be extremely difficult or unfair."
- **Inputs:** event triggers include colony wealth, building wealth, colonist count, animal count, recent colonist deaths or severe wounds, and time since the last major event. — [RimWorld Wiki: AI storytellers](https://rimworldwiki.com/wiki/AI_storytellers)
- **Threat scale and adaptation:** threat scale runs 0–500%. The presets from Peaceful to "Losing is fun" are 10/30/60/100/155/220%.
  - "Adaptation" rises over time and drops when the colony takes damage. Growth rate by preset: 0/25/75/100/100/100%. Impact: 100/100/100/90/70/40%.
  - An optional "wealth-independent" mode replaces wealth scaling with a time curve: years until maximum threat, 1–20, default 12. — [RimWorld Wiki: AI storytellers](https://rimworldwiki.com/wiki/AI_storytellers)
- **Raid points formula:** Raid Points = (Wealth Points + Pawn Points) × Difficulty × Starting Factor × Adaptation Factor.
  - Storyteller Wealth = items + creatures + 0.5 × buildings.
  - Wealth points are 0 up to 14,000 wealth, 2,400 at 400,000 and 4,200 at 1,000,000 (flat above that).
  - Pawn points rise from 15 per colonist (up to 10,000 wealth) to 140 at 400k and 200 at 1M. — [RimWorld Wiki: Raid points](https://rimworldwiki.com/wiki/Raid_points); [RimWorld Wiki: Wealth](https://rimworldwiki.com/wiki/Wealth)
- **Population intent:** "population intent" lowers the odds of joiner events as the colony grows, flattening at 20 colonists. The minimum factor is reportedly 0.20 for Randy and 0.05 for Cassandra and Phoebe (a community analysis cited on the wiki, so unofficial). — [RimWorld Wiki: AI storytellers](https://rimworldwiki.com/wiki/AI_storytellers)
- **Time base:** 1 in-game day = 60,000 ticks. At 1× speed (60 ticks/s) that is 16 min 40 s of real time. — [RimWorld Wiki: Time](https://rimworldwiki.com/wiki/Time)

### Inferences
- **Earning-time prices (estimate, from code defaults):** an active non-subscriber at karma 100 earns 30 coins per 2 minutes, about 900 coins per hour. That puts most weather at 250–450 coins, about 17–30 minutes of watching. A raid (1,500) is about 1 h 40 min. Toxic Fallout (6,500) is about 7 h 13 min.
- **Price ladder:** cheap good events are about 80–200 coins, weather about 250–800, standard threats 1,500–2,500 and doom 3,200–6,500. That is roughly 1 : 4 : 15 : 50 from cheapest to doom.
- **Real-time cooldown (estimate):** 15 in-game days at 1× speed is 250 real minutes, about 4 h 10 min. So most weather types can be bought only once per about 4 real hours at normal speed, and 2–4 times faster at speeds 2 and 3. Caps are therefore effectively shared real-time windows per event type, set by game speed.
- **Karma as "taxed griefing":** buying Bad events is allowed but lowers future income, so harmful influence becomes self-limiting rather than forbidden. RICS adds decay so that karma regresses over real time.
- **Puppeteer's lesson:** it separates who is to blame for a death (viewer vs streamer) and protects viewers from losing their character to the streamer's actions, using cooldown windows to settle ambiguous cases.
- **Two control models:** the storyteller is a pacing director computed from state (wealth, population, recent damage, adaptation). Audience spending in Toolkit happens alongside it. Several fork settings (vote packs with MTB days) let the audience choose among events the director generated, instead of buying them directly. These are two different models: viewers as buyers and viewers as electors.

### Gaps
- Exact Cassandra, Phoebe and Randy pacing parameters (minimum days between major threats, on/off cycle lengths) were not on the wiki page fetched. They live in the game's storyteller definitions, which I did not inspect.
- The body of `CalculateForCurve()` (the karma curve multiplier) and the full ban logic were not read. Karma deltas above are therefore "before curve."
- How `maxWager` (10,000) is used: the field name and the Toolkit "variables" event class suggest viewers can pay above the base price to scale raid or disease strength. I did not verify this in the code.
- No usage statistics (number of streamers or purchases) were found for Twitch Toolkit, RICS or Puppeteer.
- The GitHub user pardeike is commonly identified as the RimWorld modder "Brrainz" (author of the Harmony library). I did not verify that identity during this session.

---

## 2. Crowd Control and platform economics (Bits, Channel Points, Super Chat, TikTok gifts, Twitch Extensions)

### Takeaway
Crowd Control (Warp World) prices effects in coins at 100 coins = US$1. The standard split is 80:20 in the streamer's favor, and partners get 85:15 on Global Coins. Twitch Bits are always 80:20. Effects are rationed with streamer-set prices, per-user and global cooldowns, and optional price scaling: a percentage increase compounded on each trigger that decays back to base over time. Effects that fail to run are refunded. Platform cuts on the money that reaches the creator vary widely:
- Twitch keeps about 29% of what a viewer pays for Bits (US$1.40 per 100, streamer gets US$1.00).
- YouTube Super Chat pays 70%.
- TikTok LIVE pays 50% of net, so effectively much less of what the viewer paid.

### Cited Findings

**Crowd Control coin and revenue model**
- 1,000 coins = US$10, i.e. 100 coins per dollar.
- Coin types:
  - Global Coins are bought with card or PayPal and can be spent on any creator's link.
  - Local Coins come from exchanging Twitch Bits through the Extension, work on one channel only, and are "slightly more" expensive.
  - Bonus Coins are free: 50 per session by default, rising to 250 on a timer with Pro. Streamers can also convert Channel Points to coins or give subscribers a monthly allowance.
  - Charity Coins come from Tiltify donations. — [Crowd Control blog: How coins work](https://crowdcontrol.live/blog/how-crowd-control-coins-work)
- **Split and payout:** 80/20, including Twitch Extension revenue. Example: a 1,000-coin (US$10) spend gives the streamer US$8. Payout happens once earnings reach US$50, 30 days after the end of the month. — [Crowd Control blog: How coins work](https://crowdcontrol.live/blog/how-crowd-control-coins-work); [Crowd Control FAQ](https://crowdcontrol.live/faq)
- **Partner program:** an 85:15 split on Global Coins (5 points better), and revenue from Global Coins is booked only when they are spent, not when bought. Bits revenue stays 80:20.
  - Qualification thresholds conflict across pages: about US$150 gross before the split, about US$120 net, or US$100 gross over three consecutive months on a third-party page. The FAQ says requirements were raised after Gifted Coins launched. — [Crowd Control partner program](https://crowdcontrol.live/partner-program/); [Partner program blog](https://crowdcontrol.live/blog/everything-you-need-to-know-about-the-crowd-control-partner-program); [Fairly Odd Streamers (third-party)](https://fairlyoddstreamers.pages.dev/resources/sponsorships/crowd-control/)
- **Rationing mechanics:**
  - Each effect has a set coin cost, and chat can pool coins to afford big effects.
  - Coins are refunded if an effect doesn't trigger or the session ends. Effects stuck in queue for about 5 minutes are auto-refunded, and streamers can manually refund or retry.
  - "Price scaling" for high-impact effects raises cost with each use and cools back down over time. It is not enabled by default and has to be requested on Discord, according to the coins blog. — [Crowd Control blog: How coins work](https://crowdcontrol.live/blog/how-crowd-control-coins-work)
- **Advanced pricing (2024–2026 guides):**
  - Scale-up is a percentage applied to the current price. The official example is a 50-coin effect at 20% going to 60, then 72.
  - Scale-down can only be enabled with scale-up and returns the price toward base over a "scale duration." The price never drops below base.
  - Two cooldown types: individual (per viewer, per effect) and global (across all effects). Viewers see cooldown and scaling state on the effect list, with a red symbol when an effect is on cooldown. — [Crowd Control: Advanced pricing](https://crowdcontrol.live/how-to-customize-your-crowd-control-effects-with-advanced-pricing/); [Dec 2024 effects update](https://crowdcontrol.live/how-to-adjust-your-crowd-control-effects-december-2024-update/); [Effect Manager 2026 guide](https://crowdcontrol.live/blog/complete-guide-to-the-crowd-control-effect-manager-2026-update)
- **Feature set "as of June 2026":**
  - More than 200 game integrations with "thousands" of effects. Developer tools are free.
  - Effect durations (timed effects) for Pro and Max.
  - "Disrupts" (always-on interactions).
  - Limits on alternative triggers: Twitch Channel Rewards 3 free / 12 Pro / unlimited Max. TikTok Gifts 5 / 12 / unlimited. Follows, subs, raids, likes and shares only on Max.
  - Anonymous effect sending, and a "Chaos Bot" that sends effects automatically.
  - Goal overlays tracking coins, effects, revenue and users.
  - Subscription prices are not listed. — [Every Crowd Control feature as of June 2026](https://crowdcontrol.live/blog/every-crowd-control-feature-as-of-june-2026)
  - Note: Crowd Control blog pages fetched today all show a "Nov 1, 2026, 8:38 PM UTC" timestamp. That looks like a rendering timestamp, not a publication date.
- **Traction [May 2023]:**
  - More than 100 games supported and over 70,000 creators had used it.
  - Team of 10, CEO Matthew "Jaku" Jakubowski, undisclosed pre-seed round.
  - 2.0 beta added YouTube, TikTok, Discord and Facebook Gaming.
  - Example effects: summon enemies in Minecraft, spawn a shiny in Pokémon Emerald, shrink the avatar in RE4.
  - Jaku: "$100 is $100 of coins." — [TechCrunch, 2023-05-01](https://techcrunch.com/2023/05/01/crowd-control-interactive-stream/)

**Twitch Bits and Extensions**
- **Bits:** a viewer pays about US$1.40 for 100 Bits, and the streamer gets US$0.01 per Bit cheered, so Twitch keeps the US$0.40 gap at the base pack. Bulk packs are cheaper per Bit, and reported bundle prices vary by source. — [TechCrunch, 2016-06-29](https://techcrunch.com/2016/06/29/twitch-makes-cheering-exchange-rate-clear-one-penny-per-bit-for-streamers/)
- **Bits in Extensions [launch April 2018]:** 80% to the Partner or Affiliate broadcaster and 20% to the Extension developer. — [Twitch blog, 2018-04-23](https://blog.twitch.tv/en/2018/04/23/the-next-big-update-for-extensions-is-here-a036151cc309)
- **Bits in Extensions [current docs]:** revenue is "shared between the broadcaster and the Extension developer," with no percentage stated.
  - Products (SKUs) cost 1–10,000 Bits, with up to 250 products, and SKUs can't be changed once saved.
  - The Bits price is flat and doesn't vary by location.
  - A transaction can be broadcast to every viewer's Extension instance, which is useful for shared visible effects.
  - `isBitsEnabled` is false when the broadcaster can't receive Bits. — [Twitch Dev: Extensions monetization](https://dev.twitch.tv/docs/extensions/bits/)
- **Channel Points (free, earned by watching):** commonly reported as 10 points per 5 minutes watched plus a 50-point click-to-claim bonus about every 15 minutes. Subscriber multipliers are reported inconsistently (1.2×/1.4×/2× by tier vs a flat 2×). A calculator cites an average of about 220 points per hour, which is unverified. There is no official Twitch page among these sources. — [StreamScheme](https://www.streamscheme.com/how-to-earn-twitch-channel-points/); [AllThings.How](https://allthings.how/how-to-earn-and-use-channel-points-on-twitch); [Channel-point calculator](https://bot.isaiahcreati.com/tools/twitch-channel-point-calculator)

**YouTube and TikTok**
- **YouTube Super Chat and Super Stickers:** the creator gets 70%. **TikTok LIVE gifts:** the creator gets 50% of TikTok's *net* revenue from virtual items. — [Statista compilation](https://statista.com/statistics/1394689/live-streaming-video-content-creators-cut)
- **TikTok diamonds:** 1 diamond is about US$0.005 according to creator calculators (TikTok publishes no peg). One low-authority estimate puts the creator's effective share at about 33–40% of viewer spend after all fees. Both figures are unverified. — [BetterTok guide](https://bettertok.app/guides/tiktok-gift-earnings); [Influencer Marketing Hub](https://influencermarketinghub.com/live-gifting-earnings/)

### Inferences
- **Godling's prices against Crowd Control (estimate, using €1 ≈ US$1.08):**
  - 1 Godling credit (€0.05) is about 5 Crowd Control coins.
  - A Godling object (€0.15) is about a 15-coin effect, at the very cheap end.
  - Godling weather (€1.33) is about 140 coins, a typical mid effect, and is close to the US$1.40 a viewer pays for 100 Bits.
  - The daily large event (€25) is about 2,700 coins, in "pooled by chat" territory.
- **Godling's prices against Twitch Toolkit (estimate):** Godling's ladder from object to weather to big event is about 1 : 9 : 167, much steeper at the top than Toolkit's roughly 1 : 4 : 15 : 50. Toolkit's top tier is capped by event caps and karma, not by price alone.
- **Creator take by payment rail (estimate):** Twitch Bits through an Extension gives the broadcaster about 57% of what the viewer paid at base-pack prices (US$1.40 → US$1.00 → 80% = US$0.80). Crowd Control Global Coins give about 80–85% (before card fees). YouTube Super Chat gives 70%. TikTok gives 50% of net. So which payment rail Godling uses matters as much as its price list.
- **Fixing the "nobody can afford the big event" problem:** pooling plus auto-refund on failure or timeout plus visible cooldown state is Crowd Control's standard answer, and it also deals with "I paid and nothing happened."

### Gaps
- No public data on *which* Crowd Control effects sell most, average spend per viewer, or total paid out to creators. The "celebrating one year of 2.0" stats page returned 404.
- Current Crowd Control Pro and Max subscription prices weren't on the pages fetched.
- Official Twitch documentation for Channel Point earn rates wasn't retrieved. Whether the 80/20 Bits-in-Extensions split is still current is not stated in the current docs.

---

## 3. Other audience-intervention games and streams (Choice Chamber, Twitch Plays, Darwin Project, Rival Peak, 2023–2026 AI-agent streams)

### Takeaway
Earlier designs mostly used free votes rather than payment: Choice Chamber (2014–15), Twitch Plays Pokémon (2014), Darwin Project's Show Director plus Twitch extension (2017–18), and Rival Peak (2020–21). The lessons that last:
- Aggregation modes and supermajority rules help tame chaos.
- Vote windows need filler content while they run.
- A human or AI "director" layer should route the audience's will.

The closest precedent to Godling is Rival Peak: 12 AI contestants on 13 simultaneous 24/7 streams. Viewers helped or hindered them and voted out one per week, and it reached 100M+ minutes watched, but sources say it struggled to keep interest over months. AI-agent streams from 2025–2026 (Claude Plays Pokémon, AI Village, AGEMS "Survive or Die") mostly *forbid* viewer intervention so the run stays autonomous. Neuro-sama shows that a personality-driven AI streamer can draw very large paid support (hype-train records), but that is support for a personality, not purchased world events. I found no verified 24/7 LLM-agent stream that sells world-condition changes the way Godling plans to.

### Cited Findings

**Choice Chamber (Studio Bean)**
- Twitch chat votes on the environments, weapons, power-ups, enemy types and room layouts the streamer faces. — [Engadget, 2014-04-16](https://www.engadget.com/2014-04-16-twitch-funds-choice-chamber.html); [GamesBeat](https://gamesbeat.com/choice-chamber-has-twitch-viewers-help-or-torture-a-streamer/)
- **Funding:** a Kickstarter with a US$30,000 goal. Twitch pledged to match the remainder and the campaign funded on 2014-04-17, making it the first Twitch-funded game.
- **Release:** July 2015 on Steam and Humble, as a procedurally generated roguelike platformer accepting input from "an unlimited number of viewers." — [Twitch blog, 2014-04-16](https://blog.twitch.tv/en/2014/04/16/twitch-announces-support-of-studio-bean-s-choice-chamber-5677e0289690); [Tubefilter, 2015-07-17](https://tubefilter.com/2015/07/17/choice-chamber-twitch-chat-video-game/)

**Twitch Plays Pokémon [2014]**
- **Scale:** started 2014-02-12 and beat Red on 2014-03-01, after about 16 d 7 h 50 m. Twitch estimated over 1.16M participants (Guinness: 1,165,140). Peak simultaneous participation was about 121,000, with about 55M total views. Average concurrent viewers were above 80,000, with at least 10% participating.
- **Anarchy vs Democracy:** Democracy mode was added 2014-02-18 after a Rocket Hideout puzzle stalled the run. It tallied inputs over a window (usually 30 s) and ran the winner. It caused "start9" protest spam. The final system needed a *supermajority* to switch to Democracy but only a majority to switch back, shown on an on-screen meter. In Crystal, Democracy switched on automatically at the top of each hour.
- **Griefing and countermeasures:** spamming "start", deliberately jumping ledges, and "Bloody Sunday" (2014-02-23, about a dozen Pokémon released permanently). Fixes included throttling "start" inputs, user scripts to hide command spam, and a troll-detection program.
- **Lore:** chaos produced emergent lore (the "Helix Fossil" religion, "Bird Jesus") that became the main draw. — [Wikipedia: Twitch Plays Pokémon](https://en.wikipedia.org/wiki/Twitch_Plays_Pok%C3%A9mon)

**Darwin Project (Scavengers Studio) – Show Director [2017–2018]**
- One player per match (described in alpha coverage as chosen at random from the 11 in a lobby) is an invincible drone "Show Director" who hands out game-altering powers and obstacles. — [GamesRadar](https://www.gamesradar.com/darwin-project-is-a-game-hungry-for-viewers-as-much-as-players-but-can-this-unique-take-on-battle-royale-actually-work)
- The Twitch "Spectator Interactions" extension (July 2018) let viewers vote, with no setup, on who gets hunted, healing specific players, zone powers, resource rewards and crowd favourites. The Show Director launches the votes. — [Twitch blog, 2018-07-24](https://blog.twitch.tv/en/2018/07/24/scavengers-spectator-interactions-extension-makes-all-viewers-players-4a1b2ceb10f8); [Twitch blog, 2018-02-23](https://medium.com/twitch-news/lets-play-the-darwin-project-6064c000fd19)

**Rival Peak (Genvid / Pipeworks / dj2 for Facebook Watch; Dec 2020 – Mar 2021)**
- **Format:** 12 AI contestants in a stylised Pacific Northwest, on 24/7 per-character interactive livestreams over a 12-week season. Viewers could "help or hinder" contestants, and collectively voted one off each week. Wil Wheaton hosted a weekly recap show, "Rival Speak." — [Wikipedia: Rival Peak](https://en.wikipedia.org/wiki/Rival_Peak)
- **Mechanics (from Genvid's COO, Game Developer, 2021-03-05):**
  - Thirteen simultaneous 24/7 streams.
  - Viewers pooled points toward game-wide "Tribute" goals that unlocked cut-scenes and story.
  - Vote results took up to 90 s, so Match-3 and Memory mini-games were added to fill the wait.
  - Writers re-cut Rival Speak until midday on air day using events from hours earlier. "No one" knew the ending in advance.
  - After launch they added VODs, recaps, an interactive map and achievements.
  - About 10% of viewers used iOS after mid-season support.
  - Rival Speak averaged more than 8M views. — [Game Developer, 2021-03-05](https://www.gamedeveloper.com/business/the-real-time-evolution-of-i-rival-peak-i-)
- **Traction:** 100M+ minutes watched, viewers from more than 70 countries, more than 600,000 unique viewers interacting, and peak concurrency above 46,000 (Genvid/press figures). The Rival Speak average is about 13M per episode according to Wikipedia, which conflicts with Game Developer's "more than 8M." — [GamesBeat](https://gamesbeat.com/interactive-reality-show-rival-peak-hit-100m-minutes-watched-in-its-first-season/); [Wikipedia](https://en.wikipedia.org/wiki/Rival_Peak)
- **Limits:** a secondary overview notes the difficulty of sustaining long-term audience investment through AI contestants alone over months (weak source). — [meta-guide.com overview](https://meta-guide.com/virtualbeings/genvids-exploration-of-ai-characters-an-overview)

**AI-agent and AI-character streams, 2023–2026**
- **Nothing, Forever [Feb 2023]:** an endless AI-generated Seinfeld parody on Twitch.
  - It got a 14-day Twitch suspension over a transphobic stand-up bit and returned with a new cast. Viewership "has not matched" its earlier peak.
  - Influence came through chat feedback and a Patreon tier that put fans into the show as characters. I found no source for bits-picks-topic mechanics. — [Vice](https://www.vice.com/en/article/thousands-of-people-cant-stop-watching-ai-tv-show-nothing-forever/); [Dot Esports](https://dotesports.com/streaming/news/viral-ai-seinfeld-stream-nothing-forever-explained); [KSHB](https://www.kshb.com/news/national/the-seinfield-inspired-ai-show-returns-to-twitch)
- **Claude Plays Pokémon:** launched 2025-02-25 with Claude 3.7 Sonnet playing Pokémon Red. It continued with later models: a Manifold market concerns a Claude Opus 4.7 run [Oct 2026]. — [Wikipedia: TPP (later runs)](https://en.wikipedia.org/wiki/Twitch_Plays_Pok%C3%A9mon); [Tubefilter, 2025-02-26](https://www.tubefilter.com/2025/02/26/anthropic-claude-ai-twitch-plays-pokemon/amp/); [Manifold](https://manifold.markets/Anthem/what-will-happen-during-claude-opus-SP2yqy8Sty)
  - Early coverage cited a snapshot of about 2,000 concurrent viewers (search-result snippet; source page not opened).
- **AI Village (Sage / AI Digest), 2025–:**
  - From April to August 2025, any human viewer could message the agents' group chat. Viewers pushed off-topic requests, such as Warsaw itineraries and Wordle.
  - The team then closed chat to humans partway through a fundraising goal "to observe the fully autonomous efforts of the agents." It says it "strongly avoid[s] intervening."
  - Viewers can still watch, read logs, and inspect each agent's chain of thought and memory. — [AI Village: What we learned in 2025](https://aivillageblog.substack.com/p/what-we-learned-2025); [How the AI Village works](https://theaidigest.org/village/blog/how-the-ai-village-works)
- **AGEMS "Survive or Die" [Season 1, 2026]:** 13 AI agents share a real US$1,000 bank account drained by their compute costs, and must build a business to survive.
  - It runs as a 24/7 YouTube stream with daily recaps and weekly episodes.
  - Can viewers interact? "Not directly." The dashboard is read-only and the agents "don't know they're being watched."
  - Revenue was US$0.00 at the Day 11 recap. — [survival.agems.ai](https://survival.agems.ai/)
- **N3on AI clone [Sept 2026]:** Kick streamer N3on launched a 24/7 AI clone (via Higgsfield) to stream while he is offline, and drew backlash. — [Complex](https://www.complex.com/pop-culture/a/alex-ocho/n3on-responds-ai-streamer-backlash)
- **Neuro-sama (Vedal; Twitch relaunch 2022-12-19)**
  - Responds to chat and acknowledges donations. Disallowed output is replaced on-screen by the word "filtered."
  - Hype-train records: level 111 on 2025-01-01 (84,904 subs, 1.2M bits); level 123 on 2025-12-23; level 126 on 2026-01-05 (126,273 subs, 1.19M bits).
  - The channel peaked at 343,215 active subscribers on 2026-01-09, third most-subscribed on Twitch at the time.
  - About 1.01M Twitch followers [Nov 2026].
  - Two-week ban in January 2023 for "hateful conduct." — [Wikipedia: Neuro-sama](https://en.wikipedia.org/wiki/Neuro-sama)
- **TikTok-gift Minecraft mods (2023–2026):** TikTok Live Connector, TikTok Chaos and StreamTK map gifts, likes, follows and comments to deterministic in-game actions such as spawning mobs, giving items and applying effects. TikTok Chaos states that LIVE comments are *never* executed as Minecraft or OS commands. — [TikTok Live Connector (CurseForge)](https://www.curseforge.com/minecraft/mc-mods/tiktok-live-connector); [TikTok Chaos (CurseForge)](https://www.curseforge.com/minecraft/mc-mods/tiktok-chaos); [SuperStream / StreamTK](https://speedgot.ajg0702.us/resources/107642)

### Inferences
- **Free-vote and paid-buy systems feel different.** TPP and Darwin Project aggregate many viewers into one decision (one shared intervention per window). Toolkit and Crowd Control let individuals buy (many interventions, rationed by price and cooldown). Rival Peak combined both: pooled tribute goals plus votes plus individual help/hinder. A daily "large event" funded by pooling (Crowd Control pooling, Rival Peak tributes) fits Godling's €25 tier.
- **Waiting needs filling.** Rival Peak's 90-second vote latency needed filler mini-games. Godling's LLM reaction latency (perception, then deliberation, then action) needs an equivalent instant acknowledgement so a payer sees *something* right away.
- **Autonomy-focused projects close the input channel.** AI Village and Survive or Die keep the agent's run "authentic." Godling's "can't buy decisions" rule is a middle path: the audience changes the *world*, never the *mind*. No precedent found does exactly this with an LLM agent.
- **Moderation risk carries over to AI characters.** Nothing, Forever's ban and Neuro-sama's early ban show that LLM output reacting to audience-supplied context can get a channel suspended. Output filtering that is visible on stream ("filtered") is one accepted pattern.

### Gaps
- I could not find any verifiable trace of "ARK by arkreality," a "Nixi" AI VTuber in Minecraft, or a "Nodus" Minecraft TikTok-gift AI stream. Searches returned unrelated ARK viewership news (VCR ARK) and Neuro-sama. These may be small channels, misremembered names, or not indexed.
- I found no audience-intervention feature for "Dead Static Drive" (a narrative driving horror game). The name may be confused with another title.
- No viewer-count data for Claude Plays Pokémon in 2025–26, and no verified figure for whether it accepts chat input (my understanding is that it does not, but this wasn't confirmed this session).
- No reliable revenue or traction figures for Choice Chamber sales, or Darwin Project extension usage.
- No 2024–2026 example found of an *LLM agent* reacting to *paid world events* with published pricing.

---

## 4. Black & White (2001), Black & White 2 (2005) and other learning-inhabitant games (Creatures; Tamagotchi-style persistence)

### Takeaway
Black & White's creature was a belief–desire–intention agent. Desires were simple perceptrons, and opinions about how to satisfy them were learned as decision trees. Players shaped it by slapping (punish) and stroking (reward), by demonstration under a "learning leash," and with compassion and aggression leashes. It won AI awards and Guinness's "most intelligent being in a game" (2003). The common complaints were opaque learning, micromanagement and under-use of the creature. Black & White 2 moved toward menus where players could set, review and edit learned behaviour and assign roles (builder/gatherer/soldier). Reviewers called this "watered down"; Lionhead called it "vastly improved." Creatures (1996) had earlier used tickle and slap on neural-network norns whose drives functioned as reward and punishment.

### Cited Findings

**Black & White creature design and learning**
- **Architecture:** Richard Evans built the AI using Michael Bratman's belief–desire–intention model.
  - Beliefs are lists of data about world objects.
  - Desires are goals expressed as simplified perceptrons.
  - Opinions, meaning how to satisfy a desire, are decision trees.
  - For each desire, the creature picks the belief with the best opinion, and that becomes its intention. — [Wikipedia: Black & White](https://en.wikipedia.org/wiki/Black_%26_White_(video_game))
- **Mixed techniques and unpredictability:** Evans combined techniques from "apparently competing AI paradigms," including perceptron training and decision-tree learning. He has said the creature's actions were hard to predict even for him. — [Wikipedia: Richard Evans](https://en.wikipedia.org/wiki/Richard_Evans_(AI_researcher))
- **Training:** reinforcement through slapping (discourage) and stroking (approve). The creature remembers and gradually changes behaviour. Taught behaviours include stocking the village store, eating, attacking or impressing enemy villages, and performing miracles. Fighting is trained in one-on-one creature battles. — [Wikipedia: Black & White](https://en.wikipedia.org/wiki/Black_%26_White_(video_game))
- **Leashes:** three leashes. One makes the creature attentive while the player demonstrates an action (the learning leash). The other two push benevolent or malevolent behaviour. Any leash can be tied to a building to restrict roaming. — [Wikipedia: Black & White](https://en.wikipedia.org/wiki/Black_%26_White_(video_game))
- **Species and alignment:**
  - Ape learns fast but is weak. Tiger is strong but learns slowly. Others are unlocked via Silver Reward Scrolls.
  - The creature grows over the game, and its alignment is separate from the player's.
  - Appearance shows alignment and fatness: evil wolves get glowing eyes and fangs, good ones turn purple and glow. Each form uses 7 meshes and 3 texture sets, with two-way blends. — [Wikipedia: Black & White](https://en.wikipedia.org/wiki/Black_%26_White_(video_game))
- **Postmortem (Peter Molyneux, 2001-06-13):**
  - The creature learns through practice and reinforcement "like… a clever puppy," "mirrors" the player, and develops its own personality, so no two are the same.
  - The design avoided random elements, and anything the player can do can be taught.
  - The team rated the creature AI "absolutely spot-on."
  - Human creatures were cut because slapping a child, woman or man felt wrong and human-paced learning couldn't be balanced. Ants, fish and flyers were cut because they broke the game.
  - The team was about 6 at the start and 9 by February 1998. The game had over 1M lines of code and took about 3 years. — [Game Developer: Postmortem](https://gamedeveloper.com/design/postmortem-lionhead-studios-i-black-white-i-)
- **Reception:**
  - Praise for the "amazing," "revolutionary" creature AI (Computer Games Magazine, Game Revolution, GamePro).
  - Evans won a Game Developers Choice award for Excellence in Programming, and PC Gamer gave it Best AI.
  - Guinness World Records 2003 named it the "most intelligent being in a game."
  - Criticism: "frequent micromanagement and ambiguous objectives" (Playboy). GameSpy later named it the most over-rated game of all time, citing poor use of the creatures.
  - Sales: over 2M, and about 2.5M on PC by 2006. Released 2001-03-27 in North America. — [Wikipedia: Black & White](https://en.wikipedia.org/wiki/Black_%26_White_(video_game))
- **Black & White 2 (2005):**
  - Molyneux said creature learning in the first game was "flawed" and "vastly improved" in the sequel. — [GameSpot Q&A (search snippet; page returned 403)](https://www.gamespot.com/articles/black-and-white-2-updated-qanda-lessons-from-black-and-white-tech-details-creature-ai/1100-6123145/)
  - Reviews said creature training was "watered down" and "Black and White Lite," and that the original's example-based teaching gave way to direct commands and combat moves. A menu now lets players set behaviour early, revisit everything taught, and adjust it at any time. — [Hexus review](https://hexus.net/gaming/reviews/pc/3859-black-white-2/?page=3); [GameWatcher review](https://www.gamewatcher.com/black-white-ii/review); [Game Over Online review](https://www.game-over.net/reviews/pc/Black_amp;_White_2.html) (attributions from search snippets)
  - Creature roles were builder, gatherer and soldier. — [Gamepressure guide](https://www.gamepressure.com/blackandwhite2/basics/z58940)

**Creatures (Millennium Interactive / Steve Grand, 1996)**
- Norns have simulated drives. A drive *rising* is punishment and a drive *falling* is reward, giving behaviourist learning.
- Early on, the player's tools are tickle (reward) and slap (punish).
- First-generation norns use a 952-neuron, about 5,000-connection network. Grand said they could learn and generalise but "could not think."
- Emergent behaviour included two norns learning to play catch. — [Wikipedia: Creatures series](https://en.wikipedia.org/wiki/Creatures_(video_game_series)); [Alan Zucconi: The AI of Creatures](https://www.alanzucconi.com/2020/07/27/the-ai-of-creatures/)

### Inferences
- **Feedback that clearly targets one behaviour.** The main failure the sources point to is credit assignment: the player can't tell what the creature learned from a slap or stroke ("ambiguous," "micromanagement"). B&W2's fix was to show the creature's learned state and let players edit it directly, at the cost of the magic. For Godling, the matching need is legible cause and effect: viewers should *see* the agent attribute a change to the event they bought ("the rain soaked my planks, so I'll build a roof"), without being able to edit its mind.
- **Influence-not-control is a proven fantasy.** B&W players accepted an autonomous creature they could only influence, and the creature was the game's most-praised element. The frustration came from slow or opaque feedback loops, not from the lack of control.
- **Visible, cumulative identity:** B&W's alignment- and weight-driven appearance changes and Creatures' emergent behaviour both turned hidden learning into a visible identity. That suits a 24/7 character whose history should be readable at a glance.
- **Moral limits on punishment:** Lionhead dropped human creatures because slapping humans felt wrong. A humanoid builder that viewers can *harm* via events carries a similar tone risk.

### Gaps
- I could not open Evans' own technical write-ups (for example his AI Game Programming Wisdom chapter or GDC talks). Specifics such as how many examples it takes to learn, how slap/stroke maps to desire weights, and observation-learning details are not confirmed here.
- The Eurogamer 25th-anniversary retrospective (2026) was not fetchable, and its claims about links to modern AI weren't read.
- I collected no sourced facts on Tamagotchi (death or neglect mechanics, sales) or Spore's creature stage in this session.

---

## 5. Cross-cutting design patterns: cooldowns, per-viewer limits, global caps, escalating prices, director pacing, visible reaction, anti-griefing

### Takeaway
The systems above converge on a layered rationing stack:
1. A price tier per intervention.
2. A global per-event cap within a time window.
3. Optional per-category caps (good/bad/doom).
4. Per-viewer cooldowns.
5. Price escalation that decays.
6. Reputation (karma) that taxes harmful buyers.
7. Refunds when an effect cannot visibly fire.
8. A "director" that keeps baseline pacing tied to the inhabitant's state.

Visible reaction is handled by chat confirmations, overlays, broadcast-to-all extension messages and recaps. Griefing is handled by throttling, supermajority switches, karma or bans, and never executing free text as commands.

### Cited Findings
- **Global per-event cap in a window:** Toolkit eventCap per 15 in-game days, with per-type karma caps (3 bad / 10 good / 10 neutral per 5 days) and a chat reply telling buyers how many days to wait. — [Purchase_Handler.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Store/Purchase_Handler.cs); [ToolkitSettings.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Settings/ToolkitSettings.cs)
- **Per-viewer and global cooldowns, plus compounding price scaling that decays back to base:** Crowd Control. — [Crowd Control: Advanced pricing](https://crowdcontrol.live/how-to-customize-your-crowd-control-effects-with-advanced-pricing/)
- **Reputation tax on harm:** Toolkit karma multiplies coin income, with a ban branch for doom spammers. RICS adds 5% karma decay per 30 minutes. — [Store_Karma.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Store/Store_Karma.cs); [RICS wiki](https://github.com/ekudram/-cap-RimworldInteractiveChatServices/wiki/SettingsEnconomy)
- **Activity gating of free currency:** Toolkit halves coin income after 30 minutes without chatting and stops it after 60. Crowd Control gives 50 free coins per session. — [Viewers.cs](https://github.com/hodlhodl1132/twitchtoolkit/blob/master/TwitchToolkit/Viewers.cs); [Crowd Control blog](https://crowdcontrol.live/blog/how-crowd-control-coins-work)
- **Pooling for big effects, refund on failure or timeout (about 5 min):** Crowd Control. — [Crowd Control blog](https://crowdcontrol.live/blog/how-crowd-control-coins-work)
- **Community goal unlocks:** Rival Peak "Tributes" unlocked cut-scenes and story. — [Game Developer](https://www.gamedeveloper.com/business/the-real-time-evolution-of-i-rival-peak-i-)
- **Director pacing tied to state:** RimWorld threat points from wealth and colonists, adaptation that drops after damage, and personality-specific gap patterns. — [RimWorld Wiki: Raid points](https://rimworldwiki.com/wiki/Raid_points); [RimWorld Wiki: AI storytellers](https://rimworldwiki.com/wiki/AI_storytellers)
- **Director as a role:** Darwin Project's Show Director launches viewer votes and dispenses powers. — [Twitch blog, 2018](https://blog.twitch.tv/en/2018/07/24/scavengers-spectator-interactions-extension-makes-all-viewers-players-4a1b2ceb10f8)
- **Aggregation against chaos:** TPP's Democracy needed a supermajority to enable and a simple majority to revert, used a 30-second tally window, auto-enabled hourly in Crystal, and throttled "start." — [Wikipedia: TPP](https://en.wikipedia.org/wiki/Twitch_Plays_Pok%C3%A9mon)
- **Blame attribution and protection windows:** Puppeteer refunds viewer-caused deaths with respawn tickets and treats deaths during a streamer-interaction cooldown as the streamer's fault. — [pardeike/puppeteer](https://github.com/pardeike/puppeteer)
- **Visible acknowledgement channels:**
  - Twitch Extension transactions can be broadcast to every viewer's instance. — [Twitch Dev docs](https://dev.twitch.tv/docs/extensions/bits/)
  - Crowd Control has effect and goal overlays and shows cooldown and scaling state in the effect list. — [Crowd Control features 2026](https://crowdcontrol.live/blog/every-crowd-control-feature-as-of-june-2026)
  - Rival Peak added recaps, VODs and a weekly host show built from the latest events. — [Game Developer](https://www.gamedeveloper.com/business/the-real-time-evolution-of-i-rival-peak-i-)
- **Input sanitisation:** TikTok Chaos never executes LIVE comments as game or OS commands. — [TikTok Chaos](https://www.curseforge.com/minecraft/mc-mods/tiktok-chaos)
- **Closing the channel for autonomy:** AI Village shut human chat input after about four months to observe autonomous behaviour. — [AI Village 2025 retrospective](https://aivillageblog.substack.com/p/what-we-learned-2025)

### Inferences
- **Typical cap depth (estimate):** an effect commonly faces three independent limits: its own cap or cooldown, a category cap, and a per-user cooldown. Price alone is never the only limit for harmful effects. In Toolkit, the cheapest harmful events still have caps of 1–2 per 15 days.
- **Cooldowns reset in different units.** Toolkit counts in-game days, which shift with game speed; Crowd Control counts real time. For a 24/7 world with its own day/night cycle, choosing world-time or real-time cooldowns changes how often each weather or event type can recur.
- **Director plus market hybrid.** The most robust precedent is a director that keeps baseline pacing (RimWorld) with a market layered on top. Neither Toolkit nor Crowd Control lets the director *veto or delay* purchases based on the inhabitant's state, beyond fixed caps. That is an open design space.

### Notable for Godling
- Twitch Toolkit default prices (in coins earned at about 900/hour of active chat): weather 250–800, standard threats 1,500–2,500, doom 3,200–6,500. Each weather type is capped at 1 per 15 in-game days (about 4 real hours at 1×), set globally. Godling's €1.33 weather is similar in money to 100 Bits (US$1.40).
- Karma that multiplies future earning power, plus decay (RICS: 5% per 30 minutes), makes griefing self-limiting without banning "bad" events outright.
- Crowd Control's scale-up (for example +20% per trigger, compounding) with timed scale-down and per-user plus global cooldowns is a ready-made model for escalating prices on popular effects like weather.
- Pool funding with auto-refund on failure or timeout (about 5 minutes) fits a once-per-day €25 event, as do Rival Peak-style community "tributes" that unlock it.
- Rival Peak is the closest prior art: 24/7 AI characters, help/hinder, votes, more than 100M minutes in 12 weeks. Its reported weak spot was keeping interest over months, and it needed recaps, VODs and a weekly show.
- Black & White's lasting lesson: influence-not-control is accepted and loved, but learning must be legible. B&W2's menu-based editing traded away magic for clarity. Godling should make attributions visible ("because it rained…") without exposing its mind to editing.
- Puppeteer-style blame windows suggest separating "viewer-caused harm" from the agent's own mistakes, perhaps with compensation such as auto-repair of event-caused damage.
- AI-agent streams (AI Village, Survive or Die) closed viewer input to protect autonomy. Godling's "world, not mind" rule is a distinct middle position with little direct precedent as of 2026-11-01.
- Payment rail matters:
  - Twitch Bits through an Extension gives the broadcaster about 57% of what the viewer paid (US$1.40 → US$1.00 → 80%).
  - Crowd Control Global Coins give 80–85%.
  - YouTube Super Chat gives 70%.
  - TikTok gives 50% of net.

### Gaps
- No published data on how often paid events make a stream's character visibly react, or on viewer satisfaction or retention against cap depth. Statements about "visible reaction" here are design inferences from feature sets.
- No primary source found on per-viewer *daily spend limits* (as opposed to cooldowns) in Crowd Control or Toolkit. Crowd Control's Pro "custom coin amounts and limits" exists but its details weren't retrieved.
