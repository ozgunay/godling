import * as THREE from 'three'

// A meteor's blast. The world marks the contact point with a short-lived part, Blast_<n> (RenderRole "Blast", Radius
// about 7, SkyId n), and the blast plays once, when the marker is first seen:
// - a flash that lights the ground (a point light; on the low tier the ambient light flares instead),
// - a fireball: puffs thrown out that swell and burn white, yellow, orange and red, then turn to smoke (they are
//   solid, so they read by day too), with a glow of added light at its heart,
// - a shock ring that runs along the ground out to Radius, pushing a ring of dust before it,
// - smoke that rises and drifts with the wind, and sand and embers thrown out in arcs,
// - charred chunks that tumble out, bounce once and sink away, and coals that smoulder in the crater,
// - a jolt of the camera, weaker the farther off it is (none in the server's capture, see shake.js).
// A meteor falling fast (Meteor_<n>, before it lands) trails fire and smoke. Its crater (Crater_<n>, the same SkyId)
// tells where the ground is, for a meteor that hits the top of a building: debris and sand land on the crater's floor.
// Puffs and embers are fixed pools of pixel billboards that move in their shaders, as the dust's: a new one takes the
// oldest's place, each pool is one draw call, and only the few chunks move on the CPU. Fewer of everything on the
// weaker tiers (quality.js).

const HEAT = 0 // the glow pool's kinds: added light
const EMBER = 1
const FLASH = 2
const SMOKE = 0 // the soft pool's kinds: blended over the scene
const SAND = 1
const DUST = 2
const FIRE = 3
const TRAIL = 4
const TRAIL_SPEED = 10 // a meteor falling faster than this (units per second) trails fire
const TRAIL_EVERY = 0.03 // seconds between its trail's puffs, on the high tier
const SMOULDER = 4 // seconds the crater smokes
const LINGER = SMOULDER + 0.5 // seconds a blast is kept
const GRAVITY = 26 // the chunks'
const RINGS = 3 // shock rings at once

// Shared by both pools: where a puff is after t seconds, slowed by drag and pushed by a steady force (gravity, the
// fire's lift, the wind), and its billboard turned to face the camera.
const motion = /* glsl */`
  uniform float time;
  attribute vec4 origin; // where, and when it starts
  attribute vec4 velocity; // its first velocity, and how long it lasts
  attribute vec4 look; // its first size, how much it grows over its life, a seed, its kind
  attribute float ground; // it never goes below this
  varying vec2 vUv;
  varying vec3 vColor;
  varying float vAlpha;
  vec3 travel( float t, float drag, vec3 force ) {
    return origin.xyz + force * ( t / drag ) + ( velocity.xyz - force / drag ) * ( 1.0 - exp( -drag * t ) ) / drag;
  }
  vec4 billboard( vec3 centre, float size, float spin ) {
    vec4 mvPosition = viewMatrix * vec4( centre, 1.0 );
    mvPosition.xy += mat2( cos( spin ), -sin( spin ), sin( spin ), cos( spin ) ) * position.xy * size;
    gl_Position = projectionMatrix * mvPosition;
    vUv = uv;
    return mvPosition;
  }
`

