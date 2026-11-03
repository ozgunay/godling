// What jsdom lacks for the renderer: a 2D canvas context and WebGL. The 2D context records what is drawn and draws
// nothing; the WebGL renderer is three.js's API without a GPU (it counts renders). Everything else is three.js's own.
import { vi } from 'vitest'

export function fake2d(canvas) {
  const calls = []
  const gradient = { addColorStop: () => {} }
  const target = { canvas, calls, fillStyle: '', strokeStyle: '', lineWidth: 1, font: '', textAlign: '', textBaseline: '', lineCap: '' }
  return new Proxy(target, {
    get(obj, name) {
      if (name in obj) return obj[name]
      if (name === 'createRadialGradient' || name === 'createLinearGradient') return () => gradient
      return (...args) => {
        calls.push([name, ...args])
      }
    },
    set(obj, name, value) {
      obj[name] = value
      return true
    },
  })
}

// Gives every canvas a recording 2D context (one per canvas, as browsers do).
export function install2d() {
  const contexts = new WeakMap()
  HTMLCanvasElement.prototype.getContext = function getContext(type) {
    if (type !== '2d') return null
    if (!contexts.has(this)) contexts.set(this, fake2d(this))
    return contexts.get(this)
  }
  HTMLCanvasElement.prototype.toDataURL = () => 'data:image/png;base64,'
}

export const renders = { count: 0, made: 0, disposed: 0 }

// three.js with its WebGLRenderer swapped for one without a GPU: use as vi.mock('three', threeWithFakeGL).
export async function threeWithFakeGL() {
  const real = await vi.importActual('three')
  class WebGLRenderer {
    constructor(options = {}) {
      renders.made += 1
      this.options = options
      this.domElement = options.canvas || document.createElement('canvas')
      this.shadowMap = { enabled: false, type: null }
      this.info = { render: { calls: 3, triangles: 4200 } }
      this.pixelRatio = 1
      this.size = [0, 0]
    }

    setPixelRatio(ratio) { this.pixelRatio = ratio }
    getPixelRatio() { return this.pixelRatio }
    setSize(width, height) { this.size = [width, height] }
    setClearColor() {}
    render(scene, camera) {
      renders.count += 1
      this.last = { scene, camera }
    }

    dispose() { renders.disposed += 1 }
  }
  return { ...real, WebGLRenderer }
}
