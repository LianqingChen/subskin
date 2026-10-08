/**
 * 白斑标注工具集 —— 浏览器端「逐像素颜色 + 邻域色差」算法。
 *
 * 与后端 `vasi_edge_segmentation` 同源思路，但跑在标注画布上，用于**即时交互**：
 *   1. `buildEdgeMap`         —— 对 L / a* / b* 做 Sobel，得到相邻像素颜色差异图；
 *   2. `magicWandSelect`      —— 点击白斑做边缘感知区域生长：
 *                                颜色接近「已选区均值」且未跨过强边缘才继续扩散；
 *   3. `refineLesionMask`     —— 离散水平集式的边缘吸附：
 *                                边界像素比较「更像白斑」还是「更像周围皮肤」，
 *                                逐步扩张/收缩到真实色差过渡处；
 *   4. `paintMask`            —— 把结果掩膜合并进标注层。
 *
 * 全部为纯函数，无 Vue 依赖，便于单测与复用。
 */

/** 邻域色差图（Sobel 梯度幅值）。 */
export interface EdgeMap {
  width: number
  height: number
  data: Float32Array
}

export interface MagicWandOptions {
  /** Growth may not leave the reviewed skin region. */
  allowedMask?: Uint8Array
  /** 颜色容差 0-100（越大选得越多） */
  tolerance?: number
  /** 边缘停止强度 0-100（越大越容易越过边缘） */
  edgeSensitivity?: number
  /** 最大像素数保护 */
  limit?: number
}

export interface RefineOptions {
  allowedMask?: Uint8Array
  /** 迭代次数（扩张/收缩轮数） */
  iterations?: number
  /** 颜色容差 0-100 */
  tolerance?: number
  /** 边缘停止强度 0-100 */
  edgeSensitivity?: number
  /** 每次迭代最多改动多少像素（保护性能与大图） */
  maxShiftPerIteration?: number
}

/** 逐像素 LAB 近似特征：亮度 + 两个对立色通道。 */
function toFeatures(img: ImageData) {
  const n = img.width * img.height
  const d = img.data
  const lum = new Float32Array(n)
  const ca = new Float32Array(n)
  const cb = new Float32Array(n)
  for (let p = 0, i = 0; p < n; p++, i += 4) {
    const r = d[i]
    const g = d[i + 1]
    const b = d[i + 2]
    lum[p] = 0.299 * r + 0.587 * g + 0.114 * b
    ca[p] = r - g
    cb[p] = 0.5 * (r + g) - b
  }
  return { lum, ca, cb, n }
}

const SOBEL_X = [-1, 0, 1, -2, 0, 2, -1, 0, 1]
const SOBEL_Y = [-1, -2, -1, 0, 0, 0, 1, 2, 1]

/**
 * 计算邻域色差图（相邻像素颜色差异）。
 * 亮度权重最高（人眼对亮度差最敏感），a/b 通道各 0.8。
 */
export function buildEdgeMap(img: ImageData): EdgeMap {
  const { width: w, height: h } = img
  const { lum, ca, cb, n } = toFeatures(img)
  const edge = new Float32Array(n)
  const wsum = 1 + 0.8 + 0.8
  for (let y = 1; y < h - 1; y++) {
    const row = y * w
    for (let x = 1; x < w - 1; x++) {
      let gxl = 0, gyl = 0
      let gxa = 0, gya = 0
      let gxb = 0, gyb = 0
      for (let k = 0; k < 9; k++) {
        const idx = (y + ((k / 3) | 0) - 1) * w + x + (k % 3) - 1
        const kx = SOBEL_X[k]
        const ky = SOBEL_Y[k]
        gxl += lum[idx] * kx
        gyl += lum[idx] * ky
        gxa += ca[idx] * kx
        gya += ca[idx] * ky
        gxb += cb[idx] * kx
        gyb += cb[idx] * ky
      }
      const v =
        (gxl * gxl + gyl * gyl) +
        0.64 * (gxa * gxa + gya * gya) +
        0.64 * (gxb * gxb + gyb * gyb)
      edge[row + x] = Math.sqrt(v) / wsum
    }
  }
  return { width: w, height: h, data: edge }
}

function colorDist(
  d: Uint8ClampedArray, p: number,
  r: number, g: number, b: number,
): number {
  const i = p * 4
  const dr = d[i] - r
  const dg = d[i + 1] - g
  const db = d[i + 2] - b
  return Math.sqrt(dr * dr + dg * dg + db * db)
}

/**
 * 边缘感知区域生长（魔法棒）。
 *
 * 与普通魔棒的区别：比较对象是**已接受区域的均值**（而不是单个种子像素），
 * 因此白斑内部的渐变不会被中途判停；同时在跨过强边缘时立即停止，
 * 保证不会把相邻的正常皮肤/背景一并吞进来。
 *
 * @returns 0/1 掩膜（Uint8Array，长度 = w*h）
 */
