<script setup lang="ts">
/**
 * 公益风控（/hospital-risk）。原「医评风控」，模块 2026-09-12 由「医评」改名「公益」。
 *
 * 对应《网络信息内容生态治理规定》第 9/10 条要求的「发布审核 + 实时巡查 + 留存记录」，
 * 以及《民法典》第 1028 条「及时采取更正或删除等必要措施」的处置动作落地。
 *
 * 看板三块：待处理举报 / 待处理申诉（含超时标红）/ 高冲突评价（按风险分）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { NCard, NDataTable, NButton, NTag, NSpace, NStatistic, NEmpty, NSpin, useMessage } from 'naive-ui'
import request from '@/api/request'

interface RiskItem {
  review_id: number
  hospital_id: number
  hospital_name?: string | null
  target: string
  risk_score: number
  risk_level: string
  risk_flags: string[]
  moderation_status: string
  report_count: number
  appeal_count: number
  content_excerpt: string
  created_at?: string | null
}

interface RiskBoard {
  total: number
  pending_reports: number
  pending_appeals: number
  overdue_appeals: number
  high_risk_count: number
  items: RiskItem[]
}

const message = useMessage()
const loading = ref(false)
const board = ref<RiskBoard>({
  total: 0, pending_reports: 0, pending_appeals: 0, overdue_appeals: 0, high_risk_count: 0, items: [],
})
const onlyPending = ref(true)

const TARGET_LABEL: Record<string, string> = {
  hospital: '医院评价', doctor: '医生评价', treatment: '治疗方案', experience: '治疗经历',
}
const STATUS_LABEL: Record<string, string> = {
  approved: '正常', flagged: '待复核', restricted: '受限（排序靠后）', blocked: '已下架',
}
const LEVEL_TYPE: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  safe: 'success', watch: 'warning', restricted: 'warning', high: 'error',
}

async function load() {
  loading.value = true
  try {
    const { data } = await request.get<RiskBoard>('/hospitals/admin/risk', {
      params: { limit: 100, offset: 0, only_pending: onlyPending.value },
    })
    board.value = data
  } catch {
    message.error('风控数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

/** 下架 / 恢复一条评价（复用既有可见性接口） */
async function setVisibility(item: RiskItem, hidden: boolean) {
  try {
    await request.post(`/hospitals/admin/reviews/${item.review_id}/visibility`, null, {
      params: { hidden },
    })
    message.success(hidden ? '已下架该评价' : '已恢复公开')
    await load()
  } catch {
    message.error('操作失败，请稍后重试')
  }
}

const columns = computed(() => [
  {
    title: '医院', key: 'hospital_name', minWidth: 150,
    render: (row: RiskItem) => row.hospital_name || `#${row.hospital_id}`,
  },
  {
    title: '类型', key: 'target', width: 100,
    render: (row: RiskItem) => TARGET_LABEL[row.target] || row.target,
  },
  {
    title: '风险分', key: 'risk_score', width: 90,
    render: (row: RiskItem) =>
      h('div', { class: 'flex items-center gap-1' }, [
        h(NTag, { type: LEVEL_TYPE[row.risk_level] || 'default', size: 'small' }, { default: () => `${row.risk_score}` }),
        h('span', { class: 'text-xs text-gray-400' }, row.risk_level),
      ]),
  },
  {
    title: '命中规则', key: 'risk_flags', minWidth: 180,
    render: (row: RiskItem) => (row.risk_flags?.length
      ? h('div', { class: 'flex flex-wrap gap-1' }, row.risk_flags.slice(0, 4).map(flag =>
          h(NTag, { size: 'small', type: 'warning' }, { default: () => flag })))
      : h('span', { class: 'text-xs text-gray-400' }, '—')),
  },
  {
    title: '举报 / 申诉', key: 'counts', width: 110,
    render: (row: RiskItem) => `${row.report_count} / ${row.appeal_count}`,
  },
  {
    title: '状态', key: 'moderation_status', width: 140,
    render: (row: RiskItem) => h(NTag, {
      size: 'small',
      type: row.moderation_status === 'blocked' ? 'error' : row.moderation_status === 'approved' ? 'success' : 'warning',
    }, { default: () => STATUS_LABEL[row.moderation_status] || row.moderation_status }),
  },
  {
    title: '内容摘要', key: 'content_excerpt', minWidth: 260,
    render: (row: RiskItem) => h('span', { class: 'text-xs' }, row.content_excerpt || '—'),
  },
  {
    title: '操作', key: 'actions', width: 170,
    render: (row: RiskItem) => h(NSpace, { size: 8 }, {
      default: () => [
        row.moderation_status === 'blocked'
          ? h(NButton, { size: 'small', onClick: () => setVisibility(row, false) }, { default: () => '恢复公开' })
          : h(NButton, { size: 'small', type: 'warning', ghost: true, onClick: () => setVisibility(row, true) }, { default: () => '下架' }),
      ],
    }),
  },
])

onMounted(load)
</script>

<template>
  <div class="p-4">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold">公益风控</h1>
        <p class="mt-1 text-xs text-gray-500">
          只审核评价是否违反社区公约，不判断医疗行为是否构成过错。处置动作全部写入审计日志。
        </p>
      </div>
      <div class="flex items-center gap-2">
        <NButton size="small" :type="onlyPending ? 'primary' : 'default'" @click="onlyPending = true; load()">仅看待处理</NButton>
        <NButton size="small" :type="!onlyPending ? 'primary' : 'default'" @click="onlyPending = false; load()">全部</NButton>
        <NButton size="small" @click="load">刷新</NButton>
      </div>
    </div>

    <div class="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <NCard size="small"><NStatistic label="待处理举报" :value="board.pending_reports" /></NCard>
      <NCard size="small"><NStatistic label="待处理申诉" :value="board.pending_appeals" /></NCard>
      <NCard size="small">
        <NStatistic label="申诉超时（>3 工作日）" :value="board.overdue_appeals" />
      </NCard>
      <NCard size="small"><NStatistic label="高风险评价（≥60 分）" :value="board.high_risk_count" /></NCard>
    </div>

    <NCard size="small">
      <template #header>
        <span class="text-sm">待办列表（{{ board.total }} 条）</span>
      </template>
      <NSpin :show="loading">
        <NDataTable
          v-if="board.items.length"
          :columns="columns"
          :data="board.items"
          :bordered="false"
          :single-line="false"
          size="small"
          :scroll-x="1100"
        />
        <NEmpty v-else description="当前没有需要处理的评价" />
      </NSpin>
    </NCard>

    <p class="mt-4 text-xs leading-6 text-gray-500">
      申诉处理时限为 3 个工作日（《民法典》第 1028 条：对失实内容应及时采取更正或删除等必要措施）。
      涉及诊疗争议的，平台不作出过错判断，应引导当事人通过医院医务处 / 医疗纠纷人民调解委员会 / 卫健委处理。
    </p>
  </div>
</template>
