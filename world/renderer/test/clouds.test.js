import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createClouds } from '../src/clouds.js'

const sky = (daylight) => ({ sunColor: new THREE.Color(1, 0.6, 0.3), daylight, night: 1 - daylight })

describe('clouds', () => {
  it('voxel puffs follow the camera in a 3 x 3 block and drift', () => {
    const scene = new THREE.Scene()
    const clouds = createClouds(scene, { clouds: 'voxel' })
    const mesh = scene.children[0]
    expect(mesh.isInstancedMesh).toBe(true)
    const camera = new THREE.PerspectiveCamera()
    camera.position.set(1000, 0, -500)
    clouds.update({ camera, time: 10, sky: sky(1) })
    const m = new THREE.Matrix4()
    mesh.getMatrixAt(4, m) // the middle tile is under the camera
    const middle = new THREE.Vector3().setFromMatrixPosition(m)
    expect(Math.abs(middle.x - camera.position.x)).toBeLessThan(384)
    expect(middle.y).toBe(92)
    const day = mesh.material.color.clone()
    clouds.update({ camera, time: 10, sky: sky(0), rain: 1 })
    expect(mesh.material.color.r).toBeLessThan(day.r) // dark and grey at night in the rain
    clouds.dispose()
    expect(scene.children).toHaveLength(0)
  })

  it('a flat pixel layer on the low tier', () => {
    const scene = new THREE.Scene()
    const clouds = createClouds(scene, { clouds: 'flat' })
    const mesh = scene.children[0]
    expect(mesh.isInstancedMesh).toBeFalsy()
    clouds.update({ camera: new THREE.PerspectiveCamera(), time: 20, sky: sky(0.5) })
    expect(mesh.position.y).toBe(92)
    expect(mesh.material.map.offset.x).toBeCloseTo(-28 / 384)
    clouds.dispose()
  })
})
