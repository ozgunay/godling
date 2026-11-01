import * as THREE from 'three'
import { Sky } from 'three/addons/objects/Sky.js'

// The sky is three.js's Sky: Preetham's daylight model, with the sun's disc. One sun direction drives it, the
// sun's light and shadows, the hemisphere and ambient light, the fog, the clouds' colour and the sea's
// reflections, so another time of day is one call to setSun. The sea and the fog need the sky's colour in many
// directions, so the same model is also evaluated here on the CPU into a small sky map (azimuth x elevation),
// which costs the sea one texture read instead of the whole model per pixel.

const ATMOSPHERE = { turbidity: 2.2, rayleigh: 2.0, mieCoefficient: 0.003, mieDirectionalG: 0.8 }
// Scales the sky's radiance. Sky.js is tuned for a sunset at toneMappingExposure 0.5; at midday under this
// renderer's 1.2 (the art was checked at 1.2) it would be nearly white.
const SKY_EXPOSURE = 0.08
const TONE_EXPOSURE = 1.2
const MAP_WIDTH = 64 // azimuth
const MAP_HEIGHT = 16 // elevation, from the horizon up
// The light's direction before this sky existed; the props' colours were checked under it.
export const DEFAULT_SUN = new THREE.Vector3(30, 50, 20).normalize()

// Preetham constants, as in Sky.js.
const TOTAL_RAYLEIGH = [5.804542996261093e-6, 1.3562911419845635e-5, 3.0265902468824876e-5]
const MIE_CONST = [1.8399918514433978e14, 2.7798023919660528e14, 4.0790479543861094e14]
const CUTOFF_ANGLE = 1.6110731556870734
const STEEPNESS = 1.5
const SUN_E = 1000
const NIGHT_TINT = [0, 0.0003, 0.00075]

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))
const smoothstep = (a, b, v) => {
  const t = clamp((v - a) / (b - a), 0, 1)
  return t * t * (3 - 2 * t)
}

function atmosphereFor(sun) {
  const sunE = SUN_E * Math.max(0, 1 - Math.exp(-((CUTOFF_ANGLE - Math.acos(clamp(sun.y, -1, 1))) / STEEPNESS)))
  const sunfade = 1 - clamp(1 - Math.exp(sun.y / 450000), 0, 1)
  const rayleigh = ATMOSPHERE.rayleigh - (1 - sunfade)
  const mie = 0.434 * (0.2 * ATMOSPHERE.turbidity * 10e-18) * ATMOSPHERE.mieCoefficient
  return {
    sun,
    sunE,
    betaR: TOTAL_RAYLEIGH.map((v) => v * rayleigh),
    betaM: MIE_CONST.map((v) => v * mie),
    g: ATMOSPHERE.mieDirectionalG,
  }
}

// What fraction of each primary gets through the air along a direction (Sky.js's Fex).
function extinction(a, dy, out) {
  const zenith = Math.acos(Math.max(0, dy))
  const inverse = 1 / (Math.cos(zenith) + 0.15 * Math.pow(93.885 - (zenith * 180) / Math.PI, -1.253))
  for (let i = 0; i < 3; i++) out[i] = Math.exp(-(a.betaR[i] * 8.4e3 + a.betaM[i] * 1.25e3) * inverse)
  return out
}

// The sky's linear radiance along (dx, dy, dz) without the sun's disc, scaled like the dome: Sky.js's fragment
// shader, line for line.
function radiance(a, dx, dy, dz, out) {
  const fex = extinction(a, dy, [0, 0, 0])
  const cosTheta = dx * a.sun.x + dy * a.sun.y + dz * a.sun.z
  const rPhase = (3 / (16 * Math.PI)) * (1 + Math.pow(cosTheta * 0.5 + 0.5, 2))
  const g2 = a.g * a.g
  const mPhase = (1 / (4 * Math.PI)) * ((1 - g2) / Math.pow(1 - 2 * a.g * cosTheta + g2, 1.5))
  const low = clamp(Math.pow(1 - a.sun.y, 5), 0, 1)
  for (let i = 0; i < 3; i++) {
    const scatter = (a.betaR[i] * rPhase + a.betaM[i] * mPhase) / (a.betaR[i] + a.betaM[i])
    let lin = Math.pow(a.sunE * scatter * (1 - fex[i]), 1.5)
    lin *= 1 + (Math.sqrt(a.sunE * scatter * fex[i]) - 1) * low
    out[i] = ((lin + 0.1 * fex[i]) * 0.04 + NIGHT_TINT[i]) * SKY_EXPOSURE
  }
  return out
}

// three.js's ACESFilmicToneMapping, so the fog (mixed in after tone mapping) can match the sky it fades into.
function acesFilmic(rgb, exposure) {
  const c = rgb.map((v) => (v * exposure) / 0.6)
  const a = [
    0.59719 * c[0] + 0.35458 * c[1] + 0.04823 * c[2],
    0.076 * c[0] + 0.90834 * c[1] + 0.01566 * c[2],
    0.0284 * c[0] + 0.13383 * c[1] + 0.83777 * c[2],
  ]
  const f = a.map((v) => (v * (v + 0.0245786) - 0.000090537) / (v * (0.983729 * v + 0.432951) + 0.238081))
  return [
    clamp(1.60475 * f[0] - 0.53108 * f[1] - 0.07367 * f[2], 0, 1),
    clamp(-0.10208 * f[0] + 1.10813 * f[1] - 0.00605 * f[2], 0, 1),
    clamp(-0.00327 * f[0] - 0.07276 * f[1] + 1.07602 * f[2], 0, 1),
  ]
}

