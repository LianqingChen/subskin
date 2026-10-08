<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ObservationContext } from '@/types/assessment'
const props = defineProps<{ image: string }>()
const emit = defineEmits<{ change: [ObservationContext['calibration']] }>()
const points = ref<number[][]>([])
const length = ref(25)
const samePlane = ref(false)
const cursor = ref([0.5, 0.5])
function keyboard(event: KeyboardEvent) {
  const arrows: Record<string, number[]> = { ArrowLeft: [-0.01,0], ArrowRight: [0.01,0], ArrowUp: [0,-0.01], ArrowDown: [0,0.01] }
  if (arrows[event.key]) { event.preventDefault(); cursor.value = cursor.value.map((v,i) => Math.max(0, Math.min(1, v + arrows[event.key][i]))) }
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); points.value = points.value.length === 2 ? [[...cursor.value]] : [...points.value, [...cursor.value]] }
}
function select(event: MouseEvent) {
  const box = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const point = [(event.clientX - box.left) / box.width, (event.clientY - box.top) / box.height]
  points.value = points.value.length === 2 ? [point] : [...points.value, point]
}
function update() { emit('change', points.value.length === 2 && samePlane.value && length.value > 0 ? { points: points.value, length_mm: length.value, same_plane: true } : undefined) }
watch([points, length, samePlane], update)
watch(() => props.image, () => { points.value = []; samePlane.value = false; emit('change', undefined) })
</script>
<template>
  <details class="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
    <summary class="min-h-[44px] cursor-pointer text-sm">尺寸标定（选填，可换算真实面积）</summary>
    <p class="mb-3 text-sm text-gray-600 dark:text-gray-400">把一枚硬币放在患处旁，点它直径的两端并填写对应毫米数；也可点选尺子上两个已知刻度。参照物需与皮肤近似同平面，倾斜明显、曲面或没有参照物时请跳过。</p>
    <div class="relative cursor-crosshair focus:outline focus:outline-primary-500" tabindex="0" role="button" aria-label="标定参照物：方向键移动光标，回车确认落点" @keydown="keyboard" @click="select"><img :src="image" alt="在参照物上点选参照物两端或两个已知刻度" class="block h-auto w-full rounded-xl" /><svg class="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none"><circle :cx="cursor[0]*100" :cy="cursor[1]*100" r="0.8" fill="none" stroke="currentColor" stroke-width="0.3" class="text-primary-500" /><line v-if="points.length === 2" :x1="points[0][0]*100" :y1="points[0][1]*100" :x2="points[1][0]*100" :y2="points[1][1]*100" stroke="currentColor" stroke-width="0.6" class="text-primary-500" /><circle v-for="(point,i) in points" :key="i" :cx="point[0]*100" :cy="point[1]*100" r="1.2" fill="currentColor" class="text-primary-500" /></svg></div>
    <div class="mt-3 grid gap-3 sm:grid-cols-2"><label class="text-sm">两点实际距离（毫米）<input v-model.number="length" type="number" min="1" max="1000" class="mt-2 block min-h-[44px] w-full rounded-lg border border-gray-300 bg-white px-3 dark:border-gray-600 dark:bg-gray-800" /></label><div class="flex flex-wrap content-end items-end gap-2 text-sm"><button type="button" class="min-h-[44px] rounded-lg border border-gray-300 px-3 dark:border-gray-600" @click="length = 25">一元硬币 25 毫米</button><button type="button" class="min-h-[44px] rounded-lg border border-gray-300 px-3 dark:border-gray-600" @click="length = 19">一角硬币 19 毫米</button><button type="button" class="min-h-[44px] px-3 underline" @click="points = []">重新点选</button></div></div>
    <label class="mt-3 flex min-h-[44px] items-center gap-3 text-sm"><input v-model="samePlane" type="checkbox" class="h-5 w-5" />我确认参照物尺寸填写正确，且它与目标皮肤近似同平面</label>
    <p aria-live="polite" class="mt-2 text-sm text-gray-500">{{ points.length === 2 && samePlane ? '已添加参照物，将估算二维投影面积。' : '未完成标定时只记录照片内占比。' }}</p>
  </details>
</template>
