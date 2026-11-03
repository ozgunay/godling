# ADR-016: Replay and time travel (P3)

Date: 2026-11-02. Status: **built and tested live** on a real run, with the recommended choice for each of D1–D9 (you said to implement it using all of this) and Cloudflare R2 as the storage (D10). What was built, how it differs from the plan, and what is left are at the end, under "What was built".

## Why
You decided that P3 must be done before the release (`ROADMAP.md`), and planned in detail first. The master plan asks for this (§15, §16, §19 P3, §20 IT-02 and IT-11, §21):
- **World time and viewer time.** Each viewer has their own point on the timeline, while the world goes on.
- **Speeds.** The past plays at 1×, 2×, 4×, 8× or 16×. There is no seeking into a future that has not happened yet.
- **Controls:** scrub, pause, jump, Go Live, keep the camera, focus on a place or a thing, a link to share a moment, markers for events, and a timelapse across days from a fixed camera.
- **The live world is never touched.** Replay reads the record; it never rewinds the engine (IT-02).
- **Old records keep working.** A replay recorded under an older format either plays or says clearly why not (IT-11).
- **Storage** in hot, warm and archive classes, sized from measurement rather than assumption.
- **Measures:** seek time (p95), size per day, and accuracy.

## What is there already (read and measured on 2 November)
### Every run already records
- **`run_godling.py` starts the world with `--record`.** Each world start writes `<run>/recordings/<UTC start>.clawrec`.
  - In production the run continues across restarts in one folder (`/runs/live`), so each restart adds a new file.
- **The format** (Clawblox `src/recording.rs`) is a SQLite file holding:
  - a full snapshot of what spectators see (every entity and player, with their attributes), every 60 recorded ticks, about once a second, compressed with zstd;
  - a delta for each tick in between (about 60 a second). A delta holds positions and rotations; an entity whose anything else changed is written out whole;
  - chat and inputs;
  - its start time, tick rate (60), length and duration. These are rewritten every second, so a file stays readable after a crash.
- **What is in it:** everything the renderer draws. The island and every piece, Godling with its thought-bubble attributes, gesture, wet and cold, the fish, fires, and the Clock (time of day, rain, fog, wind).
- **What is not in it:** the viewers' screen around the island.
  - Godling's thought text, needs, intention and feed come from `mind/log.jsonl` through the panel's `/api/status`.
  - The viewers' pop-ups, with names and note texts, come from the panel and the site's database.
  - The reasoning stream, `mind/thinking.jsonl`, lives only in the run folder.

### Measured size
Measured on a 4-minute recording: Godling walking about, 709 entities, clear weather.

| What | Rate | Per day | Per year |
|---|---|---|---|
| The raw recording, as Clawblox writes it | 57 KB/s | 5.0 GB | 1.8 TB |
| Repacked for replay at 60 frames a second, 10 s chunks | 3.7 KB/s | 0.32 GB | 115 GB |
| … at 20 frames a second | 2.1 KB/s | 0.19 GB | 67 GB |
| … at 10 frames a second | 1.7 KB/s | 0.15 GB | 54 GB |
| … at 10 frames a second, 30 s chunks | 1.05 KB/s | 0.09 GB | 33 GB |

- **How the repacking works:** rebuild the full state at every tick, sample it, and round positions to 0.01 and rotations to 0.001. Each chunk is one full keyframe plus the deltas after it, compressed together with zstd. The raw file compresses each tick's delta on its own, which is why, even at the same 60 frames a second, it is 15 times larger.
- **A caveat.** A building day with rain, fires and viewers' powers will be larger. The numbers are re-measured on a night-run recording before M1 is done.

### Upstream's replay
- **`clawblox replay <file>`** is a server with a replay page. It has seek, speed, pause, skip-idle, play-a-range, a camera bridge and an agent-log timeline, and it uses the world's own renderer, so ours draws its frames.
- **It cannot be Godling's public replay:**
  1. **One playhead per server.** Seek, speed and pause live in one shared `ReplayPlayback`, so any viewer's seek moves everyone.
  2. **One finished file.** It reads the length when it opens the file, so it cannot follow the live file (no Go Live) or join files across restarts.
  3. **Its agent timeline** reads Claude Code's logs, not our mind's.
  4. **It streams every raw tick at playback speed:** about 57 KB/s per viewer at 1×, and 0.9 MB/s at 16×.
