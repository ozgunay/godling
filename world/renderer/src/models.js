import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { clone as cloneSkinned } from 'three/addons/utils/SkeletonUtils.js'

// GLB models, each loaded once. A model with animations or a skin is a character: every body gets its own copy
// and animation mixer. Any other model is a static prop, flattened to its meshes so that instances.js can draw
// all the trees (or stones, or logs) in one draw call per mesh.
//
// The world fits each model to the height of the part carrying it (uniform scale) and centres it (art/README.md).

export function createModelLibrary({ onReady, onError, trackLoad, onMaterial }) {
  const loader = new GLTFLoader()
  const templates = new Map()

  function flatten(scene) {
    scene.updateMatrixWorld(true)
    const parts = []
    scene.traverse((node) => {
      // art/build_props.py gives each prop a "bounds" material: two specks at its outline's corners, there only
      // so the model's box is its whole outline (the box is taken before this). Not worth a draw call.
      if (!node.isMesh || node.material?.name === 'bounds') return
      onMaterial?.(node.material)
      parts.push({ geometry: node.geometry, material: node.material, matrix: node.matrixWorld.clone() })
    })
    return parts
  }

  function load(url) {
    const template = { url, ready: false, failed: false }
    templates.set(url, template)
    const work = loader.loadAsync(url).then((gltf) => {
      const scene = gltf.scene
      let skinned = false
      scene.traverse((node) => {
        if (node.isSkinnedMesh) skinned = true
        if (node.isMesh) {
          node.castShadow = true
          node.receiveShadow = true
        }
      })
      template.scene = scene
      template.animations = withCarryLayers(gltf.animations || [])
      template.animated = skinned || template.animations.length > 0
      template.box = new THREE.Box3().setFromObject(scene) // every part, in the rest pose
      template.extent = template.box.getSize(new THREE.Vector3())
      template.height = Math.max(template.extent.y, 1e-6)
      template.center = template.box.getCenter(new THREE.Vector3())
      if (!template.animated) template.parts = flatten(scene)
      else scene.traverse((node) => node.isMesh && onMaterial?.(node.material))
      template.ready = true
      onReady?.(url)
    }).catch((err) => {
      template.failed = true
      onError?.(err, { modelUrl: url })
    })
    trackLoad?.(work)
    return template
  }

  return {
    // The template if loaded, else null (and the load starts).
    get(url) {
      const template = templates.get(url) || load(url)
      return template.ready ? template : null
    },
    // True once the model has failed to load (a missing file, say): the part is then drawn as if it had none.
    failed: (url) => Boolean(templates.get(url)?.failed),
    // The model's transform inside its part: turned by the yaw offset, scaled to the part's height, centred. A
    // stretched model (a crater) is scaled to the part's whole size instead, each way on its own.
    fit(template, size, yawOffsetDeg, out, stretch = false) {
      const scale = (size?.[1] ?? 5) / template.height
      const sx = stretch ? (size?.[0] ?? 1) / Math.max(template.extent.x, 1e-6) : scale
      const sz = stretch ? (size?.[2] ?? 1) / Math.max(template.extent.z, 1e-6) : scale
      out.makeScale(sx, scale, sz)
      out.setPosition(-template.center.x * sx, -template.center.y * scale, -template.center.z * sz)
      if (yawOffsetDeg) out.premultiply(new THREE.Matrix4().makeRotationY(THREE.MathUtils.degToRad(yawOffsetDeg)))
      return out
    },
    dispose() {
      templates.clear()
    },
  }
}

