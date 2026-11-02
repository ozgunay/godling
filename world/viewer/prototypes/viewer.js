// Godling's viewer screen, the prototypes: three HUDs over a still of the island, picked with ?hud=block|kit|sky.
// ?demo=day|night|meteor picks the demo moment. All names, numbers and lines below are demo data, not a real run.
import { icon } from '../icons.js'

const params = new URLSearchParams(location.search)
const HUD = ['block', 'kit', 'sky'].includes(params.get('hud')) ? params.get('hud') : 'block'
const PHONE = () => matchMedia('(max-width: 760px)').matches
const EURO = (credits) => `€${(credits * 0.05).toFixed(2)}`

const POWERS = [
  { id: 'stone', name: 'Stone', icon: 'stone', price: 4, charges: 4, max: 4, kind: 'Gift', does: 'A stone block thuds down near Godling.' },
  { id: 'log', name: 'Driftwood', icon: 'log', price: 4, charges: 2, max: 4, refill: '1:12', kind: 'Gift', does: 'A log rides a wave onto the beach nearest Godling.' },
  { id: 'coconut', name: 'Ripe coconut', icon: 'coconut', price: 6, charges: 1, max: 2, kind: 'Gift', does: 'The nearest palm drops a ripe coconut: food for Godling.' },
  { id: 'regrow', name: 'Regrow a palm', icon: 'sapling', price: 6, charges: 3, max: 3, kind: 'Gift', does: 'A stump near Godling grows back at once.' },
  { id: 'fish', name: 'School of fish', icon: 'fish', price: 10, charges: 0, max: 1, cooldown: '6:12', cdFrac: 0.42, kind: 'Gift', does: 'Fish gather in the shallows by Godling for two minutes.' },
  { id: 'lightning', name: 'Lightning', icon: 'lightning', price: 40, charges: 1, max: 1, kind: 'Wonder', harm: true, does: 'A bolt fells the nearest palm into two logs. Hurts Godling within 7.' },
  { id: 'meteor', name: 'Meteor', icon: 'meteor', price: 40, charges: 1, max: 1, kind: 'Wonder', harm: true, does: 'A shadow spreads near Godling; 40 s later a dark stone lands in it. Hurts within 6.', rule: 'Refills every 15 min' },
  { id: 'rain', name: 'Rain shower', icon: 'rain', price: 27, charges: 1, max: 1, kind: 'Weather', does: 'Five minutes of rain: coconuts ripen faster, fires go out.' },
  { id: 'quake', name: 'Earthquake', icon: 'quake', price: 500, pooled: true, pot: 312, kind: 'Disaster', harm: true, does: 'The ground rumbles, then shakes for 20 s. Loose pieces fall, fastened ones hold. Godling braces.', rule: 'Community pot, once a day' },
]

