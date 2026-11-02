import * as THREE from 'three'

// Dust: puffs where a loose piece lands hard (a dropped stone, a felled log, a sky drop), and where the earthquake
// (the Clock's Quake) rocks or slides pieces along the ground. The renderer only sees where pieces are, so it watches
// each loose piece's speed: a fall that stops is a landing; in a quake, a piece shifting with no fall is rocking where
// it lies (a little dust now and then) or sliding (a trail). Puffs are a fixed pool of pixel billboards that rise a little, grow and fade in their shader; a new puff
// takes the oldest one's place, so all the dust is one draw call and nothing moves on the CPU.

const LIFE = 1.4 // seconds a puff lasts
const LANDING = 5 // falling faster than this (units per second) and then stopping is a landing
const SLIDE = 2.5 // sliding faster than this during a quake trails dust
const TRAIL_EVERY = 0.12 // seconds between a sliding piece's puffs
const RATTLE = 0.2 // a piece shifting even this fast in a quake raises a little dust: it is rocking where it lies
const RATTLE_EVERY = 0.5 // seconds between those
const TELEPORT = 4 // a jump this far in one frame is a respawn, not a movement
const MAX_PIECE = 12 // anything longer than this is land, not a piece (the stream does not say what is anchored)

const vertexShader = /* glsl */`
  uniform float time;
  uniform float life;
  attribute vec4 origin; // where, and when it was made
  attribute vec2 shape; // size, seed
  varying float vAlpha;
  varying vec2 vUv;
  #include <common>
  #include <fog_pars_vertex>
  void main() {
    float age = ( time - origin.w ) / life;
    if ( age < 0.0 || age > 1.0 ) {
      gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 ); // outside the view: not drawn
      return;
    }
    float seed = shape.y;
    vec3 centre = origin.xyz + vec3( sin( seed * 17.0 ) * 0.7 * age, 0.35 + 1.4 * age, cos( seed * 23.0 ) * 0.7 * age );
    float size = shape.x * mix( 0.45, 1.5, sqrt( age ) );
    vec4 mvPosition = viewMatrix * vec4( centre, 1.0 );
    float a = seed * 6.28 + age * 0.8;
    mvPosition.xy += mat2( cos( a ), -sin( a ), sin( a ), cos( a ) ) * position.xy * size;
    gl_Position = projectionMatrix * mvPosition;
    vAlpha = smoothstep( 0.0, 0.08, age ) * ( 1.0 - smoothstep( 0.3, 1.0, age ) );
    vUv = uv;
    #include <fog_vertex>
  }
`

const fragmentShader = /* glsl */`
  uniform vec3 color;
  uniform float opacity;
  varying float vAlpha;
  varying vec2 vUv;
  #include <common>
  #include <fog_pars_fragment>
  void main() {
    vec2 p = floor( vUv * 8.0 ) / 8.0 + 1.0 / 16.0; // pixel puffs, as the blocks
    float r = length( p - 0.5 ) * 2.0;
    float a = ( 1.0 - smoothstep( 0.5, 0.95, r ) ) * vAlpha * opacity;
    if ( a < 0.01 ) discard;
    gl_FragColor = vec4( color, a );
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
    #include <fog_fragment>
  }
`

