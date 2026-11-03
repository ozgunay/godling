import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createWind, swayMaterial } from '../src/wind.js'

describe('wind', () => {
  it('eases towards the Clock and gusts on top', () => {
    const wind = createWind(new URLSearchParams())
    wind.read({ WindX: 0.8, WindZ: 0 })
    wind.read({ WindX: 'calm' }) // not a number: ignored
    let now
    for (let i = 0; i < 200; i++) now = wind.update(0.1)
    expect(now.x).toBeGreaterThan(0.3)
    expect(wind.uniforms.uWindTime.value).toBeCloseTo(20)
    const light = createWind(new URLSearchParams())
    for (let i = 0; i < 20; i++) now = light.update(0.1)
    expect(now.length()).toBeLessThan(0.3) // a breeze
  })

  it('can be forced from the URL, and the Clock no longer moves it', () => {
    const wind = createWind(new URLSearchParams('wind=1'))
    wind.read({ WindX: 0, WindZ: 0.1 })
    expect(wind.update(0.01).x).toBeGreaterThan(0.5)
  })

  it('sways a material once, keeping what patched it before', () => {
    const material = new THREE.MeshStandardMaterial()
    const calls = []
    material.onBeforeCompile = () => calls.push('before')
    material.customProgramCacheKey = () => 'csm'
    const uniforms = createWind(new URLSearchParams()).uniforms
    swayMaterial(material, uniforms)
    swayMaterial(material, uniforms) // again: nothing more
    swayMaterial(null, uniforms)
    const shader = { uniforms: {}, vertexShader: 'void main() {\n#include <project_vertex>\n}' }
    material.onBeforeCompile(shader, null)
    expect(calls).toEqual(['before'])
    expect(shader.uniforms.uWind).toBe(uniforms.uWind)
    expect(shader.vertexShader).toContain('mvPosition.xz += swayBend;')
    expect(shader.vertexShader.startsWith('uniform vec2 uWind;')).toBe(true)
    expect(material.customProgramCacheKey()).toBe('csm|sway')
    const plain = new THREE.MeshStandardMaterial()
    plain.customProgramCacheKey = undefined
    swayMaterial(plain, uniforms)
    plain.onBeforeCompile({ uniforms: {}, vertexShader: '#include <project_vertex>' }, null)
    expect(plain.customProgramCacheKey()).toBe('|sway')
  })
})
