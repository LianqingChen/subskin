<script setup lang="ts">
import { ref } from 'vue'
import type { ContributionEvent, ContributionLevel, ContributionRule, MyContributions } from '@/types/contribution'
defineProps<{
  summary: MyContributions | null; rules: ContributionRule[]; levels: ContributionLevel[]
  events: ContributionEvent[]; totalEvents: number; eventsError: boolean; loadingEvents: boolean; syncError: boolean
}>()
defineEmits<{ more: []; retry: [] }>()
const showRules = ref(false)
const day = (iso: string) => new Date(iso).toLocaleDateString('zh-CN')
</script>

<template>
  <section id="contribution-growth" class="scroll-mt-24" aria-labelledby="growth-title">
    <div class="mb-4 flex items-center justify-between gap-2"><div><p class="text-xs font-medium text-primary-700 dark:text-primary-300">每份投入，都被记下</p><h2 id="growth-title" class="mt-1 text-lg font-semibold md:text-xl">一起贡献，一起成长</h2></div><button type="button" class="min-h-11 text-xs text-primary-700 dark:text-primary-300" :aria-expanded="showRules" @click="showRules = !showRules">{{ showRules ? '收起规则' : '积分规则' }}<i class="ri-arrow-down-s-line ml-1" aria-hidden="true"></i></button></div>
    <div class="grid gap-4 lg:grid-cols-2">
      <div class="card p-5 dark:bg-gray-800">
        <template v-if="summary">
          <div class="flex items-start justify-between gap-3"><div><p class="text-xs text-gray-500 dark:text-gray-400">同行积分</p><p class="mt-2 text-4xl font-semibold tabular-nums">{{ summary.membership.points.toLocaleString('zh-CN') }}<span class="ml-2 text-xs font-normal text-gray-400">分</span></p></div><span class="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-50 text-3xl text-primary-600 dark:bg-primary-900/40 dark:text-primary-300"><i class="ri-plant-line" aria-hidden="true"></i></span></div>
          <div class="mt-5 flex items-center justify-between gap-2 text-xs"><span>Lv.{{ summary.membership.current.level }} {{ summary.membership.current.name }}</span><span class="text-gray-500 dark:text-gray-400">{{ summary.membership.next ? `距下一等级 ${summary.membership.remaining} 分` : '已达最高等级' }}</span></div>
          <div class="mt-2 h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700" role="progressbar" aria-label="贡献等级进度" :aria-valuenow="summary.membership.progress" aria-valuemin="0" aria-valuemax="100"><div class="h-full rounded-full bg-primary-500 transition-all motion-reduce:transition-none" :style="{ width: `${summary.membership.progress}%` }"></div></div>
          <div class="mt-5 grid grid-cols-4 gap-2"><div v-for="badge in summary.badges" :key="badge.name" class="rounded-xl p-2 text-center" :class="badge.earned ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'bg-gray-50 text-gray-400 dark:bg-gray-900/30 dark:text-gray-500'"><i :class="badge.icon" class="text-2xl" aria-hidden="true"></i><p class="mt-1 text-[10px]">{{ badge.name }}</p><p class="mt-1 text-[10px]">{{ badge.earned ? '已获得' : '待点亮' }}</p></div></div>
          <p v-if="syncError" role="alert" class="mt-3 text-xs text-gray-500 dark:text-gray-400">积分更新未完成，当前显示已入账积分。<button type="button" class="min-h-11 px-2 text-primary-700 dark:text-primary-300" @click="$emit('retry')">重试更新</button></p>
        </template>
        <template v-else><i class="ri-plant-line text-3xl text-primary-600 dark:text-primary-300" aria-hidden="true"></i><h3 class="mt-3 text-base font-medium">让认真积累成为可见的成长</h3><p class="mt-2 text-sm leading-7 text-gray-500 dark:text-gray-400">合格图片、仔细核对、持续记录，逐步点亮你的贡献徽章。</p></template>
        <ol class="mt-5 space-y-2 border-t border-gray-100 pt-4 dark:border-gray-700"><li v-for="level in levels" :key="level.level" class="flex items-center justify-between text-xs" :class="summary?.membership.current.level === level.level ? 'font-medium text-primary-700 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'"><span>Lv.{{ level.level }} · {{ level.name }}</span><span class="tabular-nums">{{ level.threshold.toLocaleString('zh-CN') }} 分</span></li></ol>
      </div>
      <div class="card p-5 dark:bg-gray-800"><h3 class="text-base font-medium">贡献足迹</h3><p class="mt-1 text-xs leading-6 text-gray-500 dark:text-gray-400">通过审核与授权校验后记分；重复提交和刷新不重复计分。</p>
        <ul v-if="events.length" class="mt-4 divide-y divide-gray-100 dark:divide-gray-700"><li v-for="event in events" :key="event.id" class="flex items-center justify-between gap-3 py-3"><div><p class="text-sm">{{ event.title }}</p><time :datetime="event.awarded_at" class="mt-1 block text-xs text-gray-400">{{ day(event.awarded_at) }} · 已计分</time></div><span class="shrink-0 text-sm font-semibold tabular-nums text-primary-700 dark:text-primary-300">+{{ event.points }}</span></li></ul>
        <p v-else class="py-9 text-center text-sm leading-7 text-gray-500 dark:text-gray-400">{{ summary ? '第一份被采纳的贡献，将从这里开始。' : '登录后，在这里查看每一笔贡献积分。' }}</p>
        <p v-if="eventsError" role="alert" class="text-xs text-gray-500 dark:text-gray-400">贡献明细加载失败。</p>
        <button v-if="events.length < totalEvents || eventsError" type="button" class="btn-ghost mt-3 min-h-11 w-full text-xs" :disabled="loadingEvents" @click="$emit('more')">{{ loadingEvents ? '加载中…' : eventsError ? '重新加载明细' : '查看更多贡献' }}</button>
        <p class="mt-4 border-t border-gray-100 pt-4 text-xs leading-6 text-gray-500 dark:border-gray-700 dark:text-gray-400">贡献等级记录你的投入。正常撤回授权保留已获得的荣誉，数据退出当前有效统计；基础服务向每位病友开放。</p>
      </div>
    </div>
    <div v-if="showRules" class="card mt-4 p-5 dark:bg-gray-800"><h3 class="text-base font-medium">积分如何获得</h3><ul class="mt-3 grid gap-3 md:grid-cols-2"><li v-for="rule in rules" :key="rule.kind" class="rounded-xl border border-gray-100 p-4 dark:border-gray-700"><div class="flex items-center justify-between gap-2"><span class="text-sm">{{ rule.title }}</span><span class="text-sm font-semibold text-primary-700 dark:text-primary-300">+{{ rule.points }}</span></div><p class="mt-2 text-xs leading-6 text-gray-500 dark:text-gray-400">{{ rule.note }}</p><span class="mt-2 inline-block rounded-full bg-gray-50 px-2 py-1 text-[10px] text-gray-500 dark:bg-gray-900/40 dark:text-gray-400">{{ rule.enabled ? '已开放' : '规划中 · 暂不计分' }}</span></li></ul><p class="mt-4 text-xs leading-6 text-gray-500 dark:text-gray-400">如实回答「不知道」也是有效信息。授权点击本身不加分，不鼓励无意义高频拍照或额外体检。</p></div>
  </section>
</template>
