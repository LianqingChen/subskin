<script setup lang="ts">
/** 发现 · 科普：调养各主体的证据等级、怎么选、注意事项（不写功效，不是治疗建议）。 */
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import CareTopicSection from '@/components/care/CareTopicSection.vue'
import { CARE_TOPICS } from '@/data/care-catalog'

const route = useRoute()
function jump(id: string) { document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
onMounted(() => { const id = route.hash.replace(/^#/, ''); if (id) setTimeout(() => jump(id), 50) })
</script>

<template>
  <div class="page pb-10 pt-3 text-gray-900 dark:text-gray-100 md:pt-5">
    <!-- 桌面端：左侧主题目录 + 右侧正文；手机/平板：顶部横向主题条 -->
    <div class="lg:grid lg:grid-cols-[11rem_minmax(0,1fr)] lg:gap-10 xl:grid-cols-[12rem_minmax(0,48rem)] xl:justify-center">
      <aside class="hidden lg:block">
        <nav aria-label="科普主题" class="sticky top-[4.5rem] mt-12 space-y-0.5">
          <p class="px-3 pb-2 text-xs font-semibold text-gray-400 dark:text-gray-500">主题</p>
          <button v-for="topic in CARE_TOPICS" :key="topic.id" type="button" class="flex min-h-[40px] w-full items-center gap-2 rounded-lg px-3 text-left text-sm text-gray-600 transition-colors hover:bg-white hover:text-gray-900 dark:text-gray-300 dark:hover:bg-gray-800" @click="jump(topic.id)"><i :class="topic.icon" class="text-base text-gray-400" aria-hidden="true"></i>{{ topic.title }}</button>
        </nav>
      </aside>
      <div class="min-w-0 max-w-3xl">
        <router-link to="/community" class="-ml-1 inline-flex min-h-10 items-center gap-1 text-sm text-gray-500 no-underline hover:text-gray-800 dark:text-gray-400"><i class="ri-arrow-left-s-line" aria-hidden="true"></i>返回发现</router-link>
        <header class="mt-1">
          <p class="text-xs font-semibold tracking-widest text-primary-700 dark:text-primary-300">发现 · 科普</p>
          <h1 class="page-title mt-1">把日常过好：吃得稳、晒得对、记得准</h1>
          <p class="page-subtitle leading-6">每个话题先告诉你现在的证据到哪，再告诉你怎么选。这里没有神奇功效，只有踏实的日常。</p>
        </header>
        <p role="note" class="mt-4 flex gap-2 rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
          <i class="ri-information-line mt-0.5 shrink-0" aria-hidden="true"></i>
          <span>本页是日常生活与饮食参考，<strong>不是治疗建议</strong>，食品和用品都不能替代药物和光疗。</span>
        </p>
        <nav aria-label="科普主题" class="sticky top-14 z-20 -mx-4 mt-3 flex gap-2 overflow-x-auto bg-gray-50 px-4 py-2 no-scrollbar dark:bg-gray-950 sm:-mx-6 sm:px-6 lg:hidden">
          <button v-for="topic in CARE_TOPICS" :key="topic.id" type="button" class="min-h-[40px] shrink-0 whitespace-nowrap rounded-full border border-gray-200 bg-white px-4 text-sm font-medium text-gray-600 hover:border-primary-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300" @click="jump(topic.id)">{{ topic.title }}</button>
        </nav>
        <div class="mt-3 space-y-4 lg:mt-5">
          <CareTopicSection v-for="topic in CARE_TOPICS" :key="topic.id" :topic="topic" />
        </div>
      </div>
    </div>
  </div>
</template>
