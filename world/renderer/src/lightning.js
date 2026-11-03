import * as THREE from 'three'

// Lightning: the Lightning power, and the storms of heavy rain. The world marks a strike with a short-lived part,
// SkyBolt_<n> (RenderRole "SkyFlash", with SkyId n and the strike point in StrikeX/Y/Z; older worlds give only a thin
// post standing on it), and the strike plays once, when the marker is first seen, as real lightning goes and as games
// draw it:
// - the stepped leader: a faint, forked channel feels its way down from the clouds in steps,
// - the return stroke: the moment it touches, the whole channel blazes white, forks and all, and the island flashes,
// - restrikes: one to three more strokes down the main channel only, each weaker (real ones come 20-50 ms apart; these
//   are slowed to 70-130 ms, which a screen can show as the flicker the eye sees),
// - the afterglow, fading, and short arcs crackling along the ground where it struck.
// The bolt is cut by midpoint displacement from the clouds to the strike point, with forks thrown off downwards that
// fork again. It is drawn as camera-facing ribbons, all in one draw call: a white core inside a violet-blue glow, as
// added light. Each strike's shape and rhythm come from its SkyId, each part of the bolt (the channel, every fork,
// every arc) from a random stream of its own, always cut at full detail and then thinned: every viewer, on any tier,
// and the island's past see the same bolt, the weaker tiers with fewer small kinks and fewer of the small forks. The
// flash raises the exposure (the sky and clouds too), lifts the ambient light by night, and, given the meteor's flash
// light (blast.js; one light for both, on the tiers that have it), lights the ground.

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
const DEPTH = 7 // the channel is always cut this fine, then thinned for the weaker tiers
const FORKS = 5 // forks always worked out, of which a tier draws some
const ARCS = 5 // the same for the ground arcs
const LIGHT = 900 // the flash light's strength at a stroke's peak

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
    // The leader has not come this far yet. With some slack: an arrival of exactly 1 (the arcs, the channel's foot)
    // may be interpolated a hair above 1.
    if ( vArrive > leader + 0.001 ) discard;
    float d = abs( vAcross );
    float core = 1.0 - smoothstep( 0.04, 0.09, d ); // a hard white thread down the middle
    float inner = exp( -d * d * 45.0 ); // white-hot just around it
    float halo = exp( -d * d * 5.0 ) * ( 1.0 - d ); // and a wide violet-blue glow
    float tip = exp( -max( leader - vArrive, 0.0 ) * 14.0 ); // the leader's front is its brightest part
    float lit = vKind > 1.5 ? arcs : vKind > 0.5 ? stroke : forks;
    float l = max( lit, feel * ( 0.3 + 0.7 * tip ) ) * vBright;
    vec3 color = coreColor * ( core + 0.55 * inner ) * l + glowColor * halo * l * glow * 0.6;
    gl_FragColor = vec4( color, 1.0 );
  }
