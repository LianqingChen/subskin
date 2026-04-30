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

const props = defineProps<{
  assessments: Record<string, AssessmentSnapshot | null>
}>()

const emit = defineEmits<{
  'select-part': [part: string]
  'open-chat': []
  'open-report': []
}>()

const containerRef = ref<HTMLDivElement>()
let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let controls: OrbitControls
let raycaster: THREE.Raycaster
let animationId = 0
let torsoMesh: THREE.Mesh | null = null
let torsoBaseScale = new THREE.Vector3(1, 1, 0.72)

// Interactive objects
let bubbleGroup: THREE.Group | null = null
let stethoscopeGroup: THREE.Group | null = null

// Highlight flash state
let highlightTarget: 'bubble' | 'stethoscope' | null = null
let highlightStart = 0
const HIGHLIGHT_DURATION = 500 // ms

// Idle greeting state
const IDLE_MESSAGES = [
  '点击我身上的部位，可以评估白斑情况哦~',
  '想问问关于白癜风的问题？点击旁边的对话气泡~',
  '上传体检报告，我帮你解读关键指标~',
  '左右滑动可以旋转查看我哦~',
  '有白斑问题随时问我，我一直在~',
]
let hasGreeted = false
let lastInteractionTime = Date.now()
let idleTimer: ReturnType<typeof setInterval> | null = null
let greetingIndex = 0

// Greeting bubble overlay state
const greetingText = ref('')
const greetingPos = ref({ x: 0, y: 0 })
let greetingTimeout: ReturnType<typeof setTimeout> | null = null

const partGroups = new Map<string, THREE.Group>()
const partMaterials = new Map<string, THREE.MeshStandardMaterial[]>()
const outlineMeshes = new Map<string, THREE.Mesh[]>()

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

const baseSkin = new THREE.Color('#E8C9A0')
const whiteColor = new THREE.Color('#FAF5F0')
const unassessedColor = new THREE.Color('#C8BFB8')

function skinMat(color?: THREE.Color): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color: color || baseSkin,
    roughness: 0.55,
    metalness: 0.0,
  })
}

