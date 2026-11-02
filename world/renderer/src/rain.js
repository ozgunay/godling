import * as THREE from 'three'

// Rain (ADR-010): the world's Clock carries Rain, 0 (dry) to 1 (pouring). Streaks fall in a box that travels with
// the camera, more of them and more opaque the harder it rains, slanting a little with the wind. The rest of the
// look (a greyer sky, dimmer light, grey clouds) is applied by index.js from the same number.

const BOX = { x: 70, y: 36, z: 70 }
const FALL_SPEED = 34 // units per second
const WIND = new THREE.Vector3(3, 0, 1.2) // a slight slant
const STREAK = 1.6 // length of a drop's streak

export function createRain(scene, tier) {
  const count = tier.name === 'low' ? 1500 : tier.name === 'medium' ? 3000 : 5000
  const positions = new Float32Array(count * 6)
  const drops = new Float32Array(count * 3) // each drop's place in the box
  for (let i = 0; i < count; i++) {
    drops[i * 3] = Math.random() * BOX.x
    drops[i * 3 + 1] = Math.random() * BOX.y
    drops[i * 3 + 2] = Math.random() * BOX.z
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  const material = new THREE.LineBasicMaterial({ color: 0xc8d4e0, transparent: true, opacity: 0, depthWrite: false, fog: true })
  const lines = new THREE.LineSegments(geometry, material)
  lines.frustumCulled = false
  lines.visible = false
  scene.add(lines)
  const slant = WIND.clone().divideScalar(FALL_SPEED).multiplyScalar(STREAK)
  let last = 0

  return {
    // rain: 0..1 from the world; time: seconds; camera: where the box goes.
    update({ rain, time, camera }) {
      lines.visible = rain > 0.02
      if (!lines.visible) return
      const dt = Math.min(0.1, Math.max(0, time - last))
      last = time
      material.opacity = 0.18 + 0.32 * rain
      const shown = Math.floor(count * Math.min(1, rain))
      const ox = camera.position.x - BOX.x / 2
      const oy = camera.position.y - BOX.y / 2
      const oz = camera.position.z - BOX.z / 2
      for (let i = 0; i < shown; i++) {
        let y = drops[i * 3 + 1] - FALL_SPEED * dt
        if (y < 0) y += BOX.y
        drops[i * 3 + 1] = y
        const x = drops[i * 3] = (drops[i * 3] + WIND.x * dt + BOX.x) % BOX.x
        const z = drops[i * 3 + 2] = (drops[i * 3 + 2] + WIND.z * dt + BOX.z) % BOX.z
        // Wrap the box round the camera, so the rain stays put in the world as the camera moves.
        const wx = ox + ((x - ox) % BOX.x + BOX.x) % BOX.x
        const wz = oz + ((z - oz) % BOX.z + BOX.z) % BOX.z
        const wy = oy + y
        const k = i * 6
        positions[k] = wx
        positions[k + 1] = wy
        positions[k + 2] = wz
        positions[k + 3] = wx - slant.x
        positions[k + 4] = wy + STREAK
        positions[k + 5] = wz - slant.z
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
