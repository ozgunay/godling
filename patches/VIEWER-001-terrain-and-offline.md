# VIEWER-001: terrain for viewers, an offline viewer, fresh world files

| Field | Value |
|---|---|
| Upstream SHA | `8be90a0` (v0.1.5-2), nacloos/clawblox, with [v0-fix-cli-sandbox.patch](v0-fix-cli-sandbox.patch) applied first |
| Patch | [v1-viewer-terrain-and-offline.patch](v1-viewer-terrain-and-offline.patch) |
| Status | **Built and tested 2026-11-01** in WSL (Ubuntu 22.04): `cargo test --release` 396 passed, 0 failed (2 of them new). Checked live in the browser and with `/observe/image` |
| Goes with | ADR-006 and the renderer in `world/renderer/` |

## What it changes

1. **Terrain reaches viewers.** Clawblox has voxel terrain (`Workspace.Terrain:FillBlock`, `WriteVoxelChannels`, water with fluid forces), but it never sent it to the browser. Now:
   - `SpectatorObservation.terrain` carries the voxels. Each voxel is six numbers: cell x, y, z, material index, solid occupancy and liquid occupancy (both 0-255). It also has a `revision` and a material list.
   - Full observations include it when there is any terrain.
   - Live updates (`spectator_delta`) include it only when the terrain changed. Every terrain edit bumps `TerrainData.revision` and marks the Terrain instance dirty in the existing replication state.
   - The browser keeps the terrain across deltas (`frontend_runtime/dist/main.js`).
   - Godling's renderer draws it as Minecraft-style blocks (`world/renderer/src/terrain.js`).
   - Recordings get terrain through their full keyframes. Their frame deltas don't carry it yet, so a replay shows a terrain edit at the next keyframe.
2. **The viewer works without a CDN.** The runtime page imported lucide icons from esm.sh. If esm.sh was down, the page failed and so did Godling's vision capture, which loads the same page.
   - The four lucide exports the page uses are vendored in `frontend_runtime/dist/vendor/lucide.js` (2 KB, ISC licence kept). Godling's renderer bundles three.js itself.
   - The page now loads nothing from outside the server.
   - The import map's `three` entries still point at esm.sh, for other worlds' renderers that import `three` by name; Godling's doesn't.
3. **World files are revalidated.** `/renderer-files/*` and `/assets/*` now send `Cache-Control: no-cache`. Before, browsers guessed how long to keep them, so a viewer could see an old model or renderer after an update. Now the browser revalidates each file: an unchanged file costs a 304 and nothing more.
4. **`trackAssetLoad` is exported** from the runtime's three SDK. Godling's renderer loads its own models; with this it can register them, so the replay viewer's "assets settled" wait covers them.

## Apply

On top of v0, in the WSL clone:

```bash
cd ~/clawblox && git checkout 8be90a0 && git apply /path/to/godling/patches/v0-fix-cli-sandbox.patch && git apply /path/to/godling/patches/v1-viewer-terrain-and-offline.patch && cargo install --path . --locked
```

## Tests

- `tests/spectator_terrain_test.rs`:
  - Terrain is in the full observation only when there is some, with the right cells, materials and occupancies.
  - A replication update carries terrain only after an edit.
  - Clearing the terrain sends an empty terrain.
- Live, with a test copy of the world that fills terrain at sea and grows a brick column every 3 s:
  - The terrain shows on connect.
  - Each brick arrives as a delta and is drawn.
  - The sea's shore map includes the terrain.
- Offline: with the patched server, the page's only resource host was the server itself (no esm.sh request).
- `/observe/image` works under WSL with the patched server (about 0.25 s per capture warm).
