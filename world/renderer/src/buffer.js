// The island between two updates (ADR-017). States come ten a second through the relay, 31 straight from the world,
// and faster still in a quick replay; the renderer draws a moment just past, between the two states either side of it.
// In place of Clawblox's snapshot buffer, which eased positions only and showed everything else from the newer state:
// - positions are eased and rotations turned (slerp) between the two states, so a turn is smooth at any rate;
// - everything else (what is there, attributes, a character's state) is the older state's until the moment reaches
//   the newer one, so a blast shows when the falling stone is drawn arriving, not a whole gap before;
// - the delay follows the stream: two of its gaps, at least 100 ms (200 at ten a second, 100 straight from the world
//   or in a fast replay), changing a little at a time, so one late update does not leave things standing still;
// - states are kept for a time, not by count, so a fast replay still has two to draw between.

const MIN_DELAY_MS = 100
const MAX_DELAY_MS = 600
const FIRST_DELAY_MS = 200 // until a few gaps are known: the relay's ten a second
const STEP_MS = 5 // the delay moves at most this much a state, towards two gaps
const GAPS_KEPT = 16
const KEEP_MS = MAX_DELAY_MS + 200 // states older than this behind the newest are let go (two always stay)
const MOST_KEPT = 256
const MAX_TICK_GAP = 120 // a jump in the world's tick this big is a new world: start over

export function createStateBuffer({ delayMs } = {}) {
  const fixed = Number.isFinite(delayMs) ? Math.max(0, delayMs) : null
  let delay = fixed ?? FIRST_DELAY_MS
  const snapshots = [] // { state, nowMs, byId }
  const gaps = []
  let lastPushMs = null

  function median() {
    if (!gaps.length) return null
    const sorted = [...gaps].sort((a, b) => a - b)
    return sorted[sorted.length >> 1]
  }

  function follow() {
    if (fixed != null || gaps.length < 4) return
    // To the nearest 10 ms, so the stream's small wobbles do not move it.
    const target = Math.round(Math.min(MAX_DELAY_MS, Math.max(MIN_DELAY_MS, 2 * median())) / 10) * 10
    delay += Math.max(-STEP_MS, Math.min(STEP_MS, target - delay))
  }

  function push(state, nowMs = performance.now()) {
    const last = snapshots.length ? snapshots[snapshots.length - 1].state : null
    if (Number.isFinite(Number(last?.tick)) && Number.isFinite(Number(state?.tick)) &&
        Math.abs(Number(state.tick) - Number(last.tick)) > MAX_TICK_GAP) clear()
    if (lastPushMs != null && nowMs > lastPushMs) {
      gaps.push(nowMs - lastPushMs)
      if (gaps.length > GAPS_KEPT) gaps.shift()
    }
    lastPushMs = nowMs
    follow()
    snapshots.push({ state, nowMs, byId: null })
    while (snapshots.length > 2 && (snapshots[1].nowMs < nowMs - KEEP_MS || snapshots.length > MOST_KEPT)) snapshots.shift()
  }

  function interpolated(nowMs = performance.now()) {
    if (!snapshots.length) return null
    const target = nowMs - delay
    const newest = snapshots[snapshots.length - 1]
    if (target >= newest.nowMs) return newest.state
    if (snapshots.length === 1 || target <= snapshots[0].nowMs) return snapshots[0].state
    for (let i = snapshots.length - 2; i >= 0; i--) {
      const a = snapshots[i]
      if (a.nowMs <= target) return between(a, snapshots[i + 1], (target - a.nowMs) / Math.max(1, snapshots[i + 1].nowMs - a.nowMs))
    }
    return snapshots[0].state
  }

  function clear() {
    snapshots.length = 0
    lastPushMs = null // the gap to the next state is not the stream's
  }

  return {
    push,
    interpolated,
    clear,
    latest: () => (snapshots.length ? snapshots[snapshots.length - 1].state : null),
    previous: () => (snapshots.length > 1 ? snapshots[snapshots.length - 2].state : null),
    forEachRecent(fn) {
      for (let i = snapshots.length - 1; i >= 0; i--) fn(snapshots[i].state, i)
    },
    size: () => snapshots.length,
    delayMs: () => delay,
    gapMs: () => median(),
  }
}

