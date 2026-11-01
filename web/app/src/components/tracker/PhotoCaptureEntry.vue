<script setup lang="ts">
import { ref, useId } from 'vue'
import { BODY_SITES } from '@/constants/bodySites'
const props = defineProps<{ bodySite: string; loggedIn: boolean; creative?: boolean }>()
const emit = defineEmits<{ select: [string]; camera: []; files: [File[]]; login: [] }>()
const input = ref<HTMLInputElement | null>(null)
const fieldId = useId()
function openCamera() { if (!props.loggedIn) emit('login'); else emit('camera') }
function openGallery() { if (!props.loggedIn) emit('login'); else input.value?.click() }
function selected(event: Event) {
  const element = event.target as HTMLInputElement
  if (element.files?.[0]) emit('files', [element.files[0]])
  element.value = ''
}
</script>
<template>
  <div class="space-y-3">
    <label :for="fieldId" class="block text-sm font-medium">这次拍哪个部位？</label>
    <select :id="fieldId" :value="bodySite" class="input-field min-h-[44px] min-w-0 w-full bg-white text-gray-900 dark:bg-gray-900 dark:text-gray-100" @change="emit('select', ($event.target as HTMLSelectElement).value)">
      <option value="" disabled>选择身体部位</option>
      <option v-for="site in BODY_SITES" :key="site.id" :value="site.id">{{ site.label }}</option>
    </select>
    <p class="text-xs leading-5 text-gray-500 dark:text-gray-400">光线均匀，拍全白斑和周围皮肤。</p>
    <button type="button" :disabled="!bodySite" class="btn-primary min-h-[48px] w-full disabled:opacity-40" :data-track-id="creative ? 'story_camera' : 'diary_camera'" @click="openCamera"><i class="ri-camera-line mr-2" aria-hidden="true"></i>{{ creative ? '拍照创作' : '打开相机' }}</button>
    <button type="button" :disabled="!bodySite" class="min-h-[44px] w-full text-sm text-primary-700 disabled:opacity-40 dark:text-primary-300" @click="openGallery">从相册选择一张</button>
    <input ref="input" type="file" accept="image/jpeg,image/png,image/webp" aria-label="选择白斑照片" class="hidden" @change="selected" />
  </div>
</template>
