<script setup lang="ts">
import { computed, ref } from 'vue'
import { getKnowledgeCards, type KnowledgeCardList } from '@/api/knowledge'
import { useKnowledgeResource } from '@/composables/useKnowledgeResource'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import HubState from './HubState.vue'
import KnowledgeCardItem from './KnowledgeCardItem.vue'
import KnowledgeCardSheet from './KnowledgeCardSheet.vue'

// 一次取全量再前端按主题筛选，切换主题无需等待
const { data, loading, error, load } = useKnowledgeResource<KnowledgeCardList>((p) => getKnowledgeCards('', p))
const topic = ref('')
const open = ref('')
const items = computed(() => data.value?.items ?? [])
const topics = computed(() => (data.value?.topics ?? []).filter(t => items.value.some(c => c.topic === t.key)))
const shown = computed(() => topic.value ? items.value.filter(c => c.topic === topic.value) : items.value)
const current = computed(() => items.value.find(c => c.slug === open.value) ?? null)
const chip = (active: boolean) => active ? 'border-primary-600 bg-primary-600 text-white dark:border-primary-500 dark:bg-primary-600' : 'border-gray-200 bg-white text-gray-600 hover:border-primary-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300'
</script>

<template>
  <div class="space-y-4">
    <HubState :loading="loading" :error="error" :empty="!items.length" @retry="load">
      <div v-if="topics.length" class="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:flex-wrap md:px-0" role="group" aria-label="按主题筛选">
        <button type="button" class="min-h-11 shrink-0 rounded-full border px-4 text-sm" :class="chip(topic === '')" :aria-pressed="topic === ''" @click="topic = ''">全部</button>
        <button v-for="t in topics" :key="t.key" type="button" class="min-h-11 shrink-0 rounded-full border px-4 text-sm" :class="chip(topic === t.key)" :aria-pressed="topic === t.key" @click="topic = t.key">{{ t.label }}</button>
      </div>
      <ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <li v-for="c in shown" :key="c.slug" class="flex min-w-0"><KnowledgeCardItem :card="c" class="flex-1" @open="open = $event" /></li>
      </ul>
    </HubState>
    <p class="text-xs leading-5 text-gray-500 dark:text-gray-400">证据等级：A 指南/综述 · B 临床试验 · C 观察研究 · D 专家意见 · E 病友经验。等级越靠前，证据越充分。</p>
    <MedicalDisclaimer variant="footer" message="知识卡片仅供科普，不构成医疗建议；具体诊疗请遵医嘱。" />
    <KnowledgeCardSheet v-if="open" :slug="open" :summary="current" :all="items" @close="open = ''" @open="open = $event" />
  </div>
</template>
