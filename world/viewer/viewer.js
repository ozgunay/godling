// Godling's viewer screen, live: the Block HUD over the island (see .impeccable/surfaces/world-viewer-index-html.md).
// The guest panel (tools/guest_panel.py) serves it and answers /api/status, /api/power and /api/note. The three HUD
// prototypes it was chosen from live in prototypes/.
import { icon } from './icons.js'

const DAY_SECONDS = 2400 // main.lua DAY_SECONDS: one island day
const POLL_MS = 1500
const POPUP_MS = 9000 // a viewer's pop-up stays this long; a note's a little longer
const POPUPS_SHOWN = 4
const FEED_SHOWN = 5
const PHONE = () => matchMedia('(max-width: 760px)').matches
const EURO = (credits) => `€${(credits * 0.05).toFixed(2)}`
const FREE_KEYS = new Set(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyQ', 'KeyE', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
  'ShiftLeft', 'ShiftRight', 'Space'])

// What a viewer can call, in hotbar order. `id` is the world's name for it (main.lua SKY_POWERS).
// Viewers aim every power but the earthquake and the note. Only the meteor lands on Godling or on what it built
// (main.lua sky.aim, the user's rule); the rest go to the nearest clear spot, and a gift aimed at Godling lands at its
// feet. The meteor is priced as the disaster it is.
const POWERS = [
  { id: 'Stone', name: 'Stone', icon: 'stone', price: 4, kind: 'Gift', aim: true, did: 'dropped a stone', after: 'from the sky',
    does: 'A stone block drops where you aim. Aimed at Godling, it lands at its feet; it never lands on its walls.' },
  { id: 'Log', name: 'Log', icon: 'log', price: 4, kind: 'Gift', aim: true, did: 'dropped a log', after: 'from the sky',
    does: 'A log beam drops where you aim. Aimed at Godling, it lands at its feet; it never lands on its walls.' },
  { id: 'Regrow', name: 'Regrow a palm', icon: 'sapling', price: 6, kind: 'Gift', aim: true, did: 'regrew a palm',
    after: 'from its stump', does: 'The stump nearest your aim grows back at once.' },
  { id: 'Lightning', name: 'Lightning', icon: 'lightning', price: 40, kind: 'Wonder', aim: true, did: 'called lightning',
    after: 'a palm comes down', does: 'Strikes the palm nearest your aim and fells it into two logs. Only palms well away from Godling and its walls.' },
  { id: 'Meteor', name: 'Meteor', icon: 'meteor', price: 300, kind: 'Disaster', harm: true, aim: true, did: 'called a meteor',
    after: 'it blasts in 40 s', does: 'A shadow spreads where you aim; 40 s later a stone blasts there, whatever stands in it: Godling, its walls, palms. It leaves a crater.',
    rule: 'The only power that can hit Godling or its walls · one a minute · never while Godling is weak' },
  { id: 'Earthquake', name: 'Earthquake', icon: 'quake', price: 500, kind: 'Disaster', harm: true, did: 'shook the island',
    after: 'the ground rumbles', does: 'The ground rumbles, then shakes for 20 s. Loose pieces fall, fastened ones hold. Godling braces; it is never hurt.',
    rule: 'One every 10 minutes, never while Godling is weak' },
  { id: 'Note', name: 'Note', icon: 'glider', price: 0, kind: 'Words', note: true,
    does: 'Fold a short note into a paper glider. Godling reads every note and decides for itself what to do.' },
]

const store = {
  get(key) { try { return localStorage.getItem(key) } catch { return null } },
  set(key, value) { try { localStorage.setItem(key, value) } catch { /* private window: forget it */ } },
}
const client = store.get('godling.client') || Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => (b % 36).toString(36)).join('')
store.set('godling.client', client)

