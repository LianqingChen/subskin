/**
 * 小白管家 3D 形象的程序化建模（Three.js 无外部模型文件，零下载、秒加载）：
 * - 金斑蝶（默认）：呼应品牌 Logo 的橙色蝴蝶——CanvasTexture 手绘金斑蝶纹样
 *   （品牌橙渐变 + 黑色翅脉 + 黑色宽边 + 白色斑点列），黑色天鹅绒身体 + 环节白点 + 触角；
 *   解剖结构：身体躺在翅平面内（头朝局部 +Y），翅绕身体纵轴（Y）拍动，
 *   整体后仰约 60° 呈俯视 3/4 视角——翅尖越过背部/压向腹面的弧线拍击 + 透视缩短；
 * - 梅花鹿：奶栗色圆身 + 背部梅花状白斑 + 大眼高光/腮红/微笑 + 弧形小鹿角 + 摆耳/点头/甩尾；
 * 均返回归一化前的模型组与 animate 动画闭包（t 秒，state 心情/飞行/拖拽）。
 */
import type * as ThreeNS from 'three'

export type Creature3DModule = typeof import('three')

export interface Creature3DState {
  mood: 'idle' | 'happy' | 'thinking' | 'greeting'
  flying: boolean
  dragging: boolean
}

export interface Creature3D {
  group: ThreeNS.Group
  animate: (s: number, state: Creature3DState) => void
}

/* ─────────────────── 金斑蝶 ─────────────────── */

/** 品牌色板（与 Logo 同源，按白底按钮对比度加深）：金斑蝶深橙 + 近黑墨色 */
const ORANGE_LIGHT = '#ffa85c'
const ORANGE_MAIN = '#f97316'
const ORANGE_DEEP = '#d94e08'
const INK = '#241a14'
const CREAM = '#fffdf6'

function paintWing(THREE: Creature3DModule, kind: 'fore' | 'hind'): ThreeNS.CanvasTexture {
  const S = 512
  const cv = document.createElement('canvas')
  cv.width = cv.height = S
  const ctx = cv.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D context unavailable')

  // 底色：翅根亮橙 → 翅缘深橙（径向渐变，中心在翅根/左中）
  const g = ctx.createRadialGradient(S * 0.08, S * 0.5, S * 0.04, S * 0.45, S * 0.5, S * 0.8)
  g.addColorStop(0, ORANGE_LIGHT)
  g.addColorStop(0.5, ORANGE_MAIN)
  g.addColorStop(1, ORANGE_DEEP)
  ctx.fillStyle = g
  ctx.fillRect(0, 0, S, S)

  // 翅脉：从翅根放射的黑色弧线
  ctx.strokeStyle = INK
  ctx.lineCap = 'round'
  const veins = kind === 'fore' ? 7 : 6
  for (let i = 0; i < veins; i++) {
    const a = -Math.PI * 0.08 + (i / (veins - 1)) * Math.PI * 0.98
    const len = S * (kind === 'fore' ? 0.98 : 0.88) * (1 - 0.28 * Math.abs(i / (veins - 1) - 0.5))
    ctx.lineWidth = 7
    ctx.beginPath()
    ctx.moveTo(S * 0.06, S * 0.5)
    ctx.quadraticCurveTo(
      S * 0.06 + Math.cos(a) * len * 0.55,
      S * 0.5 + Math.sin(a) * len * 0.55 - S * 0.03,
      S * 0.06 + Math.cos(a) * len,
      S * 0.5 + Math.sin(a) * len,
    )
    ctx.stroke()
  }

  // 黑色宽边：前翅=顶缘+外缘；后翅=外缘+下缘
  ctx.lineWidth = 46
  ctx.beginPath()
  if (kind === 'fore') {
    ctx.moveTo(S * 0.02, S * 0.32)
    ctx.quadraticCurveTo(S * 0.36, S * 0.02, S * 0.84, S * 0.05)
    ctx.quadraticCurveTo(S * 1.02, S * 0.32, S * 0.8, S * 0.88)
  } else {
    ctx.moveTo(S * 0.86, S * 0.12)
    ctx.quadraticCurveTo(S * 1.04, S * 0.5, S * 0.82, S * 0.9)
    ctx.quadraticCurveTo(S * 0.42, S * 1.06, S * 0.03, S * 0.74)
  }
  ctx.stroke()

  // 白色斑点列（沿黑边内侧）
  ctx.fillStyle = CREAM
  const dots: [number, number][] =
    kind === 'fore'
      ? [[0.17, 0.1], [0.34, 0.055], [0.52, 0.045], [0.7, 0.065], [0.86, 0.14], [0.945, 0.31], [0.925, 0.5], [0.84, 0.68]]
      : [[0.925, 0.29], [0.9, 0.47], [0.835, 0.63], [0.72, 0.77], [0.56, 0.86], [0.38, 0.91], [0.2, 0.85]]
  for (const [dx, dy] of dots) {
    ctx.beginPath()
    ctx.arc(dx * S, dy * S, S * 0.025, 0, Math.PI * 2)
    ctx.fill()
  }

  const tex = new THREE.CanvasTexture(cv)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 4
  return tex
}