- **A bug found while reading it.** When a player moves in a tick, the delta keeps only its new position and health. Other attribute changes in that tick (the thought, a gesture, wet) are lost until the next snapshot, up to a second later.
  - The repacking diffs whole entities, so replays are at most a second late on these.
  - The live recording should still get the fix, as a Clawblox patch like BUG-001.

### Our renderer can draw replay frames
- **The viewers' screen** (`world/viewer/`) shows the island in an iframe: Clawblox's page with our renderer.
- **The renderer takes whole states** in `onState`. Its capture path (`__mesaCaptureMeta`: reset the buffer, set the clock) already lets a page feed it frames.
- **Clawblox's page runtime** also has its own replay mode, built for upstream's single-playhead server.
- **Still to try (M0):** mounting our renderer on a page of our own, without Clawblox's runtime socket.

## The proposal
### The shape
```
live world ──--record──▶ recordings/*.clawrec (raw, one per world start, kept a few days)
                │
                ▼  packer (in the island container; reads only, never touches the world)
      replay/chunks/<day>/<hour>/<start>.zst   10 s each: a keyframe and the frames after it
      replay/tracks/<day>/<hour>.json          what the screen shows: thoughts, needs, intention, feed, bubble
      replay/index.json                        segments, gaps and markers
                │
     Caddy ─────┤ chunks: static files, cached for good once closed
     site  ─────┘ index and tracks, joined with viewers' acts from its database: names looked up, hidden notes
                  dropped, access rules
                ▼
 browser: the viewers' screen in replay mode. It fetches chunks around its own playhead, plays them at its own speed
          into the renderer, and shows the screen from the tracks. Go Live switches back to the live stream.
```

### Principles
- **The browser plays, the server only serves files.** Every viewer has their own playhead and the server holds no state for it, so a thousand replay viewers cost a thousand static file reads.
- **The live world is never touched.** The packer reads the recording read-only, while the world writes it. No viewer reads the live SQLite file.
- **One clock: wall-clock UTC.** A segment is one recording file. A restart shows on the timeline as a short gap.
- **Record raw, serve slim.** Raw files are kept for a few days for debugging; replay chunks are kept long.
- **People's data is looked up when served, never baked in.** Viewer names and note texts come from the site's database at the moment of serving. A hidden note or a deleted account therefore disappears from replays too.

### The parts
1. **The packer** (new; built as `mind/godling/replay.py`). It runs beside the world in the island container.
   - It follows the newest recording; SQLite readers do not block the writer. Every 10 seconds it rebuilds the states and writes the next chunk.
   - **A chunk** holds a header (format version, start and end time, frame rate), one keyframe and the deltas after it, rounded and compressed with zstd. It is named by its start time.
   - It diffs whole entities itself, so the attribute bug above does not reach replays.
   - When a new recording starts, it closes the segment. On start-up it catches up any recording it has not packed.
   - It writes `index.json`: segments (start, end, the gaps between them), and the chunks of each hour.
2. **Tracks:** what the screen shows around the island, one file per hour.
   - **From `mind/log.jsonl`:** the thought, needs, intention, feed lines and bubble (picture and feeling), each at its time.
   - **Viewers' acts are not packed.** The site's database already keeps every power a viewer called (`PowerCall`) and every note (`Note`), with its time. The site reads them for the asked span when it serves the tracks. In test mode without the site, the panel keeps them only in memory, so they do not replay there.
   - **Markers** (D8), from the world's and the mind's logs:
     - weather turning: rain, a wet spell, a storm, fog;
     - sky powers and notes;
     - meteor, earthquake, lightning;
     - fire made or put out;
     - fish speared;
     - a faint;
     - a structure milestone: the first wall, roof or enclosure;
     - dawn and dusk.
3. **Serving.**
   - **Chunks:** Caddy serves `/replay/chunks/*` straight from the runs volume, read-only. Closed chunks get `Cache-Control: immutable`.
   - **Index and tracks:** the site serves `/replay/index` and `/replay/tracks?from=…&to=…`. It joins the packed tracks with viewers' acts from its database, adds names, drops hidden notes and applies the access rules (D1).
   - **Nothing new of the world is reachable from outside.**
