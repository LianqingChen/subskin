<template>
  <main class="dev-docs-page" :style="themeStyle">
    <!-- Top Banner & Agent Handover Bar -->
    <header class="docs-hero">
      <div class="hero-main">
        <div class="eyebrow-row">
          <span class="eyebrow-pill"><i class="ri-shield-star-line" /> SINGLE SOURCE OF TRUTH</span>
          <span class="eyebrow-meta">与仓库 <code>docs/standards/</code> · <code>AGENTS.md</code> · <code>.agents/skills/</code> 实时同源编译</span>
        </div>
        <h1>开发文档与多 Agent 维护规范中心</h1>
        <p class="hero-desc">
          汇集 SubSkin 网站建设、UI/UX 设计系统、用户动线、L1–L4 隐私安全生死线、前后端与 AI 架构、三环境部署运维及多 Agent 无缝交接规范。任何进入项目空间的 Agent 与大模型均以此为最高行动准则。
        </p>
      </div>
      <div class="hero-actions">
        <button type="button" class="primary-action-btn" @click="copyHandoverPrompt">
          <i class="ri-robot-2-line" />
          <span>复制新 Agent 接手指令</span>
        </button>
        <button type="button" class="secondary-action-btn" @click="showQuickBoard = !showQuickBoard">
          <i :class="showQuickBoard ? 'ri-Polaroid-line' : 'ri-dashboard-horizontal-line'" />
          <span>{{ showQuickBoard ? '收起核心速查看板' : '展开核心速查看板' }}</span>
        </button>
      </div>
    </header>

    <!-- KPI Summary Bar -->
    <section class="docs-metrics" aria-label="规范体系概览">
      <div class="metric-card" @click="activeGroup = 'core'">
        <div class="metric-icon" style="color: #14b8a6; background: rgba(20, 184, 166, 0.12)">
          <i class="ri-book-read-line" />
        </div>
        <div class="metric-body">
          <span>核心全栈规范 (STD-00 ~ 07)</span>
          <strong>8 <small>大模块</small></strong>
        </div>
      </div>
      <div class="metric-card" @click="activeGroup = 'architecture'">
        <div class="metric-icon" style="color: #6366f1; background: rgba(99, 102, 241, 0.12)">
          <i class="ri-compasses-2-line" />
        </div>
        <div class="metric-body">
          <span>根级宪章与设计规格</span>
          <strong>3 <small>份权威源</small></strong>
        </div>
      </div>
      <div class="metric-card" @click="activeGroup = 'skills'">
        <div class="metric-icon" style="color: #f59e0b; background: rgba(245, 158, 11, 0.12)">
          <i class="ri-cpu-line" />
        </div>
        <div class="metric-body">
          <span>统一 Agent 守门员技能</span>
          <strong>9 <small>项核心 Skill</small></strong>
        </div>
      </div>
      <div class="metric-card" @click="selectDoc('std-03-privacy-security')">
        <div class="metric-icon" style="color: #ef4444; background: rgba(239, 68, 68, 0.12)">
          <i class="ri-shield-keyhole-line" />
        </div>
        <div class="metric-body">
          <span>数据安全与部署红线</span>
          <strong>L1–L4 <small>零容忍</small></strong>
        </div>
      </div>
    </section>

    <!-- Collapsible Interactive Quick Reference Board -->
    <section v-if="showQuickBoard" class="quick-board" aria-label="核心红线与令牌速查看板">
      <div class="quick-board-grid">
        <!-- Card 1: Three Environments & Commands -->
        <div class="board-panel">
          <div class="panel-head">
            <h3><i class="ri-rocket-2-line" /> 三套环境隔离与构建铁律</h3>
            <button type="button" class="link-btn" @click="selectDoc('std-06-deploy-ops')">查看 STD-06 详情 →</button>
          </div>
          <div class="env-table-wrap">
            <table class="mini-table">
              <thead>
                <tr>
                  <th>环境</th>
                  <th>域名与源码</th>
                  <th>构建命令</th>
                  <th>部署规则</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="env-tag stg">Staging 测试</span></td>
                  <td><code>staging.subskin.cn</code><br><small>web/app/</small></td>
                  <td><code>npm run build</code></td>
                  <td>每次改动<strong>立即自动部署</strong>并记入 DEPLOY_LOG</td>
                </tr>
                <tr>
                  <td><span class="env-tag prod">Prod 正式</span></td>
                  <td><code>subskin.cn</code><br><small>web/app/</small></td>
                  <td><code>npm run deploy:prod</code></td>
                  <td><strong>严禁擅自发布</strong>，需用户确认后全量同步</td>
                </tr>
                <tr>
                  <td><span class="env-tag adm">Admin 后台</span></td>
                  <td><code>admin.subskin.cn</code><br><small>web/admin/</small></td>
                  <td><code>npx vite build</code></td>
                  <td>独立应用，修改后直接构建生效，严禁混发</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Card 2: Design System Swatches & Tokens -->
        <div class="board-panel">
          <div class="panel-head">
            <h3><i class="ri-palette-line" /> Cursor & GitHub × 医疗温度设计令牌</h3>
            <button type="button" class="link-btn" @click="selectDoc('std-02-ui-design')">查看 STD-02 详情 →</button>
          </div>
          <div class="swatch-grid">
            <div v-for="swatch in designSwatches" :key="swatch.token" class="swatch-item" @click="copyText(swatch.token, `已复制令牌 ${swatch.token}`)">
              <span class="swatch-color" :style="{ background: swatch.hex }" />
              <div class="swatch-info">
                <strong>{{ swatch.label }}</strong>
                <code>{{ swatch.token }} · {{ swatch.hex }}</code>
              </div>
            </div>
          </div>
          <div class="token-pills">
            <span>容器宽度：<code>.page-wide</code> (80rem) / <code>.page</code> (72rem) / <code>.page-narrow</code> (48rem)</span>
            <span>图标唯一标准：<code>RemixIcon (ri-*)</code></span>
            <span>Canvas 圆角：<code>traceRoundedRect()</code> (禁用原生 roundRect)</span>
          </div>
        </div>

        <!-- Card 3: Canonical Site Modules (from site-modules.json) -->
        <div class="board-panel">
          <div class="panel-head">
            <h3><i class="ri-route-line" /> 全站模块唯一命名源 (site-modules.json)</h3>
            <button type="button" class="link-btn" @click="selectDoc('std-01-product-ux')">查看 STD-01 详情 →</button>
          </div>
          <div class="module-chips">
            <div v-for="mod in CANONICAL_SITE_MODULES" :key="mod.path" class="module-chip">
              <i :class="mod.icon" />
              <div>
                <div class="module-chip-title">
                  <strong>{{ mod.label }}</strong>
                  <code>{{ mod.path }}</code>
                  <span v-if="mod.nav_hidden" class="hidden-pill">主导航隐藏</span>
                </div>
                <p>{{ mod.desc }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Card 4: L1-L4 Privacy & Security Lifelines -->
        <div class="board-panel">
          <div class="panel-head">
            <h3><i class="ri-shield-keyhole-line" /> L1–L4 隐私分级与后端架构红线</h3>
            <button type="button" class="link-btn" @click="selectDoc('std-03-privacy-security')">查看 STD-03 详情 →</button>
          </div>
          <ul class="lifeline-list">
            <li><span class="lvl l4">L4 极高机密</span> 密码 (bcrypt)、JWT、API Key — 严禁入 Git、严禁入日志与任何响应。</li>
            <li><span class="lvl l3">L3 高敏个人</span> 手机号 (<code>138****1234</code>)、邮箱、白斑原图、化验单 — 强制脱敏与所有者鉴权。</li>
            <li><span class="lvl l2">L2 社区档案</span> 昵称、帖子、报告分享 — 颗粒度授权 (<code>UserConsent</code>) + 不可篡改 <code>AuditLog</code>。</li>
            <li><span class="lvl warn">反逻辑警示</span> 数据库 <code>privacy_mode=True</code> 表示<strong>公开可被发现</strong>，新代码一律优先用 <code>is_discoverable</code>。</li>
            <li><span class="lvl arch">三层纯净性</span> <code>api → services → models/utils</code>；Service 层严禁导入 FastAPI，严禁向客户端返回 <code>str(e)</code>。</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- Filter & Search Bar -->
    <section class="toolbar-bar" aria-label="文档筛选与搜索">
      <div class="group-tabs" role="tablist">
        <button
          type="button"
          class="group-tab"
          :class="{ active: activeGroup === 'all' }"
          @click="activeGroup = 'all'"
        >
          全部文档 <span>{{ DEV_STANDARD_DOCS.length }}</span>
        </button>
        <button
          v-for="grp in DOC_GROUPS"
          :key="grp.key"
          type="button"
          class="group-tab"
          :class="{ active: activeGroup === grp.key }"
          @click="activeGroup = grp.key"
        >
          <i :class="grp.icon" />
          {{ grp.label }}
          <span>{{ countByGroup(grp.key) }}</span>
        </button>
      </div>

      <div class="search-controls">
        <div class="search-input-wrap">
          <i class="ri-search-line" />
          <input
            v-model="searchQuery"
            type="search"
            placeholder="搜索规范全文（如：roundRect、privacy_mode、Staging、AuditLog、100dvh）…"
            aria-label="搜索开发文档全文"
          />
          <button v-if="searchQuery" type="button" class="clear-btn" @click="searchQuery = ''">
            <i class="ri-close-circle-fill" />
          </button>
        </div>
        <button type="button" class="outline-btn focus-btn" @click="focusedMode = !focusedMode">
          <i :class="focusedMode ? 'ri-layout-left-line' : 'ri-fullscreen-line'" />
          <span>{{ focusedMode ? '显示模块栏' : '专注阅读' }}</span>
        </button>
      </div>
    </section>

    <!-- Main Workspace: Left Sidebar + Center Markdown Reader + Right TOC -->
    <div class="docs-workspace" :class="{ 'focused-mode': focusedMode, 'mobile-reading': mobileReading }">
      <!-- Left Document Navigation Rail -->
      <aside v-show="!focusedMode" class="docs-sidebar" aria-label="开发规范模块列表">
        <div v-if="filteredGroups.length === 0" class="empty-sidebar">
          <i class="ri-file-search-line" />
          <p>未找到包含「{{ searchQuery }}」的规范文档</p>
          <button type="button" class="outline-btn" @click="searchQuery = ''; activeGroup = 'all'">重置筛选</button>
        </div>

        <div v-for="group in filteredGroups" :key="group.key" class="sidebar-group">
          <div class="sidebar-group-header">
            <i :class="group.icon" />
            <span>{{ group.label }}</span>
          </div>
          <div class="sidebar-doc-list">
            <button
              v-for="doc in group.docs"
              :key="doc.id"
              type="button"
              class="sidebar-doc-card"
              :class="{ active: currentDoc.id === doc.id }"
              @click="selectDoc(doc.id)"
            >
              <div class="doc-card-top">
                <span class="doc-code" :style="{ color: doc.badgeColor, borderColor: doc.badgeColor + '44', background: doc.badgeColor + '14' }">
                  {{ doc.code }}
                </span>
                <span class="doc-badge">{{ doc.badge }}</span>
                <span v-if="searchQuery && getMatchCount(doc) > 0" class="hit-pill">
                  {{ getMatchCount(doc) }} 处匹配
                </span>
              </div>
              <div class="doc-card-title">
                <i :class="doc.icon" />
                <span>{{ doc.title }}</span>
              </div>
              <p class="doc-card-summary">{{ doc.summary }}</p>
              <div class="doc-card-tags">
                <span v-for="tag in doc.highlights.slice(0, 3)" :key="tag" class="mini-tag">{{ tag }}</span>
              </div>
            </button>
          </div>
        </div>
      </aside>

      <!-- Center Reader Area -->
      <article class="docs-reader" aria-label="规范正文阅读器">
        <header class="reader-top">
          <div class="reader-top-bar">
            <button type="button" class="mobile-back-btn outline-btn" @click="mobileReading = false">
              <i class="ri-arrow-left-line" /> 返回模块列表
            </button>
            <div class="reader-badges">
              <span class="reader-code" :style="{ background: currentDoc.badgeColor }">{{ currentDoc.code }}</span>
              <span class="reader-group-badge">{{ currentDoc.badge }}</span>
              <span class="reader-date"><i class="ri-calendar-check-line" /> 更新于 {{ currentDoc.updatedAt }}</span>
            </div>
            <div class="reader-btn-group">
              <button type="button" class="outline-btn" @click="rawMode = !rawMode">
                <i :class="rawMode ? 'ri-article-line' : 'ri-code-view'" />
                <span>{{ rawMode ? '排版阅读' : 'Markdown 源码' }}</span>
              </button>
              <button type="button" class="outline-btn" @click="copyText(currentDoc.repoPath, '仓库文件路径已复制')">
                <i class="ri-file-copy-line" />
                <span>复制路径</span>
              </button>
              <button type="button" class="outline-btn" @click="copyText(currentDoc.content, `已复制《${currentDoc.shortTitle}》全文`)">
                <i class="ri-clipboard-line" />
                <span>复制全文</span>
              </button>
            </div>
          </div>

          <h2 class="reader-title">{{ currentDoc.title }}</h2>
          <p class="reader-summary">{{ currentDoc.summary }}</p>

          <div class="reader-repo-bar">
            <span class="repo-label"><i class="ri-git-repository-line" /> 仓库权威源路径：</span>
            <code>/root/subskin/{{ currentDoc.repoPath }}</code>
          </div>

          <!-- Mobile / Compact TOC Selector -->
          <div v-if="renderedDoc.headings.length && !rawMode" class="compact-toc">
            <label for="dev-doc-toc-select"><i class="ri-list-unordered" /> 章节跳转</label>
            <select id="dev-doc-toc-select" @change="scrollToHeading(($event.target as HTMLSelectElement).value)">
              <option value="">选择章节快速定位…</option>
              <option
                v-for="heading in renderedDoc.headings"
                :key="heading.id"
                :value="heading.id"
              >
                {{ '　'.repeat(Math.max(0, Math.min(heading.level - 1, 3))) }}{{ heading.text }}
              </option>
            </select>
          </div>
        </header>

        <div class="reader-body-layout">
          <div ref="readerScrollRef" class="reader-scroll-pane">
            <pre v-if="rawMode" class="raw-markdown">{{ currentDoc.content }}</pre>
            <div
              v-else
              class="markdown-prose"
              @click="handleProseClick"
              v-html="renderedDoc.html"
            />

            <!-- Prev / Next Module Navigation Footer -->
            <footer class="reader-pager">
              <button
                v-if="prevDoc"
                type="button"
                class="pager-btn prev"
                @click="selectDoc(prevDoc.id)"
              >
                <span class="pager-dir"><i class="ri-arrow-left-s-line" /> 上一模块</span>
                <strong>{{ prevDoc.code }} · {{ prevDoc.shortTitle }}</strong>
              </button>
              <div v-else />
              <button
                v-if="nextDoc"
                type="button"
                class="pager-btn next"
                @click="selectDoc(nextDoc.id)"
              >
                <span class="pager-dir">下一模块 <i class="ri-arrow-right-s-line" /></span>
                <strong>{{ nextDoc.code }} · {{ nextDoc.shortTitle }}</strong>
              </button>
            </footer>
          </div>

          <!-- Desktop Sticky Chapter Outline -->
          <aside
            v-if="renderedDoc.headings.length && !rawMode"
            class="reader-outline"
            aria-label="本篇章节目录"
          >
            <div class="outline-title">
              <i class="ri-Bookmark-3-line" />
              <span>本篇章节目录</span>
            </div>
            <nav class="outline-list">
              <button
                v-for="heading in renderedDoc.headings"
                :key="heading.id"
                type="button"
                class="outline-item"
                :class="`level-${heading.level}`"
                @click="scrollToHeading(heading.id)"
              >
                {{ heading.text }}
              </button>
            </nav>
          </aside>
        </div>
      </article>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, useThemeVars } from 'naive-ui'
