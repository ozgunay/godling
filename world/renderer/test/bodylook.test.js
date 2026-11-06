import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import { CSM } from 'three/addons/csm/CSM.js'
import { CLEAR, createBodyLook, FADE, GLOW, SHOCK, SMOKE } from '../src/bodylook.js'

// A body as the character controller hangs it under its root: meshes whose material the model shares.
function body() {
  const shared = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x000000 })
  const root = new THREE.Group()
  root.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), shared))
  root.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), [shared, shared]))
  return { root, shared }
}

const named = (scene, name) => scene.children.filter((c) => c.name === name)
const glows = (scene) => named(scene, 'GodlingRebirthGlow')
const steady = () => 0.5 // no randomness: the shake and the arcs stay put

describe('bodylook: death — a dead body fades before it is born again, and comes back in a glow', () => {
  it('leaves a living body as it is, and its shared materials untouched', () => {
    const scene = new THREE.Scene()
    const look = createBodyLook(scene)
    const { root, shared } = body()
    look.update(1, root, {}, [0, 2.5, 0], 0.1)
    expect(root.children[0].material).toBe(shared)
    expect(look.info()).toEqual([{ id: 1, dead: false, opacity: 1, char: 0, shock: false, glow: false, smoke: 0 }])
  })

  it('lies there whole until the last seconds, fades on its own clock between the world\'s, and is gone at the end', () => {
    const scene = new THREE.Scene()
    const look = createBodyLook(scene)
    const { root, shared } = body()
    look.update(1, root, { Dead: true, DeadFor: 30 }, [5, 2.5, 5], 0.1)
    expect(look.info()[0].opacity).toBe(1)
    look.update(1, root, { Dead: true, DeadFor: FADE }, [5, 2.5, 5], 0.1)
    expect(look.info()[0].opacity).toBe(1)
    look.update(1, root, { Dead: true, DeadFor: FADE }, [5, 2.5, 5], 1.5) // the same whole second: its own clock runs
    const half = look.info()[0].opacity
    expect(half).toBeCloseTo((FADE - 1.5) / FADE)
    const own = root.children[0].material
    expect(own).not.toBe(shared) // its own copy: the model's material is not faded with it
    expect(own.transparent).toBe(true)
    expect(own.depthWrite).toBe(false)
    expect(own.opacity).toBeCloseTo(half)
    expect(root.children[1].material.every((m) => m !== shared && m.opacity === own.opacity)).toBe(true)
    expect(shared.opacity).toBe(1)
    root.visible = true
    look.update(1, root, { Dead: true, DeadFor: 1 }, [5, 2.5, 5], 1)
    look.update(1, root, { Dead: true, DeadFor: 1 }, [5, 2.5, 5], 1)
    expect(look.info()[0].opacity).toBe(0)
    expect(root.visible).toBe(false)
  })

  it('born again, it is whole at once and rises in a glow that fades and goes', () => {
    const scene = new THREE.Scene()
    const look = createBodyLook(scene)
    const { root } = body()
    look.update(1, root, { Dead: true, DeadFor: 0 }, [5, 2.5, 5], 0.1)
    expect(look.info()[0].opacity).toBe(0)
    look.update(1, root, { Dead: false }, [15, 2.5, -27.5], 0.1)
    const own = root.children[0].material
    expect(own.opacity).toBe(1)
    expect(own.transparent).toBe(false)
    expect(own.depthWrite).toBe(true)
    const [glow] = glows(scene)
    const [gx, gy, gz] = glow.position.toArray()
    expect([gx, gz]).toEqual([15, -27.5]) // at the start spot,
    expect(gy).toBeCloseTo(0.1) // at its feet
    look.update(1, root, { Dead: false }, [15, 2.5, -27.5], GLOW / 2)
    expect(glow.children[0].material.opacity).toBeCloseTo(0.55 * (1 - (0.1 + GLOW / 2) / GLOW))
    expect(glow.scale.x).toBeGreaterThan(1)
    look.update(1, root, { Dead: false }, [15, 2.5, -27.5], GLOW)
    expect(glows(scene)).toHaveLength(0)
    expect(look.info()[0].glow).toBe(false)
  })

  it('a page that first sees the body dead shows no glow until it was seen dying; a new model starts afresh', () => {
    const scene = new THREE.Scene()
    const look = createBodyLook(scene)
    const first = body()
    look.update(2, first.root, {}, [0, 2.5, 0], 0.1)
    expect(glows(scene)).toHaveLength(0)
    look.update(2, first.root, { Dead: true, DeadFor: 2 }, [0, 2.5, 0], 0.1)
    const second = body() // the controller hung another root (a model swapped)
    look.update(2, second.root, { Dead: true, DeadFor: 2 }, [0, 2.5, 0], 0.1)
    expect(second.root.children[0].material).not.toBe(second.shared)
  })

  it('registers its own materials for cascaded lighting, which survives rebirth', () => {
    const scene = new THREE.Scene()
    const csm = new CSM({ parent: scene, camera: new THREE.PerspectiveCamera(), cascades: 3 })
    const { root, shared } = body()
    csm.setupMaterial(shared)
    const look = createBodyLook(scene, { onMaterial: (m) => csm.setupMaterial(m) })
    look.update(1, root, { Dead: true, DeadFor: 2 }, [0, 2.5, 0], 0)
    look.update(1, root, { Dead: false }, [0, 2.5, 0], 0)
    root.traverse((node) => {
      if (!node.isMesh) return
      for (const material of [].concat(node.material)) {
        expect(material.defines).toMatchObject({ USE_CSM: 1, CSM_CASCADES: 3 })
        const shader = { uniforms: {} }
        material.onBeforeCompile(shader)
        expect(Object.keys(shader.uniforms)).toEqual(['CSM_cascades', 'cameraNear', 'shadowFar'])
      }
    })
    look.dispose()
    csm.dispose()
    csm.remove()
  })

  it('restores shared materials and disposes only its own copies on replacement, pruning, reset and disposal', () => {
    const scene = new THREE.Scene()
    const registered = new Set()
    const look = createBodyLook(scene, { onMaterial: (m) => {
      registered.add(m)
      return () => registered.delete(m)
    } })
    const bodies = Array.from({ length: 4 }, body)
    const originals = bodies.map(({ shared }) => vi.spyOn(shared, 'dispose'))
    const own = ({ root }) => root.children.flatMap((node) => [].concat(node.material)).map((m) => vi.spyOn(m, 'dispose'))
    look.update(1, bodies[0].root, { Dead: true, DeadFor: 2 }, [0, 2.5, 0], 0)
    const first = own(bodies[0])
    look.update(1, bodies[1].root, { Dead: true, DeadFor: 2 }, [0, 2.5, 0], 0)
    const second = own(bodies[1])
    expect(first.every((dispose) => dispose.mock.calls.length === 1)).toBe(true)
    look.prune(new Set())
    expect(second.every((dispose) => dispose.mock.calls.length === 1)).toBe(true)
    look.update(1, bodies[2].root, { Dead: true, DeadFor: 2 }, [0, 2.5, 0], 0)
    const third = own(bodies[2])
    look.update(1, bodies[2].root, {}, [0, 2.5, 0], 0)
    look.reset()
    expect(third.every((dispose) => dispose.mock.calls.length === 1)).toBe(true)
    expect(glows(scene)).toHaveLength(0)
    expect(look.info()).toEqual([])
    look.update(1, bodies[3].root, { Dead: true, DeadFor: 2 }, [0, 2.5, 0], 0)
    const fourth = own(bodies[3])
    look.dispose()
    expect(fourth.every((dispose) => dispose.mock.calls.length === 1)).toBe(true)
    for (const { root, shared } of bodies) {
      expect(root.children[0].material).toBe(shared)
      expect(root.children[1].material).toEqual([shared, shared])
      expect(shared.opacity).toBe(1)
    }
    expect(originals.every((dispose) => dispose.mock.calls.length === 0)).toBe(true)
    expect(registered.size).toBe(0)
  })
})

