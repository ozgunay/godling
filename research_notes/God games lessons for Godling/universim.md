# The Universim (Crytivo): structure, mechanics, in-game economy and business, as of 2026-11-01

Source note: Steam announcement texts were pulled in full from Steam's public news API (`api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=352720`, 221 announcements, the newest dated 2024-12-24). Each is cited by its Steam news URL (`store.steampowered.com/news/app/352720/view/<gid>`). Many mechanics posts are developer **design devlogs** written before the feature shipped, so each is labelled with its date. Numbers from them may have changed by 1.0. SteamDB, Gamalytic, VG Insights (now Sensor Tower), the Fandom "God Powers" page, TV Tropes and the Kickstarter page all refused automated fetches (403/402/429/redirect).

## 1. History and business: developer, Kickstarter, early access, 1.0, price, DLC, sales, reviews, reception of the long development

### Takeaway
The Universim is a debut game from Crytivo, a small US indie studio founded in 2013 by Alex Koshelkov. Its timeline:
- Kickstarter in Apr–May 2014: $387,345 raised against a $320,000 goal.
- Steam Early Access on 2018-08-28.
- Full 1.0 release (out of Early Access) on 2024-01-22, after about 10 years of development.
- PC only (Windows/macOS, Linux listed but "TBA" today). No console port was found.

It sells for $29.99 with one small cosmetic/collector DLC and no microtransactions. Estimated lifetime sales are about 0.2–0.5M copies and roughly $3.5M–$10M gross, depending on the tracker. Steam reviews sit at about 79–81% positive across about 10.1–10.7K reviews. Crytivo moved its focus to a new game (Farm Folks) in May 2024. The last Steam announcement or patch is v1.0.2 on 2024-12-24. Concurrent players averaged about 57 in Oct 2026.

