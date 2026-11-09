import * as THREE from 'three'
import { MOON_COLOR } from './sky.js'

// Minecraft-style clouds: a flat pixel layer on the low tier, puffs of voxel cubes otherwise. One pattern tile
// repeats in a 3 x 3 block that moves with the camera, so the camera never reaches the edge, and the clouds
// drift along X. They take the sky's light colour, and the fog fades them into the horizon.

const CELLS = 32 // a tile is CELLS x CELLS cloud cells
const CELL = 12
const TILE = CELLS * CELL
const HEIGHT = 92
const THICKNESS = 4.5
const SPEED = 1.4 // units per second
const SEED = 20261101

// Value noise that repeats every `period` lattice cells, so the tile has no seams.
function periodicNoise(seed, period) {
  const values = new Float32Array(period * period)
  let s = seed >>> 0
  for (let i = 0; i < values.length; i++) {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0
    values[i] = s / 4294967296
  }
  const at = (x, z) => values[(((z % period) + period) % period) * period + (((x % period) + period) % period)]
  const fade = (t) => t * t * (3 - 2 * t)
  return (x, z) => {
    const x0 = Math.floor(x)
    const z0 = Math.floor(z)
    const tx = fade(x - x0)
    const tz = fade(z - z0)
    const top = at(x0, z0) + (at(x0 + 1, z0) - at(x0, z0)) * tx
    const bottom = at(x0, z0 + 1) + (at(x0 + 1, z0 + 1) - at(x0, z0 + 1)) * tx
    return top + (bottom - top) * tz
  }
}

function cloudPattern() {
  const broad = periodicNoise(SEED, 8)
  const fine = periodicNoise(SEED * 7 + 3, 16)
  const cells = new Uint8Array(CELLS * CELLS)
  for (let z = 0; z < CELLS; z++) {
    for (let x = 0; x < CELLS; x++) {
      const v = 0.68 * broad((x * 8) / CELLS, (z * 8) / CELLS) + 0.32 * fine((x * 16) / CELLS, (z * 16) / CELLS)
      cells[z * CELLS + x] = v > 0.56 ? 1 : 0
    }
  }
  return cells
}

function flatLayer(cells) {
  const pixels = new Uint8Array(CELLS * CELLS * 4)
  for (let k = 0; k < cells.length; k++) {
    pixels.set([255, 255, 255, cells[k] ? 255 : 0], k * 4)
  }
  const texture = new THREE.DataTexture(pixels, CELLS, CELLS, THREE.RGBAFormat)
  texture.magFilter = THREE.NearestFilter
  texture.minFilter = THREE.NearestFilter
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(3, 3)
  texture.needsUpdate = true
  const geometry = new THREE.PlaneGeometry(TILE * 3, TILE * 3)
  geometry.rotateX(Math.PI / 2) // facing down, towards the viewer below
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    opacity: 0.85,
    alphaTest: 0.5,
    depthWrite: false,
    side: THREE.DoubleSide,
    fog: true,
    toneMapped: false, // white stays white, as in Minecraft
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.frustumCulled = false
  return {
    object: mesh,
    material,
    place(baseX, baseZ, drift) {
      mesh.position.set(baseX, HEIGHT, baseZ)
      texture.offset.x = -drift / TILE // (the plane faces down, so +u runs along +X)
    },
    dispose() {
      geometry.dispose()
      material.dispose()
      texture.dispose()
    },
  }
}

// The faces of the cloud cells that can be seen: tops, bottoms, and sides with no cloud next to them.
// Shaded like Minecraft's: bright tops, darker sides, darkest bottoms.
function voxelTile(cells) {
  const positions = []
  const colors = []
  const filled = (x, z) => cells[(((z % CELLS) + CELLS) % CELLS) * CELLS + (((x % CELLS) + CELLS) % CELLS)] === 1
  const quad = (corners, shade) => {
    const [a, b, c, d] = corners
    for (const p of [a, b, c, a, c, d]) {
      positions.push(p[0], p[1], p[2])
      colors.push(shade, shade, shade)
    }
  }
  const h = THICKNESS
  for (let z = 0; z < CELLS; z++) {
    for (let x = 0; x < CELLS; x++) {
      if (!filled(x, z)) continue
      const x0 = x * CELL
      const x1 = x0 + CELL
      const z0 = z * CELL
      const z1 = z0 + CELL
      quad([[x0, h, z0], [x0, h, z1], [x1, h, z1], [x1, h, z0]], 1.0)
      quad([[x0, 0, z0], [x1, 0, z0], [x1, 0, z1], [x0, 0, z1]], 0.72)
      if (!filled(x - 1, z)) quad([[x0, 0, z0], [x0, 0, z1], [x0, h, z1], [x0, h, z0]], 0.86)
      if (!filled(x + 1, z)) quad([[x1, 0, z1], [x1, 0, z0], [x1, h, z0], [x1, h, z1]], 0.86)
      if (!filled(x, z - 1)) quad([[x1, 0, z0], [x0, 0, z0], [x0, h, z0], [x1, h, z0]], 0.8)
      if (!filled(x, z + 1)) quad([[x0, 0, z1], [x1, 0, z1], [x1, h, z1], [x0, h, z1]], 0.8)
    }
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
  geometry.translate(-TILE / 2, 0, -TILE / 2)
  geometry.computeBoundingSphere()
  const material = new THREE.MeshBasicMaterial({ vertexColors: true, fog: true, toneMapped: false })
  const mesh = new THREE.InstancedMesh(geometry, material, 9)
  mesh.frustumCulled = false
  const matrix = new THREE.Matrix4()
  return {
    object: mesh,
    material,
    place(baseX, baseZ, drift) {
      let k = 0
      for (let j = -1; j <= 1; j++) {
        for (let i = -1; i <= 1; i++) {
          matrix.makeTranslation(baseX + i * TILE + drift, HEIGHT, baseZ + j * TILE)
          mesh.setMatrixAt(k++, matrix)
        }
      }
      mesh.instanceMatrix.needsUpdate = true
    },
    dispose() {
      geometry.dispose()
      material.dispose()
    },
  }
}

export function createClouds(scene, tier) {
  const cells = cloudPattern()
  const layer = tier.clouds === 'voxel' ? voxelTile(cells) : flatLayer(cells)
  layer.object.userData.noAim = true // sky, not island: never aimed at (aim.js)
  scene.add(layer.object)
  const tint = new THREE.Color()
  const white = new THREE.Color(1, 1, 1)

  return {
    update({ camera, time, sky, rain = 0 }) {
      const drift = (time * SPEED) % TILE
      const baseX = Math.floor((camera.position.x - drift) / TILE) * TILE + TILE / 2
      const baseZ = Math.floor(camera.position.z / TILE) * TILE + TILE / 2
      layer.place(baseX, baseZ, drift)
      // White by day, the sunset's colour low in the sky, moonlit grey-blue at night; heavy and grey in the rain.
      tint.copy(white).lerp(sky.sunColor, 0.12 + 0.5 * (1 - sky.daylight)).lerp(MOON_COLOR, sky.night * 0.5)
        .multiplyScalar((0.3 + 0.7 * sky.daylight) * (1 - 0.45 * rain))
      layer.material.color.copy(tint)
    },
    dispose() {
      scene.remove(layer.object)
      layer.dispose()
    },
  }
}
