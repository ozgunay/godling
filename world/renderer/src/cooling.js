import * as THREE from 'three'

// A meteor's stone cools (main.lua sky.meteor.cool, the user's wish of 2026-11-05). The world gives the stone and its
// crater a Heat: 1 white-hot as it falls and lands, down to 0, cold, about a day of the island's clock later, in steps
// of 0.05, fast at first. Drawn here:
// - the stone's cracks (meteor.glb's emissive "ember" material) burn yellow-white, then orange, then a dull red, and
//   close up into dark veins with a metal sheen: cold, it is a plain dark meteorite;
// - its crater's scorch (crater.glb's dark vertex colours, on the burnt ground) fades towards the sand's colour, but
//   not all the way: the crater still says a meteor fell there. The charred chunks lying in it stay as they are.
// A part without Heat (a replay from before stones cooled) is drawn as its model is.
// Each step of heat is its own material or geometry, made once and shared, so the instancer draws every stone (or
// crater) of the same heat in one draw call.

export const HEAT_STEPS = 20 // the world's steps of 0.05
export const SCORCH_FADE = 0.65 // how much of the scorch is gone once the stone is cold

const SAND = new THREE.Color().setRGB(0.64, 0.56, 0.45, THREE.SRGBColorSpace) // art/build_props.py's sand_dark
const SCORCH = new THREE.Color().setRGB(0.32, 0.28, 0.25, THREE.SRGBColorSpace) // and its scorch
const luma = (r, g, b) => 0.2126 * r + 0.7152 * g + 0.0722 * b
const SAND_LUMA = luma(SAND.r, SAND.g, SAND.b)
const SCORCH_LUMA = luma(SCORCH.r, SCORCH.g, SCORCH.b)
// Cold cracks: dark grey metal, a shade off the rock's own colour (meteor.glb paints only the rock; its cracks' vertex
// colours are white, so this is the colour they show).
const COLD_VEIN = new THREE.Color(0.1, 0.095, 0.09)

// The step of heat an entity is drawn at (0 cold to HEAT_STEPS white-hot), or null when the world gave it none.
export function heatStep(attributes) {
  const heat = Number(attributes?.Heat)
  if (attributes?.Heat == null || !Number.isFinite(heat)) return null
  return Math.round(Math.min(1, Math.max(0, heat)) * HEAT_STEPS)
}

// How a crack glows at heat h (0 to 1), as hot iron does: yellow-orange, orange, dull red, then not at all. Kept
// saturated: brighter, the tone mapping turned the hottest cracks flat white by day, stripes rather than a glow.
export function glowAt(h, out = new THREE.Color()) {
  out.setRGB(1, 0.04 + 0.31 * h * h, 0.005 + 0.055 * h * h * h)
  return { color: out, intensity: h > 0 ? 1.8 * h ** 0.6 : 0 }
}

// A glowing material is the stone's cracks (meteor.glb's "ember"): anything that gives off light of its own.
const glows = (material) => Boolean(material?.emissive) && (material.emissive.r + material.emissive.g + material.emissive.b) > 0
  && (material.emissiveIntensity ?? 1) > 0

