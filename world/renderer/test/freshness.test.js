import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import { BUILD, createBuildWatch } from '../src/freshness.js'
import { buildId } from '../build-id.mjs'

const BUNDLE = 'https://island.example/island/renderer-files/dist/renderer.bundle.js'

// A fake island: build.json says `served` (or fails), and every fetch is recorded.
function island(served) {
  const calls = []
  const fetch = vi.fn(async (url, init) => {
    calls.push([String(url), init?.cache])
    if (String(url).endsWith('build.json')) {
      if (served instanceof Error) throw served
      if (served === 404) return { ok: false, json: async () => ({}) }
      return { ok: true, json: async () => ({ build: served }) }
    }
    return { ok: true, arrayBuffer: async () => new ArrayBuffer(0) }
  })
  return { fetch, calls }
}

function memoryStorage() {
  const data = new Map()
  return { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => data.set(k, String(v)), data }
}

// No timers of its own: the tests call check() themselves.
const noTimers = { setTimeout: () => 0, clearTimeout: () => {} }

function deferred() {
  let resolve
  const promise = new Promise((done) => { resolve = done })
  return { promise, resolve }
}

function watch(served, extra = {}) {
  const net = island(served)
  const reload = vi.fn()
  const storage = extra.storage ?? memoryStorage()
  const w = createBuildWatch({ build: 'aaaa', bundleUrl: BUNDLE, fetch: net.fetch, storage, reload, timers: noTimers,
    doc: null, log: { warn: vi.fn() }, ...extra })
  return { w, net, reload, storage }
}

