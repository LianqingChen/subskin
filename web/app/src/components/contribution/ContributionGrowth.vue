<script setup lang="ts">
import type { ContributionEvent, ContributionLevel, ContributionRule, MyContributions } from '@/types/contribution'
defineProps<{ summary: MyContributions | null; rules: ContributionRule[]; levels: ContributionLevel[]; events: ContributionEvent[]; totalEvents: number; eventsError: boolean; loadingEvents: boolean; syncError: boolean }>()
defineEmits<{ more: []; retry: [] }>()
const day = (iso: string) => new Date(iso).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })
</script>

<template>
  <section id="contribution-growth" class="card scroll-mt-24 p-5 dark:bg-gray-800 sm:p-6" aria-labelledby="growth-title">
    <h2 id="growth-title" class="text-lg font-semibold">每一份投入，都被认真记下</h2>
    <div v-if="summary" class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4"><div v-for="badge in summary.badges" :key="badge.name" class="flex min-w-0 items-center gap-3 rounded-xl p-3" :class="badge.earned ? 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300' : 'bg-gray-50 text-gray-500 dark:bg-gray-900 dark:text-gray-400'"><i :class="badge.icon" class="text-2xl" aria-hidden="true"></i><div class="min-w-0"><p class="text-xs font-medium">{{ badge.name }}</p><p class="mt-1 text-[11px]">{{ badge.earned ? '已获得' : '待点亮' }}</p></div></div></div>
    <p v-if="syncError" role="alert" class="mt-3 text-xs text-gray-500 dark:text-gray-400">积分更新未完成，当前显示已入账积分。<button type="button" class="min-h-11 px-2 text-primary-700 dark:text-primary-300" @click="$emit('retry')">重试更新</button></p>
    <div class="mt-4 grid gap-4 md:grid-cols-2">
      <details class="min-w-0 rounded-xl border border-gray-100 px-4 dark:border-gray-700"><summary class="flex min-h-12 cursor-pointer items-center justify-between gap-2 text-sm">贡献足迹<span class="text-xs text-gray-500 dark:text-gray-400">{{ summary && !eventsError ? `${totalEvents} 笔已计分` : eventsError ? '暂未加载' : '登录后查看' }}</span></summary>
        <ul v-if="events.length" class="divide-y divide-gray-100 pb-3 dark:divide-gray-700"><li v-for="event in events" :key="event.id" class="flex items-center justify-between gap-3 py-3"><div><p class="text-sm">{{ event.title }}</p><time :datetime="event.awarded_at" class="mt-1 block text-xs text-gray-500 dark:text-gray-400">{{ day(event.awarded_at) }} · 积分入账</time></div><span class="shrink-0 text-sm font-semibold text-primary-700 dark:text-primary-300">+{{ event.points }}</span></li></ul><p v-else class="pb-4 text-xs leading-6 text-gray-500 dark:text-gray-400">{{ summary ? '第一份被采纳的贡献，将从这里开始。' : '登录后查看每一笔贡献积分。' }}</p>
        <p v-if="eventsError" role="alert" class="text-xs text-gray-500 dark:text-gray-400">贡献明细加载失败。</p><button v-if="events.length < totalEvents || eventsError" type="button" class="btn-ghost mb-3 min-h-11 w-full text-xs" :disabled="loadingEvents" @click="$emit('more')">{{ loadingEvents ? '加载中…' : eventsError ? '重新加载明细' : '查看更多贡献' }}</button>
      </details>
      <details class="min-w-0 rounded-xl border border-gray-100 px-4 dark:border-gray-700"><summary class="min-h-12 cursor-pointer py-4 text-sm">积分规则与等级</summary><ul class="space-y-3 pb-4"><li v-for="rule in rules" :key="rule.kind"><div class="flex justify-between gap-2 text-xs"><span>{{ rule.title }}</span><span class="font-semibold text-primary-700 dark:text-primary-300">+{{ rule.points }}</span></div><p class="mt-1 text-[11px] leading-6 text-gray-500 dark:text-gray-400">{{ rule.note }} · {{ rule.enabled ? '已开放' : '规划中，暂不计分' }}</p></li></ul><ol class="space-y-2 border-t border-gray-100 py-4 dark:border-gray-700"><li v-for="level in levels" :key="level.level" class="flex justify-between gap-2 text-xs text-gray-500 dark:text-gray-400"><span>Lv.{{ level.level }} {{ level.name }}</span><span>{{ level.threshold.toLocaleString('zh-CN') }} 分</span></li></ol></details>
    </div>
    <p class="mt-4 text-xs leading-6 text-gray-500 dark:text-gray-400">正常撤回授权保留历史贡献荣誉，数据退出当前有效统计。重复提交与刷新不重复计分，基础服务向每位病友开放。</p>
  </section>
</template>
