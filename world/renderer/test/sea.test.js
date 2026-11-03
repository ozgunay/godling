import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { bakeShoreDistances, createSea } from '../src/sea.js'
import { createSky } from '../src/sky.js'

const SIZE = 256

describe('shore map', () => {
  it('is 0 on land and grows out to sea', () => {
    const out = new Uint8Array(SIZE * SIZE)
    bakeShoreDistances([{ center: [0, 0, 0], half: [10, 1, 10], rotation: null }], out)
    const at = (x, z) => out[Math.floor((z + 160) / 1.25) * SIZE + Math.floor((x + 160) / 1.25)]
    expect(at(0, 0)).toBe(0)
    expect(at(20, 0)).toBeGreaterThan(0)
    expect(at(150, 150)).toBe(255) // far out: fully deep
  })

  it('turns boxes that are turned, and clips at the map edge', () => {
    const out = new Uint8Array(SIZE * SIZE)
    const quarter = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]] // long along z once turned
    bakeShoreDistances([{ center: [0, 0, 0], half: [20, 1, 2], rotation: quarter },
      { center: [158, 0, 158], half: [10, 1, 10], rotation: null }], out)
    const at = (x, z) => out[Math.floor((z + 160) / 1.25) * SIZE + Math.floor((x + 160) / 1.25)]
    expect(at(0, 15)).toBe(0)
    expect(at(15, 0)).toBeGreaterThan(0)
    expect(at(159, 159)).toBe(0)
  })
})

describe('sea', () => {
  const tier = (more = {}) => ({ seaWaves: 4, seaRipples: true, seaSegments: 8, ...more })
  const light = { direction: new THREE.Vector3(0, 1, 0), color: new THREE.Color(1, 1, 1), glint: 6 }

  it('waits for the world to say where the sea is, then follows the camera', () => {
    const scene = new THREE.Scene()
    const sky = createSky(scene, { skyClouds: 0 })
    const sea = createSea(scene, tier(), sky)
    expect(sea.mesh.visible).toBe(false)
    expect(sea.surfaceAt(0, 0)).toBeNull()
    const camera = new THREE.PerspectiveCamera()
    camera.position.set(13, 5, -21)
    const land = [{ center: [0, 0, 0], half: [30, 1, 30], rotation: null }]
    sea.update({ camera, time: 3, seaLevel: -0.5, land, landKey: 'a', light })
    expect(sea.mesh.visible).toBe(true)
    expect(sea.mesh.position.toArray()).toEqual([16, 0, -24])
    expect(sea.mesh.material.defines.SEA_RIPPLES).toBe('')
    const calm = Math.abs(sea.surfaceAt(5, 5) + 0.5)
    const open = Math.abs(sea.surfaceAt(140, 140) + 0.5)
    expect(calm).toBeLessThan(0.2)
    expect(open).toBeLessThan(0.4)
    expect(sea.surfaceAt(900, 900)).toBeCloseTo(-0.5, 1) // off the map, far from the eye: no short waves
    sea.update({ camera, time: 4, seaLevel: -0.5, land, landKey: 'a', light }) // the same land: not baked again
    sea.update({ camera, time: 5, seaLevel: null })
    expect(sea.mesh.visible).toBe(false)
    sea.dispose()
  })

  it('has fewer waves and no ripples on the low tier', () => {
    const scene = new THREE.Scene()
    const sea = createSea(scene, tier({ seaWaves: 2, seaRipples: false }), createSky(scene, { skyClouds: 0 }))
    expect(sea.mesh.material.defines).toEqual({ WAVE_COUNT: 2 })
  })
})
