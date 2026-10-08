<script setup lang="ts">
/**
 * ComparisonPhotoUploader — 白斑对比报告的直接照片上传
 *
 * 用户无需先发分享，可直接一次选多张照片、逐张标注拍摄日期（对比部位在
 * 报告级统一选择），保存为私有日记照片后即可在对比报告页选择生成报告。
 */
import { computed, ref } from 'vue'
import { communityApi } from '@/api/community'
import { saveComparisonPhotos } from '@/api/skin_report'
import { useToast } from '@/composables/useToast'
import DateWheelPicker from '@/components/common/DateWheelPicker.vue'

const emit = defineEmits<{ (e: 'saved'): void }>()

const props = defineProps<{
  /** 默认打标部位（来自测评页选中的身体部位）；null = 不标注 */
  defaultBodySite?: string | null
}>()

interface UploadItem {
  id: number
  file: File
  preview: string
  captureDate: string
}

const toast = useToast()
const fileInput = ref<HTMLInputElement | null>(null)
const items = ref<UploadItem[]>([])
const saving = ref(false)
const datePickerFor = ref<number | null>(null)
const pickerValue = ref('')

const datePickerItem = computed(
  () => items.value.find((it) => it.id === datePickerFor.value) || null,
)

function openDatePicker(id: number) {
  const it = items.value.find((x) => x.id === id)
  pickerValue.value = it?.captureDate || ''
  datePickerFor.value = id
}

function confirmDate() {
  const it = datePickerItem.value
  if (it) it.captureDate = pickerValue.value
  datePickerFor.value = null
}

function pick() {
  fileInput.value?.click()
}

function onFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return
  const MAX_PHOTOS = 4
  const remaining = Math.max(0, MAX_PHOTOS - items.value.length)
  const taken = files.slice(0, remaining)
  if (files.length > remaining) {
    toast.warning(`一次最多选择 ${MAX_PHOTOS} 张照片`)
  }
  for (const f of taken) {
    if (!/^image\//.test(f.type)) continue
    items.value.push({
      id: Date.now() + Math.random(),
      file: f,
      preview: URL.createObjectURL(f),
      captureDate: '',
    })
  }
  input.value = ''
}

function remove(id: number) {
  const idx = items.value.findIndex((it) => it.id === id)
  if (idx >= 0) {
    URL.revokeObjectURL(items.value[idx].preview)
    items.value.splice(idx, 1)
  }
}

function clearAll() {
  for (const it of items.value) URL.revokeObjectURL(it.preview)
  items.value = []
}

