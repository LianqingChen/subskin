/**
 * 就医经验发布前风控（客户端，即时反馈）。
 *
 * 与后端 `web/backend/services/review_risk.py` 同源规则，但目标是**帮用户把话说到
 * 站得住**，而不是封口：命中风险时给出「对事不对人」的改写建议，并在涉及结论性
 * 指控时进入发布前冷静确认（而不是直接拦截表达）。
 *
 * 法规依据（详见 docs/specs/2026-09-11-medical-review-research.md E 节）：
 *  - 《民法典》第 1025 条：舆论监督抗辩明确排除「使用侮辱性言辞」；
 *  - 《互联网信息服务管理办法》第 15 条：不得发布侮辱、诽谤他人的信息；
 *  - 《广告法》第 16 条 / 《医疗广告管理办法》第 7 条：不得宣传疗效、治愈率。
 *
 * 纯函数，无 Vue 依赖，便于单测。
 */

export type RiskLevel = 'safe' | 'watch' | 'restricted' | 'high'

export interface RiskFlag {
  code: string
  category: string
  weight: number
  detail: string
  hint: string
  hardBlock: boolean
}

export interface RiskAssessment {
  score: number
  level: RiskLevel
  blocked: boolean
  flags: RiskFlag[]
  categories: string[]
  hints: string[]
}

/** 统一 6 维就医体验（与后端 EXPERIENCE_DIMENSIONS 一致） */
export const EXPERIENCE_DIMENSIONS = [
  { key: '挂号与预约', question: '号好不好挂？你是怎么挂到的？' },
  { key: '候诊与流程', question: '等了多久？指引和动线清楚吗？' },
  { key: '医患沟通', question: '医生有没有把方案和注意事项讲清楚？你的疑问得到回应了吗？' },
  { key: '费用与告知', question: '哪些是自费的？事先说明了吗？' },
  { key: '复诊与连续性', question: '复诊好约吗？需要异地来回跑吗？' },
  { key: '环境与隐私', question: '候诊环境、隐私保护、儿童或无障碍是否友好？' },
] as const

export const EXPERIENCE_LEVELS = [
  { key: 'satisfied', label: '满意' },
  { key: 'neutral', label: '一般' },
  { key: 'unsatisfied', label: '不满意' },
  { key: 'na', label: '没体验过' },
] as const

/** 禁止采集/展示的评价维度（疗效、医术、治愈率等） */
export const BANNED_DIMENSIONS = [
  '疗效', '治愈', '治愈率', '有效率', '好转率', '好转', '医术', '技术水平',
  '诊断准确', '误诊率', '死亡率', '复发率', '并发症', '根治', '排名', '排行',
  '最好', '第一', '推荐度',
]

/** 疗效/推广类用语（好评差评同一词库 —— 只审差评会漏掉变相推荐位） */
const PROMOTION_TERMS = [
  '根治', '治愈', '包治', '断根', '永不复发', '100%治愈', '百治百愈',
  '偏方根治', '祖传秘方', '特效药', '包好', '药到病除', '一劳永逸',
  '彻底治愈', '永不扩散', '保证治好', '完全康复', '痊愈了', '治好了',
  '都去这家', '强烈推荐这家', '必须去', '别去别家', '包治百病',
]

const INSULT_TERMS = [
  '骗子', '骗钱', '黑心', '无良', '谋财害命', '没医德', '医德败坏',
  '庸医', '垃圾医院', '垃圾医生', '坑人', '害人', '不要脸', '畜生',
  '去死', '滚出', '黑店', '抢钱',
]

const DEFAMATION_PATTERNS: [RegExp, string][] = [
  [/就是(?:误诊|错诊)/, '断言「就是误诊」'],
  [/肯定(?:是|就是)(?:医疗事故|误诊|治坏)/, '断言「肯定是医疗事故」'],
  [/(?:害|毁)(?:了)?我/, '断言对方「害了我」'],
  [/(?:把|给)我(?:治|看)(?:坏|死|残)/, '断言被治坏/治残'],
  [/(?:根本|完全)不(?:会|懂)(?:看病|治疗)/, '断言医生不会看病'],
]

const ORGANIZED_PATTERNS: [RegExp, string][] = [
  [/大家一起/, '号召「大家一起」'],
  [/维权群/, '提及「维权群」'],
  [/曝光(?:他|她|这家|该院)/, '号召「曝光」'],
  [/(?:联名|集体)(?:投诉|举报|上访)/, '号召联名/集体投诉'],
  [/(?:拉|建)(?:个)?群/, '组织建群'],
]

