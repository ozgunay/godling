import * as THREE from 'three'

// Lightning: the Lightning power, and the storms of heavy rain. The world marks a strike with a short-lived part,
// SkyBolt_<n> (RenderRole "SkyFlash", a thin post standing on the strike point), and the strike plays once, when the
// marker is first seen, as real lightning goes and as games draw it:
// - the stepped leader: a faint, forked channel feels its way down from the clouds in steps,
// - the return stroke: the moment it touches, the whole channel blazes white, forks and all, and the island flashes,
// - restrikes: one to three more strokes down the main channel only, each weaker (real ones come 20-50 ms apart; these
//   are slowed to 70-130 ms, which a screen can show as the flicker the eye sees),
// - the afterglow, fading, and short arcs crackling along the ground where it struck.
// The bolt is cut by midpoint displacement from the clouds to the strike point, with forks thrown off downwards that
// fork again. It is drawn as camera-facing ribbons, all in one draw call: a white core inside a violet-blue glow,
// blended by keeping the brightest (so forks crossing the channel never stack into hot spots). Each strike's shape and
// rhythm come from its marker, so every viewer, and the island's past, sees the same bolt. The flash raises the
// exposure (the sky and clouds too), lifts the ambient light by night, and on stronger tiers lights the ground with a
// light of its own. Fewer subdivisions and forks on the weaker tiers (quality.js).

const CLOUDS = 88 // where a bolt comes out of the clouds (clouds.js HEIGHT is their middle)
const LEADER = 0.16 // seconds the stepped leader takes to come down: a real one takes ~0.05 s, too quick to see
const STEPS = 9 // the steps it comes down in
const STROKE_FADE = 0.05 // seconds a stroke's light takes to fall to a third
const AFTERGLOW = 0.3 // seconds the channel's last glow takes to fall to a third
const LINGER = 1.2 // seconds a strike is kept
const CORE = 0.42 // the white core's width, in world units
const GLOW = 12 // the glow's width, in cores
const MAIN = 1 // a segment's kind: the main channel, lit by every stroke
const FORK = 0 // a fork, lit by the first stroke only
const ARC = 2 // an arc along the ground at the strike point

const vertexShader = /* glsl */`
  uniform float shimmer; // a fresh seed for each stroke: the channel quivers a little between strokes
  attribute vec3 finish; // the segment's other end (position is its start)
  attribute vec2 corner; // along the segment (0 at its start, 1 at its finish), and across it (-1 to 1)
  attribute vec4 look; // half the ribbon's width, brightness, when the leader reaches this end (0 to 1), kind
  varying float vAcross;
  varying float vBright;
  varying float vArrive;
  varying float vKind;
  void main() {
    vec3 world = mix( position, finish, corner.x );
    vec4 a = modelViewMatrix * vec4( position, 1.0 );
    vec4 b = modelViewMatrix * vec4( finish, 1.0 );
    vec2 along = b.xy - a.xy;
    vec2 across = normalize( vec2( -along.y, along.x ) + vec2( 1e-6, 0.0 ) );
    vec4 p = mix( a, b, corner.x );
    float quiver = fract( sin( dot( world, vec3( 12.9898, 78.233, 37.719 ) ) + shimmer ) * 43758.5453 ) - 0.5;
    p.xy += across * ( corner.y * look.x + quiver * look.x * 0.12 );
    gl_Position = projectionMatrix * p;
    vAcross = corner.y;
    vBright = look.y;
    vArrive = look.z;
    vKind = look.w;
  }
`

const fragmentShader = /* glsl */`
  uniform float leader; // how far the leader has come, 0 (the clouds) to 1 (the ground)
  uniform float feel; // the leader's own faint light, while it feels its way down
  uniform float stroke; // the main channel's light now (strokes and afterglow)
  uniform float forks; // the forks' light now
  uniform float arcs; // the ground arcs' light now
  uniform float glow; // how much the halo shows (less by day)
  uniform vec3 coreColor;
  uniform vec3 glowColor;
  varying float vAcross;
  varying float vBright;
  varying float vArrive;
  varying float vKind;
  void main() {
    if ( vArrive > leader ) discard; // the leader has not come this far yet
    float d = abs( vAcross );
    float core = 1.0 - smoothstep( 0.04, 0.09, d ); // a hard white thread down the middle
    float inner = exp( -d * d * 45.0 ); // white-hot just around it
    float halo = exp( -d * d * 5.0 ) * ( 1.0 - d ); // and a wide violet-blue glow
    float tip = exp( -( leader - vArrive ) * 14.0 ); // the leader's front is its brightest part
    float lit = vKind > 1.5 ? arcs : vKind > 0.5 ? stroke : forks;
    float l = max( lit, feel * ( 0.3 + 0.7 * tip ) ) * vBright;
    vec3 color = coreColor * ( core + 0.55 * inner ) * l + glowColor * halo * l * glow * 0.6;
    gl_FragColor = vec4( color, 1.0 );
  }
`

