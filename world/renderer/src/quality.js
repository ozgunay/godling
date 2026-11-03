// Quality tiers. Godling is watched in phone browsers and on low-end PCs, and it sees through this same renderer
// on the server's CPU (headless Chromium with SwiftShader, Clawblox's /observe/image). Each tier trades looks for
// frame time; a software-rendered or automated browser, which is how that capture runs, always gets "low".
// `?quality=low|medium|high` overrides the choice.

export const TIERS = {
  low: {
    name: 'low',
    fireLights: 1, // fires that light their surroundings at once (the nearest)
    smokePuffs: 28, // per fire
    shake: 0.5, // how much of an earthquake's camera shake (none in the capture)
    dustPuffs: 48, // dust puffs alive at once, where pieces land or slide
    blastDetail: 0.4, // how much of a meteor's blast is drawn: fireball, embers, smoke, chunks (blast.js)
    blastGlow: 128, // fire, embers and flashes alive at once
    blastSoft: 96, // smoke, sand and dust alive at once
    blastChunks: 8, // charred chunks thrown out at once
    blastLight: false, // the flash lights the ground with a light of its own (a lightning strike's too); without one,
    // the ambient light flares
    // A bolt is the same on every tier (lightning.js), drawn with less of it:
    lightningDepth: 5, // its channel drawn with 2^n segments (of 2^7)
    lightningForks: 3, // forks off the channel (of 5)
    lightningForkDepth: 0, // forks of forks
    lightningArcs: 3, // arcs along the ground where it strikes (of 5)
    pixelRatio: 1.25, // the most device pixels per CSS pixel
    antialias: false,
    shadowMapSize: 1024,
    shadowRadius: 1,
    shadowExtent: 45, // half the width of the sun's shadow box, around the camera's target
    cascades: 0,
    seaSegments: 96,
    seaWaves: 2,
    seaRipples: false,
    clouds: 'flat',
    skyClouds: 0,
    fogFar: 520,
  },
  medium: {
    name: 'medium',
    fireLights: 2,
    smokePuffs: 56,
    shake: 0.8,
    dustPuffs: 96,
    blastDetail: 0.7,
    blastGlow: 256,
    blastSoft: 160,
    blastChunks: 16,
    blastLight: true,
    lightningDepth: 6,
    lightningForks: 4,
    lightningForkDepth: 1,
    lightningArcs: 4,
    pixelRatio: 1.5,
    antialias: true,
    shadowMapSize: 2048,
    shadowRadius: 2,
    shadowExtent: 60,
    cascades: 0,
    seaSegments: 160,
    seaWaves: 4,
    seaRipples: true,
    clouds: 'voxel',
    skyClouds: 0,
    fogFar: 640,
  },
  high: {
    name: 'high',
    fireLights: 3,
    smokePuffs: 84,
    shake: 1,
    dustPuffs: 160,
    blastDetail: 1,
    blastGlow: 384,
    blastSoft: 256,
    blastChunks: 24,
    blastLight: true,
    lightningDepth: 7,
    lightningForks: 5,
    lightningForkDepth: 1,
    lightningArcs: 5,
    pixelRatio: 2,
    antialias: true,
    shadowMapSize: 2048,
    shadowRadius: 2,
    shadowExtent: 60,
    cascades: 3, // cascaded shadow maps: sharp near the camera, still there far away
    seaSegments: 256,
    seaWaves: 4,
    seaRipples: true,
    clouds: 'voxel',
    skyClouds: 0.25, // a thin high layer in the sky dome, above the voxel clouds
    fogFar: 760,
  },
}

function rendererName() {
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
    if (!gl) return ''
    const info = gl.getExtension('WEBGL_debug_renderer_info')
    const name = String(gl.getParameter(info ? info.UNMASKED_RENDERER_WEBGL : gl.RENDERER) || '')
    gl.getExtension('WEBGL_lose_context')?.loseContext()
    return name
  } catch {
    return ''
  }
}

// The server's capture: headless and automated, usually without a GPU.
function isCaptureLike(gpu) {
  const nav = globalThis.navigator || {}
  return nav.webdriver === true ||
    /HeadlessChrome/.test(nav.userAgent || '') ||
    /SwiftShader|llvmpipe|softpipe|Software Rasterizer|Basic Render/i.test(gpu)
}

export function chooseTier(config = {}) {
  const params = new URLSearchParams(globalThis.location?.search || '')
  const asked = String(config.quality || params.get('quality') || '').toLowerCase()
  const gpu = rendererName()
  const capture = isCaptureLike(gpu)
  if (TIERS[asked]) return { ...TIERS[asked], reason: 'asked', capture, gpu }
  if (capture) return { ...TIERS.low, pixelRatio: 1, reason: 'software or automated browser', capture, gpu }

  const nav = globalThis.navigator || {}
  const ua = nav.userAgent || ''
  const phone = nav.userAgentData?.mobile ?? /Android|iPhone|iPad|iPod|Mobile/i.test(ua)
  const tablet = /Macintosh/.test(ua) && nav.maxTouchPoints > 1 // iPadOS reports a desktop Safari
  const cores = nav.hardwareConcurrency || 4
  const memory = nav.deviceMemory || 4 // Chromium only, and capped at 8
  if (phone || tablet) {
    const strong = memory >= 6 && cores >= 8
    return { ...(strong ? TIERS.medium : TIERS.low), reason: 'phone or tablet', capture, gpu }
  }
  if (cores <= 2 || memory <= 2) return { ...TIERS.low, reason: 'low-end PC', capture, gpu }
  if (cores <= 4 || memory <= 4) return { ...TIERS.medium, reason: 'mid-range PC', capture, gpu }
  return { ...TIERS.high, reason: 'PC', capture, gpu }
}

// Keeps the frame time near budget by scaling the resolution between 60% and 100% of the tier's pixel ratio.
// The capture renders single frames on demand, so it keeps a fixed resolution.
export function createResolutionGovernor(tier) {
  let scale = 1
  let time = 0
  let frames = 0
  return {
    get scale() {
      return scale
    },
    // Returns true when the scale changed.
    sample(dt) {
      if (tier.capture || !(dt > 0)) return false
      time += dt
      frames += 1
      if (time < 2) return false
      const frameTime = time / frames
      time = 0
      frames = 0
      const before = scale
      if (frameTime > 1 / 40) scale = Math.max(0.6, scale - 0.15)
      else if (frameTime < 1 / 57) scale = Math.min(1, scale + 0.1)
      return scale !== before
    },
  }
}