const glowVertex = /* glsl */`
  ${motion}
  varying float vSmooth;
  #include <common>
  #include <fog_pars_vertex>
  void main() {
    float t = time - origin.w;
    float age = t / velocity.w;
    vSmooth = 0.0;
    if ( age < 0.0 || age > 1.0 ) {
      gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 ); // outside the view: not drawn
      return;
    }
    float kind = look.w;
    vec3 p = origin.xyz;
    if ( kind < 0.5 ) { // heat: the fireball's glowing heart, slowed hard, rising
      p = travel( t, 3.2, vec3( 0.0, 5.0, 0.0 ) );
      vec3 orange = vec3( 1.0, 0.42, 0.08 );
      vColor = age < 0.2 ? mix( vec3( 1.0, 0.9, 0.62 ), orange, age / 0.2 ) : mix( orange, vec3( 0.42, 0.05, 0.02 ), ( age - 0.2 ) / 0.8 );
      vColor *= 1.7;
      vAlpha = smoothstep( 0.0, 0.05, age ) * ( 1.0 - smoothstep( 0.35, 1.0, age ) );
    } else if ( kind < 1.5 ) { // an ember: thrown, falling, flickering, cooling
      p = travel( t, 0.8, vec3( 0.0, -16.0, 0.0 ) );
      float flicker = 0.65 + 0.35 * sin( time * 37.0 + look.z * 91.0 );
      vColor = mix( vec3( 1.0, 0.8, 0.35 ), vec3( 0.95, 0.18, 0.03 ), smoothstep( 0.0, 0.6, age ) ) * 2.2 * flicker;
      vAlpha = 1.0 - smoothstep( 0.55, 1.0, age );
    } else { // the flash: a smooth glow, not a pixel puff (that big, a puff's steps would read as a pane)
      vColor = vec3( 1.0, 0.94, 0.78 ) * 2.6;
      vAlpha = ( 1.0 - age ) * ( 1.0 - age );
      vSmooth = 1.0;
    }
    p.y = max( p.y, ground );
    vec4 mvPosition = billboard( p, look.x * mix( 1.0, look.y, sqrt( age ) ), look.z * 6.28 + age * 0.6 );
    #include <fog_vertex>
  }
`

const glowFragment = /* glsl */`
  uniform float glow;
  varying vec2 vUv;
  varying vec3 vColor;
  varying float vAlpha;
  varying float vSmooth;
  #include <common>
  #include <fog_pars_fragment>
  void main() {
    vec2 p = mix( floor( vUv * 8.0 ) / 8.0 + 1.0 / 16.0, vUv, vSmooth ); // pixel puffs, as the blocks
    float r = length( p - 0.5 ) * 2.0;
    float a = mix( 1.0 - smoothstep( 0.4, 0.95, r ), pow( max( 1.0 - r, 0.0 ), 2.0 ), vSmooth ) * vAlpha;
    #ifdef USE_FOG
      a *= 1.0 - smoothstep( fogNear, fogFar, vFogDepth ); // added light fades out in the fog, not into its colour
    #endif
    if ( a < 0.01 ) discard;
    gl_FragColor = vec4( vColor * glow * ( 0.7 + 0.6 * ( 1.0 - r ) ), a ); // hotter at the heart
  }
`

