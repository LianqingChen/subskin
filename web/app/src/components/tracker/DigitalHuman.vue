<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

// ── Types ──
export interface AssessmentSnapshot {
  vasiScore: number
  areaPercentage: number
  stage: string
  classification?: string
}

const props = defineProps<{
  assessments: Record<string, AssessmentSnapshot | null>
}>()

const emit = defineEmits<{
  'select-part': [part: string]
}>()

// ── State ──
const containerRef = ref<HTMLDivElement>()
let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let controls: OrbitControls
let raycaster: THREE.Raycaster
let animationId = 0

const partGroups = new Map<string, THREE.Group>()
const partMaterials = new Map<string, THREE.MeshStandardMaterial[]>()
const outlineMeshes = new Map<string, THREE.Mesh[]>()

const baseSkin = new THREE.Color('#E8C9A0')
const whiteColor = new THREE.Color('#FAF5F0')
const unassessedColor = new THREE.Color('#B0A8A0')

// ── Material factory ──
function skinMaterial(color?: THREE.Color): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color: color || baseSkin,
    roughness: 0.48,
    metalness: 0.02,
  })
}

// ── Helper: create a capsule-like limb (cylinder + end spheres) ──
function createLimb(
  radius: number, length: number, segments = 20,
): { meshes: THREE.Mesh[] } {
  const meshes: THREE.Mesh[] = []
  const geo = new THREE.CylinderGeometry(radius, radius, length, segments)
  const mat = skinMaterial()
  const cyl = new THREE.Mesh(geo, mat)
  cyl.position.y = -length / 2
  meshes.push(cyl)

  // Top cap (joint)
  const capGeo = new THREE.SphereGeometry(radius * 1.15, segments, segments / 2)
  const capMat = skinMaterial()
  const cap = new THREE.Mesh(capGeo, capMat)
  cap.position.y = 0
  meshes.push(cap)

  return { meshes }
}

