import * as THREE from 'three'

// The sea: one opaque mesh that follows the camera to the horizon, with Gerstner waves in the vertex shader and,
// per pixel, a fresnel blend of the water's own colour and the sky (sky.js's sky map), the sun's glint and foam
// at the shore. How far each spot is from land comes from a distance map baked from the island's footprint, so
// the water is turquoise and calm near the beach and deep blue further out, at no cost per frame.
//
// The server's Ocean part only sets the sea level: everything here is for the eye, and its waves do not move
// anything in the world.

const SHORE_RANGE = 24 // world units from the coast to where the water is fully deep
const SHORE_MAP_SIZE = 256
const SHORE_HALF_EXTENT = 160 // the map covers the island and its coast, centred on the world origin
const HALF_SIZE = 1600 // the mesh reaches past the fog
const SNAP = 8 // the mesh moves in steps, so its vertices rarely change where they sample the waves

// Direction (x, z), wavelength, amplitude. The ground's top is 0.5 above the sea, so the waves stay low.
const WAVES = [
  [0.96, 0.28, 34, 0.15],
  [-0.37, 0.93, 19, 0.09],
  [0.71, -0.71, 11, 0.055],
  [-0.94, -0.34, 6.5, 0.03],
]

const vertexShader = /* glsl */`
  uniform float time;
  uniform float seaLevel;
  uniform sampler2D shoreMap;
  uniform vec2 shoreCenter;
  uniform float shoreExtent;
  uniform vec4 waves[ WAVE_COUNT ];
  varying vec3 vWorld;
  varying vec3 vNormal;
  varying float vShore;

  #include <common>
  #include <fog_pars_vertex>

  // 0 at the coast, 1 at SHORE_RANGE units out to sea and beyond.
  float shoreDistance( vec2 xz ) {
    vec2 uv = ( xz - shoreCenter ) / ( 2.0 * shoreExtent ) + 0.5;
    if ( uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0 ) return 1.0;
    return texture2D( shoreMap, uv ).r;
  }

  void main() {
    vec4 world = modelMatrix * vec4( position, 1.0 );
    vec2 xz = world.xz;
    float shore = shoreDistance( xz );
    float calm = mix( 0.3, 1.0, smoothstep( 0.0, 0.4, shore ) );
    float distanceToEye = length( cameraPosition.xz - xz );
    vec3 offset = vec3( 0.0 );
    vec3 normal = vec3( 0.0, 1.0, 0.0 );
    for ( int i = 0; i < WAVE_COUNT; i ++ ) {
      vec4 w = waves[ i ];
      float k = 6.2831853 / w.z;
      // Short waves fade out with distance, where the mesh is too coarse to carry them.
      float a = w.w * calm * ( 1.0 - smoothstep( w.z * 6.0, w.z * 14.0, distanceToEye ) );
      float qa = min( 0.5 / ( k * w.w * float( WAVE_COUNT ) ), 1.0 ) * a; // steepness Q times amplitude
      float f = k * ( dot( w.xy, xz ) - sqrt( 9.8 / k ) * 0.55 * time );
      float s = sin( f );
      float c = cos( f );
      offset += vec3( qa * w.x * c, a * s, qa * w.y * c );
      normal -= vec3( w.x * k * a * c, qa * k * s, w.y * k * a * c );
    }
    world.xyz += offset;
    world.y = seaLevel + offset.y;
    vWorld = world.xyz;
    vNormal = normalize( normal );
    vShore = shore;
    vec4 mvPosition = viewMatrix * world;
    gl_Position = projectionMatrix * mvPosition;
    #include <fog_vertex>
  }
`

