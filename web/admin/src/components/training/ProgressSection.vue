<template>
  <section class="section" aria-labelledby="progress-title">
    <div class="head"><h2 id="progress-title">标注进度</h2>
      <n-button size="small" quaternary :loading="loading" aria-label="刷新进度" @click="emit('refresh')"><i class="ri-refresh-line" /></n-button></div>
    <p v-if="error" class="err" role="alert">{{ error }}</p>
    <template v-if="progress">
      <div class="cards">
        <div v-for="card in cards" :key="card.label" class="card"><span>{{ card.label }}</span><strong class="num">{{ card.value }}</strong></div>
      </div>
      <p class="gate">
        距离登记门槛：测试集需 ≥{{ progress.gate.min_test_images }} 张、≥{{ progress.gate.min_test_subjects }} 位受试者。
        测试集约占受试者的 15%，因此大约需要 ≥{{ needSubjects }} 位已授权受试者
        <template v-if="missing > 0">，当前约 {{ progress.gold.subjects_estimate }} 位，还差约 {{ missing }} 位。</template>
        <template v-else>，当前约 {{ progress.gold.subjects_estimate }} 位，已满足。</template>
      </p>
      <h3>标注员（近 {{ progress.window_days }} 天）</h3>
      <div class="table-wrap">
        <table v-if="progress.annotators.length" class="people">
          <thead><tr><th scope="col">标注员</th><th scope="col">提交</th><th scope="col">通过</th><th scope="col">退回</th><th scope="col">每张分钟</th></tr></thead>
          <tbody><tr v-for="row in progress.annotators" :key="row.author_id">
            <td>{{ row.author ?? `#${row.author_id}` }}</td><td class="num">{{ row.submitted }}</td><td class="num">{{ row.approved }}</td>
            <td class="num">{{ row.returned }}</td><td class="num">{{ row.minutes_per_image?.toFixed(1) ?? '—' }}</td>
          </tr></tbody>
        </table>
        <p v-else class="muted">近期暂无提交</p>
      </div>
      <h3>标注质量</h3>
      <div class="quality">
        <div><span>AI 初稿 vs 最终标注</span><strong class="num">白斑 Dice {{ dice(progress.draft_quality.vs_ai_lesion_dice) }} · 皮肤 Dice {{ dice(progress.draft_quality.vs_ai_skin_dice) }}</strong></div>
        <div><span>用户日记版 vs 最终标注</span><strong class="num">白斑 Dice {{ dice(progress.draft_quality.vs_user_lesion_dice) }}</strong></div>
        <div><span>标注员之间一致性（{{ progress.inter_annotator.pairs }} 对）</span><strong class="num">白斑 Dice {{ dice(progress.inter_annotator.lesion_dice) }} · 皮肤 Dice {{ dice(progress.inter_annotator.skin_dice) }}</strong></div>
      </div>
      <p class="muted">Dice 越接近 1 越一致：初稿值高说明 AI 初稿可靠；一致性低说明标注规范需要统一。</p>
      <h3>金标准覆盖</h3>
      <CoverageMatrix :coverage="progress.gold.coverage" />
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import CoverageMatrix from '@/components/training/CoverageMatrix.vue'
import type { LabelingProgress } from '@/types/labeling'

const props = defineProps<{ progress: LabelingProgress | null; loading: boolean; error: string }>()
const emit = defineEmits<{ refresh: [] }>()

const cards = computed(() => {
  const p = props.progress
  if (!p) return []
  return [
    { label: '待复核', value: p.awaiting_review }, { label: '金标准', value: p.gold.total },
    { label: '阴性样本（无白斑）', value: p.gold.negatives }, { label: '基准集', value: p.gold.benchmark },
    { label: '受试者（估计）', value: p.gold.subjects_estimate },
  ]
})
const needSubjects = computed(() => (props.progress ? Math.max(props.progress.gate.min_test_subjects, Math.ceil(props.progress.gate.min_test_subjects / 0.15)) : 0))
const missing = computed(() => (props.progress ? needSubjects.value - props.progress.gold.subjects_estimate : 0))
const dice = (value: number | null) => (value === null ? '—' : value.toFixed(3))
</script>
<style scoped>
.section { margin-bottom: 28px; }
.head { display: flex; align-items: center; justify-content: space-between; }
h2 { font-size: 18px; margin: 0 0 12px; font-weight: 600; }
h3 { font-size: 14px; margin: 20px 0 8px; font-weight: 600; }
.cards { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.card { display: flex; flex-direction: column; gap: 6px; padding: 14px 16px; border: 1px solid var(--tr-border); border-radius: 12px; background: var(--tr-panel); }
.card span, .muted { color: var(--tr-muted); font-size: 12px; }
.card strong { font-size: 24px; font-weight: 600; }
.num { font-variant-numeric: tabular-nums; }
.gate { color: var(--tr-muted); font-size: 13px; line-height: 1.7; margin: 12px 0 0; }
.table-wrap { overflow-x: auto; }
.people { width: 100%; border-collapse: collapse; font-size: 13px; }
.people th, .people td { padding: 10px 8px; text-align: left; border-bottom: 1px solid var(--tr-border); white-space: nowrap; }
.people th { color: var(--tr-muted); font-weight: 500; }
.quality { display: grid; gap: 8px; }
.quality > div { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px; padding: 10px 14px; border: 1px solid var(--tr-border); border-radius: 10px; background: var(--tr-panel); font-size: 13px; }
.quality span { color: var(--tr-muted); }
.err { color: #e88080; font-size: 13px; }
@media (max-width: 1100px) { .cards { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 767px) { .cards { grid-template-columns: repeat(2, 1fr); } }
</style>
