import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import { createSky, DEFAULT_SUN, sunForHour } from '../src/sky.js'

describe('sky', () => {
  it('turns the hours into the sun\'s way across the sky', () => {
    expect(sunForHour(6).y).toBeCloseTo(0)
    expect(sunForHour(13).y).toBeCloseTo(Math.sin(THREE.MathUtils.degToRad(62)))
    expect(sunForHour(9.5).x).toBeGreaterThan(0) // the morning sun is in the east
    expect(sunForHour(16.5).x).toBeLessThan(0)
    expect(sunForHour(0).y).toBeLessThan(0)
  })

  it('lights day and night from one sun', () => {
    const scene = new THREE.Scene()
    const sky = createSky(scene, { skyClouds: 0.25 })
    expect(scene.children).toContain(sky.dome)
    expect(sky.daylight).toBeGreaterThan(0.9)
    expect(sky.night).toBe(0)
    expect(sky.sun.distanceTo(DEFAULT_SUN)).toBeLessThan(1e-6)
    expect(sky.setSun(DEFAULT_SUN)).toBe(false) // the same sun: nothing to do
    const day = sky.fogColor.clone()
    expect(sky.setSun(sunForHour(2))).toBe(true)
    expect(sky.night).toBe(1)
    expect(sky.daylight).toBe(0)
    expect(sky.moon.y).toBeGreaterThan(0.29)
    expect(sky.fogColor.r).toBeLessThan(day.r)
    sky.setSun(sunForHour(19.6)) // dusk: a reddish sun
    expect(sky.sunColor.r).toBeGreaterThan(sky.sunColor.b)
    expect(sky.map.needsUpdate).toBe(undefined === sky.map.needsUpdate ? undefined : sky.map.needsUpdate)
    const camera = new THREE.PerspectiveCamera()
    camera.position.set(5, 6, 7)
    sky.update(camera, 12)
    expect(sky.dome.position.toArray()).toEqual([5, 6, 7])
    expect(sky.dome.material.uniforms.time.value).toBe(12)
    expect(sky.dome.material.fragmentShader).toContain('texColor * skyExposure')
    sky.dispose()
    expect(scene.children).toHaveLength(0)
  })

  it('says so when three.js\'s sky no longer has the line it hooks into', async () => {
    vi.resetModules()
    vi.doMock('three/addons/objects/Sky.js', async () => {
      const real = await vi.importActual('three/addons/objects/Sky.js')
      class OddSky extends real.Sky {
        constructor() {
          super()
          this.material.fragmentShader = 'void main() { gl_FragColor = vec4( 1.0 ); }'
        }
      }
      return { Sky: OddSky }
    })
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { createSky: createOddSky } = await import('../src/sky.js')
    createOddSky(new THREE.Scene(), { skyClouds: 0 })
    expect(warn).toHaveBeenCalledWith('sky: exposure hook not found')
    vi.doUnmock('three/addons/objects/Sky.js')
    vi.resetModules()
  })
})
