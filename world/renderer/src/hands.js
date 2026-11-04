import * as THREE from 'three'

// A tool in Godling's hand. The world carries a held piece over the body's head (main.lua HOLD_OFFSET), where the
// mind looks for what it holds, and names the holder in the piece's "HeldBy". The world has no hands: they are the
// model's, posed here by its clips. So a held tool is drawn on the holder's right hand bone instead (models.js grip),
// as games attach a held item to a hand: it goes where the hand goes as the body walks, idles and works. Picked up,
// it eases from where the world has it into the hand; let go, back out to where the world puts it down.
//
// How each tool sits in the fist. Every tool's part runs along Z, its head at -Z (art/README.md): the handle passes
// through the fist from the little finger to the thumb, the head beyond the thumb and its edge or face (the part's
// +Y) the way the knuckles point, so a swing leads with it. along: where the fist closes, as a share of the part's
// length back from its middle towards the butt (the axe's and hammer's coral grips); up: the handle's height off
// the part's middle, as a share of its height (the axe's blade rises above the handle); dip: degrees the head
// turns down towards the fingers, as a relaxed wrist lets it.
// The spear is held a little ahead of its middle and dipped well down. The art pipeline poses Godling for these dips
// (art/build_godling.py SPEAR_DIP and TOOL_DIP): the carry clips (IdleCarry, WalkCarry) turn the fist so a carried
// spear points just above level, and the Spear clip's hand is turned so the thrust is level. Change a dip here and
// godling.glb must be rebuilt with the build's dip changed to match (a test checks they agree).
export const IN_HAND = {
  Axe: { along: 0.4, up: -0.21, dip: 20 },
  Hammer: { along: 0.39, up: 0, dip: 20 },
  Spear: { along: -0.1, up: 0, dip: 55 },
}
export const GRAB_SECONDS = 0.4 // into the hand, or back out

export function createHands(characters) {
  const holds = new Map() // part id -> { body, weight }: in a hand (weight 1), or on its way in or out
  const grip = new THREE.Matrix4()
  const local = new THREE.Matrix4()
  const turn = new THREE.Matrix4()
  const from = { at: new THREE.Vector3(), turn: new THREE.Quaternion() }
  const to = { at: new THREE.Vector3(), turn: new THREE.Quaternion() }
  const scale = new THREE.Vector3()

  // The part's place in the grip's frame: the grip point on its handle at the origin, the head along +X.
  function inHand(fit, size, out) {
    out.makeTranslation(0, -fit.up * size[1], -fit.along * size[2])
    out.premultiply(turn.makeRotationY(-Math.PI / 2)) // the part's -Z (its head) to the thumb, +X
    return out.premultiply(turn.makeRotationZ(THREE.MathUtils.degToRad(fit.dip)))
  }

  return {
    // Whether the part is in a hand, or on its way in or out: if so, place() it every frame.
    has: (id) => holds.has(id),
    // Where to draw a tool this frame, into `out`: `served` (where the world has it) eased towards the hand of the body
    // `bodyId` that holds it (null: nobody, or a body not drawn). False when no hand has anything to do with it: draw it
    // as served.
    place({ id, kind, size }, bodyId, served, dt, out) {
      const fit = IN_HAND[kind]
      let hold = fit ? holds.get(id) : null
      if (fit && bodyId != null) {
        if (hold?.body !== bodyId) hold = { body: bodyId, weight: 0, at: new THREE.Vector3() }
        hold.weight = Math.min(1, hold.weight + dt / GRAB_SECONDS)
        holds.set(id, hold)
      } else if (hold) {
        hold.weight -= dt / GRAB_SECONDS
        if (hold.weight <= 0) hold = null // back where the world has it
      }
      if (!hold || !characters.grip(hold.body, grip)) {
        holds.delete(id)
        return false
      }
      out.multiplyMatrices(grip, inHand(fit, size || [1, 1, 1], local))
      if (hold.weight < 1) {
        const t = hold.weight * hold.weight * (3 - 2 * hold.weight) // smooth at both ends
        served.decompose(from.at, from.turn, scale)
        out.decompose(to.at, to.turn, scale)
        out.compose(from.at.lerp(to.at, t), from.turn.slerp(to.turn, t), scale.set(1, 1, 1))
      }
      hold.at.setFromMatrixPosition(out)
      return true
    },
    prune(activeIds) {
      for (const id of holds.keys()) if (!activeIds.has(id)) holds.delete(id)
    },
    clear: () => holds.clear(),
    // For checks: each tool in a hand, or on its way, how far in, and where it was last drawn.
    info: () => [...holds.entries()].map(([id, hold]) => ({
      id, body: hold.body, weight: Number(hold.weight.toFixed(2)), at: hold.at.toArray().map((v) => Number(v.toFixed(2))),
    })),
  }
}