const stage = document.getElementById('stage')
stage.classList.add('hud-block')
let status = null
let camera = store.get('godling.camera') === 'free' ? 'free' : 'follow'
const seen = new Set() // pop-ups already shown
const cooling = {} // power id -> when the world lets it be called again (ms)
let noteReadyAt = 0

function el(tag, cls, html) {
  const e = document.createElement(tag)
  if (cls) e.className = cls
  if (html !== undefined) e.innerHTML = html
  return e
}

function text(tag, cls, words) {
  const e = el(tag, cls)
  e.textContent = words
  return e
}

const clockText = (hour) => {
  const minutes = Math.floor((((hour % 24) + 24) % 24) * 60)
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}
const minutesText = (s) => `${Math.floor(s / 60)}:${String(Math.ceil(s) % 60).padStart(2, '0')}`

// ---- the island ---------------------------------------------------------------------------

const view = el('iframe', 'island')
view.title = "Godling's island, live"
view.allow = 'fullscreen; autoplay'
stage.append(view)
let viewSrc = ''

function showView(url) {
  if (!url) return
  const src = url + (url.includes('?') ? '&' : '?') + 'embed=1'
  if (src === viewSrc) return
  viewSrc = src
  view.src = src
}

function tellView(message) {
  view.contentWindow?.postMessage({ source: 'godling-viewer', ...message }, '*')
}
view.addEventListener('load', () => tellView({ type: 'godling-camera', mode: camera }))

// ---- top: live and watching, the clock, the camera ----------------------------------------

const live = el('header', 'b-live stone')
live.innerHTML = `<span class="dot" aria-hidden="true"></span><b class="word">Live</b><span class="sep" aria-hidden="true"></span>${icon('eye', 3)}<b class="n">0</b><span class="label">watching</span>`
live.setAttribute('aria-live', 'polite')
stage.append(live)

const statusBar = el('div', 'b-status')
const clock = el('div', 'b-clock stone')
statusBar.append(clock)
const cameraGroup = el('div', 'camera b-camera')
cameraGroup.setAttribute('role', 'group')
cameraGroup.setAttribute('aria-label', 'Camera')
const followBtn = el('button', 'cam', `${icon('eye', 2)}<span>Follow Godling</span>`)
const freeBtn = el('button', 'cam', `${icon('move', 2)}<span>Free camera</span><span class="keys"><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd></span>`)
for (const [b, mode] of [[followBtn, 'follow'], [freeBtn, 'free']]) {
  b.type = 'button'
  b.addEventListener('click', () => setCamera(mode))
}
cameraGroup.append(followBtn, freeBtn)
statusBar.append(cameraGroup)
stage.append(statusBar)
const camHint = text('p', 'b-camhint', matchMedia('(pointer: coarse)').matches
  ? 'Drag to look · pinch to fly in and out'
  : 'W A S D to fly · Q E down and up · Shift to hurry · drag to look')
stage.append(camHint)

function setCamera(mode) {
  camera = mode
  store.set('godling.camera', mode)
  followBtn.setAttribute('aria-pressed', String(mode === 'follow'))
  freeBtn.setAttribute('aria-pressed', String(mode === 'free'))
  stage.classList.toggle('free-camera', mode === 'free')
  tellView({ type: 'godling-camera', mode })
}
setCamera(camera)

// ---- top-left: Godling's mind -------------------------------------------------------------

const mind = el('section', 'b-mind')
mind.setAttribute('aria-label', 'What Godling thinks and notices')
const feed = el('ol', 'feed b-feed')
const objective = el('p', 'b-objective')
mind.append(feed, objective)
stage.append(mind)

