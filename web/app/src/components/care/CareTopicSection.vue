<script setup lang="ts">
import { EVIDENCE, type CareTopic } from '@/data/care-catalog'
defineProps<{ topic: CareTopic }>()
</script>

<template>
  <section :id="topic.id" :aria-labelledby="`care-title-${topic.id}`" class="scroll-mt-28 rounded-2xl border border-gray-200/80 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 md:p-6">
    <header class="flex flex-wrap items-center gap-x-3 gap-y-2">
      <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-xl text-primary-700 dark:bg-gray-700 dark:text-primary-200"><i :class="topic.icon" aria-hidden="true"></i></span>
      <h2 :id="`care-title-${topic.id}`" class="min-w-0 flex-1 text-lg font-semibold">{{ topic.title }}</h2>
      <span class="inline-flex min-h-[28px] items-center gap-1 rounded-full px-3 text-xs font-medium" :class="EVIDENCE[topic.evidence].badge" :title="EVIDENCE[topic.evidence].hint">
        <i :class="EVIDENCE[topic.evidence].icon" aria-hidden="true"></i>{{ EVIDENCE[topic.evidence].label }}
      </span>
    </header>
    <p class="mt-3 text-sm leading-6 text-gray-700 dark:text-gray-200">{{ topic.summary }}</p>

    <div class="mt-4 grid gap-3 md:grid-cols-2">
      <div>
        <h3 class="text-sm font-semibold">怎么选</h3>
        <ul class="mt-2 space-y-1.5 text-sm leading-6 text-gray-600 dark:text-gray-300">
          <li v-for="line in topic.pickGuide" :key="line" class="flex gap-2"><i class="ri-checkbox-circle-line mt-1 shrink-0 text-primary-600 dark:text-primary-300" aria-hidden="true"></i><span>{{ line }}</span></li>
        </ul>
      </div>
      <div class="rounded-xl bg-amber-50 p-3 dark:bg-amber-900/20">
        <h3 class="flex items-center gap-1 text-sm font-semibold text-amber-900 dark:text-amber-200"><i class="ri-error-warning-line" aria-hidden="true"></i>请注意</h3>
        <ul class="mt-2 space-y-1.5 text-sm leading-6 text-amber-900 dark:text-amber-100">
          <li v-for="line in topic.cautions" :key="line" class="flex gap-2"><span aria-hidden="true">·</span><span>{{ line }}</span></li>
        </ul>
      </div>
    </div>

    <router-link :to="`/care#${topic.id}`" class="mt-4 inline-flex min-h-[44px] items-center gap-1 text-sm font-medium text-primary-700 no-underline dark:text-primary-300" :data-track-id="`science_to_mall_${topic.id}`">去调养看「{{ topic.title }}」好物（{{ topic.items.length }}）<i class="ri-arrow-right-s-line" aria-hidden="true"></i></router-link>
  </section>
</template>
