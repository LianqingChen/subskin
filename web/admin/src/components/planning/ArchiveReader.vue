<template>
  <article class="archive-reader" aria-label="文档阅读">
    <header class="reader-header">
      <div class="reader-actions">
        <button @click="emit('back')"><i class="ri-arrow-left-line" /> 返回列表</button>
        <button @click="raw = !raw">{{ raw ? '排版阅读' : '查看原文' }}</button>
        <button @click="copyLink"><i class="ri-link" /> 复制链接</button>
      </div>
      <p class="document-kind">{{ archiveCategories[document.category] }} <span>· 文档记录</span></p>
      <h2>{{ document.title }}</h2>
      <p class="reader-meta">{{ document.date || '文档日期未知' }} <span>更新于 {{ formattedTime }}</span></p>
      <p class="reader-path">{{ document.path }}</p>
      <div v-if="document.related.length > 1" class="related" aria-label="同主题文档">
        <span>同主题</span>
        <button v-for="item in document.related" :key="item.id" :title="item.title" :class="{ active: item.id === document.id }"
          @click="emit('select', item.id)">{{ archiveCategories[item.category] }} · {{ item.title }}</button>
      </div>
    </header>
    <nav v-if="rendered.headings.length && !raw" class="toc" aria-label="文档章节">
      <label for="archive-chapter">章节目录</label>
      <select id="archive-chapter" @change="jump(($event.target as HTMLSelectElement).value)">
        <option value="">跳转到章节…</option>
        <option v-for="heading in rendered.headings" :key="heading.id" :value="heading.id">{{ '　'.repeat(Math.min(heading.level - 1, 3)) }}{{ heading.text }}</option>
      </select>
    </nav>
    <div ref="body" class="reader-body">
      <pre v-if="raw" class="raw-text">{{ document.content }}</pre>
      <div v-else class="archive-prose" @click="handleLink" v-html="rendered.html" />
    </div>
    <footer class="reader-footnote">按仓库原文呈现，已隐藏可识别的敏感信息。图片不会自动加载。</footer>
  </article>
