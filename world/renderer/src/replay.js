// Replay (ADR-016): the island's past, played here from the chunks the packer writes (mind/godling/replay.py).
// The viewers' screen (world/viewer) says where and how fast to play. This fetches the 10 s chunks around its own
// playhead, rebuilds the frame due now from the chunk's keyframe and the changes after it, and hands it to the
// renderer, so every viewer has a playhead of their own and the server only serves files. The live stream keeps
// coming meanwhile: going live again is instant.

const FORMAT = 1 // the newest chunk format this renderer can draw
const AHEAD = 3 // chunks fetched ahead of the playhead, once the playhead's own is in
const TELL_MS = 250 // how often the screen hears where the playhead is
const RETRY_MS = 2000 // a chunk that did not come is asked for again after this…
const TRIES = 4 // …this many times, before its 10 s are skipped as lost
const TOP_KEPT = ['players', 'recent_events', 'sounds', 'game_status']
const ASSET_PATH = /^(?:[^?#]*\/)?assets\/([^/?#]+)$/

async function readChunk(res) {
  const bytes = new Uint8Array(await res.arrayBuffer())
  if (bytes[0] === 0x1f && bytes[1] === 0x8b) { // still gzipped: no server or CDN unpacked it on the way
    if (typeof DecompressionStream !== 'function') {
      const err = new Error('this browser cannot unpack the past')
      err.unsupported = true
      throw err
    }
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))
    return JSON.parse(await new Response(stream).text())
  }
  return JSON.parse(new TextDecoder().decode(bytes))
}

// The screen's clock and Godling's body, from a frame's Clock (the guest panel reads the same, live: Island.status).
function hudOf(obs) {
  const clock = (obs.entities || []).find((e) => e.attributes && e.attributes.TimeOfDay !== undefined)
  const c = clock?.attributes || {}
  const out = { clock: { hour: c.TimeOfDay, day: c.Day, rain: c.Rain || 0, fog: c.Fog || 0, quake: c.QuakePhase || '' } }
  if (c.GodlingHealth !== undefined) {
    out.godling = { health: c.GodlingHealth, hunger: c.GodlingHunger, wet: c.GodlingWet || 0, cold: Boolean(c.GodlingCold),
      bracing: Boolean(c.GodlingBracing), knockedDown: Boolean(c.GodlingKnockedDown),
      dead: Boolean(c.GodlingDead), deadFor: c.GodlingDeadFor || 0, diedOf: c.GodlingDiedOf || '', deaths: c.GodlingDeaths || 0 }
  }
  return out
}

// The last frame at or before t, by index, or -1.
function frameIndex(frames, t) {
  if (!frames.length || frames[0].t > t) return -1
  let lo = 0
  let hi = frames.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (frames[mid].t <= t) lo = mid
    else hi = mid - 1
  }
  return lo
}