// The vertices of a geometry's largest connected piece (welded where positions meet): a crater's ground, not the
// small chunks of rock lying on it.
export function largestPiece(geometry) {
  const position = geometry.attributes.position
  const n = position.count
  const parent = new Int32Array(n).map((_, i) => i)
  const find = (i) => {
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]]
      i = parent[i]
    }
    return i
  }
  const join = (a, b) => {
    const ra = find(a)
    const rb = find(b)
    if (ra !== rb) parent[ra] = rb
  }
  const at = new Map()
  for (let i = 0; i < n; i++) {
    const key = `${position.getX(i).toFixed(4)},${position.getY(i).toFixed(4)},${position.getZ(i).toFixed(4)}`
    const same = at.get(key)
    if (same == null) at.set(key, i)
    else join(i, same)
  }
  const index = geometry.index
  const corners = index ? index.count : n
  for (let k = 0; k + 2 < corners; k += 3) {
    const a = index ? index.getX(k) : k
    join(a, index ? index.getX(k + 1) : k + 1)
    join(a, index ? index.getX(k + 2) : k + 2)
  }
  const sizes = new Map()
  let best = -1
  let bestSize = 0
  for (let i = 0; i < n; i++) {
    const r = find(i)
    const size = (sizes.get(r) || 0) + 1
    sizes.set(r, size)
    if (size > bestSize) {
      best = r
      bestSize = size
    }
  }
  const out = new Uint8Array(n)
  for (let i = 0; i < n; i++) out[i] = find(i) === best ? 1 : 0
  return out
}

export function createCooling({ onMaterial } = {}) {
  const variants = new Map() // `${source uuid}@${step}` -> material or geometry
  const grounds = new WeakMap() // a crater's geometry -> its ground's vertices

  function ember(material, step) {
    const key = `${material.uuid}@heat${step}`
    let m = variants.get(key)
    if (m) return m
    m = material.clone()
    m.name = `${material.name || 'ember'}@heat${step}`
    const h = step / HEAT_STEPS
    const { color, intensity } = glowAt(h, m.emissive)
    m.emissive = color
    m.emissiveIntensity = intensity
    // The crack's own colour: its glowing red while hot, then dark grey metal, which catches the sun.
    const hot = THREE.MathUtils.smoothstep(h, 0, 0.35)
    m.color.copy(COLD_VEIN).lerp(material.color, hot)
    m.metalness = THREE.MathUtils.lerp(0.6, material.metalness ?? 0, hot)
    m.roughness = THREE.MathUtils.lerp(0.45, material.roughness ?? 1, hot)
    variants.set(key, m)
    onMaterial?.(m)
    return m
  }

  function scorch(geometry, step) {
    const key = `${geometry.uuid}@scorch${step}`
    let g = variants.get(key)
    if (g) return g
    const fade = SCORCH_FADE * (1 - step / HEAT_STEPS)
    if (!grounds.has(geometry)) grounds.set(geometry, largestPiece(geometry))
    const ground = grounds.get(geometry)
    g = geometry.clone()
    const colors = g.attributes.color
    for (let i = 0; i < colors.count; i++) {
      if (!ground[i]) continue
      const r = colors.getX(i)
      const gg = colors.getY(i)
      const b = colors.getZ(i)
      // The darker than the sand, the more it fades: scorch most, the sand thrown up on the rim not at all.
      const dark = THREE.MathUtils.clamp((SAND_LUMA - luma(r, gg, b)) / (SAND_LUMA - SCORCH_LUMA), 0, 1)
      const k = fade * dark
      colors.setXYZ(i, r + (SAND.r - r) * k, gg + (SAND.g - gg) * k, b + (SAND.b - b) * k)
    }
    colors.needsUpdate = true
    variants.set(key, g)
    return g
  }

  return {
    // A model's part as drawn at this step of heat: { geometry, material, suffix } (the suffix sets its instancing
    // group apart), or the part as it is when heat does not change it.
    variant(part, role, step) {
      if (step == null) return { geometry: part.geometry, material: part.material, suffix: '' }
      if (role === 'Crater' && part.geometry?.attributes?.color) {
        return { geometry: scorch(part.geometry, step), material: part.material, suffix: `@scorch${step}` }
      }
      if (role !== 'Crater' && !Array.isArray(part.material) && glows(part.material)) {
        return { geometry: part.geometry, material: ember(part.material, step), suffix: `@heat${step}` }
      }
      return { geometry: part.geometry, material: part.material, suffix: '' }
    },
    info: () => ({ variants: variants.size }),
    dispose() {
      for (const v of variants.values()) v.dispose()
      variants.clear()
    },
  }
}
