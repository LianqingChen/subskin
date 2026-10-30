<template>
  <div class="thumb" :style="{ width: `${size}px`, height: `${size}px` }">
    <img v-if="url" :src="url" :alt="alt" loading="lazy" />
    <i v-else :class="failed ? 'ri-image-line' : 'ri-loader-4-line spin'" aria-hidden="true" />
  </div>
</template>
<script setup lang="ts">
import { toRef } from 'vue'
import { useAuthImage } from '@/composables/useAuthImage'

const props = withDefaults(defineProps<{ id: number; alt?: string; size?: number }>(), { alt: '任务缩略图', size: 56 })
const { url, failed } = useAuthImage(toRef(props, 'id'), 'thumb')
</script>
<style scoped>
.thumb { display: flex; align-items: center; justify-content: center; flex-shrink: 0; border-radius: 8px; overflow: hidden; background: rgba(128, 128, 128, .12); color: rgba(128, 128, 128, .8); font-size: 20px; }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.spin { animation: thumb-spin 1s linear infinite; }
@keyframes thumb-spin { to { transform: rotate(360deg); } }
</style>
