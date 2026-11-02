import * as THREE from 'three'

// An earthquake's camera shake: the Clock's Quake, 0 (calm) to 1. The camera is nudged only for the frame being
// drawn and put back right after, so the camera's own following never sees the shake. The nudge is smooth (sines at
// unrelated rates, quicker as the quake grows): a tremor, not a glitch. It is smaller on weaker tiers and when the
// viewer's system asks for reduced motion. The server's capture gets none: its single frames are what Godling sees,
// and the mind reads the quake from the Clock rather than from a blurred view.

const MOVE = 0.4 // world units at full strength
const TURN = 0.015 // radians at full strength

export function createCameraShake(tier) {
  let reduced = false
  try {
    reduced = Boolean(globalThis.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches)
  } catch {}
  const scale = tier.capture ? 0 : (tier.shake ?? 1) * (reduced ? 0.25 : 1)
  const savedPosition = new THREE.Vector3()
  const savedQuaternion = new THREE.Quaternion()
  const turn = new THREE.Euler()
  const nudge = new THREE.Quaternion()
  let applied = false

  return {
    // Right before drawing. quake: 0..1; time: seconds.
    apply(camera, quake, time) {
      const k = quake * scale
      applied = k > 0.002
      if (!applied) return
      savedPosition.copy(camera.position)
      savedQuaternion.copy(camera.quaternion)
      const rate = 7 + 9 * quake
      const wobble = (a, b) => 0.6 * Math.sin(time * rate * a + b) + 0.4 * Math.sin(time * rate * a * 2.3 + b * 1.7)
      camera.position.x += wobble(1.0, 0.0) * MOVE * k
      camera.position.y += wobble(1.21, 1.7) * MOVE * k * 0.6
      camera.position.z += wobble(0.87, 3.1) * MOVE * k
      turn.set(wobble(1.13, 4.2) * TURN * k, wobble(0.93, 5.3) * TURN * k * 0.5, wobble(1.05, 2.2) * TURN * k)
      camera.quaternion.multiply(nudge.setFromEuler(turn))
      camera.updateMatrixWorld()
    },
    // Right after drawing.
    restore(camera) {
      if (!applied) return
      camera.position.copy(savedPosition)
      camera.quaternion.copy(savedQuaternion)
      camera.updateMatrixWorld()
      applied = false
    },
  }
}
