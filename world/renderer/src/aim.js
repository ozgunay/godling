// Aiming a sky power from the viewer screen (world/viewer, the user's wish): while a power is picked, a ring follows
// the pointer over the island, on whatever is there, and a click (or tap) reports the spot. The world decides what
// lands there (main.lua sky.aim): a meteor or storm can hit Godling; a meteor can also break what it built. A storm
// (main.lua sky.storm) takes three spots: the screen aims again after each, and the spots picked so far stay marked.

const LOOKS = { // ring radius (the meteor's: its blast), colour, and an inner disk (the meteor's: what it smashes)
  Meteor: { radius: 7, color: 0xec4b4f, inner: 2.5 },
  Lightning: { radius: 1.8, color: 0xfff1a8 },
  Storm: { radius: 2.5, color: 0x9cc8ff }, // a strike: within 2.5 it is on Godling (main.lua sky.storm HIT)
  Regrow: { radius: 1.8, color: 0x63b544 },
  default: { radius: 1.6, color: 0xf6c945 },
}
const AT_GODLING = 4.5 // main.lua sky.aim.AT_GODLING: an aim this close counts as aimed at Godling
const CLICK_PX = 7 // a press that moves less than this is a click, not a drag of the camera

export function createAim(THREE, scene, camera, canvas, { godling, onHover, onAimed, onCancel }) {
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
  let press = null
  let spot = null

  function pick(event) {
    const r = canvas.getBoundingClientRect()
    pointer.set(((event.clientX - r.left) / r.width) * 2 - 1, -((event.clientY - r.top) / r.height) * 2 + 1)
    raycaster.setFromCamera(pointer, camera)
    // The island's parts and terrain: drawn in instanced groups and the terrain mesh, all straight under the scene.
    const targets = scene.children.filter((o) => (o.isInstancedMesh || o.isMesh) && o.visible && o !== reticle
      && !(o.material && o.material.transparent))
    const hit = raycaster.intersectObjects(targets, false).find((h) => h.distance < 1500 && h.point.y > -5 && h.point.y < 150)
    return hit ? hit.point : null
  }

  function show(point) {
    const look = LOOKS[power] || LOOKS.default
    const g = godling()
    const atGodling = Boolean(g) && Math.hypot(point.x - g.x, point.z - g.z) < AT_GODLING
    const harms = power === 'Meteor' || power === 'Storm' // red on Godling: a blast, or a strike, hurts it there
    const color = atGodling ? (harms ? 0xec4b4f : 0x45d6cf) : look.color // teal: it will land at Godling's feet
    ringMaterial.color.setHex(color)
    fillMaterial.color.setHex(color)
    ring.scale.setScalar(look.radius)
    fill.scale.setScalar(look.inner || look.radius * 0.5)
    reticle.position.set(point.x, point.y + 0.06, point.z)
    reticle.visible = true
    spot = { x: point.x, y: point.y, z: point.z, atGodling }
    onHover?.(spot)
  }

  canvas.addEventListener('pointermove', (e) => {
    if (!power) return
    const point = pick(e)
    if (point) show(point)
  })
  canvas.addEventListener('pointerdown', (e) => {
    if (!power) return
    press = { x: e.clientX, y: e.clientY }
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
    const aimed = { power, ...spot }
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
    spot = null
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
    },
    stop,
    get active() { return Boolean(power) },
  }
}
