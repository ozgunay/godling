import * as THREE from 'three'

// The thought bubble (ADR-009), as in The Sims: a cloud over Godling's head holding a picture of what it has in mind,
// its rim tinted by how it feels (green glad, red troubled, grey in between). The world names both on the player:
// Thought (a key below), Feeling, and a Thoughts counter that goes up with each new reading. Each new thought pops
// up, stays a while and fades, and the next one pops up in its place.
//
// The pictures are the island's own models, drawn once into a small picture each (as The Sims draws the cake
// itself); what has no model (fire, the HELP sign, a ship, the night) is drawn by hand.

const SHOW_SECONDS = 10
const POP_SECONDS = 0.25
const FADE_SECONDS = 0.8
const ABOVE_HEAD = 2.9 // from the body's centre to the tip of the bubble's tail, just over the head
const WORLD_SIZE = 4.6 // the bubble's width in world units
const PICTURE = 128 // pixels
// The cloud sits up and to one side of the head, as in The Sims, and its tail leads down to the head: the sprite is
// anchored at the tail's tip (in the 256-pixel canvas: x 46, y 236), so a block held over the head stays in view.
const CLOUD = { x: 148, y: 100 }
const TAIL = [[80, 196, 14], [56, 224, 9]]
const TIP = new THREE.Vector2(46 / 256, 1 - 236 / 256)

const GLAD = new Set(['happy', 'proud', 'hopeful', 'curious', 'calm'])
const TROUBLED = new Set(['tired', 'lonely', 'worried', 'frustrated', 'scared', 'hungry', 'sad'])
const RIM = { glad: '#3fb24a', troubled: '#de3b34', between: '#8f9aa6' }

const stone = 'asset://stone.glb'
const PICTURES = {
  coconut: { model: 'asset://coconut.glb' },
  fish: { model: 'asset://fish.glb', yaw: 0.2 },
  cooked_fish: { model: 'asset://fish_cooked.glb', yaw: 0.2 },
  log: { model: 'asset://log.glb' },
  block: { model: stone },
  boulder: { model: 'asset://boulder.glb' },
  axe: { model: 'asset://axe.glb', tilt: 0.1 },
  hammer: { model: 'asset://hammer.glb', tilt: 0.1 },
  spear: { model: 'asset://spear.glb', roll: 0.8 },
  palm: { model: 'asset://palm.glb', tilt: 0.05 },
  ladder: { model: 'asset://ladder.glb', tilt: 0.1 },
  raft: { model: 'asset://raft.glb' },
  ball: { model: 'asset://volleyball.glb' },
  tower: { pieces: [[stone, 0, 0, 0], [stone, 0, 1, 0], [stone, 0, 2, 0]] },
  wall: { pieces: [[stone, -1, 0, 0], [stone, 0, 0, 0], [stone, 1, 0, 0], [stone, -0.5, 1, 0], [stone, 0.5, 1, 0]] },
  shelter: {
    pieces: [[stone, -1, 0, 0], [stone, 1, 0, 0], [stone, -1, 1, 0], [stone, 1, 1, 0],
      ['asset://log.glb', 0, 2, 0, 3.2]],
  },
  fire: { draw: drawFire },
  help: { draw: drawHelp },
  rescue: { draw: drawShip },
  sea: { draw: drawSea },
  lightning: { draw: drawBolt },
  explore: { draw: drawMap },
  night: { draw: drawNight },
}

