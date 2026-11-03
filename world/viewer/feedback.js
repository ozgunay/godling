// The bottle: while the site is in beta, viewers tell the people who make the island about a bug, a question or an
// idea (web/apps/feedback). Notes fly in to Godling as paper gliders; these drift out to the makers, and Godling never
// reads them. Only behind the accounts site, and sending needs an account (the user's choice, 2026-11-03); a signed-out
// viewer's words wait here while they sign in.

const LIMIT = 2000 // web/apps/feedback/models.py TEXT_LIMIT
const MIN = 3 // web/apps/feedback/views.py TEXT_MIN
const DRAFT = 'godling.bottle' // the words and the kind, kept until they are sent
const REOPEN = 'godling.bottle.reopen' // gone to sign in from the bottle: open it again on the way back
const KINDS = [
  { id: 'bug', name: 'Bug', icon: 'bug', ask: 'What happened, and what did you expect instead?' },
  { id: 'question', name: 'Question', icon: 'question', ask: 'Ask the makers anything about Godling or the island.' },
  { id: 'idea', name: 'Idea', icon: 'idea', ask: 'A power, a change, something you wish you could do here…' },
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

const hourText = (h) => `${String(Math.floor(h)).padStart(2, '0')}:${String(Math.floor((h % 1) * 60)).padStart(2, '0')}`
// The facts as the viewer reads them under the checkbox: exactly what will be sent, in words.
export function factsLine(f) {
  return [f.size?.replace('x', '×'), [f.browser, f.system].filter(Boolean).join(' · '),
    f.view === 'replay' ? 'the past' : f.view,
    Number.isFinite(f.hour) ? `day ${f.day || 1} ${hourText(f.hour)}` : '',
    f.camera && `${f.camera} camera`].filter(Boolean).join(' · ')
}

export function createFeedback({ stage, dock, el, text, icon, post, store, facts, phone }) {
  let account = null
  let open = false
  const draft = (() => {
    try { return JSON.parse(store.get(DRAFT) || '{}') || {} } catch { return {} }
  })()

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
      <input type="radio" name="bottle-kind" value="${k.id}">${icon(k.icon, 2)}<span>${k.name}</span></label>`).join('')}</fieldset>
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
  stage.append(panel, opener)

  const $ = (sel) => panel.querySelector(sel)
  const form = $('.bt-write'), sent = $('.bt-sent'), words = $('textarea'), count = $('.count'), hint = $('.bt-hint')
  const send = $('.bt-send'), signIn = $('.bt-signin'), attach = $('.bt-attach input'), factsShown = $('.facts')
  const kinds = [...panel.querySelectorAll('input[name=bottle-kind]')]

  // The bottle sits in the bottom-right corner, unless the dock reaches it there (a narrow window, a long name, the
  // past's timeline): then it floats just above the dock, as it always does on a phone. Measured as the dock changes,
  // and again with every word from the site in case a hidden page let a change go unobserved.
  function place() {
    stage.style.setProperty('--dock-h', `${dock.offsetHeight}px`)
    stage.classList.remove('bottle-raised')
    if (opener.hidden || phone()) return
    const o = opener.getBoundingClientRect(), d = dock.getBoundingClientRect()
    stage.classList.toggle('bottle-raised', o.left < d.right + 16 && o.top < d.bottom)
  }
  if (typeof ResizeObserver === 'function') new ResizeObserver(place).observe(dock)
  addEventListener('resize', place)

  const kind = () => kinds.find((k) => k.checked)?.value || 'bug'
  function keep() {
    store.set(DRAFT, JSON.stringify({ kind: kind(), text: words.value }))
  }
  function pick(id) {
    for (const k of kinds) k.checked = k.value === id
    words.placeholder = KINDS.find((k) => k.id === id).ask
  }
  function counted() {
    const n = [...words.value].length
    count.textContent = `${n.toLocaleString('en')}/${LIMIT.toLocaleString('en')}`
    count.classList.toggle('full', n >= LIMIT)
  }
  function say(words, tone = '') {
    hint.textContent = words
    hint.className = `bt-hint ${tone}`
  }
  function greet() {
    if (account?.signedIn) say(`Sent from your account, ${account.username}.`)
    else say('Sign in to send it. Your words wait here meanwhile.')
  }
  pick(KINDS.some((k) => k.id === draft.kind) ? draft.kind : 'bug')
  words.value = typeof draft.text === 'string' ? draft.text.slice(0, LIMIT) : ''
  counted()

  function drawFacts() {
    factsShown.textContent = factsLine(facts())
  }

  function show(on = !open) {
    if (on === open) return
    open = on
    panel.hidden = !on
    opener.setAttribute('aria-expanded', String(on))
    stage.classList.toggle('bottle-open', on)
    if (!on) return
    if (!sent.hidden) writeAgain()
    drawFacts()
    greet()
    // On a phone, the keyboard would take half the screen before the viewer has read what this is.
    if (phone()) panel.focus()
    else words.focus()
  }
  function close() {
    if (!open) return
    show(false)
    opener.focus()
  }
  function writeAgain() {
    sent.hidden = true
    form.hidden = false
    greet()
  }

  opener.addEventListener('click', () => show())
  $('.bt-close').addEventListener('click', close)
  $('.bt-back').addEventListener('click', close)
  $('.bt-again').addEventListener('click', () => {
    writeAgain()
    words.focus()
  })
  panel.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return
    e.stopPropagation() // the screen's own Escape would close the note composer too
    close()
  })
  for (const k of kinds) k.addEventListener('change', () => {
    pick(k.value)
    keep()
  })
  words.addEventListener('input', () => {
    counted()
    keep()
  })
  words.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { // Enter alone starts a new line: bug reports run long
      e.preventDefault()
      form.requestSubmit()
    }
  })
  signIn.addEventListener('click', () => store.set(REOPEN, '1'))

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    if (!account?.signedIn || send.disabled) return
    if ([...words.value.trim()].length < MIN) {
      say('Write a few words first.', 'no')
      return words.focus()
    }
    send.disabled = true
    send.textContent = 'Corking…'
    drawFacts() // what the line says is what goes
    const answer = await post('api/feedback', { kind: kind(), text: words.value, screen: attach.checked ? facts() : null })
    send.disabled = false
    send.textContent = 'Cork and send'
    if (!answer.ok) return say(answer.text || 'The bottle did not get away. Try again in a moment.', 'no')
    words.value = ''
    counted()
    store.set(DRAFT, JSON.stringify({ kind: kind(), text: '' }))
    form.hidden = true
    sent.hidden = false
    // The drift plays again for every bottle.
    const drift = $('.bt-drift')
    drift.replaceWith(drift.cloneNode(true))
    $('.bt-back').focus()
  })

  return {
    get open() { return open },
    close,
    // The viewer's account, every time the screen hears the site: the bottle shows only behind it.
    draw(a) {
      const was = account ? `${account.signedIn}:${account.username || ''}` : ''
      account = a
      opener.hidden = !account
      if (!account) return show(false)
      place()
      const now = `${account.signedIn}:${account.username || ''}`
      if (now !== was) {
        send.hidden = !account.signedIn
        signIn.hidden = account.signedIn
        signIn.href = `${account.signIn}?next=${encodeURIComponent('/')}`
        if (open) greet()
      }
      if (account.signedIn && store.get(REOPEN)) {
        store.set(REOPEN, '')
        show(true)
      }
      if (open) drawFacts()
    },
  }
}