const fragmentShader = /* glsl */`
  uniform float time;
  uniform vec3 sunDirection;
  uniform vec3 sunColor;
  uniform float sunStrength;
  uniform vec3 deepColor;
  uniform vec3 shallowColor;
  uniform vec3 foamColor;
  uniform float waterLight;
  uniform sampler2D skyMap;
  varying vec3 vWorld;
  varying vec3 vNormal;
  varying float vShore;

  #include <common>
  #include <fog_pars_fragment>

  vec3 skyColor( vec3 d ) {
    float u = atan( d.z, d.x ) / ( 2.0 * PI ) + 0.5;
    float v = asin( clamp( d.y, 0.0, 1.0 ) ) / ( 0.5 * PI );
    return texture2D( skyMap, vec2( u, v ) ).rgb;
  }

  void main() {
    vec3 n = normalize( vNormal );
    #ifdef SEA_RIPPLES
      // Small ripples crossing in two directions, too fine for the mesh.
      vec2 p = vWorld.xz;
      float r1 = cos( dot( p, vec2( 0.81, 0.59 ) ) * 2.3 + time * 2.1 );
      float r2 = cos( dot( p, vec2( -0.47, 0.88 ) ) * 3.1 + time * 2.7 );
      n = normalize( n + vec3( 0.81 * r1 + -0.47 * r2, 0.0, 0.59 * r1 + 0.88 * r2 ) * 0.035 );
    #endif
    vec3 toEye = normalize( cameraPosition - vWorld );
    float facing = max( dot( n, toEye ), 0.0 );
    float fresnel = 0.02 + 0.98 * pow( 1.0 - facing, 5.0 );
    vec3 r = reflect( -toEye, n );
    vec3 sky = skyColor( r );

    vec3 body = mix( shallowColor, deepColor, smoothstep( 0.0, 1.0, vShore ) ) * waterLight;
    // The reflection is held below a mirror's, so the water keeps its colour at a low angle.
    vec3 color = mix( body, sky, fresnel * 0.7 );
    float glint = pow( max( dot( r, sunDirection ), 0.0 ), 700.0 );
    color += sunColor * glint * sunStrength;

    // Foam: a broken line along the coast, and bands that roll in towards it.
    float coast = vShore * ${SHORE_RANGE.toFixed(1)};
    vec2 q = vWorld.xz;
    float breakup = 0.5 + 0.5 * sin( q.x * 0.37 + sin( q.y * 0.53 + time * 0.4 ) * 1.7 ) *
      sin( q.y * 0.41 + sin( q.x * 0.29 - time * 0.3 ) * 1.9 );
    float line = 1.0 - smoothstep( 0.15, 1.4 + breakup, coast );
    float bands = smoothstep( 0.86, 1.0, sin( coast * 1.3 + time * 1.2 ) ) * ( 1.0 - smoothstep( 1.0, 6.0, coast ) );
    float foam = clamp( line + bands * breakup * 0.5, 0.0, 1.0 );
    color = mix( color, foamColor * waterLight, foam * 0.85 );

    gl_FragColor = vec4( color, 1.0 );
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
    #include <fog_fragment>
  }
`

function createSeaGeometry(segments) {
  // Dense near the camera, sparse towards the horizon: linear in the middle, cubic further out.
  const geometry = new THREE.PlaneGeometry(2, 2, segments, segments)
  geometry.rotateX(-Math.PI / 2)
  const position = geometry.attributes.position
  const stretch = (t) => HALF_SIZE * (0.1 * t + 0.9 * t * t * t)
  for (let i = 0; i < position.count; i++) {
    position.setX(i, stretch(position.getX(i)))
    position.setZ(i, stretch(position.getZ(i)))
  }
  geometry.computeBoundingSphere()
  return geometry
}

// Land at sea level, as XZ footprints: boxes (center, half size, 3x3 rotation or null). Returns the distance map.
export function bakeShoreDistances(boxes, out) {
  const n = SHORE_MAP_SIZE
  const cell = (SHORE_HALF_EXTENT * 2) / n
  const far = 1e9
  const dist = new Float32Array(n * n).fill(far)
  for (const box of boxes) {
    const [cx, , cz] = box.center
    const [hx, , hz] = box.half
    const reach = Math.hypot(hx, hz)
    const i0 = Math.max(0, Math.floor((cx - reach + SHORE_HALF_EXTENT) / cell))
    const i1 = Math.min(n - 1, Math.ceil((cx + reach + SHORE_HALF_EXTENT) / cell))
    const j0 = Math.max(0, Math.floor((cz - reach + SHORE_HALF_EXTENT) / cell))
    const j1 = Math.min(n - 1, Math.ceil((cz + reach + SHORE_HALF_EXTENT) / cell))
    const r = box.rotation
    for (let j = j0; j <= j1; j++) {
      for (let i = i0; i <= i1; i++) {
        const dx = (i + 0.5) * cell - SHORE_HALF_EXTENT - cx
        const dz = (j + 0.5) * cell - SHORE_HALF_EXTENT - cz
        // Into the box's own axes (the rotation's columns), when it is turned.
        const lx = r ? r[0][0] * dx + r[2][0] * dz : dx
        const lz = r ? r[0][2] * dx + r[2][2] * dz : dz
        if (Math.abs(lx) <= hx && Math.abs(lz) <= hz) dist[j * n + i] = 0
      }
    }
  }
  // Two-pass chamfer distance (3 straight, 4 diagonal), in thirds of a cell.
  const at = (i, j) => (i < 0 || j < 0 || i >= n || j >= n ? far : dist[j * n + i])
  for (let j = 0; j < n; j++) {
    for (let i = 0; i < n; i++) {
      const k = j * n + i
      dist[k] = Math.min(dist[k], at(i - 1, j) + 3, at(i, j - 1) + 3, at(i - 1, j - 1) + 4, at(i + 1, j - 1) + 4)
    }
  }
  for (let j = n - 1; j >= 0; j--) {
    for (let i = n - 1; i >= 0; i--) {
      const k = j * n + i
      dist[k] = Math.min(dist[k], at(i + 1, j) + 3, at(i, j + 1) + 3, at(i + 1, j + 1) + 4, at(i - 1, j + 1) + 4)
    }
  }
  for (let k = 0; k < n * n; k++) {
    out[k] = Math.round(Math.min(1, (dist[k] / 3) * cell / SHORE_RANGE) * 255)
  }
  return out
}