const speaker = { godling: () => icon('godling', 2), sky: () => icon('sky', 2), notice: () => icon('notice', 2) }
// What the mind noticed is written to Godling ("you") with the world's names and coordinates; viewers read it about
// Godling, with plain names and no coordinates. A line about "you" with no rewrite here is left out.
const ABOUT_GODLING = [
  [/^A paper glider drifted down\b.*?It reads: /, 'A note drifted down: '],
  [/^You were caught inside a piece.*$/, 'Godling got caught inside a piece and was pushed out'],
  [/^You were hurt by (.*?): your health is.*$/, 'Godling was hurt by $1'],
  [/^You have grown cold.*$/, 'Godling has grown cold'],
  [/^The ground is rumbling under you: /, 'The ground is rumbling: '],
]
const article = (name) => (/^[AEIOU]/.test(name) ? 'an ' : 'a ') + name.toLowerCase()
function plain(words, who = 'notice') {
  let s = String(words || '')
  for (const [from, to] of ABOUT_GODLING) s = s.replace(from, to)
  s = s.replace(/\s*\b(at|to|from|near) \(-?\d+(\.\d+)?, -?\d+(\.\d+)?\)/g, '')
    .replace(/\s*\(-?\d+(\.\d+)?, -?\d+(\.\d+)?\)/g, '')
    .replace(/: \w+_\d+( and \w+_\d+)* (landed|lies|lie)\b.*$/, '') // "a log dropped from the sky: Log_3 landed"
    .replace(/\b([A-Z][a-z]+)_\d+\b/g, (_, name) => article(name))
  s = s.charAt(0).toUpperCase() + s.slice(1)
  return who !== 'godling' && /\byou(r)?\b/i.test(s) ? '' : s
}
// Cut at a word, with an ellipsis, so a long line never ends mid-word.
function clip(s, most) {
  if (s.length <= most) return s
  const cut = s.slice(0, most)
  return `${cut.slice(0, Math.max(cut.lastIndexOf(' '), most * 0.6)).replace(/[\s,;:.]+$/, '')}…`
}

function needsIcon(words) {
  const w = words.toLowerCase()
  if (/log|wood|beam|lintel|plank/.test(w)) return 'log'
  if (/stone|block|rock|wall/.test(w)) return 'stone'
  if (/food|coconut|fish|eat|hungry/.test(w)) return 'coconut'
  if (/warm|fire|cold/.test(w)) return 'sun'
  return 'notice'
}

function drawMind(m, hour, now) {
  const lines = (m?.feed || []).map((f) => ({ ...f, words: plain(f.text, f.who) })).filter((f) => f.words)
    .slice(-(PHONE() ? 3 : FEED_SHOWN))
  feed.replaceChildren(...lines.map((f, i) => {
    const li = el('li', `line ${f.who}`)
    li.style.setProperty('--age', lines.length - 1 - i)
    if (Number.isFinite(hour) && f.time) li.append(text('time', '', clockText(hour - ((now - f.time) * 24) / DAY_SECONDS)))
    else li.append(el('time'))
    li.insertAdjacentHTML('beforeend', speaker[f.who]?.() || speaker.notice())
    const words = clip(f.words, 150)
    const span = text('span', 'text', f.who === 'godling' ? `“${words}”` : words)
    if (words !== f.words) span.title = f.words
    li.append(span)
    return li
  }))
  if (!lines.length) feed.append(el('li', 'line notice waiting', `<time></time>${icon('godling', 2)}<span class="text">Godling is waking up…</span>`))
  const needs = plain(m?.needs || '', 'godling')
  objective.hidden = !needs
  if (needs) {
    const first = needs.split(/;\s*/)[0]
    objective.innerHTML = `${icon(needsIcon(first), 2)}<b>Needs</b>`
    const what = text('span', 'what', first.charAt(0).toUpperCase() + first.slice(1))
    what.title = needs
    objective.append(what)
  }
}

// ---- right: what viewers did --------------------------------------------------------------

const popups = el('aside', 'b-popups')
popups.setAttribute('aria-label', 'What viewers did')
popups.setAttribute('role', 'log')
stage.append(popups)

