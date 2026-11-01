# ADR-006: Keep Clawblox and three.js; rebuild the renderer for phones

Date: 2026-11-01 (night). Status: built, not yet run in a long run.

## Question
Godling is meant to get shaders, a proper sea, clouds, a sun, and 3D models with animations, at about Minecraft's level. It must still run in phone browsers and on low-end PCs. Is the engine enough, or should Godling move to Magnum or raylib?

## Answer: the engine was never the limit
- Clawblox has three layers:
  - a headless Rust server (Rapier physics at 60 Hz, Luau world scripts);
  - a three.js renderer in the browser;
  - Godling's eyes: `/observe/image`, which runs that same renderer in headless Chromium on the server's CPU (SwiftShader).
- Every wanted feature lives in the renderer.
- In a browser, Magnum and raylib are compiled to WebAssembly and draw through WebGL, the same WebGL 2 three.js uses. Neither has WebGPU.
- WebAssembly's speed would have nothing to work on: physics runs on the server, and the browser only interpolates.
- Switching would have meant rebuilding the renderer contract, the camera, the interpolation, the model animation, and Godling's vision path, for no new GPU feature.
- Other points against:
  - Magnum: no tagged release since v2020.06; nearly all commits by one author.
  - raylib's documented web path: WebGL 1, with GPU skinning only on GL 3.3+.
- The renderer is one module behind a fixed contract (`createRenderer(ctx)`), so even a later move to Babylon.js or PlayCanvas would replace one folder, not the engine.

## What was actually wrong, and what changed
| Problem | Change |
|---|---|
| three.js r160 (Dec 2023) loaded from esm.sh at runtime. If esm.sh was down, the stream went black and Godling went blind. The runtime's own page also imported icons from esm.sh. | three.js r187 bundled in (`world/renderer/build.mjs`, bundle committed). Clawblox patch VIEWER-001 vendors the icons. The page now loads nothing from outside the server. |
| One mesh, geometry and material per part, so one draw call each. | Instanced drawing (`instances.js`), one draw call per kind of mesh. |
| Godling's model: 51,776 triangles in 23 meshes. | 4,560 triangles in one skinned mesh, 6 materials (`art/build_godling.py`). It moves and looks the same. |
| No quality tiers; 2048 soft shadows and antialiasing everywhere; pixel ratio ignored. | Low, medium and high tiers (`quality.js`), chosen per device. The capture always gets low. Resolution scales down when frames are slow. |
| Clawblox's terrain never reached the browser. | VIEWER-001 sends it (only when it changes). `terrain.js` draws it as Minecraft-style blocks. |
| A flat see-through plane for the sea, sphere clouds, a two-colour sky. | three.js `Sky` with one sun driving everything (`sky.js`). A Gerstner-wave sea with sky reflection, glint and shore foam from a baked distance map (`sea.js`). Minecraft-style pixel or voxel clouds (`clouds.js`). Fog. Cascaded shadows on high. |
| Found on the way: Godling's first-person capture showed the back of its own head. | The body the camera sits in is hidden during a first-person capture. Godling now sees the island. |
| Found on the way: Clawblox sent no `Cache-Control`, so viewers could keep an old model or renderer after an update. | VIEWER-001: `no-cache` on world files (a cheap 304 when unchanged). |

## Measured (same island, one player, default camera)
| | Before | After: low | After: medium | After: high |
|---|---|---|---|---|
| Draw calls per frame | 203 | 70 | 69 | 135 (3 shadow cascades) |
| Triangles per frame | 172k | 127k | 177k | 365k |
| What is drawn | flat sea, sphere clouds | waves, foam, pixel clouds, sky, fog | plus ripples, voxel clouds, 2048 shadows | plus cascaded shadows, sky cloud layer |

The renderer bundle is 863 KB (228 KB gzipped).

Godling's capture (SwiftShader, 1088 x 640):
- Warm, it takes 0.15 s before and after on Windows, and 0.25 s in WSL with the patched server.
- Before the change the picture was mostly the inside of its head; now it is the island.

## Still open (yours to decide)
- **A day/night cycle in the world.** The renderer can show any hour (`?time=`, `?dayMinutes=`), but by default the sun is fixed where the light always stood. A real cycle would come from the world (for example an attribute the renderer reads). Night would also darken Godling's own view.
- **Deploy VIEWER-001** in the WSL `~/clawblox` (README, step 1). Until then the world works, but its page needs esm.sh for one icon set, and terrain is not sent.
- **Not measured on a real phone.** Phone sizes were emulated in the browser. The tier choice is a heuristic; `?quality=` overrides it.

## Not done
- **Raymarched volumetric clouds.** Voxel clouds fit the look and cost almost nothing.
- **Reflections of the island in the sea** (a second render of the scene).
- **WebGPU.** WebGLRenderer stays: WebGPU on phones is still patchy (Android only on some GPUs, iOS 26 and later), and three.js's WebGPU renderer does not take the GLSL shaders written here.
