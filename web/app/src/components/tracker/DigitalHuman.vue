<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { useThemeStore } from '@/stores/theme'

export interface AssessmentSnapshot {
  vasiScore: number
  areaPercentage: number
  stage: string
  classification?: string
}

const emit = defineEmits<{
  'open-chat': []
}>()

const containerRef = ref<HTMLDivElement>()
let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let controls: OrbitControls
let raycaster: THREE.Raycaster
let animationId = 0

// Interactive objects
let bubbleGroup: THREE.Group | null = null

// Highlight flash state
let highlightTarget: 'bubble' | null = null
let highlightStart = 0
const HIGHLIGHT_DURATION = 500 // ms

// Idle greeting state
const IDLE_MESSAGES = [
  '你好呀~ 有什么需要帮助的吗？',
  '点击我头顶的气泡，和我聊天吧~',
  '左右滑动可以旋转查看我哦~',
  '我是你的AI销售助手，随时为你服务~',
]
let hasGreeted = false
let lastInteractionTime = Date.now()
let idleTimer: ReturnType<typeof setInterval> | null = null
let greetingIndex = 0

// Greeting bubble overlay state
const greetingText = ref('')
const greetingPos = ref({ x: 0, y: 0 })
let greetingTimeout: ReturnType<typeof setTimeout> | null = null

// 暗色模式适配
const themeStore = useThemeStore()
const isDarkMode = computed(() => themeStore.mode === 'dark')

// 眨眼动画
const blinkState = ref(0) // 0=睁眼, 1=闭眼中
let blinkCooldown: ReturnType<typeof setTimeout> | null = null

function scheduleBlink() {
  blinkCooldown = setTimeout(() => {
    blinkState.value = 1
    setTimeout(() => { blinkState.value = 0 }, 150)
    blinkCooldown = null
    scheduleBlink()
  }, 2000 + Math.random() * 4000) // 2-6秒随机间隔
}

// ── Idle Greeting System ──
function showGreetingBubble(msg: string) {
  // Clear any existing greeting
  if (greetingTimeout) clearTimeout(greetingTimeout)
  greetingText.value = msg
  // Auto-dismiss after 5 seconds
  greetingTimeout = setTimeout(() => { greetingText.value = '' }, 5000)
}

function startIdleGreeting() {
  if (idleTimer) return
  idleTimer = setInterval(() => {
    const elapsed = Date.now() - lastInteractionTime
    if (elapsed < 5000) return // Wait at least 5s of inactivity
    if (!hasGreeted) {
      showGreetingBubble(IDLE_MESSAGES[0])
      hasGreeted = true
      greetingIndex = 1
    } else {
      showGreetingBubble(IDLE_MESSAGES[greetingIndex % IDLE_MESSAGES.length])
      greetingIndex++
    }
  }, 8000) // Every 8 seconds
}

function stopIdleGreeting() {
  if (idleTimer) { clearInterval(idleTimer); idleTimer = null }
  if (greetingTimeout) { clearTimeout(greetingTimeout); greetingTimeout = null }
  greetingText.value = ''
}

function markInteraction() {
  lastInteractionTime = Date.now()
}

