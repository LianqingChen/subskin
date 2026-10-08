// 白斑标注编辑器（MaskEditor / MaskEditorToolbar）交互回归。
// 用编译后的 SFC setup 与模板渲染做静态断言：不启动浏览器、不使用任何患者照片。
//
// 运行: node --test tests/frontend/mask-editor-tools.cjs
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const path = require('node:path')

// 组件 setup 会创建 ResizeObserver / 访问 document；Node 环境补最小桩件。
globalThis.ResizeObserver = globalThis.ResizeObserver || class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.document = globalThis.document || {
  addEventListener() {},
  removeEventListener() {},
  createElement: () => ({ getContext: () => null, style: {} }),
  body: { style: {} },
}

const appRequire = createRequire(path.resolve('web/app/package.json'))
const vue = appRequire('vue')
const { parse, compileScript, compileTemplate } = appRequire('@vue/compiler-sfc')
const ts = appRequire('typescript')

function evaluate(source, requireFn) {
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const exports = {}
  new Function('exports', 'require', output)(exports, requireFn || ((name) => {
    throw new Error('Unexpected dependency: ' + name)
  }))
  return exports
}

function read(rel) {
  return readFileSync(path.resolve('web/app/src/components/tracker', rel), 'utf8')
}

function loadSfc(rel) {
  const descriptor = parse(read(rel)).descriptor
  const script = compileScript(descriptor, { id: rel })
  const component = evaluate(script.content, (name) => {
    if (name === 'vue') return vue
    if (name.endsWith('.vue')) return { __esModule: true, default: { name: path.basename(name) } }
    if (name === '@/composables/useRemoteMaskSelection') return { useRemoteMaskSelection: () => ({ pending: vue.ref(false), select: async () => {} }) }
    if (name === '@/composables/useToast') {
      return { useToast: () => ({ show() {}, success() {}, warning() {}, error() {} }) }
    }
    if (name === '@/utils/maskMeasurement') return evaluate(readFileSync(path.resolve('web/app/src/utils/maskMeasurement.ts'), 'utf8'))
    if (name === '@/utils/lesionMaskTools') {
      return {
        buildEdgeMap: () => ({ width: 0, height: 0, data: new Float32Array(0) }),
        magicWandSelect: () => new Uint8Array(0),
        refineLesionMask: (i, e, m) => m,
        paintMask: () => 0,
        readMask: () => new Uint8Array(0),
      }
    }
    throw new Error('Unexpected dependency: ' + name)
  }).default
  const template = compileTemplate({
    source: descriptor.template.content,
    id: rel,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(template.errors, [])
  return { component, template, source: read(rel) }
}

// ── 工具栏 ────────────────────────────────────────────────────────────────

test('工具栏暴露智能选斑 / 边缘吸附 / 清空白斑 / 重做', () => {
  const { component } = loadSfc('MaskEditorToolbar.vue')
  const props = vue.reactive({
    tool: 'lesion-brush',
    brushSize: 32,
    canUndo: false,
    canRedo: false,
    fullscreen: false,
    wandTolerance: 30,
    snapping: false,
  })
  const events = []
  const state = component.setup(props, {
    emit: (name, ...args) => events.push([name, ...args]),
    expose() {},
  })
  const tools = state.TOOLS.map((t) => t.id)
  assert.deepEqual(tools, ['magic-wand', 'lesion-brush', 'skin-brush', 'exclude', 'eraser'])
  state.setTool('magic-wand')
  assert.deepEqual(events.at(-1), ['update:tool', 'magic-wand'])
})

test('工具栏渲染出边缘吸附与清空按钮', () => {
  const { template } = loadSfc('MaskEditorToolbar.vue')
  assert.match(template.code, /snapEdges/)
  assert.match(template.code, /clearLesion/)
  assert.match(template.code, /wandTolerance/)
})

// ── 编辑器脚本 ────────────────────────────────────────────────────────────

test('编辑器暴露魔法棒 / 边缘吸附 / 清空处理函数并返回给模板', () => {
  const { component } = loadSfc('MaskEditor.vue')
  const state = component.setup({ imageUrl: 'x', editable: true }, { emit() {}, expose() {} })
  for (const fn of ['runMagicWand', 'snapEdges', 'clearLesionLayer', 'onWandTolerance', 'onToolChange', 'confirmMasks']) {
    assert.equal(typeof state[fn], 'function', `setup 应返回 ${fn}`)
  }
  assert.equal(typeof state.wandTolerance.value, 'number')
})

test('浅色工具不自动扩大皮肤分母，排除工具单独提供', () => {
  const src = read('MaskEditor.vue')
  assert.doesNotMatch(src, /lesion-brush' && skinCanvasRef\.value\)/)
  assert.match(src, /allowedMask: readMask\(skin\)/)
  assert.match(src, /tool\.value === 'exclude' && skinCanvasRef\.value/)
})

test('编辑器模板把新工具透传给工具栏并更新引导文案', () => {
  const src = read('MaskEditor.vue')
  assert.match(src, /:wand-tolerance="wandTolerance"/)
  assert.match(src, /@snap-edges="snapEdges"/)
  assert.match(src, /@clear-lesion="clearLesionLayer"/)
  assert.match(src, /@update:wand-tolerance="onWandTolerance"/)
  assert.match(src, /:snapping="isSnapping"/)
  assert.match(src, /智能选斑/)
})

test('编辑器未确认前不提交评估修正（交互精修只创建私有临时任务）', () => {
  const src = read('MaskEditor.vue')
  assert.doesNotMatch(src, /localStorage\.(setItem|removeItem|clear)/)
  assert.doesNotMatch(src, /sessionStorage\.(setItem|removeItem|clear)/)
})
