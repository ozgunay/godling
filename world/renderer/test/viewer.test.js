// The viewer screen (world/viewer/viewer.js) as a viewer meets it: it loads, polls the panel (or the accounts site)
// every 1.5 s, and answers clicks, keys and the island's messages. fetch is answered here; timers are fake.
import { afterEach, describe, expect, it, vi } from 'vitest'

const NOW = 1_800_000_000 // seconds, the panel's clock

function panelStatus(more = {}) {
  return {
    world: true, watching: 1284, now: NOW, testMode: true, view: 'http://island/?spectator_token=t',
    clock: { hour: 14.5, day: 3, rain: 0, fog: 0, wind: 0.2, quake: '' },
    godling: { health: 75, hunger: 45, wet: 40, cold: true, bracing: true, knockedDown: true },
    notes: { limit: 140, every: 180, queue: 0, wait: 0 },
    mind: {
      thought: 'Two logs now.', needs: '3 logs for the gate lintel; a stone', intention: 'carry logs',
      feed: [
        { time: NOW - 60, who: 'godling', text: 'Two logs now. One more and the gate gets its lintel.' },
        { time: NOW - 50, who: 'notice', text: 'A log washed up on the beach: Log_7 lies at (12, -4)' },
        { time: NOW - 40, who: 'sky', text: 'A paper glider drifted down at (3, 4) with a note from one of the strangers who watch you. It reads: "hi"' },
        { time: NOW - 30, who: 'notice', text: 'You were hurt by lightning striking close by: your health is 70 of 100' },
        { time: NOW - 20, who: 'notice', text: 'You have grown cold: the night is chilly out here' },
        { time: NOW - 10, who: 'notice', text: 'You noticed something about yourself' }, // about "you", no rewrite: left out
        { time: null, who: 'odd', text: `Block_3 moved near (1.5, 2) ${'and on '.repeat(40)}` },
      ],
    },
    popups: [
      { id: 1, time: NOW - 2, kind: 'power', name: 'mara', power: 'Meteor', text: 'Meteor #1', ok: true },
      { id: 2, time: NOW - 1, kind: 'note', name: 'tomv', power: 'Note', text: 'hello Godling', ok: true, noteId: 7 },
      { id: 3, time: NOW - 100, kind: 'power', name: '', power: 'Unknown', text: '', ok: true },
    ],
    ...more,
  }
}

const account = (more = {}) => ({ enabled: true, signedIn: true, username: 'ann', credits: 30, free: false, notesMuted: false,
  signIn: '/accounts/login/', signUp: '/accounts/signup/', signOut: '/accounts/logout/', creditsPage: '/credits/', ...more })

// Each test's screen is a page of its own: the window listeners it adds go when the test ends, as they would with its
// page (jsdom keeps one window for every test, and an old screen's keys would reach the frame of a page long gone).
const pageListeners = []

async function boot({ statuses = [panelStatus()], answers = {}, phone = false, coarse = false, stored = {} } = {}) {
  vi.resetModules()
  const listen = globalThis.addEventListener.bind(globalThis)
  vi.spyOn(globalThis, 'addEventListener').mockImplementation((type, fn, options) => {
    pageListeners.push([type, fn, options])
    listen(type, fn, options)
  })
  vi.useFakeTimers()
  vi.setSystemTime(NOW * 1000)
  document.body.innerHTML = '<main id="stage"></main>'
  document.head.innerHTML = ''
  document.cookie = 'csrftoken=abc123'
  localStorage.clear()
  for (const [k, v] of Object.entries(stored)) localStorage.setItem(k, v)
  vi.stubGlobal('matchMedia', (q) => ({ matches: q.includes('max-width') ? phone : q.includes('coarse') ? coarse : false }))
  vi.stubGlobal('requestAnimationFrame', (fn) => setTimeout(fn, 16))
  const posts = []
  const queue = [...statuses]
  vi.stubGlobal('fetch', vi.fn(async (path, init = {}) => {
    if (String(path).startsWith('api/status')) {
      const s = queue.length > 1 ? queue.shift() : queue[0]
      if (s instanceof Error) throw s
      return { json: async () => structuredClone(s) }
    }
    if (init.body === undefined) { // asking how a queued power went: answers[path] gives { status, body }, or throws
      const a = answers[path]
      const { status = 200, body = {} } = (typeof a === 'function' ? a() : a) || {}
      return { status, ok: status < 400, json: async () => body }
    }
    const body = JSON.parse(init.body)
    posts.push({ path, body, headers: init.headers })
    const a = answers[path]
    const reply = typeof a === 'function' ? a(body) : a
    if (reply instanceof Error) throw reply
    return { json: async () => reply ?? { ok: true, text: 'done' } }
  }))
  await import('../../viewer/viewer.js')
  await vi.advanceTimersByTimeAsync(0)
  const stage = document.getElementById('stage')
  const view = stage.querySelector('iframe')
  const told = []
  if (view.contentWindow) vi.spyOn(view.contentWindow, 'postMessage').mockImplementation((m) => told.push(m))
  const $ = (sel) => stage.querySelector(sel)
  const slot = (id) => stage.querySelector(`.slot[data-id="${id}"]`)
  const fromIsland = (data) => {
    const event = new MessageEvent('message', { data: { source: 'godling-renderer', ...data } })
    Object.defineProperty(event, 'source', { value: view.contentWindow })
    dispatchEvent(event)
  }
  return { stage, view, posts, told, $, slot, fromIsland, tick: (ms) => vi.advanceTimersByTimeAsync(ms) }
}