function popup(entry, fresh = true) {
  if (seen.has(entry.id)) return
  seen.add(entry.id)
  if (!fresh) return
  const power = POWERS.find((p) => p.id === entry.power) || POWERS[0]
  const card = el('article', `b-pop stone${entry.kind === 'note' ? ' note' : ''}${power.harm ? ' harm' : ''}`)
  card.append(el('span', 'tile block', icon(power.icon, 3)))
  const body = el('div', 'body')
  const head = el('p', 'head')
  head.append(text('strong', '', entry.name || 'Someone'), document.createTextNode(entry.kind === 'note' ? ' sent Godling a note' : ` ${power.did}`))
  body.append(head)
  if (entry.kind === 'note') body.append(text('q', 'paper', entry.text))
  else body.append(text('small', '', power.after))
  card.append(body)
  popups.prepend(card)
  requestAnimationFrame(() => card.classList.add('in'))
  while (popups.children.length > (PHONE() ? 1 : POPUPS_SHOWN)) popups.lastChild.remove()
  stage.classList.add('has-pop')
  setTimeout(() => {
    card.classList.remove('in')
    card.classList.add('out')
    setTimeout(() => {
      card.remove()
      stage.classList.toggle('has-pop', popups.children.length > 0)
    }, 400)
  }, entry.kind === 'note' ? POPUP_MS + 5000 : POPUP_MS)
}

// ---- bottom: Godling's body, the hotbar, the note ------------------------------------------

const dock = el('footer', 'b-dock')
const vitals = el('div', 'b-vitals')
const say = el('p', 'b-say')
say.setAttribute('role', 'status')
const composer = el('form', 'b-note stone')
composer.hidden = true
composer.innerHTML = `<div class="n-head">${icon('glider', 3)}<label for="note-text">A note for Godling</label><span class="count">0/140</span></div>
  <textarea id="note-text" rows="2" maxlength="140" placeholder="Cheer it on, ask it something, tell it what you see…"></textarea>
  <div class="n-foot"><input id="note-name" maxlength="18" placeholder="Your name" autocomplete="nickname" aria-label="Your name">
  <button type="submit" class="get">Fold and send</button></div>
  <p class="n-hint">Godling reads every note and decides for itself what to do. No links. One note every 3 minutes.</p>`
const noteText = composer.querySelector('textarea')
const noteName = composer.querySelector('input')
const noteSend = composer.querySelector('button')
const noteCount = composer.querySelector('.count')
const noteHint = composer.querySelector('.n-hint')
noteName.value = store.get('godling.name') || ''

const belt = el('div', 'b-belt')
const bar = el('div', 'b-hotbar')
bar.setAttribute('role', 'toolbar')
bar.setAttribute('aria-label', 'Sky powers')
const slots = POWERS.map((p, i) => {
  const s = el('button', `slot block${p.harm ? ' harm' : ''}${p.note ? ' note' : ''}`)
  s.type = 'button'
  s.dataset.id = p.id
  s.setAttribute('aria-label', p.note ? 'Write Godling a note' : `${p.name}, ${p.price} credits`)
  s.innerHTML = `<kbd>${i + 1}</kbd>${icon(p.icon, 3)}<span class="n"></span><span class="price">${p.note ? 'free' : `${p.price} cr`}</span>`
  s.addEventListener('mouseenter', () => pick(p.id))
  s.addEventListener('focus', () => pick(p.id))
  s.addEventListener('mouseleave', () => { if (document.activeElement !== s) unpick() })
  s.addEventListener('blur', () => unpick())
  s.addEventListener('click', () => (p.note ? toggleNote() : p.aim ? toggleAim(p) : call(p, s)))
  bar.append(s)
  return s
})
const purse = el('div', 'b-purse stone', `${icon('coin', 3)}<span><b>Free</b>test mode<small>prices shown for later</small></span>`)
belt.append(bar, purse)
dock.append(composer, say, vitals, belt)
stage.append(dock)

