<script setup lang="ts">
/**
 * DiaryImageUploader — 图文日记的图片上传组件
 *
 * 支持：
 * - 多图上传（调 communityApi.uploadImage）
 * - 每张图独立选择部位 + 拍摄/记录日期（支持历史补录）
 * - 上传中遮罩、删除、预览
 *
 * 通过 v-model 同步 DiaryImageInput[] 给父组件。
 */
import { ref } from 'vue'
import { communityApi } from '@/api/community'
import { BODY_SITES } from '@/constants/bodySites'
import type { DiaryImageInput } from '@/api/diary'
import { useToast } from '@/composables/useToast'

interface PendingImage extends DiaryImageInput {
  id: string
  preview: string
  uploading: boolean
}

const props = defineProps<{ modelValue?: DiaryImageInput[]; max?: number }>()
const emit = defineEmits<{ 'update:modelValue': [DiaryImageInput[]] }>()

const toast = useToast()
const pending = ref<PendingImage[]>([])
const fileInput = ref<HTMLInputElement>()
const today = new Date().toISOString().slice(0, 10)
const maxImages = props.max ?? 9

const siteOptions = Object.values(BODY_SITES).map((s) => ({ value: s.id, label: s.label }))

function genId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
}

function sync() {
  emit(
    'update:modelValue',
    pending.value
      .filter((p) => p.image_url && !p.uploading)
      .map(({ image_url, body_site, capture_date }) => ({
        image_url,
        body_site: body_site || undefined,
        capture_date: capture_date || undefined,
      })),
  )
}

function pickFiles() {
  fileInput.value?.click()
}

async function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files || input.files.length === 0) return
  const files = Array.from(input.files).slice(0, maxImages - pending.value.length)

  for (const file of files) {
    if (!file.type.startsWith('image/')) continue
    if (file.size > 10 * 1024 * 1024) {
      toast.show('图片不能超过 10MB', 'warning')
      continue
    }
    const preview = URL.createObjectURL(file)
    const item: PendingImage = {
      id: genId(),
      image_url: '',
      preview,
      body_site: '',
      capture_date: today,
      uploading: true,
    }
    pending.value.push(item)
    try {
      const result = await communityApi.uploadImage(file)
      item.image_url = result.image_url
      item.uploading = false
      sync()
    } catch {
      toast.show('图片上传失败', 'error')
      pending.value = pending.value.filter((p) => p.id !== item.id)
      URL.revokeObjectURL(preview)
    }
  }
  input.value = ''
}

function removeItem(id: string) {
  const item = pending.value.find((p) => p.id === id)
  if (item) URL.revokeObjectURL(item.preview)
  pending.value = pending.value.filter((p) => p.id !== id)
  sync()
}

function onSiteChange(id: string, value: string) {
  const item = pending.value.find((p) => p.id === id)
  if (item) {
    item.body_site = value
    sync()
  }
}

function onDateChange(id: string, value: string) {
  const item = pending.value.find((p) => p.id === id)
  if (item) {
    item.capture_date = value
    sync()
  }
}

function clearAll() {
  pending.value.forEach((p) => URL.revokeObjectURL(p.preview))
  pending.value = []
  sync()
}

defineExpose({ clearAll })
</script>

<template>
  <div class="diary-uploader">
    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      multiple
      class="hidden"
      @change="onFileChange"
    />

    <!-- 预览网格 -->
    <div v-if="pending.length > 0" class="diary-uploader__grid">
      <div v-for="item in pending" :key="item.id" class="diary-uploader__item">
        <div class="diary-uploader__thumb">
          <img :src="item.preview" alt="预览" />
          <div v-if="item.uploading" class="diary-uploader__mask">
            <i class="ri-loader-4-line animate-spin"></i>
            <span>上传中</span>
          </div>
          <button
            v-else
            class="diary-uploader__remove"
            @click="removeItem(item.id)"
            aria-label="删除"
          >
            <i class="ri-close-line"></i>
          </button>
        </div>
        <select
          class="diary-uploader__select"
          :value="item.body_site"
          @change="onSiteChange(item.id, ($event.target as HTMLSelectElement).value)"
          :disabled="item.uploading"
        >
          <option value="">选择部位</option>
          <option v-for="s in siteOptions" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
        <input
          type="date"
          class="diary-uploader__date"
          :value="item.capture_date"
          @change="onDateChange(item.id, ($event.target as HTMLInputElement).value)"
          :disabled="item.uploading"
        />
      </div>

      <!-- 添加按钮 -->
      <button
        v-if="pending.length < maxImages"
        class="diary-uploader__add"
        @click="pickFiles"
        aria-label="添加图片"
      >
        <i class="ri-image-add-line"></i>
        <span>添加</span>
      </button>
    </div>

    <!-- 空状态触发按钮 -->
    <button v-else class="diary-uploader__trigger" @click="pickFiles">
      <i class="ri-image-add-line"></i>
      <span>添加白斑照片</span>
      <span class="diary-uploader__trigger-hint">记录变化，支持历史补录</span>
    </button>
  </div>
</template>

<style scoped>
.diary-uploader {
  margin-top: 10px;
}

.diary-uploader__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.diary-uploader__item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.diary-uploader__thumb {
  position: relative;
  aspect-ratio: 1;
  border-radius: 10px;
  overflow: hidden;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}

html.dark .diary-uploader__thumb {
  background: #334155;
  border-color: #475569;
}

.diary-uploader__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.diary-uploader__mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: white;
  font-size: 11px;
}

.diary-uploader__mask i {
  font-size: 22px;
}

.diary-uploader__remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.55);
  color: white;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  line-height: 1;
}

.diary-uploader__select,
.diary-uploader__date {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 4px 6px;
  font-size: 11px;
  color: #475569;
  background: white;
  outline: none;
}

html.dark .diary-uploader__select,
html.dark .diary-uploader__date {
  background: #1e293b;
  border-color: #334155;
  color: #cbd5e1;
}

.diary-uploader__select:focus,
.diary-uploader__date:focus {
  border-color: var(--color-primary-500);
}

.diary-uploader__add {
  aspect-ratio: 1;
  border: 1.5px dashed #cbd5e1;
  border-radius: 10px;
  background: transparent;
  color: #94a3b8;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

html.dark .diary-uploader__add {
  border-color: #475569;
}

.diary-uploader__add i {
  font-size: 22px;
}

.diary-uploader__add:active {
  border-color: var(--color-primary-500);
  color: var(--color-primary-500);
}

.diary-uploader__trigger {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 16px;
  border: 1.5px dashed color-mix(in srgb, var(--color-primary-500) 35%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--color-primary-500) 4%, transparent);
  color: var(--color-primary-600);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.diary-uploader__trigger i {
  font-size: 26px;
}

.diary-uploader__trigger-hint {
  font-size: 11px;
  font-weight: 400;
  color: #94a3b8;
}

.diary-uploader__trigger:active {
  transform: scale(0.98);
}

.hidden {
  display: none;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