const MOMENTS = {
  day: {
    bg: '../demo/day.jpg', bgPhone: '../demo/phone.jpg', head: [49.7, 54], headPhone: [48.6, 55],
    day: 3, time: '14:20', hour: 14.33, weather: 'sun', health: 7.5, hunger: 6, wet: 0, cold: false,
    intention: 'Carry the new log to the gate and lay it across the posts.',
    feed: [
      { t: '14:12', who: 'godling', text: 'The tremor cut the last haul short.' },
      { t: '14:13', who: 'notice', text: 'A log washed up on the beach.' },
      { t: '14:16', who: 'sky', text: 'mara_k dropped a log near Godling', cost: 4 },
      { t: '14:17', who: 'notice', text: 'Godling turned to look at the log.' },
      { t: '14:19', who: 'godling', text: 'Two logs now. One more and the gate gets its lintel.' },
    ],
    needs: { text: 'logs for the gate lintel', have: 2, of: 3, icon: 'log' },
    toast: { icon: 'stone', title: 'First wall', text: 'Godling fastened a wall three blocks long', when: 'Day 3' },
    thought: 'log', credits: 340, selected: 'meteor', viewers: 1284,
  },
  night: {
    bg: '../demo/night.jpg', bgPhone: '../demo/phone-night.jpg', head: [49.7, 54], headPhone: [48.6, 55],
    day: 3, time: '22:40', hour: 22.66, weather: 'moon', health: 5, hunger: 3.5, wet: 0, cold: true,
    intention: 'Sit by the gate until it is light again.',
    feed: [
      { t: '22:31', who: 'notice', text: 'You have grown cold: the night is chilly out here.' },
      { t: '22:33', who: 'godling', text: 'No fire yet. Twelve rubs and only smoke.' },
      { t: '22:36', who: 'sky', text: 'tomv dropped a ripe coconut', cost: 6 },
      { t: '22:37', who: 'notice', text: 'A coconut fell from the palm by the gate.' },
      { t: '22:39', who: 'godling', text: 'Ate it. Warmer inside, still cold out.' },
    ],
    needs: { text: 'a dry log and a coconut husk for fire', have: 1, of: 2, icon: 'coconut' },
    toast: { icon: 'coconut', title: 'Fed by the sky', text: 'Hunger 35 → 50', when: 'Day 3, night' },
    thought: 'coconut', credits: 82, selected: 'coconut', viewers: 911,
  },
  meteor: {
    bg: '../demo/meteor.jpg', bgPhone: '../demo/phone.jpg', head: [49.7, 54], headPhone: [48.6, 55],
    day: 4, time: '09:05', hour: 9.08, weather: 'sun', health: 9, hunger: 8, wet: 0, cold: false,
    intention: 'Stand clear of the shadow and watch where it lands.',
    feed: [
      { t: '09:02', who: 'godling', text: 'Morning. The wall held through the night.' },
      { t: '09:04', who: 'sky', text: 'ozzy called a meteor', cost: 40 },
      { t: '09:04', who: 'notice', text: 'A dark shadow spreads on the ground: something is falling, in about 40 s.' },
      { t: '09:04', who: 'godling', text: 'A shadow by the towers. Not standing under that.' },
      { t: '09:05', who: 'notice', text: 'Godling glanced at the shadow.' },
    ],
    needs: { text: 'stones for a second wall', have: 1, of: 4, icon: 'stone' },
    toast: { icon: 'meteor', title: 'Meteor incoming', text: 'Lands in 31 s, by the towers', when: 'Day 4' },
    thought: 'meteor', credits: 296, selected: 'meteor', cooling: 'meteor', viewers: 2410,
  },
}

const M = MOMENTS[params.get('demo')] || MOMENTS.day
const stage = document.getElementById('stage')
stage.classList.add(`hud-${HUD}`)
let camera = params.get('camera') === 'free' ? 'free' : 'follow'
let selected = M.selected

function el(tag, cls, html) {
  const e = document.createElement(tag)
  if (cls) e.className = cls
  if (html !== undefined) e.innerHTML = html
  return e
}

function power(id) {
  const p = { ...POWERS.find((x) => x.id === id) }
  if (M.cooling === id) Object.assign(p, { charges: 0, cooldown: '14:31', cdFrac: 0.97 })
  return p
}

function speaker(who) {
  return { godling: icon('godling', 2), sky: icon('sky', 2), notice: icon('notice', 2) }[who]
}

// ---- shared pieces --------------------------------------------------------------------

function island() {
  const bg = el('div', 'island')
  bg.setAttribute('role', 'img')
  bg.setAttribute('aria-label', "Godling's island, live")
  bg.style.backgroundImage = `url(${PHONE() ? M.bgPhone : M.bg})`
  const live = el('span', 'live', 'Live')
  stage.append(bg, live)
}

function bubble(cls) {
  const [x, y] = PHONE() ? M.headPhone : M.head
  const b = el('div', `bubble ${cls}`, `<span class="cloud">${icon(M.thought, 3)}</span><i></i><i></i><i></i>`)
  b.style.left = `${x}%`
  b.style.top = `${y}%`
  b.setAttribute('aria-hidden', 'true')
  stage.append(b)
}

function cameraSwitch(cls) {
  const group = el('div', `camera ${cls}`)
  group.setAttribute('role', 'group')
  group.setAttribute('aria-label', 'Camera')
  const follow = el('button', 'cam', `${icon('eye', 2)}<span>Follow Godling</span>`)
  const free = el('button', 'cam', `${icon('move', 2)}<span>Free camera</span><span class="keys"><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd></span>`)
  for (const [b, mode] of [[follow, 'follow'], [free, 'free']]) {
    b.type = 'button'
    b.setAttribute('aria-pressed', String(camera === mode))
    b.addEventListener('click', () => {
      camera = mode
      follow.setAttribute('aria-pressed', String(camera === 'follow'))
      free.setAttribute('aria-pressed', String(camera === 'free'))
    })
  }
  group.append(follow, free)
  return group
}

