// Godling's viewer screen, live: the Block HUD over the island (see .impeccable/surfaces/world-viewer-index-html.md).
// The guest panel (tools/guest_panel.py) serves it and answers /api/status, /api/power and /api/note; or the accounts
// site (web/, ADR-012) does, in front of the panel: then powers and notes need a signed-in account, and the status
// carries an `account`. The three HUD prototypes it was chosen from live in prototypes/.
import { icon } from './icons.js'
import { createReplayUI } from './replay.js'
import { browserOf, createFeedback, systemOf } from './feedback.js'

const DAY_SECONDS = 2400 // main.lua DAY_SECONDS: one island day
const POLL_MS = 1500
const POPUP_MS = 9000 // a viewer's pop-up stays this long; a note's a little longer
const POPUPS_SHOWN = 4
const FEED_SHOWN = 5 // lines of the feed (a phone shows 3)…
const WORLD_SHOWN = 2 // …of them the world's at most (a phone's 1), so notices never crowd Godling's own lines out
const NOW_STALE = 600 // seconds: a project or a think begun longer ago than this is not what Godling does now
const FRESH = 15 // seconds a new line shows while the feed is folded (two at most, a phone's one), as a game's chat line
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
let past = null // the island's past, once the screen is built (replay.js)
let bottle = null // the feedback bottle, once the screen is built (feedback.js)

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

// The island has its own origin behind the site (ADR-014): keys and camera wishes go to that origin only, never to
// whatever page the frame might have been sent to instead.
function tellView(message) {
  if (!viewSrc) return
  view.contentWindow?.postMessage({ source: 'godling-viewer', ...message }, new URL(viewSrc, location.href).origin)
}
view.addEventListener('load', () => {
  tellView({ type: 'godling-camera', mode: camera })
  past?.reloading() // the island's page says when it can hear the screen (godling-ready)
})

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

// Folded, as a game's quest tracker folds (the viewer's choice, kept): the newest thought cut to two lines, what
// Godling does now and what it needs, and for a few seconds each new line, fading as a game's chat does. Unfolded,
// the feed's last lines.
const mind = el('section', 'b-mind')
mind.setAttribute('aria-label', 'What Godling thinks and notices')
const fold = el('button', 'b-fold')
fold.type = 'button'
const feed = el('ol', 'feed b-feed')
feed.id = 'godling-feed'
fold.setAttribute('aria-controls', feed.id)
const doing = el('p', 'b-now') // what Godling is doing this moment, or that it stands thinking
const objective = el('p', 'b-objective')
mind.append(fold, feed, doing, objective)
stage.append(mind)
let folded = store.get('godling.mind') !== 'open'
let mindShown = null // what drawMind last drew from, to draw it again folded or not
fold.addEventListener('click', () => {
  folded = !folded
  store.set('godling.mind', folded ? 'folded' : 'open')
  if (mindShown) drawMind(...mindShown)
})
let feedDrawn = '' // the feed as last drawn: drawn again only when it changes, so a line's button keeps its focus
let opened = '' // the one line opened in full, by its time and words
// Each line's island time, worked out when it is first drawn: the world's clock and the panel's are read moments apart,
// so working it out again on every poll would make it jump a minute back and forth.
const stamps = new Map()

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
  s = s.replace(/\s*\b(at|to|from|near) \(-?\d+(\.\d+)?, ?-?\d+(\.\d+)?\)/g, '')
    .replace(/\s*\(-?\d+(\.\d+)?, ?-?\d+(\.\d+)?\)/g, '')
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

// Godling's lines that are not thoughts: what came of a project, a skill it taught itself, a dream. Its own words
// (an intention, what a skill does) follow, with the world's names and coordinates made plain as in its thoughts.
const lower = (s) => (/^[A-Z][a-z]/.test(s) ? s.charAt(0).toLowerCase() + s.slice(1) : s)
const ABOUT = {
  failed: ['close', (f) => `Couldn’t finish: ${lower(f.words)}`],
  stopped: ['pause', (f) => `Stopped to think again: ${lower(f.words)}`],
  learned: ['idea', (f) => `Learned “${String(f.name).replace(/_/g, ' ')}”${f.words ? `: ${f.words.replace(/\$(\w+)/g, 'the $1')}` : ''}`],
  dream: ['moon', (f) => `Dreamt: ${f.words}`],
}
// A line longer than this many characters may be cut by its clamp (two lines of about 50 characters; unfolded, the
// newest thought three), so it carries a chevron and opens in full on a click or a tap.
const OPENS_FROM = { line: 70, latest: 110 }