4. **In the browser,** in the viewers' screen and a small replay page for the iframe.
   - **The replay page** (as built: the renderer itself, `world/renderer/src/replay.js`; see "Different from the plan") feeds it states built from the chunks:
     - it fetches the chunk at the playhead and prefetches the next two or three (at 16× that is one chunk every 0.6 s);
     - it decodes zstd in the browser with `fzstd`, a small pure-JavaScript decoder (MIT), or with gzip and the browser's own `DecompressionStream`, if M0 finds gzip no more than 30% larger.
   - **The timeline,** along the bottom of the viewers' screen:
     - drag to scrub;
     - day and night shading;
     - markers that jump on a tap;
     - pause and speeds (1×, 2×, 4×, 8×, 16×);
     - a time label ("Tuesday 21:14 · 2 h ago") and a Live button;
     - a phone layout.
   - **The screen in the past:** the same panels as live, filled from the tracks at the playhead. The powers are greyed out with "Go live to act" (D6).
   - **The camera:** the free camera and following Godling carry over between Live and Replay. The pose passes to the replay page.
   - **A link to share:** `?t=<UTC time>&cam=<follow | x,y,z,yaw,pitch>` opens replay at that moment and from that view. A time not yet reached opens Live.
   - **Go Live** switches the iframe back to the live island. The newest replay lags live by 10–20 s (one chunk), so the right end of the timeline is simply "Live".
5. **Keeping it** (D4): a daily job deletes raw recordings older than a few days, and keeps chunks and tracks. It warns when the disk is 80% full.
6. **The timelapse** (D7): days from a fixed camera, made from keyframes only, such as one day a minute.

### Targets: the exit criteria
| Target | Number |
|---|---|
| Seek to the first frame, on a phone over 4G | p95 ≤ 1.5 s |
| 16× on a mid-range phone, at the low quality tier | no stalls |
| Data per replay viewer | ≤ 3 KB/s at 1×, ≤ 50 KB/s at 16× |
| How far replay lags live | ≤ 20 s |
| The packer's CPU | ≤ 5% of one core |
| The live world with 100 replay viewers | tick p95 unchanged |
| Accuracy at 200 random times | the replayed state equals the raw recording's: the same entities and attributes, positions within 0.01 |

### Acceptance tests
| ID | Scenario | Expected |
|---|---|---|
| RP-01 (IT-02) | A viewer replays while the world runs | The live tick p95 and stream are unchanged; the world never rewinds |
| RP-02 | Two viewers replay different times at different speeds | Each sees their own; neither moves the other |
| RP-03 | 200 random times | The state from chunks equals the state from the raw recording |
| RP-04 | Playing across a restart | It plays up to the restart, shows the gap, and goes on in the next segment |
| RP-05 | Go Live, and back | Live in ≤ 2 s; the last 10 minutes can be replayed |
| RP-06 | A link to a time after now | It opens Live |
| RP-07 (IT-11) | A chunk in an unknown format, and old chunks after a renderer update | A clear message and no broken scene; golden chunks from every format version still play |
| RP-08 | A note hidden by moderation; a deleted account | The note is gone from replays at once; the name shows as "Someone" |
| RP-09 | The packer crashes and restarts; the world crashes mid-file | It catches up with no missing or doubled chunks; a cut-off recording packs up to its last second |
| RP-10 | 100 replay viewers at 16× | Server CPU and data out measured; the live world unaffected |
| RP-11 | 16× on a mid-range phone | Frame rate measured at the low tier |
| RP-12 | The daily keeping job | Deletes only raw files older than the limit; chunks stay; the disk warning fires at 80% |
| RP-13 | A shared link on another device | The same moment and the same view |
| RP-14 | Each kind of marker | At the right time (±1 s); a tap jumps there |

### Milestones
| | Work | Exit | Estimate |
|---|---|---|---|
| M0 | Spikes: mount the renderer on our own page and feed it frames; zstd or gzip in the browser; re-measure sizes on a night-run recording | The renderer plays a 10-minute chunk file in a plain page | 1 day |
| M1 | The packer, the index, and golden tests | RP-03, RP-09 | 2–3 days |
| M2 | Tracks and markers, served by the site with moderation and names | RP-08, RP-14 | 2 days |
| M3 | Serving: Caddy for chunks, the site's endpoints, access rules (D1) | Reachable through Caddy as in production | 1 day |
| M4 | Replay mode in the viewers' screen: timeline, speeds, Go Live, links, phone layout | RP-02, 05, 06, 13 | 3–4 days |
| M5 | The Clawblox attribute patch, the keeping job, format checks | RP-07, RP-12 | 1 day |
| M6 | Load, phone and a 24-hour soak with packing on | RP-01, 04, 10, 11 | 2 days |
| M7 | The timelapse, if D7 says now | Days play at about one a minute | 1–2 days |