function buildPanda() {
  const blackMat = new THREE.MeshStandardMaterial({ color: '#1a1a1a', roughness: 0.45, metalness: 0.0 })
  const whiteMat = new THREE.MeshStandardMaterial({ color: '#fafaf8', roughness: 0.5, metalness: 0.0 })
  const noseMat = new THREE.MeshStandardMaterial({ color: '#111111', roughness: 0.3 })
  const eyeWhiteMat = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.15, emissive: '#ffffff', emissiveIntensity: 0.2 })
  const pupilMat = new THREE.MeshStandardMaterial({ color: '#0a0a0a', roughness: 0.05 })
  const highlightMat = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.05, emissive: '#ffffff', emissiveIntensity: 0.6 })

  const pandaGroup = new THREE.Group()
  pandaGroup.name = 'panda'

  // ── BODY (white ellipsoid, slightly squat) ──
  const bodyGeo = new THREE.SphereGeometry(0.22, 32, 24)
  bodyGeo.scale(1, 0.7, 0.65)
  const bodyMesh = new THREE.Mesh(bodyGeo, whiteMat)
  bodyMesh.position.set(0, 0.02, 0)
  bodyMesh.castShadow = true
  bodyMesh.receiveShadow = true
  pandaGroup.add(bodyMesh)

  // ── HEAD (large white sphere) ──
  const headGroup = new THREE.Group()
  headGroup.position.set(0, 0.48, 0)
  const headGeo = new THREE.SphereGeometry(0.20, 32, 24)
  headGeo.scale(1, 0.88, 0.82)
  const headMesh = new THREE.Mesh(headGeo, whiteMat)
  headMesh.castShadow = true
  headMesh.receiveShadow = true
  headGroup.add(headMesh)

  // ── EARS (black spheres on top) ──
  for (const sx of [-1, 1]) {
    const earGeo = new THREE.SphereGeometry(0.07, 16, 12)
    const ear = new THREE.Mesh(earGeo, blackMat)
    ear.position.set(sx * 0.14, 0.18, -0.03)
    ear.castShadow = true
    headGroup.add(ear)
  }

  // ── EYE PATCHES (black ellipses, angled) ──
  for (const sx of [-1, 1]) {
    const patchShape = new THREE.Shape()
    const rx = 0.06, ry = 0.045
    // Draw an ellipse using a circle scaled
    const segs = 24
    for (let i = 0; i <= segs; i++) {
      const angle = (i / segs) * Math.PI * 2
      const x = Math.cos(angle) * rx
      const y = Math.sin(angle) * ry
      if (i === 0) patchShape.moveTo(x, y)
      else patchShape.lineTo(x, y)
    }
    const patchGeo = new THREE.ShapeGeometry(patchShape)
    const patch = new THREE.Mesh(patchGeo, blackMat)
    patch.position.set(sx * 0.08, 0.05, 0.14)
    patch.rotation.z = sx * -0.2
    patch.rotation.y = sx * 0.15
    headGroup.add(patch)
  }

  // ── EYES (white + pupil + highlight) ──
  const eyeMeshes: THREE.Mesh[] = []
  for (const sx of [-1, 1]) {
    // White of eye
    const ewGeo = new THREE.SphereGeometry(0.035, 14, 10)
    ewGeo.scale(1.15, 1.0, 0.5)
    const ew = new THREE.Mesh(ewGeo, eyeWhiteMat)
    ew.position.set(sx * 0.075, 0.05, 0.155)
    ew.userData.isPandaEye = true
    headGroup.add(ew)
    eyeMeshes.push(ew)

    // Pupil
    const pupilGeo = new THREE.SphereGeometry(0.016, 10, 8)
    const pupil = new THREE.Mesh(pupilGeo, pupilMat)
    pupil.position.set(sx * 0.075, 0.05, 0.170)
    headGroup.add(pupil)

    // Highlight sparkle
    const hlGeo = new THREE.SphereGeometry(0.006, 6, 4)
    const hl = new THREE.Mesh(hlGeo, highlightMat)
    hl.position.set(sx * 0.068, 0.058, 0.172)
    headGroup.add(hl)
  }

  // ── NOSE (small black oval) ──
  const noseGeo = new THREE.SphereGeometry(0.025, 12, 8)
  noseGeo.scale(1.3, 0.7, 0.6)
  const nose = new THREE.Mesh(noseGeo, noseMat)
  nose.position.set(0, -0.03, 0.18)
  headGroup.add(nose)

  // ── MOUTH (gentle curve) ──
  const mouthCurve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(-0.025, 0, 0),
    new THREE.Vector3(0, -0.01, 0.003),
    new THREE.Vector3(0.025, 0, 0),
  )
  const mouthGeo = new THREE.TubeGeometry(mouthCurve, 12, 0.004, 6, false)
  const mouthMesh = new THREE.Mesh(mouthGeo, blackMat)
  mouthMesh.position.set(0, -0.07, 0.17)
  headGroup.add(mouthMesh)

  pandaGroup.add(headGroup)

  // ── ARMS (black capsules, hanging at sides) ──
  for (const sx of [-1, 1]) {
    const upperGeo = new THREE.CapsuleGeometry(0.055, 0.18, 8, 16)
    const upper = new THREE.Mesh(upperGeo, blackMat)
    upper.position.set(sx * 0.22, 0.10, 0)
    upper.rotation.z = sx * 0.15
    upper.castShadow = true
    pandaGroup.add(upper)

    const lowerGeo = new THREE.CapsuleGeometry(0.045, 0.14, 8, 16)
    const lower = new THREE.Mesh(lowerGeo, blackMat)
    lower.position.set(sx * 0.27, -0.06, 0)
    lower.rotation.z = sx * 0.1
    lower.castShadow = true
    pandaGroup.add(lower)
  }

  // ── LEGS (black short cylinders) ──
  for (const sx of [-1, 1]) {
    const legGeo = new THREE.CapsuleGeometry(0.07, 0.12, 8, 16)
    const leg = new THREE.Mesh(legGeo, blackMat)
    leg.position.set(sx * 0.09, -0.16, 0.02)
    leg.castShadow = true
    leg.receiveShadow = true
    pandaGroup.add(leg)
  }

  // ── FEET (black ellipsoids) ──
  for (const sx of [-1, 1]) {
    const footGeo = new THREE.SphereGeometry(0.06, 16, 12)
    footGeo.scale(1.15, 0.3, 1.3)
    const foot = new THREE.Mesh(footGeo, blackMat)
    foot.position.set(sx * 0.09, -0.24, 0.05)
    foot.castShadow = true
    foot.receiveShadow = true
    pandaGroup.add(foot)
  }

  // ── TAIL (small white sphere at back) ──
  const tailGeo = new THREE.SphereGeometry(0.05, 12, 10)
  const tail = new THREE.Mesh(tailGeo, whiteMat)
  tail.position.set(0, -0.10, -0.16)
  pandaGroup.add(tail)

  scene.add(pandaGroup)

  // Store reference to panda group for animation
  ;(scene as any).__pandaGroup = pandaGroup
  ;(scene as any).__pandaEyeMeshes = eyeMeshes

  // ── PLATFORM ──
  const isDark = themeStore.mode === 'dark'
  const platGeo = new THREE.CylinderGeometry(0.34, 0.37, 0.018, 32)
  const platMat = new THREE.MeshStandardMaterial({ color: isDark ? '#2a2a3e' : '#e8e0d8', roughness: 0.85, metalness: 0.05 })
  const plat = new THREE.Mesh(platGeo, platMat)
  plat.position.y = -0.32
  plat.receiveShadow = true
  scene.add(plat)

  // ── AI SPEECH BUBBLE ──
  buildSpeechBubble()
}

