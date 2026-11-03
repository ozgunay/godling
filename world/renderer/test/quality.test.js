import { afterEach, describe, expect, it, vi } from 'vitest'
import { chooseTier, createResolutionGovernor, TIERS } from '../src/quality.js'

function gpu(name, { debugInfo = true } = {}) {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation((type) => (type === 'webgl2' ? {
    RENDERER: 1,
    getExtension: (ext) => (ext === 'WEBGL_debug_renderer_info' ? (debugInfo ? { UNMASKED_RENDERER_WEBGL: 2 } : null)
      : { loseContext: () => {} }),
    getParameter: (p) => (p === 2 ? name : 'Generic GPU'),
  } : null))
}

function device(nav) {
  vi.stubGlobal('navigator', { userAgent: 'Mozilla/5.0 (Windows NT 10.0)', hardwareConcurrency: 8, deviceMemory: 8, ...nav })
}

describe('quality tiers', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('has three tiers, each better than the last', () => {
    expect(Object.keys(TIERS)).toEqual(['low', 'medium', 'high'])
    expect(TIERS.low.pixelRatio).toBeLessThan(TIERS.high.pixelRatio)
  })

  it('gives a strong PC the high tier', () => {
    gpu('NVIDIA GeForce RTX 3080')
    device({})
    expect(chooseTier()).toMatchObject({ name: 'high', reason: 'PC', capture: false, gpu: 'NVIDIA GeForce RTX 3080' })
  })

  it('gives the server\'s capture the low tier at one pixel per pixel', () => {
    gpu('Google SwiftShader')
    device({})
    expect(chooseTier()).toMatchObject({ name: 'low', pixelRatio: 1, capture: true })
    gpu('ANGLE', { debugInfo: false })
    device({ webdriver: true })
    expect(chooseTier().reason).toBe('software or automated browser')
    device({ userAgent: 'Mozilla/5.0 HeadlessChrome/120' })
    expect(chooseTier().capture).toBe(true)
  })

  it('reads the device: phones, tablets and weaker PCs', () => {
    gpu('Adreno 740')
    device({ userAgentData: { mobile: true }, deviceMemory: 8, hardwareConcurrency: 8 })
    expect(chooseTier()).toMatchObject({ name: 'medium', reason: 'phone or tablet' })
    device({ userAgent: 'Mozilla/5.0 (iPhone)', hardwareConcurrency: 6, deviceMemory: undefined })
    expect(chooseTier().name).toBe('low')
    device({ userAgent: 'Mozilla/5.0 (Macintosh)', maxTouchPoints: 5 }) // an iPad that says it is a Mac
    expect(chooseTier().reason).toBe('phone or tablet')
    device({ hardwareConcurrency: 2 })
    expect(chooseTier().reason).toBe('low-end PC')
    device({ hardwareConcurrency: 4 })
    expect(chooseTier()).toMatchObject({ name: 'medium', reason: 'mid-range PC' })
    device({ hardwareConcurrency: undefined, deviceMemory: undefined }) // unknown: assumed mid-range
    expect(chooseTier().name).toBe('medium')
  })

  it('follows ?quality= or the capture config, and survives no WebGL and no navigator', () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => null)
    device({})
    expect(chooseTier({ quality: 'HIGH' })).toMatchObject({ name: 'high', reason: 'asked' })
    vi.stubGlobal('location', { search: '?quality=low' })
    expect(chooseTier().reason).toBe('asked')
    vi.stubGlobal('location', undefined)
    vi.stubGlobal('navigator', undefined)
    expect(chooseTier().name).toBe('medium')
    HTMLCanvasElement.prototype.getContext.mockImplementation(() => { throw new Error('blocked') })
    expect(chooseTier({ quality: 'medium' }).gpu).toBe('')
  })
})

describe('resolution governor', () => {
  it('drops the resolution when frames are slow and lifts it when they are quick', () => {
    const governor = createResolutionGovernor({ capture: false })
    expect(governor.scale).toBe(1)
    expect(governor.sample(0)).toBe(false)
    let samples = 0
    while (!governor.sample(1 / 20) && samples < 100) samples += 1 // 20 fps, until two seconds are in
    expect(samples).toBeGreaterThanOrEqual(38)
    expect(samples).toBeLessThanOrEqual(40)
    expect(governor.scale).toBeCloseTo(0.85)
    for (let k = 0; k < 6; k++) for (let i = 0; i < 61; i++) governor.sample(1 / 30)
    expect(governor.scale).toBe(0.6) // no lower than this
    for (let k = 0; k < 6; k++) for (let i = 0; i < 121; i++) governor.sample(1 / 60.5)
    expect(governor.scale).toBe(1)
    for (let i = 0; i < 100; i++) governor.sample(1 / 50) // in between: kept
    expect(governor.scale).toBe(1)
  })

  it('keeps a fixed resolution for the capture', () => {
    const governor = createResolutionGovernor({ capture: true })
    for (let i = 0; i < 100; i++) expect(governor.sample(1)).toBe(false)
  })
})
