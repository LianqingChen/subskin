<script setup lang="ts">
import { computed } from 'vue'
import type { HospitalStats } from '@/types/hospital'

/**
 * 「病友常提到」中性标签云：由病友评价里的标签聚合而成。
 * 明确免责：只反映病友个人经历，不代表医院整体水平，也不构成医疗建议；不做排名。
 */
const props = defineProps<{ stats: HospitalStats; active: string; limit?: number }>()
const emit = defineEmits<{ select: [tag: string] }>()
const tags = computed(() => (props.stats.topTags ?? []).slice(0, props.limit ?? 8))
</script>

<template>
  <section v-if="tags.length" aria-labelledby="hospital-tag-cloud-title" class="rounded-2xl bg-gray-50 p-4 dark:bg-gray-800">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h3 id="hospital-tag-cloud-title" class="text-sm font-medium">病友常提到</h3>
      <button v-if="active" class="min-h-11 text-xs text-primary-700 underline dark:text-primary-300" @click="emit('select', '')">清除筛选：{{ active }}</button>
    </div>
    <div class="mt-2 flex flex-wrap gap-2">
      <button
        v-for="item in tags" :key="item.tag" :aria-pressed="active === item.tag"
        class="min-h-11 rounded-xl border px-3 text-xs"
        :class="active === item.tag
          ? 'border-primary-500 bg-primary-50 font-medium text-primary-700 dark:bg-primary-900 dark:text-primary-300'
          : 'border-gray-200 bg-white text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200'"
        @click="emit('select', active === item.tag ? '' : item.tag)"
      >{{ item.tag }} <span class="opacity-60">{{ item.count }}</span></button>
    </div>
    <p class="mt-2 text-[11px] leading-5 text-gray-400">
      标签来自病友自己对这次就诊的描述，仅代表个人经历，不代表医院整体水平，也不构成医疗建议；本页不做医院排名。
    </p>
  </section>
</template>
