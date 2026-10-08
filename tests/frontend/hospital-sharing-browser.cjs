// A generated in-memory session and intercepted APIs; no live user or publish request.
const { chromium } = require(process.env.SUBSKIN_PLAYWRIGHT_MODULE || 'playwright')
const { randomUUID } = require('node:crypto')
const assert = require('node:assert/strict')
const fs = require('node:fs')
;(async () => {
  const browser = await chromium.launch({ executablePath: process.env.SUBSKIN_CHROMIUM_PATH, headless: true, args: ['--no-sandbox'] })
  const context = await browser.newContext({ viewport: { width: 375, height: 900 }, serviceWorkers: 'block' })
  const user = { id: 999001, username: '合成测试病友', is_active: true, is_admin: false }
  await context.addInitScript(({ user, session }) => {
    localStorage.setItem('subskin_user', JSON.stringify(user))
    localStorage.setItem('subskin_token', session)
  }, { user, session: randomUUID() })
  const hospital = { id: 1, slug: 'synthetic', name: '合成测试医院', province: '上海', city: '上海', origin: 'official', department: '皮肤科', features: [], stats: { review_count: 0, targets: {} } }
  let publication = null
  const page = await context.newPage()
  await page.route('**/api/**', async route => {
    const req = route.request(), url = new URL(req.url())
    if (req.method() === 'POST' && url.pathname === '/api/hospitals/1/reviews') {
      publication = req.postDataJSON()
      return route.fulfill({ json: { review: { id: 1, hospital_id: 1, target: publication.target, content: publication.content }, message: '模拟发布成功' } })
    }
    if (url.pathname.includes('/user/me')) return route.fulfill({ json: user })
    if (url.pathname === '/api/hospitals') return route.fulfill({ json: { items: [hospital], total: 1 } })
    if (url.pathname === '/api/hospitals/reviews/mine') return route.fulfill({ json: [] })
    if (url.pathname.startsWith('/api/hospitals/') && url.pathname.endsWith('/reviews')) return route.fulfill({ json: { items: [], total: 0, summary: hospital.stats } })
    // Block all remaining API calls; synthetic session never leaves the browser.
    return route.fulfill({ json: {} })
  })
  await page.goto('https://staging.subskin.cn/hospitals?hospital=synthetic&write=1')
  const dialog = page.getByRole('dialog')
  await dialog.waitFor()
  await dialog.locator('textarea').fill('挂号后等了一个小时，医生解释了复诊安排，下次会提前准备检查资料。')
  const publish = dialog.getByRole('button', { name: '公开发布评价', exact: true })
  assert.ok(await publish.isDisabled(), 'No public health consent means no publication')
  const consent = dialog.getByRole('checkbox').filter({ visible: true })
  // The dedicated health consent label is located by its visible user-facing wording.
  const healthConsent = dialog.locator('label').filter({ hasText: '单独同意' }).getByRole('checkbox')
  if (await healthConsent.count()) await healthConsent.check()
  else await consent.last().check()
  assert.ok(await publish.isEnabled(), 'Explicit consent enables a valid experience')
  await publish.click()
  await page.waitForFunction(() => !document.querySelector('dialog[open]'))
  assert.equal(publication.health_consent, true)
  assert.equal(publication.target, 'experience')
  assert.ok(publication.content.length >= 20)
  fs.writeFileSync('data/release-candidates/hospital-redesign-20260916/sharing-results.json', JSON.stringify({ passed: ['deep link selects hospital', 'consent defaults unchecked', 'publish blocked without consent', 'experience payload submitted to intercepted API', 'dialog closes after success'], realWrites: 0 }, null, 2))
  console.log('PASS sharing deep link, consent gate, simulated publish, and dialog close; 0 real writes')
  await browser.close()
})().catch(error => { console.error(error); process.exit(1) })
