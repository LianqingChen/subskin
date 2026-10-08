<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useObservationCompare } from '@/composables/useObservationCompare'
import ComparisonAlignmentControls from '@/components/report/ComparisonAlignmentControls.vue'
import type { AlignmentTransform } from '@/types/comparison-alignment'
import { toProtectedFileUrl } from '@/utils/file-url'
const route = useRoute()
const router = useRouter()
const compare = useObservationCompare()
const manualAlignment = ref<AlignmentTransform | null>(null), manualReady = ref(false)
watch(() => compare.items.value.map(item => item.id).join(','), () => { manualAlignment.value = null })
const ids = computed(() => [...new Set(String(route.query.ids || '').split(',').map(Number).filter(id => Number.isInteger(id) && id > 0))])
watch([ids, () => route.query.site], () => compare.load(ids.value, typeof route.query.site === 'string' ? route.query.site : undefined), { immediate: true })
const samePosition = computed(() => {
  const first = compare.items.value[0]?.observation
  return !!first?.id && compare.items.value.every(i => i.observation?.id === first.id && i.observation?.view === first.view)
})
async function generate() { const id = await compare.generate(manualAlignment.value); if (id) router.push({ name: 'skin-report-view', params: { id } }) }
</script>
<template>
  <div class="page space-y-5 py-5 pb-8 text-gray-900 dark:text-gray-100 md:py-6 md:pb-10 lg:max-w-5xl">
    <!-- 标题区：桌面端主操作放在标题右侧，手机端独占一行 -->
    <header class="flex flex-wrap items-center gap-x-2 gap-y-3">
      <router-link to="/assessment" class="-ml-2 flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800" aria-label="返回记录"><i class="ri-arrow-left-line text-xl" aria-hidden="true"></i></router-link>
      <h1 class="page-title">白斑对比</h1>
      <button class="btn-primary min-h-[48px] w-full rounded-xl disabled:opacity-40 md:ml-auto md:w-auto md:min-h-[44px] md:px-5" :disabled="compare.loading.value || compare.generating.value || compare.items.value.length !== 2 || (!!manualAlignment && !manualReady)" @click="generate">{{ compare.generating.value ? '正在创建对比…' : manualAlignment ? '确认对齐并分析' : '检查可比性并生成结果' }}</button>
    </header>
    <p v-if="compare.loading.value" role="status" class="text-sm text-gray-500 dark:text-gray-400">正在加载照片…</p><p v-if="compare.error.value" role="alert" class="rounded-xl bg-primary-50 p-4 dark:bg-primary-900">{{ compare.error.value }}</p>
    <ComparisonAlignmentControls v-if="compare.items.value.length === 2" v-model="manualAlignment" :before-url="compare.items.value[0].image_url" :after-url="compare.items.value[1].image_url" :disabled="compare.generating.value" @ready="manualReady = $event" />
    <div class="grid gap-4 md:grid-cols-2"><figure v-for="item in compare.items.value" :key="item.id" class="card p-4"><img :src="toProtectedFileUrl(item.image_url)" alt="参与比较的观察照片" class="max-h-[45dvh] w-full rounded-xl object-contain" /><figcaption class="mt-3 text-sm"><strong>{{ item.observation?.label || item.body_site }}</strong><p class="mt-1 text-gray-500 dark:text-gray-400">{{ item.assessment_date.slice(0,10) }} · {{ item.observation?.view || '视角未记录' }}</p></figcaption></figure></div>
    <p v-if="compare.items.value.length && !samePosition" class="rounded-2xl border border-gray-200/80 bg-white p-4 text-sm leading-6 text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300">这些记录可直接尝试对比；若画面位置不同，可以先手动调整叠影。</p>
  </div>
</template>