async function save() {
  if (!items.value.length || saving.value) return
  saving.value = true
  try {
    const metas = []
    for (const it of items.value) {
      const up = await communityApi.uploadImage(it.file)
      metas.push({
        image_url: up.image_url,
        // 上传照片默认按测评页选中的身体部位打标
        body_site: props.defaultBodySite || null,
        capture_date: it.captureDate || null,
      })
    }
    await saveComparisonPhotos(metas)
    toast.show('照片已保存，可在下方选择生成对比报告', 'success')
    clearAll()
    emit('saved')
  } catch (err: any) {
    toast.show(err?.response?.data?.detail || '上传失败，请重试', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="cpu">
    <input ref="fileInput" type="file" accept="image/*" multiple class="cpu-hidden" @change="onFiles" />

    <button v-if="!items.length" type="button" class="cpu-upload" @click="pick">
      <i class="ri-upload-cloud-2-line"></i>
      <span>直接上传照片</span>
      <em>一次可选4张照片</em>
    </button>

    <div v-else class="cpu-panel">
      <div class="cpu-panel__head">
        <span>已选 {{ items.length }} 张，逐张标注拍摄日期</span>
        <button v-if="items.length < 4" type="button" class="cpu-add" @click="pick">
          <i class="ri-add-line"></i> 继续添加
        </button>
      </div>

      <div class="cpu-list">
        <div v-for="it in items" :key="it.id" class="cpu-item">
          <img :src="it.preview" alt="待上传照片" />
          <div class="cpu-item__fields">
            <button
              type="button"
              class="cpu-date"
              :aria-label="`选择拍摄日期（当前 ${it.captureDate || '未标注'}）`"
              @click="openDatePicker(it.id)"
            >
              <i class="ri-calendar-line"></i>
              <span :class="{ 'cpu-date--empty': !it.captureDate }">{{ it.captureDate || '选择日期' }}</span>
            </button>
          </div>
          <button type="button" class="cpu-del" aria-label="移除" @click="remove(it.id)">
            <i class="ri-close-line"></i>
          </button>
        </div>
      </div>

      <div class="cpu-panel__foot">
        <button type="button" class="cpu-cancel" @click="clearAll">取消</button>
        <button type="button" class="cpu-save" :disabled="saving" @click="save">
          <i v-if="saving" class="ri-loader-4-line cpu-spin"></i>
          <span>{{ saving ? '保存中…' : '保存照片' }}</span>
        </button>
      </div>
    </div>

    <!-- 日期滚轮弹层（确认后生效） -->
    <Teleport to="body">
      <div
        v-if="datePickerItem"
        class="fixed inset-0 bg-black/50 z-[110] flex items-center justify-center px-4"
        @click.self="datePickerFor = null"
      >
        <div class="bg-white dark:bg-gray-800 rounded-2xl p-4 w-full max-w-xs shadow-xl">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-semibold text-gray-900 dark:text-gray-100">选择拍摄日期</span>
            <button
              type="button"
              class="w-9 h-9 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
              aria-label="关闭日历"
              @click="datePickerFor = null"
            >
              <i class="ri-close-line text-lg"></i>
            </button>
          </div>

          <p class="text-center text-sm mb-2">
            已选：
            <span class="font-semibold text-primary-600 dark:text-primary-400">
              {{ pickerValue || '未选择' }}
            </span>
          </p>

          <DateWheelPicker v-model="pickerValue" />

          <div class="flex gap-3 mt-3">
            <button type="button" class="btn-ghost flex-1 min-h-[44px]" @click="datePickerFor = null">
              取消
            </button>
            <button type="button" class="btn-primary flex-1 min-h-[44px]" @click="confirmDate">
              确定
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.cpu-hidden {
  display: none;
}

.cpu-upload {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 18px 16px;
  border-radius: 14px;
  border: 2px dashed var(--color-primary-300, #99f6e4);
  background: var(--color-primary-50, #f0fdfa);
  color: var(--color-primary-700, #0f766e);
  cursor: pointer;
  transition: all 0.2s;
}

.cpu-upload i {
  font-size: 26px;
}

.cpu-upload span {
  font-size: 15px;
  font-weight: 700;
}

.cpu-upload em {
  font-style: normal;
  font-size: 12px;
  color: var(--color-primary-600, #0d9488);
}

.cpu-panel {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 12px;
  background: white;
}

html.dark .cpu-panel {
  background: #1e293b;
  border-color: #334155;
}

.cpu-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
}

html.dark .cpu-panel__head {
  color: #cbd5e1;
}

.cpu-add {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  border: none;
  background: transparent;
  color: var(--color-primary-600, #0d9488);
  font-size: 12px;
  cursor: pointer;
}

.cpu-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cpu-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cpu-item img {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
  background: #f1f5f9;
}

.cpu-item__fields {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cpu-select,
.cpu-date {
  width: 100%;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  font-size: 13px;
  color: #334155;
  background: white;
  min-height: 34px;
}

.cpu-date {
  display: flex;
  align-items: center;
  gap: 6px;
  text-align: left;
  cursor: pointer;
}

.cpu-date i {
  color: var(--color-primary-500);
  font-size: 15px;
  flex-shrink: 0;
}

.cpu-date--empty {
  color: #94a3b8;
}

html.dark .cpu-select,
html.dark .cpu-date {
  background: #0f172a;
  border-color: #334155;
  color: #cbd5e1;
}

.cpu-del {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 8px;
  background: #f1f5f9;
  color: #94a3b8;
  font-size: 18px;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

html.dark .cpu-del {
  background: #334155;
  color: #94a3b8;
}

.cpu-panel__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.cpu-cancel {
  padding: 8px 16px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: white;
  color: #64748b;
  font-size: 13px;
  cursor: pointer;
}

html.dark .cpu-cancel {
  background: #0f172a;
  border-color: #334155;
  color: #94a3b8;
}

.cpu-save {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 18px;
  border-radius: 10px;
  border: none;
  background: var(--color-primary-500, #14b8a6);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.cpu-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cpu-spin {
  animation: cpu-rotate 1s linear infinite;
}

@keyframes cpu-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
