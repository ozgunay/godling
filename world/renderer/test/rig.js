// A skinned stand-in for godling.glb, as art/build_godling.py makes Godling: rigid parts, each fully weighted to one
// bone, on bones named as three.js names the Mixamo rig's. The body is on the hips; the mitten on the right hand,
// whose bone sits at (-0.5, 1, 0) turned a quarter about Z (its Y, along the fingers, points to -X). The mitten's
// middle is 0.1 along the hand bone. `mitten: false` leaves the hand without one.
import * as THREE from 'three'

function weighted(geometry, bone, weight = 1) {
  const count = geometry.attributes.position.count
  geometry.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(new Array(count * 4).fill(0).map((_, i) => (i % 4 ? 0 : bone)), 4))
  geometry.setAttribute('skinWeight', new THREE.Float32BufferAttribute(new Array(count * 4).fill(0).map((_, i) => (i % 4 ? 0 : weight)), 4))
  return geometry
}

export function handed({ clips = ['Idle'], mitten = true } = {}) {
  const scene = new THREE.Group()
  const hips = new THREE.Bone()
  hips.name = 'mixamorigHips'
  hips.position.set(0, 1, 0)
  const hand = new THREE.Bone()
  hand.name = 'mixamorigRightHand'
  hand.position.set(-0.5, 0, 0)
  hand.rotation.z = Math.PI / 2
  hips.add(hand)
  scene.add(hips)
  scene.updateMatrixWorld(true)
  const skeleton = new THREE.Skeleton([hips, hand])
  const parts = [weighted(new THREE.BoxGeometry(0.6, 2, 0.6).translate(0, 1, 0), 0)]
  parts.push(weighted(new THREE.BoxGeometry(0.1, 0.1, 0.1).translate(-0.6, 1, 0), 1, mitten ? 1 : 0.4))
  for (const geometry of parts) {
    const mesh = new THREE.SkinnedMesh(geometry, new THREE.MeshStandardMaterial())
    scene.add(mesh)
    mesh.bind(skeleton)
  }
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.1, 0.1), new THREE.MeshStandardMaterial())) // not skinned
  const sway = (name) => new THREE.AnimationClip(name, 1, [
    new THREE.NumberKeyframeTrack('mixamorigRightHand.rotation[x]', [0, 1], [0, 0.6])])
  return { scene, animations: clips.map(sway) }
}