// `fresh`: the lines shown folded only because they are new, each with its age in seconds: they fade out by FRESH.
function drawFeed(lines, times, phone, fresh = new Map()) {
  const key = JSON.stringify([lines.map((f, i) => [times[i], f.who, f.about, f.name, f.words, fresh.has(f)]), opened,
    phone, folded])
  if (key === feedDrawn) return
  feedDrawn = key
  const focused = feed.contains(document.activeElement) ? document.activeElement.dataset.key : null
  const latest = lines.findLast((f) => f.who === 'godling' && !f.about) // the newest thought, shown at more length
  feed.replaceChildren(...lines.map((f, i) => {
    const li = el('li', `line ${f.who}${f.about ? ` ${f.about}` : ''}${f === latest ? ' latest' : ''}`)
    li.style.setProperty('--age', lines.length - 1 - i)
    if (fresh.has(f)) {
      li.classList.add('fresh')
      li.style.animationDelay = `${-fresh.get(f)}s` // drawn again, it fades on from where it was
    }
    li.append(text('time', '', times[i]))
    const [pic, say] = ABOUT[f.about] || []
    li.insertAdjacentHTML('beforeend', pic ? icon(pic, 2) : speaker[f.who]?.() || speaker.notice())
    if (f.who !== 'godling') {
      const words = clip(f.words, 150)
      const span = text('span', 'text', words)
      if (words !== f.words) span.title = f.words
      li.append(span)
      return li
    }
    const words = say ? say(f) : `“${f.words}”` // whole: the clamp cuts what does not fit, at a word
    const most = f !== latest || folded ? OPENS_FROM.line : OPENS_FROM.latest
    if (words.length <= most) {
      li.append(text('span', 'text', words))
      return li
    }
    const id = `${f.time}|${f.words.slice(0, 80)}`
    const open = el('button', 'open')
    open.type = 'button'
    open.dataset.key = id
    open.setAttribute('aria-expanded', String(opened === id))
    open.append(text('span', 'text', words))
    open.insertAdjacentHTML('beforeend', icon(opened === id ? 'less' : 'more', 2))
    open.addEventListener('click', () => {
      opened = opened === id ? '' : id
      drawFeed(lines, times, phone, fresh)
    })
    li.classList.toggle('opened', opened === id)
    li.append(open)
    return li
  }))
  if (!lines.length) feed.append(el('li', 'line notice waiting', `<time></time>${icon('godling', 2)}<span class="text">Godling is waking up…</span>`))
  if (focused) [...feed.querySelectorAll('.open')].find((b) => b.dataset.key === focused)?.focus()
}

// What the bubble's picture stands for (mind/godling/bubble.py THINGS): what Godling has in mind while it thinks.
const THINKING_ABOUT = {
  coconut: 'coconuts', fish: 'fish', cooked_fish: 'a meal', fire: 'fire', log: 'logs', block: 'stone blocks',
  boulder: 'the boulders', axe: 'the axe', hammer: 'the hammer', spear: 'a spear', palm: 'the palms',
  ladder: 'the ladder', raft: 'the raft', ball: 'its volleyball', help: 'a HELP sign', rescue: 'being rescued',
  sea: 'the sea', lightning: 'the sky', tower: 'a tower', wall: 'a wall', shelter: 'a shelter',
  explore: 'exploring', night: 'the night', rain: 'the rain',
}

// Now: the project under way, in Godling's words, and how far it is into its agenda; or, while its body stands
// until its mind has thought, what is on its mind (the bubble) and how it feels.
function drawNow(now, bubble, at) {
  const fresh = now && !(Number.isFinite(now.time) && Number.isFinite(at) && at - now.time > NOW_STALE)
  const about = THINKING_ABOUT[bubble?.thing]
  const what = !fresh ? '' : now.thinking ? `Thinking${about ? ` about ${about}` : ''}…` : plain(now.text || '', 'godling')
  doing.hidden = !what
  doing.classList.toggle('thinking', Boolean(what && now.thinking))
  if (!what) return
  doing.innerHTML = `${icon(now.thinking ? 'think' : 'play', 2)}<b>Now</b>`
  const words = text('span', 'what', what)
  words.title = what
  doing.append(words)
  const aside = now.thinking ? bubble?.feeling : now.of > 1 && now.step <= now.of ? `${now.step} of ${now.of}` : ''
  if (aside) doing.append(text('span', 'aside', aside))
}

