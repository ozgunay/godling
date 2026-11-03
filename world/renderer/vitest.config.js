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
      // With allowExternal (the viewer lives beside the renderer), files are matched by their absolute paths.
      include: ['**/world/renderer/src/**/*.js', '**/world/viewer/*.js', '**/world/viewer/prototypes/*.js'],
      exclude: ['**/node_modules/**', '**/world/viewer/test/**'],
      allowExternal: true,
      reporter: ['text', 'lcov', 'json-summary'],
      reportsDirectory: 'coverage',
    },
  },
})
