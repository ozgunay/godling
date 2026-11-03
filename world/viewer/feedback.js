// The bottle: while the site is in beta, viewers tell the people who make the island about a bug, a question or an
// idea (web/apps/feedback). Notes fly in to Godling as paper gliders; these drift out to the makers, and Godling never
// reads them. Only behind the accounts site, and sending needs an account (the user's choice, 2026-11-03); a signed-out
// viewer's words wait here while they sign in.
import { when } from './replay.js'

const LIMIT = 2000 // web/apps/feedback/models.py TEXT_LIMIT
const MIN = 3 // web/apps/feedback/views.py TEXT_MIN
const DRAFT = 'godling.bottle' // the words, the kind and whose they are, kept until they are sent
const BACK = 'bottle' // ?bottle=1: back from signing in through the bottle, so it opens again
const KINDS = [
  { id: 'bug', name: 'Bug', ask: 'What happened, and what did you expect instead?' },
  { id: 'question', name: 'Question', ask: 'Ask the makers anything about Godling or the island.' },
  { id: 'idea', name: 'Idea', ask: 'A power, a change, something you wish you could do here…' },
]

// A browser's and a system's names from its user agent, for a bug report: a name and a major version, nothing finer.
const BROWSERS = [[/Edg(?:A|iOS)?\/(\d+)/, 'Edge'], [/OPR\/(\d+)/, 'Opera'], [/SamsungBrowser\/(\d+)/, 'Samsung Internet'],
  [/(?:Firefox|FxiOS)\/(\d+)/, 'Firefox'], [/(?:Chrome|CriOS)\/(\d+)/, 'Chrome'], [/Version\/(\d+)[\d.]*(?: Mobile\/\S+)? Safari/, 'Safari']]
export function browserOf(ua) {
  for (const [re, name] of BROWSERS) {
    const m = ua.match(re)
    if (m) return `${name} ${m[1]}`
  }
  return ''
}
export function systemOf(ua) {
  return /iPhone|iPad|iPod/.test(ua) ? 'iOS' : /Android/.test(ua) ? 'Android' : /CrOS/.test(ua) ? 'ChromeOS'
    : /Windows/.test(ua) ? 'Windows' : /Macintosh|Mac OS X/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : ''
}

const two = (n) => String(n).padStart(2, '0')
// The facts as the viewer reads them under the checkbox: every one that will be sent (viewer.js screenFacts), in words.
export function factsLine(f) {
  return [
    f.size && `${f.size.replace('x', '×')}${f.pixels ? ` at ${f.pixels}x` : ''}${f.touch ? ', touch' : ''}`,
    [f.browser, f.system].filter(Boolean).join(' on '),
    f.view === 'replay' && `the past${f.moment ? `, ${when(f.moment)}` : ''}`,
    f.stream && `island ${f.stream}`,
    Number.isInteger(f.minute) && `day ${f.day} ${two(Math.floor(f.minute / 60))}:${two(f.minute % 60)}`,
    f.camera && `${f.camera} camera`,
  ].filter(Boolean).join(' · ')
}

