# A layered mind for Godling: think about past and future, don't think about walking

Design note, 2026-11-01. It builds on the plan's §9.3 (LLM → Jev → Skill Executor), on runs a-003 (Opus) and a-004 (DeepSeek Flash), and on the research below. Cost figures marked *estimate* are my arithmetic from published prices and stated assumptions, not measurements.

## 1. The idea

People spend their deliberate thinking on the **past** (what happened, what it means) and the **future** (what to do next, what might go wrong). Walking, grasping and throwing run on **automatic skills** that need no conscious thought once learned. Godling should work the same way:
- an expensive, capable model only does "mental time travel": remembering, reflecting, imagining projects;
- cheap, fast machinery handles the moment-to-moment body.

## 2. Is this how people actually work? (short answer: yes, roughly)

- **Two systems for action.** Neuroscience distinguishes goal-directed control (prefrontal cortex) from habitual control (basal ganglia). Practice shifts behaviour from the first to the second. The basal ganglia also "chunk" action sequences into single units, which is exactly what a skill library is ([PMC4826769](https://pmc.ncbi.nlm.nih.gov/articles/PMC4826769); [Frontiers 2020](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2020.00380/pdf)).
- **The basal ganglia act as an action-selection gate.** Parallel cortico-basal-ganglia loops resolve competition between alternative actions. That's the role Jev would play: pick among options, don't invent them. Under time pressure or cognitive load, people fall back on habits ([Drummond & Niv](https://nivlab.princeton.edu/wp-content/uploads/sites/938/2024/02/drummond20.pdf)).
- **Remembering and imagining are one machine.** Schacter & Addis's *constructive episodic simulation*: the same core network (hippocampus plus the default network) recombines past episodes to simulate future ones. Amnesic patients also struggle to imagine the future ([OECS entry](https://oecs.mit.edu/pub/d16msun2); [Addis et al. 2015 meta-analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC4546530)). For Godling, this means **memory and planning belong in the same layer**, fed by the same episode store.

## 3. Who already builds agents this way

| System | Slow layer | Fast layer | Result |
|---|---|---|---|
| Figure **Helix** (robotics, 2025) | VLM "System 2", 7–9 Hz | visuomotor "System 1", 200 Hz | Dexterous 35-DoF control on onboard GPUs ([coverage](https://blog.kowatek.com/2025/02/21/the-hive-minded-fully-autonomous-vla-humanoid-robot/)) |
| NVIDIA **GR00T N1** (2025) | VLM System 2 | diffusion policy System 1, ~120 Hz | Open humanoid foundation model ([arXiv 2503.14734](https://web3.arxiv.org/pdf/2503.14734)) |
| **SwiftSage** (NeurIPS 2023) | GPT-4 planner | 770M fine-tuned T5 | SOTA 84.7 on ScienceWorld ([arXiv 2305.17390](https://arxiv.org/pdf/2305.17390)) |
| DeepMind **Talker-Reasoner** (2024) | Reasoner: plans, beliefs | Talker: fast responses | Lower latency, modular; qualitative evaluation only ([arXiv 2410.08328](https://arxiv.org/abs/2410.08328)) |
| **Hierarchical Language Agent** (AAMAS 2024) | "Slow Mind" LLM | "Fast Mind" | ~74% lower action latency in a real-time game ([paper](https://www.ifaamas.org/Proceedings/aamas2024/pdfs/p1219.pdf)) |
| **Voyager** (Minecraft, 2023) | GPT-4 writes and composes skills | skill library as executable code | 3.3× more items, milestones up to 15.3× faster; without the library, discovery plateaus ([arXiv 2305.16291](https://arxiv.org/pdf/2305.16291)) |
| **AgenticCache** (MLSys 2026) | LLM planner | cached, validated plan transitions | Up to 86% less latency and 79% less cost on embodied tasks ([paper](https://proceedings.mlsys.org/paper_files/paper/2026/file/c66a9db149261435664284a20b6f1d42-Paper-Conference.pdf)) |
| **Generative Agents** (2023) | memory stream → reflection → planning | — | Each of memory, reflection and planning is needed for believable behaviour ([arXiv 2304.03442](https://arxiv.org/pdf/2304.03442v2)) |

The robotics systems are the strongest evidence: dual-system control is now standard there. For LLM game agents, the evidence is good but smaller-scale. Voyager's skill library is the most relevant precedent.

## 4. What our own runs already show

- **Opus (a-003):** about **2 full-context model calls per world action**. About 45% of the time went on waiting for the model and 20% on `sleep` commands it wrote to wait out walks. Cost was $24/h. The model was "thinking about walking".
- **DeepSeek (a-004):** it **invented the motor layer itself**. It wrote `tools/world.py` (`move_and_wait`, `entities`, `leap`), and its median gap between actions dropped to **0.5 s**. But deliberation and motor control still share one expensive loop, and its intentions stay invisible.
- **False beliefs about physics.** Opus recorded pickup/place range as "~3 units", while `main.lua` says 6 and 7. **If the skill layer owns physical facts** (ranges, block height, throw ballistics), the mind never has to guess them, which removes a whole class of memory errors.

## 5. Proposed architecture

```
 L3  MIND  (capable LLM: v4-pro / Opus-class)           ~10-30 calls per hour
     "mental time travel": remember, reflect, imagine projects, choose goals, narrate
     owns: SOUL, episodic digest (past), project list (future), semantic notes
        |  writes a PROJECT: goal, skill steps, success test, abort conditions, one-line narration
        v                                                   ^ escalates salient events,
 L2  ATTENTION / SELECTION  (Jev 1.14, or Flash, or rules)  | finished/failed projects
     "basal ganglia": pick next step or option, score sites, | ~0.5-1 decisions per second
     decide "interrupt for this new thing?", detect stuck    |
        v                                                   |
 L1  SKILLS  (deterministic code, a library that can grow)  | reports success/failure + facts
     move_and_wait, pick, place_on_top, carry_to, throw_to (ballistics), climb
        v
 L0  REFLEXES + ENGINE  (executor guards + Clawblox physics)
     fall/respawn recovery, stuck detection, never walk through own tower, world truth
```

**How each layer behaves:**
- **L3 never sees raw coordinates streams.** It gets a compact digest: what changed, what finished, what failed, which notable objects are where. It's woken by events (project done or failed, a salient event from L2), by a timer (every few minutes), and by an hourly **"sleep"** that consolidates episodes. That sleep is the paper's hourly reset, turned into a feature.
- **L2 answers only typed questions over compact state.** For example: "Which of these 4 build sites?" (Choice), "How interesting is this new object, 1–5?" (Score), "Interrupt the current project?" (Boolean), "Is the agent looping?" (Boolean). It never invents goals.
- **L1 skills hold the physics.** They check reachability before acting (ranges from the world's config), verify the result, and return typed outcomes. New skills can be proposed by L3, Voyager-style, but only join the library after a test passes.
- **Memory follows the plan's rules:** engine truth, entries cite `world_tick`/event IDs, and observations are kept separate from interpretations.

## 6. Where Jev fits, honestly

- **Good fit:** fast, cheap L2 decisions. TypeSafe quotes about 100 ms typical and $0.042 per million input tokens (output free), so about $0.00002 per decision. That makes **continuous attention** affordable without waking the expensive mind. The product payoff is responsiveness: a viewer drops a meteor, L2 notices within about a second, L1 turns and walks towards it (a *visible* reaction), and L3 decides in the background what it means. That's the "reaction rate" metric from the review.
- **Bad fit:** making plans, inventing goals, arithmetic or coordinates (its docs list weakness at arithmetic and counting), and images ("danger zone", not production-ready).
- **Risks:**
  - It's about 2.5 weeks old, and TypeSafe paused signups (use OpenRouter or Vercel).
  - Accuracy drops as the state fills with unrelated content, so keep L2's state compact.
  - There are no public benchmarks.
- **Comparison to run (plan arm C vs B):** L2 as Jev vs Flash-with-structured-output vs simple rules. **The speed gain comes from L1. Jev's value is cheap, constant attention.** That's a narrower claim than the plan's, but a defensible one.

## 7. Cost estimate (*estimate*; assumptions stated)

**Assumptions:**
- L3: 20 calls/h with a 25k-token context (SOUL + digest + projects + filtered observation), 90% cache hits, 2k output tokens per call.
- L2: one decision every 2 s with 1.5k tokens.

| Configuration | L3 mind | L2 attention (Jev) | Total | 24/7 per month |
|---|---|---|---|---|
| Flash mind | ~$0.03/h | ~$0.11/h | ~$0.14/h | ~$100 |
| **v4-pro mind** | ~$0.12/h | ~$0.11/h | **~$0.25/h** | **~$180** |
| Opus-class mind | ~$1.55/h | ~$0.11/h | ~$1.7/h | ~$1,200 |
| *Measured today:* coding-agent harness | Opus $24.23/h · Flash $0.27/h | | | $17,450 · $240 |

**The key economic point: a capable model becomes affordable once it only thinks about the past and future and never about walking.** A v4-pro mind would cost about what today's Flash agent costs.

## 8. Product bonus: the inner life *is* the show

Run a-004's biggest problem was legibility. The agent did purposeful things (a gate, the Spire throw, a stone arc), but viewers saw cubes moving. In this design, L3's output is exactly what viewers need:
- an intention line ("I'll try a wider base this time");
- a reflection ("The ring rolled off the summit twice; I keep knocking it down when I climb");
- a project with a visible goal.

Feeding that into a thought ticker or the Chronicle turns invisible meaning into content. Remembering and imagining become the narrative; the body provides the motion.

## 9. Build path (maps to plan P1)

1. **L1 skill library v0 (1–2 days).** Formalise DeepSeek's `world.py` into about 8 skills with pre-checks, verification and typed results. Use the real ranges from `main.lua` (pickup 6, place 7).
2. **L3 mind loop (2–3 days).** A direct API loop with **no coding-agent harness**:
   - input: digest + project list;
   - output: JSON project (skill steps), narration, memory writes;
   - triggers: events, a timer, and an hourly "sleep".
3. **L2 v0 = rules plus Flash (1 day).** Then add Jev as arm C and compare.
4. **Narration.** L3's intention lines go to `/chat` and the Chronicle log.
5. **Measure with the existing tools:**
   - actions/h, gap p95 (G5 ≤ 2 s), motion duty cycle;
   - stack height (`stack_timeline.py`);
   - reaction rate to spawned objects;
   - $/h.
   - Baselines: a-003 (Opus harness) and a-004 (Flash harness).

**Trade-off:** Godling would own its agent loop instead of driving a coding-agent CLI, as the plan already anticipated with its "Python worker". The big-context cost disappears, but so does Claude Code's general toolset. Memory can stay as files.