/** 把 ShapeGeometry 的 uv 从形状坐标归一化到 0~1（按包围盒） */
function normalizeShapeUV(geo: ThreeNS.ShapeGeometry) {
  geo.computeBoundingBox()
  const bb = geo.boundingBox
  if (!bb) return
  const uv = geo.getAttribute('uv')
  const pos = geo.getAttribute('position')
  const sx = Math.max(bb.max.x - bb.min.x, 1e-6)
  const sy = Math.max(bb.max.y - bb.min.y, 1e-6)
  for (let i = 0; i < uv.count; i++) {
    uv.setXY(i, (pos.getX(i) - bb.min.x) / sx, (pos.getY(i) - bb.min.y) / sy)
  }
  uv.needsUpdate = true
}

export function buildButterfly(THREE: Creature3DModule): Creature3D {
  // root = 动画容器（位移/转身/侧倾）；model = 姿态容器（整体后仰，俯视 3/4 视角）
  const root = new THREE.Group()
  const model = new THREE.Group()
  model.rotation.x = -1.05
  root.add(model)

  const wingMat = (kind: 'fore' | 'hind') =>
    new THREE.MeshStandardMaterial({
      map: paintWing(THREE, kind),
      side: THREE.DoubleSide,
      roughness: 0.55,
      metalness: 0,
      emissive: new THREE.Color(ORANGE_MAIN),
      emissiveIntensity: 0.06,
    })

  const foreShape = new THREE.Shape()
  foreShape.moveTo(0, 0)
  foreShape.quadraticCurveTo(0.35, 0.52, 0.95, 0.6)
  foreShape.quadraticCurveTo(1.1, 0.26, 0.88, -0.12)
  foreShape.quadraticCurveTo(0.5, -0.3, 0, -0.14)
  foreShape.lineTo(0, 0)
  const hindShape = new THREE.Shape()
  hindShape.moveTo(0, 0.12)
  hindShape.quadraticCurveTo(0.55, 0.3, 0.72, -0.05)
  hindShape.quadraticCurveTo(0.82, -0.44, 0.4, -0.6)
  hindShape.quadraticCurveTo(0.05, -0.72, 0, -0.34)
  hindShape.lineTo(0, 0.12)

  const foreGeo = new THREE.ShapeGeometry(foreShape, 24)
  const hindGeo = new THREE.ShapeGeometry(hindShape, 24)
  normalizeShapeUV(foreGeo)
  normalizeShapeUV(hindGeo)

  const makeWingSet = () => {
    const set = new THREE.Group()
    const fore = new THREE.Mesh(foreGeo, wingMat('fore'))
    fore.position.z = 0.02
    const hind = new THREE.Mesh(hindGeo, wingMat('hind'))
    hind.position.z = -0.02
    set.add(fore, hind)
    return { set, fore, hind }
  }
  const R = makeWingSet()
  const L = makeWingSet()
  L.set.scale.x = -1
  model.add(R.set, L.set)

  // 身体躺在翅平面内（头朝 +Y），与真实蝴蝶解剖一致
  const bodyMat = new THREE.MeshStandardMaterial({ color: 0x2e211a, roughness: 0.85 })
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.075, 0.42, 6, 12), bodyMat)
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.095, 16, 12), bodyMat)
  head.position.y = 0.36
  model.add(body, head)

  // 触角：从头顶斜向上外侧，端部球杆
  for (const side of [-1, 1]) {
    const antenna = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.009, 0.28, 6), bodyMat)
    antenna.position.set(side * 0.06, 0.5, 0.02)
    antenna.rotation.z = -side * 0.55
    const club = new THREE.Mesh(new THREE.SphereGeometry(0.02, 8, 6), bodyMat)
    club.position.set(side * 0.135, 0.61, 0.02)
    model.add(antenna, club)
  }
  const dotMat = new THREE.MeshStandardMaterial({ color: CREAM, roughness: 0.6 })
  for (let i = 0; i < 5; i++) {
    for (const side of [-1, 1]) {
      const dot = new THREE.Mesh(new THREE.SphereGeometry(0.013, 6, 5), dotMat)
      dot.position.set(side * 0.052, -0.02 - i * 0.06, 0.045)
      model.add(dot)
    }
  }

  // 拍翅：绕身体纵轴（局部 Y）转动——翅尖抬过背部（+）或压向腹面（−），
  // 右翅取负角、左翅同角（set 已镜像 scale.x=-1，镜像自动同步两侧）
  const setFlap = (foreA: number, hindA: number) => {
    R.fore.rotation.y = -foreA
    L.fore.rotation.y = foreA
    R.hind.rotation.y = -hindA
    L.hind.rotation.y = hindA
  }
  setFlap(0.6, 0.55) // 初始上举（用于归一化包围盒）

  const animate = (s: number, st: Creature3DState) => {
    let speed = 5.5
    let amp = 0.5
    let bias = 0.22
    if (st.dragging || st.flying) {
      speed = st.dragging ? 22 : 15
      amp = 0.5
      bias = 0.3
    } else if (st.mood === 'greeting') {
      speed = 4.5
      amp = 0.6
      bias = 0.4
    } else if (st.mood === 'happy') {
      speed = 10.5
      amp = 0.45
      bias = 0.35
    } else if (st.mood === 'thinking') {
      speed = 2.4
      amp = 0.3
      bias = 0.3
    }
    const t = s * speed
    // 非对称拍翅（下拍快、上抬慢）+ 前后翅近同步（真实金斑蝶前后翅联动，仅轻微滞后）
    const flapWave = (x: number) => Math.sin(x) - 0.22 * Math.sin(2 * x)
    setFlap(bias + flapWave(t) * amp, bias + flapWave(t - 0.12) * amp * 0.92)

    root.position.y = Math.sin(s * 2.2) * 0.045 + (st.mood === 'happy' ? Math.abs(Math.sin(s * 3)) * 0.09 : 0)
    if (st.dragging || st.flying) root.rotation.y = s * 2.6
    else root.rotation.y = Math.sin(s * 0.85) * 0.14
    root.rotation.z = st.mood === 'thinking' ? Math.sin(s * 1.1) * 0.16 : Math.sin(s * 1.7) * 0.05
  }
  return { group: root, animate }
}