// `resolve` turns the world's asset:// names into URLs the browser can load (null until it knows how).
export function createBubbles(scene, models, resolve) {
  const bubbles = new Map() // character entity id -> its bubble
  const pictures = createPictures(models, resolve)

  function make() {
    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 256
    const texture = new THREE.CanvasTexture(canvas)
    texture.colorSpace = THREE.SRGBColorSpace
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false, depthTest: false,
      fog: false, opacity: 0 }) // over everything, as a Sims bubble is
    const sprite = new THREE.Sprite(material)
    sprite.center.copy(TIP)
    sprite.renderOrder = 10
    sprite.visible = false
    scene.add(sprite)
    return { canvas, texture, sprite, count: null, thing: null, feeling: null, age: Infinity, drawn: null }
  }

  // Each frame, for each character: where its body is, its attributes, and whether the camera sits in its head.
  function update(id, position, attributes, hidden, dt) {
    const count = Number(attributes?.Thoughts || 0)
    let bubble = bubbles.get(id)
    if (!bubble) {
      if (!count) return
      bubble = make()
      bubbles.set(id, bubble)
    }
    if (count !== bubble.count) {
      if (bubble.count !== null || count) bubble.age = 0 // a new thought pops up (not one from before we looked)
      bubble.count = count
      bubble.thing = String(attributes?.Thought || '')
      bubble.feeling = String(attributes?.Feeling || '')
    }
    bubble.age += dt
    const key = `${bubble.thing}|${bubble.feeling}`
    if (bubble.drawn !== key && bubble.age < SHOW_SECONDS) {
      const picture = pictures.get(bubble.thing)
      if (picture !== undefined) { // undefined: its models are still on the way
        paint(bubble.canvas, picture, bubble.feeling)
        bubble.texture.needsUpdate = true
        bubble.drawn = key
      }
    }
    const shown = !hidden && bubble.drawn === key && bubble.age < SHOW_SECONDS
    bubble.sprite.visible = shown
    if (!shown) return
    const pop = Math.min(1, bubble.age / POP_SECONDS)
    const fade = Math.min(1, (SHOW_SECONDS - bubble.age) / FADE_SECONDS)
    const s = WORLD_SIZE * (0.6 + 0.4 * easeOutBack(pop))
    bubble.sprite.scale.set(s, s, 1)
    bubble.sprite.material.opacity = Math.min(pop * 1.5, fade, 1)
    bubble.sprite.position.set(position[0], position[1] + ABOVE_HEAD + 0.12 * Math.sin(bubble.age * 1.6), position[2])
  }

  function prune(activeIds) {
    for (const [id, bubble] of bubbles) {
      if (activeIds.has(id)) continue
      scene.remove(bubble.sprite)
      bubble.texture.dispose()
      bubble.sprite.material.dispose()
      bubbles.delete(id)
    }
  }

  return {
    update,
    prune,
    info: () => [...bubbles].map(([id, b]) => ({ id, count: b.count, thing: b.thing, feeling: b.feeling, drawn: b.drawn,
      age: Math.round(b.age * 10) / 10, visible: b.sprite.visible })),
    dispose() {
      prune(new Set())
      pictures.dispose()
    },
  }
}

function easeOutBack(t) {
  const c = 1.7
  return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2)
}

// The cloud: puffs round an oval, two small puffs trailing down to the head, the rim in the feeling's colour.
function paint(canvas, picture, feeling) {
  const g = canvas.getContext('2d')
  g.clearRect(0, 0, canvas.width, canvas.height)
  const rim = GLAD.has(feeling) ? RIM.glad : TROUBLED.has(feeling) ? RIM.troubled : RIM.between
  const { x: cx, y: cy } = CLOUD
  const puffs = []
  for (let k = 0; k < 11; k++) {
    const a = (k / 11) * Math.PI * 2
    puffs.push([cx + Math.cos(a) * 70, cy + Math.sin(a) * 52, 28 + 6 * Math.sin(k * 2.3)])
  }
  const outline = (grow) => {
    g.beginPath()
    for (const [x, y, r] of [...puffs, ...TAIL]) {
      g.moveTo(x + r + grow, y)
      g.arc(x, y, r + grow, 0, Math.PI * 2)
    }
    g.ellipse(cx, cy, 72 + grow, 54 + grow, 0, 0, Math.PI * 2)
  }
  g.fillStyle = rim
  outline(9)
  g.fill()
  const shade = g.createRadialGradient(cx - 30, cy - 40, 10, cx, cy, 120)
  shade.addColorStop(0, '#ffffff')
  shade.addColorStop(1, '#e4ecf2')
  g.fillStyle = shade
  outline(0)
  g.fill()
  if (picture) g.drawImage(picture, cx - 60, cy - 60, 120, 120)
}

