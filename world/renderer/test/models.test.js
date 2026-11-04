import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'

// GLB files without a network: each URL gets a scene (and clips) made here, or fails.
const files = {}
vi.mock('three/addons/loaders/GLTFLoader.js', () => ({
  GLTFLoader: class {
    loadAsync(url) {
      const make = files[url]
      return make ? Promise.resolve(make()) : Promise.reject(new Error(`404 ${url}`))
    }
  },
}))
const { createCharacterController, createModelLibrary } = await import('../src/models.js')
const { handed } = await import('./rig.js')

const flush = () => new Promise((resolve) => setTimeout(resolve, 0))

function prop() {
  const scene = new THREE.Group()
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 4, 1), new THREE.MeshStandardMaterial())
  mesh.position.y = 2
  const specks = new THREE.Mesh(new THREE.BoxGeometry(0.01, 0.01, 0.01), new THREE.MeshBasicMaterial({ name: 'bounds' }))
  scene.add(mesh, specks)
  return { scene, animations: [] }
}

const clip = (name, seconds = 1) => new THREE.AnimationClip(name, seconds, [
  new THREE.NumberKeyframeTrack('.position[x]', [0, seconds], [0, 1])])

function character(clips) {
  const scene = new THREE.Group()
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(1, 5, 1), new THREE.MeshStandardMaterial()))
  return { scene, animations: clips.map((name) => clip(name)) }
}

function skinned() {
  const bone = new THREE.Bone()
  const geometry = new THREE.BoxGeometry(1, 1, 1)
  const count = geometry.attributes.position.count
  geometry.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(new Array(count * 4).fill(0), 4))
  geometry.setAttribute('skinWeight', new THREE.Float32BufferAttribute(new Array(count * 4).fill(0).map((_, i) => (i % 4 ? 0 : 1)), 4))
  const mesh = new THREE.SkinnedMesh(geometry, new THREE.MeshStandardMaterial())
  mesh.add(bone)
  mesh.bind(new THREE.Skeleton([bone]))
  const scene = new THREE.Group()
  scene.add(mesh)
  return { scene } // no clips at all
}

describe('model library', () => {
  it('loads each model once, flattens props, and fits them to their part', async () => {
    files['/tree.glb'] = prop
    files['/godling.glb'] = () => character(['Idle'])
    files['/skin.glb'] = skinned
    const ready = []
    const materials = []
    const tracked = []
    const models = createModelLibrary({ onReady: (url) => ready.push(url), onMaterial: (m) => materials.push(m),
      trackLoad: (work) => tracked.push(work) })
    expect(models.get('/tree.glb')).toBeNull() // the load starts
    expect(models.get('/tree.glb')).toBeNull() // still on its way, not loaded twice
    models.get('/godling.glb')
    models.get('/skin.glb')
    await flush()
    expect(tracked).toHaveLength(3)
    expect(ready).toEqual(['/tree.glb', '/godling.glb', '/skin.glb'])
    const tree = models.get('/tree.glb')
    expect(tree.animated).toBe(false)
    expect(tree.parts).toHaveLength(1) // the outline specks are not drawn
    expect(models.get('/godling.glb').animated).toBe(true)
    expect(models.get('/skin.glb').animated).toBe(true)
    expect(materials.length).toBeGreaterThanOrEqual(3)
    const fit = models.fit(tree, [1, 8, 1], 90, new THREE.Matrix4())
    const scale = new THREE.Vector3()
    fit.decompose(new THREE.Vector3(), new THREE.Quaternion(), scale)
    expect(scale.y).toBeCloseTo(2) // to the part's height
    const stretched = models.fit(tree, [10, 8, 3], 0, new THREE.Matrix4(), true)
    stretched.decompose(new THREE.Vector3(), new THREE.Quaternion(), scale)
    expect([scale.x, scale.z].map((v) => Number(v.toFixed(3)))).toEqual([5, 3]) // a crater: to its whole size
    const plain = models.fit(tree, undefined, 0, new THREE.Matrix4(), true)
    expect(plain.elements[5]).toBeCloseTo(5 / 4)
    models.dispose()
  })

  it('reports a model that cannot load, and draws as if it had none', async () => {
    const errors = []
    const models = createModelLibrary({ onError: (err, meta) => errors.push(meta.modelUrl) })
    expect(models.failed('/missing.glb')).toBe(false)
    models.get('/missing.glb')
    await flush()
    expect(models.failed('/missing.glb')).toBe(true)
    expect(errors).toEqual(['/missing.glb'])
  })
})