import {
  AGENT_HANDOVER_PROMPT,
  CANONICAL_SITE_MODULES,
  DEV_STANDARD_DOCS,
  DOC_GROUPS,
  type DevStandardDoc,
  type DocGroupKey,
} from '@/data/dev-standards'
import { renderArchiveMarkdown } from '@/utils/planning-markdown'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const theme = useThemeVars()

const themeStyle = computed(() => ({
  '--doc-panel': theme.value.cardColor,
  '--doc-bg': theme.value.bodyColor,
  '--doc-text': theme.value.textColor1,
  '--doc-muted': theme.value.textColor3,
  '--doc-border': theme.value.borderColor,
  '--doc-accent': '#14b8a6',
  '--doc-accent-bg': 'rgba(20, 184, 166, 0.12)',
}))

const designSwatches = [
  { label: 'Brand Primary 600 (CTA)', token: '--color-primary-600', hex: '#0d9488' },
  { label: 'Brand Primary 500 (Standard)', token: '--color-primary-500', hex: '#14b8a6' },
  { label: 'Brand Primary 700 (Hover)', token: '--color-primary-700', hex: '#0f766e' },
  { label: 'Light Canvas (GitHub 冷白)', token: '--color-bg (Light)', hex: '#f6f8fa' },
  { label: 'Dark Canvas (Cursor 碳黑)', token: '--color-bg (Dark)', hex: '#0b0f17' },
  { label: 'Dark Surface (一级卡片)', token: '--color-surface (Dark)', hex: '#111827' },
]

