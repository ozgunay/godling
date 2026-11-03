import * as THREE from 'three'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { bubbleSheet, createBubbles } from '../src/bubble.js'
import { install2d, renders } from './gl.js'

vi.mock('three', async () => (await import('./gl.js')).threeWithFakeGL())
beforeAll(install2d)

// A model as models.js hands it over: a scene with a mesh, and the art's outline specks.
function template() {
  const scene = new THREE.Group()
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(1, 2, 1), new THREE.MeshStandardMaterial()))
  const specks = new THREE.Mesh(new THREE.BoxGeometry(0.01, 0.01, 0.01), new THREE.MeshBasicMaterial({ name: 'bounds' }))
  specks.position.set(5, 5, 5)
  scene.add(specks)
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), [new THREE.MeshStandardMaterial(), new THREE.MeshStandardMaterial()]))
  return { scene }
}

const models = (loaded = true) => ({ get: (url) => (loaded ? template() : (url, null)) })
const resolve = (url) => url.replace('asset://', '/assets/')

function sprites(scene) {
  return scene.children.filter((o) => o.isSprite)
}

describe('thought bubbles', () => {
  it('pops up a new thought over the head, stays a while and fades', () => {
    const scene = new THREE.Scene()
    const bubbles = createBubbles(scene, models(), resolve)
    bubbles.update(1, [0, 2.5, 0], { Thoughts: 0 }, false, 0.1) // no thought yet: no bubble
    expect(sprites(scene)).toHaveLength(0)
    bubbles.update(1, [0, 2.5, 0], { Thoughts: 1, Thought: 'fire', Feeling: 'happy' }, false, 0.1)
    const [sprite] = sprites(scene)
    expect(sprite.visible).toBe(true)
    expect(sprite.position.y).toBeGreaterThan(5)
    const ctx = sprite.material.map.image.getContext('2d')
    expect(ctx.fillStyle).toBeTruthy()
    for (let t = 0; t < 4; t++) bubbles.update(1, [0, 2.5, 0], { Thoughts: 1, Thought: 'fire', Feeling: 'happy' }, false, 1)
    expect(sprite.material.opacity).toBe(1)
    bubbles.update(1, [0, 2.5, 0], { Thoughts: 1, Thought: 'fire', Feeling: 'happy' }, true, 0.1) // the camera is in its head
    expect(sprite.visible).toBe(false)
    for (let t = 0; t < 7; t++) bubbles.update(1, [0, 2.5, 0], { Thoughts: 1, Thought: 'fire', Feeling: 'happy' }, false, 1)
    expect(sprite.visible).toBe(false) // shown long enough
    bubbles.update(1, [0, 2.5, 0], { Thoughts: 2, Thought: 'block', Feeling: 'lonely' }, false, 0.1)
    expect(sprite.visible).toBe(true) // the next thought, a model drawn into a picture
    expect(renders.count).toBeGreaterThan(0)
    bubbles.update(1, [0, 2.5, 0], { Thoughts: 3, Thought: 'shelter', Feeling: 'bored' }, false, 0.1)
    bubbles.update(1, [0, 2.5, 0], { Thoughts: 4, Thought: 'nothing-known', Feeling: 'calm' }, false, 0.1)
    const info = bubbles.info()
    expect(info[0]).toMatchObject({ id: 1, count: 4, thing: 'nothing-known', visible: true })
    bubbles.prune(new Set([1]))
    expect(sprites(scene)).toHaveLength(1)
    bubbles.dispose()
    expect(sprites(scene)).toHaveLength(0)
  })

  it('waits for its models, and after a while shows an empty cloud', () => {
    let now = 0
    vi.spyOn(performance, 'now').mockImplementation(() => now)
    const scene = new THREE.Scene()
    const bubbles = createBubbles(scene, models(false), resolve)
    bubbles.update(2, [0, 0, 0], { Thoughts: 5, Thought: 'log', Feeling: 'proud' }, false, 0.1)
    const [sprite] = sprites(scene)
    expect(sprite.visible).toBe(false) // its model is on the way
    now = 9000
    bubbles.update(2, [0, 0, 0], { Thoughts: 5, Thought: 'log', Feeling: 'proud' }, false, 0.1)
    expect(sprite.visible).toBe(true)
    const unknown = createBubbles(new THREE.Scene(), models(), () => null) // the asset folder is not known yet
    unknown.update(3, [0, 0, 0], { Thoughts: 1, Thought: 'axe', Feeling: 'calm' }, false, 0.1)
    expect(unknown.info()[0].drawn).toBeNull()
  })

  it('draws every picture onto one sheet, naming those it could not draw', () => {
    const sheet = bubbleSheet(models(), resolve)
    expect(sheet.url.startsWith('data:image/png')).toBe(true)
    expect(sheet.missing).toEqual([])
    const waiting = bubbleSheet(models(false), resolve)
    expect(waiting.missing).toContain('coconut')
    expect(waiting.missing).not.toContain('fire') // drawn by hand
  })
})
