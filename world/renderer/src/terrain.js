import * as THREE from 'three'

// Clawblox's voxel terrain (Workspace.Terrain), which the patched server sends as `state.terrain`
// (patches/v1-viewer-terrain-and-offline.patch). Solid voxels are drawn as blocks with only their open faces, all
// in one mesh with a colour per face, Minecraft-style: a grass block is green on top and earth on its sides.
// Water voxels get their open faces in a second, see-through mesh. The mesh is rebuilt only when the terrain's
// revision changes.

const FIELDS = 6 // per voxel: x, y, z, material index, solid occupancy, liquid occupancy (0-255)
const FILLED = 128 // half full or more counts as full

// Clawblox's materials first; the other Roblox terrain names in case a later Clawblox adds them.
const COLORS = {
  Grass: 0x6cbf4f, Sand: 0xe3cf8f, Slate: 0x6f7378, Granite: 0x9b8f86, Marble: 0xe6e2da, Concrete: 0xb8b8b8,
  Brick: 0xa8553f, Wood: 0x9c6e48, Ice: 0xcfeeff, Metal: 0x8f979e, Glass: 0xa8d8ea, Neon: 0x6af0ff,
  Fabric: 0xb07f5a, Plastic: 0xa3a2a5, SmoothPlastic: 0xa3a2a5, ForceField: 0x9fd8ff,
  LeafyGrass: 0x5aa844, Ground: 0x8b6a4a, Mud: 0x6b4f3a, Sandstone: 0xd8b27a, Rock: 0x8a8a8a, Basalt: 0x4a4a4f,
  Limestone: 0xd9cfae, Pavement: 0x9a9a9a, Cobblestone: 0x7b7b7b, WoodPlanks: 0xb4864f, Snow: 0xf4f8ff,
  Glacier: 0xbfe6ff, Asphalt: 0x3c3c3c, Salt: 0xeeeeee, CrackedLava: 0xc4502a,
}
const SIDE_COLORS = { Grass: 0x8b6a4a, LeafyGrass: 0x8b6a4a } // a grass block's sides and bottom are earth
const FALLBACK = 0x9a9a9a

// Outward normal, then the face's four corners on a unit cube, counter-clockwise from outside.
const FACES = [
  [[1, 0, 0], [[1, 0, 0], [1, 1, 0], [1, 1, 1], [1, 0, 1]], 0.86],
  [[-1, 0, 0], [[0, 0, 1], [0, 1, 1], [0, 1, 0], [0, 0, 0]], 0.86],
  [[0, 1, 0], [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]], 1.0],
  [[0, -1, 0], [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], 0.62],
  [[0, 0, 1], [[1, 0, 1], [1, 1, 1], [0, 1, 1], [0, 0, 1]], 0.8],
  [[0, 0, -1], [[0, 0, 0], [0, 1, 0], [1, 1, 0], [1, 0, 0]], 0.8],
]

const keyOf = (x, y, z) => `${x},${y},${z}`

function buildMesh(cells, isOpen, colorOf, size) {
  const positions = []
  const normals = []
  const colors = []
  const color = new THREE.Color()
  for (const [x, y, z, material] of cells) {
    // A faint per-block variation, so a wall of one material still reads as blocks.
    const jitter = 0.96 + 0.08 * (((x * 73856093) ^ (y * 19349663) ^ (z * 83492791)) >>> 0) / 4294967296
    for (const [normal, corners, shade] of FACES) {
      if (!isOpen(x + normal[0], y + normal[1], z + normal[2])) continue
      colorOf(material, normal, color)
      const r = color.r * shade * jitter
      const g = color.g * shade * jitter
      const b = color.b * shade * jitter
      for (const i of [0, 1, 2, 0, 2, 3]) {
        const c = corners[i]
        positions.push((x + c[0]) * size, (y + c[1]) * size, (z + c[2]) * size)
        normals.push(normal[0], normal[1], normal[2])
        colors.push(r, g, b)
      }
    }
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3))
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
  geometry.computeBoundingSphere()
  return geometry
}

export function createTerrain(scene, { onMaterial }) {
  const solidMaterial = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, metalness: 0 })
  const waterMaterial = new THREE.MeshStandardMaterial({
    color: 0x3fa7d6, transparent: true, opacity: 0.72, roughness: 0.08, metalness: 0.1, depthWrite: false,
  })
  onMaterial?.(solidMaterial)
  onMaterial?.(waterMaterial)
  const solidMesh = new THREE.Mesh(new THREE.BufferGeometry(), solidMaterial)
  solidMesh.castShadow = true
  solidMesh.receiveShadow = true
  const waterMesh = new THREE.Mesh(new THREE.BufferGeometry(), waterMaterial)
  waterMesh.receiveShadow = true
  scene.add(solidMesh, waterMesh)

  let revision = null
  let land = [] // footprints of solid voxels at sea level, for the sea's shore map
  let voxels = { solid: [], size: 4 }

  function rebuild(terrain) {
    const size = Number(terrain.voxel_size) || 4
    const names = terrain.materials || []
    const flat = terrain.voxels || []
    const solid = []
    const water = []
    const solidSet = new Set()
    const waterSet = new Set()
    for (let i = 0; i + FIELDS <= flat.length; i += FIELDS) {
      const cell = [flat[i], flat[i + 1], flat[i + 2], names[flat[i + 3]] || 'Air']
      if (flat[i + 4] >= FILLED) {
        solid.push(cell)
        solidSet.add(keyOf(cell[0], cell[1], cell[2]))
      } else if (flat[i + 5] >= FILLED) {
        water.push(cell)
        waterSet.add(keyOf(cell[0], cell[1], cell[2]))
      }
    }
    const solidColor = (material, normal, out) => {
      const side = normal[1] <= 0 ? SIDE_COLORS[material] : null
      return out.setHex(side ?? COLORS[material] ?? FALLBACK, THREE.SRGBColorSpace)
    }
    solidMesh.geometry.dispose()
    solidMesh.geometry = buildMesh(solid, (x, y, z) => !solidSet.has(keyOf(x, y, z)), solidColor, size)
    waterMesh.geometry.dispose()
    waterMesh.geometry = buildMesh(
      water,
      (x, y, z) => !waterSet.has(keyOf(x, y, z)) && !solidSet.has(keyOf(x, y, z)),
      (material, normal, out) => out.setRGB(1, 1, 1),
      size,
    )
    voxels = { solid, size }
    land = null
  }

  return {
    update(terrain) {
      if (!terrain) {
        if (revision !== null) rebuild({ voxels: [] })
        revision = null
        return
      }
      if (terrain.revision === revision) return
      revision = terrain.revision
      rebuild(terrain)
    },
    // Solid voxels that reach sea level, as boxes for the sea's shore map, and a key that changes with them.
    landAt(seaLevel) {
      if (!land) {
        const { solid, size } = voxels
        land = solid
          .filter(([, y]) => y * size <= seaLevel && (y + 1) * size >= seaLevel - 1)
          .map(([x, y, z]) => ({
            center: [(x + 0.5) * size, (y + 0.5) * size, (z + 0.5) * size],
            half: [size / 2, size / 2, size / 2],
            rotation: null,
          }))
      }
      return { boxes: land, key: `terrain:${revision}` }
    },
    dispose() {
      scene.remove(solidMesh, waterMesh)
      solidMesh.geometry.dispose()
      waterMesh.geometry.dispose()
      solidMaterial.dispose()
      waterMaterial.dispose()
    },
  }
}