function mesh(geo: THREE.BufferGeometry, pos: [number, number, number], key: string, opts?: { rotZ?: number; scale?: [number, number, number] }): THREE.Mesh {
  const m = new THREE.Mesh(geo, skinMat())
  m.position.set(...pos)
  if (opts?.rotZ) m.rotation.z = opts.rotZ
  if (opts?.scale) m.scale.set(...opts.scale)
  m.userData.partKey = key
  return m
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

function buildHumanoid() {
  const S = 24

  // ── HEAD ──
  const headGroup = new THREE.Group()
  headGroup.name = 'face'
  const headGeo = new THREE.SphereGeometry(0.105, 32, 24)
  const hp = headGeo.attributes.position
  for (let i = 0; i < hp.count; i++) {
    let x = hp.getX(i), y = hp.getY(i), z = hp.getZ(i)
    // Chin: taper gently
    if (y < -0.03) {
      const t = Math.min(1, (-y - 0.03) / 0.075)
      x *= 1 - t * 0.25
      z *= 1 - t * 0.12
      if (z > 0) z += t * 0.010
    }
    // Nose bump: subtler
    if (z > 0.08 && y > -0.01 && y < 0.04) z += 0.012
    // Cheeks: slight fullness
    if (Math.abs(x) > 0.06 && y > -0.02 && y < 0.04 && z > 0.02) z += 0.005
    hp.setX(i, x); hp.setY(i, y); hp.setZ(i, z)
  }
  hp.needsUpdate = true
  headGeo.computeVertexNormals()

  const headMs: THREE.Mesh[] = []
  const headMain = mesh(headGeo, [0, 0.88, 0], 'face')
  headGroup.add(headMain)
  headMs.push(headMain)

  // Ears — slightly larger, rounder, more visible
  for (const sx of [-1, 1]) {
    const ear = mesh(new THREE.SphereGeometry(0.024, 10, 10), [sx * 0.10, 0.87, -0.01], 'face', { scale: [0.55, 1.0, 0.75] })
    headGroup.add(ear)
    headMs.push(ear)
  }

  // Eyes — bigger, cuter, with iris highlights
  const eyeWhiteMat = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.3 })
  const irisMat = new THREE.MeshStandardMaterial({ color: '#3d2b1f', roughness: 0.2, metalness: 0.15 })
  const pupilMat = new THREE.MeshStandardMaterial({ color: '#1a1a1a', roughness: 0.1 })
  const highlightMat = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.1, emissive: '#ffffff', emissiveIntensity: 0.5 })
  for (const sx of [-1, 1]) {
    // White
    const ewMesh = new THREE.Mesh(new THREE.SphereGeometry(0.018, 14, 10), eyeWhiteMat)
    ewMesh.scale.set(1.2, 0.85, 0.5)
    ewMesh.position.set(sx * 0.036, 0.895, 0.093)
    ewMesh.userData.partKey = 'face'
    headGroup.add(ewMesh)
    headMs.push(ewMesh)
    // Iris (colored, bigger)
    const iris = new THREE.Mesh(new THREE.SphereGeometry(0.010, 10, 8), irisMat)
    iris.position.set(sx * 0.036, 0.895, 0.105)
    iris.userData.partKey = 'face'
    headGroup.add(iris)
    headMs.push(iris)
    // Pupil
    const pupil = new THREE.Mesh(new THREE.SphereGeometry(0.005, 8, 6), pupilMat)
    pupil.position.set(sx * 0.036, 0.895, 0.110)
    pupil.userData.partKey = 'face'
    headGroup.add(pupil)
    headMs.push(pupil)
    // Highlight dot (cute sparkle)
    const hl = new THREE.Mesh(new THREE.SphereGeometry(0.003, 6, 4), highlightMat)
    hl.position.set(sx * 0.033, 0.898, 0.112)
    hl.userData.partKey = 'face'
    headGroup.add(hl)
    headMs.push(hl)
  }

  // Eyebrows — softer, thinner, more natural arc
  const browMat = new THREE.MeshStandardMaterial({ color: '#5c4033', roughness: 0.6 })
  for (const sx of [-1, 1]) {
    const browCurve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(sx * -0.02, 0, 0),
      new THREE.Vector3(0, 0.004, 0.001),
      new THREE.Vector3(sx * 0.02, -0.001, 0),
    )
    const browGeo = new THREE.TubeGeometry(browCurve, 10, 0.003, 6, false)
    const browMesh = new THREE.Mesh(browGeo, browMat)
    browMesh.position.set(sx * 0.036, 0.918, 0.096)
    browMesh.rotation.z = sx * -0.05
    browMesh.userData.partKey = 'face'
    headGroup.add(browMesh)
    headMs.push(browMesh)
  }

  // Nose — softer, smaller bump
  const noseMat = new THREE.MeshStandardMaterial({ color: '#ddb896', roughness: 0.55 })
  const noseMesh = new THREE.Mesh(new THREE.SphereGeometry(0.010, 10, 8), noseMat)
  noseMesh.scale.set(0.9, 1.0, 0.7)
  noseMesh.position.set(0, 0.872, 0.102)
  noseMesh.userData.partKey = 'face'
  headGroup.add(noseMesh)
  headMs.push(noseMesh)

  // Mouth — gentle smile curve, softer color
  const mouthCurve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(-0.018, 0, 0),
    new THREE.Vector3(0, 0.005, 0.003),
    new THREE.Vector3(0.018, 0, 0),
  )
  const mouthGeo = new THREE.TubeGeometry(mouthCurve, 12, 0.003, 6, false)
  const mouthMat = new THREE.MeshStandardMaterial({ color: '#c47a6c', roughness: 0.45 })
  const mouthMesh = new THREE.Mesh(mouthGeo, mouthMat)
  mouthMesh.position.set(0, 0.848, 0.094)
  mouthMesh.userData.partKey = 'face'
  headGroup.add(mouthMesh)
  headMs.push(mouthMesh)

  // Blush cheeks — subtle warm spheres
  const blushMat = new THREE.MeshStandardMaterial({ color: '#f0b8a8', roughness: 0.7, transparent: true, opacity: 0.35 })
  for (const sx of [-1, 1]) {
    const blush = new THREE.Mesh(new THREE.SphereGeometry(0.018, 10, 8), blushMat)
    blush.position.set(sx * 0.055, 0.870, 0.08)
    blush.scale.set(1.2, 0.7, 0.3)
    blush.userData.partKey = 'face'
    headGroup.add(blush)
    headMs.push(blush)
  }

  registerPart('face', headGroup, headMs)

  // ── NECK ──
  const neckGroup = new THREE.Group()
  neckGroup.name = 'neck'
  const neckM = mesh(new THREE.CylinderGeometry(0.046, 0.058, 0.10, S), [0, 0.76, 0], 'neck')
  neckGroup.add(neckM)
  registerPart('neck', neckGroup, [neckM])

  // ── TORSO ──
  const torsoGroup = new THREE.Group()
  torsoGroup.name = 'trunk'
  const profile = [
    new THREE.Vector2(0.00, 0.70), new THREE.Vector2(0.08, 0.70),
    new THREE.Vector2(0.19, 0.67), new THREE.Vector2(0.21, 0.62),
    new THREE.Vector2(0.19, 0.55), new THREE.Vector2(0.16, 0.48),
    new THREE.Vector2(0.13, 0.38), new THREE.Vector2(0.14, 0.33),
    new THREE.Vector2(0.17, 0.28), new THREE.Vector2(0.16, 0.23),
    new THREE.Vector2(0.00, 0.23),
  ]
  torsoMesh = mesh(new THREE.LatheGeometry(profile, 32), [0, 0, 0], 'trunk', { scale: [1, 1, 0.72] })
  torsoBaseScale = torsoMesh.scale.clone()
  torsoGroup.add(torsoMesh)
  registerPart('trunk', torsoGroup, [torsoMesh])

  // ── ARMS ──
  const armsGroup = new THREE.Group()
  armsGroup.name = 'arms'
  const armMs: THREE.Mesh[] = []
  for (const s of [-1, 1]) {
    armMs.push(mesh(new THREE.SphereGeometry(0.055, S, S / 2), [s * 0.20, 0.66, 0], 'arms'))
    armMs.push(mesh(new THREE.CapsuleGeometry(0.044, 0.20, 8, S), [s * 0.24, 0.55, 0], 'arms', { rotZ: s * 0.10 }))
    armMs.push(mesh(new THREE.CapsuleGeometry(0.037, 0.20, 8, S), [s * 0.27, 0.32, 0], 'arms', { rotZ: s * 0.05 }))
  }
  armMs.forEach(m => armsGroup.add(m))
  registerPart('arms', armsGroup, armMs)

  // ── HANDS ──
  const handsGroup = new THREE.Group()
  handsGroup.name = 'hands'
  const handMs: THREE.Mesh[] = []
  for (const s of [-1, 1]) {
    handMs.push(mesh(new THREE.SphereGeometry(0.038, 12, 10), [s * 0.30, 0.10, 0], 'hands', { scale: [0.85, 1.15, 0.50] }))
    for (const fz of [0.022, 0, -0.022]) handMs.push(mesh(new THREE.CapsuleGeometry(0.009, 0.042, 4, 8), [s * 0.30, 0.04, fz], 'hands'))
    handMs.push(mesh(new THREE.CapsuleGeometry(0.011, 0.028, 4, 8), [s * 0.275, 0.09, 0.018], 'hands', { rotZ: s * -0.3 }))
  }
  handMs.forEach(m => handsGroup.add(m))
  registerPart('hands', handsGroup, handMs)

  // ── LEGS ──
  const legsGroup = new THREE.Group()
  legsGroup.name = 'legs'
  const legMs: THREE.Mesh[] = []
  for (const s of [-1, 1]) {
    legMs.push(mesh(new THREE.CapsuleGeometry(0.063, 0.24, 8, S), [s * 0.09, 0.06, 0], 'legs'))
    legMs.push(mesh(new THREE.SphereGeometry(0.052, S, S / 2), [s * 0.085, -0.08, 0], 'legs'))
    legMs.push(mesh(new THREE.CapsuleGeometry(0.046, 0.26, 8, S), [s * 0.085, -0.32, 0], 'legs'))
  }
  legMs.forEach(m => legsGroup.add(m))
  registerPart('legs', legsGroup, legMs)

  // ── FEET ──
  const feetGroup = new THREE.Group()
  feetGroup.name = 'feet'
  const footMs: THREE.Mesh[] = []
  for (const s of [-1, 1]) footMs.push(mesh(new THREE.SphereGeometry(0.055, 16, 12), [s * 0.09, -0.49, 0.04], 'feet', { scale: [0.72, 0.32, 1.35] }))
  footMs.forEach(m => feetGroup.add(m))
  registerPart('feet', feetGroup, footMs)

  // ── PLATFORM ──
  const platGeo = new THREE.CylinderGeometry(0.32, 0.35, 0.015, 32)
  const isDark = isDarkMode.value
  const platMat = new THREE.MeshStandardMaterial({ color: isDark ? '#2a2a3e' : '#e8e2dc', roughness: 0.85, metalness: 0.05 })
  const plat = new THREE.Mesh(platGeo, platMat)
  plat.position.y = -0.555
  plat.receiveShadow = true
  scene.add(plat)

  // ── AI SPEECH BUBBLE (3D cloud, right side of head) ──
  buildSpeechBubble()

  // ── STETHOSCOPE (around neck) ──
  buildStethoscope()
}

