<script setup lang="ts">
/**
 * PhotoMetaEditor — 白斑照片拍摄日期编辑弹窗
 *
 * 照片墙点击日期打开：补标注/修改拍摄日期（删除照片已改为照片右上角 × 直接操作）。
 */
import { computed, ref, watch } from 'vue'
import type { PostImage } from '@/types'
import { updatePhotoMeta } from '@/api/skin_report'
import { toProtectedFileUrl } from '@/utils/file-url'
import { useToast } from '@/composables/useToast'
import DateWheelPicker from '@/components/common/DateWheelPicker.vue'

const props = defineProps<{
  visible: boolean
  image: PostImage | null
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const toast = useToast()
const captureDate = ref<string | null>(null)
const saving = ref(false)

const imgSrc = computed(() =>
  props.image ? toProtectedFileUrl(props.image.image_url) || props.image.image_url : '',
)

watch(
  () => [props.visible, props.image] as const,
  ([visible, image]) => {
    if (visible && image) {
      captureDate.value = (image.capture_date || '').slice(0, 10) || null
    }
  },
  { immediate: true },
)

async function save() {
  if (!props.image || saving.value) return
  saving.value = true
  try {
    await updatePhotoMeta(props.image.id, {
      capture_date: captureDate.value || null,
    })
    toast.show('照片信息已更新', 'success')
    emit('saved')
    emit('close')
  } catch (err: any) {
    toast.show(err?.response?.data?.detail || '保存失败，请重试', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible && image"
      class="fixed inset-0 bg-black/50 z-[110] flex items-end sm:items-center justify-center"
      @click.self="emit('close')"
    >
      <div class="bg-white dark:bg-gray-800 rounded-t-2xl sm:rounded-2xl w-full sm:max-w-sm mx-auto shadow-xl px-5 pt-4 pb-5 safe-bottom max-h-[92dvh] overflow-y-auto">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">修改拍摄日期</h3>
          <button
            type="button"
            class="w-9 h-9 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
            aria-label="关闭"
            @click="emit('close')"
          >
            <i class="ri-close-line text-lg"></i>
          </button>
        </div>

        <img
          :src="imgSrc"
          :alt="`白斑照片 ${image.id}`"
          class="w-full h-36 object-cover rounded-xl bg-gray-100 dark:bg-gray-700 mb-4"
        />

        <div class="mb-4">
          <span class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-medium text-gray-500 dark:text-gray-400">
              拍摄日期
              <em v-if="captureDate" class="not-italic text-primary-600 dark:text-primary-400 font-semibold">{{ captureDate }}</em>
              <em v-else class="not-italic text-amber-600">（未标注）</em>
            </span>
            <button
              v-if="captureDate"
              type="button"
              class="text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400 px-2 py-1 rounded"
              @click="captureDate = null"
            >
              清除日期
            </button>
          </span>
          <DateWheelPicker v-model="captureDate" />
        </div>

        <div class="flex items-center gap-3 justify-end">
          <button type="button" class="btn-ghost min-h-[44px] px-4" :disabled="saving" @click="emit('close')">
            取消
          </button>
          <button type="button" class="btn-primary min-h-[44px] px-5" :disabled="saving" @click="save">
            <i v-if="saving" class="ri-loader-4-line ri-spin mr-1"></i>
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
