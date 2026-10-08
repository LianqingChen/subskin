<script setup lang="ts">
import { computed, ref } from 'vue'
import type { HospitalMark, HospitalView } from '@/types/hospital'

/**
 * 首屏主 CTA：「我刚看完病，写两句」。
 * 已选医院 → 直接进入 30 秒快评；未选医院 → 就地选（我的标记 / 搜索 / 去列表）。
 */
const props = defineProps<{
  selected: HospitalView | null
  hospitals: HospitalView[]
  marks: Record<string, HospitalMark>
  isLoggedIn: boolean
  open: boolean
}>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  write: []
  pick: [hospital: HospitalView]
  login: []
  browse: []
}>()

const query = ref('')
const open = computed({ get: () => props.open, set: value => emit('update:open', value) })
const marked = computed(() => props.hospitals.filter(h => props.marks[h.key]).slice(0, 6))
const results = computed(() => {
  const word = query.value.trim().toLowerCase()
  if (!word) return []
  return props.hospitals
    .filter(h => [h.name, h.city, h.district, h.address].join(' ').toLowerCase().includes(word))
    .slice(0, 5)
})
function start() {
  if (props.selected) { emit('write'); return }
  open.value = true
}
function choose(hospital: HospitalView) {
  emit('pick', hospital)
  open.value = false
  query.value = ''
}
</script>

<template>
  <section aria-labelledby="quick-review-title" class="rounded-2xl border border-primary-200 bg-white p-4 dark:border-primary-800 dark:bg-gray-900 md:p-5">
    <div class="flex flex-wrap items-center gap-4">
      <div class="min-w-0 flex-1">
        <h2 id="quick-review-title" class="text-lg font-semibold"><i class="ri-edit-2-line mr-1 text-primary-600 dark:text-primary-300" />分享这次就诊经历</h2>
        <p class="mt-1 text-sm leading-6 text-gray-600 dark:text-gray-300">
          选医院，写下至少 20 字的亲身经历。挂号、候诊、沟通、费用、复诊等体验可以按需点选补充。
        </p>
        <p v-if="selected" class="mt-2 text-sm text-primary-800 dark:text-primary-200">
          当前医院：<strong>{{ selected.name }}</strong>（{{ selected.city }}）
          <button class="ml-2 min-h-11 rounded-lg px-3 underline" :aria-expanded="open" aria-controls="quick-hospital-picker" @click="open = !open">换一家</button>
        </p>
      </div>
      <button class="min-h-11 w-full shrink-0 md:w-auto rounded-xl bg-primary-600 px-5 text-sm font-medium text-white" @click="start">
        {{ selected ? '开始写评价' : '选一家医院开始写' }}
      </button>
    </div>

    <div v-if="open" id="quick-hospital-picker" class="mt-4 space-y-3 border-t border-primary-100 pt-4 dark:border-primary-900">
      <div class="flex items-center justify-between"><h3 class="text-sm font-medium">选择本次就诊医院</h3><button class="min-h-11 px-3 text-sm text-gray-500 dark:text-gray-400" @click="open = false">收起</button></div>
      <div v-if="marked.length">
        <p class="mb-2 text-sm text-gray-500 dark:text-gray-400">我标记过的医院</p>
        <div class="flex flex-wrap gap-2">
          <button v-for="hospital in marked" :key="hospital.key" class="min-h-11 rounded-xl border border-gray-200 bg-white px-3 text-sm dark:border-gray-700 dark:bg-gray-800" @click="choose(hospital)">
            <i :class="marks[hospital.key] === 'visited' ? 'ri-map-pin-user-line' : 'ri-bookmark-line'" class="mr-1" />{{ hospital.name }}
          </button>
        </div>
      </div>
      <label class="block text-sm text-gray-500 dark:text-gray-400">或直接搜索医院
        <span class="relative mt-2 block">
          <i class="ri-search-line absolute left-3 top-3.5 text-gray-400" />
          <input v-model="query" type="search" maxlength="100" class="min-h-11 w-full min-w-0 rounded-xl border border-gray-200 bg-white pl-9 pr-3 text-sm dark:border-gray-700 dark:bg-gray-800" placeholder="医院名称、城市或地址">
        </span>
      </label>
      <div v-if="results.length" class="space-y-1">
        <button v-for="hospital in results" :key="hospital.key" class="flex min-h-11 w-full items-center justify-between rounded-xl px-3 text-left text-sm hover:bg-white dark:hover:bg-gray-800" @click="choose(hospital)">
          <span>{{ hospital.name }}<span class="ml-2 text-gray-400">{{ hospital.city }}</span></span>
          <i class="ri-arrow-right-s-line" />
        </button>
      </div>
      <p v-else-if="query" class="text-sm text-gray-400">没有匹配的医院，可以到下方列表里创建一家。</p>
      <button class="min-h-11 text-sm text-primary-700 underline dark:text-primary-300" @click="emit('browse')">去下面的列表按省市找医院</button>
    </div>
  </section>
</template>
