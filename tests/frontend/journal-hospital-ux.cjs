// Component-state and rendered VNode regressions. No browser, network or patient data.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const path = require('node:path')
const appRequire = createRequire(path.resolve('web/app/package.json'))
const vue = appRequire('vue')
const { parse, compileScript, compileTemplate } = appRequire('@vue/compiler-sfc')
const ts = appRequire('typescript')
function evaluate(source) {
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
  const exports = {}
  new Function('exports', 'require', output)(exports, name => {
    if (name === 'vue') return { ...vue, withDirectives: vnode => vnode }
    if (name.endsWith('.vue')) return { __esModule: true, default: { name: path.basename(name) } }
    if (name === '@/utils/file-url') return { toProtectedFileUrl: value => value }
    if (name === 'vue-router') return { RouterLink: { name: 'RouterLink' }, useRoute: () => ({ query: {} }), useRouter: () => ({ push() {} }) }
    if (name.startsWith('@/')) return evaluate(readFileSync(path.resolve('web/app/src', name.slice(2) + '.ts'), 'utf8'))
    throw new Error('Unexpected dependency: ' + name)
  })
  return exports
}
function harness(file, initial) {
  const descriptor = parse(readFileSync('web/app/src/components/' + file, 'utf8')).descriptor
  const script = compileScript(descriptor, { id: file })
  const component = evaluate(script.content).default
  const template = compileTemplate({ source: descriptor.template.content, id: file, compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  const render = evaluate(template.code).render
  const props = vue.reactive(initial), events = []
  const state = component.setup(props, { expose() {}, emit(name, ...args) {
    events.push([name, ...args])
    if (name.startsWith('update:')) props[name.slice(7)] = args[0]
  } })
  return { props, state, events, render: () => render({}, [], props, vue.proxyRefs(state), {}, {}) }
}
function nodes(node) {
  if (!node || typeof node !== 'object') return []
  return [node, ...(Array.isArray(node.children) ? node.children.flatMap(nodes) : [])]
}
function text(node) {
  if (typeof node === 'string') return node
  if (!node || typeof node !== 'object') return ''
  return Array.isArray(node.children) ? node.children.map(text).join('') : typeof node.children === 'string' ? node.children : ''
}
function button(h, label) {
  const node = nodes(h.render()).find(node => node.type === 'button' && text(node).includes(label))
  assert.ok(node, 'Visible button: ' + label)
  return node
}
const hospital = { key: 'synthetic-a', name: '示例医院甲', province: '示例省', city: '示例市', district: '', address: '', features: [], stats: { reviewCount: 1, ratingCount: 0, ratingAvg: null } }
test('quick review can change an already selected hospital repeatedly', () => {
  const other = { ...hospital, key: 'synthetic-b', name: '示例医院乙' }
  const h = harness('hospitals/HospitalQuickReviewCta.vue', { selected: hospital, hospitals: [hospital, other], marks: {}, isLoggedIn: true, open: false })
  for (let i = 0; i < 2; i++) {
    button(h, '换一家').props.onClick()
    assert.ok(nodes(h.render()).some(n => n.type === 'input' && n.props.type === 'search'))
    h.state.query.value = '乙'
    button(h, '示例医院乙').props.onClick()
    assert.equal(h.props.open, false)
    assert.equal(h.events.filter(e => e[0] === 'pick').length, i + 1)
    assert.equal(h.events.filter(e => e[0] === 'write').length, 0)
  }
  button(h, '开始写评价').props.onClick()
  assert.equal(h.events.filter(e => e[0] === 'write').length, 1)
})
test('guest can choose a hospital before requesting to write', () => {
  const h = harness('hospitals/HospitalQuickReviewCta.vue', { selected: null, hospitals: [hospital], marks: {}, isLoggedIn: false, open: false })
  button(h, '选一家医院开始写').props.onClick()
  assert.equal(h.props.open, true)
  assert.equal(h.events.some(e => e[0] === 'login'), false)
})
function composer(target = 'hospital') { return harness('hospitals/HospitalReviewComposer.vue', { hospital, initialTarget: target, uploadImage: async () => null, publishing: false }) }
test('required doctor and treatment inputs are visible while optional fields stay closed', () => {
  for (const target of ['doctor', 'treatment']) {
    const h = composer(target)
    assert.equal(h.state.showMore.value, false)
    assert.ok(nodes(h.render()).some(n => n.type === 'input' && n.props.required !== undefined))
    assert.equal(h.state.valid.value, false)
    assert.match(text(h.render()), target === 'doctor' ? /请填写医生称呼/ : /请填写方案或用药名称/)
  }
})
test('writing enough text does not expand optional fields and does not require tags', async () => {
  const h = composer()
  h.state.form.value.content = '这是完全合成的就诊体验内容，仅用于组件回归检查。'
  await vue.nextTick()
  assert.equal(h.state.showMore.value, false)
  // v3：就医体验属敏感个人信息，未勾选单独同意前不可发布（PIPL 第 28/29 条）
  assert.equal(h.state.valid.value, false)
  assert.equal(h.state.healthConsent.value, false)
  assert.match(text(h.render()), /请先勾选同意公开你的就医体验/)
  h.state.healthConsent.value = true
  await vue.nextTick()
  assert.equal(h.state.valid.value, true)
  assert.equal(nodes(h.render()).some(n => n.type === 'input' && n.props.type === 'month'), false)
  assert.equal(button(h, '公开发布评价').props.disabled, false)
})
test('invalid review submission emits nothing; valid doctor review retains required name', async () => {
  const h = composer('doctor')
  h.state.form.value.content = '这是完全合成的就诊体验内容，仅用于组件回归检查。'
  h.state.submit()
  assert.equal(h.events.length, 0)
  h.state.form.value.doctorName = '示例称呼'
  h.state.healthConsent.value = true
  await vue.nextTick()
  h.state.submit()
  assert.equal(h.events[0][0], 'save')
  // 前端原样提交用户输入，脱敏由服务端落库时执行（前端只做发布前预览）
  assert.equal(h.events[0][1].doctorName, '示例称呼')
  assert.equal(h.events[0][1].healthConsent, true)
})

test('v3 命中疗效夸大时前端硬拦截且不发出 save', async () => {
  const h = composer()
  h.state.form.value.content = '这家医院把我的白斑根治了，效果很好我很满意。'
  h.state.healthConsent.value = true
  await vue.nextTick()
  assert.equal(h.state.risk.value.blocked, true)
  assert.equal(h.state.valid.value, false)
  h.state.submit()
  assert.equal(h.events.length, 0)
})

test('v3 结论性指控需要冷静确认后才可发布', async () => {
  const h = composer()
  h.state.form.value.content = '我觉得这家医院就是误诊，把我的病情耽误了。'
  h.state.healthConsent.value = true
  await vue.nextTick()
  assert.equal(h.state.riskNeedsAck.value, true)
  assert.equal(h.state.valid.value, false)
  h.state.riskAck.value = true
  await vue.nextTick()
  assert.equal(h.state.valid.value, true)
})

test('v3 医生姓名实时预览为脱敏称谓', async () => {
  const h = composer('doctor')
  h.state.form.value.doctorName = '张三丰'
  h.state.form.value.doctorDepartment = '皮肤科'
  await vue.nextTick()
  assert.equal(h.state.sanitizedDoctor.value, '张医生（皮肤科）')
})
test('third comparison selection preserves the original pair and explains the limit', () => {
  const h = harness('tracker/AssessmentRecords.vue', { items: [1,2,3].map(id => ({ id, bodySite: 'left_hand', date: '2026-09-10' })), loading: false, page: 1, totalPages: 1 })
  h.state.toggle(1)
  assert.match(text(h.render()), /已选 1 \/ 2/)
  h.state.toggle(2); h.state.toggle(3)
  assert.deepEqual([...h.state.selected.value], [1,2])
  assert.match(text(h.render()), /请先取消一条/)
  button(h, '开始对比').props.onClick()
  assert.deepEqual([...h.events[0][1]], [1,2])
  h.state.toggle(1); h.state.toggle(3)
  assert.deepEqual([...h.state.selected.value], [2,3])
})
test('empty filter state offers clearing filters without asserting the hospital is unlisted', () => {
  const filters = { query: '', province: '示例省', city: '', district: '', feature: '', onlyMarked: true, onlyReviewed: false }
  const h = harness('hospitals/HospitalPicker.vue', { modelValue: filters, hospitals: [], total: 3, provinces: [], cities: [], districts: [], features: [], marks: {}, comparisonKeys: [], selectedKey: '', loading: false })
  const empty = nodes(h.render()).find(n => n.type?.name === 'EmptyState.vue')
  assert.equal(empty.props.title, '没有符合当前条件的医院')
  empty.props.onAction()
  assert.equal(h.props.modelValue.onlyMarked, false)
  assert.equal(h.props.modelValue.province, '')
})
test('tag filter with no visible matches can load the remaining unfiltered records', () => {
  const h = harness('hospitals/HospitalReviewBoard.vue', { hospital, reviews: [], total: 24, loadedCount: 20, summary: { targets: {}, reviewCount: 24, ratingAvg: null }, target: '', sort: 'recent', activeTag: '示例标签', loading: false, loadingMore: false, isLoggedIn: false })
  button(h, '加载更多（还有 4 条）').props.onClick()
  assert.equal(h.events[0][0], 'more')
  h.props.loadedCount = 24
  assert.equal(nodes(h.render()).some(n => n.type === 'button' && text(n).includes('加载更多')), false)
})
test('v3 医院卡片不展示任何评分或星级，只展示评价数与中性标签', () => {
  const h = harness('hospitals/HospitalCard.vue', { hospital, compared: false })
  assert.match(text(h.render()), /1 条病友评价/)
  assert.doesNotMatch(text(h.render()), /已有评分|★|评分/)
})
test('capture guidance follows missing fields and quality without enabling premature analysis', () => {
  const h = harness('tracker/AssessmentCapture.vue', { context: {}, bodySite: 'left_hand', preview: 'synthetic-preview', checking: false, quality: null, busy: false })
  assert.match(h.state.nextStep.value, /视角/)
  assert.equal(h.state.ready.value, false)
  h.props.context = { view: '正面', capture_date: '2026-09-10' }
  assert.match(h.state.nextStep.value, /检查未完成/)
  h.props.quality = { overall: 'poor', suggestions: ['请调整光照后重拍'] }
  assert.equal(h.state.ready.value, false)
  assert.match(h.state.nextStep.value, /光照/)
  h.props.quality = { overall: 'good', suggestions: [] }
  assert.equal(h.state.ready.value, true)
})