const softVertex = /* glsl */`
  ${motion}
  uniform vec2 wind;
  uniform float shade;
  uniform vec3 sand;
  #include <common>
  #include <fog_pars_vertex>
  void main() {
    float t = time - origin.w;
    float age = t / velocity.w;
    if ( age < 0.0 || age > 1.0 ) {
      gl_Position = vec4( 2.0, 2.0, 2.0, 1.0 );
      return;
    }
    float kind = look.w;
    vec3 p;
    if ( kind < 0.5 ) { // smoke: rises, slows, drifts with the wind; lit by the fireball at first
      p = travel( t, 1.5, vec3( wind.x * 3.0, 1.8, wind.y * 3.0 ) );
      vec3 smoke = mix( vec3( 0.025, 0.022, 0.02 ), vec3( 0.2, 0.18, 0.15 ), smoothstep( 0.05, 0.75, age ) ) * shade;
      vColor = mix( vec3( 0.95, 0.45, 0.15 ), smoke, smoothstep( 0.0, 0.14, age ) );
      vAlpha = smoothstep( 0.0, 0.06, age ) * ( 1.0 - smoothstep( 0.35, 1.0, age ) ) * 0.8;
    } else if ( kind < 1.5 ) { // sand: thrown, falls, settles
      p = travel( t, 0.7, vec3( 0.0, -20.0, 0.0 ) );
      vColor = sand * shade;
      vAlpha = smoothstep( 0.0, 0.04, age ) * ( 1.0 - smoothstep( 0.45, 1.0, age ) ) * 0.75;
    } else if ( kind < 2.5 ) { // dust pushed out along the ground by the shock
      p = travel( t, 2.4, vec3( wind.x * 2.0, 0.6, wind.y * 2.0 ) );
      vColor = sand * shade * 0.9;
      vAlpha = smoothstep( 0.0, 0.05, age ) * ( 1.0 - smoothstep( 0.3, 1.0, age ) ) * 0.6;
    } else if ( kind < 3.5 ) { // fire: thrown out, slowed hard, rising; it burns white, yellow, orange and red, then is smoke
      p = travel( t, 3.0, vec3( wind.x * 1.5, 5.0, wind.y * 1.5 ) );
      vec3 c = mix( vec3( 3.0, 2.7, 1.9 ), vec3( 2.6, 1.3, 0.25 ), smoothstep( 0.0, 0.15, age ) );
      c = mix( c, vec3( 1.6, 0.36, 0.06 ), smoothstep( 0.15, 0.35, age ) );
      c = mix( c, vec3( 0.12, 0.04, 0.02 ), smoothstep( 0.35, 0.6, age ) );
      vColor = mix( c, vec3( 0.03, 0.026, 0.024 ) * shade, smoothstep( 0.6, 0.8, age ) );
      vAlpha = smoothstep( 0.0, 0.03, age ) * ( 1.0 - smoothstep( 0.55, 1.0, age ) ) * 0.95;
    } else { // a falling meteor's smoke: pale and thin, spreading and drifting
      p = travel( t, 1.2, vec3( wind.x * 2.4, 0.8, wind.y * 2.4 ) );
      vColor = mix( vec3( 0.9, 0.42, 0.14 ), vec3( 0.32, 0.3, 0.28 ) * shade, smoothstep( 0.0, 0.2, age ) );
      vAlpha = smoothstep( 0.0, 0.05, age ) * ( 1.0 - smoothstep( 0.2, 1.0, age ) ) * 0.55;
    }
    p.y = max( p.y, ground );
    vec4 mvPosition = billboard( p, look.x * mix( 1.0, look.y, sqrt( age ) ), look.z * 6.28 + age * 0.8 );
    #include <fog_vertex>
  }
`

const softFragment = /* glsl */`
  varying vec2 vUv;
  varying vec3 vColor;
  varying float vAlpha;
  #include <common>
  #include <fog_pars_fragment>
  void main() {
    vec2 p = floor( vUv * 8.0 ) / 8.0 + 1.0 / 16.0;
    float r = length( p - 0.5 ) * 2.0;
    float a = ( 1.0 - smoothstep( 0.5, 0.95, r ) ) * vAlpha;
    if ( a < 0.01 ) discard;
    gl_FragColor = vec4( vColor, a );
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
    #include <fog_fragment>
  }
`

const ringVertex = /* glsl */`
  varying vec2 vUv;
  #include <common>
  #include <fog_pars_vertex>
  void main() {
    vUv = uv;
    vec4 mvPosition = modelViewMatrix * vec4( position, 1.0 );
    gl_Position = projectionMatrix * mvPosition;
    #include <fog_vertex>
  }
`

const ringFragment = /* glsl */`
  uniform float age; // 0 to 1 over the ring's run
  uniform float glow;
  varying vec2 vUv;
  #include <common>
  #include <fog_pars_fragment>
  void main() {
    vec2 p = floor( vUv * 48.0 ) / 48.0 + 1.0 / 96.0 - 0.5; // pixel steps
    float r = length( p ) * 2.0; // 1 at Radius
    float front = 1.0 - pow( 1.0 - age, 2.2 ); // out fast, slowing
    float a = smoothstep( front - 0.16, front, r ) * ( 1.0 - smoothstep( front, front + 0.03, r ) ) * pow( 1.0 - age, 1.4 );
    #ifdef USE_FOG
      a *= 1.0 - smoothstep( fogNear, fogFar, vFogDepth );
    #endif
    if ( a < 0.01 ) discard;
    gl_FragColor = vec4( vec3( 1.0, 0.82, 0.55 ) * 1.6 * glow, a );
  }
`

