import * as THREE from 'three'

// A storm called down (main.lua THE STORM, ADR-023): its three strike spots, StormSpot parts the world lays on the
// ground for the warning and the storm, drawn as rings of pale blue light that crackle (a restless, uneven flicker) and
// flare white the moment before their bolt (Charged). The part itself is never drawn. Each frame: watch() for every
// entity, update(time) once, prune() with the ids still there.
const PALE = 0x9cc8ff
const WHITE = 0xeef6ff

export function createStormSpots(scene) {
  const spots = new Map() // entity id -> { group, ring, glow, charged, seed }
  const ringGeometry = new THREE.RingGeometry(1.5, 2.1, 48).rotateX(-Math.PI / 2)
  const glowGeometry = new THREE.CircleGeometry(2.4, 40).rotateX(-Math.PI / 2)
  const material = (opacity) => new THREE.MeshBasicMaterial({ color: PALE, transparent: true, opacity,
    blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide })

  function forget(id) {
    const s = spots.get(id)
    if (!s) return
    scene.remove(s.group)
    s.ring.material.dispose()
    s.glow.material.dispose()
    spots.delete(id)
  }

  return {
    watch(entity) {
      if (entity.render?.role !== 'StormSpot') return
      let s = spots.get(entity.id)
      if (!s) {
        const ring = new THREE.Mesh(ringGeometry, material(0.5))
        const glow = new THREE.Mesh(glowGeometry, material(0.15))
        const group = new THREE.Group()
        group.add(glow, ring)
        group.name = 'GodlingStormSpot'
        group.renderOrder = 20
        scene.add(group)
        s = { group, ring, glow, charged: false, seed: (entity.id * 9301 + 49297) % 233280 }
        spots.set(entity.id, s)
      }
      const [x, y, z] = entity.position
      s.group.position.set(x, y + 0.05, z)
      s.charged = entity.attributes?.Charged === true
    },
    // How each spot looks now: a crackle while it waits, a white flare when its bolt comes.
    update(time) {
      for (const s of spots.values()) {
        const t = time * (s.charged ? 23 : 9) + s.seed
        const crackle = 0.5 + 0.5 * Math.sin(t) * Math.sin(t * 2.3 + 1.7) // uneven, never quite still
        const color = s.charged ? WHITE : PALE
        s.ring.material.color.setHex(color)
        s.glow.material.color.setHex(color)
        s.ring.material.opacity = s.charged ? 0.65 + 0.35 * crackle : 0.3 + 0.35 * crackle
        s.glow.material.opacity = s.charged ? 0.3 + 0.3 * crackle : 0.08 + 0.1 * crackle
        s.group.scale.setScalar(s.charged ? 1.12 + 0.06 * crackle : 1)
      }
    },
    prune(activeIds) {
      for (const id of [...spots.keys()]) if (!activeIds.has(id)) forget(id)
    },
    info: () => [...spots.values()].map((s) => ({ charged: s.charged, opacity: Number(s.ring.material.opacity.toFixed(3)) })),
    dispose() {
      for (const id of [...spots.keys()]) forget(id)
      ringGeometry.dispose()
      glowGeometry.dispose()
    },
  }
}
