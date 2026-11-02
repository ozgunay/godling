// The free camera: fly over the island with W A S D along where the camera looks, Q and E (or Space) down and up,
// Shift to hurry; drag to look around, the wheel or a pinch to move along the view. It replaces the upstream spectator
// controls, whose keys pan along fixed map axes, never climb, and never reach the page inside the viewer's frame
// (the viewer screen forwards its keys here instead, see world/viewer/viewer.js).

const FLY = {
  KeyW: [0, 0, 1], ArrowUp: [0, 0, 1], KeyS: [0, 0, -1], ArrowDown: [0, 0, -1],
  KeyA: [-1, 0, 0], ArrowLeft: [-1, 0, 0], KeyD: [1, 0, 0], ArrowRight: [1, 0, 0],
  KeyE: [0, 1, 0], Space: [0, 1, 0], KeyQ: [0, -1, 0],
}
const SPEED = 16 // units per second; Shift triples it
const HURRY = 3
const SMOOTHING = 9 // how quickly the camera reaches the speed the keys ask for (per second)
const LOOK = 0.0042 // radians per pixel dragged
const DOLLY = 0.02 // units per wheel unit
const PITCH_LIMIT = 1.45
const LOWEST = 1.2 // above the sea
const HIGHEST = 160
const REACH = 600 // how far from the middle of the island the camera may go

export function createFreeCamera(THREE, camera, canvas) {
  const keys = new Set()
  const velocity = new THREE.Vector3()
  const wish = new THREE.Vector3()
  const forward = new THREE.Vector3()
  const right = new THREE.Vector3()
  const euler = new THREE.Euler(0, 0, 0, 'YXZ')
  let active = false
  let yaw = 0
  let pitch = -0.5
  let drag = null
  const touches = new Map()
  let pinch = 0

  const key = (code, down) => {
    if (code === 'all') return keys.clear()
    if (!(code in FLY) && code !== 'ShiftLeft' && code !== 'ShiftRight') return
    if (down) keys.add(code)
    else keys.delete(code)
  }
  const typing = (target) => target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target?.isContentEditable
  addEventListener('keydown', (e) => {
    if (!active || typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return
    if (e.code in FLY || e.code.startsWith('Shift')) {
      key(e.code, true)
      e.preventDefault()
      e.stopImmediatePropagation()
    }
  }, true)
  addEventListener('keyup', (e) => key(e.code, false), true)
  addEventListener('blur', () => keys.clear())

  const look = (dx, dy) => {
    yaw -= dx * LOOK
    pitch = Math.max(-PITCH_LIMIT, Math.min(PITCH_LIMIT, pitch - dy * LOOK))
  }
  const dolly = (amount) => {
    camera.getWorldDirection(forward)
    camera.position.addScaledVector(forward, amount)
  }
  canvas.addEventListener('pointerdown', (e) => {
    if (!active) return
    if (e.pointerType === 'touch') {
      touches.set(e.pointerId, [e.clientX, e.clientY])
      if (touches.size === 2) pinch = spread()
      return
    }
    drag = { id: e.pointerId, x: e.clientX, y: e.clientY }
    try { canvas.setPointerCapture(e.pointerId) } catch { /* not ours to capture */ }
  }, true)
  canvas.addEventListener('pointermove', (e) => {
    if (!active) return
    if (e.pointerType === 'touch' && touches.has(e.pointerId)) {
      const [x, y] = touches.get(e.pointerId)
      touches.set(e.pointerId, [e.clientX, e.clientY])
      if (touches.size === 1) look(e.clientX - x, e.clientY - y)
      else if (touches.size === 2) {
        const now = spread()
        dolly((now - pinch) * 0.08)
        pinch = now
      }
      e.preventDefault()
      return
    }
    if (!drag || drag.id !== e.pointerId) return
    look(e.clientX - drag.x, e.clientY - drag.y)
    drag.x = e.clientX
    drag.y = e.clientY
  }, true)
  const end = (e) => {
    touches.delete(e.pointerId)
    if (drag?.id === e.pointerId) drag = null
  }
  canvas.addEventListener('pointerup', end, true)
  canvas.addEventListener('pointercancel', end, true)
  canvas.addEventListener('wheel', (e) => {
    if (!active) return
    dolly(-e.deltaY * DOLLY * (keys.has('ShiftLeft') || keys.has('ShiftRight') ? HURRY : 1))
    e.preventDefault()
  }, { passive: false, capture: true })
  function spread() {
    const [a, b] = [...touches.values()]
    return Math.hypot(a[0] - b[0], a[1] - b[1])
  }

  return {
    get active() { return active },
    key,
    // Takes over from wherever the camera is, so switching modes never jumps; `target` places a camera that has
    // never been placed (at the start, with nobody to follow) above and behind it.
    enter(target) {
      if (active) return
      active = true
      velocity.set(0, 0, 0)
      if (camera.position.lengthSq() < 1 && target) {
        camera.position.set(target.x, target.y + 18, target.z - 18)
        camera.lookAt(target)
      }
      euler.setFromQuaternion(camera.quaternion, 'YXZ')
      yaw = euler.y
      pitch = Math.max(-PITCH_LIMIT, Math.min(PITCH_LIMIT, euler.x))
    },
    leave() {
      active = false
      keys.clear()
      drag = null
      touches.clear()
    },
    update(dt) {
      if (!active) return
      wish.set(0, 0, 0)
      for (const code of keys) {
        const d = FLY[code]
        if (d) wish.x += d[0], wish.y += d[1], wish.z += d[2]
      }
      if (wish.lengthSq() > 1) wish.normalize()
      const speed = SPEED * (keys.has('ShiftLeft') || keys.has('ShiftRight') ? HURRY : 1)
      forward.set(-Math.sin(yaw), 0, -Math.cos(yaw)) // along the ground, where the camera looks
      right.set(Math.cos(yaw), 0, -Math.sin(yaw))
      const target = new THREE.Vector3()
        .addScaledVector(forward, wish.z * speed)
        .addScaledVector(right, wish.x * speed)
      target.y = wish.y * speed
      velocity.lerp(target, 1 - Math.exp(-SMOOTHING * dt))
      camera.position.addScaledVector(velocity, dt)
      camera.position.y = Math.max(LOWEST, Math.min(HIGHEST, camera.position.y))
      const out = Math.hypot(camera.position.x, camera.position.z)
      if (out > REACH) {
        camera.position.x *= REACH / out
        camera.position.z *= REACH / out
      }
      euler.set(pitch, yaw, 0, 'YXZ')
      camera.quaternion.setFromEuler(euler)
    },
  }
}
