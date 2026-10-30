<script setup lang="ts">
/**
 * 日记分割模型：金标准（图片打标「复核通过」）→ 导出数据集 → 训练 → 测试集门槛 → 登记上线。
 * 只用用户已授权「改进识别」且复核通过的标注；不达门槛的模型不能登记。
 */
import { useDialog } from 'naive-ui'
import { useRgbTraining } from '@/composables/useRgbTraining'
import DatasetList from '@/components/training/DatasetList.vue'
import RunList from '@/components/training/RunList.vue'
import type { Run } from '@/types/training'

const dialog = useDialog()
const { status, exporting, busyRun, epochs, running, load, exportDataset, train, cancel, register, disable } = useRgbTraining()

function confirmRegister(run: Run) {
  dialog.warning({
    title: '登记为线上模型',
    content: `登记后，所有用户在「日记」拍照都会使用 ${run.run_id} 生成初稿（仍需用户确认）。可随时停用回到原初稿。确定登记？`,
    positiveText: '登记上线', negativeText: '取消',
    onPositiveClick: () => { void register(run) },
  })
}
function confirmDisable() {
  dialog.warning({
    title: '停用线上分割模型',
    content: '停用后「日记」回到「人体解析 + 自适应初稿」。确定停用？',
    positiveText: '停用', negativeText: '取消',
    onPositiveClick: () => { void disable() },
  })
}
</script>

<template>
  <section class="panel" aria-labelledby="rgb-title">
    <div class="head">
      <h2 id="rgb-title">数据集与模型</h2>
      <div class="actions">
        <n-button size="medium" :loading="exporting" :disabled="!status || status.gold_consented === 0" @click="exportDataset">导出数据集</n-button>
        <n-button size="medium" quaternary aria-label="刷新" @click="load"><i class="ri-refresh-line" /></n-button>
      </div>
    </div>
    <p class="desc">
      金标准来自「图片打标」中复核通过的标注（仅限已授权「改进识别」的用户）。导出的数据集使用匿名编号、按受试者分训练/验证/测试，
      30 天后自动删除；用户撤回授权时，含其数据的数据集会被删除。训练 → 测试集达标后登记上线。
    </p>
    <template v-if="status">
      <div class="cards">
        <div class="card"><span>可标注任务</span><strong class="num">{{ status.rgb_labels }}</strong></div>
        <div class="card"><span>已提交标注</span><strong class="num">{{ status.admin_labeled }}</strong></div>
        <div class="card"><span>金标准</span><strong class="num">{{ status.gold }}</strong></div>
        <div class="card"><span>可训练（已授权）</span><strong class="num">{{ status.gold_consented }}</strong></div>
        <div class="card"><span>其中基准集</span><strong class="num">{{ status.benchmark_gold }}</strong></div>
        <div class="card"><span>涉及用户</span><strong class="num">{{ status.subjects }}</strong></div>
      </div>
      <p class="gate">
        登记门槛（锁定测试集）：≥{{ status.gate.min_test_images }} 张、≥{{ status.gate.min_test_subjects }} 位用户，白斑 Dice ≥ {{ status.gate.min_dice }}，皮肤 Dice ≥ {{ status.gate.min_skin_dice }}，且超过当前线上初稿。
        <span v-if="status.gold_consent_withdrawn">另有 {{ status.gold_consent_withdrawn }} 条金标准因授权撤回不会导出。</span>
      </p>
      <div class="registry">
        <span>线上模型：</span>
        <template v-if="status.registry.enabled">
          <n-tag type="success" size="small" :bordered="false">{{ status.registry.model_id }}</n-tag>
          <span class="muted">来自 {{ status.registry.run_id }}</span>
          <n-button size="small" type="error" ghost @click="confirmDisable">停用</n-button>
        </template>
        <span v-else class="muted">未登记专用模型，使用「人体解析 + 自适应初稿」</span>
      </div>
      <DatasetList v-if="status.datasets.length" v-model:epochs="epochs" :datasets="status.datasets" :running="running" :busy-run="busyRun" @train="train" />
      <RunList v-if="status.runs.length" :runs="status.runs" @cancel="cancel" @register="confirmRegister" />
      <n-empty v-if="!status.datasets.length && !status.runs.length" size="small" description="还没有导出过数据集：先在「图片打标」把标注复核通过为金标准" style="margin-top: 12px" />
    </template>
  </section>
</template>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
h2 { font-size: 18px; margin: 0; font-weight: 600; }
.actions { display: flex; gap: 8px; }
.desc, .gate { color: var(--tr-muted); font-size: 13px; line-height: 1.7; margin: 10px 0 12px; }
.cards { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }
.card { display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; border: 1px solid var(--tr-border); border-radius: 12px; background: var(--tr-panel); }
.card span, .muted { color: var(--tr-muted); font-size: 12px; }
.card strong { font-size: 22px; font-weight: 600; }
.num { font-variant-numeric: tabular-nums; }
.registry { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 13px; }
@media (max-width: 1100px) { .cards { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 767px) { .cards { grid-template-columns: repeat(2, 1fr); } }
</style>