`

// mulberry32: the same seed makes the same numbers for every viewer.
function randomFrom(seed) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// A strike's seed from its SkyId (or, from older worlds, its entity id): FNV-1a over its digits, in 32-bit integer
// arithmetic, so a large id keeps all its entropy.
export function seedOf(id) {
  let h = 2166136261
  for (const c of String(id)) h = Math.imul(h ^ c.charCodeAt(0), 16777619)
  return h >>> 0
}

// The random stream of one part of a strike (the channel, a fork, an arc): the same part draws the same numbers
// whatever else the tier draws.
function streamOf(seed, part) {
  return randomFrom(Math.imul(seed ^ Math.imul(part + 1, 0x9e3779b9), 0x85ebca6b))
}

// A jagged path from a to b by midpoint displacement: `depth` times, every segment's midpoint is pushed sideways by up
// to `rough` of the segment's length (a little less at each finer level), in a random direction square to it. Points
// of a coarser level never move, so every 2^k-th point of the path is the path cut k levels coarser (thin).
function jag(rand, a, b, depth, rough) {
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

// Every 2^coarser-th of a list: a path cut `coarser` levels less finely.
const thin = (list, coarser) => list.filter((_, i) => i % (1 << Math.max(0, coarser)) === 0)

// The leader's arrival at each point of a path that leaves at arrival `from`, at the channel's pace (`total` is the
// channel's length): never past 1, when it touches the ground and everything still growing is lit by the stroke.
function arrivals(points, from, total) {
  const out = [from]
  for (let i = 1; i < points.length; i++) out.push(out[i - 1] + points[i].distanceTo(points[i - 1]) / total)
  return out.map((a) => Math.min(1, a))
}

// Which of `all` parts a tier with room for `n` draws: spread evenly, the same ones on every tier that draws them.
const chosen = (n, all) => Array.from({ length: Math.min(n, all) }, (_, i) => Math.floor(((i + 0.5) * all) / Math.min(n, all)))

// The whole strike, as segments { a, b, width, bright, arriveA, arriveB, kind }: the main channel from the clouds
// to `ground`, forks (and their forks) thrown off downwards, and arcs along the ground. `arrive` is when the leader
// reaches each end, 0 to 1 over the main channel's length; forks grow at the same pace from where they leave it.
export function boltOf(seed, ground, detail = {}) {
  const depth = Math.min(DEPTH, detail.depth ?? DEPTH)
  const segments = []
  const add = (points, arrive, width, bright, kind) => {
    for (let i = 1; i < points.length; i++) {
      segments.push({ a: points[i - 1], b: points[i], width, bright, kind, arriveA: arrive[i - 1], arriveB: arrive[i] })
    }
  }
  const channel = streamOf(seed, 0)
  const angle = channel() * Math.PI * 2
  const out = 10 + channel() * 18 // bolts lean: they leave the clouds off to one side
  const top = new THREE.Vector3(ground.x + Math.cos(angle) * out, CLOUDS, ground.z + Math.sin(angle) * out)
  const main = jag(channel, top, ground, DEPTH, 0.2)
  let total = 0
  for (let i = 1; i < main.length; i++) total += main[i].distanceTo(main[i - 1])
  const mainArrive = arrivals(main, 0, total)
  add(thin(main, DEPTH - depth), thin(mainArrive, DEPTH - depth), CORE * GLOW, 1, MAIN)

  // A fork off `points` (cut at full detail, with `arrive` its arrivals), `at` of the way along: its own stream decides
  // where it leaves, its direction and its kinks, and its forks are streams of their own.
  const forkOff = (part, points, arrive, at, length, level, bright, width) => {
    const rand = streamOf(seed, part)
    const i = Math.min(points.length - 2, Math.floor(at * (points.length - 1)))
    const start = points[i]
    const along = points[i + 1].clone().sub(start).normalize()
    const sideways = new THREE.Vector3(rand() - 0.5, 0, rand() - 0.5).normalize()
    const dir = along.clone().addScaledVector(sideways, 0.6 + rand() * 0.7) // 30 to 55 degrees off the channel
    dir.y = Math.min(dir.y, -0.25) // and always downwards
    dir.normalize()
    const end = start.clone().addScaledVector(dir, length)
    end.y = Math.max(end.y, ground.y + 2)
    const full = DEPTH - 2 - level
    const path = jag(rand, start, end, full, 0.26)
    const pathArrive = arrivals(path, arrive[i], total)
    const drawn = Math.max(2, depth - 2 - level)
    add(thin(path, full - drawn), thin(pathArrive, full - drawn), CORE * GLOW * width, bright, FORK)
    if (level < (detail.forkDepth ?? 1)) {
      for (let k = 0; k < 2; k++) {
        const kid = streamOf(seed, part * 4 + k + 100)
        if (k > 0 && kid() > 0.4) continue // a second fork, sometimes
        forkOff(part * 4 + k + 100, path, pathArrive, 0.2 + kid() * 0.5, length * (0.35 + kid() * 0.25), level + 1,
          bright * 0.6, width * 0.7)
      }
    }
  }
  const below = main[0].y - ground.y
  for (const f of chosen(detail.forks ?? FORKS, FORKS)) {
    const rand = streamOf(seed, 10 + f)
    const at = 0.08 + (f + rand()) * (0.62 / FORKS) // spread down the upper two thirds
    forkOff(20 + f, main, mainArrive, at, (1 - at) * below * (0.35 + rand() * 0.3), 0, 0.45 + rand() * 0.25, 0.6)
  }

  // A glare where it strikes: a short, very wide ribbon standing on the ground, lit with the strokes.
  add([ground.clone(), ground.clone().add(new THREE.Vector3(0, 1.4, 0))], [1, 1], CORE * GLOW * 2.2, 0.5, ARC)
  for (const k of chosen(detail.arcs ?? ARCS, ARCS)) { // the strike crackles out along the ground
    const rand = streamOf(seed, 200 + k)
    const a = (k / ARCS + rand() * 0.15) * Math.PI * 2
    const reach = 1.8 + rand() * 2.8
    const from = ground.clone().add(new THREE.Vector3(0, 0.15, 0))
    const to = ground.clone().add(new THREE.Vector3(Math.cos(a) * reach, 0.1 + rand() * 0.4, Math.sin(a) * reach))
    const path = jag(rand, from, to, 3, 0.35)
    add(path, path.map(() => 1), CORE * GLOW * 0.35, 0.8, ARC)
  }
  return segments
}

// The strike's rhythm: the return stroke when the leader touches, then one to three restrikes, each weaker.
export function strokesOf(seed) {
  const rand = streamOf(seed, 1)
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
    const flicker = [0, 0.5, 1][(step * 7) % 3] // the leader's light wavers from step to step
    return { leader: step / STEPS, feel: 0.22 + 0.12 * flicker, main: 0, forks: 0, arcs: 0, flash: 0 }
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

function boltMaterial() {
  return new THREE.ShaderMaterial({
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
}

// How much of a bolt a quality tier draws (quality.js).
export const detailOf = (tier) => ({ depth: tier.lightningDepth ?? DEPTH, forks: tier.lightningForks ?? FORKS,
  forkDepth: tier.lightningForkDepth ?? 1, arcs: tier.lightningArcs ?? ARCS })

// `light`: the meteor's flash light (blast.js), shared: a strike lights the ground with it, after the blast has set it
// for the frame, and only when brighter. Without one (the low tier), the exposure and the ambient light still flash.
export function createLightning(scene, tier, { light = null } = {}) {
  const detail = detailOf(tier)
  // Materials are kept, never disposed, so the shader is compiled once: a strike never waits on a compile. The first
  // is drawn once at the start on an empty ribbon (nothing of it shows), to compile it before any strike.
  const pool = [boltMaterial()]
  const warm = new THREE.Mesh(geometryOf([{ a: new THREE.Vector3(), b: new THREE.Vector3(), width: 0, bright: 0,
    arriveA: 2, arriveB: 2, kind: MAIN }]), pool[0])
  warm.name = 'GodlingLightningWarm'
  warm.frustumCulled = false
  let warmed = false
  warm.onAfterRender = () => { warmed = true } // taken away on the next update: not while the scene is drawn
  scene.add(warm)
  const seen = new Set() // markers already played
  const strikes = []
  let now = 0
  let flashNow = 0
  let nightNow = 0
  let lightSet = -1 // the intensity this module last gave the light, to put it out after
  const dir = new THREE.Vector3()

  function strike(x, y, z, seed) {
    const ground = new THREE.Vector3(x, y, z)
    const material = pool.pop() ?? boltMaterial()
    const mesh = new THREE.Mesh(geometryOf(boltOf(seed, ground, detail)), material)
    mesh.name = 'GodlingLightning'
    mesh.frustumCulled = false // the ribbons are made in the shader: the bounding box knows nothing of them
    mesh.renderOrder = 5
    scene.add(mesh)
    strikes.push({ ground, born: now, strokes: strokesOf(seed), mesh, material, stroke: -1 })
  }

  function forget(s) {
    scene.remove(s.mesh)
    s.mesh.geometry.dispose()
    pool.push(s.material) // kept for the next strike
  }

  return {
    strike,
    // Each frame, for each entity: lightning markers. Before the hidden check: the marker is never drawn. The strike
    // point is the marker's StrikeX/Y/Z; from an older world, the foot of the post it stands as.
    watch(entity) {
      if (entity.render?.role !== 'SkyFlash' || seen.has(entity.id)) return
      seen.add(entity.id)
      const at = entity.attributes || {}
      const [x, y, z] = entity.position
      const marked = [at.StrikeX, at.StrikeY, at.StrikeZ].every(Number.isFinite)
      if (marked) strike(at.StrikeX, at.StrikeY, at.StrikeZ, seedOf(at.SkyId ?? entity.id))
      else strike(x, y - (entity.size?.[1] ?? 0) / 2, z, seedOf(at.SkyId ?? entity.id))
    },
    // Forget what is gone.
    prune(activeIds) {
      for (const id of seen) if (!activeIds.has(id)) seen.delete(id)
    },
    // time: the renderer's clock (seconds); daylight 0 to 1. Returns how much the ambient light flares.
    update({ time, daylight = 1 }) {
      now = time
      if (warmed && warm.parent) {
        scene.remove(warm)
        warm.geometry.dispose()
      }
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
        const ours = light.intensity === lightSet // still as this left it: nothing else (a blast) has set it since
        const want = LIGHT * flashNow
        if (brightest && (ours || want > light.intensity)) { // the brighter flash has the light
          light.position.set(brightest.ground.x, brightest.ground.y + 6, brightest.ground.z)
          light.color.setRGB(0.79, 0.83, 1)
          light.intensity = want
          lightSet = want
        } else if (ours) { // the strike is over: put it out
          light.intensity = 0
          lightSet = 0
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
      materials: pool.length + strikes.length,
      flash: Number(flashNow.toFixed(3)),
      light: light ? Number(light.intensity.toFixed(1)) : null,
    }),
    dispose() {
      for (const s of strikes) forget(s)
      strikes.length = 0
      seen.clear()
      if (warm.parent) {
        scene.remove(warm)
        warm.geometry.dispose()
      }
      for (const material of pool) material.dispose()
      pool.length = 0
      flashNow = 0
    },
  }
}
