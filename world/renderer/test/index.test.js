// The renderer as Clawblox's runtime drives it: createRenderer(ctx), then onResize, onState and onFrame with the
// world's observations, and unmount. WebGL is stood in for (gl.js); models come from a fake loader.
import * as THREE from 'three'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { install2d, renders } from './gl.js'
import { canvas as makeCanvas, pointer } from './events.js'

vi.mock('three', async () => (await import('./gl.js')).threeWithFakeGL())
// The state buffer (buffer.js, tested on its own) stood in for, keeping only the last state; what it was made with.
const held = vi.hoisted(() => ({ buffer: null, options: null }))
vi.mock('../src/buffer.js', () => ({ createStateBuffer: (options) => { held.options = options; return held.buffer } }))
const files = {}
vi.mock('three/addons/loaders/GLTFLoader.js', () => ({
  GLTFLoader: class {
    loadAsync(url) {
      const make = files[url.replace(/\?.*$/, '')]
      return make ? Promise.resolve(make()) : Promise.reject(new Error(`404 ${url}`))
    }
  },
}))
const { createRenderer } = await import('../src/index.js')
const { handed } = await import('./rig.js')

beforeAll(install2d)
const flush = () => new Promise((resolve) => setTimeout(resolve, 0))

function prop() {
  const scene = new THREE.Group()
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(1, 2, 1), new THREE.MeshStandardMaterial()))
  return { scene, animations: [] }
}
function body() {
  const scene = new THREE.Group()
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(1, 5, 1), new THREE.MeshStandardMaterial()))
  return { scene, animations: ['Idle', 'Walk'].map((n) => new THREE.AnimationClip(n, 1, [
    new THREE.NumberKeyframeTrack('.position[x]', [0, 1], [0, 1])])) }
}
files['/assets/palm.glb'] = prop
files['/assets/crater.glb'] = prop
files['/assets/fish.glb'] = prop
files['/assets/stone.glb'] = prop
files['/assets/godling.glb'] = body
files['/assets/handed.glb'] = () => handed({ clips: ['Idle', 'Walk', 'IdleCarry', 'WalkCarry'] })

function runtime() {
  const buffer = {
    last: null,
    cleared: 0,
    push(obs) { this.last = obs },
    latest() { return this.last },
    interpolated() { return this.last },
    clear() { this.cleared += 1; this.last = null },
    delayMs: () => 200,
  }
  held.buffer = buffer
  const cameraModes = { api: { name: 'camera api' }, update: vi.fn(), dispose: vi.fn(), spectator: { state: { attach: null } } }
  const ctx = {
    canvas: makeCanvas(),
    log: vi.fn(),
    runtime: {
      state: { createSnapshotBuffer: () => buffer },
      three: { createCameraModeController: () => cameraModes, trackAssetLoad: (work) => work },
      internal: { expose: vi.fn(), remove: vi.fn() },
    },
  }
  return { ctx, buffer, cameraModes }
}

const I = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
const part = (id, role, position, size, extra = {}) => ({
  id, position, size, render: { role, color: [0.5, 0.6, 0.7], ...(extra.render || {}) }, ...extra,
  ...(extra.render ? { render: { role, color: [0.5, 0.6, 0.7], ...extra.render } } : {}),
})