let tip = null
function pick(id) {
  unpick()
  if (PHONE() || !composer.hidden || aiming) return // the note box and the aim bar sit where the tip would
  const p = POWERS.find((x) => x.id === id)
  const s = slots[POWERS.indexOf(p)]
  tip = el('div', 'tip b-tip stone')
  tip.setAttribute('role', 'tooltip')
  const wait = cooling[p.id] > Date.now() ? `<dt>Ready</dt><dd>in ${minutesText((cooling[p.id] - Date.now()) / 1000)}</dd>` : ''
  tip.innerHTML = `<div class="tip-head">${icon(p.icon, 2)}<strong>${p.name}</strong><em class="${p.harm ? 'harm' : ''}">${p.kind}</em></div>
    <p>${p.does}</p>
    <dl>${p.note ? `<dt>Price</dt><dd>Free · ${status?.notes?.limit || 140} characters</dd>` : `<dt>Price</dt><dd>${p.price} credits · ${EURO(p.price)}<span class="free">free while testing</span></dd>`}
    ${p.rule ? `<dt>Rule</dt><dd>${p.rule}</dd>` : ''}${wait}</dl>`
  stage.append(tip)
  const r = s.getBoundingClientRect(), sr = stage.getBoundingClientRect()
  tip.style.left = `${Math.max(16, Math.min(sr.width - tip.offsetWidth - 16, r.left - sr.left + r.width / 2 - tip.offsetWidth / 2))}px`
  tip.style.top = `${r.top - sr.top - tip.offsetHeight - 14}px`
}
function unpick() {
  tip?.remove()
  tip = null
}

let sayTimer = 0
function tell(words, tone = '') {
  say.textContent = words
  say.className = `b-say shown ${tone}`
  clearTimeout(sayTimer)
  sayTimer = setTimeout(() => { say.className = 'b-say' }, 6000)
}

async function post(path, body) {
  try {
    const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client, name: noteName.value.trim() || store.get('godling.name') || '', ...body }) })
    return await res.json()
  } catch {
    return { ok: false, text: 'The island is out of reach. Try again in a moment.' }
  }
}

async function call(p, s, at = null) {
  if (s.classList.contains('calling')) return
  if (cooling[p.id] > Date.now()) return tell(`${p.name} is not ready yet: ${minutesText((cooling[p.id] - Date.now()) / 1000)} to go.`)
  s.classList.add('calling')
  const answer = await post('api/power', { power: p.id, ...(at ? { at } : {}) })
  s.classList.remove('calling')
  if (answer.ok) popup(answer)
  else tell(answer.text || `${p.name} did not work.`, 'no')
  if (answer.wait) cooling[p.id] = Date.now() + answer.wait * 1000
  drawSlots()
}

// Aiming: pick a slot, and the island shows a ring where the power would land (renderer aim.js); a click there calls
// it. "Let the sky choose" calls it without an aim, as before.
let aiming = null
const aimBar = el('div', 'b-aim stone')
aimBar.hidden = true
aimBar.setAttribute('role', 'status')
const aimWords = el('p', 'words')
const skyChooses = el('button', 'get', 'Let the sky choose')
skyChooses.type = 'button'
const aimCancel = el('button', 'cancel', 'Cancel')
aimCancel.type = 'button'
aimBar.append(aimWords, skyChooses, aimCancel)
dock.prepend(aimBar)
const aimTap = matchMedia('(pointer: coarse)').matches ? 'Tap' : 'Click'

function aimHint(p, spot) {
  aimWords.replaceChildren()
  aimWords.insertAdjacentHTML('afterbegin', icon(p.icon, 2))
  let words = `${aimTap} the island where the ${p.name.toLowerCase()} should land`
  let tone = ''
  if (spot?.atGodling && p.id === 'Meteor') [words, tone] = ['On Godling: the blast will hit it', 'harm']
  else if (spot?.atGodling && (p.id === 'Stone' || p.id === 'Log')) [words, tone] = ['At Godling: it lands at its feet', 'feet']
  else if (spot) words = `${aimTap} to call it here`
  aimWords.append(text('span', tone, words))
}

