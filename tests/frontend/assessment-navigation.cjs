// Routing and one-shot multi-photo handoff contracts; no browser or uploads.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const path = require('node:path')
const appRequire = createRequire(path.resolve('web/app/package.json'))
const ts = appRequire('typescript')
function load(file, dependencies) {
  const compiled = ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
  const result = {}
  new Function('exports', 'require', compiled)(result, name => {
    if (name in dependencies) return dependencies[name]
    if (name === 'vue') return appRequire('vue')
    if (name.startsWith('@/views/')) return { default: name }
    throw new Error('Unexpected dependency: ' + name)
  })
  return result
}
const router = load('web/app/src/router/index.ts', {
  'vue-router': { createWebHistory: () => null, createRouter: options => ({ options, afterEach() {} }) },
}).default
const routes = router.options.routes

test('both old exam URLs open the independent exam route', async () => {
  const record = routes.find(route => route.name === 'assessment')
  for (const tab of ['exam', 'report']) assert.equal(record.beforeEnter({ query: { tab } }).name, 'assessment-exam')
  assert.equal(record.beforeEnter({ query: {} }), true)
  const exam = routes.find(route => route.name === 'assessment-exam')
  assert.equal(exam.path, '/assessment/exam')
  assert.equal((await exam.component()).default, '@/views/AssessmentExamPage.vue')
})
test('single photo detail and multi-photo comparison routes stay available', () => {
  for (const name of ['vasi-detail', 'vasi-compare', 'assessment-photo-compare']) assert.ok(routes.find(route => route.name === name))
})
test('gallery multi-selection reaches comparison once in original order', () => {
  const transfer = load('web/app/src/composables/useQuickPhotoCompare.ts', {
    '@/api/community': {}, '@/api/skin_report': {},
  })
  const files = [new File(['a'], 'a.png'), new File(['b'], 'b.png'), new File(['c'], 'c.png')]
  transfer.queueComparisonPhotos(files)
  assert.deepEqual(transfer.takeComparisonPhotos(), files)
  assert.deepEqual(transfer.takeComparisonPhotos(), [])
})
