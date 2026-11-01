# Indirect-control classics: Majesty, Dungeon Keeper, From Dust, The Sims, Dwarf Fortress (plus SimEarth/Spore)

Scope note: Black & White and RimWorld are covered elsewhere and are left out here. All prices marked "Steam store API" were read from `store.steampowered.com/api/appdetails` on 2026-11-01 (US region). Sales figures are labelled with their source and date. Most are publisher or press claims, not audits. Where a figure came only from a search-result snippet and not from a page I opened, it is marked "(snippet)". Fan-wiki and fan-remake data is marked as such.

---

## 1. Majesty: The Fantasy Kingdom Sim (Cyberlore, 2000) and Majesty 2 (1C:Ino-Co, 2009): bounty flags, hero decisions, taxes, why indirect control

### Takeaway
In Majesty the player cannot command heroes. The only levers are building things and posting gold bounties. Bounties are paid up front, cannot be refunded, and heroes may ignore them. Heroes weigh a bounty through class personality: a per-class "Greed" multiplier, Loyalty, and fixed behaviour-cycle odds. Gold circulates from heroes to shops to tax collectors and back to the treasury. Majesty 2 added defend and fear ("stay away") flags, hero parties and persistent "lords". Critics said its heroes felt more robotic and the game more like a conventional RTS.

