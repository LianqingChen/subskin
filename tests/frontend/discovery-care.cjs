const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const path = require('node:path')
const appRequire = createRequire(path.resolve('web/app/package.json'))
const vue = appRequire('vue')
const ts = appRequire('typescript')
const { parse, compileScript, compileTemplate } = appRequire('@vue/compiler-sfc')
const read = rel => readFileSync(path.resolve('web/app/src', rel), 'utf8')
function evaluate(source, dependencies) {
  const exports = {}
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
  new Function('exports', 'require', js)(exports, dependencies)
  return exports
}
const catalog = evaluate(read('data/care-catalog.ts'), () => { throw Error('Unexpected catalog dependency') })
function loadCatalogState() {
  return evaluate(read('composables/useCareCatalog.ts'), name => {
    if (name === 'vue') return vue
    if (name === '@/data/care-catalog') return catalog
    throw Error(`Unexpected dependency ${name}`)
  }).useCareCatalog()
}
test('发现首页不再展示科普或种草入口，保留就医经验', () => {
  const source = read('views/CommunityPage.vue')
  assert.doesNotMatch(source, /\/discover\/(science|picks)/)
  assert.match(source, /\/hospitals/)
  assert.doesNotMatch(source, /as any/)
})
test('调养统一结果网格而非分类重复分段', () => {
  const source = read('views/CarePage.vue')
  assert.doesNotMatch(source, /v-for="section in sections"/)
  assert.match(source, /商品排序/)
  assert.match(source, /清除筛选/)
  assert.doesNotMatch(source, /\/discover\/|w-\[84px\]/)
})
test('调养导航使用购物车图标且页面顶部不再显示清单入口或标题', () => {
  const modules = JSON.parse(readFileSync(path.resolve('web/shared/site-modules.json'), 'utf8')).modules
  assert.equal(modules.find(module => module.path === '/care').icon, 'ri-shopping-cart-line')
  const source = read('views/CarePage.vue')
  assert.doesNotMatch(source, /CartButton|CartSheet|日常用品，按需选择/)
  assert.match(source, /<h1 class="sr-only">调养<\/h1>/)
})
test('调养搜索提供原生提交表单和可点击搜索按钮', () => {
  const { descriptor } = parse(read('views/CarePage.vue'))
  assert.match(descriptor.template.content, /<form[^>]*@submit\.prevent="submitSearch"/)
  assert.match(descriptor.template.content, /<button[^>]*type="submit"[^>]*>[\s\S]*?搜索[\s\S]*?<\/button>/)
  assert.match(descriptor.scriptSetup.content, /query\.value = query\.value\.trim\(\)/)
})
test('清单没有未提交的需求登记或虚假结算文案', () => {
  const source = read('components/care/CartSheet.vue')
  assert.doesNotMatch(source, /已记录需求|价格待定/)
  assert.match(source, /仅保存在此设备/)
  assert.match(read('composables/useCareCart.ts'), /subskin-care-cart-v1:/)
})
test('暗色选中态不使用现有 CSS 变量调色板无法生成的不透明度变体', () => {
  for (const file of ['views/CarePage.vue', 'views/CommunityPage.vue']) {
    assert.doesNotMatch(read(file), /dark:bg-primary-\d+\/\d+/)
  }
})
test('真实目录15项，护理在前，筹备工具在后，分类和搜索叠加', () => {
  const state = loadCatalogState()
  assert.equal(state.items.value.length, 15)
  assert.equal(state.items.value[0].topic.id, 'sun')
  assert.equal(state.items.value.at(-1).item.status, 'planned')
  state.active.value = 'food'
  state.query.value = '  黑芝麻  '
  assert.deepEqual(state.items.value.map(x => x.item.id), ['food-sesame', 'food-sesame-paste'])
  state.query.value = '不存在的合成用品'
  assert.equal(state.items.value.length, 0)
  state.reset()
  assert.equal(state.items.value.length, 15)
})
test('名称排序不修改原始目录且分类计数来自实际数据', () => {
  const state = loadCatalogState()
  const original = catalog.CARE_TOPICS.flatMap(t => t.items.map(i => i.id))
  state.sort.value = 'name'
  const names = state.items.value.map(x => x.item.name)
  assert.deepEqual(names, [...names].sort((a, b) => a.localeCompare(b, 'zh-CN')))
  assert.equal(state.categories.find(c => c.id === 'food').count, 5)
  assert.equal(state.categories.find(c => c.id === 'copper').title, '日常餐具')
  assert.deepEqual(catalog.CARE_TOPICS.flatMap(t => t.items.map(i => i.id)), original)
})
test('所有调养 SFC 模板与 TypeScript setup 可编译', () => {
  for (const rel of ['views/CarePage.vue', 'views/CareProductPage.vue', 'components/care/ProductCard.vue', 'components/care/CartSheet.vue', 'components/care/CartButton.vue']) {
    const { descriptor } = parse(read(rel))
    const script = compileScript(descriptor, { id: rel })
    const template = compileTemplate({ source: descriptor.template.content, id: rel, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(template.errors, [], rel)
  }
})

function makeFeed(api, user = null) {
  const mounted = []
  const auth = vue.reactive({ user, isLoggedIn: !!user, showLoginModal: false })
  const geo = { city: vue.ref('测试城'), requestCity: async () => '测试城', preloadCity() {} }
  const fakeVue = { ...vue, onMounted: fn => mounted.push(fn), onActivated() {}, onDeactivated() {}, onUnmounted() {} }
  const scope = vue.effectScope()
  let state
  scope.run(() => {
    state = evaluate(read('composables/useDiscoveryFeed.ts'), name => {
      if (name === 'vue') return fakeVue
      if (name === '@/api/community') return { communityApi: api }
      if (name === '@/stores/auth') return { useAuthStore: () => auth }
      if (name === '@/composables/useGeolocation') return { useGeolocation: () => geo }
      throw Error(`Unexpected dependency ${name}`)
    }).useDiscoveryFeed()
  })
  return { state, auth, start: () => mounted[0](), dispose: () => scope.stop() }
}
function fakePost(id, privatePost = false) { return { id, is_private: privatePost, author: { id: 900001 }, like_count: 0 } }
test('发现本人日记只在未筛选推荐中合并，关注与同城参数保留', async () => {
  const calls = []
  let diaries = 0
  const env = makeFeed({ getPosts: async params => { calls.push(params); return { items: [fakePost(1)], total: 1, next_cursor: null } }, getMyDiaries: async () => { diaries++; return { items: [fakePost(2, true)] } } }, { id: 900001 })
  try {
    await env.start()
    assert.deepEqual(env.state.posts.value.map(p => p.id), [1, 2])
    env.state.activeFeedType.value = 'follow'
    await vue.nextTick(); await vue.nextTick()
    assert.equal(calls.at(-1).feed_type, 'following')
    assert.equal(diaries, 1)
    env.state.activeFeedType.value = 'local'
    await vue.nextTick(); await vue.nextTick()
    assert.equal(calls.at(-1).city, '测试城')
    env.state.searchQuery.value = '测试标签'
    await env.state.retryLoad()
    assert.equal(calls.at(-1).tag, '测试标签')
    assert.equal(diaries, 1)
  } finally { env.dispose() }
})
test('发现加载更多使用服务端游标并保留排序去重', async () => {
  const calls = []
  const env = makeFeed({ getPosts: async params => {
    calls.push(params)
    return calls.length === 1 ? { items: [fakePost(2), fakePost(1)], total: 3, next_cursor: 'cursor-a' } : { items: [fakePost(1), fakePost(3)], total: 3, next_cursor: null }
  } })
  try {
    await env.start(); await env.state.loadMore()
    assert.equal(calls[1].after, 'cursor-a')
    assert.deepEqual(env.state.posts.value.map(p => p.id), [2, 1, 3])
    assert.equal(env.state.hasMore.value, false)
  } finally { env.dispose() }
})
test('旧请求失败不能覆盖新筛选成功状态', async () => {
  let rejectOld
  let calls = 0
  const env = makeFeed({ getPosts: async () => {
    calls++
    if (calls === 1) return { items: [], total: 0, next_cursor: null }
    if (calls === 2) return new Promise((resolve, reject) => { rejectOld = reject })
    return { items: [fakePost(3)], total: 1, next_cursor: null }
  } })
  try {
    await env.start()
    const old = env.state.retryLoad()
    await env.state.retryLoad()
    const savedError = console.error
    console.error = () => {}
    try { rejectOld(new Error('synthetic old failure')); await old } finally { console.error = savedError }
    assert.equal(env.state.loadError.value, false)
    assert.deepEqual(env.state.posts.value.map(p => p.id), [3])
  } finally { env.dispose() }
})
