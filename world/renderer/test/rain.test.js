import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createRain } from '../src/rain.js'

describe('rain', () => {
  it('falls in a box round the camera, more and slanted in a storm', () => {
    const scene = new THREE.Scene()
    const rain = createRain(scene, { name: 'low' })
    const lines = scene.children[0]
    const camera = new THREE.PerspectiveCamera()
    camera.position.set(500, 20, -300)
    rain.update({ rain: 0, time: 0, camera })
    expect(lines.visible).toBe(false)
    rain.update({ rain: 0.5, time: 0.05, camera, wind: new THREE.Vector2(1, -1) })
    expect(lines.visible).toBe(true)
    expect(lines.material.opacity).toBeCloseTo(0.525)
    expect(lines.geometry.drawRange.count).toBe(2500)
    const p = lines.geometry.attributes.position.array
    expect(Math.abs(p[0] - camera.position.x)).toBeLessThanOrEqual(35)
    expect(p[3]).toBeLessThan(p[0]) // the streak trails back against the wind
    rain.update({ rain: 1, time: 10, camera }) // a long gap is capped; no wind
    expect(lines.geometry.drawRange.count).toBe(5000)
    rain.dispose()
    expect(scene.children).toHaveLength(0)
  })

  it('has more drops on better tiers', () => {
    for (const [name, count] of [['medium', 4500], ['high', 7000]]) {
      const scene = new THREE.Scene()
      createRain(scene, { name }).update({ rain: 1, time: 0.1, camera: new THREE.PerspectiveCamera() })
      expect(scene.children[0].geometry.drawRange.count).toBe(count * 2)
    }
  })
})