// Every picture in a cloud, each feeling's tint in turn, on one sheet (a data URL): for checking the art.
export function bubbleSheet(models, resolve) {
  const pictures = createPictures(models, resolve)
  const things = Object.keys(PICTURES)
  const feelings = ['happy', 'determined', 'lonely']
  const sheet = document.createElement('canvas')
  const cols = 6
  sheet.width = cols * 256
  sheet.height = Math.ceil(things.length / cols) * 256
  const g = sheet.getContext('2d')
  g.fillStyle = '#6aa84f'
  g.fillRect(0, 0, sheet.width, sheet.height)
  const cell = document.createElement('canvas')
  cell.width = 256
  cell.height = 256
  const missing = []
  things.forEach((thing, i) => {
    const picture = pictures.get(thing)
    if (!picture) missing.push(thing)
    paint(cell, picture || null, feelings[i % feelings.length])
    g.drawImage(cell, (i % cols) * 256, Math.floor(i / cols) * 256)
    g.fillStyle = '#102010'
    g.font = '18px sans-serif'
    g.fillText(thing, (i % cols) * 256 + 150, Math.floor(i / cols) * 256 + 245)
  })
  return { url: sheet.toDataURL(), missing }
}

// One picture per thing: a model drawn by a small renderer of its own (so the scene's renderer and its shadows are
// left alone), or a hand drawing. get() is undefined while models are loading, null for an unknown thing.
function createPictures(models, resolve) {
  const cache = new Map()
  const asked = new Map() // thing -> when its picture was first wanted; a model that never comes gives an empty cloud
  let renderer = null
  let stage = null
  let camera = null

  function setUp() {
    const canvas = document.createElement('canvas')
    canvas.width = PICTURE
    canvas.height = PICTURE
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true })
    renderer.setClearColor(0x000000, 0)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    stage = new THREE.Scene()
    stage.add(new THREE.HemisphereLight(0xffffff, 0x8a7a66, 1.7))
    const sun = new THREE.DirectionalLight(0xffffff, 2.0)
    sun.position.set(3, 5, 4)
    stage.add(sun)
    camera = new THREE.PerspectiveCamera(28, 1, 0.05, 100)
  }

  function render(spec) {
    const pieces = spec.pieces || [[spec.model, 0, 0, 0]]
    const urls = pieces.map(([url]) => resolve(url))
    if (urls.some((url) => !url)) return undefined
    const templates = urls.map((url) => models.get(url))
    if (templates.some((t) => !t)) return undefined // models.get() has started the loads
    if (!renderer) setUp()
    const group = new THREE.Group()
    templates.forEach((template, i) => {
      const [, x, y, z, length] = pieces[i]
      const model = template.scene.clone(true)
      const box = new THREE.Box3()
      model.updateMatrixWorld(true)
      model.traverse((node) => {
        if (!node.isMesh) return
        if ([].concat(node.material).some((m) => m?.name === 'bounds')) { // the art's outline specks: not drawn
          node.visible = false
          return
        }
        // Own materials: the scene's are set up for its shadows.
        node.material = Array.isArray(node.material) ? node.material.map((m) => m.clone()) : node.material.clone()
        box.expandByObject(node) // framed on what is drawn
      })
      const size = box.getSize(new THREE.Vector3())
      const s = (length || 1) / Math.max(size.x, size.y, size.z, 1e-6)
      model.scale.setScalar(s)
      model.position.copy(box.getCenter(new THREE.Vector3())).multiplyScalar(-s)
      const holder = new THREE.Group()
      holder.add(model)
      holder.position.set(x, y, z)
      group.add(holder)
    })
    group.rotation.set(0.35 + (spec.tilt || 0), -0.6 + (spec.yaw || 0), spec.roll || 0)
    stage.add(group)
    group.updateMatrixWorld(true)
    const drawn = new THREE.Box3()
    group.traverse((node) => node.isMesh && node.visible && drawn.expandByObject(node))
    // Framed on its width and height as seen from the front, a little room round it (a bounding sphere left it small).
    const centre = drawn.getCenter(new THREE.Vector3())
    const size = drawn.getSize(new THREE.Vector3())
    camera.position.set(centre.x, centre.y, centre.z + size.z / 2
      + Math.max(size.x, size.y) * 0.56 / Math.tan(THREE.MathUtils.degToRad(14)))
    camera.lookAt(centre)
    renderer.render(stage, camera)
    stage.remove(group)
    group.traverse((node) => {
      if (node.isMesh) for (const m of [].concat(node.material)) m.dispose()
    })
    const picture = document.createElement('canvas')
    picture.width = PICTURE
    picture.height = PICTURE
    picture.getContext('2d').drawImage(renderer.domElement, 0, 0)
    return picture
  }

  return {
    get(thing) {
      if (cache.has(thing)) return cache.get(thing)
      const spec = PICTURES[thing]
      let picture = null
      if (spec?.draw) {
        picture = document.createElement('canvas')
        picture.width = PICTURE
        picture.height = PICTURE
        spec.draw(picture.getContext('2d'), PICTURE)
      } else if (spec) {
        picture = render(spec)
        if (picture === undefined) {
          if (!asked.has(thing)) asked.set(thing, performance.now())
          if (performance.now() - asked.get(thing) < 8000) return undefined
          picture = null
        }
      }
      cache.set(thing, picture)
      return picture
    },
    dispose() {
      cache.clear()
      renderer?.dispose()
    },
  }
}

