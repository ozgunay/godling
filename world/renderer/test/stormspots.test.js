import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createStormSpots } from '../src/stormspots.js'

const spot = (id, charged = false, position = [3, 0.05, 4]) => ({ id, position, render: { role: 'StormSpot' },
  attributes: { StormId: 1, Charged: charged } })
const drawn = (scene) => scene.children.filter((c) => c.name === 'GodlingStormSpot')

describe('stormspots: a storm\'s strike spots crackle on the ground, and flare before their bolt', () => {
  it('draws a ring of light for each spot (nothing for anything else), crackling but never still', () => {
    const scene = new THREE.Scene()
    const spots = createStormSpots(scene)
    spots.watch({ id: 9, position: [0, 0, 0], render: { role: 'Tree' } })
    spots.watch(spot(1))
    spots.watch(spot(1)) // seen again: the same ring
    expect(drawn(scene)).toHaveLength(1)
    expect(drawn(scene)[0].position.toArray()).toEqual([3, 0.1, 4])
    const looks = new Set()
    for (let t = 0; t < 2; t += 0.1) {
      spots.update(t)
      looks.add(spots.info()[0].opacity)
    }
    expect(looks.size).toBeGreaterThan(5)
    expect(Math.max(...looks)).toBeLessThanOrEqual(0.65)
  })

  it('flares white and bright, a little wider, the moment before its bolt', () => {
    const scene = new THREE.Scene()
    const spots = createStormSpots(scene)
    spots.watch(spot(1, true))
    spots.update(0.3)
    const [group] = drawn(scene)
    expect(spots.info()[0]).toMatchObject({ charged: true })
    expect(spots.info()[0].opacity).toBeGreaterThanOrEqual(0.65)
    expect(group.scale.x).toBeGreaterThan(1.1)
    expect(group.children[1].material.color.getHex()).toBe(0xeef6ff)
  })

  it('lets a struck spot go, and everything when disposed', () => {
    const scene = new THREE.Scene()
    const spots = createStormSpots(scene)
    spots.watch(spot(1))
    spots.watch(spot(2))
    spots.prune(new Set([2]))
    expect(drawn(scene)).toHaveLength(1)
    spots.dispose()
    expect(drawn(scene)).toHaveLength(0)
    expect(spots.info()).toEqual([])
  })
})