function buildSpeechBubble() {
  bubbleGroup = new THREE.Group()
  // Position: right side of panda head
  bubbleGroup.position.set(0.28, 0.60, 0.10)

  const cloudMat = new THREE.MeshStandardMaterial({
    color: '#ffffff',
    roughness: 0.25,
    metalness: 0.0,
    transparent: true,
    opacity: 0.95,
    emissive: '#ffffff',
    emissiveIntensity: 0.15,
  })

  // Main cloud body — large center sphere
  const center = new THREE.Mesh(new THREE.SphereGeometry(0.045, 20, 14), cloudMat)
  center.userData.isBubble = true
  bubbleGroup.add(center)

  // Cloud bumps — 5 spheres around center to create fluffy cloud outline
  const bumps: { pos: [number, number, number]; r: number }[] = [
    { pos: [0.035, 0.015, 0], r: 0.035 },   // top-right
    { pos: [-0.03, 0.02, 0], r: 0.033 },     // top-left
    { pos: [0.04, -0.012, 0], r: 0.030 },    // right
    { pos: [-0.035, -0.01, 0], r: 0.028 },   // left
    { pos: [0, -0.025, 0], r: 0.026 },        // bottom
  ]
  for (const b of bumps) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(b.r, 14, 10), cloudMat)
    m.position.set(...b.pos)
    m.userData.isBubble = true
    bubbleGroup.add(m)
  }

  // Tail — two small bubbles pointing toward mouth (left-downward)
  const tailMat = new THREE.MeshStandardMaterial({
    color: '#ffffff', roughness: 0.25, metalness: 0.0,
    transparent: true, opacity: 0.92, emissive: '#ffffff', emissiveIntensity: 0.12,
  })
  const tail1 = new THREE.Mesh(new THREE.SphereGeometry(0.016, 10, 8), tailMat)
  tail1.position.set(-0.07, -0.035, 0)
  tail1.userData.isBubble = true
  bubbleGroup.add(tail1)
  const tail2 = new THREE.Mesh(new THREE.SphereGeometry(0.010, 8, 6), tailMat)
  tail2.position.set(-0.10, -0.055, 0)
  tail2.userData.isBubble = true
  bubbleGroup.add(tail2)

  // Green "AI" badge dot inside cloud
  const badgeMat = new THREE.MeshStandardMaterial({ color: '#10b981', roughness: 0.3, emissive: '#10b981', emissiveIntensity: 0.4 })
  const badge = new THREE.Mesh(new THREE.SphereGeometry(0.012, 10, 8), badgeMat)
  badge.position.set(0, 0.005, 0.038)
  badge.userData.isBubble = true
  bubbleGroup.add(badge)

  // Two small white "eyes" inside cloud for character
  const eyeMat = new THREE.MeshStandardMaterial({ color: '#374151', roughness: 0.4 })
  for (const sx of [-1, 1]) {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.006, 8, 6), eyeMat)
    eye.position.set(sx * 0.012, 0.01, 0.04)
    eye.userData.isBubble = true
    bubbleGroup.add(eye)
  }

  // Subtle shadow ring beneath cloud
  const shadowMat = new THREE.MeshBasicMaterial({ color: '#000000', transparent: true, opacity: 0.06 })
  const shadow = new THREE.Mesh(new THREE.RingGeometry(0.03, 0.06, 20), shadowMat)
  shadow.rotation.x = -Math.PI / 2
  shadow.position.set(0, -0.035, -0.01)
  shadow.userData.isBubble = true
  bubbleGroup.add(shadow)

  scene.add(bubbleGroup)
}

