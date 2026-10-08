<script setup lang="ts">
/**
 * 小白管家真实 3D 形象渲染器（Three.js 程序化建模，见 utils/butlerCreatures.ts）：
 * - butterfly 金斑蝶（默认，呼应品牌 Logo） / deer 梅花鹿
 * - three 按需动态加载（独立 chunk），透明背景；心情/飞行/拖拽映射动作
 * - WebGL 不可用或初始化失败时回退 SVG 卡通形象（ButlerMascot），功能不受影响
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type * as ThreeNS from 'three'
import { buildButterfly, buildDeer, type Creature3D } from '@/utils/butlerCreatures'
import ButlerMascot from '@/components/butler/ButlerMascot.vue'

const props = withDefaults(
  defineProps<{
    creature?: 'butterfly' | 'deer'
    size?: number
    mood?: 'idle' | 'happy' | 'thinking' | 'greeting'
    flying?: boolean
    dragging?: boolean
  }>(),
  { creature: 'butterfly', size: 56, mood: 'idle', flying: false, dragging: false },
)

const hostEl = ref<HTMLDivElement>()
const ready = ref(false)
const failed = ref(false)

let renderer: ThreeNS.WebGLRenderer | null = null
let scene: ThreeNS.Scene | null = null
let camera: ThreeNS.PerspectiveCamera | null = null
let holder: ThreeNS.Group | null = null
let creature: Creature3D | null = null
let rafId = 0
let threeMod: typeof import('three') | null = null
let disposed = false
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

onMounted(() => {
  void init()
})

onBeforeUnmount(() => {
  disposed = true
  teardown()
})

watch(
  () => props.creature,
  () => {
    if (ready.value) rebuild()
  },
)
watch(() => props.size, () => {
  applySize()
  if (reduceMotion) renderFrame(performance.now())
})
// 减弱动态模式下仅静态渲染，但状态切换仍刷新一帧
watch(
  () => [props.mood, props.flying, props.dragging, props.creature],
  () => {
    if (reduceMotion) renderFrame(performance.now())
  },
)

async function init() {
  try {
    threeMod = await import('three')
    if (disposed || !hostEl.value) return

    renderer = new threeMod.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' })
    renderer.setClearColor(0x000000, 0)
    renderer.outputColorSpace = threeMod.SRGBColorSpace
    renderer.toneMapping = threeMod.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    applySize()

    scene = new threeMod.Scene()
    scene.add(new threeMod.HemisphereLight(0xffffff, 0xcbb89d, 0.55))
    const key = new threeMod.DirectionalLight(0xfff3e6, 2.3)
    key.position.set(2.2, 3.2, 4)
    scene.add(key)

    camera = new threeMod.PerspectiveCamera(32, 1, 0.1, 50)
    camera.position.set(0.55, 0.5, 3.15)
    camera.lookAt(0, 0, 0)

    mountCreature()

    renderer.domElement.addEventListener('webglcontextlost', onContextLost)
    document.addEventListener('visibilitychange', onVisibility)

    hostEl.value.appendChild(renderer.domElement)
    ready.value = true
    if (reduceMotion) renderFrame(performance.now())
    else startLoop()
  } catch (err) {
    console.warn('[ButlerCreature3D] 3D 渲染不可用，回退卡通形象:', err)
    failed.value = true
  }
}

/** 构建当前 creature 并归一化（居中 + 缩放到 ~1.5 单位）挂到场景 */
function mountCreature() {
  if (!threeMod || !scene) return
  const THREE = threeMod
  const built = props.creature === 'deer' ? buildDeer(THREE) : buildButterfly(THREE)
  const box = new THREE.Box3().setFromObject(built.group)
  const center = box.getCenter(new THREE.Vector3())
  const dim = box.getSize(new THREE.Vector3())
  const scale = 1.5 / Math.max(dim.x, dim.y, dim.z, 1e-6)
  holder = new THREE.Group()
  holder.position.set(-center.x * scale, -center.y * scale, -center.z * scale)
  holder.scale.setScalar(scale)
  holder.add(built.group)
  scene.add(holder)
  creature = built
}

/** 切换形象（外观选择器实时预览）：释放旧模型再挂新的 */
function rebuild() {
  if (creature && holder && scene) {
    scene.remove(holder)
    disposeObject(creature.group)
    creature = null
    holder = null
  }
  mountCreature()
  if (reduceMotion) renderFrame(performance.now())
}

function applySize() {
  if (!renderer) return
  renderer.setSize(props.size, props.size, false)
}

function startLoop() {
  const loop = (t: number) => {
    rafId = requestAnimationFrame(loop)
    if (document.hidden) return
    renderFrame(t)
  }
  rafId = requestAnimationFrame(loop)
}

function renderFrame(tms: number) {
  if (!renderer || !scene || !camera || !creature) return
  creature.animate(tms / 1000, { mood: props.mood, flying: props.flying, dragging: props.dragging })
  renderer.render(scene, camera)
}

function onContextLost() {
  failed.value = true
  teardown()
}

function onVisibility() {
  if (!document.hidden && reduceMotion) renderFrame(performance.now())
}

function teardown() {
  cancelAnimationFrame(rafId)
  document.removeEventListener('visibilitychange', onVisibility)
  if (creature) disposeObject(creature.group)
  creature = null
  holder = null
  scene = null
  camera = null
  renderer?.domElement.removeEventListener('webglcontextlost', onContextLost)
  renderer?.dispose()
  renderer = null
}

function disposeObject(obj: ThreeNS.Object3D) {
  obj.traverse((o) => {
    const mesh = o as ThreeNS.Mesh
    mesh.geometry?.dispose()
    const mat = mesh.material as ThreeNS.Material | ThreeNS.Material[] | undefined
    if (Array.isArray(mat)) mat.forEach((m) => disposeMaterial(m))
    else if (mat) disposeMaterial(mat)
  })
}

function disposeMaterial(m: ThreeNS.Material) {
  const std = m as ThreeNS.MeshStandardMaterial
  std.map?.dispose()
  std.normalMap?.dispose()
  m.dispose()
}
</script>

<template>
  <div ref="hostEl" class="creature3d" :style="{ width: size + 'px', height: size + 'px' }" aria-hidden="true">
    <!-- 加载中/失败时回退 SVG 卡通形象 -->
    <div v-if="!ready || failed" class="creature3d-fallback">
      <ButlerMascot mood="idle" :size="size" />
    </div>
  </div>
</template>

<style scoped>
.creature3d {
  position: relative;
  filter: drop-shadow(0 5px 9px rgba(61, 68, 81, 0.28));
}
.creature3d :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
  animation: creature3d-in 0.45s ease;
}
.creature3d-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
@keyframes creature3d-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
