# Godling Master Plan v2.2 — Critical Review

Reviewed 2026-10-31 against: the plan PDF (42 pages), the Clawblox source at `8be90a0` (`v0.1.5-2`, your local checkout), the Machine Playing paper (arXiv 2610.07130 v1), and current public pricing and docs. Anything marked *derived* is my own arithmetic, not a published figure.

---

## 0. Verdict in seven lines

1. **The engineering hygiene is excellent, but the plan aims it at the wrong risk first.** The biggest unknown isn't whether the agent moves smoothly at 1x. It's whether anyone keeps watching an AI stack blocks for days. Real users only arrive at P9, phase 13 of 15.
2. **The speed problem has a known cause, and it isn't mainly the LLM.** Clawblox's "agent" is a full coding-agent CLI (Claude Code, Codex or Kimi Code) that sends `curl` commands from a bash tool, prodded by a "please don't stop" hook. Every action is a whole agent turn. The fix is a direct API loop plus a Skill Executor (arm B). Jev (arm C) is a side bet, not the core of P1.
3. **24/7 persistence is unproven, and the paper suggests it's hard.** Its runs reset the session and restore the island every hour, partly because agents fall into idle loops after a few hours. Your core promise is one world and one agent running for days. Test that first.
4. **The plan's own capacity caps put a ceiling on revenue.** At 100% utilisation, 24/7, the price list and slot limits gross roughly €17k/month (*derived*). At a realistic 5–25% it's €0.8–4k. That only works with Flash-class models (~€200–400/month); an Opus-class agent costs more than the likely revenue.
5. **Upstream already ships about a third of what the roadmap plans to build:** snapshot+delta spectator WebSocket, recording, replay with agent timeline, resume, checkpoints, a SQLite datastore and vision capture. Re-scope P2/P3 to "extend", not "build".
6. **The process is too heavy for a part-time solo project.** It has 15 gates, ~70 test IDs, 4 workspaces and ADRs, but no time estimates. Upstream already has 398 tests; run them instead of re-specifying PHY-01..10.
7. **Fix the factual errors before relying on the plan.** The Jev source link points to an unaffiliated wrapper. Two competitor links are dead. Physics runs at 60 Hz, not 30. `--agent` needs tmux, so it doesn't run on native Windows. `godling.world` looks unregistered.

*Measured on 2026-10-31 (§1b):* the unchanged upstream agent on Opus managed 180 actions/h, with a p95 gap between actions of 39.8 s (G5 wants ≤ 2 s). The character was moving 4% of the time, and it cost about $24/h. It still built a 4-block tower in 16 minutes.

---

## 1. What I verified

