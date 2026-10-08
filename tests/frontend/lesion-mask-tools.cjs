// 白斑标注工具（浏览器端逐像素算法）回归测试。
// 全部使用合成图像，不依赖浏览器、网络或任何患者数据。
//
// 运行: node --test tests/frontend/lesion-mask-tools.cjs
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const path = require('node:path')

const appRequire = createRequire(path.resolve('web/app/package.json'))
const ts = appRequire('typescript')

/** 用 TypeScript 编译器把工具模块转成 CommonJS 后求值。 */
function loadTools() {
  const src = readFileSync('web/app/src/utils/lesionMaskTools.ts', 'utf8')
  const out = ts.transpileModule(src, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const exports = {}
  new Function('exports', 'module', out)(exports, { exports })
  return exports
}

const tools = loadTools()

const W = 200
const H = 200
const CX = 100
const CY = 100
const R = 45

/** 带横向光照梯度的肤色背景 + 中央低色素白斑；返回 { img, truth }。 */
function synthetic(radius = R) {
  const data = new Uint8ClampedArray(W * H * 4)
  const truth = new Uint8Array(W * H)
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const p = y * W + x
      const i = p * 4
      const t = 0.8 + 0.4 * (x / W)
      data[i] = 205 * t
      data[i + 1] = 165 * t
      data[i + 2] = 140 * t
      data[i + 3] = 255
      if ((y - CY) ** 2 + (x - CX) ** 2 <= radius * radius) {
        data[i] = 233
        data[i + 1] = 227
        data[i + 2] = 223
        truth[p] = 1
      }
    }
  }
  return { img: { width: W, height: H, data }, truth }
}

function dice(a, b) {
  let inter = 0
  let sa = 0
  let sb = 0
  for (let p = 0; p < a.length; p++) {
    if (a[p] && b[p]) inter++
    if (a[p]) sa++
    if (b[p]) sb++
  }
  return sa + sb === 0 ? 1 : (2 * inter) / (sa + sb)
}

/** 检出边界的像素到真实圆周的平均距离（px） */
function edgeDistance(mask, radius) {
  let sum = 0
  let n = 0
  for (let y = 1; y < H - 1; y++) {
    for (let x = 1; x < W - 1; x++) {
      const p = y * W + x
      if (!mask[p]) continue
      const isEdge = !(mask[p - 1] && mask[p + 1] && mask[p - W] && mask[p + W])
      if (!isEdge) continue
      sum += Math.abs(Math.hypot(x - CX, y - CY) - radius)
      n++
    }
  }
  return n ? sum / n : 0
}

test('buildEdgeMap 在色差边界处取到极值', () => {
  const { img } = synthetic()
  const edge = tools.buildEdgeMap(img)
  let onEdge = 0
  let onEdgeN = 0
  let inside = 0
  let insideN = 0
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const r = Math.hypot(x - CX, y - CY)
      if (r > R - 3 && r < R + 3) { onEdge += edge.data[y * W + x]; onEdgeN++ }
      if (r < R - 15) { inside += edge.data[y * W + x]; insideN++ }
    }
  }
  assert.ok(onEdge / onEdgeN > 8 * (inside / insideN), '边界梯度应显著高于白斑内部')
})

test('magicWandSelect 点一下即可圈出白斑范围', () => {
  const { img, truth } = synthetic()
  const edge = tools.buildEdgeMap(img)
  const sel = tools.magicWandSelect(img, edge, CX, CY, { tolerance: 30 })
  assert.ok(dice(sel, truth) > 0.9, `dice 应 > 0.9，实际 ${dice(sel, truth)}`)
  assert.ok(edgeDistance(sel, R) < 3, '选中边界应贴合真实白斑边缘')
})

test('magicWandSelect 不会沿平缓光照渐变吞掉整片皮肤', () => {
  const data = new Uint8ClampedArray(W * H * 4)
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4
      const t = 0.8 + 0.4 * (x / W)
      data[i] = 205 * t
      data[i + 1] = 165 * t
      data[i + 2] = 140 * t
      data[i + 3] = 255
    }
  }
  const img = { width: W, height: H, data }
  const edge = tools.buildEdgeMap(img)
  const sel = tools.magicWandSelect(img, edge, CX, CY, { tolerance: 8 })
  let count = 0
  for (let p = 0; p < sel.length; p++) if (sel[p]) count++
  assert.ok(count / (W * H) < 0.35, `低容差下不应吞掉大面积皮肤，实际 ${(100 * count / (W * H)).toFixed(1)}%`)
})

test('refineLesionMask 把过大边界吸附回真实色差处', () => {
  const { img, truth } = synthetic()
  const edge = tools.buildEdgeMap(img)
  const coarse = new Uint8Array(W * H)
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      if ((y - CY) ** 2 + (x - CX) ** 2 <= (R + 12) ** 2) coarse[y * W + x] = 1
    }
  }
  const before = dice(coarse, truth)
  const beforeDist = edgeDistance(coarse, R)
  const refined = tools.refineLesionMask(img, edge, coarse, { tolerance: 30 })
  const after = dice(refined, truth)
  const afterDist = edgeDistance(refined, R)

  assert.ok(after > before + 0.1, `吸附后 dice 应明显提升：${before} → ${after}`)
  assert.ok(afterDist < beforeDist * 0.4, `边界偏差应显著下降：${beforeDist} → ${afterDist}`)
})

test('refineLesionMask 对空掩膜安全', () => {
  const { img } = synthetic()
  const edge = tools.buildEdgeMap(img)
  const empty = new Uint8Array(W * H)
  const out = tools.refineLesionMask(img, edge, empty)
  assert.equal(out.length, empty.length)
  assert.ok(out.every((v) => v === 0))
})

test('medianFilter 去除孤立噪点', () => {
  const mask = new Uint8Array(W * H)
  mask[5 * W + 5] = 1
  for (let y = 50; y < 60; y++) for (let x = 50; x < 60; x++) mask[y * W + x] = 1
  const out = tools.medianFilter(mask, W, H)
  assert.equal(out[5 * W + 5], 0, '孤立单点应被抹掉')
  assert.equal(out[55 * W + 55], 1, '实心块应保留')
})