// Hours (0-24) to a sun direction: up at 6, highest at 13, down at 20; +X east, +Z south.
export function sunForHour(hour) {
  const day = ((hour - 6) / 14) * Math.PI
  const elevation = Math.sin(day) * THREE.MathUtils.degToRad(62)
  const azimuth = Math.PI * 0.5 - day // east, through south, to west
  return new THREE.Vector3(
    Math.cos(elevation) * Math.sin(azimuth),
    Math.sin(elevation),
    Math.cos(elevation) * Math.cos(azimuth),
  )
}

export function createSky(scene, tier) {
  const dome = new Sky()
  const uniforms = dome.material.uniforms
  const shader = dome.material.fragmentShader
  const exposed = shader
    .replace('uniform float time;', 'uniform float time;\nuniform float skyExposure;')
    .replace('gl_FragColor = vec4( texColor, 1.0 );', 'gl_FragColor = vec4( texColor * skyExposure, 1.0 );')
  if (exposed === shader || !exposed.includes('texColor * skyExposure')) console.warn('sky: exposure hook not found')
  dome.material.fragmentShader = exposed
  uniforms.skyExposure = { value: SKY_EXPOSURE }
  uniforms.turbidity.value = ATMOSPHERE.turbidity
  uniforms.rayleigh.value = ATMOSPHERE.rayleigh
  uniforms.mieCoefficient.value = ATMOSPHERE.mieCoefficient
  uniforms.mieDirectionalG.value = ATMOSPHERE.mieDirectionalG
  uniforms.cloudCoverage.value = tier.skyClouds
  dome.scale.setScalar(2000) // inside the camera's far plane; the shader puts it at the far plane anyway
  dome.frustumCulled = false
  dome.renderOrder = -1
  scene.add(dome)

  // The sky map: half floats, so the bright sky near the sun survives for the sea's reflection.
  const data = new Uint16Array(MAP_WIDTH * MAP_HEIGHT * 4)
  const map = new THREE.DataTexture(data, MAP_WIDTH, MAP_HEIGHT, THREE.RGBAFormat, THREE.HalfFloatType)
  map.wrapS = THREE.RepeatWrapping
  map.wrapT = THREE.ClampToEdgeWrapping
  map.magFilter = THREE.LinearFilter
  map.minFilter = THREE.LinearFilter
  map.colorSpace = THREE.NoColorSpace

  const sun = new THREE.Vector3()
  const sunColor = new THREE.Color() // the sunlight's tint (brightest channel 1)
  const zenith = new THREE.Color()
  const fogColor = new THREE.Color()
  let daylight = 1 // 0 at night, 1 by day
  const sample = [0, 0, 0]

  function setSun(direction) {
    if (sun.distanceToSquared(direction) < 1e-8 && map.version > 0) return false
    sun.copy(direction).normalize()
    uniforms.sunPosition.value.copy(sun)
    const atmosphere = atmosphereFor(sun)

    for (let j = 0; j < MAP_HEIGHT; j++) {
      const elevation = ((j + 0.5) / MAP_HEIGHT) * Math.PI * 0.5
      for (let i = 0; i < MAP_WIDTH; i++) {
        const phi = ((i + 0.5) / MAP_WIDTH - 0.5) * Math.PI * 2 // the sea shader's atan(z, x)
        radiance(atmosphere, Math.cos(elevation) * Math.cos(phi), Math.sin(elevation), Math.cos(elevation) * Math.sin(phi), sample)
        const o = (j * MAP_WIDTH + i) * 4
        data[o] = THREE.DataUtils.toHalfFloat(sample[0])
        data[o + 1] = THREE.DataUtils.toHalfFloat(sample[1])
        data[o + 2] = THREE.DataUtils.toHalfFloat(sample[2])
        data[o + 3] = THREE.DataUtils.toHalfFloat(1)
      }
    }
    map.needsUpdate = true

    // The fog takes the horizon's colour, averaged around, as it shows on screen.
    const horizon = [0, 0, 0]
    for (let i = 0; i < 16; i++) {
      const phi = (i / 16) * Math.PI * 2
      radiance(atmosphere, Math.cos(phi) * 0.999, 0.035, Math.sin(phi) * 0.999, sample)
      for (let c = 0; c < 3; c++) horizon[c] += sample[c] / 16
    }
    const shown = acesFilmic(horizon, TONE_EXPOSURE)
    fogColor.setRGB(shown[0], shown[1], shown[2])

    radiance(atmosphere, 0, 1, 0, sample)
    const top = Math.max(sample[0], sample[1], sample[2], 1e-6)
    zenith.setRGB(sample[0] / top, sample[1] / top, sample[2] / top)

    const fex = extinction(atmosphere, sun.y, [0, 0, 0])
    const brightest = Math.max(fex[0], fex[1], fex[2], 1e-6)
    sunColor.setRGB(fex[0] / brightest, fex[1] / brightest, fex[2] / brightest)
    daylight = smoothstep(-0.06, 0.22, sun.y)
    return true
  }

  setSun(DEFAULT_SUN)

  return {
    dome,
    map,
    sun,
    sunColor,
    zenith,
    fogColor,
    get daylight() {
      return daylight
    },
    setSun,
    update(camera, time) {
      dome.position.copy(camera.position)
      uniforms.time.value = time
    },
    dispose() {
      scene.remove(dome)
      dome.geometry.dispose()
      dome.material.dispose()
      map.dispose()
    },
  }
}
