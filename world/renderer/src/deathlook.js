import * as THREE from 'three'

// Death (main.lua DEATH) as viewers see it. The body falls where it dies (the Stagger clip, held down while the
// world says Dead: models.js) and lies still; over the last FADE seconds before it is born again it fades away. Born
// again at the start spot it rises (WakeUp) in a short glow: a pale column of light and a ring on the ground, fading.
// The world counts DeadFor down in whole seconds; between its steps the fade runs on its own clock.
export const FADE = 3 // seconds before it is born again that the dead body fades away in
export const GLOW = 2.5 // seconds the glow round a body born again lasts

export function createDeathLook(scene) {
  const looks = new Map() // entity id -> { root, dead, left, opacity, materials, glow }
  const column = new THREE.CylinderGeometry(1.3, 1.3, 7, 24, 1, true).translate(0, 1, 0)
  const ring = new THREE.RingGeometry(1.1, 2.3, 32).rotateX(-Math.PI / 2)
  const glowMaterial = (opacity) => new THREE.MeshBasicMaterial({ color: 0xfff1c4, transparent: true, opacity,
    blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide })

  // The body's own copies of its materials, made the first time it fades: a model's materials are shared.
  function materialsOf(look) {
    if (!look.materials) {
      look.materials = []
      look.root.traverse((node) => {
        if (!node.isMesh) return
        node.material = Array.isArray(node.material) ? node.material.map((m) => m.clone()) : node.material.clone()
        for (const m of [].concat(node.material)) {
          look.materials.push({ m, transparent: m.transparent, opacity: m.opacity, depthWrite: m.depthWrite })
        }
      })
    }
    return look.materials
  }

  function setOpacity(look, k) {
    if (look.opacity === k) return
    const fading = k < 1
    for (const s of materialsOf(look)) {
      if ((look.opacity < 1) !== fading) { // a change of blending: once as it starts to fade, once when it is back
        s.m.transparent = fading || s.transparent
        s.m.depthWrite = fading ? false : s.depthWrite
        s.m.needsUpdate = true
      }
      s.m.opacity = s.opacity * k
    }
    look.opacity = k
  }

  function startGlow(look, position) {
    endGlow(look)
    const pillar = new THREE.Mesh(column, glowMaterial(0.55))
    const base = new THREE.Mesh(ring, glowMaterial(0.8))
    const group = new THREE.Group()
    group.add(pillar, base)
    group.position.set(position[0], position[1] - 2.4, position[2]) // the ring at the feet (the body is 5 tall)
    group.name = 'GodlingRebirthGlow'
    scene.add(group)
    look.glow = { group, pillar, base, age: 0 }
  }

  function endGlow(look) {
    if (!look.glow) return
    scene.remove(look.glow.group)
    look.glow.pillar.material.dispose()
    look.glow.base.material.dispose()
    look.glow = null
  }

  return {
    // Each frame, for each drawn body: how it looks now, from its attributes (Dead, DeadFor).
    update(id, root, attributes, position, dt) {
      const dead = attributes.Dead === true
      let look = looks.get(id)
      if (!look) {
        look = { root, dead, left: Infinity, seenLeft: null, opacity: 1, materials: null, glow: null }
        looks.set(id, look)
      }
      if (look.root !== root) {
        look.root = root
        look.materials = null
        look.opacity = 1
      }
      if (look.dead && !dead) startGlow(look, position) // born again: it rises in the light
      look.dead = dead
      const told = Number(attributes.DeadFor)
      if (dead && Number.isFinite(told) && told !== look.seenLeft) {
        look.seenLeft = told
        look.left = told
      } else if (dead) {
        look.left -= dt
      } else {
        look.seenLeft = null
        look.left = Infinity
      }
      setOpacity(look, dead ? Math.min(1, Math.max(0, look.left / FADE)) : 1)
      if (look.opacity <= 0.01) root.visible = false // gone before it comes back
      if (look.glow) {
        const g = look.glow
        g.age += dt
        const k = Math.max(0, 1 - g.age / GLOW)
        g.pillar.material.opacity = 0.55 * k
        g.base.material.opacity = 0.8 * k
        g.group.scale.set(1 + 0.4 * (1 - k), 1, 1 + 0.4 * (1 - k))
        if (g.age >= GLOW) endGlow(look)
      }
    },
    prune(activeIds) {
      for (const [id, look] of looks) {
        if (!activeIds.has(id)) {
          endGlow(look)
          looks.delete(id)
        }
      }
    },
    info: () => [...looks].map(([id, l]) => ({ id, dead: l.dead, opacity: Number(l.opacity.toFixed(3)), glow: Boolean(l.glow) })),
    dispose() {
      for (const look of looks.values()) endGlow(look)
      looks.clear()
      column.dispose()
      ring.dispose()
    },
  }
}
