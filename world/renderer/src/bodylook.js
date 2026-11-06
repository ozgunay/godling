import * as THREE from 'three'

// How a body looks beyond its animation, from what the world says of it.
// - Death (main.lua DEATH, ADR-022). The body falls where it dies (the Stagger clip, held down while Dead: models.js)
//   and lies still; over the last FADE seconds before it is born again it fades away. Born again at the start spot it
//   rises (WakeUp) in a short glow: a pale column of light and a ring on the ground, fading.
// - Struck by a storm's lightning (main.lua THE STORM, ADR-023). The moment Struck counts up, the body is electrocuted
//   for SHOCK seconds: it flickers blue-white, arcs crawl over it, and it shakes. Then, while Scorched counts down (a
//   minute), it is charred black, with smoke rising off it at first; over the last CLEAR seconds it turns back to its
//   own colours.
// The body's materials are its own copies, made the first time any of this shows: a model's materials are shared.
// The world counts DeadFor and Scorched down in whole seconds; between its steps each runs on its own clock.
export const FADE = 3 // seconds before it is born again that the dead body fades away in
export const GLOW = 2.5 // seconds the glow round a body born again lasts
export const SHOCK = 1.5 // seconds a struck body is electrocuted
export const CLEAR = 10 // the last seconds of a char, in which the body turns back to its own colours
export const SMOKE = 8 // seconds smoke rises off a charred body
const CHAR = new THREE.Color(0x191614) // charcoal, with a little warmth
const SPARK = new THREE.Color(0xbfe0ff) // the electrocution's blue-white
const ARCS = 4 // arcs crawling over a body being electrocuted
const ARC_STEPS = 6 // kinks in each

