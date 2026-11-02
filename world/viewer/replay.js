// The island's past on the viewers' screen (ADR-016): a timeline to scrub, speeds, markers for what happened, and
// "Go live". The island's own page plays the chunks (world/renderer/src/replay.js); this page says where and how fast,
// and fills the screen around it from the tracks: what Godling thought, needed and noticed, and what viewers did.
// Anyone may watch the whole history (D1); powers rest while you watch the past (D6).

const TRACKS_AHEAD = 30 * 60e3 // the screen's tracks are fetched this far past the playhead
const INDEX_EVERY = 10e3
const SPANS = [[60 * 60e3, '1 h'], [6 * 3600e3, '6 h'], [24 * 3600e3, '24 h'], [7 * 86400e3, '7 days']]
const SPEEDS = [1, 2, 4, 8, 16]
const MARKS = { // what a marker on the timeline means (mind/godling/replay.py marks_of), with its icon
  rain: ['rain', 'Rain began'], fog: ['sky', 'Fog rolled in'], ship: ['wave', 'A ship passed'],
  meteor: ['meteor', 'A meteor'], earthquake: ['quake', 'An earthquake'], lightning: ['lightning', 'Lightning'],
  stone: ['stone', 'A stone from the sky'], log: ['log', 'A log from the sky'], regrow: ['sapling', 'A palm grew back'],
  note: ['glider', 'A note drifted down'], fire: ['fire', 'Godling made fire'], 'fire-out': ['drop', 'A fire went out'],
  fish: ['fish', 'Godling caught a fish'], hurt: ['heartHalf', 'Godling was hurt'], faint: ['heartEmpty', 'Godling fainted'],
  wall: ['stone', 'Godling built a wall'], roof: ['stone', 'Godling built a roof'], enclosure: ['stone', 'Godling closed a room'],
}

// What the screen shows of Godling's mind after these entries of its log: the guest panel's reading, live and in
// replay alike (mind/godling/replay.py reduce_status).
export function reduceStatus(entries, feedKept = 8) {
  const out = { thought: '', needs: '', intention: '' }
  const feed = []
  const add = (line) => {
    feed.push(line)
    if (feed.length > feedKept) feed.shift()
  }
  for (const e of entries) {
    if (e.kind === 'decision') {
      out.thought = e.thought || ''
      out.needs = e.needs || ''
      if (out.thought && (!feed.length || feed[feed.length - 1].text !== out.thought)) add({ time: e.time, who: 'godling', text: out.thought })
    } else if (e.kind === 'bubble' && e.ok) out.bubble = { thing: e.thing, feeling: e.feeling }
    else if (e.kind === 'project' && e.phase === 'start') out.intention = e.intention || e.goal || ''
    else if (e.kind === 'event') add({ time: e.time, who: e.sky ? 'sky' : 'notice', text: e.text, glance: null })
    else if (e.kind === 'glance') {
      const seen = [...feed].reverse().find((n) => n.text === e.text && n.glance === null)
      if (seen) seen.glance = e.turned ? e.degrees : 0
    }
  }
  out.feed = feed
  return out
}

