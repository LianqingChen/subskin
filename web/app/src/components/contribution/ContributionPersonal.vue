<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import ContributionMetric from './ContributionMetric.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { MyContributions } from '@/types/contribution'
defineProps<{ summary: MyContributions | null; loading: boolean; error: boolean }>()
defineEmits<{ retry: [] }>()
const auth = useAuthStore()
</script>

<template>
  <section id="my-contribution" class="scroll-mt-24" aria-labelledby="personal-title">
    <div class="mb-4 flex flex-wrap items-end justify-between gap-2">
      <div><p class="text-xs font-medium text-primary-700 dark:text-primary-300">从我的一份，开始</p><h2 id="personal-title" class="mt-1 text-lg font-semibold md:text-xl">我的贡献</h2></div>
      <router-link to="/profile/data" class="inline-flex min-h-11 items-center gap-1 text-xs text-gray-500 dark:text-gray-400">管理数据授权<i class="ri-arrow-right-s-line" aria-hidden="true"></i></router-link>
    </div>
    <div class="card overflow-hidden bg-primary-50/40 p-5 dark:bg-gray-800 md:p-6">
      <EmptyState v-if="!auth.isLoggedIn" icon="ri-hand-heart-line" title="每一份认真记录，都有自己的位置" description="登录后查看你的贡献、积分和成长进度。" action-label="登录查看我的贡献" @action="auth.showLoginModal = true" />
      <div v-else-if="loading" role="status" aria-label="正在加载个人贡献" class="grid animate-pulse grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"><div v-for="n in 5" :key="n" class="h-32 rounded-2xl bg-gray-100 dark:bg-gray-700"></div><span class="sr-only">加载中</span></div>
      <div v-else-if="error" role="alert" class="py-8 text-center"><p class="text-sm text-gray-500 dark:text-gray-400">个人贡献暂时没有加载成功</p><button type="button" class="btn-ghost mt-3 min-h-11 px-4" @click="$emit('retry')">重新加载</button></div>
      <template v-else-if="summary">
        <div class="mb-5 flex flex-wrap items-center gap-2">
          <span class="font-medium">{{ auth.user?.username || '同行伙伴' }}</span>
          <span class="rounded-full bg-primary-100 px-3 py-1 text-xs text-primary-700 dark:bg-primary-900 dark:text-primary-300">Lv.{{ summary.membership.current.level }} {{ summary.membership.current.name }}</span>
          <span class="text-xs text-gray-500 dark:text-gray-400">{{ summary.active_consent ? '已开启图片贡献授权' : '记录由你自主决定是否用于共建' }}</span>
        </div>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <ContributionMetric label="有效图片" icon="ri-image-line" :metric="summary.images" :secondary="`已上传 ${summary.uploaded} 张 · 待复核 ${summary.pending} 张`" />
          <ContributionMetric label="有效打标" icon="ri-edit-circle-line" :metric="summary.checked" :secondary="`本人已核对 ${summary.personally_checked} 张`" />
          <ContributionMetric label="体检资料" icon="ri-file-list-3-line" :metric="summary.reports" secondary="已上传份数 · 共建授权待开放" />
          <ContributionMetric label="医生确认" icon="ri-stethoscope-line" :metric="summary.doctor" secondary="认证医生确认链路完善后统计" />
          <ContributionMetric label="预计帮助" icon="ri-heart-3-line" :metric="summary.impact" secondary="共同影响正在积累" />
        </div>
        <div class="mt-5 flex flex-wrap gap-3">
          <router-link to="/assessment" class="btn-primary inline-flex min-h-11 items-center gap-2 px-4 text-sm"><i class="ri-camera-line" aria-hidden="true"></i>继续记录</router-link>
          <router-link to="/assessment/exam" class="btn-ghost inline-flex min-h-11 items-center gap-2 px-4 text-sm"><i class="ri-file-add-line" aria-hidden="true"></i>整理体检资料</router-link>
          <router-link to="/photo-guide" class="inline-flex min-h-11 items-center gap-1 px-2 text-xs text-primary-700 dark:text-primary-300">查看拍摄指南<i class="ri-arrow-right-up-line" aria-hidden="true"></i></router-link>
        </div>
        <p class="mt-4 text-xs leading-6 text-gray-500 dark:text-gray-400">已上传不等于已入库。有效贡献通过质量审核和用途授权后才计入；你可随时管理或撤回授权。</p>
      </template>
    </div>
  </section>
</template>