function buildSpeechBubble() {
  bubbleGroup = new THREE.Group()
  // Position: right side of head, near mouth level
  bubbleGroup.position.set(0.22, 0.94, 0.08)

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

function buildStethoscope() {
  stethoscopeGroup = new THREE.Group()
  stethoscopeGroup.position.set(0, 0.72, 0)

  const tubeMat = new THREE.MeshStandardMaterial({ color: '#4b5563', roughness: 0.3, metalness: 0.4 })
  const metalMat = new THREE.MeshStandardMaterial({ color: '#c0c0c0', roughness: 0.15, metalness: 0.85 })
  const chestPieceMat = new THREE.MeshStandardMaterial({ color: '#d4d4d8', roughness: 0.1, metalness: 0.9, emissive: '#d4d4d8', emissiveIntensity: 0.05 })

  // ── Main tube: loops around back of neck, both sides come down to chest piece ──
  // Continuous curve: left ear → over back of neck → right ear → Y-merge → down to chest piece
  const mainTubePath = new THREE.CatmullRomCurve3([
    // Left ear tip (up and to the left)
    new THREE.Vector3(-0.06, 0.10, 0.03),
    // Left side of neck
    new THREE.Vector3(-0.08, 0.06, 0.0),
    // Behind neck (left)
    new THREE.Vector3(-0.06, 0.08, -0.07),
    // Behind neck (center)
    new THREE.Vector3(0, 0.09, -0.08),
    // Behind neck (right)
    new THREE.Vector3(0.06, 0.08, -0.07),
    // Right side of neck
    new THREE.Vector3(0.08, 0.06, 0.0),
    // Right ear tip
    new THREE.Vector3(0.06, 0.10, 0.03),
  ])
  const mainTube = new THREE.Mesh(new THREE.TubeGeometry(mainTubePath, 40, 0.005, 8, false), tubeMat)
  mainTube.userData.isStethoscope = true
  stethoscopeGroup.add(mainTube)

  // ── Stem tube: from center of neck loop down to chest piece ──
  const stemPath = new THREE.CatmullRomCurve3([
    // Start at front of neck
    new THREE.Vector3(0, 0.02, 0.06),
    // Curve down and slightly forward
    new THREE.Vector3(0, -0.04, 0.07),
    new THREE.Vector3(0, -0.10, 0.08),
    // End at chest piece
    new THREE.Vector3(0, -0.14, 0.09),
  ])
  const stemTube = new THREE.Mesh(new THREE.TubeGeometry(stemPath, 20, 0.005, 8, false), tubeMat)
  stemTube.userData.isStethoscope = true
  stethoscopeGroup.add(stemTube)

  // ── Ear tips (dark rubber) ──
  const earTipMat = new THREE.MeshStandardMaterial({ color: '#1f2937', roughness: 0.6, metalness: 0.05 })
  for (const sx of [-1, 1]) {
    const tip = new THREE.Mesh(new THREE.SphereGeometry(0.009, 10, 8), earTipMat)
    tip.position.set(sx * 0.06, 0.10, 0.03)
    tip.userData.isStethoscope = true
    stethoscopeGroup.add(tip)
  }

  // ── Spring connector (metal ring between ear tube and ear tip) ──
  for (const sx of [-1, 1]) {
    const spring = new THREE.Mesh(new THREE.TorusGeometry(0.007, 0.002, 6, 12), metalMat)
    spring.position.set(sx * 0.06, 0.095, 0.03)
    spring.userData.isStethoscope = true
    stethoscopeGroup.add(spring)
  }

  // ── Chest piece (the round disc) ──
  // Outer bell ring
  const bell = new THREE.Mesh(new THREE.CylinderGeometry(0.024, 0.026, 0.006, 24), chestPieceMat)
  bell.position.set(0, -0.15, 0.095)
  bell.rotation.x = 0.1
  bell.userData.isStethoscope = true
  stethoscopeGroup.add(bell)

  // Diaphragm face (flat disc, slightly different metal)
  const diaphragmMat = new THREE.MeshStandardMaterial({ color: '#e4e4e7', roughness: 0.05, metalness: 0.95 })
  const diaphragm = new THREE.Mesh(new THREE.CylinderGeometry(0.020, 0.020, 0.002, 24), diaphragmMat)
  diaphragm.position.set(0, -0.153, 0.097)
  diaphragm.rotation.x = 0.1
  diaphragm.userData.isStethoscope = true
  stethoscopeGroup.add(diaphragm)

  // Stem connector (metal piece between tube and bell)
  const stemConn = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.004, 0.020, 10), metalMat)
  stemConn.position.set(0, -0.13, 0.09)
  stemConn.rotation.x = 0.15
  stemConn.userData.isStethoscope = true
  stethoscopeGroup.add(stemConn)

  // ── Red cross on diaphragm ──
  const crossMat = new THREE.MeshStandardMaterial({ color: '#ef4444', roughness: 0.4, emissive: '#ef4444', emissiveIntensity: 0.2 })
  const crossH = new THREE.Mesh(new THREE.BoxGeometry(0.014, 0.004, 0.002), crossMat)
  crossH.position.set(0, -0.155, 0.10)
  crossH.rotation.x = 0.1
  crossH.userData.isStethoscope = true
  stethoscopeGroup.add(crossH)
  const crossV = new THREE.Mesh(new THREE.BoxGeometry(0.004, 0.014, 0.002), crossMat)
  crossV.position.set(0, -0.155, 0.10)
  crossV.rotation.x = 0.1
  crossV.userData.isStethoscope = true
  stethoscopeGroup.add(crossV)

  scene.add(stethoscopeGroup)
}

