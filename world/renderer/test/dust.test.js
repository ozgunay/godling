import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createDust } from '../src/dust.js'

const piece = (id, y, x = 0, extra = {}) => ({ id, position: [x, y, 0], size: [2.5, 2.5, 2.5], ...extra })

function setup() {
  const scene = new THREE.Scene()
  const dust = createDust(scene, { dustPuffs: 16 })
  let time = 0
  const step = (entity, dt = 0.1, quake = 0, sea = null) => {
    time += dt
    dust.update({ time, daylight: 1 })
    dust.watch(entity, dt, quake, sea)
  }
  return { scene, dust, step }
}

describe('dust', () => {
  it('puffs where a falling piece lands', () => {
    const { dust, step } = setup()
    step(piece(1, 20))
    step(piece(1, 17)) // falling at 30 a second
    step(piece(1, 14))
    expect(dust.info().alive).toBe(0)
    step(piece(1, 14)) // stopped: a landing
    step(piece(1, 14))
    expect(dust.info().alive).toBeGreaterThanOrEqual(2)
    expect(dust.info().watched).toBe(1)
    dust.prune(new Set())
    expect(dust.info().watched).toBe(0)
  })

  it('a quake rattles and slides pieces, and dust takes the oldest place', () => {
    const { dust, step } = setup()
    step(piece(2, 1.25, 0))
    for (let i = 1; i < 40; i++) step(piece(2, 1.25, i * 0.5), 0.1, 0.8) // sliding at 5 a second
    expect(dust.info().alive).toBeGreaterThan(5)
    step(piece(3, 1.25, 50))
    for (let i = 1; i < 10; i++) step(piece(3, 1.25, 50 + i * 0.03), 0.1, 0.8) // rocking where it lies
  })

  it('ignores land, respawns, the sea, a stopped clock, and stood-up logs land on their end', () => {
    const { dust, step } = setup()
    step({ id: 4, position: [0, 0, 0], size: [40, 1, 40] }) // a beach: never loose
    expect(dust.info().watched).toBe(0)
    step(piece(5, 30))
    step(piece(5, 2)) // a jump this far is a respawn
    step(piece(5, 2), 0) // no time passed
    step(piece(6, 10))
    step(piece(6, 1)) // falling...
    step(piece(6, 0.5), 0.1, 0, 1) // ...into the sea
    step(piece(6, 0.5), 0.1, 0, 1)
    expect(dust.info().alive).toBe(0)
    const log = (y) => ({ id: 7, position: [0, y, 0], size: [7.5, 1, 1], rotation: [[0, -1, 0], [1, 0, 0], [0, 0, 1]] })
    step(log(14))
    step(log(11))
    step(log(8))
    step(log(8))
    expect(dust.info().alive).toBeGreaterThan(0)
  })

  it('cleans up', () => {
    const { scene, dust } = setup()
    expect(scene.children).toHaveLength(1)
    dust.dispose()
    expect(scene.children).toHaveLength(0)
  })
})