function feedList(cls, count) {
  const list = el('ol', `feed ${cls}`)
  list.setAttribute('aria-label', 'What Godling thinks and notices')
  const lines = M.feed.slice(-count)
  lines.forEach((f, i) => {
    const age = lines.length - 1 - i
    const li = el('li', `line ${f.who}`, `<time>${f.t}</time>${speaker(f.who)}<span class="text">${f.who === 'godling' ? `“${f.text}”` : f.text}${f.cost ? `<b class="cost">${f.cost} cr</b>` : ''}</span>`)
    li.style.setProperty('--age', age)
    list.append(li)
  })
  return list
}

function tipFor(p, cls) {
  const t = el('div', `tip ${cls}`)
  t.setAttribute('role', 'tooltip')
  t.innerHTML = `<div class="tip-head">${icon(p.icon, 2)}<strong>${p.name}</strong><em class="${p.harm ? 'harm' : ''}">${p.kind}</em></div>
    <p>${p.does}</p>
    <dl><dt>Price</dt><dd>${p.price} credits · ${EURO(p.price)}</dd>
    <dt>${p.pooled ? 'Pot' : 'Charges'}</dt><dd>${p.pooled ? `${p.pot} of ${p.price} filled` : `${p.charges} of ${p.max}${p.cooldown ? `, next in ${p.cooldown}` : ''}`}</dd>
    ${p.rule ? `<dt>Rule</dt><dd>${p.rule}</dd>` : ''}</dl>`
  return t
}

function onKeys(slots) {
  addEventListener('keydown', (e) => {
    const n = Number(e.key)
    if (n >= 1 && n <= slots.length) slots[n - 1].focus()
  })
}

// ---- 1. Block HUD -------------------------------------------------------------------------

