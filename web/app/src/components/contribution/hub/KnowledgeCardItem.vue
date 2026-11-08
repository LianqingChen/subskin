<script setup lang="ts">
import type { KnowledgeCardSummary } from '@/api/knowledge'
import { fmtDate } from '@/utils/knowledge-format'
import EvidenceBadge from './EvidenceBadge.vue'
import DraftBadge from './DraftBadge.vue'
defineProps<{ card: KnowledgeCardSummary }>()
defineEmits<{ open: [string] }>()
</script>

<template>
  <button type="button" class="card card-hover flex min-h-11 w-full min-w-0 flex-col gap-2 p-4 text-left dark:bg-gray-800" @click="$emit('open', card.slug)">
    <span class="flex flex-wrap items-center gap-1.5">
      <EvidenceBadge :level="card.evidence_level" />
      <DraftBadge :status="card.status" />
      <span v-if="card.ai_assisted" class="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400"><i class="ri-sparkling-2-line" aria-hidden="true"></i>AI 辅助整理</span>
    </span>
    <span class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ card.title }}</span>
    <span class="line-clamp-3 text-sm leading-6 text-gray-600 dark:text-gray-400">{{ card.summary }}</span>
    <span class="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500 tabular-nums dark:text-gray-400">
      <span><i class="ri-links-line" aria-hidden="true"></i> {{ card.source_count }} 个来源</span>
      <span v-if="fmtDate(card.reviewed_at)">审核于 {{ fmtDate(card.reviewed_at) }}</span>
    </span>
  </button>
</template>
