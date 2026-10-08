// 医评 v3 前端回归：风险规则引擎 + 6 维体验体系 + 「不做排名/不展示平均分」硬约束。
// 全部为纯逻辑与编译后 SFC 的静态断言，不启动浏览器、不使用任何患者数据。
//
// 运行: node --test tests/frontend/hospital-review-v3.cjs
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const path = require('node:path')

const appRequire = createRequire(path.resolve('web/app/package.json'))
const ts = appRequire('typescript')

/** 用 TypeScript 编译器把 .ts 工具模块转成 CommonJS 后求值。 */
function loadTs(rel) {
  const src = readFileSync(path.resolve('web/app/src', rel), 'utf8')
  const out = ts.transpileModule(src, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const exports = {}
  new Function('exports', 'module', out)(exports, { exports })
  return exports
}

function readSrc(rel) {
  return readFileSync(path.resolve('web/app/src', rel), 'utf8')
}

const risk = loadTs('utils/reviewRiskRules.ts')

// ── 统一评价体系 ──────────────────────────────────────────────────────────

test('6 维体验维度不含任何疗效/医术维度', () => {
  assert.equal(risk.EXPERIENCE_DIMENSIONS.length, 6)
  for (const banned of risk.BANNED_DIMENSIONS) {
    for (const dim of risk.EXPERIENCE_DIMENSIONS) {
      assert.ok(!dim.key.includes(banned), `维度 ${dim.key} 不应含疗效类词 ${banned}`)
    }
  }
})

test('档位为四档且包含「没体验过」', () => {
  assert.deepEqual(risk.EXPERIENCE_LEVELS.map(l => l.key), ['satisfied', 'neutral', 'unsatisfied', 'na'])
})

// ── 风险规则引擎 ──────────────────────────────────────────────────────────

test('疗效夸大在发布前硬拦截并给出改写建议', () => {
  for (const text of ['这家医院把我根治了', '医生保证治好，永不复发', '强烈推荐这家，别去别家']) {
    const result = risk.assessReviewRisk(text)
    assert.equal(result.blocked, true, text)
    assert.ok(result.hints.length > 0, '硬拦截必须给出改写建议')
  }
})

test('侮辱性言辞硬拦截', () => {
  for (const text of ['这个医生就是骗子', '黑心医院谋财害命', '庸医一个']) {
    assert.equal(risk.assessReviewRisk(text).blocked, true, text)
  }
})

test('对流程与费用的批评必须放行（风控不是封口）', () => {
  const result = risk.assessReviewRisk('候诊等了两个小时，有一项自费项目事先没有说明，复诊也要重新排队。')
  assert.equal(result.level, 'safe')
  assert.equal(result.blocked, false)
})

test('结论性指控触发冷静确认而不是直接拦截', () => {
  const result = risk.assessReviewRisk('我觉得这家医院就是误诊，把病情耽误了。')
  assert.equal(result.blocked, false)
  assert.notEqual(result.level, 'safe')
  assert.ok(result.categories.includes('断言性指控'))
})

test('联系方式不阻断发布（会被自动脱敏）', () => {
  const result = risk.assessReviewRisk('有问题可以打 13800001111 找科室。')
  assert.equal(result.level, 'safe')
  assert.equal(result.blocked, false)
})

test('引流、组织化维权、他人病历号被识别', () => {
  assert.ok(risk.assessReviewRisk('想交流的加我微信').blocked)
  assert.ok(risk.assessReviewRisk('大家一起建个维权群曝光这家医院').categories.includes('组织化维权'))
  assert.ok(risk.assessReviewRisk('我的病历号 12345678').level !== 'safe')
})

test('疗效类标签同样被拦截（防止绕过正文校验）', () => {
  assert.equal(risk.assessReviewRisk('挂号挺方便的', { tags: ['治愈率高'] }).blocked, true)
})

test('分档阈值与后端一致', () => {
  assert.equal(risk.levelForScore(0), 'safe')
  assert.equal(risk.levelForScore(30), 'watch')
  assert.equal(risk.levelForScore(60), 'restricted')
  assert.equal(risk.levelForScore(80), 'high')
})

// ── 医生称谓脱敏 ──────────────────────────────────────────────────────────

test('医生姓名在发布前即预览为脱敏称谓', () => {
  assert.equal(risk.sanitizeDoctorName('张三', ''), '张医生')
  assert.equal(risk.sanitizeDoctorName('王五主任医师', '皮肤科'), '王主任（皮肤科）')
  const result = risk.sanitizeDoctorName('李四', '皮肤科')
  assert.ok(!result.includes('李四'))
})

// ── 具体性引导 ────────────────────────────────────────────────────────────

test('具体性自检能识别时间/流程/费用/沟通/复诊要素', () => {
  const rich = risk.specificityScore('上个月挂的普通号，等了 40 分钟，费用 300 元，医生把方案讲清楚了，下月复诊。')
  assert.ok(rich.hit >= 4, `应命中至少 4 个要素，实际 ${rich.hit}`)
  const poor = risk.specificityScore('还行吧')
  assert.ok(poor.hit <= 1)
})

// ── 展示层硬约束：不做排名、不展示平均分 ──────────────────────────────────

test('医院卡片不再展示任何平均分或星级', () => {
  const src = readSrc('components/hospitals/HospitalCard.vue')
  assert.ok(!src.includes('ratingAvg'), '医院卡片不得引用 ratingAvg')
  assert.ok(!src.includes('★'), '医院卡片不得出现星标')
  assert.ok(src.includes('mentionedTags'), '应改为展示常被提到的中性标签')
})

test('医院对比表不再比较主观评分', () => {
  const src = readSrc('components/hospitals/HospitalCompare.vue')
  assert.ok(!src.includes('ratingAvg'))
  assert.ok(!src.includes('主观评分'))
  assert.ok(!src.includes('★'))
})

test('评价板块用维度分布替代平均分', () => {
  const src = readSrc('components/hospitals/HospitalReviewBoard.vue')
  assert.ok(!src.includes('ratingAvg'), '板块不得再展示平均分')
  assert.ok(src.includes('HospitalDimensionBars'), '应使用维度提及分布组件')
  assert.ok(src.includes('不代表医疗水平评价') && src.includes('不能作为疗效证据'), '应明确个人经历不等于医疗水平或疗效证据')
})

test('评价卡片不再展示星级评分，改为 6 维档位', () => {
  const src = readSrc('components/hospitals/HospitalReviewCard.vue')
  assert.ok(!src.includes('ratingAvg'))
  assert.ok(!src.includes('★'))
  assert.ok(src.includes('experienceEntries'))
  assert.ok(src.includes('时间较早'), '应有时间衰减标注')
})

test('维度分布组件包含「没体验过」档与不做排名的说明', () => {
  const src = readSrc('components/hospitals/HospitalDimensionBars.vue')
  assert.ok(src.includes('没体验过'))
  assert.ok(src.includes('不代表医疗水平评价'))
  assert.ok(src.includes('历史评价条数') && src.includes('去重后的近一年'), '历史条数与去重体验统计必须区分')
})

// ── 编辑器合规门禁 ────────────────────────────────────────────────────────

test('编辑器强制单独同意与冷静确认，且医生姓名预览脱敏', () => {
  const src = readSrc('components/hospitals/HospitalReviewComposer.vue')
  assert.ok(src.includes('healthConsent'), '必须有 PIPL 单独同意')
  assert.ok(src.includes('riskAck'), '必须有发布前冷静确认')
  assert.ok(src.includes('riskNeedsAck'), '命中风险时必须要求确认')
  assert.ok(src.includes('sanitizedDoctor'), '医生姓名应实时预览脱敏结果')
  assert.ok(src.includes('医疗纠纷人民调解委员会'), '应给出正当维权渠道指引')
  assert.ok(src.includes('6 维') || src.includes('EXPERIENCE_DIMENSIONS'), '应使用 6 维体验点选')
  // 未勾选单独同意 → 不能发布
  assert.match(src, /if \(!healthConsent\.value\) return false/)
  // 硬拦截 → 不能发布
  assert.match(src, /if \(risk\.value\.blocked\) return false/)
})

test('编辑器不再使用旧版 4 维星级评分', () => {
  const src = readSrc('components/hospitals/HospitalReviewComposer.vue')
  assert.ok(!src.includes('REVIEW_DIMENSIONS'), '不应再引用旧 4 维星级')
  assert.ok(!src.includes('★'.repeat(1)), '不应再渲染星标')
})

// ── 公约页与申诉页 ────────────────────────────────────────────────────────

test('社区公约页覆盖禁止内容与申诉渠道', () => {
  const src = readSrc('views/HospitalRulesPage.vue')
  for (const keyword of ['侮辱性言辞', '疗效', '隐私', '引流广告', '组织化维权', '排名', '医疗纠纷人民调解委员会']) {
    assert.ok(src.includes(keyword), `公约页应包含「${keyword}」`)
  }
  assert.ok(src.includes('不做付费删差评'), '应明确禁止付费删差评/置顶')
})

test('申诉页公开可达且设定 3 个工作日时限', () => {
  const src = readSrc('views/HospitalAppealPage.vue')
  assert.ok(src.includes('3 个工作日'))
  assert.ok(src.includes('claimantType'))
  assert.ok(src.includes('不判断医疗行为本身是否存在过错'), '应明确平台不做过错判断')
  assert.ok(!src.includes('auth.isLoggedIn'), '申诉页不应要求登录')
})

test('路由注册了公约页与申诉页', () => {
  const src = readSrc('router/index.ts')
  assert.ok(src.includes("path: '/hospitals/rules'"))
  assert.ok(src.includes("path: '/hospitals/appeal'"))
})
