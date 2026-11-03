import * as THREE from 'three'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createCameraShake } from '../src/shake.js'

const camera = () => {
  const c = new THREE.PerspectiveCamera()
  c.position.set(1, 2, 3)
  return c
}

describe('camera shake', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('nudges the camera for one frame and puts it back', () => {
    const shake = createCameraShake({ shake: 1 })
    const c = camera()
    shake.apply(c, 1, 0.37)
    expect(c.position.distanceTo(new THREE.Vector3(1, 2, 3))).toBeGreaterThan(0)
    expect(c.quaternion.equals(new THREE.Quaternion())).toBe(false)
    shake.restore(c)
    expect(c.position.toArray()).toEqual([1, 2, 3])
    expect(c.quaternion.equals(new THREE.Quaternion())).toBe(true)
    shake.restore(c) // nothing applied: nothing to put back
    expect(c.position.toArray()).toEqual([1, 2, 3])
  })

  it('does nothing when calm, in the capture, or below a hair', () => {
    const c = camera()
    createCameraShake({ capture: true, shake: 1 }).apply(c, 1, 1)
    createCameraShake({}).apply(c, 0.001, 1)
    expect(c.position.toArray()).toEqual([1, 2, 3])
  })

  it('shakes less for viewers who ask for reduced motion', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }))
    const reduced = createCameraShake({ shake: 1 })
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    const full = createCameraShake({ shake: 1 })
    const a = camera()
    const b = camera()
    reduced.apply(a, 1, 0.5)
    full.apply(b, 1, 0.5)
    const moved = (c) => c.position.distanceTo(new THREE.Vector3(1, 2, 3))
    expect(moved(a)).toBeCloseTo(moved(b) / 4)
  })

  it('survives a browser whose matchMedia throws', () => {
    vi.stubGlobal('matchMedia', () => { throw new Error('no media queries') })
    const c = camera()
    createCameraShake({ shake: 1 }).apply(c, 1, 0.5)
    expect(c.position.x).not.toBe(1)
  })
})
