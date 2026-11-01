# Deisim (Myron Software / Myron Games): VR god game, state as of 2026-11-01

Notes compiled 2026-11-01. Most primary detail comes from the developer's own Steam news posts (106 posts, Nov 2016 to Jun 2026), which I read through the Steam news API. Store pages, an Android Central review, an UploadVR news piece, Belgian company filings (through an aggregator) and SteamSpy cover the rest. Third-party estimators Gamalytic and VG Insights/Sensor Tower could not be read (HTTP 429, or the page rendered client-side), and SteamDB returned 403.

## 1. History and business: developer, platforms, engine, price, updates, sales, reviews, awards, support status

### Takeaway
Deisim is essentially a one-man Belgian project by Tommy Maloteaux ("Myron"). It launched in Steam Early Access on 19 Dec 2016, left Early Access on 1 Sep 2022 (Steam and the Quest Store together), and still receives regular free updates: there were monthly updates from Sep 2025 to Jun 2026, and Quest builds are still being uploaded in Sep and Oct 2026. It sells for $14.99/€14.99 with frequent deep discounts and has no paid DLC. Steam ownership is modest (SteamSpy: 20k–50k owners), and Quest appears to be the larger audience: about 2,035 Quest ratings against about 920 Steam reviews. There is no PlayStation VR version.

