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
      if (!node.isMesh) return
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
      template.animations = gltf.animations || []
      template.animated = skinned || template.animations.length > 0
      template.box = new THREE.Box3().setFromObject(scene) // every part, in the rest pose
      template.height = Math.max(template.box.getSize(new THREE.Vector3()).y, 1e-6)
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
    // The model's transform inside its part: turned by the yaw offset, scaled to the part's height, centred.
    fit(template, size, yawOffsetDeg, out) {
      const scale = (size?.[1] ?? 5) / template.height
      out.makeScale(scale, scale, scale)
      out.setPosition(-template.center.x * scale, -template.center.y * scale, -template.center.z * scale)
      if (yawOffsetDeg) out.premultiply(new THREE.Matrix4().makeRotationY(THREE.MathUtils.degToRad(yawOffsetDeg)))
      return out
    },
    dispose() {
      templates.clear()
    },
  }
}

// Godling (art/build_godling.py) and any other animated model. The clips are driven by the player's attributes:
// a one-shot clip each time a counter goes up, Climb for as long as "Climbing" is true, Walk at the body's speed.
const WALK_STRIDE_SPEED = 0.655 // model metres per second the Walk clip covers at normal speed
const ONE_SHOTS = [
  { attribute: 'Reaches', clip: 'PickUp', seconds: 1.1 }, // the world lifts a block in 1.0 s, lowers one in 1.2 s
  { attribute: 'Strikes', clip: 'Strike', seconds: 1.0 }, // a hammer blow on the quarry
]

export function createCharacterController(models) {
  const states = new Map()

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

    state.mixer = new THREE.AnimationMixer(model)
    const action = (name, once) => {
      const clip = template.animations.find((c) => c.name.toLowerCase() === name.toLowerCase())
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
    state.idle = action('Idle')
    state.walk = action('Walk')
    state.climb = action('Climb')
    state.oneShots = ONE_SHOTS.map((spec) => ({ ...spec, action: action(spec.clip, true), count: null, left: 0 }))
    state.idle?.setEffectiveWeight(1)
    if (!state.idle) state.walk?.setEffectiveWeight(1)
    state.ready = true
    return true
  }

  function update(entityId, { dt = 1 / 60, speed = 0, humanoidState = null, attributes = {} } = {}) {
    const state = states.get(entityId)
    if (!state?.ready) return
    let playing = null // the one-shot clip in progress, if any; a new one cuts an older one short
    for (const shot of state.oneShots) {
      const count = Number(attributes[shot.attribute] || 0)
      if (count !== shot.count) {
        if (shot.count !== null && shot.action) {
          shot.action.reset().setEffectiveTimeScale(shot.action.getClip().duration / shot.seconds).play()
          shot.left = shot.seconds
          for (const other of state.oneShots) if (other !== shot) other.left = 0
        }
        shot.count = count
      }
      shot.left = Math.max(0, shot.left - dt)
      if (shot.left > 0) playing = shot
    }
    const climbing = attributes.Climbing === true && Boolean(state.climb)
    const airborne = humanoidState === 'Jumping' || humanoidState === 'Freefall'
    const moving = speed > 0.5 && !airborne && !playing && !climbing
    const blend = (action, target, rate) => {
      if (!action) return
      const w = action.getEffectiveWeight()
      action.setEffectiveWeight(w + (target - w) * Math.min(1, dt * rate))
    }
    for (const shot of state.oneShots) blend(shot.action, shot === playing && !climbing ? 1 : 0, 14)
    blend(state.climb, climbing ? 1 : 0, 10)
    blend(state.walk, moving || !state.idle ? 1 : 0, 8)
    blend(state.idle, moving || playing || climbing ? 0 : 1, 8)
    if (state.walk && moving) {
      // Feet keep pace with the body: the clip's stride, scaled with the model, at the body's real speed.
      state.walk.setEffectiveTimeScale(Math.min(3, Math.max(0.5, speed / (WALK_STRIDE_SPEED * state.scale))))
    }
    state.mixer.update(dt)
  }

  return {
    upsert,
    update,
    remove: (entityId) => states.delete(entityId),
    clear: () => states.clear(),
  }
}