// ---- hand drawings, on a square of side n -----------------------------------------------------------------------

function drawFire(g, n) {
  g.fillStyle = '#7a4a26'
  g.save()
  g.translate(n / 2, n * 0.8)
  for (const a of [-0.35, 0.35]) {
    g.save()
    g.rotate(a)
    g.fillRect(-n * 0.32, -n * 0.05, n * 0.64, n * 0.1)
    g.restore()
  }
  g.restore()
  const flame = (w, h, color) => {
    g.fillStyle = color
    g.beginPath()
    g.moveTo(n / 2, n * 0.76 - h)
    g.bezierCurveTo(n / 2 + w, n * 0.76 - h * 0.45, n / 2 + w * 0.8, n * 0.76, n / 2, n * 0.76)
    g.bezierCurveTo(n / 2 - w * 0.8, n * 0.76, n / 2 - w, n * 0.76 - h * 0.45, n / 2, n * 0.76 - h)
    g.fill()
  }
  flame(n * 0.3, n * 0.62, '#f05a1a')
  flame(n * 0.2, n * 0.44, '#ffb020')
  flame(n * 0.1, n * 0.24, '#fff3a0')
}

function drawHelp(g, n) {
  g.fillStyle = '#e8d6a8'
  g.beginPath()
  g.ellipse(n / 2, n / 2, n * 0.47, n * 0.3, 0, 0, Math.PI * 2)
  g.fill()
  g.fillStyle = '#6b4f2e'
  g.font = `bold ${Math.round(n * 0.27)}px sans-serif`
  g.textAlign = 'center'
  g.textBaseline = 'middle'
  g.fillText('HELP', n / 2, n / 2 + 2)
}

function drawSea(g, n) {
  g.lineWidth = n * 0.06
  g.lineCap = 'round'
  ;['#2e7fb8', '#3f9ad0', '#6cc0e6'].forEach((color, row) => {
    g.strokeStyle = color
    g.beginPath()
    const y = n * (0.38 + row * 0.16)
    for (let x = n * 0.08; x <= n * 0.92; x += 2) g.lineTo(x, y + Math.sin(x / n * Math.PI * 4 + row) * n * 0.05)
    g.stroke()
  })
}

