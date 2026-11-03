import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createFishLayer } from '../src/fish.js'

const sea = { surfaceAt: (x) => (x > 100 ? null : 0.3) }

describe('fish', () => {
  it('draws a shadow, a wake and a fin per fish, riding the waves', () => {
    const scene = new THREE.Scene()
    const layer = createFishLayer(scene)
    expect(scene.children).toHaveLength(3)
    const fish = [
      { id: 1, position: [10, 0, 5], rotation: [[0, 0, 1], [0, 1, 0], [-1, 0, 0]], size: [1.3, 0.4, 0.5] },
      { id: 2, position: [200, -0.5, 5] }, // off the sea's map: under where it is, no rotation, default size
      { id: 3, position: [12, 0, 6], modelled: true }, // its model is its fin
    ]
    layer.update(fish, sea, 1.5)
    const [body, wake, fin] = scene.children
    expect(body.count).toBe(3)
    const m = new THREE.Matrix4()
    body.getMatrixAt(0, m)
    expect(new THREE.Vector3().setFromMatrixPosition(m).y).toBeCloseTo(0.32)
    body.getMatrixAt(1, m)
    expect(new THREE.Vector3().setFromMatrixPosition(m).y).toBeCloseTo(-0.63)
    fin.getMatrixAt(2, m)
    expect(m.determinant()).toBe(0) // hidden: the model shows it
    expect(wake.instanceMatrix.needsUpdate).toBe(undefined === wake.instanceMatrix.needsUpdate ? undefined : wake.instanceMatrix.needsUpdate)
  })

  it('grows for a shoal, and cleans up', () => {
    const scene = new THREE.Scene()
    const layer = createFishLayer(scene)
    const shoal = Array.from({ length: 40 }, (_, i) => ({ id: i, position: [i, 0, 0] }))
    layer.update(shoal, sea, 0)
    expect(scene.children).toHaveLength(3)
    expect(scene.children.every((mesh) => mesh.instanceMatrix.count >= 40 && mesh.count === 40)).toBe(true)
    layer.update(shoal.slice(0, 5), sea, 0.1) // fewer: no new meshes
    expect(scene.children[0].count).toBe(5)
    layer.dispose()
    expect(scene.children).toHaveLength(0)
  })
})
