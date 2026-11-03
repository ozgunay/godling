import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createTerrain } from '../src/terrain.js'

// Voxels as the patched server sends them: x, y, z, material index, solid and liquid occupancy (0-255).
const terrain = (revision, voxels, extra = {}) => ({ revision, voxel_size: 4, materials: ['Grass', 'Water', 'Rock', 'Unobtainium'], voxels, ...extra })

describe('voxel terrain', () => {
  it('builds open faces only, grass with earth sides, and water beside it', () => {
    const scene = new THREE.Scene()
    const materials = []
    const t = createTerrain(scene, { onMaterial: (m) => materials.push(m) })
    expect(materials).toHaveLength(2)
    const [solid, water] = scene.children
    t.update(terrain(1, [
      0, 0, 0, 0, 255, 0, // grass
      1, 0, 0, 2, 255, 0, // rock beside it: the faces between them are not drawn
      0, 2, 0, 3, 200, 0, // an unknown material: grey
      2, 0, 0, 1, 0, 255, // water
      3, 0, 0, 1, 10, 10, // mostly empty: nothing
    ]))
    expect(solid.geometry.attributes.position.count).toBe((5 + 5 + 6) * 6)
    expect(water.geometry.attributes.position.count).toBe(5 * 6) // its side against the rock is hidden
    const colors = solid.geometry.attributes.color.array
    expect(colors.some((c, i) => i % 3 === 1 && c > colors[i - 1] + 0.1)).toBe(true) // something green
    t.update(terrain(1, [])) // the same revision: kept
    expect(solid.geometry.attributes.position.count).toBe(96)
  })

  it('finds the land at sea level, once per revision', () => {
    const scene = new THREE.Scene()
    const t = createTerrain(scene, {})
    t.update(terrain(7, [0, 0, 0, 0, 255, 0, 5, 9, 5, 2, 255, 0], { voxel_size: undefined }))
    const first = t.landAt(2)
    expect(first.key).toBe('terrain:7')
    expect(first.boxes).toEqual([{ center: [2, 2, 2], half: [2, 2, 2], rotation: null }])
    expect(t.landAt(2).boxes).toBe(first.boxes)
    t.update(null) // the terrain is gone: cleared once
    expect(scene.children[0].geometry.attributes.position.count).toBe(0)
    t.update(null)
    expect(t.landAt(2).boxes).toEqual([])
    t.update({ revision: 8 })
    t.dispose()
    expect(scene.children).toHaveLength(0)
  })
})