export function createDust(scene, tier) {
  const count = tier.dustPuffs
  const geometry = new THREE.InstancedBufferGeometry()
  const quad = new THREE.PlaneGeometry(1, 1)
  geometry.index = quad.index
  geometry.setAttribute('position', quad.attributes.position)
  geometry.setAttribute('uv', quad.attributes.uv)
  const origins = new Float32Array(count * 4).fill(-1e4) // all born long ago: none shows
  const shapes = new Float32Array(count * 2)
  const originAttribute = new THREE.InstancedBufferAttribute(origins, 4).setUsage(THREE.DynamicDrawUsage)
  const shapeAttribute = new THREE.InstancedBufferAttribute(shapes, 2).setUsage(THREE.DynamicDrawUsage)
  geometry.setAttribute('origin', originAttribute)
  geometry.setAttribute('shape', shapeAttribute)
  geometry.instanceCount = count
  const material = new THREE.ShaderMaterial({
    name: 'GodlingDust',
    uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
      time: { value: 0 },
      life: { value: LIFE },
      color: { value: new THREE.Color() },
      opacity: { value: 0.55 },
    }]),
    vertexShader,
    fragmentShader,
    transparent: true,
    depthWrite: false,
    fog: true,
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.frustumCulled = false // the puffs are placed in the shader
  mesh.renderOrder = 3
  scene.add(mesh)

  const SAND_DUST = new THREE.Color(0xcdbb94)
  const pieces = new Map() // entity id -> { x, y, z, fall, lastPuff }
  let next = 0
  let dirty = false
  let now = 0

  function puff(x, y, z, size) {
    const i = next
    next = (next + 1) % count
    origins.set([x, y, z, now], i * 4)
    shapes[i * 2] = size
    shapes[i * 2 + 1] = Math.random()
    dirty = true
  }

  function burst(x, bottom, z, footprint, strength) {
    const n = Math.min(6, Math.max(2, Math.round(strength / 3)))
    const size = Math.min(3.2, Math.max(0.8, footprint * 0.9))
    for (let k = 0; k < n; k++) {
      const angle = (k / n) * Math.PI * 2 + Math.random()
      const out = footprint * 0.45
      puff(x + Math.cos(angle) * out, bottom, z + Math.sin(angle) * out, size * (0.8 + 0.4 * Math.random()))
    }
  }

  return {
    // Each frame, for each loose piece: its entity, the time step, the quake (0..1) and the sea level (no dust on
    // the water).
    watch(entity, dt, quake, seaLevel) {
      const size = entity.size || [1, 1, 1]
      if (Math.max(size[0], size[1], size[2]) > MAX_PIECE) return // ground, beaches, mesas: never loose
      const [x, y, z] = entity.position
      const piece = pieces.get(entity.id)
      if (!piece) {
        pieces.set(entity.id, { x, y, z, fall: 0, lastPuff: -1 })
        return
      }
      const dx = x - piece.x
      const dy = y - piece.y
      const dz = z - piece.z
      piece.x = x
      piece.y = y
      piece.z = z
      if (!(dt > 0)) return
      if (dx * dx + dy * dy + dz * dz > TELEPORT * TELEPORT) {
        piece.fall = 0
        return
      }
      const vy = dy / dt
      const across = Math.sqrt(dx * dx + dz * dz) / dt
      const r = entity.rotation
      // Half the piece's height as it lies now (a log may stand on end), and about how wide it is.
      const halfHeight = r ? (Math.abs(r[1][0]) * size[0] + Math.abs(r[1][1]) * size[1] + Math.abs(r[1][2]) * size[2]) / 2 : size[1] / 2
      const bottom = y - halfHeight
      if (seaLevel != null && bottom < seaLevel + 0.3) {
        piece.fall = 0
        return
      }
      const footprint = Math.min(4, Math.max(size[0], size[2]))
      if (vy < -LANDING) piece.fall = Math.max(piece.fall, -vy)
      else if (piece.fall > 0 && vy > -1) {
        burst(x, bottom, z, footprint, piece.fall)
        piece.fall = 0
      }
      const sliding = across > SLIDE
      if (quake > 0.3 && across > RATTLE && Math.abs(vy) < 1.5 && now - piece.lastPuff > (sliding ? TRAIL_EVERY : RATTLE_EVERY)) {
        puff(x - dx * 0.5, bottom, z - dz * 0.5, Math.min(2.4, Math.max(0.6, footprint * (sliding ? 0.7 : 0.45))))
        piece.lastPuff = now
      }
    },
    // Forget pieces that are gone.
    prune(activeIds) {
      for (const id of pieces.keys()) if (!activeIds.has(id)) pieces.delete(id)
    },
    // time: the same clock the puffs were made on (seconds).
    update({ time, daylight }) {
      now = time
      material.uniforms.time.value = time
      material.uniforms.color.value.copy(SAND_DUST).multiplyScalar(0.25 + 0.75 * daylight)
      if (dirty) {
        originAttribute.needsUpdate = true
        shapeAttribute.needsUpdate = true
        dirty = false
      }
    },
    info: () => ({ watched: pieces.size, alive: Array.from({ length: count }, (_, i) => now - origins[i * 4 + 3] < LIFE).filter(Boolean).length }),
    dispose() {
      scene.remove(mesh)
      geometry.dispose()
      quad.dispose()
      material.dispose()
      pieces.clear()
    },
  }
}
