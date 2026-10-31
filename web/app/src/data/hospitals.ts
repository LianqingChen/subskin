import { EXPERIENCE_DIMENSIONS } from '@/utils/reviewRiskRules'
import type { Hospital } from '@/types/hospital'

// Editorial seed directory, not a ranking. No review counts, scores or efficacy claims.
// Approximate city centers below are NOT hospital geocoding or navigation coordinates.
export const HOSPITALS: Hospital[] = [
  { id: 'pumch', name: '北京协和医院', province: '北京', city: '北京', district: '东城区', address: '北京市东城区帅府园1号（东院）/ 西城区大木仓胡同41号（西院）', department: '皮肤科', kind: '综合医院', features: ['皮肤科诊疗'], summary: '官方皮肤科医师介绍列有白癜风诊疗方向。请在官方渠道核对院区及普通、专病或专家门诊。', source: 'https://www.pumch.cn/department_ims/dsearchs/dockerinfo/__techang__/__keshiname__/__title__/1%C3%9F%27/13.html', checkedAt: '2026-09-10', lat: 39.9148, lng: 116.4178 },
  { id: 'huashan', name: '复旦大学附属华山医院', province: '上海', city: '上海', district: '静安区', address: '上海市静安区乌鲁木齐中路12号', department: '皮肤科', kind: '综合医院', features: ['白癜风专病门诊', '皮肤外科'], summary: '官方科室介绍列有白癜风专病门诊及相关皮肤外科诊疗。具体适用方案需经面诊评估。', source: 'https://www.huashan.org.cn/xueke/detail/12.html', checkedAt: '2026-09-10', lat: 31.2155, lng: 121.4468 },
  { id: 'pumcderm', name: '中国医学科学院皮肤病医院', province: '江苏', city: '南京', district: '玄武区', address: '江苏省南京市玄武区蒋王庙街12号', department: '皮肤内科', kind: '皮肤病专科', features: ['皮肤科诊疗'], summary: '官方皮肤内科介绍列有白癜风的基础与临床诊疗研究。就诊科室及排班以医院发布为准。', source: 'https://www.pumcderm.net/list/92.html', checkedAt: '2026-09-10', lat: 32.0838, lng: 118.8256 },
  { id: 'westchina', name: '四川大学华西医院', province: '四川', city: '成都', district: '武侯区', address: '四川省成都市武侯区国学巷37号', department: '皮肤性病科', kind: '综合医院', features: ['白癜风诊疗组', '光疗中心'], summary: '官方科室介绍列有白癜风专病研究诊疗组、光疗中心和皮肤外科等服务。', source: 'https://www.wchscu.cn/department_pfxbk.html', checkedAt: '2026-09-10', lat: 30.6409, lng: 104.0624 },
  { id: 'xjtu1', name: '西安交通大学第一附属医院', province: '陕西', city: '西安', district: '雁塔区', address: '陕西省西安市雁塔区雁塔西路277号', department: '皮肤科', kind: '综合医院', features: ['窄谱UVB', '308准分子光'], summary: '官方科室介绍列有用于白癜风诊疗的窄谱中波紫外线、308准分子光设备。当前可用情况请向科室确认。', source: 'https://www.dyyy.xjtu.edu.cn/lmby/ksdh_bf/nkxt/pfk.htm', checkedAt: '2026-09-10', lat: 34.2185, lng: 108.9328 },
  { id: 'gz12', name: '广州市第十二人民医院', province: '广东', city: '广州', district: '天河区', address: '广东省广州市天河区黄埔大道西天强街1号', department: '皮肤科', kind: '综合医院', features: ['皮肤科诊疗'], summary: '官方皮肤科介绍列有白癜风相关诊疗服务。治疗方式和就诊安排以科室评估及最新公告为准。', source: 'https://www.gz12hospital.cn/zk/mz/pf/', checkedAt: '2026-09-10', lat: 23.1298, lng: 113.3242 },
  { id: 'yueyang', name: '上海中医药大学附属岳阳中西医结合医院', province: '上海', city: '上海', district: '虹口区', address: '上海市虹口区甘河路110号', department: '皮肤科', kind: '综合医院', features: ['白癜风专病门诊', '中西医结合'], summary: '医院官方健康教育页面列有皮肤科白癜风专病门诊。具体出诊院区及安排需在官方渠道核对。', source: 'https://www.shyueyanghospital.com/Html/News/Articles/16097.html', checkedAt: '2026-09-10', lat: 31.2858, lng: 121.4886 },
]
// 统一 6 维就医体验：唯一事实来源是 utils/reviewRiskRules（与后端 review_risk.py 对齐）。
// 旧版 4 维星级（医护沟通/方案解释/费用透明/复诊便利）仅用于兼容展示历史评价。
export const EXPERIENCE_DIMENSION_KEYS = EXPERIENCE_DIMENSIONS.map(item => item.key)
export const REVIEW_DIMENSIONS_LEGACY = ['医护沟通', '方案解释', '费用透明', '复诊便利']
// 中性措辞：只描述病友的个人感受，不做医院水平或疗效的定性
export const REVIEW_TAGS_GOOD = ['解释耐心', '费用清楚', '不乱加项', '复诊方便', '异地可接续', '儿童友好', '设备齐全', '指引清楚']
export const REVIEW_TAGS_WATCH = ['候诊较久', '需多次往返', '自费项目多', '排期等待', '沟通时间短', '停车不便', '异地成本高']
/** 全部可选标签（展示与聚合共用） */
export const REVIEW_TAGS = [...REVIEW_TAGS_GOOD, ...REVIEW_TAGS_WATCH]
/** 历史版本标签，仅用于兼容展示旧评价 */
export const REVIEW_TAGS_LEGACY = ['儿童就诊', '异地就医']

// 治疗方案评价的常见选项（仅作输入建议，不构成推荐）
export const TREATMENT_OPTIONS = [
  '308 准分子光', '窄谱 UVB（NB-UVB）', '外用激素', '钙调神经磷酸酶抑制剂（他克莫司等）',
  'JAK 抑制剂（外用）', 'JAK 抑制剂（口服）', '口服激素/免疫抑制剂', '中医中药',
  '表皮移植/黑素细胞移植', '遮盖或化妆', '仅观察随访',
]


// Explicit city centers: the older shared city list omits several prefecture capitals.
export const HOSPITAL_CITIES = [
  { name: '北京', province: '北京', lat: 39.9042, lng: 116.4074 },
  { name: '上海', province: '上海', lat: 31.2304, lng: 121.4737 },
  { name: '南京', province: '江苏', lat: 32.0603, lng: 118.7969 },
  { name: '成都', province: '四川', lat: 30.5728, lng: 104.0668 },
  { name: '西安', province: '陕西', lat: 34.3416, lng: 108.9398 },
  { name: '广州', province: '广东', lat: 23.1291, lng: 113.2644 },
]
