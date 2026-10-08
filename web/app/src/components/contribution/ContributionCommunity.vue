<script setup lang="ts">
import ContributionMetric from './ContributionMetric.vue'
import type { ContributionOverview } from '@/types/contribution'
defineProps<{ overview: ContributionOverview | null; loading: boolean; error: boolean }>()
defineEmits<{ retry: [] }>()
const date = (iso: string) => new Date(iso).toLocaleString('zh-CN', { hour12: false })
</script>

<template>
  <section id="community-results" class="scroll-mt-24" aria-labelledby="community-title">
    <div class="mb-4"><p class="text-xs font-medium text-primary-700 dark:text-primary-300">汇成大家的力量</p><h2 id="community-title" class="mt-1 text-lg font-semibold md:text-xl">我们一起建成的数据库</h2><p class="mt-2 text-sm leading-7 text-gray-500 dark:text-gray-400">一张照片提供一个视角，一次核对让资料更清楚。每个人的一份，正在汇成更多人的参考。</p></div>
    <div v-if="loading" role="status" aria-label="正在加载共建成果" class="grid animate-pulse grid-cols-2 gap-3 md:grid-cols-4"><div v-for="n in 4" :key="n" class="h-32 rounded-2xl bg-gray-100 dark:bg-gray-800"></div></div>
    <div v-else-if="error" role="alert" class="card p-5 text-center dark:bg-gray-800"><p class="text-sm text-gray-500 dark:text-gray-400">共建成果暂时没有加载成功</p><button type="button" class="btn-ghost mt-3 min-h-11 px-4" @click="$emit('retry')">重新加载</button></div>
    <template v-else-if="overview"><div class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <ContributionMetric label="社区用户" icon="ri-team-line" :metric="overview.users" secondary="当前有效注册账号" />
      <ContributionMetric label="图片贡献者" icon="ri-hand-heart-line" :metric="overview.contributors" secondary="至少一张有效贡献图片" />
      <ContributionMetric label="有效图片" icon="ri-gallery-line" :metric="overview.images" secondary="授权 · 去重 · 质量审核" />
      <ContributionMetric label="本人已核对" icon="ri-checkbox-circle-line" :metric="overview.checked" secondary="有效图片中的人工核对" />
    </div><div class="mt-3 grid gap-3 sm:grid-cols-2"><ContributionMetric label="带医生参考的病友占比" icon="ri-stethoscope-line" :metric="overview.doctor_ratio" secondary="完整确认与病友关联后统计" /><ContributionMetric label="同部位持续随访的病友" icon="ri-route-line" :metric="overview.followup" secondary="至少三次合格、可比记录" /></div>
    <p class="mt-3 text-[11px] leading-6 text-gray-400 dark:text-gray-500">更新于 <time :datetime="overview.updated_at">{{ date(overview.updated_at) }}</time> · 点击各指标可查看统计口径。小样本数据暂不公开，尚未具备的数据单独标记。</p></template>
  </section>
</template>