function blockHud() {
  island()
  bubble('bubble-block')
  const phone = PHONE()

  const mind = el('section', 'b-mind')
  mind.append(feedList('b-feed', phone ? 3 : 5))
  mind.append(el('p', 'b-objective', `${icon(M.needs.icon, 2)}<span><b>Needs</b> ${M.needs.of} ${M.needs.text}</span><span class="pips">${'<i class="on"></i>'.repeat(M.needs.have)}${'<i></i>'.repeat(M.needs.of - M.needs.have)}</span><span class="count">${M.needs.have}/${M.needs.of}</span>`))
  stage.append(mind)

  const status = el('header', 'b-status')
  status.append(el('div', 'b-clock stone', `${icon(M.weather, 3)}<span class="day">Day ${M.day}</span><span class="time">${M.time}</span>`))
  status.append(cameraSwitch('b-camera'))
  stage.append(status)

  if (M.toast) {
    stage.append(el('div', 'b-toast stone', `<span class="t-icon block">${icon(M.toast.icon, 3)}</span><span><strong>${M.toast.title}</strong><small>${M.toast.text} · ${M.toast.when}</small></span>`))
  }

  const dock = el('footer', 'b-dock')
  const hearts = Array.from({ length: 10 }, (_, i) => icon(M.health >= i + 1 ? 'heart' : M.health > i ? 'heartHalf' : 'heartEmpty', phone ? 2 : 3)).join('')
  const food = Array.from({ length: 10 }, (_, i) => icon(M.hunger >= 10 - i ? 'food' : M.hunger > 9 - i ? 'foodHalf' : 'foodEmpty', phone ? 2 : 3)).join('')
  dock.append(el('div', 'b-vitals', `<span class="row hearts" aria-label="Health ${M.health * 10} of 100">${hearts}</span>${M.cold ? `<span class="state">${icon('cold', 2)}Cold</span>` : ''}<span class="row food" aria-label="Hunger ${M.hunger * 10} of 100">${food}</span>`))
  const bar = el('div', 'b-hotbar')
  bar.setAttribute('role', 'toolbar')
  bar.setAttribute('aria-label', 'Sky powers')
  const slots = POWERS.map((x, i) => {
    const p = power(x.id)
    const s = el('button', `slot block${p.charges === 0 && !p.pooled ? ' cooling' : ''}${p.harm ? ' harm' : ''}${p.id === selected ? ' picked' : ''}`)
    s.type = 'button'
    s.style.setProperty('--cd', p.cdFrac || 0)
    s.setAttribute('aria-label', `${p.name}, ${p.price} credits`)
    s.innerHTML = `<kbd>${i + 1}</kbd>${icon(p.icon, phone ? 2 : 3)}
      ${p.pooled ? `<span class="pot"><i style="width:${(p.pot / p.price) * 100}%"></i></span>` : `<span class="n">${p.charges === 0 ? p.cooldown : p.charges}</span>`}
      <span class="price">${icon('coin', 1)}${p.price}</span>`
    s.addEventListener('mouseenter', () => pick(p.id))
    s.addEventListener('focus', () => pick(p.id))
    bar.append(s)
    return s
  })
  const purse = el('div', 'b-purse stone', `${icon('coin', 3)}<span><b>${M.credits}</b> credits<small>≈ ${EURO(M.credits)}</small></span><button type="button" class="get">Get credits</button>`)
  dock.append(el('div', 'b-belt'))
  dock.lastChild.append(bar, purse)
  stage.append(dock)
  stage.append(el('p', 'watching', `${M.viewers.toLocaleString('en')} watching<span class="proto">Prototype · demo data</span>`))

  let tip = null
  function pick(id) {
    selected = id
    slots.forEach((s, i) => s.classList.toggle('picked', POWERS[i].id === id))
    tip?.remove()
    const p = power(id)
    if (phone) {
      tip = el('p', 'b-pickline', `${icon(p.icon, 2)}<b>${p.name}</b> ${p.price} cr · ${EURO(p.price)}<span>${p.charges === 0 && !p.pooled ? `ready in ${p.cooldown}` : 'Tap again to call'}</span>`)
      dock.prepend(tip)
    } else {
      tip = tipFor(p, 'b-tip stone')
      const s = slots[POWERS.findIndex((x) => x.id === id)]
      stage.append(tip)
      const r = s.getBoundingClientRect(), sr = stage.getBoundingClientRect()
      tip.style.left = `${Math.max(16, Math.min(sr.width - tip.offsetWidth - 16, r.left - sr.left + r.width / 2 - tip.offsetWidth / 2))}px`
      tip.style.top = `${r.top - sr.top - tip.offsetHeight - 14}px`
    }
  }
  pick(selected)
  onKeys(slots)
}

// ---- 2. Castaway Kit ----------------------------------------------------------------------