function island(t = 0, more = []) {
  return {
    players: [
      { id: 'p1', name: 'Godling', root_part_id: 100, humanoid_state: 'Running', position: [t, 2.5, 0],
        attributes: { Thoughts: 1, Thought: 'fire', Feeling: 'happy', Gestures: 0 } },
      { id: 'p2', name: 'Sky', position: [0, 0, 0] },
      { id: 'p3', name: 'Ghost', root_part_id: 'x' },
    ],
    entities: [
      part(1, 'Ocean', [0, -1, 0], [2000, 1, 2000]),
      part(2, 'Ground', [0, -0.5, 0], [100, 1, 100], { attributes: { Surface: 'Sand' } }),
      part(3, 'Ground', [0, 0, 0], [60, 1, 60]),
      part(4, 'Wreck', [10, 1, 10], [6, 2, 4]),
      part(5, 'Mesa', [-20, 5, 0], [10, 10, 10]),
      part(6, 'Mesa', [-40, 6, 0], [10, 12, 10], { attributes: { Surface: 'Rock' } }),
      part(7, 'Rock', [3, 1, 3], [1, 1, 1]),
      part(8, 'Plank', [4, 1, 3], [3, 0.3, 1]),
      part(9, 'Ring', [5, 1, 3], [3, 0.5, 3]),
      part(10, 'SkyShadow', [6, 0.05, 3], [4, 0.1, 4]),
      part(11, 'Blast', [6, 0.5, 3], [1, 1, 1], { attributes: { SkyId: 4, Radius: 7 }, render: { visible: false } }),
      part(12, 'Crater', [6, 0.3, 3], [14, 0.6, 14], { attributes: { SkyId: 4 } }),
      part(13, 'SkyNote', [7, 6, 3], [1, 0.2, 1]),
      part(14, 'PickupObject', [8, 1.25, 3], [2.5, 2.5, 2.5], { rotation: I }),
      part(15, 'Fire', [9, 1.5, 3], [2, 3, 2]),
      part(16, 'Fish', [30, -0.6, 30], [1.3, 0.4, 0.5], { rotation: I }),
      part(17, 'SandMark', [2, 0, -3], [4, 0.2, 0.4]),
      part(18, 'Coconut', [2, 0.4, -4], [0.8, 0.8, 0.8]),
      part(19, 'Volleyball', [2, 0.5, -5], [1, 1, 1]),
      part(20, 'Catch', [2, 0.3, -6], [1.3, 0.4, 0.5], { attributes: { Cooked: true } }),
      part(21, 'Catch', [2, 0.3, -7], [1.3, 0.4, 0.5]),
      part(22, 'Tool', [2, 0.3, -8], [0.3, 0.3, 4], { attributes: { ToolKind: 'Spear' } }),
      part(23, 'Thing', [2, 1, -9], [1, 1, 1], { render: { primitive: 'cylinder' } }),
      part(24, 'Thing', [2, 1, -10], [1, 1, 1], { render: { primitive: 'ball' } }),
      part(25, 'Thing', [2, 1, -11], [1, 1, 1], { render: { primitive: 'wedge' } }),
      part(26, 'Hidden', [2, 1, -12], [1, 1, 1], { render: { transparency: 1 } }),
      part(27, 'Palm', [12, 5, -12], [2, 10, 2], { model_url: '/assets/palm.glb' }),
      part(28, 'Crater', [-12, 0.3, -12], [10, 0.6, 10], { attributes: { ModelUrl: 'asset://crater.glb' } }),
      part(29, 'Fish', [32, -0.6, 32], [1.3, 0.4, 0.5], { model_url: '/assets/fish.glb' }),
      part(30, 'Lost', [0, 1, 20], [1, 1, 1], { model_url: '/assets/missing.glb' }),
      part(100, 'Body', [t, 2.5, 0], [2, 5, 2], { model_url: '/assets/godling.glb', model_yaw_offset_deg: 180, rotation: I }),
      { id: 31, position: [0, 1, 25], size: [1, 1, 1], render: { role: 'NoColour' } }, // a part without its colour
      { id: 32, name: 'Clock', position: [0, -50, 0], size: [1, 1, 1], render: { role: 'Clock', visible: false },
        attributes: { TimeOfDay: 21.5, Rain: 0.6, WindX: 0.5, WindZ: 0, Fog: 0.7, Quake: 0.5, QuakePhase: 'shaking' } },
      ...more,
    ],
    terrain: { revision: 1, voxel_size: 4, materials: ['Grass'], voxels: [0, -1, 0, 0, 255, 0] },
  }
}

function shelteredHut(selected = true) {
  return {
    selected_player_id: selected ? 'p1' : null,
    players: [{ id: 'p1', name: 'Godling', root_part_id: 1, position: [0, 2.5, 0], attributes: { Sheltered: 'roof' } }],
    entities: [part(1, 'Body', [0, 2.5, 0], [2, 5, 2]),
      part(10, 'Log', [0, 8.75, 0], [7.5, 2.5, 2.5])],
  }
}

function roofMatrix() {
  // The fallback body and log share a group; the roof is its second instance.
  const mesh = renders.renderer.last.scene.children.find((child) => child.isInstancedMesh && child.count === 2)
  const matrix = new THREE.Matrix4()
  mesh.getMatrixAt(1, matrix)
  return matrix
}

