import * as THREE from 'three'

// Fires (RenderRole "Fire": a part over a burning log, ADR-007). Each is drawn as pixel-style flames on three crossed
// quads, a column of smoke that rises some 40 units (on the beach it is a rescue signal, seen from far off), and a
// warm light that matters at night. Flames and smoke move in their shaders, so a fire costs nothing per frame
// on the CPU. The lights come from a fixed pool, the nearest fires first: a fire lit or put out never changes the
// number of lights, which would recompile every material.

const SMOKE_HEIGHT = 40
const LIGHT_COLOR = 0xff8a3c

const flameVertex = /* glsl */`
  varying vec2 vUv;
  varying float vSeed;
  void main() {
    vUv = uv;
    vSeed = fract( dot( modelMatrix[ 3 ].xz, vec2( 0.137, 0.271 ) ) ); // each fire flickers its own way
    gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4( position, 1.0 );
  }
`

const flameFragment = /* glsl */`
  uniform float time;
  uniform float glow;
  varying vec2 vUv;
  varying float vSeed;
  float hash( vec2 p ) { return fract( sin( dot( p, vec2( 127.1, 311.7 ) ) ) * 43758.5453 ); }
  float noise( vec2 p ) {
    vec2 i = floor( p );
    vec2 f = fract( p );
    f = f * f * ( 3.0 - 2.0 * f );
    return mix( mix( hash( i ), hash( i + vec2( 1.0, 0.0 ) ), f.x ), mix( hash( i + vec2( 0.0, 1.0 ) ), hash( i + vec2( 1.0 ) ), f.x ), f.y );
  }
  void main() {
    vec2 p = floor( vUv * 12.0 ) / 12.0 + 1.0 / 24.0; // pixel flames, as the blocks
    float t = time + vSeed * 10.0;
    float n = noise( vec2( p.x * 4.0 + vSeed * 7.0, p.y * 3.0 - t * 2.4 ) ) * 0.65
      + noise( vec2( p.x * 8.0, p.y * 6.0 - t * 4.0 ) ) * 0.35;
    float shape = mix( 0.42, 0.04, p.y ) - abs( p.x - 0.5 ) + ( n - 0.5 ) * 0.35 * ( 0.3 + p.y );
    float flame = smoothstep( 0.0, 0.08, shape ) * ( 1.0 - smoothstep( 0.55, 1.0, p.y + ( n - 0.5 ) * 0.4 ) );
    if ( flame < 0.02 ) discard;
    float heat = clamp( shape * 3.0 + ( 1.0 - p.y ) * 0.4, 0.0, 1.0 );
    vec3 color = mix( vec3( 0.9, 0.18, 0.02 ), vec3( 1.0, 0.82, 0.3 ), heat );
    gl_FragColor = vec4( color * flame * glow, flame );
  }
`

const smokeVertex = /* glsl */`
  uniform float time;
  uniform float height;
  attribute float seed;
  varying float vAlpha;
  varying float vLife;
  varying vec2 vUv;
  #include <common>
  #include <fog_pars_vertex>
  void main() {
    vec3 origin = modelMatrix[ 3 ].xyz;
    float life = fract( time * 0.06 + seed ); // a puff takes about 16 s to rise
    float h = life * height;
    vec2 drift = vec2( 0.8, 0.35 ) * h * 0.35 // a steady breeze bends the column
      + vec2( sin( seed * 40.0 + time * 0.5 ), cos( seed * 31.0 + time * 0.4 ) ) * ( 0.4 + h * 0.06 );
    vec3 centre = origin + vec3( drift.x, 1.5 + h, drift.y );
    float size = mix( 1.2, 9.0, sqrt( life ) ) * ( 0.8 + 0.4 * fract( seed * 7.3 ) );
    vec4 mvPosition = viewMatrix * vec4( centre, 1.0 );
    float a = ( fract( seed * 13.7 ) - 0.5 ) * 6.28 + time * 0.1;
    mvPosition.xy += mat2( cos( a ), -sin( a ), sin( a ), cos( a ) ) * position.xy * size;
    gl_Position = projectionMatrix * mvPosition;
    vAlpha = smoothstep( 0.0, 0.08, life ) * ( 1.0 - smoothstep( 0.55, 1.0, life ) );
    vLife = life;
    vUv = uv;
    #include <fog_vertex>
  }
`

const smokeFragment = /* glsl */`
  uniform vec3 smokeColor;
  uniform vec3 glowColor;
  uniform float opacity;
  varying float vAlpha;
  varying float vLife;
  varying vec2 vUv;
  #include <common>
  #include <fog_pars_fragment>
  void main() {
    float r = length( vUv - 0.5 ) * 2.0;
    float a = smoothstep( 1.0, 0.35, r ) * vAlpha * opacity;
    if ( a < 0.01 ) discard;
    vec3 color = mix( glowColor, smokeColor, smoothstep( 0.0, 0.15, vLife ) ); // lit by the flames at its foot
    gl_FragColor = vec4( color, a );
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
    #include <fog_fragment>
  }
`

