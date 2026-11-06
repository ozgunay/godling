import * as THREE from 'three'

// Meteoric iron (main.lua METEORIC IRON, sky.iron): a flake knocked off a cooled meteor's stone (Iron_<n>, RenderRole
// "Iron"), and a tool with one bound on as its edge (its Edge "Iron").
// - A flake: a thin sliver of grey metal with a sheen, faceted, fitting its part (a hand long, lying flat).
// - An edged tool: the part of its model that cuts or strikes is worked iron instead: the axe's and the hammer's
//   "edge", the spear's carved point ("heartwood"). One shared material per source material, so every edged tool of
//   a kind is still one draw call. A spear's point is small (0.2 of its 4.5), so it also gets a leaf-shaped iron
//   blade over it (point()), the flake's own shape drawn out: a harpoon's tip that reads on stream.

export const EDGE_MATERIALS = new Set(['edge', 'heartwood']) // art/build_props.py's names for a tool's working part
// Worked meteoric iron: grey metal with a sheen, bright where it was struck or broke (the stone's crust is dark; a
// darker grey came out near black under the tone mapping, and the steel tools' edges showed no change).
export const IRON = { color: 0x77726b, metalness: 0.65, roughness: 0.3 }

export function createIronLook({ onMaterial } = {}) {
  const made = new Map() // source material uuid -> its iron variant
  let flake = null

  function edgeOf(material) {
    let m = made.get(material.uuid)
    if (m) return m
    m = material.clone()
    m.name = `${material.name}@iron`
    m.color.setHex(IRON.color)
    m.metalness = IRON.metalness
    m.roughness = IRON.roughness
    m.vertexColors = false // the iron's own colour, whatever the wood or steel was painted
    if (m.emissive) m.emissive.setHex(0x000000)
    made.set(material.uuid, m)
    onMaterial?.(m)
    return m
  }

  return {
    // A model's part as an iron-edged tool shows it: { geometry, material, suffix }, or the part as it is.
    variant(part, attributes) {
      const material = part.material
      if (attributes?.Edge !== 'Iron' || Array.isArray(material) || !EDGE_MATERIALS.has(material?.name)) {
        return { geometry: part.geometry, material, suffix: '' }
      }
      return { geometry: part.geometry, material: edgeOf(material), suffix: '@iron' }
    },
    // A flake's look, for its part's box: a sliver pointed at both ends (an octahedron, drawn out to the part).
    flake() {
      if (!flake) {
        const material = new THREE.MeshStandardMaterial({ ...IRON, flatShading: true, name: 'ironFlake' })
        onMaterial?.(material)
        flake = { geometry: new THREE.OctahedronGeometry(0.5, 0), material }
      }
      return flake
    },
    // The iron blade over an iron-edged spear's point: its transform inside the part (the point at the part's -Z,
    // art/README.md), or null for anything else.
    point(attributes, size) {
      if (attributes?.Edge !== 'Iron' || attributes?.ToolKind !== 'Spear') return null
      const [w, h, l] = size || [0.3, 0.3, 4.5]
      const local = new THREE.Matrix4().makeScale(w * 0.75, h * 0.22, l * 0.17).setPosition(0, 0, -l / 2 + l * 0.02)
      return { ...this.flake(), local }
    },
    info: () => ({ edges: made.size, flake: Boolean(flake) }),
    dispose() {
      for (const m of made.values()) m.dispose()
      made.clear()
      if (flake) {
        flake.geometry.dispose()
        flake.material.dispose()
        flake = null
      }
    },
  }
}
