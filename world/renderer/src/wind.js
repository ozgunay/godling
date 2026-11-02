import * as THREE from 'three'

// Wind (the user's wish): the world's Clock carries WindX/WindZ, its direction times its strength (0 breeze .. 1 gale).
// Here it is eased in, given gusts, and handed to the rain (which it bends) and to the palms (which it sways). As games
// do it: the sway grows with height, so a trunk stays rooted while the crown moves; a slow gust sweeps across the grove
// (its phase runs with position), and the fronds flutter faster on top of the bend. `?wind=1` forces a gale, to look.

const SWAY_TOP = 20 // palms stand 20 tall from the ground
const SWAY_BEND = 3.6 // how far a palm's crown leans in a full gale, in units (about 5 at a gust's top)
const SWAY_FLUTTER = 0.45 // fronds' quick shiver, relative to the bend

export function createWind(params) {
  const forced = params.has('wind') ? Number(params.get('wind')) : NaN
  const target = new THREE.Vector2(Number.isFinite(forced) ? forced : 0.2, 0)
  const eased = target.clone()
  const now = new THREE.Vector2() // with the gusts: what blows this frame
  const uniforms = { uWind: { value: now }, uWindTime: { value: 0 } }
  let time = 0

  return {
    uniforms,
    now,
    // The Clock's attributes, when an entity carries them.
    read(attributes) {
      const x = Number(attributes?.WindX)
      const z = Number(attributes?.WindZ)
      if (Number.isFinite(x) && Number.isFinite(z) && !Number.isFinite(forced)) target.set(x, z)
    },
    update(dt) {
      time += dt
      eased.lerp(target, Math.min(1, dt * 0.3))
      const strength = eased.length()
      // Gusts: a few slow waves on top of the wind; in a gale they are wilder.
      const wave = 0.5 * Math.sin(time * 0.9) + 0.3 * Math.sin(time * 2.3 + 1.7) + 0.2 * Math.sin(time * 0.37 + 0.4)
      const gust = 1 + (strength > 0.6 ? 0.45 : 0.2) * wave
      now.copy(eased).multiplyScalar(gust)
      uniforms.uWindTime.value = time
      return now
    },
  }
}

// Make a palm model's material sway: bend the vertex along the wind after the instance places it in the world (the
// instanced meshes sit at the scene's origin), more the higher it is. Keeps whatever else patches the material (the
// cascaded shadows) and gives the program its own cache key.
export function swayMaterial(material, uniforms) {
  if (!material || material.userData.sways) return
  material.userData.sways = true
  const before = material.onBeforeCompile
  material.onBeforeCompile = (shader, renderer) => {
    before?.call(material, shader, renderer)
    shader.uniforms.uWind = uniforms.uWind
    shader.uniforms.uWindTime = uniforms.uWindTime
    shader.vertexShader = 'uniform vec2 uWind;\nuniform float uWindTime;\n' + shader.vertexShader.replace(
      '#include <project_vertex>',
      THREE.ShaderChunk.project_vertex.replace('mvPosition = modelViewMatrix * mvPosition;', `
        float swayH = clamp( mvPosition.y / ${SWAY_TOP.toFixed(1)}, 0.0, 1.0 );
        float swayPhase = dot( mvPosition.xz, vec2( 0.045, 0.031 ) ); // a gust sweeps across the grove
        float swayGust = 0.7 + 0.3 * sin( uWindTime * 0.8 - swayPhase * 6.0 );
        float swayFlutter = sin( uWindTime * 5.0 + mvPosition.x * 1.7 + mvPosition.z * 1.3 );
        vec2 swayBend = uWind * ${SWAY_BEND.toFixed(2)} * swayH * swayH * ( swayGust + ${SWAY_FLUTTER.toFixed(2)} * swayFlutter * swayH );
        mvPosition.xz += swayBend;
        mvPosition.y -= dot( swayBend, swayBend ) * 0.03; // a crown bent over sits a little lower
        mvPosition = modelViewMatrix * mvPosition;`))
  }
  const key = material.customProgramCacheKey
  material.customProgramCacheKey = () => `${key ? key.call(material) : ''}|sway`
  material.needsUpdate = true
}