function drawMind(m, hour, now) {
  mindShown = [m, hour, now]
  const phone = PHONE()
  const all = (m?.feed || []).map((f) => ({ ...f, words: plain(f.text, f.who) }))
    .filter((f) => f.words || f.about === 'learned' && f.name)
  const full = [] // the lines shown unfolded
  const most = phone ? 3 : FEED_SHOWN
  let world = 0
  for (let i = all.length - 1; i >= 0 && full.length < most; i--) {
    if (all[i].who !== 'godling' && world++ >= (phone ? 1 : WORLD_SHOWN)) continue
    full.unshift(all[i])
  }
  const latest = all.findLast((f) => f.who === 'godling' && !f.about)
  if (latest && !full.includes(latest)) { // the newest thought always shows, however much came of the plan since
    if (full.length >= most) full.shift()
    full.unshift(latest)
  }
  const ids = full.map((f) => `${f.time}|${f.who}|${f.text}`)
  const times = full.map((f, i) => {
    if (!stamps.has(ids[i]) && Number.isFinite(hour) && f.time) stamps.set(ids[i], clockText(hour - ((now - f.time) * 24) / DAY_SECONDS))
    return stamps.get(ids[i]) || ''
  })
  for (const id of stamps.keys()) if (!ids.includes(id)) stamps.delete(id)
  const fresh = new Map()
  if (folded) {
    for (const f of full.filter((l) => l !== latest && now - l.time < FRESH).slice(phone ? -1 : -2)) fresh.set(f, now - f.time)
  }
  const shown = folded ? full.filter((f) => f === latest || fresh.has(f)) : full
  drawFeed(shown, shown.map((f) => times[full.indexOf(f)]), phone, fresh)
  mind.classList.toggle('folded', folded)
  const more = full.length - shown.length
  fold.hidden = folded && !more
  const label = folded ? `${more} more` : 'Less'
  if (fold.dataset.label !== label) {
    fold.dataset.label = label
    fold.innerHTML = `${icon(folded ? 'more' : 'less', 2)}<span>${label}</span>`
    fold.setAttribute('aria-expanded', String(!folded))
    fold.setAttribute('aria-label', folded ? `Show ${more} more of what Godling thought and noticed` : 'Show less of it')
  }
  drawNow(m?.now, m?.bubble, now)
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
  if (entry.kind === 'note') {
    body.append(text('q', 'paper', entry.text))
    if (account?.signedIn && entry.noteId && entry.name !== account.username) body.append(reportButton(entry.noteId))
  }
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

// Behind the accounts site, a note seen can be reported (the user's choice: report after delivery). Enough reports
// hide it from every screen and pause its sender's notes until a moderator looks.
function reportButton(noteId) {
  const b = text('button', 'report quiet', 'Report')
  b.type = 'button'
  b.title = 'Report this note to the moderators'
  b.addEventListener('click', async () => {
    b.disabled = true
    const answer = await post('api/report', { note: noteId, reason: 'unkind' })
    b.textContent = answer.ok ? 'Reported' : 'Not reported'
    tell(answer.text, answer.ok ? '' : 'no')
  })
  return b
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
// Behind the accounts site: who is signed in, or the way in. Hidden when the panel serves the screen on its own.
const accountChip = el('div', 'b-account stone')
accountChip.hidden = true
belt.append(bar, purse, accountChip)
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
  // Words only, never markup: behind the site a power's name, words and rule are what the admin typed (its Power
  // rows), and this page shares the admin's origin.
  const head = el('div', 'tip-head', icon(p.icon, 2))
  head.append(text('strong', '', p.name), text('em', p.harm ? 'harm' : '', p.kind))
  const facts = el('dl')
  const fact = (term, words, after = null) => {
    const dd = text('dd', '', words)
    if (after) dd.append(after)
    facts.append(text('dt', '', term), dd)
  }
  // Free only in test mode: the panel on its own (no accounts), or the site's rules saying so (drawPurse).
  if (p.note) fact('Price', `Free · ${status?.notes?.limit || 140} characters`)
  else fact('Price', `${p.price} credits · ${EURO(p.price)}`, !account || account.free ? text('span', 'free', 'free while testing') : null)
  if (p.rule) fact('Rule', p.rule)
  if (cooling[p.id] > Date.now()) fact('Ready', `in ${minutesText((cooling[p.id] - Date.now()) / 1000)}`)
  tip.append(head, text('p', '', p.does), facts)
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

const csrf = () => document.cookie.split('; ').find((c) => c.startsWith('csrftoken='))?.slice(10) || ''

async function post(path, body) {
  try {
    const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify({ client, name: noteName.value.trim() || store.get('godling.name') || '', ...body }) })
    const answer = await res.json()
    if (answer.signIn) nudgeSignIn()
    return answer
  } catch {
    return { ok: false, text: 'The island is out of reach. Try again in a moment.' }
  }
}

