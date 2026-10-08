<script setup lang="ts">
/**
 * SkinReportCreatePage — 生成白斑变化对比报告
 *
 * 从用户的所有日记照片中选择 ≥2 张，AI 生成对比分析报告。
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { communityApi } from '@/api/community'
import type { Post, PostImage } from '@/types'
import { createComparisonReport, reorderPhotos, deletePhoto } from '@/api/skin_report'
import { toProtectedFileUrl } from '@/utils/file-url'
import { PART_LABELS } from '@/constants/bodySites'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ComparisonPhotoUploader from '@/components/report/ComparisonPhotoUploader.vue'
import PhotoMetaEditor from '@/components/report/PhotoMetaEditor.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const MAX_SELECT = 4

const router = useRouter()
const route = useRoute()
const toast = useToast()
const authStore = useAuthStore()
const posts = ref<Post[]>([])
const loading = ref(false)
const generating = ref(false)
const selected = ref<Set<number>>(new Set())
const editingImage = ref<PostImage | null>(null)
const showEditor = ref(false)
const deleting = ref(false)
const deleteTarget = ref<PostImage | null>(null)
const confirmDeleteVisible = ref(false)

// 对比部位：从测评页带入选中的身体部位（不再提供选择器，仅左上角展示）
const reportSite = ref<string>(typeof route.query.site === 'string' ? route.query.site : '')

function openEditor(img: PostImage) {
  editingImage.value = img
  showEditor.value = true
}

// ── 照片墙：微信朋友圈式长按拖动排序 ──
const draggingIndex = ref<number | null>(null)

let pressTimer: number | null = null
let pressStart: { x: number; y: number } | null = null
let dragFrom: number | null = null
let suppressNextClick = false

function onTilePointerDown(e: PointerEvent, item: ImageItem) {
  // 日期按钮 / 删除按钮上的按下不进入拖动或长按
  const target = e.target as HTMLElement | null
  if (target?.closest('.create-grid__date-btn, .create-grid__x')) return
  pressStart = { x: e.clientX, y: e.clientY }
  suppressNextClick = false
  if (pressTimer) window.clearTimeout(pressTimer)
  // 长按 350ms 进入拖动（微信朋友圈节奏）
  pressTimer = window.setTimeout(() => {
    pressTimer = null
    suppressNextClick = true
    dragFrom = wallItems.value.findIndex((x) => x.image.id === item.image.id)
    draggingIndex.value = dragFrom
    document.body.style.overflow = 'hidden'
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) navigator.vibrate(30)
  }, 350)
}

function onTilePointerMove(e: PointerEvent) {
  // 未进入拖动前：移动超过阈值视为滚动，取消长按
  if (pressTimer && pressStart) {
    if (Math.abs(e.clientX - pressStart.x) > 10 || Math.abs(e.clientY - pressStart.y) > 10) cancelPress()
    return
  }
  if (dragFrom === null || draggingIndex.value === null) return
  const target = document.elementFromPoint(e.clientX, e.clientY)
  const cell = target?.closest?.('[data-widx]') as HTMLElement | null
  if (!cell) return
  const to = Number(cell.dataset.widx)
  if (Number.isNaN(to) || to === dragFrom) return
  const [moved] = wallItems.value.splice(dragFrom, 1)
  wallItems.value.splice(to, 0, moved)
  dragFrom = to
  draggingIndex.value = to
}

function onTilePointerEnd() {
  if (dragFrom !== null) {
    endDrag()
    void saveWallOrder()
  } else {
    cancelPress()
  }
}

function endDrag() {
  dragFrom = null
  draggingIndex.value = null
  document.body.style.overflow = ''
}

function cancelPress() {
  if (pressTimer) {
    window.clearTimeout(pressTimer)
    pressTimer = null
  }
  pressStart = null
}

async function saveWallOrder() {
  const ids = wallItems.value.map((x) => x.image.id)
  try {
    await reorderPhotos(ids)
    toast.show('照片顺序已保存', 'success')
    await load()
  } catch {
    toast.show('保存顺序失败，请重试', 'error')
  }
}

function handlePickClick(img: PostImage) {
  if (suppressNextClick) {
    suppressNextClick = false
    return
  }
  toggle(img.id)
}

// ── 照片删除：右上角 × ──
function askDelete(img: PostImage) {
  deleteTarget.value = img
  confirmDeleteVisible.value = true
}

async function confirmDelete() {
  const img = deleteTarget.value
  if (!img || deleting.value) return
  deleting.value = true
  try {
    await deletePhoto(img.id)
    const s = new Set(selected.value)
    s.delete(img.id)
    selected.value = s
    toast.show('照片已删除', 'success')
    confirmDeleteVisible.value = false
    await load()
  } catch (err: any) {
    toast.show(err?.response?.data?.detail || '删除失败，请重试', 'error')
  } finally {
    deleting.value = false
  }
}

onUnmounted(() => {
  cancelPress()
  document.body.style.overflow = ''
})

interface ImageItem {
  image: PostImage
  post: Post
}

const allImages = computed<ImageItem[]>(() => {
  const imgs: ImageItem[] = []
  for (const p of posts.value) {
    for (const im of p.images || []) {
      imgs.push({ image: im, post: p })
    }
  }
  return imgs.sort((a, b) => {
    const d = (b.image.capture_date || '').localeCompare(a.image.capture_date || '')
    if (d !== 0) return d
    return (a.image.order ?? 0) - (b.image.order ?? 0)
  })
})

/** 照片墙顺序（长按拖动时本地交换，松手后保存） */
const wallItems = ref<ImageItem[]>([])

