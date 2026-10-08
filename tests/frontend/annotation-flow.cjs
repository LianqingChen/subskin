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
  const props = vue.reactive(Object.fromEntries(Object.entries(initial).map(([key,value]) => [key.replace(/-([a-z])/g, (_,letter) => letter.toUpperCase()),value]))), events = []
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

test('pending reference asks for review, not direct confirmation',()=>{
 const h=harness('tracker/AssessmentObservationResult.vue',{result:{id:1,imageUrl:'/synthetic.png',bodySite:'示例',measurement:{status:'measured',area_percentage:20,reasons:[],annotation:{protocol:'skin-outline-v1',review_state:'pending',uncertain_pixels:10,uncertain_percentage:2}}},saved:false})
 assert.match(text(h.render()),/像素分割参考，待你核对/)
 assert.match(text(h.render()),/未核对前不提供完整测量/)
 button(h,'核对范围后保存').props.onClick()
 assert.equal(h.events[0][0],'save')
})
test('one confirmation submits the prefilled masks without a second checkbox',()=>{
 const h=harness('tracker/AnnotationReviewPanel.vue',{image:'/synthetic.png',skin:'skin',lesion:'lesion',uncertain:'candidate',busy:false})
 assert.equal(button(h,'确认').props.disabled,true)
 h.state.editor.value={snapshot:()=>({skinMaskDataUrl:'skin',lesionMaskDataUrl:'lesion',annotatedImageDataUrl:'fused'})}
 h.state.confirm();assert.equal(h.events.length,0)
 h.state.ready.value=true;h.state.confirm();assert.equal(h.events[0][1].uncertaintyReviewed,true);assert.equal(h.events[0][1].annotatedImageDataUrl,'fused')
 assert.ok(!nodes(h.render()).some(n=>n.type==='input' && n.props?.type==='checkbox'))
 h.props.busy=true;h.state.confirm();assert.equal(h.events.length,1)
 const canvas=nodes(h.render()).find(n=>n.type?.name==='PhotoMaskCanvas.vue');assert.equal(canvas.props.candidate,'candidate')
})
test('one fused photo replaces layer tabs and opacity selection',()=>{
 const h=harness('tracker/AnnotationEvidence.vue',{image:'/synthetic.png',skin:'blue',lesion:'pink',uncertain:'candidate'})
 assert.equal(nodes(h.render()).filter(n=>n.type==='button').length,0)
 assert.equal(nodes(h.render()).filter(n=>n.type==='input').length,0)
 const canvas=nodes(h.render()).find(n=>n.type?.name==='PhotoMaskCanvas.vue');assert.equal(canvas.props.skin,'blue');assert.equal(canvas.props.lesion,'pink');assert.equal(canvas.props.candidate,'candidate')
})

test('blocked coarse results never display area or perimeter',()=>{
 const h=harness('tracker/AssessmentObservationResult.vue',{result:{id:1,imageUrl:'/synthetic.png',bodySite:'示例',measurement:{status:'unavailable',area_percentage:null,area_cm2:null,border:null,reasons:['仅粗定位'],annotation:{protocol:'skin-outline-v1',review_state:'pending',refine:{version:'pixel-refine-v2',status:'partial',measurement_eligible:false,unresolved_region_count:2},uncertain_pixels:5}}},saved:false});
 assert.match(text(h.render()),/尚未完成可靠分割/);assert.match(text(h.render()),/2 个候选区域/);assert.doesNotMatch(text(h.render()),/80.4|cm²|周长：/);
})