That is about 12–15 working days without M7. These are estimates; M0 may change them.

### Where it lives
As built:
- **`mind/godling/replay.py`:** the packer, the tracks, and the readers the panel serves.
- **`tools/guest_panel.py` and `web/apps/screen/views.py`:** the replay endpoints; the site's moderation of them.
- **`world/renderer/src/replay.js`:** the player, in the island's page.
- **`world/viewer/replay.js`:** the timeline on the viewers' screen.
- **`deploy/Caddyfile`:** the chunk route.
- **`patches/`:** the Clawblox attribute fix.

### Risks
- **The renderer may lean on Clawblox's page runtime** more than its capture path shows. M0 finds out first. The fallback is upstream's page runtime in replay mode, fed by one small replay process per viewer, which costs more on the server.
- **Disk on the one server.** Raw recordings take 5 GB a day, so they must not be kept long. The server's disk size sets the limit in D4.
- **Busy days are larger than measured.** M0 re-measures.
- **Old replays after the world or renderer changes,** for example renamed attributes or replaced models. The rules: asset files are never deleted, the renderer stays backward-compatible, and golden chunks from every format version are tested.
- **A thought that quotes a hidden note** would still show it. Feed and thought lines that contain a hidden note's text are hidden too.
- **The law.** Replays keep viewers' names and notes, so the privacy policy must say how long replays are kept and what deleting an account removes.

## Decisions for you
1. **D1: Who can watch replays, and how far back?**
   - **a) Everyone, the whole history (recommended).** Catching up on what happened while you were away is a reason to come back, and it costs little.
   - b) Everyone for the last 24 hours, accounts for older.
   - c) Older than 24 hours for supporters only.
2. **D2: Where playback runs.**
   - **The browser, from static chunk files (recommended).**
   - Or one server session per viewer, upstream's way: a process per viewer, and 0.9 MB/s per viewer at 16×.
3. **D3: Frame rate in replay.**
   - **10 a second, smoothed by the renderer (recommended):** 1.7 KB/s.
   - 20 a second: 2.1 KB/s.
   - 60 a second: 3.7 KB/s.
4. **D4: How long things are kept.**
   - **Raw recordings 3 days, for debugging; replay chunks and tracks for good, 54 GB a year at 10 a second (recommended).**
   - Or chunks for 90 days.
5. **D5: What the screen shows in the past.**
   - **The same as live (recommended):** thought, needs, intention, feed, bubble and viewers' pop-ups.
   - The full reasoning could come later as a side panel.
6. **D6: Powers during replay.**
   - **Off, with "Go live to act" (recommended).** Nobody pays to change the past.
7. **D7: The timelapse across days.**
   - **After the release, with the Chronicle in P9 (recommended).** That keeps P3 to what the release needs.
   - Or in P3 now, as M7.
8. **D8: The markers.** The list under "Tracks" above. Confirm it, or change it.
9. **D9: Shareable links.**
   - **The time and the camera in the link (recommended).**
   - A preview picture for social posts can come later.
10. **D10: Where the recordings and chunks are kept** (asked after the plan).
    - **Raw recordings: on the server's own disk, 3 days.**
    - **Replay chunks: Cloudflare R2 (recommended),** through the S3 interface: about $1.50 a month in the first year, and downloads cost nothing. Hetzner Object Storage (€6.49 a month flat) or Amazon S3 work the same way, by endpoint and keys. Amazon S3 would cost the most here, mainly in downloads.
    - **Tracks, markers and the index** stay on the server, beside the run.

## What was built (2 November)
Taken as recommended: D1 everyone, all the history; D2 the browser plays static chunks; D3 10 frames a second; D4 raw 3 days, chunks for good; D5 the screen as live; D6 powers off in the past; D7 the timelapse after the release; D8 the markers listed; D9 the time in the link; D10 R2, or the runs volume without a bucket.

### The pieces
- **The packer** (`mind/godling/replay.py`) runs beside the world as its own process (`python3 -m godling.replay follow <run>`, started and stopped by `run_godling.py`), so catching up never holds up the mind.
  - It reads the recording read-only, rebuilds every tick, and every 10 s writes `replay/chunks/<day>/<hour>/<t0>.json.gz`: a keyframe and 99 frames.
  - It writes the index, the tracks from the mind's log, the markers, and the island's hour and weather once a minute.
  - It deletes raw recordings once they are packed and older than `GODLING_REPLAY_RAW_DAYS`, and warns in `replay.log` when the disk is 80% full.
  - With `GODLING_REPLAY_BUCKET` set, it also uploads each chunk to the bucket. The local chunks then stay only two days.
  - `python3 -m godling.replay check <run>` compares random replayed moments with the raw recording.