// mulberry32: the same seed makes the same bolt for every viewer.
function randomFrom(seed) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function seedOf(id) {
  const n = Number(id)
  if (Number.isFinite(n)) return Math.floor(n) * 2654435761
  let h = 2166136261
  for (const c of String(id)) h = Math.imul(h ^ c.charCodeAt(0), 16777619)
  return h
}

// A jagged path from a to b by midpoint displacement: `depth` times, every segment's midpoint is pushed sideways by up
// to `rough` of the segment's length, in a random direction square to it. a first, b last.
export function jag(rand, a, b, depth, rough) {
  let points = [a.clone(), b.clone()]
  let bend = rough
  const dir = new THREE.Vector3()
  const side = new THREE.Vector3()
  for (let level = 0; level < depth; level++) {
    const next = [points[0]]
    for (let i = 1; i < points.length; i++) {
      const p = points[i - 1]
      const q = points[i]
      dir.subVectors(q, p)
      const length = dir.length() || 1
      dir.divideScalar(length)
      side.set(rand() - 0.5, rand() - 0.5, rand() - 0.5)
      side.addScaledVector(dir, -side.dot(dir)).normalize().multiplyScalar((rand() * 2 - 1) * bend * length)
      next.push(p.clone().add(q).multiplyScalar(0.5).add(side), q)
    }
    points = next
    bend *= 0.88 // big kinks, finer ones a little gentler: a channel, not a scribble
  }
  return points
}

// The whole strike, as segments { a, b, width, bright, arriveA, arriveB, kind }: the main channel from the clouds
// to `ground`, forks (and their forks) thrown off downwards, and arcs along the ground. `arrive` is when the leader
// reaches each end, 0 to 1 over the main channel's length; forks grow at the same pace from where they leave it.
export function boltOf(seed, ground, detail = {}) {
  const rand = randomFrom(seed)
  const depth = detail.depth ?? 7
  const segments = []
  const add = (points, startArrive, scale, width, bright, kind) => {
    let run = 0
    for (let i = 1; i < points.length; i++) {
      const step = points[i].distanceTo(points[i - 1])
      segments.push({ a: points[i - 1], b: points[i], width, bright, kind,
        arriveA: startArrive + run * scale, arriveB: startArrive + (run + step) * scale })
      run += step
    }
  }
  const angle = rand() * Math.PI * 2
  const out = 10 + rand() * 18 // bolts lean: they leave the clouds off to one side
  const top = new THREE.Vector3(ground.x + Math.cos(angle) * out, CLOUDS, ground.z + Math.sin(angle) * out)
  const main = jag(rand, top, ground, depth, 0.2)
  let total = 0
  for (let i = 1; i < main.length; i++) total += main[i].distanceTo(main[i - 1])
  add(main, 0, 1 / total, CORE * GLOW, 1, MAIN)

  const arrival = [0] // the leader's arrival at each main point
  for (let i = 1; i < main.length; i++) arrival.push(arrival[i - 1] + main[i].distanceTo(main[i - 1]) / total)
  const fork = (points, arrive, from, length, level, bright, width) => {
    const i = Math.min(points.length - 2, Math.floor(from * (points.length - 1)))
    const start = points[i]
    const along = points[i + 1].clone().sub(start).normalize()
    const sideways = new THREE.Vector3(rand() - 0.5, 0, rand() - 0.5).normalize()
    const dir = along.clone().addScaledVector(sideways, 0.6 + rand() * 0.7) // 30 to 55 degrees off the channel
    dir.y = Math.min(dir.y, -0.25) // and always downwards
    dir.normalize()
    const end = start.clone().addScaledVector(dir, length)
    end.y = Math.max(end.y, ground.y + 2)
    const path = jag(rand, start, end, Math.max(2, depth - 2 - level), 0.26)
    add(path, arrive[i], 1 / total, CORE * GLOW * width, bright, FORK)
    if (level < (detail.forkDepth ?? 1)) {
      const kids = rand() < 0.6 ? 1 : 2
      const own = [arrive[i]]
      for (let k = 1; k < path.length; k++) own.push(own[k - 1] + path[k].distanceTo(path[k - 1]) / total)
      for (let k = 0; k < kids; k++) {
        fork(path, own, 0.2 + rand() * 0.5, length * (0.35 + rand() * 0.25), level + 1, bright * 0.6, width * 0.7)
      }
    }
  }
  const forks = detail.forks ?? 5
  for (let f = 0; f < forks; f++) {
    const from = 0.08 + (f + rand()) * (0.62 / forks) // spread down the upper two thirds
    const below = main[0].y - ground.y
    fork(main, arrival, from, (1 - from) * below * (0.35 + rand() * 0.3), 0, 0.45 + rand() * 0.25, 0.6)
  }

  // A glare where it strikes: a short, very wide ribbon standing on the ground, lit with the strokes.
  const glare = ground.clone().add(new THREE.Vector3(0, 1.4, 0))
  add([ground.clone(), glare], 1, 0, CORE * GLOW * 2.2, 0.5, ARC)
  const arcs = detail.arcs ?? 5
  for (let k = 0; k < arcs; k++) { // the strike crackles out along the ground
    const a = (k / arcs + rand() * 0.15) * Math.PI * 2
    const reach = 1.8 + rand() * 2.8
    const from = ground.clone().add(new THREE.Vector3(0, 0.15, 0))
    const to = ground.clone().add(new THREE.Vector3(Math.cos(a) * reach, 0.1 + rand() * 0.4, Math.sin(a) * reach))
    add(jag(rand, from, to, 3, 0.35), 1, 0, CORE * GLOW * 0.35, 0.8, ARC)
  }
  return segments
}