// The older state, with every place eased and every rotation turned towards the newer state's, t of the way.
function between(a, b, t) {
  const older = a.state
  const newer = b.state
  if (t <= 0 || older === newer) return older
  if (t >= 1) return newer
  const players = Array.isArray(older?.players) ? older.players.map((p) => {
    const q = Array.isArray(newer?.players) ? newer.players.find((n) => n && n.id === p?.id) : null
    return q && q !== p && Array.isArray(p.position) && Array.isArray(q.position)
      ? { ...p, position: lerp3(p.position, q.position, t) }
      : p
  }) : older?.players
  const byId = idsOf(b)
  const entities = Array.isArray(older?.entities) ? older.entities.map((e) => {
    const f = e && byId.get(e.id)
    // The page keeps an unchanged entity as the same object from one state to the next.
    if (!f || f === e) return e
    const position = Array.isArray(e.position) && Array.isArray(f.position) ? lerp3(e.position, f.position, t) : e.position
    // The world leaves an unturned thing's rotation out: the identity.
    const from = isMatrix(e.rotation) ? e.rotation : null
    const to = isMatrix(f.rotation) ? f.rotation : null
    const rotation = from || to ? turn(from || IDENTITY, to || IDENTITY, t) : e.rotation
    return position === e.position && rotation === e.rotation ? e : { ...e, position, rotation }
  }) : older?.entities
  return { ...older, players, entities }
}

function idsOf(snapshot) {
  if (!snapshot.byId) {
    snapshot.byId = new Map()
    for (const e of snapshot.state?.entities || []) if (e && e.id != null) snapshot.byId.set(e.id, e)
  }
  return snapshot.byId
}

const IDENTITY = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
const lerp3 = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]
const isMatrix = (m) => Array.isArray(m) && m.length === 3 && m.every((row) => Array.isArray(row) && row.length === 3)

// A rotation (3x3, rows) t of the way from a to b, the short way round.
export function turn(a, b, t) {
  if (a.every((row, i) => row.every((v, j) => v === b[i][j]))) return a
  const p = quaternionOf(a)
  const q = quaternionOf(b)
  let dot = p[0] * q[0] + p[1] * q[1] + p[2] * q[2] + p[3] * q[3]
  if (dot < 0) {
    for (let i = 0; i < 4; i++) q[i] = -q[i]
    dot = -dot
  }
  let wp = 1 - t
  let wq = t
  if (dot < 0.9995) {
    const angle = Math.acos(dot)
    const sin = Math.sin(angle)
    wp = Math.sin((1 - t) * angle) / sin
    wq = Math.sin(t * angle) / sin
  }
  const r = [0, 1, 2, 3].map((i) => wp * p[i] + wq * q[i])
  return matrixOf(r)
}

// [x, y, z, w], unit length, from a rotation matrix given as rows (as three.js does from its elements).
function quaternionOf(m) {
  const [[m00, m01, m02], [m10, m11, m12], [m20, m21, m22]] = m
  const trace = m00 + m11 + m22
  let x, y, z, w
  if (trace > 0) {
    const s = 0.5 / Math.sqrt(trace + 1)
    w = 0.25 / s
    x = (m21 - m12) * s
    y = (m02 - m20) * s
    z = (m10 - m01) * s
  } else if (m00 > m11 && m00 > m22) {
    const s = 2 * Math.sqrt(1 + m00 - m11 - m22)
    w = (m21 - m12) / s
    x = 0.25 * s
    y = (m01 + m10) / s
    z = (m02 + m20) / s
  } else if (m11 > m22) {
    const s = 2 * Math.sqrt(1 + m11 - m00 - m22)
    w = (m02 - m20) / s
    x = (m01 + m10) / s
    y = 0.25 * s
    z = (m12 + m21) / s
  } else {
    const s = 2 * Math.sqrt(1 + m22 - m00 - m11)
    w = (m10 - m01) / s
    x = (m02 + m20) / s
    y = (m12 + m21) / s
    z = 0.25 * s
  }
  const n = Math.hypot(x, y, z, w) || 1
  return [x / n, y / n, z / n, w / n]
}

function matrixOf([x, y, z, w]) {
  const n = Math.hypot(x, y, z, w) || 1
  x /= n; y /= n; z /= n; w /= n
  return [
    [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
    [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
    [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
  ]
}
