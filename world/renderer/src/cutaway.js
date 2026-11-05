// The roof off, as The Sims takes it: the pieces of a building near the body the camera follows (with the free camera,
// near Godling) that would hide it from the camera are left out of the picture. Without this, Godling sheltering in its
// hut was a roof with nobody under it: building pieces are drawn solid, and the follow camera looks down from above
// and behind. Viewers can turn it off (index.js: the screen's "See inside", or ?cutaway=off).
// - Overhead: while the world says the body is sheltered (its "Sheltered" attribute, main.lua shelterOf), every
//   building piece over its head close by, so the whole roof comes off, not a patch of it.
// - In the way: any building piece close by that crosses the line from the camera to the body, a wall in front of it.
// Only pieces within NEAR of the body count: its hut, not a tower across the beach the camera happens to look past.
// A piece stays out for HOLD seconds after it stops being in the way, so the follow camera's sway never makes it
// flicker. Godling's own eyes (the first-person capture) see their roof.

export const CUTAWAY_ROLES = new Set(['PickupObject', 'Stone', 'Log', 'Brick', 'Boulder', 'Meteor'])
export const NEAR = 8 // world units from the body to a piece's nearest side
export const HOLD = 0.4 // seconds
const BODY_HALF = 2.5 // the body is 5 tall, its position at its middle
const GRAZE = 0.05 // a line that only grazes a piece's face does not hide anything behind it

// A piece's box in the world: its size turned by its rotation's rows (or none), around its position.
export function boxOf({ position, size, rotation }) {
  const half = [0, 1, 2].map((i) => (rotation
    ? rotation[i].reduce((sum, r, j) => sum + Math.abs(r) * size[j] / 2, 0)
    : size[i] / 2))
  return { min: position.map((v, i) => v - half[i]), max: position.map((v, i) => v + half[i]) }
}

// Whether the segment from a to b passes through the box (slab test, the box shrunk by GRAZE).
export function crosses(a, b, box) {
  let enter = 0
  let leave = 1
  for (let i = 0; i < 3; i++) {
    const lo = box.min[i] + GRAZE
    const hi = box.max[i] - GRAZE
    const d = b[i] - a[i]
    if (Math.abs(d) < 1e-9) {
      if (a[i] < lo || a[i] > hi) return false
      continue
    }
    let t1 = (lo - a[i]) / d
    let t2 = (hi - a[i]) / d
    if (t1 > t2) [t1, t2] = [t2, t1]
    enter = Math.max(enter, t1)
    leave = Math.min(leave, t2)
    if (enter > leave) return false
  }
  return true
}

export function createCutaway({ near = NEAR, hold = HOLD } = {}) {
  const left = new Map() // piece id -> seconds it stays out

  // Which pieces stay out of the picture this frame. `body`: {position, sheltered} of the body to keep in sight, or
  // null (Godling's own eyes, turned off, nobody); `camera`: [x, y, z]; `pieces`: [{id, position, size, rotation}]
  // of the building pieces drawn now. Returns {hidden: Set of ids, restored: [ids to draw again]}.
  function update({ body, camera, pieces, dt }) {
    const now = new Set()
    if (body) {
      const [bx, by, bz] = body.position
      const head = by + BODY_HALF
      const feet = by - BODY_HALF
      const sight = [[bx, by + 1.5, bz], [bx, by, bz]] // its face and its middle
      for (const piece of pieces) {
        if (!piece.size) continue
        const box = boxOf(piece)
        const dx = Math.max(box.min[0] - bx, 0, bx - box.max[0])
        const dz = Math.max(box.min[2] - bz, 0, bz - box.max[2])
        if (Math.hypot(dx, dz) > near || box.max[1] <= feet + 0.3) continue // far off, or what it stands on
        const overhead = body.sheltered && box.min[1] >= head - 0.3
        if (overhead || sight.some((eye) => crosses(camera, eye, box))) now.add(piece.id)
      }
    }
    const restored = []
    for (const id of now) left.set(id, hold)
    for (const [id, seconds] of left) {
      if (now.has(id)) continue
      if (seconds - dt <= 0) {
        left.delete(id)
        restored.push(id)
      } else {
        left.set(id, seconds - dt)
      }
    }
    return { hidden: new Set(left.keys()), restored }
  }

  return {
    update,
    // Everything back in the picture (the island cleared): the ids to draw again.
    clear() {
      const all = [...left.keys()]
      left.clear()
      return all
    },
    hidden: () => [...left.keys()],
  }
}