| Plan claim | Finding | Status |
|---|---|---|
| Clawblox: headless Rust/Rapier, Luau, Three.js, `run --agent codex`, `--resume` | All true in the README and code. MIT license (added 2026-08-20). v0.1.5. | ✅ |
| Clawblox maturity (implied stable base) | 71 stars, 11 forks, **596 of 604 commits by one author** (nacloos). 66k lines of Rust in `src/`, 398 tests. Research code (MIT / US Air Force AI Accelerator sponsorship). Last commit 2026-10-07. | ⚠️ bus factor = 1 |
| Native memory files SOUL.md / SEMANTIC_MEMORY.md / EPISODIC_MEMORY | Confirmed in `DEFAULT_SYSTEM_PROMPT` ([agent_runner.rs:26](../clawblox/src/agent_runner.rs)) and `docs/agents.md`. Episodic entries go to `EPISODIC_MEMORY.jsonl`, append-only. | ✅ |
| Mesa Island actions MoveTo/Jump/Stop/Pickup/Place/Throw | Confirmed in `worlds/mesa-island/API.md`. Also `/observe/image` (vision), `/chat`, `/reset`. | ✅ |
| Towers can collapse (plan §12 demo) | Yes. `Place` anchors the block for a 0.3 s animation, then sets `Anchored=false, CanCollide=true`, so placed blocks are real physics bodies. | ✅ |
| Weld/attachment API (PHY-08) | The engine has `tests/weld_stability_test.rs` and `construction_assembly_regression_test.rs`, but Mesa Island exposes no weld action to the agent. | ⚠️ engine yes, world no |
| Physics target "30 Hz; 60 Hz later" | The engine is **fixed 60 Hz** (`game/constants.rs`); the paper measures about 62 ticks/s. 30 Hz would be a downgrade. | ❌ fix plan |
| Machine Playing paper, arXiv 2610.07130 | Exists. 13 Claude Code + Opus 4.7 agents × 30 wall-clock hours, plus Codex/GPT-5.5 and Kimi Code/K2.6 (5 each) and Sonnet/Haiku (13 × 10 h). Total API cost about **$8,000** across all runs (from a summary of the paper, less reliable than a direct quote). | ✅ |
| "8x/16x/32x videos imply slow 1x" | The paper doesn't state this. Its replay tool has variable speed and **idle skipping**, and it says agents sometimes do nothing and fall into idle loops after a few hours. The premise holds qualitatively; there are no numbers. | ⚠️ unmeasured |
| Jev 1.14 | Real: TypeSafe AI decision model, released 2026-10-14. **But** the plan's link (thejevai.com) is an *unaffiliated third-party wrapper*. TypeSafe **paused new signups on 2026-09-22**; it's reachable via OpenRouter, Vercel AI Gateway or Inworld. Closed weights. About $0.042/M input tokens, output free, roughly 100 ms typical (vendor figure, no p95). Images and long context are vendor-labelled "danger zone" (not production-ready). It returns Choice/Score/Boolean judgements only and takes no actions. | ⚠️ fix source; downgrade role |
| DeepSeek V4.1 Flash / MiniMax M3.1 Flash as cheap candidates | Both real. DeepSeek: $0.15/$0.60 per M off-peak, $0.30/$1.20 peak, cache hits ~$0.003/M. MiniMax M3.1 Flash: $0.15/$0.60, cached $0.015/M (open weights). | ✅ |
| Kimi K3.1 Pro | Not found. Kimi K3 exists (~$3/$15 per M), and Clawblox already ships a Kimi K3 config (commit `3a7a847`). | ❌ |
| Hindsight (MIT), Cognee (Apache-2.0), Memgraph (license TBD) | Hindsight: MIT, 57k stars. Cognee: Apache-2.0, 33k stars. Memgraph: `NOASSERTION` on GitHub (BSL-style). I did not verify Cognee's operation names. | ✅ |
| Agent_Memory_Techniques | Real, Apache-2.0, 30 notebooks. A teaching resource, not a benchmark harness. | ✅ |
| Competitors | **5imulites.live: domain doesn't resolve.** Blerp page: HTTP 403. thejevai: see Jev row. **Closest real analogs:** ARK (autonomous LLM agents in a 3D voxel world; paid **Solana token** transactions trigger events; no visible traction), Nixi (AI VTuber in Minecraft; *free* chat commands with cooldowns), AI Plays Games (paid prompts from $3), Nodus (TikTok gifts → meteors/tornadoes in Minecraft, $9.99/mo for the streamer, no AI). | ⚠️ update list |
| Domain godling.world "selected" | No DNS records, and RDAP returns 404, so it **appears unregistered**. | ⚠️ register now |
| 4 vCPU / 8 GB starting server | Hetzner CX33 is about €8.49–8.99/mo after the June 2026 price rise, may be unavailable for new orders, and includes 20 TB traffic. CPX32 is about €35.49/mo. Vision capture runs **headless Chromium + SwiftShader software WebGL** on the server (`src/capture.rs`). CPU-only works, but that's the CPU hog to measure. | ✅ cheap either way |
| Replay storage 2.6 GB/day | The arithmetic is right (1 KB × 30/s), but upstream sends dirty-tracked deltas, so a quiet world is far below that. Even 78 GB/month costs about €1–2 on object storage. | ✅ but a non-issue |

---

## 1b. First measurement: baseline run a-003 (2026-10-31)

