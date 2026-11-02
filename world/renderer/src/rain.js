import * as THREE from 'three'

// Rain (ADR-010): the world's Clock carries Rain, 0 (dry) to 1 (pouring). Streaks fall in a box that travels with
// the camera, more of them and more opaque the harder it rains. As in games, each streak is stretched along its
// velocity: the wind (wind.js) pushes the drops sideways, so in a storm the rain drives in at a slant. The rest of the
// look (a greyer sky, dimmer light, heavier clouds) is applied by index.js from the same number.

const BOX = { x: 70, y: 36, z: 70 }
const FALL_SPEED = 34 // units per second
const WIND_PUSH = 26 // sideways speed of the drops in a full gale, units per second
const STREAK = 0.085 // a streak's length, in seconds of its fall: faster drops draw longer streaks

export function createRain(scene, tier) {
  const count = tier.name === 'low' ? 2500 : tier.name === 'medium' ? 4500 : 7000
  const positions = new Float32Array(count * 6)
  const drops = new Float32Array(count * 3) // each drop's place in the box
  for (let i = 0; i < count; i++) {
    drops[i * 3] = Math.random() * BOX.x
    drops[i * 3 + 1] = Math.random() * BOX.y
    drops[i * 3 + 2] = Math.random() * BOX.z
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  const material = new THREE.LineBasicMaterial({ color: 0xe8eff6, transparent: true, opacity: 0, depthWrite: false, fog: true })
  const lines = new THREE.LineSegments(geometry, material)
  lines.frustumCulled = false
  lines.visible = false
  scene.add(lines)
  let last = 0

  return {
    // rain: 0..1 from the world; time: seconds; camera: where the box goes; wind: the wind blowing now (x, y = z).
    update({ rain, time, camera, wind }) {
      lines.visible = rain > 0.02
      if (!lines.visible) return
      const dt = Math.min(0.1, Math.max(0, time - last))
      last = time
      material.opacity = 0.3 + 0.45 * rain
      const vx = (wind?.x || 0) * WIND_PUSH
      const vz = (wind?.y || 0) * WIND_PUSH
      const shown = Math.floor(count * Math.min(1, rain))
      const ox = camera.position.x - BOX.x / 2
      const oy = camera.position.y - BOX.y / 2
      const oz = camera.position.z - BOX.z / 2
      for (let i = 0; i < shown; i++) {
        let y = drops[i * 3 + 1] - FALL_SPEED * dt
        if (y < 0) y += BOX.y
        drops[i * 3 + 1] = y
        const x = drops[i * 3] = ((drops[i * 3] + vx * dt) % BOX.x + BOX.x) % BOX.x
        const z = drops[i * 3 + 2] = ((drops[i * 3 + 2] + vz * dt) % BOX.z + BOX.z) % BOX.z
        // Wrap the box round the camera, so the rain stays put in the world as the camera moves.
        const wx = ox + ((x - ox) % BOX.x + BOX.x) % BOX.x
        const wz = oz + ((z - oz) % BOX.z + BOX.z) % BOX.z
        const wy = oy + y
        const k = i * 6
        positions[k] = wx
        positions[k + 1] = wy
        positions[k + 2] = wz
        positions[k + 3] = wx - vx * STREAK // the streak trails back along the way the drop came
        positions[k + 4] = wy + FALL_SPEED * STREAK
        positions[k + 5] = wz - vz * STREAK
      }
      geometry.setDrawRange(0, shown * 2)
      geometry.attributes.position.needsUpdate = true
    },
    dispose() {
      scene.remove(lines)
      geometry.dispose()
      material.dispose()
    },
  }
}