function drawShip(g, n) {
  drawSea(g, n)
  g.fillStyle = '#5a3b22'
  g.beginPath()
  g.moveTo(n * 0.24, n * 0.48)
  g.lineTo(n * 0.76, n * 0.48)
  g.lineTo(n * 0.66, n * 0.6)
  g.lineTo(n * 0.34, n * 0.6)
  g.fill()
  g.fillStyle = '#ffffff'
  g.beginPath()
  g.moveTo(n * 0.5, n * 0.12)
  g.lineTo(n * 0.5, n * 0.46)
  g.lineTo(n * 0.72, n * 0.46)
  g.fill()
  g.strokeStyle = '#5a3b22'
  g.lineWidth = n * 0.025
  g.beginPath()
  g.moveTo(n * 0.5, n * 0.1)
  g.lineTo(n * 0.5, n * 0.48)
  g.stroke()
}

function drawBolt(g, n) {
  g.fillStyle = '#5f6670'
  for (const [x, y, r] of [[0.32, 0.3, 0.17], [0.52, 0.24, 0.2], [0.7, 0.32, 0.15], [0.5, 0.36, 0.18]]) {
    g.beginPath()
    g.arc(n * x, n * y, n * r, 0, Math.PI * 2)
    g.fill()
  }
  g.fillStyle = '#ffd629'
  g.beginPath()
  ;[[0.52, 0.42], [0.36, 0.68], [0.5, 0.68], [0.42, 0.94], [0.68, 0.58], [0.54, 0.58], [0.64, 0.42]]
    .forEach(([x, y], i) => (i ? g.lineTo(n * x, n * y) : g.moveTo(n * x, n * y)))
  g.fill()
}

function drawMap(g, n) { // exploring: a little map, a dotted way across it, and an X where it leads
  g.fillStyle = '#efe0b4'
  g.strokeStyle = '#a8865a'
  g.lineWidth = n * 0.025
  g.beginPath()
  g.roundRect(n * 0.1, n * 0.18, n * 0.8, n * 0.64, n * 0.06)
  g.fill()
  g.stroke()
  g.fillStyle = '#7fb86a'
  g.beginPath()
  g.ellipse(n * 0.42, n * 0.52, n * 0.22, n * 0.18, -0.4, 0, Math.PI * 2)
  g.fill()
  g.setLineDash([n * 0.04, n * 0.035])
  g.strokeStyle = '#7a4a26'
  g.beginPath()
  g.moveTo(n * 0.2, n * 0.72)
  g.bezierCurveTo(n * 0.35, n * 0.5, n * 0.55, n * 0.7, n * 0.68, n * 0.38)
  g.stroke()
  g.setLineDash([])
  g.strokeStyle = '#d23a2a'
  g.lineWidth = n * 0.04
  g.beginPath()
  g.moveTo(n * 0.64, n * 0.28)
  g.lineTo(n * 0.78, n * 0.42)
  g.moveTo(n * 0.78, n * 0.28)
  g.lineTo(n * 0.64, n * 0.42)
  g.stroke()
}

function drawNight(g, n) {
  g.fillStyle = '#1d2a4a'
  g.beginPath()
  g.arc(n / 2, n / 2, n * 0.46, 0, Math.PI * 2)
  g.fill()
  g.fillStyle = '#f4ecc2'
  g.beginPath()
  g.arc(n * 0.45, n * 0.5, n * 0.24, 0, Math.PI * 2)
  g.fill()
  g.fillStyle = '#1d2a4a'
  g.beginPath()
  g.arc(n * 0.56, n * 0.43, n * 0.22, 0, Math.PI * 2)
  g.fill()
  g.fillStyle = '#ffffff'
  for (const [x, y] of [[0.7, 0.28], [0.76, 0.6], [0.3, 0.24], [0.62, 0.76]]) {
    g.beginPath()
    g.arc(n * x, n * y, n * 0.022, 0, Math.PI * 2)
    g.fill()
  }
}
