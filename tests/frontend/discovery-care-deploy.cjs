const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const staging = '/usr/share/nginx/html/subskin-staging'
const production = '/usr/share/nginx/html/subskin'
const json = file => JSON.parse(fs.readFileSync(file, 'utf8'))
async function publicGet(url) {
  const response = await fetch(url)
  assert.equal(response.status, 200, url)
  return response
}
;(async () => {
  const version = json(`${staging}/version.json`)
  const prod = json(`${production}/version.json`)
  assert.equal(version.env, 'staging')
  assert.equal(prod.env, 'production')
  assert.equal(version.lastProdBuildTime, prod.buildTime)
  assert.ok(version.buildTime > 1790918022517)
  for (const [file, hash] of [['version.json', 'df32da040dcff3d89e0e29a9d9d684efd720c82d04abf11da48396a637b3bce9'], ['index.html', '340e7df8f2a457070980cffac31c0d67e8af9d00a4cd7765f2d85f5d54951dd9']]) {  // pragma: allowlist secret
    assert.equal(crypto.createHash('sha256').update(fs.readFileSync(`${production}/${file}`)).digest('hex'), hash, 'production unchanged')
  }
  const manifest = json(`${staging}/manifest.webmanifest`)
  assert.equal(manifest.name, 'SubSkin [STAGING]')
  assert.equal(manifest.theme_color, '#1e293b')
  assert.equal(manifest.display, 'standalone')
  for (const icon of manifest.icons) assert.ok(fs.existsSync(path.join(staging, icon.src.split('?')[0])))
  const html = fs.readFileSync(`${staging}/index.html`, 'utf8')
  assert.match(html, /rel="manifest"/)
  assert.match(html, /name="theme-color"/)
  for (const match of html.matchAll(/(?:src|href)="(\/assets\/[^"?]+)/g)) assert.ok(fs.existsSync(path.join(staging, match[1])))
  assert.ok(fs.statSync(`${staging}/sw.js`).size > 3000)
  const live = await (await publicGet('https://staging.subskin.cn/version.json')).json()
  assert.deepEqual(live, version)
  const liveManifest = await (await publicGet('https://staging.subskin.cn/manifest.webmanifest')).json()
  assert.deepEqual(liveManifest, manifest)
  const sw = await publicGet('https://staging.subskin.cn/sw.js')
  assert.ok((await sw.text()).length > 3000)
  const health = await (await publicGet('http://127.0.0.1:8000/api/health')).json()
  assert.equal(health.status, 'ok')
  console.log(JSON.stringify({ staging: version, production: prod, health, checks: 'production hashes unchanged; live/local version and manifest match; icons/assets/SW/health pass' }, null, 2))
})().catch(error => { console.error(error); process.exitCode = 1 })
