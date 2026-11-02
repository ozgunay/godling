import * as THREE from 'three'
import { CSM } from 'three/addons/csm/CSM.js'
import { chooseTier, createResolutionGovernor } from './quality.js'
import { createSky, DEFAULT_SUN, MOON_COLOR, sunForHour } from './sky.js'
import { createSea } from './sea.js'
import { createClouds } from './clouds.js'
import { createModelLibrary, createCharacterController } from './models.js'
import { createInstancer } from './instances.js'
import { createTerrain } from './terrain.js'
import { createFires } from './fire.js'
import { createFishLayer } from './fish.js'
import { bubbleSheet, createBubbles } from './bubble.js'
import { createRain } from './rain.js'
import { createCameraShake } from './shake.js'
import { createDust } from './dust.js'
import { createBlasts } from './blast.js'
import { createWind, swayMaterial } from './wind.js'
import { createFreeCamera } from './freecam.js'
import { createAim } from './aim.js'
import { createReplay } from './replay.js'

// Godling's renderer. three.js is bundled in (build.mjs): nothing loads from a CDN, so the viewer and Godling's
// own camera (the server's capture) keep working offline. Parts are drawn instanced, models load once, and a
// quality tier (quality.js) sets resolution, shadows, sea and clouds for the device.

const COLLIDER_DEBUG_FILL_MATERIAL = new THREE.MeshBasicMaterial({
  color: 0x00d8ff,
  transparent: true,
  opacity: 0.08,
  depthWrite: false,
  depthTest: false,
  toneMapped: false,
})

const COLLIDER_DEBUG_LINE_MATERIAL = new THREE.LineBasicMaterial({
  color: 0x00d8ff,
  transparent: true,
  opacity: 0.95,
  depthTest: false,
  toneMapped: false,
})

function rotationToQuaternion(rot) {
  const m = new THREE.Matrix4()
  m.set(
    rot[0][0], rot[0][1], rot[0][2], 0,
    rot[1][0], rot[1][1], rot[1][2], 0,
    rot[2][0], rot[2][1], rot[2][2], 0,
    0, 0, 0, 1,
  )
  return new THREE.Quaternion().setFromRotationMatrix(m)
}

function resolveEntityModelUrl(entity) {
  if (typeof entity.model_url === 'string' && entity.model_url.length > 0) {
    return entity.model_url
  }
  const attrs = entity.attributes
  if (attrs && typeof attrs.ModelUrl === 'string' && attrs.ModelUrl.length > 0) {
    return attrs.ModelUrl
  }
  return null
}

// Part colours are sRGB, as in Roblox; the rock's has always been read as linear, and the art was checked so.
function resolveEntityColor(entity, linear, out) {
  const color = entity?.render?.color
  if (!Array.isArray(color) || color.length < 3) {
    console.warn(`Entity ${entity?.id ?? '?'} (role=${entity?.render?.role ?? '?'}) missing render.color`)
    return out.setHex(0xff00ff)
  }
  return linear ? out.setRGB(color[0], color[1], color[2]) : out.setRGB(color[0], color[1], color[2], THREE.SRGBColorSpace)
}

function readDebugFlag(name) {
  if (typeof globalThis?.location?.search !== 'string') return false
  const params = new URLSearchParams(globalThis.location.search)
  const raw = params.get(name)
  if (raw == null) return false
  const normalized = raw.trim().toLowerCase()
  return normalized === '' || normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on'
}

function resolveColliderShape(entity) {
  if (typeof entity?.shape === 'string' && entity.shape.length > 0) {
    return entity.shape
  }

  const primitive = typeof entity?.render?.primitive === 'string'
    ? entity.render.primitive.toLowerCase()
    : ''
  if (primitive === 'sphere' || primitive === 'ball') return 'Ball'
  if (primitive === 'cylinder') return 'Cylinder'
  if (primitive === 'wedge') return 'Wedge'

  const role = typeof entity?.render?.role === 'string' ? entity.render.role : ''
  if (role === 'Ring') return 'Ring'
  return 'Block'
}

function createWedgeGeometry(size) {
  const hx = size[0] * 0.5
  const hy = size[1] * 0.5
  const hz = size[2] * 0.5
  const vertices = new Float32Array([
    -hx, -hy, -hz,
    hx, -hy, -hz,
    -hx, -hy, hz,
    hx, -hy, hz,
    -hx, hy, -hz,
    -hx, hy, hz,
  ])
  const indices = [
    0, 1, 2,
    1, 3, 2,
    0, 4, 1,
    2, 3, 5,
    0, 2, 4,
    2, 5, 4,
    1, 4, 3,
    3, 4, 5,
  ]
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3))
  geometry.setIndex(indices)
  geometry.computeVertexNormals()
  return geometry
}

function buildRingSegmentSpecs(size) {
  const outerRadius = Math.min(size[0], size[2]) * 0.5
  const tubeRadius = Math.max(Math.min(size[1] * 0.5, outerRadius * 0.45), 0.05)
  const majorRadius = Math.max(outerRadius - tubeRadius, 0.05)
  const segments = 12
  const segmentLength = Math.max(2 * majorRadius * Math.tan(Math.PI / segments), tubeRadius * 1.5) * 1.08
  const segmentSize = [segmentLength, tubeRadius * 2, tubeRadius * 2]
  const out = []
  for (let index = 0; index < segments; index += 1) {
    const angle = (index / segments) * Math.PI * 2
    out.push({
      position: [Math.cos(angle) * majorRadius, 0, Math.sin(angle) * majorRadius],
      rotationY: -(angle + Math.PI / 2),
      size: segmentSize,
    })
  }
  return out
}

function addColliderDebugPrimitive(parent, geometry, position = [0, 0, 0], quaternion = null) {
  const fill = new THREE.Mesh(geometry, COLLIDER_DEBUG_FILL_MATERIAL)
  fill.renderOrder = 999
  fill.position.set(position[0], position[1], position[2])
  if (quaternion) fill.quaternion.copy(quaternion)
  parent.add(fill)

  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), COLLIDER_DEBUG_LINE_MATERIAL)
  edges.renderOrder = 1000
  edges.position.copy(fill.position)
  if (quaternion) edges.quaternion.copy(quaternion)
  parent.add(edges)
}

function buildColliderDebugKey(entity) {
  const size = Array.isArray(entity?.size) && entity.size.length >= 3 ? entity.size : null
  if (!size) return 'none'
  const shape = resolveColliderShape(entity)
  return `${shape}:${size.map((value) => Number(value).toFixed(3)).join(',')}`
}

function createColliderDebugVisual(entity) {
  const size = Array.isArray(entity?.size) && entity.size.length >= 3 ? entity.size : null
  if (!size) return null

  const shape = resolveColliderShape(entity)
  const group = new THREE.Group()
  group.userData.colliderDebugKey = buildColliderDebugKey(entity)

  if (shape === 'Ball') {
    addColliderDebugPrimitive(group, new THREE.SphereGeometry(size[0] * 0.5, 18, 12))
    return group
  }

  if (shape === 'Cylinder') {
    addColliderDebugPrimitive(group, new THREE.CylinderGeometry(size[0] * 0.5, size[0] * 0.5, size[1], 18, 1, false))
    return group
  }

  if (shape === 'Wedge') {
    addColliderDebugPrimitive(group, createWedgeGeometry(size))
    return group
  }

  if (shape === 'Ring') {
    for (const segment of buildRingSegmentSpecs(size)) {
      const rotation = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), segment.rotationY)
      addColliderDebugPrimitive(
        group,
        new THREE.BoxGeometry(segment.size[0], segment.size[1], segment.size[2]),
        segment.position,
        rotation,
      )
    }
    return group
  }

  addColliderDebugPrimitive(group, new THREE.BoxGeometry(size[0], size[1], size[2]))
  return group
}

