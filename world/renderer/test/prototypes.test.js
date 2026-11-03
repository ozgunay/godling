// The three HUD prototypes the viewer screen was chosen from (world/viewer/prototypes), each at each demo moment, on a
// desktop and on a phone: they draw, and picking a slot moves its tip.
import { afterEach, describe, expect, it, vi } from 'vitest'

async function open(query, phone = false) {
  vi.resetModules()
  history.replaceState(null, '', `/?${query}`)
  document.body.innerHTML = '<main id="stage"></main>'
  vi.stubGlobal('matchMedia', (q) => ({ matches: q.includes('max-width') ? phone : false }))
  await import('../../viewer/prototypes/viewer.js')
  return document.getElementById('stage')
}

describe('HUD prototypes', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    history.replaceState(null, '', '/')
  })

  for (const hud of ['block', 'kit', 'sky']) {
    for (const demo of ['day', 'night', 'meteor']) {
      for (const phone of [false, true]) {
        it(`${hud} at ${demo}${phone ? ' on a phone' : ''}`, async () => {
          const stage = await open(`hud=${hud}&demo=${demo}&camera=${phone ? 'free' : 'follow'}`, phone)
          expect(stage.classList.contains(`hud-${hud}`)).toBe(true)
          expect(stage.querySelector('.island').style.backgroundImage).toContain(phone ? 'phone' : demo)
          expect(stage.textContent).toContain('Prototype · demo data')
          const slots = stage.querySelectorAll('[aria-label$="credits"]')
          expect(slots.length).toBe(9)
          slots[2].dispatchEvent(new MouseEvent('mouseenter'))
          slots[3].dispatchEvent(new FocusEvent('focus'))
          dispatchEvent(new KeyboardEvent('keydown', { key: '1' }))
          dispatchEvent(new KeyboardEvent('keydown', { key: 'x' }))
          expect(stage.querySelector('.picked')).not.toBeNull()
          const [follow, free] = stage.querySelectorAll('.camera button')
          free.click()
          expect(free.getAttribute('aria-pressed')).toBe('true')
          follow.click()
          expect(follow.getAttribute('aria-pressed')).toBe('true')
        })
      }
    }
  }

  it('falls back to the block HUD at the day moment', async () => {
    const stage = await open('hud=nothing&demo=nothing')
    expect(stage.classList.contains('hud-block')).toBe(true)
    expect(stage.querySelector('.b-clock .time').textContent).toBe('14:20')
  })
})