// Watching the past (ADR-016 D6): nothing can be changed there; the powers wait for live.
function inThePast() {
  if (!past?.on) return false
  tell('You are watching the past. Go live to call powers and send notes.')
  return true
}

// Behind the site a power is queued for the island and the answer is `pending` (its call's id): ask how it went, every
// half second at first and then every two, until the world has answered. The panel on its own answers at once.
const PENDING_DEADLINE_MS = 4.5 * 60 * 1000 // the site gives a call up after 3 minutes (4 once sent), so this ends
async function settled(answer) {
  const deadline = Date.now() + PENDING_DEADLINE_MS
  for (let tries = 0; answer.pending && Date.now() < deadline; tries++) {
    await new Promise((done) => setTimeout(done, tries < 20 ? 500 : 2000))
    try {
      const res = await fetch(`api/power/${encodeURIComponent(answer.pending)}`, { cache: 'no-store' })
      if (res.status === 401) {
        nudgeSignIn()
        return { ok: false, text: 'You were signed out; sign in again to see how your power went.' }
      }
      if (res.status === 404) return { ok: false, text: 'That power is no longer on its way.' }
      if (res.ok) answer = await res.json()
    } catch { /* a blip: ask again */ }
  }
  return answer.pending ? { ok: false, text: 'The island is slow to answer; your power is still on its way.' } : answer
}

async function call(p, s, at = null) {
  if (inThePast() || s.classList.contains('calling')) return
  if (cooling[p.id] > Date.now()) return tell(`${p.name} is not ready yet: ${minutesText((cooling[p.id] - Date.now()) / 1000)} to go.`)
  s.classList.add('calling')
  const answer = await settled(await post('api/power', { power: p.id, ...(at ? { at } : {}) }))
  s.classList.remove('calling')
  if (account && Number.isFinite(answer.credits)) drawPurse({ ...account, credits: answer.credits })
  if (answer.ok) popup(answer)
  else tell(answer.text || `${p.name} did not work.`, 'no')
  if (answer.needCredits) nudge(purse)
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
  if (inThePast()) return
  if (cooling[p.id] > Date.now()) return tell(`${p.name} is not ready yet: ${minutesText((cooling[p.id] - Date.now()) / 1000)} to go.`)
  toggleNote(false)
  bottle?.close({ focus: false })
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
  else if (data.type === 'godling-ready') { // the island's page can hear the screen now: its camera, and the past
    tellView({ type: 'godling-camera', mode: camera })
    past?.heard(data)
  } else if (String(data.type).startsWith('godling-replay')) past?.heard(data)
  else if (data.type === 'godling-stream') {
    islandStream = { state: String(data.state), world: data.world === 'down' ? 'down' : 'up' }
    drawLive(status?.watching || 0, status?.world)
  }
})

function toggleNote(open = composer.hidden) {
  if (open && inThePast()) return
  if (open && aiming) endAim()
  if (open) bottle?.close({ focus: false })
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

// The island frame's own stream (patches/v3, through the renderer) decides the badge, so it never says Live over a
// frozen island; until the frame has said anything, the panel's word stands.
let islandStream = null
const STREAM_WORDS = { connecting: 'Connecting', reconnecting: 'Reconnecting', paused: 'Paused' }

// The badge's word: the island's stream as the frame said it, or the panel's word until it has. A bug report takes the
// same word (screenFacts), so it never says live where the screen said otherwise.
function liveWord(panelUp) {
  const s = islandStream
  return !s ? (panelUp ? 'Live' : 'Offline')
    : s.state === 'live' ? (s.world === 'down' ? 'Restarting' : 'Live')
    : STREAM_WORDS[s.state] || 'Offline'
}

function drawLive(n, panelUp) {
  const word = liveWord(panelUp)
  const up = word === 'Live'
  const replaying = Boolean(past?.on)
  live.classList.toggle('down', !up && !replaying)
  live.classList.toggle('past', replaying)
  live.querySelector('.word').textContent = replaying ? 'Replay' : word
  live.querySelector('.n').textContent = n.toLocaleString('en')
  live.setAttribute('aria-label', replaying ? `Replay of the island's past; ${n} watching it live`
    : up ? `Live, ${n} watching` : word)
}

// ---- keys: numbers pick a slot; in the free camera, W A S D Q E fly it ---------------------

function typing(target) {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement
}
addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && bottle?.open) return bottle.close() // the topmost thing open closes first
  if (typing(e.target) || e.target.closest?.('.b-bottle')) { // the bottle is a dialog: its keys stay its own
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
  // Space on a focused button presses it, as it should. Every other flying key flies, even with a button focused: the
  // Free camera button keeps the focus after the click that chose it.
  if (camera === 'free' && FREE_KEYS.has(e.code) && !(e.code === 'Space' && e.target instanceof HTMLButtonElement)) {
    e.preventDefault()
    tellView({ type: 'godling-key', code: e.code, down: true })
  }
})
addEventListener('keyup', (e) => {
  if (camera === 'free' && FREE_KEYS.has(e.code)) tellView({ type: 'godling-key', code: e.code, down: false })
})
addEventListener('blur', () => tellView({ type: 'godling-key', code: 'all', down: false }))

