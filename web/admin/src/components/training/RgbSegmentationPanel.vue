<script setup lang="ts">
/**
 * 记录页分割模型（新流程）：金标准 → 导出数据集 → 训练 → 测试集门槛 → 登记上线。
 * 只用用户已授权「改进识别」且管理员审核通过的标注；不达门槛的模型不能登记。
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { NCard, NStatistic, NGrid, NGi, NTag, NButton, NSpace, NInputNumber, NEmpty, useMessage, useDialog } from 'naive-ui'
import request from '@/api/request'

interface Gate { passed: boolean; reasons: string[]; dice?: number | null; skin_dice?: number | null; baseline_dice?: number | null; test_subjects?: number }
interface DatasetReport { dataset_id: string; items: number; subjects: number; counts: Record<string, number>; valid: boolean; error: string | null; skipped: unknown[] }
interface Run { run_id: string; dataset_id: string; epochs: number; state: string; error: string | null; created_at: string; epochs_run?: number; gate: Gate }
interface Status {
  rgb_labels: number; admin_labeled: number; gold: number; gold_consented: number; gold_consent_withdrawn: number; subjects: number
  gate: { min_test_images: number; min_test_subjects: number; min_dice: number; min_skin_dice: number }
  datasets: DatasetReport[]; runs: Run[]
  registry: { enabled: boolean | null; model_id: string | null; dataset_review_id: string | null; registered_at: string | null; run_id: string | null }
}

const message = useMessage()
const dialog = useDialog()
const status = ref<Status | null>(null)
const exporting = ref(false)
const busyRun = ref<string | null>(null)
const epochs = ref(30)
let timer: ReturnType<typeof setInterval> | null = null

const running = computed(() => status.value?.runs.some(r => ['queued', 'training', 'evaluating'].includes(r.state)) ?? false)
const STATE: Record<string, [string, 'default' | 'info' | 'success' | 'error' | 'warning']> = {
  queued: ['排队中', 'default'], training: ['训练中', 'info'], evaluating: ['评测中', 'info'], completed: ['已完成', 'success'], failed: ['失败', 'error'],
}

async function load() {
  try {
    const { data } = await request.get<Status>('/vasi/admin/rgb-training/status')
    status.value = data
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '加载分割模型状态失败')
  }
}

async function exportDataset() {
  exporting.value = true
  try {
    const { data } = await request.post<DatasetReport>('/vasi/admin/rgb-training/datasets')
    if (data.valid) message.success(`已导出 ${data.items} 张、${data.subjects} 位用户`)
    else message.warning(`已导出，但未通过校验：${data.error}`)
    await load()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function train(datasetId: string) {
  busyRun.value = datasetId
  try {
    await request.post('/vasi/admin/rgb-training/runs', { dataset_id: datasetId, epochs: epochs.value })
    message.success('训练已在后台开始')
    await load()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '无法开始训练')
  } finally {
    busyRun.value = null
  }
}

async function cancel(runId: string) {
  try {
    await request.delete(`/vasi/admin/rgb-training/runs/${runId}`)
    message.info('已请求停止')
    await load()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '停止失败')
  }
}

function register(run: Run) {
  dialog.warning({
    title: '登记为线上模型',
    content: `登记后，所有用户在记录页拍照都会使用 ${run.run_id} 生成初稿（仍需用户确认）。可随时停用回到原初稿。确定登记？`,
    positiveText: '登记上线',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await request.post(`/vasi/admin/rgb-training/runs/${run.run_id}/register`)
        message.success('已登记，新任务立即生效')
        await load()
      } catch (err: any) {
        message.error(err?.response?.data?.detail || '登记失败')
      }
    },
  })
}

function disable() {
  dialog.warning({
    title: '停用线上分割模型',
    content: '停用后记录页回到「人体解析 + 自适应初稿」。确定停用？',
    positiveText: '停用',
    negativeText: '取消',
    onPositiveClick: async () => {
      await request.post('/vasi/admin/rgb-training/registry/disable')
      message.success('已停用')
      await load()
    },
  })
}

const pct = (v?: number | null) => (v == null ? '—' : v.toFixed(3))

onMounted(() => {
  void load()
  timer = setInterval(() => { if (running.value) void load() }, 5000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <n-card style="margin-top: 20px" :bordered="false" class="list-card">
    <template #header>
      <div class="card-header">
        <span><i class="ri-shield-check-line" /> 记录页分割模型（新流程）</span>
        <n-space :size="8">
          <n-button size="small" :loading="exporting" :disabled="!status || status.gold_consented === 0" @click="exportDataset">
            导出数据集
          </n-button>
          <n-button size="small" quaternary @click="load"><i class="ri-refresh-line" /></n-button>
        </n-space>
      </div>
    </template>

    <p class="rgb-desc">
      链路：用户在记录页拍照 → 打标页「记录页」标注 → 管理员提交并勾选「审核通过」成为金标准（仅限已授权「改进识别」的用户）→ 导出数据集（匿名编号、按用户分训练/验证/测试）→ 训练 → 测试集达标后登记上线。
    </p>

    <n-grid v-if="status" :cols="5" :x-gap="10" :y-gap="10" responsive="screen" item-responsive>
      <n-gi span="5 m:1"><n-statistic label="记录页标注" :value="status.rgb_labels" /></n-gi>
      <n-gi span="5 m:1"><n-statistic label="管理员已标" :value="status.admin_labeled" /></n-gi>
      <n-gi span="5 m:1"><n-statistic label="金标准" :value="status.gold" /></n-gi>
      <n-gi span="5 m:1"><n-statistic label="可用于训练（已授权）" :value="status.gold_consented" /></n-gi>
      <n-gi span="5 m:1"><n-statistic label="涉及用户" :value="status.subjects" /></n-gi>
    </n-grid>
    <p v-if="status" class="rgb-gate">
      登记门槛（锁定测试集）：≥{{ status.gate.min_test_images }} 张、≥{{ status.gate.min_test_subjects }} 位用户，白斑 Dice ≥ {{ status.gate.min_dice }}，皮肤 Dice ≥ {{ status.gate.min_skin_dice }}，且超过当前线上初稿。
      <span v-if="status.gold_consent_withdrawn">另有 {{ status.gold_consent_withdrawn }} 条金标准因授权撤回不会导出。</span>
    </p>

    <div v-if="status" class="rgb-registry">
      <span>线上模型：</span>
      <template v-if="status.registry.enabled">
        <n-tag type="success" size="small" :bordered="false">{{ status.registry.model_id }}</n-tag>
        <span class="muted">来自 {{ status.registry.run_id }}</span>
        <n-button size="tiny" type="error" ghost @click="disable">停用</n-button>
      </template>
      <span v-else class="muted">未登记专用模型，使用「人体解析 + 自适应初稿」</span>
    </div>

    <div v-if="status && status.datasets.length" class="rgb-block">
      <div class="rgb-block-title">
        数据集
        <span class="muted">训练轮数</span>
        <n-input-number v-model:value="epochs" size="tiny" :min="1" :max="200" style="width: 90px" />
      </div>
      <div v-for="d in status.datasets.slice(0, 5)" :key="d.dataset_id" class="rgb-row">
        <code>{{ d.dataset_id }}</code>
        <span>{{ d.items }} 张 · {{ d.subjects }} 位用户 · 训练 {{ d.counts.train }} / 验证 {{ d.counts.validation }} / 测试 {{ d.counts.test }}</span>
        <n-tag v-if="d.valid" type="success" size="tiny" :bordered="false">校验通过</n-tag>
        <n-tag v-else type="warning" size="tiny" :bordered="false" :title="d.error || ''">未通过：{{ d.error }}</n-tag>
        <n-button v-if="d.valid" size="tiny" type="primary" :disabled="running" :loading="busyRun === d.dataset_id" @click="train(d.dataset_id)">开始训练</n-button>
      </div>
    </div>

    <div v-if="status && status.runs.length" class="rgb-block">
      <div class="rgb-block-title">训练记录</div>
      <div v-for="r in status.runs" :key="r.run_id" class="rgb-row">
        <code>{{ r.run_id }}</code>
        <n-tag :type="(STATE[r.state] || ['', 'default'])[1]" size="tiny" :bordered="false">{{ (STATE[r.state] || [r.state])[0] }}</n-tag>
        <span v-if="r.state === 'completed'">白斑 Dice {{ pct(r.gate.dice) }}（线上初稿 {{ pct(r.gate.baseline_dice) }}）· 皮肤 Dice {{ pct(r.gate.skin_dice) }}</span>
        <span v-if="r.error" class="err">{{ r.error }}</span>
        <n-button v-if="['queued', 'training', 'evaluating'].includes(r.state)" size="tiny" @click="cancel(r.run_id)">停止</n-button>
        <template v-if="r.state === 'completed'">
          <n-button v-if="r.gate.passed" size="tiny" type="warning" @click="register(r)">登记上线</n-button>
          <span v-else class="muted" :title="r.gate.reasons.join('；')">未达门槛：{{ r.gate.reasons.join('；') }}</span>
        </template>
      </div>
    </div>
    <n-empty v-if="status && !status.datasets.length && !status.runs.length" size="small" description="还没有导出过数据集：先在打标页把「记录页」标注审核通过为金标准" style="margin-top: 12px" />
  </n-card>
</template>

<style scoped>
.rgb-desc, .rgb-gate { color: #94a3b8; font-size: 12px; line-height: 1.6; margin: 0 0 12px; }
.rgb-gate { margin-top: 12px; }
.rgb-registry { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 13px; color: #cbd5e1; }
.rgb-block { margin-top: 16px; }
.rgb-block-title { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 6px; }
.rgb-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 6px 0; border-top: 1px solid rgba(148, 163, 184, 0.1); font-size: 12px; color: #cbd5e1; }
.rgb-row code { color: #a5b4fc; font-size: 11px; }
.muted { color: #64748b; font-size: 12px; }
.err { color: #f87171; }
.card-header { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.card-header > span { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; }
</style>