const activeGroup = ref<'all' | DocGroupKey>('all')
const searchQuery = ref('')
const showQuickBoard = ref(false)
const focusedMode = ref(false)
const rawMode = ref(false)
const mobileReading = ref(false)
const readerScrollRef = ref<HTMLElement | null>(null)

const initialDocId = typeof route.query.doc === 'string' && DEV_STANDARD_DOCS.some(d => d.id === route.query.doc)
  ? route.query.doc
  : DEV_STANDARD_DOCS[0]!.id

const selectedDocId = ref<string>(initialDocId)

const currentDoc = computed<DevStandardDoc>(() => {
  return DEV_STANDARD_DOCS.find(d => d.id === selectedDocId.value) ?? DEV_STANDARD_DOCS[0]!
})

const renderedDoc = computed(() => {
  return renderArchiveMarkdown(currentDoc.value.content, currentDoc.value.repoPath)
})

function countByGroup(groupKey: DocGroupKey): number {
  return DEV_STANDARD_DOCS.filter(d => d.group === groupKey).length
}

function getMatchCount(doc: DevStandardDoc): number {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return 0
  const words = q.split(/\s+/).filter(Boolean)
  const haystack = `${doc.code} ${doc.title} ${doc.summary} ${doc.repoPath} ${doc.content}`.toLowerCase()
  let total = 0
  for (const w of words) {
    let idx = haystack.indexOf(w)
    while (idx !== -1) {
      total++
      idx = haystack.indexOf(w, idx + w.length)
    }
  }
  return total
}

