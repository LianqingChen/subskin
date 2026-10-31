/**
 * 「调养」内容目录（V1：静态选购指南，无真实品牌/价格/购买链接）。
 *
 * 口径约束（见 docs/design/2026-09-30-care-module-design.md §7）：
 * - 与百科 diet.md 一致：食物、铜器、用品都不是治疗手段，不能写任何功效；
 * - 保健食品只讲选购要点，不给剂量；
 * - 将来接入分销链接时，给条目加 buyUrl，页面会自动显示「推广」标识与「去购买」。
 *
 * 2026-10-02 起：「调养」按分类组织选购参考，详情保留护理依据与风险，本机清单不代表订单。
 * 原分享科普/种草路径保留兼容访问，但不再作为分享首页频道；
 * 购买一律跳转外部链接（buyUrl），站内不收款、不下单。
 */
export type EvidenceLevel = 'supported' | 'limited' | 'doctor' | 'lifestyle'

export interface EvidenceMeta { label: string; icon: string; hint: string; badge: string }

export const EVIDENCE: Record<EvidenceLevel, EvidenceMeta> = {
  supported: { label: '有研究支持', icon: 'ri-shield-check-line', hint: '有指南或研究支持的日常做法', badge: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200' },
  limited: { label: '证据有限', icon: 'ri-scales-3-line', hint: '民间常用，缺少直接的疗效证据，不是治疗', badge: 'bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200' },
  doctor: { label: '遵医嘱', icon: 'ri-stethoscope-line', hint: '与用药或检查结果相关，请先问医生', badge: 'bg-sky-50 text-sky-800 dark:bg-sky-900/30 dark:text-sky-200' },
  lifestyle: { label: '生活品质', icon: 'ri-sparkling-2-line', hint: '与疗效无关，只是让日常更方便', badge: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200' },
}

export interface CareItem {
  id: string
  name: string
  /** 为什么放在这里（不写功效） */
  why: string
  /** 选购要点 */
  pick: string[]
  /** guide＝选购指南；planned＝规划中，先收集需求 */
  status: 'guide' | 'planned'
  /** 接入分销后填写；有值时显示「推广」标识与「去购买」 */
  buyUrl?: string
  /** 参考价（元）；未填写时显示「价格待定」，购物车不汇总 */
  price?: number
  /** 规格，如「500g / 袋」 */
  spec?: string
}

export interface CareTopic {
  id: string
  title: string
  icon: string
  evidence: EvidenceLevel
  summary: string
  pickGuide: string[]
  cautions: string[]
  items: CareItem[]
}

export const CARE_TOPICS: CareTopic[] = [
  {
    id: 'food',
    title: '日常食材',
    icon: 'ri-seedling-line',
    evidence: 'limited',
    summary: '黑芝麻、黑豆、核桃等是日常饮食里的好食材，含有蛋白质、不饱和脂肪酸和多种微量元素。目前没有充分证据表明吃某种食物能让白斑变黑，也不必为此大量、单一地吃。把它们当作均衡饮食的一部分就好。',
    pickGuide: [
      '看配料表，越短越好，优先「只有黑芝麻」这类单一原料',
      '芝麻糊、黑豆粉注意含糖量，选无额外添加糖的',
      '坚果选原味、未过度加工；开封后密封防潮，尽快吃完',
      '对坚果、芝麻过敏的人不要尝试',
    ],
    cautions: [
      '它们不是治疗白癜风的药物，不能替代药物和光疗',
      '没有哪种普通食物需要一律忌口；不要因为焦虑而极端节食',
    ],
    items: [
      { id: 'food-sesame', name: '黑芝麻', why: '撒在粥、豆浆里，增加饮食的多样性', pick: ['选颗粒饱满、无哈喇味的', '整粒不易消化，研磨后更容易吃到'], status: 'guide' },
      { id: 'food-black-bean', name: '黑豆', why: '优质植物蛋白来源，煮粥、打豆浆都合适', pick: ['选颗粒均匀、无虫蛀霉变的', '提前浸泡再煮，更软烂'], status: 'guide' },
      { id: 'food-walnut', name: '核桃', why: '原味坚果，适合作为随手的健康零食', pick: ['选原味，不要盐焗、糖渍的', '一天一小把即可，热量不低'], status: 'guide' },
      { id: 'food-black-peanut', name: '黑花生', why: '口感好，适合作零食或佐餐', pick: ['带壳的更容易保存', '选少盐少油的做法'], status: 'guide' },
      { id: 'food-sesame-paste', name: '黑芝麻糊', why: '早餐的便捷选择', pick: ['看配料表，选无额外添加糖的', '对比每份含糖量，别只看口味'], status: 'guide' },
    ],
  },
  {
    id: 'copper',
    title: '日常餐具',
    icon: 'ri-restaurant-line',
    evidence: 'limited',
    summary: '铜参与体内黑色素合成相关酶的活性，所以「补铜」常被病友提起。但目前没有可靠证据表明使用铜器皿或额外补铜能改善白癜风；多数人从日常饮食（坚果、豆类、全谷物、海鲜）中摄入的铜已经够用，过量补铜反而有害。',
    pickGuide: [
      '想补铜，先从饮食入手；是否缺铜，请让医生检测后判断',
      '如果只是喜欢铜质餐具，选明确标注「食品级」、能提供检测报告的产品',
      '铜碗、铜勺不要长时间盛放醋、果汁等酸性食物',
    ],
    cautions: [
      '不要因为用了铜器就自行停药或减少治疗',
      '有肝豆状核变性（Wilson 病）等铜代谢问题的人不能额外补铜，须遵医嘱',
    ],
    items: [
      { id: 'copper-bowl', name: '铜碗', why: '喜欢铜质器皿的人的日常选择，当作餐具，而不是「补药」', pick: ['认准食品级，索要检测报告', '内壁光滑、易清洗', '不盛酸性食物过夜'], status: 'guide' },
      { id: 'copper-spoon', name: '铜勺', why: '和铜碗搭配使用的餐具', pick: ['认准食品级', '手柄隔热、重量适中'], status: 'guide' },
      { id: 'copper-chopsticks', name: '铜筷子', why: '日常餐具的一种选择', pick: ['认准食品级', '表面光滑无毛刺，避免划伤口腔'], status: 'guide' },
    ],
  },
  {
    id: 'nutrition',
    title: '维生素与营养',
    icon: 'ri-capsule-line',
    evidence: 'doctor',
    summary: '部分研究观察到，白癜风患者中维生素 D、B12、叶酸等偏低的情况更常见，缺乏时应当纠正。但并没有证据显示「水平正常还额外大量补充」能让白斑变化。补什么、补多少，请先检查，再由医生决定。日常吃水果蔬菜里的维生素 C，不需要刻意回避。',
    pickGuide: [
      '先做血液检查，再决定补不补',
      '保健食品认准包装上的「蓝帽子」标志和批准文号',
      '看清每份含量和每日建议量，别叠加多种产品导致超量',
      '正在用药或有慢性病，先问医生',
    ],
    cautions: [
      '本页不提供也不推荐具体剂量，请以医嘱为准',
      '保健食品不能代替药物',
    ],
    items: [
      { id: 'nutrition-d', name: '维生素 D 补充剂', why: '检查提示偏低时，医生常会建议补充', pick: ['先确认检测结果再买', '按医嘱选规格，不自行加量'], status: 'guide' },
      { id: 'nutrition-b12-folate', name: 'B12 / 叶酸类补充剂', why: '检查提示缺乏时，在医生指导下使用', pick: ['先确认检测结果再买', '同类成分的产品不要叠加服用'], status: 'guide' },
    ],
  },
  {
    id: 'sun',
    title: '防晒与遮盖',
    icon: 'ri-sun-line',
    evidence: 'supported',
    summary: '白斑处缺少黑色素的保护，更容易被晒伤，而晒伤可能诱发新的白斑。防晒是各类诊疗指南都会提到的日常护理，也是最值得认真做的一件事。',
    pickGuide: [
      '物理防晒（氧化锌、二氧化钛）对敏感皮肤更温和；日常 SPF30+、PA+++ 足够',
      '出门前 15–30 分钟涂抹，室外每 2–3 小时补涂',
      '衣物防晒更省心：防晒衣、帽子、袖套',
      '遮盖产品只用于美观，不会让白斑复色；先在耳后小范围试用',
    ],
    cautions: [
      '完全不见光会影响维生素 D，日常适度户外即可，避开正午强烈日晒',
      '涂抹后出现红肿、瘙痒，立即停用',
    ],
    items: [
      { id: 'sun-mineral', name: '物理防晒霜', why: '面部、手背等长期暴露部位的日常防护', pick: ['优先成分表里有氧化锌或二氧化钛', '质地不搓泥、容易补涂的更容易坚持'], status: 'guide' },
      { id: 'sun-clothing', name: '防晒衣 / 帽 / 袖套', why: '不靠涂抹，穿上就有遮挡', pick: ['看 UPF 标识（UPF50+ 更好）', '透气、速干，夏天才穿得住'], status: 'guide' },
      { id: 'sun-cover', name: '白斑遮盖产品', why: '需要时让外观更自在，不改变病情', pick: ['先在耳后小范围试用', '选易卸除、不含刺激性成分的'], status: 'guide' },
    ],
  },
  {
    id: 'tools',
    title: '记录工具',
    icon: 'ri-camera-lens-line',
    evidence: 'lifestyle',
    summary: '想看清楚变化，关键是每次拍得一样。下面两件是为「日记」准备的拍摄辅助，还在规划中，先看看你是否需要。',
    pickGuide: [
      '同一部位尽量固定距离、角度和光线',
      '拍摄时让照片里带上参照物，后面换算大小和对比颜色才可靠',
    ],
    cautions: [
      '紫外光对眼睛有伤害，不要直射眼睛，也不要近距离长时间照射',
      '家用紫外灯只能辅助观察，不能用来诊断，也不能替代医院的检查',
    ],
    items: [
      { id: 'tools-marker', name: 'SubSkin 标定贴纸', why: '贴在白斑旁一起拍：校正颜色、换算实际大小、对齐两次照片', pick: ['含定位码、灰阶和色块', '价格与发售时间待定'], status: 'planned' },
      { id: 'tools-uv', name: '紫外手机夹灯（365nm）', why: '部分浅肤色用户在紫外光下更容易看清白斑边界，仅作辅助观察', pick: ['只会选有安全认证的产品', '使用时避免照到眼睛'], status: 'planned' },
    ],
  },
]

/** 商品图占位底色（按主体区分；接入商品图后仅作加载底色） */
export const TOPIC_TINT: Record<string, string> = {
  food: 'from-amber-100 to-orange-50 text-amber-700 dark:from-amber-900/40 dark:to-orange-900/20 dark:text-amber-200',
  copper: 'from-orange-100 to-rose-50 text-orange-700 dark:from-orange-900/40 dark:to-rose-900/20 dark:text-orange-200',
  nutrition: 'from-sky-100 to-cyan-50 text-sky-700 dark:from-sky-900/40 dark:to-cyan-900/20 dark:text-sky-200',
  sun: 'from-yellow-100 to-lime-50 text-yellow-700 dark:from-yellow-900/40 dark:to-lime-900/20 dark:text-yellow-200',
  tools: 'from-primary-100 to-teal-50 text-primary-700 dark:from-primary-900/40 dark:to-teal-900/20 dark:text-primary-200',
}

export function formatPrice(item: CareItem): string {
  return item.price === undefined ? '价格待定' : `¥${item.price.toFixed(item.price % 1 ? 2 : 0)}`
}

export const CARE_ITEM_INDEX: Record<string, { item: CareItem; topic: CareTopic }> = Object.fromEntries(
  CARE_TOPICS.flatMap(topic => topic.items.map(item => [item.id, { item, topic }] as const)),
)
