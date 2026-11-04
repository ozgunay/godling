import { describe, expect, it } from 'vitest'
import { icon } from '../../viewer/icons.js'

const NAMES = ['stone', 'log', 'coconut', 'sapling', 'fish', 'lightning', 'meteor', 'rain', 'quake', 'wave', 'heart',
  'heartHalf', 'heartEmpty', 'food', 'foodHalf', 'foodEmpty', 'sun', 'moon', 'eye', 'move', 'coin', 'godling', 'sky',
  'notice', 'lock', 'drop', 'cold', 'glider', 'think', 'close', 'pause', 'play', 'idea', 'more', 'less']

describe('pixel icons', () => {
  it('draws every icon as crisp SVG, outlined, at any scale', () => {
    for (const name of NAMES) {
      const svg = icon(name, 2)
      expect(svg).toMatch(/^<svg class="px" width="\d+" height="\d+" viewBox="0 0 \d+ \d+" shape-rendering="crispEdges"/)
      expect(svg).toContain('fill="#15191b"') // the one-pixel dark outline
      expect(svg).toContain('aria-hidden="true"')
    }
    const big = icon('stone')
    expect(big).toContain('width="48"')
    expect(icon('stone')).toBe(big) // drawn once, then cached
    expect(icon('heart', 1, 'Health')).toContain('role="img" aria-label="Health"')
  })

  it('merges runs of one colour into one rect', () => {
    const svg = icon('coin', 1)
    const rects = svg.match(/<rect /g).length
    expect(rects).toBeLessThan(16 * 16)
  })
})