- **The guest panel** serves `/api/replay/index`, `/tracks`, `/marks` and `/sky`, and `/replay/chunks/…`, and keeps what viewers did for replays (`replay/acts/`).
- **The site** relays the same endpoints (`apps.screen.views.api_replay`). On the way it hides notes hidden by moderation, and lines of Godling's mind that quote one, and shows names whose account is gone as "Someone".
- **Caddy** serves `/replay/chunks/*` straight from the runs volume, cached for good, on the island's own origin (ADR-014), where the page that plays them lives. The site's index names that address (`GODLING_REPLAY_URL`), or the bucket's when the packer uploads. The island image gets `zstd` and `python3-boto3`.
- **The island's page** (`world/renderer/src/replay.js`) plays the chunks itself when the screen asks. Its frames go into the same buffer as the live ones, so the camera follows Godling in the past as it does live. The live stream stays connected, so going live is instant.
- **The viewers' screen** (`world/viewer/replay.js`):
  - Rewind under the live badge; the badge then says "Replay".
  - A timeline above the hotbar: scrub, play and pause, ±1 minute, speeds from 1× to 16×, and spans of 1 h, 6 h, 24 h or 7 days, picked to fit a young history.
  - Day, night and rain shading on the timeline; the time before the first start or during a restart hatched; markers to tap.
  - "Share this moment", and Go live. Playing into the present goes live by itself.
  - The feed, needs, bubble, clock, body and viewers' pop-ups as they were at that moment.
  - The address carries `?t=…`, so a link opens that moment.

### Different from the plan
- **No separate replay page.** M0 found that the renderer runs inside Clawblox's page, which always opens the live stream. So the replay player lives in the renderer and switches on by a message from the screen. It is simpler, and going live costs nothing.
- **gzip, not zstd.** gzip was 31% larger (2.2 KB/s against 1.7), just over the 30% the plan allowed. It needs no decoder in the browser or in Python, and every CDN passes it as it is.
- **The packer is a process of its own,** not a thread in the mind's process (above).
- **Chunks one per object, not packed hourly.** On R2 the uploads are free (about 263,000 a month, within the free million). Packing an hour into one object is needed only on Amazon S3.
- **The link carries the time,** but not yet the free camera's position.

### Measured and tested
| Check | Result |
|---|---|
| Packing speed | 4 minutes of recording packed in 3.9 s: about 1.5% of one core |
| Size | 2.2–2.5 KB/s with gzip: 1.6 MB for 13 minutes of a real run, against 34 MB raw |
| RP-03 accuracy | 300 random moments of the real run (three segments): all the same as the raw recording. A first run of 200 found one difference (a tool set down lost its rotation, and the packer said "rotation: none"); fixed |
| RP-04 across restarts | Played at 4× across a 2.5-minute restart: the screen said "The island was restarting here", jumped to where it came back, and showed the gap hatched |
| RP-05 Go live | Instant (the live stream never stopped); playing into the present at 16× went live by itself |
| RP-06 and RP-13 links | A link with `?t=` opened that moment, at the shadow 40 s before a stone fell; the stone then fell and left its crater |
| RP-08 moderation | Site tests: a hidden note leaves the pop-ups, a line quoting it is hidden, a gone account shows as "Someone" |
| RP-09 crash and stop | Stopped three times: each segment closed and packed up to its last second, and the next start made a new segment |
| RP-14 markers | The stone from the sky marked at its time; a tap jumped to 5 s before it. One event told twice is now one marker |
| D6 | A power pressed in the past: "You are watching the past. Go live to call powers and send notes." |
| Object storage | Against a local S3 stand-in (moto): 24 of 24 chunks uploaded under the prefix, with the right type and cache header, and read back from the public address |
| Phone (375 × 812) | The timeline fits; the hotbar steps aside while you watch the past |
| Site tests | 57 of 57 pass, 4 of them new |

