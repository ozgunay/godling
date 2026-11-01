// Bundles the renderer with three.js inside it, so neither the viewer nor Godling's camera needs a CDN.
// `clawblox run` calls this through `npm run build`.
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const here = (path) => new URL(path, import.meta.url)
const outfile = 'dist/renderer.bundle.js'

if (!existsSync(here('./node_modules/three/package.json'))) {
  // Run copies (run_godling.py) leave node_modules out; they use the committed bundle as it is.
  if (existsSync(here(outfile)) && readFileSync(here(outfile), 'utf8').includes('createRenderer')) {
    console.log(`renderer: dependencies not installed, using the committed ${outfile}`)
    process.exit(0)
  }
  console.error('renderer: run `npm install` in world/renderer first')
  process.exit(1)
}

const esbuild = await import('esbuild')
await esbuild.build({
  absWorkingDir: fileURLToPath(new URL('.', import.meta.url)),
  entryPoints: ['src/index.js'],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: 'es2020',
  minify: true,
  sourcemap: true,
  legalComments: 'eof',
  logLevel: 'warning',
})
console.log(`renderer: built ${outfile}`)
