import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { createIronLook, EDGE_MATERIALS, IRON } from '../src/iron.js'

// A tool's model parts as art/build_props.py names their materials: the axe's steel head and its edge.
const axe = () => [
  { geometry: new THREE.BoxGeometry(), material: new THREE.MeshStandardMaterial({ name: 'handle' }) },
  { geometry: new THREE.BoxGeometry(), material: new THREE.MeshStandardMaterial({ name: 'steel', metalness: 0.6 }) },
  { geometry: new THREE.BoxGeometry(), material: new THREE.MeshStandardMaterial({ name: 'edge', color: 0xdddddd }) },
]

describe('meteoric iron', () => {
  it('shows an iron-edged tool\'s working part in dark metal, one shared material each', () => {
    const made = []
    const look = createIronLook({ onMaterial: (m) => made.push(m) })
    const [handle, steel, edge] = axe()
    expect(look.variant(handle, { Edge: 'Iron' }).suffix).toBe('')
    expect(look.variant(steel, { Edge: 'Iron' }).material).toBe(steel.material)
    const iron = look.variant(edge, { Edge: 'Iron' })
    expect(iron.suffix).toBe('@iron')
    expect(iron.geometry).toBe(edge.geometry)
    expect(iron.material).not.toBe(edge.material)
    expect(iron.material.name).toBe('edge@iron')
    expect(iron.material.color.getHex()).toBe(new THREE.Color(IRON.color).getHex())
    expect(iron.material.metalness).toBe(IRON.metalness)
    expect(edge.material.color.getHex()).toBe(0xdddddd) // the model's own is left as it is
    expect(look.variant(axe()[2], { Edge: 'Iron' }).material).not.toBe(iron.material) // another source, another
    expect(look.variant(edge, { Edge: 'Iron' }).material).toBe(iron.material) // made once
    expect(made).toHaveLength(2)
    expect(look.variant(edge, {}).material).toBe(edge.material) // no edge bound on
    expect(look.variant(edge, undefined).suffix).toBe('')
    expect(look.variant({ geometry: edge.geometry, material: [edge.material] }, { Edge: 'Iron' }).suffix).toBe('')
    const point = { geometry: new THREE.BoxGeometry(), material: new THREE.MeshStandardMaterial({ name: 'heartwood', vertexColors: true, emissive: 0x111111 }) }
    const pointed = look.variant(point, { Edge: 'Iron' }).material
    expect(pointed.vertexColors).toBe(false)
    expect(pointed.emissive.getHex()).toBe(0)
    expect([...EDGE_MATERIALS]).toEqual(['edge', 'heartwood'])
    expect(look.info()).toEqual({ edges: 3, flake: false })
    look.dispose()
    expect(look.info().edges).toBe(0)
  })

  it('draws a flake as a dark sliver, made once', () => {
    const made = []
    const look = createIronLook({ onMaterial: (m) => made.push(m) })
    const a = look.flake()
    expect(look.flake()).toBe(a)
    expect(a.material.metalness).toBe(IRON.metalness)
    expect(a.material.flatShading).toBe(true)
    a.geometry.computeBoundingBox()
    expect(a.geometry.boundingBox.max.x).toBeCloseTo(0.5) // fits a unit box: scaled to its part
    expect(made).toEqual([a.material])
    look.dispose()
    expect(look.info().flake).toBe(false)
    expect(createIronLook().flake().material.name).toBe('ironFlake')
  })
})

describe('an iron point on a spear', () => {
  it('lays a blade over the point, at the part\'s -Z end, only on an iron-edged spear', () => {
    const look = createIronLook()
    expect(look.point({ Edge: 'Iron', ToolKind: 'Axe' }, [0.4, 0.4, 1])).toBeNull()
    expect(look.point({ ToolKind: 'Spear' }, [0.3, 0.3, 4.5])).toBeNull()
    const point = look.point({ Edge: 'Iron', ToolKind: 'Spear' }, [0.3, 0.3, 4.5])
    expect(point.geometry).toBe(look.flake().geometry) // the flake's own leaf shape
    const at = new THREE.Vector3().setFromMatrixPosition(point.local)
    expect(at.z).toBeCloseTo(-2.25 + 0.09)
    const scale = new THREE.Vector3().setFromMatrixScale(point.local)
    expect(scale.z).toBeCloseTo(4.5 * 0.17) // about three quarters of a unit long
    expect(scale.x).toBeLessThan(0.3) // a little narrower than the shaft is thick, flat
    expect(look.point({ Edge: 'Iron', ToolKind: 'Spear' }).local).toBeTruthy() // a part without a size: a spear's
  })
})