export function createReplay({ onFrame, onReset, tell, assetBase, defaultAssetBase }) {
  let base = '' // where the island serves the chunks, absolute
  let remote = '' // the bucket's public address, when chunks also go there…
  let remoteUntil = 0 // …for chunks starting before this (UTC ms), which are up
  let segments = [] // [{ start, end, live }], oldest first
  let chunkMs = 10000
  let playhead = 0 // UTC ms
  let speed = 1
  let paused = false
  let active = false
  let shown = null // the observation on screen
  let lastStep = 0
  let lastTell = 0
  let waiting = false
  const told = new Set() // problems already told to the screen
  const chunks = new Map() // t0 -> a chunk being played | { loading } | { failed, tries, at }

  // Chunks name models asset://name.glb (older ones by the path they were served at): resolved where this island
  // serves models, learned from the live entities, or else beside this renderer.
  const prefix = () => assetBase() || defaultAssetBase
  const fixAsset = (e) => {
    const url = e.model_url
    if (typeof url !== 'string') return e
    const name = url.startsWith('asset://') ? url.slice(8) : (!url.startsWith(prefix()) && ASSET_PATH.exec(url)?.[1])
    if (!name) return e
    const attrs = e.attributes?.ModelUrl ? { ...e.attributes, ModelUrl: prefix() + name } : e.attributes
    return { ...e, model_url: prefix() + name, ...(attrs ? { attributes: attrs } : {}) }
  }

  // A chunk as it came, built frame by frame as the playhead reaches them: its keyframe, then the changes in place
  // (a seek back starts again from the keyframe). Only the frame shown is copied out.
  const prepare = (raw) => ({ frames: raw.frames || [], ents: null, top: null, idx: -1, obs: null, obsIdx: -1 })
  function frameOf(c, idx) {
    if (c.ents === null || idx < c.idx) {
      const full = c.frames[0].full || {}
      c.top = { ...full }
      delete c.top.entities
      c.ents = new Map((full.entities || []).map((e) => [e.id, fixAsset(e)]))
      c.idx = 0
    }
    while (c.idx < idx) {
      const f = c.frames[++c.idx]
      for (const e of f.e || []) {
        if (e.add) c.ents.set(e.add.id, fixAsset(e.add))
        else if (e.rm) c.ents.delete(e.id)
        else {
          const was = c.ents.get(e.id)
          if (was) c.ents.set(e.id, { ...was, ...(e.p ? { position: e.p } : {}), ...(e.r ? { rotation: e.r } : {}) })
        }
      }
      c.top = { ...c.top, tick: f.tick ?? c.top.tick, server_time_ms: f.ms ?? c.top.server_time_ms }
      for (const key of TOP_KEPT) if (key in f) c.top[key] = f[key]
    }
    if (c.obsIdx !== idx) {
      c.obs = { ...c.top, entities: [...c.ents.values()] }
      c.obsIdx = idx
    }
    return c.obs
  }

  function problem(kind) {
    if (told.has(kind)) return
    told.add(kind)
    tell({ type: 'godling-replay-problem', problem: kind })
  }

  function chunkUrl(t0) {
    const iso = new Date(t0).toISOString()
    return `${remote && t0 < remoteUntil ? remote : base}/chunks/${iso.slice(0, 10)}/${iso.slice(11, 13)}/${t0}.json.gz`
  }

  const edge = () => (segments.length ? segments[segments.length - 1].end - 100 : 0)
  const segmentAt = (t) => segments.find((s) => t >= s.start && t < s.end)
  const recorded = (t0) => segments.some((s) => s.start < t0 + chunkMs && s.end > t0) // a chunk the index says exists

  function load(t0) {
    const was = chunks.get(t0)
    if (was && !(was.failed && was.tries < TRIES && performance.now() - was.at > RETRY_MS)) return
    const tries = was?.tries || 0
    const controller = typeof AbortController === 'function' ? new AbortController() : null
    chunks.set(t0, { loading: true, controller })
    fetch(chunkUrl(t0), controller ? { signal: controller.signal } : undefined).then(async (res) => {
      if (!res.ok) throw new Error(String(res.status))
      const chunk = await readChunk(res)
      if (!chunks.get(t0)?.loading) return
      if (chunk.format > FORMAT) {
        problem('newer')
        chunks.set(t0, { failed: true, tries: TRIES, at: performance.now() })
      } else chunks.set(t0, prepare(chunk))
    }).catch((err) => {
      if (err?.name === 'AbortError' || !chunks.get(t0)?.loading) return
      if (err?.unsupported) problem('unsupported')
      chunks.set(t0, { failed: true, tries: err?.unsupported ? TRIES : tries + 1, at: performance.now() })
    })
  }

  function forget(t0) {
    chunks.get(t0)?.controller?.abort()
    chunks.delete(t0)
  }

  // Where the playhead may be: inside a segment. In a gap (the island was restarting), on to the next one.
  function settle(t) {
    if (!segments.length) return t
    if (t < segments[0].start) return segments[0].start
    if (t >= edge()) return edge()
    if (segmentAt(t)) return t
    const next = segments.find((s) => s.start > t)
    return next ? next.start : edge()
  }

  function step(nowMs = performance.now()) {
    if (!active) return
    const dt = Math.min(Math.max(nowMs - lastStep, 0), 250)
    lastStep = nowMs
    const t0 = playhead - (playhead % chunkMs)
    for (let k = 0; k <= AHEAD; k++) {
      const t = t0 + k * chunkMs
      if (t <= edge() && recorded(t)) load(t) // never past what the index says is written: not yet there
      // The playhead's own chunk first: on a slow line the ones ahead would share it, and a seek would wait for all
      // four (ADR-016, "Load and phone").
      if (k === 0 && chunks.get(t0)?.loading) break
    }
    for (const key of [...chunks.keys()]) if (key < t0 - chunkMs || key > t0 + (AHEAD + 1) * chunkMs) forget(key)
    const here = chunks.get(t0)
    if (here?.failed && here.tries >= TRIES) { // lost, after every try: skip its 10 s
      playhead = settle(t0 + chunkMs)
      waiting = false
    } else if (!here?.frames) {
      waiting = true // on its way, or being asked for again: hold the playhead
    } else {
      waiting = false
      const idx = frameIndex(here.frames, playhead)
      if (idx >= 0) {
        const obs = frameOf(here, idx)
        if (obs !== shown) {
          shown = obs
          onFrame(obs)
        }
      }
      if (!paused) {
        const wanted = playhead + dt * speed
        const next = settle(wanted)
        if (next - wanted > chunkMs) tell({ type: 'godling-replay-gap' }) // jumped the time the island was restarting
        playhead = next
      }
    }
    if (nowMs - lastTell > TELL_MS) {
      lastTell = nowMs
      tell({ type: 'godling-replay-time', t: playhead, waiting, paused, edge: edge(), ...(shown ? hudOf(shown) : {}) })
    }
  }

  function seek(t) {
    playhead = settle(Number(t) || 0)
    shown = null
    onReset()
  }

  return {
    get active() { return active },
    step,
    // From the screen: { action: 'start' | 'seek' | 'segments' | 'live', … }, and speed, paused, base, remote and
    // remoteUntil whatever the action.
    command(m) {
      if (Array.isArray(m.segments)) segments = [...m.segments].sort((a, b) => a.start - b.start)
      if (m.chunkMs) chunkMs = Number(m.chunkMs)
      if (m.base) base = String(m.base).replace(/\/$/, '')
      if (m.remote !== undefined) remote = String(m.remote || '').replace(/\/$/, '')
      if (Number.isFinite(m.remoteUntil)) remoteUntil = m.remoteUntil
      if (m.speed) speed = Math.min(16, Math.max(0.25, Number(m.speed)))
      if (typeof m.paused === 'boolean') paused = m.paused
      if (m.action === 'start') {
        active = true
        told.clear()
        lastStep = performance.now()
        seek(m.t)
      } else if (m.action === 'seek') seek(m.t)
      else if (m.action === 'live') {
        active = false
        for (const key of [...chunks.keys()]) forget(key)
        shown = null
        onReset()
      }
    },
  }
}
