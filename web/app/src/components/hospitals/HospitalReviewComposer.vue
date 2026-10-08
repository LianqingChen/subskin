<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import HospitalReviewImages from './HospitalReviewImages.vue'
import { REVIEW_TAGS_GOOD, REVIEW_TAGS_WATCH, TREATMENT_OPTIONS } from '@/data/hospitals'
import { detectPii } from '@/utils/piiCheck'
import {
  BANNED_DIMENSIONS, EXPERIENCE_DIMENSIONS, EXPERIENCE_LEVELS,
  assessReviewRisk, sanitizeDoctorName, specificityScore,
} from '@/utils/reviewRiskRules'
import {
  COMPLETE_DETAIL_SCORE, MAX_REVIEW_IMAGES, type ExperienceLevel, type HospitalReviewDraft,
  type HospitalReviewImage, type HospitalReviewPayload, type HospitalView, type ReviewTarget,
} from '@/types/hospital'

/**
 * 两档写评价（v3）：
 *  - 快速评价（默认可见）：对象 + 6 维体验点选 + 标签 + 20 字以上 + 单独同意 → 发布；
 *  - 完整分享（折叠「想说更多？」）：费用 / 疗程 / 月份 / 医生脱敏称谓 / 方案 / 凭证图。
 *
 * 合规要点：
 *  1. 「单独同意」（PIPL 第 28/29 条）必填且不默认勾选；
 *  2. 医生姓名只保留「张医生（皮肤科）」脱敏称谓；
 *  3. 疗效类维度/标签黑名单即时提示；
 *  4. 命中情绪化或结论性表述 → 发布前冷静确认（附正当维权渠道指引），
 *     而不是直接封口；疗效断言、侮辱性言辞、引流广告则硬拦截并给改写建议。
 */
const props = defineProps<{
  hospital: HospitalView
  initialTarget?: ReviewTarget
  draft?: HospitalReviewDraft
  uploading?: boolean
  publishing?: boolean
  uploadImage: (file: File, label: string) => Promise<string | null>
}>()
const emit = defineEmits<{ save: [payload: HospitalReviewPayload]; cancel: [] }>()

const TARGETS: { id: ReviewTarget; label: string; icon: string; hint: string }[] = [
  { id: 'hospital', label: '医院评价', icon: 'ri-hospital-line', hint: '挂号、候诊、费用、环境、复诊安排' },
  { id: 'doctor', label: '医生评价', icon: 'ri-user-heart-line', hint: '只写称呼、职称、科室；姓名会自动脱敏为「张医生（科室）」' },
  { id: 'treatment', label: '治疗方案', icon: 'ri-capsule-line', hint: '方案名称、疗程、费用、做了多久、有无不适' },
  { id: 'experience', label: '治疗经历', icon: 'ri-book-open-line', hint: '从确诊到复诊的完整过程，给病友一个参考' },
]

const target = ref<ReviewTarget>(props.initialTarget ?? 'hospital')
const form = ref({
  doctorName: '', doctorTitle: '', doctorDepartment: '', treatmentName: '', treatmentDetail: '',
  visitMonth: props.draft?.month ?? '', duration: props.draft?.duration ?? '',
  cost: props.draft?.cost ?? '', outcome: props.draft?.outcome ?? '', content: props.draft?.text ?? '',
  tags: [...(props.draft?.tags ?? [])],
})
const experience = ref<Record<string, ExperienceLevel>>({})
const images = ref<HospitalReviewImage[]>([])
const imagesConfirmed = ref(false)
const healthConsent = ref(false)
const riskAck = ref(false)
const showMore = ref(props.initialTarget === 'experience' || props.initialTarget === 'treatment')
const maxMonth = new Date().toISOString().slice(0, 7)
const active = computed(() => TARGETS.find(t => t.id === target.value) ?? TARGETS[0])

const detailScore = computed(() => [
  Object.keys(experience.value).length > 0,
  Boolean(form.value.cost),
  Boolean(form.value.duration),
  Boolean(form.value.visitMonth),
  images.value.length > 0,
  Boolean(form.value.doctorName) || Boolean(form.value.treatmentName),
  Boolean(form.value.treatmentDetail),
].filter(Boolean).length)
const isComplete = computed(() => detailScore.value >= COMPLETE_DETAIL_SCORE)
const missing = computed(() => Math.max(0, COMPLETE_DETAIL_SCORE - detailScore.value))
const contentLength = computed(() => form.value.content.trim().length)
const piiHits = computed(() => detectPii([form.value.content, form.value.treatmentDetail].join('\n')))
const specificity = computed(() => specificityScore(form.value.content))