### Cited Findings
**Core control model**
- Units are autonomous and act on their own internal priorities. They cannot be commanded, only influenced by offering money, and cooperation is not guaranteed. — [Wikipedia: Majesty](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- Bounties cost gold up front. They can be raised or cancelled, but the gold cannot be taken back. — [Wikipedia: Majesty](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- The original Majesty has two flag types. Attack flags draw heroes to attack structures or units (even the player's own). Explore flags get an area explored or draw heroes to a map location. — [Majesty Wiki (fandom): Reward Flags](https://majesty.fandom.com/wiki/Reward_Flags)
- Each flag carries a bounty, and the first hero to reach it claims it. — Wikipedia-derived text in search results (snippet) via [Majesty Gold mirror](https://www.wikiwand.com/en/articles/Majesty_Gold)
- Tuning the reward is the core skill. Too high a reward sends every hero, whatever their level, rushing in, and many die. Too low and nobody leaves home. — [GamePressure retrospective (Maciej Bogusz)](https://www.gamepressure.com/newsroom/majesty-the-fantasy-kingdom-sim-is-the-game-of-my-childhood-its-u/z477d2)
- Marketing manager Jay Adan called reward flags one of the game's key innovations. He said a bounty could target a monster's destruction or its capture (rangers try to bring it back). — GameSpot Q&A (snippet) [GameSpot](https://www.gamespot.com/articles/majesty-legends-qanda/1100-6026166/)

**How heroes decide (class personality, greed, loyalty)**
- Each hero has a Greed stat from 1 to 26. When deciding whether to take a bounty, a hero multiplies its value by Greed/4 (rounded down). Greed also sets how far a hero will travel to steal and, with Willpower, how likely they are to use a Gambling Hall. — [Majesty Wiki: Attributes](https://majesty.fandom.com/wiki/Attributes) (fan-derived formula; I did not verify it against the game code)
- Loyalty decides how likely a hero is to steal from your buildings, shop at a rival's buildings, or answer another sovereign's attack flag. High-loyalty heroes wait at an Inn rather than leave the map when they become homeless. A Royal Garden adds +15 Loyalty to every hero and a Statue adds +5, and these stack. — [Majesty Wiki: Attributes](https://majesty.fandom.com/wiki/Attributes)
- Class stats (fan-wiki infoboxes):
  - Rogue: Greed 26, Loyalty 0, 275 gold to recruit.
  - Ranger: Greed 3, Loyalty 10, 350 gold.
  - Paladin: Greed 3, Loyalty 90, 1,000 gold (the most expensive hero).
  - Sources: [Rogue](https://majesty.fandom.com/wiki/Rogue), [Ranger](https://majesty.fandom.com/wiki/Ranger), [Paladin](https://majesty.fandom.com/wiki/Paladin).
- Heroes run a repeating behaviour cycle, and checking for interest in reward flags is one step in it. The Ranger's listed odds are Explore 95%, Train Magic Resistance 15%, Raid lair 15%, Raid enemy building 10%, Visit Inn 15%. The Rogue's include Loot gravestones 100% and Steal 95%. — [Majesty Wiki: Ranger](https://majesty.fandom.com/wiki/Ranger), [Rogue](https://majesty.fandom.com/wiki/Rogue)
- Rangers care most about explore flags and less about combat flags. When not fighting or chasing a flag, they:
  - defend their guild, the Palace and trading posts;
  - otherwise upgrade gear or train;
  - otherwise look for entertainment at elven buildings. Once inside one, no other behaviour fires until that cycle ends.
  - Source: [Majesty Wiki: Ranger](https://majesty.fandom.com/wiki/Ranger)
- The manual-derived text says a rogue's greed can be used to the player's advantage: rogues will scout the borders for a fraction of the bounty other heroes demand. — [Majesty Wiki: Rogue](https://majesty.fandom.com/wiki/Rogue)
- Class flavour:
  - Paladins prefer attacking dangerous monsters and raiding lairs.
  - Rogues steal.
  - Elves perform at inns.
  - Rogues are the first to try for rewards, followed by elves or dwarves.
  - Wizards are slow, fragile and expensive.
  - Source: [Wikipedia: Majesty](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)

**Hero needs, shopping, temples**
- Heroes earn gold from kills, rewards, destroyed dens and treasure chests. They pay tax to their home building when they return, then spend the rest on gear: enchantments up to +3, poison at an upgraded Rogues' Guild, healing potions and minor magic items. — [Wikipedia: Majesty](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- Guilds and temples house about four heroes each. Some temples exclude each other, and the player can host only one of elves, dwarves or gnomes. Service buildings are the blacksmith, marketplace, inn, fairgrounds, library and royal gardens. Houses, sewers and graveyards appear on their own as the town grows. — [Wikipedia: Majesty](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- Elves double the gold from the first income source but bring a gambling hall and an "elven lounge" that drain heroes' wealth. — [Wikipedia: Majesty](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)

**Taxes and the gold economy**
- Gold is the only resource. The marketplace has the highest automatic daily income of any building. — [Wikipedia: Majesty](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- Tax collectors are the main income source. Rules:
  - You get one collector per Palace level. Each set of 5 service buildings (fairgrounds, blacksmiths, gardens, marketplaces, inns) creates a Fountain, which adds one collector.
  - The player sets each collector's minimum pickup and minimum return thresholds. The default return is 250.
  - A collector who dies loses all the gold he was carrying.
  - Gold that heroes recover gets back to the treasury only at about 60–76%, because some is spent in shops and some becomes untaxable.
  - Source: [Majesty Wiki: Tax Collector](https://majesty.fandom.com/wiki/Tax_Collector)
- Buildings can be set to pickup, exempt or one-time pickup. The Rogues' Guild "Extort" ability collects all available gold but loses most of it. — [Wikipedia: Majesty](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- One retrospective describes the core loop as levelling heroes so that a steady flow of gold reaches the treasury. It notes that slow tax collectors get ambushed on the town's edge. — [GamePressure](https://www.gamepressure.com/newsroom/majesty-the-fantasy-kingdom-sim-is-the-game-of-my-childhood-its-u/z477d2)

**Why indirect control (designer)**
- Designer Jim DuBois traces the idea to watching a worker fish in *The Settlers*. He noticed he was giving simple-algorithm workers thoughts and personality in his head. He says the stories players tell themselves matter as much as the mechanics. He also cites heroes in *Warcraft II: Beyond the Dark Portal* and AD&D, a wish not to micromanage units, and the view that computers are good at automation. — [Genesis Temple interview, Damiano Gerli, 13 Nov 2019](https://genesistemple.com/interview-with-jim-dubois-on-pc-game-majesty)
- Development history: development passed through several publishers (Ripcord went under and Hasbro Interactive published). DuBois says each lost publisher made the game better. The final crunch was 16-hour days, 7 days a week. — [Genesis Temple](https://genesistemple.com/interview-with-jim-dubois-on-pc-game-majesty)

**Business and reception (Majesty 1)**
- Release: Windows, 21 March 2000 (NA), published by Hasbro Interactive under MicroProse. Later releases: Mac (Dec 2000), Linux (2003), mobile (2011–12). Expansion: *The Northern Expansion* (March 2001). Gold Edition: January 2002. *Majesty Gold HD* (Paradox): 21 March 2012. — [Wikipedia](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- Scores:
  - GameRankings (PC): 76.
  - Metacritic (iOS): 72.
  - Computer Gaming World: 4/5.
  - PC Gamer US: 82%.
  - PC Zone: 50.
  - Source: [Wikipedia](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- Computer Gaming World nominated it for Best Strategy Game of 2000 (it lost to *Sacrifice*) and gave it "Pleasant Surprise of the Year". — [Wikipedia](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- Paradox bought the IP in July 2007. Cyberlore's planned *Majesty Legends* was never released, reportedly for lack of a publisher. — [Wikipedia](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- Price now: Majesty Gold HD $9.99 on Steam. — [Steam store API, 2026-11-01](https://store.steampowered.com/app/25990/)

**Majesty 2 changes**
- Developer 1C:Ino-Co, publisher Paradox, released 18 Sept 2009, in 3D. Wikipedia calls the core gameplay "essentially the same". Heroes are semi-autonomous with class AI: hunters scout, warriors attack or defend. At launch there was no freestyle mode and no co-op. — [Wikipedia: Majesty 2](https://en.wikipedia.org/wiki/Majesty_2:_The_Fantasy_Kingdom_Sim)
- Gameplay changes:
  - Flags: Majesty 2 adds defend and "stay away" flags to attack and explore.
  - Parties of up to four heroes, so wizards die alone less often.
  - A lord system keeps some heroes between missions.
  - A lightning bolt can be cast anywhere cheaply, so enemies can be killed without heroes.
  - Only one marketplace is allowed, and temples and trading posts go only on preset sites.
  - Missions run 150+ game days, against about 35 in Majesty 1.
  - The reviewer found heroes "robots" that mill around the base without flags. That was safer but more boring, and made the game more like an RTS.
  - Price: $30.
  - Source: [GameBanshee review, Steven Carter, 16 Sept 2009](http://www.gamebanshee.com/a84)
- Fear-flag details from previews and guides (snippets): the fear flag keeps heroes out of an area. The level of hero it scares is said to scale with the gold attached. Reviewers and guides called it redundant or unnecessary. Parties are formed at Inns. Each mission allows one lord, and a Hall of Lords later allows two. — search snippets from [GameBanshee previews](https://gamebanshee.com/xxyq) and [AlteredGamer guide](https://www.alteredgamer.com/majesty-2/50461-majesty-2-strategy-guide) (not opened in full)
- Reception: Metacritic 72, GameRankings 75.85. Individual scores ranged from 50% to 88%. Expansions: Kingmaker (2010), Battles of Ardania (2010), Monster Kingdom (2011). — [Wikipedia: Majesty 2](https://en.wikipedia.org/wiki/Majesty_2:_The_Fantasy_Kingdom_Sim)

### Inferences
- Majesty's bounty works because it is a public, priced offer to autonomous agents. Each agent values it on its own terms: greed multiplier, loyalty, class appetite, and whatever its behaviour cycle is doing at the moment. The gold is sunk even when nobody bites, so the player pays for influence, never for an outcome.
- The economy closes the loop. Bounty gold goes to heroes, heroes spend it in the player's shops, and tax collectors bring it back. A well-tuned bounty is partly recovered, which takes the sting out of "wasted" offers.
- Majesty 2's lesson is that heroes need rich self-directed behaviour when no bounty is posted. If heroes idle without flags, the flag stops being a nudge and becomes the only way to make anything happen, and the indirect-control feel collapses.

### Gaps
- I found no sales figures for Majesty 1 or Majesty 2 from Cyberlore, Hasbro, Paradox or the press.
- I found no official post-mortem or GDC talk on how the bounty-evaluation AI was built. The Greed/4 formula comes from the fan wiki and was not verified against the game.
- The defend-flag and fear-flag mechanics come from previews and guides I saw only as snippets.

---

## 2. Dungeon Keeper (Bullfrog, 1997) and Dungeon Keeper 2 (1999): Hand of Evil, creature needs, anger, job choice, imps

### Takeaway
Dungeon Keeper mixes direct and indirect control. The Hand of Evil can pick up, drop and slap creatures, and imps carry out tiles the player flags for digging. Every other creature picks its own job from built-in preferences. Its loyalty depends on a running anger score fed by pay, food, sleep, slaps and its environment. Above a threshold it does "anger jobs" such as leaving, stealing or destroying rooms. Which creatures turn up depends on which rooms you build and how big they are. It sold about 700,000 copies by 2003 (book claim), and Molyneux called that a "missed opportunity".

### Cited Findings
**Player tools**
- The Hand of Evil picks up, carries and drops creatures and objects, and slaps them. A slap makes a creature work faster for a while but takes some of its health. The player must flag tiles for imps to dig. Rooms and traps can only go on owned tiles, and imps must build traps from blueprints. — [Wikipedia: Dungeon Keeper](https://en.wikipedia.org/wiki/Dungeon_Keeper)
- Artist Mark Healey proposed slapping creatures to speed them up. Co-designer Jonty Barnes later called it a great design decision. — [Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Keeper)
- Imps dig tunnels, claim rooms and portals, mine gold and gems, and set traps. More can be made with the Create Imp spell. — [Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Keeper)
- A Possession spell lets the player see and act through one creature in first person. — [Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Keeper)

**Recruitment through rooms (environment as invitation)**
- Which creatures arrive at the Portal depends on the rooms the player has and their sizes. Some creatures refuse some tasks, and some are natural enemies (flies and spiders, for example). — [Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Keeper)
- Example entry requirements (KeeperFX fan remake data, see caveat below):
  - Dragon: Treasure Room 25 tiles plus Lair 15.
  - Bile Demon: Hatchery 25 plus Lair 25.
  - Warlock: Library 9.
  - Troll: Workshop 1.
  - Dark Mistress: Torture Chamber 9.
  - Vampire: Graveyard 30 plus Lair 9.
  - Source: [KeeperFX creature configs (GitHub dkfans/keeperfx, config/creatrs/*.cfg)](https://github.com/dkfans/keeperfx/tree/master/config/creatrs)

**Needs: lair, food, payday, training**
- The basic rooms are a Lair (sleep), a Hatchery (grows chickens to eat) and a Treasury. Creatures are paid on a schedule and walk to the Treasure Room to collect wages. Training raises a creature's level, and its level star darkens as it takes damage. A Temple keeps creatures happy, and sacrifices there can bring a reward, a punishment or nothing. — [Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Keeper)
- Thought bubbles over a creature's head show what it is doing or feeling: hungry, going to its lair, angry, doing an anger job, training, praying, fleeing, and so on. — [Dungeon Keeper Wiki: Creature Thought Bubbles](https://dungeonkeeper.fandom.com/wiki/Creature_Thought_Bubbles)
- Happiness is shown as an Anger Bar in Query and Possess modes, and angry creatures are highlighted in the control panel. What causes anger:
  - not being paid, having no lair, or starving;
  - being held in the hand (Horned Reapers and Vampires);
  - being idle;
  - standing on a dead ally (standing on a dead enemy has the opposite effect).
- Remedies:
  - Praying in the Temple pleases most creatures but upsets Vampires.
  - In the original game, dropping any amount of gold on a creature instantly clears all its unhappiness. In KeeperFX the effect is gradual.
  - A Horned Reaper that has "gone psycho" can never be calmed down.
  - Source: [Dungeon Keeper Wiki: Happiness](https://dungeonkeeper.fandom.com/wiki/Happiness)

**Anger as a number (KeeperFX data)**
Caveat: KeeperFX is an open-source fan remake of DK1. Its default config values are meant to reproduce the original game, but I have not checked these numbers against the 1997 executable.
- Global rules:
  - Payday comes every 10,000 game turns.
  - Each treasury tile holds at most 2,000 gold, and a loose gold pile at most 1,024.
  - Selling a room refunds 50%.
  - A starving creature loses 50 HP every 400 turns, and each meal restores 50 HP.
  - Source: [KeeperFX rules.cfg](https://github.com/dkfans/keeperfx/blob/master/config/fxdata/rules.cfg)
- Dragon (Pay 350, AnnoyLevel 4,000):
  - Adds anger: missed salary +3,000; slap +600; being woken by alarm, Call to Arms or a slap +400; dropped on a job it won't do +100.
  - Adds anger per turn: no lair +4, no hatchery +3, sulking +4, queueing +10, seeing others leave +10, standing on a dead friend +10.
  - Reduces anger: eating −1,000, getting paid −1,000, winning a battle −500, standing on a dead enemy −14 per turn, praying −25 per turn, sleeping −10 per turn.
  - Anger jobs: LEAVE_DUNGEON, STEAL_GOLD.
  - Source: [KeeperFX dragon.cfg](https://github.com/dkfans/keeperfx/blob/master/config/creatrs/dragon.cfg)
- Wages and personalities differ widely between creatures:
  - Horned Reaper: Pay 950; missed salary +8,000; slap +3,750; +10 per turn while held; anger job MAD_PSYCHO.
  - Vampire: Pay 750; won't manufacture or pray; anger jobs KILL_CREATURES and PERSUADE; lair enemy: Warlock.
  - Dark Mistress: a slap *reduces* her anger by 400; anger jobs KILL_CREATURES and LEAVE.
  - Bile Demon: Pay 98; lair enemy: Skeleton.
  - Troll: primary job MANUFACTURE; won't research; anger jobs DESTROY_ROOMS and LEAVE.
  - Fly: Pay 5; primary job EXPLORE; lair enemy: Spider (and vice versa).
  - Imp: Pay 0, never angry, primary job DIG.
  - Source: [KeeperFX creature configs](https://github.com/dkfans/keeperfx/tree/master/config/creatrs)

**How creatures pick jobs**
- Each creature has PrimaryJobs it chooses for itself, and falls back to SecondaryJobs when no primary job is possible. NotDoJobs are refused even when the player drops the creature into that room (unless "Must Obey" is active), and the drop adds anger. StressfulJobs can be done but build anger over time.
- A creature "goes postal" when creatures that would not normally pick its primary job are assigned to it. It attacks them, forces them out of the room, and gains anger itself.
- The full list of anger jobs: kill creatures, destroy rooms, leave the dungeon, steal gold, damage walls, go "mad psycho", persuade others (raising their anger), and join the enemy.
- Source: [KeeperFX imp.cfg comments](https://github.com/dkfans/keeperfx/blob/master/config/creatrs/imp.cfg)

**Development and design statements**
- Peter Molyneux wrote the design, testbed, computer players and assistant. Lead programmer Simon Carter started in November 1994, and development took about 2.5 years. Late in development the team restarted much of the game because it felt too much like *Command & Conquer*. — [Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Keeper)
- Molyneux praised the creature navigation code and the digging-based play. He disliked the control panel because it reminded players they were playing a game, and that view shaped Black & White's interface-free design. — [Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Keeper)

**Business and reception**
- DK1 release: 26 or 27 June 1997 in North America (sources conflict) and 3 July 1997 in Europe. Free on Origin from October 2016. On GOG from 2011 and on Steam from 2024. — [Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Keeper). The Steam listing for "Dungeon Keeper Gold" shows 7 March 2024 at $4.99. — [Steam store API, 2026-11-01](https://store.steampowered.com/app/1996630/)
- DK1 sales claims:
  - 113,407 copies in the US in 1997 (PC Gamer US, April 1998).
  - A VUD "Gold" award for at least 100,000 units in Germany, Austria and Switzerland (VUD, 26 August 1998).
  - About 700,000 worldwide by 2003 (Adams & Rollings book, 2003).
  - Molyneux called it a "missed opportunity" next to *Theme Park*'s millions.
  - Source: [Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Keeper)
- DK1 reception:
  - GameRankings: 92%.
  - Scores: PC Gamer UK 95%, GameSpot 9/10, Edge 9/10, Next Generation 5/5.
  - Won the Interactive Achievement Award for PC Role-Playing Game of the Year.
  - Source: [Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Keeper)
- DK2: released 25 June 1999 in the UK. Designer Sean Cooper, producer Nick Goldsworthy.
  - Spells cost mana instead of gold.
  - The Training Room only trains up to level 4; higher levels need real combat or the new Combat Pit.
  - New rooms include the Casino.
  - Creatures rebel over missing food, unpaid wages or being slapped.
  - Edge called the AI extremely impressive.
  - "My Pet Dungeon" mode was added after testers played levels with no invaders.
  - Source: [Wikipedia: Dungeon Keeper 2](https://en.wikipedia.org/wiki/Dungeon_Keeper_2)
- In DK2, unhappy creatures sulk and angry ones head for the exit, or rebel and become heroes if they can't leave. The Mentor tells you why a creature is angry. — [Dungeon Keeper Wiki: Happiness](https://dungeonkeeper.fandom.com/wiki/Happiness)
- DK2 business: 70,685 US copies by April 2000 (PC Gamer, April 2000). GameRankings 82%. — [Wikipedia: Dungeon Keeper 2](https://en.wikipedia.org/wiki/Dungeon_Keeper_2)

### Inferences
- DK makes autonomy readable through three layers: an icon (thought bubble), a meter (anger bar), and a spoken explanation (DK2's Mentor saying why a creature is angry). The player always knows why a creature is misbehaving, even though they can't simply order it to stop.
- The rooms are smart objects too. The size of a room decides who shows up, and a creature's own job preferences decide who works where. Building is the main way the player influences creatures.
- Slapping is a paid shortcut: faster work in exchange for health and anger. Where an agent must keep its own will, giving the player a short-term speed-up at a visible cost is a pattern worth noting.
- Escalating anger jobs (sulk, then vandalise, then leave or defect) give the player a readable chance to fix problems before losing a creature.

### Gaps
- I did not verify that KeeperFX defaults match the 1997 game's data files exactly.
- I could not confirm how many game turns run per real second, so the real-time length of a payday is unknown.
- I found no official Bullfrog post-mortem on the creature AI. Molyneux's comments come via Wikipedia's sources.

---

## 3. From Dust (Ubisoft Montpellier, Éric Chahi, 2011): the Breath, autonomous tribe, terrain as guidance

### Takeaway
In From Dust the player is "the Breath". It sucks up and drops soil, water and lava to reshape a fast-flowing terrain simulation. The tribe walks its own routes to totems the player picks and builds villages there. Influence is purely environmental. Chahi said it only feels fair if the player can predict the villagers' route. Reviewers' top complaint was villager pathfinding (people getting stuck or taking the long way). It sold more than 500,000 copies by December 2011, Ubisoft's fastest-selling digital title at the time.

### Cited Findings
- **Powers and threats.** The player controls the Breath from a god-like first-person view, shaping matter in real time with a spherical cursor. Lava cools into rock, vegetation spreads once a village exists, and water erodes the land. Tribespeople learn songs from relics: "repel water" lets a village survive a tsunami. Story missions unlock powers such as jellifying water. Shamans warn shortly before tsunamis and eruptions. — [Wikipedia: From Dust](https://en.wikipedia.org/wiki/From_Dust)
- **Goal structure.** The player helps the tribe reach scattered totems and build a village beside each one. When every totem has a village, a portal opens to the next map. Challenge mode has 30 short levels with leaderboards. — [Wikipedia](https://en.wikipedia.org/wiki/From_Dust)
- **Chahi on indirect control.** The player only controls the obstacles on the terrain, and the team gave the player a lot of terrain power so they can react quickly when a villager's route changes. He said it would be very frustrating if players could not anticipate the plan. The hard cases are routes that change a lot, or a villager changing his mind because another way is faster. He added that the simulation has no special cases, and that its rules are very simple and tuned by trial and error. — [Game Developer interview, Brandon Sheffield, 10 Dec 2010](https://gamedeveloper.com/design/the-core-of-i-from-dust-i-)
- **Development.** Chahi pitched the game in 2006, and real development started in January 2008 with three people, growing to about 15–20. A villager life cycle and wildlife were cut for cost. It was marketed as a spiritual successor to *Populous*. — [Wikipedia](https://en.wikipedia.org/wiki/From_Dust)
- **Pathfinding criticism (bit-tech, 60/100, 27 July 2011).** The reviewer called pathfinding the game's most frustrating part: villagers stuck on small hills and dirt bridges, or taking the longest possible route. In one tidal-lake level they ignored the direct route to a totem about to flood. — [bit-tech review, David Hing](https://bit-tech.net/reviews/gaming/xbox/from-dust/2/)
- **Other reviewers (snippets).** Game Informer complained that players can't control which way villagers go. GameCritics noted that no level can be finished without the villagers' cooperation, so bad pathing is a major problem. — search snippets: [Game Informer](https://www.gameinformer.com/games/from_dust/b/xbox360/archive/2011/07/27/ubisoft’s-god-game-is-a-breath-of-fresh-air.aspx), [GameCritics](https://gamecritics.com/brad-gallaway/from-dust-review/)
- **PC criticism.** The PC version was criticised for a 30 FPS cap, no anti-aliasing, crashes, and always-online DRM (despite reports of one-time activation). Ubisoft promised an offline patch and offered refunds. Other critics complained there was no free sandbox mode. — [Wikipedia](https://en.wikipedia.org/wiki/From_Dust)
- **Business.** Release dates: XBLA 27 July 2011, PC 17 Aug 2011, PSN 13–14 Sept 2011. It sold more than 500,000 copies across platforms by December 2011 and beat Ubisoft's previous digital record by 45% (Ubisoft claims via Wikipedia). — [Wikipedia](https://en.wikipedia.org/wiki/From_Dust). Steam price is $14.99. — [Steam store API, 2026-11-01](https://store.steampowered.com/app/33460/)
- **Reception.** Metacritic (infobox): X360 80, PC 76, PS3 81. The article body lists the platforms in a different order, so the per-platform mapping is uncertain. Scores: Eurogamer 9/10, IGN 8.5, GameSpot 7.5, Destructoid 5.5. — [Wikipedia](https://en.wikipedia.org/wiki/From_Dust)

### Inferences
- Shaping the environment only reads as influence when the agent's response can be predicted. When villagers re-route on their own, the player's careful terrain work looks pointless. Showing the agent's intended path or goal would ease this.
- Shaman warnings before a disaster give the player a readable lead-up, a window in which to act. That is a good model for announcing large events.

### Gaps
- I did not open Chahi's full answer on totem and village design, and found no post-mortem specific to the villager AI.
- I found no sales data after 2011.

---

## 4. The Sims (Maxis, 2000): free will, motives, smart objects that advertise, indirect influence, watchability

### Takeaway
In The Sims, the objects hold the intelligence. Each object carries its own behaviours plus "advertisements" saying how much each behaviour will satisfy each need. A Sim not under direct control picks, from every advertised behaviour, the one that most raises its current happiness. Appeal is scaled by distance (attenuation) and personality. So the player shapes behaviour mostly by choosing and placing objects. Will Wright said the early AI was so good that player input usually made things worse, and the team made Sims less competent so the player had a role. The franchise has reportedly sold more than 200 million copies and made more than $5 billion.

### Cited Findings
**How autonomy works (primary source: Forbus & Wright course notes, version of 31 May 2001)**
- Each object has local data and a set of behaviours. Each behaviour has a procedure that runs it, a check for whether it is currently possible, and advertisements describing which Sim needs it satisfies. — [Forbus & Wright, "Some notes on programming objects in The Sims" (Northwestern QRG)](https://qrg.northwestern.edu/papers/Files/Programming_Objects_in_The_Sims.pdf)
- A Sim not under direct player control chooses from all possible behaviours in all objects the one that maximises its current happiness. The chosen behaviour's code, which belongs to the object, then runs in the Sim's own thread. Sims are just more elaborate objects. Social actions create an invisible "Social Interaction" object. — [Forbus & Wright](https://qrg.northwestern.edu/papers/Files/Programming_Objects_in_The_Sims.pdf)
- **Motives listed:** energy, comfort, hunger, hygiene, bladder, room, social, fun, mood. — [Forbus & Wright](https://qrg.northwestern.edu/papers/Files/Programming_Objects_in_The_Sims.pdf)
- **Advertisement parameters:**
  - A min–max strength per motive. Example: a toilet advertises Bladder in a 0–70 range.
  - Optional personality scaling. The aquarium's Feed Fish gives 1–11 Fun depending on the Playful trait, and traits come in opposite pairs such as nice/grouchy and active/lazy.
  - Attenuation (high, moderate, low, none or custom) sets how fast the appeal fades with distance.
  - "Available to" flags set who the interaction is offered to.
  - Source: [Forbus & Wright](https://qrg.northwestern.edu/papers/Files/Programming_Objects_in_The_Sims.pdf)
- **Design guidance in the same notes:**
  - Objects that give a benefit should also have a cost, and the most interesting costs are indirect, unintended side effects.
  - Their "Joy Booth" example advertises strongly for Social, Fun and Mood. Sims overuse it, socialise less, weaken their relationships and lose sleep. Early versions were so addictive that Sims used it until they collapsed.
  - Addictive objects are easy to make (high advertisement on one dimension). Balanced sets of objects that produce natural-looking variety are hard.
  - A suggested exercise is "skeptical Sims": record whether an object delivered what it advertised, and discount its future adverts.
  - Source: [Forbus & Wright](https://qrg.northwestern.edu/papers/Files/Programming_Objects_in_The_Sims.pdf)
- The developer tools had a Simulation Globals toggle for whether free will is on. — [Forbus & Wright](https://qrg.northwestern.edu/papers/Files/Programming_Objects_in_The_Sims.pdf)
- **In-game limits on autonomy.** Free will can be switched on in options, and the player can cancel autonomous actions in the queue. Sims still need direct commands for some things: paying bills, finding a job, exercising, conceiving children. Failure states include Sims leaving after conflict, children sent to military school, and neglected babies taken away. Families start with 20,000 simoleons. The base game has more than 150 objects in 8 categories. — [Wikipedia: The Sims](https://en.wikipedia.org/wiki/The_Sims_(video_game))
- **Origins.** Influences were Christopher Alexander's *A Pattern Language* and Scott McCloud's *Understanding Comics*. The game began as an architecture simulator where Sims mainly rated houses. A focus group disliked it, so it was built in the background as "Project X". Programmer Jamie Doornbos became lead programmer and built the open-ended behaviour system with Wright. — [Wikipedia](https://en.wikipedia.org/wiki/The_Sims_(video_game))
- **Wright at launch (Salon, 17 Feb 2000).** He kept the presentation abstract so players could fill in the story themselves, citing McCloud's idea that meaning forms in the gap between panels. He said the team was handing the god role to the player. He described objects that look innocent, like a new lamp, but carry new social mechanics (for example, a contagious disease). He said the shipped game was about 30% of the planned design. — [Salon, Daniel Sieberg](https://www.salon.com/2000/02/17/wright_5)
- **Wright on the AI being "too good" (NYT 25th-anniversary interview, Feb 2025, as reported).** He said "almost anything the player did was worse than the Sims running on autopilot". The team then deliberately made Sims less competent and added flaws and risks so players would have something to do. — [PC Gamer headline](https://www.pcgamer.com/games/the-sims/will-wright-says-the-original-sims-ai-was-actually-too-good-almost-anything-the-player-did-was-worse-than-the-sims-running-on-autopilot); [MeinMMO, 5 Feb 2025](https://mein-mmo.de/en/players-should-feel-like-gods-in-the-sims-but-played-like-ants-says-the-chef,1224288). I could not open the original NYT piece.
- **Later games.** The Sims 2 (2004) added wants and fears driven by aspiration and personality, with an aspiration meter. The Sims 3 (2009) added an open neighbourhood and "wishes" the player can accept or refuse. The Sims 4 went free-to-play on 18 Oct 2022. — [Wikipedia: The Sims (series)](https://en.wikipedia.org/wiki/The_Sims)

**Watchability and Let's Play culture**
- YouTube says Sims creators act as showrunners of their own sitcoms, playing with the game's unpredictability. It reported more than 18 million views of "100 baby challenge" videos in 2024. — [YouTube Culture & Trends blog](https://blog.youtube/culture-and-trends/the-sims/) (snippet; page not opened)
- Fan challenge formats such as Legacy and 100 Baby give viewers structured, serialised goals. — [Fanlore: List of The Sims Challenges](https://fanlore.org/wiki/List_of_The_Sims_Challenges) (snippet)
- EA, Turner and BuzzFeed made *The Sims Spark'd*, a TV competition for Sims content creators. It aired on TBS from 17 July 2020 with a $100,000 prize. — [Wikipedia: The Sims (series)](https://en.wikipedia.org/wiki/The_Sims)

**Business**
- Release: 4 Feb 2000 in North America (Windows).
  - Best-selling US computer game of 2000: 1.77 million units, $72.9 million (PC Gamer US, Apr 2001).
  - Another 1.48 million units and $60.4 million in 2001.
  - EA said it passed *Myst* as the best-selling PC game at 6.3 million copies (GameSpot, 22 Mar 2002).
  - The base game and expansions passed 41 million units (NBC News, 28 Sept 2004).
  - Source: [Wikipedia: The Sims](https://en.wikipedia.org/wiki/The_Sims_(video_game))
- The franchise has generated more than $5 billion in lifetime sales (EA CEO Andrew Wilson, Oct 2019 earnings call). — [PocketGamer.biz](https://www.pocketgamer.biz/news/71879/the-sims-surpasses-5-billion-in-lifetime-revenue/); [Wikipedia citing GamesIndustry.biz, 29 Oct 2019](https://en.wikipedia.org/wiki/The_Sims)
- The series has "reportedly" sold more than 200 million copies as of its 20th anniversary in 2020 (Guinness). The Strong Museum's 2016 Hall of Fame release also cited more than 200 million. — [Guinness World Records](https://www.guinnessworldrecords.com.br/world-records/682902-best-selling-social-simulation-videogame-series); [Wikipedia: The Sims (series)](https://en.wikipedia.org/wiki/The_Sims)
- Reception: Metacritic (PC) 92. Won Game of the Year at the D.I.C.E. (Interactive Achievement) Awards and the first Game Developers Choice Awards. Inducted into the World Video Game Hall of Fame in 2016. — [Wikipedia](https://en.wikipedia.org/wiki/The_Sims_(video_game))

### Inferences
- The "smart object" design moves decision-relevant knowledge into the world. Anyone who adds an object, including a viewer, adds new options and new appeal to the agent's choice set without touching the agent's decision rule. That is influence without control in its purest form.
- Wright's "too good" remark is a warning. If the autonomous agent already does well, interventions feel pointless or harmful. Interventions need real, visible needs to answer.
- The Joy Booth shows how an outside party can accidentally (or deliberately) create an addictive attractor. Some form of diminishing returns or "skepticism" stops one object from dominating behaviour.

### Gaps
- I could not open a primary source for the much-quoted line about dumb people and smart objects, or for the "pheromones" framing (the will-wright.com archive failed on an expired certificate). Treat that wording as unverified.
- I found no official GDC Vault talk transcript.
- The Sims 4 player counts (70M in 2023, 85M in 2024) appear only on aggregator sites, not in EA documents I could open.

---

## 5. Dwarf Fortress (Bay 12 Games): needs, moods, stress, strange moods, labour, world-gen and Legends, Steam release

### Takeaway
Dwarves are never commanded. The player marks jobs to be done, and dwarves with matching labours and skills do them. Each dwarf's state is one hidden stress number, fed only by the emotions shown on its thoughts screen. Past thresholds it has tantrums, depression and eventually insanity, which can spread through a fortress. Strange moods are rare, unpredictable artifact quests that demand materials and fail into insanity. World generation simulates centuries of history, which Legends mode shows. On Steam (6 Dec 2022, $29.99) it sold 160,000 copies in 24 hours, had more than $7.2 million in January 2023 revenue, and passed 1 million Steam copies by April 2025.

### Cited Findings
**Autonomy and labour**
- The player embarks with seven dwarves and doesn't control them directly. The player marks tasks and the dwarves perform them. Work quality depends on skill, which grows with practice. Attributes, preferences and desires are randomly generated. A manager dwarf can auto-assign jobs. — [Wikipedia: Dwarf Fortress](https://en.wikipedia.org/wiki/Dwarf_Fortress)

**Needs and stress**
- Dwarves need food and drink (mostly alcohol) and dislike water or the same drink every day. Things that upset them:
  - no private bedroom;
  - injuries, poor clothing, or losing pets, friends or family;
  - seeing corpses.
- Things that improve their lives: good bedrooms, a decorated dining room, medical care, varied drinks, cooked meals. Nobles make demands. — [Wikipedia](https://en.wikipedia.org/wiki/Dwarf_Fortress)
- Stress is a single hidden number from −1,000,000 to +1,000,000 (negative is good). Symptoms begin at +10,000, +25,000 and +50,000. In the short term these are tantrums, depression or "oblivious" wandering. In the long term they become insanity and the "Harrowed" state. Only two things change stress: the emotions a dwarf feels (all listed on its thoughts screen) and a drift back toward neutral. — [DF Wiki: Stress (DF2014)](https://dwarffortresswiki.org/index.php/DF2014:Stress)
- Three personality traits matter:
  - bravery: how fast stress builds;
  - stress vulnerability: how much stress a dwarf can take before breaking;
  - anxiety: how fast stress fades.
  - Source: [DF Wiki: Stress](https://dwarffortresswiki.org/index.php/DF2014:Stress)
- A wiki contributor's experiment (300 dwarves, 3 fortresses, 7 years) found:
  - 3x3 engraved bedrooms gave more than 99% of dwarves blissful sleep memories.
  - A 15x20 dining room gave 88% blissful meal memories.
  - 93% were satisfied at work.
  - Military training gave 93% happy long-term memories.
  - Source: [DF Wiki: Stress](https://dwarffortresswiki.org/index.php/DF2014:Stress) (community testing, not developer data)
- Constant stress leads to tantrums and insanity (berserk, suicidal, or stark raving mad). A tantrum that kills a well-liked dwarf can sour many others and spread through the fortress. — [Wikipedia](https://en.wikipedia.org/wiki/Dwarf_Fortress)

**Strange moods and artifacts**
- Once a fortress has at least 20 dwarves, a dwarf is sometimes struck by a strange mood. The game pauses and announces it. The dwarf:
  - claims a workshop matching its highest moodable skill;
  - gathers or demands specific materials, which the player can supply but can't specify;
  - makes an artifact;
  - usually gains 20,000 XP, which takes it to legendary skill.
- Limits on player control: a dwarf can have only one mood in its life, and the player can't choose who gets a mood, what kind it is, or which artifact results.
- How it fails: if the workshop is destroyed (or a magma forge loses power), or materials never arrive, the dwarf goes insane.
- Mood types are fey, secretive, possessed, fell and macabre. A "fell" dwarf murders the nearest dwarf and makes an artifact from the body.
- Source: [DF Wiki: Strange mood (DF2014)](https://dwarffortresswiki.org/index.php/DF2014:Strange_mood)
- The artifact is usually worth more than a starting fortress's entire wealth. — [Wikipedia](https://en.wikipedia.org/wiki/Dwarf_Fortress)

**World generation, Legends mode, stories**
- World generation runs procedural geography (elevation, rainfall, drainage, temperature, minerals, rivers traced from eroded mountains) and then simulates history for the chosen number of years. Civilisations, religions and wars spread while population and death counters climb. Worlds persist after a fortress is retired or lost. Legends mode browses figures, sites, civilisations and conflict maps, and can export history as XML. — [Wikipedia](https://en.wikipedia.org/wiki/Dwarf_Fortress)
- Strange moods also happen during world generation in a simplified form, creating the artifacts found across the world. — [DF Wiki: Strange mood](https://dwarffortresswiki.org/index.php/DF2014:Strange_mood)
- Tarn Adams calls the game an open-ended "story generator" and prefers modelling individual elements over whole systems. — [Wikipedia](https://en.wikipedia.org/wiki/Dwarf_Fortress)
- In "Boatmurdered" (2006), fans passed one fortress save from player to player until it fell. The saga spread widely and boosted the game's popularity. — [Wikipedia](https://en.wikipedia.org/wiki/Dwarf_Fortress)
- At GDC 2025, Adams compared dwarves to *Blade Runner* replicants, "more human than human". He said dwarves can show bigger emotions and make bigger mistakes, which lets players empathise with impulses they would judge harshly in real people. — [PC Gamer, Lincoln Carpenter](https://www.pcgamer.com/games/sim/dwarf-fortress-dwarves-are-more-human-than-human-creator-says-theyre-allowed-to-embody-bigger-emotions-theyre-allowed-to-make-bigger-mistakes-theyre-allowed-to-do-anything) (snippet; page not opened)
- Adams has given talks on emergent narrative (Progression Mechanics, Sept 2017; UCSC, Nov 2019, similar to his FDG 2019 talk). He also wrote the chapter "Emergent Narrative in Dwarf Fortress" in *Procedural Storytelling in Game Design*. — [Bay 12 links page](https://bay12games.com/dwarves/links.html) (snippet); [Routledge](https://www.routledge.com/Procedural-Storytelling-in-Game-Design-1st-Edition/Short-Adams/p/book/9781138595309)
- Adams (2017): Adventure mode was the original plan. Fortress mode is "the only one that's a game", where the player feels their impact quickly. — [Game Developer, Alex Wawro, 20 Mar 2017](https://gamedeveloper.com/design/-i-dwarf-fortress-i-dev-it-s-kind-of-funny-we-never-achieved-our-original-goals-)

**Business**
- Before Steam: Adams added a PayPal button around 2006. The first 5 months brought about $300, then roughly $800–1,000 a month after the 2006 alpha. Patreon started in 2015. In 2011 he turned down a $300,000 licensing deal. — [Wikipedia](https://en.wikipedia.org/wiki/Dwarf_Fortress)
- Steam/itch edition (Kitfox Games as publisher):
  - Released 6 Dec 2022.
  - Kitfox's economist forecast about 160,000 units in two months, which was beaten on day one.
  - Sales claims: 160,000 in 24 hours; 300,000 in the first week; more than 500,000 by end of 2022; more than 600,000 by March 2023; more than 800,000 in the first year; more than 1 million on Steam by April 2025.
  - It was the best-selling title on Steam at launch.
  - Source: [Wikipedia](https://en.wikipedia.org/wiki/Dwarf_Fortress); 1 million claim also reported by [heise](https://heise.de/-10355215) (snippet)
- Tarn Adams reported January 2023 revenue of $7,230,123.58 on the Bay 12 forums, against $15,635 in December 2022. He said a little less than half would go to taxes. — [Game World Observer, 2 Feb 2023](https://gameworldobserver.com/2023/02/02/dwarf-fortress-revenue-7-million-january-bay-12-games) (snippet); [PC Gamer](https://pcgamer.com/dwarf-fortress-releases-sales-figures-since-steam-release-showing-46000-increase-in-earnings) (snippet). Wikipedia rounds the gap to "over 400 times" monthly pre-Steam income. — [Wikipedia](https://en.wikipedia.org/wiki/Dwarf_Fortress)
- Price: $29.99. — [Steam store API, 2026-11-01](https://store.steampowered.com/app/975370/)
- Reception and honours:
  - Metacritic: 93 (12 reviews).
  - IGN: 10/10.
  - Won Strategy/Simulation Game of the Year at D.I.C.E. 2023.
  - MoMA added it to its collection in March 2012 and archives each update.
  - Source: [Wikipedia](https://en.wikipedia.org/wiki/Dwarf_Fortress)

### Inferences
- DF makes a black-box agent readable by showing its *reasons* (the thought list), not its internal number. Every cause of stress is a named, viewable thought.
- A strange mood is a good template for an agent-driven "event". It is rare, announced and pausing, and it creates a clear demand that outsiders can help meet but can't direct. It ends in a lasting artifact or a dramatic failure.
- Legends mode and persistent worlds turn long simulations into history that can be retold. Players tell stories because the game keeps a record of causes and consequences, and because dwarves fail dramatically.

### Gaps
- I couldn't open Tarn Adams's original forum revenue post, the PC Gamer GDC 2025 interview, or his emergent-narrative talks in full.
- I found no first-party Steam revenue number beyond January 2023.

---

## 6. SimEarth (1990) and Spore (2008), briefly: condition-setting versus agent control

### Takeaway
SimEarth is the purest "change conditions, not decisions" game. The player tunes atmosphere, drift, mutation rates and disasters, life evolves on its own, and every action costs from a budget. Spore shows the risk of pulling the other way: the player became the "intelligent designer", and critics found each stage shallow.

### Cited Findings
- **SimEarth player controls.** Designers were Will Wright and Fred Haslam, with James Lovelock advising and writing the manual introduction (the game models his Gaia hypothesis). The player sets atmospheric gases (to three decimals), continental drift and life's reproduction and mutation rates. The player can place devices such as oxygen generators and terraformers, and trigger disasters. — [Wikipedia: SimEarth](https://en.wikipedia.org/wiki/SimEarth)
- **What evolves on its own.** Life evolves autonomously, species thrive or die out, sapient species climb from the Stone Age to the Nanotech Age, and they may leave the planet in an "Exodus". — [Wikipedia: SimEarth](https://en.wikipedia.org/wiki/SimEarth)
- **Energy budget.** Every action costs energy units: 50 for a terrain square, 500 for a terraforming device. The budget scales with planet development and difficulty. — [Wikipedia: SimEarth](https://en.wikipedia.org/wiki/SimEarth)
- **SimEarth reception.** It won 1991 SPA awards for Best Simulation and Best Secondary Education Program. — [Wikipedia: SimEarth](https://en.wikipedia.org/wiki/SimEarth)
- **Spore sales and reception.**
  - EA said it sold 2 million copies in its first three weeks (Sept 2008).
  - Metacritic: 84 (PC).
  - Critics found individual stages too simple.
  - SecuROM DRM triggered a wave of one-star Amazon ratings (2,016 of 2,216 by 14 Sept 2008) and a class action.
  - Players had made more than 100 million creations by May 2009 (Wired).
  - Source: [Wikipedia: Spore](https://en.wikipedia.org/wiki/Spore_(2008_video_game))
- **Wright on Spore.** He said the team aimed at casual players. Early prototypes driven by mutation lacked emotional engagement, so the player was cast as an "intelligent designer". — [Wikipedia: Spore](https://en.wikipedia.org/wiki/Spore_(2008_video_game))

### Inferences
- SimEarth's priced, tiered intervention budget is a direct precedent for selling *conditions* at different price points while the simulated life stays autonomous.

### Gaps
- I found no SimEarth sales figures, and no statement from Wright on whether SimEarth was fun.

---

## 7. Across all: how indirect control was made satisfying and legible, and how interventions visibly mattered

### Takeaway
Across these games, indirect control satisfies when four things hold:
1. The agent's reasons are visible: thought bubbles, anger bars, thought lists, Mentor lines.
2. The player's lever is a priced, public *offer* or *environmental change* that the agent evaluates on its own terms: bounties, advertised objects, room sizes, terrain.
3. The agent is imperfect enough that interventions are needed. Wright made Sims dumber.
4. Responses can be predicted. From Dust's pathing shows the cost of failing at this.

### Cited Findings
- **Public priced offers.** Majesty's influence is a priced public offer that may be refused, and the money is gone either way. — [Wikipedia: Majesty](https://en.wikipedia.org/wiki/Majesty:_The_Fantasy_Kingdom_Sim)
- **Personality-weighted valuation.** Heroes' Greed and Loyalty decide how they value it. — [Majesty Wiki: Attributes](https://majesty.fandom.com/wiki/Attributes)
- **Objects that advertise.** Sims objects advertise motive payoffs with distance attenuation and personality scaling, and Sims pick the happiness-maximising option. — [Forbus & Wright](https://qrg.northwestern.edu/papers/Files/Programming_Objects_in_The_Sims.pdf)
- **Visible state.** DK shows a creature's needs and anger with thought bubbles and anger bars, and DK2's Mentor says why a creature is angry. — [DK Wiki: Thought Bubbles](https://dungeonkeeper.fandom.com/wiki/Creature_Thought_Bubbles); [DK Wiki: Happiness](https://dungeonkeeper.fandom.com/wiki/Happiness)
- **Readable causes.** DF's stress comes only from emotions listed on each dwarf's thoughts screen. — [DF Wiki: Stress](https://dwarffortresswiki.org/index.php/DF2014:Stress)
- **Predictability.** Chahi: if the player can't anticipate the plan, it's frustrating, and the player only controls obstacles. — [Game Developer, 2010](https://gamedeveloper.com/design/the-core-of-i-from-dust-i-)
- **Imperfection by design.** Wright: early Sims on autopilot beat the player, so they were made less competent. — [MeinMMO on NYT, 2025](https://mein-mmo.de/en/players-should-feel-like-gods-in-the-sims-but-played-like-ants-says-the-chef,1224288)
- **Stories in the player's head.** DuBois: the stories players tell themselves about simple agents are as important as the mechanics. — [Genesis Temple, 2019](https://genesistemple.com/interview-with-jim-dubois-on-pc-game-majesty). Wright: abstraction lets players fill in the story. — [Salon, 2000](https://www.salon.com/2000/02/17/wright_5)
- **Self-directed life.** Majesty 2's heroes idle without flags, which critics called robotic and less charming than the original. — [GameBanshee, 2009](http://www.gamebanshee.com/a84)

### Inferences

#### Notable for Godling
- **Viewer credits as Majesty bounties.** A paid offer, posted publicly, that the agent may ignore, with credits spent either way. Godling's choice can be weighted by its own traits (a "greed" for novelty or materials) and by how far away the offer is.
- **Spawned objects as Sims "smart objects".** Each viewer-spawned object could carry a machine-readable advertisement: what it offers, which needs it serves, how strong, how fast the appeal fades with distance. That would go into the LLM agent's observation, and the agent's decision rule stays untouched. This is influence without control.
- **Guard against the Joy Booth.** One overpowered object can capture the agent. Use diminishing returns, or Forbus and Wright's "skeptical Sims" idea: remember whether an object delivered what it advertised and discount it next time.
- **Don't make the agent too competent (Wright).** If Godling never lacks anything, viewer interventions feel pointless. Real unmet needs (shortages, weather, tired tools) give credits something to answer.
- **Show reasons, not just actions (DK and DF).** Thought bubbles or captions, a mood or stress readout, and a log of which viewer-caused event changed its plan. DK2's Mentor explaining why a creature is angry is the model for a narrator line.
- **Predictability for environment changes (From Dust).** When viewers change terrain or weather, show Godling's current goal or path so viewers can predict how their change will land. Unexplained re-routing reads as the intervention being ignored.
- **Strange-mood-style agent events (DF).** Rare, announced moments where Godling fixes on a project and needs specific materials. Viewers can supply materials but not direct the project. The result is a lasting monument or a visible failure.
- **Pricing tiers (SimEarth).** SimEarth's energy costs (50 for a terrain square, 500 for a terraformer) are a precedent for tiered credit prices on conditions of different size.
- **A Legends-mode chronicle.** A persistent, browsable history of builds, disasters and who caused what turns a 24/7 stream into retellable stories. That suits the clip and Let's Play culture that made The Sims and DF so watchable.
- **Self-directed life between offers (Majesty 2's failure).** Godling must look busy and purposeful with no viewer input, or offers start to feel like the only thing that makes it act.

### Gaps
- I found no single post-mortem from any of these teams that systematically covers "legibility of indirect control". The points above are put together from interviews, wikis and reviews.
