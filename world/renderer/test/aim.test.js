import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import { createAim } from '../src/aim.js'
import { createClouds } from '../src/clouds.js'
import { canvas, key, pointer } from './events.js'

function setup(godlingAt = new THREE.Vector3(0, 0, 0), more = {}) {
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
    ...more,
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

  it('a storm\'s strike turns red on Godling, and the spots picked so far stay marked', () => {
    const { aim, c, calls, reticle, scene } = setup()
    aim.start('Storm')
    c.dispatchEvent(pointer('pointermove', { x: 50, y: 50 }))
    expect(reticle.children[1].material.color.getHex()).toBe(0xec4b4f) // a strike on Godling hurts it
    expect(reticle.children[1].scale.x).toBe(2.5)
    c.dispatchEvent(pointer('pointermove', { x: 80, y: 50 }))
    expect(reticle.children[1].material.color.getHex()).toBe(0x9cc8ff)
    c.dispatchEvent(pointer('pointerdown', { x: 80, y: 50 }))
    c.dispatchEvent(pointer('pointerup', { x: 80, y: 50 }))
    expect(calls.aimed[0].y).toBeCloseTo(0) // the ground's height, for the mark
    const before = scene.children.length
    aim.marks([{ x: 1, y: 0, z: 2 }, { x: 3, z: 4 }, { x: 'no' }])
    expect(aim.marked).toBe(2)
    expect(scene.children.length).toBe(before + 2)
    aim.marks([{ x: 1, y: 0, z: 2 }])
    expect(aim.marked).toBe(1)
    aim.marks()
    expect(aim.marked).toBe(0)
    expect(scene.children.length).toBe(before)
  })

  it('a log shows Godling\'s reach, and an aim past it comes in to the edge, where the world will drop it (ADR-029)', () => {
    const godlingAt = new THREE.Vector3(-50, 2.4, 0)
    const { aim, c, calls, reticle, scene } = setup(godlingAt)
    const step = new THREE.Mesh(new THREE.BoxGeometry(4, 6, 4).translate(10, 0, 0), new THREE.MeshBasicMaterial())
    scene.add(step) // a block standing at the edge of the reach: the ring sits on it there
    scene.updateMatrixWorld()
    const reach = scene.getObjectByName('aim-reach')
    expect(reach.visible).toBe(false)
    aim.start('Log')
    expect(reach.visible).toBe(true)
    expect([reach.position.x, reach.position.z]).toEqual([-50, 0])
    reach.geometry.computeBoundingSphere()
    expect(reach.geometry.boundingSphere.radius * reach.scale.x).toBeCloseTo(60, 5) // main.lua sky.aim.REACH
    c.dispatchEvent(pointer('pointermove', { x: 95, y: 50 })) // about 76 out from Godling
    const hovered = calls.hover.at(-1)
    expect(hovered.beyond).toBe(true)
    expect(Math.hypot(hovered.x + 50, hovered.z)).toBeCloseTo(60, 5) // on the edge
    expect(hovered.z).toBeCloseTo(0, 5) // on the line from Godling to the pointer
    expect(hovered.y).toBeCloseTo(3, 5) // on top of what stands there
    expect(reticle.position.x).toBeCloseTo(10, 5)
    c.dispatchEvent(pointer('pointermove', { x: 50, y: 50 })) // 50 out: within reach, where the pointer is
    expect(calls.hover.at(-1).beyond).toBe(false)
    expect(calls.hover.at(-1).x).toBeCloseTo(0, 5)
    c.dispatchEvent(pointer('pointerdown', { x: 95, y: 50 }))
    c.dispatchEvent(pointer('pointerup', { x: 95, y: 50 }))
    // What the viewer aimed at goes to the world, which brings it in itself (79-CDE3): its log then says when a
    // viewer aimed past the ring, and it brings it in from where Godling is when the call arrives.
    expect(calls.aimed[0]).toMatchObject({ power: 'Log', beyond: true })
    expect(calls.aimed[0].x).toBeGreaterThan(20)
    expect(calls.aimed[0].z).toBeCloseTo(0, 5)
    expect(reach.visible).toBe(false) // aimed: the ring goes with the reticle
    aim.start('Log')
    expect(reach.material.opacity).toBe(0.5) // not still lit from the aim before (79-CDE4)
    godlingAt.set(-40, 2.4, 5) // Godling walks while the viewer aims: the ring goes with it
    aim.update()
    expect([reach.position.x, reach.position.z]).toEqual([-40, 5])
    aim.stop()
    aim.update()
    expect(reach.visible).toBe(false)
    aim.start('Stone') // the other powers are as they were: no ring, and the aim is where the pointer is
    expect(reach.visible).toBe(false)
    c.dispatchEvent(pointer('pointermove', { x: 95, y: 50 }))
    expect(calls.hover.at(-1).beyond).toBe(false)
    expect(calls.hover.at(-1).x).toBeGreaterThan(20)
  })

  it('while Godling walks under a still pointer, the reticle and the words go with it (79-AB4)', () => {
    const godlingAt = new THREE.Vector3(-50, 2.4, 0)
    const { aim, c, calls, reticle } = setup(godlingAt)
    aim.start('Log')
    c.dispatchEvent(pointer('pointermove', { x: 95, y: 50 })) // about 76 out
    expect(reticle.position.x).toBeCloseTo(10, 5)
    const told = calls.hover.length
    aim.update() // nothing moved: nothing new to tell
    expect(calls.hover.length).toBe(told)
    godlingAt.set(-40, 2.4, 0)
    aim.update()
    expect(reticle.position.x).toBeCloseTo(20, 5) // still past the ring: on it, where it is now
    godlingAt.set(-30, 2.4, 0)
    aim.update()
    expect(reticle.position.x).toBeGreaterThan(25) // within reach now: under the pointer
    expect(calls.hover.at(-1).beyond).toBe(false) // and the aim bar is told
    aim.stop()
    godlingAt.set(-60, 2.4, 0)
    aim.update()
    expect(reticle.visible).toBe(false)
  })

  it('the clouds are never aimed at: the reticle stays on the ground under them (79-SWEEP1)', () => {
    const godlingAt = new THREE.Vector3(-50, 2.4, 0)
    const { aim, c, calls, scene, camera } = setup(godlingAt)
    const clouds = createClouds(scene, { clouds: 'voxel' }) // the medium and high tiers: an opaque layer
    clouds.update({ camera, time: 0, sky: { sunColor: new THREE.Color(1, 1, 1), daylight: 1, night: 0 }, rain: 0 })
    const layer = scene.children.find((o) => o.isInstancedMesh)
    expect(layer.userData.noAim).toBe(true)
    const roof = new THREE.Mesh(new THREE.PlaneGeometry(400, 400).rotateX(-Math.PI / 2).translate(0, 92, 0),
      new THREE.MeshBasicMaterial())
    roof.userData.noAim = true // anything so marked, over the whole island
    scene.add(roof)
    scene.updateMatrixWorld(true)
    aim.start('Log')
    c.dispatchEvent(pointer('pointermove', { x: 95, y: 50 }))
    expect(calls.hover.at(-1).beyond).toBe(true)
    expect(calls.hover.at(-1).y).toBeCloseTo(0, 5)
    clouds.dispose()
  })

  it("the reach is the world's, read from its Clock (79-CLEAN10)", () => {
    let reach = 45
    const godlingAt = new THREE.Vector3(-50, 2.4, 0)
    const { aim, c, calls, scene } = setup(godlingAt, { reach: () => reach })
    aim.start('Log')
    const ring = scene.getObjectByName('aim-reach')
    expect(ring.scale.x).toBeCloseTo(45, 5)
    c.dispatchEvent(pointer('pointermove', { x: 50, y: 50 })) // 50 out: past a reach of 45
    expect(calls.hover.at(-1).beyond).toBe(true)
    expect(Math.hypot(calls.hover.at(-1).x + 50, calls.hover.at(-1).z)).toBeCloseTo(45, 5)
    reach = undefined // nothing heard yet: 60
    aim.update()
    expect(ring.scale.x).toBeCloseTo(60, 5)
  })

  it('a log aimed with Godling out of sight is taken as it is', () => {
    const { aim, c, calls, scene } = setup(null)
    aim.start('Log')
    aim.update()
    expect(scene.getObjectByName('aim-reach').visible).toBe(false)
    c.dispatchEvent(pointer('pointermove', { x: 95, y: 50 }))
    expect(calls.hover.at(-1).beyond).toBe(false)
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