export function createSea(scene, tier, sky) {
  const shoreData = new Uint8Array(SHORE_MAP_SIZE * SHORE_MAP_SIZE).fill(255)
  const shoreMap = new THREE.DataTexture(shoreData, SHORE_MAP_SIZE, SHORE_MAP_SIZE, THREE.RedFormat, THREE.UnsignedByteType)
  shoreMap.magFilter = THREE.LinearFilter
  shoreMap.minFilter = THREE.LinearFilter
  shoreMap.needsUpdate = true

  const waveCount = Math.min(tier.seaWaves, WAVES.length)
  const material = new THREE.ShaderMaterial({
    name: 'GodlingSea',
    vertexShader,
    fragmentShader,
    defines: { WAVE_COUNT: waveCount, ...(tier.seaRipples ? { SEA_RIPPLES: '' } : {}) },
    uniforms: THREE.UniformsUtils.merge([
      THREE.UniformsLib.fog,
      {
        time: { value: 0 },
        seaLevel: { value: -0.5 },
        shoreMap: { value: null },
        shoreCenter: { value: new THREE.Vector2(0, 0) },
        shoreExtent: { value: SHORE_HALF_EXTENT },
        waves: { value: WAVES.slice(0, waveCount).map(([x, z, length, amp]) => new THREE.Vector4(x, z, length, amp)) },
        sunDirection: { value: new THREE.Vector3() },
        sunColor: { value: new THREE.Color() },
        sunStrength: { value: 6 },
        deepColor: { value: new THREE.Color(0x0b4373) },
        shallowColor: { value: new THREE.Color(0x1aa6b8) },
        foamColor: { value: new THREE.Color(0xf4fbff) },
        waterLight: { value: 1 },
        skyMap: { value: null },
      },
    ]),
    fog: true,
  })
  // Textures are set after the merge, which would otherwise clone them.
  material.uniforms.shoreMap.value = shoreMap
  material.uniforms.skyMap.value = sky.map

  const mesh = new THREE.Mesh(createSeaGeometry(tier.seaSegments), material)
  mesh.frustumCulled = false
  mesh.visible = false // until the world says where the sea is
  scene.add(mesh)

  let shoreKey = ''

  return {
    mesh,
    // `seaLevel` is the top of the Ocean part; `land` lists the island's footprints at that height.
    update({ camera, time, seaLevel, land, landKey }) {
      if (seaLevel == null) {
        mesh.visible = false
        return
      }
      mesh.visible = true
      const u = material.uniforms
      u.seaLevel.value = seaLevel
      u.time.value = time
      u.sunDirection.value.copy(sky.sun)
      u.sunColor.value.copy(sky.sunColor)
      u.sunStrength.value = 6 * sky.daylight
      u.waterLight.value = 0.25 + 0.75 * sky.daylight
      mesh.position.set(Math.round(camera.position.x / SNAP) * SNAP, 0, Math.round(camera.position.z / SNAP) * SNAP)
      if (landKey !== shoreKey) {
        shoreKey = landKey
        bakeShoreDistances(land, shoreData)
        shoreMap.needsUpdate = true
      }
    },
    dispose() {
      scene.remove(mesh)
      mesh.geometry.dispose()
      material.dispose()
      shoreMap.dispose()
    },
  }
}