// ── Build a more realistic humanoid ──
function buildHumanoid() {
  const seg = 24

  // ── Head (ellipsoid: slightly wider, squash vertically) ──
  const headGroup = new THREE.Group()
  headGroup.name = 'face'
  const headGeo = new THREE.SphereGeometry(1, seg, seg)
  const headMesh = new THREE.Mesh(headGeo, skinMaterial())
  headMesh.scale.set(0.14, 0.155, 0.13)
  headMesh.position.set(0, 0.87, 0.01)
  headMesh.userData.partKey = 'face'
  headGroup.add(headMesh)
  registerPart('face', headGroup, [headMesh])

  // ── Neck ──
  const neckGroup = new THREE.Group()
  neckGroup.name = 'neck'
  const neckGeo = new THREE.CylinderGeometry(0.05, 0.058, 0.09, seg)
  const neckMesh = new THREE.Mesh(neckGeo, skinMaterial())
  neckMesh.position.set(0, 0.74, 0)
  neckMesh.userData.partKey = 'neck'
  neckGroup.add(neckMesh)
  registerPart('neck', neckGroup, [neckMesh])

  // ── Torso (shoulders wider, waist narrower) ──
  const torsoGroup = new THREE.Group()
  torsoGroup.name = 'trunk'
  // Upper chest
  const chestGeo = new THREE.BoxGeometry(0.34, 0.22, 0.18, 4, 4, 4)
  const chestMesh = new THREE.Mesh(chestGeo, skinMaterial())
  chestMesh.position.set(0, 0.60, 0)
  chestMesh.userData.partKey = 'trunk'
  torsoGroup.add(chestMesh)
  // Lower torso
  const waistGeo = new THREE.BoxGeometry(0.30, 0.24, 0.16, 4, 4, 4)
  const waistMesh = new THREE.Mesh(waistGeo, skinMaterial())
  waistMesh.position.set(0, 0.39, 0)
  waistMesh.userData.partKey = 'trunk'
  torsoGroup.add(waistMesh)
  registerPart('trunk', torsoGroup, [chestMesh, waistMesh])

  // ── Arms (upper + lower with joints) ──
  const leftUpper = createLimb(0.048, 0.24, seg)
  const leftLower = createLimb(0.042, 0.24, seg)
  const rightUpper = createLimb(0.048, 0.24, seg)
  const rightLower = createLimb(0.042, 0.24, seg)

  const armsGroup = new THREE.Group()
  armsGroup.name = 'arms'

  // Left arm
  const laGroup = new THREE.Group()
  laGroup.position.set(-0.22, 0.62, 0)
  laGroup.rotation.z = 0.12
  for (const m of leftUpper.meshes) { m.userData.partKey = 'arms'; laGroup.add(m) }
  const lalGroup = new THREE.Group()
  lalGroup.position.set(0, -0.24, 0)
  lalGroup.rotation.z = -0.08
  for (const m of leftLower.meshes) { m.userData.partKey = 'arms'; lalGroup.add(m) }
  laGroup.add(lalGroup)
  armsGroup.add(laGroup)

  // Right arm
  const raGroup = new THREE.Group()
  raGroup.position.set(0.22, 0.62, 0)
  raGroup.rotation.z = -0.12
  for (const m of rightUpper.meshes) { m.userData.partKey = 'arms'; raGroup.add(m) }
  const ralGroup = new THREE.Group()
  ralGroup.position.set(0, -0.24, 0)
  ralGroup.rotation.z = 0.08
  for (const m of rightLower.meshes) { m.userData.partKey = 'arms'; ralGroup.add(m) }
  raGroup.add(ralGroup)
  armsGroup.add(raGroup)

  const allArmMeshes = [...leftUpper.meshes, ...leftLower.meshes, ...rightUpper.meshes, ...rightLower.meshes]
  registerPart('arms', armsGroup, allArmMeshes)

  // ── Hands ──
  const handsGroup = new THREE.Group()
  handsGroup.name = 'hands'
  for (const side of [-1, 1]) {
    const handGeo = new THREE.BoxGeometry(0.08, 0.10, 0.06, 2, 2, 2)
    const handMat = skinMaterial()
    const handMesh = new THREE.Mesh(handGeo, handMat)
    handMesh.position.set(side * 0.26, 0.04, 0)
    handMesh.userData.partKey = 'hands'
    handsGroup.add(handMesh)
    // Thumb
    const thumbGeo = new THREE.BoxGeometry(0.03, 0.05, 0.03)
    const thumbMesh = new THREE.Mesh(thumbGeo, handMat)
    thumbMesh.position.set(side * 0.26 + side * 0.04, 0.08, 0)
    thumbMesh.userData.partKey = 'hands'
    handsGroup.add(thumbMesh)
    registerPartMaterial('hands', handMat)
  }
  registerPartGroup('hands', handsGroup)

  // ── Legs (upper + lower with joints) ──
  const leftUpLeg = createLimb(0.07, 0.28, seg)
  const leftLoLeg = createLimb(0.062, 0.28, seg)
  const rightUpLeg = createLimb(0.07, 0.28, seg)
  const rightLoLeg = createLimb(0.062, 0.28, seg)

  const legsGroup = new THREE.Group()
  legsGroup.name = 'legs'

  for (const side of [-1, 1]) {
    const upMeshes = side === -1 ? leftUpLeg.meshes : rightUpLeg.meshes
    const loMeshes = side === -1 ? leftLoLeg.meshes : rightLoLeg.meshes

    const ulGroup = new THREE.Group()
    ulGroup.position.set(side * 0.09, 0.06, 0)
    for (const m of upMeshes) { m.userData.partKey = 'legs'; ulGroup.add(m) }
    const llGroup = new THREE.Group()
    llGroup.position.set(0, -0.28, 0)
    for (const m of loMeshes) { m.userData.partKey = 'legs'; llGroup.add(m) }
    ulGroup.add(llGroup)
    legsGroup.add(ulGroup)
  }

  const allLegMeshes = [...leftUpLeg.meshes, ...leftLoLeg.meshes, ...rightUpLeg.meshes, ...rightLoLeg.meshes]
  registerPart('legs', legsGroup, allLegMeshes)

  // ── Feet ──
  const feetGroup = new THREE.Group()
  feetGroup.name = 'feet'
  for (const side of [-1, 1]) {
    const footGeo = new THREE.BoxGeometry(0.10, 0.06, 0.17, 3, 2, 3)
    const footMat = skinMaterial()
    const footMesh = new THREE.Mesh(footGeo, footMat)
    footMesh.position.set(side * 0.09, -0.52, 0.06)
    footMesh.userData.partKey = 'feet'
    feetGroup.add(footMesh)
    registerPartMaterial('feet', footMat)
  }
  registerPartGroup('feet', feetGroup)
}