// 暗色模式监听
watch(isDarkMode, (isDark) => {
  if (isDark) {
    scene.background = new THREE.Color('#1a1a2e')
    const ambient = scene.children.find(c => c instanceof THREE.AmbientLight) as THREE.AmbientLight
    if (ambient) ambient.color.set('#2a3050')
  } else {
    scene.background = new THREE.Color('#ede8e2')
    const ambient = scene.children.find(c => c instanceof THREE.AmbientLight) as THREE.AmbientLight
    if (ambient) ambient.color.set('#fef5ee')
  }
}, { immediate: false })

function setupLighting() {
  // Ambient — generous warm fill, keeps character clearly visible
  scene.add(new THREE.AmbientLight('#fef5ee', 2.2))

  // Key Light（主光）— 右上方45°，bright warm white
  const key = new THREE.DirectionalLight('#fff5eb', 3.8)
  key.position.set(3, 4, 5)
  key.castShadow = true
  key.shadow.mapSize.set(1024, 1024)
  key.shadow.camera.near = 0.5
  key.shadow.camera.far = 15
  key.shadow.camera.left = -3
  key.shadow.camera.right = 3
  key.shadow.camera.top = 3
  key.shadow.camera.bottom = -3
  key.shadow.bias = -0.0001
  scene.add(key)

  // Fill Light（补光）— left fill for shadow softness
  const fill = new THREE.DirectionalLight('#e8f0ff', 0.9)
  fill.position.set(-2.5, 1.5, -1.5)
  scene.add(fill)

  // Rim Light（轮廓光）— strong back light for clear silhouette
  const rim = new THREE.DirectionalLight('#c8d6ff', 2.0)
  rim.position.set(0, 2.5, -3.5)
  scene.add(rim)

  // Bottom bounce — slight upward fill
  const bounce = new THREE.DirectionalLight('#ffe4cc', 0.2)
  bounce.position.set(0, -0.5, 1.5)
  scene.add(bounce)
}

