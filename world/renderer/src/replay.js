// Replay (ADR-016): the island's past, played here from the chunks the packer writes (mind/godling/replay.py).
// The viewers' screen (world/viewer) says where and how fast to play. This fetches the 10 s chunks around its own
// playhead, rebuilds each frame's whole state, and hands the frame due now to the renderer, so every viewer has a
// playhead of their own and the server only serves files. The live stream keeps coming meanwhile: going live again
// is instant.

const FORMAT = 1 // the newest chunk format this renderer can draw
const AHEAD = 3 // chunks fetched ahead of the playhead
const TELL_MS = 250 // how often the screen hears where the playhead is
const TOP_KEPT = ['players', 'recent_events', 'sounds', 'game_status']

async function readChunk(res) {
  const bytes = new Uint8Array(await res.arrayBuffer())
  if (bytes[0] === 0x1f && bytes[1] === 0x8b) { // still gzipped: no server or CDN unpacked it on the way
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
      bracing: Boolean(c.GodlingBracing), knockedDown: Boolean(c.GodlingKnockedDown) }
  }
  return out
}

export function createReplay({ onFrame, onReset, tell, assetBase }) {
  let base = '' // where the chunks are, absolute
  let segments = [] // [{ start, end, live }], oldest first
  let chunkMs = 10000
  let playhead = 0 // UTC ms
  let speed = 1
  let paused = false
  let active = false
  let shown = null // the frame on screen
  let lastStep = 0
  let lastTell = 0
  let waiting = false
  let problem = ''
  const chunks = new Map() // t0 -> { frames } | { loading } | { missing }

  // The world records its models as /assets/<name>; the live island serves them where its own entities say.
  const fixAsset = (e) => {
    const url = e.model_url
    const at = assetBase()
    if (typeof url !== 'string' || !at || !url.startsWith('/assets/')) return e
    return { ...e, model_url: at + url.slice(8) }
  }

  // Every frame of a chunk as a whole observation, as the live stream's would be. Unchanged entities are shared.
  function build(chunk) {
    const frames = []
    let ents = new Map()
    let top = {}
    for (const f of chunk.frames || []) {
      if (f.full) {
        top = { ...f.full }
        delete top.entities
        ents = new Map(f.full.entities.map((e) => [e.id, fixAsset(e)]))
      } else {
        if (f.e) {
          ents = new Map(ents)
          for (const e of f.e) {
            if (e.add) ents.set(e.add.id, fixAsset(e.add))
            else if (e.rm) ents.delete(e.id)
            else if (ents.has(e.id)) {
              const was = ents.get(e.id)
              ents.set(e.id, { ...was, ...(e.p ? { position: e.p } : {}), ...(e.r ? { rotation: e.r } : {}) })
            }
          }
        }
        top = { ...top, tick: f.tick ?? top.tick, server_time_ms: f.ms ?? top.server_time_ms }
        for (const key of TOP_KEPT) if (key in f) top[key] = f[key]
      }
      frames.push({ t: f.t, obs: { ...top, entities: [...ents.values()] } })
    }
    return frames
  }

  function chunkUrl(t0) {
    const iso = new Date(t0).toISOString()
    return `${base}/chunks/${iso.slice(0, 10)}/${iso.slice(11, 13)}/${t0}.json.gz`
  }

  function load(t0) {
    if (chunks.has(t0)) return
    chunks.set(t0, { loading: true })
    fetch(chunkUrl(t0)).then(async (res) => {
      if (!res.ok) throw new Error(String(res.status))
      const chunk = await readChunk(res)
      if (chunk.format > FORMAT) {
        problem = 'newer'
        chunks.set(t0, { missing: true })
        return
      }
      if (chunks.get(t0)?.loading) chunks.set(t0, { frames: build(chunk) })
    }).catch(() => {
      if (chunks.get(t0)?.loading) chunks.set(t0, { missing: true })
    })
  }

  const edge = () => (segments.length ? segments[segments.length - 1].end - 100 : 0)
  const segmentAt = (t) => segments.find((s) => t >= s.start && t < s.end)

  // Where the playhead may be: inside a segment. In a gap (the island was restarting), on to the next one.
  function settle(t) {
    if (!segments.length) return t
    if (t < segments[0].start) return segments[0].start
    if (t >= edge()) return edge()
    if (segmentAt(t)) return t
    const next = segments.find((s) => s.start > t)
    return next ? next.start : edge()
  }

  function frameAt(frames, t) {
    let lo = 0
    let hi = frames.length - 1
    if (!frames.length || frames[0].t > t) return null
    while (lo < hi) { // the last frame at or before t
      const mid = (lo + hi + 1) >> 1
      if (frames[mid].t <= t) lo = mid
      else hi = mid - 1
    }
    return frames[lo]
  }

  function step(nowMs = performance.now()) {
    if (!active) return
    const dt = Math.min(Math.max(nowMs - lastStep, 0), 250)
    lastStep = nowMs
    const t0 = playhead - (playhead % chunkMs)
    for (let k = 0; k <= AHEAD; k++) load(t0 + k * chunkMs)
    for (const key of chunks.keys()) if (key < t0 - chunkMs || key > t0 + (AHEAD + 1) * chunkMs) chunks.delete(key)
    const here = chunks.get(t0)
    if (here?.missing) { // a hole in the record: skip it
      playhead = settle(t0 + chunkMs)
      waiting = false
    } else if (!here?.frames) {
      waiting = true // the chunk is on its way: hold the playhead
    } else {
      waiting = false
      const frame = frameAt(here.frames, playhead)
      if (frame && frame !== shown) {
        shown = frame
        onFrame(frame.obs)
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
      tell({ type: 'godling-replay-time', t: playhead, waiting, paused, speed, edge: edge(), problem,
        ...(shown ? hudOf(shown.obs) : {}) })
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
    // { action: 'start' | 'seek' | 'speed' | 'pause' | 'segments' | 'live', ... } from the screen
    command(m) {
      if (m.segments) segments = [...m.segments].sort((a, b) => a.start - b.start)
      if (m.chunkMs) chunkMs = Number(m.chunkMs)
      if (m.base) base = String(m.base).replace(/\/$/, '')
      if (m.speed) speed = Math.min(16, Math.max(0.25, Number(m.speed)))
      if (typeof m.paused === 'boolean') paused = m.paused
      if (m.action === 'start') {
        active = true
        problem = ''
        lastStep = performance.now()
        seek(m.t)
      } else if (m.action === 'seek') seek(m.t)
      else if (m.action === 'live') {
        active = false
        chunks.clear()
        shown = null
        onReset()
      }
    },
  }
}
