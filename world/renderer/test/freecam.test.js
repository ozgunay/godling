import * as THREE from 'three'
import { afterEach, describe, expect, it } from 'vitest'
import { createFreeCamera } from '../src/freecam.js'
import { canvas, key, pointer, wheel } from './events.js'

// Each free camera listens on the window for good: one left flying would take the next test's keys.
const made = []
afterEach(() => made.splice(0).forEach((free) => free.leave()))

function setup() {
  const camera = new THREE.PerspectiveCamera()
  const c = canvas()
  const free = createFreeCamera(THREE, camera, c)
  made.push(free)
  return { camera, c, free }
}

const fly = (free, seconds) => {
  for (let t = 0; t < seconds; t += 0.05) free.update(0.05)
}

describe('free camera', () => {
  it('places a camera that was never placed above and behind the target', () => {
    const { camera, free } = setup()
    expect(free.active).toBe(false)
    free.update(0.1) // inactive: nothing
    free.enter(new THREE.Vector3(10, 0, 10))
    expect(free.active).toBe(true)
    expect(camera.position.toArray()).toEqual([10, 18, -8])
    free.enter(new THREE.Vector3(99, 0, 99)) // already flying: no jump
    expect(camera.position.x).toBe(10)
  })

  it('flies with the keys along where it looks, faster with Shift, and stops on letting go', () => {
    const { camera, free } = setup()
    camera.position.set(0, 20, 0)
    free.enter()
    dispatchEvent(key('keydown', 'KeyW'))
    fly(free, 1)
    const slow = camera.position.length()
    dispatchEvent(key('keydown', 'ShiftLeft'))
    fly(free, 1)
    expect(camera.position.length() - slow).toBeGreaterThan(slow * 1.5)
    dispatchEvent(key('keyup', 'KeyW'))
    dispatchEvent(key('keyup', 'ShiftLeft'))
    dispatchEvent(key('keydown', 'KeyE'))
    fly(free, 0.5)
    expect(camera.position.y).toBeGreaterThan(20)
    dispatchEvent(new Event('blur'))
    const still = camera.position.clone()
    fly(free, 2)
    expect(camera.position.distanceTo(still)).toBeLessThan(3) // only the speed left over
  })

  it('ignores keys when typing, with modifiers, or for other keys; the screen forwards keys too', () => {
    const { camera, free } = setup()
    camera.position.set(0, 20, 0)
    free.enter()
    const input = document.createElement('input')
    document.body.append(input)
    input.dispatchEvent(key('keydown', 'KeyW'))
    dispatchEvent(key('keydown', 'KeyW', { ctrlKey: true }))
    dispatchEvent(key('keydown', 'KeyZ'))
    fly(free, 1)
    expect(camera.position.toArray()).toEqual([0, 20, 0])
    free.key('KeyZ', true) // not a flying key
    free.key('KeyD', true)
    free.key('KeyW', true)
    fly(free, 1)
    expect(camera.position.x).toBeGreaterThan(5)
    free.key('all')
    free.key('KeyQ', true)
    fly(free, 20)
    expect(camera.position.y).toBe(1.2) // never under the sea
    free.key('KeyQ', false)
    free.key('KeyE', true)
    fly(free, 30)
    expect(camera.position.y).toBe(160)
  })

  it('keeps within reach of the island', () => {
    const { camera, free } = setup()
    camera.position.set(590, 20, 0)
    free.enter()
    free.key('KeyW', true)
    free.key('ShiftRight', true)
    fly(free, 20)
    expect(Math.hypot(camera.position.x, camera.position.z)).toBeCloseTo(600, 3)
  })

  it('looks round with a drag, and dollies with the wheel and a pinch', () => {
    const { camera, c, free } = setup()
    camera.position.set(0, 20, 0)
    c.dispatchEvent(pointer('pointerdown', { x: 0 })) // not flying: ignored
    free.enter()
    const before = camera.quaternion.clone()
    c.dispatchEvent(pointer('pointerdown', { x: 10, y: 10 }))
    c.dispatchEvent(pointer('pointermove', { x: 60, y: 30 }))
    c.dispatchEvent(pointer('pointermove', { x: 70, id: 9 })) // another pointer: not the drag
    c.dispatchEvent(pointer('pointerup', { x: 60, y: 30 }))
    free.update(0.016)
    expect(camera.quaternion.equals(before)).toBe(false)
    const start = camera.position.clone()
    c.dispatchEvent(wheel(-100))
    expect(camera.position.distanceTo(start)).toBeCloseTo(2)
    free.key('ShiftLeft', true)
    c.dispatchEvent(wheel(-100))
    expect(camera.position.distanceTo(start)).toBeCloseTo(8)
    free.key('all')
    // one finger looks, two pinch
    c.dispatchEvent(pointer('pointerdown', { x: 0, y: 0, id: 2, kind: 'touch' }))
    c.dispatchEvent(pointer('pointermove', { x: 30, y: 0, id: 2, kind: 'touch' }))
    c.dispatchEvent(pointer('pointerdown', { x: 100, y: 0, id: 3, kind: 'touch' }))
    const pinched = camera.position.clone()
    c.dispatchEvent(pointer('pointermove', { x: 150, y: 0, id: 3, kind: 'touch' }))
    expect(camera.position.distanceTo(pinched)).toBeCloseTo(4)
    c.dispatchEvent(pointer('pointercancel', { id: 2, kind: 'touch' }))
    c.dispatchEvent(pointer('pointerup', { id: 3, kind: 'touch' }))
    free.leave()
    c.dispatchEvent(pointer('pointermove', { x: 0 }))
    c.dispatchEvent(wheel(-100))
    dispatchEvent(key('keydown', 'KeyW'))
    expect(free.active).toBe(false)
  })
})