function registerPart(key: string, group: THREE.Group, meshes: THREE.Mesh[]) {
  scene.add(group)
  partGroups.set(key, group)
  const mats = new Set<THREE.MeshStandardMaterial>()
  meshes.forEach(m => { if (m.material instanceof THREE.MeshStandardMaterial) mats.add(m.material) })
  partMaterials.set(key, [...mats])
}

function getPartColor(part: string): THREE.Color {
  const a = props.assessments[part]
  if (!a) return unassessedColor.clone()
  return baseSkin.clone().lerp(whiteColor, Math.min(1, a.areaPercentage / 100))
}

const STAGE_COLORS: Record<string, string> = {
  '好转': '#22c55e', '稳定': '#eab308', '扩散': '#ef4444',
  '好转期': '#22c55e', '稳定期': '#eab308', '进展期': '#ef4444',
}

function updateOutlines() {
  for (const ms of outlineMeshes.values()) ms.forEach(m => { m.parent?.remove(m); m.geometry.dispose(); (m.material as THREE.Material).dispose() })
  outlineMeshes.clear()
  for (const [key, group] of partGroups) {
    const a = props.assessments[key]
    if (!a) continue
    const color = new THREE.Color(STAGE_COLORS[a.stage] || '#94a3b8')
    const outlines: THREE.Mesh[] = []
    group.children.forEach(child => {
      if (!(child instanceof THREE.Mesh) || child.userData.isOutline) return
      const oGeo = child.geometry.clone()
      const oMat = new THREE.MeshBasicMaterial({ color, wireframe: true, transparent: true, opacity: 0.6 })
      const oMesh = new THREE.Mesh(oGeo, oMat)
      oMesh.position.copy(child.position)
      oMesh.rotation.copy(child.rotation)
      oMesh.scale.copy(child.scale).multiplyScalar(1.06)
      oMesh.userData.isOutline = true
      oMesh.userData.baseScale = oMesh.scale.clone()
      group.add(oMesh)
      outlines.push(oMesh)
    })
    outlineMeshes.set(key, outlines)
  }
}

