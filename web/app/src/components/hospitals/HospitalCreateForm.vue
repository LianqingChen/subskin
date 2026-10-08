<script setup lang="ts">
import { computed, ref } from 'vue'
import { detectPii } from '@/utils/piiCheck'
import type { HospitalCreatePayload } from '@/types/hospital'

/** 病友补充医院：省份、城市、区县、具体地址必填到「能指向一家医院」的程度。 */
const props = defineProps<{ province?: string; city?: string; name?: string; district?: string }>()
const emit = defineEmits<{ save: [payload: HospitalCreatePayload] }>()
const form = ref({
  name: props.name ?? '', province: props.province ?? '', city: props.city ?? '',
  district: props.district ?? '', address: '', department: '', kind: '综合医院', source: '', note: '',
})
const kinds = ['综合医院', '皮肤病专科', '中医院', '其他']
const piiHits = computed(() => detectPii([form.value.address, form.value.note].join('\n')))
const valid = computed(() => form.value.name.trim().length >= 2 && form.value.province.trim() && form.value.city.trim()
  && form.value.address.trim().length >= 4)
function submit() {
  if (!valid.value) return
  emit('save', {
    name: form.value.name.trim(), province: form.value.province.trim(), city: form.value.city.trim(),
    district: form.value.district.trim(), address: form.value.address.trim(),
    department: form.value.department.trim(), kind: form.value.kind,
    source: form.value.source.trim(), note: form.value.note.trim(),
    confirmNoPii: Boolean(form.value.source.trim()),
  })
}
</script>

<template>
  <form class="space-y-4" @submit.prevent="submit">
    <p class="rounded-xl bg-primary-50 p-3 text-xs leading-6 text-primary-800 dark:bg-primary-900 dark:text-primary-200">
      创建后会立即出现在就医经验目录里，并标注「<strong>病友补充 · 待核实</strong>」，方便其他病友接着评价。请填写真实存在的医院；不要填写医生或任何人的联系方式。
    </p>
    <label class="block text-sm">医院 / 院区全称 <span class="text-gray-400">*</span>
      <input v-model.trim="form.name" required maxlength="200" class="create-input" placeholder="例如：某某市人民医院（东院区）">
    </label>
    <div class="grid grid-cols-2 gap-3">
      <label class="text-sm">省份 <span class="text-gray-400">*</span><input v-model.trim="form.province" required maxlength="50" class="create-input" placeholder="例如：江苏"></label>
      <label class="text-sm">城市 <span class="text-gray-400">*</span><input v-model.trim="form.city" required maxlength="50" class="create-input" placeholder="例如：南京"></label>
      <label class="text-sm">区县<input v-model.trim="form.district" maxlength="50" class="create-input" placeholder="例如：玄武区"></label>
      <label class="text-sm">就诊科室<input v-model.trim="form.department" maxlength="100" class="create-input" placeholder="例如：皮肤科"></label>
    </div>
    <label class="block text-sm">具体地址 / 院区 <span class="text-gray-400">*</span>
      <input v-model.trim="form.address" required maxlength="300" class="create-input" placeholder="例如：某某路 12 号 3 号楼（门诊楼 5 楼皮肤科）">
      <span class="mt-1 block text-[11px] text-gray-400">写清楚到能导航或问路的程度；不要填个人住址。</span>
    </label>
    <label class="block text-sm">医院类型
      <select v-model="form.kind" class="create-input"><option v-for="kind in kinds" :key="kind" :value="kind">{{ kind }}</option></select>
    </label>
    <label class="block text-sm">官方来源链接（有则填，可核实）
      <input v-model.trim="form.source" type="url" maxlength="500" class="create-input" placeholder="https://">
    </label>
    <label class="block text-sm">补充说明
      <textarea v-model.trim="form.note" rows="3" maxlength="500" class="create-input resize-y" placeholder="例如：该院有白癜风专病门诊，周三上午出诊；挂号在官方公众号。" />
    </label>
    <p v-if="piiHits.length" class="rounded-xl bg-amber-50 p-3 text-xs leading-6 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
      <i class="ri-error-warning-line mr-1" />检测到{{ piiHits.join('、') }}，公开显示时会自动脱敏。建议直接删除这些内容。
    </p>
    <p class="text-xs text-gray-500">提交即表示你确认该医院真实存在，且内容不含他人隐私与广告引流。本文不构成医疗建议。</p>
    <button :disabled="!valid" type="submit" class="min-h-11 w-full rounded-xl bg-primary-600 px-4 py-3 text-sm font-medium text-white disabled:opacity-40">创建医院并公开</button>
  </form>
</template>

<style scoped>
.create-input { @apply mt-2 block min-h-11 w-full min-w-0 rounded-xl border border-gray-200 bg-white p-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100; }
</style>
