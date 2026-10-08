<script setup lang="ts">
import type { HospitalView } from '@/types/hospital'
defineProps<{ hospitals: HospitalView[] }>()
const emit = defineEmits<{ remove: [key: string] }>()
</script>
<template>
  <section>
    <p class="mb-4 text-xs leading-6 text-gray-500">并排查看官方资料与病友评价数量，不按治疗效果排名。费用、医保和出诊以医院确认为准。</p>
    <div class="grid gap-4" :class="hospitals.length === 3 ? 'md:grid-cols-3' : 'md:grid-cols-2'">
      <article v-for="hospital in hospitals" :key="hospital.key" class="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
        <h3 class="min-h-12 text-sm font-semibold leading-6">{{ hospital.name }}</h3>
        <p class="mt-1 text-[11px]" :class="hospital.origin === 'community' ? 'text-amber-700 dark:text-amber-300' : 'text-primary-700 dark:text-primary-300'">
          {{ hospital.origin === 'community' ? '病友补充 · 待核实' : '平台收录 · 附官方来源' }}
        </p>
        <dl class="mt-4 space-y-4 text-xs">
          <div><dt class="text-gray-400">所在地区</dt><dd class="mt-1">{{ hospital.province }} · {{ hospital.city }}<template v-if="hospital.district"> · {{ hospital.district }}</template></dd></div>
          <div><dt class="text-gray-400">详细地址</dt><dd class="mt-1">{{ hospital.address || '待补充' }}</dd></div>
          <div><dt class="text-gray-400">就诊科室</dt><dd class="mt-1">{{ hospital.department || '待确认' }}</dd></div>
          <div><dt class="text-gray-400">诊疗服务</dt><dd class="mt-1 leading-6">{{ hospital.features.join('、') || '待补充' }}</dd></div>
          <div><dt class="text-gray-400">病友评价</dt><dd class="mt-1">{{ hospital.stats.reviewCount }} 条（医生 {{ hospital.stats.doctorCount }} · 方案 {{ hospital.stats.treatmentCount }}）</dd></div>
          <div><dt class="text-gray-400">费用 / 医保 / 院区</dt><dd class="mt-1">待向医院确认</dd></div>
        </dl>
        <a v-if="hospital.source" :href="hospital.source" target="_blank" rel="noopener noreferrer" class="mt-4 flex min-h-11 items-center text-xs text-primary-700 dark:text-primary-300">核对官方资料 <i class="ri-external-link-line ml-1" /></a>
        <button class="min-h-11 text-xs text-gray-500" @click="emit('remove', hospital.key)">移出对比</button>
      </article>
    </div>
    <p v-if="!hospitals.length" class="py-8 text-center text-sm text-gray-500">暂无对比医院，请返回列表添加。</p>
    <p class="mt-4 text-[11px] leading-5 text-gray-400">评价数量与病友常提到的标签均来自个人就医体验，不代表医院诊疗水平；本表只对比客观字段，不做评分与排名。</p>
  </section>
</template>
