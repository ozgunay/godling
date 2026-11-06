// A page keeps the renderer it loaded, however long it stays open: the relay carries its stream through island
// restarts (ADR-015) and the page never imports the renderer again. A tab, a phone or the stream's browser source left
// open across a deploy would draw tonight's island with yesterday's code (on 2026-11-05 a page from before the deploy
// drew the new lightning as the old pale post). And a reload alone may not help: the bundle's URL never changes, and
// Cloudflare tells browsers to keep it four hours whatever the world says (its Browser Cache TTL overrides the world's
// `no-cache` for .js files).
//
// So the bundle knows its own build (BUILD, a hash of the renderer's sources that build.mjs bakes in), and the world
// serves the same hash beside it, in dist/build.json. Now and then the page asks for that file, past every cache; when
// the island serves another build, the page fetches the new bundle past the browser's cache (so the reload gets it)
// and reloads itself. Never while a viewer is aiming a power, never on the world's own capture page (it is started
// again with the island), and never twice for the same build: a page that is still stale after one reload says so and
// stays as it is.

/* global __RENDERER_BUILD__ */
export const BUILD = typeof __RENDERER_BUILD__ === 'string' ? __RENDERER_BUILD__ : 'dev'

const GUARD = 'godling-renderer-reload' // sessionStorage: the build this page last reloaded for, and when
const GUARD_MS = 10 * 60 * 1000 // one reload per build in this long

export function createBuildWatch({
  build = BUILD,
  bundleUrl,
  fetch = globalThis.fetch?.bind(globalThis),
  storage = safeSession(),
  reload = () => globalThis.location.reload(),
  busy = () => false,
  now = () => Date.now(),
  random = Math.random,
  every = 5 * 60 * 1000, // between looks
  first = 5000, // the first look, once the island has loaded
  timers = globalThis,
  doc = globalThis.document,
  log = console,
} = {}) {
  let timer = null
  let lastLook = -Infinity
  let checking = false
  let stopped = false
  let warned = false
  const enabled = build !== 'dev' && Boolean(bundleUrl) && typeof fetch === 'function'

  async function check() {
    if (!enabled || checking || stopped) return 'off'
    checking = true
    lastLook = now()
    try {
      const served = await servedBuild()
      if (!served || served === build) return 'fresh'
      if (busy()) return 'busy' // a viewer aiming: the next look tries again
      const before = readGuard()
      if (before && before.to === served && now() - before.at < GUARD_MS) {
        if (!warned) log.warn?.(`renderer: build ${build} still loaded after a reload for ${served}`)
        warned = true
        return 'stuck'
      }
      writeGuard({ to: served, at: now() })
      try {
        await fetch(bundleUrl, { cache: 'reload' }) // the fresh bundle into the browser's cache, for the reload
      } catch {
        // the reload asks again
      }
      if (stopped) return 'off'
      reload()
      return 'reloading'
    } finally {
      checking = false
    }
  }

  async function servedBuild() {
    try {
      const answer = await fetch(new URL('build.json', bundleUrl).href, { cache: 'no-store' })
      if (!answer?.ok) return null
      const body = await answer.json()
      return typeof body?.build === 'string' && body.build ? body.build : null
    } catch {
      return null // the island is restarting, or there is no build.json (a test page): nothing to compare
    }
  }

  function readGuard() {
    try {
      const value = JSON.parse(storage?.getItem(GUARD) || 'null')
      return value && typeof value.to === 'string' && Number.isFinite(value.at) ? value : null
    } catch {
      return null
    }
  }

  function writeGuard(value) {
    try {
      storage?.setItem(GUARD, JSON.stringify(value))
    } catch {
      // no storage: the reload still happens; a page that comes back stale reloads again only after `every`
    }
  }

  function schedule(ms) {
    if (stopped) return
    timers.clearTimeout?.(timer)
    timer = timers.setTimeout(async () => {
      await check()
      schedule(every * (0.8 + 0.4 * random())) // spread out, so a deploy does not bring every page back at once
    }, ms)
  }

  const onVisible = () => {
    if (doc?.visibilityState === 'visible' && now() - lastLook > 60 * 1000) void check()
  }

  if (enabled) {
    schedule(first)
    doc?.addEventListener?.('visibilitychange', onVisible)
  }

  return {
    check,
    get enabled() { return enabled },
    dispose() {
      stopped = true
      timers.clearTimeout?.(timer)
      doc?.removeEventListener?.('visibilitychange', onVisible)
    },
  }
}

function safeSession() {
  try {
    return globalThis.sessionStorage ?? null
  } catch {
    return null // storage blocked (a sandboxed frame)
  }
}
