<template>
  <n-modal :show="!!item" :mask-closable="true" @update:show="(v: boolean) => { if (!v) emit('close') }">
    <div v-if="item" class="lightbox" role="dialog" aria-label="照片详情">
      <figure class="viewer">
        <img v-if="image.url.value" :src="image.url.value" :alt="`公开图库 #${item.id}`" />
        <i v-else :class="image.failed.value ? 'ri-image-line' : 'ri-loader-4-line spin'" aria-hidden="true" />
        <button type="button" class="nav prev" :disabled="!hasPrev" aria-label="上一张" @click="emit('step', -1)"><i class="ri-arrow-left-s-line" /></button>
        <button type="button" class="nav next" :disabled="!hasNext" aria-label="下一张" @click="emit('step', 1)"><i class="ri-arrow-right-s-line" /></button>
      </figure>
      <aside class="info">
        <header>
          <strong>#{{ item.id }}</strong>
          <n-tag size="small" :bordered="false">{{ SOURCE[item.external?.source ?? ''] ?? '后台上传' }}</n-tag>
          <n-tag size="small" :type="item.status === 'rejected' ? 'error' : item.status === 'gold' ? 'success' : 'default'" :bordered="false">{{ STATUS_LABEL[item.status] }}</n-tag>
        </header>
        <dl>
          <dt>许可证</dt><dd>{{ item.external?.license ?? '—' }}<template v-if="item.external?.share_alike">（相同方式共享）</template></dd>
          <template v-if="item.external?.citation"><dt>出处</dt><dd>{{ item.external.citation }} {{ item.external.figure }}</dd></template>
          <template v-if="item.external?.artist"><dt>作者</dt><dd>{{ item.external.artist }}</dd></template>
          <template v-if="item.external?.caption"><dt>原图注</dt><dd class="caption">{{ item.external.caption }}</dd></template>
          <template v-if="item.rejection?.reasons"><dt>不可用原因</dt><dd>{{ item.rejection.reasons.map((r) => REASON_LABEL[r] ?? r).join('、') }}</dd></template>
          <template v-if="item.latest"><dt>最新标注</dt><dd>{{ item.latest.author ?? '—' }} · 白斑 {{ item.latest.stats.lesion_ratio?.toFixed(1) ?? '—' }}%</dd></template>
        </dl>
        <a v-if="item.external?.url" :href="sourceLink" target="_blank" rel="noopener" class="link"><i class="ri-external-link-line" /> 查看原始来源</a>
        <div class="actions">
          <n-button type="primary" @click="emit('label', item)"><template #icon><i class="ri-brush-line" /></template>去标注</n-button>
          <n-button v-if="item.status !== 'rejected'" type="error" secondary @click="emit('reject', item)">不可用</n-button>
          <n-button quaternary @click="emit('close')">关闭</n-button>
        </div>
      </aside>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthImage } from '@/composables/useAuthImage'
import { REASON_LABEL, STATUS_LABEL, type TaskSummary } from '@/types/labeling'

const props = defineProps<{ item: TaskSummary | null; hasPrev: boolean; hasNext: boolean }>()
const emit = defineEmits<{ close: []; step: [delta: number]; label: [item: TaskSummary]; reject: [item: TaskSummary] }>()
const SOURCE: Record<string, string> = { pmc_oa: 'PMC 开放获取', wikimedia_commons: '维基共享资源' }
const image = useAuthImage(computed(() => props.item?.id ?? null))
const sourceLink = computed(() => {
  const ext = props.item?.external
  if (ext?.doi) return `https://doi.org/${ext.doi}`
  if (ext?.pmcid) return `https://pmc.ncbi.nlm.nih.gov/articles/${ext.pmcid}/`
  return ext?.url ?? ''
})
</script>

<style scoped>
.lightbox { display: flex; width: min(1280px, 96vw); height: min(860px, 92vh); background: #0b1220; border: 1px solid #1f2937; border-radius: 14px; overflow: hidden; color: #e2e8f0; }
.viewer { position: relative; flex: 1; min-width: 0; margin: 0; display: flex; align-items: center; justify-content: center; background: #020617; }
.viewer img { max-width: 100%; max-height: 100%; object-fit: contain; }
.viewer > i { font-size: 40px; color: #475569; }
.nav { position: absolute; top: 50%; transform: translateY(-50%); width: 44px; height: 64px; border: 0; border-radius: 10px; background: rgba(15, 23, 42, .7); color: #f8fafc; font-size: 24px; cursor: pointer; }
.nav:disabled { opacity: .25; cursor: default; }
.prev { left: 10px; } .next { right: 10px; }
.info { width: 340px; flex-shrink: 0; padding: 16px; overflow-y: auto; border-left: 1px solid #1f2937; display: flex; flex-direction: column; gap: 12px; font-size: 13px; }
header { display: flex; align-items: center; gap: 8px; }
dl { margin: 0; display: grid; gap: 4px; }
dt { color: #94a3b8; font-size: 12px; margin-top: 6px; }
dd { margin: 0; line-height: 1.6; }
.caption { max-height: 220px; overflow-y: auto; color: #cbd5e1; }
.link { color: #2dd4bf; text-decoration: none; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: auto; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 900px) { .lightbox { flex-direction: column; } .viewer { min-height: 50vh; } .info { width: 100%; border-left: 0; border-top: 1px solid #1f2937; } }
</style>