// Carry layers (art/build_godling.py): a clip "<Loop>Carry" holds only the bones it poses (Godling's right arm,
// holding a tool steadily), keyed frame by frame against <Loop>'s own body. Laid over <Loop>, it makes the whole carry
// clip: <Loop>'s tracks, with those bones' tracks taken from the layer. The same mask a game engine puts on an arm
// layer, done once when the model loads. A carry clip without its loop stays as it is.
export function withCarryLayers(clips) {
  const byName = new Map(clips.map((clip) => [clip.name, clip]))
  return clips.map((layer) => {
    const loop = layer.name.endsWith('Carry') ? byName.get(layer.name.slice(0, -'Carry'.length)) : null
    if (!loop) return layer
    const own = new Set(layer.tracks.map((track) => track.name))
    return new THREE.AnimationClip(layer.name, loop.duration,
      [...loop.tracks.filter((track) => !own.has(track.name)), ...layer.tracks])
  })
}

// Godling (art/build_godling.py) and any other animated model. The clips follow the player's attributes:
// - "Gesture" names a clip and "Gestures" counts the body's actions (world/main.lua). Each new count plays that clip
//   once at its own speed (the art pipeline cuts each to the world's timing). A model without that clip falls back
//   to the older counters (ONE_SHOTS), as before there were gestures.
// - Climb loops while "Climbing" is true, and Brace (crouched, holding on through an earthquake) while "Bracing" is;
//   Jump and Fall loop while the body jumps or falls. Each only if the model has the clip.
// - Walk plays at the body's real speed, Idle when nothing else does.
// - With a tool in the hand (`carrying`), each of these loops plays as its carry clip (withCarryLayers), if the
//   model has one: the same body, the right arm holding the tool steadily instead of swinging it. A loop and its carry
//   clip play in step, so picking up or setting down a tool cross-fades only the arm.
// A new one-shot cuts the one in progress short. Stagger holds its last pose while "KnockedDown" is true.
const WALK_STRIDE_SPEED = 0.667 // model metres per second the Walk clip covers at normal speed
const ONE_SHOTS = [
  { attribute: 'Reaches', clip: 'PickUp', seconds: 1.1 }, // the world lifts a block in 1.0 s, lowers one in 1.2 s
  { attribute: 'Strikes', clip: 'Strike', seconds: 1.0 }, // a hammer blow on the quarry
]
const AIRBORNE_CLIPS = { Jumping: 'Jump', Freefall: 'Fall' } // humanoid state -> looping clip
const HAND_BONE = 'mixamorigRightHand' // three.js drops the ':' of the Mixamo rig's "mixamorig:RightHand"

// Where a tool is held (hands.js): the middle of the right mitten, in the hand bone's own frame. Each part of Godling
// is rigid and fully weighted to one bone (art/build_godling.py), so the mitten is the vertices that follow that
// bone, measured once in the rest pose. Null for a model without the bone.
function measureGrip(scene) {
  const hand = scene.getObjectByName(HAND_BONE)
  if (!hand?.isBone) return null
  scene.updateMatrixWorld(true)
  const toHand = new THREE.Matrix4().copy(hand.matrixWorld).invert()
  const mitten = new THREE.Box3()
  const at = new THREE.Vector3()
  scene.traverse((node) => {
    const bone = node.isSkinnedMesh ? node.skeleton.bones.indexOf(hand) : -1
    const { position, skinIndex, skinWeight } = node.geometry?.attributes || {}
    if (bone < 0 || !skinIndex || !skinWeight) return
    for (let i = 0; i < position.count; i++) {
      let weight = 0
      for (let k = 0; k < 4; k++) if (skinIndex.getComponent(i, k) === bone) weight += skinWeight.getComponent(i, k)
      if (weight > 0.5) mitten.expandByPoint(node.getVertexPosition(i, at).applyMatrix4(node.matrixWorld).applyMatrix4(toHand))
    }
  })
  return mitten.isEmpty() ? new THREE.Vector3() : mitten.getCenter(new THREE.Vector3())
}

