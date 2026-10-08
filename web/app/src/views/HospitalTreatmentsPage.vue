<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
const active = ref('topical')
const collapsed = ref(false)
const topics = [
  { id: 'topical', title: '外用治疗', icon: 'ri-medicine-bottle-line', brief: '医生可能根据部位、年龄和病情选择外用药物。',
    detail: '常见类别包括外用糖皮质激素、钙调神经磷酸酶抑制剂等。药物强度、使用部位和疗程需要个体评估，不能照搬病友的处方。',
    watch: '哪些地方能涂、多久复查、出现刺激怎么处理，都需要提前问清。不要自行延长疗程。', questions: ['我的部位和年龄适合哪一类？', '怎样判断需要复查或调整？', '与其他外用产品如何安排？'] },
  { id: 'light', title: '光疗', icon: 'ri-sun-line', brief: '窄谱 UVB、308 nm 准分子光/激光是常见光疗方式。',
    detail: '光疗通常需要连续安排多次治疗，是否适合、采用哪一种以及怎样与药物配合，由医生评估。家用设备也需要专业指导。',
    watch: '提前考虑往返、排班和长期时间投入。照射参数不能照抄他人；出现明显红痛、水疱等情况应及时联系诊疗团队。', questions: ['需要怎样的频次和复查安排？', '单次费用按什么计算，医保如何结算？', '漏做一次或出现红痛该怎样处理？'] },
  { id: 'systemic', title: '系统治疗', icon: 'ri-capsule-line', brief: '部分进展期或其他特定情况，需要医生评估系统治疗。',
    detail: '系统治疗可能涉及口服等方式，需权衡病情、基础疾病与监测要求。JAK 抑制剂等新治疗的适应证、年龄限制及可及性，应逐药核实国内最新说明书。',
    watch: '海外获批或病友用过，不代表国内适应证相同，也不代表适合你。不自行买药、加量或停药。', questions: ['目前为什么需要这项治疗？', '开始前和治疗中需要哪些检查？', '与我正在使用的药物有冲突吗？'] },
  { id: 'surgery', title: '手术治疗', icon: 'ri-surgical-mask-line', brief: '移植等方式只适用于经过筛选的部分患者。',
    detail: '医生需要评估疾病稳定性、皮损部位和范围等因素，再讨论是否适合手术。它不是所有白斑都能采用的常规第一步。',
    watch: '在决定前问清术前评估、术后照护、可能风险和复诊安排，不能只看个别前后对比照片。', questions: ['怎样判断我的病情足够稳定？', '有哪些风险和其他选择？', '术后护理与后续治疗如何安排？'] },
  { id: 'support', title: '日常与心理支持', icon: 'ri-heart-line', brief: '防晒、外观遮盖和心理支持也可以纳入照护。',
    detail: '治疗目标可以包括减少生活困扰、保护皮肤、改善生活质量。与医生讨论你的期待，不必把他人的变化速度当作自己的标准。',
    watch: '谨慎对待“包治”“根治”和必须预付高额套餐的承诺。保留费用明细与沟通记录；需要时通过正规渠道咨询或反映问题。', questions: ['日常皮肤护理需要注意什么？', '情绪困扰时可以获得哪些支持？', '怎样记录病情并与医生讨论变化？'] },
]
let schema: HTMLScriptElement | undefined
onMounted(() => {
  schema = document.createElement('script')
  schema.type = 'application/ld+json'
  schema.textContent = JSON.stringify({ '@context': 'https://schema.org', '@type': 'MedicalWebPage',
    name: '白癜风治疗知识', description: '常见治疗类别与就诊前沟通清单，不提供个体治疗建议',
    dateModified: '2026-09-16', url: `${location.origin}/hospitals/treatments` })
  document.head.appendChild(schema)
})
onBeforeUnmount(() => schema?.remove())
</script>
<template>
  <div class="page pb-8 pt-4 text-gray-900 dark:text-gray-100 md:pt-6">
    <header class="mb-6">
      <p class="text-xs font-medium tracking-widest text-primary-700 dark:text-primary-300">就诊前，先了解一些基本知识</p>
      <h1 class="page-title mt-2">白癜风治疗知识</h1>
      <p class="mt-3 max-w-3xl text-sm leading-6 text-gray-600 dark:text-gray-300">治疗需要结合类型、进展情况、部位、年龄和个人目标讨论。这里帮助你准备问题，不替你选择药物或判断哪家医院更好。</p>
      <MedicalDisclaimer class="mt-3" variant="inline" message="本文不构成医疗建议。仅作通用知识整理，尚未经本站临床医师审阅；具体方案请与医生讨论。" />
    </header>
    <div class="flex min-w-0 flex-col gap-6 md:flex-row">
      <aside class="relative shrink-0" :class="collapsed ? 'md:w-11' : 'md:w-52'">
        <nav aria-label="治疗知识分类" class="flex gap-2 overflow-x-auto md:sticky md:top-20 md:block md:space-y-2">
          <button v-for="topic in topics" :key="topic.id" :aria-pressed="active === topic.id" :title="topic.title" class="flex min-h-11 shrink-0 items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm md:w-full" :class="active === topic.id ? 'bg-primary-50 font-medium text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800'" @click="active = topic.id"><i :class="topic.icon" aria-hidden="true" /><span :class="collapsed ? 'md:sr-only' : ''">{{ topic.title }}</span></button>
        </nav>
        <button class="absolute -right-4 top-36 hidden min-h-11 w-6 rounded-full border border-gray-200 bg-white text-gray-500 dark:border-gray-700 dark:bg-gray-900 md:block" :aria-label="collapsed ? '展开知识分类' : '收起知识分类'" :aria-expanded="!collapsed" @click="collapsed = !collapsed"><i :class="collapsed ? 'ri-arrow-right-s-line' : 'ri-arrow-left-s-line'" aria-hidden="true" /></button>
      </aside>
      <div class="min-w-0 flex-1 space-y-5">
        <article v-for="topic in topics.filter(item => item.id === active)" :key="topic.id" class="card p-5 dark:bg-gray-900 md:p-6">
          <span class="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-50 text-2xl text-primary-600 dark:bg-primary-900 dark:text-primary-300"><i :class="topic.icon" aria-hidden="true" /></span>
          <h2 class="mt-4 text-xl font-semibold">{{ topic.title }}</h2>
          <p class="mt-2 text-sm font-medium leading-6">{{ topic.brief }}</p>
          <p class="mt-3 text-sm leading-7 text-gray-600 dark:text-gray-300">{{ topic.detail }}</p>
          <section class="mt-5 rounded-xl bg-gray-50 p-4 dark:bg-gray-800"><h3 class="text-base font-medium">需要留意</h3><p class="mt-2 text-sm leading-7 text-gray-600 dark:text-gray-300">{{ topic.watch }}</p></section>
          <section class="mt-5"><h3 class="text-base font-medium">可以带去问医生</h3><ul class="mt-3 space-y-3"><li v-for="question in topic.questions" :key="question" class="flex gap-2 text-sm leading-6 text-gray-600 dark:text-gray-300"><i class="ri-question-line text-primary-600 dark:text-primary-300" aria-hidden="true" />{{ question }}</li></ul></section>
        </article>
        <section class="card p-5 dark:bg-gray-900" aria-labelledby="treatment-sources"><h2 id="treatment-sources" class="text-lg font-semibold">资料来源与阅读边界</h2><p class="mt-2 text-xs leading-6 text-gray-500 dark:text-gray-400">整理日期：2026-09-16。以下为国际指南与患者资料，不能替代国内药品说明书、面诊或个体治疗计划。未提供药物剂量、照射参数或效果承诺。</p><ul class="mt-3 space-y-2 text-sm text-primary-700 dark:text-primary-300"><li><a class="inline-flex min-h-11 items-center underline" href="https://pubmed.ncbi.nlm.nih.gov/37715487/" target="_blank" rel="noopener noreferrer">2023 国际白癜风专家建议 · PMID 37715487</a></li><li><a class="inline-flex min-h-11 items-center underline" href="https://www.bad.org.uk/pils/vitiligo" target="_blank" rel="noopener noreferrer">英国皮肤科医师协会 · 白癜风患者资料</a></li><li><a class="inline-flex min-h-11 items-center underline" href="https://www.nhs.uk/conditions/vitiligo/treatment/" target="_blank" rel="noopener noreferrer">NHS · 白癜风治疗概览</a></li></ul></section>
      </div>
    </div>
  </div>
</template>