function refreshAllColors() {
  for (const [key, mats] of partMaterials) mats.forEach(m => m.color.copy(getPartColor(key)))
  updateOutlines()
}

// 暗色模式监听
watch(isDarkMode, (isDark) => {
  if (isDark) {
    scene.background = new THREE.Color('#1a1a2e')
    // 调整环境光色温
    const ambient = scene.children.find(c => c instanceof THREE.AmbientLight) as THREE.AmbientLight
    if (ambient) ambient.color.set('#2a2a3e')
  } else {
    scene.background = new THREE.Color('#f5f0eb')
    const ambient = scene.children.find(c => c instanceof THREE.AmbientLight) as THREE.AmbientLight
    if (ambient) ambient.color.set('#fef9f0')
  }
}, { immediate: false })

function setupLighting() {
  // Ambient — 基础暖光
  scene.add(new THREE.AmbientLight('#fef9f0', 1.0))

  // Key Light（主光）— 右上方45°，暖白
  const key = new THREE.DirectionalLight('#fff8f0', 3.0)
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

  // Fill Light（补光）— 左下方，冷白
  const fill = new THREE.DirectionalLight('#e8f0ff', 0.7)
  fill.position.set(-2.5, 1.5, -1.5)
  scene.add(fill)

  // Rim Light（轮廓光）— 后方上方，蓝紫调，让角色从背景弹出来
  const rim = new THREE.DirectionalLight('#c8d6ff', 1.4)
  rim.position.set(0, 2.5, -3.5)
  scene.add(rim)

  // Bottom bounce — 底部反光，减少过暗阴影
  const bounce = new THREE.DirectionalLight('#ffe8d0', 0.3)
  bounce.position.set(0, -0.5, 1.5)
  scene.add(bounce)
}

