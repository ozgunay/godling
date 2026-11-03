import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createHands, GRAB_SECONDS, IN_HAND } from '../src/hands.js'

// The bodies' grips stand in for models.js: body id -> the grip's matrix in the world.
function setup() {
  const grips = new Map()
  const hands = createHands({ grip: (id, out) => (grips.has(id) ? out.copy(grips.get(id)) : null) })
  return { grips, hands }
}
const axe = { id: 5, kind: 'Axe', size: [0.4, 0.4, 1.0] }
const served = new THREE.Matrix4().makeTranslation(10, 0.2, -3) // lying on the grass
const at = (m, x, y, z) => new THREE.Vector3(x, y, z).applyMatrix4(m)
const near = (a, b) => a.distanceTo(b) < 1e-6

describe('a tool in the hand', () => {
  it('closes the fist on its handle, the head beyond the thumb, dipped towards the fingers', () => {
    const { grips, hands } = setup()
    const out = new THREE.Matrix4()
    const fit = IN_HAND.Axe
    const handle = [0, fit.up * axe.size[1], fit.along * axe.size[2]] // where the fist closes, on the part
    const dip = THREE.MathUtils.degToRad(fit.dip)
    // A hand at (1, 2, 3), level: the thumb along X, the fingers along Y.
    grips.set(7, new THREE.Matrix4().makeTranslation(1, 2, 3))
    expect(hands.place(axe, 7, served, GRAB_SECONDS, out)).toBe(true)
    expect(near(at(out, ...handle), new THREE.Vector3(1, 2, 3))).toBe(true)
    const head = at(out, 0, 0, -0.5).sub(at(out, 0, 0, 0.5)).normalize()
    expect(near(head, new THREE.Vector3(Math.cos(dip), Math.sin(dip), 0))).toBe(true)
    const edge = at(out, 0, 1, 0).sub(at(out, 0, 0, 0)) // the blade, the way the knuckles point
    expect(near(edge, new THREE.Vector3(-Math.sin(dip), Math.cos(dip), 0))).toBe(true)
    // The hand turns (a clip): the tool turns with it, its grip still in the fist.
    grips.set(7, new THREE.Matrix4().makeRotationY(Math.PI / 2).setPosition(-4, 1, 0))
    hands.place(axe, 7, served, 1 / 60, out)
    expect(near(at(out, ...handle), new THREE.Vector3(-4, 1, 0))).toBe(true)
    const turned = at(out, 0, 0, -0.5).sub(at(out, 0, 0, 0.5)).normalize()
    expect(near(turned, new THREE.Vector3(0, Math.sin(dip), -Math.cos(dip)))).toBe(true)
    const middle = at(out, 0, 0, 0).toArray().map((v) => Number(v.toFixed(2))) // where the part's middle is drawn
    expect(hands.info()).toEqual([{ id: 5, body: 7, weight: 1, at: middle }])
  })

  it('eases from where the world has it into the hand, and back out once let go', () => {
    const { grips, hands } = setup()
    const out = new THREE.Matrix4()
    grips.set(7, new THREE.Matrix4().makeTranslation(0, 1.5, 0))
    const inHand = new THREE.Matrix4()
    hands.place(axe, 7, served, GRAB_SECONDS, inHand) // where it ends up
    hands.clear()
    expect(hands.place(axe, 7, served, 0, out)).toBe(true) // just picked up: still where it lay
    expect(near(at(out, 0, 0, 0), at(served, 0, 0, 0))).toBe(true)
    hands.place(axe, 7, served, GRAB_SECONDS / 2, out) // half way in time, and smoothly so half way between
    const half = at(served, 0, 0, 0).lerp(at(inHand, 0, 0, 0), 0.5)
    expect(near(at(out, 0, 0, 0), half)).toBe(true)
    hands.place(axe, 7, served, GRAB_SECONDS, out)
    expect(out.equals(inHand)).toBe(true)
    // Let go (no holder now): out of the hand towards where the world sets it down, then the world's alone.
    expect(hands.place(axe, null, served, GRAB_SECONDS / 4, out)).toBe(true)
    expect(at(out, 0, 0, 0).distanceTo(at(inHand, 0, 0, 0))).toBeGreaterThan(0.01)
    expect(hands.has(5)).toBe(true)
    expect(hands.place(axe, null, served, GRAB_SECONDS, out)).toBe(false)
    expect(hands.has(5)).toBe(false)
    expect(hands.place(axe, null, served, 0.1, out)).toBe(false) // a tool nobody holds
  })

  it('leaves it to the world when no hand can take it', () => {
    const { grips, hands } = setup()
    const out = new THREE.Matrix4()
    grips.set(7, new THREE.Matrix4())
    grips.set(8, new THREE.Matrix4().makeTranslation(5, 0, 0))
    expect(hands.place({ id: 6, kind: 'Ladder', size: [1, 7, 0.3] }, 7, served, 0.1, out)).toBe(false) // not a tool
    expect(hands.place({ id: 9, kind: 'Spear' }, 3, served, 0.1, out)).toBe(false) // a body not drawn, or without a hand
    expect(hands.has(9)).toBe(false)
    hands.place({ id: 9, kind: 'Spear' }, 7, served, GRAB_SECONDS, out) // no size: a unit part
    hands.place({ id: 9, kind: 'Spear' }, 8, served, 0.1, out) // passed to another body: it starts over
    expect(hands.info()[0]).toMatchObject({ id: 9, body: 8, weight: 0.25 })
    hands.place(axe, 7, served, 0.1, out)
    hands.prune(new Set([5])) // the spear is gone from the island
    expect(hands.info().map((h) => h.id)).toEqual([5])
  })
})