const pointer = new THREE.Vector2()

function flashHighlight(target: 'bubble') {
  highlightTarget = target
  highlightStart = Date.now()
}

function onPointerDown(event: PointerEvent) {
  if (!containerRef.value) return
  markInteraction()
  const rect = containerRef.value.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)

  // Check bubble first
  if (bubbleGroup) {
    const bubbleHits = raycaster.intersectObjects(bubbleGroup.children, true)
    if (bubbleHits.length > 0) {
      flashHighlight('bubble')
      setTimeout(() => emit('open-chat'), HIGHLIGHT_DURATION)
      return
    }
  }

  // Click on panda anywhere → open chat
  emit('open-chat')
}

function onPointerMove(event: PointerEvent) {
  if (!containerRef.value) return
  markInteraction()
  const rect = containerRef.value.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)

  // Check bubble for pointer cursor
  if (bubbleGroup) {
    const bubbleHits = raycaster.intersectObjects(bubbleGroup.children, true)
    if (bubbleHits.length > 0) { containerRef.value.style.cursor = 'pointer'; return }
  }
  containerRef.value.style.cursor = 'grab'
}

function updateGreetingBubblePos() {
  if (!greetingText.value || !bubbleGroup || !camera || !containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  const worldPos = new THREE.Vector3()
  bubbleGroup.getWorldPosition(worldPos)
  // Offset slightly above the cloud
  worldPos.y += 0.08
  const projected = worldPos.clone().project(camera)
  greetingPos.value = {
    x: (projected.x * 0.5 + 0.5) * rect.width,
    y: (-projected.y * 0.5 + 0.5) * rect.height,
  }
}

function animate() {
  animationId = requestAnimationFrame(animate)
  const time = Date.now() * 0.001

  // Panda gentle idle breathing — scale body slightly
  const pandaGroup = (scene as any).__pandaGroup as THREE.Group | undefined
  if (pandaGroup) {
    const breath = 1 + Math.sin(time * 1.5) * 0.008
    pandaGroup.scale.setScalar(breath)
  }

  // Bubble gentle bob
  if (bubbleGroup) {
    bubbleGroup.position.y = 0.60 + Math.sin(time * 1.2) * 0.008
  }

  // Highlight flash animation
  if (highlightTarget) {
    const elapsed = Date.now() - highlightStart
    if (elapsed < HIGHLIGHT_DURATION) {
      const t = elapsed / HIGHLIGHT_DURATION
      const intensity = Math.max(0, 1 - t) * 1.5
      bubbleGroup?.traverse(child => {
        if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial) {
          child.material.emissive.set('#10b981')
          child.material.emissiveIntensity = intensity
        }
      })
    } else {
      // Reset emissive
      bubbleGroup?.traverse(child => {
        if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial) {
          const isBadge = child.material.color.getHex() === 0x10b981
          child.material.emissive.set(isBadge ? '#10b981' : '#ffffff')
          child.material.emissiveIntensity = isBadge ? 0.4 : 0.15
        }
      })
      highlightTarget = null
    }
  }

  // 眨眼效果 — 使用 isPandaEye 标记
  const blinkScale = blinkState.value === 1 ? 0.05 : 1
  const eyeMeshes = (scene as any).__pandaEyeMeshes as THREE.Mesh[] | undefined
  if (eyeMeshes) {
    eyeMeshes.forEach(m => { m.scale.y = blinkScale })
  }

  controls.update()
  updateGreetingBubblePos()
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