const AD_PATTERNS: [RegExp, string][] = [
  [/(?:加|留)(?:我)?(?:微信|weixin|vx|v信|扣扣|qq)/i, '引导加私人联系方式'],
  [/(?:私聊|私信)我/, '引导私聊'],
  [/(?:代购|转卖|出售)(?:药|号|名额)/, '药品/号源交易'],
]

const RECORD_PATTERNS: [RegExp, string][] = [
  [/病历号\s*[:：]?\s*\w{4,}/, '出现病历号'],
  [/住院号\s*[:：]?\s*\w{4,}/, '出现住院号'],
  [/(?:检验|检查)单号\s*[:：]?\s*\w{4,}/, '出现检验/检查单号'],
]

const HEARSAY_PATTERNS: [RegExp, string][] = [
  [/(?:听|据)(?:说|朋友说|别人说|同事说)/, '内容含转述（非亲身经历）'],
  [/(?:网上|群里)(?:都)?(?:说|传)/, '内容含网传信息'],
]

const PHONE_RE = /(?<!\d)1[3-9]\d{9}(?!\d)/
const ID_RE = /(?<!\d)\d{17}[\dXx](?!\d)/
const EMAIL_RE = /[\w.+-]+@[\w-]+\.[\w.]+/

export function levelForScore(score: number): RiskLevel {
  if (score >= 80) return 'high'
  if (score >= 60) return 'restricted'
  if (score >= 30) return 'watch'
  return 'safe'
}

function push(flags: RiskFlag[], flag: RiskFlag) {
  if (!flags.some(item => item.code === flag.code)) flags.push(flag)
}

/** 扫描评价文本，返回命中的风控标签。 */
export function scanReviewRisk(
  text: string,
  options: { doctorName?: string; tags?: string[] } = {},
): RiskFlag[] {
  const content = (text || '').trim()
  const flags: RiskFlag[] = []
  if (!content) return flags

  const firstPromotion = PROMOTION_TERMS.find(term => content.includes(term))
  if (firstPromotion) {
    push(flags, {
      code: `promotion:${firstPromotion}`, category: '疗效夸大', weight: 45,
      detail: `出现「${firstPromotion}」`,
      hint: '请改为第一人称的过程描述，例如「我治疗后白斑有变化」，不要写「根治/治愈」。',
      hardBlock: true,
    })
  }

  const firstInsult = INSULT_TERMS.find(term => content.includes(term))
  if (firstInsult) {
    push(flags, {
      code: `insult:${firstInsult}`, category: '侮辱性言辞', weight: 40,
      detail: `出现「${firstInsult}」`,
      hint: '把对人的评价改成对事的描述：把「XX 就是骗子」改成「我这次的费用构成没有提前告知」。',
      hardBlock: true,
    })
  }

  for (const [pattern, detail] of DEFAMATION_PATTERNS) {
    if (pattern.test(content)) {
      push(flags, {
        code: `defamation:${pattern.source}`, category: '断言性指控', weight: 35,
        detail,
        hint: '如果你认为诊疗存在问题，可以写清时间、经过和沟通过程；结论应由鉴定或调解机构作出。',
        hardBlock: false,
      })
      break
    }
  }

  if ((options.doctorName || '').trim() && (firstInsult || /(?:就是|肯定|根本).{0,6}(?:骗|坑|害|坏)/.test(content))) {
    push(flags, {
      code: 'named_accusation', category: '指名指控', weight: 30,
      detail: '内容同时出现具体医护称谓与贬损性表述',
      hint: '建议只描述你经历的服务过程，不针对具体医护人员下结论。',
      hardBlock: false,
    })
  }

  for (const [pattern, detail] of ORGANIZED_PATTERNS) {
    if (pattern.test(content)) {
      push(flags, {
        code: `organized:${pattern.source}`, category: '组织化维权', weight: 45,
        detail,
        hint: '组织集体维权不在本平台进行；可以走医院医患办、医疗纠纷人民调解委员会或 12345。',
        hardBlock: false,
      })
      break
    }
  }

  for (const [pattern, detail] of AD_PATTERNS) {
    if (pattern.test(content)) {
      push(flags, {
        code: `ad:${pattern.source}`, category: '引流广告', weight: 40, detail,
        hint: '请不要在评价里留联系方式或做药品、号源交易。',
        hardBlock: true,
      })
      break
    }
  }

  for (const [pattern, detail] of RECORD_PATTERNS) {
    if (pattern.test(content)) {
      push(flags, {
        code: `record:${pattern.source}`, category: '他人病历信息', weight: 40, detail,
        hint: '病历、检验单属于个人健康信息，请不要公开具体单号。',
        hardBlock: false,
      })
      break
    }
  }

  // 权重 <30：联系方式会被自动脱敏，属「可自动修复」，不应因此拦下正常评价
  if (PHONE_RE.test(content) || ID_RE.test(content) || EMAIL_RE.test(content)) {
    push(flags, {
      code: 'contact_info', category: '联系方式', weight: 20,
      detail: '出现手机号/邮箱/证件号',
      hint: '系统会自动脱敏，建议直接删除这些信息。',
      hardBlock: false,
    })
  }

  for (const [pattern, detail] of HEARSAY_PATTERNS) {
    if (pattern.test(content)) {
      push(flags, {
        code: `hearsay:${pattern.source}`, category: '非亲身经历', weight: 15, detail,
        hint: '只写你自己经历的部分更有参考价值。',
        hardBlock: false,
      })
      break
    }
  }

  if (/[!！]{3,}/.test(content) || /[?？]{4,}/.test(content)) {
    push(flags, {
      code: 'emotional_punctuation', category: '情绪强度', weight: 12,
      detail: '连续感叹号/问号',
      hint: '语气平和的描述更容易被其他病友采信。',
      hardBlock: false,
    })
  }

  const letters = content.match(/[A-Za-z]/g) || []
  if (letters.length >= 12 && letters.every(letter => letter === letter.toUpperCase())) {
    push(flags, {
      code: 'emotional_caps', category: '情绪强度', weight: 10,
      detail: '大段全大写英文',
      hint: '建议改用正常大小写。',
      hardBlock: false,
    })
  }

  for (const tag of options.tags || []) {
    const banned = BANNED_DIMENSIONS.find(word => String(tag).includes(word))
    if (banned) {
      push(flags, {
        code: 'banned_tag', category: '疗效夸大', weight: 45,
        detail: `标签含禁止维度「${tag}」`,
        hint: '疗效类标签不采集，请改用中性体验标签。',
        hardBlock: true,
      })
      break
    }
  }

  return flags
}