export function createFeedback({ stage, dock, el, icon, post, store, facts, phone, onOpen }) {
  let account = null
  let open = false
  let unseen = false // a bottle went while the panel was closed: its confirmation waits for the next look
  const draft = (() => {
    try { return JSON.parse(store.get(DRAFT) || '{}') || {} } catch { return {} }
  })()
  let owner = typeof draft.owner === 'string' ? draft.owner : '' // who wrote the words: '' while signed out
  // Back from signing in through the bottle: open it again, once, and take the mark off the address.
  const here = new URL(location.href)
  let reopen = here.searchParams.get(BACK) === '1'
  if (reopen) {
    here.searchParams.delete(BACK)
    history.replaceState(history.state, '', here)
  }

  // ---- the parts ----
  // A pressable island block, as the camera buttons are: on a phone it stands at the right edge like them.
  const opener = el('button', 'b-bottle-open cam', `${icon('bottle', 2)}<span class="word">Feedback</span><em class="beta">Beta</em>`)
  opener.type = 'button'
  opener.hidden = true
  opener.setAttribute('aria-label', 'Feedback (beta): send the makers a message')
  opener.setAttribute('aria-controls', 'bottle')
  opener.setAttribute('aria-expanded', 'false')

  const panel = el('section', 'b-bottle stone')
  panel.id = 'bottle'
  panel.hidden = true
  panel.tabIndex = -1
  panel.setAttribute('role', 'dialog')
  panel.setAttribute('aria-labelledby', 'bottle-title')
  panel.innerHTML = `<header class="bt-head">${icon('bottle', 3)}<h2 id="bottle-title">Message in a bottle</h2><em class="beta">Beta</em>
    <button type="button" class="bt-close" aria-label="Close">${icon('close', 2)}</button></header>
  <form class="bt-write" novalidate>
    <p class="bt-lede"><span class="long">Tell the island’s makers about a bug, a question or an idea. </span>Godling never reads these; the makers do.</p>
    <fieldset class="bt-kinds"><legend class="sr">What is it?</legend>${KINDS.map((k) => `<label class="bt-kind block">
      <input type="radio" name="bottle-kind" value="${k.id}">${icon(k.id, 2)}<span>${k.name}</span></label>`).join('')}</fieldset>
    <label class="sr" for="bottle-text">Your message</label>
    <textarea id="bottle-text" rows="5" maxlength="${LIMIT}"></textarea>
    <div class="bt-meta"><label class="bt-attach"><input type="checkbox" checked><span class="box">${icon('tick', 2)}</span>
      <span class="words">Attach what my screen shows<small class="facts"></small></span></label>
      <span class="count">0/${LIMIT}</span></div>
    <div class="bt-foot"><p class="bt-hint" role="status"></p>
      <button type="submit" class="get bt-send">Cork and send</button><a class="get bt-signin">Sign in to send</a></div>
  </form>
  <div class="bt-sent" hidden>
    <div class="bt-sea" aria-hidden="true"><span class="bt-drift">${icon('bottle', 3)}</span></div>
    <p class="bt-done" role="status">Corked and sent</p>
    <p class="bt-thanks">Your bottle is drifting to the makers. Thank you for helping build the island.</p>
    <div class="bt-foot"><button type="button" class="quiet bt-again">Write another</button>
      <button type="button" class="get bt-back">Back to the island</button></div>
  </div>`
  // One corner holds both, the panel stacked above its opener by layout: neither can run into the other, whatever the
  // root size. The corner itself lets the island have every click it does not cover (viewer.css).
  const corner = el('div', 'b-bottle-corner')
  corner.append(panel, opener)
  stage.append(corner)

  const $ = (sel) => panel.querySelector(sel)
  const form = $('.bt-write'), sent = $('.bt-sent'), words = $('textarea'), count = $('.count'), hint = $('.bt-hint')
  const send = $('.bt-send'), signIn = $('.bt-signin'), attach = $('.bt-attach input'), factsShown = $('.facts')
  const back = $('.bt-back')
  const kinds = [...panel.querySelectorAll('input[name=bottle-kind]')]

  // The corner sits at the bottom right, unless the dock reaches it there (a narrow window, a long name, the past's
  // timeline): then it rises just above the dock, as the opener always does on a phone. Measured from the corner's own
  // place, whatever the opener's place now (its left edge is the same in both), so nothing moves to be measured.
  let raised = false
  let dockHeight = -1
  function place() {
    if (dock.offsetHeight !== dockHeight) corner.style.setProperty('--dock-h', `${(dockHeight = dock.offsetHeight)}px`)
    let up = false
    if (!opener.hidden && !phone()) {
      const o = opener.getBoundingClientRect(), d = dock.getBoundingClientRect(), s = stage.getBoundingClientRect()
      const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
      up = o.left < d.right + 16 && s.bottom - 1.1 * rem - o.height < d.bottom // 1.1rem: the corner's bottom edge
    }
    if (up !== raised) corner.classList.toggle('raised', (raised = up))
  }
  let placing = 0
  if (typeof ResizeObserver === 'function') new ResizeObserver(place).observe(dock)
  addEventListener('resize', () => {
    placing ||= requestAnimationFrame(() => {
      placing = 0
      place()
    })
  })

  const kind = () => kinds.find((k) => k.checked).value
  function keep() {
    store.set(DRAFT, JSON.stringify({ kind: kind(), text: words.value, owner }))
  }
  function pick(id) {
    for (const k of kinds) {
      k.checked = k.value === id
      k.parentElement.classList.toggle('on', k.checked) // the chosen tile, drawn without :has()
    }
    words.placeholder = KINDS.find((k) => k.id === id).ask
  }
  function counted() {
    // In UTF-16 units, as maxlength counts them: an emoji is two, so the counter fills when the box stops taking more.
    const n = words.value.length
    count.textContent = `${n.toLocaleString('en')}/${LIMIT.toLocaleString('en')}`
    count.classList.toggle('full', n >= LIMIT)
  }
  function say(text, tone = '') {
    hint.textContent = text
    hint.className = `bt-hint ${tone}`
  }
  function greet() {
    if (account?.signedIn) say(`It goes from your account, ${account.username}.`)
    else say('Sign in to send it. Your words wait here meanwhile.')
  }
  pick(KINDS.some((k) => k.id === draft.kind) ? draft.kind : 'bug')
  words.value = typeof draft.text === 'string' ? draft.text : ''
  counted()

  function drawFacts() {
    factsShown.textContent = factsLine(facts())
  }
  function signInHref() {
    const next = new URL(location.href) // the moment watched (?t=) comes back too
    next.searchParams.set(BACK, '1')
    return `${account.signIn}?next=${encodeURIComponent(next.pathname + next.search)}`
  }

  function show(on) {
    if (on === open) return
    open = on
    panel.hidden = !on
    opener.setAttribute('aria-expanded', String(on))
    stage.classList.toggle('bottle-open', on)
    if (!on) return
    onOpen?.() // the aim and the note give way, as they do to each other (viewer.js)
    if (unseen) unseen = false
    else if (!sent.hidden) writeAgain()
    drawFacts()
    if (!form.hidden) greet()
    // On a phone, the keyboard would take half the screen before the viewer has read what this is.
    if (phone()) panel.focus()
    else (form.hidden ? back : words).focus()
  }
  // Closed by Escape or its own buttons, focus goes back to the opener; closed because another part opened, it stays.
  function close({ focus = true } = {}) {
    if (!open) return
    show(false)
    if (focus) opener.focus()
  }
  function writeAgain() {
    sent.hidden = true
    form.hidden = false
    greet()
  }

  opener.addEventListener('click', () => show(!open))
  $('.bt-close').addEventListener('click', () => close())
  back.addEventListener('click', () => close())
  $('.bt-again').addEventListener('click', () => {
    writeAgain()
    words.focus()
  })
  for (const k of kinds) k.addEventListener('change', () => {
    pick(k.value)
    keep()
  })
  words.addEventListener('input', () => {
    counted()
    keep()
    if (hint.classList.contains('no')) greet() // a refusal is about the words as they were
  })
  words.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { // Enter alone starts a new line: bug reports run long
      e.preventDefault()
      form.requestSubmit()
    }
  })
  form.addEventListener('keydown', (e) => {
    // Enter on a kind or on the checkbox would send the form there and then (implicit submission): there it only
    // means "this one".
    if (e.key === 'Enter' && e.target.matches?.('input[type=radio], input[type=checkbox]')) e.preventDefault()
  })
  signIn.addEventListener('click', () => { signIn.href = signInHref() })

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    if (!account?.signedIn || send.disabled) return
    if ([...words.value.trim()].length < MIN) {
      say('Write a few words first.', 'no')
      return words.focus()
    }
    send.disabled = true
    send.textContent = 'Corking…'
    words.readOnly = true // what is on its way is what is in the box: nothing typed meanwhile is lost
    drawFacts() // what the line says is what goes
    const answer = await post('api/feedback', { kind: kind(), text: words.value, screen: attach.checked ? facts() : null })
    send.disabled = false
    send.textContent = 'Cork and send'
    words.readOnly = false
    if (!answer.ok) return say(answer.text || 'The bottle did not get away. Try again in a moment.', 'no')
    words.value = ''
    counted()
    keep()
    form.hidden = true
    sent.hidden = false // out of display:none, the drift plays from the start
    if (open) back.focus()
    else unseen = true
  })

  return {
    get open() { return open },
    close,
    // The viewer's account, every time the screen hears the site: the bottle shows only behind it.
    draw(a) {
      const was = account ? `${account.signedIn}:${account.username || ''}` : null
      account = a
      if (opener.hidden !== !account) {
        opener.hidden = !account
        place()
      }
      if (!account) return close({ focus: false })
      const now = `${account.signedIn}:${account.username || ''}`
      if (now !== was) {
        // The words wait for whoever wrote them: kept through signing in, gone when another account, or nobody,
        // comes to this browser.
        const me = account.signedIn ? account.username : ''
        if (owner && owner !== me) {
          words.value = ''
          counted()
        }
        if (owner !== me) {
          owner = me
          keep()
        }
        send.hidden = !account.signedIn
        signIn.hidden = account.signedIn
        if (!account.signedIn) signIn.href = signInHref()
        if (open && !form.hidden) greet()
      }
      if (reopen && account.signedIn) {
        reopen = false
        show(true)
      }
      if (open) drawFacts()
    },
  }
}
