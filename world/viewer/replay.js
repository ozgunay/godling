// The island's past on the viewers' screen (ADR-016): a timeline to scrub, speeds, markers for what happened, and
// "Go live". The island's own page plays the chunks (world/renderer/src/replay.js); this page says where and how fast,
// and fills the screen around it from the tracks: what Godling thought, needed and noticed, and what viewers did.
// Anyone may watch the whole history (D1); powers rest while you watch the past (D6).

const TRACKS_BEFORE = 2 * 60e3 // the screen's tracks are fetched from a little before the playhead…
const TRACKS_AHEAD = 30 * 60e3 // …to this far past it
const INDEX_EVERY = 10e3
const SPANS = [[60 * 60e3, '1 h'], [6 * 3600e3, '6 h'], [24 * 3600e3, '24 h'], [7 * 86400e3, '7 days']]
const SPEEDS = [1, 2, 4, 8, 16]
const MARKS = { // what a marker on the timeline means (mind/godling/replay.py marks_of), with its icon
  rain: ['rain', 'Rain began'], fog: ['sky', 'Fog rolled in'], ship: ['wave', 'A ship passed'],
  meteor: ['meteor', 'A meteor'], earthquake: ['quake', 'An earthquake'], lightning: ['lightning', 'Lightning'],
  stone: ['stone', 'A stone from the sky'], log: ['log', 'A log from the sky'], regrow: ['sapling', 'A palm grew back'],
  note: ['glider', 'A note drifted down'], fire: ['fire', 'Godling made fire'], 'fire-out': ['drop', 'A fire went out'],
  fish: ['fish', 'Godling caught a fish'], hurt: ['heartHalf', 'Godling was hurt'], faint: ['heartEmpty', 'Godling fainted'],
  death: ['heartEmpty', 'Godling died'], // with its cause, when the mark has one (DIED_OF)
  storm: ['lightning', 'A storm'], struck: ['lightning', 'Lightning struck Godling'],
  wall: ['stone', 'Godling built a wall'], roof: ['stone', 'Godling built a roof'], enclosure: ['stone', 'Godling closed a room'],
}
const PROBLEMS = {
  newer: 'This part of the past was recorded by a newer island: reload the page to see it.',
  unsupported: 'This browser cannot play the island’s past. A newer browser can.',
}

// The last item that passes `test`, or undefined (Array.prototype.findLast needs Safari 15.4; phones older than that
// watch too).
// What killed Godling (main.lua DEATH's DiedOf), in viewers' words.
const DIED_OF = { Hunger: 'hunger', Cold: 'the cold', HungerAndCold: 'hunger and cold', Lightning: 'lightning',
  Meteor: 'a meteor', Storm: 'a lightning strike', Sea: 'drowning' }
export const diedOf = (cause) => DIED_OF[cause] || String(cause || 'something').toLowerCase()

export function lastOf(items, test) {
  for (let i = items.length - 1; i >= 0; i--) if (test(items[i])) return items[i]
  return undefined
}
export const isThought = (line) => line.who === 'godling' && !line.about

// The newest `most` lines of a feed, at most `worldMost` of them the world's (notices, the sky's doings), so they never
// crowd Godling's own out; and its newest thought always, however much came after it. The screen keeps fewer than the
// panel sends (viewer.js), by the same rule.
export function keepLines(feed, most, worldMost) {
  const kept = []
  let world = 0
  for (let i = feed.length - 1; i >= 0 && kept.length < most; i--) {
    if (feed[i].who !== 'godling' && world++ >= worldMost) continue
    kept.unshift(feed[i])
  }
  const latest = lastOf(feed, isThought)
  if (latest && !kept.includes(latest)) {
    if (kept.length >= most) kept.shift()
    kept.unshift(latest)
  }
  return kept
}

