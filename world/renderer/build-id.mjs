// The renderer's build: a hash of what the bundle is made from (every file in src/ and the dependencies' versions).
// build.mjs bakes it into the bundle and writes it to dist/build.json, which the world serves beside the bundle; a page
// that finds another build there reloads (src/freshness.js). The same sources give the same build, so a test can tell
// a committed bundle that was not rebuilt.
import { createHash } from 'node:crypto'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

function filesIn(dir, prefix = '') {
  return readdirSync(dir, { withFileTypes: true })
    .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))
    .flatMap((entry) => (entry.isDirectory()
      ? filesIn(join(dir, entry.name), `${prefix}${entry.name}/`)
      : [[`${prefix}${entry.name}`, join(dir, entry.name)]]))
}

// `root`: world/renderer (this file's folder by default; a test passes its own, as vitest's module URLs are not files).
export function buildId(root = fileURLToPath(new URL('.', import.meta.url))) {
  const hash = createHash('sha256')
  const { dependencies = {} } = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))
  hash.update(JSON.stringify(dependencies))
  for (const [name, path] of filesIn(join(root, 'src'))) {
    // Line endings as committed: a Windows checkout with CRLF must give the same build as the server's.
    hash.update(`\0${name}\0`).update(readFileSync(path, 'utf8').replace(/\r\n/g, '\n'))
  }
  return hash.digest('hex').slice(0, 16)
}