/** 发布前风控（客户端即时反馈，服务端会再判一次） */
const risk = computed(() => assessReviewRisk(form.value.content, {
  doctorName: form.value.doctorName, tags: form.value.tags,
}))
const riskNeedsAck = computed(() => risk.value.level !== 'safe')
const sanitizedDoctor = computed(() => sanitizeDoctorName(form.value.doctorName, form.value.doctorDepartment))

/** 疗效类维度/标签不允许出现 */
const bannedInTags = computed(() => form.value.tags.filter(tag =>
  BANNED_DIMENSIONS.some(word => tag.includes(word)),
))

const valid = computed(() => {
  if (contentLength.value < 20) return false
  if (target.value === 'doctor' && !form.value.doctorName.trim()) return false
  if (target.value === 'treatment' && !form.value.treatmentName.trim()) return false
  if (form.value.visitMonth && form.value.visitMonth > maxMonth) return false
  if (images.value.length && !imagesConfirmed.value) return false
  if (bannedInTags.value.length) return false
  if (risk.value.blocked) return false
  if (!healthConsent.value) return false
  if (riskNeedsAck.value && !riskAck.value) return false
  return true
})

const submitHint = computed(() => {
  if (target.value === 'doctor' && !form.value.doctorName.trim()) return '请填写医生称呼（会自动脱敏）'
  if (target.value === 'treatment' && !form.value.treatmentName.trim()) return '请填写方案或用药名称'
  if (contentLength.value < 20) return `再写 ${20 - contentLength.value} 字即可满足正文要求`
  if (form.value.visitMonth && form.value.visitMonth > maxMonth) return '就诊月份不能晚于本月'
  if (images.value.length && !imagesConfirmed.value) return '请确认凭证图片已遮盖个人信息'
  if (bannedInTags.value.length) return `标签「${bannedInTags.value[0]}」属疗效类表述，平台不采集`
  if (risk.value.blocked) return '内容含需要修改的表述，请按下方建议改写后再发布'
  if (!healthConsent.value) return '请先勾选同意公开你的就医体验'
  if (riskNeedsAck.value && !riskAck.value) return '请阅读并确认下方「发布前提醒」'
  return '内容已就绪，发布后会公开给其他病友'
})

function toggleTag(tag: string) {
  form.value.tags = form.value.tags.includes(tag)
    ? form.value.tags.filter(t => t !== tag)
    : [...form.value.tags, tag]
}
function setLevel(dimension: string, level: ExperienceLevel) {
  const next = { ...experience.value }
  if (next[dimension] === level) delete next[dimension]
  else next[dimension] = level
  experience.value = next
}
async function handleUpload(file: File, label: string) {
  if (images.value.length >= MAX_REVIEW_IMAGES) return
  const url = await props.uploadImage(file, label)
  if (url) images.value = [...images.value, { url, label }]
}
function removeImage(url: string) {
  images.value = images.value.filter(image => image.url !== url)
}
function submit() {
  if (!valid.value) return
  emit('save', {
    target: target.value,
    doctorName: form.value.doctorName.trim(), doctorTitle: form.value.doctorTitle.trim(),
    doctorDepartment: form.value.doctorDepartment.trim(),
    treatmentName: form.value.treatmentName.trim(), treatmentDetail: form.value.treatmentDetail.trim(),
    visitMonth: form.value.visitMonth, duration: form.value.duration, cost: form.value.cost,
    outcome: form.value.outcome, tags: form.value.tags,
    experienceScores: { ...experience.value },
    content: form.value.content.trim(), images: images.value, imagesConfirmed: imagesConfirmed.value,
    healthConsent: healthConsent.value, riskAck: riskAck.value,
  })
}
</script>