// One geometry and one material of each kind for the whole world, shared by every part drawn with them.
function createPartKit(onMaterial) {
  const geometries = new Map()
  const materials = new Map()
  const standard = (options) => () => new THREE.MeshStandardMaterial(options)
  const MATERIALS = {
    plain: standard({ roughness: 0.5, metalness: 0.2 }),
    rock: standard({ roughness: 0.95, metalness: 0.0, flatShading: true }),
    ground: standard({ roughness: 0.5, metalness: 0.2 }), // in the part's colour: grass, or upstream's mint
    sand: standard({ roughness: 0.96, metalness: 0.0 }),
    mesaFoot: standard({ color: 0x8b6940, roughness: 0.9, metalness: 0.0 }),
    mesaMiddle: standard({ color: 0xa57d50, roughness: 0.9, metalness: 0.0 }),
    mesaTop: standard({ color: 0x55cfb0, roughness: 0.9, metalness: 0.0 }),
    // Set light: filmic tone mapping darkens greys a lot (art/README.md).
    rockDark: standard({ color: 0x9a9286, roughness: 0.95, metalness: 0.0 }),
    rockLight: standard({ color: 0xb4ada2, roughness: 0.95, metalness: 0.0 }),
    rockMoss: standard({ color: 0x6da34c, roughness: 0.9, metalness: 0.0 }),
    raft: standard({ roughness: 0.55, metalness: 0.0 }), // rubberised fabric, in the part's colour
    raftFloor: standard({ color: 0x2f3236, roughness: 0.8, metalness: 0.0 }),
    plank: standard({ color: 0x9c6e48, roughness: 0.92, metalness: 0.0 }),
    plankGroove: standard({ color: 0x6f4a2c, roughness: 1.0, metalness: 0.0 }),
    ring: standard({ roughness: 0.82, metalness: 0.12 }),
    // The pieces of the castaway's life (ADR-007), until the art pipeline models them; colours are the parts'.
    sandMark: standard({ roughness: 1.0, metalness: 0.0, vertexColors: true }),
    husk: standard({ roughness: 0.95, metalness: 0.0 }),
    leather: standard({ roughness: 0.6, metalness: 0.0 }),
    seam: standard({ color: 0x8c8a84, roughness: 0.8, metalness: 0.0 }),
    wood: standard({ roughness: 0.85, metalness: 0.0 }),
    freshWood: standard({ color: 0xe0c08e, roughness: 0.8, metalness: 0.0 }),
    fishSkin: standard({ roughness: 0.4, metalness: 0.15 }),
    // A sky event's warning (world/main.lua, PR #3): the shadow of a stone about to land. Unlit, see-through, casts
    // nothing.
    skyShadow: () => new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.45, depthWrite: false }),
    // A meteor's crater, until its model loads (or if it cannot): a scorch on the ground, a dark pit, a ring of
    // thrown-up sand. Drawn a little towards the camera, so the flat marks never flicker against the sand.
    scorch: standard({ color: 0x2a221d, roughness: 1.0, metalness: 0.0, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 }),
    craterPit: standard({ color: 0x16110e, roughness: 1.0, metalness: 0.0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }),
    craterRim: standard({ color: 0x8a7350, roughness: 1.0, metalness: 0.0, flatShading: true }),
  }
  const GEOMETRIES = {
    box: () => new THREE.BoxGeometry(1, 1, 1),
    cylinder: () => new THREE.CylinderGeometry(0.5, 0.5, 1, 16),
    sphere: () => new THREE.SphereGeometry(0.5, 16, 16),
    rock: () => new THREE.DodecahedronGeometry(1, 0),
    disk: () => new THREE.CircleGeometry(0.5, 32).rotateX(-Math.PI / 2),
    // A groove: its floor darker than its rims, so a strip lying on the sand reads as drawn into it.
    groove: () => {
      const box = new THREE.BoxGeometry(1, 1, 1)
      const normals = box.attributes.normal
      const shades = []
      for (let i = 0; i < normals.count; i++) {
        const shade = normals.getY(i) > 0.5 ? 0.78 : normals.getY(i) < -0.5 ? 0.7 : 1.15
        shades.push(shade, shade, shade)
      }
      box.setAttribute('color', new THREE.Float32BufferAttribute(shades, 3))
      return box
    },
    seamRing: () => new THREE.TorusGeometry(0.5, 0.014, 6, 40),
    spearTip: () => new THREE.ConeGeometry(0.5, 1, 8).rotateX(Math.PI / 2), // point along +Z
    tail: () => new THREE.ConeGeometry(0.5, 1, 4).rotateZ(-Math.PI / 2), // point along +X, into the body
    craterRim: () => new THREE.TorusGeometry(0.42, 0.08, 5, 22).rotateX(Math.PI / 2), // lying flat, chunky
  }
  return {
    geometry(key, make = GEOMETRIES[key]) {
      if (!geometries.has(key)) geometries.set(key, make())
      return geometries.get(key)
    },
    material(key) {
      if (!materials.has(key)) {
        const material = MATERIALS[key]()
        onMaterial(material)
        materials.set(key, material)
      }
      return materials.get(key)
    },
    dispose() {
      for (const geometry of geometries.values()) geometry.dispose()
      for (const material of materials.values()) material.dispose()
      geometries.clear()
      materials.clear()
    },
  }
}

const MESA_LAYERS = [
  { frac: 0.0, hFrac: 0.40, material: 'mesaFoot' },
  { frac: 0.40, hFrac: 0.40, material: 'mesaMiddle' },
  { frac: 0.80, hFrac: 0.20, material: 'mesaTop' },
]
const LAND_ROLES = new Set(['Ground', 'Mesa']) // what makes the coastline for the sea's shore map
const STRATUM = 2.5 // rock (Mesa, Surface "Rock") is drawn in block-high strata, as the block grid (ADR-005)
const MOSS = 0.35 // the green cap on rock, as on Monuriki's peak

// Rock: alternating strata of volcanic stone, one block each from the foot, and a cap of moss on top.
function rockParts(size, part, kit) {
  const [w, h, d] = size
  const bottom = -h / 2
  const stoneTop = h / 2 - Math.min(MOSS, h / 2)
  const parts = []
  for (let y = bottom, i = 0; y < stoneTop - 1e-3; y += STRATUM, i += 1) {
    const top = Math.min(y + STRATUM, stoneTop)
    const key = i % 2 ? 'rockLight' : 'rockDark'
    parts.push(part(key, kit.geometry('box'), kit.material(key),
      new THREE.Matrix4().makeScale(w, top - y, d).setPosition(0, (y + top) / 2, 0)))
  }
  parts.push(part('rockMoss', kit.geometry('box'), kit.material('rockMoss'),
    new THREE.Matrix4().makeScale(w, h / 2 - stoneTop, d).setPosition(0, (stoneTop + h / 2) / 2, 0)))
  return parts
}

