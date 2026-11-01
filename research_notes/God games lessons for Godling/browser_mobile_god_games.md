# Browser, online-multiplayer and mobile F2P god games: god powers as economy and money (state as of 2026-11-01)

Scope note: WorldBox, The Universim, Deisim, Reus, Populous, Godus and Godville are excluded (researched separately). Store-tracker revenue figures (AppGoblin, AppBrain) are third-party estimates, not developer-reported numbers. Currency conversions marked "approx." are my own, at roughly 1 EUR = 11 SEK and 1 EUR = 4.2 AED (late-2025 ballpark rates, not sourced).

## 1. Grepolis (InnoGames): gods, favor, divine powers, mythical units, gold, revenue and players

### Takeaway
Grepolis rations god powers through one regenerating resource, favor. Favor comes from temples on a square-root curve, so extra temples give less and less, and the pool is hard-capped at 500. Each power costs 25 to 300 favor, which for a typical player is hours to days of saved-up production. Gold, the premium currency, mostly does not buy powers directly. It buys timer skips, advisors and event items, including a "Blessing of Favor" that refills the pool instantly. The game has made over €200M in its lifetime and had 75,000+ daily players in Sept 2024.

### Cited Findings
**Gods and structure**
- There are eight gods: Zeus, Poseidon, Hera, Athena, Hades, Artemis, Aphrodite and Ares. Old worlds have only six, because Aphrodite was added in 2020 and Ares in 2021. Each god brings its own divine powers and mythical units. — [InnoGames Support KB: Temple](https://support.innogames.com/kb/Grepolis/en_DK/3290)
- A city worships one god. Switching gods wipes all stored favor, plus the old god's mythical units and divine powers. — [Grepolis wiki: Gods (search snippet)](https://wiki.en.grepolis.com/wiki/Gods)
- Every god has 4 divine powers. — [Grepolis wiki: Divine Powers (search snippet)](https://wiki.en.grepolis.com/wiki/Spells)

**Favor generation (the regenerating god currency)**
- InnoGames' official formula: favor per hour = game speed × √(sum of temple levels in all cities worshipping that god + 5 × number of divine statues). Example: three Zeus cities with temples at levels 25, 13 and 19 give √57, about 7.5 favor per hour. Example: temples at levels 25 and 14 plus 2 statues on a speed-1 world give √49 = 7 favor per hour. — [InnoGames Support KB: Temple](https://support.innogames.com/kb/Grepolis/en_DK/3290)
- The temple goes up to level 30. Level 1 takes 0:03:20 to build and level 30 takes 48:38:02. — [InnoGames Support KB: Temple](https://support.innogames.com/kb/Grepolis/en_DK/3290)
- Divine favor is always capped at 500, whatever the size of the temple or warehouse. A Divine Statue adds favor production equal to 5 temple levels. — [Grepolis wiki: Temple (search snippet)](https://wiki.en.grepolis.com/wiki/Temple)
- A developer-blog comment says favor, not resources, is the real limit on mythical units. — [Grepolis devblog: Proposed changes to Researches (search snippet)](https://devblog.grepolis.com/?p=2127)

**Divine power favor costs found** (the wiki pages are years old; current values may differ)
- Zeus:
  - Divine Sign: 50 favor, adds a chariot to the target city. — [Grepolis wiki: Divine Sign](https://wiki.en.grepolis.com/wiki/Divine_Sign)
  - Lightning Bolt: 200 favor, damages a random building. It has a cooldown during which it cannot be cast on the same city again. — [Grepolis wiki: Lightning Bolt](https://wiki.en.grepolis.com/wiki/Lightning_Bolt)
  - Favorable Wind: 250 favor, makes the fleet 10% stronger; outgoing attacks only. — [Grepolis wiki: Favorable Wind](https://wiki.en.grepolis.com/wiki/Favorable_Wind)
  - Zeus' Rage: 300 favor, destroys 10-30% of an incoming attack's land units. — [Grepolis wiki: Zeus' Rage](https://wiki.en.grepolis.com/wiki/Zeus'_Rage)
- Poseidon (powers: Kingly Gift, Call of the Ocean, Earthquake, Sea Storm):
  - Kingly Gift: 25 favor, gives 800 wood. — [Grepolis wiki: Kingly Gift](https://wiki.en.grepolis.com/wiki/Kingly_Gift)
  - Sea Storm: 280 favor, destroys 10-30% of an incoming fleet. — [Grepolis wiki: Sea Storm](https://wiki.en.grepolis.com/wiki/Sea_Storm)
- Hera (powers: Wedding, Happiness, Population Growth, Desire):
  - Wedding: 30 favor, gives 200 wood, 200 stone and 200 silver. — [Grepolis wiki: Wedding](https://wiki.en.grepolis.com/wiki/Wedding)
  - Happiness: 120 favor, +50% wood, stone and silver production for 12 hours on a speed-1 world. — [Grepolis wiki: Happiness](https://wiki.en.grepolis.com/wiki/Happiness)
- Athena (powers: Patroness, Wisdom, City Protection, Heroic Power):
  - Patroness: 60 favor, gives 5 random troops. — [Grepolis wiki: Patroness](https://wiki.en.grepolis.com/wiki/Patroness)
  - The Heroic Power entry shows 200 favor in a snippet, but the snippet does not clearly tie the number to that power. — [Grepolis wiki: Heroic Power](https://wiki.en.grepolis.com/wiki/Heroic_Power)
- Hades (powers: Plague, Return from the Underworld, Treasures of the Underworld, Helmet of Invisibility):
  - Plague: 250 favor, halves the target city's basic resource production for 6 hours on speed 1. Cast on enemies. — [Grepolis wiki: Plague](https://wiki.en.grepolis.com/wiki/Plague)
- Artemis (powers: Nature's Gift, Aim of the Huntress, Illusion, Purification): power lists from [Grepolis wiki: Heroic Power (search snippet)](https://wiki.en.grepolis.com/wiki/Heroic_Power).
- "Charitable Festival: 130 favor" appeared in a search snippet attributed to Zeus. I could not verify which god it belongs to. — [Grepolis wiki: Divine Powers (search snippet)](https://wiki.en.grepolis.com/wiki/Spells)
- Ares (added 2021) uses a second resource, Fury, capped at 5,000:
  - Ares' Sacrifice: 100 favor. Sacrifices up to 50 population of your own non-mythical units, at 2 Fury per population (max 100 Fury).
  - Ares' Army: 380 favor. Spends the whole Fury pool for 1 Spartoi per 25 Fury.
  - Bloodlust: 100 favor. +5% attack, plus 1% per 200 Fury.
  - Spartan Training: 80 favor. +70% recruitment speed, plus 1% per 100 Fury, for 6 hours.
  - Mythical units: Ladon 490 favor, Spartoi 60 favor. The Divine Envoy, which any god can recruit, costs 12 favor.
  - — [InnoGames Support KB: Ares](https://support.innogames.com/kb/Grepolis/en_DK/3500)

**Mythical units (favor cost)**
- A rebalance table on the wiki lists:

  | Unit | Favor (old cost) |
  |---|---|
  | Manticore | 270 (was 405) |
  | Hydra | 300 (was 400) |
  | Cyclops | 240 |
  | Griffin | 230 |
  | Cerberus | 180 |
  | Minotaur | 180 |
  | Pegasus | 120 |
  | Medusa | 110 |
  | Harpy | 85 |
  | Centaur | 70 |

  The snippet says this rebalance went live only on the beta community at version 2.70, so live costs may differ. — [Grepolis wiki: Rebalancing 4 (search snippet)](https://wiki.en.grepolis.com/wiki/Rebalancing_4)
- An older wiki entry lists Minotaur at 202 and Manticore at 405. A 2026 fan guide says official support shows the Hydra at 300 favor, 50 population and 6,750 wood / 3,500 stone / 4,750 silver. — [Grepolis wiki: Mythical Units](https://wiki.en.grepolis.com/wiki/Mythical_Units); [Grepoliss.com Hydra guide 2026](https://grepoliss.com/the-hydra-in-grepolis-your-complete-guide/)
- Units by god: Zeus has Minotaur and Manticore, Hera has Harpy and Medusa, Poseidon has Cyclops and Hydra, Athena has Centaur and Pegasus, and Hades has Cerberus and Erinys. — [Grepoliss.com gods guide 2026](https://grepoliss.com/grepolis-gods-guide-2026-powers-mythical-units-best-god-strategy/)

**How gold (premium) touches favor and powers**
- Favor can also come from:
  - a "Blessing of Favor" item, which fills the favor pool instantly;
  - heroes, which can generate instant favor;
  - the "Temple looting" research, which steals favor from other players.
  - Event rewards can raise favor production in all cities by 60% for 5 weeks.
  - — [InnoGames Support KB 4379 (search snippet)](https://support.innogames.com/kb/Grepolis/en_DK/4379)
- Events: gold buys extra offerings, and each repeat purchase that day costs more (the price rises by the base price each time and resets at midnight). In the Tyche wheel event, gold buys Tyche Coins and each spin costs 10 coins. — [InnoGames Support KB (search snippet)](https://support.innogames.com/kb/Grepolis/en_DK/4379)
- Gold trading needs a market at level 5 or higher, with a maximum of 200 gold per trade. Building and research timers can be finished with gold, and anything with under 5 minutes left finishes free. — [InnoGames Support KB: Premium Features (search snippet)](https://support.innogames.com/kb/Grepolis/en_DK/3545)
- Advisors cost 100 gold per 14 days each, according to an old fan guide. The Administrator unlocks the Quick Bar and overview menus. — [Grepolis Guide by Omego](https://grepomego.weebly.com/premium.html); [InnoGames Support KB: Advisors](https://support.innogames.com/kb/Grepolis/en_DK/3539/Advisors)
- Gold packages run from $4.99 (440 gold) to $79.99 (20,000 gold), per a third-party review about 2 years old. I found no current official price list. — [Insider Gaming / MMOBomb review (search snippet)](https://www.mmobomb.com/review/grepolis)
- The mobile app is currently listed as "Grepolis - Divine Strategy MMO". — [App Store](https://apps.apple.com/app/id1612262044)

**Revenue and players**
- Grepolis launched in 2009. At its 15th anniversary (Sept 25, 2024) it had more than €200M lifetime revenue and 75,000+ daily active players, 30% of whom had played for 10+ years. — [InnoGames Newsroom, 2024-09-25](https://newsroom.innogames.com/15-years-of-grepolis-why-a-second-hit-game-is-so-important)
- InnoGames passed €2B lifetime revenue in July 2025:
  - Forge of Empires leads; Tribal Wars, Grepolis and Elvenar each passed €200M.
  - 99% of revenue since 2007 has come from in-app purchases.
  - Mobile's share rose from 27% (2007–2019) to 43% (2020–present).
  - Top markets are the US, Germany and France.
  - — [InnoGames Newsroom](https://newsroom.innogames.com/strong-evergreen-ips-enable-innogames-to-reach-eur-2-billion-in-lifetime-revenues); [PocketGamer.biz](https://www.pocketgamer.biz/innogames-has-surpassed-2-billion-in-lifetime-revenue/)

### Inferences
- **Powers cost hours to days of saving.** On a speed-1 world, one city with a maxed (level-30) temple makes √30 ≈ 5.5 favor per hour, about 131 per day. At that rate:

  | Power | Favor | Wait |
  |---|---|---|
  | Wedding | 30 | ~5.5 h |
  | Divine Sign | 50 | ~9 h |
  | Happiness | 120 | ~22 h |
  | Lightning Bolt | 200 | ~36 h |
  | Plague | 250 | ~46 h |
  | Zeus' Rage | 300 | ~55 h |
  | Full 500 cap | 500 | ~91 h |

  Ten maxed cities make only √300 ≈ 17.3 per hour, about 3.2× one city rather than 10×. The square root deliberately squeezes large empires (calculation from the official formula).
- **The 500 cap blocks hoarding.** Favor above the cap is lost, so players keep spending regularly instead of saving for one huge burst. The most expensive regular spells (280–300) are about 60% of the cap.
- **Gold sells around the scarcity.** The cheapest gold-adjacent ways to get favor are event items (Blessing of Favor, production boosts) and heroes, not a "buy favor" button. The escalating offering price that resets at midnight is a daily spending throttle.
- **Ares adds a second currency fed by sacrifice.** Fury comes from destroying your own units, so it is earned by destruction, not by time.

### Gaps
- I could not get the full official cost table. The wiki host (wiki.en.grepolis.com) refused connections and the Fandom mirror returned 402. Costs are missing for Aphrodite's powers and for many Poseidon, Hera, Athena, Hades and Artemis powers, as are the Siren and Satyr unit costs. Some current values may differ from the old wiki pages.
- I found no current official gold price list or gold price for a Blessing of Favor.
- I found no annual Grepolis revenue for 2024–2026; only lifetime figures exist.

## 2. Ikariam (Gameforge): wonders, miracles, priests, cooldowns, ambrosia

### Takeaway
Ikariam's god power is the island miracle. Each island has one wonder; players fire it from a temple staffed with priests. It then lasts 4–24 hours and goes on a 1–9 day cooldown, which gets shorter when more players on the island build temples to the same wonder. Ambrosia, the premium currency (about €0.06–0.12 each on mobile), is sold as comfort: premium account, trader, build speed-ups, plots, cosmetics. Gameforge markets it as "comfortable, not stronger." A 2023 update added gods kept happy with favor earned from daily tasks.

### Cited Findings
- Ikariam is a Gameforge browser game launched February 2008. Wikipedia calls it "nominally free-to-play." Each island holds 16 players, or 17 with Ambrosia, and the English version has 19 worlds. — [Wikipedia: Ikariam](https://en.wikipedia.org/wiki/Ikariam)
- Priests are needed to trigger island wonders, and you need a temple to hire them. A level-32 temple holds up to 1,092 priests. — [Ikariam Fandom wiki: Priest (search snippet)](https://ikariam.fandom.com/wiki/Priest)
- The Forge miracle lasts 24 hours and then has a 7-day cooldown. Building more temples to the same miracle in other towns shortens the cooldown. — [AnandTech forum, Ikariam thread (search snippet)](https://forums.anandtech.com/threads/ikariam-web-based-graphical-game.186424/post-33876752)
- A third-party calculator (dated June 27, 2026) lists base duration and cooldown:

  | Miracle | Effect | Duration | Cooldown |
  |---|---|---|---|
  | Forge of Hephaestus | Armour and damage | 24 h | 7 days |
  | Sacred Grove of Hades | Marble from losses | 16 h | 4 days |
  | Gardens of Demeter | Population growth | 24 h | 9 days |
  | Parthenon of Athena | Safe warehouse goods | 24 h | 7 days |
  | Temple of Hermes | Loading speed | 4 h | 1 day |
  | Fortress of Ares | Morale | 12 h | 3 days |
  | Fountain of Poseidon | Ship speed | 4 h | 1 day |
  | Colossus | Enemy scatter | instant | 3 days |

  The calculator's examples fit a cooldown factor of 5 ÷ (summed faith levels of same-miracle temples), with Theocracy multiplying by 0.8. Faith must be at least 20% to use a miracle and caps at 100%. Effective faith is limited by priest coverage. — [West-Games Ikariam Miracle Cooldown Calculator](https://west-games.com/ikariam-miracle-cooldown-calculator/) (unofficial; its formula is not confirmed by Gameforge)
- Ambrosia prices on the Belgian App Store: 50 for €5.99, 400 for €29.99, 1,000 for €59.99. A 2009 review cited $14.99 for 100 Ambrosia. — [App Store BE: Ikariam (search snippet)](https://apps.apple.com/be/app/ikariam/id555265373); [Gamezebo 2009 review](https://www.gamezebo.com/2009/12/31/ikariam-review/)
- Ambrosia uses, from the fan wiki: Premium account 10 Ambrosia per 7 days, Premium Trader 5 Ambrosia per trade, about 4 Ambrosia per 30 minutes of build time skipped, and colony founding. — [Ikariam Fandom: Ikariam Plus (search snippet)](https://ikariam.fandom.com/wiki/Ikariam_Plus); [Ikariam Fandom: Shorten Building Time (search snippet)](https://ikariam.fandom.com/wiki/Shorten_Building_Time)
- Gameforge's own Ambrosia guide (undated, © 2002–2026):
  - Uses: automatic worker distributor ("most-used"), build-time speed-ups, extra building plots, cosmetic customisation, and a permanent "Governor".
  - Ambrosia "gives no direct combat advantage — it makes the gaming experience more comfortable, not stronger".
  - Small amounts are given free as event rewards.
  - — [Gameforge: Ikariam Ambrosia Guide](https://gameforge.com/en-GB/games/ikariam-ambrosia.html)
- Gameforge also runs "Is Ikariam pay-to-win?" marketing pages saying Ambrosia does not buy stronger or faster troops. These are publisher marketing, not independent. — [Gameforge: Is Ikariam Pay-to-Win?](https://gameforge.com/no-NO/games/ikariam-pay-to-win.html)
- The "Gods of Olympus" update was announced Nov 8, 2023:
  - Six gods, each boosting one resource: Dionysus wine, Pan wood, Hephaestus sulfur, Tyche marble, Theia crystal, Plutus gold.
  - A new Gods' Shrine building; each colony worships one god.
  - Favor is earned by completing daily tasks and donated to keep gods satisfied, and satisfied gods give bigger production bonuses.
  - — [Game Developer press release, 2023-11-08](https://www.gamedeveloper.com/press-release/gameforge-reveals-_ikariam_-gods-of-olympus-update-bringing-new-content-to-greek-city-builder-mmo-later-this-winter)

### Inferences
- **Ambrosia unit price is about €0.12 at the smallest pack and €0.06 at the 1,000 pack.** That makes:
  - Premium account: about €0.60–1.20 per week.
  - One premium trade: about €0.30–0.60.
  - 30 minutes of build skip: about €0.24–0.48.

  The bulk Ambrosia unit price (€0.06) is close to Godling's €0.05 credit.
- **Miracles are rationed by cooldown, not by currency, and the cooldown is a shared island resource.** More co-worshipping temples mean faster recharge. That gives neighbours a cooperative reason to invest together instead of a reason to pay.
- **Ikariam's 2023 favor works as attendance currency.** It is earned by daily tasks and spent to keep gods "satisfied," a retention loop rather than a purchase.

### Gaps
- I found no official Gameforge source for miracle cooldown formulas or level tables; the Fandom wiki returned 402.
- I could not confirm whether Ambrosia can shorten a miracle cooldown or trigger a miracle directly.
- I found no Ikariam player counts or revenue for 2020–2026.

## 3. Other browser and online games with god powers or a god role (Travian, InnoGames portfolio, Facebook-era and social god games)

### Takeaway
Few browser MMOs outside Grepolis and Ikariam make the player a god. The nearest equivalents are Travian's Natar artefacts, which are powerful relics captured mid-game, and its World Wonder endgame, where gold is switched off. GodFinger (2010, ngmoco) was the main social/mobile god game of the Facebook era. It used regenerating mana for powers and sold "Awe" for speed-ups. I found no evidence for "Wonderhill" or a "My Little Planet" god game.

### Cited Findings
- **Travian Legends artefacts and World Wonder**
  - Artefacts are crafted by the Natars (an NPC faction), appear mid-game, give "significant power," and do nothing while the Natars hold them. Legends caps how many artefacts one player can capture, and only one can have an account-wide effect. — [Travian support: Artefacts](https://support.travian.com/pt/articles/101-artefacts); [Travian blog: Artefact release](https://blog.travian.com/2023/06/how-to-get-ready-for-the-artefact-release)
  - The first player or alliance to raise a World Wonder to level 100 wins the server. In World Wonder villages, gold cannot be used: instant builds and NPC trading are disabled, though Travian Plus still works. — [Travian support: World Wonder](https://support.travian.com/pt/articles/153-building-a-world-wonder)
  - Gold packages on the App Store run about $1.99–$69.99. A Daily Star review says the game is not pay-to-win; TV Tropes says it is often called "allegedly free" and that you must spend heavily to compete. — [App Store: Travian Legends](https://apps.apple.com/us/app/-/id1544118325); [The Daily Star](https://www.thedailystar.net/shout/game-review/news/slow-steady-and-fun-1829737); [TV Tropes: Travian](https://tvtropes.org/pmwiki/pmwiki.php/VideoGame/Travian)
- **InnoGames' other titles** (Forge of Empires, Tribal Wars, Elvenar) each made more than €200M lifetime. I found no god-power mechanic in them that matches this brief. — [InnoGames Newsroom](https://newsroom.innogames.com/strong-evergreen-ips-enable-innogames-to-reach-eur-2-billion-in-lifetime-revenues)
- **GodFinger** (the brief's "Godfinger by Wonderhill, iOS 2011" is a misattribution)
  - Developed by Wonderland Software (ex-Lionhead staff) and published by ngmoco. It came out on iPad April 3, 2010 and on iPhone/iPod Touch June 17, 2010. — [Wikipedia: GodFinger](https://en.wikipedia.org/wiki/GodFinger); [Engadget 2010-01-26](https://www.engadget.com/2010-01-26-ex-lionhead-devs-form-wonderland-software-announce-godfinger.html)
  - Gameplay:
    - You are a god with one small planet. Followers farm gold, but they tire and must recharge at buildings.
    - Powers (terraforming, rain, floods, lightning, sun, fire) unlock as you level up, and each use costs mana.
    - Mana starts at 10 and regenerates over time. The maximum grows with level, and visiting other planets or having followers worship at a totem or shrine speeds regeneration.
    - Visiting friends' planets and "enchanting" their followers pays both you and the owner.
    - — [Wikipedia: GodFinger](https://en.wikipedia.org/wiki/GodFinger)
  - Monetization: the game was free, with the premium currency "Awe" bought by in-app purchase to speed up farming and construction and to buy items. — [Wikipedia: GodFinger](https://en.wikipedia.org/wiki/GodFinger); [PocketGamer](https://www.pocketgamer.com/godfinger/godfinger-coming-to-iphone-very-soon)
  - It was pulled from the App Store Feb 1, 2013, and its service shut down Mar 31, 2013. GodFinger 2 (JiggeryPokery) soft-launched in Canada in 2014 via DeNA and launched worldwide May 19, 2016, to mixed reviews. Classic mode returned inside it in 2017, and it was gone from the App Store by Jan 2022. — [Wikipedia: GodFinger](https://en.wikipedia.org/wiki/GodFinger)
- **Doodle God** (JoyBits) began as a web (Flash) element-combination "god" game. In 2013, most of the Doodle series' 100M+ downloads came from Flash portals. — [PocketGamer.biz](https://www.pocketgamer.biz/doodle-god-series-uses-flash-to-surpass-170-million-downloads-worldwide)

### Inferences
- **Travian keeps money out of the decisive endgame.** Gold is disabled in World Wonder villages, which concedes that paying where the winner is decided would delegitimise the outcome.
- **GodFinger had the full template early.** Its regenerating mana, worship that speeds regeneration, social visits that pay both sides, and a premium speed-up currency are the template that later mobile god games reused. Its shutdown shows that live-service god games die when the servers go dark.

### Gaps
- I found no reliable sources on "Gods & Kings"-style browser MMOs, Neopets-style social god games, or a "My Little Planet" god game; none appeared in my searches.
- I found no GodFinger download or revenue figures.
- I did not check Elvenar's Ancient Wonders for god-like mechanics.

## 4. Mobile god games and idle god or planet sims: what they sell

### Takeaway
Mobile god and sandbox titles make money in three ways:
1. Paid toys with cheap add-ons: Pocket God, $0.99 plus 99¢ packs.
2. Ad-heavy F2P sandboxes that sell "remove ads" and one-off power or weapon unlocks: Solar Smash, with an estimated 62% of revenue from ads and individual weapons around €2.6.
3. Timer and premium-currency economies, which drew the main regulatory backlash: EA's Dungeon Keeper, 2014.

### Cited Findings
- **Pocket God** (Bolt Creative, launched Jan 9, 2009): a god game with pygmies on an island that you can pamper or torment.
  - It sold for $0.99 and reached 2M paid units in Jan 2010, the first paid iPhone app to do so. — [Game Developer](https://gamedeveloper.com/game-platforms/-i-pocket-god-i-becomes-first-iphone-app-to-sell-over-2m-units); [GamesBeat](https://gamesbeat.com/pocket-god-sells-2m-units-on-the-iphone-first-paid-app-to-do-so/)
  - At peak it sold about 18,000 copies a day, about $18,000 a day. It shipped weekly episodic updates that stayed free, plus optional 99¢ skin packs (130,000 sold early on). — [GamesBeat case study](https://gamesbeat.com/pocket-god-is-a-case-study-of-a-hit-iphone-game/); [PocketGamer.biz GDC 2010](https://www.pocketgamer.biz/interview/19075/gdc-2010-castelnuovo-on-pocket-gods-140000-in-app-purchases/feature/60621/top-games-soft-launch/)
  - It ended after 47 updates, 6M paid downloads and 1.3M in-app purchases. — [GamesBeat](https://gamesbeat.com/after-6m-paid-downloads-mobile-game-hit-pocket-god-wraps-up-with-its-final-apocalyptic-update/)
  - Bolt Creative publicly argued it needed to "be frank with gamers and explain why we need micro transactions." — [PocketGamer.biz](https://www.pocketgamer.biz/bolt-creative-we-need-to-be-frank-with-gamers-and-explain-why-we-need-micro-transactions/)
- **Doodle God / Doodle Devil / Doodle Kingdom** (JoyBits)
  - 100M+ downloads across the series by 2013, later 170M. Store listings now claim "over 185–190 million" players, which is marketing. JoyBits said 95% of players came organically. — [PocketGamer.biz](https://www.pocketgamer.biz/doodle-god-series-uses-flash-to-surpass-170-million-downloads-worldwide); [GamesBeat](https://gamesbeat.com/after-100m-downloads-joybits-readies-an-ambitious-doodle-god-sequel-for-tablets)
  - Revenue was about $2M a year in 2013, when in-app purchases were overtaking paid downloads. A Jan 2025 interview said IAP monetization grew 650% in 2024. — [PocketGamer.biz interview](https://www.pocketgamer.biz/100-million-downloads-is-just-the-start-for-us-says-joybits-ceo-paul-baldwin); [WN Hub, Jan 2025](https://wnhub.io/news/monetization/item-46810)
  - AppGoblin estimates the main Doodle God app at about 817.5K installs and under $10K a month (an estimate covering one app only). — [AppGoblin](https://appgoblin.info/apps/joybits.doodlegod)
- **Solar Smash** (Paradyme, London): a planet-destruction physics sandbox with 50+ weapons.
  - Android: 240M downloads, about 100K a day over the prior 30 days. — [AppBrain](https://www.appbrain.com/app/solar-smash/com.paradyme.solarsmash)
  - Estimated $1M+ a month on Android, split 62% ads and 38% IAP (estimate). The spin-off Solar Smash 2D has about 15.5M installs and $50K+ a month. — [AppGoblin](https://appgoblin.info/apps/com.paradyme.solarsmash); [AppGoblin 2D](https://appgoblin.info/apps/com.paradyme.solarsmash2d)
  - iOS: 4.7★ from 7.3K ratings (Sweden store). In-app purchases in SEK, with approx. euro values:

    | Item | SEK | Approx. € |
    |---|---|---|
    | AdFree | 49 | 4.4 |
    | Von Neumann Probe | 29 | 2.6 |
    | Ancient Destroyer | 29 | 2.6 |
    | Planet Killer | 29 | 2.6 |
    | Healing Pack | 39 | 3.5 |
    | Unlock Levels and Achievements | 39 | 3.5 |
    | Monster Weapon Pack | 69 | 6.3 |
    | All Planets Pack | 99 | 9 |
    | All Weapons Pack | 129 | 11.7 |
    | Weapons and planets pack | 199 | 18 |

    — [App Store SE: Solar Smash](https://apps.apple.com/se/app/solar-smash/id1495723103?l=en)
- **Cell to Singularity** (Computer Lunch, NYC): an idle evolution game.
  - 36M Android downloads per AppBrain; Google Play shows 10M+. — [AppBrain](https://www.appbrain.com/app/cell-to-singularity-evolution/com.computerlunch.evolution)
  - Revenue estimates conflict: $200K+ a month (94% IAP) in one AppGoblin snapshot and $10K+ in another. — [AppGoblin](https://appgoblin.info/apps/com.computerlunch.evolution)
  - Google's publisher case study credits ads together with in-app purchases. — [Google AdMob story](https://www.google.nl/ads/publisher/stories/computer_lunch_games/)
- **God of World: Sandbox Sim Life** (Pixio): 4.9★ from 217 ratings, last updated 20/08/2025.
  - In-app purchases in AED (approx. €):

    | Item | AED | Approx. € |
    |---|---|---|
    | God Powers Tier 1 Pack | 22.99 | 5.5 |
    | No Ads Pack | 12.99 | 3.1 |
    | Double Speed | 19.99 | 4.8 |
    | Auto Manager | 39.99 | 9.5 |
    | Gold Pack | 39.99 | 9.5 |
    | Builder Pack | 2.99 | 0.7 |
    | Buy Wood | 2.99 | 0.7 |

  - A 2022 review complained of "an ad every 10 seconds." — [App Store AE](https://apps.apple.com/ae/app/id1579657842?l=en-gb)
- **Religion Inc. God Simulator** (GameFirst, Armenia): costs €0.29 upfront, plus in-app purchases at €0.99–5.99 (unlock archetypes such as "Destructive" or "Shamanism", or "Unlock everything" for €5.99). It was still updated in 2026. — [App Store BG](https://apps.apple.com/bg/app/id1484622401)
- **Almighty: God Idle Clicker** added a rewarded-video system (changelog entries from 2019 and 2022). — [App Store](https://apps.apple.com/id/app/id1344171057)
- **Dungeon Keeper mobile** (EA, 2014): an "evil overlord" god game.
  - In July 2014 the UK ASA ruled EA's email ad "GET DUNGEON KEEPER ON MOBILE FOR FREE!" misleading. Timers grow longer and dearer to skip as you progress, and gems earned in play come too slowly to keep pace. EA had to make clear that in-app purchases significantly affect gameplay.
  - EA argued the "average player" expects premium-currency-and-timer monetization.
  - — [ASA ruling](https://www.asa.org.uk/Rulings/Adjudications/2014/7/Electronic-Arts-Ltd/SHP_ADJ_258907.aspx); [Engadget 2014-07-02](https://www.engadget.com/2014-07-02-uk-regulator-rules-free-dungeon-keeper-ad-was-misleading.html); [PocketGamer.biz analysis](https://www.pocketgamer.biz/asas-dungeon-keeper-ruling-risks-opening-up-a-nasty-can-of-worms)

### Inferences
- **Pocket God is the closest precedent to Godling** (an island of little people, a watcher-god who intervenes). By my estimate, 6M × $0.99 ≈ $5.9M gross from sales plus about $1.3M gross from in-app purchases. It ran on weekly free content and cheap optional packs, not energy or timers.
- **Destruction toys sell weapons as one-off unlocks.** Solar Smash sells weapons at about €2.6 each, not as consumables. Almost all its revenue is ads plus permanent unlocks. That fits a "watch and smash" audience that does not tolerate energy systems.
- **Timer escalation is the regulator-tested red line.** When timers get longer while earn rates stay flat (Dungeon Keeper), "free" marketing becomes legally misleading in the UK.

### Gaps
- I found no reliable 2020–2026 top-grossing list for "god" or "planet" mobile games specifically. Sensor Tower/AppMagic coverage of the category did not surface.
- I did not check TerraGenesis, "Idle Universe"-type titles or "Sandbox: God Simulator."
- I found no developer-reported revenue for Solar Smash; all figures are tracker estimates.

## 5. Browser sandbox toys where the player is effectively a god (falling-sand games)

### Takeaway
Falling-sand toys (Dan-Ball's Powder Game from 2007, The Powder Toy, and Sandspiel from 2018) are free, mostly not monetized, and live on emergent behaviour plus share galleries. Sandspiel had a couple of thousand daily players and 70,000+ uploads within months of launch. I found no reliable audience totals for Powder Game or The Powder Toy.

### Cited Findings
- Sandspiel (Max Bittker, late 2018, Rust/WebGL, MIT-licensed):
  - "A couple thousand" daily players and a young playerbase as of April 2019.
  - Over 70,000 creations uploaded.
  - Firestore cost about $50 a month (99% from reads) before a move to Postgres at about 10% of the cost.
  - Creations are saved as PNGs. The gallery supports browsing, search and voting, with no comments and no accounts.
  - Bittker describes a "healthy remix culture," and uploads were also posted to the @sandspiel_feed Twitter account.
  - — [Max Bittker, "Making Sandspiel", 2019-04-30](https://maxbittker.com/making-sandspiel)
- Why these toys compel, per Bittker:
  - Simple per-element rules produce complex interactions.
  - They are open-ended experiments and story-making.
  - "Low-fidelity art is also appealingly open to interpretation" (quoting Loren Schmidt).
  - Every player gets an immediate audience through uploads.
  - He credits the "microcommunity" of Powder Game's upload galleries (about 2007–2013) for his own interest.
  - — [Max Bittker, "Making Sandspiel"](https://maxbittker.com/making-sandspiel)
- Sandspiel's stated goal is to support "sharing and forking of fun creations." It is featured on Chrome Experiments and hosted on CrazyGames. — [Sandspiel README](https://raw.githubusercontent.com/MaxBittker/sandspiel/master/README.md); [Experiments with Google](https://experiments.withgoogle.com/sandspiel); [CrazyGames](https://www.crazygames.com/es/game/sandspiel)
- The follow-up Sandspiel Studio (with TodePond) lets players visually program and share their own elements. — [Brian Lovin HN mirror](https://brianlovin.com/hn/35999835)
- The Powder Toy:
  - Created by Stanislaw K. Skowronek; now maintained by jacob1 and GitHub contributors.
  - Online "saves" let people view and play with others' creations. Saving and commenting need an account, and save history was added later.
  - — [Falling-sand game (Wikipedia mirror)](https://ipfs.aleph.im/ipfs/QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco/wiki/The_Powder_Toy.html); [The Powder Toy releases](https://www.github.com/The-Powder-Toy/The-Powder-Toy/releases?page=8)
- Dan-Ball's Powder Game timeline: versions 6.4 (2009) through 8.6 (2011) added an upload limit and vote counts in user rankings. — [Dan-Ball fan wiki](https://danball.fandom.com/wiki/File:PG_ver6.8.gif)

### Inferences
- **The draw is emergence plus an audience, not monetization.** The audience comes from upload galleries, voting and remixing, so sharing is the retention engine. That suits a watched sim like Godling, where viewers come for surprising consequences of small interventions.
- **Upload galleries attract young users and junk.** They draw memes and promotion from young players, so moderation matters as soon as viewers can inject content.

### Gaps
- I found no audited audience sizes for Powder Game or The Powder Toy (total saves, monthly users). Sandspiel's numbers are a single 2019 data point.

## 6. Patterns: regenerating god currencies, premium for powers, timers, pay-to-win backlash, fairness, EU consumer protection

### Takeaway
The accepted pattern is a slow, capped, regenerating god currency (favor or mana) that rations power by time, with money buying convenience, cosmetics or one-off unlocks around it. The hated pattern is escalating timers or energy that money skips, plus pressure selling. EU regulators have codified the second as a target: CPC Key Principles (March 2025), Star Stable enforcement, a Sept 2026 follow-up, and a pending Digital Fairness Act.

### Cited Findings
**Regeneration rates found**

| Game | Currency | Rate | Cap / cost |
|---|---|---|---|
| Grepolis | Favor | √(sum of temple levels + 5 × statues) per hour × speed | 500 cap; powers 25–380 |
| GodFinger | Mana | Starts at 10, regenerates; worship and visits speed it up | Max rises with level |
| Ikariam | Miracle | 4–24 h effect | 1–9 day cooldown, shortened by co-worshipping temples |

Sources: [InnoGames KB](https://support.innogames.com/kb/Grepolis/en_DK/3290); [Wikipedia: GodFinger](https://en.wikipedia.org/wiki/GodFinger); [West-Games calculator](https://west-games.com/ikariam-miracle-cooldown-calculator/)

**What players and regulators see as unfair**
- The UK ASA (2014) treated timers that grow with progress, where premium currency is the practical way forward, as making "free" claims misleading. — [ASA](https://www.asa.org.uk/Rulings/Adjudications/2014/7/Electronic-Arts-Ltd/SHP_ADJ_258907.aspx)
- Publishers defend themselves by framing purchases as convenience ("comfortable, not stronger"). Independent views on Travian split between "not pay-to-win" and "allegedly free." — [Gameforge](https://gameforge.com/en-GB/games/ikariam-ambrosia.html); [Daily Star](https://www.thedailystar.net/shout/game-review/news/slow-steady-and-fun-1829737); [TV Tropes](https://tvtropes.org/pmwiki/pmwiki.php/VideoGame/Travian)
- Ad overload is the main complaint in ad-funded god sims, for example "an ad every 10 seconds." — [App Store: God of World](https://apps.apple.com/ae/app/id1579657842?l=en-gb)

**EU consumer protection**
- On 21 March 2025 the CPC Network published Key Principles on in-game virtual currencies, as soft law resting on the Unfair Commercial Practices Directive 2005/29/EC.
  - It defines virtual currencies as bought with real money and used to pay for in-game content.
  - It requires clear, transparent pricing and pre-contractual information.
  - — [Baker McKenzie](https://connectontech.bakermckenzie.com/european-consumer-protection-network-issues-new-key-principles-on-in-game-virtual-currencies-impact-for-gaming-and-gambling-entities-in-belgium-the-eu-and-beyond/); [Lewis Silkin](https://www.lewissilkin.com/insights/2025/03/26/eu-bodies-act-against-gaming-companies-to-protect-children-from-in-game-purchase-102k658); [Bird & Bird](https://www.twobirds.com/en/insights/2025/global/regulatory-spotlight-virtual-currency-vs-consumer-law-part-2)
- Star Stable Entertainment was the first enforcement target. The Network cited direct appeals to children to buy or nag adults, and time-limited offers as "pressuring techniques." — [Forbrukertilsynet](https://www.forbrukertilsynet.no/eng-articles/national-consumer-authorities-and-commission-take-action-on-harmful-practices-in-the-gaming-industry); [Games Market](https://www.gamesmarket.global/case-of-star-stable-online-conflict-ahead-eu-commission-and-cpc-set-sights-on-games-industry-1870db4b2004d7d284e1c833a28c1f38/)
- Industry groups Video Games Europe and EGDF call the principles "misinterpretations of EU consumer law." — [Games Market](https://www.gamesmarket.global/case-of-star-stable-online-conflict-ahead-eu-commission-and-cpc-set-sights-on-games-industry-1870db4b2004d7d284e1c833a28c1f38/)
- A CPC Network statement dated 30 September 2026 says it is following up on the principles. It is examining how virtual currencies are sold, how gamers' personal data is collected, and whether games use addictive design. — [IEU Monitoring, 2026-09-30 (search snippet only; page returned 403)](https://ieu-monitoring.com/?p=1251157)
- Digital Fairness Act: the Commission has said it will address addictive design. Consultation respondents strongly backed showing real-money prices for items bought with virtual currency and disclosing loot-box odds. As of a May 2026 article, no draft had been presented; other sources expected a proposal in Q3 or Q4 2026. EGDF objects to treating in-game currencies like crypto, and Video Games Europe warns of a de facto ban. — [Heuking, 2026-05-08](https://www.heuking.de/en/news-events/newsletter-articles/detail/digital-fairness-act-implementation-obligations-companies-need-to-prepare-for.html); [Mondaq](https://www.mondaq.com/gaming/1741258/digital-fairness-act-what-the-public-consultation-tells-the-video-game-industry); [EU Perspectives, Nov 2025](https://euperspectives.eu/2025/11/developers-push-back-the-digital-fairness-act/)

### Inferences
- **Fair versus exploitative, from the evidence above:**
  - Accepted: regeneration by time, hard caps, per-target cooldowns, cosmetics and permanent unlocks, cheap honest add-ons (Pocket God).
  - Contested: speed-ups and extra slots (Ikariam's 17th island slot, Grepolis instant-buy).
  - Hated or sanctioned: escalating timers or paywalls on progress (Dungeon Keeper), ad spam, pressure tactics aimed at children (Star Stable).
- **Escalating daily prices could attract scrutiny.** Grepolis's offering price rises with each purchase and resets at midnight. That throttles spending, but read against the CPC principles it could look like pressure if marketed with countdowns. This is my inference; no regulator has said so.

### Gaps
- I could not verify whether the Digital Fairness Act proposal was published between May and Nov 2026.
- I could not read the full text of the Sept 30, 2026 CPC follow-up (403).
- I found no regulator action aimed specifically at god-power purchases.

### Notable for Godling
- **Square-root regeneration with a hard cap.** Grepolis rations powers this way so that more income gives sub-linear power and banking is capped. It is a proven way to stop whales stacking interventions; a daily large-event slot is the same idea expressed as cadence.
- **Per-target cooldowns and long cooldowns on big miracles are accepted.** Examples are Lightning Bolt's same-city cooldown and Ikariam's 24-hour effect followed by a 7-day cooldown. Rationing by cooldown reads as fair; rationing by price escalation reads less so.
- **Price anchors from the evidence:**
  - Ikariam Ambrosia: €0.06–0.12 each, close to Godling's €0.05 credit.
  - Solar Smash single weapon: about €2.6.
  - Pixio "God Powers Tier 1 Pack": about €5.5.
  - Pocket God add-on: $0.99.

  Godling's €0.15 objects and ~€1.33 weather sit below these one-off unlock prices; a €25 daily event sits above any single item found.
- **Hold a zone where money cannot act.** Travian turns gold off in the World Wonder endgame. That is a public "money can't touch this" boundary, close in spirit to Godling's "can't buy decisions."
- **Players accept "comfort, not strength" framing.** It works only when it is true; Ikariam's extra island slot is where critics push back. Godling viewers buying conditions but never outcomes fits the accepted side.
- **Avoid the Dungeon Keeper and Star Stable patterns.** No escalating timers sold as skips, no countdown pressure, no appeals to minors. Show the euro price next to every credit price, which the EU consultation backs and Godling's fixed €0.05 rate makes easy.
- **Pocket God is the nearest analogue.** It had an island of little people, god interventions, weekly free content and cheap optional packs, and it reached 6M paid downloads before ending after 47 updates.
- **Watchability comes from emergence and shareable moments** (falling-sand galleries, Solar Smash destruction). Social "both sides benefit" mechanics, like GodFinger's visits that paid visitor and owner, are a precedent for viewer interventions that also reward the community.