// ---- the island's news, every POLL_MS -------------------------------------------------------

// ---- the viewer's account (behind the accounts site) ---------------------------------------

let account = null
function drawAccount(a) {
  account = a?.enabled ? a : null
  const shown = account ? `${account.signedIn}:${account.username || ''}` : '' // redrawn only when that changes
  if (shown === accountChip.dataset.shown) return
  accountChip.dataset.shown = shown
  accountChip.hidden = !account
  noteName.hidden = Boolean(account) // the account's name goes with its notes
  if (!account) return
  accountChip.replaceChildren()
  if (account.signedIn) {
    accountChip.insertAdjacentHTML('afterbegin', icon('godling', 2))
    accountChip.append(text('span', 'who', account.username))
    const out = el('form', 'out')
    out.method = 'post'
    out.action = account.signOut
    const token = el('input')
    Object.assign(token, { type: 'hidden', name: 'csrfmiddlewaretoken', value: csrf() })
    const button = text('button', 'quiet', 'Sign out')
    button.type = 'submit'
    out.append(token, button)
    accountChip.append(out)
    noteHint.textContent = `Signed in as ${account.username}. Godling reads every note and decides for itself what to do.`
  } else {
    const next = encodeURIComponent('/')
    const signIn = text('a', 'get', 'Sign in')
    signIn.href = `${account.signIn}?next=${next}`
    const signUp = text('a', 'quiet', 'Create an account')
    signUp.href = `${account.signUp}?next=${next}`
    accountChip.append(signIn, signUp)
    noteHint.textContent = 'Sign in to send Godling a note. It reads every one and decides for itself what to do.'
  }
}

function nudge(block) {
  block.classList.remove('nudge')
  void block.offsetWidth // restart the nudge
  block.classList.add('nudge')
}
const nudgeSignIn = () => nudge(accountChip)

// The purse: test mode, the way to sign in for credits, or the account's credits and the way to buy more.
function drawPurse(a) {
  const key = !a ? 'panel' : a.free ? 'free' : a.signedIn ? `cr:${a.credits}` : 'out'
  if (key === purse.dataset.shown) return
  purse.dataset.shown = key
  purse.replaceChildren()
  purse.insertAdjacentHTML('afterbegin', icon('coin', 3))
  const words = el('span')
  if (!a || a.free) {
    words.innerHTML = '<b>Free</b>test mode<small>prices shown for later</small>'
  } else if (!a.signedIn) {
    words.innerHTML = '<b>Credits</b><small>sign in to call powers</small>'
  } else {
    words.append(text('b', '', a.credits.toLocaleString('en')), document.createTextNode('credits'),
      text('small', '', `≈ ${EURO(a.credits)}`))
  }
  purse.append(words)
  if (a?.signedIn && !a.free) {
    const get = text('a', 'get', 'Get credits')
    get.href = a.creditsPage
    purse.append(get)
  }
  drawPrices()
}

// Prices come from the site (the admin sets them); a slot the purse cannot pay for shows its price dimmed.
function drawPrices() {
  POWERS.forEach((p, i) => {
    if (p.note) return
    const price = slots[i].querySelector('.price')
    price.textContent = `${p.price} cr`
    price.classList.toggle('short', Boolean(account?.signedIn && !account.free && (account.credits ?? 0) < p.price))
  })
}