### Cited Findings
**Developer, team, engine**
- Developer and publisher: Crytivo; creative director Alex Koshelkov. Engine: "Prometheus", a custom engine built on Unity. Platforms listed: Windows, macOS, Linux; single-player — [Wikipedia: The Universim](https://en.wikipedia.org/wiki/The_Universim)
- Crytivo was founded in 2013 by Alex Koshelkov, and Wikipedia gives its headquarters as **San Diego, California**. That article carries conflict-of-interest and citation tags. Crytivo also publishes third-party games: Roots of Pacha (Apr 2023; Soda Den took the publishing rights back in May 2023 after a revenue-share dispute), Serin Fate, Prehistoric Kingdom and others — [Wikipedia: Crytivo](https://en.wikipedia.org/wiki/Crytivo). **Conflict:** the 1.0 press release is datelined **Dallas, Texas**. It gives the founding year as 2014 in one place and 2013 in another — [Gamespress 1.0 press release](https://gamespress.com/The-Universim-10-is-now-Live-on-Steam)
- Team size: Crytivo never gave a headcount. In 2023 it called itself an "extremely small team with a limited budget". It said combat "was never planned" and that it would not expand combat — [Steam: Progress Update, 2023-06-02](https://store.steampowered.com/news/app/352720/view/5151601211231078833). In 2018 Koshelkov called it a "small team" and said "We don't cut corners, but that unfortunately sometimes delays content" — [Game Developer, 2018-10-03](https://www.gamedeveloper.com/game-platforms/how-i-the-universim-i-s-god-game-twist-charmed-early-access-players)
- Prometheus handles planet generation, life simulation, dynamic events, pathfinding and resource distribution. The Beta rework (Dec 2019) halved planet generation from more than 2 minutes, roughly tripled the number of objects on a planet, and replaced the pathfinding to fix the "Standing Nuggets" bug, the most-reported bug of all time — [Steam: The Universim is entering Beta, 2019-12-17](https://store.steampowered.com/news/app/352720/view/3370312875267221615)

**Kickstarter and funding**
- Kickstarter goal: $320,000 (April 2014). Total raised: $387,345 — [Wikipedia](https://en.wikipedia.org/wiki/The_Universim)
- About 12,000 backers — [Cliqist, Aug 2015, "A year after a $387K Kickstarter"](https://cliqist.com/2015/08/28/a-year-after-a-387k-kickstarter-the-universim-is-back-for-more/) (figure from the search summary; the page was not opened)
- Campaign start, about 28 Apr 2014 — [GameWatcher](https://gamewatcher.com/news/2014-28-04-the-universim-on-kickstarter-a-planet-management-god-game)
- With 12 days left, more than 7,500 backers had pledged about $210K; the URL dates this to 12 May 2014 — [GameWatcher](https://gamewatcher.com/news/2014-12-05-planet-god-game-the-universim-with-12-days-on-kickstarter-needs-110k-more)
- Fully funded report, 21 May 2014 — [Worthplaying](https://worthplaying.com/article/2014/5/21/news/92387-the-universim-fully-funded-through-kickstarter/)
- On 2014-06-13 PayPal put a $1M minimum reserve on Crytivo's account, blocking access to the funds. Crytivo addressed it publicly on 2015-05-15 — [Wikipedia](https://en.wikipedia.org/wiki/The_Universim)
- After the Kickstarter, Crytivo kept selling "website backer" tiers on its own site — [Crytivo support](https://support.crytivo.com/article/20-what-is-the-difference-between-kickstarter-backer-and-website-backer). Stretch goals were still being "unlocked" in 2015–16, for example "Nugget Customizer" on 2015-10-21 and "New Stretch Goal Reached" on 2016-01-26 (Steam announcement titles via the news API).

**Timeline**
- Pre-alpha for alpha-tier backers: 2015-09-15. Alpha: 2016-08-02. Medieval era: Oct 2017. Modern era: Dec 2018. Space era: Dec 2021. Full release: 2024-01-22 — [Wikipedia](https://en.wikipedia.org/wiki/The_Universim)
- A Steam "Mother Planet" demo patch was released on 2015-09-15. A public Steam demo followed on 2017-07-11 — [Steam: Demo available, 2017-07-11](https://store.steampowered.com/news/app/352720/view/2078825132651398974)
- Steam Early Access began on 2018-08-28 — [Steam store page](https://store.steampowered.com/app/352720/The_Universim/); [Steam: Now Available on Steam, 2018-08-28](https://store.steampowered.com/news/app/352720/view/2444779293806080763)
- The EA launch carried a 10% launch discount. The game reached the **#1 Top Seller** spot on day one, and the launch was "a bit bumpy" — [Steam: Launch recap, 2018-08-29](https://store.steampowered.com/news/app/352720/view/2447032361185051078); [Game Developer](https://www.gamedeveloper.com/game-platforms/how-i-the-universim-i-s-god-game-twist-charmed-early-access-players)
- Beta began with the Feb 2020 update. The developers said "more than 500,000 people" had wishlisted the game — [Steam: entering Beta, 2019-12-17](https://store.steampowered.com/news/app/352720/view/3370312875267221615)
- Apr 2023: "We did what we could with an extremely limited budget... We managed to deliver almost all of our promises, but it took some time." Crytivo estimated "no more than 3 months" until release. The actual release came about 9.5 months later — [Steam: The last mile is always the longest, 2023-04-05](https://store.steampowered.com/news/app/352720/view/5121196841285545411)
- 1.0 released on 2024-01-22 for $29.99 with a 25% launch discount. It shipped 200+ techs, 15 god powers, Toxic/Ice/Lava/Terrestrial planets, a "complete storyline", Exile Villages, quests and 600+ voiced lines. Crytivo again cited "over half a million Steam wishlists" — [Gamespress 1.0 press release](https://gamespress.com/The-Universim-10-is-now-Live-on-Steam)
- The 1.0 announcement said "around 4,552 commitments" had gone in since the previous update. Six languages were **removed**: Turkish, Latin American Spanish, Traditional Chinese, Czech, Italian and Japanese. Eight stayed: English, Russian, German, French, Spanish, Portuguese, Simplified Chinese and Korean — [Steam: 1.0 is Finally Here!, 2024-01-22](https://store.steampowered.com/news/app/352720/view/5510784213113218236); Japanese coverage of the removal: [Automaton, 2024-01-24](https://automaton-media.com/articles/newsjp/20240124-280024/)

**After 1.0 (full list from the Steam news API)**
- Patches after launch: Day-1 stability patch (01-23), Day-3 hotfix, then hotfixes #3–#6 (Jan 27, Feb 2, Feb 10, Mar 10), and a bug-fix patch on 2024-04-02.
- **2024-05-22, "What the Future Holds"** (signed by Alex): "our focus will shift entirely to Farm Folks", with "The Universim's final content update on the horizon". Bug fixes, QoL and balance work were promised to continue. The post planned a **Tower of Babel resource-sink building** with a colony mini-game and leaderboard, because "many players have amassed substantial resources with no clear direction for their use", expected "within the next 1-2 months" — [Steam](https://store.steampowered.com/news/app/352720/view/5741605105604108334)
- **2024-07-15**: modding announced, plus a bundle with VEOM Studio's *The Crust* — [Steam](https://store.steampowered.com/news/app/352720/view/6000566704280770002)
- **2024-09-13, v1.0.1 "Creator Power" patch**: modding chapter I (custom factories, made in-game and shared through Steam Workshop), and a **Creator Panel** (unlimited resources and workforce, drones, UFOs, every power) enabled in settings — [Steam](https://store.steampowered.com/news/app/352720/view/6250522009517508396)
- **2024-12-24, v1.0.2 "The Cauldron"**: mines and custom resources become moddable. Adds an experimental **Cauldron** building that "heavily relies on your god powers and direct player actions", with minister AI fixes. It said "Creator Mode" would come back and that electric flying cars were "within the next 1–2 patches" — [Steam](https://store.steampowered.com/news/app/352720/view/1786573930788015)
- The news API lists **no Steam announcements after 2024-12-24** up to 2026-11-01. The returned feed held 221 items against a requested count of 400 — [Steam news API](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=352720&count=400&maxlength=1&feeds=steam_community_announcements)

**Price, DLC, bundles**
- Price: **$29.99** (SteamSpy `price`/`initialprice` 2999) — [SteamSpy API](https://steamspy.com/api.php?request=appdetails&appid=352720); also [Raijin](https://raijin.gg/app/352720/The_Universim)
- EU price: **€27.99**. Only DLC: "The Universim – Collector's Pack (Vol 1)" at €5.69. Bundles: Collector's Edition (€33.68), "Gods & Cults" (€52.49 before discount), and "Sintopia x The Universim" (€62.98 before discount). Store lists 8 languages and 16 GB RAM minimum (32 GB recommended). Not compatible with M1 Macs. SteamOS/Linux requirements show "TBA" — [Steam store page](https://store.steampowered.com/app/352720/The_Universim/)
- A reader comment from 2018 describes the Collector's bundle as a 150-page art book, about 1,000 art assets and a 34-track soundtrack (a user comment, not official) — [GamingOnLinux comments, Aug 2018](https://www.gamingonlinux.com/2018/08/the-universim-is-now-officially-available-in-early-access-on-steam/page=1)
- 1.0 launch sale in Japan: 25% off, ¥2,235 until 2024-02-06 — [Automaton](https://automaton-media.com/articles/newsjp/20240124-280024/)
- Review-mining puts the community's "fair price" at $9.99–$14.99. "Wait for a sale" is a common recommendation — [Vaporlens](https://vaporlens.app/app/352720/the_universim.md)
- The game has also been sold on GOG and Humble Store — [GamingOnLinux, Dec 2023](https://gamingonlinux.com/2023/12/god-sim-city-builder-the-universim-releases-10-on-january-22-2024)

**Sales and owner estimates (all third-party estimates)**
- SteamSpy: **200,000–500,000 owners**; 8,207 positive and 1,930 negative reviews; current CCU 87 — [SteamSpy API, fetched 2026-11-01](https://steamspy.com/api.php?request=appdetails&appid=352720)
- Raijin.gg: about **193.5K copies**, about **$3.48M gross** ("medium confidence"; up from $3.40M in May 2026). 10,681 reviews at 79.4% positive. 191.5K followers. Estimated wishlists 296,905, down from 462,404 in May 2026 — [Raijin.gg, as of 2026-11-01](https://raijin.gg/app/352720/The_Universim)
- SteamData.ai: about **475.1K units** and **$9.84M gross**. This comes from the search snippet only; the page was not opened — [steamdata.ai](https://steamdata.ai/game/352720)
- Gamalytic and VG Insights (now Sensor Tower): pages refused automated access, and Gamalytic's API needs a key — [Gamalytic](https://gamalytic.com/game/352720)
- Crytivo has never published a sales figure. Its only published metric is ">500K wishlists" — [Gamespress](https://gamespress.com/The-Universim-10-is-now-Live-on-Steam)

**Players over time (SteamCharts)**
- All-time peak: **2,819** concurrent players, most likely Jan 2024.
- EA launch, Sep 2018: average 396, peak 1,861.
- 1.0 window: Jan 2024 average 581, peak 2,771; Feb 2024 average 716.5, peak 2,157.
- Decay after 1.0: Mar 2024 average 420 → Jun 2024 160 → Jan 2025 142 → Jul 2025 91 → Oct 2026 average 57.1, peak 138.
- Earlier spikes match content drops: Feb 2020 Beta (average 372, peak 1,442) and Feb 2022 (average 312, peak 1,561).
- Source: [SteamCharts](https://steamcharts.com/app/352720)

**Reviews and critics**
- Steam store (fetched 2026-11-01): English all-time "Mostly Positive", **79% of 5,155**. Recent 30 days: 71% of only **14** reviews — [Steam store](https://store.steampowered.com/app/352720/The_Universim/)
- In Oct 2018, about six weeks into EA, the game had nearly 1,000 Steam reviews, "Mostly Positive" — [Game Developer](https://www.gamedeveloper.com/game-platforms/how-i-the-universim-i-s-god-game-twist-charmed-early-access-players)
- Metacritic: **no Metascore** (only 2 critic reviews). KeenGamer gave 80; GameStar gave 70: "starts off great and then flattens out to the point of boredom". User score 7.7 from 33 ratings — [Metacritic](https://www.metacritic.com/game/the-universim/)
- OpenCritic lists NoobFeed 88/100, GamesCreed 4.2/5, ZdobywcyGier 7.5/10 and neXGam 7/10 — [OpenCritic](https://opencritic.com/game/16105/the-universim) (via search summary)
- The Drastik Measure gave 8.5/10 — [review, 2024-02-07](https://www.thedrastikmeasure.com/2024/02/07/the-universim-pc-review/)
- I found no PC Gamer, RPS or IGN scored review of 1.0. PC Gamer ran an EA-era feature, "I destroy everything I touch in god game The Universim", whose body did not load — [PC Gamer](https://www.pcgamer.com/i-destroy-everything-i-touch-in-god-game-the-universim)
- Awards and community campaigns: "Coolest Indie of the Year Award 2015" (2015-12-23), nominated for Best Indie of the Year (2016-12-01), and a Steam "Labor of Love" nomination push (2019-11-27). All are Steam announcement titles via the news API.

### Inferences
- Throughout Early Access, Crytivo used Steam reviews as a funding signal. In the Pitchfork patch it asks for reviews: "If the overall score remains positive, we loosen the shackles on our developers". The game ran for about 10 years on roughly $387K of Kickstarter money plus EA sales and other publishing revenue. That fits the "extremely limited budget" line, and the trackers' $3.5–10M gross range fits too.
- A common reviews-to-sales rule of thumb (about 30–60 sales per review) applied to about 10.7K reviews gives roughly 320K–640K copies. That is closer to SteamSpy's upper band and SteamData.ai than to Raijin. This is my rough estimate, not a sourced figure.
- The player curve is typical of long-EA games: launch-day #1 Top Seller in 2018, a 1.0 bump in 2024 that roughly matched but did not exceed the EA peak, then a long tail of about 50–100 average CCU. Updates and sales produce small spikes; for example Sep 2024 (v1.0.1) peaked at 474.
- Promised later features — Tower of Babel, flying cars, the return of Creator Mode — appear in no later announcement. They were most likely never delivered, but I only checked Steam announcements.

### Gaps
- Gamalytic, VG Insights and SteamDB figures: blocked. Exact backer count from Kickstarter itself: blocked; the ~12,000 figure is secondary.
- The Early Access launch price (2018) and any price changes between EA and 1.0 could not be confirmed. It is unclear whether the price was always $29.99.
- No official headcount for Crytivo or the Universim team.
- No console port, announced or released, turned up in any search as of 2026-11-01.
- Steam review score over time (per-year percentages) was not retrievable; SteamDB was blocked.

## 2. Structure and loop: campaign vs sandbox, eras, planets and travel, win/lose, session length

### Takeaway
Each game is a single persistent run on a procedurally generated spherical "Mother Planet". You guide Nuggets through four tech "levels" — Stone Age → Medieval → Industrial/Modern → Space — using a research tree of 200+ items. In the Space era you colonise other procedural planets (Toxic, Ice, Lava, Terrestrial, plus alien worlds) and trade between them. 1.0 layered a quest-driven storyline with a "final encounter" (alien invasion) on top. After the finale the sandbox continues indefinitely. A full playthrough is reportedly about 11–20 hours. The late game is the most-criticised part.

### Cited Findings
- The player is the "Creator" guiding a civilisation from the Stone Age to the Space era, including colonising other planets. Planets are random and dynamic, with weather, seasons, meteor crashes, forest fires and long winters, and some have alien inhabitants — [Wikipedia](https://en.wikipedia.org/wiki/The_Universim)
- The research tree is split into four levels from the Stone Age to the Space Age. Some research needs Discovery Points — [The Drastik Measure](https://www.thedrastikmeasure.com/2024/02/07/the-universim-pc-review/)
- 1.0 content: complete storyline, Exile Villages, quests, Toxic/Ice/Lava/Terrestrial planet types, and a space map that "allows colonizing any number of planets" — [Gamespress](https://gamespress.com/The-Universim-10-is-now-Live-on-Steam). It added "30 new research items, new aliens and planets, and quests" — [Automaton](https://automaton-media.com/articles/newsjp/20240124-280024/)
- Crytivo's description of the ending: "We're working on a game finale... After the final scene, you will be able to continue playing your game indefinitely, colonizing other planets and establishing trade between them." It also promised deeper interactions with "aliens" and an invasion, but no full alien war — [Steam: Progress Update, 2023-06-02](https://store.steampowered.com/news/app/352720/view/5151601211231078833)
- Alien planets were designed to need terraforming. Examples: lava and ice planets, planets without water, and planets where the time of day never changes. Planting trees raises oxygen and Thermogenerators change temperature. Resources come from mining the planet or from interplanetary trading — [Steam: entering Beta, 2019-12-17](https://store.steampowered.com/news/app/352720/view/3370312875267221615)
- Space-era support buildings include Spaceport (trade between planets), Terraformer, Oxygen Generator, Hydro-Collider, Cloud Generator, Oxygen Refill Station, Celestial Alchemixer (alien resources), and an extractor for "Planet Cracker" parts (v1.0.02-era table) — [Universim Fandom wiki: Buildings](https://theuniversim.fandom.com/wiki/Buildings)
- Inventor and influencer Nuggets drive branching quests. "Nuggola Tesla" makes you pick one electricity path: wind turbines, a Nugget-powered "Nuggetic Motion Generator" with an "Insane Mode" that can make Nuggets explode, or polluting gas plants. Others include "Elon Nugsk" (colonisation), "Donnug Rump" (walls) and "Florence Nuggingale" (hospitals). They "appear randomly" so runs differ (design devlog) — [Steam: How your choice matter, 2018-06-08](https://store.steampowered.com/news/app/352720/view/2431262152939082983)
- Since 2021 you can choose which era's look to use for each building once it is unlocked. Roads and the black market still follow the research tree — [Steam: Beta V49 "The Core", 2021-05-28](https://store.steampowered.com/news/app/352720/view/4069544815360003577)
- KeenGamer saw no linear campaign. It described a survival story that emerges from your choices and from small events where Nuggets pray to you — [KeenGamer review, 2024-01-27](https://www.keengamer.com/articles/reviews/pc-reviews/the-universim-review-creative-incarnate-pc)
- Session length, from review mining: full completion about 20 hours (others report 10–30); story/campaign about 11 hours; longest single session about 8 hours. Players complain research tops out at 2x speed and want 5x–25x time acceleration — [Vaporlens](https://vaporlens.app/app/352720/the_universim.md)
- Since 2024-09 a Creator Panel in settings gives unlimited resources and workforce. A separate "Creator Mode" sandbox was missing at 1.0, and in Dec 2024 Crytivo said it was working to bring it back — [Steam v1.0.1](https://store.steampowered.com/news/app/352720/view/6250522009517508396); [Steam v1.0.2](https://store.steampowered.com/news/app/352720/view/1786573930788015)
- Planets, travel and Space content arrived in Space Age Devlog Part 1 (2021-12-13), Part 2 (2022-04-21), "MOON Patch v0.1.54" (2022-02-16) and "WORLD AT WAR Patch v0.1.59" (2022-12-22). These are Steam announcement titles via the news API.

### Inferences
- The loop is "survive, then research the next tier, then expand", with the god layer as a support and disruption tool. A run has a soft ending (the story finale) but no hard win state. After it, the only goals are colonising and trading, which explains the "late game is empty" criticism (see section 6). The planned Tower of Babel resource sink was Crytivo's own admission of this.
- Time scale matters. Early research items take seconds to minutes (section 5), and a planet takes 10+ hours to "control". A run spans a few evenings, not a persistent world.

### Gaps
- No explicit lose condition was found. The game presumably ends or stalls if every Nugget dies, but I did not verify this. Difficulty settings were not found either.
- No detailed spoiler-level description of the 1.0 storyline or final encounter; sources avoid spoilers.
- HowLongToBeat figures were not fetched. The session-length numbers above are Vaporlens's review-mining summaries.

## 3. God powers: catalogue, currency (Creator Points), earning and regeneration, costs, unlocks, good vs evil

### Takeaway
Powers ("Creator Powers") cost **Creator Points (CP)**, which fill like "sand in an hourglass". The 2015 design capped them at **3,600 CP**. Costs were given in real-time equivalents (600 CP = 10 minutes), which implies a base of about **1 CP per second**. Cheap pick-up and throw actions cost little; disasters (earthquake, volcano, tornado, thermostat) cost the entire 3,600 CP bank, about an hour of regeneration.

From 2017 the regeneration rate was tied to **Faith** from **Believers**. Faith is split into **Fear vs Love**. In the 2017 design fear-based faith generated CP **2× as fast** as love-based faith but "can cause problems in the long run".

Other CP sources and modifiers:
- Accepting prayer quests grants CP.
- Temples can **sacrifice Nuggets in a grinder** for a lump of CP plus +1 believer (the "evil" path).
- A peaceful civilisation makes temples generate CP passively "increasingly higher" (the "good" path).
- Laws can trade research for CP (±15%).
- An "Overjoyed" civilisation gets bonus CP generation.

1.0 ships 15 powers in four categories: Influence, Wrath, Protector, Creation. Influence is available from the start; the rest unlock through quests.

### Cited Findings
**2015 design: CP bank, regeneration and price list (devlog, before shipping; numbers "still in testing")** — [Steam: Creator Powers, 2015-12-26](https://store.steampowered.com/news/app/352720/view/341510664123598210)
- "CP acts somewhat like sand in an hourglass. You accumulate CP at a certain rate... 3600 Points is the maximum that you can collect at any given time." Cost scales with the size of the action: picking up a tree or rock "only cost[s] a few points", while a natural disaster costs "a huge number of points, if not all of them".
- *Intervention*:
  - Basic Object Interaction (grab and throw stones, trees or people; harder throws do more damage): 60 CP.
  - Inspiration (crowd works faster, more Might, stamina refilled): 600 CP (10 min).
  - Construction & Repair Focus (a building "shines" and draws builders to it): 600 CP.
  - Inconceivable (makes a female Nugget pregnant without a male): 600 CP.
  - Immortality (one Nugget never ages but can still be killed): 2,400 CP (40 min).
- *Terraforming*:
  - Plant 1 tree: 420 CP (7 min). Plant 10 trees: 2,400 CP.
  - Drop 1 stone: 420 CP. Drop 10 stones: 2,400 CP.
  - Cloud Formation (rain clouds that drift with the wind): 840 CP (14 min).
  - Thermostat (±10 °C planet-wide for 1 hour, stackable): 3,600 CP (60 min).
- *Disasters*:
  - Lightning Strike (damages buildings and creatures, can start wind-driven fires): 420 CP.
  - Earthquake (random location; opens new resource deposits): 3,600 CP.
  - Volcano (lasts 120 min, heats an area, destroys its core zone): 3,600 CP.
  - Tornado ("You can choose where it begins, but it decides where to end"): 3,600 CP.
  - Meteor Strike (each meteor carries a "Pandora's Box" that is either a gift — research item or resources — or a bomb or contagious virus): 1,200 CP (20 min).

**2016 design: influencing construction** — [Steam: The Nugget Revolution, 2016-05-02](https://store.steampowered.com/news/app/352720/view/4249665521682770589)
- Nuggets build in the order buildings were placed. The player can spend CP on the Influence power to move the focus to particular buildings.

**2017 Faith system: Fear and Love (devlog, then shipped in the "Chupacabra" patch on 2017-10-01)** — [Steam: Have a Little Faith, 2017-09-15](https://store.steampowered.com/news/app/352720/view/4249665521682766845); [Steam: Chupacabra patch, 2017-10-01](https://store.steampowered.com/news/app/352720/view/4249665521682766731)
- "These Creator Points regenerate depending on the Faith of your population (the higher the Faith, the faster the points generate)."
- Faith also rises "by simply using Creator Powers within range of Nuggets". Even evil acts raise it ("would certainly increase Faith, but it feels different").
- Healing raises Love; killing a Nugget with a power raises Fear. Fear and Love move independently of Faith but strongly affect it.
- "Fear-based Faith can cause problems in the long run, [but] it does generate Creator Points twice as fast as love-based Faith."
- You can stay neutral as a "careless god", which means fewer interruptions to the Nuggets.
- Nuggets build Faith monuments, a Love Tower or Fear Tower, whose size grows with Faith.
- High-Faith populations are more likely to be born with positive traits.
- Shipped version (Chupacabra): "Creator points are accumulated over time, which can be sped up by increasing Faith. The more you use these powers, the faster Creator Points will be generated."
- Shipped version (Chupacabra): "Picking someone up will cause other Nuggets to flee. Such actions will increase Fear and decrease the Happiness of affected Nuggets."
- Shipped version (Chupacabra): powers are cast by holding Ctrl and left-clicking, and the power menu opens with the middle mouse button or Tab.

**2017–2018 prayers and quests as a faith source (design)**
- The planned **Prayer Enclave** was an inbox of Nugget prayers with Inbox/Started/Responded/Spam/Trash tabs. Prayers are mini-quests with timers, marked good (heart) or evil (skull); accepting and finishing one rewards Faith. Examples: rescue a child from wolves; "punish my nemesis"; remove a boulder from a farm — [Steam: Have a Little Faith](https://store.steampowered.com/news/app/352720/view/4249665521682766845)
- These became "God Quests" for the Steam launch in 2018 — [Steam: How your choice matter, 2018-06-08](https://store.steampowered.com/news/app/352720/view/2431262152939082983)
- Balance change: "Players will now receive Creator Points upon accepting a quest to ensure they can actually complete them" — [Steam: Grass Patch v0.0.27, 2018-10-05](https://store.steampowered.com/news/app/352720/view/2447035533298658213)
- Same patch: non-believers who disagree with society leave and form **Exile Villages**. You win believers back "by answering their prayers (quests) or performing Creator Powers near witnesses (there shouldn't be any witnesses if it's a murder, though)" — [Steam: Grass Patch v0.0.27](https://store.steampowered.com/news/app/352720/view/2447035533298658213)

**2018 laws and happiness as CP modifiers**
- Law examples (design): "Scientific Focus (Research rate +15%, Creator Point production -15%)" and "Religious Focus (Creator Point production +15%, Research rate -15%)" — [Steam: Nuggets Leaders and Law System, 2018-07-20](https://store.steampowered.com/news/app/352720/view/2412125660639160799)
- Civilisation-wide happiness levels; "an overjoyed civilization will have a bonus to research speed, twin birth rates, and Creator Point generation" — [Steam: Happy Patch v0.0.28, 2018-11-02](https://store.steampowered.com/news/app/352720/view/2407631646376276293)
- Enemy Exile "Priests" infiltrate your city and convert Believers into Non-Believers, who then leave to join the Exiles — [Steam: Happy Patch v0.0.28](https://store.steampowered.com/news/app/352720/view/2407631646376276293)

**2019 sacrifice and alignment (shipped)**
- "Temple 2.0": every Temple from the Stone Age on has a grinder. Sacrificing a Nugget "generates a chunk of Creator Points" and "can also help feed your other citizens".
- If you avoid sacrifices and keep a peaceful civilisation, "Temples will start passively generating increasingly higher amounts of Creators Points."
- "Now you can choose to be good or evil, and your civilization will change to reflect your alignment. Being evil will make buildings look a lot creepier, and Nugget Happiness may be affected. You'll get more believers, though, whether they like it or not."
- Source for the three points above: [Steam: Pitchfork Patch v0.0.36, 2019-09-13](https://store.steampowered.com/news/app/352720/view/3658535001296419745)
- Follow-up: sacrificing a Nugget = +1 believer, with a separate faith value for sacrifice. More temple workers raise the chance of a new believer. Temples show how many points a sacrifice will give — [Steam: Sky High Patch v0.0.37, 2019-10-09](https://store.steampowered.com/news/app/352720/view/2426802943980272729)
- A beta reviewer said grinder sacrifices give instant CP and may add believers, but "Do this too often and you'll turn evil" — [KeenGamer beta preview](https://www.keengamer.com/articles/previews/the-universim-beta-review-rule-the-world-and-all-its-nuggets/) (via search summary)

**Player-observed economics (EA, 2018–2019; may be outdated)** — [Steam discussion "Tips on getting believers?", Oct 2018–May 2019](https://steamcommunity.com/app/352720/discussions/0/3335371283872229575)
- Believers come from using powers. Each use fills a "believer meter", and a full meter gives one believer. Expensive powers give about one believer per cast; cheap ones need 2–3 casts. Reforestation was called the most cost-effective.
- The believer share fell as the population grew: about 43 of 100 Nuggets believed, and the poster expected that to drop into the low 30s.
- The Temple shows two meters: fear vs love, and a slow-to-fast CP gain rate. In this player's experience, fear actions (destroying, picking things up, meteors) slowed CP gain, while love actions sped it up. **This contradicts** the 2017 design note that fear generates CP twice as fast.
- Players reported a CP cap of about 1,000, "linking couples" for 20 CP and healing for 10 CP.
- One player said that once all powers are unlocked, the total believer count "has no in game effect". For an individual Nugget, believer status only removes the random chance of turning exile.

**1.0 state**
- "Command more than 15 godly powers" to guide, protect or punish — [Steam store](https://store.steampowered.com/app/352720/The_Universim/). The 1.0 press release gives exactly 15, including tornadoes, earthquakes and lightning — [Gamespress](https://gamespress.com/The-Universim-10-is-now-Live-on-Steam)
- 1.0 categories are Wrath, Influence, Protector and Creation. Influence is available from the start; the others unlock through quests. CP are earned "when nuggets worship you or when you sacrifice them". Example powers: pick up and throw, lightning, skipping seasons — [The Drastik Measure](https://www.thedrastikmeasure.com/2024/02/07/the-universim-pc-review/)
- Named powers in patch notes:
  - **Telekinesis** (pick up Nuggets and objects; usable from the Nugget list; can drop sick Nuggets into hospitals, added Apr 2023).
  - **Lightning Strike**, buffed against tanks and helicopters in Apr 2023.
  - **Forestation** icon (2018) and a **Season change** power (2019 fix: "Season change power has no effect on believers").
  - **Protection dome** against tornadoes and meteors, per the wiki.
  - Sources: [Steam: 1.0 notes](https://store.steampowered.com/news/app/352720/view/5510784213113218236); [Steam: Last mile, 2023-04-05](https://store.steampowered.com/news/app/352720/view/5121196841285545411); [Steam: Grass Patch](https://store.steampowered.com/news/app/352720/view/2447035533298658213); [Fandom: Tornadoes](https://theuniversim.fandom.com/wiki/Tornadoes)
- Rules on targets: imprisoned Nuggets and Nuggets carried off by UFOs are immune to powers through building panels and the Nugget list. Builder bots are immune — [Steam: Last mile](https://store.steampowered.com/news/app/352720/view/5121196841285545411); [Steam: 1.0](https://store.steampowered.com/news/app/352720/view/5510784213113218236)
- Bug fixed in 2023: "while traveling between planets, the Creator power generation was failing to update correctly" — [Steam: Last mile](https://store.steampowered.com/news/app/352720/view/5121196841285545411). 1.0 notes add "Citizens will still believe in you regardless of what planet you're on".
- Electing a preferred leader by "blessing" a candidate costs CP and "might not work". "Accidents" (dropped boulders, lightning) also remove candidates, but they scar the mental state of witnesses — [Steam: Leaders and Law, 2018-07-20](https://store.steampowered.com/news/app/352720/view/2412125660639160799)
- In 1.0 a quest-driven **Cauldron** (Dec 2024) uses powers as a crafting tool: grow crops on the cauldron's balcony, pick them, drop them in, and work the bellows to brew potions that buff productivity or happiness — [Steam v1.0.2](https://store.steampowered.com/news/app/352720/view/1786573930788015)
- Wikipedia describes the influence model as **Power** (earned by completing tasks) and **Wrath** (built up when Nuggets fail tasks, spent on destruction). This reads like the Kickstarter-era design and does not match later devlogs, which use CP and Faith — [Wikipedia](https://en.wikipedia.org/wiki/The_Universim). I could not reconcile the two.

**Twitch integration: viewer-driven events (directly relevant to Godling)**
- Introduced 2019-09-13:
  - Viewers type **#CreateNugget** to spawn an avatar Nugget with their name above its head.
  - Avatars passively gain **"Action Points"** over time; streamers can give extra AP to viewers who cheer.
  - Commands: #CheckBalance, #Commands, **#StartFamily**, **#StartFire** (the streamer can arrest the arsonist), **#Suicide** (leave the game), and **#Steal** (steal from the stockpile; bold acts earn extra AP). There is a cooldown between uses of each command.
  - **Public Events Voting**: periodically chat sees **3 random options** and the most-voted one fires. Options can help ("bonus Creator Points") or hurt ("summoning an evil UFO").
  - Streamers can enable or disable, rename, and re-cost every command, and control which vote items appear and how often voting runs.
  - Source: [Steam: Pitchfork Patch v0.0.36](https://store.steampowered.com/news/app/352720/view/3658535001296419745)
- "Twitch Elections" (2019-10-09): chat votes in civilisation elections, and chat Nuggets are always put in the race — [Steam: Sky High v0.0.37](https://store.steampowered.com/news/app/352720/view/2426802943980272729)
- Apr 2023: Twitch API changes had broken the integration "for a period of time", and the code was restructured — [Steam: Last mile](https://store.steampowered.com/news/app/352720/view/5121196841285545411)
- The 1.0 notes say "Fixed the Twitch connectivity issue" and "Twitch viewers may now take away Creator Points" — [Steam: 1.0](https://store.steampowered.com/news/app/352720/view/5510784213113218236)

### Inferences
- The price list makes the design intent clear. Cost is tied to regeneration time, and the bank is capped at exactly one big disaster. Over an hour the player chooses between one cataclysm, a few mid-sized nudges (inspire, focus, rain), or many small physical acts.
- The fear/love split is a moral-cost layer on top of the currency. In the design, cruelty is the faster way to earn and the Nuggets, their happiness and the town's look all reflect it. In practice, the player reports (2018) say love sped regeneration. Players found the system opaque and the believer count meaningless late in the game. I read the faith economy as never fully balanced.
- Crytivo had already shipped crowd-in-the-loop mechanics: avatar spawning, a per-viewer passive point balance with per-command cooldowns, 3-option votes for disasters or buffs, and streamer-configurable costs. Viewers could even drain the god's CP. Viewers could act *through* their own avatar Nuggets (start fires, steal), but the *civilisation's* decisions stayed with the AI and the streamer.

### Gaps
- No authoritative 1.0 list of all 15 powers with their current CP costs, cooldowns and unlock quests. The Fandom "God Powers" page returned HTTP 402, and no guide had numbers.
- Search summaries mentioned "Electrify" (lightning) and "Trickle" (rain over an area) as power names in a review, but I could not confirm which page.
- No source for the current CP cap or regeneration rate in 1.0. Does 3,600 still apply? Players reported about 1k in 2018.
- Whether powers have cooldowns separate from CP cost: no source found. Twitch commands do have cooldowns.

## 4. Nugget simulation: needs, jobs, lifespan, reproduction, traits, intelligence, worship, reactions; player control vs autonomy

### Takeaway
Nuggets are autonomous agents. Each has need bars (health, hunger, thirst, stamina, happiness), a strength or "might" stat, inheritable traits, family ties, believer status and a vote. They pick tasks by weighted priorities: food is more important than wood, and collection stops when storage is full. Jobs are assigned automatically by the Town Hall, and from 2019 by **Ministers**. Nuggets elect leaders who pass laws.

The player places buildings, sets research, assigns jobs if they want, and intervenes with powers. The player cannot order an individual Nugget to do a task, apart from Telekinesis and arrests. Crytivo's own framing: players "suggest ideas rather than issuing commands", like playing with "an ant farm". Players often complain about Nugget incompetence and the micromanagement it forces.

### Cited Findings
**Need bars and stats (devlog design, 2016)** — [Steam: A God's Guide to Nuggets, 2016-02-29](https://store.steampowered.com/news/app/352720/view/295354567847060820)
- **Health**: three intervals.
  - Top interval: health recovers on its own.
  - Middle interval: no recovery; the Nugget seeks a Witch Doctor, shows a sick icon and moves 25% slower.
  - Critical interval: health drains over time and the Nugget will die without help.
  - Some jobs (Hunter's Hut, Defense Tower) add +25 maximum health.
- **Hunger**: three intervals.
  - Full: +0.2 happiness.
  - Hungry: the Nugget eats after its current task.
  - Starving: it stops working and the player gets a critical news alert.
- **Thirst**: works like hunger. It drains 25% faster above 35 °C, and Nuggets drink at wells or ponds.
- **Stamina**: four intervals.
  - Tired: speed −25%.
  - Exhausted: an icon appears.
  - Passed out on the spot: recovery takes 50% longer.
  - It drains 25% faster above 35 °C or at 0 °C and below.
- **Happiness**: two intervals.
  - When low, Nuggets go idle at times with angry icons until they visit recreation buildings.
  - Pollution, low oxygen and deaths in the family lower it.
  - Some God Powers raise happiness temporarily.
- **Strength**: starts at 1–4 and grows with the tasks a Nugget does.
- **Families**: each needs its own home and grieves a death by visiting the cemetery. Families celebrate when a member gains education or a profession, which makes them more productive. Research can lengthen or shorten lifespans.

**Reproduction (design, 2016)** — [Steam: Reproduction Process Update, 2016-10-19](https://store.steampowered.com/news/app/352720/view/4249665521682768805)
- An adult female's Fertility Timer reaches 100%, she finds a mate, and the couple builds a house.
- The planned design added a player-clicked **heart icon** over the hut to allow conception, giving population control "when food or water supplies get low". Pregnancy cuts movement speed by 15%.
- Separately, an "Inconceivable" power causes pregnancy without a male (2015 design), and players later spent CP "linking couples" (2018 forum).

**Traits (Fandom wiki; launch-era list)** — [Fandom: Nugget traits](https://theuniversim.fandom.com/wiki/Nugget_traits)
- Positive or negative ±25% modifiers: Workaholic (+25% stamina), Weak (−25% might), Surefooted (+25% speed), Nibbler and Gourmand (hunger ±25%), Lazy (stamina drains 25% faster), Hermit (50% longer to find a mate), Immune (never sick).
- **True Believer**: "born a believer... forever faithful and give an extra boost to creator point generation".
- Unlockable special traits with drawbacks:
  - Nugg Norris, unlocked after 1,000 trees are chopped.
  - Matenator, unlocked at 150 population. Its partner's heart "gives out after five matings".
  - Fugitive, unlocked after 5 arrests. It may steal.
  - Highlander, unlocked by finishing all quests. It lives forever but is contagious.
  - Coffin Dodger, unlocked at 800 population. It reincarnates and can become a zombie.
  - Greenlander drops seeds as it walks but has a short life.
  - Arnold carries more but eats three times as much.
- Inheritance (design, 2017): each parent gives a 25% chance of passing on a trait, rising to 50% if both share it. Populations with high Faith get more positive traits — [Steam: Have a Little Faith](https://store.steampowered.com/news/app/352720/view/4249665521682766845)

**Automation and the limits of control**
- 2016: "we want to make Nuggets as self-sustaining as possible". Day-to-day actions have weightings ("food collection is more important than wood collection"; skip collecting "if your stashes are all filled"). The Priority Panel had been needed only "because the AI was simply not advanced enough" — [Steam: The Nugget Revolution, 2016-05-02](https://store.steampowered.com/news/app/352720/view/4249665521682770589)
- 2018: a Labor Management building runs work shifts. Electricity enables night shifts — [Steam: Micro to Macro, 2018-05-17](https://store.steampowered.com/news/app/352720/view/2391853754536702559)
- 2019 Ministers (Defense, Agriculture, Education, Water, Food, Entertainment, Architecture, Medicine, Power) are assigned at the Town Hall. They "automatically designate workers to construct more sources of food and water... to avoid constant micromanagement". Modern factories keep producing with no workers, and workers only raise output — [Steam: Executive Branch v0.0.30, 2019-02-07](https://store.steampowered.com/news/app/352720/view/2461683368386443354)
- Dec 2024 minister fixes: they had been overbuilding identical structures and failing on other planets — [Steam v1.0.2](https://store.steampowered.com/news/app/352720/view/1786573930788015)
- Town Hall: "Automate nugget assignment to jobs. Automates construction of certain buildings" — [Fandom: Buildings](https://theuniversim.fandom.com/wiki/Buildings)
- 2023 change: the Town Hall no longer auto-assigns while the player is assigning by hand — [Steam: Last mile](https://store.steampowered.com/news/app/352720/view/5121196841285545411)
- Crytivo's philosophy (2018): Nuggets have personalities and autonomy, and players suggest rather than command. Early ages need more direction (research, placement). Later civilisations become self-sufficient and play moves to macro management; "It comes down to making players feel like they're playing with an ant farm." The world simulation runs with or without the player — [Game Developer, 2018-10-03](https://www.gamedeveloper.com/game-platforms/how-i-the-universim-i-s-god-game-twist-charmed-early-access-players)

**Politics, crime and dissent**
- **Elections** every 2 seasonal years, usually 3 candidates. Every adult votes by preference and traits; lazy Nuggets vote for fewer work hours, food-lovers for more food. They happen "with or without your intervention". The god can bless a candidate (costs CP, may fail) or arrange accidents.
- **Law** examples:
  - Food for All: +10 happiness, +100% food consumption.
  - Elderly Assisted Living: 30% chance an elderly couple dies while mating.
  - Pesticides: +15% farm yield, +5% sickness.
- Source for elections and laws (design, 2018): [Steam: Leaders and Law System, 2018-07-20](https://store.steampowered.com/news/app/352720/view/2412125660639160799); [Steam: Launch recap](https://store.steampowered.com/news/app/352720/view/2447032361185051078)
- **Crime** (2018) comes from a lack of schools, pollution, some laws and missing utilities. There are five levels; "High" spawns dangerous criminals who poison wells or bomb buildings.
- Arresting an innocent lowers happiness and can lose you believers. Too many police officers make Nuggets feel oppressed.
- Source for crime: [Steam: Crime in The Universim, 2018-09-17](https://store.steampowered.com/news/app/352720/view/2454914931414521766)
- **Riots** (Pitchfork patch, 2019) start from low happiness plus high crime. Rioters light fires and destroy buildings. The player can wait it out, arrest them, or use powers — [Fandom: Riot](https://theuniversim.fandom.com/wiki/Riot)
- **Exiles**: non-believers leave to form villages that are neutral (trade) or aggressive (ultimatums, attacks). From 2023 Exiles attack based on your relationship with them, and building too close to them lowers that relationship — [Steam: Grass Patch](https://store.steampowered.com/news/app/352720/view/2447035533298658213); [Steam: Last mile](https://store.steampowered.com/news/app/352720/view/5121196841285545411)

**Reactions to divine acts**
- Picking a Nugget up makes onlookers flee; Fear rises and their happiness falls — [Steam: Chupacabra, 2017-10-01](https://store.steampowered.com/news/app/352720/view/4249665521682766731)
- Healing a sick Nugget earns that Nugget's devotion — [TechRaptor](https://techraptor.net/content/universim-bringing-back-god-game) (via search summary)
- Evil alignment makes buildings creepier and may lower happiness, but gives more believers — [Steam: Pitchfork](https://store.steampowered.com/news/app/352720/view/3658535001296419745)
- Witnesses matter: powers performed near Nuggets win believers, but murders should have no witnesses — [Steam: Grass Patch](https://store.steampowered.com/news/app/352720/view/2447035533298658213)

**AI quality complaints**
- A long-running bug had Nuggets drinking from lakes instead of wells. In 2023 Crytivo added a well-efficiency radius to fix it — [Steam: Progress Update, 2023-06-02](https://store.steampowered.com/news/app/352720/view/5151601211231078833)
- "Standing Nuggets" (stuck or idle) was the most-reported issue until the 2019–2020 pathfinding rewrite — [Steam: entering Beta](https://store.steampowered.com/news/app/352720/view/3370312875267221615)
- Reviewers call Nuggets "incompetent", with resource failures that force micromanagement — [Vaporlens](https://vaporlens.app/app/352720/the_universim.md)
- Players asked for Creator Power and Builder Bot tutorials because they struggled with both, and Crytivo added them in 2023 — [Steam: Progress Update](https://store.steampowered.com/news/app/352720/view/5151601211231078833)

### Inferences
- The Universim's autonomy is "needs-weighted utility AI plus automated managers". In practice players feel the opposite of the intended ant farm: they babysit stuck or poorly routed Nuggets. Crytivo's answer over 8 years was more automation (Town Hall, Ministers, shifts, worker-optional factories), not smarter individuals.
- Elections are the clearest "influence, not control" mechanic. The god can nudge (a paid blessing with a chance to fail) or coerce (an "accident" that traumatises witnesses), but the outcome comes from the Nuggets' own preferences.

### Gaps
- Exact Nugget lifespan, ageing stages, intelligence and education values in 1.0 were not found. The 2016 devlog was truncated ("CONTINUE READING HERE").
- Whether the 2016 heart-click conception mechanic shipped in that form was not confirmed.

## 5. In-game economy: resources, production chains, building costs and placement, research mechanics and costs, scaling across eras, balance problems

### Takeaway
The economy is a classic tiered city-builder:
- **Stone Age**: raw wood, stone and food (gathering, farms, hunting, fishing) plus water (wells, reservoirs).
- **Medieval**: refined planks and bricks, plus iron.
- **Modern**: steel, glass, cement, chemicals, plastic, electronics, oil, gas and electricity.
- **Space**: alien resources, oxygen and terraforming.

Buildings cost bundles of the current tier's materials. Many also draw electricity and water and add happiness, crime or pollution. Research is time-based, with up to 5 items queued and an auto-research toggle. Late items also cost Discovery Points from Expeditions. The best-known balance problem, which Crytivo admits, is the late game: a resource surplus with nothing to spend it on.

### Cited Findings
- Resource categories in a pre-alpha concept image: Planet Environment (temperature, atmosphere/oxygen, pollution); Vital needs (food, water, electricity); Building (wood, stone, metal); and non-renewable Natural (oil, gas, ore). Food comes from gatherers at bushes and fruit trees or from farms; crop choice depends on local minimum and maximum temperature — [Fandom: Resources](https://theuniversim.fandom.com/wiki/Resources); [Fandom: General Tips](https://theuniversim.fandom.com/wiki/General_Tips)
- Atmosphere (wiki, likely early or speculative; treat with caution): oxygen depends on tree and water cover. Bands 0–20 / 20–40 / 40–60 cap population at 25 / 100 / 200 and raise meteor odds. Pollution bands raise temperature and sickness up to 40% — [Fandom: Resources](https://theuniversim.fandom.com/wiki/Resources)
- In 2019 a shipped pollution mechanic made Nuggets sick or die based on oxygen, and players were told to plant trees and add parks — [Steam: Sky High v0.0.37](https://store.steampowered.com/news/app/352720/view/2426802943980272729)
- Research times in the Stone Age (wiki table): Primitive Tools 0:10; Fire 0:45; Primitive Cooking 4:30 (hunger −5%, unlocks Eatery); Cooking Utensils 3:30; **Ministry of Agriculture 15:00**; Waterflow Study 3:00 (Reservoir); Leather Buckets 4:30; Water Dowsing 4:30 (well refill +10); Wood Oven 6:00; Fishing 6:30. Some items cost Discovery Points instead of time: Cooking Oils 25 DP (hunger −10%), Food Preservation 20 DP (Eatery capacity +5%). "Up to five research topics can be researched in a queue, with an optional Auto-Research toggle" — [Fandom: Research](https://theuniversim.fandom.com/wiki/Research)
- Discovery Points arrived in 2021 for Space-age-related techs and were earned through Expeditions (Expedition Camp, sending explorers into the "Sarlacc" hole) — [Steam: Beta V49 "The Core"](https://store.steampowered.com/news/app/352720/view/4069544815360003577)
- Review description: normal research accrues over time, while "golden" research uses education points. Each completed item grants a technology, a habit or an evolutionary trait — [KeenGamer review](https://www.keengamer.com/articles/reviews/pc-reviews/the-universim-review-creative-incarnate-pc)
- Earlier perk system: Blue Evolution perks advance eras and refresh in groups, Yellow "Mortal" perks give minor stacking boosts, Green Rare and Purple Ultra-rare perks are costly but strong. Perk names include Agriculture, Cooking, Primitive Waterworks and Refined Materials — [Fandom: Perks](https://theuniversim.fandom.com/wiki/Perks)
- **Modern-age costs** (wiki table for v1.0.02; electricity / water / pollution effects, then build cost):
  - University: −10 / −7 / 0; 5 Steel, 15 Glass, 5 Cement, 10 Planks. Produces educated citizens and Discovery Points, raises happiness, lowers crime.
  - Power Plant: +220 electricity, −10 water, +0.6 pollution; 5 Glass, 10 Iron, 15 Bricks, 15 Planks. Lowers happiness, raises crime.
  - Wind Turbine: +100; 2 Electronics, 10 Steel, 10 Cement, 10 Planks. Raises happiness.
  - Nuclear Plant: +1000 electricity, −50 water.
  - Water Pump: +180 water; 2 Electronics, 8 Glass, 8 Steel, 15 Planks.
  - Clone Center: produces custom Nuggets; −20 electricity, +0.8 pollution.
  - Airport: attracts exile immigrants depending on crime and happiness.
  - Hyperloop, Garage (cars), and military buildings (Barracks, Boom Barrack, Tank Hangar, Heliport): each −10 electricity; 5 Electronics, 10 Steel, 5 Glass, 15 Cement.
  - Source: [Fandom: Buildings](https://theuniversim.fandom.com/wiki/Buildings)
- **Space-age** versions cost plastic and electronics: Power Plant +380 for 15 Plastic, 10 Electronics, 10 Steel; Air Filter −3.0 pollution; Terraformer 10 Plastic, 10 Electronics, 50 Steel — [Fandom: Buildings](https://theuniversim.fandom.com/wiki/Buildings)
- Production chains: Glass Factory and Chemical Factory (Modern Age, 2019). Modern factories run without workers, and workers only raise output — [Steam: Executive Branch](https://store.steampowered.com/news/app/352720/view/2461683368386443354)
- Gas Mines feed Electric Gas Plants, which cut air quality and raise global temperature. Wind power stops during windstorms and in calm; batteries store surplus — [Steam: How your choice matter](https://store.steampowered.com/news/app/352720/view/2431262152939082983)
- Small balance tweaks: one tree yields 3 wood instead of 2. Defense tower range went from 20 to 25 and accuracy from 70% to 85% — [Steam: Grass Patch v0.0.27](https://store.steampowered.com/news/app/352720/view/2447035533298658213)
- Placement:
  - Build away from trees and rocks so builders need not clear the site — [Fandom: General Tips](https://theuniversim.fandom.com/wiki/General_Tips)
  - Since 2023 a placement UI shows crime, happiness and pollution; "Sample Building" (Ctrl + middle mouse) copies a building; wells lose efficiency near other wells — [Steam: Progress Update, 2023-06-02](https://store.steampowered.com/news/app/352720/view/5151601211231078833)
  - Building near Exiles lowers your relationship with them — [Steam: Last mile](https://store.steampowered.com/news/app/352720/view/5121196841285545411)
  - Builder Bots and drones handle construction in later eras — [Steam: v1.0.1](https://store.steampowered.com/news/app/352720/view/6250522009517508396)
- Admitted late-game imbalance: "Many players have amassed substantial resources with no clear direction for their use beyond planetary colonization." The planned fix was the Tower of Babel sink — [Steam: What the Future Holds, 2024-05-22](https://store.steampowered.com/news/app/352720/view/5741605105604108334)
- Modding (2024) lets players add custom factories, mines and resources, with a planned package system to bundle production chains — [Steam v1.0.1](https://store.steampowered.com/news/app/352720/view/6250522009517508396); [Steam v1.0.2](https://store.steampowered.com/news/app/352720/view/1786573930788015)
- Pre-1.0 balance passes listed: "Rebalance of the main planet", "Balance of new planets", "Rebalance of the crime / happiness system" — [Steam: Progress Update, 2023-06-02](https://store.steampowered.com/news/app/352720/view/5151601211231078833)

### Inferences
- Scaling across eras swaps the material basket (wood and stone → planks and bricks → steel, glass and cement → plastic and electronics). It adds utility grids (electricity, water) and social externalities (crime, happiness, pollution) rather than simply raising the numbers. The late game becomes a grid- and externality-balancing puzzle with surplus materials.
- God powers barely touch the economy after the early game. The 2015 design had earthquakes open deposits and trees and stones dropped as resources, but the main resource levers became buildings and ministers. This matches the "more city builder than god game" complaint.

### Gaps
- No full 1.0 tech-tree cost table. The wiki covers only part of the Stone Age, and its building tables are version-labelled (V0.16, V1.0.02) and may be community guesses.
- Exact production rates (food per farm per day, and so on) were not found.

## 6. What players and reviewers love and criticise; what makes long sessions interesting or boring

### Takeaway
Praised: the charm (Nuggets, witty narrator, low-poly spherical planets, weather and seasons), the god-game plus city-builder hybrid, the relaxed pacing, and the freedom to intervene as much or as little as you like.

Criticised:
- A repetitive, empty late game.
- Performance that falls as the population grows.
- Bugs and Nugget AI that force micromanagement.
- Slow research and too little time acceleration.
- Unfun or underpowered god powers relative to the city-building.
- Language removal at 1.0.
- Since mid-2024, a strong sense of abandonment after Crytivo moved on.

### Cited Findings
- Positive themes from review mining (weights): enjoyable or addictive (0.35), strong concept (0.27), visuals (0.17), funny narrator (0.15, "though some say it gets old"), relaxing (0.12), freedom to intervene as much or as little as you want (0.04) — [Vaporlens](https://vaporlens.app/app/352720/the_universim.md)
- Negative themes from the same source: **developer abandonment (0.32)**, boring or repetitive gameplay (0.23), unfinished release (0.22), optimisation (0.17), performance falls with growth (0.14), Japanese removed (0.06), slow research capped at 2× (0.06), not enough time acceleration (0.06), half-baked endgame, and quests that stop appearing late on — [Vaporlens](https://vaporlens.app/app/352720/the_universim.md)
- Reported crashes or lag around 100 Nuggets (memory) and more than 400 buildings plus Nuggets — [Vaporlens](https://vaporlens.app/app/352720/the_universim.md); summarised in search results
- GameStar (70): "starts off great and then flattens out to the point of boredom" — [Metacritic](https://www.metacritic.com/game/the-universim/)
- KeenGamer (8/10, 2024-01-27) praised the looks, narration, music and laid-back gameplay. It criticised slow-burn pacing, objectives that are easy to miss, a disorganised research tree, and narration and music that repeat — [KeenGamer](https://www.keengamer.com/articles/reviews/pc-reviews/the-universim-review-creative-incarnate-pc)
- The Drastik Measure (8.5) praised graphics, documentary-style narration, content and replayability, but found it "tedious at times" — [The Drastik Measure](https://www.thedrastikmeasure.com/2024/02/07/the-universim-pc-review/)
- LadiesGamers found casting creator powers awkward: "definitely not the most natural of ways to perform a creator power, and it feels cumbersome" — [LadiesGamers](https://ladiesgamers.com/the-universim-review/) (via search summary)
- A game-description summary says reviewers criticise "limited and underwhelming god powers", often useless, poorly balanced or capped by points — [Vaporlens](https://vaporlens.app/app/352720/the_universim.md) (via search summary)
- Forum users said the game is "more of a city builder than a god game". The endgame "forces the player to stop to maintain believers", and influence over Nuggets feels weak — [Steam discussion, 2018–19](https://steamcommunity.com/app/352720/discussions/0/3335371283872229575)
- Crytivo, May 2024: The Universim "holds a special place in our hearts, it's time for us to embark on a new adventure". This is the pivot to Farm Folks, described as "a mix of games such as Satisfactory, The Sims, Fortnite, Escape from Tarkov" — [Steam: What the Future Holds](https://store.steampowered.com/news/app/352720/view/5741605105604108334). In July 2024 Crytivo clarified "we're not stopping support" after a backlash — [Steam, 2024-07-15](https://store.steampowered.com/news/app/352720/view/6000566704280770002)
- Expectation management in 2023: fans speculating about full alien war were told "Combat/war overall was never planned" — [Steam: Progress Update](https://store.steampowered.com/news/app/352720/view/5151601211231078833)
- Crytivo's 2018 view on Early Access: the biggest fan concern is content, and feedback is the most important part of a work in progress — [Game Developer](https://www.gamedeveloper.com/game-platforms/how-i-the-universim-i-s-god-game-twist-charmed-early-access-players)
- Vaporlens gives the game a Steam Deck feature-scan verdict of "Broken on Steam Deck": tiny text, controls that do not suit the trackpad, and one-way cloud saves. This is Vaporlens's analysis, not Valve's rating — [Vaporlens](https://vaporlens.app/app/352720/the_universim.md)

### Inferences
- **Interesting:** the first hours. Survival pressure from needs, seasons and disasters is high, every new tech changes the town visibly, and god powers matter most against small populations.
- **Boring:** after automation (ministers, worker-optional factories) arrives and resources pile up. The player becomes a bug-fixer and optimiser with nothing to aim for, while frame rate falls.
- Late-game interest leans on prayer quests and events, and players report these stop appearing late on.

### Gaps
- No Reddit thread was successfully retrieved. Reddit sentiment is represented only through Steam reviews, forums and review aggregators.
- Steam review sentiment by year (for example EA vs after 1.0 vs 2025–26) could not be measured; SteamDB was blocked.

## 7. Notable for Godling (short list, facts with sources; no full design)

### Takeaway
The Universim has already tried several of the levers Godling is considering. These include a time-priced, capped divine currency; disasters that drain the whole bank; a moral split in how inhabitants perceive interventions; and a Twitch layer where viewers spend passively earned points with cooldowns and vote on three random events. It also shows how such games lose players: an empty late game, AI that needs babysitting, and visible abandonment.

### Cited Findings
- **Cost = regeneration time.** 2015 price list: 60 CP for a grab, 420 for a tree or lightning bolt, 600 for "Inspire" or "Focus", 1,200 for a meteor, and 3,600 for a tornado, earthquake, volcano or ±10 °C thermostat. The cap is 3,600, so one big disaster empties the bank and takes about an hour to rebuild — [Steam: Creator Powers, 2015](https://store.steampowered.com/news/app/352720/view/341510664123598210)
- **Regeneration tied to the inhabitants' attitude.** Faith speeds CP. In the 2017 design, fear-faith regenerates twice as fast but has long-term costs, and the town's look changes with alignment — [Steam: Have a Little Faith](https://store.steampowered.com/news/app/352720/view/4249665521682766845); [Steam: Pitchfork](https://store.steampowered.com/news/app/352720/view/3658535001296419745)
- **Witnesses and reactions.** Powers seen by Nuggets win believers. Picking a Nugget up makes others flee and lowers their happiness. Arresting an innocent costs believers — [Steam: Grass Patch](https://store.steampowered.com/news/app/352720/view/2447035533298658213); [Steam: Chupacabra](https://store.steampowered.com/news/app/352720/view/4249665521682766731); [Steam: Crime](https://store.steampowered.com/news/app/352720/view/2454914931414521766)
- **Mixed-outcome gifts.** Meteors carry a "Pandora's Box" that may hold research, resources, a bomb or a virus — [Steam: Creator Powers, 2015](https://store.steampowered.com/news/app/352720/view/341510664123598210)
- **Influence that can fail.** Blessing an election candidate costs CP and "might not work" — [Steam: Leaders and Law](https://store.steampowered.com/news/app/352720/view/2412125660639160799)
- **Shipped viewer economy.** Twitch viewers get avatar Nuggets that earn Action Points passively, plus bonus AP for cheering. Commands have cooldowns. Chat votes on 3 random public events (buff or disaster), and the streamer can re-cost or disable every command. 1.0 even let viewers drain the god's CP — [Steam: Pitchfork](https://store.steampowered.com/news/app/352720/view/3658535001296419745); [Steam: 1.0](https://store.steampowered.com/news/app/352720/view/5510784213113218236)
- **The integration needed upkeep.** A Twitch API change broke it, and Crytivo had to restructure the code — [Steam: Last mile, 2023](https://store.steampowered.com/news/app/352720/view/5121196841285545411)
- **Autonomy ceiling.** "Players suggest ideas rather than issuing commands" (the ant-farm framing). Players still complained about incompetent AI and micromanagement, and Crytivo's fix was manager layers (Town Hall, Ministers) — [Game Developer](https://www.gamedeveloper.com/game-platforms/how-i-the-universim-i-s-god-game-twist-charmed-early-access-players); [Steam: Executive Branch](https://store.steampowered.com/news/app/352720/view/2461683368386443354); [Vaporlens](https://vaporlens.app/app/352720/the_universim.md)
- **Late-game sinks.** Crytivo admitted surplus resources had no use and planned a sink building with a leaderboard — [Steam: What the Future Holds](https://store.steampowered.com/news/app/352720/view/5741605105604108334)
- **Business model.** A $29.99 one-time purchase plus one cosmetic or collector DLC. No microtransactions were found. Crowdfunding came first ($387K), then about 5.5 years of paid Early Access. The long tail is about 57 average CCU in 2026 — [Steam store](https://store.steampowered.com/app/352720/The_Universim/); [Wikipedia](https://en.wikipedia.org/wiki/The_Universim); [SteamCharts](https://steamcharts.com/app/352720)

### Inferences
- Godling's credit spending could borrow "cost equals regeneration time plus a hard cap" so a single big event (a meteor) cannot be spammed. The Universim's evidence is that a big event should take roughly the whole bank.
- The Universim's Twitch mode is the closest precedent to Godling's model. Viewers change conditions and act through proxies, while the simulated beings and the streamer keep decision authority. The 3-option vote and per-command cooldowns are proven ways to keep throughput low.
- Inhabitants' visible, lasting reactions to interventions are the system's most praised god-game texture: fleeing, fear vs love, monuments, believer shifts. The opaque arithmetic behind them is the most criticised part. Keep the reactions legible.
- To avoid The Universim's late-game decline, a 24/7 world needs continuing reasons for change, not only accumulation.

### Gaps
- No data on how much Twitch integration was actually used, or how popular it was with streamers.