<template>
  <form :aria-busy="publishing" class="space-y-5" @submit.prevent="submit">
    <div class="rounded-xl bg-primary-50 p-3 text-xs leading-6 text-primary-800 dark:bg-primary-900 dark:text-primary-200">
      正在评价 <strong>{{ hospital.name }}</strong>（{{ hospital.province }} · {{ hospital.city }}）。只写你自己的经历，不写他人隐私，不做疗效保证，也不评价医生的技术水平。
      <template v-if="hospital.origin === 'community'">该医院由病友补充，官方信息待核实。</template>
    </div>
    <p v-if="draft" class="rounded-xl bg-gray-50 p-3 text-xs leading-6 text-gray-600 dark:bg-gray-800 dark:text-gray-300">
      <i class="ri-file-edit-line mr-1" />已带入你之前保存在本机的经历草稿，确认无误后即可公开发布。
    </p>

    <fieldset>
      <legend class="mb-2 text-sm font-medium">这次分享的是</legend>
      <div class="grid grid-cols-2 gap-2 md:grid-cols-4">
        <button v-for="item in TARGETS" :key="item.id" type="button" :aria-pressed="target === item.id" class="min-h-11 rounded-xl border px-3 text-xs" :class="target === item.id ? 'border-primary-500 bg-primary-50 font-medium text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'border-gray-200 text-gray-600 dark:border-gray-700 dark:text-gray-300'" @click="target = item.id"><i :class="item.icon" class="mr-1" />{{ item.label }}</button>
      </div>
      <p class="mt-2 text-xs text-gray-500">{{ active.hint }}</p>
    </fieldset>

    <label v-if="target === 'doctor'" class="block text-sm font-medium">医生称呼 <span class="text-gray-500">（必填）</span>
      <input v-model.trim="form.doctorName" required maxlength="40" class="composer-input" placeholder="例如：张医生">
      <span v-if="sanitizedDoctor" class="mt-1 block text-xs text-gray-500">公开显示为：<strong>{{ sanitizedDoctor }}</strong> —— 为保护医护人员个人权益，平台不公开展示可识别姓名。</span>
    </label>
    <label v-if="target === 'treatment'" class="block text-sm font-medium">方案 / 用药名称 <span class="text-gray-500">（必填）</span><input v-model.trim="form.treatmentName" required maxlength="120" list="treatment-options" class="composer-input" placeholder="填写本次使用的方案或用药"><datalist id="treatment-options"><option v-for="name in TREATMENT_OPTIONS" :key="name" :value="name" /></datalist></label>

    <aside class="rounded-xl bg-gray-50 p-3 text-xs leading-6 text-gray-600 dark:bg-gray-800 dark:text-gray-300" aria-label="分享提示">可以按这三点写：<strong>做了什么</strong>（就诊过程、治疗安排）；<strong>遇到了什么</strong>（等待、费用、沟通）；<strong>下次怎么准备</strong>（值得借鉴的经验、需要提前问清的事）。只写亲身经历，不推断医术或承诺疗效。</aside>

    <!-- 6 维体验点选：结构化点选降低门槛，全部选填（含「没体验过」档） -->
    <fieldset>
      <legend class="mb-1 text-sm font-medium">这次就医体验 <span class="text-xs font-normal text-gray-500 dark:text-gray-400">（选填，点一下即可）</span></legend>
      <p class="mb-2 text-xs text-gray-500">只评价你自己的感受，不做疗效判断，也不评价医生技术水平。没经历过的项目选「没体验过」。</p>
      <div class="space-y-2">
        <div v-for="dimension in EXPERIENCE_DIMENSIONS" :key="dimension.key" class="rounded-xl border border-gray-200 p-3 dark:border-gray-700">
          <div class="flex flex-wrap items-baseline justify-between gap-2">
            <span class="text-xs font-medium text-gray-700 dark:text-gray-200">{{ dimension.key }}</span>
            <span class="text-[11px] text-gray-400">{{ dimension.question }}</span>
          </div>
          <div class="mt-2 flex flex-wrap gap-1.5">
            <button
              v-for="level in EXPERIENCE_LEVELS" :key="level.key" type="button"
              :aria-pressed="experience[dimension.key] === level.key"
              class="min-h-9 rounded-lg border px-3 text-xs"
              :class="experience[dimension.key] === level.key
                ? (level.key === 'unsatisfied' ? 'border-rose-400 bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300'
                  : level.key === 'na' ? 'border-gray-400 bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-200'
                  : 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300')
                : 'border-gray-200 text-gray-600 dark:border-gray-700 dark:text-gray-300'"
              @click="setLevel(dimension.key, level.key)"
            >{{ level.label }}</button>
          </div>
        </div>
      </div>
    </fieldset>

    <label class="block text-sm">{{ active.label }}内容 <span class="text-gray-400">*</span>
      <textarea v-model="form.content" required minlength="20" maxlength="2000" rows="5" class="composer-input resize-y" placeholder="写这几句最有用：挂号难不难、等了多久、医生有没有把方案讲清楚、这次花了多少、复诊怎么安排。请至少写 20 字。" />
      <span class="mt-1 flex items-center justify-between gap-2 text-xs">
        <span :class="specificity.hit >= 3 ? 'text-primary-600 dark:text-primary-300' : 'text-gray-400'">
          <template v-if="specificity.hit >= 3"><i class="ri-checkbox-circle-line mr-1" />内容具体（已含{{ specificity.labels.join('、') }}）</template>
          <template v-else>写清「时间 · 流程 · 费用 · 沟通 · 复诊」会更有参考价值<template v-if="specificity.labels.length">（已含{{ specificity.labels.join('、') }}）</template></template>
        </span>
        <span :class="contentLength < 20 ? 'text-gray-400' : 'text-primary-600'">{{ form.content.length }} / 2000（至少 20 字）</span>
      </span>
    </label>

    <fieldset>
      <legend class="mb-2 text-sm font-medium">标签 <span class="text-xs font-normal text-gray-500 dark:text-gray-400">（选填，可多选）</span></legend>
      <p class="mb-1 text-xs text-gray-500">值得说</p>
      <div class="flex flex-wrap gap-2">
        <button v-for="tag in REVIEW_TAGS_GOOD" :key="tag" type="button" :aria-pressed="form.tags.includes(tag)" class="min-h-11 rounded-lg border px-3 text-xs" :class="form.tags.includes(tag) ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'border-gray-200 text-gray-600 dark:border-gray-700 dark:text-gray-300'" @click="toggleTag(tag)">{{ tag }}</button>
      </div>
      <p class="mb-1 mt-3 text-xs text-gray-500">需注意</p>
      <div class="flex flex-wrap gap-2">
        <button v-for="tag in REVIEW_TAGS_WATCH" :key="tag" type="button" :aria-pressed="form.tags.includes(tag)" class="min-h-11 rounded-lg border px-3 text-xs" :class="form.tags.includes(tag) ? 'border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200' : 'border-gray-200 text-gray-600 dark:border-gray-700 dark:text-gray-300'" @click="toggleTag(tag)">{{ tag }}</button>
      </div>
      <p v-if="bannedInTags.length" class="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
        平台不采集疗效类标签，请改用中性体验标签。
      </p>
    </fieldset>

    <p v-if="piiHits.length" class="rounded-xl bg-amber-50 p-3 text-xs leading-6 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
      <i class="ri-error-warning-line mr-1" />检测到{{ piiHits.join('、') }}，发布时会自动脱敏。建议直接删掉。
    </p>

    <button type="button" class="flex min-h-11 w-full items-center justify-between rounded-xl border border-gray-200 px-4 text-sm dark:border-gray-700" :aria-expanded="showMore" @click="showMore = !showMore">
      <span>
        <i class="ri-add-circle-line mr-1 text-primary-600 dark:text-primary-300" />补充信息（选填）
        <span class="ml-1 text-xs" :class="isComplete ? 'text-primary-600 dark:text-primary-300' : 'text-gray-400'">
          {{ isComplete ? '已是完整分享' : `再补 ${missing} 项即完整分享` }}
        </span>
      </span>
      <i :class="showMore ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'" />
    </button>

    <template v-if="showMore">
      <div v-if="target === 'doctor'" class="grid gap-3 sm:grid-cols-2"><label class="text-sm">职称<input v-model.trim="form.doctorTitle" maxlength="40" class="composer-input" placeholder="例如：主任医师"></label><label class="text-sm">科室<input v-model.trim="form.doctorDepartment" maxlength="60" class="composer-input" placeholder="例如：皮肤科"></label></div>
      <label v-if="target === 'treatment'" class="block text-sm">方案要点<input v-model.trim="form.treatmentDetail" maxlength="500" class="composer-input" placeholder="可补充实际治疗安排与复诊负担，不提供他人用药指导"></label>

      <div class="grid grid-cols-2 gap-3">
        <label class="text-sm">就诊月份<input v-model="form.visitMonth" type="month" :max="maxMonth" class="composer-input"></label>
        <label class="text-sm">治疗时长<select v-model="form.duration" class="composer-input"><option value="">尚未填写</option><option>初次就诊</option><option>不足1个月</option><option>1–3个月</option><option>3–6个月</option><option>6个月以上</option></select></label>
        <label class="text-sm">每月自付费用<select v-model="form.cost" class="composer-input"><option value="">尚未填写</option><option>500元以内</option><option>500–1500元</option><option>1500–3000元</option><option>3000元以上</option><option>暂不清楚</option></select></label>
        <label class="text-sm">我的感受<select v-model="form.outcome" class="composer-input"><option value="">尚未填写</option><option>仍在观察</option><option>我治疗后白斑有变化</option><option>我没有感觉到变化</option><option>我已停止治疗</option></select></label>
      </div>
      <p class="text-[11px] leading-5 text-gray-400">「我的感受」只记录你自己的主观体会，个体差异很大，不代表疗效，也不代表医生的诊疗水平，平台不做聚合与比较。</p>

      <HospitalReviewImages
        v-model="images" :confirmed="imagesConfirmed" :uploading="uploading"
        @update:confirmed="imagesConfirmed = $event" @upload="handleUpload" @remove="removeImage"
      />
      <p class="text-[11px] leading-5 text-gray-400">
        <i class="ri-lock-line mr-1" />凭证图仅你本人和管理员可见，不会公开展示；公开层只显示「已上传挂号单/费用单」徽标。
      </p>
    </template>

    <!-- 发布前提醒：命中情绪化或结论性表述 → 冷静确认 + 正当维权渠道 -->
    <section
      v-if="riskNeedsAck"
      class="rounded-xl border p-3 text-xs leading-6"
      :class="risk.blocked
        ? 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-800/60 dark:bg-rose-900/25 dark:text-rose-200'
        : 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800/60 dark:bg-amber-900/25 dark:text-amber-200'"
      aria-live="polite"
    >
      <p class="font-medium">
        <i class="ri-error-warning-line mr-1" />
        {{ risk.blocked ? '这几处需要先改一下才能发布' : '发布前提醒（请先看一眼）' }}
      </p>
      <ul class="mt-1 list-disc space-y-1 pl-5">
        <li v-for="flag in risk.flags" :key="flag.code">{{ flag.detail }}<template v-if="flag.hint"> —— {{ flag.hint }}</template></li>
      </ul>
      <div v-if="riskNeedsAck && !risk.blocked" class="mt-2">
        <p class="mb-1">如果确实认为诊疗存在问题，可以通过这些渠道主张权利，比在评价里下结论更有效：</p>
        <ul class="list-disc space-y-0.5 pl-5">
          <li>就诊医院医务处 / 医患关系办公室</li>
          <li>医疗纠纷人民调解委员会（各地司法局设）</li>
          <li>12345 政务服务便民热线 / 当地卫健委</li>
        </ul>
        <label class="mt-2 flex items-start gap-2">
          <input v-model="riskAck" type="checkbox" class="mt-1">
          <span>我已确认：内容基于我的真实经历，不含侮辱性言辞；我知道它会公开显示，并愿意为内容负责。</span>
        </label>
      </div>
      <p v-else-if="risk.blocked" class="mt-1">按上面的建议改写后，就可以正常发布。</p>
    </section>

    <!-- PIPL 单独同意：不默认勾选，不勾选不能发布 -->
    <label class="flex items-start gap-2 rounded-xl bg-gray-50 p-3 text-xs leading-6 text-gray-600 dark:bg-gray-800 dark:text-gray-300">
      <input v-model="healthConsent" type="checkbox" class="mt-1">
      <span>
        我同意公开我这次的<strong>就医体验</strong>。我了解其中可能包含与我的健康相关的信息（就诊医院、科室、用药等），
        这些属于敏感个人信息；我可以随时删除这条评价。
        <RouterLink class="text-primary-700 underline dark:text-primary-300" to="/privacy">隐私政策</RouterLink>
      </span>
    </label>

    <p class="text-xs text-gray-500">发布后其他病友可以看到这条评价，你随时可以删除。个人经历与感受存在差异，本文不构成医疗建议。</p>

    <p id="review-submit-hint" role="status" aria-live="polite" class="text-sm text-gray-600 dark:text-gray-300">{{ submitHint }}</p>
    <div class="flex gap-3">
      <button type="button" class="min-h-11 flex-1 rounded-xl border border-gray-200 px-4 text-sm dark:border-gray-700" @click="emit('cancel')">取消</button>
      <button :disabled="!valid || publishing" aria-describedby="review-submit-hint" type="submit" class="min-h-11 flex-[2] rounded-xl bg-primary-600 px-4 py-3 text-sm font-medium text-white disabled:opacity-40">
        {{ publishing ? '发布中…' : '公开发布评价' }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.composer-input { @apply mt-2 block min-h-11 w-full min-w-0 rounded-xl border border-gray-200 bg-white p-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100; }
</style>