</template>
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { archiveCategories } from '@/types/planning'
import type { ArchiveDetail } from '@/types/planning'
import { renderArchiveMarkdown } from '@/utils/planning-markdown'
const props = defineProps<{ document: ArchiveDetail }>()
const emit = defineEmits<{ back: []; select: [id: string]; openPath: [path: string] }>()
const raw = ref(false)
const body = ref<HTMLElement | null>(null)
const message = useMessage()
const rendered = computed(() => renderArchiveMarkdown(props.document.content, props.document.path))
const formattedTime = computed(() => new Date(props.document.updated_at).toLocaleString('zh-CN', { hour12: false }))
watch(() => props.document.id, async () => { raw.value = false; await nextTick(); if (body.value) body.value.scrollTop = 0 })
function jump(id: string) {
  if (!id) return
  const target = body.value?.querySelector<HTMLElement>(`#${CSS.escape(id)}`)
  if (target && body.value) body.value.scrollTo({ top: body.value.scrollTop + target.getBoundingClientRect().top - body.value.getBoundingClientRect().top - 12, behavior: 'smooth' })
}
function handleLink(event: MouseEvent) {
  if (!(event.target instanceof Element)) return
  const link = event.target.closest('a')
  if (!link || link.target === '_blank') return
  event.preventDefault()
  if (link.dataset.document) emit('openPath', link.dataset.document)
  else if (link.dataset.section) {
    let requested: string
    try { requested = decodeURIComponent(link.dataset.section) } catch { return }
    const heading = rendered.value.headings.find(h => h.id === requested || h.text.toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu, '').replace(/\s/g, '-') === requested)
    if (heading) jump(heading.id)
  }
}
async function copyLink() {
  try { await navigator.clipboard.writeText(window.location.href); message.success('文档链接已复制，打开时需要管理员登录') }
  catch { message.warning('复制失败，可复制浏览器地址栏链接') }
}
</script>
<style scoped>
.archive-reader { min-width: 0; border: 1px solid var(--archive-border); border-radius: 14px; background: var(--archive-panel); overflow: hidden; }
.reader-header { padding: 20px 24px 16px; border-bottom: 1px solid var(--archive-border); }
.reader-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.reader-actions button { min-height: 44px; border: 0; background: transparent; color: var(--archive-accent); cursor: pointer; font-size: 12px; }
.document-kind { color: var(--archive-accent); font-size: 12px; margin: 0 0 8px; }
.document-kind span { color: var(--archive-muted); }
h2 { font-size: 22px; line-height: 1.5; margin: 0 0 12px; overflow-wrap: anywhere; }
.reader-meta { display: flex; gap: 12px; flex-wrap: wrap; color: var(--archive-muted); font-size: 12px; margin: 0; }
.reader-path { font-size: 11px; color: var(--archive-muted); overflow-wrap: anywhere; margin: 8px 0 0; }
.related { display: flex; gap: 8px; align-items: center; overflow-x: auto; padding-top: 14px; font-size: 12px; }
.related > span { flex-shrink: 0; color: var(--archive-muted); }
.related button { flex-shrink: 0; min-height: 44px; max-width: 230px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border-radius: 8px; background: transparent; border: 1px solid var(--archive-border); color: var(--archive-muted); padding: 8px 12px; cursor: pointer; }
.related button.active { background: var(--archive-accent-bg); color: var(--archive-accent); border-color: var(--archive-accent); }
.toc { display: flex; gap: 10px; align-items: center; padding: 10px 24px; border-bottom: 1px solid var(--archive-border); font-size: 12px; color: var(--archive-muted); }
.toc label { flex-shrink: 0; }
.toc select { min-width: 0; flex: 1; min-height: 44px; color: var(--archive-text); background: var(--archive-background); border: 1px solid var(--archive-border); border-radius: 8px; padding: 8px; }
.reader-body { position: relative; padding: 24px; max-height: 66dvh; overflow-y: auto; overflow-x: hidden; }
.raw-text { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; line-height: 1.8; }
.archive-prose { font-size: 14px; line-height: 1.9; overflow-wrap: anywhere; color: var(--archive-text); }
.archive-prose :deep(h1), .archive-prose :deep(h2), .archive-prose :deep(h3), .archive-prose :deep(h4) { line-height: 1.5; margin: 1.4em 0 .7em; font-weight: 600; }
.archive-prose :deep(h1) { font-size: 24px; } .archive-prose :deep(h2) { font-size: 20px; } .archive-prose :deep(h3) { font-size: 17px; }
.archive-prose :deep(p) { margin: .8em 0; }
.archive-prose :deep(ul), .archive-prose :deep(ol) { padding-left: 24px; margin: 1em 0; }
.archive-prose :deep(ul) { list-style: disc; } .archive-prose :deep(ol) { list-style: decimal; }
.archive-prose :deep(a) { color: var(--archive-accent); text-decoration: underline; text-underline-offset: 3px; }
.archive-prose :deep(a[aria-disabled]) { color: var(--archive-muted); text-decoration: none; cursor: default; }
.archive-prose :deep(blockquote) { border-left: 3px solid var(--archive-accent); background: var(--archive-accent-bg); padding: 8px 16px; margin: 16px 0; }
.archive-prose :deep(pre) { white-space: pre; overflow-x: auto; max-width: 100%; background: var(--archive-background); padding: 16px; border-radius: 8px; font-size: 12px; }
.archive-prose :deep(code) { font-family: ui-monospace, monospace; }
.archive-prose :deep(table) { display: block; max-width: 100%; overflow-x: auto; border-collapse: collapse; margin: 18px 0; font-size: 12px; }
.archive-prose :deep(th), .archive-prose :deep(td) { border: 1px solid var(--archive-border); padding: 10px 12px; min-width: 100px; text-align: left; }
.archive-prose :deep(th) { background: var(--archive-accent-bg); font-weight: 600; }
.archive-prose :deep(hr) { border: 0; border-top: 1px solid var(--archive-border); margin: 24px 0; }
.archive-prose :deep(.archive-image-note) { color: var(--archive-muted); font-size: 12px; }
.reader-footnote { padding: 12px 24px; border-top: 1px solid var(--archive-border); color: var(--archive-muted); font-size: 11px; }
@media (max-width: 767px) { .reader-header { padding: 12px 16px; } .reader-body { padding: 16px; max-height: 65dvh; } .toc { padding: 8px 16px; } h2 { font-size: 18px; } }
</style>