test('capture can start with valid quality/date and no angle; failures keep retry visible',()=>{
 const h=harness('tracker/AssessmentCapture.vue',{context:{capture_date:'2025-06-07'},bodySite:'face',preview:'photo',quality:{overall:'good',suggestions:[]},checking:false,busy:false})
 assert.equal(button(h,'开始分析').props.disabled,false)
 h.props.context.capture_date='';assert.equal(button(h,'开始分析').props.disabled,true);h.props.context.capture_date='2025-06-07'
 assert.doesNotMatch(text(h.render()),/拍摄视角/)
 h.props.quality=null;h.props.qualityError='登录已失效';h.props.needsLogin=true
 assert.equal(button(h,'开始分析').props.disabled,true)
 button(h,'登录后继续检查').props.onClick();assert.equal(h.events.at(-1)[0],'retry-quality')
 h.props.quality={overall:'poor',suggestions:['照片模糊']}
 assert.equal(button(h,'开始分析').props.disabled,true)
})
test('date is directly editable without extra confirmation or explanatory headings',()=>{
 const h=harness('tracker/AssessmentCapture.vue',{context:{capture_date:'2025-06-07'},bodySite:'face',preview:'photo',quality:{overall:'good',suggestions:[]},checking:false,busy:false})
 const wheel=nodes(h.render()).find(n=>n.type?.name==='DateWheelPicker.vue');assert.ok(wheel);assert.ok(wheel.props.compact === '' || wheel.props.compact === true)
 wheel.props['onUpdate:modelValue']('2024-02-29');assert.deepEqual(h.events[0],['date','2024-02-29'])
 assert.doesNotMatch(text(h.render()),/确认这次照片|照片日期已自动填写|修改日期|确定日期|信息已齐全/)
 const f=new File(['a'],'photo.jpg',{type:'image/jpeg'});h.state.captured(f);assert.deepEqual(h.events.at(-1),['file',f,'camera'])
})


test('confirmed result highlights deliberate sharing',()=>{
 const h=harness('tracker/AssessmentObservationResult.vue',{result:{id:1,imageUrl:'/synthetic.png',bodySite:'示例',measurement:{status:'measured',area_percentage:12,reasons:[],annotation:{protocol:'skin-seg-v2',review_state:'user_reviewed'}}},saved:true,lesionLayer:'mask'})
 button(h,'分享结果').props.onClick();assert.equal(h.events[0][0],'share');assert.match(text(h.render()),/12%/)
})
test('only four drawing tools, vertical size opens on request',()=>{
 const h=harness('tracker/CompactMaskTools.vue',{tool:'lesion',brushSize:12,disabled:false})
 assert.equal(nodes(h.render()).filter(n=>n.type==='button').length,4)
 assert.equal(nodes(h.render()).filter(n=>n.type==='input').length,0)
 button(h,'皮肤画笔').props.onClick();assert.deepEqual(h.events[0],['update:tool','skin'])
 button(h,'粗细').props.onClick()
 const slider=nodes(h.render()).find(n=>n.type==='input');assert.equal(slider.props['aria-orientation'],'vertical');slider.props.onInput({target:{value:'24'}});assert.deepEqual(h.events.at(-1),['update:brushSize',24])
 assert.equal(nodes(h.render()).filter(n=>n.type==='button').length,4)
})


test('upload keeps compact date and prominent cancel in the fitted workspace',()=>{
 const h=harness('tracker/AssessmentCapture.vue',{context:{capture_date:'2026-09-14'},bodySite:'face',preview:'photo',quality:{overall:'good',suggestions:[]},checking:false,busy:false,fitScreen:true})
 assert.match(h.render().props.class,/capture-layout--fit/)
 assert.equal(button(h,'开始分析').props.disabled,false)
 h.props.busy=true
 const wait=nodes(h.render()).find(n=>n.type?.name==='AnalysisWaitStatus.vue');assert.ok(wait);assert.equal(wait.props.active,true)
 wait.props.onCancel();assert.equal(h.events.at(-1)[0],'cancel')
})
test('review fills remaining photo space and keeps controls outside that flexible region',()=>{
 const h=harness('tracker/AnnotationReviewPanel.vue',{image:'photo',fitScreen:true,busy:false})
 const canvas=nodes(h.render()).find(n=>n.type?.name==='PhotoMaskCanvas.vue');assert.equal(canvas.props.fill,true)
 assert.match(h.render().props.class,/min-h-0/)
 assert.ok(nodes(h.render()).some(n=>n.type==='div' && String(n.props?.class).includes('shrink-0')))
 button(h,'确认')
})
test('countdown is labelled as reference and cancellation emits the real action',()=>{
 const h=harness('tracker/AnalysisWaitStatus.vue',{active:false,stage:'识别范围…'})
 assert.match(text(h.render()),/参考倒计时 90 秒/)
 button(h,'取消分析').props.onClick();assert.deepEqual(h.events[0],['cancel'])
 h.state.countdown.remaining.value=0
 assert.match(text(h.render()),/耗时较长/);assert.doesNotMatch(text(h.render()),/分析完成|100%/)
 button(h,'取消分析')
})