export function magicWandSelect(
  img: ImageData,
  edgeMap: EdgeMap,
  seedX: number,
  seedY: number,
  opts: MagicWandOptions = {},
): Uint8Array {
  const { width: w, height: h } = img
  const n = w * h
  const out = new Uint8Array(n)
  const sx = Math.max(0, Math.min(w - 1, Math.round(seedX)))
  const sy = Math.max(0, Math.min(h - 1, Math.round(seedY)))
  const seed = sy * w + sx
  if (opts.allowedMask && (opts.allowedMask.length !== n || !opts.allowedMask[seed])) return out
  const d = img.data

  const tolerance = (opts.tolerance ?? 30) * 0.9
  const edgeStop = (100 - (opts.edgeSensitivity ?? 50)) * 0.36
  const limit = opts.limit ?? n
  // 与种子的距离上限：防止沿平缓渐变「一路爬走」把整片皮肤吞进来
  const seedLimit = tolerance * 2.2

  const seedR = d[seed * 4]
  const seedG = d[seed * 4 + 1]
  const seedB = d[seed * 4 + 2]
  let meanR = seedR
  let meanG = seedG
  let meanB = seedB
  let count = 0

  const stack: number[] = [seed]
  out[seed] = 1
  count = 1

  while (stack.length > 0) {
    const p = stack.pop() as number
    const px = p % w
    const py = (p / w) | 0
    // 增量更新均值，使生长对内部渐变不敏感
    const i = p * 4
    meanR += (d[i] - meanR) / count
    meanG += (d[i + 1] - meanG) / count
    meanB += (d[i + 2] - meanB) / count

    for (let k = 0; k < 4; k++) {
      const nx = px + (k === 0 ? -1 : k === 1 ? 1 : 0)
      const ny = py + (k === 2 ? -1 : k === 3 ? 1 : 0)
      if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue
      const q = ny * w + nx
      if (out[q] || (opts.allowedMask && !opts.allowedMask[q])) continue
      if (edgeStop > 0 && edgeMap.data[q] > edgeStop) continue
      if (colorDist(d, q, meanR, meanG, meanB) > tolerance) continue
      if (colorDist(d, q, seedR, seedG, seedB) > seedLimit) continue
      out[q] = 1
      count++
      if (count >= limit) return out
      stack.push(q)
    }
  }
  return out
}

/** 掩膜内部（离边界 ≥ inner 像素）的平均颜色——比整段掩膜均值更能代表白斑本色。 */
function interiorMean(
  d: Uint8ClampedArray, mask: Uint8Array, w: number, h: number, inner = 2,
) {
  let r = 0
  let g = 0
  let b = 0
  let c = 0
  for (let y = inner; y < h - inner; y++) {
    for (let x = inner; x < w - inner; x++) {
      const p = y * w + x
      if (!mask[p]) continue
      let allIn = true
      for (let dy = -inner; dy <= inner && allIn; dy++) {
        for (let dx = -inner; dx <= inner; dx++) {
          if (!mask[(y + dy) * w + x + dx]) { allIn = false; break }
        }
      }
      if (!allIn) continue
      const i = p * 4
      r += d[i]
      g += d[i + 1]
      b += d[i + 2]
      c++
    }
  }
  if (c === 0) return null
  return { r: r / c, g: g / c, b: b / c, count: c }
}

/** 掩膜外侧环带（outer 距离内）的平均颜色 = 周围皮肤/背景。 */
function ringMean(
  d: Uint8ClampedArray, mask: Uint8Array, w: number, h: number, outer = 4, allowedMask?: Uint8Array,
) {
  let r = 0
  let g = 0
  let b = 0
  let c = 0
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const p = y * w + x
      if (mask[p] || (allowedMask && !allowedMask[p])) continue
      let near = false
      for (let dy = -outer; dy <= outer && !near; dy++) {
        const ny = y + dy
        if (ny < 0 || ny >= h) continue
        for (let dx = -outer; dx <= outer; dx++) {
          const nx = x + dx
          if (nx < 0 || nx >= w) continue
          if (mask[ny * w + nx]) { near = true; break }
        }
      }
      if (!near) continue
      const i = p * 4
      r += d[i]
      g += d[i + 1]
      b += d[i + 2]
      c++
    }
  }
  if (c === 0) return null
  return { r: r / c, g: g / c, b: b / c, count: c }
}

/**
 * 边缘吸附：把标注边界收敛到真实色差过渡处。
 *
 * 每轮迭代做两件事：
 *   扩张 — 掩膜外沿像素如果「更像白斑均值」则并入；
 *   收缩 — 掩膜边界像素如果「更像周围皮肤均值」则剔除。
 * 颜色判据带一个裕量（margin），避免在色差平缓处来回抖动；
 * 同时被邻域色差图约束，不会跨过真实边界。
 *
 * @returns 新的 0/1 掩膜
 */