function toggleAim(p) {
  if (aiming?.id === p.id) return endAim()
  if (cooling[p.id] > Date.now()) return tell(`${p.name} is not ready yet: ${minutesText((cooling[p.id] - Date.now()) / 1000)} to go.`)
  toggleNote(false)
  unpick() // the slot's focus opened its tip before the click; the aim bar takes that place
  aiming = p
  slots.forEach((s, i) => s.classList.toggle('aiming', POWERS[i] === p))
  stage.classList.add('aiming')
  aimBar.hidden = false
  aimHint(p)
  tellView({ type: 'godling-aim', power: p.id })
}

function endAim() {
  aiming = null
  slots.forEach((s) => s.classList.remove('aiming'))
  stage.classList.remove('aiming')
  aimBar.hidden = true
  tellView({ type: 'godling-aim', power: null })
}

skyChooses.addEventListener('click', () => {
  const p = aiming
  endAim()
  if (p) call(p, slots[POWERS.indexOf(p)])
})
aimCancel.addEventListener('click', endAim)

addEventListener('message', (event) => {
  const data = event.data
  if (event.source !== view.contentWindow || data?.source !== 'godling-renderer') return
  if (data.type === 'godling-aim-hover' && aiming) aimHint(aiming, data)
  else if (data.type === 'godling-aimed' && aiming) {
    const p = aiming
    endAim()
    call(p, slots[POWERS.indexOf(p)], [Number(data.x), Number(data.z)])
  } else if (data.type === 'godling-aim-cancel') endAim()
})

function toggleNote(open = composer.hidden) {
  if (open && aiming) endAim()
  composer.hidden = !open
  slots[POWERS.findIndex((p) => p.note)].classList.toggle('open', open)
  if (open) noteText.focus()
}

noteText.addEventListener('input', () => {
  const n = [...noteText.value].length
  noteCount.textContent = `${n}/${status?.notes?.limit || 140}`
  noteCount.classList.toggle('full', n >= (status?.notes?.limit || 140))
})
noteText.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    composer.requestSubmit()
  }
})
composer.addEventListener('submit', async (e) => {
  e.preventDefault()
  if (noteReadyAt > Date.now()) return
  store.set('godling.name', noteName.value.trim())
  noteSend.disabled = true
  const answer = await post('api/note', { text: noteText.value })
  noteSend.disabled = false
  noteHint.textContent = answer.text
  noteHint.className = `n-hint ${answer.ok ? 'yes' : 'no'}`
  if (answer.wait) noteReadyAt = Date.now() + answer.wait * 1000
  if (answer.ok) {
    noteText.value = ''
    noteCount.textContent = `0/${status?.notes?.limit || 140}`
  }
  drawSlots()
})

function drawSlots() {
  const now = Date.now()
  POWERS.forEach((p, i) => {
    const s = slots[i]
    const until = p.note ? noteReadyAt : cooling[p.id] || 0
    const left = Math.max(0, (until - now) / 1000)
    s.classList.toggle('cooling', left > 0)
    s.querySelector('.n').textContent = left > 0 ? minutesText(left) : ''
    s.style.setProperty('--cd', left > 0 ? Math.min(1, left / (p.note ? status?.notes?.every || 180 : 600)) : 0)
  })
  const left = Math.max(0, (noteReadyAt - now) / 1000)
  noteSend.disabled = left > 0
  noteSend.textContent = left > 0 ? `Next note in ${minutesText(left)}` : 'Fold and send'
}
setInterval(drawSlots, 1000)