function kitHud() {
  island()
  bubble('bubble-kit')
  const phone = PHONE()

  const book = el('section', 'k-book')
  book.setAttribute('aria-label', "Godling's notebook")
  const lines = M.feed.filter((f) => f.who !== 'sky').slice(phone ? -2 : -4)
  book.innerHTML = `<header><span>Day ${M.day}</span><span>${M.time}</span>${icon(M.weather, 2)}</header>
    <p class="now">${M.intention}</p>
    <ul>${lines.map((f) => `<li class="${f.who}"><time>${f.t}</time>${f.who === 'godling' ? f.text : `<em>${f.text}</em>`}</li>`).join('')}</ul>
    <p class="check"><span class="box"></span>${M.needs.of} ${M.needs.text} <b>${M.needs.have}/${M.needs.of}</b></p>
    <div class="gauges"><span>Health<i style="--v:${M.health / 10}"></i></span><span>Food<i style="--v:${M.hunger / 10}"></i></span>${M.cold ? '<span class="flag">Cold</span>' : ''}</div>`
  stage.append(book)

  const tide = el('header', 'k-tide')
  const marks = [0, 6, 12, 18, 24].map((h) => `<span style="left:${(h / 24) * 100}%">${String(h).padStart(2, '0')}</span>`).join('')
  tide.innerHTML = `<div class="strip"><div class="night a"></div><div class="night b"></div>${marks}<i class="now" style="left:${(M.hour / 24) * 100}%"></i></div>`
  tide.append(cameraSwitch('k-camera'))
  stage.append(tide)

  const log = el('section', 'k-parcels')
  log.setAttribute('aria-label', 'Sky log')
  const parcels = M.feed.filter((f) => f.who === 'sky')
  log.innerHTML = parcels.concat(M.toast ? [{ t: M.time, who: 'toast', text: `${M.toast.title}: ${M.toast.text}` }] : []).slice(-2).map((f) =>
    `<article class="label ${f.who}"><div class="bars"></div><span class="lbl">${f.who === 'sky' ? 'From the sky' : 'Godling made'}</span><p>${f.text}</p><time>${f.t}</time>${f.cost ? `<b>${f.cost} cr</b>` : ''}</article>`).join('')
  stage.append(log)

  const caseEl = el('footer', 'k-case')
  const rack = el('div', 'rack')
  rack.setAttribute('role', 'toolbar')
  rack.setAttribute('aria-label', 'Sky powers')
  const slots = POWERS.map((x, i) => {
    const p = power(x.id)
    const c = el('button', `flare${p.harm ? ' harm' : ''}${p.charges === 0 && !p.pooled ? ' cooling' : ''}${p.id === selected ? ' picked' : ''}`)
    c.type = 'button'
    c.setAttribute('aria-label', `${p.name}, ${p.price} credits`)
    c.innerHTML = `<span class="cap"></span><span class="tube">${icon(p.icon, phone ? 2 : 3)}<span class="name">${p.name}</span></span>
      <span class="pips">${p.pooled ? `<span class="potbar"><i style="width:${(p.pot / p.price) * 100}%"></i></span>` : Array.from({ length: p.max }, (_, k) => `<i class="${k < p.charges ? 'on' : ''}"></i>`).join('')}</span>
      <span class="cost">${p.price}</span>${p.charges === 0 && !p.pooled ? `<span class="wait">${p.cooldown}</span>` : ''}`
    c.addEventListener('mouseenter', () => pick(p.id))
    c.addEventListener('focus', () => pick(p.id))
    rack.append(c)
    return c
  })
  caseEl.append(el('div', 'k-purse', `<span class="stamp">Credits</span><b>${M.credits}</b><small>${EURO(M.credits)}</small><button type="button" class="get">Get credits</button>`), rack)
  stage.append(caseEl)
  stage.append(el('p', 'watching', `${M.viewers.toLocaleString('en')} watching<span class="proto">Prototype · demo data</span>`))

  let tip = null
  function pick(id) {
    selected = id
    slots.forEach((s, i) => s.classList.toggle('picked', POWERS[i].id === id))
    tip?.remove()
    const p = power(id)
    if (phone) {
      tip = el('p', 'k-pickline', `<b>${p.name}</b> ${p.price} cr · ${EURO(p.price)} — ${p.charges === 0 && !p.pooled ? `ready in ${p.cooldown}` : 'tap again to fire'}`)
      caseEl.prepend(tip)
    } else {
      tip = tipFor(p, 'k-tip')
      const s = slots[POWERS.findIndex((x) => x.id === id)]
      stage.append(tip)
      const r = s.getBoundingClientRect(), sr = stage.getBoundingClientRect()
      tip.style.left = `${Math.max(16, Math.min(sr.width - tip.offsetWidth - 16, r.left - sr.left + r.width / 2 - tip.offsetWidth / 2))}px`
      tip.style.top = `${r.top - sr.top - tip.offsetHeight - 18}px`
    }
  }
  pick(selected)
  onKeys(slots)
}

// ---- 3. Sky Bar ---------------------------------------------------------------------------

