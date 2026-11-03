import { describe, expect, it } from 'vitest'
import { createStateBuffer, turn } from '../src/buffer.js'

const yaw = (deg) => {
  const a = (deg * Math.PI) / 180
  return [[Math.cos(a), 0, Math.sin(a)], [0, 1, 0], [-Math.sin(a), 0, Math.cos(a)]]
}
const yawOf = (m) => (Math.atan2(m[0][2], m[0][0]) * 180) / Math.PI

// States as the page builds them: an entity that did not change is the same object as before.
function stream() {
  let entities = new Map()
  let tick = 0
  return (changes = {}, players) => {
    tick += 2
    entities = new Map(entities)
    for (const [id, e] of Object.entries(changes)) {
      if (e === null) entities.delete(Number(id))
      else entities.set(Number(id), { id: Number(id), ...e })
    }
    return { tick, entities: [...entities.values()], players: players || [] }
  }
}

describe('state buffer', () => {
  it('eases places and turns rotations between two states, the short way round', () => {
    const next = stream()
    const buffer = createStateBuffer({ delayMs: 100 })
    buffer.push(next({ 1: { position: [0, 0, 0], rotation: yaw(0) } }, [{ id: 'g', position: [0, 0, 0] }]), 1000)
    buffer.push(next({ 1: { position: [10, 0, 0], rotation: yaw(90) } }, [{ id: 'g', position: [4, 0, 0] }]), 1100)
    const half = buffer.interpolated(1150)
    expect(half.entities[0].position).toEqual([5, 0, 0])
    expect(yawOf(half.entities[0].rotation)).toBeCloseTo(45, 5)
    expect(half.players[0].position).toEqual([2, 0, 0])
    expect(Math.abs(yawOf(turn(yaw(170), yaw(-170), 0.5)))).toBeCloseTo(180, 4) // through 180, not back through 0
    expect(turn(yaw(30), yaw(30), 0.5)).toEqual(yaw(30))
    const unturned = createStateBuffer({ delayMs: 0 })
    const fresh = stream()
    unturned.push(fresh({ 2: { position: [0, 0, 0] } }), 0) // the world leaves the identity out
    unturned.push(fresh({ 2: { position: [0, 0, 0], rotation: yaw(60) } }), 100)
    expect(yawOf(unturned.interpolated(50).entities[0].rotation)).toBeCloseTo(30, 5)
  })

  it('shows what is there, and what it carries, as the older state until the moment reaches the newer one', () => {
    const next = stream()
    const buffer = createStateBuffer({ delayMs: 100 })
    buffer.push(next({ 1: { position: [0, 10, 0], attributes: { Falling: true } }, 2: { position: [5, 0, 0] } }), 0)
    // In one tick the stone lands, a blast marker appears and a piece it smashed is gone.
    buffer.push(next({ 1: { position: [0, 0, 0], attributes: { Falling: false } }, 2: null, 3: { position: [0, 0, 0] } }), 100)
    const before = buffer.interpolated(190) // 90% of the way
    expect(before.entities.map((e) => e.id)).toEqual([1, 2])
    expect(before.entities[0].position[1]).toBeCloseTo(1, 5)
    expect(before.entities[0].attributes.Falling).toBe(true)
    const at = buffer.interpolated(200)
    expect(at.entities.map((e) => e.id)).toEqual([1, 3])
    expect(at.entities[0].attributes.Falling).toBe(false)
  })

  it('eases an entity changed in states the page merged into one, by what changed, not by what the delta named', () => {
    const buffer = createStateBuffer({ delayMs: 100 })
    const a = { id: 1, position: [0, 0, 0] }
    buffer.push({ tick: 1, entities: [a] }, 0)
    buffer.push({ tick: 3, entities: [{ id: 1, position: [2, 0, 0] }], __spectatorDelta: { changedEntityIds: [] } }, 100)
    expect(buffer.interpolated(150).entities[0].position).toEqual([1, 0, 0])
  })

  it('draws two gaps behind the stream: 200 ms at ten a second, 100 straight from the world, moving a little at a time', () => {
    const relay = createStateBuffer()
    expect(relay.delayMs()).toBe(200)
    for (let i = 0; i < 40; i++) relay.push({ tick: i * 6 }, i * 100)
    expect(relay.delayMs()).toBe(200)
    expect(relay.gapMs()).toBe(100)
    const world = createStateBuffer()
    const delays = []
    for (let i = 0; i < 60; i++) {
      world.push({ tick: i * 2 }, i * 33)
      delays.push(world.delayMs())
    }
    expect(world.delayMs()).toBe(100)
    expect(Math.max(...delays.slice(1).map((d, i) => Math.abs(d - delays[i])))).toBeLessThanOrEqual(5)
    const slow = createStateBuffer()
    for (let i = 0; i < 80; i++) slow.push({ tick: i * 12 }, i * 200)
    expect(slow.delayMs()).toBe(400)
    const fixed = createStateBuffer({ delayMs: 50 })
    for (let i = 0; i < 40; i++) fixed.push({ tick: i }, i * 100)
    expect(fixed.delayMs()).toBe(50)
  })

  it('keeps states for a time, so a fast replay is still eased: no frame stands still', () => {
    // 4x replay on a 60 Hz screen: a pushed frame on two draws of three, 100 ms of island apart.
    const buffer = createStateBuffer()
    const drawn = []
    let frame = 0
    for (let ms = 0; ms < 3000; ms += 1000 / 60, frame++) {
      if (frame % 3 !== 2) buffer.push({ tick: frame, entities: [{ id: 1, position: [frame * 0.4, 0, 0] }] }, ms)
      drawn.push(buffer.interpolated(ms).entities[0].position[0])
    }
    const late = drawn.slice(120)
    const still = late.filter((x, i) => i > 0 && x === late[i - 1]).length
    expect(still).toBe(0)
    expect(buffer.size()).toBeGreaterThan(8)
    expect(buffer.size()).toBeLessThan(80)
  })

  it('knows its newest states, starts over on a new world, and on clear', () => {
    const buffer = createStateBuffer()
    expect(buffer.interpolated(0)).toBeNull()
    expect(buffer.latest()).toBeNull()
    expect(buffer.previous()).toBeNull()
    buffer.push({ tick: 10 }, 0)
    expect(buffer.interpolated(500)).toEqual({ tick: 10 })
    buffer.push({ tick: 12 }, 100)
    expect(buffer.previous()).toEqual({ tick: 10 })
    expect(buffer.interpolated(50).tick).toBe(10) // before the first state's time is drawn: the first
    expect(buffer.interpolated(5000)).toEqual({ tick: 12 }) // past the newest: the newest
    const seen = []
    buffer.forEachRecent((state, i) => seen.push([state.tick, i]))
    expect(seen).toEqual([[12, 1], [10, 0]])
    buffer.push({ tick: 900 }, 200) // a new world
    expect(buffer.size()).toBe(1)
    buffer.clear()
    expect(buffer.size()).toBe(0)
    buffer.push({ tick: 1 }, 10_000)
    expect(buffer.gapMs()).toBe(100) // the gap across a clear is not the stream's
  })
})
