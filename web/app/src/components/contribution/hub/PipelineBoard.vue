<script setup lang="ts">
import type { PipelineItem } from '@/api/knowledge'
import { fmtDate } from '@/utils/knowledge-format'
import DraftBadge from './DraftBadge.vue'
defineProps<{ items: PipelineItem[] }>()
// 卡片在所有宽度下都比表格可读：桌面左侧还有两层导航，六列表格会被挤成一字一行
const chipCls = 'block max-w-full rounded-md border border-gray-200 px-1.5 py-0.5 text-xs leading-5 text-gray-700 dark:border-gray-700 dark:text-gray-300'
</script>

<template>
  <ul class="grid gap-3 xl:grid-cols-2">
    <li v-for="p in items" :key="p.key" class="card flex min-w-0 flex-col gap-2 p-4 dark:bg-gray-800">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <h3 class="text-base font-semibold">{{ p.drug_zh }}</h3>
          <p v-if="p.drug_en && p.drug_en !== p.drug_zh" class="break-words text-xs text-gray-500 dark:text-gray-400">{{ p.drug_en }}</p>
        </div>
        <span v-if="p.phase" class="shrink-0 whitespace-nowrap rounded-md bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">{{ p.phase }}</span>
      </div>
      <div class="flex flex-wrap items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
        <span v-if="p.mechanism">{{ p.mechanism }}</span><span v-if="p.mechanism && p.route" aria-hidden="true">·</span><span v-if="p.route">{{ p.route }}</span>
        <DraftBadge :status="p.status" />
      </div>
      <ul v-if="p.regions.length" class="flex flex-col gap-1.5" aria-label="地区状态">
        <li v-for="r in p.regions" :key="r.region" :class="chipCls">
          <span><b class="font-medium">{{ r.region }}</b>：{{ r.status }}<span v-if="fmtDate(r.date)" class="ml-1 tabular-nums text-gray-500 dark:text-gray-400">{{ fmtDate(r.date) }}</span></span>
        </li>
      </ul>
      <p v-if="p.latest_event" class="text-sm leading-6 text-gray-700 dark:text-gray-300">
        <span class="mr-1 text-xs font-medium text-gray-500 dark:text-gray-400">最新</span>{{ p.latest_event }}
      </p>
      <details v-if="p.sources.length" class="mt-auto text-xs">
        <summary class="flex min-h-11 cursor-pointer items-center text-gray-500 dark:text-gray-400">{{ p.sources.length }} 个来源<span v-if="fmtDate(p.checked_at)" class="ml-1 tabular-nums">· 核对于 {{ fmtDate(p.checked_at) }}</span></summary>
        <ul class="space-y-1 pb-1">
          <li v-for="s in p.sources" :key="s.url"><a :href="s.url" target="_blank" rel="noopener noreferrer" class="break-words text-primary-700 hover:underline dark:text-primary-300">{{ s.label }}<i class="ri-external-link-line ml-0.5" aria-hidden="true"></i></a></li>
        </ul>
      </details>
    </li>
  </ul>
</template>
