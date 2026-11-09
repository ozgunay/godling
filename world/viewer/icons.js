// Godling's pixel icons: the island's own things, drawn on small grids and rendered as crisp SVG.
// Every icon gets the same one-pixel dark outline, so the set reads as one hand.

const PALETTE = {
  k: '#15191b', // outline
  s: '#8f979a', S: '#666e71', d: '#454b4e', // island stone, light to dark
  m: '#63b544', M: '#3f8a2c', // moss and palm green
  b: '#9a6434', B: '#6b4220', n: '#4a2c14', t: '#d9b277', y: '#f3d9a4', // wood, bark, end grain
  w: '#ffffff', W: '#d7e0e3', // white, shade
  g: '#f6c945', G: '#c9951c', // halo gold
  r: '#ec4b4f', R: '#a52a2f', // heart
  o: '#ff9a3c', O: '#e2541f', // fire and meteor trail
  c: '#45d6cf', C: '#1e9690', // lagoon teal
  u: '#5aaef5', U: '#2b6fc9', // sea blue
  e: '#5c6366', // empty pip
}

function grid(w, h) {
  return Array.from({ length: h }, () => Array(w).fill('.'))
}

function rect(g, x, y, w, h, c) {
  for (let j = y; j < y + h; j++) for (let i = x; i < x + w; i++) if (g[j] && i >= 0 && i < g[0].length) g[j][i] = c
}

function disc(g, cx, cy, r, c) {
  for (let j = 0; j < g.length; j++) {
    for (let i = 0; i < g[0].length; i++) {
      if ((i - cx) ** 2 + (j - cy) ** 2 <= r * r + 0.4) g[j][i] = c
    }
  }
}

function line(g, x0, y0, x1, y1, c) {
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0)
  const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1
  let err = dx + dy
  for (;;) {
    if (g[y0] && x0 >= 0 && x0 < g[0].length) g[y0][x0] = c
    if (x0 === x1 && y0 === y1) break
    const e2 = 2 * err
    if (e2 >= dy) { err += dy; x0 += sx }
    if (e2 <= dx) { err += dx; y0 += sy }
  }
}

function dots(g, list, c) {
  for (const [x, y] of list) if (g[y] && x >= 0 && x < g[0].length) g[y][x] = c
}

function rows(strings) {
  return strings.map((s) => s.split(''))
}

// The shared stroke: a dark outline around every filled pixel, inside the grid.
function outline(g) {
  const h = g.length, w = g[0].length
  const out = g.map((r) => r.slice())
  for (let j = 0; j < h; j++) {
    for (let i = 0; i < w; i++) {
      if (g[j][i] !== '.') continue
      const near = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => g[j + dy]?.[i + dx] && g[j + dy][i + dx] !== '.')
      if (near) out[j][i] = 'k'
    }
  }
  return out
}

