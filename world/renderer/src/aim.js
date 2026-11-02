// Aiming a sky power from the viewer screen (world/viewer, the user's wish): while a power is picked, a ring follows
// the pointer over the island, on whatever is there, and a click (or tap) reports the spot. The world decides what
// lands there (main.lua sky.aim): only the meteor lands on Godling or on what it built; the ring says as much.

const LOOKS = { // ring radius (the meteor's: its blast), colour, and an inner disk (the meteor's: what it smashes)
  Meteor: { radius: 7, color: 0xec4b4f, inner: 2.5 },
  Lightning: { radius: 1.8, color: 0xfff1a8 },
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
    const color = power !== 'Meteor' && atGodling ? 0x45d6cf : look.color // teal: it will land at Godling's feet
    ringMaterial.color.setHex(color)
    fillMaterial.color.setHex(color)
    ring.scale.setScalar(look.radius)
    fill.scale.setScalar(look.inner || look.radius * 0.5)
    reticle.position.set(point.x, point.y + 0.06, point.z)
    reticle.visible = true
    spot = { x: point.x, z: point.z, atGodling }
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

  return {
    start(name) {
      power = name
      canvas.style.cursor = 'crosshair'
    },
    stop,
    get active() { return Boolean(power) },
  }
}
