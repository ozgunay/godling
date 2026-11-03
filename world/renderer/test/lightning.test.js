import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { boltOf, createLightning, detailOf, lightAt, seedOf, strokesOf } from '../src/lightning.js'
import { TIERS } from '../src/quality.js'

const ground = new THREE.Vector3(20, 0.5, -30)
// The world's marker (main.lua lightningOn): a thin post standing on the strike point, which it also names.
const marked = { SkyId: 4, StrikeX: 20, StrikeY: 0.5, StrikeZ: -30 }
const marker = (id, attributes = {}, position = [20, 15.5, -30]) =>
  ({ id, position, size: [0.35, 30, 0.35], render: { role: 'SkyFlash' }, attributes })
const bolts = (scene) => scene.children.filter((c) => c.name === 'GodlingLightning')

function play(lightning, from, to, dt = 1 / 60, daylight = 1) {
  const seen = []
  for (let t = from; t < to; t += dt) seen.push({ t, flare: lightning.update({ time: t, daylight }), ...lightning.info() })
  return seen
}

describe('lightning', () => {
  it('cuts the same bolt from the same strike, from the clouds down to the strike point', () => {
    const a = boltOf(7, ground)
    const b = boltOf(7, ground)
    expect(a.map((s) => s.b.toArray())).toEqual(b.map((s) => s.b.toArray())) // every viewer sees the same bolt
    expect(boltOf(8, ground).map((s) => s.b.x)).not.toEqual(a.map((s) => s.b.x))
    const main = a.filter((s) => s.kind === 1)
    expect(main).toHaveLength(128) // halved and bent seven times
    expect(main[0].a.y).toBe(88) // out of the clouds
    expect(main.at(-1).b.toArray()).toEqual(ground.toArray()) // onto the strike point
    expect(Math.hypot(main[0].a.x - ground.x, main[0].a.z - ground.z)).toBeGreaterThan(9) // leaning, never a post
    // The leader reaches each point in turn, from 0 at the clouds to 1 on the ground, and never later than that.
    for (let i = 1; i < main.length; i++) expect(main[i].arriveA).toBeCloseTo(main[i - 1].arriveB, 9)
    expect(main[0].arriveA).toBe(0)
    expect(main.at(-1).arriveB).toBeCloseTo(1, 9)
    expect(a.every((s) => s.arriveA <= 1 && s.arriveB <= 1)).toBe(true) // a long fork is lit by the stroke all the same
    const forks = a.filter((s) => s.kind === 0)
    expect(forks.length).toBeGreaterThan(5 * 8)
    expect(Math.max(...forks.map((s) => s.bright))).toBeLessThan(0.75) // dimmer than the channel
    expect(Math.min(...forks.map((s) => s.b.y))).toBeGreaterThanOrEqual(ground.y + 1.9) // they end in the air
    const arcs = a.filter((s) => s.kind === 2)
    expect(arcs).toHaveLength(5 * 8 + 1) // and the glare
    expect(arcs.every((s) => s.arriveA === 1 && s.b.y < ground.y + 3)).toBe(true) // along the ground, at the stroke
  })

  it('is the same bolt on every tier, the weaker ones drawing less of it', () => {
    const key = (v) => v.toArray().map((n) => n.toFixed(6)).join()
    const high = boltOf(7, ground, detailOf(TIERS.high))
    const points = new Set(high.flatMap((s) => [key(s.a), key(s.b)]))
    for (const tier of [TIERS.medium, TIERS.low]) {
      const less = boltOf(7, ground, detailOf(tier))
      expect(less.length).toBeLessThan(high.length)
      expect(less.every((s) => points.has(key(s.a)) && points.has(key(s.b)))).toBe(true) // every point of it is the high's
    }
    const low = boltOf(7, ground, detailOf(TIERS.low))
    expect(low.filter((s) => s.kind === 1)).toHaveLength(32)
    expect(low.length).toBeLessThan(high.length / 3)
  })

  it('seeds a strike from all of its id', () => {
    expect(seedOf(7)).toBe(seedOf('7'))
    const seeds = Array.from({ length: 1000 }, (_, k) => seedOf(2 ** 45 + k)) // ids as large as the world's
    expect(new Set(seeds).size).toBe(1000)
    expect(seeds.every((s) => Number.isInteger(s) && s >= 0 && s < 2 ** 32)).toBe(true)
  })

  it('comes down as a faint stepped leader, strikes, flickers with weaker restrikes and fades', () => {
    for (let seed = 0; seed < 20; seed++) {
      const strokes = strokesOf(seed)
      expect(strokes.length).toBeGreaterThanOrEqual(2)
      expect(strokes.length).toBeLessThanOrEqual(4)
      expect(strokes[0]).toEqual({ at: 0.16, peak: 1 })
      for (let i = 1; i < strokes.length; i++) {
        expect(strokes[i].at - strokes[i - 1].at).toBeGreaterThanOrEqual(0.07)
        expect(strokes[i].at - strokes[i - 1].at).toBeLessThanOrEqual(0.13)
        expect(strokes[i].peak).toBeLessThan(strokes[i - 1].peak)
      }
    }
    const strokes = [{ at: 0.16, peak: 1 }, { at: 0.26, peak: 0.8 }]
    const early = lightAt(strokes, 0.03)
    expect(early.leader).toBeGreaterThan(0)
    expect(early.leader).toBeLessThan(0.4)
    expect(early.main).toBe(0) // only the leader's own faint light
    expect(early.feel).toBeLessThan(0.4)
    expect(lightAt(strokes, 0.04).leader).toBe(lightAt(strokes, 0.05).leader) // it comes down in steps
    expect(lightAt(strokes, 0.06).leader).toBeGreaterThan(lightAt(strokes, 0.05).leader)
    const strike = lightAt(strokes, 0.16)
    expect(strike).toMatchObject({ leader: 1, flash: 1, forks: 1 })
    const between = lightAt(strokes, 0.255)
    const restrike = lightAt(strokes, 0.26)
    expect(between.flash).toBeLessThan(0.2) // dark between strokes: the flicker
    expect(restrike.flash).toBeCloseTo(0.8, 5)
    expect(restrike.forks).toBeLessThan(0.4) // the restrike runs down the main channel
    const late = lightAt(strokes, 1)
    expect(late.flash).toBeLessThan(0.001)
    expect(late.main).toBeLessThan(0.02)
  })

  it('plays a marker once, where it says, lights the island, jolts the camera close by, and lets go', () => {
    const scene = new THREE.Scene()
    const light = new THREE.PointLight(0xffd29a, 0, 80, 1.5) // the meteor's flash light, shared
    const lightning = createLightning(scene, TIERS.high, { light })
    expect(scene.children.filter((c) => c.isLight)).toHaveLength(0) // none of its own
    lightning.update({ time: 0, daylight: 0 })
    lightning.watch(marker(9, marked))
    lightning.watch(marker(9, marked)) // the same marker: one strike
    lightning.watch({ id: 3, position: [0, 1, 0], render: { role: 'Stone' } })
    expect(lightning.info().strikes).toBe(1)
    const [mesh] = bolts(scene)
    expect(mesh.material.blending).toBe(THREE.AdditiveBlending) // added light, as games draw it
    expect(mesh.material.toneMapped).toBe(false)
    expect(mesh.geometry.getAttribute('look').count).toBe(lightning.info().segments * 4)
    const night = play(lightning, 0, 1.3, 1 / 60, 0)
    const peak = night.reduce((a, b) => (b.flash > a.flash ? b : a))
    expect(peak.t).toBeGreaterThanOrEqual(0.15)
    expect(peak.t).toBeLessThan(0.2)
    expect(peak.flare).toBeGreaterThan(1) // by night the island lights up
    expect(peak.light).toBeGreaterThan(600) // the first frame after the stroke
    expect(night.filter((s) => s.flash > 0.01).every((s) => s.light > 0)).toBe(true) // alone, it holds the light
    expect(light.position.toArray()).toEqual([20, 6.5, -30]) // above where it struck
    expect(night.at(-1).strikes).toBe(0) // gone after a second or so
    expect(night.at(-1).light).toBe(0)
    expect(bolts(scene)).toHaveLength(0)
    expect(lightning.exposure()).toBe(1)

    lightning.prune(new Set()) // the marker is gone: when the past is played again, it strikes again
    lightning.update({ time: 2, daylight: 1 })
    lightning.watch(marker(9, marked))
    const day = play(lightning, 2, 2.2, 1 / 60, 1)
    const dayPeak = day.reduce((a, b) => (b.flash > a.flash ? b : a))
    expect(dayPeak.flare).toBeLessThan(peak.flare / 4) // by day the flash is the exposure's, mostly
    lightning.update({ time: 2.17, daylight: 1 })
    expect(lightning.exposure()).toBeGreaterThan(1.2)
    expect(lightning.jolt(new THREE.Vector3(22, 2, -28))).toBeGreaterThan(0.25) // close by: the thunderclap
    expect(lightning.jolt(new THREE.Vector3(400, 2, 400))).toBeLessThan(0.01)
    lightning.dispose()
    expect(scene.children).toHaveLength(0)
  })

  it('shapes the bolt by the strike\'s id, not the marker\'s, at the strike point it names', () => {
    const shape = (entity) => {
      const scene = new THREE.Scene()
      const lightning = createLightning(scene, TIERS.medium)
      lightning.update({ time: 0 })
      lightning.watch(entity)
      return Array.from(bolts(scene)[0].geometry.getAttribute('position').array)
    }
    const live = shape(marker(9, marked))
    expect(shape(marker(70001, marked, [0, 0, 0]))).toEqual(live) // the past played again: another entity, the same bolt
    expect(shape(marker(12, { SkyId: 4 }))).toEqual(live) // an older world: the foot of the post it stands as
    expect(shape(marker(9, { ...marked, SkyId: 5 }))).not.toEqual(live)
  })

  it('shares the light: a brighter blast keeps it, and it is put out after', () => {
    const scene = new THREE.Scene()
    const light = new THREE.PointLight(0xffd29a, 0, 80, 1.5)
    const lightning = createLightning(scene, TIERS.medium, { light })
    lightning.update({ time: 0, daylight: 0 })
    lightning.watch(marker(9, marked))
    const seen = []
    for (let t = 0; t < 1.6; t += 1 / 60) {
      light.intensity = t > 0.9 && t < 1.1 ? 300 : 0 // a meteor's blast sets it first, every frame (blast.js)
      lightning.update({ time: t, daylight: 0 })
      seen.push({ t, light: light.intensity })
    }
    expect(Math.max(...seen.filter((s) => s.t < 0.3).map((s) => s.light))).toBeGreaterThan(600) // the strike's
    expect(seen.filter((s) => s.t > 0.92 && s.t < 1.08).every((s) => s.light === 300)).toBe(true) // the blast's
    expect(seen.at(-1).light).toBe(0)
  })

  it('keeps its materials: a strike never waits on a shader compile', () => {
    const scene = new THREE.Scene()
    const lightning = createLightning(scene, TIERS.low)
    const warm = scene.getObjectByName('GodlingLightningWarm') // drawn once at the start, to compile the shader
    expect(warm.frustumCulled).toBe(false)
    lightning.update({ time: 0 })
    expect(warm.parent).toBe(scene) // until it has been drawn
    warm.onAfterRender()
    lightning.update({ time: 0 })
    expect(warm.parent).toBeNull()
    let disposed = 0
    warm.material.addEventListener('dispose', () => { disposed += 1 })
    lightning.watch(marker(1, marked))
    expect(bolts(scene)[0].material).toBe(warm.material) // the compiled one
    play(lightning, 0, 1.5)
    lightning.watch(marker(2, marked))
    expect(bolts(scene)[0].material).toBe(warm.material) // the same one again
    lightning.watch(marker(3, marked)) // two at once: one more
    expect(lightning.info().materials).toBe(2)
    expect(disposed).toBe(0)
    lightning.dispose()
    expect(disposed).toBe(1)
    expect(scene.children).toHaveLength(0)
  })

  it('on the low tier: no light, a smaller bolt, the island still flashing', () => {
    const scene = new THREE.Scene()
    const lightning = createLightning(scene, TIERS.low)
    lightning.update({ time: 0, daylight: 0.5 })
    lightning.watch(marker('bolt-4'))
    expect(lightning.info().segments).toBeLessThan(100)
    const seen = play(lightning, 0, 0.3, 1 / 30, 0.5)
    expect(Math.max(...seen.map((s) => s.flare))).toBeGreaterThan(0.5)
    expect(seen.every((s) => s.light === null)).toBe(true)
  })
})
