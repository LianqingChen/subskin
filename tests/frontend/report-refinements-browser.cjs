// Synthetic images/reports and generated session; all API requests intercepted.
const { chromium } = require(process.env.SUBSKIN_PLAYWRIGHT_MODULE || 'playwright')
const { randomUUID } = require('node:crypto')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const out = 'data/release-candidates/report-refinements-20260916'
fs.mkdirSync(out, { recursive: true })
const photo = shift => 'data:image/svg+xml;base64,' + Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="400" height="400" fill="#a98b75"/><ellipse cx="200" cy="190" rx="${shift}" ry="90" fill="#e9dacf"/></svg>`).toString('base64')
const single = pct => ({ status: 'measured', scope: 'individual_photo', area_percentage: pct, lesion_pixels: pct * 100, skin_pixels: 10000, area_cm2: null, relative_lightness: 8.2, reasons: [] })
const measured = { comparison_status: 'measured', size_change_percent: -20, change_interval_percent: [-25,-15], summary: '仅比较共同照片范围。', evidence: { area_a_px: 2000, area_b_px: 1600, common_pixels: 10000, common_coverage: .95, alignment_error_px: .8, relative_lightness_change: -2 }, photo_measurements: { before: single(20), after: single(16) }, melanin_signals: {}, trend: '面积减小', reasons: [] }
const frames = [1, 2, 3].map((n, i) => ({ image_id: n, date: `2026-09-${String(10 + i).padStart(2, '0')}`, image_url: photo(100 - i * 10) }))
function report(id = 501) {
  const f = id === 503 ? frames : [frames[0], frames[2]]
  const m = id === 502 ? { ...measured, comparison_status: 'visual_only', size_change_percent: null, evidence: {}, photo_measurements: { before: single(0), after: { ...single(16), status: 'partial', reasons: ['白斑可能未拍全'] } }, capture_note: '两张照片的共同范围不足', photo_measurement_source: 'latest_source_records' } : measured
  return { id, report_type: 'comparison', title: '合成白斑对比报告', body_site: 'face', body_site_label: '面部', period_start: f[0].date, period_end: f.at(-1).date, created_at: '2026-09-16T01:00:00Z', generated_at: id === 502 ? null : '2026-09-16T01:05:00Z', status: 'completed', insights: [], recommendations: [], metrics: { point_count: f.length, first: f[0], last: f.at(-1), timeline_frames: f, refs: f.map(x => `va:${x.image_id}`), pair_metrics: m, pair_align: { aligned: true, aligned_after_url: f.at(-1).image_url }, measurement_version: 'common-roi-v1', trend: '图像观察', has_vasi: false } }
}
const passed = []
;(async () => {
  const browser = await chromium.launch({ executablePath: process.env.SUBSKIN_CHROMIUM_PATH, headless: true, args: ['--no-sandbox'] })
  for (const width of [375, 768, 1024, 1440]) {
    for (const theme of ['light', 'dark']) {
      const ctx = await browser.newContext({ viewport: { width, height: 900 }, timezoneId: 'Asia/Shanghai', serviceWorkers: 'block' })
      await ctx.addInitScript(({theme, session}) => { localStorage.setItem('subskin_theme_mode', theme); localStorage.setItem('subskin_token', session); localStorage.setItem('subskin_user', JSON.stringify({ id: 9001, username: '合成病友' })) }, {theme, session:randomUUID()})
      const page = await ctx.newPage()
      const errors = []
      page.on('pageerror', error => errors.push(error.message))
      await page.route('**/api/**', async route => {
        const url = new URL(route.request().url())
        if (url.pathname.includes('/user/me') || url.pathname.includes('/users/me')) return route.fulfill({ json: { id: 9001, username: '合成病友', is_active: true } })
        if (url.pathname.endsWith('/vasi/history')) return route.fulfill({ json: {total:0,items:[]} })
        if (url.pathname.endsWith('/skin-reports/')) return route.fulfill({ json: { total: 2, items: [report(501), report(502)] } })
        if (url.pathname.endsWith('/periodic/preview')) return route.fulfill({ json: { items: [] } })
        if (url.pathname.endsWith('/pair-compare')) {
          const sorted = [Number(url.searchParams.get('index_a')), Number(url.searchParams.get('index_b'))].sort()
          return route.fulfill({ json: { first: frames[sorted[0]], last: frames[sorted[1]], pair_metrics: measured, pair_align: { aligned: true, aligned_after_url: frames[sorted[1]].image_url } } })
        }
        const match = url.pathname.match(/\/skin-reports\/(\d+)$/)
        if (match) return route.fulfill({ json: report(Number(match[1])) })
        return route.fulfill({ json: {} })
      })
      await page.goto('https://staging.subskin.cn/community/reports/501')
      await page.getByRole('heading', { name: '量化分析', exact: true }).waitFor()
      assert.deepEqual(await page.getByRole('tablist', {name:'对比视图切换'}).getByRole('tab').allTextContents().then(xs=>xs.map(s=>s.trim())), ['动画','叠影','滑块','并排'])
      assert.equal(await page.getByRole('tab', {name:'动画',exact:true}).getAttribute('aria-selected'), 'true')
      await page.getByText('生成于 2026/09/16 09:05', { exact: true }).waitFor()
      await page.getByText('-20%', { exact: true }).waitFor()
      const dates = page.locator('[aria-label="对比照片日期"]')
      assert.ok((await dates.textContent()).includes('2026-09-10'))
      assert.ok((await dates.textContent()).includes('2026-09-12'))
      for (const name of ['叠影','滑块','并排','动画']) {
        await page.getByRole('tab', {name,exact:true}).click()
        const text = await page.locator('.cv').innerText()
        assert.ok(!text.includes('2026-09-10') && !text.includes('2026-09-12'), `${name}: dates repeated in view`)
      }
      const sizes = await page.evaluate(() => ({ width:innerWidth, scroll:document.documentElement.scrollWidth }))
      assert.ok(sizes.scroll <= sizes.width + 1, `${width}: horizontal overflow`)
      await page.screenshot({ path:`${out}/measured-${width}-${theme}.png`, fullPage:true })
      await page.goto('https://staging.subskin.cn/community/reports/502')
      await page.getByText('各张照片已有的测量结果', {exact:false}).waitFor()
      assert.equal(await page.getByText('-20%',{exact:true}).count(),0)
      const areaRow = page.getByRole('row').filter({hasText:'白斑占可见皮肤'})
      assert.deepEqual(await areaRow.locator('td').allTextContents(), ['0','16'])
      await page.getByText('创建于 2026/09/16 09:00', { exact: true }).waitFor()
      await page.screenshot({ path:`${out}/partial-${width}-${theme}.png`, fullPage:true })
      await page.goto('https://staging.subskin.cn/community/reports/503')
      await page.getByRole('heading', { name: '量化分析', exact: true }).waitFor()
      await page.locator('.pds__row').last().getByRole('button', {name:'09/11',exact:true}).click()
      await page.waitForResponse(response=>response.url().includes('/pair-compare'))
      await page.getByRole('tab', {name:'动画',exact:true}).waitFor()
      assert.equal(await page.getByRole('tab', {name:'动画',exact:true}).getAttribute('aria-selected'),'true')
      await page.goto('https://staging.subskin.cn/assessment?view=records')
      await page.getByRole('button', {name:'白斑对比',exact:true}).click()
      await page.getByText('生成于 2026/09/16 09:05', { exact: true }).waitFor()
      await page.getByText('创建于 2026/09/16 09:00', { exact: true }).waitFor()
      assert.deepEqual(errors, [])
      const name=`${width}/${theme}: animation default/order, header dates, quantitative table/zero/partial, pair switch, generated vs created time`
      passed.push(name); console.log('PASS',name)
      await ctx.close()
    }
  }
  await browser.close()
  fs.writeFileSync(`${out}/browser-results.json`, JSON.stringify({ passed, realApiCalls:0 },null,2))
})().catch(error=>{ console.error(error);process.exit(1) })
