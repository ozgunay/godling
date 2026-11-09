// Aiming a sky power from the viewer screen (world/viewer, the user's wish): while a power is picked, a ring follows
// the pointer over the island, on whatever is there, and a click (or tap) reports the spot. The world decides what
// lands there (main.lua sky.aim): a meteor or storm can hit Godling; a meteor can also break what it built. A storm
// (main.lua sky.storm) takes three spots: the screen aims again after each, and the spots picked so far stay marked.
// A log (ADR-029) shows how far from Godling it may be aimed, as a ring round Godling, and an aim past that ring comes
// in to its edge, on the line from Godling, as a ground-targeted ability's cast range does in a MOBA: the reticle shows
// the spot the world will drop it, following Godling as it walks. What the viewer aimed at is what the screen sends:
// the world brings it in itself (sky.aim.read), from where Godling is when the call arrives, and its log then says
// when a viewer aimed past the ring.
import { FEET } from './bodylook.js'

const LOOKS = { // ring radius (the meteor's: its blast), colour, and an inner disk (the meteor's: what it smashes)
  Meteor: { radius: 7, color: 0xec4b4f, inner: 2.5 },
  Lightning: { radius: 1.8, color: 0xfff1a8 },
  Storm: { radius: 2.5, color: 0x9cc8ff }, // a strike: within 2.5 it is on Godling (main.lua sky.storm HIT)
  Regrow: { radius: 1.8, color: 0x63b544 },
  Log: { radius: 1.6, color: 0xf6c945, reach: true },
  default: { radius: 1.6, color: 0xf6c945 },
}
const AT_GODLING = 4.5 // main.lua sky.aim.AT_GODLING: an aim this close counts as aimed at Godling
const REACH = 60 // main.lua sky.aim.REACH, until the world's Clock says (SkyReach): a log aimed further comes in to it
const RING_WIDTH = 0.6 // the reach ring's band, at a reach of 60
const CLICK_PX = 7 // a press that moves less than this is a click, not a drag of the camera