/** 综合评估：权重求和（封顶 100）+ 分档。 */
export function assessReviewRisk(
  text: string,
  options: { doctorName?: string; tags?: string[] } = {},
): RiskAssessment {
  const flags = scanReviewRisk(text, options)
  const score = Math.min(100, flags.reduce((sum, flag) => sum + flag.weight, 0))
  const hints: string[] = []
  for (const flag of flags) {
    if (flag.hint && !hints.includes(flag.hint)) hints.push(flag.hint)
  }
  return {
    score,
    level: levelForScore(score),
    blocked: flags.some(flag => flag.hardBlock),
    flags,
    categories: [...new Set(flags.map(flag => flag.category))],
    hints: hints.slice(0, 4),
  }
}

/** 医生称谓脱敏（与后端 sanitize_doctor_name 行为一致，用于发布前预览）。 */
export function sanitizeDoctorName(raw: string, department = ''): string {
  const text = (raw || '').trim()
  if (!text) return ''
  const honorific = text.includes('主任') ? '主任' : text.includes('教授') ? '教授' : '医生'
  const core = text
    .replace(/(主任医师|副主任医师|主治医师|住院医师|主任|教授|医师|医生|大夫|老师)/g, '')
    .replace(/[　 ·,，.。]/g, '')
  const match = core.match(/[\u4e00-\u9fa5A-Za-z]/)
  const label = match ? `${match[0]}${honorific}` : `某${honorific}`
  const dept = (department || '').replace(/[（）()\s]/g, '').slice(0, 20)
  return dept ? `${label}（${dept}）` : label
}

/**
 * 就医体验「具体性」自检：命中 ≥3 个要素给正反馈（提示而非阻断）。
 * 五要素来自好大夫「就诊经验最重要、写详细些」的引导思路。
 */
const SPECIFICITY_SIGNALS: [RegExp, string][] = [
  [/(?:月|号|上周|去年|今年|昨天|今天|初诊|复诊)/, '时间'],
  [/(?:挂号|门诊|专家|普通号|号源|预约)/, '流程'],
  [/(?:费用|自费|医保|多少钱|元|价格|收费)/, '费用'],
  [/(?:医生|护士|主任|大夫|科室|沟通|解释)/, '沟通'],
  [/(?:复诊|随访|复查|下次|后续)/, '复诊'],
  [/(?:光疗|308|uvb|药|外用|口服|方案|治疗)/i, '治疗'],
]

export function specificityScore(text: string): { hit: number; labels: string[] } {
  const content = text || ''
  const labels = SPECIFICITY_SIGNALS.filter(([pattern]) => pattern.test(content)).map(([, label]) => label)
  return { hit: labels.length, labels }
}