describe('bodylook: a storm\'s strike — electrocuted, then charred for a minute, then its own colours', () => {
  it('electrocuted for a moment: a blue-white flicker, arcs over it, and a shake; then charred, smoking', () => {
    const scene = new THREE.Scene()
    const look = createBodyLook(scene, { random: steady })
    const { root, shared } = body()
    look.update(1, root, {}, [5, 2.5, 5], 0.1) // seen before: nothing that happened before plays
    root.position.set(5, 2.5, 5)
    look.update(1, root, { Struck: 1, Scorched: 60 }, [5, 2.5, 5], 0.01)
    expect(look.info()[0].shock).toBe(true)
    const own = root.children[0].material
    expect(own).not.toBe(shared)
    expect(own.emissiveIntensity).toBeGreaterThan(0)
    expect(own.emissive.b).toBeGreaterThan(0.2) // blue-white
    expect(own.color.r).toBeLessThan(0.2) // charred from the first moment
    expect(shared.color.getHex()).toBe(0xffffff)
    const [arcs] = named(scene, 'GodlingShockArcs')
    expect(arcs.geometry.attributes.position.count).toBeGreaterThan(0)
    const positions = arcs.geometry.attributes.position.array
    expect(positions.some((v) => v !== 0)).toBe(true) // the arcs crawl over the body
    expect(named(scene, 'GodlingSmoke')).toHaveLength(1)
    look.update(1, root, { Struck: 1, Scorched: 60 }, [5, 2.5, 5], SHOCK)
    expect(look.info()[0].shock).toBe(false)
    expect(named(scene, 'GodlingShockArcs')).toHaveLength(0) // the arcs go with the shock
    expect(own.emissiveIntensity).toBe(1) // its own glow back
    expect(own.emissive.getHex()).toBe(0x000000)
    expect(look.info()[0].char).toBe(1)
    expect(look.info()[0].smoke).toBeGreaterThan(0)
  })

  it('stays charred, smokes only at first, and turns back to its own colours over the last seconds', () => {
    const scene = new THREE.Scene()
    const look = createBodyLook(scene, { random: steady })
    const { root } = body()
    look.update(1, root, {}, [0, 2.5, 0], 0.1)
    look.update(1, root, { Struck: 1, Scorched: 60 }, [0, 2.5, 0], 0.1)
    for (let t = 0; t < SMOKE + 3; t += 0.5) look.update(1, root, { Struck: 1, Scorched: 60 - Math.floor(t) }, [0, 2.5, 0], 0.5)
    expect(look.info()[0].char).toBe(1)
    expect(look.info()[0].smoke).toBe(0) // no more smoke: the wisps have risen and gone
    expect(named(scene, 'GodlingSmoke')).toHaveLength(0)
    look.update(1, root, { Struck: 1, Scorched: CLEAR / 2 }, [0, 2.5, 0], 0.01)
    expect(look.info()[0].char).toBeCloseTo(0.5)
    const own = root.children[0].material
    expect(own.color.r).toBeGreaterThan(0.4) // half way back to white
    look.update(1, root, { Struck: 1, Scorched: 0 }, [0, 2.5, 0], 0.1)
    expect(look.info()[0].char).toBe(0)
    expect(own.color.getHex()).toBe(0xffffff)
  })

  it('a page that first sees a charred body shows the char, without the shock it did not see', () => {
    const scene = new THREE.Scene()
    const look = createBodyLook(scene)
    const { root } = body()
    look.update(1, root, { Struck: 2, Scorched: 40 }, [0, 2.5, 0], 0.1)
    expect(look.info()[0].shock).toBe(false)
    expect(look.info()[0].char).toBe(1)
    expect(named(scene, 'GodlingSmoke')).toHaveLength(0)
  })

  it('clears shock, char, smoke and private materials when replay seeks to another moment', () => {
    const scene = new THREE.Scene()
    const look = createBodyLook(scene, { random: steady })
    const { root, shared } = body()
    look.update(1, root, {}, [0, 2.5, 0], 0)
    look.update(1, root, { Struck: 1, Scorched: 60 }, [0, 2.5, 0], 0.1)
    const own = root.children[0].material
    const dispose = vi.spyOn(own, 'dispose')
    expect(look.info()[0]).toMatchObject({ char: 1, shock: true })
    expect(scene.children.length).toBeGreaterThan(0)
    look.reset()
    expect(dispose).toHaveBeenCalledTimes(1)
    expect(root.children[0].material).toBe(shared)
    expect(scene.children).toHaveLength(0)
    look.update(1, root, {}, [0, 2.5, 0], 0)
    expect(look.info()[0]).toMatchObject({ char: 0, shock: false, glow: false, smoke: 0 })
  })

  it('lets go of bodies no longer drawn, glow, arcs, smoke and all, and of everything when disposed', () => {
    const scene = new THREE.Scene()
    const look = createBodyLook(scene)
    const { root } = body()
    look.update(1, root, { Dead: true, DeadFor: 1 }, [0, 2.5, 0], 0.1)
    look.update(1, root, {}, [0, 2.5, 0], 0.1)
    const struck = body().root
    look.update(3, struck, {}, [0, 2.5, 0], 0.1)
    look.update(3, struck, { Struck: 1, Scorched: 60 }, [0, 2.5, 0], 0.1)
    look.update(4, body().root, { Dead: true, DeadFor: 1 }, [0, 2.5, 0], 0.1)
    look.update(4, body().root, {}, [0, 2.5, 0], 0.1)
    expect(glows(scene)).toHaveLength(2)
    expect(named(scene, 'GodlingShockArcs')).toHaveLength(1)
    look.prune(new Set([4]))
    expect(glows(scene)).toHaveLength(1)
    expect(named(scene, 'GodlingShockArcs')).toHaveLength(0)
    expect(named(scene, 'GodlingSmoke')).toHaveLength(0)
    expect(look.info().map((l) => l.id)).toEqual([4])
    const again = body().root
    look.update(5, again, {}, [0, 2.5, 0], 0.1)
    look.update(5, again, { Struck: 1, Scorched: 60 }, [0, 2.5, 0], 0.1)
    look.dispose()
    expect(scene.children).toHaveLength(0)
    expect(look.info()).toEqual([])
  })
})
