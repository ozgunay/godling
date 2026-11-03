import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import { createAim } from '../src/aim.js'
import { canvas, key, pointer } from './events.js'

function setup(godlingAt = new THREE.Vector3(0, 0, 0)) {
  const scene = new THREE.Scene()
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(200, 200).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial())
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(200, 200).rotateX(-Math.PI / 2).translate(0, 5, 0),
    new THREE.MeshBasicMaterial({ transparent: true })) // see-through things are never aimed at
  scene.add(ground, glass)
  scene.updateMatrixWorld()
  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000)
  camera.position.set(0, 50, 0.001)
  camera.lookAt(0, 0, 0)
  camera.updateMatrixWorld()
  const c = canvas()
  const calls = { hover: [], aimed: [], cancel: 0 }
  const aim = createAim(THREE, scene, camera, c, {
    godling: () => godlingAt,
    onHover: (spot) => calls.hover.push(spot),
    onAimed: (spot) => calls.aimed.push(spot),
    onCancel: () => { calls.cancel += 1 },
  })
  const reticle = scene.children.find((o) => o.isGroup)
  return { aim, c, calls, reticle, scene, camera }
}

describe('aiming a sky power', () => {
  it('does nothing until a power is picked', () => {
    const { c, calls, reticle } = setup()
    c.dispatchEvent(pointer('pointermove', { x: 50, y: 50 }))
    c.dispatchEvent(pointer('pointerdown', { x: 50, y: 50 }))
    c.dispatchEvent(pointer('pointerup', { x: 50, y: 50 }))
    expect(calls.hover).toEqual([])
    expect(reticle.visible).toBe(false)
  })

  it('follows the pointer and reports a click', () => {
    const { aim, c, calls, reticle } = setup()
    aim.start('Meteor')
    expect(aim.active).toBe(true)
    expect(c.style.cursor).toBe('crosshair')
    c.dispatchEvent(pointer('pointermove', { x: 50, y: 50 }))
    expect(reticle.visible).toBe(true)
    expect(calls.hover[0].atGodling).toBe(true)
    expect(reticle.children[1].material.color.getHex()).toBe(0xec4b4f) // a meteor stays red, even at Godling
    expect(reticle.children[1].scale.x).toBe(7)
    c.dispatchEvent(pointer('pointerdown', { x: 80, y: 50 }))
    c.dispatchEvent(pointer('pointerup', { x: 82, y: 51 }))
    expect(calls.aimed).toHaveLength(1)
    expect(calls.aimed[0].power).toBe('Meteor')
    expect(calls.aimed[0].x).toBeGreaterThan(5)
    expect(aim.active).toBe(false)
    expect(reticle.visible).toBe(false)
    expect(c.style.cursor).toBe('')
  })

  it('turns teal where a gift would land at Godling, and a drag is not a click', () => {
    const { aim, c, calls, reticle } = setup()
    aim.start('Stone')
    c.dispatchEvent(pointer('pointerdown', { x: 50, y: 50 }))
    expect(reticle.children[1].material.color.getHex()).toBe(0x45d6cf)
    c.dispatchEvent(pointer('pointerup', { x: 90, y: 90 })) // dragged the camera
    expect(calls.aimed).toEqual([])
    c.dispatchEvent(pointer('pointerup', { x: 90, y: 90 })) // no press to end
    aim.start('Regrow')
    c.dispatchEvent(pointer('pointermove', { x: 95, y: 5 }))
    expect(reticle.children[1].material.color.getHex()).toBe(0x63b544)
  })

  it('misses the sky, and Escape cancels', () => {
    const { aim, c, calls, camera } = setup(null)
    camera.position.set(0, 50, 0)
    camera.lookAt(100, 50, 0) // looking at the horizon: nothing under the pointer
    camera.updateMatrixWorld()
    aim.start('Lightning')
    c.dispatchEvent(pointer('pointermove', { x: 50, y: 50 }))
    c.dispatchEvent(pointer('pointerdown', { x: 50, y: 50 }))
    c.dispatchEvent(pointer('pointerup', { x: 50, y: 50 }))
    expect(calls.hover).toEqual([])
    expect(calls.aimed).toEqual([])
    dispatchEvent(key('keydown', 'KeyA', { key: 'a' }))
    expect(aim.active).toBe(true)
    dispatchEvent(key('keydown', 'Escape', { key: 'Escape' }))
    expect(aim.active).toBe(false)
    expect(calls.cancel).toBe(1)
    dispatchEvent(key('keydown', 'Escape', { key: 'Escape' })) // nothing to cancel now
    expect(calls.cancel).toBe(1)
  })

  it('works without the screen listening', () => {
    const scene = new THREE.Scene()
    scene.add(new THREE.Mesh(new THREE.PlaneGeometry(10, 10).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial()))
    scene.updateMatrixWorld()
    const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 100)
    camera.position.set(0, 20, 0.001)
    camera.lookAt(0, 0, 0)
    camera.updateMatrixWorld()
    const c = canvas()
    const aim = createAim(THREE, scene, camera, c, { godling: () => null })
    aim.start('Log')
    c.dispatchEvent(pointer('pointerdown', { x: 50, y: 50 }))
    c.dispatchEvent(pointer('pointerup', { x: 50, y: 50 }))
    aim.start('Log')
    dispatchEvent(key('keydown', 'Escape', { key: 'Escape' }))
    expect(aim.active).toBe(false)
    vi.restoreAllMocks()
  })
})