### Cited Findings
**Developer, team, location**
- The developer/publisher appears on Steam as "Myron Games". The VR wiki notes it earlier appeared as "Myron Software". Quest and Pico stores list "Myron Software" — [Steam store](https://store.steampowered.com/app/525680/Deisim/); [VR & AR Wiki](https://vrarwiki.com/wiki/Deisim); [Pico store](https://store-global.picoxr.com/gb/detail/1/1257)
- UploadVR (20 Aug 2022) names the developer as Tommy Maloteaux — [UploadVR](https://uploadvr.com/deisim-quest-store-release/)
- Company: MYRON SOFTWARE SRL/BV, enterprise no. BE 0735.604.052, founded 2 Oct 2019, Chemin de l'Oasis 15, 7000 Mons, Belgium. Directors are Tommy Maloteaux and Perrine Mercier-Guyon — [busibee.be (aggregates Belgian filings)](https://busibee.be/en/0735604052-myron-software/financials)
- In a 2017 Steam forum reply the developer calls himself a "solo developer with limited resources" — [Steam discussion "Only VR?", Jun–Jul 2017](https://steamcommunity.com/app/525680/discussions/0/2333276539602722819)
- Dec 2018: the developer mentions working with an artist. Earlier, an outside volunteer made four human models — [Steam news feed, Aug 2018–Feb 2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=10&maxlength=0&enddate=1550275200)
- 24 Feb 2021, "Big announcement": the developer was leaving his day job to work on Deisim full-time, which Patreon supporters made possible. He targeted one update per month. A Patreon had been announced on 19 Feb 2020 — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- 1 Sep 2022, "Deisim is out of early access!": the post cites "6 years of development" and says "We will use the revenue of this launch to grow the team." — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- 16 Apr 2024: the studio ("we") announced its second VR game, Underworld Overseer, as its first new project after about 8 years on Deisim. A Halloween 2025 update marked that game's first anniversary, which puts its launch around Oct 2024 — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

**Platforms and release dates**
- Steam Early Access (SteamVR, HTC Vive and Oculus Rift via SteamVR): 19 Dec 2016, after a launch postponement posted 14 Nov 2016. Native Oculus SDK support was added on Steam on 18 Aug 2017 — [Steam store](https://store.steampowered.com/app/525680/Deisim/); [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)
- Oculus (Rift) Store: the 19 Dec 2018 roadmap post links an "Oculus launch" page but gives no date. UploadVR says the game "originally launched on PC VR in 2018", which conflicts with the Steam Early Access date of 2016 and probably refers to the Oculus PC store — [Steam news feed, Aug 2018–Feb 2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=10&maxlength=0&enddate=1550275200); [UploadVR](https://uploadvr.com/deisim-quest-store-release/)
- Quest: available by sideloading/SideQuest before App Lab existed. It was one of the first 14 App Lab apps (early 2021), and moved to the full Quest Store on 1 Sep 2022. The App Lab listing went unavailable after 22 Aug 2022. Cross-buy covers Quest and Oculus PC VR, and App Lab owners got the store version automatically — [UploadVR, 20 Aug 2022](https://uploadvr.com/deisim-quest-store-release/)
- Steam full release: 1 Sep 2022 — [Steam store](https://store.steampowered.com/app/525680/Deisim/)
- Pico: listed on the Pico store at €14.99 (version 1.41, updated 14 Sep 2023, 448.9 MB, PEGI 7). It supports Neo2/Neo3/Pico 4/4 Ultra and others — [Pico store](https://store-global.picoxr.com/gb/detail/1/1257)
- Non-VR mode, including full Steam Deck playability, launched on Steam on 8 May 2025. In 2017 the developer had said non-VR play was impossible and floated a "Deisim : Flatist Edition" — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0); [Steam discussion](https://steamcommunity.com/app/525680/discussions/0/2333276539602722819)
- macOS support for the Steam version was added on 2 Jan 2026. The store requires Apple Silicon (M1 minimum, M4 recommended) — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0); [Steam store](https://store.steampowered.com/app/525680/Deisim/)
- PlayStation VR: no PSVR or PSVR2 release found. The 2017 developer forum thread does not mention PSVR — [Steam discussion](https://steamcommunity.com/app/525680/discussions/0/2333276539602722819)
- Multiplayer: in Jan 2019 the developer said there will "never" be multiplayer because it needs a different architecture — [Steam discussion](https://steamcommunity.com/app/525680/discussions/0/2333276539602722819)

**Engine**
- Unity. On 21 Oct 2025 the studio shipped a "Hotfix for Unity vulnerability issue" that fixes a vulnerability "affecting all games made with Unity" — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

**Price and price history**
- Early Access-era listing: $7.99 (VR wiki infobox, from a 2016/17 listing) — [VR & AR Wiki](https://vrarwiki.com/wiki/Deisim)
- 24 Feb 2021: "The price of the game will be increased in the coming months." The 19 Feb 2020 post had said the price would "probably be around 15$", and the 12 Nov 2021 post said "The new price will be around 15$" — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- App Lab/Quest Store price: $14.99, unchanged at the Aug 2022 move — [UploadVR](https://uploadvr.com/deisim-quest-store-release/)
- Steam now: €14.99. SteamSpy reports a $14.99 initial price — [Steam store](https://store.steampowered.com/app/525680/Deisim/); [SteamSpy API](https://steamspy.com/api.php?request=appdetails&appid=525680)
- Quest: $14.99 list, $9.99 (−33%) on sale until 2 Nov 2026. The lowest tracked price is $5.99 (15 Dec 2025), with tracking since Jun/Nov 2024 — [vrdb.app](https://vrdb.app/game/3526702020710931); [QuestStoreDB](https://queststoredb.com/game/deisim/3526702020710931)
- A deal-aggregator snippet (dekudeals) showed a Steam sale of $4.94 (−67%). I did not verify this, and the date is unknown — [dekudeals via search](https://www.dekudeals.com/items/deisim)
- Feb 2019: a 55% discount ran for the Belgian Game Awards — [Steam news feed, Aug 2018–Feb 2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=10&maxlength=0&enddate=1550275200)
- Bundles on Steam (2026-11): "God's Eye View – VR Strategy Bundle" with Eternal Starlight VR (€23.82 at 20% off), "Myron Games Collection" with Underworld Overseer (€24.48 at 30% off), and "Townsmen VR + Deisim" (€31.48 at 43% off €54.98). On Quest, Townsmen VR + Deisim costs €39.99 (−11% off €44.98, Oct 2026) — [Steam store](https://store.steampowered.com/app/525680/Deisim/); [QuestStoreDB](https://queststoredb.com/game/deisim/3526702020710931)

**DLC and updates**
- No DLC is listed. Every content update is free — [Steam store](https://store.steampowered.com/app/525680/Deisim/)
- Major updates:
  - Early Access versions 1.1 to 1.24 (2016–2019), with updates roughly monthly in 2017.
  - EA-1.24 Industrial Revolution (30 Jun 2019).
  - 1.30 Modern Age (19 Jun 2020).
  - EA-1.32 Future Age (11 Apr 2021).
  - EA-1.34 Pathfinding (22 Jun 2021).
  - Kingdoms (12 Mar 2022).
  - 1.0 (1 Sep 2022).
  - 1.39 Pirates (19 Dec 2022).
  - Space Update (14 Sep 2023).
  - Golden Empires/Jungle biome (7 Dec 2023).
  - 1.45 multi-kingdom creation (13 Oct 2024).
  - Non-VR mode (8 May 2025).
  - Dinosaurs (30 Jun 2025).
  - War (30 Sep 2025).
  - Halloween/Underworld creatures (31 Oct 2025).
  - Alien Invasion (30 Nov 2025).
  - 3 miracles + macOS (2 Jan 2026).
  - Galactic (31 Jan 2026).
  - Fantasy parts I–IV, 1.53–1.57 (28 Feb to 4 Jun 2026).
  - Sources: [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0); [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)
- Support status: the most recent Steam news post is 4 Jun 2026 (1.57). On Quest, build 1.57.520 is live. Build 1.58.543 was seen on the store on 16 Sep 2026, and 1.58.547 was uploaded on 20 Oct 2026 but not yet live. The game is therefore still actively maintained as of Oct 2026 — [vrdb.app](https://vrdb.app/game/3526702020710931); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

**Sales, owners, revenue**
- SteamSpy: 20,000–50,000 owners, 705 positive and 57 negative reviews (a lagging count), CCU 3 — [SteamSpy API](https://steamspy.com/api.php?request=appdetails&appid=525680)
- Sept 2018 dev diary: "The game is not a big success yet." — [Steam news feed, Aug 2018–Feb 2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=10&maxlength=0&enddate=1550275200)
- Company accounts for Myron Software SRL, in EUR. Belgian abbreviated accounts report gross margin, not revenue, and the figures cover all Myron titles plus Patreon income, not Deisim alone — [busibee.be](https://busibee.be/en/0735604052-myron-software/financials)

  | Period | Gross margin | Net profit/loss | Cash | Dividend |
  |---|---|---|---|---|
  | Oct 2019–Dec 2020 | 34,411 | 26,173 | 34,973 | – |
  | 2021 | 125,728 | 90,725 | 45,786 | – |
  | 2022 | 579,601 | 421,634 | 626,752 | 58,824 |
  | 2023 | 68,982 | −51,493 | 424,117 | – |
  | 2024 | −86,943 | −245,249 | 164,330 | – |
  | 2025 | 225,964 | 187,524 | 286,490 | 30,000 |

**Reviews and scores**
- Steam store fetch (2026-11-01): "Very Positive", 93% of 884 user reviews, 38 curators. The store quotes GrayStillPlays ("The ultimate God simulator 2019"), Cheru and Game Rant ("absolute sandbox game") — [Steam store](https://store.steampowered.com/app/525680/Deisim/)
- VR & AR Wiki: Very Positive as of Oct 2026, with 863 of 922 Steam reviews positive (about 93.6%) — [VR & AR Wiki](https://vrarwiki.com/wiki/Deisim)
- Meta Quest: 4.6★ from 2,035 ratings and 1,166 reviews. Distribution: 5★ 74%, 4★ 15%, 3★ 5%, 2★ 2%, 1★ 3%. Comfort rating "Comfortable" — [vrdb.app](https://vrdb.app/game/3526702020710931). QuestStoreDB gives 4.6 from about 2K ratings and 1,197 reviews — [QuestStoreDB](https://queststoredb.com/game/deisim/3526702020710931)
- Meta PC VR (Rift) store: 4.3 from 86 ratings, per a search snippet. I could not open the page — [Meta PC VR listing](https://www.meta.com/experiences/pcvr/deisim/1101455296589556/)
- Pico: 93% positive from 29 reviews — [Pico store](https://store-global.picoxr.com/gb/detail/1/1257)

**Awards**
- Nominated for Best VR/AR at the Belgian Game Awards 2019. The post says "nominated", and I found no record of a win — [Steam news feed, Aug 2018–Feb 2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=10&maxlength=0&enddate=1550275200)

### Inferences
- Steam unit estimate (my own, using the common 30–50× "Boxleiter" ratio): about 920 Steam reviews suggests roughly 28k–46k Steam units, which matches SteamSpy's 20k–50k band. At $14.99 list and heavy discounting, lifetime Steam gross revenue is probably in the low-to-mid hundreds of thousands of USD. This is an estimate, not a reported figure.
- Quest has about twice as many ratings as Steam has reviews, and ratings on Quest come easily. Quest is likely the main revenue platform. The 2022 spike in company gross margin (€580k) coincides with the 1 Sep 2022 Quest Store and Steam 1.0 launch.
- The 2023–2024 losses most likely reflect spending on the team and on Underworld Overseer (released about Oct 2024). The 2025 recovery coincides with the non-VR/Steam Deck launch, monthly updates and a second title on sale. The financials cannot be attributed to Deisim alone.
- Myron's model is a premium one-time purchase ($14.99), cross-buy, bundles with its own and partner games, deep seasonal sales, free monthly content updates, and Patreon from 2020. There are no microtransactions.

### Gaps
- No Gamalytic or VG Insights estimate (copies sold, revenue, playtime) could be retrieved: the sites returned HTTP 429 or rendered client-side. SteamDB returned 403, so there is no SteamDB price history, follower count or peak CCU.
- Exact Oculus Rift Store launch date not found (late 2018 inferred). Exact first SideQuest date also not found.
- Current team size is unknown. The studio uses "we" from 2022 to 2024, but no headcount is published.
- No dated record of the Steam price change from $7.99 toward $14.99 (2021 or 2022).
- No reviews from UploadVR, Road to VR or PSVR-focused sites were found. UploadVR's piece is a news item, not a review.

## 2. Structure and loop: eras, goals, win/lose, session shape, sandbox vs campaign

### Takeaway
Deisim has no campaign and no win or lose state. It is an open-ended god sandbox on a floating tile world: you build land and humans grow autonomously through ages. Progression comes from Deity ranks, which unlock miracles as global population grows, and from milestones such as launching a space cruiser. A separate Sandbox mode removes the mana limit and unlocks everything. Play is slow and bonsai-like, built for long and repeated sessions with autosave.

### Cited Findings
- Store description: "create your own world tile by tile and perform miracles". Humans are autonomous and evolve "from the stone age to modern age and beyond" — [Steam store](https://store.steampowered.com/app/525680/Deisim/)
- Deity ranks were added in EA-1.12 (3 Jul 2017). They are based on human count, and miracles unlock at required ranks. Rank names include minor deity (Animal miracle), Greater deity (Mine) and Supreme Deity (Void, 2017). The 1.30 update (Jun 2020) moved Void to a "bad miracle unlocked at intermediate deity lvl" — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- 12 Apr 2021: "The global population needed to reach the next deity level is now displayed in the menu." 22 Jun 2021: a message now appears when a new Deity rank is reached, and more miracles unlock early in the game — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Sandbox mode (EA-1.17, 23 May 2018) "disables the mana pool and unlocks all miracles". Achievements are disabled in Sandbox mode (Jun 2020) — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Milestone reward: launching the space cruiser unlocks the Abundance miracle. At first (2 Jan 2026) this applied only in sandbox. By the 31 Jan/1 Feb 2026 post it was "now always available even when sandbox mode is disabled" — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Era ladder as shipped:
  - Tribal/stone age, then Roman, Egyptian, Medieval, Asian and Viking-styled cultures (human models listed Jul 2018), and an "Empire Age" in progress in Dec 2018.
  - Industrial Age (EA-1.24, 30 Jun 2019), with blacksmiths and a steel factory.
  - Modern Age (1.30, 19 Jun 2020), adding oil, jewels and knowledge.
  - Future Age (EA-1.32, 11 Apr 2021).
  - Space: airships, space shuttles, and a space cruiser that sends humans to other planets (14 Sep 2023).
  - New planets: Galactic (31 Jan 2026) and Fantasy with Orcs, Elves and Wizards (28 Feb 2026).
  - Sources: [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Android Central (Nicholas Sutrich, 14 Sep 2022): eras run from early ages to kingdom, then modern and futuristic. The reviewer liked the "relaxed, bonsai-like pace" and said the game is best experienced over long periods — [Android Central via Yahoo Tech](https://tech.yahoo.com/ar-vr/articles/deisim-oculus-quest-filled-void-130023103.html)
- Session mechanics: autosave every 5 minutes, a save/load menu, and three zoom levels — [ZyberVR guide, 20 May 2025](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies). Named saves and double-click quick save/load were added in 1.55 (31 Mar 2026). Game speed control exists: speed no longer resets during UFO arrivals (EA-1.35) — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Planned "quests", where humans pray for something, were mentioned only as a possible future feature (Feb 2019 dev diary) — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)

### Inferences
- The loop: place tiles, autonomous humans settle and gather, cities show needs, the god supplies land and resources or intervenes with miracles, population grows, a Deity rank unlocks new miracles, and cities advance an era. Disasters and heretics interrupt this loop.
- Win and lose are replaced by soft goals: ranks, eras, space launch and achievements. The god can also lose a civilisation by neglect or malice, but this is not a game-over state.

### Gaps
- I did not find the total number of Deity ranks or the population threshold for each.
- I could not find typical session length or median playtime. SteamSpy reports 0, which means no data.
- No formal "wonder" system was found. Pyramids appear as a desert-city building (EA-1.16, Mar 2018).

## 3. Mechanics: shaping the world, the god's hands, miracles and their currency

### Takeaway
The god builds the world from terrain tiles chosen in a wrist-style Miracle menu. Terrain type determines resources, animals and the culture of the cities that grow there. The god's hands grab, throw and crush humans, buildings, UFOs and meteors, and move, scale and rotate the whole world. Miracles cost mana. Mana comes from cities that believe in you, is drained by cities praying to a false god, and Neutral towns generate none. Mana caps and regeneration rates are not published.

### Cited Findings
**World shaping**
- Terrain tiles: grass, ice, pine forest, desert/oasis, savanna, swamp and sakura. Each terrain spawns its own animals: deer on grass, polar bears on ice, wolves in pine forest, snakes in desert, elephants on savanna, alligators in swamp and bunnies on sakura. Mountains yield copper, coal, iron and gold depending on the adjacent terrain — [ZyberVR guide, 20 May 2025](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies)
- Later additions: Jungle biome (7 Dec 2023), blending terrains (Dec 2022), Stone miracle (EA-1.34), a limited-time Christmas Forest tile (Nov 2025), and Alien and Fantasy/Orc/Enchanted tiles (2026) — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Android Central: tiles go on empty squares, and some tools place patches of six (forests, water). Placed tiles are "hard to undo". The god does not order construction or zoning, but can build mines and regrow forests — [Android Central via Yahoo Tech](https://tech.yahoo.com/ar-vr/articles/deisim-oculus-quest-filled-void-130023103.html)
- Biome sets city style: oasis gives Arabic, savanna African, sakura Asian, and snow Nordic (futuristic Nordic cities on snow, 2023 hotfix) — [ZyberVR guide](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- The world floats above an "abyss": heretics are thrown into it and UFOs are thrown "into space" — [ZyberVR guide](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies)

**Hands in VR**
- Animated hands replaced controller models (EA-1.9, Apr 2017). In EA-1.12 (Jul 2017) the grip button crushes humans. Buildings can be destroyed by throwing them (EA-1.9). EA-1.13 (Aug 2017) set one grip to move the world, two grips to scale and rotate it, and miracles to "return to the hand". In Oct 2018, grabbing a human started showing information about that person — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)
- Quest controls (2025 guide): X/A opens the Miracle menu (terrain, animals, humans, miracles), Y cycles 3 zoom levels, the stick teleports, grip plus a hand motion gives directional teleport, and the triggers grab items and people — [ZyberVR guide](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies)
- Android Central: holding the triggers pushes and pulls the world, pinch-to-zoom scales it, and teleport or smooth locomotion is available. The god can pick up humans and their dwellings — [Android Central via Yahoo Tech](https://tech.yahoo.com/ar-vr/articles/deisim-oculus-quest-filled-void-130023103.html)
- Physical counters to threats: grab red-clad heretics and throw them into the abyss, and grab a UFO saucer and throw it into space. Meteorites are grabbable, as are airships and space shuttles: 2025 fixes cover meteorite grabbing and airships or shuttles "getting stuck after being thrown" — [ZyberVR guide](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- EA-1.35 (Jul 2021): "miracles no longer kill humans on collision". Before that, physically hurled miracles could kill people — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

**Miracles and powers (names found across sources)**
- Good or utility: Rain (the main fire extinguisher), Regen (regrows forests and restores over-mined resources), Healing/Fast-Healing (cures sick cities), Abundance, Immortality (immortal humans with strong regeneration, Jan 2026), Inspiration (creates a kingdom from a city), Create Human, Create Priest, Create Scientist, Mine, Forest, Stone, Animal (spawns fauna for the tile), Dinosaurs (species depend on the tile, Jun 2025), Underworld creatures (10 summonable, Oct 2025), Kraken (1.56), and Omens (persuade leaders to expand or start wars, Mar 2022 and Sep 2025).
- Bad, evil or disaster: Void (deletes terrain, classed as a "bad miracle"), Fear (Halloween 2019), Disease (EA-1.33 "evil miracle"), Tornado, Locusts, fire raining from heaven, Nuclear Bomb, Maelstrom, Pirates Den, Meteor, and Alien Invasion/alien capsule.
- Sources: [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0); [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600); [ZyberVR guide](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies); [Android Central via Yahoo Tech](https://tech.yahoo.com/ar-vr/articles/deisim-oculus-quest-filled-void-130023103.html)
- The 2026-03-31 update (1.55) rate-limited destructive disasters: "Destructive disasters (Meteor, Alien Invasion) can now only happen once per hour" — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- The Miracle Menu was overhauled in Oct 2025 — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

**Currency: mana**
- EA-1.2 (13 Jan 2017): "Neutral towns" stopped generating mana, and towns praying to a false god drain it. This implies that believing towns generate mana — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)
- EA-1.18 (1 Jul 2018): mana gain was rebalanced so it would not rise or fall too quickly, and the Tornado's mana cost was fixed. EA-1.24 (Jun 2019): Regen and Rain swapped cost and menu order. The Animal miracle costs "a lot of mana" (Feb 2019) — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)
- EA-1.26 (4 Aug 2019): "Mana is not consumed anymore if the animal miracle is casted on an incompatible tile." EA-1.34 (22 Jun 2021) added visual and audio feedback when the player "doesn't have enough mana". EA-1.33 added a sound for impossible miracle combinations — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Karma: EA-1.6 (Feb 2017) made karma change miracle area. EA-1.18 (Jul 2018) removed karma's effect on radius — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)

### Inferences
- The currency is earned from the simulation itself: believers produce mana, and heresy and neutrality starve it. The god's spending power therefore depends on keeping followers faithful. Healthy, believing population drives two things: mana income and Deity rank unlocks.
- Many miracles are "material" ones (place a forest, mine or stone), so the god's spending is also the city's resource supply. Mana spent becomes resources the humans need.

### Gaps
- No published numbers for mana cap, regeneration rate per believer or town, or individual miracle costs. The manual is a Google Drive link from the Steam page, which I did not retrieve.
- Unknown whether mana scales with population or with prayer activity. Humans "pray in their free time" (Aug 2018), but no source links prayer directly to the mana rate.
- No details on what the Fear miracle, Omens or Abundance do numerically.

## 4. Follower simulation: population, settlements, needs, prayers and requests, reactions, enemies, wonders

### Takeaway
Humans are fully autonomous. They gather, trade, build cities that evolve in style and era, have children who grow into workers, and choose to become priests or heretics. Each city broadcasts one "need bubble" showing its most-needed resource, with the bubble's size scaled to how badly it is needed. This is the game's version of prayer. Cities remember whether the god was kind or rude. Faith competes with science (scientists make cities atheist) and with heresy toward a false god that spreads like a plague. From 2022, cities group into kingdoms that expand, rebel, split among heirs and wage war.

### Cited Findings
**Population and lifecycle**
- Dev diary #1 (17 Sep 2018): children are smaller and too weak to work. As adults they become productive and can choose to become Priests or Heretics. The game had 44 adult models plus 40 child models in progress, and 84 human models by 29 Sep 2018 — [Steam news feed, Aug 2018–Feb 2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=10&maxlength=0&enddate=1550275200)
- Android Central: each human "has a personality and culture" that can influence others. Kingdoms expand, flourish or die out depending on the god's actions, and restless kingdoms may need to expand — [Android Central via Yahoo Tech](https://tech.yahoo.com/ar-vr/articles/deisim-oculus-quest-filled-void-130023103.html)
- Cities have names (EA-1.27, Sep 2019). The menu shows population and need-bubble stock numbers (EA-1.32, Apr 2021) — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

**Needs, which act as prayers**
- Dev Diary #4 (24 Feb 2019): early cities need food, wood and stone, and a bubble above the city shows its most-needed resource. "The more a city is evolving the more complex its need are." Medieval cities want crafted goods and meat. A prayer for Tools needs iron, coal and smelting, and trade can meet needs — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)
- EA-1.23 (Mar 2019): the size of the resource in the bubble reflects how great the need is. EA-1.6 (Feb 2017) had shown stockpiles before bubbles existed — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)
- Dec 2019: the bubble shows only resources needed "to progress and not to fill it stocks". Jun 2020: at least one worker always looks for the displayed need. Apr 2021: cities pursue their most-needed resources first. Apr 2026: imported tools, weapons and jewels are shared in small amounts so no city goes without — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Players are told to "watch city resource circles" to see which materials are needed — [ZyberVR guide](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies)

**Reactions to the god: kindness and rudeness, fear**
- EA-1.19 "Divine Favor" (1 Aug 2018): "The cities will now remember if you have been kind or rude with them." Human animations reflect happiness, and "Humans are now praying during their free time." — [Steam news feed, Aug 2018–Feb 2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=10&maxlength=0&enddate=1550275200)
- Humans flee terrifying sights. The Jan 2026 patch notes "Fearless humans no longer flee when they see something terrifying". A "Fear" miracle exists (Oct 2019) — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

**Faith, science, heresy**
- Towns have a belief system, and clothing colour shows it (EA-1.2, Jan 2017). Priest and heretic colours reflect true belief (EA-1.10) — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)
- EA-1.13 (Aug 2017): miracles convert heretics to priests at 15%, and the heretic spawn rate dropped from 10% to 5%. EA-1.23 (2019): heresy "spreads like a plague" instead of appearing at random. EA-1.24: heretics take longer to convert a city, and a heresy on/off toggle was added — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)
- Pico listing: "heretics praying to the false god" try to convert your people — [Pico store](https://store-global.picoxr.com/gb/detail/1/1257)
- 1.30 (Jun 2020): scientists produce knowledge but lower their city's faith, "making it an atheist city over time" — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0). A guide suggests keeping a 2:3 scientist-to-priest ratio — [ZyberVR guide](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies)

**Kingdoms, war, rivals**
- Kingdoms (12 Mar 2022): the Inspiration miracle creates a kingdom, and omens can persuade leaders to expand. Neutral and heretic cities form new kingdoms once they grow big enough. When a king dies, the realm is split among the heirs. 1.45 (Oct 2024) allows creating multiple kingdoms. The War update (30 Sep 2025) added a War Omen, military ships, airships and helicopters, and raised the kingdom limit to 8. 1.55 (Mar 2026) lets armies attack other continents — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Android Central: unruly kingdoms spawn heretics and attack neighbours as their rulers grow paranoid — [Android Central via Yahoo Tech](https://tech.yahoo.com/ar-vr/articles/deisim-oculus-quest-filled-void-130023103.html)
- External threats: UFOs that abduct citizens, wildfires, an alien capsule crash (Nov 2025), underworld creatures attacking cities (Halloween 2024), pirates (Dec 2022), and dangerous animals that "retaliate against humans trying to hunt them" (1.57, Jun 2026) — [ZyberVR guide](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

**Buildings and wonders**
- Pyramids for desert cities (EA-1.16, Mar 2018). Churches with cemeteries and Viking funeral boats (EA-1.11, Jun 2017). Harbours that build trade ships or pirate ships (Dec 2022). Space cruiser launch site (2023) — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

### Inferences
- Deisim expresses follower desire as passive, always-visible signals: one need bubble per city, sized by urgency, plus colour-coded belief and visible happiness animations. It does not use explicit dialogue requests. The god reads the world rather than an inbox.
- The love-or-fear axis is mostly implicit. Cities remember kind and rude acts, good and evil miracles are distinguished, frightened humans flee, and heresy grows where the god is absent or harmful. I found no evidence of a Black & White-style alignment meter.

### Gaps
- Unknown how "kind or rude" memory changes behaviour: mana output, heresy rate, rebellion or happiness.
- Birth-rate formula and housing or carrying-capacity rules were not found.
- No details of the "false god" as an entity: whether it is an AI rival god or just a heretic belief label.

## 5. In-game economy: resources, costs, growth scaling, balance

### Takeaway
Two economies are linked. The humans' economy is resource chains whose complexity scales with era. The god's economy is mana from believers, spent on miracles, with miracles unlocked by population ranks. Balance is tuned by patch-level rules, not by visible numbers: refunds on invalid casts, rate limits on disasters, and rebalanced mana gain.

### Cited Findings
- Human resource chain by era:
  - Early cities: food, wood, stone.
  - Medieval: crafted goods, meat.
  - Tools: iron plus coal plus smelting. The Industrial Age needs limited resources such as coal (2018–2019).
  - Modern Age adds oil, jewels and knowledge (Jun 2020).
  - Sources: [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600); [Steam news feed, Aug 2018–Feb 2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=10&maxlength=0&enddate=1550275200); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Mountains yield resources depending on the adjacent terrain. Resources can be over-mined and then restored with Regen — [ZyberVR guide](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies)
- Trade between cities (EA-1.16 "Trade and Pyramids", Mar 2018). Imports are shared in small amounts (Apr 2026). Harbour trade ships (Dec 2022) — [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Food dynamics: humans hunt dinosaurs for meat when other meat runs out, and dinosaurs take 15 minutes to starve instead of 3 (1.55) — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Balance and gating levers that are on record:
  - Mana gain smoothed (2018).
  - Mana refunded on incompatible animal casts (2019).
  - Feedback when mana is insufficient (2021).
  - Miracles unlocked faster early on (2021).
  - Sandbox mode removes the mana pool (2018).
  - Heresy can be toggled (2019).
  - Destructive disasters capped at once per hour (2026).
  - Sources: [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

### Inferences
- Growth scaling is qualitative. As cities advance, each era adds new required inputs, which raises the demand for divine supply (tiles, mines, regen). Rising population raises Deity rank, which in turn unlocks more ways to meet that demand.

### Gaps
- No numerical cost tables (mana per miracle), stock caps, or growth curves were found.

## 6. Making divine influence tangible in VR; what players love and criticise

### Takeaway
Deisim's god-feel comes from treating the world as a tabletop diorama. You grab, scale and rotate the whole planet, pick up individual people to inspect, fling, crush or convert them, and physically throw threats (heretics, UFOs, meteors) off the world. Players praise the bonsai-like calm, emergent cultural variety and the "being a god" feeling. They criticise poor explanation of controls, awkward early locomotion, and a $15 price for a slow game.

### Cited Findings
- Hands-on interaction:
  - One grip moves the world, two grips scale and rotate it (2017).
  - Grip crushes humans (2017), and thrown buildings are destroyed (2017).
  - Grabbing a human shows information about them (2018).
  - Miracles return to the hand (2017).
  - Heretics are thrown into the abyss, and UFOs into space.
  - Sources: [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600); [ZyberVR guide](https://zybervr.com/blogs/news/miracle-of-the-gods-complete-guide-controls-tips-strategies)
- The developer in 2017: "the game is designed around the possibilities VR offer so it is not possible to play it without VR." He later shipped a non-VR mode (May 2025), with follow-up fixes to make heretics visible when zoomed out and UFOs easier to crash in non-VR — [Steam discussion](https://steamcommunity.com/app/525680/discussions/0/2333276539602722819); [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Android Central's praise (14 Sep 2022):
  - The sense of being a god.
  - A "relaxed, bonsai-like pace".
  - Cultural variety by biome.
  - Layered complexity that emerges over time.
  - A "unique gem" for Quest 2, and the headline says it "filled the void in my heart that Black & White left".
  - Source: [Android Central via Yahoo Tech](https://tech.yahoo.com/ar-vr/articles/deisim-oculus-quest-filled-void-130023103.html)
- Android Central's criticism: some controls and actions could be explained better, locomotion feels awkward at first, and $15 may be steep given the slow pace — [Android Central via Yahoo Tech](https://tech.yahoo.com/ar-vr/articles/deisim-oculus-quest-filled-void-130023103.html)
- MoguraVR (Japanese, Sep 2022) reportedly warns that movement is fairly fast, so players prone to motion sickness should take care. This comes from a search-result summary; I did not read the article — [MoguraVR](https://www.moguravr.com/?p=193373)
- A player in 2017 bought the game because they had always wanted a god game "without consequences". Player suggestions included making people fall in love, placing monsters to limit travel, and possessing a human — [Steam discussion](https://steamcommunity.com/app/525680/discussions/0/2333276539602722819)
- Steam user tags favour "Relaxing", "Funny", "Family Friendly", "Colorful", "Artificial Intelligence" and "Outbreak Sim" — [SteamSpy API](https://steamspy.com/api.php?request=appdetails&appid=525680)

### Inferences
- The "Outbreak Sim" tag and the plague-like heresy suggest that players experience faith as a contagion they physically contain by picking out and throwing away heretics. The intervention becomes a hands-on chore with visible results.

### Gaps
- Reading individual Steam or Quest reviews at scale was out of scope. I found no aggregated list of common complaints beyond Android Central's.
- No Road to VR or UploadVR review was found.

## 7. Notable for Godling

### Takeaway
Several Deisim patterns map directly onto Godling's design, where viewers pay credits to change conditions but cannot buy decisions. Deisim's god also cannot command buildings or zoning; it can only shape the land, supply materials and send events while autonomous humans decide.

### Cited Findings
- No direct orders: the god "doesn't order construction of buildings or zones" and only shapes conditions — [Android Central via Yahoo Tech](https://tech.yahoo.com/ar-vr/articles/deisim-oculus-quest-filled-void-130023103.html)
- One visible need per city, sized by urgency, filtered to "needed to progress" items, and guaranteed that a worker is pursuing it — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0); [Steam news feed, 2016–2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=70&maxlength=0&enddate=1564617600)
- Destructive disasters (Meteor, Alien Invasion) are rate-limited to once per hour (Mar 2026) — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Cities remember whether the god was kind or rude, show happiness through animation, and pray in their free time (2018) — [Steam news feed, Aug 2018–Feb 2019](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=10&maxlength=0&enddate=1550275200)
- Mana is refunded when a miracle is cast on an incompatible tile, and failed casts give audio and visual feedback — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)
- Free themed monthly updates, limited-time seasonal content (Christmas Forest tile, Halloween creatures) and milestone unlocks (space cruiser unlocks Abundance) kept a niche 2016 game active into 2026 — [Steam news feed, recent](https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=525680&count=40&maxlength=0)

### Inferences
- **Influence currency versus agency.** Deisim's currency is earned from followers' faith. In Godling the currency comes from viewers instead. The analogue is that Deisim ties spending power to the health of the simulation, and Godling could make the cost or availability of events respond to the builder's state. That is a design option, not a Deisim fact.
- **Legible wants.** Deisim's single, size-scaled need bubble is a cheap, readable way to show stream viewers what an autonomous agent currently wants. That helps viewers decide what to spawn without being able to command anything.
- **Built-in pacing guardrails.** A once-per-hour cap on destructive disasters, mana refunds for invalid casts and smoothed income show the need to rate-limit big paid events and to refund failed ones.
- **Memory of the god's conduct.** "Cities remember kind or rude" is a direct model for Godling remembering whether viewer interventions helped or harmed it, without viewers controlling its choices.
- **Tangible, physical intervention.** Objects are grabbed, thrown and dropped into the world, and objects arrive "in the hand". Spawned objects and meteors that physically land and persist, and that the agent then reacts to, carry the same diorama feeling to a phone-browser stream.
- **Contagion-style threats** such as heresy spreading city to city, and UFOs abducting people, give recurring events the observer can watch develop and resolve.
- **Pricing reference.** Deisim sells as a $14.99 premium game with sales down to $5.99 on Quest and free updates. Its revenue came from sales plus Patreon, with no in-game purchases. It shows a small, steady audience (about 2k Quest ratings and about 920 Steam reviews over 10 years) for a calm, watch-it-grow god sim.

### Gaps
- There is no Deisim precedent for paid influence by onlookers. It is single-player only, and the developer ruled out multiplayer in 2019 — [Steam discussion](https://steamcommunity.com/app/525680/discussions/0/2333276539602722819)
