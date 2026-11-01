import * as THREE from 'three'

// Draws the world's parts with one draw call per kind of mesh (THREE.InstancedMesh), instead of a mesh, a
// geometry and a material for every part. Phones run out of draw calls long before triangles, and a
// Minecraft-scale build is thousands of blocks of a few kinds.
//
// A group is one geometry with one material. Each part an entity is drawn with takes a slot in its group; slots
// are packed (a removed slot takes the group's last instance), and only the changed range is sent to the GPU.

export function createInstancer(scene) {
  const groups = new Map()
  const colorScratch = new THREE.Color()

  function group(key, geometry, material, { colored = false, castShadow = true, receiveShadow = true } = {}) {
    let g = groups.get(key)
    if (g) return g
    g = { key, geometry, material, colored, castShadow, receiveShadow, mesh: null, capacity: 0, count: 0, owners: [], lo: Infinity, hi: -1 }
    grow(g, 16)
    groups.set(key, g)
    return g
  }

  function grow(g, capacity) {
    const mesh = new THREE.InstancedMesh(g.geometry, g.material, capacity)
    mesh.count = g.count
    mesh.frustumCulled = false // one island: the camera nearly always sees part of every group
    mesh.castShadow = g.castShadow
    mesh.receiveShadow = g.receiveShadow
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
    if (g.colored) {
      mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3).fill(1), 3)
      mesh.instanceColor.setUsage(THREE.DynamicDrawUsage)
    }
    if (g.mesh) {
      mesh.instanceMatrix.array.set(g.mesh.instanceMatrix.array.subarray(0, g.count * 16))
      if (g.colored) mesh.instanceColor.array.set(g.mesh.instanceColor.array.subarray(0, g.count * 3))
      scene.remove(g.mesh)
      g.mesh.dispose() // the attributes only; the geometry and material are shared
      g.lo = 0
      g.hi = g.count - 1
    }
    g.mesh = mesh
    g.capacity = capacity
    scene.add(mesh)
  }

  function touch(g, index) {
    if (index < g.lo) g.lo = index
    if (index > g.hi) g.hi = index
  }

  return {
    group,

    add(g, matrix, color = null) {
      if (g.count === g.capacity) grow(g, g.capacity * 2)
      const slot = { group: g, index: g.count }
      g.owners[g.count] = slot
      g.count += 1
      g.mesh.count = g.count
      g.mesh.setMatrixAt(slot.index, matrix)
      if (g.colored) g.mesh.setColorAt(slot.index, color || colorScratch.setRGB(1, 1, 1))
      touch(g, slot.index)
      return slot
    },

    setMatrix(slot, matrix) {
      slot.group.mesh.setMatrixAt(slot.index, matrix)
      touch(slot.group, slot.index)
    },

    setColor(slot, color) {
      if (!slot.group.colored) return
      slot.group.mesh.setColorAt(slot.index, color)
      touch(slot.group, slot.index)
    },

    remove(slot) {
      const g = slot.group
      const last = g.count - 1
      if (slot.index !== last) {
        const moved = g.owners[last]
        const m = g.mesh.instanceMatrix.array
        m.copyWithin(slot.index * 16, last * 16, last * 16 + 16)
        if (g.colored) {
          const c = g.mesh.instanceColor.array
          c.copyWithin(slot.index * 3, last * 3, last * 3 + 3)
        }
        moved.index = slot.index
        g.owners[slot.index] = moved
        touch(g, slot.index)
      }
      g.owners.length = last
      g.count = last
      g.mesh.count = last
      slot.index = -1
    },

    // Sends what changed this frame to the GPU.
    flush() {
      for (const g of groups.values()) {
        if (g.hi < g.lo) continue
        const im = g.mesh.instanceMatrix
        im.clearUpdateRanges()
        im.addUpdateRange(g.lo * 16, (g.hi - g.lo + 1) * 16)
        im.needsUpdate = true
        if (g.colored) {
          const ic = g.mesh.instanceColor
          ic.clearUpdateRanges()
          ic.addUpdateRange(g.lo * 3, (g.hi - g.lo + 1) * 3)
          ic.needsUpdate = true
        }
        g.lo = Infinity
        g.hi = -1
      }
    },

    stats() {
      let instances = 0
      for (const g of groups.values()) instances += g.count
      return { groups: groups.size, instances }
    },

    clear() {
      for (const g of groups.values()) {
        scene.remove(g.mesh)
        g.mesh.dispose()
      }
      groups.clear()
    },
  }
}