function registerPart(key: string, group: THREE.Group, meshes: THREE.Mesh[]) {
  scene.add(group)
  partGroups.set(key, group)
  const mats = new Set<THREE.MeshStandardMaterial>()
  meshes.forEach(m => {
    if (m.material instanceof THREE.MeshStandardMaterial) mats.add(m.material)
  })
  partMaterials.set(key, [...mats])
}

function registerPartGroup(key: string, group: THREE.Group) {
  scene.add(group)
  partGroups.set(key, group)
  if (!partMaterials.has(key)) partMaterials.set(key, [])
}

function registerPartMaterial(key: string, mat: THREE.MeshStandardMaterial) {
  const mats = partMaterials.get(key)
  if (mats) mats.push(mat)
  else partMaterials.set(key, [mat])
}

// ── Color interpolation ──
function getPartColor(part: string): THREE.Color {
  const a = props.assessments[part]
  if (!a) return unassessedColor.clone()
  const t = Math.min(1, a.areaPercentage / 100)
  return baseSkin.clone().lerp(whiteColor, t)
}

const STAGE_COLORS: Record<string, string> = {
  '好转': '#22c55e', '稳定': '#eab308', '扩散': '#ef4444',
  '好转期': '#22c55e', '稳定期': '#eab308', '进展期': '#ef4444',
}
function getStageColor(stage: string): string { return STAGE_COLORS[stage] || '#94a3b8' }

function updateOutlines() {
  for (const meshes of outlineMeshes.values()) {
    meshes.forEach(m => {
      m.parent?.remove(m)
      m.geometry.dispose()
      ;(m.material as THREE.Material).dispose()
    })
  }
  outlineMeshes.clear()

  for (const [key, group] of partGroups) {
    const a = props.assessments[key]
    if (!a) continue
    const stageColor = new THREE.Color(getStageColor(a.stage))
    const outlines: THREE.Mesh[] = []
    group.children.forEach(child => {
      if (!(child instanceof THREE.Mesh)) return
      const outlineGeo = child.geometry.clone()
      const outlineMat = new THREE.MeshBasicMaterial({
        color: stageColor, wireframe: true, transparent: true,
        opacity: 0.65, depthTest: true, depthWrite: false,
      })
      const outlineMesh = new THREE.Mesh(outlineGeo, outlineMat)
      outlineMesh.position.copy(child.position)
      outlineMesh.rotation.copy(child.rotation)
      outlineMesh.scale.copy(child.scale).multiplyScalar(1.07)
      outlineMesh.userData.isOutline = true
      group.add(outlineMesh)
      outlines.push(outlineMesh)
    })
    outlineMeshes.set(key, outlines)
  }
}

function refreshAllColors() {
  for (const [key, materials] of partMaterials) {
    const color = getPartColor(key)
    materials.forEach(m => { m.color.copy(color) })
  }
  updateOutlines()
}

// ── Lighting ──
function setupLighting() {
  const ambient = new THREE.AmbientLight('#fff5ee', 1.6)
  scene.add(ambient)
  const key = new THREE.DirectionalLight('#ffffff', 2.2)
  key.position.set(4, 3, 5)
  scene.add(key)
  const fill = new THREE.DirectionalLight('#ffe0cc', 0.9)
  fill.position.set(-3, 1.5, -2)
  scene.add(fill)
  const rim = new THREE.DirectionalLight('#ccddff', 0.7)
  rim.position.set(0, 1, -4)
  scene.add(rim)
}

// ── Raycasting ──
const pointer = new THREE.Vector2()

