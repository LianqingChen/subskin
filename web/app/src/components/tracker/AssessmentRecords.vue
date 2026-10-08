<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { measuredPercentage } from '@/utils/assessment-story/summary'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { toProtectedFileUrl } from '@/utils/file-url'
import type { ObservationContext, PhotoMeasurement } from '@/types/assessment'
export interface ObservationRecord { id: number; date: string; bodySite: string; imageUrl?: string; observation?: ObservationContext | null; measurement?: PhotoMeasurement | null }
const props = defineProps<{ items: ObservationRecord[]; loading: boolean; page: number; totalPages: number; tracking?: boolean; selecting?: boolean }>()
const emit = defineEmits<{ continue: [ObservationRecord]; page: [number]; compare: [number[]]; create: [] }>()
// 手绘范围同图重复约有 ±5 个百分点的误差，接近这个幅度的变化不当作趋势。
const NOISE_POINTS = 5
const trend = computed(() => {
  const out = new Map<number, { percent: number; delta: number | null }>()
  props.items.forEach((item, index) => {
    const percent = measuredPercentage(item.measurement)
    if (percent === null) return
    const key = item.observation?.label || item.bodySite
    const earlier = props.items.slice(index + 1).find(other => (other.observation?.label || other.bodySite) === key && measuredPercentage(other.measurement) !== null)
    out.set(item.id, { percent, delta: earlier ? percent - (measuredPercentage(earlier.measurement) as number) : null })
  })
  return out
})
function trendText(delta: number) {
  if (Math.abs(delta) < NOISE_POINTS) return '与上次接近'
  return `较上次${delta < 0 ? '减少' : '增加'} ${Math.abs(delta).toFixed(1)} 个百分点`
}
const selected = ref<number[]>([])
const selectionHint = ref('')
function toggle(id: number) {
  selectionHint.value = ''
  if (selected.value.includes(id)) selected.value = selected.value.filter(value => value !== id)
  else if (selected.value.length < 2) selected.value = [...selected.value, id]
  else selectionHint.value = '最多对比两条记录，请先取消一条已选记录'
}
watch(() => props.items, items => {
  selected.value = selected.value.filter(id => items.some(item => item.id === id))
  selectionHint.value = ''
})
</script>
<template>
  <section aria-label="白斑记录列表" class="space-y-4">
    <h2 v-if="tracking" class="text-xl font-semibold">选择之前记录的位置</h2>
    <aside v-if="!tracking && (selecting || selected.length)" aria-label="白斑对比选择" class="rounded-2xl border border-primary-200 bg-white p-4 shadow-sm dark:border-primary-800 dark:bg-gray-800">
      <div class="flex flex-wrap items-center gap-3"><p role="status" class="min-w-0 flex-1 text-sm font-medium">已选 {{ selected.length }} / 2 条记录</p><button v-if="selected.length" class="min-h-11 px-3 text-sm text-gray-500 dark:text-gray-400" @click="selected = []; selectionHint = ''">清空</button><button class="btn-primary min-h-11 text-sm disabled:opacity-40" :disabled="loading || selected.length !== 2" @click="emit('compare', selected)">开始对比</button></div>
      <p v-if="selectionHint" role="status" class="mt-2 text-sm text-primary-700 dark:text-primary-300">{{ selectionHint }}</p>
    </aside>
    <LoadingSpinner v-if="loading" message="正在加载记录…" />
    <EmptyState v-else-if="!items.length" icon="ri-camera-line" title="还没有白斑记录" description="拍下第一张照片，留下下次对照的参照。" action-label="开始拍照记录" @action="emit('create')" />
    <!-- 桌面端两列卡片，避免单列卡片横向过宽 -->
    <div v-if="!loading && items.length" class="grid gap-3 lg:grid-cols-2 lg:gap-4">
    <article v-for="item in items" :key="item.id" :class="selected.includes(item.id) ? 'ring-2 ring-primary-500' : ''" class="flex flex-col rounded-2xl border border-gray-200/80 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <router-link :to="{ name: 'vasi-detail', params: { id: item.id } }" :aria-label="`查看${item.observation?.label || item.bodySite}的记录结果`" class="flex min-h-[44px] items-center gap-3 rounded-lg">
        <img v-if="item.imageUrl" :src="toProtectedFileUrl(item.imageUrl)" alt="记录照片缩略图" class="h-20 w-20 shrink-0 rounded-xl object-cover" />
        <span class="min-w-0 flex-1"><span class="block font-medium">{{ item.observation?.label || item.bodySite }}</span><time :datetime="item.date" class="mt-1 block text-sm text-gray-500 dark:text-gray-400">{{ item.date }}</time><span v-if="item.measurement?.status === 'legacy' || !item.measurement" class="mt-1 block text-xs text-gray-500 dark:text-gray-400">历史记录</span><span v-else-if="trend.get(item.id)" class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs"><span class="font-medium text-gray-800 dark:text-gray-100">照片内白斑占比 {{ Number(trend.get(item.id)!.percent.toFixed(1)) }}%</span><span v-if="trend.get(item.id)!.delta !== null" :class="Math.abs(trend.get(item.id)!.delta!) < NOISE_POINTS ? 'text-gray-500 dark:text-gray-400' : trend.get(item.id)!.delta! < 0 ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'">{{ trendText(trend.get(item.id)!.delta!) }}</span></span><span v-else class="mt-1 block text-xs text-gray-500 dark:text-gray-400">暂无占比</span></span>
        <i class="ri-arrow-right-s-line shrink-0 text-gray-400" aria-hidden="true"></i>
      </router-link>
      <div class="mt-auto flex flex-wrap justify-end gap-2 pt-2"><button v-if="!selecting" type="button" class="min-h-[44px] rounded-lg px-3 text-sm text-primary-700 dark:text-primary-300" @click="emit('continue', item)">继续拍</button><button v-if="!tracking" type="button" class="min-h-[44px] rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-600" :aria-pressed="selected.includes(item.id)" @click="toggle(item.id)"><i v-if="selected.includes(item.id)" class="ri-checkbox-circle-fill mr-1 text-primary-600 dark:text-primary-300" aria-hidden="true"></i>{{ selected.includes(item.id) ? '已选对比' : '选择对比' }}</button></div>
    </article>
    </div>
    <nav v-if="totalPages > 1" aria-label="白斑记录分页" class="flex items-center justify-center gap-4"><button class="min-h-[44px] px-3 disabled:opacity-40" :disabled="page <= 1" @click="selected = []; emit('page', page - 1)">上一页</button><span class="text-sm">{{ page }} / {{ totalPages }}</span><button class="min-h-[44px] px-3 disabled:opacity-40" :disabled="page >= totalPages" @click="selected = []; emit('page', page + 1)">下一页</button></nav>
  </section>
</template>