// A pool of billboards in one instanced draw: each slot is written once, when it is made, and moves in the shader.
function createPool(scene, count, uniforms, vertexShader, fragmentShader, options) {
  const geometry = new THREE.InstancedBufferGeometry()
  const quad = new THREE.PlaneGeometry(1, 1)
  geometry.index = quad.index
  geometry.setAttribute('position', quad.attributes.position)
  geometry.setAttribute('uv', quad.attributes.uv)
  const origin = new Float32Array(count * 4).fill(-1e4) // all made long ago: none shows
  const velocity = new Float32Array(count * 4).fill(1)
  const look = new Float32Array(count * 4)
  const ground = new Float32Array(count).fill(-1e4)
  const attributes = [[origin, 4, 'origin'], [velocity, 4, 'velocity'], [look, 4, 'look'], [ground, 1, 'ground']].map(([array, size, name]) => {
    const attribute = new THREE.InstancedBufferAttribute(array, size).setUsage(THREE.DynamicDrawUsage)
    geometry.setAttribute(name, attribute)
    return attribute
  })
  geometry.instanceCount = count
  const material = new THREE.ShaderMaterial({
    uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, uniforms]),
    vertexShader,
    fragmentShader,
    transparent: true,
    depthWrite: false,
    fog: true,
    ...options,
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.frustumCulled = false // the puffs are placed in the shader
  scene.add(mesh)
  let next = 0
  let dirty = false
  return {
    material,
    mesh,
    add(x, y, z, birth, vx, vy, vz, life, size, grow, kind, floor) {
      const i = next
      next = (next + 1) % count
      origin[i * 4] = x
      origin[i * 4 + 1] = y
      origin[i * 4 + 2] = z
      origin[i * 4 + 3] = birth
      velocity[i * 4] = vx
      velocity[i * 4 + 1] = vy
      velocity[i * 4 + 2] = vz
      velocity[i * 4 + 3] = life
      look[i * 4] = size
      look[i * 4 + 1] = grow
      look[i * 4 + 2] = Math.random()
      look[i * 4 + 3] = kind
      ground[i] = floor
      dirty = true
    },
    flush() {
      if (!dirty) return
      for (const attribute of attributes) attribute.needsUpdate = true
      dirty = false
    },
    alive: (now) => {
      let n = 0
      for (let i = 0; i < count; i++) if (now >= origin[i * 4 + 3] && now - origin[i * 4 + 3] < velocity[i * 4 + 3]) n++
      return n
    },
    dispose() {
      scene.remove(mesh)
      geometry.dispose()
      quad.dispose()
      material.dispose()
    },
  }
}

const rand = (a, b) => a + Math.random() * (b - a)
// A random direction, raised by `up` (0: anywhere above flat, 1: straight up).
function direction(out, up) {
  const angle = Math.random() * Math.PI * 2
  const y = up + (1 - up) * Math.random()
  const r = Math.sqrt(1 - y * y)
  return out.set(Math.cos(angle) * r, y, Math.sin(angle) * r)
}