const DRAW = {
  stone() {
    const g = grid(16, 16)
    rect(g, 2, 3, 12, 11, 's')
    rect(g, 2, 3, 12, 3, 'm')
    dots(g, [[3, 6], [6, 6], [7, 6], [11, 6], [12, 7]], 'm')
    dots(g, [[2, 5], [5, 5], [9, 5], [13, 5]], 'M')
    dots(g, [[4, 9], [9, 8], [11, 11], [6, 12], [3, 12]], 'S')
    rect(g, 2, 13, 12, 1, 'S')
    rect(g, 13, 6, 1, 8, 'S')
    return outline(g)
  },
  log() {
    const g = grid(16, 16)
    rect(g, 1, 6, 11, 6, 'b')
    rect(g, 1, 6, 11, 1, 't')
    line(g, 2, 8, 6, 8, 'B'); line(g, 5, 10, 10, 10, 'B'); line(g, 8, 8, 10, 8, 'B')
    disc(g, 12, 9, 3, 't')
    disc(g, 12, 9, 1.4, 'y')
    dots(g, [[12, 9]], 'B')
    return outline(g)
  },
  coconut() {
    const g = grid(16, 16)
    disc(g, 8, 9, 5, 'n')
    disc(g, 7, 8, 3.2, 'B')
    dots(g, [[6, 7], [7, 6]], 'b')
    dots(g, [[7, 11], [10, 10], [9, 12]], 'k')
    rect(g, 8, 2, 1, 2, 'M'); dots(g, [[9, 2], [10, 1], [7, 2], [6, 1]], 'm')
    return outline(g)
  },
  sapling() {
    const g = grid(16, 16)
    rect(g, 3, 13, 10, 2, 't')
    rect(g, 7, 6, 2, 7, 'b')
    disc(g, 5, 6, 2.2, 'm'); disc(g, 11, 5, 2.2, 'm'); disc(g, 8, 3, 2.2, 'M')
    dots(g, [[4, 5], [10, 4], [8, 2]], 'm')
    return outline(g)
  },
  fish() {
    const g = grid(16, 16)
    disc(g, 7, 8, 4, 'u')
    rect(g, 4, 9, 7, 2, 'U')
    dots(g, [[11, 7], [12, 6], [13, 5], [11, 9], [12, 10], [13, 11], [12, 8], [13, 8], [13, 7], [13, 9], [12, 7], [12, 9]], 'U')
    dots(g, [[5, 7]], 'w'); dots(g, [[5, 6]], 'k')
    dots(g, [[2, 12], [4, 13], [9, 14], [12, 13]], 'c')
    return outline(g)
  },
  lightning() {
    return outline(rows([
      '................',
      '.........ggg....',
      '........ggg.....',
      '.......ggg......',
      '......ggg.......',
      '.....gggggggg...',
      '.........ggG....',
      '........ggG.....',
      '.......ggG......',
      '......ggG.......',
      '.....ggG........',
      '....ggG.........',
      '...gG...........',
      '................',
      '................',
      '................',
    ]))
  },
  meteor() {
    const g = grid(16, 16)
    line(g, 1, 1, 7, 7, 'o'); line(g, 2, 1, 8, 7, 'O'); line(g, 1, 2, 7, 8, 'O'); line(g, 4, 1, 8, 5, 'y')
    disc(g, 10, 10, 3.6, 'd')
    dots(g, [[9, 9], [11, 11], [8, 11]], 'S')
    dots(g, [[9, 8], [8, 9]], 'o')
    return outline(g)
  },
  rain() {
    const g = grid(16, 16)
    disc(g, 6, 6, 3, 'W'); disc(g, 10, 5, 3.3, 'w'); rect(g, 3, 6, 11, 3, 'w'); rect(g, 3, 8, 11, 1, 'W')
    line(g, 4, 11, 3, 13, 'u'); line(g, 8, 11, 7, 14, 'u'); line(g, 12, 11, 11, 13, 'u')
    return outline(g)
  },
  quake() {
    const g = grid(16, 16)
    rect(g, 1, 9, 14, 5, 't')
    rect(g, 1, 9, 14, 1, 'm')
    rect(g, 3, 3, 5, 5, 's'); rect(g, 3, 3, 5, 1, 'm')
    rect(g, 9, 4, 4, 4, 'S')
    line(g, 8, 9, 7, 11, 'k'); line(g, 7, 11, 9, 13, 'k')
    dots(g, [[1, 6], [2, 4], [14, 2], [15, 5]], 'W')
    return outline(g)
  },
  wave() {
    const g = grid(16, 16)
    disc(g, 6, 9, 5, 'u'); rect(g, 1, 9, 14, 5, 'u'); disc(g, 8, 6, 3, 'U')
    dots(g, [[4, 5], [5, 4], [6, 4], [7, 4], [3, 6]], 'w')
    rect(g, 1, 12, 14, 1, 'U')
    return outline(g)
  },
  heart() {
    return outline(rows(['.RR.RR.', 'RwrRrrR', 'RrrrrrR', '.RrrrR.', '..RrR..', '...R...']))
  },
  heartHalf() {
    return outline(rows(['.RR.ee.', 'RwrReee', 'RrrReee', '.RrRee.', '..RRe..', '...R...']))
  },
  heartEmpty() {
    return outline(rows(['.ee.ee.', 'eeeeeee', 'eeeeeee', '.eeeee.', '..eee..', '...e...']))
  },
  // The husk is bark brown, not end grain: on the dark dock end grain vanished, and a full coconut looked smaller than
  // an empty one. Coconuts fill from the right (viewer.js drawBody), so a half one keeps its right half.
  food() {
    return outline(rows(['..BBB..', '.BbbbB.', 'BbwwwbB', 'BbwyWbB', '.BbbbB.', '..BBB..']))
  },
  foodHalf() {
    return outline(rows(['..eBB..', '.eebbB.', 'eeewwbB', 'eeeyWbB', '.eebbB.', '..eBB..']))
  },
  foodEmpty() {
    return outline(rows(['..eee..', '.eeeee.', 'eeeeeee', 'eeeeeee', '.eeeee.', '..eee..']))
  },
  sun() {
    const g = grid(12, 12)
    disc(g, 6, 6, 2.6, 'g')
    dots(g, [[6, 0], [6, 1], [6, 11], [6, 10], [0, 6], [1, 6], [11, 6], [10, 6], [2, 2], [9, 2], [2, 9], [9, 9]], 'G')
    return outline(g)
  },
  moon() {
    const g = grid(12, 12)
    disc(g, 6, 6, 4, 'W')
    disc(g, 8, 5, 3.2, '.')
    return outline(g)
  },
  eye() {
    return outline(rows(['....wwww....', '..wwwwwwww..', '.wwwccccwww.', 'wwwcckkccwww', '.wwwccccwww.', '..wwwwwwww..', '....wwww....']))
  },
  wallsUp() { // the building as it stands, roof and all (the walls mode: walls up)
    return outline(rows(['....b....', '...bbb...', '..bbbbb..', '.bbbbbbb.', 'bbbbbbbbb', '.sssssss.', '.sssssss.',
      '.ssSSSss.', '.ssSSSss.']))
  },
  wallsCut() { // the roof off and the walls cut low, Godling showing inside (the walls mode: cutaway)
    return outline(rows(['.........', '.........', '...www...', '...wkw...', '...www...', '.s.www.s.', '.s.....s.',
      '.sssssss.', '.sssssss.']))
  },
  move() {
    return outline(rows(['.....w.....', '....www....', '.....w.....', '..w..w..w..', '.wwwwwwwww.', '..w..w..w..', '.....w.....', '....www....', '.....w.....']))
  },
  coin() {
    const g = grid(10, 10)
    disc(g, 4.5, 4.5, 4, 'g')
    disc(g, 4.5, 4.5, 2.2, 'G')
    dots(g, [[3, 2], [2, 3]], 'y')
    return outline(g)
  },
  godling() {
    const g = grid(12, 12)
    rect(g, 3, 1, 6, 1, 'g'); dots(g, [[2, 2], [9, 2]], 'g'); rect(g, 3, 3, 6, 1, 'G')
    disc(g, 5.5, 7.5, 3.6, 'w')
    dots(g, [[4, 7], [7, 7]], 'k')
    return outline(g)
  },
  sky() {
    return outline(rows(['....g....', '....g....', '...ggg...', 'gggggyggg', '...ggg...', '....g....', '....g....']))
  },
  notice() {
    return outline(rows(['...cc...', '..cwwc..', '..cwwc..', '..cwwc..', '...cc...', '........', '...ww...', '...ww...']))
  },
  lock() {
    return outline(rows(['..ddd..', '.d...d.', '.d...d.', 'ggggggg', 'ggGkGgg', 'gggkggg', 'ggggggg']))
  },
  drop() {
    return outline(rows(['...u...', '..uuu..', '.uuuuu.', 'uuwuuuu', 'uwuuuuu', '.uuuuu.', '..uuu..']))
  },
  cold() {
    return outline(rows(['...w...', '.w.w.w.', '..www..', 'wwwcwww', '..www..', '.w.w.w.', '...w...']))
  },
  play() {
    return outline(rows(['.w.....', '.ww....', '.www...', '.wwww..', '.www...', '.ww....', '.w.....']))
  },
  pause() {
    return outline(rows(['.ww.ww.', '.ww.ww.', '.ww.ww.', '.ww.ww.', '.ww.ww.', '.ww.ww.', '.ww.ww.']))
  },
  back() { // the island's past: a clock hand turning back
    return outline(rows(['..www..', '.w...w.', 'w..w..w', 'ww.w..w', 'w..ww.w', '.w...w.', '..www..']))
  },
  fire() {
    return outline(rows(['...o...', '..oo...', '..ooo.o', '.ooyoo.', '.oyyyo.', '.OoyoO.', '..bbb..']))
  },
  bottle() { // a viewer's feedback, corked in sea glass and drifting off to the makers
    const g = grid(16, 16)
    rect(g, 2, 5, 9, 4, 'c'); rect(g, 3, 4, 7, 1, 'c'); rect(g, 2, 8, 9, 1, 'C'); rect(g, 3, 9, 7, 1, 'C')
    rect(g, 11, 5, 1, 4, 'C'); rect(g, 12, 6, 1, 2, 'c')
    rect(g, 13, 6, 2, 2, 'b'); dots(g, [[13, 7], [14, 7]], 'B')
    rect(g, 3, 5, 5, 1, 'w')
    rect(g, 4, 6, 5, 2, 'y'); dots(g, [[4, 6], [4, 7], [8, 7]], 't')
    dots(g, [[1, 12], [2, 11], [3, 11], [4, 12], [9, 12], [10, 11], [11, 11], [12, 12]], 'u')
    return outline(g)
  },
  bug() {
    const g = grid(11, 12)
    dots(g, [[2, 0], [8, 0], [3, 1], [7, 1]], 'n')
    rect(g, 4, 2, 3, 2, 'n')
    disc(g, 5, 7, 3.6, 'M')
    disc(g, 3.6, 6, 1.2, 'm'); disc(g, 6.4, 6, 1.2, 'm')
    rect(g, 5, 4, 1, 7, 'n')
    dots(g, [[0, 5], [0, 8], [10, 5], [10, 8]], 'n')
    return outline(g)
  },
  question() {
    return outline(rows([
      '.wwwwwwwwww.',
      'wwwwkkkkwwww',
      'wwwkkwwkkwww',
      'wwwwwwwkkwww',
      'wwwwwkkkwwww',
      'wwwwwkkwwwww',
      'wwwwwwwwwwww',
      'wwwwwkkwwwww',
      '.WWWWWWWWWW.',
      '..WWW.......',
      '..WW........',
      '..W.........',
    ]))
  },
  idea() {
    const g = grid(12, 13)
    disc(g, 5.5, 4.5, 4.2, 'g')
    dots(g, [[8, 3], [9, 4], [9, 5], [8, 6], [7, 7], [8, 7]], 'G')
    dots(g, [[3, 2], [4, 1], [2, 3], [2, 4]], 'y')
    dots(g, [[5, 5], [6, 5], [5, 6], [6, 6]], 'o')
    rect(g, 4, 9, 4, 1, 's'); rect(g, 4, 10, 4, 1, 'S'); rect(g, 5, 11, 2, 1, 'd')
    return outline(g)
  },
  think() { // Godling thinking: its thought bubble, as over its head on the island
    const g = grid(14, 14)
    disc(g, 4.6, 5, 2.6, 'w')
    disc(g, 8.4, 4, 3, 'w')
    disc(g, 10.8, 6.4, 2.1, 'w')
    rect(g, 3, 6, 9, 2, 'w')
    rect(g, 3, 8, 9, 1, 'W')
    disc(g, 3, 10.6, 1, 'w')
    dots(g, [[1, 12]], 'w')
    return outline(g)
  },
  speech() { // Godling saying something aloud: a speech balloon, its tail to the speaker (unlike think's bubbles)
    return outline(rows([
      '.wwwwwwwwww.',
      'wwwwwwwwwwww',
      'wwkkwkkwkkww',
      'wwwwwwwwwwww',
      'WWWWWWWWWWWW',
      '.WWWWWWWWWW.',
      '..WW........',
      '..W.........',
    ]))
  },
  more() { // the feed unfolds downwards
    return outline(rows(['.........', '.ww...ww.', '.www.www.', '..wwwww..', '...www...', '....w....', '.........']))
  },
  less() {
    return outline(rows(['.........', '....w....', '...www...', '..wwwww..', '.www.www.', '.ww...ww.', '.........']))
  },
  close() {
    return outline(rows(['ww...ww', 'www.www', '.wwwww.', '..www..', '.wwwww.', 'www.www', 'ww...ww']))
  },
  tick() {
    return outline(rows(['......w', '.....ww', 'w...ww.', 'ww.ww..', '.www...', '..w....']))
  },
  glider() { // a viewer's note, folded into a paper glider
    return outline(rows([
      '................',
      '................',
      '.ww.............',
      '.wwwww..........',
      '..wwwwwww.......',
      '..wwwwwwwwww....',
      '...wwwwwwwwwwww.',
      '...WWWWWWWWWWWw.',
      '..WWWWWWWWWW....',
      '..WWWWWWW.......',
      '.WWWWW..........',
      '.WW.............',
      '................',
      '..u.u...........',
      '................',
      '................',
    ]))
  },
}

const cache = new Map()

// <svg> markup for an icon at `scale` screen pixels per grid pixel. Runs of one colour merge into one rect.
export function icon(name, scale = 3, label = '') {
  const key = `${name}@${scale}`
  if (!cache.has(key)) {
    const g = DRAW[name]()
    const h = g.length, w = g[0].length
    let rects = ''
    for (let j = 0; j < h; j++) {
      let i = 0
      while (i < w) {
        const c = g[j][i]
        let n = 1
        while (i + n < w && g[j][i + n] === c) n++
        if (c !== '.') rects += `<rect x="${i}" y="${j}" width="${n}" height="1" fill="${PALETTE[c]}"/>`
        i += n
      }
    }
    cache.set(key, { w, h, rects })
  }
  const { w, h, rects } = cache.get(key)
  const a11y = label ? `role="img" aria-label="${label}"` : 'aria-hidden="true"'
  return `<svg class="px" width="${w * scale}" height="${h * scale}" viewBox="0 0 ${w} ${h}" shape-rendering="crispEdges" ${a11y}>${rects}</svg>`
}
