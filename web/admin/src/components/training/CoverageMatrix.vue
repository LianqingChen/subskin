<template>
  <div class="matrix-wrap">
    <table class="matrix">
      <caption class="sr-only">金标准覆盖：部位分组与肤色</caption>
      <thead><tr><th scope="col">部位</th><th v-for="col in COLUMNS" :key="col.key" scope="col">{{ col.label }}</th></tr></thead>
      <tbody>
        <tr v-for="group in GROUPS" :key="group">
          <th scope="row">{{ GROUP_LABEL[group] }}</th>
          <td v-for="col in COLUMNS" :key="col.key" class="num" :class="{ gap: !cell(group, col.key) }">
            {{ cell(group, col.key) || '缺' }}
          </td>
        </tr>
      </tbody>
    </table>
    <p class="legend">数字为金标准张数，「缺」表示该组合尚无样本。</p>
  </div>
</template>
<script setup lang="ts">
import { GROUP_LABEL } from '@/types/labeling'

const props = defineProps<{ coverage: Record<string, Record<string, number>> }>()
const GROUPS = ['head', 'torso', 'arm', 'hand', 'leg', 'foot', 'other', 'unknown']
const COLUMNS = [
  { key: 'mst_1_3', label: '浅 (1–3)' }, { key: 'mst_4_6', label: '中 (4–6)' },
  { key: 'mst_7_10', label: '深 (7–10)' }, { key: 'unknown', label: '未标肤色' },
]
const cell = (group: string, band: string) => props.coverage[group]?.[band] ?? 0
</script>
<style scoped>
.matrix-wrap { overflow-x: auto; }
.matrix { width: 100%; border-collapse: separate; border-spacing: 4px; font-size: 13px; }
th { color: var(--tr-muted); font-weight: 500; text-align: center; padding: 6px 8px; white-space: nowrap; }
tbody th { text-align: left; }
td { text-align: center; padding: 10px 8px; min-width: 64px; border-radius: 8px; background: var(--tr-accent-bg); }
td.gap { background: rgba(232, 128, 128, .14); color: #e88080; border: 1px dashed rgba(232, 128, 128, .5); }
.num { font-variant-numeric: tabular-nums; }
.legend { color: var(--tr-muted); font-size: 12px; margin: 6px 0 0; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