// The strike's rhythm: the return stroke when the leader touches, then one to three restrikes, each weaker.
export function strokesOf(seed) {
  const rand = randomFrom(seed ^ 0x9e3779b9)
  const strokes = [{ at: LEADER, peak: 1 }]
  const more = 1 + Math.floor(rand() * 3)
  let at = LEADER
  for (let i = 0; i < more; i++) {
    at += 0.07 + rand() * 0.06
    strokes.push({ at, peak: 0.8 - i * 0.2 })
  }
  return strokes
}

// How the strike is lit `age` seconds in: where the leader is and its own faint light, the main channel's, the
// forks', the ground arcs', and the flash it throws on the island (0 to 1).
export function lightAt(strokes, age) {
  if (age < LEADER) {
    const step = Math.ceil((age / LEADER) * STEPS)
    return { leader: step / STEPS, feel: 0.22 + 0.12 * ((step * 7) % 3) / 2, main: 0, forks: 0, arcs: 0, flash: 0 }
  }
  let main = 0
  let flash = 0
  for (const s of strokes) {
    if (age < s.at) continue
    const k = s.peak * Math.exp(-(age - s.at) / STROKE_FADE)
    main += k
    flash = Math.max(flash, k)
  }
  const since = age - LEADER
  main = Math.min(1.25, main + 0.16 * Math.exp(-since / AFTERGLOW))
  const forks = Math.exp(-since / 0.07) + 0.1 * Math.max(0, main - 0.2) // the first stroke, a little of the rest
  return { leader: 1, feel: 0, main, forks: Math.min(1, forks), arcs: Math.min(1, main * 1.2), flash: Math.min(1, flash) }
}

function geometryOf(segments) {
  const n = segments.length
  const start = new Float32Array(n * 12)
  const finish = new Float32Array(n * 12)
  const corner = new Float32Array(n * 8)
  const look = new Float32Array(n * 16)
  const index = new Uint32Array(n * 6)
  segments.forEach((s, i) => {
    for (let v = 0; v < 4; v++) {
      const along = v >> 1
      const k = i * 4 + v
      s.a.toArray(start, k * 3)
      s.b.toArray(finish, k * 3)
      corner[k * 2] = along
      corner[k * 2 + 1] = v & 1 ? 1 : -1
      look.set([s.width / 2, s.bright, along ? s.arriveB : s.arriveA, s.kind], k * 4)
    }
    index.set([i * 4, i * 4 + 1, i * 4 + 2, i * 4 + 2, i * 4 + 1, i * 4 + 3], i * 6)
  })
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(start, 3))
  geometry.setAttribute('finish', new THREE.BufferAttribute(finish, 3))
  geometry.setAttribute('corner', new THREE.BufferAttribute(corner, 2))
  geometry.setAttribute('look', new THREE.BufferAttribute(look, 4))
  geometry.setIndex(new THREE.BufferAttribute(index, 1))
  return geometry
}