// A busted inflatable life raft, from its part's size and colour: a ring of fat tubes with rounded corners round a
// dark floor, the side facing -Z gone flat.
function lifeRaftParts(size, part, kit) {
  const [w, h, d] = size
  const r = Math.max(0.15, Math.min(h * 0.45, d * 0.2, w * 0.2))
  const y = -h / 2 + r
  const lengthX = Math.max(0.01, w - 2 * r)
  const lengthZ = Math.max(0.01, d - 2 * r)
  const flat = 0.45 // how much of its height the deflated side keeps
  const tube = (x, z, length, alongX, squash) => {
    const sag = (1 - squash) * r
    const turn = alongX ? new THREE.Matrix4().makeRotationZ(Math.PI / 2) : new THREE.Matrix4().makeRotationX(Math.PI / 2)
    // In the cylinder's own frame the length is Y; after the turn its local X (along X) or Z (along Z) is upright.
    const scale = alongX ? [2 * r * squash, length, 2 * r] : [2 * r, length, 2 * r * squash]
    const local = new THREE.Matrix4().makeTranslation(x, y - sag, z).multiply(turn).multiply(new THREE.Matrix4().makeScale(...scale))
    return part('raftTube', kit.geometry('cylinder'), kit.material('raft'), local, { colored: true })
  }
  const corner = (x, z, squash) => part('raftCorner', kit.geometry('sphere'), kit.material('raft'),
    new THREE.Matrix4().makeTranslation(x, y - (1 - squash) * r, z).multiply(new THREE.Matrix4().makeScale(2 * r, 2 * r * squash, 2 * r)),
    { colored: true })
  const ex = w / 2 - r
  const ez = d / 2 - r
  return [
    part('raftFloor', kit.geometry('box'), kit.material('raftFloor'),
      new THREE.Matrix4().makeScale(lengthX + r, Math.min(0.12, h * 0.1), lengthZ + r).setPosition(0, -h / 2 + 0.06, 0)),
    tube(0, ez, lengthX, true, 1),
    tube(0, -ez, lengthX, true, flat),
    tube(ex, 0, lengthZ, false, 1),
    tube(-ex, 0, lengthZ, false, 0.8),
    corner(ex, ez, 1),
    corner(-ex, ez, 0.9),
    corner(ex, -ez, 0.7),
    corner(-ex, -ez, flat),
  ]
}

// A small on-screen readout for `?stats=1`: frame rate, draw calls, triangles, tier and resolution.
function createStatsReadout(canvas, renderer, tier, instancer) {
  const box = document.createElement('div')
  box.style.cssText = 'position:absolute;left:8px;top:8px;z-index:10;padding:4px 7px;border-radius:4px;' +
    'background:rgba(0,0,0,.55);color:#e8fff6;font:11px/1.35 ui-monospace,monospace;pointer-events:none;white-space:pre'
  ;(canvas.parentElement || document.body).appendChild(box)
  let time = 0
  let frames = 0
  return {
    tick(dt) {
      time += dt
      frames += 1
      if (time < 0.5) return
      const { calls, triangles } = renderer.info.render
      const { groups, instances } = instancer.stats()
      box.textContent = `${Math.round(frames / time)} fps · ${calls} calls · ${(triangles / 1000).toFixed(1)}k tris\n` +
        `${tier.name} (${tier.reason}) · px ${renderer.getPixelRatio().toFixed(2)} · ${instances} parts in ${groups} groups`
      time = 0
      frames = 0
    },
    dispose() {
      box.remove()
    },
  }
}

