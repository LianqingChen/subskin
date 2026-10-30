<template>
  <div class="block">
    <div class="title">数据集
      <span class="muted">训练轮数</span>
      <n-input-number :value="epochs" size="small" :min="1" :max="200" style="width: 100px" aria-label="训练轮数" @update:value="(v: number | null) => emit('update:epochs', v ?? 30)" />
    </div>
    <div v-for="d in datasets.slice(0, 5)" :key="d.dataset_id" class="row">
      <code>{{ d.dataset_id }}</code>
      <span class="num">{{ d.items }} 张 · {{ d.subjects }} 位 · 训练 {{ d.counts.train }} / 验证 {{ d.counts.validation }} / 测试 {{ d.counts.test }}
        · 阴性 {{ d.negatives ?? 0 }} · 基准 {{ d.benchmark_items ?? 0 }}<template v-if="d.expires_at"> · {{ d.expires_at }} 到期删除</template></span>
      <n-tag v-if="d.valid" type="success" size="small" :bordered="false">校验通过</n-tag>
      <n-tag v-else type="warning" size="small" :bordered="false" :title="d.error || ''">未通过：{{ d.error }}</n-tag>
      <n-button v-if="d.valid" size="small" type="primary" :disabled="running" :loading="busyRun === d.dataset_id" @click="emit('train', d.dataset_id)">开始训练</n-button>
    </div>
  </div>
</template>
<script setup lang="ts">
import type { DatasetReport } from '@/types/training'

defineProps<{ datasets: DatasetReport[]; epochs: number; running: boolean; busyRun: string | null }>()
const emit = defineEmits<{ train: [id: string]; 'update:epochs': [value: number] }>()
</script>
<style scoped>
.block { margin-top: 16px; }
.title { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 0; border-top: 1px solid var(--tr-border); font-size: 12px; }
.row code { font-size: 11px; color: var(--tr-accent); }
.muted { color: var(--tr-muted); font-size: 12px; font-weight: 400; }
.num { font-variant-numeric: tabular-nums; }
</style>
