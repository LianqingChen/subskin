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
const hoveredPart = ref<string | null>(null)

// ── Body part geometry definitions ──
interface MeshDef {
  type: 'sphere' | 'cylinder' | 'box'
  params: number[]
  position: [number, number, number]
  rotation?: [number, number, number]
}

const BODY_DEFS: { key: string; meshes: MeshDef[] }[] = [
  {
    key: 'face',
    meshes: [
      { type: 'sphere', params: [0.14, 32, 32], position: [0, 0.88, 0] },
    ],
  },
  {
    key: 'neck',
    meshes: [
      { type: 'cylinder', params: [0.055, 0.06, 0.09, 20], position: [0, 0.75, 0] },
    ],
  },
  {
    key: 'trunk',
    meshes: [
      { type: 'box', params: [0.34, 0.46, 0.18], position: [0, 0.44, 0] },
    ],
  },
  {
    key: 'arms',
    meshes: [
      { type: 'cylinder', params: [0.052, 0.052, 0.26, 16], position: [-0.24, 0.56, 0], rotation: [0, 0, 0.15] },
      { type: 'cylinder', params: [0.045, 0.045, 0.26, 16], position: [-0.28, 0.30, 0], rotation: [0, 0, -0.05] },
      { type: 'cylinder', params: [0.052, 0.052, 0.26, 16], position: [0.24, 0.56, 0], rotation: [0, 0, -0.15] },
      { type: 'cylinder', params: [0.045, 0.045, 0.26, 16], position: [0.28, 0.30, 0], rotation: [0, 0, 0.05] },
    ],
  },
  {
    key: 'hands',
    meshes: [
      { type: 'box', params: [0.09, 0.11, 0.07], position: [-0.30, 0.06, 0] },
      { type: 'box', params: [0.09, 0.11, 0.07], position: [0.30, 0.06, 0] },
    ],
  },
  {
    key: 'legs',
    meshes: [
      { type: 'cylinder', params: [0.075, 0.075, 0.30, 16], position: [-0.09, 0.04, 0] },
      { type: 'cylinder', params: [0.065, 0.065, 0.28, 16], position: [-0.09, -0.25, 0] },
      { type: 'cylinder', params: [0.075, 0.075, 0.30, 16], position: [0.09, 0.04, 0] },
      { type: 'cylinder', params: [0.065, 0.065, 0.28, 16], position: [0.09, -0.25, 0] },
    ],
  },
  {
    key: 'feet',
    meshes: [
      { type: 'box', params: [0.10, 0.06, 0.16], position: [-0.09, -0.50, 0.06] },
      { type: 'box', params: [0.10, 0.06, 0.16], position: [0.09, -0.50, 0.06] },
    ],
  },
]

const STAGE_COLORS: Record<string, string> = {
  '好转': '#22c55e',
  '稳定': '#eab308',
  '扩散': '#ef4444',
  '好转期': '#22c55e',
  '稳定期': '#eab308',
  '进展期': '#ef4444',
}

function getStageColor(stage: string): string {
  return STAGE_COLORS[stage] || '#94a3b8'
}

// ── Color interpolation ──
function getPartColor(part: string): THREE.Color {
  const a = props.assessments[part]
  if (!a) return unassessedColor.clone()
  const t = Math.min(1, a.areaPercentage / 100)
  return baseSkin.clone().lerp(whiteColor, t)
}

// ── Scene setup ──
function createGeometry(def: MeshDef): THREE.BufferGeometry {
  switch (def.type) {
    case 'sphere': return new THREE.SphereGeometry(...(def.params as [number, number, number]))
    case 'cylinder': return new THREE.CylinderGeometry(...(def.params as [number, number, number, number]))
    case 'box': return new THREE.BoxGeometry(...(def.params as [number, number, number]))
  }
}

function buildHumanoid() {
  for (const partDef of BODY_DEFS) {
    const group = new THREE.Group()
    group.name = partDef.key
    const materials: THREE.MeshStandardMaterial[] = []

    for (const meshDef of partDef.meshes) {
      const geo = createGeometry(meshDef)
      const mat = new THREE.MeshStandardMaterial({
        color: getPartColor(partDef.key),
        roughness: 0.55,
        metalness: 0.05,
        name: partDef.key,
      })
      const mesh = new THREE.Mesh(geo, mat)
      mesh.position.set(...meshDef.position)
      if (meshDef.rotation) {
        mesh.rotation.set(...meshDef.rotation)
      }
      mesh.castShadow = true
      mesh.receiveShadow = true
      // Tag each mesh with its assessment key for raycasting
      mesh.userData.partKey = partDef.key
      group.add(mesh)
      materials.push(mat)
    }

    scene.add(group)
    partGroups.set(partDef.key, group)
    partMaterials.set(partDef.key, materials)
  }
}

