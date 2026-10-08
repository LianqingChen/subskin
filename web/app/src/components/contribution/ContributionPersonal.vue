<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { contributionMetricLabel } from '@/utils/contribution-charts'
import ContributionGrowthRing from './ContributionGrowthRing.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { MyContributions } from '@/types/contribution'
defineProps<{ summary: MyContributions | null; loading: boolean; error: boolean }>()
defineEmits<{ retry: [] }>()
const auth = useAuthStore()
</script>

<template>
  <section id="my-contribution" class="card min-w-0 scroll-mt-24 p-5 dark:bg-gray-800 sm:p-6" aria-labelledby="personal-title">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 id="personal-title" class="text-lg font-semibold">我的贡献</h2><span v-if="summary" class="rounded-full bg-primary-50 px-3 py-1 text-xs text-primary-700 dark:bg-primary-900 dark:text-primary-300">Lv.{{ summary.membership.current.level }} {{ summary.membership.current.name }}</span></div>
    <EmptyState v-if="!auth.isLoggedIn" icon="ri-hand-heart-line" title="每一份认真记录，都有自己的位置" description="登录后查看你的贡献、成长，以及你在共同成果中的一份。" action-label="登录查看" @action="auth.showLoginModal = true" />
    <div v-else-if="loading" role="status" aria-label="加载个人贡献" class="h-56 animate-pulse rounded-2xl bg-gray-100 dark:bg-gray-700"><span class="sr-only">加载中</span></div>
    <div v-else-if="error" role="alert" class="py-8 text-center"><p class="text-sm text-gray-500 dark:text-gray-400">个人贡献暂时没有加载成功</p><button type="button" class="btn-ghost mt-3 min-h-11 px-4" @click="$emit('retry')">重新加载</button></div>
    <template v-else-if="summary">
      <div class="flex items-center gap-4"><ContributionGrowthRing :membership="summary.membership" /><div class="min-w-0 text-sm leading-7"><p class="font-medium text-primary-700 dark:text-primary-300">{{ summary.membership.next ? `再积累 ${summary.membership.remaining} 分，升至 Lv.${summary.membership.next.level}` : '已达最高贡献等级' }}</p><p class="break-words text-gray-600 dark:text-gray-300">{{ auth.user?.username || '同行伙伴' }}，谢谢你的认真投入。</p><p class="text-xs text-gray-500 dark:text-gray-400">{{ summary.active_consent ? '图片贡献授权已开启' : '记录是否用于共建，由你决定' }}</p></div></div>
      <div class="mt-5 grid grid-cols-2 gap-2 min-[360px]:grid-cols-3">
        <details class="rounded-xl bg-gray-50 p-3 dark:bg-gray-900"><summary class="min-h-11 cursor-pointer list-none"><span class="block text-xs text-gray-500 dark:text-gray-400">有效图片</span><span class="mt-2 block text-2xl font-semibold sm:text-3xl tabular-nums" :aria-label="`有效图片：${summary.images.status === 'available' && summary.images.value !== null ? `${summary.images.value}张` : contributionMetricLabel(summary.images)}`">{{ contributionMetricLabel(summary.images) }}<span v-if="summary.images.status === 'available' && summary.images.value !== null" class="ml-1 text-[11px] font-normal text-gray-500 dark:text-gray-400">张</span></span></summary><p class="mt-3 text-xs leading-6 text-gray-500 dark:text-gray-400">{{ summary.images.note }}</p></details>
        <details class="rounded-xl bg-gray-50 p-3 dark:bg-gray-900"><summary class="min-h-11 cursor-pointer list-none"><span class="block text-xs text-gray-500 dark:text-gray-400">范围核对</span><span class="mt-2 block text-2xl font-semibold tabular-nums" :aria-label="`范围核对：${summary.checked.status === 'available' && summary.checked.value !== null ? `${summary.checked.value}张` : contributionMetricLabel(summary.checked)}`">{{ contributionMetricLabel(summary.checked) }}<span v-if="summary.checked.status === 'available' && summary.checked.value !== null" class="ml-1 text-[11px] font-normal text-gray-500 dark:text-gray-400">张</span></span></summary><p class="mt-3 text-xs leading-6 text-gray-500 dark:text-gray-400">{{ summary.checked.note }}</p></details>
        <details class="rounded-xl bg-gray-50 p-3 dark:bg-gray-900"><summary class="min-h-11 cursor-pointer list-none"><span class="block text-xs text-gray-500 dark:text-gray-400">体检资料</span><span class="mt-2 block text-2xl font-semibold tabular-nums">{{ contributionMetricLabel(summary.reports) }}<span v-if="summary.reports.status === 'available' && summary.reports.value !== null" class="ml-1 text-[11px] font-normal text-gray-500 dark:text-gray-400">份</span></span></summary><p class="mt-3 text-xs leading-6 text-gray-500 dark:text-gray-400">{{ summary.reports.note }}</p></details>
      </div>
      <p class="mt-3 text-xs leading-6 text-gray-500 dark:text-gray-400">已上传 {{ summary.uploaded }} 张 · 本人已核对 {{ summary.personally_checked }} 张 · 待复核 {{ summary.pending }} 张。上传与有效入库分别记录。</p>
      <details class="mt-2 text-xs text-gray-500 dark:text-gray-400"><summary class="min-h-11 cursor-pointer">医生确认与共同影响</summary><p class="leading-6">医生确认：{{ summary.doctor.status === 'available' ? `${summary.doctor.value}条` : '待统计' }}。{{ summary.doctor.note }}。</p><p class="mt-2 leading-6">预计帮助：{{ summary.impact.status === 'available' ? `${summary.impact.value}人` : '正在积累' }}。{{ summary.impact.note }}。</p></details>
      <div class="mt-2 flex flex-wrap gap-2"><router-link to="/assessment" class="btn-primary inline-flex min-h-11 items-center gap-2 px-4 text-sm"><i class="ri-camera-line" aria-hidden="true"></i>继续记录</router-link><router-link to="/profile/data" class="btn-ghost inline-flex min-h-11 items-center px-3 text-xs">管理授权</router-link><router-link to="/assessment/exam" class="inline-flex min-h-11 items-center px-2 text-xs text-primary-700 dark:text-primary-300">整理体检资料</router-link></div>
    </template>
  </section>
</template>
