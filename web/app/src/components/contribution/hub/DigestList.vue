<script setup lang="ts">
import type { DigestItem } from '@/api/knowledge'
import { fmtDate } from '@/utils/knowledge-format'
import DraftBadge from './DraftBadge.vue'
defineProps<{ items: DigestItem[] }>()
</script>

<template>
  <ul class="space-y-3">
    <li v-for="d in items" :key="d.key" class="card space-y-2 p-4 dark:bg-gray-800">
      <div class="flex flex-wrap items-center gap-1.5">
        <span v-if="d.is_preprint" class="inline-flex items-center gap-1 rounded-md border border-dashed border-gray-400 px-1.5 py-0.5 text-xs text-gray-600 dark:border-gray-500 dark:text-gray-300">预印本 · 未经同行评议</span>
        <DraftBadge :status="d.status" />
        <span class="text-xs text-gray-500 tabular-nums dark:text-gray-400">{{ [d.study_type, d.sample_size ? `样本量 ${d.sample_size}` : '', d.journal, fmtDate(d.published_on)].filter(Boolean).join(' · ') }}</span>
      </div>
      <h3 class="text-base font-semibold">{{ d.title_zh || d.title_en }}</h3>
      <p v-if="d.one_liner" class="text-sm leading-6 text-gray-800 dark:text-gray-200">{{ d.one_liner }}</p>
      <p v-if="d.why_it_matters" class="text-sm leading-6 text-gray-600 dark:text-gray-400"><b class="font-medium text-gray-700 dark:text-gray-300">为什么值得关注：</b>{{ d.why_it_matters }}</p>
      <details v-if="d.limitations" class="text-sm text-gray-600 dark:text-gray-400"><summary class="min-h-11 cursor-pointer py-2.5">研究局限</summary><p class="leading-6">{{ d.limitations }}</p></details>
      <a v-if="d.url" :href="d.url" target="_blank" rel="noopener noreferrer" class="inline-flex min-h-11 items-center text-sm text-primary-700 hover:underline dark:text-primary-300">查看原文<i class="ri-external-link-line ml-1" aria-hidden="true"></i></a>
    </li>
  </ul>
</template>