onMounted(() => {
  if (!containerRef.value) return
  const { width, height } = containerRef.value.getBoundingClientRect()
  scene = new THREE.Scene()
  scene.background = new THREE.Color('#ede8e2')

  // 检查当前暗色模式
  if (isDarkMode.value) {
    scene.background = new THREE.Color('#1a1a2e')
  }

  camera = new THREE.PerspectiveCamera(36, width / height, 0.1, 20)
  camera.position.set(0, 0.30, 2.8)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.8
  containerRef.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0.25, 0)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 1.5
  controls.maxDistance = 4.5
  controls.minPolarAngle = Math.PI / 2
  controls.maxPolarAngle = Math.PI / 2
  controls.autoRotate = true
  controls.autoRotateSpeed = 0.5
  controls.update()

  // 生成环境贴图（让金属材质有真实反射）
  const pmremGenerator = new THREE.PMREMGenerator(renderer)
  pmremGenerator.compileEquirectangularShader()

  // 用简单渐变色创建环境贴图
  const envCanvas = document.createElement('canvas')
  envCanvas.width = 256
  envCanvas.height = 128
  const ctx = envCanvas.getContext('2d')!
  const gradient = ctx.createLinearGradient(0, 0, 0, 128)
  gradient.addColorStop(0, '#ede8e2')    // 顶部暖米色
  gradient.addColorStop(0.5, '#ddd5cc')  // 中部
  gradient.addColorStop(1, '#c8c0b8')    // 底部
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, 256, 128)
  const envTexture = new THREE.CanvasTexture(envCanvas)
  envTexture.mapping = THREE.EquirectangularReflectionMapping

  const envMap = pmremGenerator.fromEquirectangular(envTexture).texture
  scene.environment = envMap
  scene.background = new THREE.Color('#ede8e2')

  envTexture.dispose()
  pmremGenerator.dispose()

  raycaster = new THREE.Raycaster()
  setupLighting()
  buildPanda()

  containerRef.value.addEventListener('pointerdown', onPointerDown)
  containerRef.value.addEventListener('pointermove', onPointerMove)
  window.addEventListener('resize', onResize)
  startIdleGreeting()
  scheduleBlink()
  animate()
})

onUnmounted(() => {
  cancelAnimationFrame(animationId)
  stopIdleGreeting()
  if (blinkCooldown) clearTimeout(blinkCooldown)
  containerRef.value?.removeEventListener('pointerdown', onPointerDown)
  containerRef.value?.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('resize', onResize)
  controls?.dispose()
  renderer?.dispose()
  // Clean up bubble
  if (bubbleGroup) bubbleGroup.traverse(c => {
    if (c instanceof THREE.Mesh) { c.geometry.dispose(); (c.material as THREE.Material).dispose() }
  })
})

</script>

<template>
  <div class="relative w-full h-full min-h-[320px]">
    <div ref="containerRef" class="w-full h-full rounded-2xl overflow-hidden cursor-grab active:cursor-grabbing" />
    <!-- Greeting bubble overlay -->
    <Transition name="greeting">
      <div
        v-if="greetingText"
        class="absolute pointer-events-none z-10"
        :style="{ left: greetingPos.x + 'px', top: greetingPos.y + 'px', transform: 'translate(-50%, -100%)' }"
      >
        <div class="relative bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 text-xs leading-relaxed px-3 py-2 rounded-xl shadow-lg border border-gray-100 dark:border-gray-700 max-w-[180px] whitespace-normal">
          {{ greetingText }}
          <!-- Speech bubble tail pointing down -->
          <div class="absolute -bottom-[6px] left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-white dark:border-t-gray-800" />
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.greeting-enter-active { transition: all 0.3s ease-out; }
.greeting-leave-active { transition: all 0.25s ease-in; }
.greeting-enter-from { opacity: 0; transform: translate(-50%, -90%) scale(0.9); }
.greeting-leave-to { opacity: 0; transform: translate(-50%, -90%) scale(0.9); }
</style>
