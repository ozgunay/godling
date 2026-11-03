import { defineConfig } from 'vitest/config'

// The renderer's and the viewer screen's tests (TESTING.md). WebGL itself is not here: test/gl.js stands in for
// three.js's WebGLRenderer; everything else (the scene, geometry, shader source, maths) is three.js's own.
export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['test/**/*.test.js', '../viewer/test/**/*.test.js'],
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      // Paths are relative to this folder (vitest 5 matches a file in it only so); allowExternal lets the viewer, which
      // lives beside the renderer, in through its "../" paths.
      include: ['src/**/*.js', '../viewer/*.js', '../viewer/prototypes/*.js'],
      exclude: ['**/node_modules/**', '../viewer/test/**'],
      allowExternal: true,
      reporter: ['text', 'lcov', 'json-summary'],
      reportsDirectory: 'coverage',
    },
  },
})
