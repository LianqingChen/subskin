<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { contributionMetricLabel } from '@/utils/contribution-charts'
import ContributionGrowthRing from './ContributionGrowthRing.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { MyContributions } from '@/types/contribution'
const props = defineProps<{ summary: MyContributions | null; loading: boolean; error: boolean }>()
defineEmits<{ retry: [] }>()
const auth = useAuthStore()
const tiles = computed(() => props.summary ? [
  { label: '有效图片', metric: props.summary.images, unit: '张', to: null },
  { label: '范围核对', metric: props.summary.checked, unit: '张', to: null },
  { label: '体检资料', metric: props.summary.reports, unit: '份', to: '/assessment/exam' },
] : [])
// 医生确认/预计帮助在有数据后才出现，避免恒为「待统计」的占位
const extras = computed(() => props.summary ? [
  { label: '医生确认', metric: props.summary.doctor, unit: '条' },
  { label: '预计帮助', metric: props.summary.impact, unit: '人' },
].filter(x => x.metric.status === 'available') : [])
</script>

<template>
  <section id="my-contribution" class="card min-w-0 p-4 dark:bg-gray-800 sm:p-5" aria-labelledby="personal-title">
    <div class="mb-3 flex items-center justify-between gap-2">
      <h2 id="personal-title" class="text-base font-semibold">我的贡献</h2>
      <span v-if="summary" class="rounded-full bg-primary-50 px-2.5 py-0.5 text-xs text-primary-700 dark:bg-primary-900 dark:text-primary-300">Lv.{{ summary.membership.current.level }} {{ summary.membership.current.name }}</span>
    </div>
    <EmptyState v-if="!auth.isLoggedIn" icon="ri-hand-heart-line" title="登录查看我的贡献" action-label="登录" @action="auth.showLoginModal = true" />
    <div v-else-if="loading" role="status" aria-label="加载个人贡献" class="h-48 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-700"><span class="sr-only">加载中</span></div>
    <div v-else-if="error" role="alert" class="py-6 text-center"><p class="text-sm text-gray-500 dark:text-gray-400">个人贡献加载失败</p><button type="button" class="btn-ghost mt-2 min-h-11 px-4" @click="$emit('retry')">重新加载</button></div>
    <template v-else-if="summary">
      <div class="flex items-center gap-4">
        <ContributionGrowthRing :membership="summary.membership" />
        <div class="min-w-0 space-y-1 text-sm">
          <p class="font-medium text-primary-700 dark:text-primary-300">{{ summary.membership.next ? `再积累 ${summary.membership.remaining} 分升至 Lv.${summary.membership.next.level}` : '已达最高等级' }}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400">{{ summary.active_consent ? '图片贡献授权已开启' : '图片贡献授权未开启' }}</p>
        </div>
      </div>
      <div class="mt-4 grid grid-cols-3 gap-2">
        <component :is="tile.to ? 'router-link' : 'div'" v-for="tile in tiles" :key="tile.label" :to="tile.to ?? undefined" class="min-w-0 rounded-xl bg-gray-50 px-3 py-2.5 dark:bg-gray-900" :class="tile.to && 'transition-colors hover:bg-primary-50 dark:hover:bg-primary-900'">
          <span class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">{{ tile.label }}<i v-if="tile.to" class="ri-arrow-right-s-line" aria-hidden="true"></i></span>
          <span class="mt-1 block truncate text-xl font-semibold tabular-nums">{{ contributionMetricLabel(tile.metric) }}<span v-if="tile.metric.status === 'available' && tile.metric.value !== null" class="ml-0.5 text-[11px] font-normal text-gray-500 dark:text-gray-400">{{ tile.unit }}</span></span>
        </component>
      </div>
      <p class="mt-3 text-xs tabular-nums text-gray-500 dark:text-gray-400">已上传 {{ summary.uploaded }} · 已核对 {{ summary.personally_checked }} · 待复核 {{ summary.pending }}</p>
      <details class="mt-1 text-xs text-gray-500 dark:text-gray-400">
        <summary class="min-h-10 cursor-pointer py-2.5">统计口径</summary>
        <ul class="space-y-1.5 pb-2 leading-5">
          <li v-for="tile in tiles" :key="tile.label">{{ tile.label }}：{{ tile.metric.note }}</li>
          <li v-for="extra in extras" :key="extra.label">{{ extra.label }}：{{ extra.metric.value }}{{ extra.unit }}，{{ extra.metric.note }}</li>
        </ul>
      </details>
      <div class="mt-2 flex gap-2">
        <router-link to="/assessment" class="btn-primary inline-flex min-h-11 flex-1 items-center justify-center gap-1.5 px-4 text-sm"><i class="ri-camera-line" aria-hidden="true"></i>继续记录</router-link>
        <router-link to="/profile/data" class="btn-ghost inline-flex min-h-11 items-center justify-center px-4 text-sm">管理授权</router-link>
      </div>
    </template>
  </section>
</template>