// What the screen shows of Godling's mind after these entries of its log, the way the guest panel reads it live
// (mind/godling/replay.py reduce_status).
export function reduceStatus(entries, feedKept = 8, worldKept = Math.floor(feedKept / 2)) {
  const out = { thought: '', needs: '', intention: '', now: null }
  const feed = []
  let agenda = 0
  let step = 0
  let said = null // the last thought in the feed, which is not said again
  const say = (e, about, text, more = {}) => feed.push({ time: e.time, who: 'godling', about, text, ...more })
  for (const e of entries) {
    if (e.kind === 'decision') {
      out.thought = e.thought || ''
      out.needs = e.needs || ''
      if (out.thought && out.thought !== said) {
        feed.push({ time: e.time, who: 'godling', text: out.thought })
        said = out.thought
      }
      agenda = Number.isInteger(e.agenda) ? e.agenda : (e.projects || []).filter((p) => p?.steps?.length).length
      step = 0
      out.now = null
    } else if (e.kind === 'bubble' && e.ok) out.bubble = { thing: e.thing, feeling: e.feeling }
    else if (e.kind === 'thinking') {
      if (!out.now?.thinking) out.now = { time: e.time, thinking: true } // thinking since the first time it said so
    } else if (e.kind === 'project' && e.phase === 'start' && e.stopgap) { // no step of the agenda (ADR-030)
      out.intention = e.intention || e.goal || ''
      out.now = { time: e.time, text: out.intention }
    } else if (e.kind === 'project' && e.phase === 'start') {
      out.intention = e.intention || e.goal || ''
      step += 1
      out.now = { time: e.time, text: out.intention, step, of: agenda }
    } else if (e.kind === 'project' && e.phase === 'end') {
      const text = e.intention || out.now?.text || e.goal
      if (e.ok === false && text) say(e, 'failed', text)
      out.now = null
    } else if (e.kind === 'plan_discarded') { // something happened that it stopped for, to think again
      const last = feed[feed.length - 1]
      if (last?.about === 'failed') last.about = 'stopped'
    } else if (e.kind === 'learn' && e.name) say(e, 'learned', e.does || '', { name: e.name })
    else if (e.kind === 'sleep' && e.dream) say(e, 'dream', e.dream)
    else if (e.kind === 'event') feed.push({ time: e.time, who: e.sky ? 'sky' : 'notice', text: e.text, glance: null })
    else if (e.kind === 'glance') {
      const seen = lastOf(feed, (n) => n.text === e.text && n.glance === null)
      if (seen) seen.glance = e.turned ? e.degrees : 0
    }
  }
  out.feed = keepLines(feed, feedKept, worldKept)
  return out
}