const key = (type, code, extra = {}) => new KeyboardEvent(type, { code, key: extra.key ?? code, bubbles: true, cancelable: true, ...extra })

// The page goes, as a reload or the end of a test takes it.
function closePage() {
  for (const [type, fn, options] of pageListeners.splice(0)) removeEventListener(type, fn, options)
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
}

describe('the viewer screen', () => {
  afterEach(closePage)

  it('shows the island, the clock, Godling\'s mind and body, and what viewers did', async () => {
    const { stage, view, $ } = await boot()
    expect(view.src).toBe('http://island/?spectator_token=t&embed=1')
    expect($('.b-live .word').textContent).toBe('Live')
    expect($('.b-live .n').textContent).toBe('1,284')
    expect($('.b-clock .day').textContent).toBe('Day 3')
    expect($('.b-clock .time').textContent).toBe('14:30')
    const lines = [...stage.querySelectorAll('.b-feed .line .text')].map((e) => e.textContent)
    expect(lines).toContain('A note drifted down: "hi"')
    expect(lines).toContain('Godling was hurt by lightning striking close by')
    expect(lines).toContain('Godling has grown cold')
    expect(lines.some((l) => l.startsWith('A block moved') && l.endsWith('…'))).toBe(true)
    expect(lines.some((l) => l.includes('yourself'))).toBe(false)
    expect($('.b-objective .what').textContent).toBe('3 logs for the gate lintel')
    expect($('.b-vitals .states').textContent).toContain('Knocked down')
    expect($('.b-vitals .states').textContent).toContain('Wet')
    expect(stage.querySelectorAll('.b-pop')).toHaveLength(2) // the old one is not shown again
    expect($('.b-pop.harm .head').textContent).toBe('mara called a meteor')
    expect($('.b-pop.note q').textContent).toBe('hello Godling')
    expect($('.b-pop.note .report')).toBeNull() // the panel on its own: no reports
    expect($('.b-purse').textContent).toContain('Free')
    expect(stage.classList.contains('has-pop')).toBe(true)
    await vi.advanceTimersByTimeAsync(20)
    expect($('.b-pop').classList.contains('in')).toBe(true)
    await vi.advanceTimersByTimeAsync(15000) // the pop-ups go
    expect(stage.querySelectorAll('.b-pop')).toHaveLength(0)
    expect(stage.classList.contains('has-pop')).toBe(false)
  })

  it('goes offline when the panel cannot be reached, and comes back', async () => {
    const quiet = panelStatus({ world: false, mind: { feed: [] }, godling: null, popups: [], clock: {}, view: '', now: undefined })
    const { $, stage, tick } = await boot({ statuses: [new Error('down'), quiet, panelStatus({ clock: { hour: 2, rain: 0.5, quake: 'rumble' }, notes: { wait: 30 } })] })
    expect($('.b-live .word').textContent).toBe('Offline')
    expect($('.b-clock .day').textContent).toBe('Out of reach')
    expect(stage.querySelector('.b-feed .waiting')).not.toBeNull()
    await tick(1500)
    expect($('.b-vitals').innerHTML).toBe('')
    expect($('.b-objective').hidden).toBe(true)
    await tick(1500)
    expect($('.b-clock').textContent).toContain('Shaking')
    expect($('.b-clock .day').textContent).toBe('Day 1')
    await tick(1000)
    expect($('.b-note .get').textContent).toMatch(/^Next note in 0:/)
  })

  it('switches the camera, remembers it, and forwards the flying keys to the island', async () => {
    const { $, view, told } = await boot()
    const [follow, free] = $('.b-camera').querySelectorAll('button')
    expect(follow.getAttribute('aria-pressed')).toBe('true')
    view.dispatchEvent(new Event('load'))
    expect(told.at(-1)).toEqual({ source: 'godling-viewer', type: 'godling-camera', mode: 'follow' })
    // to the island's own origin only, never to whatever page the frame was sent to instead
    expect(view.contentWindow.postMessage).toHaveBeenLastCalledWith(told.at(-1), 'http://island')
    free.click()
    expect(free.getAttribute('aria-pressed')).toBe('true')
    expect(localStorage.getItem('godling.camera')).toBe('free')
    free.focus()
    free.dispatchEvent(key('keydown', 'KeyW'))
    expect(told.at(-1)).toEqual({ source: 'godling-viewer', type: 'godling-key', code: 'KeyW', down: true })
    told.length = 0
    free.dispatchEvent(key('keydown', 'Space'))
    expect(told).toEqual([]) // Space presses the button
    dispatchEvent(key('keyup', 'KeyW'))
    expect(told.at(-1)).toMatchObject({ code: 'KeyW', down: false })
    dispatchEvent(new Event('blur'))
    expect(told.at(-1)).toMatchObject({ code: 'all' })
    follow.click()
    told.length = 0
    dispatchEvent(key('keydown', 'KeyW'))
    dispatchEvent(key('keyup', 'KeyW'))
    expect(told).toEqual([])
  })

  it('starts in the free camera when it was left there, on a touch screen', async () => {
    const { $ } = await boot({ stored: { 'godling.camera': 'free', 'godling.name': 'Ann' }, coarse: true })
    expect($('.b-camera button:last-child').getAttribute('aria-pressed')).toBe('true')
    expect($('.b-camhint').textContent).toContain('pinch')
    expect($('#note-name').value).toBe('Ann')
  })

  it('shows a power\'s tip, picks slots with number keys, and calls a power', async () => {
    const { stage, slot, posts, $ } = await boot({ answers: { 'api/power': { ok: true, id: 99, time: NOW, kind: 'power', name: 'me', power: 'Earthquake', wait: 600 } } })
    slot('Meteor').dispatchEvent(new MouseEvent('mouseenter'))
    expect($('.b-tip strong').textContent).toBe('Meteor')
    expect($('.b-tip').textContent).toContain('free while testing')
    slot('Meteor').dispatchEvent(new MouseEvent('mouseleave'))
    expect($('.b-tip')).toBeNull()
    dispatchEvent(key('keydown', 'Digit7', { key: '7' }))
    expect(document.activeElement).toBe(slot('Note'))
    expect($('.b-tip').textContent).toContain('140 characters')
    slot('Note').blur()
    dispatchEvent(key('keydown', 'Digit6', { key: '6', ctrlKey: true })) // with a modifier: not a slot key
    slot('Earthquake').click()
    await vi.advanceTimersByTimeAsync(0)
    expect(posts[0]).toMatchObject({ path: 'api/power', body: { power: 'Earthquake', client: expect.any(String) } })
    expect(posts[0].headers['X-CSRFToken']).toBe('abc123')
    expect(stage.querySelector('.b-pop .head').textContent).toBe('me shook the island')
    expect(slot('Earthquake').classList.contains('cooling')).toBe(true)
    slot('Earthquake').click() // cooling: not called again
    expect($('.b-say').textContent).toMatch(/Earthquake is not ready yet: 10:00 to go/)
    slot('Earthquake').dispatchEvent(new FocusEvent('focus'))
    expect($('.b-tip').textContent).toContain('Ready')
  })

  it('says why a power did not work, and when the island is out of reach', async () => {
    const answers = { 'api/power': { ok: false, needCredits: true, text: 'Meteor costs 300 credits; you hold 0.' } }
    const { slot, $, fromIsland, tick } = await boot({ answers })
    slot('Meteor').click() // aim first
    fromIsland({ type: 'godling-aimed', x: 1, z: 2 })
    await tick(0)
    expect($('.b-say').textContent).toBe('Meteor costs 300 credits; you hold 0.')
    expect($('.b-purse').classList.contains('nudge')).toBe(true)
    answers['api/power'] = { ok: false }
    slot('Earthquake').click()
    await tick(0)
    expect($('.b-say').textContent).toBe('Earthquake did not work.')
    answers['api/power'] = new Error('network')
    slot('Earthquake').click()
    await tick(0)
    expect($('.b-say').textContent).toBe('The island is out of reach. Try again in a moment.')
    await tick(6000)
    expect($('.b-say').className).toBe('b-say')
  })

  it('behind the site, asks after a queued power until the island has answered', async () => {
    const asked = []
    const answers = {
      'api/power': { ok: true, pending: 12, text: 'Stone: on its way to the island…', credits: 25 },
      'api/power/12': () => {
        asked.push(Date.now())
        if (asked.length === 1) throw new Error('a blip')
        return asked.length < 3 ? { body: { ok: true, pending: 12 } }
          : { body: { ok: true, id: 98, time: NOW, kind: 'power', name: 'ann', power: 'Stone', credits: 25 } }
      },
    }
    const { stage, slot, $, tick } = await boot({ statuses: [panelStatus({ account: account() })], answers })
    slot('Stone').click()
    $('.b-aim .get').click()
    await tick(0)
    expect(slot('Stone').classList.contains('calling')).toBe(true) // on its way
    await tick(1500)
    expect(asked).toHaveLength(3) // every half second, through a blip
    expect(stage.querySelector('.b-pop .head').textContent).toContain('ann')
    expect(slot('Stone').classList.contains('calling')).toBe(false)
    expect($('.b-purse').textContent).toContain('25')
  })

  it('a queued power whose viewer was signed out, that is gone, or that the island is slow to take', async () => {
    const answers = { 'api/power': { ok: true, pending: 5 }, 'api/power/5': { status: 401 } }
    const { slot, $, tick } = await boot({ statuses: [panelStatus({ account: account() })], answers })
    const callStone = async () => {
      slot('Stone').click()
      $('.b-aim .get').click()
      await tick(0)
    }
    await callStone()
    await tick(500)
    expect($('.b-say').textContent).toBe('You were signed out; sign in again to see how your power went.')
    expect($('.b-account').classList.contains('nudge')).toBe(true)
    answers['api/power/5'] = { status: 404 }
    await callStone()
    await tick(500)
    expect($('.b-say').textContent).toBe('That power is no longer on its way.')
    let asked = 0
    answers['api/power/5'] = () => { asked += 1; return { status: 503 } } // the site busy: asked again and again
    await callStone()
    await tick(12_000)
    expect(asked).toBe(21) // every half second for ten seconds, then every two
    vi.setSystemTime(Date.now() + 4.5 * 60 * 1000) // until the site has surely given the call up
    await tick(2000)
    expect($('.b-say').textContent).toBe('The island is slow to answer; your power is still on its way.')
  })

  it('the island frame\'s own stream decides the Live badge', async () => {
    const { $, fromIsland } = await boot()
    expect($('.b-live .word').textContent).toBe('Live') // until the frame says anything, the panel's word
    fromIsland({ type: 'godling-stream', state: 'reconnecting', world: 'up' })
    expect($('.b-live .word').textContent).toBe('Reconnecting')
    expect($('.b-live').classList.contains('down')).toBe(true)
    expect($('.b-live').getAttribute('aria-label')).toBe('Reconnecting')
    fromIsland({ type: 'godling-stream', state: 'live', world: 'down' })
    expect($('.b-live .word').textContent).toBe('Restarting')
    fromIsland({ type: 'godling-stream', state: 'odd' })
    expect($('.b-live .word').textContent).toBe('Offline')
    fromIsland({ type: 'godling-stream', state: 'live' })
    expect($('.b-live .word').textContent).toBe('Live')
    expect($('.b-live').getAttribute('aria-label')).toBe('Live, 1284 watching')
  })

  it('aims a power on the island, or lets the sky choose', async () => {
    const { stage, slot, $, told, posts, fromIsland, tick } = await boot()
    slot('Meteor').dispatchEvent(new FocusEvent('focus'))
    slot('Meteor').click()
    expect(stage.classList.contains('aiming')).toBe(true)
    expect($('.b-tip')).toBeNull()
    expect(told.at(-1)).toMatchObject({ type: 'godling-aim', power: 'Meteor' })
    slot('Meteor').dispatchEvent(new MouseEvent('mouseenter')) // no tip while aiming
    expect($('.b-tip')).toBeNull()
    fromIsland({ type: 'godling-aim-hover', atGodling: true })
    expect($('.b-aim .words').textContent).toBe('On Godling: the blast will hit it')
    fromIsland({ type: 'godling-aim-hover', atGodling: false })
    expect($('.b-aim .words').textContent).toBe('Click to call it here')
    slot('Meteor').click() // the same slot again: aiming ends
    expect($('.b-aim').hidden).toBe(true)
    slot('Stone').click()
    fromIsland({ type: 'godling-aim-hover', atGodling: true })
    expect($('.b-aim .words').textContent).toBe('At Godling: it lands at its feet')
    fromIsland({ type: 'godling-aim-cancel' })
    expect($('.b-aim').hidden).toBe(true)
    fromIsland({ type: 'godling-aim-hover', atGodling: true }) // not aiming: nothing
    fromIsland({ type: 'godling-aimed', x: 0, z: 0 })
    const notTheIsland = new MessageEvent('message', { data: { source: 'godling-renderer', type: 'godling-aim-cancel' } })
    dispatchEvent(notTheIsland)
    slot('Log').click()
    fromIsland({ type: 'godling-aimed', x: '4.5', z: -2 })
    await tick(0)
    expect(posts.at(-1).body).toMatchObject({ power: 'Log', at: [4.5, -2] })
    slot('Regrow').click()
    $('.b-aim .get').click() // let the sky choose
    await tick(0)
    expect(posts.at(-1).body).toMatchObject({ power: 'Regrow' })
    expect(posts.at(-1).body.at).toBeUndefined()
    slot('Lightning').click()
    $('.b-aim .cancel').click()
    expect($('.b-aim').hidden).toBe(true)
    slot('Lightning').click()
    dispatchEvent(key('keydown', 'Escape', { key: 'Escape' }))
    expect($('.b-aim').hidden).toBe(true)
    $('.b-aim .get').click() // nothing picked: nothing called
    await tick(0)
    expect(posts.at(-1).body.power).toBe('Regrow')
  })

  it('cools an aimed power, and the note box closes the aim', async () => {
    const { slot, $, tick } = await boot({ answers: { 'api/power': { ok: false, text: 'no', wait: 90 } } })
    slot('Lightning').click()
    $('.b-aim .get').click()
    await tick(0)
    slot('Lightning').click()
    expect($('.b-say').textContent).toMatch(/Lightning is not ready yet: 1:30/)
    slot('Stone').click()
    slot('Note').click() // the note box takes the aim's place
    expect($('.b-aim').hidden).toBe(true)
    expect($('.b-note').hidden).toBe(false)
  })

  it('sends a note, counts its letters, and waits its turn', async () => {
    const answers = { 'api/note': { ok: true, text: 'Folded into a glider.', wait: 180 } }
    const { slot, $, posts, tick } = await boot({ answers })
    slot('Note').click()
    const box = $('#note-text')
    expect(document.activeElement).toBe(box)
    box.value = 'hello 🙂'
    box.dispatchEvent(new Event('input'))
    expect($('.b-note .count').textContent).toBe('7/140')
    box.value = 'x'.repeat(140)
    box.dispatchEvent(new Event('input'))
    expect($('.b-note .count').classList.contains('full')).toBe(true)
    $('#note-name').value = ' Ann '
    box.dispatchEvent(key('keydown', 'Enter', { key: 'Enter', shiftKey: true })) // a new line, not a send
    expect(posts).toHaveLength(0)
    box.dispatchEvent(key('keydown', 'Enter', { key: 'Enter' }))
    await tick(0)
    expect(posts[0].body).toMatchObject({ name: 'Ann', text: 'x'.repeat(140) })
    expect(localStorage.getItem('godling.name')).toBe('Ann')
    expect($('.b-note .n-hint').textContent).toBe('Folded into a glider.')
    expect(box.value).toBe('')
    $('.b-note').requestSubmit() // too soon after the last
    await tick(0)
    expect(posts).toHaveLength(1)
    answers['api/note'] = { ok: false, text: 'Write something first.' }
    vi.setSystemTime(Date.now() + 181000) // past its turn (the clock moved on, not every frame between)
    await tick(1600)
    $('.b-note').requestSubmit()
    await tick(0)
    expect($('.b-note .n-hint').className).toBe('n-hint no')
    box.dispatchEvent(key('keydown', 'Escape', { key: 'Escape' }))
    expect($('.b-note').hidden).toBe(true)
    box.dispatchEvent(key('keydown', 'KeyA', { key: 'a' }))
    slot('Note').click()
    dispatchEvent(key('keydown', 'Escape', { key: 'Escape' }))
    expect($('.b-note').hidden).toBe(true)
  })

  it('behind the accounts site: the account, its credits, the site\'s prices, and reports', async () => {
    const powers = {
      Stone: { label: 'Stone', price: 4, kind: 'Gift', harms: false, does: 'drops', rule: '', did: '', after: '' },
      Meteor: { label: 'Meteor', price: 300, kind: 'Disaster', harms: true, does: 'blasts <img src=x>', rule: 'one a minute', did: 'sent a meteor', after: 'boom' },
    }
    const signedIn = panelStatus({ account: account(), powers, notes: { limit: 100, every: 120, queue: 0, wait: 0 } })
    const answers = { 'api/report': { ok: true, text: 'Reported. Thank you.' }, 'api/note': { ok: false, signIn: true, text: 'Sign in.' } }
    const { stage, slot, $, posts, tick } = await boot({ statuses: [signedIn, signedIn, panelStatus({ account: account({ signedIn: false, username: '' }), powers })], answers })
    expect($('.b-account .who').textContent).toBe('ann')
    expect($('.b-account form').action).toContain('/accounts/logout/')
    expect($('.b-account input[name=csrfmiddlewaretoken]').value).toBe('abc123')
    expect($('#note-name').hidden).toBe(true)
    expect($('.b-purse').textContent).toContain('30credits')
    expect($('.b-purse .get').getAttribute('href')).toBe('/credits/')
    expect(slot('Log').hidden).toBe(true) // switched off on the site
    expect(slot('Meteor').querySelector('.price').classList.contains('short')).toBe(true)
    expect($('#note-text').maxLength).toBe(100)
    slot('Meteor').dispatchEvent(new MouseEvent('mouseenter'))
    expect($('.b-tip').textContent).toContain('one a minute')
    expect($('.b-tip').textContent).not.toContain('free while testing')
    // what the admin typed is shown as words, never as markup (the screen shares the admin's origin)
    expect($('.b-tip p').textContent).toBe('blasts <img src=x>')
    expect($('.b-tip img')).toBeNull()
    const report = $('.b-pop.note .report')
    report.click()
    await tick(0)
    expect(posts.at(-1)).toMatchObject({ path: 'api/report', body: { note: 7 } })
    expect(report.textContent).toBe('Reported')
    slot('Note').click()
    $('.b-note').requestSubmit()
    await tick(0)
    expect($('.b-account').classList.contains('nudge')).toBe(true)
    await tick(1500) // the same account: drawn once
    await tick(1500) // signed out now
    expect($('.b-account a.get').getAttribute('href')).toBe('/accounts/login/?next=%2F')
    expect($('.b-purse').textContent).toContain('sign in to call powers')
    expect(stage.querySelectorAll('.slot:not([hidden])').length).toBe(3)
  })

  it('a report that did not go through, credits from a call, and the site\'s test mode', async () => {
    const free = panelStatus({ account: account({ free: true }), popups: [
      { id: 5, time: NOW, kind: 'note', name: 'tomv', text: 'hi', noteId: 9 },
      { id: 6, time: NOW, kind: 'note', name: 'ann', text: 'mine', noteId: 10 }] })
    const answers = { 'api/report': { ok: false, text: 'That is your own note.' }, 'api/power': { ok: false, text: 'no', credits: 12 } }
    const { stage, slot, $, tick } = await boot({ statuses: [free, panelStatus({ account: account({ credits: 12 }) })], answers })
    expect($('.b-purse').textContent).toContain('Free')
    expect(stage.querySelectorAll('.b-pop .report')).toHaveLength(1) // not on one's own note
    $('.b-pop .report').click()
    await tick(0)
    expect($('.b-pop .report').textContent).toBe('Not reported')
    slot('Earthquake').click()
    await tick(0)
    expect($('.b-purse').textContent).toContain('Free') // the site's test mode: credits are not shown
    await tick(1500) // test mode is over
    expect($('.b-purse').textContent).toContain('12credits')
  })

  it('picks an icon for what Godling needs', async () => {
    const needs = ['a stone wall', 'two coconuts', 'a warm fire', 'a friend']
    const { $, tick } = await boot({ statuses: needs.map((n) => panelStatus({ mind: { feed: [], needs: n } })) })
    const icons = []
    for (let i = 0; i < needs.length; i++) {
      icons.push($('.b-objective svg').outerHTML)
      await tick(1500)
    }
    expect(new Set(icons).size).toBe(4)
  })

  it('on a phone: fewer lines, one pop-up, no tips; and a private window that keeps nothing', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('private') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('private') })
    const { stage, slot, $ } = await boot({ phone: true })
    expect(stage.querySelectorAll('.b-feed .line').length).toBeLessThanOrEqual(3)
    expect(stage.querySelectorAll('.b-pop')).toHaveLength(1)
    slot('Stone').dispatchEvent(new MouseEvent('mouseenter'))
    expect($('.b-tip')).toBeNull()
  })

  it('the bottle: only behind the site; a signed-in viewer sends a bug with what their screen shows', async () => {
    let screen = await boot()
    expect(screen.$('.b-bottle-open').hidden).toBe(true) // the panel on its own has nowhere to send it
    closePage()
    screen = await boot({ statuses: [panelStatus({ account: account() })] })
    const { $, posts, tick, stage } = screen
    const opener = $('.b-bottle-open')
    expect(opener.hidden).toBe(false)
    opener.click()
    expect($('.b-bottle').hidden).toBe(false)
    expect(opener.getAttribute('aria-expanded')).toBe('true')
    expect(document.activeElement).toBe($('#bottle-text'))
    expect($('.bt-hint').textContent).toBe('Sent from your account, ann.')
    expect($('.facts').textContent).toBe('1024×768 · live · day 3 14:30 · follow camera')
    expect($('#bottle-text').placeholder).toBe('What happened, and what did you expect instead?')
    $('.bt-send').click()
    await tick(0)
    expect($('.bt-hint').textContent).toBe('Write a few words first.')
    expect(posts.some((p) => p.path === 'api/feedback')).toBe(false)
    $('.bt-kind input[value=question]').click()
    expect($('#bottle-text').placeholder).toBe('Ask the makers anything about Godling or the island.')
    $('.bt-kind input[value=bug]').click()
    $('#bottle-text').value = 'The log fell through the wall.'
    $('#bottle-text').dispatchEvent(new Event('input'))
    expect($('.b-bottle .count').textContent).toBe('30/2,000')
    expect(JSON.parse(localStorage.getItem('godling.bottle'))).toEqual({ kind: 'bug', text: 'The log fell through the wall.' })
    $('#bottle-text').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true }))
    await tick(0)
    const sent = posts.find((p) => p.path === 'api/feedback')
    expect(sent.headers['X-CSRFToken']).toBe('abc123')
    expect(sent.body).toMatchObject({ kind: 'bug', text: 'The log fell through the wall.', screen: {
      view: 'live', day: 3, hour: 14.5, camera: 'follow', stream: 'live', size: '1024x768', touch: false } })
    expect($('.bt-write').hidden).toBe(true)
    expect($('.bt-sent').hidden).toBe(false)
    expect(document.activeElement).toBe($('.bt-back'))
    expect(JSON.parse(localStorage.getItem('godling.bottle')).text).toBe('')
    $('.bt-again').click()
    expect($('.bt-write').hidden).toBe(false)
    $('#bottle-text').dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect($('.b-bottle').hidden).toBe(true)
    expect(document.activeElement).toBe(opener)
    expect(stage.classList.contains('bottle-open')).toBe(false)
    opener.click()
    $('.bt-close').click()
    expect($('.b-bottle').hidden).toBe(true)
  })

  it('the bottle: refusals, facts left off, the past, and a draft kept through signing in', async () => {
    const out = panelStatus({ account: account({ signedIn: false, username: '' }) })
    let screen = await boot({ statuses: [out] })
    screen.$('.b-bottle-open').click()
    expect(screen.$('.bt-send').hidden).toBe(true)
    const signIn = screen.$('.bt-signin')
    expect(signIn.hidden).toBe(false)
    expect(signIn.getAttribute('href')).toBe('/accounts/login/?next=%2F')
    expect(screen.$('.bt-hint').textContent).toBe('Sign in to send it. Your words wait here meanwhile.')
    screen.$('.bt-kind input[value=idea]').click()
    screen.$('#bottle-text').value = 'A coconut power.'
    screen.$('#bottle-text').dispatchEvent(new Event('input'))
    document.addEventListener('click', (e) => e.preventDefault(), { capture: true, once: true }) // no navigating in jsdom
    signIn.click()
    screen.$('.bt-write').requestSubmit() // signed out: nothing is sent
    await screen.tick(0)
    expect(screen.posts.some((p) => p.path === 'api/feedback')).toBe(false)
    const kept = { 'godling.bottle': localStorage.getItem('godling.bottle'), 'godling.bottle.reopen': localStorage.getItem('godling.bottle.reopen') }
    expect(kept['godling.bottle.reopen']).toBe('1')
    closePage()

    const answers = {
      'api/feedback': (body) => (body.screen === null ? new Error('down')
        : { ok: false, text: 'That is 6 messages this hour. The next can go in 12:00.', wait: 720 }),
      'api/replay/index': { body: { segments: [{ start: NOW * 1000 - 3600e3, end: NOW * 1000, live: true }] } },
    }
    screen = await boot({ statuses: [panelStatus({ account: account() })], answers, stored: kept, phone: true })
    const { $, posts, tick, fromIsland, stage } = screen
    expect($('.b-bottle').hidden).toBe(false) // back from signing in: open again, words and kind kept
    expect(document.activeElement).toBe($('.b-bottle')) // on a phone, no keyboard before the viewer has read it
    expect($('#bottle-text').value).toBe('A coconut power.')
    expect($('.bt-kind input[value=idea]').checked).toBe(true)
    expect(localStorage.getItem('godling.bottle.reopen')).toBe('')
    $('.bt-send').click()
    await tick(0)
    expect($('.bt-hint').textContent).toBe('That is 6 messages this hour. The next can go in 12:00.')
    expect($('.bt-hint').classList.contains('no')).toBe(true)
    expect($('#bottle-text').value).toBe('A coconut power.') // refused: the words stay
    $('.bt-attach input').click()
    $('.bt-send').click()
    await tick(0)
    expect(posts.filter((p) => p.path === 'api/feedback').at(-1).body.screen).toBeNull()
    expect($('.bt-hint').textContent).toBe('The island is out of reach. Try again in a moment.')
    // From the past, the report says when.
    fromIsland({ type: 'godling-ready', live: true })
    stage.querySelector('.b-rewind').click()
    await tick(0)
    $('.bt-attach input').click()
    $('.bt-send').click()
    await tick(0)
    const fromThePast = posts.filter((p) => p.path === 'api/feedback').at(-1).body.screen
    expect(fromThePast).toMatchObject({ view: 'replay', moment: NOW * 1000 - 600e3 })
    expect(fromThePast.day).toBeUndefined() // the live clock says nothing about the moment watched
    expect($('.facts').textContent).toContain('the past')
  })

  it('the bottle reads a browser and a system plainly', async () => {
    const { browserOf, systemOf, factsLine } = await import('../../viewer/feedback.js')
    const agents = {
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0': ['Edge 142', 'Windows'],
      'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1': ['Safari 18', 'iOS'],
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0': ['Firefox 144', 'macOS'],
      'Mozilla/5.0 (Linux; Android 15; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36': ['Samsung Internet 28', 'Android'],
      'Mozilla/5.0 (X11; CrOS x86_64 16093.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 OPR/120.0.0.0': ['Opera 120', 'ChromeOS'],
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36': ['Chrome 142', 'Linux'],
      'curl/8.0': ['', ''],
    }
    for (const [ua, [browser, system]] of Object.entries(agents)) expect([browserOf(ua), systemOf(ua)]).toEqual([browser, system])
    expect(factsLine({ size: '375x812', browser: 'Safari 18', system: 'iOS', view: 'replay', camera: 'free' }))
      .toBe('375×812 · Safari 18 · iOS · the past · free camera')
    expect(factsLine({})).toBe('')
  })
})