export function refineLesionMask(
  img: ImageData,
  edgeMap: EdgeMap,
  mask: Uint8Array,
  opts: RefineOptions = {},
): Uint8Array {
  const { width: w, height: h } = img
  const n = w * h
  const iterations = opts.iterations ?? 10
  const tolerance = (opts.tolerance ?? 30) * 1.2
  const edgeStop = (100 - (opts.edgeSensitivity ?? 50)) * 0.5
  const maxShift = opts.maxShiftPerIteration ?? Math.max(2000, Math.round(n * 0.02))
  const d = img.data

  let cur = mask.slice()
  if (opts.allowedMask) {
    if (opts.allowedMask.length !== n) return new Uint8Array(n)
    for (let p = 0; p < n; p++) if (!opts.allowedMask[p]) cur[p] = 0
  }
  if (cur.every((v) => v === 0)) return cur

  for (let it = 0; it < iterations; it++) {
    const lesion = interiorMean(d, cur, w, h, 2)
    const bg = ringMean(d, cur, w, h, 4, opts.allowedMask)
    if (!lesion || !bg) break

    const next = cur.slice()
    let shifted = 0

    // ── 扩张 ──
    for (let p = 0; p < n && shifted < maxShift; p++) {
      if (cur[p] || (opts.allowedMask && !opts.allowedMask[p])) continue
      const px = p % w
      const py = (p / w) | 0
      let adjacent = false
      if (px > 0 && cur[p - 1]) adjacent = true
      else if (px < w - 1 && cur[p + 1]) adjacent = true
      else if (py > 0 && cur[p - w]) adjacent = true
      else if (py < h - 1 && cur[p + w]) adjacent = true
      if (!adjacent) continue
      if (edgeStop > 0 && edgeMap.data[p] > edgeStop) continue
      const dl = colorDist(d, p, lesion.r, lesion.g, lesion.b)
      const db = colorDist(d, p, bg.r, bg.g, bg.b)
      if (dl + tolerance * 0.1 < db) {
        next[p] = 1
        shifted++
      }
    }

    // ── 收缩 ──
    for (let p = 0; p < n && shifted < maxShift; p++) {
      if (!cur[p]) continue
      const px = p % w
      const py = (p / w) | 0
      let adjacentBg = false
      if (px > 0 && !cur[p - 1]) adjacentBg = true
      else if (px < w - 1 && !cur[p + 1]) adjacentBg = true
      else if (py > 0 && !cur[p - w]) adjacentBg = true
      else if (py < h - 1 && !cur[p + w]) adjacentBg = true
      if (!adjacentBg) continue
      const dl = colorDist(d, p, lesion.r, lesion.g, lesion.b)
      const db = colorDist(d, p, bg.r, bg.g, bg.b)
      if (db + tolerance * 0.1 < dl) {
        next[p] = 0
        shifted++
      }
    }

    cur = next
    if (shifted === 0) break
  }

  return medianFilter(cur, w, h)
}

/** 3×3 中值滤波，去除吸附后的孤立噪点。 */
export function medianFilter(mask: Uint8Array, w: number, h: number): Uint8Array {
  const out = new Uint8Array(mask.length)
  const buf: number[] = []
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      buf.length = 0
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const nx = x + dx
          const ny = y + dy
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue
          buf.push(mask[ny * w + nx])
        }
      }
      buf.sort((a, b) => a - b)
      out[y * w + x] = buf[(buf.length / 2) | 0]
    }
  }
  return out
}

/** 把掩膜合并进画布（仅设置 alpha，颜色由调用方给定）。 */
export function paintMask(
  ctx: CanvasRenderingContext2D,
  mask: Uint8Array,
  w: number,
  h: number,
  color: string,
  erase = false,
): number {
  const img = ctx.getImageData(0, 0, w, h)
  const d = img.data
  let changed = 0
  const rgba = parseColor(color)
  for (let p = 0; p < w * h; p++) {
    if (!mask[p]) continue
    const i = p * 4
    if (erase) {
      d[i + 3] = 0
    } else {
      d[i] = rgba[0]
      d[i + 1] = rgba[1]
      d[i + 2] = rgba[2]
      d[i + 3] = 255
    }
    changed++
  }
  ctx.putImageData(img, 0, 0)
  return changed
}

function parseColor(color: string): [number, number, number] {
  const m = color.match(/rgba?\(([^)]+)\)/)
  if (!m) return [255, 255, 255]
  const parts = m[1].split(',').map((v) => parseFloat(v.trim()))
  return [parts[0] || 0, parts[1] || 0, parts[2] || 0]
}

/** 从画布读取掩膜（alpha > 32 记为选中）。 */
export function readMask(canvas: HTMLCanvasElement): Uint8Array {
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return new Uint8Array(canvas.width * canvas.height)
  const d = ctx.getImageData(0, 0, canvas.width, canvas.height).data
  const out = new Uint8Array(canvas.width * canvas.height)
  for (let p = 0, i = 3; p < out.length; p++, i += 4) {
    if (d[i] > 32) out[p] = 1
  }
  return out
}
