<script setup lang="ts">
/**
 * 评价申诉（/hospitals/appeal）。
 *
 * 面向：被评价的医院/科室、被评价的医护人员、以及「认为自己的评价被误判」的作者。
 * 该页**不要求登录** —— 机构申诉不应被登录门槛挡住。
 *
 * 法律依据：《民法典》第 1028 条要求对失实内容及时采取更正或删除等必要措施；
 * 参考同类平台规则，处理时限为 3 个工作日（工作日不含周末）。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { submitHospitalReviewAppeal } from '@/api/hospital'
import { useToast } from '@/composables/useToast'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import type { AppealClaimantType, HospitalReviewAppeal } from '@/types/hospital'

const route = useRoute()
const toast = useToast()

const CLAIMANTS: { id: AppealClaimantType; label: string; hint: string }[] = [
  { id: 'hospital', label: '医院 / 科室', hint: '以机构名义提出，请填写机构名称与可核实的联系方式' },
  { id: 'doctor', label: '医护人员本人', hint: '请填写你的称谓与可核实的联系方式' },
  { id: 'author', label: '我是这条评价的作者', hint: '认为自己的评价被误判或误删，可申请复核' },
  { id: 'other', label: '其他', hint: '其他利害关系人' },
]

const form = ref({
  reviewId: Number(route.query.review ?? 0) || 0,
  claimantType: 'hospital' as AppealClaimantType,
  claimantName: '',
  contact: '',
  reason: '',
})
const submitting = ref(false)
const result = ref<HospitalReviewAppeal | null>(null)

const activeHint = computed(() => CLAIMANTS.find(item => item.id === form.value.claimantType)?.hint ?? '')
const valid = computed(() =>
  form.value.reviewId > 0
  && form.value.claimantName.trim().length > 0
  && form.value.contact.trim().length > 0
  && form.value.reason.trim().length >= 20,
)

const dueText = computed(() => {
  if (!result.value?.dueAt) return ''
  const date = new Date(result.value.dueAt)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('zh-CN')
})

async function submit() {
  if (!valid.value || submitting.value) return
  submitting.value = true
  try {
    const appeal = await submitHospitalReviewAppeal({
      reviewId: form.value.reviewId,
      claimantType: form.value.claimantType,
      claimantName: form.value.claimantName.trim(),
      contact: form.value.contact.trim(),
      reason: form.value.reason.trim(),
    })
    if (appeal) result.value = appeal
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    toast.error(detail || '申诉提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

let schema: HTMLScriptElement | undefined
onMounted(() => {
  schema = document.createElement('script')
  schema.type = 'application/ld+json'
  schema.textContent = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name: '就医经验评价申诉',
    description: '对 SubSkin 就医经验中的评价提出申诉与复核申请，3 个工作日内处理',
    url: `${location.origin}/hospitals/appeal`,
  })
  document.head.appendChild(schema)
})
</script>

<template>
  <div class="page-narrow pb-8 pt-4 text-gray-900 dark:text-gray-100 md:pt-6">
    <nav class="mb-4 text-xs text-gray-500 dark:text-gray-400" aria-label="面包屑">
      <RouterLink class="underline" to="/hospitals">就医经验</RouterLink>
      <span class="mx-1">/</span><span>评价申诉</span>
    </nav>

    <header class="mb-6">
      <h1 class="page-title">评价申诉</h1>
      <p class="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">
        如果你是<strong>被评价的医院或医护人员</strong>，或者你认为<strong>自己的评价被误判</strong>，
        可以在这里提交申诉。我们会在 <strong>3 个工作日</strong>内核实并反馈处理结果。
      </p>
      <p class="mt-2 text-xs leading-6 text-gray-500 dark:text-gray-400">
        说明：平台只对评价是否违反<a class="underline" href="/hospitals/rules">社区公约</a>做审核，
        <strong>不判断医疗行为本身是否存在过错</strong>。涉及诊疗争议，请通过医院医务处、医疗纠纷人民调解委员会或卫健委等法定渠道处理。
      </p>
    </header>

    <!-- 提交结果 -->
    <section v-if="result" class="card p-4 dark:bg-gray-900 md:p-5" aria-live="polite">
      <h2 class="flex items-center gap-2 text-base font-semibold text-primary-700 dark:text-primary-300">
        <i class="ri-checkbox-circle-line" aria-hidden="true" />申诉已提交
      </h2>
      <dl class="mt-3 space-y-2 text-sm text-gray-600 dark:text-gray-300">
        <div class="flex gap-2"><dt class="text-gray-400">申诉编号</dt><dd class="font-medium">#{{ result.id }}</dd></div>
        <div class="flex gap-2"><dt class="text-gray-400">涉及评价</dt><dd>#{{ result.reviewId }}</dd></div>
        <div class="flex gap-2"><dt class="text-gray-400">当前状态</dt><dd>{{ result.status === 'pending' ? '待处理' : result.status }}</dd></div>
        <div v-if="dueText" class="flex gap-2"><dt class="text-gray-400">预计反馈</dt><dd>{{ dueText }}</dd></div>
      </dl>
      <p class="mt-3 text-xs leading-6 text-gray-500 dark:text-gray-400">
        我们会用你留下的联系方式反馈结果。如需补充材料，请再次提交申诉并说明补充内容。
      </p>
      <RouterLink class="mt-3 inline-flex min-h-11 items-center rounded-xl border border-gray-200 px-4 text-sm dark:border-gray-700" to="/hospitals">返回就医经验</RouterLink>
    </section>

    <!-- 申诉表单 -->
    <form v-else class="card space-y-5 p-4 dark:bg-gray-900 md:p-5" @submit.prevent="submit">
      <fieldset>
        <legend class="mb-2 text-sm font-medium">你是哪一方</legend>
        <div class="grid grid-cols-2 gap-2">
          <button
            v-for="item in CLAIMANTS" :key="item.id" type="button" :aria-pressed="form.claimantType === item.id"
            class="min-h-11 rounded-xl border px-3 text-xs"
            :class="form.claimantType === item.id ? 'border-primary-500 bg-primary-50 font-medium text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'border-gray-200 text-gray-600 dark:border-gray-700 dark:text-gray-300'"
            @click="form.claimantType = item.id"
          >{{ item.label }}</button>
        </div>
        <p class="mt-2 text-xs text-gray-500 dark:text-gray-400">{{ activeHint }}</p>
      </fieldset>

      <label class="block text-sm font-medium">评价编号 <span class="text-gray-500">（必填）</span>
        <input v-model.number="form.reviewId" type="number" min="1" required class="form-input" placeholder="例如：128">
        <span class="mt-1 block text-xs text-gray-500">在评价卡片的地址栏或分享链接中可以找到；从评价卡片点「申诉」进入时会自动带填。</span>
      </label>

      <div class="grid gap-3 sm:grid-cols-2">
        <label class="text-sm font-medium">申诉人 / 机构名称 <span class="text-gray-500">*</span>
          <input v-model.trim="form.claimantName" required maxlength="80" class="form-input" placeholder="例如：某某医院医务处 / 张医生"></label>
        <label class="text-sm font-medium">联系方式 <span class="text-gray-500">*</span>
          <input v-model.trim="form.contact" required maxlength="120" class="form-input" placeholder="手机号或邮箱，仅用于核实与反馈"></label>
      </div>
      <p class="text-xs leading-6 text-gray-500 dark:text-gray-400">
        <i class="ri-lock-line mr-1" />联系方式仅管理员可见，不对外公开。平台会按《个人信息保护法》最小必要原则处理。
      </p>

      <label class="block text-sm font-medium">申诉理由 <span class="text-gray-500">（至少 20 字，必填）</span>
        <textarea v-model="form.reason" required minlength="20" maxlength="2000" rows="6" class="form-input resize-y" placeholder="请说明哪一部分与事实不符、你希望我们如何处理（保留 / 要求作者补充依据 / 隐藏 / 更正），以及可以核实的依据（如当日挂号记录、排班表等）。" />
        <span class="mt-1 block text-right text-xs text-gray-400">{{ form.reason.length }} / 2000</span>
      </label>

      <p class="rounded-xl bg-gray-50 p-3 text-xs leading-6 text-gray-600 dark:bg-gray-800 dark:text-gray-300">
        我们只依据<a class="underline" href="/hospitals/rules">社区公约</a>与事实依据判断评价是否应当保留、更正或隐藏；
        <strong>不会因为一次申诉就必然删除评价</strong>，也不会因申诉而泄露申诉人身份给评价作者。
      </p>

      <p role="status" aria-live="polite" class="text-sm text-gray-600 dark:text-gray-300">
        <template v-if="!form.reviewId">请填写评价编号</template>
        <template v-else-if="!form.claimantName.trim()">请填写申诉人 / 机构名称</template>
        <template v-else-if="!form.contact.trim()">请留下联系方式</template>
        <template v-else-if="form.reason.trim().length < 20">再写 {{ 20 - form.reason.trim().length }} 字说明申诉理由</template>
        <template v-else>信息已就绪，提交后我们会在 3 个工作日内反馈</template>
      </p>

      <div class="flex gap-3">
        <RouterLink class="flex min-h-11 items-center justify-center rounded-xl border border-gray-200 px-4 text-sm dark:border-gray-700" to="/hospitals">返回</RouterLink>
        <button :disabled="!valid || submitting" type="submit" class="min-h-11 flex-1 rounded-xl bg-primary-600 px-4 text-sm font-medium text-white disabled:opacity-40">
          {{ submitting ? '提交中…' : '提交申诉' }}
        </button>
      </div>
    </form>

    <MedicalDisclaimer class="mt-6" variant="inline" message="平台不对医疗行为是否构成过错作出判断，相关争议请通过法定渠道解决。" />
  </div>
</template>

<style scoped>
.form-input { @apply mt-2 block min-h-11 w-full min-w-0 rounded-xl border border-gray-200 bg-white p-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100; }
</style>
