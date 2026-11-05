import { describe, expect, it } from 'vitest'
import { HOLD, boxOf, createCutaway, crosses } from '../src/cutaway.js'

// A hut round a body standing at the origin (its middle 2.5 up): a log roof over its head, a wall block between it
// and the camera, a block behind it, the block it stands beside on the ground, and a tower far off on the camera's line.
const body = (sheltered) => ({ position: [0, 2.5, 0], sheltered })
const camera = [0, 14, 14] // above and behind, as the follow camera is
const roof = { id: 1, position: [0, 8.75, 0], size: [7.5, 2.5, 2.5], rotation: null }
const wall = { id: 2, position: [0, 3.75, 2.5], size: [2.5, 2.5, 2.5], rotation: null }
const behind = { id: 3, position: [0, 3.75, -2.5], size: [2.5, 2.5, 2.5], rotation: null }
const floor = { id: 4, position: [0, -1.25, 0], size: [2.5, 2.5, 2.5], rotation: null } // under its feet
const far = { id: 5, position: [0, 20, 30], size: [2.5, 2.5, 2.5], rotation: null }
const pieces = [roof, wall, behind, floor, far]

describe('cutaway', () => {
  it('measures a turned piece by its turned box', () => {
    const quarter = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]] // a log turned a quarter round: its length along z
    expect(boxOf({ position: [0, 8.75, 0], size: [7.5, 2.5, 2.5], rotation: quarter })).toEqual({
      min: [-1.25, 7.5, -3.75], max: [1.25, 10, 3.75] })
  })

  it('finds the pieces a line passes through, not those it only grazes', () => {
    const box = { min: [-1, -1, -1], max: [1, 1, 1] }
    expect(crosses([0, 0, -5], [0, 0, 5], box)).toBe(true)
    expect(crosses([0, 0, -5], [0, 0, -2], box)).toBe(false) // stops short
    expect(crosses([1, 0, -5], [1, 0, 5], box)).toBe(false) // along its face
    expect(crosses([3, 0, -5], [3, 0, 5], box)).toBe(false)
  })

  it('takes the roof off while the body shelters, and what stands between it and the camera', () => {
    const cutaway = createCutaway()
    const out = cutaway.update({ body: body(true), camera, pieces, dt: 0.05 })
    expect([...out.hidden].sort()).toEqual([1, 2]) // not behind it, not its floor, not the tower far off
    expect(out.restored).toEqual([])
    // Out from under it, the roof is still drawn where it does not hide the body.
    const open = createCutaway().update({ body: body(false), camera: [14, 4, 0], pieces, dt: 0.05 })
    expect([...open.hidden]).toEqual([])
  })

  it('draws a piece again a little while after it stops being in the way', () => {
    const cutaway = createCutaway()
    cutaway.update({ body: body(true), camera, pieces, dt: 0.05 })
    let out = cutaway.update({ body: null, camera, pieces, dt: HOLD / 2 }) // a free camera: nobody followed
    expect([...out.hidden].sort()).toEqual([1, 2])
    out = cutaway.update({ body: null, camera, pieces, dt: HOLD })
    expect(out.hidden.size).toBe(0)
    expect(out.restored.sort()).toEqual([1, 2])
    cutaway.update({ body: body(true), camera, pieces, dt: 0.05 })
    expect(cutaway.clear().sort()).toEqual([1, 2])
    expect(cutaway.hidden()).toEqual([])
  })
})