watch(
  () => allImages.value,
  (v) => {
    wallItems.value = v.map((x) => x)
  },
  { immediate: true },
)

const selectedSiteCount = computed(() => {
  const selectedImages = allImages.value.filter((item) => selected.value.has(item.image.id))
  return new Set(selectedImages.map((item) => item.image.body_site).filter(Boolean)).size
})

const hasMixedSelectedSites = computed(
  () => selected.value.size >= 2 && selectedSiteCount.value > 1,
)

// 选择了报告级部位时，以报告级部位为准；否则要求所选照片部位一致
const canGenerate = computed(
  () =>
    selected.value.size >= 2 &&
    (!!reportSite.value || !hasMixedSelectedSites.value),
)

/** 请求保护：15 秒未返回即失败提示，避免整页加载态一直转圈 */
function withTimeout<T>(p: Promise<T>, ms = 15000): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('timeout')), ms)
    p.then(
      (v) => { clearTimeout(t); resolve(v) },
      (e) => { clearTimeout(t); reject(e) },
    )
  })
}

async function load() {
  if (!authStore.isLoggedIn) {
    authStore.showLoginModal = true
    return
  }
  loading.value = true
  try {
    const result = await withTimeout(communityApi.getMyDiaries(50, 0))
    posts.value = result.items
  } catch {
    toast.show('加载照片失败，请重试', 'error')
  } finally {
    loading.value = false
  }
}