export function createCharacterController(models) {
  const states = new Map()
  const gripAt = new THREE.Vector3()
  const gripTurn = new THREE.Quaternion()
  const gripScale = new THREE.Vector3()
  const unit = new THREE.Vector3(1, 1, 1)

  function upsert({ entityId, root, modelUrl, size, yawOffsetDeg }) {
    let state = states.get(entityId)
    if (state?.modelUrl === modelUrl && state.ready) return true
    if (!state || state.modelUrl !== modelUrl) {
      state = { modelUrl, ready: false }
      states.set(entityId, state)
    }
    const template = models.get(modelUrl)
    if (!template) return false
    const model = cloneSkinned(template.scene)
    const fit = models.fit(template, size, 0, new THREE.Matrix4())
    model.applyMatrix4(fit)
    state.scale = (size?.[1] ?? 5) / template.height
    const pivot = new THREE.Group()
    if (yawOffsetDeg) pivot.rotation.y = THREE.MathUtils.degToRad(yawOffsetDeg)
    pivot.add(model)
    for (const child of [...root.children]) root.remove(child)
    root.add(pivot)
    if (template.grip === undefined) template.grip = measureGrip(template.scene)
    state.hand = template.grip ? model.getObjectByName(HAND_BONE) : null
    state.grip = template.grip

    state.mixer = new THREE.AnimationMixer(model)
    state.clips = new Map(template.animations.map((clip) => [clip.name.toLowerCase(), clip]))
    state.action = (name, once) => {
      const clip = state.clips.get(String(name).toLowerCase())
      if (!clip) return null
      const a = state.mixer.clipAction(clip)
      if (once) {
        a.setLoop(THREE.LoopOnce, 1)
        a.clampWhenFinished = true
      }
      a.play()
      a.setEffectiveWeight(0)
      return a
    }
    // Each loop as a pair: its own clip, and its carry clip for a tool in the hand. Either may be missing.
    const loop = (name) => ({ plain: state.action(name), carry: state.action(name + 'Carry') })
    state.idle = loop('Idle')
    state.walk = loop('Walk')
    state.climb = loop('Climb')
    state.brace = loop('Brace')
    state.airborne = Object.fromEntries(Object.entries(AIRBORNE_CLIPS).map(([humanoid, clip]) => [humanoid, loop(clip)]))
    state.oneShots = ONE_SHOTS.map((spec) => ({ ...spec, action: state.action(spec.clip, true), count: null }))
    state.gestures = new Map() // clip name -> one-shot, made the first time that gesture is seen
    state.gestureCount = null
    state.current = null // the one-shot in progress, and how long it has left
    state.idle.plain?.setEffectiveWeight(1)
    if (!state.idle.plain) state.walk.plain?.setEffectiveWeight(1)
    state.ready = true
    return true
  }

  function gesture(state, name) {
    const key = String(name || '').toLowerCase()
    if (!key) return null
    if (!state.gestures.has(key)) {
      const action = state.action(key, true)
      state.gestures.set(key, action ? { action, left: 0 } : null)
    }
    return state.gestures.get(key)
  }

  function start(state, shot, seconds, timeScale) {
    shot.action.reset().setEffectiveTimeScale(timeScale).play()
    shot.left = seconds
    state.current = shot
  }

  function update(entityId, { dt = 1 / 60, speed = 0, humanoidState = null, attributes = {}, carrying = false } = {}) {
    const state = states.get(entityId)
    if (!state?.ready) return
    // A new action: its gesture clip, else (an older model) the older counter's clip. Not on first sight.
    let gestured = false
    const gestures = attributes.Gestures
    if (gestures !== undefined && gestures !== state.gestureCount) {
      const shot = state.gestureCount !== null ? gesture(state, attributes.Gesture) : null
      if (shot) {
        start(state, shot, shot.action.getClip().duration, 1)
        gestured = true
      }
      state.gestureCount = gestures
    }
    for (const shot of state.oneShots) {
      const count = Number(attributes[shot.attribute] || 0)
      if (count !== shot.count) {
        if (shot.count !== null && shot.action && !gestured) {
          start(state, shot, shot.seconds, shot.action.getClip().duration / shot.seconds)
        }
        shot.count = count
      }
    }
    if (state.current) {
      state.current.left -= dt
      // Knocked down (an earthquake), the body stays on the ground in Stagger's last pose until it gets up (WakeUp).
      const down = attributes.KnockedDown === true && state.current === state.gestures.get('stagger')
      if (state.current.left <= 0 && !down) state.current = null
    }
    const playing = state.current
    const pick = (pair) => (carrying && pair.carry) || pair.plain // the clip a loop plays now, if any
    const climbing = attributes.Climbing === true && Boolean(pick(state.climb))
    const bracing = attributes.Bracing === true && Boolean(pick(state.brace)) && !climbing
    const holding = climbing || bracing // a held loop: nothing else plays over it
    const airborne = humanoidState === 'Jumping' || humanoidState === 'Freefall'
    const inAir = airborne && !holding && !playing ? pick(state.airborne[humanoidState]) : null
    const moving = speed > 0.5 && !airborne && !playing && !holding
    const blend = (action, target, rate) => {
      if (!action) return
      const w = action.getEffectiveWeight()
      action.setEffectiveWeight(w + (target - w) * Math.min(1, dt * rate))
    }
    // A loop on: the clip it plays now fades in, its other clip (with or without the tool) out.
    const fade = (pair, on, rate) => {
      const now = pick(pair)
      for (const action of [pair.plain, pair.carry]) blend(action, on && action === now ? 1 : 0, rate)
    }
    // A gesture and an older counter can name the same clip, and so share one action: blend each action once.
    const shotActions = new Set(state.oneShots.map((shot) => shot.action))
    for (const shot of state.gestures.values()) if (shot) shotActions.add(shot.action)
    for (const action of shotActions) blend(action, action && action === playing?.action && !holding ? 1 : 0, 14)
    for (const pair of Object.values(state.airborne)) fade(pair, Boolean(inAir) && pick(pair) === inAir, 10)
    fade(state.climb, climbing, 10)
    fade(state.brace, bracing, 10)
    const walking = moving || !pick(state.idle) // a model with no idle (for this hand) walks when it stands too
    fade(state.walk, walking, 8)
    fade(state.idle, !(moving || playing || holding || inAir), 8)
    if (moving && pick(state.walk)) {
      // Feet keep pace with the body: the clip's stride, scaled with the model, at the body's real speed.
      const pace = Math.min(3, Math.max(0.5, speed / (WALK_STRIDE_SPEED * state.scale)))
      for (const action of [state.walk.plain, state.walk.carry]) action?.setEffectiveTimeScale(pace)
    }
    state.mixer.update(dt)
  }

  return {
    upsert,
    update,
    // The body's grip in the world as it is posed now (call after update): at the middle of its right mitten, turned
    // as the hand is (X towards the thumb, Y along the fingers, Z out of the palm), at the world's own scale. Into
    // `out`; null until the body is drawn, or when its model has no hand.
    grip(entityId, out) {
      const state = states.get(entityId)
      if (!state?.ready || !state.hand) return null
      state.hand.updateWorldMatrix(true, false)
      state.hand.matrixWorld.decompose(gripAt, gripTurn, gripScale)
      gripAt.copy(state.grip).applyMatrix4(state.hand.matrixWorld)
      return out.compose(gripAt, gripTurn, unit)
    },
    remove: (entityId) => states.delete(entityId),
    clear: () => states.clear(),
    // For checks: each character's one-shot in progress, the clips that weigh in now, and how far into each it is.
    debug: () => [...states.entries()].filter(([, state]) => state.ready).map(([id, state]) => {
      const weighing = state.mixer._actions.filter((a) => a.getEffectiveWeight() > 0.05)
      return {
        id,
        current: state.current?.action.getClip().name ?? null,
        weights: Object.fromEntries(weighing.map((a) => [a.getClip().name, Number(a.getEffectiveWeight().toFixed(2))])),
        times: Object.fromEntries(weighing.map((a) => [a.getClip().name, Number(a.time.toFixed(3))])),
      }
    }),
  }
}