**Setup:**
- Mesa Island, one Claude Code agent on `claude-opus-4-6` (upstream's default), sandboxed.
- Upstream's default system prompt, rendered.
- Patch BUG-001 applied (`patches/BUG-001-cli-sandbox.md`).
- Stopped after **16.6 minutes** because of token use.
- Report: `~/godling-runs/a-003/analysis/report.md`, produced by `tools/analyze_run.py`.

| Metric | Measured | Plan's G5 target | Gap |
|---|---|---|---|
| World actions | 50 in 16.6 min (**180/h**) | — | — |
| Gap between consecutive actions | p50 **14.4 s**, p95 **39.8 s**, max 106 s | p95 ≤ 2 s | **20×** |
| Gaps ≤ 2 s | **2%** | most | — |
| Motion duty cycle (character moving) | **4%** | "watchable at 1x" | — |
| Time to first action | 83 s (reads/writes its memory first) | — | — |
| Cost | **$7.19 → $24/h → ~$17.4k/month** 24/7 | $400–800/month band | **22–44×** |
| Avg context per model call | 85k tokens, 96% cache hits | — | — |

Where the 16.6 minutes went (approximate, overlapping):
- **About 45% waiting for the model.** 105 calls, about 2 per world action, median 3.8 s each, 447 s in total.
- **About 20% deliberate `sleep` commands the agent wrote** to wait for a MoveTo to finish. That's 33 sleeps, 196 s in total. The API has no "arrived" event.
- **The rest:** shell and tool execution, and memory upkeep (24% of all tool calls were workspace/memory edits).

Cost breakdown: cache reads are 60% of the bill and cache writes 28%. The output text itself is only 12%. **The cost comes from the coding-agent harness re-reading an 85k-token context about 6 times a minute, not from the model "thinking".**

What it did:
1. Explored, then learned the block mechanics and wrote them to `SEMANTIC_MEMORY.md`.
2. Built a **3-block tower at ~12 min and a 4-block tower at ~16 min**.
3. Was carrying a 5th block when the world stopped.

That works out to about **$1.80 per tower block** on Opus.

Action outcomes: Place succeeded at least 10 of 14 times; Pickup at least 6–8 of 13. Failures were `Occupied`, `OutOfRange`, `NoBlock` and `AlreadyHolding`, all coordinate or state slips that a Skill Executor with pre-checks would catch.

**Memory was already unreliable within 17 minutes:**
- It recorded the pickup/place range as "~3 units", while the code says 6 and 7.
- Its episodic timestamps mix UTC and local time (`22:43Z`, then `21:50Z`).
- The ticks it recorded are consistent, which supports the plan's rule that memory entries should cite `world_tick` and event IDs rather than agent-written times.

**Flash-model projection for the same token profile** (an assumption: a different model will behave differently):

| Model | $/hour | $/month 24/7 |
|---|---|---|
| Claude Opus 4.6 (measured) | 24.23 | ~17,450 |
| MiniMax M3.1 Flash ($0.15 in, $0.015 cached, $0.60 out) | ~0.67 | ~480 |
| DeepSeek V4.1 Flash off-peak / peak ($0.15 / $0.003 cached / $0.60) | ~0.32 / ~0.65 | ~235 / ~470 |

**What this means for P1:**
- Arm A is now measured.
- Even with an instant model, roughly 20% of time would still be agent-written sleeps, and every action would still need about 2 full-context harness calls.
- That points straight at arm B: an executor that chains MoveTo → wait-for-arrival → Pickup → Place without asking the LLM in between, plus a cheap model. Jev can't fix either problem.
- Next, cheapest experiment: the same run with a Flash model via `ANTHROPIC_BASE_URL`. That still needs verifying inside the sandbox.

---

## 1c. Overnight run a-004: DeepSeek Flash, 8.4 hours (2026-10-31 → 11-01)

**Setup:**
- Same as a-003, but `deepseek-flash` through Claude Code (`~/.claude-deepseek`).
- **Vision started working mid-run.** The libraries were installed during the run, and the first image reached the model at 23:18 UTC, about 0.75 h in.
- The Ctrl+C fix (BUG-005) was validated: a clean stop in 6 s with nothing left behind.

| Whole night | Value |
|---|---|
| World actions | 5,449 (645/h), but **96% MoveTo/Stop**; Place 60, Pickup 56 |
| Gaps | p50 0.3 s, p95 16.4 s, **81% ≤ 2 s** (would pass G5); longest idle 17 min |
| Character moving | 8% |
| Tallest stack | 1 after the first minutes (3 at start was the world's initial pile) |
| Model calls | 4,163 (489/h); 323 auto-continues; **44 automatic context compactions** (about every 20–25 min) |
| Context per call | ~90–109k tokens and rising |
| Memory text | ~450 KB (semantic 82 KB, episodic 152 KB, journal 99 KB, camera log 42 KB …); 34 self-written tools |
| Images the model saw | 179 (after vision started working) |
| Cost | **$2.80 for 8.4 h = $0.33/h**, about $240/month 24/7 |

| Hour | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| Actions | 836 | 587 | 382 | 192 | 662 | 236 | 573 | 1,326 | 655 |
| **Blocks placed** | **47** | 7 | 3 | 0 | 0 | 2 | 0 | 0 | 1 |
| Images seen | 24 | 34 | 26 | 25 | 22 | 23 | 17 | 5 | 3 |

**Three phases, from its own log and chat:**
1. **Builder of landmarks (0–0.7 h).** Ring with a five-stone arc on the great mesa, rock on the Peak, a stone on the Spire, three stones in a line on the east ridge, a rebuilt Gate. It posted an "island guide" in chat.
2. **Photographer and cartographer (0.75–2 h, right after vision started working).** 360° panoramas, `map.svg`, contact sheets, an atlas, skyline captions with a self-written font renderer.
3. **Instrument scientist (2–8.4 h).** It studied an offset in its own first-person camera after 180° turns, running hundreds of identical walk-and-stop trials near spawn (one target 552 times). Chat notes like *"The camera desync is a cliff at the exact 180."* Building stopped completely.

It also lost material through its own movements: it shoved the rock off the Peak (2.2 h) and a fragment off a summit (5.9 h).

**What this means:**
- **Good: no idle collapse.** It stayed busy and self-directed for 8.4 h without resets, better than the worst case the paper's hourly resets imply. Its 16 chat messages are honest, self-correcting field notes that read like a Chronicle, so the narration material exists.
- **Bad for the product: its interests drifted from visible creation to invisible meta-science within ~2 h.** Activity metrics looked excellent (G5-level gaps, 645 actions/h) while viewer-meaningful activity fell from 47 placements/hour to 0. **G5 is necessary but not sufficient.** Add "visible change" metrics: blocks moved or placed per hour, new structures, stack height, time spent away from one spot.
- **Vision cuts both ways.** It gave the agent a new thing to study (the camera itself) that pulled it away from the world. Confound: vision arrived mid-run.
- **The world is too small.** Building material and space were exhausted in about 45 minutes, and losses are permanent. That supports viewer interventions and stimuli as a core mechanic, not a revenue add-on.
- **Memory and context keep growing.** 44 compactions and ~100k-token contexts mean the coding-agent harness keeps costing more over time. That's another argument for the layered design's compact mind context.
- **A possible upstream renderer issue,** reported by the agent and **not verified by me:** the first-person capture's yaw stays offset by whole rotation steps after a 180° turn.

**Design implication** (see `research/layered-mind-design.md`): the mind layer's projects should have **visible outcomes**, and attention should score "is what I'm doing visible and changing the world?". That's a value written into Godling's own persona, not viewer control, so it stays within the plan's autonomy principle.

---

## 2. Findings that should change the plan, ranked

### 2.1 Treat P1 as a harness replacement; Jev is a side bet

How the upstream agent actually works (`agent_runner.rs`, `agent.rs`):
- Clawblox starts **Claude Code / Codex / Kimi Code inside tmux** with `--permission-mode bypassPermissions`.
- The agent fetches `API.md` with curl, then acts through bash `curl` calls to `/input` and `/observe`.
- A stop hook auto-sends "Please don't stop. Just continue doing whatever you want to do."
- The default model for the claude agent is `claude-opus-4-6`.

So each world action costs a full coding-agent turn: reasoning, then a tool call, then reading the JSON. That's where 1x looks slow. A small decision model can't fix a slow harness.

**Recommendation:**
- **Arm B is the real experiment.** Build a ~300-line direct API loop: the LLM emits a *plan* of N typed sub-actions, and an executor runs them back to back against `/input`, polling `LastActionResult`.
- **Re-implement native memory in arm B.** It must read and write the same SOUL/SEMANTIC/EPISODIC files, or A vs B mixes up harness, memory and prompt. The plan's experiment design misses this confound.
- **Make arm C (Jev) conditional.** Run it only if B's traces show remaining gaps caused by tactical-choice latency. A Flash LLM with structured output answers "which of these 5 sub-actions" in about 0.5–1.5 s anyway. Jev's best fit here is *gating*: "Should Godling react to this new event now?" (Boolean), at ~100 ms and almost no cost.
- **Don't make a 17-day-old model, with signups paused at the vendor, part of a blocking gate.**
- **Fix the internal contradiction.** §17 costs assume one LLM call per 30 s; G5 wants under 2 s of avoidable idle. These only fit together if the executor runs multi-step plans. Write that down explicitly: LLM calls/hour = f(average plan length).

### 2.2 Make long-run watchability the first gate

Evidence:
- The paper resets each session and restores the island every hour.
- Agents drift into idle loops after a few hours.
- Memory files grow roughly linearly and agents rarely delete anything.
- A recorded false belief persists and harms later behaviour (agent 7's "towers should be thrown").
- Codex agents spent more time in their workspace than in the world.

Your product is the opposite setup: no resets, one world, days long.

**Recommendation:** right after the baseline, run a **72 h soak**. Use a Flash model through the *unchanged* upstream harness (see 2.6 for how to do this without code changes). Measure:
- Actions per hour, by hour.
- Novelty: distinct activity types per 6 h.
- Idle-loop episodes.
- Memory-file token size over time.
- Cost per hour.

Then compare a second run with a **diegetic day/night cycle**: Godling "sleeps", the session resets, memory is consolidated, and it wakes up. That turns the paper's hourly reset into a feature, and the dream/sleep moment can be content in its own right.

### 2.3 Validate the audience before building the product

The plan puts real users at P9, after the viewer, replay, skills, memory, building, interactions and preservation work. Analogs suggest attention is the scarce resource, not features:
- Nothing Forever (24/7 AI Seinfeld) peaked at about 10–20k concurrent viewers and fell to under 10 viewers within about 18 months.
- Claude Plays Pokémon was reported at about 2k viewers in one snapshot.
- ARK and Nixi, the closest current analogs, show no public traction numbers.

**Recommendation:** in weeks 3–5, stream the *existing* spectator URL through OBS to Twitch or YouTube, and post daily highlight clips. The paper shows good raw material: invented games, towers, ground patterns, a clock face. That costs almost no code. Measure:
- Median concurrent viewers.
- Average watch time.
- 7-day return rate of chatters.
- Clip views.

Set a go/no-go threshold *before* the test. Example to calibrate: median CCV ≥ 15–20 without paid promotion over 2 weeks, plus ≥ 25% of chatters returning within 7 days.

This also tests a hidden assumption: that **1x live** is the product. The paper's own presentation, and most AI streams, depend on highlights, timelapse and visible reasoning. A **thought ticker** overlay showing the agent's current intent turns "idle" time into content. You might pass G5 with presentation as much as with architecture.

### 2.4 Check the revenue ceiling against costs now

I used the plan's own limits (§13) and price list. The PDF's text layer scrambles the table columns; I realigned them with 1 credit = €0.05, which also makes the island 600 credits / €30 / 48 h, matching §14. Assumptions:

- **Objects:** 20 active, average life ~18 min → about 67 slots/h × ~€0.15 → about €10/h.
- **Weather:** 1 active at a time, assumed 5–10 min each → about 9/h × ~€1.33 → about €12/h.
- **Large events:** at most 1/day × ~€25 → about €1/h.
- **Total at 100% utilisation:** about €23/h → **about €16.6k/month gross**, VAT included.

| Utilisation (24/7) | Gross / month | Ex-VAT (NL 21%) | After ~6% payment fees |
|---|---|---|---|
| 5% | €830 | €686 | ~€645 |
| 10% | €1,660 | €1,372 | ~€1,290 |
| 25% | €4,150 | €3,430 | ~€3,225 |
| 100% (theoretical) | €16,600 | €13,720 | ~€12,900 |

Inference at the plan's own assumption (8k input + 2k output tokens every 30 s, which is 0.96M input + 0.24M output per hour):

| Model | $/hour | $/month 24/7 |
|---|---|---|
| DeepSeek V4.1 Flash (off-peak / peak) | $0.29 / $0.58 | ~$210 / ~$420 |
| MiniMax M3.1 Flash | $0.29 | ~$210 |
| Claude Opus 4.7 ($5/$25) | $10.80 | ~$7,800 |
| Coding-agent harness + Opus (paper: ~$8k / ~1,100 agent-hours, *derived*) | ~$7–15 | ~$5–11k |
| Jev gating, 1 call/5 s × 1k tokens | ~$0.03 | ~$22 |

**Implications:**
- **Commit to Flash-class models for production.** Use Opus only as a quality reference arm.
- **The capacity caps are the business model.** One world with a 20-object cap means revenue can't scale with audience. Write down which lever you'll use if demand appears:
  - Scarcity pricing (the plan forbids it initially, which is reasonable).
  - Supporter subscriptions.
  - Sponsorship.
  - Platform currencies (Twitch Bits, YouTube Super Chat), as Crowd Control does.
  - More worlds or shards later.
- **Consider platform currencies before your own Stripe ledger.** Twitch or YouTube handle VAT, refunds, minors and chargebacks. You lose about 30% to the platform, but you skip all of P10's legal and ledger work until revenue justifies it.
- **If you sell your own credits, the EU CPC "Key Principles on in-game virtual currencies" (March 2025) apply** in spirit:
  - Show the real-money price next to every item. Your table already does this, which is good.
  - Packs mustn't force over-buying. Your packs are linear €5/€10/€20/€50 with no leftover traps, so keep them that way.
  - Include pre-contract info and the withdrawal-right waiver for immediate digital supply.
  - EU OSS VAT applies for B2C.

### 2.5 Re-scope against what upstream already ships

| Plan phase | Already in upstream |
|---|---|
| §15 snapshot-then-delta WS protocol ("may differ from upstream") | Upstream **already does exactly this**: a full `SpectatorObservation`, then `spectator_delta` frames with dirty tracking. The docs include a script that measures bytes/message. |
| P3 replay | `--record` writes `.clawrec`; `clawblox replay <file> --speed N --agent <jsonl>` overlays the agent timeline; replay manifests exist. *Missing:* many viewers each on their own timeline concurrently. |
| Resume / crash recovery | `--resume snapshot.json` restores the whole Lua VM, physics and pending inputs; Python `checkpoint` packages world + agent. |
| Datastore | SQLite DataStoreService locally. Defer PostgreSQL until payments. |
| World mutations (P7/P11) | Luau world scripts can spawn parts, change gravity, use terrain and fluid forces, and fire events. **Most interventions are world-script work, not engine work.** |

Also: the plan proposes Python/FastAPI + React/TS + PostgreSQL on top of Rust + Luau + JS. Five stacks is a lot for one person. Stay in Rust + Luau + the upstream JS runtime as long as possible, and keep Python for analysis scripts only.

### 2.6 Compress S0–S4 into about a week, and run them on Linux

- **Native Windows can't run `--agent`.** It shells out to `tmux` ([agent_runner.rs:1219](../clawblox/src/agent_runner.rs), and `docs/installation.md` says so). There's also a Windows bug: `require_program` checks `dir.join("claude")` and ignores PATHEXT, so `claude.exe` is never found. Use your WSL2 Ubuntu-22.04. Production will be Linux anyway.
- **You can run cheap models in V0 without code changes.** Claude Code honours `ANTHROPIC_BASE_URL`. DeepSeek documents an Anthropic-compatible endpoint (`https://api.deepseek.com/anthropic`; `claude-sonnet-*`/`haiku-*` map to the Flash model). Alternatively, `--agent kimi` is supported natively. That makes the 72 h soak affordable.
- **Use upstream's tests.** Run `cargo test` (398 tests, including mechanic, resume and weld-stability suites) instead of writing PHY-01..10 from scratch. Add only the tests that are about *your* product.
- **Keep the baseline clean.** `my-game/` is untracked inside the upstream checkout. Move it out (the plan's S0 rule is that `git status --porcelain` is empty).
- **V0 is essentially "upstream `8be90a0` on Ubuntu, tagged".** Tag it, write ENVIRONMENT.md, record one 2-hour run with `--record`, and move on. The evidence templates in §3.2 are good; one page per gate is enough.

### 2.7 You'll own the engine; plan for it

One maintainer, a research grant and a published paper is the classic profile of a repo that goes quiet. The 66k lines of Rust include a custom Luau VM persistence bridge in C++ (`crates/luau-persist`). Rewrite the risk "upstream incompatibility" as "**upstream goes quiet; we maintain a fork**". Mitigation:
- Pin a SHA.
- Keep Godling logic in world scripts and external services.
- Upstream small fixes, such as the PATHEXT bug, to build goodwill and context with the author.

### 2.8 Product-loop risk the plan underweights

The plan's principle is that the agent never sees who paid and new events don't automatically interrupt its task. That's ethically clean, but a viewer who pays €2.50 for a meteor the agent ignores will feel cheated. **The "reaction rate" is the core product metric:** the share of interventions the agent notices or engages with within N minutes. Measure it in the soak test by spawning objects from a Luau admin hook. Decide what the policy is if it's low, for example an "attention" reflex that at least *looks*, without breaking autonomy.

### 2.9 Memory: defer the framework bake-off

The paper shows native markdown memory *causally* helps:
- 8 of 13 agents built more than 2 towers after 30 h, against 2 of 13 at hour 0.
- Ablating one learned technique dropped one agent's tower count from 6 to 2.

The failure modes are false beliefs and linear growth. Hindsight or Cognee don't fix those automatically. MB-01..12 is a research project of its own. Trigger P5 only when the soak test shows a *specific* memory failure, such as context bloat beyond budget, repeated forgotten lessons, or uncorrected false beliefs. Start with the cheapest fix: periodic consolidation in the "sleep" cycle from 2.2.

---

## 3. What the plan gets right (keep these)

- **Engine as the source of truth, memory as interpretation.** Memory can never assert that an object exists. This is the most important architectural rule in the document.
- **Viewers change conditions; they can't buy decisions.** And the agent never sees payment info.
- **Reservation → apply → commit ledger with idempotency keys,** plus "charge only on successful application". That's correct, and it's usually done wrong.
- **The careful definition of `avoidable_idle_gap_ms`,** which excludes physical waits and deliberate pauses.
- **The A/B/C design logic.** "C beats A" doesn't prove Jev helps; C vs B does. "If equal, choose the simpler option."
- **Feature flags, a native fallback for every sidecar, and "a failed experiment stays on its branch".**
- **Event IDs on everything, so replay and the Chronicle can cite their sources.**

---

## 4. Proposed slim plan (part-time, timeboxed)

| Week | Work | Exit criterion |
|---|---|---|
| 1 | **Baseline:** WSL2/Ubuntu, pin `8be90a0`, `cargo test`, `--agent claude` with Opus (reference) and with a Flash model via `ANTHROPIC_BASE_URL`, 2 h recorded runs each. Register godling.world. | Tag `v0.1.0-baseline`; one-page evidence; first measured gap and cost numbers (= arm A). |
| 2–3 | **Arm B:** direct API loop + Skill Executor + the same memory files. Same scenes as A, 3 repeats. | B halves A's p95 avoidable gap at ≤5 pp success loss → `v0.2.0-control`. Jev only if residual gaps are from choice latency. |
| 3–4 | **72 h soak** (B, Flash), no resets vs a day/night sleep cycle; Luau admin hook spawns objects hourly to measure reaction rate. | Novelty and idle curves over time; reaction rate; $/hour. Pick the reset policy. |
| 4–6 | **Public stream test:** spectator view + thought ticker via OBS → Twitch/YouTube; daily clips; free chat-vote interventions (manual or a Luau hook). | Pre-registered go/no-go on CCV, watch time and 7-day return. |
| 7+ | **Only if go:** branded viewer (extend upstream renderer) → multi-viewer replay → free interactions queue → building/preservation → payments (platform currency first). | Each step keeps the plan's test → minimal implementation → regression → tag discipline. |

My rough estimate for P1–P11 as written: **30–50 weeks part-time**. The slim path reaches a real audience signal in **about 5–6 weeks**, and every step reuses the plan's own measurement discipline.

---

## 5. Smaller corrections to the document

- §2 decision ledger, §13 prices, §19 roadmap and §21 risks: these tables come out scrambled from the PDF text layer. Check that the source renders them aligned, and consider keeping the plan as Markdown in git, which also gives the ADR history the plan asks for.
- §11 model list: replace "Kimi K3.1 Pro" with Kimi K3 (supported upstream). Add the paper's actual baselines: Opus 4.7, GPT-5.5 via Codex, Kimi K2.6.
- §15: physics is 60 Hz upstream; drop the "30 Hz target".
- §17: the $400–800/mo band holds for Flash models; state the model assumption next to the number.
- §18: remove 5imulites (dead) and the Blerp link (403). Add ARK, Nixi and AI Plays Games with their monetisation models. Label thejevai.com as third-party.
- §23 #18: replace the Jev link with TypeSafe's docs or OpenRouter, and note the signup pause.
- Add durations or timeboxes to every phase; a plan without them can't flag a slip.

---

## 6. Decisions only you can make

1. Is the goal a **business** (then go/no-go metrics and platform-currency monetisation come first) or a **research/art project** (then the plan's rigour is the point and revenue is optional)?
2. Is **1x live** the product, or is "live + highlights/timelapse + Chronicle" acceptable? This changes how strict G5 should be.
3. Is a **day/night reset cycle** acceptable, or is uninterrupted continuity a hard product principle?
4. What's your monthly budget cap for inference during experiments? (My suggestion: $150 for weeks 1–4, mostly Flash.)

---

## Sources

- Clawblox repo and docs (local checkout `8be90a0`): https://github.com/nacloos/clawblox
- Machine Playing paper: https://arxiv.org/abs/2610.07130 · https://arxiv.org/html/2610.07130 · https://clawblox.pages.dev/paper
- Jev: https://openrouter.ai/blog/insights/what-is-jev/ · https://vercel.com/changelog/typesafe-ais-jev-1-14-is-now-available-on-ai-gateway · https://inworld.ai/models/typesafe-jev-1-14 · https://flaviocopes.com/jev/ · https://thejevai.com/typesafe-jev (third party)
- DeepSeek pricing: https://benchlm.ai/deepseek/api-pricing · https://www.aipricing.guru/deepseek-pricing/ · https://www.yottalabs.ai/post/deepseek-v4-1-flash-pricing-specs-v4-pro-routing-2026 · Anthropic-compatible API: https://api-docs.deepseek.com/guides/anthropic_api
- MiniMax M3.1 Flash: https://openrouter.ai/minimax/minimax-m3.1-flash · https://www.marktechpost.com/2026/10/19/minimax-m3-1-flash-release/
- Claude Opus 4.7 pricing: https://www.finout.io/blog/claude-opus-4.7-pricing-the-real-cost-story-behind-the-unchanged-price-tag · https://pricepertoken.com/pricing-page/model/anthropic-claude-opus-4.7
- EU CPC virtual-currency principles: https://www.twobirds.com/en/insights/2025/european-move-towards-protecting-users-from-harmful-practices-in-video-games-eu-consumer-protection · https://www.arthurcox.com/insights/eu-consumer-protection-new-principles-for-virtual-currencies-in-video-games/
- Stripe NL fees: https://stripe.com/resources/more/how-payment-gateway-fees-work-in-the-netherlands (confirm on stripe.com/nl/pricing)
- Hetzner 2026 prices: https://findstack.com/resources/hetzner-price-increase-2026 · https://www.bitdoze.com/es/hetzner-cloud-precios-2026/
- Nothing Forever: https://kotaku.com/ai-seinfeld-twitch-nothing-forever-mismatch-media-dead-1850208542 · https://getcoai.com/news/what-ai-seinfelds-rise-and-fall-reveal-about-the-future-of-ai-entertainment
- Claude Plays Pokémon: https://jamtest.dexerto.com/pokemon/what-is-claude-plays-pokemon-ai-attempts-to-beat-pokemon-3146630
- Competitors: https://arkreality.world/ · https://nixivt.com/ · https://www.aiplaysgames.com/ · https://noduspanel.com/ · https://crowdcontrol.live/ · https://www.cognizant.com/us/en/ai-lab/terralingua