function toggle(id: number) {
  if (!selected.value.has(id) && selected.value.size >= MAX_SELECT) {
    toast.warning(`最多选择 ${MAX_SELECT} 张照片`)
    return
  }
  const s = new Set(selected.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selected.value = s
}

function protectedUrl(url: string) {
  return toProtectedFileUrl(url) || url
}

function siteLabel(site: string | null | undefined) {
  if (!site) return '未标注'
  return PART_LABELS[site] || site
}

function orderOf(id: number): number | null {
  if (!selected.value.has(id)) return null
  return Array.from(selected.value).indexOf(id) + 1
}

async function generate() {
  if (!canGenerate.value) return
  if (!authStore.isLoggedIn) {
    authStore.showLoginModal = true
    return
  }
  generating.value = true
  try {
    const { data } = await createComparisonReport({
      image_ids: Array.from(selected.value),
      body_site: reportSite.value || undefined,
    })
    toast.show('已开始生成，约需 1-2 分钟', 'success')
    router.replace({ name: 'skin-report-view', params: { id: data.id } })
  } catch (e: any) {
    toast.show(e.response?.data?.detail || '生成失败，请重试', 'error')
  } finally {
    generating.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="create-page">
    <header class="create-header">
      <div class="create-header__inner">
        <button class="create-back" @click="router.back()">
          <i class="ri-arrow-left-s-line"></i>
        </button>
        <h1 class="create-header__title">白斑对比报告</h1>
        <!-- 对比部位：测评页已选择，仅在左上角展示 -->
        <span v-if="reportSite" class="create-header__site">
          <i class="ri-focus-3-line"></i>{{ PART_LABELS[reportSite] || reportSite }}
        </span>
      </div>
    </header>

    <main class="create-main">
      <div class="create-intro">
        <h2>选择照片生成对比报告</h2>
      </div>

      <LoadingSpinner v-if="loading" message="加载照片中..." />

      <EmptyState
        v-else-if="!authStore.isLoggedIn"
        icon="ri-lock-line"
        title="登录后生成白斑报告"
        description="白斑照片和报告属于个人健康数据，需要登录后访问"
        action-label="登录 / 注册"
        @action="authStore.showLoginModal = true"
      />

      <template v-else>
        <EmptyState
          v-if="allImages.length === 0"
          icon="ri-image-2-line"
          title="还没有照片"
          description="在下方上传白斑照片，或到分享发布「仅自己可见」的图文记录"
        />

        <!-- 照片墙：2 列（每行 2 张）；长按拖动排序（微信朋友圈式）、点日期改日期、右上角 × 删除 -->
        <div v-else class="create-grid">
          <div
            v-for="(item, i) in wallItems"
            :key="item.image.id"
            class="create-grid__item"
            :class="{
              'create-grid__item--selected': selected.has(item.image.id),
              'create-grid__item--drag': draggingIndex === i,
            }"
            :data-widx="i"
            @pointerdown="onTilePointerDown($event, item)"
            @pointermove="onTilePointerMove"
            @pointerup="onTilePointerEnd"
            @pointerleave="onTilePointerEnd"
            @pointercancel="onTilePointerEnd"
          >
            <button
              type="button"
              class="create-grid__pick"
              :aria-pressed="selected.has(item.image.id)"
              @click="handlePickClick(item.image)"
            >
              <img :src="protectedUrl(item.image.image_url)" alt="白斑照片" loading="lazy" />
              <span class="create-grid__site">{{ siteLabel(item.image.body_site) }}</span>
              <span v-if="item.image.vasi_assessment_id" class="create-grid__vasi" title="已深度分析">
                <i class="ri-microscope-line"></i>
              </span>
              <span v-if="orderOf(item.image.id)" class="create-grid__order">
                {{ orderOf(item.image.id) }}
              </span>
            </button>

            <!-- 日期（点击弹出日期选择） -->
            <button
              type="button"
              class="create-grid__date-btn"
              :title="item.image.capture_date ? '修改拍摄日期' : '补标注日期'"
              :aria-label="'修改拍摄日期'"
              @click.stop="openEditor(item.image)"
            >
              <i class="ri-calendar-line"></i>
              {{ item.image.capture_date ? item.image.capture_date.slice(0, 10) : '未标注日期' }}
            </button>

            <!-- 删除（右上角 ×） -->
            <button
              type="button"
              class="create-grid__x"
              aria-label="删除照片"
              title="删除照片"
              @click.stop="askDelete(item.image)"
            >
              <i class="ri-close-line"></i>
            </button>
          </div>
        </div>

        <p v-if="!reportSite && hasMixedSelectedSites" class="create-warning">
          <i class="ri-error-warning-line"></i> 已选照片包含多个部位，请选择同一部位
        </p>

        <p v-if="allImages.length > 1" class="create-reorder-hint">
          <i class="ri-drag-move-2-line"></i> 长按照片拖动排序 · 点日期改日期 · × 删除
        </p>

        <!-- 上传照片工具框（页面下方） -->
        <ComparisonPhotoUploader class="create-uploader" :default-body-site="reportSite || null" @saved="load" />

        <!-- 底部生成按钮 -->
        <div class="create-footer">
          <div class="create-footer__row">
            <span class="create-footer__count">已选 {{ selected.size }} / {{ MAX_SELECT }} 张</span>
            <button
              type="button"
              class="create-footer__btn"
              :disabled="!canGenerate || generating"
              @click="generate"
            >
              <i v-if="generating" class="ri-loader-4-line create-spin"></i>
              <i v-else class="ri-magic-line"></i>
              <span>{{ generating ? 'AI 生成中...' : '生成报告' }}</span>
            </button>
          </div>
        </div>
      </template>
    </main>

    <PhotoMetaEditor
      :visible="showEditor"
      :image="editingImage"
      @close="showEditor = false"
      @saved="load"
    />

    <ConfirmDialog
      :visible="confirmDeleteVisible"
      title="删除照片"
      message="确定删除这张照片吗？删除后不可恢复。"
      confirm-text="删除"
      :loading="deleting"
      @confirm="confirmDelete"
      @cancel="confirmDeleteVisible = false"
    />
  </div>
</template>

<style scoped>
.create-page {
  min-height: 0;
  min-height: 0;
  background: #f5f7fa;
  padding-bottom: 100px;
}

html.dark .create-page {
  background: #0f172a;
}

.create-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(245, 247, 250, 0.85);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid #e2e8f0;
}

html.dark .create-header {
  background: rgba(15, 23, 42, 0.85);
  border-color: #1e293b;
}

.create-header__inner {
  max-width: 896px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  height: 48px;
}

.create-back {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #475569;
  font-size: 22px;
  cursor: pointer;
}

html.dark .create-back {
  color: #cbd5e1;
}

.create-header__title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

html.dark .create-header__title {
  color: #f1f5f9;
}

/* 左上角对比部位徽标（测评页已选部位，仅展示） */
.create-header__site {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 2px;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(20, 184, 166, 0.12);
  color: var(--color-primary-600);
  font-size: 12px;
  font-weight: 600;
}

.create-header__site i {
  font-size: 13px;
}

html.dark .create-header__site {
  background: rgba(20, 184, 166, 0.18);
  color: var(--color-primary-300);
}

.create-main {
  max-width: 896px;
  margin: 0 auto;
  padding: 16px;
}

.create-intro {
  text-align: center;
  padding: 8px 16px 12px;
}

.create-intro h2 {
  font-size: 17px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

html.dark .create-intro h2 {
  color: #f1f5f9;
}

.create-uploader {
  display: block;
  margin-top: 16px;
}

.create-cta {
  margin-top: 16px;
  padding: 8px 24px;
  border-radius: 20px;
  border: none;
  background: var(--color-primary-500);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

/* 照片墙：2 列（每行 2 张） */
.create-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.create-warning {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #9a3412;
  font-size: 13px;
  line-height: 1.5;
}

html.dark .create-warning {
  background: rgba(124, 45, 18, 0.2);
  border-color: rgba(251, 146, 60, 0.35);
  color: #fdba74;
}

.create-reorder-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}

html.dark .create-reorder-hint {
  color: #64748b;
}

@media (min-width: 640px) {
  /* 每行 2 张：桌面端保持与移动端一致的 2 列 */
  .create-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.create-grid__item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 10px;
  overflow: hidden;
  border: 3px solid transparent;
  background: #f1f5f9;
  transition: all 0.15s;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}

.create-grid__item img {
  pointer-events: none;
  -webkit-user-drag: none;
}

html.dark .create-grid__item {
  background: #334155;
}

.create-grid__item--selected {
  border-color: var(--color-primary-500);
  box-shadow: 0 0 0 2px rgba(20, 184, 166, 0.25);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-primary-500) 25%, transparent);
}

