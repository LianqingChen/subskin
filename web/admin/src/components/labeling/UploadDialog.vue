<template>
  <n-modal :show="show" preset="card" title="上传图片" style="width: min(520px, 94vw)" :mask-closable="!busy" :closable="!busy" @update:show="onShow">
    <template v-if="result">
      <p class="summary" role="status">已创建 {{ result.created.length }} 个任务，跳过 {{ result.skipped.length }} 张。</p>
      <ul v-if="result.skipped.length" class="skipped">
        <li v-for="item in result.skipped" :key="item.name">{{ item.name }}：{{ item.reason }}</li>
      </ul>
      <div class="actions"><n-button type="primary" @click="close">完成</n-button></div>
    </template>
    <n-form v-else label-placement="top" @submit.prevent="submit">
      <n-form-item label="图片文件">
        <div class="picker">
          <input ref="input" type="file" multiple accept="image/jpeg,image/png,image/webp" class="sr-only" aria-label="选择图片文件" @change="pick" />
          <n-button @click="input?.click()"><template #icon><i class="ri-image-add-line" /></template>选择图片</n-button>
          <span class="num hint">{{ files.length ? `已选 ${files.length} 张` : `JPG / PNG / WebP，最多 ${MAX_FILES} 张，单张 ≤ 10MB` }}</span>
        </div>
        <p v-if="fileError" class="err" role="alert">{{ fileError }}</p>
      </n-form-item>
      <n-form-item label="来源与授权说明" required>
        <n-input v-model:value="note" maxlength="200" show-count placeholder="例如：合作医院A 授权研究" />
      </n-form-item>
      <n-form-item label="患者编号（选填）" :validation-status="subjectValid ? undefined : 'error'" :feedback="subjectValid ? undefined : '仅限字母、数字、下划线、短横线，最多 64 位'">
        <n-input v-model:value="subject" maxlength="64" placeholder="例如：P-0012" />
      </n-form-item>
      <p class="hint">同一患者多张图填同一编号，保证训练/测试不串；不得填真实姓名或手机号。</p>
      <n-checkbox v-model:checked="confirmed">我确认已取得将这些图片用于模型训练的授权</n-checkbox>
      <p class="hint">每张图需要几秒生成 AI 初稿，请耐心等待。</p>
      <div class="actions">
        <n-button :disabled="busy" @click="close">取消</n-button>
        <n-button type="primary" attr-type="submit" :loading="busy" :disabled="!canSubmit">{{ busy ? '处理中…' : '上传' }}</n-button>
      </div>
    </n-form>
  </n-modal>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { UploadResult } from '@/types/labeling'

const props = defineProps<{ show: boolean; busy: boolean; submitFn: (files: File[], note: string, subject: string) => Promise<UploadResult | null> }>()
const emit = defineEmits<{ 'update:show': [value: boolean] }>()

const MAX_FILES = 20
const MAX_BYTES = 10 * 1024 * 1024
const TYPES = ['image/jpeg', 'image/png', 'image/webp']
const input = ref<HTMLInputElement | null>(null)
const files = ref<File[]>([])
const note = ref('')
const subject = ref('')
const confirmed = ref(false)
const fileError = ref('')
const result = ref<UploadResult | null>(null)

const subjectValid = computed(() => !subject.value || /^[A-Za-z0-9_-]{1,64}$/.test(subject.value))
const canSubmit = computed(() => files.value.length > 0 && !fileError.value && note.value.trim().length > 0 && subjectValid.value && confirmed.value)

function pick(event: Event) {
  const picked = Array.from((event.target as HTMLInputElement).files ?? [])
  fileError.value = ''
  if (picked.length > MAX_FILES) fileError.value = `一次最多 ${MAX_FILES} 张`
  else if (picked.some((f) => !TYPES.includes(f.type))) fileError.value = '仅支持 JPG / PNG / WebP'
  else if (picked.some((f) => f.size > MAX_BYTES)) fileError.value = '存在超过 10MB 的图片'
  files.value = fileError.value ? [] : picked
}
async function submit() {
  if (!canSubmit.value || props.busy) return
  result.value = await props.submitFn(files.value, note.value.trim(), subject.value.trim())
}
function reset() {
  files.value = []; note.value = ''; subject.value = ''; confirmed.value = false; fileError.value = ''; result.value = null
  if (input.value) input.value.value = ''
}
function close() { emit('update:show', false) }
function onShow(value: boolean) { if (!props.busy) emit('update:show', value) }
watch(() => props.show, (value) => { if (!value) reset() })
</script>
<style scoped>
.picker { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.hint { color: rgba(128, 128, 128, .95); font-size: 12px; line-height: 1.7; margin: 0 0 10px; }
.num { font-variant-numeric: tabular-nums; }
.err { color: #e88080; font-size: 12px; margin: 6px 0 0; }
.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
.summary { font-size: 14px; margin: 0 0 8px; }
.skipped { font-size: 12px; color: rgba(128, 128, 128, .95); padding-left: 18px; max-height: 160px; overflow-y: auto; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
