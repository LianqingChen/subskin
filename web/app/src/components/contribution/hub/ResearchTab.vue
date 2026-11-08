<script setup lang="ts">
import { computed } from 'vue'
import { getKnowledgeResearch, type KnowledgeResearch, type ResearchPurpose } from '@/api/knowledge'
import { useKnowledgeResource } from '@/composables/useKnowledgeResource'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import HubState from './HubState.vue'

const { data, loading, error, load } = useKnowledgeResource<KnowledgeResearch>(() => getKnowledgeResearch())
const purposes = computed(() => data.value?.purposes ?? [])
const projects = computed(() => data.value?.projects ?? [])
const PROMISES = ['不出售社区数据', '逐项目单独授权', '可随时撤回', '研究数据存放在境内', '研究须经合作机构伦理审查']
function activeText(p: ResearchPurpose) {
  const a = p.active
  if (a.status === 'suppressed') return '人数较少暂不公开'
  if (a.status === 'available' && a.value !== null) return `${a.value.toLocaleString('zh-CN')} 人已授权`
  return a.note || '暂无统计'
}
</script>

<template>
  <div class="space-y-6">
    <section aria-labelledby="research-data-title" class="space-y-3">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="research-data-title" class="text-base font-semibold">你的数据去了哪里</h2>
        <router-link to="/profile/data" class="inline-flex min-h-11 items-center text-sm text-primary-700 hover:underline dark:text-primary-300">管理我的授权<i class="ri-arrow-right-line ml-0.5" aria-hidden="true"></i></router-link>
      </div>
      <HubState :loading="loading" :error="error" :empty="!purposes.length" empty-text="数据用途说明暂时无法显示，请稍后再试" :skeleton="2" @retry="load">
        <ul class="grid gap-3 md:grid-cols-2">
          <li v-for="p in purposes" :key="p.purpose" class="card space-y-2 p-4 dark:bg-gray-800">
            <div class="flex items-start justify-between gap-2">
              <h3 class="text-sm font-semibold">{{ p.title }}</h3>
              <span class="shrink-0 rounded-md px-1.5 py-0.5 text-xs font-medium" :class="p.open ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'border border-dashed border-gray-400 text-gray-600 dark:border-gray-500 dark:text-gray-300'">{{ p.open ? '开放中' : '未开放' }}</span>
            </div>
            <p class="text-sm leading-6 text-gray-600 dark:text-gray-400">{{ p.description }}</p>
            <p class="text-xs tabular-nums text-gray-500 dark:text-gray-400"><i class="ri-user-line" aria-hidden="true"></i> {{ activeText(p) }}</p>
          </li>
        </ul>
      </HubState>
    </section>

    <section aria-labelledby="research-projects-title" class="space-y-3">
      <h2 id="research-projects-title" class="text-base font-semibold">研究项目公示</h2>
      <ul v-if="projects.length" class="space-y-3">
        <li v-for="(pr, i) in projects" :key="pr.key ?? i" class="card p-4 dark:bg-gray-800">
          <h3 class="text-sm font-semibold">{{ pr.title || pr.name }}</h3>
          <p v-if="pr.institution" class="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{{ pr.institution }}</p>
          <p v-if="pr.summary" class="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-400">{{ pr.summary }}</p>
        </li>
      </ul>
      <p v-else class="card flex items-start gap-2 p-4 text-sm leading-6 text-gray-600 dark:bg-gray-800 dark:text-gray-400"><i class="ri-file-list-3-line mt-0.5 shrink-0 text-primary-600 dark:text-primary-400" aria-hidden="true"></i>目前没有使用社区数据的外部研究项目。任何项目上线前都会在这里公示，并单独征得你的同意。</p>
    </section>

    <section aria-labelledby="research-promise-title" class="space-y-3">
      <h2 id="research-promise-title" class="text-base font-semibold">我们的承诺</h2>
      <ul class="grid gap-2 sm:grid-cols-2">
        <li v-for="t in PROMISES" :key="t" class="flex min-h-11 items-center gap-2 rounded-xl bg-primary-50 px-3 text-sm text-primary-800 dark:bg-primary-900/20 dark:text-primary-300"><i class="ri-shield-check-line shrink-0" aria-hidden="true"></i>{{ t }}</li>
      </ul>
    </section>

    <MedicalDisclaimer variant="footer" message="数据授权不影响你使用本平台的任何功能；是否授权由你决定，并可随时撤回。" />
  </div>
</template>