const ago = (ms) => {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 90) return `${s} s ago`
  if (s < 5400) return `${Math.round(s / 60)} min ago`
  if (s < 172800) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} days ago`
}
export const when = (t) => new Date(t).toLocaleString(undefined, { weekday: 'short', hour: '2-digit', minute: '2-digit' })

export function createReplayUI({ stage, dock, rewindIn, el, text, icon, tellView, tell, show, onChange }) {
  let on = false
  let ready = false // the island's page has said it can hear the screen (godling-ready)
  let pending = null // a moment to open once it can (a shared link)
  let index = null // the last good index
  let at = 0 // where the playhead is (UTC ms), as the island's page last said
  let edge = 0
  let speed = 1
  let paused = false
  let waiting = false
  let spanMs = 6 * 3600e3
  let spanChosen = false
  let win = [0, 0]
  let marks = []
  let sky = []
  let timelineAsked = 0
  let tracks = null
  let tracksLoading = false
  let scrubbing = false
  let indexTimer = 0
  let indexLoading = false
  let urlAt = 0
  let pass = 0 // each start and seek is a new pass over the past: its pop-ups show again
  let drawn = '' // what the HUD last drew, to draw it again only when it changes
  let controlsDrawn = ''

  // ---- the parts ----
  const rewind = el('button', 'b-rewind cam', `${icon('back', 2)}<span>Rewind</span>`)
  rewind.type = 'button'
  rewind.title = "Watch the island's past"
  rewindIn.append(rewind) // beside the camera buttons: on a phone, an icon in the top row, clear of the feed

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
    b.addEventListener('click', () => {
      speed = s
      command({ speed })
    })
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
      drawControls()
    })
    spans.append(b)
    return b
  })
  strip.append(bar, spans)
  panel.append(controls, strip, tip)
  dock.prepend(panel)

  // ---- talking to the island's page ----
  function command(m) {
    tellView({ type: 'godling-replay', ...m })
    drawControls()
  }

  const startMessage = () => ({ action: 'start', t: at, base: new URL(index.chunks || 'replay', location.href).href,
    remote: index.chunks_url ? new URL(index.chunks_url, location.href).href : '', remoteUntil: index.chunks_url_until ?? 0,
    segments: index.segments, chunkMs: index.chunk_ms, speed, paused })

  // The index, kept only if it is one: a site or panel that is out of reach answers with an error instead.
  async function fetchIndex() {
    if (indexLoading) return Boolean(index)
    indexLoading = true
    try {
      const res = await fetch('api/replay/index', { cache: 'no-store' })
      const got = res.ok ? await res.json() : null
      if (got && Array.isArray(got.segments)) {
        index = got
        edge = got.segments.length ? got.segments[got.segments.length - 1].end : 0
      }
    } catch { /* keep the last good one */ }
    indexLoading = false
    return Boolean(index)
  }

  async function start(t) {
    if (!ready) { // the island's page is still loading: open the moment when it can hear us
      pending = t ?? null
      return
    }
    if (!(await fetchIndex()) || !index.segments.length) {
      tell(index ? 'Nothing has been recorded yet: the past starts once the island has run a little.'
        : "The island's past is out of reach. Try again in a moment.", 'no')
      return
    }
    on = true
    paused = false
    pass += 1
    if (!spanChosen) { // a young island's past fits a short span; after that, the viewer's choice stays
      const recorded = edge - index.segments[0].start
      spanMs = (SPANS.find(([ms]) => ms >= recorded * 1.1) || SPANS[SPANS.length - 1])[0]
    }
    at = Math.min(t ?? edge - 10 * 60e3, edge - 1000)
    command(startMessage())
    stage.classList.add('replaying')
    panel.hidden = false
    rewind.hidden = true
    drawn = ''
    placeWindow(true)
    clearInterval(indexTimer)
    indexTimer = setInterval(async () => {
      if (await fetchIndex()) {
        tellView({ type: 'godling-replay', action: 'segments', segments: index.segments,
          remoteUntil: index.chunks_url_until ?? 0 })
      }
    }, INDEX_EVERY)
    onChange(true)
  }

  function stop() {
    pending = null
    if (!on) return
    on = false
    clearInterval(indexTimer)
    tellView({ type: 'godling-replay', action: 'live' })
    stage.classList.remove('replaying')
    panel.hidden = true
    rewind.hidden = false
    tracks = null
    const url = new URL(location.href)
    url.searchParams.delete('t')
    history.replaceState(null, '', url)
    onChange(false)
  }

  function seek(t) {
    at = Math.max(index?.segments?.[0]?.start ?? t, Math.min(t, edge - 1000))
    pass += 1
    command({ action: 'seek', t: at })
    drawHead()
  }

  // ---- the timeline ----
  function placeWindow(force) {
    const end = edge || Date.now()
    const [from, to] = win
    const margin = (to - from) * 0.05
    // Kept while the playhead is well inside it; near its right end too, until now has moved on a fiftieth of it.
    if (!force && to - from === spanMs && at >= from + margin &&
        (at <= to - margin || to >= end - Math.max(30e3, spanMs / 50))) return
    const winTo = at > end - spanMs * 0.9 ? end : Math.min(end, at + spanMs / 2)
    win = [winTo - spanMs, winTo]
    loadTimeline()
  }

  async function loadTimeline() {
    const [from, to] = win.map(Math.round)
    const asked = ++timelineAsked
    const q = `from=${from}&to=${to}`
    const every = Math.max(60e3, Math.round(spanMs / 600)) // about one sample per bar pixel or two
    try {
      const [m, s] = await Promise.all([fetch(`api/replay/marks?${q}`).then((r) => r.json()),
        fetch(`api/replay/sky?${q}&every=${every}`).then((r) => r.json())])
      if (asked !== timelineAsked) return // a newer window was asked for meanwhile
      marks = (Array.isArray(m) ? m : []).sort((a, b) => a.t - b.t)
      sky = Array.isArray(s) ? s : []
    } catch {
      if (asked !== timelineAsked) return
      marks = []
      sky = []
    }
    drawBar()
  }

  const x = (t) => ((t - win[0]) / (win[1] - win[0])) * 100

  function drawBar() {
    // Day and night, and rain, from the island's clock; runs of one kind become one stop.
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
      const [ico, said] = MARKS[m.m] || ['notice', m.m]
      const words = m.m === 'death' && m.cause ? `${said} of ${diedOf(m.cause)}` : said
      const p = x(m.t)
      if (p < 0 || p > 100) continue
      if (prev && p - prev.p < 1.2) {
        prev.b.title += `\n${when(m.t)} · ${words}`
        prev.b.setAttribute('aria-label', prev.b.title)
        continue
      }
      const b = el('button', 'r-mark', icon(ico, 1))
      b.type = 'button'
      b.dataset.mark = m.m
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
    label.replaceChildren(text('b', '', when(at)), text('span', '', waiting ? 'loading…' : ago(Date.now() - at)))
  }

  function drawControls() {
    const shown = `${paused}:${speed}:${spanMs}`
    if (shown === controlsDrawn) return
    controlsDrawn = shown
    playBtn.innerHTML = icon(paused ? 'play' : 'pause', 2)
    playBtn.setAttribute('aria-label', paused ? 'Play' : 'Pause')
    speedBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(SPEEDS[i] === speed)))
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
  for (const gone of ['pointercancel', 'lostpointercapture']) { // a touch taken over by the page: no seek, no freeze
    bar.addEventListener(gone, () => { scrubbing = false })
  }
  bar.addEventListener('keydown', (e) => {
    const step = { ArrowLeft: -60e3, ArrowRight: 60e3, PageDown: -600e3, PageUp: 600e3 }[e.key]
    if (step) {
      e.preventDefault()
      seek(at + step)
    }
  })

  playBtn.addEventListener('click', () => {
    paused = !paused
    command({ paused })
  })
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
  // One request at a time, kept if it covers where the playhead is by the time it comes (on a slow link, a request
  // per report would never be answered in time to be kept).
  async function fetchTracks() {
    if (tracksLoading) return
    tracksLoading = true
    const t = Math.round(at)
    try {
      const got = await fetch(`api/replay/tracks?from=${t - TRACKS_BEFORE}&to=${t + TRACKS_AHEAD}`).then((r) => r.json())
      if (on && Array.isArray(got.entries)) tracks = got
    } catch { /* keep the last; the next report asks again */ }
    tracksLoading = false
  }

  const covers = (tr) => tr && at >= tr.from && at <= tr.to - 60e3

  function hud(m) {
    const entries = covers(tracks) ? [...tracks.lead, ...tracks.entries.filter((e) => e.time * 1000 <= at)] : []
    const mind = reduceStatus(entries)
    const c = m.clock || {}
    const g = m.godling
    const key = JSON.stringify([mind.thought, mind.needs, mind.bubble, mind.now,
      mind.feed.map((f) => [f.time, f.text, f.glance, f.about]),
      Math.floor((c.hour ?? -1) * 60), c.day, c.rain >= 0.3, c.quake,
      g && [Math.round((g.health ?? 100) / 5), Math.round((g.hunger ?? 100) / 5), g.cold, g.wet >= 30, g.bracing, g.knockedDown,
        g.drowning, g.dead, g.deadFor, g.deaths, g.scorched > 0]])
    if (key === drawn) return
    drawn = key
    show({ clock: m.clock, godling: m.godling, mind, now: at / 1000 })
  }

  function heard(m) {
    if (m.type === 'godling-ready') {
      ready = true
      if (on) command(startMessage()) // a reloaded island page: back to where the playhead was
      else if (pending !== null) start(pending)
      return
    }
    if (!on) return
    if (m.type === 'godling-replay-gap') {
      tell('The island was restarting here: on to where it came back.')
      return
    }
    if (m.type === 'godling-replay-problem') {
      tell(PROBLEMS[m.problem] || 'Part of the past could not be played.', 'no')
      return
    }
    if (m.type !== 'godling-replay-time') return
    const before = at
    if (!scrubbing) at = m.t
    paused = Boolean(m.paused)
    waiting = Boolean(m.waiting)
    if (!paused && !waiting && at >= edge - 1500) { // caught up with now
      tell('Caught up: this is the island live.')
      stop()
      return
    }
    placeWindow(false)
    drawHead()
    drawControls()
    if (!covers(tracks)) fetchTracks()
    hud(m)
    // What viewers did, as the playhead passes it (not while skipping about). Each pass shows them again.
    if (covers(tracks) && at - before > 0 && at - before < 60e3) {
      for (const a of tracks.acts || []) {
        if (a.time * 1000 > before && a.time * 1000 <= at) show({ act: { ...a, id: `past:${pass}:${a.time}:${a.id}` } })
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
    get at() { return at }, // the playhead (UTC ms), for a viewer's bug report from the past
    start,
    stop,
    heard,
    // The island's page was (re)loaded: it will say when it can hear the screen again.
    reloading() { ready = false },
  }
}