/* ─────────────────── 梅花鹿 ─────────────────── */

export function buildDeer(THREE: Creature3DModule): Creature3D {
  const root = new THREE.Group()
  const furMat = new THREE.MeshStandardMaterial({ color: 0xd6955a, roughness: 0.9 })
  const creamMat = new THREE.MeshStandardMaterial({ color: 0xf9efe0, roughness: 0.95 })
  const darkMat = new THREE.MeshStandardMaterial({ color: 0x4a352a, roughness: 0.6 })
  const hornMat = new THREE.MeshStandardMaterial({ color: 0xe3cfa9, roughness: 0.5 })
  const blushMat = new THREE.MeshStandardMaterial({ color: 0xf2b3ac, roughness: 0.9 })
  const whiteMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.25 })

  // 身体（奶栗色椭圆球，圆润不臃肿）+ 奶油胸腹
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.42, 28, 20), furMat)
  body.scale.set(0.92, 0.8, 0.72)
  body.position.y = 0.66
  root.add(body)
  const chest = new THREE.Mesh(new THREE.SphereGeometry(0.24, 18, 14), creamMat)
  chest.position.set(0, 0.56, 0.22)
  chest.scale.set(0.85, 0.75, 0.62)
  root.add(chest)

  // 背部梅花白斑（上半个椭球面散布的小圆斑，大小略有变化）
  const a = 0.42 * 0.92
  const b = 0.42 * 0.8
  const c = 0.42 * 0.72
  const spots: [number, number, number][] = [
    [24, 34, 1], [66, 27, 0.85], [108, 38, 1], [152, 30, 0.9], [198, 37, 1], [242, 29, 0.85], [286, 40, 1], [330, 34, 0.9],
    [88, 52, 0.8], [170, 50, 0.9], [256, 54, 0.8], [348, 49, 0.9],
    [130, 62, 0.75], [300, 63, 0.75], [172, 68, 0.7], [226, 66, 0.7],
  ]
  spots.forEach(([deg, phiDeg, size], i) => {
    const th = (deg * Math.PI) / 180
    const ph = (phiDeg * Math.PI) / 180
    const spot = new THREE.Mesh(new THREE.SphereGeometry(0.042 * size + (i % 3) * 0.003, 10, 8), creamMat)
    spot.position.set(
      a * Math.sin(ph) * Math.cos(th) * 0.99,
      0.66 + b * Math.cos(ph) * 0.99,
      c * Math.sin(ph) * Math.sin(th) * 0.99,
    )
    root.add(spot)
  })

  // 头部组（点头/歪头动画作用于此）——大头小身的幼鹿比例
  const headG = new THREE.Group()
  headG.position.set(0, 1.06, 0.34)
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.27, 24, 18), furMat)
  const muzzle = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 12), creamMat)
  muzzle.position.set(0, -0.08, 0.19)
  muzzle.scale.set(0.82, 0.66, 0.95)
  const nose = new THREE.Mesh(new THREE.SphereGeometry(0.045, 10, 8), darkMat)
  nose.position.set(0, -0.045, 0.32)
  nose.scale.set(1, 0.8, 0.7)
  headG.add(head, muzzle, nose)

  // 大眼睛 + 高光 + 腮红 + 微笑（弧环贴出口鼻轮廓）
  for (const side of [-1, 1]) {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.05, 12, 10), darkMat)
    eye.position.set(side * 0.145, 0.07, 0.225)
    const spark = new THREE.Mesh(new THREE.SphereGeometry(0.018, 8, 6), whiteMat)
    spark.position.set(side * 0.131, 0.084, 0.263)
    const blush = new THREE.Mesh(new THREE.SphereGeometry(0.05, 10, 8), blushMat)
    blush.position.set(side * 0.205, -0.06, 0.17)
    blush.scale.set(1, 0.62, 0.55)
    headG.add(eye, spark, blush)
  }
  const smile = new THREE.Mesh(new THREE.TorusGeometry(0.034, 0.008, 6, 12, Math.PI * 0.85), darkMat)
  smile.position.set(0, -0.132, 0.318)
  smile.rotation.z = Math.PI * 1.075
  headG.add(smile)

  // 耳朵（叶形扁球 + 奶油内耳，可摆动）
  const ears: ThreeNS.Group[] = []
  for (const side of [-1, 1]) {
    const ear = new THREE.Group()
    ear.position.set(side * 0.2, 0.2, -0.04)
    const leaf = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 10), furMat)
    leaf.scale.set(0.55, 1, 0.35)
    leaf.position.set(side * 0.06, 0.1, 0)
    leaf.rotation.z = -side * 0.5
    const inner = new THREE.Mesh(new THREE.SphereGeometry(0.075, 10, 8), creamMat)
    inner.scale.set(0.5, 1, 0.3)
    inner.position.set(side * 0.055, 0.095, 0.03)
    inner.rotation.z = -side * 0.5
    ear.add(leaf, inner)
    headG.add(ear)
    ears.push(ear)
  }
  // 小鹿角（弧形主枝 + 两根分叉，左右对称）
  for (const side of [-1, 1]) {
    const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.013, 0.02, 0.26, 8), hornMat)
    beam.position.set(side * 0.13, 0.36, -0.06)
    beam.rotation.z = -side * 0.38
    beam.rotation.x = 0.28
    const tineA = new THREE.Mesh(new THREE.CylinderGeometry(0.009, 0.013, 0.14, 6), hornMat)
    tineA.position.set(side * 0.165, 0.4, 0.02)
    tineA.rotation.z = -side * 0.55
    tineA.rotation.x = -0.25
    const tineB = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.012, 0.13, 6), hornMat)
    tineB.position.set(side * 0.185, 0.47, -0.1)
    tineB.rotation.z = -side * 0.3
    tineB.rotation.x = 0.15
    headG.add(beam, tineA, tineB)
  }
  root.add(headG)

  // 四条小短腿 + 深色蹄
  const legs: ThreeNS.Mesh[] = []
  for (const [sx, sz] of [[-1, 1], [1, 1], [-1, -1], [1, -1]] as const) {
    const leg = new THREE.Mesh(new THREE.CapsuleGeometry(0.048, 0.25, 4, 10), furMat)
    leg.position.set(sx * 0.17, 0.17, sz * 0.2)
    const hoof = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.056, 0.07, 10), darkMat)
    hoof.position.set(leg.position.x, 0.035, leg.position.z)
    root.add(leg, hoof)
    legs.push(leg)
  }

  // 尾巴（奶油绒球，可甩动）
  const tailG = new THREE.Group()
  tailG.position.set(0, 0.84, -0.31)
  const tail = new THREE.Mesh(new THREE.SphereGeometry(0.095, 12, 10), creamMat)
  tail.scale.set(0.9, 0.9, 0.8)
  tailG.add(tail)
  root.add(tailG)

  const animate = (s: number, st: Creature3DState) => {
    root.position.y = Math.sin(s * 2.1) * 0.035 + (st.mood === 'happy' ? Math.abs(Math.sin(s * 5.2)) * 0.11 : 0)
    root.scale.setScalar(1 + Math.sin(s * 2.1) * 0.01)
    if (st.dragging || st.flying) {
      root.rotation.y = s * 3.2
    } else {
      root.rotation.y = 0.28 + Math.sin(s * 0.7) * 0.12
    }
    // 腿部：蹦跳/开心时交替轻摆，静态时几乎不动，让整体更灵动
    const legKick = st.mood === 'happy' || st.dragging ? Math.sin(s * 11) * 0.12 : Math.sin(s * 2.1) * 0.02
    legs.forEach((leg, i) => { leg.rotation.x = (i % 2 === 0 ? legKick : -legKick) * 0.6 })
    // 点头 / 思考歪头
    if (st.mood === 'thinking') {
      headG.rotation.z = 0.2 + Math.sin(s * 1.2) * 0.06
      headG.rotation.x = 0.12
    } else if (st.mood === 'greeting') {
      headG.rotation.z = 0
      headG.rotation.x = Math.sin(s * 3.5) * 0.14
    } else {
      headG.rotation.z = Math.sin(s * 1.4) * 0.05
      headG.rotation.x = Math.sin(s * 1.8) * 0.06
    }
    // 耳朵偶尔抖动
    const twitch = Math.max(0, Math.sin(s * 0.85) - 0.82) * Math.sin(s * 38) * 1.4
    ears[0].rotation.z = twitch
    ears[1].rotation.z = -twitch
    // 甩尾巴
    const wagSpeed = st.mood === 'happy' || st.dragging ? 11 : 6.5
    tailG.rotation.z = Math.sin(s * wagSpeed) * 0.35
  }
  return { group: root, animate }
}
