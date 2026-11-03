import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createBlasts } from '../src/blast.js'

const HIGH = { blastDetail: 1, blastGlow: 384, blastSoft: 256, blastChunks: 24, blastLight: true }
const LOW = { blastDetail: 0.4, blastGlow: 128, blastSoft: 96, blastChunks: 8, blastLight: false }

const meteor = (id, y) => ({ id, position: [10, y, 0], size: [2.5, 2.5, 2.5], render: { role: 'Stone' },
  attributes: { SkyEvent: 'Meteor', SkyId: 4 } })
const marker = (id, more = {}) => ({ id, position: [10, 0.5, 0], render: { role: 'Blast' }, attributes: { SkyId: 4, Radius: 7, ...more } })
const crater = (id) => ({ id, position: [10, 0.3, 0], size: [14, 0.6, 14], render: { role: 'Crater' }, attributes: { SkyId: 4 } })

function run(blasts, from, to, dt = 1 / 30, camera = new THREE.PerspectiveCamera()) {
  let flare = 0
  for (let t = from; t < to; t += dt) flare = Math.max(flare, blasts.update({ time: t, dt, daylight: 1, wind: new THREE.Vector2(0.2, 0), camera }))
  return flare
}

describe('meteor blasts', () => {
  it('trails a falling meteor, then blasts where its marker appears', () => {
    const scene = new THREE.Scene()
    const materials = []
    const blasts = createBlasts(scene, HIGH, { onMaterial: (m) => materials.push(m) })
    expect(materials).toHaveLength(1) // the chunks are lit
    let y = 80
    for (let k = 0; k < 20; k++, y -= 2) { // falling at 60 a second
      blasts.watch(meteor(1, y), 1 / 30)
      blasts.update({ time: k / 30, dt: 1 / 30, daylight: 1, camera: new THREE.PerspectiveCamera() })
    }
    expect(blasts.info().meteors).toBe(1)
    expect(blasts.info().glow).toBeGreaterThan(0)
    blasts.watch(meteor(1, y), 0) // no time passed: no speed
    blasts.watch(marker(2), 1 / 30)
    blasts.watch(marker(2), 1 / 30) // the same marker: played once
    blasts.watch(crater(3), 1 / 30)
    blasts.update({ time: 1, dt: 1 / 30, daylight: 0, camera: new THREE.PerspectiveCamera() })
    const info = blasts.info()
    expect(info.blasts).toBe(1)
    expect(info.chunks).toBe(20)
    expect(info.light).toBeGreaterThan(500)
    const near = new THREE.Vector3(12, 2, 0)
    expect(blasts.jolt(near)).toBeGreaterThan(0.5)
    expect(blasts.jolt(new THREE.Vector3(500, 0, 0))).toBeLessThan(0.01)
    run(blasts, 1.033, 3.5) // the chunks bounce, settle and sink; the crater smoulders
    expect(blasts.info().chunks).toBe(0)
    expect(blasts.info().light).toBe(0)
    expect(blasts.jolt(near)).toBe(0)
    run(blasts, 3.5, 6.5)
    expect(blasts.info().blasts).toBe(0) // gone after it lingered
    blasts.prune(new Set())
    expect(blasts.info().meteors).toBe(0)
    blasts.dispose()
    expect(scene.children).toHaveLength(0)
  })

  it('flares the ambient light on a tier without the flash\'s own light', () => {
    const scene = new THREE.Scene()
    const blasts = createBlasts(scene, LOW)
    blasts.watch({ id: 9, position: [0, 0, 0], render: { role: 'Blast' }, attributes: {} }, 0.1) // no SkyId, no radius
    const camera = new THREE.PerspectiveCamera()
    camera.position.set(0, 10, 10)
    const flare = blasts.update({ time: 0, dt: 0.016, daylight: 0.5, camera })
    expect(flare).toBeGreaterThan(0.5)
    expect(blasts.info().light).toBeNull()
    expect(blasts.info().chunks).toBe(8) // the low tier's pool
    expect(run(blasts, 0.6, 1, 0.1, camera)).toBe(0)
  })

  it('ignores what is not a meteor, and a crater may come a moment after its blast', () => {
    const blasts = createBlasts(new THREE.Scene(), {})
    blasts.watch({ id: 1, position: [0, 0, 0], render: { role: 'Stone' }, attributes: {} }, 0.1)
    blasts.watch({ id: 2, position: [0, 0, 0], attributes: { SkyEvent: 'Meteor' } }, 0.1)
    expect(blasts.info().meteors).toBe(0)
    blasts.watch(marker(5, { Radius: 50 }), 0.1) // capped at 20
    blasts.update({ time: 0, dt: 0.1, daylight: 1, camera: new THREE.PerspectiveCamera() })
    blasts.watch({ id: 6, position: [10, 0.3, 0], render: { role: 'Crater' }, attributes: { SkyId: 4 } }, 0.1)
    blasts.update({ time: 0.2, dt: 0.1, daylight: 1, camera: new THREE.PerspectiveCamera() })
    expect(blasts.info().blasts).toBe(1)
    blasts.watch({ id: 7, position: [0, 0, 0], render: { role: 'Crater' } }, 0.1) // no size, no SkyId
    expect(blasts.info().light).toBe(null)
  })
})