function skyHud() {
  island()
  bubble('bubble-sky')
  const phone = PHONE()

  // The sun (or moon) travels an arc across the top: the hour at a glance.
  const arc = el('header', 's-arc')
  const f = M.hour / 24
  const x = f * 100, y = 100 - Math.sin(Math.PI * Math.min(1, Math.max(0, (M.hour - 5) / 16))) * 100
  arc.innerHTML = `<svg viewBox="0 0 100 20" preserveAspectRatio="none" aria-hidden="true"><path d="M0,19 Q50,-17 100,19"/></svg>
    <span class="body" style="left:${x}%;--rise:${y}">${icon(M.weather, 3)}</span>
    <span class="label">Day ${M.day} · ${M.time}</span>`
  stage.append(arc)
  stage.append(cameraSwitch('s-camera'))

  const card = el('section', 's-card')
  card.setAttribute('aria-label', 'Godling')
  const need = (name, v, cls) => `<div class="need ${cls}"><span>${name}</span><i style="--v:${v}"></i></div>`
  card.innerHTML = `<div class="who">${icon('godling', phone ? 3 : 4)}<div><h2>Godling</h2><p>${M.intention}</p></div></div>
    ${need('Health', M.health / 10, 'health')}${need('Food', M.hunger / 10, 'food')}${need('Warmth', M.cold ? 0.25 : 0.85, 'warm')}
    <p class="wants">${icon(M.needs.icon, 2)}Needs ${M.needs.of} ${M.needs.text}: ${M.needs.have} of ${M.needs.of}</p>`
  stage.append(card)

  const said = el('section', 's-said')
  said.setAttribute('aria-label', 'What Godling says and notices')
  said.innerHTML = M.feed.slice(phone ? -2 : -4).map((f) => `<p class="${f.who}">${speaker(f.who)}<span>${f.who === 'godling' ? `“${f.text}”` : f.text}</span><time>${f.t}</time></p>`).join('')
  stage.append(said)

  // The credit bar: the viewer's credits fill it; each power sits at its price and lights up once affordable.
  const scale = (c) => 0.05 + 0.9 * (Math.log10(1 + c) / Math.log10(1 + 520)) // log scale, kept inside the bar's ends
  const barWrap = el('footer', 's-bar')
  const bar = el('div', 'bar')
  bar.innerHTML = `<div class="fill" style="width:${scale(M.credits) * 100}%"><span>${M.credits} credits · ${EURO(M.credits)}</span></div>`
  const ticks = [5, 10, 25, 50, 100, 250, 500].map((c) => `<span class="tick" style="left:${scale(c) * 100}%">${c}</span>`).join('')
  bar.insertAdjacentHTML('beforeend', ticks)
  const slots = []
  const placed = [] // [position %, lane] of the gems so far: a gem too close to another climbs a lane
  const gap = phone ? 8.5 : 4.9 // about one medallion's width, in % of the bar
  for (const x of [...POWERS].sort((a, b) => a.price - b.price)) {
    const p = power(x.id)
    const pos = scale(p.price) * 100
    let lane = 0
    while (placed.some(([at, l]) => l === lane && Math.abs(at - pos) < gap)) lane++
    placed.push([pos, lane])
    const g = el('button', `gem${M.credits >= p.price || p.pooled ? ' can' : ''}${p.harm ? ' harm' : ''}${p.charges === 0 && !p.pooled ? ' cooling' : ''}${p.id === selected ? ' picked' : ''}`)
    g.type = 'button'
    g.style.left = `${pos}%`
    g.style.setProperty('--lane', lane)
    g.setAttribute('aria-label', `${p.name}, ${p.price} credits`)
    g.innerHTML = `${icon(p.icon, phone ? 2 : 3)}<span class="p">${p.price}</span>${p.pooled ? `<span class="pot"><i style="height:${(p.pot / p.price) * 100}%"></i></span>` : ''}${p.charges === 0 && !p.pooled ? `<span class="wait">${p.cooldown}</span>` : ''}`
    g.dataset.id = p.id
    g.addEventListener('mouseenter', () => pick(p.id))
    g.addEventListener('focus', () => pick(p.id))
    bar.append(g)
    slots.push(g)
  }
  barWrap.append(bar, el('button', 'get', 'Get credits'))
  stage.append(barWrap)
  stage.append(el('p', 'watching', `${M.viewers.toLocaleString('en')} watching<span class="proto">Prototype · demo data</span>`))

  let tip = null
  function pick(id) {
    selected = id
    slots.forEach((s) => s.classList.toggle('picked', s.dataset.id === id))
    tip?.remove()
    const p = power(id)
    tip = tipFor(p, 's-tip')
    stage.append(tip)
    if (!phone) {
      const s = slots.find((g) => g.dataset.id === id)
      const r = s.getBoundingClientRect(), sr = stage.getBoundingClientRect()
      tip.style.left = `${Math.max(16, Math.min(sr.width - tip.offsetWidth - 16, r.left - sr.left + r.width / 2 - tip.offsetWidth / 2))}px`
      tip.style.top = `${r.top - sr.top - tip.offsetHeight - 18}px`
    }
  }
  pick(selected)
  onKeys(slots)
}

;({ block: blockHud, kit: kitHud, sky: skyHud })[HUD]()