const ago = (ms) => {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 90) return `${s} s ago`
  if (s < 5400) return `${Math.round(s / 60)} min ago`
  if (s < 172800) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} days ago`
}
const when = (t) => new Date(t).toLocaleString(undefined, { weekday: 'short', hour: '2-digit', minute: '2-digit' })

export function createReplayUI({ stage, dock, liveBadge, el, text, icon, tellView, tell, show, onChange }) {
  let on = false
  let index = null
  let base = ''
  let at = 0 // where the playhead is (UTC ms), as the island's page last said
  let edge = 0
  let speed = 1
  let paused = false
  let spanMs = 6 * 3600e3
  let spanChosen = false
  let win = [0, 0]
  let marks = []
  let sky = []
  let tracks = null
  let tracksWanted = 0
  let scrubbing = false
  let indexTimer = 0
  let urlAt = 0
  const actsShown = new Set()

  // ---- the parts ----
  const rewind = el('button', 'b-rewind cam', `${icon('back', 2)}<span>Rewind</span>`)
  rewind.type = 'button'
  rewind.title = "Watch the island's past"
  stage.append(rewind)

  const panel = el('section', 'b-replay stone')
  panel.hidden = true
  panel.setAttribute('aria-label', "The island's past")
  const controls = el('div', 'r-controls')
  const playBtn = el('button', 'r-play block')
  playBtn.type = 'button'
  const back = el('button', 'r-jump quiet', '−1 min')
  const ahead = el('button', 'r-jump quiet', '+1 min')
  back.type = ahead.type = 'button'
  const speeds = el('div', 'r-speeds')
  speeds.setAttribute('role', 'group')
  speeds.setAttribute('aria-label', 'Speed')
  const speedBtns = SPEEDS.map((s) => {
    const b = text('button', 'r-speed', `${s}×`)
    b.type = 'button'
    b.addEventListener('click', () => command({ speed: s }, () => { speed = s }))
    speeds.append(b)
    return b
  })
  const label = el('p', 'r-when')
  label.setAttribute('aria-live', 'off')
  const share = text('button', 'r-share quiet', 'Share this moment')
  share.type = 'button'
  const goLive = el('button', 'r-live get', '<span class="dot" aria-hidden="true"></span>Go live')
  goLive.type = 'button'
  controls.append(playBtn, back, ahead, speeds, label, share, goLive)

  const strip = el('div', 'r-strip')
  const bar = el('div', 'r-bar')
  bar.setAttribute('role', 'slider')
  bar.setAttribute('aria-label', 'Time')
  bar.tabIndex = 0
  const head = el('div', 'r-head')
  const tip = el('div', 'r-tip stone')
  tip.hidden = true
  bar.append(head)
  const spans = el('div', 'r-spans')
  spans.setAttribute('role', 'group')
  spans.setAttribute('aria-label', 'How much of the past the timeline shows')
  const spanBtns = SPANS.map(([ms, words]) => {
    const b = text('button', 'r-span', words)
    b.type = 'button'
    b.addEventListener('click', () => {
      spanMs = ms
      spanChosen = true
      placeWindow(true)
      drawSpans()
    })
    spans.append(b)
    return b
  })
  strip.append(bar, spans)
  panel.append(controls, strip, tip)
  dock.prepend(panel)

  // ---- talking to the island's page ----
  function command(m, then) {
    then?.()
    tellView({ type: 'godling-replay', ...m })
    drawControls()
  }

  async function fetchIndex() {
    try {
      const res = await fetch('api/replay/index', { cache: 'no-store' })
      index = await res.json()
    } catch {
      return null
    }
    base = new URL(index.chunks || 'replay', location.href).href
    const segs = index.segments || []
    edge = segs.length ? segs[segs.length - 1].end : 0
    return index
  }

  async function start(t, opts = {}) {
    if (!(await fetchIndex()) || !(index.segments || []).length) {
      tell('Nothing has been recorded yet: the past starts once the island has run a little.', 'no')
      return
    }
    on = true
    speed = opts.speed || speed
    paused = false
    if (!spanChosen) { // a young island's past fits a short span; after that, the viewer's choice stays
      const recorded = edge - index.segments[0].start
      spanMs = (SPANS.find(([ms]) => ms >= recorded * 1.1) || SPANS[SPANS.length - 1])[0]
    }
    at = Math.min(t ?? edge - 10 * 60e3, edge - 1000)
    tellView({ type: 'godling-replay', action: 'start', t: at, base, segments: index.segments, chunkMs: index.chunk_ms,
      speed, paused })
    stage.classList.add('replaying')
    panel.hidden = false
    rewind.hidden = true
    actsShown.clear()
    placeWindow(true)
    drawControls()
    clearInterval(indexTimer)
    indexTimer = setInterval(async () => {
      if (await fetchIndex()) tellView({ type: 'godling-replay', action: 'segments', segments: index.segments })
    }, INDEX_EVERY)
    onChange(true)
  }

  function stop() {
    if (!on) return
    on = false
    clearInterval(indexTimer)
    tellView({ type: 'godling-replay', action: 'live' })
    stage.classList.remove('replaying')
    panel.hidden = true
    rewind.hidden = false
    const url = new URL(location.href)
    url.searchParams.delete('t')
    history.replaceState(null, '', url)
    drawControls()
    onChange(false)
  }

  function seek(t) {
    at = Math.max(index?.segments?.[0]?.start ?? t, Math.min(t, edge - 1000))
    actsShown.clear()
    command({ action: 'seek', t: at })
    drawHead()
  }

  // ---- the timeline ----
  function placeWindow(force) {
    const end = edge || Date.now()
    const [from, to] = win
    const margin = (to - from) * 0.05
    // Kept while the playhead is well inside it; near its right end too when that end is (nearly) now.
    if (!force && to - from === spanMs && at >= from + margin && (at <= to - margin || to >= end - 30e3)) return
    const winTo = at > end - spanMs * 0.9 ? end : Math.min(end, at + spanMs / 2)
    win = [winTo - spanMs, winTo]
    loadTimeline()
  }

  async function loadTimeline() {
    const [from, to] = win.map(Math.round)
    const q = `from=${from}&to=${to}`
    try {
      const [m, s] = await Promise.all([fetch(`api/replay/marks?${q}`).then((r) => r.json()),
        fetch(`api/replay/sky?${q}`).then((r) => r.json())])
      marks = Array.isArray(m) ? m : []
      sky = Array.isArray(s) ? s : []
    } catch {
      marks = []
      sky = []
    }
    drawBar()
  }

  const x = (t) => ((t - win[0]) / (win[1] - win[0])) * 100

  function drawBar() {
    // Day and night, and rain, from the island's clock once a minute; runs of one kind become one stop.
    const stops = []
    let last = null
    for (const s of sky) {
      const kind = s.rain >= 0.3 ? 'rain' : s.hour >= 6 && s.hour < 19.5 ? 'day' : 'night'
      if (kind !== last) stops.push([x(s.t), kind])
      last = kind
    }
    const colour = { day: 'var(--r-day)', night: 'var(--r-night)', rain: 'var(--r-rain)' }
    bar.style.backgroundImage = stops.length
      ? `linear-gradient(90deg, ${stops.map(([p, k], i) => `${colour[k]} ${Math.max(0, p)}% ${i + 1 < stops.length ? Math.max(0, stops[i + 1][0]) : 100}%`).join(', ')})`
      : ''
    bar.replaceChildren(head)
    // Where there is no record (before the first start, or while the island restarted): hatched.
    const segs = index?.segments || []
    let cursor = win[0]
    for (const s of [...segs, { start: win[1], end: win[1] }]) {
      if (s.start > cursor) {
        const gap = el('span', 'r-gap')
        gap.style.left = `${Math.max(0, x(cursor))}%`
        gap.style.width = `${Math.max(0, Math.min(100, x(s.start)) - Math.max(0, x(cursor)))}%`
        bar.append(gap)
      }
      cursor = Math.max(cursor, s.end)
    }
    // Markers: close ones share a button, which names them all.
    let prev = null
    for (const m of marks) {
      const [ico, words] = MARKS[m.m] || ['notice', m.m]
      const p = x(m.t)
      if (p < 0 || p > 100) continue
      if (prev && p - prev.p < 1.2) {
        prev.b.title += `\n${when(m.t)} · ${words}`
        continue
      }
      const b = el('button', `r-mark ${m.m}`, icon(ico, 1))
      b.type = 'button'
      b.style.left = `${p}%`
      b.title = `${when(m.t)} · ${words}`
      b.setAttribute('aria-label', b.title)
      b.addEventListener('click', (e) => {
        e.stopPropagation()
        seek(m.t - 5000)
      })
      bar.append(b)
      prev = { p, b }
    }
    drawHead()
  }

  function drawHead() {
    head.style.left = `${Math.min(100, Math.max(0, x(at)))}%`
    bar.setAttribute('aria-valuetext', `${when(at)}, ${ago(Date.now() - at)}`)
    label.replaceChildren(text('b', '', when(at)), text('span', '', ago(Date.now() - at)))
  }

  function drawControls() {
    playBtn.innerHTML = icon(paused ? 'play' : 'pause', 2)
    playBtn.setAttribute('aria-label', paused ? 'Play' : 'Pause')
    speedBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(SPEEDS[i] === speed)))
    drawSpans()
    liveBadge.classList.toggle('past', on)
    liveBadge.querySelector('.word').textContent = on ? 'Replay' : 'Live'
  }

  function drawSpans() {
    spanBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(SPANS[i][0] === spanMs)))
  }

  const timeAt = (clientX) => {
    const r = bar.getBoundingClientRect()
    return win[0] + ((clientX - r.left) / r.width) * (win[1] - win[0])
  }
  bar.addEventListener('pointerdown', (e) => {
    if (e.target.closest('.r-mark')) return
    scrubbing = true
    bar.setPointerCapture(e.pointerId)
    at = timeAt(e.clientX)
    drawHead()
  })
  bar.addEventListener('pointermove', (e) => {
    const t = timeAt(e.clientX)
    tip.hidden = false
    tip.textContent = `${when(t)} · ${ago(Date.now() - t)}`
    const r = bar.getBoundingClientRect()
    const pr = panel.getBoundingClientRect()
    tip.style.left = `${Math.min(pr.width - tip.offsetWidth - 8, Math.max(8, e.clientX - pr.left - tip.offsetWidth / 2))}px`
    tip.style.top = `${r.top - pr.top - tip.offsetHeight - 6}px`
    if (scrubbing) {
      at = t
      drawHead()
    }
  })
  bar.addEventListener('pointerleave', () => { tip.hidden = true })
  bar.addEventListener('pointerup', () => {
    if (!scrubbing) return
    scrubbing = false
    seek(at)
  })
  bar.addEventListener('keydown', (e) => {
    const step = { ArrowLeft: -60e3, ArrowRight: 60e3, PageDown: -600e3, PageUp: 600e3 }[e.key]
    if (step) {
      e.preventDefault()
      seek(at + step)
    }
  })

  playBtn.addEventListener('click', () => command({ paused: !paused }, () => { paused = !paused }))
  back.addEventListener('click', () => seek(at - 60e3))
  ahead.addEventListener('click', () => seek(at + 60e3))
  goLive.addEventListener('click', stop)
  rewind.addEventListener('click', () => start())
  share.addEventListener('click', async () => {
    const url = new URL(location.href)
    url.searchParams.set('t', new Date(Math.round(at)).toISOString())
    try {
      await navigator.clipboard.writeText(url.href)
      tell('A link to this moment is copied.')
    } catch {
      tell(`A link to this moment: ${url.href}`)
    }
  })

  // ---- what the island's page says, about four times a second ----
  async function fetchTracks(t) {
    tracksWanted = t
    try {
      const got = await fetch(`api/replay/tracks?from=${Math.round(t)}&to=${Math.round(t + TRACKS_AHEAD)}`).then((r) => r.json())
      if (tracksWanted === t && Array.isArray(got.entries)) tracks = got
    } catch { /* keep the last */ }
  }

  function heard(m) {
    if (!on) return
    if (m.type === 'godling-replay-gap') {
      tell('The island was restarting here: on to where it came back.')
      return
    }
    if (m.type !== 'godling-replay-time') return
    if (m.problem === 'newer') tell('This part of the past was recorded by a newer island: reload the page to see it.', 'no')
    const before = at
    if (!scrubbing) at = m.t
    edge = Math.max(edge, m.edge || 0)
    paused = m.paused
    if (!paused && speed >= 1 && at >= edge - 1500) { // caught up with now
      tell('Caught up: this is the island live.')
      stop()
      return
    }
    placeWindow(false)
    drawHead()
    drawControls()
    if (!tracks || at < tracks.from || at > tracks.to - 60e3) {
      if (tracksWanted !== Math.round(at)) fetchTracks(Math.round(at))
    }
    const entries = tracks ? [...tracks.lead, ...tracks.entries.filter((e) => e.time * 1000 <= at)] : []
    show({ clock: m.clock, godling: m.godling, mind: reduceStatus(entries), now: at / 1000 })
    // What viewers did, as the playhead passes it (not while skipping about).
    if (tracks && at - before > 0 && at - before < 60e3) {
      for (const a of tracks.acts || []) {
        const key = `${a.time}:${a.id}`
        if (a.time * 1000 > before && a.time * 1000 <= at && !actsShown.has(key)) {
          actsShown.add(key)
          show({ act: { ...a, id: `past:${key}` } })
        }
      }
    }
    if (Date.now() - urlAt > 2000) { // the address bar holds the moment, to share or to reload into
      urlAt = Date.now()
      const url = new URL(location.href)
      url.searchParams.set('t', new Date(Math.round(at)).toISOString())
      history.replaceState(null, '', url)
    }
  }

  drawControls()
  return {
    get on() { return on },
    start,
    stop,
    heard,
    // The island's page reloaded: it starts live; take it back to where the playhead was.
    reloaded() {
      if (on) {
        tellView({ type: 'godling-replay', action: 'start', t: at, base, segments: index.segments, chunkMs: index.chunk_ms,
          speed, paused })
      }
    },
  }
}
