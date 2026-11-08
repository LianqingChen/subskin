<script setup lang="ts">
export type HubTab = 'knowledge' | 'frontier' | 'build' | 'research'
defineProps<{ modelValue: HubTab; loggedIn: boolean }>()
defineEmits<{ 'update:modelValue': [HubTab] }>()
const TABS: { key: HubTab; label: string; icon: string }[] = [
  { key: 'knowledge', label: '知识', icon: 'ri-book-open-line' },
  { key: 'frontier', label: '前沿', icon: 'ri-flask-line' },
  { key: 'build', label: '共建', icon: 'ri-team-line' },
  { key: 'research', label: '科研', icon: 'ri-microscope-line' },
]
</script>

<template>
  <!-- 手机：分段切换 -->
  <div class="grid grid-cols-4 rounded-xl bg-gray-100 p-1 dark:bg-gray-800 md:hidden" role="tablist" aria-label="同行栏目">
    <button v-for="t in TABS" :id="`hub-tab-${t.key}`" :key="t.key" type="button" role="tab" :aria-selected="modelValue === t.key" aria-controls="hub-panel"
      class="min-h-11 rounded-lg text-sm" :class="modelValue === t.key ? 'bg-white font-medium text-primary-700 shadow-sm dark:bg-gray-700 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'"
      @click="$emit('update:modelValue', t.key)">{{ t.label }}</button>
  </div>
  <!-- 桌面：左侧页内导航 -->
  <nav class="hidden w-52 shrink-0 md:block" aria-label="同行栏目">
    <div class="sticky top-4 space-y-1" role="tablist" aria-orientation="vertical">
      <button v-for="t in TABS" :id="`hub-tab-d-${t.key}`" :key="t.key" type="button" role="tab" :aria-selected="modelValue === t.key" aria-controls="hub-panel"
        class="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-left text-sm"
        :class="modelValue === t.key ? 'bg-primary-50 font-medium text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800'"
        @click="$emit('update:modelValue', t.key)"><i :class="t.icon" aria-hidden="true"></i>{{ t.label }}</button>
      <router-link v-if="loggedIn" to="/profile/data" class="mt-3 flex min-h-11 items-center justify-between rounded-lg border-t border-gray-100 px-3 pt-3 text-sm text-gray-600 hover:text-primary-700 dark:border-gray-800 dark:text-gray-400 dark:hover:text-primary-300">授权管理<i class="ri-arrow-right-line" aria-hidden="true"></i></router-link>
    </div>
  </nav>
</template>