.create-grid__pick {
  display: block;
  width: 100%;
  height: 100%;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  position: relative;
}

.create-grid__pick img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 编辑按钮：44px 触控热区，视觉上仅显示右下角小圆钮 */
/* 删除按钮：右上角红色 × */
.create-grid__x {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 26px;
  height: 26px;
  min-height: 26px;
  min-width: 26px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.92);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  cursor: pointer;
  z-index: 4;
  transition: transform 0.12s;
}

.create-grid__x:active {
  transform: scale(0.9);
}

/* 日期按钮：左上角，点击弹出日期选择 */
.create-grid__date-btn {
  position: absolute;
  top: 4px;
  left: 4px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  max-width: calc(100% - 38px);
  padding: 2px 6px;
  min-height: 20px;
  border: none;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.55);
  color: white;
  font-size: 10px;
  line-height: 1.2;
  cursor: pointer;
  z-index: 4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.create-grid__date-btn i {
  font-size: 11px;
  flex-shrink: 0;
}

.create-grid__site {
  position: absolute;
  bottom: 4px;
  left: 4px;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.55);
  color: white;
}

.create-grid__vasi {
  position: absolute;
  bottom: 4px;
  right: 4px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-primary-500);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
}

/* 选中序号：右上角 × 下方 */
.create-grid__order {
  position: absolute;
  top: 34px;
  right: 4px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--color-primary-500);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  z-index: 4;
}

/* 拖动中的照片：放大 + 描边（微信朋友圈式） */
.create-grid__item--drag {
  transform: scale(1.04);
  box-shadow: 0 0 0 3px var(--color-primary-500), 0 8px 24px rgba(0, 0, 0, 0.25);
  z-index: 6;
  transition: transform 0.12s;
}

.create-footer {
  position: fixed;
  /* 移动端 BottomNav 固定高 54px，底栏需整体避开，否则"生成报告"按钮被遮挡 */
  bottom: calc(54px + env(safe-area-inset-bottom, 0px));
  left: 0;
  right: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  border-top: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 16px 12px;
  z-index: 20;
}

@media (min-width: 768px) {
  /* 桌面端无 BottomNav，贴底并兼顾 safe-area */
  .create-footer {
    bottom: 0;
    padding-bottom: calc(12px + env(safe-area-inset-bottom, 0px));
  }
}

html.dark .create-footer {
  background: rgba(15, 23, 42, 0.95);
  border-color: #1e293b;
}

.create-footer__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.create-footer__count {
  font-size: 14px;
  color: #64748b;
  font-weight: 500;
}

html.dark .create-footer__count {
  color: #94a3b8;
}

.create-footer__btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  border-radius: 22px;
  border: none;
  background: var(--color-primary-500);
  color: white;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.create-footer__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.create-footer__btn:not(:disabled):active {
  transform: scale(0.96);
}

.create-spin {
  animation: c-spin 1s linear infinite;
}

@keyframes c-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
