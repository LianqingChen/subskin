<script setup lang="ts">
/**
 * 就医经验社区公约（/hospitals/rules）。
 *
 * 《网络信息内容生态治理规定》第 15 条要求平台制定并公开管理规则和平台公约，
 * 第 16 条要求显著位置设置便捷的投诉举报入口并反馈处理结果 —— 本页即为该要求的落地，
 * 同时也是给用户看的「怎么写、什么不能写、被误判怎么办」说明。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'

const RULES = [
  {
    icon: 'ri-user-voice-line',
    title: '只写你亲身经历的',
    items: [
      '写你自己这一次或这一段时间的就诊体验：挂号、候诊、沟通、费用、复诊怎么安排。',
      '不写听来的、网传的、别人转述的内容；不确定的信息不要当成事实陈述。',
      '同一次就诊写一条即可，不要重复刷同一条评价。',
    ],
  },
  {
    icon: 'ri-forbid-2-line',
    title: '这些内容不允许发布',
    items: [
      '侮辱性言辞（如「骗子」「黑心」「庸医」等）—— 这是名誉权案件中最常见的败诉原因，也会被平台拦截。',
      '没有依据的结论性指控（如「就是误诊」「肯定是医疗事故」）—— 请通过法定渠道主张权利。',
      '疗效类表述（「根治」「治愈」「保证治好」「100% 有效」）—— 平台不采集也不展示疗效评价。',
      '泄露他人隐私：他人病历号、住院号、检验单号、手机号、身份证号、家庭住址。',
      '引流广告：留联系方式、拉群、代购或转卖药品与号源。',
      '组织化维权：号召集体投诉、建维权群、曝光他人。',
      '病情照片（尤其是他人病情照片）。凭证图只允许费用单、挂号单、处方、检查单。',
    ],
  },
  {
    icon: 'ri-shield-user-line',
    title: '我们如何保护你与他人',
    items: [
      '评价可能包含与健康相关的信息，属敏感个人信息：发布前需要你单独勾选同意，我们不会默认替你勾选。',
      '手机号、邮箱、证件号等会自动脱敏后再公开；凭证图只有你和管理员能看到，公开层只显示「已上传」徽标。',
      '医生姓名会被自动收敛为「张医生（皮肤科）」这类不可识别称谓，不公开展示可识别身份。',
      '你可以随时删除自己的评价；删除后其他病友立即看不到。',
    ],
  },
  {
    icon: 'ri-scales-3-line',
    title: '我们不做的事',
    items: [
      '不做医疗实力综合榜、医生医术排名或付费推荐位。体验评价仅按单个就医维度展示分布，并允许用户主动选择体验排序。',
      '单项体验排序采用最近 365 天、每账号每医院最新一条已同意公开且审核通过、冷处理结束的评价；该项至少 20 位独立评价者作答。没体验过不计分，样本不足不排名。',
      '体验排序使用满意比例的 95% Wilson 下界，减小小样本对排序的影响。账号去重不是就诊核验，结果存在自愿分享偏差。具体方法见就医经验页的体验评价。',
      '不采集、不聚合、不展示治愈率、有效率、好转率等疗效指标。',
      '不做付费删差评、付费置顶好评（《网络信息内容生态治理规定》第 22 条明文禁止）。',
      '不在评价区放置挂号、导诊等转化入口 —— 避免让病友的真实经历变成变相的医疗推广。',
    ],
  },
  {
    icon: 'ri-error-warning-line',
    title: '情绪上来了怎么办',
    items: [
      '先说事实：把「他就是骗子」换成「这次的费用构成没有提前告知」，更容易被其他病友采信。',
      '如果确实认为诊疗存在问题，可以走这些渠道：就诊医院医务处/医患关系办公室、医疗纠纷人民调解委员会、12345 或当地卫健委。',
      '发布前如果命中情绪化或结论性表述，我们会弹出「发布前提醒」请你确认，并给出改写建议 —— 这是提醒，不是封口。',
    ],
  },
]

const schema = ref<HTMLScriptElement>()
onMounted(() => {
  schema.value = document.createElement('script')
  schema.value.type = 'application/ld+json'
  schema.value.textContent = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name: '就医经验社区公约',
    description: 'SubSkin 就医经验模块的评价规范、禁止内容、隐私保护与申诉渠道',
    url: `${location.origin}/hospitals/rules`,
  })
  document.head.appendChild(schema.value)
})
onBeforeUnmount(() => schema.value?.remove())
</script>

<template>
  <div class="page-narrow pb-8 pt-4 text-gray-900 dark:text-gray-100 md:pt-6">
    <nav class="mb-4 text-xs text-gray-500 dark:text-gray-400" aria-label="面包屑">
      <RouterLink class="underline" to="/hospitals">就医经验</RouterLink>
      <span class="mx-1">/</span><span>社区公约</span>
    </nav>

    <header class="mb-6">
      <h1 class="page-title">就医经验社区公约</h1>
      <p class="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">
        就医经验是病友之间的<strong>就医体验分享</strong>，不评比医疗水平或疗效。为了让这里的信息对后面的病友真正有用，
        体验排序只反映样本中的个人感受；为了保护你、医护人员和其他病友的合法权益，请一起遵守下面的规则。
      </p>
    </header>

    <div class="space-y-4">
      <section v-for="rule in RULES" :key="rule.title" class="card p-4 dark:bg-gray-900 md:p-5">
        <h2 class="flex items-center gap-2 text-base font-semibold">
          <i :class="rule.icon" class="text-primary-600 dark:text-primary-300" aria-hidden="true" />{{ rule.title }}
        </h2>
        <ul class="mt-3 space-y-2 text-sm leading-6 text-gray-600 dark:text-gray-300">
          <li v-for="item in rule.items" :key="item" class="flex gap-2">
            <i class="ri-checkbox-blank-circle-fill mt-2 text-[6px] text-gray-300 dark:text-gray-600" aria-hidden="true" />
            <span>{{ item }}</span>
          </li>
        </ul>
      </section>

      <section class="card p-4 dark:bg-gray-900 md:p-5">
        <h2 class="flex items-center gap-2 text-base font-semibold">
          <i class="ri-service-line text-primary-600 dark:text-primary-300" aria-hidden="true" />违规怎么处理
        </h2>
        <ul class="mt-3 space-y-2 text-sm leading-6 text-gray-600 dark:text-gray-300">
          <li class="flex gap-2"><i class="ri-checkbox-blank-circle-fill mt-2 text-[6px] text-gray-300 dark:text-gray-600" aria-hidden="true" /><span>发布前：命中禁止内容会拦截并给出改写建议；命中情绪化或结论性表述会请你先确认。</span></li>
          <li class="flex gap-2"><i class="ri-checkbox-blank-circle-fill mt-2 text-[6px] text-gray-300 dark:text-gray-600" aria-hidden="true" /><span>发布后：系统会做一次风险复核。低风险内容照常公开；涉及结论性指控或收到多条举报的评价会进入人工复核，期间仍公开但排序靠后、不计入汇总。</span></li>
          <li class="flex gap-2"><i class="ri-checkbox-blank-circle-fill mt-2 text-[6px] text-gray-300 dark:text-gray-600" aria-hidden="true" /><span>复核确认不符合公约的内容会下架（仅作者本人可见），并保留处置记录。</span></li>
          <li class="flex gap-2"><i class="ri-checkbox-blank-circle-fill mt-2 text-[6px] text-gray-300 dark:text-gray-600" aria-hidden="true" /><span>误判是可能发生的。作者可在评价卡片点「我觉得被误判了」提交申诉；医院或医生也可通过<RouterLink class="underline" to="/hospitals/appeal">申诉入口</RouterLink>提出，我们会在 3 个工作日内反馈。</span></li>
        </ul>
      </section>

      <section class="card p-4 dark:bg-gray-900 md:p-5">
        <h2 class="text-base font-semibold">相关页面</h2>
        <div class="mt-3 flex flex-wrap gap-2 text-sm">
          <RouterLink class="min-h-11 rounded-xl border border-gray-200 px-4 py-2.5 dark:border-gray-700" to="/hospitals">返回就医经验</RouterLink>
          <RouterLink class="min-h-11 rounded-xl border border-gray-200 px-4 py-2.5 dark:border-gray-700" to="/hospitals/appeal">评价申诉</RouterLink>
          <RouterLink class="min-h-11 rounded-xl border border-gray-200 px-4 py-2.5 dark:border-gray-700" to="/privacy">隐私政策</RouterLink>
          <RouterLink class="min-h-11 rounded-xl border border-gray-200 px-4 py-2.5 dark:border-gray-700" to="/terms">用户协议</RouterLink>
        </div>
      </section>
    </div>

    <MedicalDisclaimer class="mt-6" variant="inline" message="本公约不构成医疗建议；诊疗安排请以医院官方信息及面诊为准。" />
  </div>
</template>