const pointer = new THREE.Vector2()

function flashHighlight(target: 'bubble' | 'stethoscope') {
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

  // Check bubble first (highest priority)
  if (bubbleGroup) {
    const bubbleHits = raycaster.intersectObjects(bubbleGroup.children, true)
    if (bubbleHits.length > 0) {
      flashHighlight('bubble')
      setTimeout(() => emit('open-chat'), HIGHLIGHT_DURATION)
      return
    }
  }

  // Check stethoscope next
  if (stethoscopeGroup) {
    const stethHits = raycaster.intersectObjects(stethoscopeGroup.children, true)
    if (stethHits.length > 0) {
      flashHighlight('stethoscope')
      setTimeout(() => emit('open-report'), HIGHLIGHT_DURATION)
      return
    }
  }

  // Check body parts last
  const targets: THREE.Object3D[] = []
  partGroups.forEach(g => targets.push(...g.children))
  const hits = raycaster.intersectObjects(targets, true)
  if (hits.length > 0) {
    let obj: THREE.Object3D | null = hits[0].object
    while (obj && !obj.userData.partKey && obj.parent) obj = obj.parent
    if (obj?.userData?.partKey) emit('select-part', obj.userData.partKey)
  }
}

function onPointerMove(event: PointerEvent) {
  if (!containerRef.value) return
  markInteraction()
  const rect = containerRef.value.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)

  // Check bubble & stethoscope for pointer cursor
  if (bubbleGroup) {
    const bubbleHits = raycaster.intersectObjects(bubbleGroup.children, true)
    if (bubbleHits.length > 0) { containerRef.value.style.cursor = 'pointer'; return }
  }
  if (stethoscopeGroup) {
    const stethHits = raycaster.intersectObjects(stethoscopeGroup.children, true)
    if (stethHits.length > 0) { containerRef.value.style.cursor = 'pointer'; return }
  }

  // Check body parts
  const targets: THREE.Object3D[] = []
  partGroups.forEach(g => targets.push(...g.children.filter(c => !(c as any).userData?.isOutline)))
  containerRef.value.style.cursor = raycaster.intersectObjects(targets, true).length > 0 ? 'pointer' : 'grab'
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
  if (torsoMesh) {
    const breath = 1 + Math.sin(time * 1.5) * 0.005
    torsoMesh.scale.set(torsoBaseScale.x * breath, torsoBaseScale.y, torsoBaseScale.z * breath)
  }
  // Bubble gentle bob
  if (bubbleGroup) {
    bubbleGroup.position.y = 0.96 + Math.sin(time * 1.2) * 0.008
  }
  // Stethoscope subtle sway on chest piece
  if (stethoscopeGroup) {
    // Tiny oscillation on the chest piece area
    stethoscopeGroup.rotation.z = Math.sin(time * 0.6) * 0.01
  }

  // Highlight flash animation
  if (highlightTarget) {
    const elapsed = Date.now() - highlightStart
    if (elapsed < HIGHLIGHT_DURATION) {
      const t = elapsed / HIGHLIGHT_DURATION
      // Ease out: strong flash then fade
      const intensity = Math.max(0, 1 - t) * 1.5
      const group = highlightTarget === 'bubble' ? bubbleGroup : stethoscopeGroup
      const emissiveColor = highlightTarget === 'bubble' ? '#10b981' : '#3b82f6'
      group?.traverse(child => {
        if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial) {
          child.material.emissive.set(emissiveColor)
          child.material.emissiveIntensity = intensity
        }
      })
    } else {
      // Reset emissive
      const group = highlightTarget === 'bubble' ? bubbleGroup : stethoscopeGroup
      group?.traverse(child => {
        if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial) {
          if (highlightTarget === 'bubble') {
            const isBadge = child.material.color.getHex() === 0x10b981
            child.material.emissive.set(isBadge ? '#10b981' : '#ffffff')
            child.material.emissiveIntensity = isBadge ? 0.4 : 0.15
          } else {
            // Stethoscope: restore per-part emissive
            const hex = child.material.color.getHex()
            if (hex === 0xef4444) {
              // Red cross
              child.material.emissive.set('#ef4444')
              child.material.emissiveIntensity = 0.2
            } else if (hex === 0xd1d5db) {
              // Chest piece metal
              child.material.emissive.set('#d1d5db')
              child.material.emissiveIntensity = 0.05
            } else {
              child.material.emissive.set('#000000')
              child.material.emissiveIntensity = 0.0
            }
          }
        }
      })
      highlightTarget = null
    }
  }

  for (const [partKey, outlines] of outlineMeshes) {
    const a = props.assessments[partKey]
    if (!a) continue
    const pulse = (a.stage === '扩散' || a.stage === '进展期') ? 1 + Math.sin(time * 3) * 0.04 : 1
    outlines.forEach(m => {
      const base = m.userData.baseScale as THREE.Vector3 | undefined
      if (base) m.scale.copy(base).multiplyScalar(pulse)
    })
  }
  // 眨眼效果 — 缩放眼睛Y轴
  const blinkScale = blinkState.value === 1 ? 0.05 : 1
  scene.traverse(child => {
    if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial) {
      // 找到眼球白色部分（通过颜色判断）
      if (child.material.color.getHex() === 0xffffff && child.geometry.type === 'SphereGeometry' && child.position.z > 0.09) {
        child.scale.y = blinkScale
      }
    }
  })

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
  scene.background = new THREE.Color('#f5f0eb')

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
  renderer.toneMappingExposure = 1.2
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
  gradient.addColorStop(0, '#f5f0eb')    // 顶部暖米色
  gradient.addColorStop(0.5, '#e8e0d8')  // 中部
  gradient.addColorStop(1, '#d5cdc5')    // 底部
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, 256, 128)
  const envTexture = new THREE.CanvasTexture(envCanvas)
  envTexture.mapping = THREE.EquirectangularReflectionMapping

  const envMap = pmremGenerator.fromEquirectangular(envTexture).texture
  scene.environment = envMap
  scene.background = new THREE.Color('#f5f0eb')

  envTexture.dispose()
  pmremGenerator.dispose()

  raycaster = new THREE.Raycaster()
  setupLighting()
  buildHumanoid()
  refreshAllColors()

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
  partMaterials.forEach(mats => mats.forEach(m => m.dispose()))
  partGroups.forEach(g => g.traverse(c => {
    if (c instanceof THREE.Mesh) {
      c.geometry.dispose()
      ;(Array.isArray(c.material) ? c.material : [c.material]).forEach((m: THREE.Material) => m.dispose())
    }
  }))
  outlineMeshes.forEach(ms => ms.forEach(m => { m.geometry.dispose(); (m.material as THREE.Material).dispose() }))
  // Clean up interactive groups
  for (const group of [bubbleGroup, stethoscopeGroup]) {
    if (group) group.traverse(c => {
      if (c instanceof THREE.Mesh) { c.geometry.dispose(); (c.material as THREE.Material).dispose() }
    })
  }
})

watch(() => props.assessments, () => refreshAllColors(), { deep: true })

function highlightPart(part: string | null) {
  partMaterials.forEach(mats => mats.forEach(m => m.emissive.set('#000000')))
  if (part) partMaterials.get(part)?.forEach(m => m.emissive.set('#332211'))
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
