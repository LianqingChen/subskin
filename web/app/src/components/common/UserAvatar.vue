<script setup lang="ts">
/**
 * Unified UserAvatar component.
 * Replaces 5 independent avatar implementations across the app.
 *
 * Features:
 * - Image avatar with error fallback to initial letter
 * - Configurable size
 * - Optional edit/upload overlay
 * - Optional link to user profile
 * - Theme-aware colors via primary-* CSS variables
 */
import { ref, computed, watch } from 'vue'
import { toProtectedFileUrl } from '@/utils/file-url'

const props = withDefaults(defineProps<{
  /** Full image URL (will be processed via toProtectedFileUrl) */
  imageUrl?: string | null
  /** Fallback initial (first character of username) */
  initial?: string
  /** Avatar size in Tailwind classes (e.g., 'w-10 h-10') */
  size?: string
  /** Show edit/upload overlay on hover */
  editable?: boolean
  /** Loading state for upload overlay */
  uploading?: boolean
  /** Link to user profile - if provided, wraps in router-link */
  userId?: number | null
}>(), {
  imageUrl: null,
  initial: 'U',
  size: 'w-10 h-10',
  editable: false,
  uploading: false,
  userId: null,
})

const emit = defineEmits<{
  click: []
}>()

const avatarLoadError = ref(false)
const protectedUrl = computed(() => toProtectedFileUrl(props.imageUrl || ''))
const showImage = computed(() => !!protectedUrl.value && !avatarLoadError.value)
const initialChar = computed(() => (props.initial || 'U').charAt(0).toUpperCase())

watch(() => props.imageUrl, () => {
  avatarLoadError.value = false
})

function onError() {
  avatarLoadError.value = true
}

function handleClick() {
  emit('click')
}
</script>

<template>
  <div
    :class="[size, 'rounded-full overflow-hidden bg-primary-100 dark:bg-primary-900 shrink-0 relative', editable ? 'group cursor-pointer' : '']"
    :role="userId ? 'link' : undefined"
    @click="handleClick"
  >
    <!-- Image avatar -->
    <img
      v-if="showImage"
      :src="protectedUrl"
      alt="用户头像"
      class="absolute inset-0 w-full h-full object-cover"
      @error="onError"
    />

    <!-- Initial fallback -->
    <span
      v-else
      class="absolute inset-0 flex items-center justify-center text-primary-700 dark:text-primary-300 font-bold"
      :class="size === 'w-8 h-8' ? 'text-xs' : size === 'w-4 h-4' ? 'text-[9px]' : 'text-lg'"
    >
      {{ initialChar }}
    </span>

    <!-- Edit overlay (when editable) -->
    <span
      v-if="editable"
      class="absolute inset-0 bg-black/40 backdrop-blur-[2px] rounded-full flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200"
      :class="{ 'opacity-100': uploading }"
    >
      <svg v-if="!uploading" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-5 h-5 text-white mb-0.5">
        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
        <circle cx="12" cy="13" r="4"/>
      </svg>
      <span v-if="!uploading" class="text-[10px] text-white font-medium">更换</span>
      <span v-else class="text-xs text-white font-medium">上传中</span>
    </span>
  </div>
</template>
