const { chromium } = require(process.env.SUBSKIN_PLAYWRIGHT_MODULE || 'playwright')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const root = process.env.SUBSKIN_TEST_URL || 'https://staging.subskin.cn'
const out = '/tmp/opencode/discovery-toolbar-20261002'
async function oneRow(page, name) {
  const controls = [page.getByRole('button', { name: '关注', exact: true }), page.getByRole('button', { name: '推荐', exact: true }), page.getByRole('navigation', { name: '发现内容筛选', exact: true }).getByRole('button').last(), page.locator('button[aria-haspopup="listbox"]'), page.getByRole('button', { name: '搜索病友内容', exact: true })]
  const boxes = await Promise.all(controls.map(control => control.boundingBox()))
  assert.ok(boxes.every(Boolean), name)
  const centers = boxes.map(box => box.y + box.height / 2)
  assert.ok(Math.max(...centers) - Math.min(...centers) <= 1, `${name}: toolbar wrapped: ${JSON.stringify(boxes)}`)
  const width = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, viewport: innerWidth }))
  assert.ok(width.page <= width.viewport + 1, `${name}: page overflow`)
}
;(async () => {
  fs.mkdirSync(out, { recursive: true })
  const browser = await chromium.launch({ headless: true, executablePath: process.env.SUBSKIN_CHROMIUM_PATH, args: ['--no-sandbox'] })
  try {
    for (const width of [320, 375, 390, 768, 1024, 1440]) for (const city of ['测试城', '合成测试长城市名称']) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: 'block' })
      await context.addInitScript(city => localStorage.setItem('subskin_user_city', JSON.stringify({ city, lat: null, lng: null, source: 'manual', timestamp: Date.now() })), city)
      const page = await context.newPage()
      const errors = []
      page.on('pageerror', error => errors.push(error.message))
      await page.route('**/api/**', route => route.fulfill({ json: route.request().url().includes('/community/posts') ? { items: [], total: 0, next_cursor: null } : [] }))
      await page.goto(`${root}/community`)
      await page.getByRole('button', { name: city, exact: true }).waitFor()
      await oneRow(page, `${width}/${city}/default`)
      const sort = page.locator('button[aria-haspopup="listbox"]')
      await sort.click()
      await page.getByRole('option', { name: '最多浏览', exact: true }).click()
      await oneRow(page, `${width}/${city}/long-sort`)
      await page.getByRole('button', { name: '搜索病友内容', exact: true }).click()
      await page.getByRole('searchbox', { name: '搜索病友分享或标签' }).waitFor()
      await oneRow(page, `${width}/${city}/search-open`)
      await page.screenshot({ path: `${out}/toolbar-${width}-${city.length}.png` })
      assert.deepEqual(errors, [])
      console.log(`PASS ${width}px / ${city}: default, long sort, search open; one row and no page overflow`)
      await context.close()
    }
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