describe('freshness: a page reloads when the island serves another renderer', () => {
  it('leaves a page with the served build alone, asking for build.json past every cache', async () => {
    const { w, net, reload } = watch('aaaa')
    expect(await w.check()).toBe('fresh')
    expect(net.calls).toEqual([['https://island.example/island/renderer-files/dist/build.json', 'no-store']])
    expect(reload).not.toHaveBeenCalled()
  })

  it('fetches the new bundle past the browser cache, then reloads, when the island has another build', async () => {
    const { w, net, reload, storage } = watch('bbbb')
    expect(await w.check()).toBe('reloading')
    expect(net.calls).toEqual([
      ['https://island.example/island/renderer-files/dist/build.json', 'no-store'],
      [BUNDLE, 'reload'], // the reload must find the new bundle, not the one Cloudflare told the browser to keep
    ])
    expect(reload).toHaveBeenCalledTimes(1)
    expect(JSON.parse(storage.data.get('godling-renderer-reload')).to).toBe('bbbb')
  })

  it('waits while a viewer aims a power, and reloads at a later look', async () => {
    let aiming = true
    const { w, reload } = watch('bbbb', { busy: () => aiming })
    expect(await w.check()).toBe('busy')
    expect(reload).not.toHaveBeenCalled()
    aiming = false
    expect(await w.check()).toBe('reloading')
  })

  it('finishes downloading the bundle before reloading so navigation cannot abort cache priming', async () => {
    const body = deferred()
    const arrayBuffer = vi.fn(() => body.promise)
    const net = island('bbbb')
    const fetch = (url, init) => String(url) === BUNDLE
      ? Promise.resolve({ ok: true, arrayBuffer }) : net.fetch(url, init)
    const { w, reload, storage } = watch('bbbb', { fetch })
    const checking = w.check()
    await vi.waitFor(() => expect(arrayBuffer).toHaveBeenCalledTimes(1))
    expect(reload).not.toHaveBeenCalled()
    expect(storage.data.size).toBe(0)
    body.resolve(new ArrayBuffer(0))
    expect(await checking).toBe('reloading')
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('defers a reload if the viewer starts aiming while the bundle is downloading', async () => {
    const bundle = deferred()
    const net = island('bbbb')
    let aiming = false
    const fetch = vi.fn((url, init) => String(url) === BUNDLE ? bundle.promise : net.fetch(url, init))
    const { w, reload, storage } = watch('bbbb', { fetch, busy: () => aiming })
    const checking = w.check()
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledWith(BUNDLE, { cache: 'reload' }))
    aiming = true
    bundle.resolve({ ok: true, arrayBuffer: async () => new ArrayBuffer(0) })
    expect(await checking).toBe('busy')
    expect(reload).not.toHaveBeenCalled()
    expect(storage.data.size).toBe(0)
    aiming = false
    expect(await w.check()).toBe('reloading')
  })

  it('does not consume the reload guard when disposed during a bundle download', async () => {
    const bundle = deferred()
    const net = island('bbbb')
    const fetch = vi.fn((url, init) => String(url) === BUNDLE ? bundle.promise : net.fetch(url, init))
    const storage = memoryStorage()
    const { w, reload } = watch('bbbb', { fetch, storage })
    const checking = w.check()
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledWith(BUNDLE, { cache: 'reload' }))
    w.dispose()
    bundle.resolve({ ok: true, arrayBuffer: async () => new ArrayBuffer(0) })
    expect(await checking).toBe('off')
    expect(reload).not.toHaveBeenCalled()
    const replacement = watch('bbbb', { storage })
    expect(await replacement.w.check()).toBe('reloading')
  })

  it('never reloads twice for the same build: a page still stale after a reload stays as it is', async () => {
    let clock = 1_000_000
    const storage = memoryStorage()
    const first = watch('bbbb', { storage, now: () => clock })
    expect(await first.w.check()).toBe('reloading')
    // The reloaded page came back with the old bundle all the same (a cache that would not let go).
    const again = watch('bbbb', { storage, now: () => clock + 1000 })
    expect(await again.w.check()).toBe('stuck')
    expect(again.reload).not.toHaveBeenCalled()
    // Ten minutes on it may try again; and a newer build than the one it tried is worth a reload at once.
    clock += 11 * 60 * 1000
    expect(await watch('bbbb', { storage, now: () => clock }).w.check()).toBe('reloading')
    expect(await watch('cccc', { storage, now: () => clock + 1000 }).w.check()).toBe('reloading')
  })

  it('does nothing when build.json cannot be had (the island restarting, or a page without one)', async () => {
    for (const served of [new Error('offline'), 404, '']) {
      const { w, reload } = watch(served)
      expect(await w.check()).toBe('fresh')
      expect(reload).not.toHaveBeenCalled()
    }
  })

  it('still reloads when storage is blocked, and when fetching the new bundle fails', async () => {
    const blocked = { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } }
    const { w, reload } = watch('bbbb', { storage: blocked })
    expect(await w.check()).toBe('reloading')
    expect(reload).toHaveBeenCalledTimes(1)
    const failing = vi.fn(async (url) => {
      if (String(url).endsWith('build.json')) return { ok: true, json: async () => ({ build: 'bbbb' }) }
      throw new Error('network')
    })
    const reload2 = vi.fn()
    const w2 = createBuildWatch({ build: 'aaaa', bundleUrl: BUNDLE, fetch: failing, storage: memoryStorage(),
      reload: reload2, timers: noTimers, doc: null })
    expect(await w2.check()).toBe('reloading')
    expect(reload2).toHaveBeenCalledTimes(1)
  })

  it('is off for unbuilt sources (tests, previews) and once disposed', async () => {
    const net = island('bbbb')
    const dev = createBuildWatch({ build: 'dev', bundleUrl: BUNDLE, fetch: net.fetch, timers: noTimers, doc: null })
    expect(dev.enabled).toBe(false)
    expect(await dev.check()).toBe('off')
    expect(net.fetch).not.toHaveBeenCalled()
    const { w, reload } = watch('bbbb')
    w.dispose()
    expect(await w.check()).toBe('off')
    expect(reload).not.toHaveBeenCalled()
    expect(BUILD).toBe('dev') // vitest runs the sources, not the bundle
  })

  it('looks first after a few seconds, then every few minutes, spread out, and when the tab comes back', async () => {
    const pending = []
    const timers = { setTimeout: (fn, ms) => { pending.push([fn, ms]); return pending.length }, clearTimeout: () => {} }
    let visibility = 'hidden'
    const listeners = {}
    const doc = { get visibilityState() { return visibility }, addEventListener: (k, fn) => { listeners[k] = fn },
      removeEventListener: vi.fn() }
    let clock = 0
    const net = island('aaaa')
    createBuildWatch({ build: 'aaaa', bundleUrl: BUNDLE, fetch: net.fetch, timers, doc, random: () => 1,
      now: () => clock, storage: memoryStorage(), reload: vi.fn() })
    expect(pending.map(([, ms]) => ms)).toEqual([5000])
    await pending[0][0]()
    expect(pending[1][1]).toBeCloseTo(5 * 60 * 1000 * 1.2)
    expect(net.fetch).toHaveBeenCalledTimes(1)
    visibility = 'visible'
    clock = 30 * 1000
    listeners.visibilitychange() // too soon after the last look
    expect(net.fetch).toHaveBeenCalledTimes(1)
    clock = 2 * 60 * 1000
    listeners.visibilitychange()
    await Promise.resolve()
    expect(net.fetch).toHaveBeenCalledTimes(2)
  })
})

describe('the committed bundle and its build.json', () => {
  const root = resolve(import.meta.dirname, '..') // from any cwd
  const dist = (name) => resolve(root, 'dist', name)
  it('match the renderer sources: rebuild (npm run build) after changing src/', () => {
    const served = JSON.parse(readFileSync(dist('build.json'), 'utf8')).build
    expect(served).toBe(buildId(root))
    expect(readFileSync(dist('renderer.bundle.js'), 'utf8')).toContain(JSON.stringify(served))
  })
})