function matchesSearch(doc: DevStandardDoc): boolean {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return true
  const words = q.split(/\s+/).filter(Boolean)
  const haystack = `${doc.code} ${doc.title} ${doc.summary} ${doc.repoPath} ${doc.highlights.join(' ')} ${doc.content}`.toLowerCase()
  return words.every(w => haystack.includes(w))
}

const filteredGroups = computed(() => {
  return DOC_GROUPS
    .filter(grp => activeGroup.value === 'all' || activeGroup.value === grp.key)
    .map(grp => ({
      ...grp,
      docs: DEV_STANDARD_DOCS.filter(doc => doc.group === grp.key && matchesSearch(doc)),
    }))
    .filter(grp => grp.docs.length > 0)
})

const flatFilteredDocs = computed(() => {
  return filteredGroups.value.flatMap(g => g.docs)
})

const prevDoc = computed(() => {
  const list = flatFilteredDocs.value
  const idx = list.findIndex(d => d.id === currentDoc.value.id)
  return idx > 0 ? list[idx - 1] : null
})

const nextDoc = computed(() => {
  const list = flatFilteredDocs.value
  const idx = list.findIndex(d => d.id === currentDoc.value.id)
  return idx >= 0 && idx < list.length - 1 ? list[idx + 1] : null
})

