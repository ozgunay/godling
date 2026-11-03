import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createInstancer } from '../src/instances.js'

const at = (x) => new THREE.Matrix4().makeTranslation(x, 0, 0)

describe('instancer', () => {
  it('packs slots, grows, and sends only what changed', () => {
    const scene = new THREE.Scene()
    const instancer = createInstancer(scene)
    const box = new THREE.BoxGeometry()
    const material = new THREE.MeshStandardMaterial()
    const g = instancer.group('box', box, material, { colored: true })
    expect(instancer.group('box', box, material)).toBe(g)
    const slots = []
    for (let i = 0; i < 20; i++) slots.push(instancer.add(g, at(i), i === 3 ? new THREE.Color(1, 0, 0) : null))
    expect(g.capacity).toBe(32)
    expect(scene.children).toHaveLength(1) // the grown mesh replaced the first
    expect(instancer.stats()).toEqual({ groups: 1, instances: 20 })
    instancer.flush()
    expect(g.lo).toBe(Infinity)
    instancer.remove(slots[2]) // the last one moves into its place
    expect(slots[19].index).toBe(2)
    const m = new THREE.Matrix4()
    g.mesh.getMatrixAt(2, m)
    expect(new THREE.Vector3().setFromMatrixPosition(m).x).toBe(19)
    instancer.remove(slots[18]) // the last one itself
    expect(g.count).toBe(18)
    instancer.setMatrix(slots[0], at(-1))
    instancer.setColor(slots[0], new THREE.Color(0, 1, 0))
    instancer.flush()
    expect(g.mesh.instanceMatrix.updateRanges).toHaveLength(1)
    expect(g.mesh.instanceColor.updateRanges[0].start).toBe(0)
    instancer.flush() // nothing changed since
    instancer.clear()
    expect(scene.children).toHaveLength(0)
  })

  it('leaves colour out of plain groups', () => {
    const instancer = createInstancer(new THREE.Scene())
    const g = instancer.group('plain', new THREE.BoxGeometry(), new THREE.MeshBasicMaterial(), { castShadow: false })
    const a = instancer.add(g, at(0))
    const b = instancer.add(g, at(1))
    instancer.setColor(a, new THREE.Color(1, 0, 0))
    expect(g.mesh.instanceColor).toBeNull()
    expect(g.mesh.castShadow).toBe(false)
    instancer.remove(a)
    expect(b.index).toBe(0)
    instancer.flush()
  })
})