### Left
- **RP-01, RP-10, RP-11:** the live world's tick time with 100 replay viewers, and frame rate on a real mid-range phone. These are not measured yet. By design the world is not touched (the packer reads a file, and viewers read static files), but there are no numbers.
- **RP-07, old formats after a renderer update:** the format number is checked, and a newer one is refused with a message. Golden chunks kept for each format are not in place yet.
- **The Clawblox attribute fix** (patches/): replays do not need it.
- **Real R2:** only the stand-in has been tested. It needs a bucket, keys and a public address in `deploy/.env`.
- **The free camera's position in shared links.**
- **D7, the timelapse:** after the release, as decided.

## After the review of PR #22
An extensive review (nine angles, each finding verified independently) found 26 real problems, and they are fixed:

- **The screen's tracks never loaded on a slow link.** A new request went out with every playhead report (four a second), and only the newest answer was kept. Now there is one request at a time, kept if it covers the playhead, from two minutes before it to thirty after.
- **The packer could stall for good.** A bad row (the world writes a NaN coordinate as null) or a failing recording was retried forever. That stopped the deletion of old recordings and the disk warning, so the disk would fill.
  - A bad row is now skipped and said in `replay.log`. Coordinates that are not numbers are kept as null.
  - A recording that will not pack holds up neither the others nor the keeping job, and an old one is left after five tries.
- **The recording being written grew without limit**, about 5 GB a day, until the world restarted. Its packed rows older than `GODLING_REPLAY_RAW_DAYS` are now deleted once an hour, a few thousand at a time. Live: 10,076 rows went in 0.16 s while the world kept writing, with no recording warnings.
- **Object storage:**
  - A chunk that failed to upload eight times was dropped, and a later success moved past it. It is now put back in the queue.
  - Progress is kept as the oldest chunk not yet up, so a local day is deleted only once all of it is up.
  - The index used to send browsers to the bucket before chunks were there. It now says up to when the bucket has them (`chunks_url_until`), and browsers fetch later chunks from the island.
  - The bucket needs a CORS rule for the island's page: the packer sets one, or says it could not.
  - A bucket without a public address is refused.
- **The start of a replay could be lost.** A shared link started 1.5 s after the island's page loaded, but the renderer starts listening later than that. The renderer now says when it can hear the screen (`godling-ready`), and the screen opens the moment then. A replay started before the first live frame now draws too.
- **Not-yet-written chunks:**
  - The player asked for chunks past the index's end, cached the 404s as holes, and skipped them later. It no longer asks past the end, and it tries a failed chunk four times before skipping it.
  - Caddy sent its keep-for-a-year header with 404s too; now only with chunks that exist.
- **Moderation in the past is an allow-list now.**
  - A note is shown only while its row exists and is not hidden, with its author's name and its text from that row. Deleting a note or an account removes it from the past too, along with the paper glider's line quoting it.
  - A hidden note is looked for in Godling's words regardless of case, and only from 8 characters up, so a hidden "no" no longer blanks every "know".
  - Report is offered only within the site's 30-minute window.
- **The site's replay endpoints** wait at most 5 s on the island, and the index is shared for 3 s, as the live status is. Without `GODLING_REPLAY_URL`, a development site points browsers at the panel's chunks.
- **Old runs drew with an old renderer.** Each start now copies in today's renderer and models, while a run keeps its own world script.
- **Smaller fixes:**
  - **Markers:**
    - an earthquake is marked at its rumble;
    - one event is one marker, by its sky id;
    - the first faint of a world start is marked, whatever the order of the players;
    - markers come back in time order.
  - **Chunks** name models `asset://name.glb`, so they still draw if the island moves.
  - **The timeline:**
    - a week's timeline downloads its sky data one sample per bar pixel, not one per minute;
    - it reloads only when now has moved on a fiftieth of its span;
    - replayed pop-ups show again on each pass;
    - the screen redraws only what changed;
    - a problem is told once;
    - a bad index answer no longer replaces the last good one;
    - a cancelled touch no longer freezes the playhead.
  - **Stopping and accessibility:**
    - the badge's label says Replay;
    - the packer saves its progress during a catch-up and stops promptly;
    - it runs in its own session, so Ctrl+C reaches it only after the world.

Tested again:

| Check | Result |
|---|---|
| Accuracy, after the trim | 150 of 150 moments of a live run |
| Synthetic checks of the packer (`test_replay_fixes.py` in the session scratchpad) | all pass: a bad row, two recordings, one marker per event, the quake at its rumble, the first faint with Sky first, upload retries, the backlog mark |
| A shared link opened cold | opened in replay once the island's page could hear it |
| Playback at 4× | one tracks request in all |
| Site | 112 tests pass |
