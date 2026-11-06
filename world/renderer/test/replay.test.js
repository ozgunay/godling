// The replay player (src/replay.js) as the island's page drives it: what it asks the island for, and when. fetch is
// answered here, one chunk at a time; performance.now is the test's own clock.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createReplay } from '../src/replay.js'

const T = Date.UTC(2026, 10, 3, 6, 0, 0) // a chunk's start: chunks are 10 s on whole multiples of it
const BASE = 'https://island.example/replay'

function chunk(t0) {
  return {
    format: 1,
    t0,
    frames: [
      { t: t0, tick: 1, ms: 0, full: { entities: [{ id: 1, position: [0, 0, 0], model_url: 'asset://box.glb' }], players: [] } },
      { t: t0 + 5000, tick: 300, ms: 5000, e: [{ id: 1, p: [1, 0, 0] }] },
    ],
  }
}

function setup({ segments = [{ start: T, end: T + 600e3, live: true }], at = T + 1000 } = {}) {
  let now = 0
  vi.spyOn(performance, 'now').mockImplementation(() => now)
  const asked = [] // [{ t0, answer(ok) }], in the order asked
  vi.stubGlobal('fetch', vi.fn((url) => new Promise((resolve) => {
    const t0 = Number(/\/(\d+)\.json\.gz$/.exec(url)[1])
    asked.push({ t0, url, answer: (ok = true) => resolve(ok
      ? { ok: true, status: 200, arrayBuffer: async () => new TextEncoder().encode(JSON.stringify(chunk(t0))).buffer }
      : { ok: false, status: 503 }) })
  })))
  const frames = []
  const told = []
  const replay = createReplay({ onFrame: (obs) => frames.push(obs), onReset: () => {}, tell: (m) => told.push(m),
    assetBase: () => '/island/assets/', defaultAssetBase: '/assets/' })
  replay.command({ action: 'start', t: at, base: BASE, segments, chunkMs: 10000, speed: 1, paused: false })
  const step = (ms = 16) => { now += ms; replay.step(now) }
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0))
  return { replay, asked, frames, told, step, settle, later: (ms) => { now += ms } }
}

describe('the replay player', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('asks for the playhead\'s chunk alone, and for the three ahead once it is in', async () => {
    const { asked, frames, step, settle } = setup()
    step()
    step() // asked again on every frame while it comes: still one request, and nothing ahead
    expect(asked.map((a) => a.t0)).toEqual([T])
    expect(asked[0].url).toBe(`${BASE}/chunks/2026-11-03/06/${T}.json.gz`)
    asked[0].answer()
    await settle()
    step()
    expect(asked.map((a) => a.t0)).toEqual([T, T + 10e3, T + 20e3, T + 30e3])
    expect(frames).toHaveLength(1) // the playhead's frame, from the keyframe, its model where this island serves them
    expect(frames[0].entities[0]).toMatchObject({ id: 1, position: [0, 0, 0], model_url: '/island/assets/box.glb' })
  })

  it('asks for a new playhead\'s chunk first after a seek, and none past what the index says is written', async () => {
    const { replay, asked, step, settle } = setup({ segments: [{ start: T, end: T + 45e3, live: true }] })
    step()
    asked[0].answer()
    await settle()
    step()
    expect(asked.map((a) => a.t0)).toEqual([T, T + 10e3, T + 20e3, T + 30e3])
    replay.command({ action: 'seek', t: T + 41e3 }) // the last chunk: it ends past the edge, so nothing after it
    step()
    expect(asked.map((a) => a.t0).slice(4)).toEqual([T + 40e3])
    asked[4].answer()
    await settle()
    step()
    expect(asked).toHaveLength(5)
  })

  it('exposes recorded time for effects: it waits for data, pauses, runs at the chosen speed and seeks backwards', async () => {
    const { replay, asked, step, settle } = setup()
    expect(replay.time).toBe(T + 1000)
    step(250)
    expect(replay.time).toBe(T + 1000) // the chunk has not arrived
    asked[0].answer()
    await settle()
    replay.command({ paused: true })
    step(250)
    expect(replay.time).toBe(T + 1000)
    replay.command({ paused: false, speed: 4 })
    step(250)
    expect(replay.time).toBe(T + 2000)
    replay.command({ action: 'seek', t: T + 500, paused: true })
    step(250)
    expect(replay.time).toBe(T + 500)
  })

  it('asks for a chunk that did not come again, and lets the ones ahead come meanwhile', async () => {
    const { asked, step, settle, later } = setup()
    step()
    asked[0].answer(false)
    await settle()
    step() // the playhead's chunk failed: the ones ahead are asked for while it waits to be asked again
    expect(asked.map((a) => a.t0)).toEqual([T, T + 10e3, T + 20e3, T + 30e3])
    later(2001)
    step()
    expect(asked.map((a) => a.t0)).toEqual([T, T + 10e3, T + 20e3, T + 30e3, T])
  })
})