export function createAim(THREE, scene, camera, canvas, { godling, onHover, onAimed, onCancel, reach: reachOf }) {
  let power = null
  const raycaster = new THREE.Raycaster()
  const pointer = new THREE.Vector2()
  const ringMaterial = new THREE.MeshBasicMaterial({ color: 0xf6c945, transparent: true, opacity: 0.95, depthTest: false })
  const fillMaterial = new THREE.MeshBasicMaterial({ color: 0xf6c945, transparent: true, opacity: 0.22, depthTest: false })
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.88, 1, 56).rotateX(-Math.PI / 2), ringMaterial)
  const fill = new THREE.Mesh(new THREE.CircleGeometry(1, 40).rotateX(-Math.PI / 2), fillMaterial)
  const reticle = new THREE.Group()
  reticle.add(fill, ring)
  reticle.visible = false
  ring.renderOrder = fill.renderOrder = 30
  scene.add(reticle)
  const reachMaterial = new THREE.MeshBasicMaterial({ color: 0xfff6d8, transparent: true, opacity: 0.5, depthTest: false })
  const band = new THREE.RingGeometry(1 - RING_WIDTH / REACH, 1, 192).rotateX(-Math.PI / 2) // scaled to the reach
  const reach = new THREE.Mesh(band, reachMaterial)
  reach.name = 'aim-reach'
  reach.renderOrder = 29
  reach.visible = false
  scene.add(reach)
  let press = null
  let spot = null
  let raw = null // what the pointer is over, before any bringing in
  let at = null // where the pointer is on the canvas, to look again as the camera and Godling move

  const reachNow = () => {
    const r = Number(reachOf?.())
    return Number.isFinite(r) && r > 0 ? r : REACH
  }

  // The island's parts and terrain: drawn in instanced groups and the terrain mesh, all straight under the scene; never
  // what is marked noAim, as the clouds are (clouds.js: on the medium and high tiers an opaque layer at 92).
  const targets = () => scene.children.filter((o) => (o.isInstancedMesh || o.isMesh) && o.visible && o !== reticle
    && !(o.material && o.material.transparent) && !o.userData?.noAim)

  function pick(where) {
    const r = canvas.getBoundingClientRect()
    pointer.set(((where.clientX - r.left) / r.width) * 2 - 1, -((where.clientY - r.top) / r.height) * 2 + 1)
    raycaster.setFromCamera(pointer, camera)
    const hit = raycaster.intersectObjects(targets(), false).find((h) => h.distance < 1500 && h.point.y > -5 && h.point.y < 150)
    return hit ? hit.point.clone() : null
  }

  const down = new THREE.Vector3(0, -1, 0)
  function topAt(x, z) { // the height of whatever is at (x, z), seen from above
    raycaster.set(new THREE.Vector3(x, 150, z), down)
    const hit = raycaster.intersectObjects(targets(), false).find((h) => h.point.y > -5)
    return hit ? hit.point.y : null
  }

  function placeReach() { // round Godling, while a power with a reach is picked and Godling is in sight
    const g = godling()
    reach.visible = Boolean(power && LOOKS[power]?.reach && g)
    if (!reach.visible) return
    reach.position.set(g.x, g.y - FEET + 0.06, g.z)
    reach.scale.setScalar(reachNow())
  }

  // The reticle where the gift would land for the pointer over `point`; the screen hears of it (onHover) when `tell`,
  // or when what the aim bar says would change.
  function show(point, tell = true) {
    const look = LOOKS[power] || LOOKS.default
    const g = godling()
    const limit = reachNow()
    raw = point
    let beyond = false
    if (look.reach && g && Math.hypot(point.x - g.x, point.z - g.z) > limit) { // in to the edge, towards the pointer
      const k = limit / Math.hypot(point.x - g.x, point.z - g.z)
      const x = g.x + (point.x - g.x) * k
      const z = g.z + (point.z - g.z) * k
      point = { x, y: topAt(x, z) ?? point.y, z }
      beyond = true
    }
    placeReach()
    reachMaterial.opacity = beyond ? 0.9 : 0.5
    const atGodling = Boolean(g) && Math.hypot(point.x - g.x, point.z - g.z) < AT_GODLING
    const harms = power === 'Meteor' || power === 'Storm' // red on Godling: a blast, or a strike, hurts it there
    const color = atGodling ? (harms ? 0xec4b4f : 0x45d6cf) : look.color // teal: it will land at Godling's feet
    ringMaterial.color.setHex(color)
    fillMaterial.color.setHex(color)
    ring.scale.setScalar(look.radius)
    fill.scale.setScalar(look.inner || look.radius * 0.5)
    reticle.position.set(point.x, point.y + 0.06, point.z)
    reticle.visible = true
    const was = spot
    spot = { x: point.x, y: point.y, z: point.z, atGodling, beyond }
    if (tell || !was || was.atGodling !== atGodling || was.beyond !== beyond) onHover?.(spot)
  }

  canvas.addEventListener('pointermove', (e) => {
    if (!power) return
    at = { clientX: e.clientX, clientY: e.clientY }
    const point = pick(e)
    if (point) show(point)
  })
  canvas.addEventListener('pointerdown', (e) => {
    if (!power) return
    press = { x: e.clientX, y: e.clientY }
    at = { clientX: e.clientX, clientY: e.clientY }
    const point = pick(e) // a tap has no hover before it
    if (point) show(point)
  }, true)
  canvas.addEventListener('pointerup', (e) => {
    if (!power || !press) return
    const click = Math.hypot(e.clientX - press.x, e.clientY - press.y) < CLICK_PX
    press = null
    if (!click) return
    const point = pick(e)
    if (!point) return
    show(point)
    const aimed = { power, ...spot, ...(spot.beyond ? { x: raw.x, z: raw.z } : {}) } // what the viewer aimed at
    stop()
    onAimed?.(aimed)
  }, true)
  addEventListener('keydown', (e) => {
    if (power && e.key === 'Escape') {
      stop()
      onCancel?.()
    }
  })

  function stop() {
    power = null
    reticle.visible = false
    reach.visible = false
    spot = raw = at = null
    canvas.style.cursor = ''
  }

  // The spots picked so far for a power that takes several (a storm's strikes): a ring on each.
  const markGeometry = new THREE.RingGeometry(0.8, 1, 48).rotateX(-Math.PI / 2)
  const markMaterial = new THREE.MeshBasicMaterial({ color: LOOKS.Storm.color, transparent: true, opacity: 0.9, depthTest: false })
  let marked = []
  function marks(spots) {
    for (const m of marked) scene.remove(m)
    marked = (Array.isArray(spots) ? spots : []).filter((s) => [s?.x, s?.z].every(Number.isFinite)).map((s) => {
      const m = new THREE.Mesh(markGeometry, markMaterial)
      m.scale.setScalar(LOOKS.Storm.radius)
      m.position.set(s.x, (Number.isFinite(s.y) ? s.y : 0) + 0.06, s.z)
      m.renderOrder = 30
      scene.add(m)
      return m
    })
  }

  return {
    marks,
    get marked() { return marked.length },
    start(name) {
      power = name
      canvas.style.cursor = 'crosshair'
      reachMaterial.opacity = 0.5 // not still lit from an aim past the ring before
      placeReach()
    },
    stop,
    // Each frame: the reach ring goes with Godling, and so do the reticle and the aim bar's words, looked at again
    // under the pointer as the camera follows (79-AB4).
    update() {
      if (!power) return
      placeReach()
      if (!LOOKS[power]?.reach || !at) return
      const point = pick(at) || raw
      if (point) show(point, false)
    },
    get active() { return Boolean(power) },
  }
}