async function selectDoc(id: string) {
  selectedDocId.value = id
  rawMode.value = false
  mobileReading.value = true
  router.replace({ query: { ...route.query, doc: id } })
  await nextTick()
  if (readerScrollRef.value) {
    readerScrollRef.value.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

watch(() => route.query.doc, (newDocId) => {
  if (typeof newDocId === 'string' && DEV_STANDARD_DOCS.some(d => d.id === newDocId)) {
    selectedDocId.value = newDocId
  }
})

function scrollToHeading(headingId: string) {
  if (!headingId || !readerScrollRef.value) return
  const target = readerScrollRef.value.querySelector<HTMLElement>(`#${CSS.escape(headingId)}`)
  if (target) {
    const top = readerScrollRef.value.scrollTop + target.getBoundingClientRect().top - readerScrollRef.value.getBoundingClientRect().top - 16
    readerScrollRef.value.scrollTo({ top, behavior: 'smooth' })
  }
}

function handleProseClick(event: MouseEvent) {
  if (!(event.target instanceof Element)) return
  const link = event.target.closest('a')
  if (!link || link.target === '_blank') return
  event.preventDefault()

  const docPath = link.dataset.document
  if (docPath) {
    const normalized = docPath.replace(/^\/+/, '')
    const matched = DEV_STANDARD_DOCS.find(
      d => d.repoPath.toLowerCase() === normalized.toLowerCase() ||
           d.repoPath.toLowerCase().endsWith('/' + normalized.split('/').pop()?.toLowerCase())
    )
    if (matched) {
      selectDoc(matched.id)
      return
    }
  }

  const section = link.dataset.section
  if (section) {
    try {
      const requested = decodeURIComponent(section)
      const heading = renderedDoc.value.headings.find(
        h => h.id === requested ||
             h.text.toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu, '').replace(/\s/g, '-') === requested
      )
      if (heading) scrollToHeading(heading.id)
    } catch {
      // ignore malformed URI
    }
  }
}

async function copyText(text: string, successMsg: string) {
  try {
    await navigator.clipboard.writeText(text)
    message.success(successMsg)
  } catch {
    message.warning('复制失败，请手动选中复制')
  }
}

async function copyHandoverPrompt() {
  await copyText(
    AGENT_HANDOVER_PROMPT,
    '已复制新 Agent 进场接手指令！可直接粘贴发送给 Cursor / Claude Code / OpenCode / Hermes 等任何 Agent'
  )
}
</script>

<style scoped>
.dev-docs-page {
  max-width: 1520px;
  margin: 0 auto;
  color: var(--doc-text);
  padding-bottom: 32px;
}

/* ── Hero Header ── */
.docs-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  padding: 22px 24px;
  margin-bottom: 16px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.22) 0%, rgba(30, 41, 59, 0.85) 60%, rgba(99, 102, 241, 0.16) 100%);
  border: 1px solid rgba(20, 184, 166, 0.28);
}

.eyebrow-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 8px;
}

.eyebrow-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #5eead4;
  background: rgba(20, 184, 166, 0.18);
  border: 1px solid rgba(94, 234, 212, 0.3);
}

.eyebrow-meta {
  font-size: 12px;
  color: #94a3b8;
}

