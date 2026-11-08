<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getKnowledgeCard, type KnowledgeCard, type KnowledgeCardSummary } from '@/api/knowledge'
import { useKnowledgeResource } from '@/composables/useKnowledgeResource'
import { renderMarkdown } from '@/utils/markdown'
import { fmtDate } from '@/utils/knowledge-format'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import EvidenceBadge from './EvidenceBadge.vue'
import DraftBadge from './DraftBadge.vue'

const props = defineProps<{ slug: string; summary: KnowledgeCardSummary | null; all: KnowledgeCardSummary[] }>()
const emit = defineEmits<{ close: []; open: [string] }>()

const slugRef = ref(props.slug)
const { data, loading, error, missing, load } = useKnowledgeResource<KnowledgeCard>((preview) => getKnowledgeCard(slugRef.value, preview), false)
const closeBtn = ref<HTMLButtonElement | null>(null)
const scroller = ref<HTMLElement | null>(null)
const head = computed(() => data.value ?? props.summary)
const html = computed(() => renderMarkdown(data.value?.body_md ?? ''))
const related = computed(() => (data.value?.related ?? []).map(s => props.all.find(c => c.slug === s)).filter((c): c is KnowledgeCardSummary => !!c))

watch(() => props.slug, (s) => { slugRef.value = s; void load(); scroller.value?.scrollTo({ top: 0 }) })
function onKey(e: KeyboardEvent) { if (e.key === 'Escape') emit('close') }
onMounted(() => {
  void load()
  document.addEventListener('keydown', onKey)
  document.body.style.overflow = 'hidden'
  void nextTick(() => closeBtn.value?.focus())
})
onBeforeUnmount(() => { document.removeEventListener('keydown', onKey); document.body.style.overflow = '' })
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50">
      <div class="absolute inset-0 bg-black/40" aria-hidden="true" @click="emit('close')"></div>
      <div role="dialog" aria-modal="true" aria-labelledby="knowledge-sheet-title"
        class="absolute inset-x-0 bottom-0 flex max-h-[90vh] max-h-[90dvh] flex-col rounded-t-2xl bg-white text-gray-900 shadow-xl dark:bg-gray-900 dark:text-gray-100 sm:bottom-6 sm:mx-auto sm:max-w-2xl sm:rounded-2xl">
        <header class="flex items-start gap-2 border-b border-gray-100 px-4 py-3 dark:border-gray-800">
          <div class="min-w-0 flex-1">
            <div class="mb-1 flex flex-wrap items-center gap-1.5">
              <EvidenceBadge :level="head?.evidence_level" />
              <DraftBadge :status="head?.status" />
              <span v-if="head?.ai_assisted" class="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400"><i class="ri-sparkling-2-line" aria-hidden="true"></i>AI 辅助整理</span>
            </div>
            <h2 id="knowledge-sheet-title" class="text-lg font-semibold">{{ head?.title }}</h2>
            <p v-if="head" class="mt-1 text-xs text-gray-500 tabular-nums dark:text-gray-400">{{ head.source_count }} 个来源<template v-if="fmtDate(head.reviewed_at)"> · 审核于 {{ fmtDate(head.reviewed_at) }}</template><template v-if="fmtDate(data?.next_review_at)"> · 下次复核 {{ fmtDate(data?.next_review_at) }}</template></p>
          </div>
          <button ref="closeBtn" type="button" class="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800" aria-label="关闭" @click="emit('close')"><i class="ri-close-line text-xl" aria-hidden="true"></i></button>
        </header>

        <div ref="scroller" class="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <div v-if="loading" role="status" class="space-y-3"><div v-for="n in 4" :key="n" class="h-5 animate-pulse rounded bg-gray-100 dark:bg-gray-800"></div><span class="sr-only">正在加载</span></div>
          <div v-else-if="error || missing" role="alert" class="py-8 text-center">
            <p class="text-sm text-gray-500 dark:text-gray-400">{{ missing ? '这篇内容暂时无法查看' : '加载失败，请检查网络后重试' }}</p>
            <button v-if="!missing" type="button" class="btn-ghost mt-2 min-h-11 px-4" @click="load">重新加载</button>
          </div>
          <template v-else-if="data">
            <div class="prose prose-sm max-w-none text-gray-700 dark:text-gray-300 dark:prose-invert prose-h2:mb-2 prose-h2:mt-5 prose-h2:text-base prose-h2:first:mt-0" v-html="html"></div>

            <section v-if="data.sources.length" class="mt-6" aria-labelledby="knowledge-sources">
              <h3 id="knowledge-sources" class="mb-2 text-sm font-semibold">参考来源</h3>
              <ul class="space-y-2">
                <li v-for="s in data.sources" :key="`${s.type}-${s.ref}`" class="flex items-start gap-2 rounded-xl bg-gray-50 p-3 text-sm dark:bg-gray-800">
                  <EvidenceBadge :level="s.evidence_level" />
                  <div class="min-w-0 flex-1">
                    <a v-if="s.url" :href="s.url" target="_blank" rel="noopener noreferrer" class="break-words text-primary-700 hover:underline dark:text-primary-300">{{ s.title || s.ref }}<i class="ri-external-link-line ml-1" aria-hidden="true"></i></a>
                    <span v-else class="break-words">{{ s.title || s.ref }}</span>
                    <p class="mt-0.5 text-xs text-gray-500 tabular-nums dark:text-gray-400">{{ s.type.toUpperCase() }} {{ s.ref }}<template v-if="s.year"> · {{ s.year }}</template></p>
                  </div>
                </li>
              </ul>
            </section>

            <section v-if="related.length" class="mt-6" aria-labelledby="knowledge-related">
              <h3 id="knowledge-related" class="mb-2 text-sm font-semibold">相关主题</h3>
              <div class="flex flex-wrap gap-2"><button v-for="r in related" :key="r.slug" type="button" class="min-h-11 rounded-full border border-gray-200 px-3 text-sm text-gray-700 hover:border-primary-400 dark:border-gray-700 dark:text-gray-300" @click="emit('open', r.slug)">{{ r.title }}</button></div>
            </section>

            <router-link to="/" class="mt-6 flex min-h-11 items-center justify-between rounded-xl bg-primary-50 px-4 text-sm font-medium text-primary-700 dark:bg-primary-900/30 dark:text-primary-300" @click="emit('close')">还有疑问？问问小白<i class="ri-arrow-right-line" aria-hidden="true"></i></router-link>
            <MedicalDisclaimer variant="footer" :message="data.disclaimer || '本文不构成医疗建议。内容可能随研究进展更新，具体诊疗请遵医嘱。'" />
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>
