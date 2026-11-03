import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createFollowCamera, framingFor } from '../src/followcam.js'

// Where a point falls on the camera's screen: [across, down], each from 0 to 1.
function onScreen(camera, point) {
  camera.updateMatrixWorld()
  const p = point.clone().project(camera)
  return [(p.x + 1) / 2, (1 - p.y) / 2]
}

function setup(aspect) {
  const camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 3000)
  const follow = createFollowCamera(THREE, camera)
  camera.fov = follow.frame(aspect).fov
  camera.updateProjectionMatrix()
  return { camera, follow }
}

describe('follow camera', () => {
  it('frames a wide screen as before, a tall one wider and from further back, and blends between', () => {
    expect(framingFor(16 / 9)).toEqual({ fov: 60, distance: 20, height: 6, screenY: 0.64 })
    expect(framingFor(1)).toEqual(framingFor(16 / 9))
    expect(framingFor(390 / 844)).toEqual({ fov: 75, distance: 25, height: 9.5, screenY: 0.55 })
    const tablet = framingFor(0.75) // an upright tablet: part way
    expect(tablet.fov).toBeGreaterThan(60)
    expect(tablet.fov).toBeLessThan(75)
    expect(framingFor(NaN)).toEqual(framingFor(1))
    // a phone held upright now sees about twice as far across as it did, though its 60° saw a quarter of a desktop's
    const across = (fov, aspect) => 2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(fov) / 2) * aspect)
    const phone = 390 / 844
    expect(across(60, phone) / across(60, 16 / 9)).toBeLessThan(0.35)
    expect(across(75, phone) / across(60, phone)).toBeGreaterThan(1.3)
  })

  it('starts in place, behind the target and above it, with the target where the framing says', () => {
    const { camera, follow } = setup(390 / 844)
    const godling = new THREE.Vector3(10, 2.5, -4)
    follow.update(godling, 0.016)
    expect(camera.position.toArray()).toEqual([10, 12, -29])
    const [x, y] = onScreen(camera, godling)
    expect(x).toBeCloseTo(0.5, 6)
    expect(y).toBeCloseTo(0.55, 6)
  })

  it('keeps a wide screen\'s view as the upstream camera had it', () => {
    const { camera, follow } = setup(16 / 9)
    follow.update(new THREE.Vector3(0, 0, 0), 0.016)
    expect(camera.position.toArray()).toEqual([0, 6, -20])
    const down = new THREE.Vector3()
    camera.getWorldDirection(down)
    // upstream looked from there at a point 2.5 ahead and 3 up: about 7.6° down, along +Z
    expect(THREE.MathUtils.radToDeg(Math.asin(-down.y))).toBeCloseTo(7.6, 0)
    expect(down.z).toBeGreaterThan(0.99)
  })

  it('eases after a moving target and settles with it in frame', () => {
    const { camera, follow } = setup(390 / 844)
    const godling = new THREE.Vector3(0, 2, 0)
    follow.update(godling, 0.016)
    godling.set(12, 2, 8)
    follow.update(godling, 0.016)
    expect(camera.position.x).toBeGreaterThan(0)
    expect(camera.position.x).toBeLessThan(6) // not there at once
    for (let k = 0; k < 200; k++) follow.update(godling, 0.05)
    expect(camera.position.distanceTo(new THREE.Vector3(12, 11.5, -17))).toBeLessThan(1e-3)
    const [x, y] = onScreen(camera, godling)
    expect(x).toBeCloseTo(0.5, 3)
    expect(y).toBeCloseTo(0.55, 3)
    follow.update(godling, 0) // a frame with no time still moves on a little, never by NaN
    expect(Number.isFinite(camera.quaternion.x)).toBe(true)
  })
})