// Behind the accounts site, each power's price and words come from its row in the admin (apps.credits Power); a power
// switched off there leaves the hotbar. On its own, the panel's screen keeps the words written above.
let powersShown = ''
function takePowers(powers) {
  if (!powers) return
  const shown = JSON.stringify(powers)
  if (shown === powersShown) return
  powersShown = shown
  POWERS.forEach((p, i) => {
    if (p.note) return
    const row = powers[p.id]
    slots[i].hidden = !row
    if (!row) return
    Object.assign(p, { name: String(row.label), price: Number(row.price) || 0, kind: String(row.kind),
      harm: Boolean(row.harms), does: String(row.does || ''), rule: row.rule ? String(row.rule) : undefined,
      did: row.did || p.did, after: row.after || p.after })
    slots[i].classList.toggle('harm', Boolean(row.harms))
    slots[i].setAttribute('aria-label', `${p.name}, ${p.price} credits`)
  })
  drawPrices()
}

function takeNoteLimit(notes) {
  const limit = notes?.limit
  if (!Number.isFinite(limit) || noteText.maxLength === limit) return
  noteText.maxLength = limit
  noteCount.textContent = `${[...noteText.value].length}/${limit}`
}

// ---- the island's past (ADR-016): a timeline, speeds and markers; the island's page plays it -----------------------

past = createReplayUI({
  stage, dock, rewindIn: statusBar, el, text, icon, tellView, tell,
  show(s) {
    if (s.act) return popup(s.act)
    drawClock(s.clock, true)
    drawBody(s.godling)
    drawMind(s.mind, s.clock?.hour, s.now)
  },
  onChange(on) {
    if (on) {
      endAim()
      toggleNote(false)
    }
    drawLive(status?.watching || 0, status?.world)
    if (!on && status) {
      drawClock(status.clock, status.world)
      drawMind(status.mind, status.clock?.hour, status.now || Date.now() / 1000)
      drawBody(status.godling)
    }
  },
})
// ---- the bottle (behind the accounts site): a bug, a question or an idea for the makers -------------------------

// What the screen shows, for a bug report the viewer chooses to attach it to (web/apps/feedback/views.py FACTS): the
// badge's word, and the clock as drawClock shows it (whole minutes; none while it says "Out of reach").
function screenFacts() {
  const facts = {
    view: past?.on ? 'replay' : 'live',
    camera,
    stream: liveWord(status?.world).toLowerCase(),
    size: `${innerWidth}x${innerHeight}`,
    pixels: Math.round((devicePixelRatio || 1) * 100) / 100,
  }
  const browser = browserOf(navigator.userAgent), system = systemOf(navigator.userAgent)
  if (browser) facts.browser = browser
  if (system) facts.system = system
  if (matchMedia('(pointer: coarse)').matches) facts.touch = true
  if (past?.on) {
    if (past.at > 0) facts.moment = Math.round(past.at)
  } else if (status?.world && Number.isFinite(status.clock?.hour)) {
    facts.day = status.clock.day || 1
    facts.minute = Math.floor((((status.clock.hour % 24) + 24) % 24) * 60) // as clockText reads it
  }
  return facts
}
bottle = createFeedback({ stage, dock, el, icon, post, store, facts: screenFacts, phone: PHONE,
  onOpen() { // the bottle takes the place of the aim and the note, as they take each other's
    if (aiming) endAim()
    toggleNote(false)
  } })

// A shared link to a moment (?t=…): into the past once the island's page has come up live.
const sharedMoment = Date.parse(new URLSearchParams(location.search).get('t') || '')
if (Number.isFinite(sharedMoment)) past.start(sharedMoment) // opens once the island's page can hear the screen

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
  drawAccount(status.account)
  bottle.draw(account)
  takePowers(status.powers)
  takeNoteLimit(status.notes)
  if (status.account) drawPurse(account)
  drawLive(status.watching || 0, status.world)
  if (!past.on) { // in the past, the replay fills these (replay.js)
    drawClock(status.clock, status.world)
    drawMind(status.mind, status.clock?.hour, now)
    drawBody(status.godling)
  }
  for (const p of status.popups || []) popup(p, !past.on && (!first && now - p.time < POPUP_MS / 1000 || first && now - p.time < 4))
  if (status.notes?.wait) noteReadyAt = Math.max(noteReadyAt, Date.now() + status.notes.wait * 1000)
  first = false
  setTimeout(poll, POLL_MS)
}
poll()
