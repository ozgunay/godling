import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createCooling, glowAt, GLOWS_ABOVE, heatStep, HEAT_STEPS, largestPiece, SCORCH_FADE } from '../src/cooling.js'

// meteor.glb's glowing cracks: an emissive material, as the art pipeline exports it (art/build_props.py "ember").
const ember = () => new THREE.MeshStandardMaterial({ name: 'ember', color: new THREE.Color(1, 0.133, 0.007),
  emissive: new THREE.Color(1, 0.133, 0.007), emissiveIntensity: 1.2, roughness: 0.6, vertexColors: true })

// A crater as crater.glb is: the ground (one welded piece, scorched in the middle, sand at the rim) and a chunk of
// charred rock lying on it, its own piece.
function crater() {
  const ground = new THREE.PlaneGeometry(8, 8, 4, 4).rotateX(-Math.PI / 2)
  const chunk = new THREE.BoxGeometry(0.3, 0.3, 0.3).translate(0.5, 0.2, 0.5)
  const scorch = new THREE.Color().setRGB(0.32, 0.28, 0.25, THREE.SRGBColorSpace)
  const sand = new THREE.Color().setRGB(0.84, 0.75, 0.59, THREE.SRGBColorSpace)
  const paint = (g, colorAt) => {
    const colors = []
    for (let i = 0; i < g.attributes.position.count; i++) {
      const c = colorAt(g.attributes.position.getX(i), g.attributes.position.getZ(i))
      colors.push(c.r, c.g, c.b)
    }
    g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
  }
  paint(ground, (x, z) => (Math.hypot(x, z) < 2.5 ? scorch : sand))
  paint(chunk, () => scorch)
  const merged = new THREE.BufferGeometry()
  const n = ground.attributes.position.count
  for (const name of ['position', 'normal', 'color']) {
    merged.setAttribute(name, new THREE.Float32BufferAttribute([...ground.attributes[name].array, ...chunk.attributes[name].array], 3))
  }
  merged.setIndex([...ground.index.array, ...chunk.index.array.map((i) => i + n)])
  return { geometry: merged, groundCount: n }
}