.eyebrow-meta code {
  color: #e2e8f0;
  background: rgba(15, 23, 42, 0.6);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.docs-hero h1 {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 8px;
  color: #f8fafc;
  letter-spacing: -0.01em;
}

.hero-desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: #cbd5e1;
  max-width: 880px;
}

.hero-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}

.primary-action-btn,
.secondary-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  padding: 8px 16px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.primary-action-btn {
  background: #0d9488;
  color: #ffffff;
  border: 1px solid #14b8a6;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.primary-action-btn:hover {
  background: #0f766e;
}

.secondary-action-btn {
  background: rgba(15, 23, 42, 0.65);
  color: #e2e8f0;
  border: 1px solid rgba(148, 163, 184, 0.28);
}

.secondary-action-btn:hover {
  border-color: #5eead4;
  color: #5eead4;
}

/* ── Metrics Row ── */
.docs-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  background: var(--doc-panel);
  border: 1px solid var(--doc-border);
  border-radius: 12px;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}

.metric-card:hover {
  border-color: rgba(20, 184, 166, 0.5);
  transform: translateY(-1px);
}

.metric-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.metric-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.metric-body span {
  font-size: 12px;
  color: var(--doc-muted);
}

.metric-body strong {
  font-size: 20px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.metric-body small {
  font-size: 12px;
  font-weight: 400;
  color: var(--doc-muted);
}

/* ── Quick Reference Board ── */
.quick-board {
  margin-bottom: 18px;
  padding: 18px;
  background: var(--doc-panel);
  border: 1px solid rgba(20, 184, 166, 0.35);
  border-radius: 14px;
}

.quick-board-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.board-panel {
  background: var(--doc-bg);
  border: 1px solid var(--doc-border);
  border-radius: 10px;
  padding: 14px 16px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.panel-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
  color: #f8fafc;
}

.panel-head h3 i {
  color: #2dd4bf;
}

.link-btn {
  border: 0;
  background: transparent;
  color: #2dd4bf;
  font-size: 12px;
  cursor: pointer;
}

.env-table-wrap {
  overflow-x: auto;
}

.mini-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.mini-table th,
.mini-table td {
  border: 1px solid var(--doc-border);
  padding: 7px 9px;
  text-align: left;
}

.mini-table th {
  background: rgba(255, 255, 255, 0.04);
  color: #cbd5e1;
}

.env-tag {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 600;
}

.env-tag.stg { background: rgba(59, 130, 246, 0.18); color: #93c5fd; }
.env-tag.prod { background: rgba(16, 185, 129, 0.18); color: #6ee7b7; }
.env-tag.adm { background: rgba(168, 85, 247, 0.18); color: #d8b4fe; }

.swatch-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.swatch-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid var(--doc-border);
  cursor: pointer;
}

.swatch-color {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  flex-shrink: 0;
}

.swatch-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.swatch-info strong {
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.swatch-info code {
  font-size: 10px;
  color: var(--doc-muted);
}

.token-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 11px;
  color: #94a3b8;
}

.token-pills span {
  background: rgba(255, 255, 255, 0.04);
  padding: 3px 8px;
  border-radius: 6px;
}

.module-chips {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  max-height: 195px;
  overflow-y: auto;
}

.module-chip {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 7px 9px;
  border: 1px solid var(--doc-border);
  border-radius: 8px;
  font-size: 11px;
}

.module-chip > i {
  font-size: 16px;
  color: #2dd4bf;
  margin-top: 2px;
}

.module-chip-title {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.module-chip-title code {
  color: #5eead4;
  font-size: 10px;
}

.hidden-pill {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(245, 158, 11, 0.16);
  color: #fcd34d;
}

.module-chip p {
  margin: 3px 0 0;
  color: var(--doc-muted);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.lifeline-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
  line-height: 1.5;
}

.lvl {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  margin-right: 6px;
}

.lvl.l4 { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
.lvl.l3 { background: rgba(249, 115, 22, 0.2); color: #fdba74; }
.lvl.l2 { background: rgba(234, 179, 8, 0.2); color: #fde047; }
.lvl.warn { background: rgba(236, 72, 153, 0.2); color: #f9a8d4; }
.lvl.arch { background: rgba(59, 130, 246, 0.2); color: #93c5fd; }

/* ── Filter & Search Toolbar ── */
.toolbar-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.group-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.group-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 38px;
  padding: 6px 13px;
  border-radius: 9px;
  border: 1px solid var(--doc-border);
  background: var(--doc-panel);
  color: var(--doc-muted);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.group-tab span {
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.group-tab.active {
  color: #5eead4;
  border-color: rgba(20, 184, 166, 0.5);
  background: rgba(20, 184, 166, 0.12);
}

.search-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 280px;
  max-width: 520px;
}

.search-input-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
}

.search-input-wrap > i {
  position: absolute;
  left: 12px;
  color: var(--doc-muted);
  font-size: 15px;
  pointer-events: none;
}

.search-input-wrap input {
  width: 100%;
  min-width: 0;
  min-height: 38px;
  padding: 7px 34px 7px 36px;
  border-radius: 9px;
  border: 1px solid var(--doc-border);
  background: var(--doc-panel);
  color: var(--doc-text);
  font-size: 13px;
}

.search-input-wrap input:focus {
  outline: none;
  border-color: #14b8a6;
}

.clear-btn {
  position: absolute;
  right: 8px;
  border: 0;
  background: transparent;
  color: var(--doc-muted);
  cursor: pointer;
}

.outline-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 38px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--doc-border);
  background: transparent;
  color: var(--doc-text);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.outline-btn:hover {
  border-color: #2dd4bf;
  color: #2dd4bf;
}

/* ── Main Workspace ── */
.docs-workspace {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: 16px;
  align-items: flex-start;
}

.docs-workspace.focused-mode {
  grid-template-columns: minmax(0, 1fr);
}

.docs-sidebar {
  background: var(--doc-panel);
  border: 1px solid var(--doc-border);
  border-radius: 14px;
  padding: 12px;
  max-height: 78dvh;
  overflow-y: auto;
}

.empty-sidebar {
  padding: 36px 16px;
  text-align: center;
  color: var(--doc-muted);
}

.empty-sidebar i {
  font-size: 32px;
  color: #2dd4bf;
}

.sidebar-group + .sidebar-group {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--doc-border);
}

.sidebar-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #94a3b8;
  text-transform: uppercase;
}

.sidebar-doc-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sidebar-doc-card {
  width: 100%;
  text-align: left;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--doc-border);
  background: var(--doc-bg);
  color: var(--doc-text);
  cursor: pointer;
  transition: all 0.15s ease;
}

.sidebar-doc-card:hover {
  border-color: rgba(20, 184, 166, 0.45);
}

.sidebar-doc-card.active {
  border-color: #14b8a6;
  background: rgba(20, 184, 166, 0.10);
  box-shadow: inset 3px 0 0 #14b8a6;
}

.doc-card-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.doc-code {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid;
  font-family: ui-monospace, monospace;
}

.doc-badge {
  font-size: 11px;
  color: var(--doc-muted);
}

.hit-pill {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.2);
  color: #5eead4;
}

.doc-card-title {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  margin-bottom: 5px;
}

.doc-card-title i {
  color: #2dd4bf;
  margin-top: 2px;
  flex-shrink: 0;
}

.doc-card-summary {
  margin: 0 0 8px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--doc-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.doc-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mini-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
  color: #cbd5e1;
}

/* ── Reader Area ── */
.docs-reader {
  background: var(--doc-panel);
  border: 1px solid var(--doc-border);
  border-radius: 14px;
  overflow: hidden;
  min-width: 0;
}

.reader-top {
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--doc-border);
  background: rgba(15, 23, 42, 0.35);
}

.reader-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.mobile-back-btn {
  display: none;
}

.reader-badges {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.reader-code {
  padding: 2px 8px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 700;
  color: #ffffff;
  font-family: ui-monospace, monospace;
}

.reader-group-badge {
  font-size: 12px;
  color: #5eead4;
  font-weight: 600;
}

.reader-date {
  font-size: 12px;
  color: var(--doc-muted);
  font-variant-numeric: tabular-nums;
}

.reader-btn-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.reader-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 8px;
  line-height: 1.4;
}

.reader-summary {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
  color: #cbd5e1;
}

.reader-repo-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--doc-bg);
  border: 1px solid var(--doc-border);
  font-size: 12px;
}

