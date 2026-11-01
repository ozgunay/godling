import * as THREE from 'three'

// Swimming fish (RenderRole "Fish", ADR-007). The world moves each one along the shore, nose along its
// part's X. The sea is opaque, so a fish is drawn as it looks from above the water: a dark shape just under the
// surface, a dorsal fin breaking it, and a faint wake of foam behind. All three ride the sea's own waves
// (sea.surfaceAt), and each is one instanced draw for all the fish. A fish with a model (fish.glb) is drawn by
// index.js riding the same waves, half under; here it keeps its shadow and wake, and its model stands for the fin.

function silhouetteGeometry() {
  // In the XZ plane, nose at +X: a body like a lens and a forked tail.
  const shape = new THREE.Shape()
  shape.moveTo(0.5, 0)
  shape.quadraticCurveTo(0.2, 0.42, -0.25, 0.16)
  shape.lineTo(-0.5, 0.42)
  shape.lineTo(-0.42, 0)
  shape.lineTo(-0.5, -0.42)
  shape.lineTo(-0.25, -0.16)
  shape.quadraticCurveTo(0.2, -0.42, 0.5, 0)
  const geometry = new THREE.ShapeGeometry(shape, 6)
  geometry.rotateX(-Math.PI / 2) // shape Y becomes world -Z: flat on the water
  return geometry
}

function finGeometry() {
  // A small triangle standing up, leaning back.
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([0.12, 0, 0, -0.16, 0, 0, -0.12, 1, 0], 3))
  geometry.setIndex([0, 1, 2])
  geometry.computeVertexNormals()
  return geometry
}

function wakeGeometry() {
  // Two thin strips opening behind the tail, as a V.
  const geometry = new THREE.BufferGeometry()
  const strip = (side) => [0, 0, 0, -1, 0, side * 0.55, -1, 0, side * 0.75, 0, 0, side * 0.12]
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([...strip(1), ...strip(-1)], 3))
  geometry.setIndex([0, 1, 2, 0, 2, 3, 4, 6, 5, 4, 7, 6])
  return geometry
}

export function createFishLayer(scene) {
  const make = (geometry, material, order) => {
    const mesh = new THREE.InstancedMesh(geometry, material, 16)
    mesh.count = 0
    mesh.frustumCulled = false
    mesh.renderOrder = order // after the sea, which they lie on
    scene.add(mesh)
    return mesh
  }
  const onWater = { transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }
  const layers = {
    body: make(silhouetteGeometry(), new THREE.MeshBasicMaterial({ color: 0x0d2a36, opacity: 0.62, ...onWater, fog: true }), 2),
    wake: make(wakeGeometry(), new THREE.MeshBasicMaterial({ color: 0xf2fbff, opacity: 0.32, side: THREE.DoubleSide, ...onWater }), 2),
    fin: make(finGeometry(), new THREE.MeshBasicMaterial({ color: 0x1f3b48, side: THREE.DoubleSide, fog: true }), 2),
  }
  const m = new THREE.Matrix4()
  const turn = new THREE.Matrix4()
  const wag = new THREE.Matrix4()
  const scale = new THREE.Matrix4()

  function grow(count) {
    for (const [name, mesh] of Object.entries(layers)) {
      if (count <= mesh.instanceMatrix.count) continue
      const bigger = new THREE.InstancedMesh(mesh.geometry, mesh.material, Math.max(count, mesh.instanceMatrix.count * 2))
      bigger.frustumCulled = false
      bigger.renderOrder = mesh.renderOrder
      scene.remove(mesh)
      mesh.dispose()
      scene.add(bigger)
      layers[name] = bigger
    }
  }

  return {
    // `fish`: { id, position, rotation, size } for each swimming fish this frame.
    update(fish, sea, time) {
      grow(fish.length)
      fish.forEach((f, i) => {
        const [x, , z] = f.position
        const water = sea.surfaceAt(x, z)
        const y = water == null ? f.position[1] - 0.15 : water
        const r = f.rotation
        // The part's X is the nose; keep only its heading.
        const hx = r ? r[0][0] : 1
        const hz = r ? r[2][0] : 0
        turn.makeRotationY(Math.atan2(-hz, hx))
        const length = f.size?.[0] ?? 1.3
        const width = f.size?.[2] ?? 0.5
        const phase = time * 7 + (f.id % 17)
        wag.makeRotationY(Math.sin(phase) * 0.12)
        m.makeTranslation(x, y + 0.02, z).multiply(turn).multiply(wag).multiply(scale.makeScale(length, 1, width * 1.2))
        layers.body.setMatrixAt(i, m)
        m.makeTranslation(x, y, z).multiply(turn).multiply(scale.makeTranslation(-length * 0.5, 0.025, 0))
          .multiply(new THREE.Matrix4().makeScale(length * (1.4 + 0.3 * Math.sin(phase * 0.5)), 1, width * 1.6))
        layers.wake.setMatrixAt(i, m)
        if (f.modelled) m.makeScale(0, 0, 0) // its model shows its own back and fin
        else {
          m.makeTranslation(x, y - 0.05, z).multiply(turn).multiply(wag)
            .multiply(scale.makeScale(length * 0.35, 0.3 + 0.04 * Math.sin(phase * 1.3), 1))
        }
        layers.fin.setMatrixAt(i, m)
      })
      for (const mesh of Object.values(layers)) {
        mesh.count = fish.length
        mesh.instanceMatrix.needsUpdate = true
      }
    },
    dispose() {
      for (const mesh of Object.values(layers)) {
        scene.remove(mesh)
        mesh.geometry.dispose()
        mesh.material.dispose()
        mesh.dispose()
      }
    },
  }
}
