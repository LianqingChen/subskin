// Pure composable regression checks; no browser session, real storage or API access.
// Run: node scripts/verification/hospital-directory.cjs
const path = require('node:path')
const fs = require('node:fs')
const vm = require('node:vm')
const assert = require('node:assert/strict')
const { createRequire } = require('node:module')
const app = path.resolve(__dirname, '../../web/app')
const appRequire = createRequire(path.join(app, 'package.json'))
const ts = appRequire('typescript')
const vue = appRequire('vue')
const auth = vue.reactive({ user: null })
const messages = []
const toast = Object.fromEntries(['warning', 'error', 'success'].map(key => [key, text => messages.push({ key, text })]))
const memory = new Map()
let failStorage = false
const storage = { getItem: key => memory.get(key) ?? null, setItem: (key, value) => {
  if (failStorage) throw new Error('Storage unavailable')
  memory.set(key, value)
} }
const cache = new Map()
function load(file) {
  file = path.resolve(file)
  if (cache.has(file)) return cache.get(file)
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
  } }).outputText
  const module = { exports: {} }
  vm.runInNewContext(code, { module, exports: module.exports, localStorage: storage, console,
    require: id => {
      if (id === '@/stores/auth') return { useAuthStore: () => auth }
      if (id === '@/composables/useToast') return { useToast: () => toast }
      if (id.startsWith('@/')) return load(path.join(app, 'src', id.slice(2) + '.ts'))
      return appRequire(id)
    },
  }, { filename: file })
  cache.set(file, module.exports)
  return module.exports
}
const { HOSPITALS, HOSPITAL_CITIES } = load(path.join(app, 'src/data/hospitals.ts'))
const { PROVINCES } = load(path.join(app, 'src/data/cities.ts'))
const { useHospitalNotebook } = load(path.join(app, 'src/composables/useHospitalNotebook.ts'))
const { useHospitalDirectory } = load(path.join(app, 'src/composables/useHospitalDirectory.ts'))
const scope = vue.effectScope()
let count = 0
function check(name, run) { run(); count++; console.log('PASS', name) }
scope.run(() => {
  const notes = useHospitalNotebook()
  const directory = useHospitalDirectory(notes.notebook)
  check('all seed hospitals have official HTTPS sources and city coordinates', () => {
    assert.equal(new Set(HOSPITALS.map(h => h.id)).size, HOSPITALS.length)
    HOSPITALS.forEach(h => {
      assert.ok(h.source.startsWith('https://'))
      assert.ok(HOSPITAL_CITIES.some(c => c.name === h.city && c.province === h.province))
    })
  })
  check('province/city filter, source directory counts and empty regions', () => {
    assert.equal(directory.filtered.value.length, 7)
    directory.province.value = '上海'; assert.equal(directory.filtered.value.length, 2)
    directory.selectCity('南京'); assert.equal(directory.filtered.value.length, 1)
    assert.equal(directory.province.value, '江苏')
    assert.ok(directory.cities.value.some(c => c.name === '南京'))
    directory.province.value = '新疆'; assert.equal(directory.city.value, '')
    assert.equal(directory.filtered.value.length, 0)
    assert.equal(PROVINCES.length, 34)
    directory.reset()
  })
  check('combined text and service filters', () => {
    directory.query.value = '西安 308'; assert.equal(directory.filtered.value[0].id, 'xjtu1')
    directory.feature.value = '光疗中心'; assert.equal(directory.filtered.value.length, 0)
    directory.reset()
  })
  check('comparison cannot exceed three and removal frees a slot', () => {
    HOSPITALS.slice(0, 4).forEach(h => directory.compare(h.id))
    assert.equal(directory.compared.value.length, 3)
    directory.compare(HOSPITALS[0].id); directory.compare(HOSPITALS[3].id)
    assert.equal(directory.compared.value.length, 3)
    assert.ok(directory.comparisonIds.value.includes(HOSPITALS[3].id))
  })
  check('bookmarks toggle and filter persists', () => {
    notes.mark('huashan', 'want'); directory.onlyMarked.value = true
    assert.equal(directory.filtered.value.length, 1)
    notes.mark('huashan', 'want'); assert.equal(directory.filtered.value.length, 0)
    notes.mark('huashan', 'visited')
    assert.equal(JSON.parse(memory.get('subskin-hospitals-v1:guest')).marks.huashan, 'visited')
  })
  check('account change isolates previous data synchronously', () => {
    auth.user = { id: 'test-a' }
    assert.equal(Object.keys(notes.notebook.value.marks).length, 0)
    notes.mark('pumch', 'want')
    auth.user = { id: 'test-b' }
    notes.mark('westchina', 'visited')
    const b = JSON.parse(memory.get('subskin-hospitals-v1:test-b'))
    assert.deepEqual(Object.keys(b.marks), ['westchina'])
    auth.user = { id: 'test-a' }; assert.equal(notes.notebook.value.marks.pumch, 'want')
    auth.user = null; assert.equal(notes.notebook.value.marks.huashan, 'visited')
  })
  check('failed storage does not falsely update memory', () => {
    failStorage = true; notes.mark('pumch', 'want')
    assert.equal(notes.notebook.value.marks.pumch, undefined)
    failStorage = false
  })
  check('damaged data stays untouched and blocks overwriting', () => {
    memory.set('subskin-hospitals-v1:broken', '{malformed')
    auth.user = { id: 'broken' }; notes.mark('pumch', 'want')
    assert.equal(memory.get('subskin-hospitals-v1:broken'), '{malformed')
    memory.set('subskin-hospitals-v1:bad-shape', JSON.stringify({ marks: [], reviews: {} }))
    auth.user = { id: 'bad-shape' }; notes.mark('pumch', 'want')
    assert.deepEqual(JSON.parse(memory.get('subskin-hospitals-v1:bad-shape')).marks, [])
  })
  check('review draft reloads only for its owner', () => {
    auth.user = { id: 'test-a' }
    assert.ok(notes.saveReview({ hospitalId: 'pumch', month: '2026-09', duration: '', cost: '', outcome: '',
      ratings: { '医护沟通': '4' }, tags: ['解释耐心'], text: '仅用于隔离检查的合成文本，不对应真实就诊或任何患者。', savedAt: new Date().toISOString() }))
    auth.user = { id: 'test-b' }; assert.equal(notes.notebook.value.reviews.pumch, undefined)
    auth.user = { id: 'test-a' }; assert.equal(notes.notebook.value.reviews.pumch.ratings['医护沟通'], '4')
  })
})
scope.stop()
console.log(`${count} hospital directory checks passed; real user data untouched.`)
