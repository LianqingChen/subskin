const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path')
const { createRequire } = require('node:module')
const req = createRequire(path.resolve('web/app/package.json')), ts = req('typescript'), cache = new Map()
function load(file) {
  const resolved = path.resolve(file)
  if (cache.has(resolved)) return cache.get(resolved)
  const module = { exports: {} }; cache.set(resolved, module.exports)
  const source = ts.transpileModule(fs.readFileSync(resolved, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
  const localRequire = value => load((value.startsWith('@/') ? path.resolve('web/app/src', value.slice(2)) : path.resolve(path.dirname(resolved), value)) + '.ts')
  new Function('module', 'exports', 'require', source)(module, module.exports, localRequire)
  return module.exports
}
const { analyzeStoryMask } = load('web/app/src/utils/assessment-story/mask.ts')
const { makeStory, profileAge, STORY_URL } = load('web/app/src/utils/assessment-story/content.ts')
function mask(points, width = 12, height = 12) {
  const rgba = new Uint8ClampedArray(width * height * 4)
  for (const [x, y] of points) { const i = (y * width + x) * 4; rgba[i + 1] = 170; rgba[i + 2] = 100; rgba[i + 3] = 255 }
  return { rgba, shape: analyzeStoryMask(rgba, width, height) }
}
test('confirmed silhouette retains holes, small islands, orientation and relative coordinates', () => {
  const points = [[2,2],[3,2],[4,2],[2,3],[4,3],[2,4],[3,4],[4,4],[10,10]]
  const {rgba, shape} = mask(points), before = rgba.slice()
  assert.equal(shape.area, points.length); assert.equal(shape.count, 2)
  assert.equal(shape.pixels[3*12+3], 0); assert.equal(shape.pixels[10*12+10], 1)
  assert.deepEqual(shape.bounds, {x:2,y:2,width:9,height:9}); assert.deepEqual(rgba, before)
})
test('connectivity does not wrap image edges and recognises scattered patterns', () => {
  const {shape} = mask([[11,0],[0,1],[6,7]])
  assert.equal(shape.count, 3); assert.equal(shape.kind, 'scattered')
})
test('empty, invalid and opaque coloured masks never generate unrelated art', () => {
  assert.equal(mask([]).shape, null)
  assert.equal(analyzeStoryMask(new Uint8ClampedArray(4), 3, 2), null)
  assert.equal(analyzeStoryMask(new Uint8ClampedArray([0,170,100,255]), 1, 1), null)
})
test('genuine grayscale masks use luminance, not their opaque background', () => {
  const shape = analyzeStoryMask(new Uint8ClampedArray([0,0,0,255,255,255,255,255]), 2, 1)
  assert.equal(shape.area, 1); assert.deepEqual([...shape.pixels], [0,1])
})
test('vertical and horizontal silhouettes ground different captions', () => {
  const a = mask([[3,2],[3,3],[3,4],[3,5]]).shape, b = mask([[2,3],[3,3],[4,3],[5,3]]).shape
  assert.equal(a.kind, 'vertical'); assert.equal(b.kind, 'horizontal')
  assert.notEqual(makeStory(a,'sky','left_hand',null,0).title,makeStory(b,'sky','left_hand',null,0).title)
})
test('body-site and profile alter meaning without leaking personal fields or claiming outcomes', () => {
  const shape = mask([[3,3],[4,3]]).shape
  const hand = makeStory(shape,'sky','left_hand',null,1), foot = makeStory(shape,'sky','left_foot',null,1)
  assert.match(hand.title,/手心/); assert.match(foot.title,/自己的路/); assert.match(hand.reason,/左手/)
  const child = makeStory(shape,'sky','face',{age:10,gender:'女',relationship:'孩子'},1)
  assert.match(child.note,/长大/); assert.equal(child.dedication,'写给她的一幅画')
  assert.doesNotMatch(JSON.stringify(child),/10岁|康复|治愈|好转|恶化|扩散/)
  assert.notEqual(child.note,makeStory(shape,'sky','face',{age:68,gender:'男',relationship:'父母'},1).note)
  assert.equal(new URL(STORY_URL).hostname,'subskin.cn'); assert.doesNotMatch(STORY_URL,/token|user_id|assessment/)
})
test('age parsing rejects missing, future and impossible dates; respects birthday boundary', () => {
  const today = new Date(2030,5,10)
  assert.equal(profileAge(null,today),null); assert.equal(profileAge('2031-01-01',today),null)
  assert.equal(profileAge('2020-02-31',today),null)
  assert.equal(profileAge('2020-06-11',today),9); assert.equal(profileAge('2020-06-10',today),10)
})
const { journalSummary } = load('web/app/src/utils/assessment-story/summary.ts')
test('only reviewed valid measurements appear in reports and share summaries', () => {
  const result = {bodySite:'left_hand',measurement:{status:'measured',area_percentage:12.34,annotation:{review_state:'pending'}}}
  assert.equal(journalSummary(result).percentage,null)
  result.measurement.annotation.review_state='user_reviewed'
  assert.equal(journalSummary(result).label,'12.34%')
  for(const value of [NaN,Infinity,-1,101,null]) {result.measurement.area_percentage=value;assert.equal(journalSummary(result).percentage,null)}
  result.measurement.area_percentage=0
  assert.equal(journalSummary(result).label,'0%')
  result.measurement.status='legacy';assert.equal(journalSummary(result).percentage,null)
})
