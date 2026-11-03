# Roadmap

This is the master plan v2.2's roadmap (the PDF of 30 October 2026, §19), showing where each phase stands now. The PDF is left as it is; this file is the living roadmap. Changes to the plan are listed at the end.

**The release** here means the first public launch: the site open to everyone, with credits (P9's public beta, with P10). P3 must be done before it.

## Where each phase stands (2 November 2026)
| Phase | What the plan asks for | Status | Where it stands |
|---|---|---|---|
| S0 | Clean local build of upstream Clawblox (G0) | ✅ Done | Pinned at `8be90a0`, built and running in WSL |
| S1 | A real LLM driving native actions (G1) | ✅ Done | Baseline runs a-003 (Opus, 16 min) and a-004 (DeepSeek Flash, 8.4 h); see `REVIEW_master_plan_v2.2.md` §1b–1c |
| S2 | Test every native mechanic (G2) | ⏭️ Skipped | Your decision. The native mechanics were checked by hand in the plan review (§1); there will be no per-mechanic pass/fail sheet. |
| S3 | Only the minimal bug fixes (G3) | ⏭️ Skipped | Your decision. The fixes Clawblox needed are kept as patch files: `patches/v0-fix-cli-sandbox.patch` (BUG-001) and `patches/v1-viewer-terrain-and-offline.patch` (VIEWER-001). |
| S4 | Freeze a `v0.1.0-baseline` tag (G4) | ⏭️ Skipped | Your decision. There is no tag. The baseline is upstream `8be90a0` plus those two patches, and the measured reference is runs a-003 and a-004. |
| P1 | Speed gate: arms A/B/C, Jev (G5) | 🟡 Mostly | Arm B replaced the upstream agent: a direct DeepSeek loop with a skill executor that thinks while moving (ADR-002, ADR-009). The character moved 4% of the time in the baseline; in night run n8 the body was busy 93%. Jev (arm C) was never run. |
| P2 | Live viewer and free camera (G6) | ✅ Done | Phone-friendly renderer (ADR-006), the viewers' screen and free camera (ADR-011), the thought bubble (ADR-009) |
| **P3** | **Replay and time travel (G7)** | ✅ **Built; required before the release** | ADR-016: each viewer's own timeline, 1×–16×, markers, Go live and shared links, tested live on a real run across restarts. Load and phone measured on the deployment (3 November): every target met, with 100 viewers and an emulated mid-range phone. Left: a real phone, the 24-hour soak, golden chunks for old formats, and a real R2 bucket. |
| P4 | Agent skills and goals (G8) | ✅ Done | Skills, reflexes, agendas, discovery, and skills the mind defines itself (ADR-002, 003, 008, 009) |
| P5 | Memory A/B and a choice (G9) | 🟡 Mostly | Three arms (native, native2, Hindsight) compared; Hindsight picked for night runs after run m2 (ADR-005). ADR-002 still says "Proposed", and there is no written benchmark report. |
| P6 | Basic building (G10) | ✅ Done | Quarry, axe, logs, ladder, fastening, the grid, a structure counter, shelter, stepping up (ADR-004, 005, 010) |
| P7 | Free viewer interactions with a queue (G11) | 🟡 Partly | Built: sky powers (Stone, Log, Regrow, Lightning, Meteor, Earthquake), random weather events, and notes with a queue and limits (ADR-010, 011). Most planned powers are not built (`research/god-powers-and-disasters-plan.md`). |
| P8 | Keeping chosen objects, TTL (G12) | ❌ Not started | |
| P9 | Chronicle and public beta (G13) | ❌ Not started | The Chronicle is undecided (`PRODUCT.md`). No public launch yet. |
| P10 | Credits and payments (G14) | 🟡 Partly | Built and tested locally: accounts, credits, a Stripe test checkout, a webhook that credits once, moderation, the admin (ADR-012, 013). Still to do: going live, running the Docker deploy, the legal and VAT review, and choosing the payment rail. |
| P11 | Large world mutations (G15) | ❌ Not started | |

## Also open
- **A long soak run.** The plan review asked for 72 hours; the longest run so far is about 8.
- **A public stream test** on Twitch or YouTube.
- **The domain.** godling.world was still free on 2 November 2026.

## Changes to the plan
- **2 November 2026:** S2, S3 and S4 are skipped (your decision). Their gates G2, G3 and G4 go with them.
- **2 November 2026:** P3 must be done before the release, and planned in detail first (ADR-016).
- **2 November 2026:** P3 built with the recommended choice for each decision; chunks go to Cloudflare R2 when a bucket is set (ADR-016).
- **Earlier, in the decision records:** in P1, Jev (arm C) was not run, and the direct loop (arm B) became the mind (ADR-002). In P5, Hindsight was chosen for night runs (ADR-005).
