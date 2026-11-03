import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createFires } from '../src/fire.js'

describe('fires', () => {
  it('stands flames and smoke on the log, and lights the nearest ones', () => {
    const scene = new THREE.Scene()
    const fires = createFires(scene, { smokePuffs: 8, fireLights: 2 })
    const lights = scene.children.filter((o) => o.isPointLight)
    expect(lights).toHaveLength(2)
    fires.add(1)
    fires.add(2)
    fires.add(3)
    fires.place(1, [0, 1.5, 0], [2, 3, 2])
    fires.place(2, [50, 1.5, 0])
    fires.place(3, [500, 1.5, 0])
    fires.place(99, [0, 0, 0]) // not a fire: nothing
    const camera = new THREE.PerspectiveCamera()
    fires.update({ time: 1, camera, daylight: 0, night: 1 })
    expect(lights[0].position.toArray()).toEqual([0, 1.6, 0])
    expect(lights[1].position.x).toBe(50)
    expect(lights[0].intensity).toBeGreaterThan(40) // stronger at night
    fires.remove(1)
    fires.remove(1) // gone already
    fires.remove(2)
    fires.remove(3)
    fires.update({ time: 2, camera, daylight: 1, night: 0 })
    expect(lights.every((l) => l.intensity === 0)).toBe(true)
    fires.add(4)
    fires.dispose()
    expect(scene.children).toHaveLength(0)
  })
})