describe('the renderer', () => {
  beforeEach(() => {
    renders.count = 0
    delete globalThis.__mesaCaptureConfig
    history.replaceState(null, '', '/')
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    delete globalThis.__mesaCaptureConfig
  })

  it('draws the whole island on the high tier, then follows it as it changes', async () => {
    globalThis.__mesaCaptureConfig = { quality: 'high', debugColliders: true, interpolationDelayMs: 50,
      followPositionSmoothing: 5, followRotationSmoothing: 7 }
    history.replaceState(null, '', '/?stats=1&dayMinutes=20')
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { ctx, buffer, cameraModes } = runtime()
    const r = createRenderer(ctx)
    expect(ctx.log).toHaveBeenCalledWith('info', 'Renderer quality', expect.objectContaining({ tier: 'high' }))
    expect(ctx.runtime.internal.expose).toHaveBeenCalledWith('camera', cameraModes.api)
    r.onResize({ width: 800, height: 600, dpr: 2 })
    r.onResize({ width: 400, height: 300 })
    r.onFrame({ dt: 0.016 }) // nothing seen yet: nothing to draw
    expect(renders.count).toBe(0)
    r.onState(island(0))
    await flush() // the models arrive
    // After the whole island, the stream sends what changed (patches/v1: the state then carries __spectatorDelta).
    const delta = (state) => ({ ...state, __spectatorDelta: { changedEntityIds: [], removedEntityIds: [], addedEntityIds: [] } })
    for (let t = 1; t <= 12; t++) r.onState(delta(island(t * 0.3)))
    for (let k = 0; k < 40; k++) r.onFrame({ dt: 0.02 })
    expect(renders.count).toBeGreaterThan(40)
    expect(warn).toHaveBeenCalled() // the part without its colour is drawn magenta, and said so
    const debug = globalThis.__godlingRenderer
    expect(debug.tier.name).toBe('high')
    expect(held.options.delayMs).toBe(50) // a capture sets its own
    expect(debug.info().modelsArrived).toBe(3) // the palm, the fish and Godling; asset://crater.glb is not served here
    expect(debug.info().instances).toBeGreaterThan(20)
    expect(debug.animations()).toHaveLength(1)
    expect(debug.quake().phase).toBe('shaking')
    expect(debug.blasts().blasts).toBe(1)
    expect(debug.bubbles().assetBase).toBe('/assets/')
    debug.bubbleSheet()
    expect(cameraModes.update).not.toHaveBeenCalled() // nobody chosen to follow: the free camera flies
    // pieces move, change colour and leave; a player is chosen to follow; the camera rides in Godling's head
    const changed = island(5, [part(40, 'Ring', [9, 1, 9], [3, 0.5, 3])])
    changed.entities = changed.entities.filter((e) => e.id !== 7)
    changed.entities.find((e) => e.id === 14).render.color = [1, 0, 0]
    changed.entities.find((e) => e.id === 14).rotation = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]
    changed.entities.find((e) => e.id === 25).render.primitive = 'cylinder'
    changed.selected_player_id = 'p1'
    cameraModes.spectator.state.attach = { playerId: 'p1' }
    r.onState(delta(changed))
    expect(cameraModes.update).toHaveBeenCalledWith(expect.objectContaining({ mode: 'follow' }))
    expect(buffer.cleared).toBe(0) // each change is eased in from the state before it
    const gone = { players: [], entities: [] }
    r.onState(gone) // a whole island again (a reconnect, or a new world): not eased in from before the gap
    expect(buffer.cleared).toBe(1)
    r.onState({}) // nothing at all: the camera looks at where it looked
    r.unmount()
    expect(ctx.runtime.internal.remove).toHaveBeenCalledWith('camera')
    expect(cameraModes.dispose).toHaveBeenCalled()
    expect(globalThis.__godlingRenderer).toBeUndefined()
  })

  it('takes the capture\'s frames as it times them, on the low tier', () => {
    globalThis.__mesaCaptureConfig = { quality: 'low' }
    history.replaceState(null, '', '/?time=17.5&rain=0.8&fog=0.4&quake=0.6&wind=1')
    const { ctx, buffer } = runtime()
    const r = createRenderer(ctx)
    const obs = island(0)
    r.onState({ ...obs, __mesaCaptureMeta: { resetBuffer: true, pushNowMs: 1000, renderNowMs: 1100, dt: 0.05 } })
    expect(buffer.cleared).toBe(1)
    r.onState({ ...obs, __mesaCaptureMeta: { push: false, dt: -1 } })
    r.onState({ ...obs, __mesaCaptureMeta: {} })
    buffer.last = null
    r.onFrame({ dt: 1 }) // the buffer had nothing: the last observation
    expect(globalThis.__godlingRenderer.tier.name).toBe('low')
    expect(held.options.delayMs).toBeUndefined() // otherwise the buffer follows the stream
    expect(globalThis.__godlingRenderer.delay()).toBe(200)
    expect(globalThis.__godlingRenderer.state().entities).toHaveLength(obs.entities.length) // as last drawn
    expect(renders.count).toBe(4)
    r.unmount()
  })

  it('inside the viewer screen, follows Godling and does what the screen asks', () => {
    history.replaceState(null, '', '/?embed=1&debugCollider=yes')
    const screen = { postMessage: vi.fn() }
    vi.stubGlobal('parent', screen)
    const { ctx, cameraModes } = runtime()
    const r = createRenderer(ctx)
    expect(document.head.querySelector('style').textContent).toContain('visibility: hidden')
    r.onResize({ width: 390, height: 844 }) // a phone held upright: our follow camera, framed for it (followcam.js)
    r.onState(island(0))
    expect(renders.camera.fov).toBe(75)
    expect(renders.camera.position.toArray()).toEqual([0, 12, -25])
    expect(cameraModes.update).not.toHaveBeenCalled() // upstream's only while the capture holds the camera
    const say = (data, source = screen) => {
      const event = new MessageEvent('message', { data })
      Object.defineProperty(event, 'source', { value: source })
      dispatchEvent(event)
    }
    say({ source: 'godling-viewer', type: 'godling-camera', mode: 'free' })
    say({ source: 'godling-viewer', type: 'godling-key', code: 'KeyW', down: true })
    r.onState(island(1))
    r.onFrame({ dt: 0.1 })
    expect(renders.camera.position.z).toBeGreaterThan(-25) // flying free now, ahead, not after Godling
    expect(renders.camera.position.x).toBeCloseTo(0, 6)
    say({ source: 'godling-viewer', type: 'godling-key', code: 'KeyW', down: false })
    say({ source: 'godling-viewer', type: 'godling-camera', mode: 'follow' })
    say({ source: 'someone-else', type: 'godling-camera', mode: 'free' })
    say({ source: 'godling-viewer', type: 'godling-camera', mode: 'free' }, window) // not from the screen: ignored
    r.onState(island(2))
    r.onFrame({ dt: 0.1 })
    expect(renders.camera.position.x).toBeGreaterThan(0.5) // following again, after Godling
    expect(cameraModes.update).not.toHaveBeenCalled()
    say({ source: 'godling-viewer', type: 'godling-aim', power: 'Meteor' })
    ctx.canvas.dispatchEvent(pointer('pointermove', { x: 50, y: 50 }))
    ctx.canvas.dispatchEvent(pointer('pointerdown', { x: 50, y: 50 }))
    ctx.canvas.dispatchEvent(pointer('pointerup', { x: 50, y: 50 }))
    dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    say({ source: 'godling-viewer', type: 'godling-aim', power: 'Stone' })
    say({ source: 'godling-viewer', type: 'godling-aim' })
    say({ source: 'godling-viewer', type: 'other' })
    // The page's stream, for the screen's Live badge (patches/v3).
    r.onConnection({ state: 'live', world: 'down' })
    expect(screen.postMessage).toHaveBeenLastCalledWith(
      { source: 'godling-renderer', type: 'godling-stream', state: 'live', world: 'down' }, '*')
    r.onConnection()
    expect(screen.postMessage).toHaveBeenLastCalledWith(
      { source: 'godling-renderer', type: 'godling-stream', state: '', world: 'up' }, '*')
    expect(screen.postMessage.mock.calls.every(([msg]) => msg.source === 'godling-renderer')).toBe(true)
    r.unmount()
  })

  it('draws a marker it can see, a body that is not turned, and a part\'s own collider shape', async () => {
    history.replaceState(null, '', '/?debugColliders=on')
    const { ctx } = runtime()
    const r = createRenderer(ctx)
    const obs = {
      players: [{ id: 'p1', name: 'Godling', root_part_id: 1, position: [0, 2.5, 0] }],
      entities: [part(1, 'Body', [0, 2.5, 0], [2, 5, 2], { model_url: '/assets/godling.glb' }),
        part(2, 'Blast', [5, 0.5, 0], [1, 1, 1], { attributes: { SkyId: 9 } }),
        part(3, 'PickupObject', [9, 1, 0], [1, 1, 1], { shape: 'Ball' }),
        part(4, 'PickupObject', [9, 1, 3], [1, 1, 1], { render: { primitive: 'sphere' } }),
        part(5, 'Ring', [9, 1, 6], null)],
    }
    r.onState(obs)
    await flush()
    r.onState(obs)
    r.onState(obs)
    expect(globalThis.__godlingRenderer.animations()).toHaveLength(1)
    r.unmount()
  })

  it('draws a tool in the hand of the body that holds it, and where the world has it otherwise', async () => {
    const { ctx, cameraModes } = runtime()
    const r = createRenderer(ctx)
    const tool = (id, kind, position, holder) => part(id, 'Tool', position, [0.4, 0.4, 1], { rotation: I,
      attributes: { ToolKind: kind, ...(holder ? { HeldBy: holder } : {}) } })
    const obs = (holder, attributes = {}) => ({
      players: [{ id: 'p1', name: 'Godling', root_part_id: 1, position: [0, 2.5, 0], attributes },
        { id: 'p2', name: 'Plain', root_part_id: 2, position: [9, 2.5, 0] },
        { id: 'p3', name: 'Torchbearer', root_part_id: 7, position: [-9, 2.5, 0] }],
      entities: [
        part(1, 'Body', [0, 2.5, 0], [2, 5, 2], { model_url: '/assets/handed.glb', rotation: I }),
        part(2, 'Body', [9, 2.5, 0], [2, 5, 2], { model_url: '/assets/godling.glb' }), // a model without a hand bone
        part(7, 'Body', [-9, 2.5, 0], [2, 5, 2], { model_url: '/assets/handed.glb', rotation: I }),
        tool(8, 'Torch', [-9, 6.5, 0], 'Torchbearer'), // a kind with no grip (IN_HAND): it stays over the head
        tool(3, 'Axe', [0, 6.5, 0], holder), // carried over the head, as the world does (main.lua HOLD_OFFSET)
        tool(4, 'Hammer', [9, 6.5, 0], 'Plain'),
        tool(5, 'Spear', [4, 0.2, 4], 'Nobody'), // a holder not on the island
        tool(6, 'Spear', [5, 0.2, 5]), // lying on the grass
      ],
    })
    const frames = (n, state) => {
      for (let i = 0; i < n; i++) {
        r.onState(state)
        r.onFrame({ dt: 0.05 })
      }
    }
    const hands = () => globalThis.__godlingRenderer.hands()
    r.onState(obs('Godling'))
    await flush() // the models arrive
    frames(12, obs('Godling'))
    expect(hands()).toEqual([expect.objectContaining({ id: 3, body: 1, weight: 1 })])
    const clips = (id) => globalThis.__godlingRenderer.animations().find((a) => a.id === id).weights
    expect(clips(1)).toEqual({ IdleCarry: 1 }) // it carries the axe: the arm holds it still
    expect(clips(2)).toEqual({ Idle: 1 }) // a model without carry clips keeps its own
    expect(clips(7)).toEqual({ Idle: 1 }) // nothing in its hand to hold steady: the torch is drawn over its head
    const [axe] = hands()
    expect(axe.at[1]).toBeLessThan(4) // in the hand at the body's side, not over its head at 6.5
    expect(Math.hypot(axe.at[0], axe.at[2])).toBeLessThan(2.5)
    // The camera inside Godling's head (its own view): that body is not drawn, and the axe goes back over the head.
    cameraModes.spectator.state.attach = { playerId: 'p1' }
    frames(12, obs('Godling'))
    expect(hands()).toEqual([])
    cameraModes.spectator.state.attach = null
    frames(12, obs('Godling'))
    expect(hands()).toHaveLength(1)
    // Climbing, both hands are on the ladder: the axe floats over the head meanwhile, and comes back to the hand after.
    frames(12, obs('Godling', { Climbing: true }))
    expect(hands()).toEqual([])
    expect(clips(1)).toEqual({ Idle: 1 }) // its hand is empty: no carry clip (this stand-in has no Climb to play)
    frames(12, obs('Godling'))
    expect(hands()).toEqual([expect.objectContaining({ id: 3, body: 1, weight: 1 })])
    // Set down: out of the hand, then where the world has it.
    frames(2, obs(null))
    expect(hands()[0].weight).toBeLessThan(1)
    frames(12, obs(null))
    expect(hands()).toEqual([])
    expect(clips(1)).toEqual({ Idle: 1 })
    r.unmount()
  })

  it('takes the roof off a body the camera follows while it shelters, but not in its own eyes', () => {
    const { ctx, cameraModes } = runtime()
    const r = createRenderer(ctx)
    const debug = globalThis.__godlingRenderer
    const hut = (sheltered) => ({
      selected_player_id: 'p1',
      players: [{ id: 'p1', name: 'Godling', root_part_id: 1, position: [0, 2.5, 0], attributes: { Sheltered: sheltered } }],
      entities: [
        part(2, 'Ground', [0, -0.5, 0], [100, 1, 100]),
        part(1, 'Body', [0, 2.5, 0], [2, 5, 2], { rotation: I }),
        part(10, 'Log', [0, 8.75, 0], [7.5, 2.5, 2.5]), // the roof, on two posts three blocks high
        ...[1.25, 3.75, 6.25].flatMap((y, i) => [part(11 + i, 'PickupObject', [-2.5, y, 0], [2.5, 2.5, 2.5]),
          part(21 + i, 'PickupObject', [2.5, y, 0], [2.5, 2.5, 2.5])]),
        part(30, 'PickupObject', [30, 1.25, 30], [2.5, 2.5, 2.5]), // a block far off
        part(31, 'Tree', [0, 10, 0], [2, 20, 2]), // not a building piece
      ],
    })
    const frames = (n, state) => {
      for (let i = 0; i < n; i++) {
        r.onState(state)
        r.onFrame({ dt: 0.05 })
      }
    }
    frames(10, hut('enclosed'))
    expect(debug.cutaway()).toContain(10) // the roof is off
    expect(debug.cutaway()).not.toContain(30)
    expect(debug.cutaway()).not.toContain(31)
    // Godling's own eyes (the camera inside its head): it sees its roof, once the hold is over.
    cameraModes.spectator.state.attach = { playerId: 'p1' }
    frames(20, hut('enclosed'))
    expect(debug.cutaway()).toEqual([])
    cameraModes.spectator.state.attach = null
    frames(10, hut('enclosed'))
    expect(debug.cutaway()).toContain(10)
    frames(10, { ...hut('enclosed'), selected_player_id: null }) // nobody followed: the free camera looks for Godling
    expect(debug.cutaway()).toContain(10)
    const away = hut('enclosed')
    away.players[0].position = [40, 2.5, 40] // Godling far from the hut: the hut is drawn whole
    frames(20, { ...away, selected_player_id: null })
    expect(debug.cutaway()).toEqual([])
    r.unmount()
  })

  it('draws every piece when the viewer turns the cutaway off', () => {
    history.replaceState(null, '', '/?cutaway=off')
    const { ctx } = runtime()
    const r = createRenderer(ctx)
    const state = {
      selected_player_id: 'p1',
      players: [{ id: 'p1', name: 'Godling', root_part_id: 1, position: [0, 2.5, 0], attributes: { Sheltered: 'roof' } }],
      entities: [part(2, 'Ground', [0, -0.5, 0], [100, 1, 100]), part(1, 'Body', [0, 2.5, 0], [2, 5, 2], { rotation: I }),
        part(10, 'Log', [0, 8.75, 0], [7.5, 2.5, 2.5])],
    }
    for (let i = 0; i < 10; i++) {
      r.onState(state)
      r.onFrame({ dt: 0.05 })
    }
    expect(globalThis.__godlingRenderer.cutaway()).toEqual([])
    r.unmount()
    history.replaceState(null, '', '/')
  })

  it('draws a meteor\'s stone and its crater as hot as the world says, a group for each step of heat', async () => {
    files['/assets/meteor.glb'] = () => {
      const scene = new THREE.Group()
      const glowing = new THREE.MeshStandardMaterial({ name: 'ember', emissive: new THREE.Color(1, 0.13, 0.01), emissiveIntensity: 1.2 })
      scene.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial()),
        new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.9, 0.9), glowing))
      return { scene, animations: [] }
    }
    files['/assets/scorched.glb'] = () => {
      const geometry = new THREE.PlaneGeometry(8, 8, 2, 2).rotateX(-Math.PI / 2)
      geometry.setAttribute('color', new THREE.Float32BufferAttribute(new Array(geometry.attributes.position.count * 3).fill(0.08), 3))
      const scene = new THREE.Group()
      scene.add(new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ vertexColors: true })))
      return { scene, animations: [] }
    }
    const { ctx } = runtime()
    const r = createRenderer(ctx)
    const debug = globalThis.__godlingRenderer
    const at = (heat) => ({
      players: [],
      entities: [
        part(1, 'Ground', [0, -0.5, 0], [100, 1, 100]),
        part(2, 'Stone', [0, 1.25, 0], [2.5, 2.5, 2.5], { model_url: '/assets/meteor.glb',
          attributes: { SkyEvent: 'Meteor', SkyId: 1, ...(heat == null ? {} : { Heat: heat }) } }),
        part(3, 'Crater', [0, 0.3, 0], [8, 0.6, 8], { model_url: '/assets/scorched.glb',
          attributes: { SkyId: 1, ...(heat == null ? {} : { Heat: heat }) } }),
      ],
    })
    r.onState(at(1))
    await flush() // the models arrive
    r.onState(at(1))
    r.onFrame({ dt: 0.02 })
    const groups = debug.info().groups
    const instances = debug.info().instances
    r.onState(at(0.55)) // cooler: the cracks and the scorch move to the next groups
    r.onFrame({ dt: 0.02 })
    expect(debug.info().groups).toBe(groups + 2)
    expect(debug.info().instances).toBe(instances) // still one stone and one crater
    r.onState(at(1)) // the same heat again: the same groups
    r.onFrame({ dt: 0.02 })
    expect(debug.info().groups).toBe(groups + 2)
    r.onState(at(null)) // a replay from before stones cooled: drawn as the models are
    r.onFrame({ dt: 0.02 })
    expect(debug.info().groups).toBe(groups + 4)
    expect(debug.info().instances).toBe(instances)
    r.unmount()
  })

  it('draws a flake of meteoric iron, and a tool with an iron edge in groups of its own', async () => {
    files['/assets/edged.glb'] = () => {
      const scene = new THREE.Group()
      scene.add(new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 1), new THREE.MeshStandardMaterial({ name: 'handle' })),
        new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.2, 0.2), new THREE.MeshStandardMaterial({ name: 'edge' })))
      return { scene, animations: [] }
    }
    const { ctx } = runtime()
    const r = createRenderer(ctx)
    const debug = globalThis.__godlingRenderer
    const at = (edge, flake) => ({
      players: [],
      entities: [
        part(1, 'Ground', [0, -0.5, 0], [100, 1, 100]),
        part(2, 'Tool', [0, 0.2, 0], [0.4, 0.4, 1.0], { model_url: '/assets/edged.glb',
          attributes: { ToolKind: 'Axe', ...(edge ? { Edge: 'Iron' } : {}) } }),
        ...(flake ? [part(3, 'Iron', [2, 0.1, 0], [0.5, 0.2, 1.0])] : []),
      ],
    })
    r.onState(at(false, false))
    await flush() // the model arrives
    r.onState(at(false, false))
    r.onFrame({ dt: 0.02 })
    const groups = debug.info().groups
    const instances = debug.info().instances
    r.onState(at(false, true)) // a flake lies beside it
    r.onFrame({ dt: 0.02 })
    expect(debug.info().groups).toBe(groups + 1)
    expect(debug.info().instances).toBe(instances + 1)
    r.onState(at(true, false)) // bound on as the axe's edge: the edge in worked iron, its own group
    r.onFrame({ dt: 0.02 })
    expect(debug.info().groups).toBe(groups + 2)
    expect(debug.info().instances).toBe(instances)
    const spear = at(true, false)
    spear.entities[1].attributes.ToolKind = 'Spear' // an iron point: a blade laid over it, one more part
    r.onState(spear)
    r.onFrame({ dt: 0.02 })
    expect(debug.info().groups).toBe(groups + 3)
    expect(debug.info().instances).toBe(instances + 1)
    r.unmount()
  })

  it.each([
    ['attach', true], ['poseOverride', true], ['attach', false], ['poseOverride', false],
  ])('restores the roof on the first %s capture frame (selected: %s)', (mode, selected) => {
    const { ctx, cameraModes } = runtime()
    const r = createRenderer(ctx)
    const state = shelteredHut(selected)
    r.onState(state)
    expect(globalThis.__godlingRenderer.cutaway()).toContain(10)
    expect(roofMatrix().determinant()).toBe(0)
    cameraModes.spectator.state[mode] = mode === 'attach' ? { playerId: 'p1' } : { position: [0, 4, 0] }
    r.onState({ ...state, __mesaCaptureMeta: { push: false, dt: 0 } })
    expect(globalThis.__godlingRenderer.cutaway()).toEqual([])
    expect(new THREE.Vector3().setFromMatrixPosition(roofMatrix()).toArray()).toEqual([0, 8.75, 0])
    expect(roofMatrix().determinant()).toBeCloseTo(7.5 * 2.5 * 2.5)
    cameraModes.spectator.state[mode] = null
    r.onFrame({ dt: 0 })
    expect(globalThis.__godlingRenderer.cutaway()).toContain(10)
    expect(roofMatrix().determinant()).toBe(0)
    r.unmount()
  })

  it('restores the roof immediately when walls up is selected, then cuts it away again', () => {
    history.replaceState(null, '', '/?embed=1')
    const screen = { postMessage: vi.fn() }
    vi.stubGlobal('parent', screen)
    const { ctx } = runtime()
    const r = createRenderer(ctx)
    r.onState(shelteredHut())
    expect(roofMatrix().determinant()).toBe(0)
    const walls = (on) => {
      const event = new MessageEvent('message', { data: { source: 'godling-viewer', type: 'godling-cutaway', on } })
      Object.defineProperty(event, 'source', { value: screen })
      dispatchEvent(event)
      r.onFrame({ dt: 0 })
    }
    walls(false)
    expect(globalThis.__godlingRenderer.cutaway()).toEqual([])
    expect(roofMatrix().determinant()).toBeCloseTo(7.5 * 2.5 * 2.5)
    walls(true)
    expect(globalThis.__godlingRenderer.cutaway()).toContain(10)
    expect(roofMatrix().determinant()).toBe(0)
    r.unmount()
  })

  it('keeps a carried log visible under shelter, including the frame it is picked up', () => {
    const { ctx } = runtime()
    const r = createRenderer(ctx)
    const state = shelteredHut()
    r.onState(state)
    expect(roofMatrix().determinant()).toBe(0)
    state.entities[1].attributes = { HeldBy: 'Godling' }
    r.onState({ ...state, __mesaCaptureMeta: { dt: 0 } })
    expect(globalThis.__godlingRenderer.cutaway()).not.toContain(10)
    expect(roofMatrix().determinant()).toBeCloseTo(7.5 * 2.5 * 2.5)
    state.entities[1].position = [0, 6.5, 0] // the world's carry offset: four above the body's middle
    for (let i = 0; i < 20; i++) r.onFrame({ dt: 0.05 })
    expect(globalThis.__godlingRenderer.cutaway()).not.toContain(10)
    expect(new THREE.Vector3().setFromMatrixPosition(roofMatrix()).toArray()).toEqual([0, 6.5, 0])
    r.unmount()
  })

  it('keeps the hand pose when a hidden material becomes a carried tool', async () => {
    const { ctx } = runtime()
    const r = createRenderer(ctx)
    const state = shelteredHut()
    state.entities[0].model_url = '/assets/handed.glb'
    r.onState(state)
    await flush()
    r.onFrame({ dt: 0.05 })
    expect(globalThis.__godlingRenderer.cutaway()).toContain(10)
    state.entities[1] = part(10, 'Tool', [0, 6.5, 0], [0.4, 0.4, 1], {
      attributes: { ToolKind: 'Axe', HeldBy: 'Godling' },
    })
    r.onState({ ...state, __mesaCaptureMeta: { dt: 0.05 } })
    expect(globalThis.__godlingRenderer.cutaway()).not.toContain(10)
    const [heldTool] = globalThis.__godlingRenderer.hands()
    expect(heldTool).toMatchObject({ id: 10, body: 1 })
    const mesh = renders.renderer.last.scene.children.find((child) => child.isInstancedMesh && child.geometry.type === 'BoxGeometry')
    const matrix = new THREE.Matrix4()
    mesh.getMatrixAt(0, matrix)
    const drawn = new THREE.Vector3().setFromMatrixPosition(matrix).toArray()
    drawn.forEach((value, i) => expect(value).toBeCloseTo(heldTool.at[i], 2))
    expect(drawn[1]).toBeLessThan(6.5)
    r.unmount()
  })

  it('plays a lightning marker as a strike: the part never drawn, the picture flashing and settling', () => {
    const { ctx } = runtime()
    const r = createRenderer(ctx)
    const debug = globalThis.__godlingRenderer
    const calm = { players: [], entities: [part(1, 'Ground', [0, -0.5, 0], [100, 1, 100])] }
    r.onState(calm)
    r.onFrame({ dt: 0.02 })
    const instances = debug.info().instances
    expect(renders.renderer.toneMappingExposure).toBe(1.2)
    r.onState({ ...calm, entities: [...calm.entities, part(2, 'SkyFlash', [4, 15, 4], [0.35, 30, 0.35],
      { attributes: { SkyId: 3, StrikeX: 4, StrikeY: 0, StrikeZ: 4 } })] })
    r.onFrame({ dt: 0.02 })
    expect(debug.info().instances).toBe(instances) // the marker itself is never drawn
    expect(debug.lightning().strikes).toBe(1)
    let brightest = 0
    for (let k = 0; k < 20; k++) {
      r.onFrame({ dt: 0.02 })
      brightest = Math.max(brightest, renders.renderer.toneMappingExposure)
    }
    expect(brightest).toBeGreaterThan(1.4) // the whole picture flashes
    for (let k = 0; k < 70; k++) r.onFrame({ dt: 0.02 })
    expect(debug.lightning().strikes).toBe(0)
    expect(renders.renderer.toneMappingExposure).toBe(1.2)
    r.unmount()
  })

  it('works without the runtime\'s extras', () => {
    const { ctx } = runtime()
    ctx.runtime.internal = undefined
    ctx.runtime.three.createCameraModeController = () => ({ update: () => {}, spectator: null })
    vi.stubGlobal('devicePixelRatio', undefined)
    const r = createRenderer(ctx)
    r.onResize({ width: 10, height: 0, dpr: NaN })
    r.onState({ entities: [part(1, 'PickupObject', [0, 1, 0], [1, 1, 1])] })
    r.onConnection({ state: 'live' }) // not inside the screen: nobody to tell
    r.unmount()
  })
})