export function createRenderer(ctx) {
  const scene = new THREE.Scene()
  const captureConfig = globalThis.__mesaCaptureConfig && typeof globalThis.__mesaCaptureConfig === 'object'
    ? globalThis.__mesaCaptureConfig
    : {}
  const debugCollidersEnabled = Boolean(captureConfig.debugColliders) || readDebugFlag('debugColliders') || readDebugFlag('debugCollider')
  const params = new URLSearchParams(globalThis.location?.search || '')

  const tier = chooseTier(captureConfig)
  const governor = createResolutionGovernor(tier)
  ctx.log('info', 'Renderer quality', { tier: tier.name, reason: tier.reason, gpu: tier.gpu })

  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 3000)

  const renderer = new THREE.WebGLRenderer({ canvas: ctx.canvas, antialias: tier.antialias, powerPreference: 'high-performance' })
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.2
  renderer.outputColorSpace = THREE.SRGBColorSpace
  let viewport = { width: 1, height: 1, dpr: globalThis.devicePixelRatio || 1 }
  const applyResolution = () => {
    renderer.setPixelRatio(Math.min(viewport.dpr, tier.pixelRatio) * governor.scale)
    renderer.setSize(viewport.width, viewport.height, false)
  }

  // Lights. By day at the default sun they are as before this renderer had a sky, so the props' colours, which
  // were checked in the game, still hold; the sky only changes them at other times of day.
  const ambient = new THREE.AmbientLight(0xffffff, 0.6)
  const hemisphere = new THREE.HemisphereLight(0x87ceeb, 0x98fb98, 0.4)
  scene.add(ambient, hemisphere)
  const SKY_BLUE = new THREE.Color(0x87ceeb)
  const GRASS_BOUNCE = new THREE.Color(0x98fb98)
  const WHITE = new THREE.Color(1, 1, 1)
  const NIGHT_AMBIENT = new THREE.Color(0.55, 0.64, 0.95) // nights are blue, and still readable
  const NIGHT_GROUND = new THREE.Color(0.12, 0.14, 0.2)
  const ramp = (a, b, v) => {
    const t = Math.min(1, Math.max(0, (v - a) / (b - a)))
    return t * t * (3 - 2 * t)
  }
  const light = { direction: DEFAULT_SUN, color: WHITE, intensity: 1.2, glint: 6 } // the sun's or the moon's

  // The sun's shadows: one map around the camera's target, or cascades (high tier) that stay sharp up close.
  const csm = tier.cascades > 0
    ? new CSM({
      camera,
      parent: scene,
      cascades: tier.cascades,
      maxFar: 240,
      mode: 'practical',
      shadowMapSize: tier.shadowMapSize,
      lightDirection: DEFAULT_SUN.clone().negate(),
      lightIntensity: 1.2,
      lightNear: 1,
      lightFar: 800,
      lightMargin: 120,
    })
    : null
  if (csm) {
    csm.fade = true
    for (const light of csm.lights) {
      light.shadow.bias = -0.0002
      light.shadow.normalBias = 0.03
      light.shadow.radius = tier.shadowRadius
    }
  }
  const sunLight = new THREE.DirectionalLight(0xffffff, 1.2)
  if (!csm) {
    sunLight.castShadow = true
    sunLight.shadow.mapSize.set(tier.shadowMapSize, tier.shadowMapSize)
    sunLight.shadow.camera.left = -tier.shadowExtent
    sunLight.shadow.camera.right = tier.shadowExtent
    sunLight.shadow.camera.top = tier.shadowExtent
    sunLight.shadow.camera.bottom = -tier.shadowExtent
    sunLight.shadow.camera.near = 1
    sunLight.shadow.camera.far = 260
    sunLight.shadow.bias = -0.0001
    // Pushed out by most of a shadow texel, or curved surfaces speckle with their own shadow (shadow acne).
    sunLight.shadow.normalBias = ((tier.shadowExtent * 2) / tier.shadowMapSize) * 0.75
    sunLight.shadow.radius = tier.shadowRadius
    scene.add(sunLight, sunLight.target)
  }
  const litMaterials = new Set()
  const onMaterial = (material) => {
    for (const m of Array.isArray(material) ? material : [material]) {
      if (!m || litMaterials.has(m) || !(m.isMeshStandardMaterial || m.isMeshPhongMaterial || m.isMeshLambertMaterial)) continue
      litMaterials.add(m)
      csm?.setupMaterial(m)
    }
  }

  const sky = createSky(scene, tier)
  scene.fog = new THREE.Fog(sky.fogColor.clone(), tier.fogFar * 0.32, tier.fogFar)
  const sea = createSea(scene, tier, sky)
  const clouds = createClouds(scene, tier)
  const terrain = createTerrain(scene, { onMaterial })
  const fires = createFires(scene, tier)
  const fish = createFishLayer(scene)
  // The world's weather (ADR-010): the Clock's Rain, 0 to 1, eased in and out here. `?rain=1` forces it, to look.
  const rain = createRain(scene, tier)
  const wind = createWind(params) // bends the rain, sways the palms
  const forcedRain = params.has('rain') ? Number(params.get('rain')) : NaN
  let worldRain = Number.isFinite(forcedRain) ? forcedRain : 0
  let rainNow = worldRain
  const RAIN_GREY = new THREE.Color(0x8b939c)
  const RAIN_FOG = new THREE.Color()
  // Morning fog from the sea (the Clock's Fog, 0 to 1): the view closes in and goes milky. `?fog=1` forces it.
  const forcedFog = params.has('fog') ? Number(params.get('fog')) : NaN
  let worldFog = Number.isFinite(forcedFog) ? forcedFog : 0
  let fogNow = worldFog
  const FOG_WHITE = new THREE.Color(0xd3d8dc)
  const FOG_NEAR = scene.fog.near
  const FOG_FAR = scene.fog.far
  // Earthquakes: the Clock's Quake (0 to 1) shakes the camera, and QuakePhase names the stage. `?quake=0.8` forces it.
  // Dust rises where loose pieces land or, in a quake, slide.
  const shake = createCameraShake(tier)
  const dust = createDust(scene, tier)
  // Meteors: the blast where one lands (a Blast_<n> marker), and the trail of one falling (blast.js).
  const blasts = createBlasts(scene, tier, { onMaterial })
  const forcedQuake = params.has('quake') ? Number(params.get('quake')) : NaN
  let worldQuake = Number.isFinite(forcedQuake) ? forcedQuake : 0
  let quakeNow = worldQuake
  let quakePhase = ''
  let lastSeaLevel = null

  // Time of day: `?time=17.5` holds the sun at that hour; `?dayMinutes=20` runs a whole day in 20 minutes.
  // Without either the sun stands where the light always stood.
  const fixedHour = params.has('time') ? Number(params.get('time')) : NaN
  const dayMinutes = Number(params.get('dayMinutes'))
  const startHour = Number.isFinite(fixedHour) ? fixedHour : 9
  let sunClock = 0
  let sunPlaced = false
  // The world's own clock, when it keeps one: an entity with a TimeOfDay attribute (Godling's day and night,
  // ADR-007). The URL settings above still win, for looking at a chosen hour.
  let worldHour = NaN
  const sunNow = (time) => {
    if (dayMinutes > 0) return sunForHour((startHour + (time / (dayMinutes * 60)) * 24) % 24)
    if (Number.isFinite(fixedHour)) return sunForHour(fixedHour)
    if (Number.isFinite(worldHour)) return sunForHour(worldHour)
    return DEFAULT_SUN
  }

  const interpolationDelayMs = Number.isFinite(captureConfig.interpolationDelayMs)
    ? Math.max(0, Number(captureConfig.interpolationDelayMs))
    : 100
  const followPositionSmoothing = Number.isFinite(captureConfig.followPositionSmoothing)
    ? Math.max(0, Number(captureConfig.followPositionSmoothing))
    : 10
  const followRotationSmoothing = Number.isFinite(captureConfig.followRotationSmoothing)
    ? Math.max(0, Number(captureConfig.followRotationSmoothing))
    : 14

  const stateBuffer = ctx.runtime.state.createSnapshotBuffer({ maxSnapshots: 8, interpolationDelayMs })
  const cameraModes = ctx.runtime.three.createCameraModeController(THREE, camera, {
    canvas: ctx.canvas,
    stateBuffer,
    debugCamera: false,
    follow: {
      followDistance: 20,
      followHeight: 6,
      shoulderOffset: 0,
      positionSmoothing: followPositionSmoothing,
      rotationSmoothing: followRotationSmoothing,
    },
    spectatorOffset: new THREE.Vector3(0, 18, -18),
    spectatorBoundsPadding: 8,
  })
  if (cameraModes?.api && ctx.runtime?.internal?.expose) {
    ctx.runtime.internal.expose('camera', cameraModes.api)
  }
  // With nobody followed, our own free camera flies (freecam.js). Inside the viewer screen (?embed=1, world/viewer)
  // the page around the island is hidden and the screen picks the camera: follow Godling, or fly free with the keys
  // it forwards.
  const freeCam = createFreeCamera(THREE, camera, ctx.canvas)
  const embedded = params.get('embed') === '1' && globalThis.parent !== globalThis
  let cameraWish = embedded ? 'follow' : null
  // Aiming a sky power (aim.js): the screen says which power; the ring follows the pointer; the spot goes back.
  const godlingAt = new THREE.Vector3()
  let godlingSeen = false
  const tellScreen = (message) => globalThis.parent.postMessage({ source: 'godling-renderer', ...message }, '*')
  const aim = embedded ? createAim(THREE, scene, camera, ctx.canvas, {
    godling: () => (godlingSeen ? godlingAt : null),
    onHover: (spot) => tellScreen({ type: 'godling-aim-hover', ...spot }),
    onAimed: (spot) => tellScreen({ type: 'godling-aimed', ...spot }),
    onCancel: () => tellScreen({ type: 'godling-aim-cancel' }),
  }) : null
  if (embedded) {
    const style = document.createElement('style')
    style.textContent = 'body * { visibility: hidden !important; } canvas { visibility: visible !important; }'
    document.head.append(style)
    addEventListener('message', (event) => {
      const data = event.data
      if (event.source !== globalThis.parent || data?.source !== 'godling-viewer') return
      if (data.type === 'godling-camera') cameraWish = data.mode === 'free' ? 'free' : 'follow'
      else if (data.type === 'godling-key') freeCam.key(String(data.code), Boolean(data.down))
      else if (data.type === 'godling-aim') (data.power ? aim.start(String(data.power)) : aim.stop())
      else if (data.type === 'godling-replay') replay?.command(data)
    })
  }

  // Entities whose look changes when a model arrives are rebuilt; the runtime's replay waits for tracked loads
  // (patched Clawblox exports trackAssetLoad; upstream keeps it private, and then models are simply untracked).
  let modelsArrived = 0
  const models = createModelLibrary({
    onReady(url) {
      modelsArrived += 1
      if (/palm\.glb(\?|$)/.test(url)) { // the palms sway in the wind
        for (const part of models.get(url)?.parts || []) {
          for (const material of [].concat(part.material)) swayMaterial(material, wind.uniforms)
        }
      }
    },
    onError(err, meta) {
      ctx.log('warn', 'Model load failed', { err: String(err), ...meta })
    },
    trackLoad: ctx.runtime?.three?.trackAssetLoad,
    onMaterial,
  })
  const characters = createCharacterController(models)
  // The runtime serves asset://name.glb from the folder it puts in each entity's model_url: learn it from one of them.
  let assetBase = null
  const resolveAsset = (url) => (url.startsWith('asset://') ? (assetBase === null ? null : assetBase + url.slice(8)) : url)
  // The island's past, when the screen asks for it (ADR-016): its frames go into the same buffer the live ones do, so
  // the camera follows Godling in replay as it does live.
  const replay = embedded ? createReplay({
    onFrame: (obs) => stateBuffer.push(obs),
    onReset: () => stateBuffer.clear(),
    tell: tellScreen,
    assetBase: () => assetBase,
  }) : null
  const bubbles = createBubbles(scene, models, resolveAsset)
  const instancer = createInstancer(scene)
  const kit = createPartKit(onMaterial)
  const records = new Map() // entity id -> how it is drawn
  const colliderDebugObjects = new Map()
  const stats = readDebugFlag('stats') ? createStatsReadout(ctx.canvas, renderer, tier, instancer) : null

  const tmpForward = new THREE.Vector3(0, 0, 1)
  const anchorPos = new THREE.Vector3(0, 4, 0)
  const entityMatrix = new THREE.Matrix4()
  const partMatrix = new THREE.Matrix4()
  const color = new THREE.Color()
  let lastStateMs = performance.now()
  let elapsed = 0
  let latestObs = null

  function syncColliderDebug(entity, visible) {
    if (!debugCollidersEnabled) return

    const debugKey = buildColliderDebugKey(entity)
    let debugObj = colliderDebugObjects.get(entity.id)
    if (!debugObj || debugObj.userData.colliderDebugKey !== debugKey) {
      if (debugObj) {
        scene.remove(debugObj)
        colliderDebugObjects.delete(entity.id)
      }
      debugObj = createColliderDebugVisual(entity)
      if (debugObj) {
        colliderDebugObjects.set(entity.id, debugObj)
        scene.add(debugObj)
      }
    }

    if (!debugObj) return
    debugObj.position.set(entity.position[0], entity.position[1], entity.position[2])
    if (entity.rotation) debugObj.quaternion.copy(rotationToQuaternion(entity.rotation))
    else debugObj.quaternion.identity()
    debugObj.visible = visible
  }

  // What an entity is drawn with: instanced parts (each a group key, geometry, material and a transform inside
  // the entity), an animated character, the sea's level, or nothing yet (its model is still loading).
  function describe(entity) {
    const role = (entity.render && entity.render.role) || entity.name || ''
    const size = entity.size || [1, 1, 1]
    const modelUrl = resolveEntityModelUrl(entity)
    const part = (key, geometry, material, local, extra = {}) => ({ key, geometry, material, local, ...extra })

    // A model that cannot load (a missing file) leaves the part drawn as if it had none, below.
    if (modelUrl && !models.failed(modelUrl)) {
      const template = models.get(modelUrl)
      if (!template) return { kind: 'pending' }
      if (template.animated) return { kind: 'character', modelUrl }
      const fit = models.fit(template, size, entity.model_yaw_offset_deg, new THREE.Matrix4(), role === 'Crater')
      return {
        kind: 'parts',
        parts: template.parts.map((p, i) =>
          part(`model:${modelUrl}#${i}`, p.geometry, p.material, fit.clone().multiply(p.matrix))),
        swims: role === 'Fish', // a swimming fish's model rides the waves, half under (see updateScene)
      }
    }

    const scaled = (x, y, z) => new THREE.Matrix4().makeScale(x, y, z)
    switch (role) {
      case 'Ocean':
        return { kind: 'sea' }
      case 'Ground': {
        const surface = entity.attributes?.Surface === 'Sand' ? 'sand' : 'ground'
        return { kind: 'parts', parts: [part(surface, kit.geometry('box'), kit.material(surface), scaled(...size), { colored: true })] }
      }
      case 'Wreck':
        return { kind: 'parts', parts: lifeRaftParts(size, part, kit) }
      case 'Mesa':
        if (entity.attributes?.Surface === 'Rock') return { kind: 'parts', parts: rockParts(size, part, kit) }
        return {
          kind: 'parts',
          parts: MESA_LAYERS.map((layer) => {
            const lh = size[1] * layer.hFrac
            const local = scaled(size[0], lh, size[2]).setPosition(0, -size[1] / 2 + size[1] * layer.frac + lh / 2, 0)
            return part(layer.material, kit.geometry('box'), kit.material(layer.material), local)
          }),
        }
      case 'Rock': {
        const r = Math.max(size[0], size[1], size[2]) / 2
        return { kind: 'parts', parts: [part('rock', kit.geometry('rock'), kit.material('rock'), scaled(r, r, r), { colored: true, linear: true })] }
      }
      case 'Plank':
        return {
          kind: 'parts',
          parts: [
            part('plank', kit.geometry('box'), kit.material('plank'), scaled(...size)),
            ...[-0.28, 0, 0.28].map((zFrac) => part('plankGroove', kit.geometry('box'), kit.material('plankGroove'),
              scaled(size[0] * 0.96, size[1] * 0.12, size[2] * 0.08).setPosition(0, size[1] * 0.18, size[2] * zFrac))),
          ],
        }
      case 'Ring': {
        const outerRadius = Math.min(size[0], size[2]) * 0.5
        const tubeRadius = Math.max(Math.min(size[1] * 0.5, outerRadius * 0.45), 0.05)
        const ringRadius = Math.max(outerRadius - tubeRadius, 0.05)
        const key = `ring:${ringRadius.toFixed(3)}:${tubeRadius.toFixed(3)}`
        const geometry = kit.geometry(key, () => new THREE.TorusGeometry(ringRadius, tubeRadius, 18, 40).rotateX(Math.PI / 2))
        return { kind: 'parts', parts: [part(key, geometry, kit.material('ring'), new THREE.Matrix4(), { colored: true })] }
      }
      case 'SkyShadow':
        return { kind: 'parts', parts: [part('skyShadow', kit.geometry('disk'), kit.material('skyShadow'), scaled(size[0], 1, size[2]), { castShadow: false })] }
      case 'Blast': // a meteor's contact point: its explosion is drawn by blast.js, the part itself never
        return { kind: 'none' }
      case 'Crater': { // lying on the ground, its foot on it (as crater.glb, whose base is the ground)
        const [w, h, d] = size
        return {
          kind: 'parts',
          parts: [
            part('scorch', kit.geometry('disk'), kit.material('scorch'), scaled(w * 1.2, 1, d * 1.2).setPosition(0, -h / 2 + 0.02, 0), { castShadow: false }),
            part('craterPit', kit.geometry('disk'), kit.material('craterPit'), scaled(w * 0.7, 1, d * 0.7).setPosition(0, -h / 2 + 0.03, 0), { castShadow: false }),
            part('craterRim', kit.geometry('craterRim'), kit.material('craterRim'), scaled(w, h / 0.16, d).setPosition(0, -h / 2 + h * 0.3, 0)),
          ],
        }
      }
      case 'SkyNote': { // a viewer's note folded into a paper glider (main.lua sky.notes): two wings in a shallow V
        const [l, h, w] = size
        return {
          kind: 'parts',
          parts: [-1, 1].map((side) => part('noteWing', kit.geometry('box'), kit.material('plain'),
            new THREE.Matrix4().makeRotationX(side * 0.32).multiply(scaled(l, h * 0.35, w * 0.5)).setPosition(0, 0, side * w * 0.24),
            { colored: true })),
        }
      }
      case 'PickupObject':
        return { kind: 'parts', parts: [part('block', kit.geometry('box'), kit.material('rock'), scaled(...size), { colored: true })] }
      // The castaway's life (ADR-007). A ModelUrl, once the art pipeline makes one, is drawn instead (above).
      case 'Fire':
        return { kind: 'fire' }
      case 'Fish':
        return { kind: 'fish' }
      case 'SandMark': // half its height, lying on the sand: a groove more than a ribbon
        return {
          kind: 'parts',
          parts: [part('sandMark', kit.geometry('groove'), kit.material('sandMark'),
            scaled(size[0], size[1] / 2, size[2]).setPosition(0, -size[1] / 4, 0), { colored: true })],
        }
      case 'Coconut':
        return { kind: 'parts', parts: [part('coconut', kit.geometry('sphere'), kit.material('husk'), scaled(size[0], size[0] * 0.92, size[0]), { colored: true })] }
      case 'Volleyball': {
        const d = size[0]
        const ring = (turn) => part('seam', kit.geometry('seamRing'), kit.material('seam'), turn.multiply(scaled(d * 1.01, d * 1.01, d * 1.01)))
        return {
          kind: 'parts',
          parts: [
            part('volleyball', kit.geometry('sphere'), kit.material('leather'), scaled(d, d, d), { colored: true }),
            ring(new THREE.Matrix4()),
            ring(new THREE.Matrix4().makeRotationY(Math.PI / 2)),
            ring(new THREE.Matrix4().makeRotationX(Math.PI / 2)),
          ],
        }
      }
      case 'Catch': { // a fish lying on its side on the sand: nose at +X, its back along Z
        const [l, h, w] = size
        const fixed = entity.attributes?.Cooked ? 0x8b5a2b : null // cooked over a fire: browned
        return {
          kind: 'parts',
          parts: [
            part('catchBody', kit.geometry('sphere'), kit.material('fishSkin'), scaled(l * 0.78, h, w).setPosition(l * 0.1, 0, 0), { colored: true, fixed }),
            part('catchTail', kit.geometry('tail'), kit.material('fishSkin'), scaled(l * 0.3, h * 0.18, w * 1.15).setPosition(-l * 0.35, 0, 0), { colored: true, fixed }),
          ],
        }
      }
      default: {
        const primitive = entity.render && entity.render.primitive
        if (role === 'Tool' && entity.attributes?.ToolKind === 'Spear') { // a carved log: a shaft and a pale point at +Z
          const [, , l] = size
          const r = Math.min(size[0], size[1]) * 0.55
          return {
            kind: 'parts',
            parts: [
              part('spearShaft', kit.geometry('cylinder'), kit.material('wood'),
                new THREE.Matrix4().makeRotationX(Math.PI / 2).multiply(scaled(r, l * 0.86, r)).setPosition(0, 0, -l * 0.07), { colored: true }),
              part('spearTip', kit.geometry('spearTip'), kit.material('freshWood'), scaled(r, r, l * 0.14).setPosition(0, 0, l * 0.43)),
            ],
          }
        }
        if (primitive === 'cylinder') {
          return { kind: 'parts', parts: [part('cylinder', kit.geometry('cylinder'), kit.material('plain'), scaled(size[0], size[1], size[0]), { colored: true })] }
        }
        if (primitive === 'sphere' || primitive === 'ball') { // a Ball part's primitive is "ball"
          return { kind: 'parts', parts: [part('sphere', kit.geometry('sphere'), kit.material('plain'), scaled(size[0], size[0], size[0]), { colored: true })] }
        }
        return { kind: 'parts', parts: [part('plain', kit.geometry('box'), kit.material('plain'), scaled(...size), { colored: true })] }
      }
    }
  }

  function lookKey(entity) {
    const modelUrl = resolveEntityModelUrl(entity)
    const visible = !(entity.render && (entity.render.visible === false || entity.render.transparency >= 0.999))
    return [
      entity.render?.role || entity.name || '',
      entity.attributes?.Surface || '',
      entity.attributes?.ToolKind || '',
      entity.attributes?.Cooked ? 'cooked' : '',
      entity.render?.primitive || '',
      modelUrl || '',
      modelUrl && models.get(modelUrl) ? 'loaded' : modelUrl && models.failed(modelUrl) ? 'failed' : '',
      (entity.size || []).join(','),
      entity.model_yaw_offset_deg ?? '',
      visible ? 'shown' : 'hidden',
    ].join('|')
  }

  function release(record) {
    for (const slot of record.slots || []) instancer.remove(slot.slot)
    if (record.kind === 'fire') fires.remove(record.id)
    if (record.root) {
      scene.remove(record.root)
      characters.remove(record.id)
    }
  }

  function build(entity, key) {
    const record = { id: entity.id, key, kind: 'none', slots: [], position: null, rotation: null, color: null }
    if (key.endsWith('|hidden')) return record
    const look = describe(entity)
    record.kind = look.kind
    record.swims = Boolean(look.swims)
    if (look.kind === 'parts') {
      for (const p of look.parts) {
        const group = instancer.group(p.key, p.geometry, p.material, { colored: Boolean(p.colored), castShadow: p.castShadow !== false })
        record.slots.push({
          slot: instancer.add(group, entityMatrix), local: p.local, linear: Boolean(p.linear), colored: Boolean(p.colored), fixed: p.fixed ?? null,
        })
      }
    } else if (look.kind === 'fire') {
      fires.add(entity.id)
    } else if (look.kind === 'character') {
      record.root = new THREE.Group()
      record.modelUrl = look.modelUrl
      scene.add(record.root)
    }
    return record
  }

  const sameNumbers = (a, b) => {
    if (a === b) return true
    if (!a || !b || a.length !== b.length) return false
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
    return true
  }

  function computeAnchorPosition(obs) {
    let count = 0
    let sumX = 0
    let sumY = 0
    let sumZ = 0
    const pushPos = (pos) => {
      if (!Array.isArray(pos)) return
      const x = Number(pos[0])
      const y = Number(pos[1])
      const z = Number(pos[2])
      if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) return
      sumX += x
      sumY += y
      sumZ += z
      count += 1
    }
    for (const player of obs.players || []) pushPos(player?.position)
    for (const entity of obs.entities || []) pushPos(entity?.position)
    if (count === 0) return anchorPos.clone()
    return new THREE.Vector3(sumX / count, sumY / count, sumZ / count)
  }

  // Returns the sea level and the island's footprint for the sea.
  function updateScene(obs, dt) {
    const activeIds = new Set()
    const stateByRootPartId = new Map()
    const attributesByRootPartId = new Map()
    for (const player of obs.players || []) {
      if (typeof player.root_part_id === 'number' && typeof player.humanoid_state === 'string') {
        stateByRootPartId.set(player.root_part_id, player.humanoid_state)
      }
      if (typeof player.root_part_id === 'number') {
        attributesByRootPartId.set(player.root_part_id, player.attributes || {})
      }
    }

    // A first-person camera (the server's capture of what Godling sees) sits inside the body's head: hide that
    // body, or its own head fills the view.
    const attach = cameraModes?.spectator?.state?.attach
    const attachedPlayer = attach ? (obs.players || []).find((p) => String(p?.id || '') === attach.playerId) : null
    const hiddenBodyId = attachedPlayer?.root_part_id ?? null

    let seaLevel = null
    const land = []
    const landKey = []
    const swimming = []

    for (const entity of obs.entities || []) {
      activeIds.add(entity.id)
      const served = entity.model_url
      if (assetBase === null && typeof served === 'string' && served.endsWith('.glb') && !served.startsWith('asset://')) {
        assetBase = served.slice(0, served.lastIndexOf('/') + 1) // all the world's models sit in one folder
      }
      const hour = Number(entity.attributes?.TimeOfDay)
      if (Number.isFinite(hour)) worldHour = hour
      const rainFall = Number(entity.attributes?.Rain)
      if (Number.isFinite(rainFall) && !Number.isFinite(forcedRain)) worldRain = rainFall
      if (entity.attributes?.WindX !== undefined) wind.read(entity.attributes)
      const mist = Number(entity.attributes?.Fog)
      if (Number.isFinite(mist) && !Number.isFinite(forcedFog)) worldFog = mist
      const quake = Number(entity.attributes?.Quake)
      if (Number.isFinite(quake) && !Number.isFinite(forcedQuake)) {
        worldQuake = quake
        quakePhase = String(entity.attributes?.QuakePhase ?? '')
      }
      blasts.watch(entity, dt)
      const key = lookKey(entity)
      let record = records.get(entity.id)
      if (!record || record.key !== key) {
        if (record) release(record)
        record = build(entity, key)
        records.set(entity.id, record)
      }
      const shown = !key.endsWith('|hidden')
      syncColliderDebug(entity, shown)

      const position = entity.position
      const rotation = entity.rotation || null
      const moved = !sameNumbers(record.position, position) ||
        !(record.rotation === rotation || (record.rotation && rotation && record.rotation.every((row, i) => sameNumbers(row, rotation[i]))))

      if (record.kind === 'sea') {
        seaLevel = position[1] + (entity.size?.[1] ?? 0) / 2
      } else if (record.kind === 'fish' || record.swims) {
        swimming.push({ id: entity.id, position, rotation, size: entity.size, modelled: record.swims })
      } else if (record.kind === 'fire') {
        fires.place(entity.id, position, entity.size)
      }
      const role = entity.render?.role
      if (shown && LAND_ROLES.has(role) && entity.size) {
        land.push({ center: position, half: entity.size.map((v) => v / 2), rotation })
        landKey.push(`${entity.id}:${position.join(',')}:${entity.size.join(',')}`)
      }

      if (record.kind === 'parts' && !record.swims && shown) {
        dust.watch(entity, dt, quakeNow, lastSeaLevel)
      }
      if (record.kind === 'parts') {
        if (moved || record.fresh !== false || record.swims) {
          // A swimming fish sits on the water as it is drawn now, its back out and its belly under.
          const water = record.swims ? sea.surfaceAt(position[0], position[2]) : null
          const y = water == null ? position[1] : water + 0.02
          if (rotation) {
            entityMatrix.set(
              rotation[0][0], rotation[0][1], rotation[0][2], position[0],
              rotation[1][0], rotation[1][1], rotation[1][2], y,
              rotation[2][0], rotation[2][1], rotation[2][2], position[2],
              0, 0, 0, 1,
            )
          } else {
            entityMatrix.makeTranslation(position[0], y, position[2])
          }
          for (const s of record.slots) instancer.setMatrix(s.slot, partMatrix.multiplyMatrices(entityMatrix, s.local))
        }
        const colorKey = entity.render?.color ? entity.render.color.join(',') : ''
        if (colorKey !== record.color) {
          for (const s of record.slots) {
            if (s.colored) instancer.setColor(s.slot, s.fixed != null ? color.setHex(s.fixed) : resolveEntityColor(entity, s.linear, color))
          }
          record.color = colorKey
        }
      } else if (record.kind === 'character') {
        const root = record.root
        root.position.set(position[0], position[1], position[2])
        if (rotation) root.quaternion.copy(rotationToQuaternion(rotation))
        else root.quaternion.identity()
        root.visible = entity.id !== hiddenBodyId

        let speed = 0
        const prev = record.prevPos
        if (prev) {
          const dx = position[0] - prev[0]
          const dz = position[2] - prev[2]
          speed = Math.sqrt(dx * dx + dz * dz) / Math.max(dt, 0.001)
        }
        record.prevPos = [position[0], position[1], position[2]]
        characters.upsert({
          entityId: entity.id,
          root,
          modelUrl: record.modelUrl,
          size: entity.size || [2, 5, 2],
          yawOffsetDeg: entity.model_yaw_offset_deg,
        })
        characters.update(entity.id, {
          dt,
          speed,
          humanoidState: stateByRootPartId.get(entity.id) || null,
          attributes: attributesByRootPartId.get(entity.id) || {},
        })
        bubbles.update(entity.id, position, attributesByRootPartId.get(entity.id) || {}, entity.id === hiddenBodyId, dt)
      }
      record.fresh = false
      if (moved) {
        // Copies: the snapshot buffer may hand over the same arrays again with new numbers in them.
        record.position = position.slice()
        record.rotation = rotation ? rotation.map((row) => row.slice()) : null
      }
    }

    for (const [id, record] of records.entries()) {
      if (!activeIds.has(id)) {
        release(record)
        records.delete(id)
      }
    }
    bubbles.prune(activeIds)
    dust.prune(activeIds)
    blasts.prune(activeIds)
    for (const [id, obj] of colliderDebugObjects.entries()) {
      if (!activeIds.has(id)) {
        scene.remove(obj)
        colliderDebugObjects.delete(id)
      }
    }

    terrain.update(obs.terrain)
    if (seaLevel != null && obs.terrain) {
      const fromTerrain = terrain.landAt(seaLevel)
      land.push(...fromTerrain.boxes)
      landKey.push(fromTerrain.key)
    }

    const players = obs.players || []
    const selectedId = obs && obs.selected_player_id ? String(obs.selected_player_id) : null
    const selectedTarget = selectedId
      ? players.find((player) => String(player?.id || '') === selectedId)
      : null
    const godling = players.find((player) => player?.name === 'Godling') || players.find((player) => player?.name !== 'Sky')
    godlingSeen = Array.isArray(godling?.position)
    if (godlingSeen) godlingAt.set(godling.position[0], godling.position[1], godling.position[2])
    const followTarget = cameraWish === 'free' ? null : cameraWish === 'follow' ? godling || null : selectedTarget || null
    const cameraTarget = followTarget && Array.isArray(followTarget.position)
      ? new THREE.Vector3(followTarget.position[0], followTarget.position[1], followTarget.position[2])
      : computeAnchorPosition(obs)
    const cameraMode = followTarget ? 'follow' : 'spectator'

    anchorPos.copy(cameraTarget)
    if (cameraMode === 'spectator') {
      freeCam.enter(cameraTarget)
      freeCam.update(dt)
    } else {
      freeCam.leave()
      cameraModes.update({
        mode: cameraMode,
        targetPosition: cameraTarget,
        targetForward: tmpForward,
        dt,
      })
    }

    return { seaLevel, land, landKey: landKey.join(';'), cameraTarget, swimming }
  }

  function updateSunAndLights(dt, cameraTarget) {
    sunClock += dt
    if (!sunPlaced || ((dayMinutes > 0 || Number.isFinite(worldHour)) && sunClock >= 0.5)) {
      sky.setSun(sunNow(elapsed))
      sunPlaced = true
      sunClock = 0
    }
    const day = sky.daylight
    const night = sky.night
    // By night the sun's light is the moon's: cool and dim, from where the moon stands, fading in after dusk.
    const moonlit = sky.sun.y < -0.02
    light.direction = moonlit ? sky.moon : sky.sun
    light.color = moonlit ? MOON_COLOR : sky.sunColor
    light.intensity = moonlit ? 0.34 * ramp(-0.02, -0.2, sky.sun.y) : 1.2 * day
    light.glint = moonlit ? 2.5 * ramp(-0.02, -0.2, sky.sun.y) : 6 * day
    ambient.color.copy(WHITE).lerp(NIGHT_AMBIENT, night)
    ambient.intensity = 0.6 * (0.3 + 0.7 * day)
    hemisphere.color.copy(SKY_BLUE).lerp(sky.zenith, 0.35)
    hemisphere.groundColor.copy(GRASS_BOUNCE).lerp(NIGHT_GROUND, night)
    hemisphere.intensity = 0.4 * (0.35 + 0.65 * day)
    scene.fog.color.copy(sky.fogColor)
    // Rain (ADR-010): an overcast, dimmer, greyer world while it pours.
    rainNow += (worldRain - rainNow) * Math.min(1, dt * 0.5)
    if (rainNow > 0.01) {
      light.intensity *= 1 - 0.45 * rainNow
      light.glint *= 1 - 0.7 * rainNow
      scene.fog.color.lerp(RAIN_FOG.copy(RAIN_GREY).multiplyScalar(0.25 + 0.75 * day), 0.6 * rainNow)
    }
    fogNow += (worldFog - fogNow) * Math.min(1, dt * 0.5)
    scene.fog.near = FOG_NEAR * (1 - 0.97 * fogNow)
    scene.fog.far = FOG_FAR * (1 - 0.92 * fogNow) // about 50 to 60 in thick fog
    if (fogNow > 0.01) scene.fog.color.lerp(RAIN_FOG.copy(FOG_WHITE).multiplyScalar(0.12 + 0.88 * day), 0.85 * fogNow)
    if (csm) {
      csm.lightDirection.copy(light.direction).negate()
      for (const l of csm.lights) {
        l.color.copy(light.color)
        l.intensity = light.intensity
      }
      csm.update()
    } else {
      sunLight.color.copy(light.color)
      sunLight.intensity = light.intensity
      sunLight.position.copy(cameraTarget).addScaledVector(light.direction, 120)
      sunLight.target.position.copy(cameraTarget)
    }
  }

  function draw(obs, dt) {
    latestObs = obs
    elapsed += dt
    const { seaLevel, land, landKey, cameraTarget, swimming } = updateScene(obs, dt)
    if (seaLevel != null) lastSeaLevel = seaLevel
    quakeNow += (worldQuake - quakeNow) * Math.min(1, dt * 3)
    updateSunAndLights(dt, cameraTarget)
    sky.update(camera, elapsed)
    sea.update({ camera, time: elapsed, seaLevel, land, landKey, light })
    clouds.update({ camera, time: elapsed, sky, rain: rainNow })
    rain.update({ rain: rainNow, time: elapsed, camera, wind: wind.update(dt) })
    fires.update({ time: elapsed, camera, daylight: sky.daylight, night: sky.night })
    fish.update(swimming, sea, elapsed)
    dust.update({ time: elapsed, daylight: sky.daylight })
    ambient.intensity += blasts.update({ time: elapsed, dt, daylight: sky.daylight, wind: wind.now, camera })
    instancer.flush()
    if (governor.sample(dt)) applyResolution()
    shake.apply(camera, Math.min(1, quakeNow + blasts.jolt(camera.position)), elapsed)
    renderer.render(scene, camera)
    shake.restore(camera)
    globalThis.__godlingRenderer?.afterDraw?.(elapsed) // for checks: the frame is still in the canvas here
    stats?.tick(dt)
  }

  // For debugging in the browser console and for checks: the tier, per-frame counts and the sky. A check may set
  // `afterDraw(time)` to look at each frame as it is drawn (time: the renderer's clock, which effects run on).
  globalThis.__godlingRenderer = {
    tier,
    sky,
    info: () => ({ ...renderer.info.render, pixelRatio: renderer.getPixelRatio(), ...instancer.stats(), modelsArrived }),
    animations: () => characters.debug(),
    quake: () => ({ quake: Number(quakeNow.toFixed(3)), phase: quakePhase, dust: dust.info() }),
    blasts: () => blasts.info(),
    bubbles: () => ({ assetBase, shown: bubbles.info() }),
    bubbleSheet: () => bubbleSheet(models, resolveAsset), // call twice: the first call starts the model loads
  }

  return {
    onResize({ width, height, dpr }) {
      viewport = { width, height, dpr: Number.isFinite(dpr) ? dpr : (globalThis.devicePixelRatio || 1) }
      camera.aspect = width / Math.max(1, height)
      camera.updateProjectionMatrix()
      applyResolution()
      csm?.updateFrustums()
    },

    onState(state) {
      if (replay?.active) { // the past is playing: the live stream waits (ADR-016)
        replay.step()
        const now = performance.now()
        const dt = Math.min((now - lastStateMs) / 1000, 0.05)
        lastStateMs = now
        if (latestObs) draw(stateBuffer.interpolated() || latestObs, dt)
        return
      }
      const captureMeta = state && typeof state === 'object' && state.__mesaCaptureMeta && typeof state.__mesaCaptureMeta === 'object'
        ? state.__mesaCaptureMeta
        : null
      const obsState = captureMeta ? { ...state } : state
      if (captureMeta) delete obsState.__mesaCaptureMeta

      if (captureMeta?.resetBuffer) stateBuffer.clear()
      // A whole island (on connecting, after falling behind, or a new world: patches/v3, ADR-015) is not eased in from
      // what was shown before the gap; only a delta's state carries __spectatorDelta.
      else if (!captureMeta && !obsState?.__spectatorDelta && stateBuffer.latest()) stateBuffer.clear()
      if (captureMeta?.push !== false) {
        const pushNowMs = Number.isFinite(captureMeta?.pushNowMs)
          ? Number(captureMeta.pushNowMs)
          : undefined
        stateBuffer.push(obsState, pushNowMs)
      }
      const renderNowMs = Number.isFinite(captureMeta?.renderNowMs)
        ? Number(captureMeta.renderNowMs)
        : undefined
      const obs = stateBuffer.interpolated(renderNowMs) || obsState
      const now = performance.now()
      const dt = Number.isFinite(captureMeta?.dt)
        ? Math.max(0, Number(captureMeta.dt))
        : Math.min((now - lastStateMs) / 1000, 0.05)
      lastStateMs = now
      draw(obs, dt)
    },

    // The page's stream (patches/v3): live, reconnecting, paused, and whether the world is up. Inside the viewers'
    // screen it decides the Live badge, so the badge never says Live over a frozen island.
    onConnection({ state, world } = {}) {
      if (embedded) tellScreen({ type: 'godling-stream', state: String(state || ''), world: world === 'down' ? 'down' : 'up' })
    },

    // Between states, keep animating (the sea, clouds and walk cycle) from the interpolated snapshots.
    onFrame({ dt }) {
      replay?.step()
      if (!latestObs) return
      lastStateMs = performance.now()
      draw(stateBuffer.interpolated() || latestObs, Math.min(Math.max(dt, 0), 0.05))
    },

    unmount() {
      if (ctx.runtime?.internal?.remove) ctx.runtime.internal.remove('camera')
      if (cameraModes?.dispose) cameraModes.dispose()
      for (const record of records.values()) release(record)
      records.clear()
      for (const obj of colliderDebugObjects.values()) scene.remove(obj)
      colliderDebugObjects.clear()
      instancer.clear()
      characters.clear()
      bubbles.dispose()
      models.dispose()
      kit.dispose()
      sky.dispose()
      sea.dispose()
      clouds.dispose()
      rain.dispose()
      terrain.dispose()
      fires.dispose()
      fish.dispose()
      dust.dispose()
      blasts.dispose()
      csm?.remove()
      csm?.dispose()
      stats?.dispose()
      delete globalThis.__godlingRenderer
      renderer.dispose()
    },
  }
}