describe('a meteor\'s stone cooling', () => {
  it('reads the world\'s Heat as a step, or none when the world gave none', () => {
    expect(heatStep(undefined)).toBeNull()
    expect(heatStep({})).toBeNull()
    expect(heatStep({ Heat: 'hot' })).toBeNull()
    expect(heatStep({ Heat: 1 })).toBe(HEAT_STEPS)
    expect(heatStep({ Heat: 0.25 })).toBe(5)
    expect(heatStep({ Heat: 0.049 })).toBe(1)
    expect(heatStep({ Heat: 0 })).toBe(0)
    expect(heatStep({ Heat: 3 })).toBe(HEAT_STEPS)
    expect(heatStep({ Heat: -1 })).toBe(0)
  })

  it('glows as hot iron does: yellow-orange, orange, dull red, then not at all once it may be held', () => {
    const white = glowAt(1)
    const orange = glowAt(0.5)
    const red = glowAt(0.2)
    expect(glowAt(GLOWS_ABOVE).intensity).toBe(0) // the world lets it be held from here (main.lua sky.iron)
    expect(glowAt(GLOWS_ABOVE + 0.05).intensity).toBeGreaterThan(0)
    expect(white.color.g).toBeGreaterThan(orange.color.g)
    expect(orange.color.g).toBeGreaterThan(red.color.g)
    expect(white.color.b).toBeGreaterThan(red.color.b)
    expect(white.intensity).toBeGreaterThan(orange.intensity)
    expect(orange.intensity).toBeGreaterThan(red.intensity)
    expect(red.intensity).toBeGreaterThan(0)
    expect(glowAt(0).intensity).toBe(0)
  })

  it('dims the stone\'s cracks step by step into dark metal, one shared material a step', () => {
    const made = []
    const cooling = createCooling({ onMaterial: (m) => made.push(m) })
    const source = { geometry: new THREE.BoxGeometry(), material: ember() }
    const hot = cooling.variant(source, 'Stone', HEAT_STEPS)
    const warm = cooling.variant(source, 'Stone', 4)
    const cold = cooling.variant(source, 'Stone', 0)
    expect(hot.suffix).toBe('@heat20')
    expect(cold.suffix).toBe('@heat0')
    expect(hot.geometry).toBe(source.geometry)
    expect(hot.material).not.toBe(source.material)
    expect(hot.material.emissiveIntensity).toBeGreaterThan(source.material.emissiveIntensity) // fresh: hotter than the model
    expect(warm.material.emissiveIntensity).toBeLessThan(hot.material.emissiveIntensity)
    expect(cold.material.emissiveIntensity).toBe(0)
    expect(cold.material.metalness).toBeCloseTo(0.6)
    expect(cold.material.color.r).toBeLessThan(0.15) // dark grey metal, near the rock's own colour
    expect(hot.material.color.g).toBeCloseTo(source.material.color.g) // hot: its own glowing red
    expect(source.material.emissiveIntensity).toBe(1.2) // the model's own is left as it is
    expect(cooling.variant(source, 'Stone', 0).material).toBe(cold.material) // made once
    expect(made).toHaveLength(3) // each lit like the island's others (the shadows' cascades)
    expect(cooling.info().variants).toBe(3)
  })

  it('leaves alone what heat does not change, and what the world gave no heat', () => {
    const cooling = createCooling()
    const rock = { geometry: new THREE.BoxGeometry(), material: new THREE.MeshStandardMaterial() }
    expect(cooling.variant(rock, 'Stone', 3)).toEqual({ geometry: rock.geometry, material: rock.material, suffix: '' })
    const glowing = { geometry: new THREE.BoxGeometry(), material: ember() }
    expect(cooling.variant(glowing, 'Stone', null).material).toBe(glowing.material)
    const many = { geometry: new THREE.BoxGeometry(), material: [ember(), ember()] }
    expect(cooling.variant(many, 'Stone', 3).suffix).toBe('')
    const plainCrater = { geometry: new THREE.BoxGeometry(), material: new THREE.MeshStandardMaterial() } // no colours
    expect(cooling.variant(plainCrater, 'Crater', 3).suffix).toBe('')
    expect(cooling.info().variants).toBe(0)
  })

  it('finds a crater\'s ground: its largest piece, welded where positions meet', () => {
    const { geometry, groundCount } = crater()
    const ground = largestPiece(geometry)
    expect([...ground.slice(0, groundCount)].every((v) => v === 1)).toBe(true)
    expect([...ground.slice(groundCount)].every((v) => v === 0)).toBe(true)
    const soup = new THREE.BoxGeometry().toNonIndexed() // no index: welded by position alone, one piece
    expect(largestPiece(soup).every((v) => v === 1)).toBe(true)
  })

  it('fades a crater\'s scorch towards the sand as the stone cools, but not its chunks or its sandy rim', () => {
    const cooling = createCooling()
    const { geometry, groundCount } = crater()
    const source = { geometry, material: new THREE.MeshStandardMaterial({ vertexColors: true }) }
    const centre = 12 // the plane's middle vertex: scorched
    const corner = 0 // its corner: sand
    const chunk = groundCount // the chunk's first vertex: scorched, but a rock
    const before = geometry.attributes.color
    const hot = cooling.variant(source, 'Crater', HEAT_STEPS)
    const cold = cooling.variant(source, 'Crater', 0)
    expect(hot.suffix).toBe('@scorch20')
    expect(hot.material).toBe(source.material)
    expect(hot.geometry).not.toBe(geometry)
    expect(hot.geometry.attributes.color.getX(centre)).toBeCloseTo(before.getX(centre)) // just landed: all scorch
    const sand = new THREE.Color().setRGB(0.64, 0.56, 0.45, THREE.SRGBColorSpace)
    const faded = cold.geometry.attributes.color.getX(centre)
    expect(faded).toBeCloseTo(before.getX(centre) + (sand.r - before.getX(centre)) * SCORCH_FADE)
    expect(cooling.variant(source, 'Crater', 10).geometry.attributes.color.getX(centre)).toBeGreaterThan(before.getX(centre))
    expect(cooling.variant(source, 'Crater', 10).geometry.attributes.color.getX(centre)).toBeLessThan(faded)
    expect(cold.geometry.attributes.color.getX(corner)).toBeCloseTo(before.getX(corner)) // sand stays sand
    expect(cold.geometry.attributes.color.getX(chunk)).toBeCloseTo(before.getX(chunk)) // the chunks stay charred
    expect(before.getX(centre)).toBeLessThan(faded) // the model's own is left as it is
    expect(cooling.variant(source, 'Crater', 0).geometry).toBe(cold.geometry)
    cooling.dispose()
    expect(cooling.info().variants).toBe(0)
  })
})