export function createBlasts(scene, tier, { onMaterial } = {}) {
  const detail = tier.blastDetail ?? 1
  const many = (n) => Math.max(1, Math.round(n * detail))
  const glow = createPool(scene, tier.blastGlow ?? 256, { time: { value: 0 }, glow: { value: 1 } }, glowVertex, glowFragment,
    { name: 'GodlingBlastGlow', blending: THREE.AdditiveBlending, toneMapped: false })
  glow.mesh.renderOrder = 4 // over the smoke
  const soft = createPool(scene, tier.blastSoft ?? 192, {
    time: { value: 0 },
    wind: { value: new THREE.Vector2() },
    shade: { value: 1 },
    sand: { value: new THREE.Color(0xcdbb94) },
  }, softVertex, softFragment, { name: 'GodlingBlastSmoke' })
  soft.mesh.renderOrder = 3

  const ringGeometry = new THREE.PlaneGeometry(2, 2).rotateX(-Math.PI / 2)
  const rings = Array.from({ length: RINGS }, () => {
    const material = new THREE.ShaderMaterial({
      name: 'GodlingShockRing',
      uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, { age: { value: 1 }, glow: { value: 1 } }]),
      vertexShader: ringVertex,
      fragmentShader: ringFragment,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      toneMapped: false,
      fog: true,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
    })
    const mesh = new THREE.Mesh(ringGeometry, material)
    mesh.visible = false
    mesh.renderOrder = 2
    scene.add(mesh)
    return { mesh, material, blast: null }
  })
  let nextRing = 0

  // Chunks: a few charred stones in one instanced draw, thrown on the CPU (they bounce on the ground).
  const chunkCount = tier.blastChunks ?? 16
  const chunkGeometry = new THREE.DodecahedronGeometry(0.5, 0)
  const chunkMaterial = new THREE.MeshStandardMaterial({ roughness: 0.95, metalness: 0, flatShading: true })
  onMaterial?.(chunkMaterial)
  const chunkMesh = new THREE.InstancedMesh(chunkGeometry, chunkMaterial, chunkCount)
  chunkMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
  chunkMesh.frustumCulled = false
  const NOWHERE = new THREE.Matrix4().makeScale(0, 0, 0)
  const CHUNK_COLORS = [0x2b2421, 0x4f4740, 0x8f7a58].map((hex) => new THREE.Color(hex)) // charred, rock, sand crust
  for (let i = 0; i < chunkCount; i++) {
    chunkMesh.setMatrixAt(i, NOWHERE)
    chunkMesh.setColorAt(i, CHUNK_COLORS[i % CHUNK_COLORS.length])
  }
  scene.add(chunkMesh)
  const chunks = Array.from({ length: chunkCount }, () => ({
    alive: false, p: new THREE.Vector3(), v: new THREE.Vector3(), axis: new THREE.Vector3(0, 1, 0), spin: 0, angle: 0,
    size: 1, born: 0, life: 1, blast: null, bounced: false,
  }))
  let nextChunk = 0

  // The flash's light, there from the start (a light added later would recompile every material), dark until a blast.
  const light = tier.blastLight ? new THREE.PointLight(0xffd29a, 0, 80, 1.5) : null
  if (light) scene.add(light)

  const seen = new Set() // Blast markers already played
  const pending = [] // seen this frame, played in update (once the craters of the same frame are known)
  const floors = new Map() // SkyId -> the crater's floor
  const meteors = new Map() // entity id -> { y, next }
  const blasts = []
  const dir = new THREE.Vector3()
  const matrix = new THREE.Matrix4()
  const turn = new THREE.Quaternion()
  const scale = new THREE.Vector3()
  let now = 0

  function trail(x, y, z, size) {
    const s = Math.max(1, size)
    // A tail of glowing puffs (the newest, at the head, white-hot) and a thin smoke behind.
    glow.add(x + rand(-0.15, 0.15) * s, y + 0.2 * s, z + rand(-0.15, 0.15) * s, now, rand(-0.6, 0.6), rand(2, 4), rand(-0.6, 0.6),
      rand(0.3, 0.45), s * rand(1, 1.4), 1.4, HEAT, -1e4)
    soft.add(x, y + 0.5 * s, z, now + 0.04, rand(-0.5, 0.5), rand(0.5, 1.5), rand(-0.5, 0.5), rand(1.2, 2), s * 0.5, 3, TRAIL, -1e4)
  }

  function explode({ key, x, y, z, radius }) {
    const R = Math.min(20, Math.max(2, radius))
    const floor = floors.get(key) ?? y
    const blast = { key, x, y, z, radius: R, floor, born: now, smoulder: now + 0.4 }
    blasts.push(blast)
    glow.add(x, y + 1.2, z, now, 0, 0, 0, 0.18, R * 1.8, 1.4, FLASH, -1e4)
    for (let i = many(22); i > 0; i--) {
      direction(dir, 0.1).multiplyScalar(R * rand(1, 2))
      soft.add(x, y + 0.5, z, now + rand(0, 0.06), dir.x, dir.y, dir.z, rand(0.9, 1.4), R * rand(0.32, 0.48), 2.3, FIRE, floor)
    }
    for (let i = many(6); i > 0; i--) {
      direction(dir, 0.3).multiplyScalar(R * rand(0.4, 0.9))
      glow.add(x, y + 0.8, z, now, dir.x, dir.y, dir.z, rand(0.35, 0.55), R * rand(0.4, 0.55), 1.8, HEAT, floor)
    }
    for (let i = many(60); i > 0; i--) {
      direction(dir, 0.25).multiplyScalar(rand(9, 22))
      glow.add(x, y + 0.5, z, now, dir.x, dir.y, dir.z, rand(0.9, 1.8), rand(0.3, 0.55), 0.6, EMBER, floor + 0.15)
    }
    for (let i = many(14); i > 0; i--) { // coals left in the crater
      const a = Math.random() * Math.PI * 2
      const r = Math.sqrt(Math.random()) * R * 0.35
      glow.add(x + Math.cos(a) * r, floor + 0.3, z + Math.sin(a) * r, now + rand(0.1, 0.4), 0, rand(0.5, 1.5), 0,
        rand(2.5, 4.5), rand(0.22, 0.36), 0.7, EMBER, floor + 0.12)
    }
    for (let i = many(24); i > 0; i--) {
      direction(dir, 0.4).multiplyScalar(rand(2, 5))
      soft.add(x + rand(-0.2, 0.2) * R, y + 0.8, z + rand(-0.2, 0.2) * R, now + rand(0, 0.25), dir.x, dir.y + rand(3, 7), dir.z,
        rand(2.2, 3.4), R * rand(0.25, 0.4), 2.6, SMOKE, floor)
    }
    for (let i = many(30); i > 0; i--) {
      direction(dir, 0.35).multiplyScalar(rand(5, 12))
      soft.add(x + rand(-0.15, 0.15) * R, floor + 0.5, z + rand(-0.15, 0.15) * R, now, dir.x, dir.y, dir.z,
        rand(0.9, 1.5), rand(0.5, 1), 1.8, SAND, floor + 0.2)
    }
    const ringDust = many(22)
    for (let i = 0; i < ringDust; i++) {
      const a = (i / ringDust) * Math.PI * 2 + rand(-0.1, 0.1)
      const speed = R * 2.4 * rand(0.9, 1.1)
      soft.add(x + Math.cos(a) * R * 0.15, floor + 0.5, z + Math.sin(a) * R * 0.15, now + 0.03, Math.cos(a) * speed, 0.5,
        Math.sin(a) * speed, rand(0.9, 1.4), rand(1, 1.8), 2.4, DUST, floor + 0.3)
    }
    for (let i = Math.min(chunkCount, many(20)); i > 0; i--) {
      const chunk = chunks[nextChunk]
      nextChunk = (nextChunk + 1) % chunkCount
      direction(dir, 0.3)
      chunk.p.set(x + dir.x * 0.5, y + 0.6, z + dir.z * 0.5)
      chunk.v.copy(dir).multiplyScalar(rand(7, 16))
      chunk.axis.set(rand(-1, 1), rand(-1, 1), rand(-1, 1)).normalize()
      chunk.spin = rand(4, 12)
      chunk.angle = 0
      chunk.size = rand(0.35, 0.8) * (R / 7)
      chunk.born = now
      chunk.life = rand(1.3, 2.2)
      chunk.blast = blast
      chunk.bounced = false
      chunk.alive = true
    }
    const ring = rings[nextRing]
    nextRing = (nextRing + 1) % RINGS
    ring.blast = blast
    ring.mesh.scale.setScalar(R)
    ring.mesh.visible = true
  }

  function moveChunks(dt) {
    let moved = false
    chunks.forEach((chunk, i) => {
      if (!chunk.alive) return
      moved = true
      const age = (now - chunk.born) / chunk.life
      if (age >= 1) {
        chunk.alive = false
        chunkMesh.setMatrixAt(i, NOWHERE)
        return
      }
      chunk.v.y -= GRAVITY * dt
      chunk.p.addScaledVector(chunk.v, dt)
      const rest = chunk.blast.floor + chunk.size * 0.4
      if (chunk.p.y < rest) {
        chunk.p.y = rest
        if (!chunk.bounced && chunk.v.y < -4) {
          chunk.v.set(chunk.v.x * 0.5, -chunk.v.y * 0.3, chunk.v.z * 0.5)
          chunk.spin *= 0.5
          chunk.bounced = true
        } else {
          chunk.v.set(0, 0, 0)
          chunk.spin = 0
        }
      }
      chunk.angle += chunk.spin * dt
      const size = chunk.size * (age < 0.75 ? 1 : 1 - (age - 0.75) / 0.25) // it sinks away at the end
      chunkMesh.setMatrixAt(i, matrix.compose(chunk.p, turn.setFromAxisAngle(chunk.axis, chunk.angle), scale.setScalar(size)))
    })
    if (moved) chunkMesh.instanceMatrix.needsUpdate = true
  }

  return {
    // Each frame, for each entity: Blast markers, craters and falling meteors. Before the hidden check: a marker may
    // be invisible.
    watch(entity, dt) {
      const role = entity.render?.role
      const attributes = entity.attributes || {}
      if (role === 'Blast') {
        if (!seen.has(entity.id)) {
          seen.add(entity.id)
          const [x, y, z] = entity.position
          pending.push({ key: String(attributes.SkyId ?? entity.id), x, y, z, radius: Number(attributes.Radius) || 7 })
        }
        return
      }
      if (role === 'Crater') { // its middle is about the ground (the world sets it 0.1 above, its dish sunk below)
        floors.set(String(attributes.SkyId ?? entity.id), entity.position[1])
        return
      }
      if (role !== 'Stone' || attributes.SkyEvent !== 'Meteor') return // the stream has no names: Meteor_<n> is this

      const y = entity.position[1]
      const tracked = meteors.get(entity.id)
      if (!tracked) {
        meteors.set(entity.id, { y, next: 0 })
        return
      }
      const vy = dt > 0 ? (y - tracked.y) / dt : 0
      tracked.y = y
      if (vy < -TRAIL_SPEED && now >= tracked.next) {
        trail(entity.position[0], y, entity.position[2], entity.size?.[1] ?? 2.5)
        tracked.next = now + TRAIL_EVERY / detail
      }
    },
    // Forget what is gone.
    prune(activeIds) {
      for (const id of seen) if (!activeIds.has(id)) seen.delete(id)
      for (const id of meteors.keys()) if (!activeIds.has(id)) meteors.delete(id)
    },
    // time: the same clock the puffs were made on (seconds); wind: what blows now (wind.js). Returns how much the
    // ambient light flares, on a tier without the flash's own light.
    update({ time, dt, daylight, wind, camera }) {
      now = time
      for (const blast of pending) explode(blast)
      pending.length = 0
      let flare = 0
      let latest = null
      for (let i = blasts.length - 1; i >= 0; i--) {
        const blast = blasts[i]
        const age = now - blast.born
        if (age > LINGER) {
          blasts.splice(i, 1)
          continue
        }
        const floor = floors.get(blast.key)
        if (floor != null && age < 0.6) blast.floor = floor // the crater came a moment after the blast
        if (now < blast.born + SMOULDER && now >= blast.smoulder) { // a thin smoke from the crater, thinning out
          const a = Math.random() * Math.PI * 2
          const r = Math.random() * blast.radius * 0.3
          soft.add(blast.x + Math.cos(a) * r, blast.floor + 0.4, blast.z + Math.sin(a) * r, now, 0, rand(1.5, 3), 0,
            rand(2, 3), rand(0.8, 1.2), 3.5, SMOKE, blast.floor)
          blast.smoulder = now + (0.3 / detail) * (1 + (2 * age) / SMOULDER)
        }
        if (!latest || blast.born > latest.born) latest = blast
      }
      for (const ring of rings) {
        if (!ring.blast) continue
        const age = (now - ring.blast.born) / 0.6
        if (age >= 1) {
          ring.blast = null
          ring.mesh.visible = false
          continue
        }
        ring.mesh.position.set(ring.blast.x, ring.blast.floor + 0.08, ring.blast.z)
        ring.material.uniforms.age.value = age
        ring.material.uniforms.glow.value = 1 - 0.4 * daylight
      }
      moveChunks(dt)
      const age = latest ? now - latest.born : Infinity
      const flash = Math.exp(-age / 0.08)
      const burn = Math.max(0, 1 - age / 0.8)
      if (light) {
        light.intensity = 0
        if (latest && age < 0.8) {
          light.position.set(latest.x, latest.y + 2.5, latest.z)
          light.intensity = 600 * flash + 60 * burn * (0.8 + 0.2 * Math.sin(age * 40))
          light.color.setRGB(1, 0.62 + 0.3 * flash, 0.3 + 0.5 * flash)
        }
      } else if (latest && age < 0.5) {
        const d = camera.position.distanceTo(dir.set(latest.x, latest.y, latest.z))
        flare = (1.4 * flash + 0.3 * burn) / (1 + (d / (latest.radius * 4)) ** 2)
      }
      glow.material.uniforms.time.value = time
      glow.material.uniforms.glow.value = 1.3 - 0.5 * daylight // added light: by day on bright sand it washes out
      const u = soft.material.uniforms
      u.time.value = time
      if (wind) u.wind.value.copy(wind)
      u.shade.value = 0.25 + 0.75 * daylight
      glow.flush()
      soft.flush()
      return flare
    },
    // How hard the camera at `position` is jolted now (0 to 1): sharp, short, weaker with distance.
    jolt(position) {
      let k = 0
      for (const blast of blasts) {
        const age = now - blast.born
        if (age > 1.2) continue
        const dx = position.x - blast.x
        const dy = position.y - blast.y
        const dz = position.z - blast.z
        const near = 1 / (1 + (dx * dx + dy * dy + dz * dz) / (blast.radius * 3) ** 2)
        k = Math.max(k, 0.9 * Math.exp(-age * 3.5) * near)
      }
      return k
    },
    info: () => ({
      time: Number(now.toFixed(3)),
      blasts: blasts.length,
      glow: glow.alive(now),
      smoke: soft.alive(now),
      chunks: chunks.filter((chunk) => chunk.alive).length,
      meteors: meteors.size,
      light: light ? Number(light.intensity.toFixed(1)) : null,
    }),
    dispose() {
      glow.dispose()
      soft.dispose()
      for (const ring of rings) {
        scene.remove(ring.mesh)
        ring.material.dispose()
      }
      ringGeometry.dispose()
      scene.remove(chunkMesh)
      chunkGeometry.dispose()
      chunkMaterial.dispose()
      chunkMesh.dispose()
      if (light) scene.remove(light)
      seen.clear()
      floors.clear()
      meteors.clear()
      blasts.length = 0
    },
  }
}