.repo-label {
  color: var(--doc-muted);
}

.reader-repo-bar code {
  color: #5eead4;
  font-family: ui-monospace, monospace;
  overflow-wrap: anywhere;
}

.compact-toc {
  display: none;
  margin-top: 12px;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.compact-toc select {
  flex: 1;
  min-width: 0;
  min-height: 38px;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--doc-border);
  background: var(--doc-bg);
  color: var(--doc-text);
}

.reader-body-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 230px;
  align-items: flex-start;
}

.reader-scroll-pane {
  padding: 24px 28px;
  max-height: 70dvh;
  overflow-y: auto;
  overflow-x: hidden;
  min-width: 0;
}

.raw-markdown {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 12.5px;
  line-height: 1.75;
  font-family: ui-monospace, monospace;
}

/* ── Markdown Prose Styling ── */
.markdown-prose {
  font-size: 14px;
  line-height: 1.85;
  color: var(--doc-text);
  overflow-wrap: anywhere;
}

.markdown-prose :deep(h1),
.markdown-prose :deep(h2),
.markdown-prose :deep(h3),
.markdown-prose :deep(h4) {
  line-height: 1.45;
  font-weight: 650;
  color: #f8fafc;
  margin: 1.5em 0 0.65em;
}

.markdown-prose :deep(h1) {
  font-size: 22px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--doc-border);
}

