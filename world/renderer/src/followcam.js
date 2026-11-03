// The follow camera: behind Godling and above it, looking the way the map runs (+Z), as the upstream follow camera
// did, but framed for the screen it is on. A camera keeps its angle from top to bottom whatever the screen's shape, so
// upstream's 60° saw only 30° across on a phone held upright, a quarter of what a desktop sees. On a wide screen this
// camera is where upstream's always was; on a tall one it opens to 75° and steps back and up, which shows about 1.7
// times as much across round Godling.
// It aims as a game camera's composer does: Godling in the middle across, at a set height on the screen. On a phone
// that is the open band between the HUD's feed at the top and its hotbar at the bottom (world/viewer/viewer.css).

const WIDE = { fov: 60, distance: 20, height: 6, screenY: 0.64 } // screenY: where Godling sits, from the top
const TALL = { fov: 75, distance: 25, height: 9.5, screenY: 0.55 }
const UPRIGHT = 0.55 // width / height: a screen this tall, or taller, is framed as TALL; in between, a blend

export function framingFor(aspect) {
  const t = Math.max(0, Math.min(1, (1 - aspect) / (1 - UPRIGHT))) || 0
  const mix = (key) => WIDE[key] + (TALL[key] - WIDE[key]) * t
  return { fov: mix('fov'), distance: mix('distance'), height: mix('height'), screenY: mix('screenY') }
}

export function createFollowCamera(THREE, camera, { positionSmoothing = 10, rotationSmoothing = 14 } = {}) {
  let framing = framingFor(Infinity)
  let placed = false
  const wanted = new THREE.Vector3()
  const toTarget = new THREE.Vector3()
  const euler = new THREE.Euler(0, 0, 0, 'YXZ')
  const aim = new THREE.Quaternion()

  return {
    // For a screen of this shape (width / height); says the framing, whose fov the renderer gives the camera.
    frame(aspect) {
      framing = framingFor(aspect)
      return framing
    },
    // Eases towards its place behind the target, and turns to put the target where the framing says; the very first
    // time it is simply there.
    update(target, dt) {
      const step = Math.max(1 / 240, Math.min(0.1, dt || 1 / 60))
      wanted.set(target.x, target.y + framing.height, target.z - framing.distance)
      if (placed) camera.position.lerp(wanted, 1 - Math.exp(-positionSmoothing * step))
      else camera.position.copy(wanted)
      toTarget.subVectors(target, camera.position)
      const elevation = Math.atan2(toTarget.y, Math.hypot(toTarget.x, toTarget.z)) // of the target, from the camera
      const offAxis = Math.atan((1 - 2 * framing.screenY) * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2))
      euler.set(elevation - offAxis, Math.atan2(-toTarget.x, -toTarget.z), 0)
      aim.setFromEuler(euler)
      if (placed) camera.quaternion.slerp(aim, 1 - Math.exp(-rotationSmoothing * step))
      else camera.quaternion.copy(aim)
      placed = true
    },
  }
}