export function createBodyLook(scene, { random = Math.random, onMaterial } = {}) {
  const looks = new Map() // entity id -> state
  const column = new THREE.CylinderGeometry(1.3, 1.3, 7, 24, 1, true).translate(0, 1, 0)
  const ring = new THREE.RingGeometry(1.1, 2.3, 32).rotateX(-Math.PI / 2)
  const puff = new THREE.SphereGeometry(0.35, 8, 6)
  const glowMaterial = (opacity) => new THREE.MeshBasicMaterial({ color: 0xfff1c4, transparent: true, opacity,
    blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide })

  // The body's own copies of its materials, with what they were: made the first time anything shows on it.
  function materialsOf(look) {
    if (!look.materials) {
      look.materials = []
      look.originals = []
      look.root.traverse((node) => {
        if (!node.isMesh) return
        look.originals.push({ node, material: node.material })
        node.material = Array.isArray(node.material) ? node.material.map((m) => m.clone()) : node.material.clone()
        for (const m of [].concat(node.material)) {
          const unregister = onMaterial?.(m) // clones need the renderer's lighting setup (including CSM) too
          look.materials.push({ m, unregister, transparent: m.transparent, opacity: m.opacity, depthWrite: m.depthWrite,
            color: m.color?.clone() ?? null, emissive: m.emissive?.clone() ?? null, emissiveIntensity: m.emissiveIntensity })
        }
      })
    }
    return look.materials
  }

  // Fade (1 whole, 0 gone), char (0 its own colours, 1 charcoal) and shock (0 none, 1 a full flash), on every material.
  function paint(look, fade, char, shock) {
    if (look.fade === fade && look.char === char && look.shock === shock) return
    const fading = fade < 1
    for (const s of materialsOf(look)) {
      if ((look.fade < 1) !== fading) { // a change of blending: once as it starts to fade, once when it is back
        s.m.transparent = fading || s.transparent
        s.m.depthWrite = fading ? false : s.depthWrite
        s.m.needsUpdate = true
      }
      s.m.opacity = s.opacity * fade
      if (s.color) s.m.color.copy(s.color).lerp(CHAR, char)
      if (s.emissive) {
        s.m.emissive.copy(s.emissive).lerp(SPARK, shock)
        s.m.emissiveIntensity = shock > 0 ? Math.max(s.emissiveIntensity, 2.5 * shock) : s.emissiveIntensity
      }
    }
    look.fade = fade
    look.char = char
    look.shock = shock
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

  // Arcs crawling over a body being electrocuted: jagged lines from one point of the body to another, cut afresh often.
  function arcsFor(look) {
    if (!look.arcs) {
      const geometry = new THREE.BufferGeometry()
      geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(ARCS * ARC_STEPS * 2 * 3), 3))
      const material = new THREE.LineBasicMaterial({ color: SPARK, transparent: true, opacity: 1,
        blending: THREE.AdditiveBlending, depthWrite: false })
      look.arcs = new THREE.LineSegments(geometry, material)
      look.arcs.name = 'GodlingShockArcs'
      look.arcs.frustumCulled = false
      scene.add(look.arcs)
    }
    return look.arcs
  }

  function crawl(arcs, position) {
    const at = arcs.geometry.attributes.position
    const onBody = () => {
      const a = random() * Math.PI * 2
      const r = 0.6 + random() * 0.5
      return [position[0] + Math.cos(a) * r, position[1] - 2.2 + random() * 4.6, position[2] + Math.sin(a) * r]
    }
    let i = 0
    for (let k = 0; k < ARCS; k++) {
      let from = onBody()
      const to = onBody()
      for (let step = 1; step <= ARC_STEPS; step++) { // each kink a step towards `to`, pushed aside at random
        const next = step === ARC_STEPS ? to
          : from.map((v, j) => v + (to[j] - from[j]) / (ARC_STEPS - step + 1) + (random() - 0.5) * 0.5)
        at.setXYZ(i++, ...from)
        at.setXYZ(i++, ...next)
        from = next
      }
    }
    at.needsUpdate = true
  }

  function endArcs(look) {
    if (!look.arcs) return
    scene.remove(look.arcs)
    look.arcs.geometry.dispose()
    look.arcs.material.dispose()
    look.arcs = null
  }

  // Smoke off a charred body: grey wisps that rise, swell and fade.
  function tickSmoke(look, position, dt, rising) {
    if (!look.smoke && !rising) return
    if (!look.smoke) {
      look.smoke = { group: new THREE.Group(), puffs: [], next: 0 }
      look.smoke.group.name = 'GodlingSmoke'
      scene.add(look.smoke.group)
    }
    const smoke = look.smoke
    smoke.next -= dt
    if (rising && smoke.next <= 0) { // a new wisp off the shoulders
      smoke.next = 0.25
      const material = new THREE.MeshBasicMaterial({ color: 0x5a5652, transparent: true, opacity: 0.5, depthWrite: false })
      const wisp = new THREE.Mesh(puff, material)
      wisp.position.set(position[0] + (random() - 0.5) * 1.2, position[1] + 1.5, position[2] + (random() - 0.5) * 1.2)
      smoke.group.add(wisp)
      smoke.puffs.push({ wisp, age: 0 })
    }
    for (const p of [...smoke.puffs]) {
      p.age += dt
      p.wisp.position.y += dt * 1.6
      p.wisp.scale.setScalar(1 + p.age * 1.2)
      p.wisp.material.opacity = Math.max(0, 0.5 * (1 - p.age / 2.5))
      if (p.age >= 2.5) {
        smoke.group.remove(p.wisp)
        p.wisp.material.dispose()
        smoke.puffs.splice(smoke.puffs.indexOf(p), 1)
      }
    }
    if (!rising && smoke.puffs.length === 0) endSmoke(look)
  }

  function endSmoke(look) {
    if (!look.smoke) return
    for (const p of look.smoke.puffs) p.wisp.material.dispose()
    scene.remove(look.smoke.group)
    look.smoke = null
  }

  function releaseMaterials(look) {
    for (const { node, material } of look.originals || []) node.material = material
    for (const { m, unregister } of look.materials || []) {
      if (typeof unregister === 'function') unregister()
      m.dispose()
    }
    look.originals = null
    look.materials = null
  }

  function clear() {
    for (const look of looks.values()) {
      endGlow(look)
      endArcs(look)
      endSmoke(look)
      releaseMaterials(look)
    }
    looks.clear()
  }

  // A countdown the world steps in whole seconds, run on between its steps.
  function countdown(clock, told, dt) {
    if (Number.isFinite(told) && told > 0 && told !== clock.seen) {
      clock.seen = told
      clock.left = told
    } else if (Number.isFinite(told) && told > 0) {
      clock.left -= dt
    } else {
      clock.seen = null
      clock.left = 0
    }
    return Math.max(0, clock.left)
  }

  return {
    // Each frame, for each drawn body: how it looks now, from its attributes (Dead, DeadFor, Struck, Scorched).
    update(id, root, attributes, position, dt) {
      const dead = attributes.Dead === true
      const struck = Number(attributes.Struck) || 0
      let look = looks.get(id)
      if (!look) {
        look = { root, dead, struck, dying: { seen: null, left: 0 }, charring: { seen: null, left: 0 }, shockLeft: 0,
          sinceStruck: Infinity, fade: 1, char: 0, shock: 0, materials: null, glow: null, arcs: null, smoke: null }
        looks.set(id, look) // first sight: nothing plays that happened before it was seen
      }
      if (look.root !== root) {
        releaseMaterials(look)
        look.root = root
        look.fade = 1
        look.char = 0
        look.shock = 0
      }
      if (look.dead && !dead) startGlow(look, position) // born again: it rises in the light
      look.dead = dead
      if (struck > look.struck) { // struck just now: electrocuted, and smoking a while
        look.shockLeft = SHOCK
        look.sinceStruck = 0
      }
      look.struck = struck
      look.shockLeft = Math.max(0, look.shockLeft - dt)
      look.sinceStruck += dt

      const deadLeft = dead ? countdown(look.dying, Number(attributes.DeadFor), dt) : Infinity
      if (!dead) countdown(look.dying, 0, dt)
      const charLeft = countdown(look.charring, Number(attributes.Scorched), dt)
      const fade = dead ? Math.min(1, deadLeft / FADE) : 1
      const char = charLeft > 0 ? Math.min(1, charLeft / CLEAR) : 0
      // The shock flickers many times a second, hard at first, dying away.
      const shock = look.shockLeft > 0 ? (look.shockLeft / SHOCK) * (0.55 + 0.45 * Math.sin(look.shockLeft * 90)) : 0
      if (look.materials || fade < 1 || char > 0 || shock > 0) paint(look, fade, char, shock)
      if (fade <= 0.01) root.visible = false // gone before it comes back

      if (look.shockLeft > 0) {
        root.position.x += (random() - 0.5) * 0.16 // it shakes
        root.position.z += (random() - 0.5) * 0.16
        const arcs = arcsFor(look)
        arcs.material.opacity = 0.5 + 0.5 * random()
        crawl(arcs, position)
      } else {
        endArcs(look)
      }
      tickSmoke(look, position, dt, charLeft > 0 && look.sinceStruck < SMOKE)

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
          endArcs(look)
          endSmoke(look)
          releaseMaterials(look)
          looks.delete(id)
        }
      }
    },
    reset: clear, // a replay seek starts the body's effects at the new moment, including backwards in time
    info: () => [...looks].map(([id, l]) => ({ id, dead: l.dead, opacity: Number(l.fade.toFixed(3)),
      char: Number(l.char.toFixed(3)), shock: l.shockLeft > 0, glow: Boolean(l.glow), smoke: l.smoke?.puffs.length ?? 0 })),
    dispose() {
      clear()
      column.dispose()
      ring.dispose()
      puff.dispose()
    },
  }
}
