// Synthetic read responses; all writes intercepted. Never publishes to real accounts.
const { chromium } = require(process.env.SUBSKIN_PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const root = process.env.SUBSKIN_TEST_URL || 'https://staging.subskin.cn'
const out = 'data/release-candidates/hospital-redesign-20260916'
fs.mkdirSync(out, { recursive: true })
const stats = { review_count: 2, targets: { experience: 2 }, dimension_distribution: [] }
const hospitals = [1, 2].map(id => ({ id, slug: `test-${id}`, name: `测试医院${id === 1 ? '甲' : '乙'}`, province: id === 1 ? '上海' : '江苏', city: id === 1 ? '上海' : '南京', district: '测试区', address: '测试院区', department: '皮肤科', kind: '综合医院', origin: 'official', features: ['皮肤科诊疗'], checked_at: '2026-09-16', source: 'https://example.org', stats }))
const reviews = [1, 2].map(id => ({ id, hospital_id: id, hospital_name: hospitals[id - 1].name, hospital_city: hospitals[id - 1].city, target: 'experience', content: `合成测试经历${id}：就诊前询问了复诊安排，费用说明清楚。`, experience_scores: { '医患沟通': 'satisfied' }, author: { username: '测试病友' }, created_at: '2026-09-15T12:00:00Z', moderation_status: 'approved', helpful_count: 0 }))
const results = []
function pass(name) { results.push(name); console.log('PASS', name) }
async function noOverflow(page, name) {
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, width: innerWidth }))
  assert.ok(sizes.scroll <= sizes.width + 1, `${name}: ${JSON.stringify(sizes)}`)
}
;(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.SUBSKIN_CHROMIUM_PATH, args: ['--no-sandbox'] })
  for (const width of [375, 768, 1024, 1440]) {
    for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: 'block' })
      await context.addInitScript(mode => localStorage.setItem('subskin_theme_mode', mode), theme)
      const page = await context.newPage()
      const errors = []
      page.on('pageerror', err => errors.push(err.message))
      await page.route('**/api/**', async route => {
        const request = route.request(), url = new URL(request.url())
        if (request.method() !== 'GET') return route.fulfill({ json: {} })
        if (url.pathname === '/api/hospitals') return route.fulfill({ json: { items: hospitals, total: 2 } })
        if (url.pathname === '/api/hospitals/experience-summary') return route.fulfill({ json: {
          minimum: 20, window_days: 365, window_start: '2025-09-16T12:00:00Z', as_of: '2026-09-16T12:00:00Z', method: 'wilson-lower-95-v1',
          items: hospitals.map(h => ({ hospital_id: h.id, participants: h.id === 1 ? 20 : 19, dimensions: [{ dimension: '医患沟通', answered: h.id === 1 ? 20 : 19, satisfied: h.id === 1 ? 20 : 19, neutral: 0, unsatisfied: 0, na: 0, eligible: h.id === 1, reference_score: h.id === 1 ? 83.887 : null }] }))
        } })
        if (/\/hospitals\/(reviews\/feed|\d+\/reviews)$/.test(url.pathname)) {
          const id = url.pathname.match(/\/(\d+)\/reviews$/)?.[1]
          const items = reviews.filter(r => (!id || r.hospital_id === Number(id)) && (!url.searchParams.get('target') || r.target === url.searchParams.get('target')))
          return route.fulfill({ json: { total: items.length, items, summary: stats } })
        }
        if (url.pathname === '/api/hospitals/reviews/mine') return route.fulfill({ json: [] })
        return route.continue()
      })
      await page.goto(`${root}/hospitals`)
      await page.getByRole('heading', { name: '找医院，看病友经验' }).waitFor()
      await page.getByRole('button', { name: '测试医院甲', exact: true }).waitFor()
      await noOverflow(page, `${width}/${theme} directory`)
      await page.screenshot({ path: `${out}/directory-${width}-${theme}.png`, fullPage: true })
      const search = page.getByRole('searchbox').first()
      await search.fill('南京')
      await page.getByRole('button', { name: '测试医院乙', exact: true }).waitFor()
      assert.equal(await page.getByRole('button', { name: '测试医院甲', exact: true }).count(), 0)
      await search.fill('')
      await page.getByRole('button', { name: '测试医院甲', exact: true }).click()
      await page.getByText('合成测试经历1：', { exact: false }).waitFor()
      assert.equal(await page.getByText('合成测试经历2：', { exact: false }).isVisible(), false)
      await page.getByRole('button', { name: '查看全部医院', exact: true }).click()
      await page.getByText('合成测试经历2：', { exact: false }).waitFor()
      await noOverflow(page, `${width}/${theme} experiences`)
      await page.screenshot({ path: `${out}/experiences-${width}-${theme}.png`, fullPage: true })
      await page.getByRole('navigation', { name: '公益页内导航' }).getByRole('button', { name: /体验评价/ }).click()
      await page.getByText('样本不足，暂不参与排序', { exact: false }).waitFor()
      await page.getByLabel('按这一项体验排序').check()
      await page.getByText('参考值 83.89', { exact: false }).waitFor()
      assert.ok(await page.getByText('样本不足，暂不参与排序', { exact: false }).isVisible())
      await noOverflow(page, `${width}/${theme} evaluation`)
      await page.screenshot({ path: `${out}/evaluation-${width}-${theme}.png`, fullPage: true })
      await page.getByRole('button', { name: '分享就诊经历', exact: true }).first().click()
      await page.getByRole('dialog').waitFor()
      await page.getByRole('dialog').getByRole('searchbox').fill('甲')
      await page.getByRole('dialog').getByRole('button', { name: /测试医院甲/ }).click()
      assert.equal(await page.getByRole('dialog', { name: '先选择你就诊的医院' }).count(), 0)
      await page.getByRole('heading', { name: '手机登录 / 注册', exact: true }).waitFor()
      await page.getByRole('heading', { name: '手机登录 / 注册', exact: true }).locator('..').getByRole('button').click()
      await page.goto(`${root}/hospitals/treatments`)
      await page.getByRole('heading', { name: '白癜风治疗知识', exact: true }).waitFor()
      await page.getByRole('button', { name: '光疗', exact: true }).click()
      await page.getByRole('heading', { name: '光疗', exact: true }).waitFor()
      await noOverflow(page, `${width}/${theme} treatments`)
      await page.screenshot({ path: `${out}/treatments-${width}-${theme}.png`, fullPage: true })
      assert.equal(await page.locator('a[href*="/hospitals/"]').count(), 0, 'knowledge content has no hospital service links')
      assert.deepEqual(errors, [])
      pass(`${width}px ${theme}: search, scoped/global feed, sample threshold, ranking, share gate, knowledge, no overflow`)
      await context.close()
    }
  }
  await browser.close()
  fs.writeFileSync(`${out}/browser-results.json`, JSON.stringify({ passed: results }, null, 2))
})().catch(error => { console.error(error); process.exit(1) })