function onPointerDown(event: PointerEvent) {
  if (!containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const allMeshes: THREE.Object3D[] = []
  partGroups.forEach(group => allMeshes.push(...group.children))
  const intersects = raycaster.intersectObjects(allMeshes, true)
  if (intersects.length > 0) {
    let obj = intersects[0].object
    while (obj && !obj.userData.partKey && obj.parent) obj = obj.parent
    const partKey = obj?.userData?.partKey as string | undefined
    if (partKey) emit('select-part', partKey)
  }
}

function onPointerMove(event: PointerEvent) {
  if (!containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const allMeshes: THREE.Object3D[] = []
  partGroups.forEach(group => allMeshes.push(...group.children.filter(c => !(c as any).userData?.isOutline)))
  const intersects = raycaster.intersectObjects(allMeshes, true)
  if (intersects.length > 0) {
    containerRef.value.style.cursor = 'pointer'
  } else {
    containerRef.value.style.cursor = 'grab'
  }
}

// ── Animation ──
function animate() {
  animationId = requestAnimationFrame(animate)
  const time = Date.now() * 0.001
  for (const [partKey, outlines] of outlineMeshes) {
    const a = props.assessments[partKey]
    if (!a) continue
    const pulse = (a.stage === '扩散' || a.stage === '进展期')
      ? 1 + Math.sin(time * 3) * 0.04 : 1.02
    outlines.forEach(m => m.scale.copy(m.scale).setScalar(pulse))
  }
  controls.update()
  renderer.render(scene, camera)
}

function onResize() {
  if (!containerRef.value) return
  const { width, height } = containerRef.value.getBoundingClientRect()
  if (width <= 0 || height <= 0) return
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

// ── Lifecycle ──
onMounted(() => {
  if (!containerRef.value) return
  const { width, height } = containerRef.value.getBoundingClientRect()

  scene = new THREE.Scene()
  scene.background = new THREE.Color('#f0ece6')

  camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 20)
  camera.position.set(0, 0.25, 2.8)
  camera.lookAt(0, 0.2, 0)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.15
  containerRef.value.appendChild(renderer.domElement)

  // Controls — lock to horizontal rotation only
  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0.2, 0)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 1.5
  controls.maxDistance = 4.5
  // Lock vertical: only horizontal 360° rotation
  controls.minPolarAngle = Math.PI / 2
  controls.maxPolarAngle = Math.PI / 2
  controls.autoRotate = true
  controls.autoRotateSpeed = 0.5
  controls.update()

  raycaster = new THREE.Raycaster()

  setupLighting()
  buildHumanoid()
  refreshAllColors()

  containerRef.value.addEventListener('pointerdown', onPointerDown)
  containerRef.value.addEventListener('pointermove', onPointerMove)
  window.addEventListener('resize', onResize)

  animate()
})

onUnmounted(() => {
  cancelAnimationFrame(animationId)
  if (containerRef.value) {
    containerRef.value.removeEventListener('pointerdown', onPointerDown)
    containerRef.value.removeEventListener('pointermove', onPointerMove)
  }
  window.removeEventListener('resize', onResize)
  controls?.dispose()
  renderer?.dispose()
  partMaterials.forEach(mats => mats.forEach(m => m.dispose()))
  partGroups.forEach(group => {
    group.traverse(child => {
      if (child instanceof THREE.Mesh) {
        child.geometry.dispose()
        if (Array.isArray(child.material)) child.material.forEach(m => m.dispose())
        else child.material.dispose()
      }
    })
  })
  outlineMeshes.forEach(meshes => meshes.forEach(m => {
    m.geometry.dispose(); (m.material as THREE.Material).dispose()
  }))
})

watch(() => props.assessments, () => refreshAllColors(), { deep: true })

function highlightPart(part: string | null) {
  partMaterials.forEach((mats) => mats.forEach(m => { m.emissive.set('#000000') }))
  if (part) {
    const mats = partMaterials.get(part)
    if (mats) mats.forEach(m => { m.emissive.set('#332211') })
  }
}

function lookAtPart(part: string) {
  const group = partGroups.get(part)
  if (!group) return
  const pos = new THREE.Vector3()
  group.getWorldPosition(pos)
  controls.target.copy(pos)
  controls.update()
}

defineExpose({ highlightPart, lookAtPart })
</script>

<template>
  <div
    ref="containerRef"
    class="w-full h-full min-h-[320px] rounded-2xl overflow-hidden cursor-grab active:cursor-grabbing"
  />
</template>
