<template>
  <section class="site-maintenance" aria-label="网站运维">
    <n-page-header title="网站运维" />
    <p>维护 SubSkin 网站的知识库与数据存储。</p>
    <n-alert type="info" :show-icon="false">
      服务器监控、系统服务与终端已统一到
      <a href="https://dsh.subskin.cn/" target="_blank" rel="noopener noreferrer">DSH Console <i class="ri-external-link-line" aria-hidden="true" /></a>。
    </n-alert>
    <n-alert v-if="error" type="error" style="margin-top:16px">{{ error }}</n-alert>
    <n-card title="网站数据存储" style="margin-top:20px">
      <template #header-extra><n-button :loading="loading" @click="refresh">刷新</n-button></template>
      <dl><dt>网站数据库</dt><dd>{{ bytes(storage?.database_bytes) }}</dd><dt>写入日志（WAL）</dt><dd>{{ bytes(storage?.wal_bytes) }}</dd></dl>
    </n-card>
    <n-card title="知识库向量化" style="margin-top:20px">
      <p>对尚未完成向量化的文献执行增量处理。此任务可能耗时较长，按需手动触发。</p>
      <n-button type="primary" :loading="embedding" :disabled="embedding" @click="confirmEmbedding">
        <template #icon><i class="ri-database-2-line" aria-hidden="true" /></template>
        {{ embedding ? '向量化执行中…' : '触发文献向量化' }}
      </n-button>
      <p v-if="result" role="status">成功 {{ result.embedded_count }} / 失败 {{ result.failed_count }} / 总计 {{ result.total }}</p>
    </n-card>
  </section>
</template>

<script setup lang="ts">
import { NAlert, NButton, NCard, NPageHeader, useDialog } from 'naive-ui'
import { useSiteMaintenance } from '@/composables/useSiteMaintenance'
const { storage, loading, embedding, result, error, refresh, embed } = useSiteMaintenance()
const dialog = useDialog()
function bytes(value: number | null | undefined) {
  if (value == null) return '暂不可用'
  return (value / 1024 / 1024).toFixed(1) + ' MB'
}
function confirmEmbedding() {
  dialog.warning({ title: '确认触发文献向量化', content: '将处理尚未向量化的文献，可能产生模型调用并耗时较长。', positiveText: '开始处理', negativeText: '取消', onPositiveClick: embed })
}
</script>

<style scoped>
.site-maintenance { max-width: 1152px; margin: 0 auto; padding: 16px; }
.site-maintenance p { color: var(--n-text-color); line-height: 1.7; }
a { color: var(--n-color-target); text-decoration: underline; }
dl { display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap: 12px; }
dd { margin: 0; text-align: right; }
:deep(button) { min-height: 44px; }
</style>
