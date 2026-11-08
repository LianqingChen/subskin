<script setup lang="ts">
import { computed } from 'vue'
import { getKnowledgeDigests, getKnowledgePipeline, type KnowledgeDigests, type KnowledgePipeline } from '@/api/knowledge'
import { useKnowledgeResource } from '@/composables/useKnowledgeResource'
import { fmtDate } from '@/utils/knowledge-format'
import MedicalDisclaimer from '@/components/common/MedicalDisclaimer.vue'
import HubState from './HubState.vue'
import PipelineBoard from './PipelineBoard.vue'
import DigestList from './DigestList.vue'

const pipeline = useKnowledgeResource<KnowledgePipeline>((p) => getKnowledgePipeline(p))
const digests = useKnowledgeResource<KnowledgeDigests>((p) => getKnowledgeDigests(10, p))
const pipelineItems = computed(() => pipeline.data.value?.items ?? [])
const digestItems = computed(() => digests.data.value?.items ?? [])
const updated = computed(() => fmtDate(pipeline.data.value?.updated_at))
</script>

<template>
  <div class="space-y-6">
    <section aria-labelledby="pipeline-title" class="space-y-3">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="pipeline-title" class="text-base font-semibold">药物研发管线</h2>
        <span v-if="updated" class="text-xs tabular-nums text-gray-500 dark:text-gray-400">更新于 {{ updated }}</span>
      </div>
      <p class="flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300"><i class="ri-error-warning-line mt-0.5 shrink-0" aria-hidden="true"></i>研发信息仅供了解进展，不代表推荐使用；用药请遵医嘱</p>
      <HubState :loading="pipeline.loading.value" :error="pipeline.error.value" :empty="!pipelineItems.length" @retry="pipeline.load">
        <PipelineBoard :items="pipelineItems" />
      </HubState>
    </section>

    <section aria-labelledby="digest-title" class="space-y-3">
      <h2 id="digest-title" class="text-base font-semibold">论文速递</h2>
      <HubState :loading="digests.loading.value" :error="digests.error.value" :empty="!digestItems.length" :skeleton="2" @retry="digests.load">
        <DigestList :items="digestItems" />
      </HubState>
    </section>

    <MedicalDisclaimer variant="footer" message="本栏目仅整理公开的研发与论文信息，不构成医疗建议，也不是药品广告；用药请遵医嘱。" />
  </div>
</template>