function crossedQuads() {
  const quads = [0, 1, 2].map((k) => {
    const plane = new THREE.PlaneGeometry(1, 1)
    plane.translate(0, 0.5, 0) // standing on its foot
    plane.rotateY((k * Math.PI) / 3)
    return plane
  })
  const geometry = new THREE.BufferGeometry()
  const positions = []
  const uvs = []
  const indices = []
  for (const plane of quads) {
    const offset = positions.length / 3
    positions.push(...plane.attributes.position.array)
    uvs.push(...plane.attributes.uv.array)
    indices.push(...Array.from(plane.index.array, (i) => i + offset))
    plane.dispose()
  }
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2))
  geometry.setIndex(indices)
  return geometry
}

export function createFires(scene, tier) {
  const flameGeometry = crossedQuads()
  const flameMaterial = new THREE.ShaderMaterial({
    name: 'GodlingFlame',
    uniforms: { time: { value: 0 }, glow: { value: 1.4 } },
    vertexShader: flameVertex,
    fragmentShader: flameFragment,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    toneMapped: false,
  })

  const smokeGeometry = new THREE.InstancedBufferGeometry()
  const quad = new THREE.PlaneGeometry(1, 1)
  smokeGeometry.index = quad.index
  smokeGeometry.setAttribute('position', quad.attributes.position)
  smokeGeometry.setAttribute('uv', quad.attributes.uv)
  const seeds = new Float32Array(tier.smokePuffs).map((_, i) => (i + Math.random() * 0.5) / tier.smokePuffs)
  smokeGeometry.setAttribute('seed', new THREE.InstancedBufferAttribute(seeds, 1))
  smokeGeometry.instanceCount = tier.smokePuffs
  const smokeMaterial = new THREE.ShaderMaterial({
    name: 'GodlingSmoke',
    uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
      time: { value: 0 },
      height: { value: SMOKE_HEIGHT },
      smokeColor: { value: new THREE.Color() },
      glowColor: { value: new THREE.Color() },
      opacity: { value: 0.45 },
    }]),
    vertexShader: smokeVertex,
    fragmentShader: smokeFragment,
    transparent: true,
    depthWrite: false,
    fog: true,
  })

  const lights = Array.from({ length: tier.fireLights }, () => {
    const light = new THREE.PointLight(LIGHT_COLOR, 0, 38, 1.7)
    scene.add(light)
    return light
  })

  const fires = new Map() // entity id -> { group, flames, seed }
  // Linear light: sRGB output lifts darks a lot, so night smoke has to be near black to read as dark.
  const daySmoke = new THREE.Color(0.42, 0.42, 0.4)
  const nightSmoke = new THREE.Color(0.018, 0.02, 0.026)
  const glow = new THREE.Color(0.95, 0.5, 0.22)
  const byDistance = []

  return {
    add(id) {
      const group = new THREE.Group()
      const flames = new THREE.Mesh(flameGeometry, flameMaterial)
      flames.frustumCulled = false
      const smoke = new THREE.Mesh(smokeGeometry, smokeMaterial)
      smoke.frustumCulled = false // the puffs are placed in the shader
      smoke.renderOrder = 3
      group.add(flames, smoke)
      scene.add(group)
      fires.set(id, { group, flames, seed: Math.random() * 100 })
    },
    // The part stands on the log: its foot is where the flames start.
    place(id, position, size) {
      const fire = fires.get(id)
      if (!fire) return
      const [w, h] = size || [2.2, 3, 2.2]
      fire.group.position.set(position[0], position[1] - h / 2, position[2])
      fire.flames.scale.set(w * 0.95, h * 1.1, w * 0.95)
    },
    remove(id) {
      const fire = fires.get(id)
      if (!fire) return
      scene.remove(fire.group)
      fires.delete(id)
    },
    update({ time, camera, daylight, night }) {
      flameMaterial.uniforms.time.value = time
      flameMaterial.uniforms.glow.value = 1.4 - 0.65 * daylight // added light: by day on bright sand it would wash out to white
      const u = smokeMaterial.uniforms
      u.time.value = time
      u.smokeColor.value.copy(nightSmoke).lerp(daySmoke, daylight)
      u.glowColor.value.copy(glow).multiplyScalar(0.45 + 0.55 * night)
      byDistance.length = 0
      for (const fire of fires.values()) byDistance.push(fire)
      byDistance.sort((a, b) => a.group.position.distanceToSquared(camera.position) - b.group.position.distanceToSquared(camera.position))
      lights.forEach((light, i) => {
        const fire = byDistance[i]
        if (!fire) {
          light.intensity = 0
          return
        }
        const flicker = 0.86 + 0.09 * Math.sin(time * 13 + fire.seed) + 0.05 * Math.sin(time * 29 + fire.seed * 2)
        light.position.copy(fire.group.position).y += 1.6
        light.intensity = (34 + 22 * night) * flicker // stronger at night, when it is the light there is
      })
    },
    dispose() {
      for (const fire of fires.values()) scene.remove(fire.group)
      fires.clear()
      for (const light of lights) scene.remove(light)
      flameGeometry.dispose()
      flameMaterial.dispose()
      smokeGeometry.dispose()
      quad.dispose()
      smokeMaterial.dispose()
    },
  }
}