export function createLightning(scene, tier) {
  const detail = { depth: tier.lightningDepth ?? 7, forks: tier.lightningForks ?? 5, forkDepth: tier.lightningForkDepth ?? 1,
    arcs: tier.lightningArcs ?? 5 }
  // The flash's light, there from the start (a light added later would recompile every material), dark until a strike.
  const light = tier.lightningLight ? new THREE.PointLight(0xc9d4ff, 0, 90, 1.4) : null
  if (light) scene.add(light)
  const seen = new Set() // markers already played
  const strikes = []
  let now = 0
  let flashNow = 0
  let nightNow = 0
  const dir = new THREE.Vector3()

  function strike(x, y, z, seed) {
    const ground = new THREE.Vector3(x, y, z)
    const material = new THREE.ShaderMaterial({
      name: 'GodlingLightning',
      uniforms: {
        leader: { value: 0 }, feel: { value: 0 }, stroke: { value: 0 }, forks: { value: 0 }, arcs: { value: 0 },
        glow: { value: 1 }, shimmer: { value: 0 },
        coreColor: { value: new THREE.Color(1, 1, 1) },
        glowColor: { value: new THREE.Color(0.55, 0.6, 1) },
      },
      vertexShader,
      fragmentShader,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending, // added light: the glow shows over a dark sky, the core burns white by day
      toneMapped: false,
      fog: false,
    })
    const mesh = new THREE.Mesh(geometryOf(boltOf(seed, ground, detail)), material)
    mesh.frustumCulled = false // the ribbons are made in the shader: the bounding box knows nothing of them
    mesh.renderOrder = 5
    scene.add(mesh)
    strikes.push({ ground, born: now, strokes: strokesOf(seed), mesh, material, stroke: -1 })
  }

  function forget(s) {
    scene.remove(s.mesh)
    s.mesh.geometry.dispose()
    s.material.dispose()
  }

  return {
    strike,
    // Each frame, for each entity: lightning markers. Before the hidden check: the marker is never drawn.
    watch(entity) {
      if (entity.render?.role !== 'SkyFlash' || seen.has(entity.id)) return
      seen.add(entity.id)
      const [x, y, z] = entity.position
      strike(x, y - (entity.size?.[1] ?? 0) / 2, z, seedOf(entity.id)) // its foot is the strike point
    },
    // Forget what is gone.
    prune(activeIds) {
      for (const id of seen) if (!activeIds.has(id)) seen.delete(id)
    },
    // time: the renderer's clock (seconds); daylight 0 to 1. Returns how much the ambient light flares.
    update({ time, daylight = 1 }) {
      now = time
      flashNow = 0
      let brightest = null
      for (let i = strikes.length - 1; i >= 0; i--) {
        const s = strikes[i]
        const age = now - s.born
        if (age > LINGER) {
          forget(s)
          strikes.splice(i, 1)
          continue
        }
        const lit = lightAt(s.strokes, age)
        const u = s.material.uniforms
        u.leader.value = lit.leader
        u.feel.value = lit.feel
        u.stroke.value = lit.main
        u.forks.value = lit.forks
        u.arcs.value = lit.arcs
        u.glow.value = 1 - 0.45 * daylight // added light washes out by day: the core carries it
        const stroke = s.strokes.filter((k) => age >= k.at).length
        if (stroke !== s.stroke) { // each stroke quivers the channel anew
          s.stroke = stroke
          u.shimmer.value = stroke * 17.31
        }
        if (lit.flash > flashNow) {
          flashNow = lit.flash
          brightest = s
        }
      }
      nightNow = 1 - daylight
      if (light) {
        light.intensity = 0
        if (brightest) {
          light.position.set(brightest.ground.x, brightest.ground.y + 6, brightest.ground.z)
          light.intensity = 900 * flashNow
        }
      }
      return flashNow * (0.15 + 1.1 * nightNow) // the island lights up, most of all by night
    },
    // How much the whole picture brightens now (multiplies the renderer's exposure): the sky and clouds flash too.
    exposure: () => 1 + flashNow * (0.35 + 1.6 * nightNow),
    // How hard the camera at `position` is jolted now (0 to 1): the thunderclap of a strike close by.
    jolt(position) {
      let k = 0
      for (const s of strikes) {
        const age = now - s.born - LEADER
        if (age < 0 || age > 1) continue
        const near = 1 / (1 + position.distanceToSquared(dir.copy(s.ground)) / 900)
        k = Math.max(k, 0.35 * Math.exp(-age * 4) * near)
      }
      return k
    },
    info: () => ({
      time: Number(now.toFixed(3)),
      strikes: strikes.length,
      segments: strikes.reduce((n, s) => n + s.mesh.geometry.index.count / 6, 0),
      flash: Number(flashNow.toFixed(3)),
      light: light ? Number(light.intensity.toFixed(1)) : null,
    }),
    dispose() {
      for (const s of strikes) forget(s)
      strikes.length = 0
      seen.clear()
      if (light) scene.remove(light)
    },
  }
}
