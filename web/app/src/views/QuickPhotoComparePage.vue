<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BODY_SITES } from '@/constants/bodySites'
import { useQuickPhotoCompare, takeComparisonPhotos } from '@/composables/useQuickPhotoCompare'
import { useVasiHistory } from '@/composables/useVasiHistory'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import ComparisonAlignmentControls from '@/components/report/ComparisonAlignmentControls.vue'
import type { AlignmentTransform } from '@/types/comparison-alignment'
import { assessmentError } from '@/utils/assessment-errors'
import { localToday } from '@/utils/capture-date'
import AssessmentRecords from '@/components/tracker/AssessmentRecords.vue'
interface Photo { key: number; file: File; url: string; date: string }
const route = useRoute(), router = useRouter(), auth = useAuthStore(), toast = useToast()
const compare = useQuickPhotoCompare(), history = useVasiHistory()
const queuedPhotos = takeComparisonPhotos()
const manualAlignment = ref<AlignmentTransform | null>(null), manualReady = ref(false)
const photos = ref<Photo[]>([]), mode = ref<'photos' | 'records'>(queuedPhotos.length ? 'photos' : 'records')
const selectedSite = computed(() => Object.values(BODY_SITES).find(site => site.id === route.query.site))
const input = ref<HTMLInputElement | null>(null)
const today = localToday()
let nextKey = 0, active = true
const slots = computed(() => [photos.value[0] || null, photos.value[1] || null])
const ready = computed(() => photos.value.length === 2 && !!selectedSite.value && photos.value.every(p => !!p.date && p.date <= today))
const orderedPhotos = computed(() => [...photos.value].sort((a, b) => a.date.localeCompare(b.date)))
watch(() => [ready.value, orderedPhotos.value.map(photo => photo.key).join(',')], () => { manualAlignment.value = null })
function clearPhotos() { photos.value.forEach(p => URL.revokeObjectURL(p.url)); photos.value = [] }
function select(event: Event) {
  addFiles(Array.from((event.target as HTMLInputElement).files || []))
  if (input.value) input.value.value = ''
}
function addFiles(files: File[]) {
  if (!files.length || compare.generating.value || !selectedSite.value) return
  if (photos.value.length + files.length > 2) { toast.warning('白斑对比只需两张照片，请重新选择'); return }
  if (files.some(file => !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024)) { toast.warning('请选择10MB以内的JPG、PNG或WebP照片'); return }
  photos.value.push(...files.map(file => ({ key: ++nextKey, file, url: URL.createObjectURL(file), date: '' })))
}
watch(selectedSite, (site, previous) => {
  if (previous?.id !== site?.id) clearPhotos()
  if (!site) { takeComparisonPhotos(); toast.warning('先在记录中点选身体部位'); void router.replace('/assessment') }
}, { immediate: true })
watch(() => auth.user?.id, () => { clearPhotos(); history.recentAssessments.value = [] })
watch([mode, selectedSite, () => auth.isLoggedIn, () => auth.user?.id], ([source, site, loggedIn]) => {
  if (source !== 'records' || !site) return
  if (!loggedIn) { history.recentAssessments.value = []; auth.showLoginModal = true; return }
  void history.loadHistory(true, site.id)
}, { immediate: true })
onMounted(() => addFiles(queuedPhotos))
function remove(photo: Photo) { URL.revokeObjectURL(photo.url); photos.value = photos.value.filter(p => p.key !== photo.key) }
function compareRecords(ids: number[]) {
  if (ids.length !== 2 || !selectedSite.value) return
  void router.push({ name: 'vasi-compare', query: { ids: ids.join(','), site: selectedSite.value.id } })
}
async function generate() {
  if (!auth.isLoggedIn) { auth.showLoginModal = true; return }
  const site = selectedSite.value?.id
  if (!ready.value || !site) return
  try {
    const id = await compare.generateReport(orderedPhotos.value, site, manualAlignment.value)
    if (active && selectedSite.value?.id === site) void router.push({ name: 'skin-report-view', params: { id } })
  } catch (error) { if (active) toast.error(assessmentError(error, '对比结果暂时无法创建，请重试')) }
}
onUnmounted(() => { active = false; clearPhotos() })
</script>
<template>
  <div v-if="selectedSite" class="page space-y-4 py-5 pb-8 text-gray-900 dark:text-gray-100 md:py-6 md:pb-10 lg:max-w-5xl">
    <header class="flex items-center gap-2"><router-link to="/assessment" class="-ml-2 flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800" aria-label="返回记录选择部位"><i class="ri-arrow-left-line text-xl" aria-hidden="true"></i></router-link><div class="min-w-0"><h1 class="page-title">白斑对比</h1><p class="text-sm text-gray-500 dark:text-gray-400">当前部位：<strong class="font-medium text-primary-700 dark:text-primary-300">{{ selectedSite.label }}</strong></p></div></header>
    <div role="group" aria-label="对比来源" class="inline-flex gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800">
      <button v-for="option in [{ id: 'records' as const, label: '两次记录' }, { id: 'photos' as const, label: '两张照片' }]" :key="option.id" type="button" :aria-pressed="mode === option.id" :disabled="compare.generating.value" class="min-h-[40px] rounded-lg px-4 text-sm disabled:opacity-40" :class="mode === option.id ? 'bg-white font-medium text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-200' : 'text-gray-600 dark:text-gray-400'" @click="mode = option.id">{{ option.label }}</button>
    </div>
    <template v-if="mode === 'photos'">
      <!-- 手机端主按钮在上方独占一行；平板/桌面与说明同排 -->
      <div class="flex flex-col gap-3 md:flex-row-reverse md:items-center md:justify-between">
        <button class="btn-primary min-h-[48px] w-full rounded-xl disabled:opacity-40 md:w-auto md:min-h-[44px] md:px-5" :disabled="!ready || compare.generating.value || (!!manualAlignment && !manualReady)" @click="generate">{{ compare.generating.value ? '正在保存…' : manualAlignment ? '确认对齐并分析' : '开始白斑对比' }}</button>
        <p class="text-sm text-gray-500 dark:text-gray-400">添加两张同一部位的照片，确认各自拍摄日期。</p>
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <figure v-for="(photo, index) in slots" :key="photo?.key || `empty-${index}`" class="card min-w-0 p-4">
          <template v-if="photo">
            <img :src="photo.url" :alt="`对比照片 ${index + 1}`" class="max-h-[38dvh] w-full rounded-xl object-contain" />
            <figcaption class="mt-3"><label class="block text-sm">拍摄日期<input v-model="photo.date" type="date" :max="today" :disabled="compare.generating.value" class="mt-2 block min-h-[44px] min-w-0 w-full rounded-xl border border-gray-300 bg-white px-3 dark:border-gray-600 dark:bg-gray-800" /></label><button type="button" class="mt-2 min-h-[44px] text-sm text-primary-700 underline dark:text-primary-300" :disabled="compare.generating.value" @click="remove(photo)">移除此照片</button></figcaption>
          </template>
          <button v-else type="button" class="flex min-h-[160px] w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-gray-300 text-sm text-primary-700 dark:border-gray-600 dark:text-primary-300" :disabled="compare.generating.value" @click="input?.click()"><i class="ri-image-add-line text-2xl" aria-hidden="true"></i>添加照片</button>
        </figure>
      </div>
      <input ref="input" type="file" multiple accept="image/jpeg,image/png,image/webp" aria-label="选择两张对比照片" class="hidden" :disabled="compare.generating.value" @change="select" />
      <ComparisonAlignmentControls v-if="ready" v-model="manualAlignment" :before-url="orderedPhotos[0].url" :after-url="orderedPhotos[1].url" :disabled="compare.generating.value" @ready="manualReady = $event" />
      <p class="text-xs text-gray-500 dark:text-gray-400">角度或范围不同的照片，仅作并排观察。</p>
    </template>
    <AssessmentRecords v-else selecting :key="selectedSite.id" :items="history.recentAssessments.value" :loading="history.loadingHistory.value" :page="history.historyPage.value" :total-pages="history.historyTotalPages.value" @create="mode = 'photos'" @page="history.goToPage" @compare="compareRecords" />
  </div>
</template>