function drawBody(g) {
  if (!g) {
    vitals.replaceChildren()
    return
  }
  const half = (v) => Math.round((v ?? 100) / 5) / 2 // hearts and coconuts fill in halves
  const health = half(g.health), hunger = half(g.hunger)
  const scale = PHONE() ? 2 : 3
  const hearts = Array.from({ length: 10 }, (_, i) => icon(health >= i + 1 ? 'heart' : health > i ? 'heartHalf' : 'heartEmpty', scale)).join('')
  const food = Array.from({ length: 10 }, (_, i) => icon(hunger >= 10 - i ? 'food' : hunger > 9 - i ? 'foodHalf' : 'foodEmpty', scale)).join('')
  const states = [g.knockedDown && ['quake', 'Knocked down'], g.bracing && ['quake', 'Bracing'], g.cold && ['cold', 'Cold'],
    g.wet >= 30 && ['drop', 'Wet']].filter(Boolean)
  vitals.innerHTML = `<span class="row hearts" role="img" aria-label="Health ${Math.round(health * 10)} of 100">${hearts}</span>
    <span class="states">${states.map(([i, w]) => `<span class="state">${icon(i, 2)}${w}</span>`).join('')}</span>
    <span class="row food" role="img" aria-label="Fed ${Math.round(hunger * 10)} of 100">${food}</span>`
}

function drawClock(c, up) {
  if (!up || !Number.isFinite(c?.hour)) {
    clock.innerHTML = `${icon('moon', 3)}<span class="day">Out of reach</span>`
    return
  }
  const weather = c.rain >= 0.3 ? 'rain' : c.hour >= 6 && c.hour < 19.5 ? 'sun' : 'moon'
  clock.innerHTML = `${icon(weather, 3)}<span class="day">Day ${c.day || 1}</span><span class="time">${clockText(c.hour)}</span>${c.quake ? `<span class="quake">${icon('quake', 2)}Shaking</span>` : ''}`
}

function drawLive(n, up) {
  live.classList.toggle('down', !up)
  live.querySelector('.word').textContent = up ? 'Live' : 'Offline'
  live.querySelector('.n').textContent = n.toLocaleString('en')
  live.setAttribute('aria-label', up ? `Live, ${n} watching` : 'Offline')
}

// ---- keys: numbers pick a slot; in the free camera, W A S D Q E fly it ---------------------

function typing(target) {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement
}
addEventListener('keydown', (e) => {
  if (typing(e.target)) {
    if (e.key === 'Escape') toggleNote(false)
    return
  }
  const n = Number(e.key)
  if (n >= 1 && n <= slots.length && !e.ctrlKey && !e.metaKey && !e.altKey) {
    slots[n - 1].focus()
    return
  }
  if (e.key === 'Escape') {
    if (aiming) return endAim()
    return toggleNote(false)
  }
  if (camera === 'free' && FREE_KEYS.has(e.code) && !(e.target instanceof HTMLButtonElement)) {
    e.preventDefault()
    tellView({ type: 'godling-key', code: e.code, down: true })
  }
})
addEventListener('keyup', (e) => {
  if (camera === 'free' && FREE_KEYS.has(e.code)) tellView({ type: 'godling-key', code: e.code, down: false })
})
addEventListener('blur', () => tellView({ type: 'godling-key', code: 'all', down: false }))

// ---- the island's news, every POLL_MS -------------------------------------------------------

let first = true
async function poll() {
  try {
    const res = await fetch(`api/status?client=${client}`, { cache: 'no-store' })
    status = await res.json()
  } catch {
    status = { ...(status || {}), world: false }
  }
  const now = status.now || Date.now() / 1000
  showView(status.view)
  drawLive(status.watching || 0, status.world)
  drawClock(status.clock, status.world)
  drawMind(status.mind, status.clock?.hour, now)
  drawBody(status.godling)
  for (const p of status.popups || []) popup(p, !first && now - p.time < POPUP_MS / 1000 || first && now - p.time < 4)
  if (status.notes?.wait) noteReadyAt = Math.max(noteReadyAt, Date.now() + status.notes.wait * 1000)
  first = false
  setTimeout(poll, POLL_MS)
}
poll()