.markdown-prose :deep(h2) {
  font-size: 18px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
  color: #5eead4;
}

.markdown-prose :deep(h3) {
  font-size: 15.5px;
}

.markdown-prose :deep(p) {
  margin: 0.75em 0;
}

.markdown-prose :deep(ul),
.markdown-prose :deep(ol) {
  padding-left: 22px;
  margin: 0.85em 0;
}

.markdown-prose :deep(ul) { list-style: disc; }
.markdown-prose :deep(ol) { list-style: decimal; }

.markdown-prose :deep(li) {
  margin: 0.35em 0;
}

.markdown-prose :deep(blockquote) {
  border-left: 3px solid #14b8a6;
  background: rgba(20, 184, 166, 0.08);
  padding: 10px 16px;
  margin: 14px 0;
  border-radius: 0 8px 8px 0;
}

.markdown-prose :deep(pre) {
  white-space: pre;
  overflow-x: auto;
  max-width: 100%;
  background: #090d16;
  border: 1px solid var(--doc-border);
  padding: 14px 16px;
  border-radius: 9px;
  font-size: 12px;
  line-height: 1.65;
  margin: 14px 0;
}

.markdown-prose :deep(code) {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 0.9em;
  background: rgba(255, 255, 255, 0.07);
  padding: 2px 5px;
  border-radius: 4px;
}

.markdown-prose :deep(pre code) {
  background: transparent;
  padding: 0;
}

.markdown-prose :deep(table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 12.5px;
}

.markdown-prose :deep(th),
.markdown-prose :deep(td) {
  border: 1px solid var(--doc-border);
  padding: 9px 12px;
  min-width: 95px;
  text-align: left;
  vertical-align: top;
}

.markdown-prose :deep(th) {
  background: rgba(20, 184, 166, 0.12);
  color: #f8fafc;
  font-weight: 600;
}

.markdown-prose :deep(a) {
  color: #2dd4bf;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.markdown-prose :deep(hr) {
  border: 0;
  border-top: 1px solid var(--doc-border);
  margin: 24px 0;
}

/* ── Pager Footer ── */
.reader-pager {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid var(--doc-border);
}

.pager-btn {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--doc-border);
  background: var(--doc-bg);
  color: var(--doc-text);
  cursor: pointer;
  text-align: left;
}

.pager-btn.next {
  text-align: right;
}

.pager-btn:hover {
  border-color: #14b8a6;
}

.pager-dir {
  font-size: 11px;
  color: var(--doc-muted);
}

.pager-btn strong {
  font-size: 13px;
  color: #5eead4;
}

/* ── Right Sticky Outline ── */
.reader-outline {
  border-left: 1px solid var(--doc-border);
  padding: 16px 14px;
  max-height: 70dvh;
  overflow-y: auto;
}

.outline-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  margin-bottom: 10px;
  text-transform: uppercase;
}

.outline-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.outline-item {
  border: 0;
  background: transparent;
  color: var(--doc-muted);
  text-align: left;
  font-size: 12px;
  line-height: 1.45;
  padding: 5px 8px;
  border-radius: 6px;
  cursor: pointer;
}

.outline-item:hover {
  color: #5eead4;
  background: rgba(20, 184, 166, 0.1);
}

.outline-item.level-2 { font-weight: 600; color: #e2e8f0; }
.outline-item.level-3 { padding-left: 18px; font-size: 11.5px; }
.outline-item.level-4 { padding-left: 26px; font-size: 11px; }

/* ── Responsive Breakpoints ── */
@media (max-width: 1280px) {
  .reader-body-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .reader-outline {
    display: none;
  }
  .compact-toc {
    display: flex;
  }
}

@media (max-width: 1024px) {
  .docs-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .quick-board-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .docs-workspace {
    grid-template-columns: minmax(0, 1fr);
  }
  .docs-workspace.mobile-reading .docs-sidebar {
    display: none;
  }
  .docs-workspace:not(.mobile-reading) .docs-reader {
    display: none;
  }
  .mobile-back-btn {
    display: inline-flex;
  }
  .focus-btn {
    display: none;
  }
}

@media (max-width: 767px) {
  .docs-hero {
    flex-direction: column;
    padding: 16px;
  }
  .hero-actions {
    width: 100%;
    flex-direction: column;
  }
  .docs-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .metric-card {
    padding: 10px 12px;
  }
  .swatch-grid,
  .module-chips,
  .reader-pager {
    grid-template-columns: minmax(0, 1fr);
  }
  .reader-top {
    padding: 14px 16px;
  }
  .reader-scroll-pane {
    padding: 16px;
  }
}
</style>