describe('characters', () => {
  async function setup(clips) {
    files['/c.glb'] = () => character(clips)
    const models = createModelLibrary({})
    models.get('/c.glb')
    await flush()
    const controller = createCharacterController(models)
    const root = new THREE.Group()
    root.add(new THREE.Object3D()) // the stand-in drawn before the model came: replaced
    return { controller, root, models }
  }
  const ALL = ['Idle', 'Walk', 'Climb', 'Brace', 'Jump', 'Fall', 'PickUp', 'Strike', 'Wave', 'Stagger']
  const weights = (controller) => controller.debug()[0].weights

  it('waits for its model, then idles and walks at the body\'s pace', async () => {
    const { controller, root } = await setup(ALL)
    expect(controller.upsert({ entityId: 1, root, modelUrl: '/not-yet.glb' })).toBe(false)
    controller.update(1, {}) // not ready: nothing
    expect(controller.upsert({ entityId: 1, root, modelUrl: '/c.glb', size: [2, 5, 2], yawOffsetDeg: 90 })).toBe(true)
    expect(controller.upsert({ entityId: 1, root, modelUrl: '/c.glb' })).toBe(true) // ready already
    expect(root.children).toHaveLength(1)
    expect(root.children[0].rotation.y).toBeCloseTo(Math.PI / 2)
    controller.update(1, { dt: 0.5 })
    expect(weights(controller)).toEqual({ Idle: 1 })
    for (let i = 0; i < 10; i++) controller.update(1, { dt: 0.2, speed: 5 })
    expect(weights(controller).Walk).toBeGreaterThan(0.9)
  })

  it('plays gestures and the older counters once, holds climbs and braces, and loops jumps', async () => {
    const { controller, root } = await setup(ALL)
    controller.upsert({ entityId: 1, root, modelUrl: '/c.glb' })
    controller.update(1, { attributes: { Gestures: 1, Gesture: 'Wave', Reaches: 0, Strikes: 0 } }) // first sight: no play
    expect(controller.debug()[0].current).toBeNull()
    controller.update(1, { dt: 0.1, attributes: { Gestures: 2, Gesture: 'Wave', Reaches: 0 } })
    expect(controller.debug()[0].current).toBe('Wave')
    controller.update(1, { dt: 0.1, attributes: { Gestures: 2, Reaches: 1 } }) // the older counter cuts it short
    expect(controller.debug()[0].current).toBe('PickUp')
    for (let i = 0; i < 20; i++) controller.update(1, { dt: 0.1, attributes: { Gestures: 2, Reaches: 1 } })
    expect(controller.debug()[0].current).toBeNull()
    controller.update(1, { dt: 0.1, attributes: { Gestures: 3, Gesture: 'nonsense', Strikes: 1 } })
    expect(controller.debug()[0].current).toBe('Strike') // an unknown gesture: the counter's clip instead
    controller.update(1, { dt: 0.1, attributes: { Gestures: 4, Gesture: '', Strikes: 1 } })
    controller.update(1, { dt: 0.1, attributes: { Gestures: 5, Gesture: 'Stagger', KnockedDown: true } })
    for (let i = 0; i < 30; i++) controller.update(1, { dt: 0.1, attributes: { Gestures: 5, KnockedDown: true } })
    expect(controller.debug()[0].current).toBe('Stagger') // held down
    controller.update(1, { dt: 0.1, attributes: { Gestures: 5, KnockedDown: false } })
    expect(controller.debug()[0].current).toBeNull()
    for (let i = 0; i < 10; i++) controller.update(1, { dt: 0.2, attributes: { Climbing: true } })
    expect(weights(controller).Climb).toBeGreaterThan(0.9)
    for (let i = 0; i < 10; i++) controller.update(1, { dt: 0.2, attributes: { Bracing: true } })
    expect(weights(controller).Brace).toBeGreaterThan(0.9)
    for (let i = 0; i < 10; i++) controller.update(1, { dt: 0.2, humanoidState: 'Freefall' })
    expect(weights(controller).Fall).toBeGreaterThan(0.9)
    controller.remove(1)
    expect(controller.debug()).toEqual([])
  })

  it('with a tool in the hand, idles and walks with the carry clips, the two walks in step', async () => {
    const { controller, root } = await setup(['Idle', 'Walk', 'IdleCarry', 'WalkCarry', 'Wave'])
    controller.upsert({ entityId: 1, root, modelUrl: '/c.glb' })
    controller.update(1, { dt: 0.2, carrying: true })
    expect(weights(controller)).toEqual({ IdleCarry: 1 })
    for (let i = 0; i < 4; i++) controller.update(1, { dt: 0.2, speed: 5, carrying: true })
    expect(weights(controller)).toEqual({ WalkCarry: 1 })
    controller.update(1, { dt: 0.05, speed: 5 }) // set down: the plain walk fades in, at the same point of the stride
    const { weights: fading, times } = controller.debug()[0]
    expect(fading.Walk).toBeGreaterThan(0.05)
    expect(fading.WalkCarry).toBeGreaterThan(0.05)
    expect(times.Walk).toBe(times.WalkCarry)
    controller.update(1, { dt: 0.2, speed: 5 })
    expect(weights(controller)).toEqual({ Walk: 1 })
    controller.update(1, { dt: 0.2, carrying: true, attributes: { Gestures: 1, Gesture: 'Wave' } })
    controller.update(1, { dt: 0.2, carrying: true, attributes: { Gestures: 2, Gesture: 'Wave' } })
    expect(weights(controller)).toEqual({ Wave: 1 }) // a gesture plays over the carry as over the plain clips
  })

  it('a model without carry clips carries a tool in its plain Idle and Walk', async () => {
    const { controller, root } = await setup(['Idle', 'Walk'])
    controller.upsert({ entityId: 1, root, modelUrl: '/c.glb' })
    controller.update(1, { dt: 0.2, carrying: true })
    expect(weights(controller)).toEqual({ Idle: 1 })
    controller.update(1, { dt: 0.2, speed: 5, carrying: true })
    expect(weights(controller)).toEqual({ Walk: 1 })
  })

  it('a model with only a walk walks when it stands too, and a new model replaces the old', async () => {
    const { controller, root } = await setup(['Walk'])
    controller.upsert({ entityId: 2, root, modelUrl: '/c.glb' })
    controller.update(2, { dt: 0.5 })
    expect(weights(controller)).toEqual({ Walk: 1 })
    controller.update(2, { dt: 0.1, attributes: { Reaches: 1 } })
    controller.update(2, { dt: 0.1, attributes: { Reaches: 2 } }) // no PickUp clip: nothing to play
    expect(controller.debug()[0].current).toBeNull()
    expect(controller.upsert({ entityId: 2, root, modelUrl: '/other.glb' })).toBe(false)
    controller.clear()
    expect(controller.debug()).toEqual([])
  })
})