function updateOutlines() {
  // Remove old outlines
  for (const meshes of outlineMeshes.values()) {
    meshes.forEach(m => {
      m.parent?.remove(m)
      m.geometry.dispose()
      ;(m.material as THREE.Material).dispose()
    })
  }
  outlineMeshes.clear()

  // Create new outlines for assessed parts
  for (const partDef of BODY_DEFS) {
    const a = props.assessments[partDef.key]
    if (!a) continue

    const stageColor = new THREE.Color(getStageColor(a.stage))
    const group = partGroups.get(partDef.key)
    if (!group) continue

    const outlines: THREE.Mesh[] = []
    group.children.forEach(child => {
      if (!(child instanceof THREE.Mesh)) return
      // Create slightly scaled-up wireframe or outline mesh
      const outlineGeo = child.geometry.clone()
      const outlineMat = new THREE.MeshBasicMaterial({
        color: stageColor,
        wireframe: true,
        transparent: true,
        opacity: 0.7,
        depthTest: true,
        depthWrite: false,
      })
      const outlineMesh = new THREE.Mesh(outlineGeo, outlineMat)
      outlineMesh.position.copy(child.position)
      outlineMesh.rotation.copy(child.rotation)
      // Slightly larger
      outlineMesh.scale.setScalar(1.06)
      outlineMesh.userData.isOutline = true
      group.add(outlineMesh)
      outlines.push(outlineMesh)
    })
    outlineMeshes.set(partDef.key, outlines)
  }
}

function refreshAllColors() {
  for (const partDef of BODY_DEFS) {
    const color = getPartColor(partDef.key)
    const materials = partMaterials.get(partDef.key)
    if (materials) {
      materials.forEach(m => { m.color.copy(color) })
    }
  }
  updateOutlines()
}

// ── Lighting ──
function setupLighting() {
  const ambient = new THREE.AmbientLight('#ffffff', 1.4)
  scene.add(ambient)

  const key = new THREE.DirectionalLight('#ffffff', 2.0)
  key.position.set(5, 3, 5)
  scene.add(key)

  const fill = new THREE.DirectionalLight('#ffe0cc', 0.8)
  fill.position.set(-3, 1, -2)
  scene.add(fill)

  const rim = new THREE.DirectionalLight('#ccddff', 0.6)
  rim.position.set(0, 0.5, -5)
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
  partGroups.forEach(group => allMeshes.push(...group.children.filter(c => c instanceof THREE.Mesh)))
  const intersects = raycaster.intersectObjects(allMeshes, false)

  if (intersects.length > 0) {
    const obj = intersects[0].object
    const partKey = obj.userData.partKey as string | undefined
    if (partKey) {
      emit('select-part', partKey)
    }
  }
}

function onPointerMove(event: PointerEvent) {
  if (!containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(pointer, camera)
  const allMeshes: THREE.Object3D[] = []
  partGroups.forEach(group => allMeshes.push(...group.children.filter(c => c instanceof THREE.Mesh && !c.userData.isOutline)))

  const intersects = raycaster.intersectObjects(allMeshes, false)
  if (intersects.length > 0) {
    const obj = intersects[0].object
    const partKey = obj.userData.partKey as string | undefined
    hoveredPart.value = partKey || null
    if (containerRef.value) {
      containerRef.value.style.cursor = 'pointer'
    }
  } else {
    hoveredPart.value = null
    if (containerRef.value) {
      containerRef.value.style.cursor = 'grab'
    }
  }
}

// ── Animation loop ──
function animate() {
  animationId = requestAnimationFrame(animate)

  // Pulse outlines for assessed parts
  const time = Date.now() * 0.001
  for (const [partKey, outlines] of outlineMeshes) {
    const a = props.assessments[partKey]
    if (!a) continue
    const pulse = a.stage === '扩散' || a.stage === '进展期'
      ? 1 + Math.sin(time * 3) * 0.04
      : 1.02
    outlines.forEach(m => m.scale.setScalar(pulse))
  }

  controls.update()
  renderer.render(scene, camera)
}

// ── Resize ──
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

  // Scene
  scene = new THREE.Scene()

  // Camera
  camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 20)
  camera.position.set(0, 0.35, 2.8)
  camera.lookAt(0, 0.3, 0)

  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.1
  containerRef.value.appendChild(renderer.domElement)

  // Controls
  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0.25, 0)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 1.5
  controls.maxDistance = 5.0
  controls.maxPolarAngle = Math.PI * 0.75
  controls.minPolarAngle = Math.PI * 0.25
  controls.autoRotate = true
  controls.autoRotateSpeed = 0.4
  controls.update()

  // Raycaster
  raycaster = new THREE.Raycaster()

  // Build
  setupLighting()
  buildHumanoid()
  refreshAllColors()

  // Events
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
  // Clean up geometries/materials
  partMaterials.forEach(mats => mats.forEach(m => m.dispose()))
  partGroups.forEach(group => {
    group.traverse(child => {
      if (child instanceof THREE.Mesh) {
        child.geometry.dispose()
      }
    })
  })
  outlineMeshes.forEach(meshes => meshes.forEach(m => {
    m.geometry.dispose()
    ;(m.material as THREE.Material).dispose()
  }))
})

// ── Watch for assessment updates ──
watch(() => props.assessments, () => {
  refreshAllColors()
}, { deep: true })

// ── Public method: highlight a part (called by parent) ──
function highlightPart(part: string | null) {
  // Reset all emissive
  partMaterials.forEach((mats) => {
    mats.forEach(m => { m.emissive.set('#000000') })
  })
  if (part) {
    const mats = partMaterials.get(part)
    if (mats) {
      mats.forEach(m => { m.emissive.set('#332211') })
    }
  }
}

// ── Public method: rotate to show a specific part ──
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
    :style="{ background: 'radial-gradient(ellipse at center, #f8f6f3 0%, #e8e4dc 100%)' }"
  />
</template>