describe('the hand', () => {
  async function body(make) {
    files['/handed.glb'] = make
    const models = createModelLibrary({})
    models.get('/handed.glb')
    await flush()
    const controller = createCharacterController(models)
    const root = new THREE.Group()
    root.position.set(10, 0, 4)
    return { controller, root }
  }
  const pose = (m) => {
    const at = new THREE.Vector3()
    const turn = new THREE.Quaternion()
    const scale = new THREE.Vector3()
    m.decompose(at, turn, scale)
    return { at, turn, scale }
  }

  it('grips at the middle of the right mitten, turned as the hand is, wherever a clip puts the hand', async () => {
    const { controller, root } = await body(() => handed())
    const out = new THREE.Matrix4()
    expect(controller.grip(1, out)).toBeNull() // not drawn yet
    controller.upsert({ entityId: 1, root, modelUrl: '/handed.glb', size: [2, 5, 2], yawOffsetDeg: 90 })
    const hand = root.getObjectByName('mixamorigRightHand')
    for (const dt of [0, 0.5]) { // at rest, then swayed by Idle
      controller.update(1, { dt })
      expect(controller.grip(1, out)).toBe(out)
      const { at, turn, scale } = pose(out)
      expect(at.distanceTo(hand.localToWorld(new THREE.Vector3(0, 0.1, 0)))).toBeLessThan(1e-6)
      expect(turn.angleTo(hand.getWorldQuaternion(new THREE.Quaternion()))).toBeLessThan(1e-6)
      expect(scale.toArray().map((v) => Number(v.toFixed(6)))).toEqual([1, 1, 1]) // the world's scale, not the model's
    }
    expect(hand.rotation.x).toBeGreaterThan(0.2) // the clip moved it
    const twin = new THREE.Group() // a second body on the same model: its own hand, measured once for both
    controller.upsert({ entityId: 2, root: twin, modelUrl: '/handed.glb', size: [2, 5, 2] })
    const { at } = pose(controller.grip(2, out))
    expect(at.distanceTo(twin.getObjectByName('mixamorigRightHand').localToWorld(new THREE.Vector3(0, 0.1, 0)))).toBeLessThan(1e-6)
  })

  it('a model without the hand bone has no grip; a hand without a mitten grips at the bone', async () => {
    const plain = await body(() => character(['Idle'])) // animated, but not rigged
    plain.controller.upsert({ entityId: 1, root: plain.root, modelUrl: '/handed.glb' })
    expect(plain.controller.grip(1, new THREE.Matrix4())).toBeNull()
    const bare = await body(() => handed({ mitten: false }))
    bare.controller.upsert({ entityId: 2, root: bare.root, modelUrl: '/handed.glb' })
    const { at } = pose(bare.controller.grip(2, new THREE.Matrix4()))
    expect(at.distanceTo(bare.root.getObjectByName('mixamorigRightHand').getWorldPosition(new THREE.Vector3()))).toBeLessThan(1e-6)
  })
})
