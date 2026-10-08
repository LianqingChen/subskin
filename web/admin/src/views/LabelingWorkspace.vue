<script setup lang="ts">
/**
 * LabelingWorkspace — full-page labeling workspace at /#/image-labeling/:id
 *
 * 自动全屏 + 可折叠右栏（画布最大化）+ 简化工具（白斑画笔/橡皮）。
 * 无管理员标注时自动带入用户（或 AI）填涂结果与表单数据，可直接提交。
 * 「暂存」= draft_mode（保持待标注状态）；「提交标注」= 正式提交并返回列表。
 */

import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import request from '@/api/request'
import MaskEditorAdmin from '@/components/labeling/MaskEditorAdmin.vue'
import LesionPanel from '@/components/labeling/LesionPanel.vue'
import { useLesionManager } from '@/composables/useLesionManager'
import type { AdminAnnotationItem } from '@/components/labeling/types'
import type { ToolName } from '@/components/labeling/tools/BaseTool'

const route = useRoute()
const router = useRouter()
const message = useMessage()

// 皮肤与白斑画笔互相覆盖，支持继续精修两类范围。
const workspaceTools: ToolName[] = ['skin-brush', 'lesion-brush', 'eraser']

const labelId = computed(() => Number(route.params.id))
const imageUrl = ref('')
const imageHash = ref<string | null>(null)
const annotatedImageUrl = ref<string | null>(null)
const loading = ref(true)
const saving = ref(false)
const savingDraft = ref(false)

// ── Canvas ref ──
const maskEditorRef = ref<InstanceType<typeof MaskEditorAdmin> | null>(null)

// ── Lesion manager ──
const lesionManager = useLesionManager()

// ── Form state ──
const form = reactive({
  body_site: null as string | null,
  is_vitiligo: true as boolean | null,
  vitiligo_type: null as string | null,
  vitiligo_stage: null as string | null,
  area_percentage: null as number | null,
  vasi_score: null as number | null,
  depigmentation_level: null as number | null,
  notes: '' as string | null,
  training_eligible: false,
})

// ── 选项（与后端 BODY_SITE_CHOICES / VITILIGO_TYPE_CHOICES 对齐，中文为规范值） ──

const bodySiteOptions = [
  '面部', '颈部', '头皮', '躯干前面', '躯干后面', '上肢近端', '上肢远端',
  '手部', '下肢近端', '下肢远端', '足部', '生殖器', '其他',
].map(s => ({ label: s, value: s }))

const vitiligoTypeOptions = [
  '非节段型(寻常型)', '节段型', '混合型', '未确定', '非白癜风',
].map(s => ({ label: s, value: s }))

const stageOptions = [
  '进展期', '稳定期', '好转期', '不确定',
].map(s => ({ label: s, value: s }))

// 历史数据/用户测评页使用英文枚举或简写，预填时归一到规范中文值
const BODY_SITE_MAP: Record<string, string> = {
  face: '面部', neck: '颈部', scalp: '头皮', trunk: '躯干前面',
  trunk_front: '躯干前面', trunk_back: '躯干后面',
  upper_limb: '上肢近端', upper_limb_proximal: '上肢近端', upper_limb_distal: '上肢远端',
  lower_limb: '下肢近端', lower_limb_proximal: '下肢近端', lower_limb_distal: '下肢远端',
  hand: '手部', 左手: '手部', 右手: '手部', 左手背: '手部', 右手背: '手部',
  foot: '足部', 左脚: '足部', 右脚: '足部',
  whole_body: '其他', genitals: '生殖器', other: '其他',
}
const VITILIGO_TYPE_MAP: Record<string, string> = {
  non_segmental: '非节段型(寻常型)', 非节段型: '非节段型(寻常型)', 寻常型: '非节段型(寻常型)',
  segmental: '节段型', 节段型: '节段型', mixed: '混合型', 混合型: '混合型',
  unclassified: '未确定', 未定型: '未确定', 未确定: '未确定', not_vitiligo: '非白癜风',
}
const STAGE_MAP: Record<string, string> = {
  progressing: '进展期', 进展: '进展期', 扩散: '进展期',
  stable: '稳定期', 稳定: '稳定期', improving: '好转期', 好转: '好转期',
  uncertain: '不确定', 不确定: '不确定',
}

function normalizeBodySite(v?: string | null): string | null {
  if (!v) return null
  if (bodySiteOptions.some(o => o.value === v)) return v
  return BODY_SITE_MAP[v] || null
}

function normalizeVitiligoType(v?: string | null): string | null {
  if (!v) return null
  if (vitiligoTypeOptions.some(o => o.value === v)) return v
  return VITILIGO_TYPE_MAP[v] || null
}

function normalizeStage(v?: string | null): string | null {
  if (!v) return null
  if (stageOptions.some(o => o.value === v)) return v
  return STAGE_MAP[v] || null
}

// ── 预填提示 ──
const prefillSource = ref<'user' | 'ai' | null>(null)
const prefillBannerVisible = ref(true)

// ── 重新带入用户标注（覆盖画布，二次点击确认） ──
const hasUserData = ref(false)
const reimporting = ref(false)
const reimportConfirming = ref(false)
let reimportConfirmTimer: ReturnType<typeof setTimeout> | null = null

// ── 自动全屏 ──
const workspaceRootRef = ref<HTMLDivElement | null>(null)
const isFullscreen = ref(false)
const fullscreenAvailable = ref(true)

async function tryAutoFullscreen() {
  if (document.fullscreenElement) { isFullscreen.value = true; return }
  try {
    await workspaceRootRef.value?.requestFullscreen()
    isFullscreen.value = true
  } catch {
    // 直接路由进入（无用户手势）时浏览器会拒绝 — 顶栏保留手动全屏按钮
    fullscreenAvailable.value = false
  }
}

async function toggleWorkspaceFullscreen() {
  if (document.fullscreenElement) {
    try { await document.exitFullscreen() } catch { /* ignore */ }
    isFullscreen.value = false
  } else {
    try {
      await workspaceRootRef.value?.requestFullscreen()
      isFullscreen.value = true
      fullscreenAvailable.value = true
    } catch { /* ignore */ }
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
}

// ── 右栏折叠 ──
const panelCollapsed = ref(false)

// ── 用户/AI 填涂数据 ──
interface UserAnnotationsData {
  has_user_data: boolean
  has_ai_data: boolean
  user_annotations: any[]
  ai_annotations: any[]
  assessment_summary: any
}

function fetchUserAnnotations() {
  return request.get<UserAnnotationsData>(
    `/vasi/admin/image-labels/${labelId.value}/user-annotations`,
  ).then(r => r.data)
}

function mapRawAnnotations(raw: any[], fromUser: boolean): AdminAnnotationItem[] {
  return raw.map((a: any, i: number) => ({
    source: 'admin' as const,
    region_index: a.region_index || i,
    body_site: a.body_site || null,
    is_vitiligo: a.is_vitiligo ?? null,
    vitiligo_type: a.vitiligo_type || null,
    vitiligo_stage: a.vitiligo_stage || null,
    area_percentage: a.area_percentage ?? null,
    depigmentation_level: a.depigmentation_level ?? null,
    region_contour: null,
    region_bbox: null,
    mask_data: a.mask_data || null,
    skin_mask_data: a.skin_mask_data || null,
    confidence: a.confidence ?? null,
    notes: fromUser ? '预填充自用户填涂结果 — 管理员审核修改' : '预填充自AI填涂结果 — 管理员审核修改',
  }))
}

// ── Load image data ──
async function loadImageData() {
  loading.value = true
  try {
    const token = localStorage.getItem('admin_token') || ''
    imageUrl.value = `/api/vasi/admin/image-labels/${labelId.value}/image?access_token=${encodeURIComponent(token)}`

    // 1. 详情：管理员已填字段 → 表单回填（否则回退 AI 字段）
    const { data: detail } = await request.get(`/vasi/admin/image-labels/${labelId.value}`)
    if (detail.annotated_image_url) {
      annotatedImageUrl.value = `/api/vasi/admin/image-labels/${labelId.value}/annotated-image?access_token=${encodeURIComponent(token)}`
    }
    if (detail.image_hash) imageHash.value = detail.image_hash

    if (detail.admin_is_vitiligo != null) {
      Object.assign(form, {
        body_site: normalizeBodySite(detail.admin_body_site),
        is_vitiligo: detail.admin_is_vitiligo ?? true,
        vitiligo_type: normalizeVitiligoType(detail.admin_vitiligo_type),
        vitiligo_stage: normalizeStage(detail.admin_vitiligo_stage),
        area_percentage: detail.admin_area_percentage ?? null,
        vasi_score: detail.admin_vasi_score ?? null,
        depigmentation_level: detail.admin_depigmentation_level ?? null,
        notes: detail.admin_notes ?? '',
        training_eligible: detail.training_eligible ?? false,
      })
    } else {
      Object.assign(form, {
        body_site: normalizeBodySite(detail.ai_body_site),
        is_vitiligo: detail.ai_is_vitiligo ?? true,
        vitiligo_type: normalizeVitiligoType(detail.ai_vitiligo_type),
        vitiligo_stage: normalizeStage(detail.ai_vitiligo_stage),
        area_percentage: detail.ai_area_percentage ?? null,
        vasi_score: detail.ai_vasi_score ?? null,
        depigmentation_level: detail.ai_depigmentation_level ?? null,
      })
    }

    // 2. 已有管理员标注 → 恢复白斑列表与画布
    let restored = false
    try {
      const { data: annData } = await request.get<{ annotations: AdminAnnotationItem[] }>(
        `/vasi/admin/image-labels/${labelId.value}/annotations`
      )
      if (annData.annotations && annData.annotations.length > 0) {
        lesionManager.loadFromAnnotations(annData.annotations)
        restored = true
      }
    } catch { /* no existing annotations */ }

    // 3. 取用户/AI 填涂数据（用户优先）：无管理员标注时预填画布与表单；
    //    同时确定顶栏「重新带入用户标注」按钮是否显示
    try {
      const userData = await fetchUserAnnotations()
      const fromUser = userData.has_user_data && userData.user_annotations.length > 0
      const fromAi = userData.has_ai_data && userData.ai_annotations.length > 0
      hasUserData.value = fromUser || fromAi

      if (!restored && (fromUser || fromAi)) {
        const raw = fromUser ? userData.user_annotations : userData.ai_annotations
        lesionManager.loadFromAnnotations(mapRawAnnotations(raw, fromUser))
        prefillSource.value = fromUser ? 'user' : 'ai'
        prefillBannerVisible.value = true

        // 表单预填（仅填充空字段）
        const first = raw[0]
        if (form.body_site == null) form.body_site = normalizeBodySite(first.body_site)
        if (first.is_vitiligo != null && (form.is_vitiligo == null || form.is_vitiligo === true)) {
          form.is_vitiligo = first.is_vitiligo
        }
        if (form.vitiligo_type == null) form.vitiligo_type = normalizeVitiligoType(first.vitiligo_type)
        if (form.vitiligo_stage == null) form.vitiligo_stage = normalizeStage(first.vitiligo_stage)
        if (form.area_percentage == null && first.area_percentage != null) form.area_percentage = first.area_percentage
        if (form.depigmentation_level == null && first.depigmentation_level != null) {
          form.depigmentation_level = first.depigmentation_level
        }
      }
    } catch { /* 无用户/AI 数据 */ }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '加载图片失败')
  } finally {
    loading.value = false
  }

  // 4. 画布就绪后载入当前白斑的蒙层（loadMaskLayers 内部会等待图片加载完成）
  await nextTick()
  const lesion = lesionManager.activeLesion.value
  if (lesion && (lesion.lesionMaskDataUrl || lesion.skinMaskDataUrl)) {
    await maskEditorRef.value?.loadMaskLayers(lesion.skinMaskDataUrl, lesion.lesionMaskDataUrl)
  }
}

// ── AI Pretrain ──
const aiPretraining = ref(false)

async function handleAiPretrain() {
  aiPretraining.value = true
  try {
    const { data } = await request.post<{
      lesion_layer_data_url?: string | null
      skin_layer_data_url?: string | null
      body_site?: string; is_vitiligo?: boolean
      vitiligo_type?: string; vitiligo_stage?: string
      area_percentage?: number; vasi_score?: number
      depigmentation_level?: number; confidence?: number
      duration_ms?: number
    }>(`/vasi/admin/image-labels/${labelId.value}/ai-pretrain`)

    if (data.lesion_layer_data_url || data.skin_layer_data_url) {
      await maskEditorRef.value?.loadMaskLayers(
        data.skin_layer_data_url || null,
        data.lesion_layer_data_url || null,
      )
      message.success(`AI 预标注完成, 耗时 ${Math.round((data.duration_ms || 0) / 1000)}s`)
    } else {
      message.warning('AI 推理未返回蒙版数据, 请手动填涂')
    }
    if (data.body_site && !form.body_site) form.body_site = normalizeBodySite(data.body_site)
    if (data.is_vitiligo != null && form.is_vitiligo == null) form.is_vitiligo = data.is_vitiligo
  } catch (err: any) {
    message.error(err?.response?.data?.detail || 'AI 预标注失败')
  } finally {
    aiPretraining.value = false
  }
}

// ── 重新带入用户标注（覆盖当前画布蒙层） ──
async function handleReimportClick() {
  if (!reimportConfirming.value) {
    reimportConfirming.value = true
    reimportConfirmTimer = setTimeout(() => { reimportConfirming.value = false }, 3000)
    return
  }
  if (reimportConfirmTimer) {
    clearTimeout(reimportConfirmTimer)
    reimportConfirmTimer = null
  }
  reimportConfirming.value = false
  reimporting.value = true
  try {
    const userData = await fetchUserAnnotations()
    const fromUser = userData.has_user_data && userData.user_annotations.length > 0
    const raw = fromUser ? userData.user_annotations : (userData.has_ai_data ? userData.ai_annotations : [])
    if (raw.length === 0) {
      message.warning('没有可带入的用户填涂数据')
      return
    }
    lesionManager.loadFromAnnotations(mapRawAnnotations(raw, fromUser))
    prefillSource.value = fromUser ? 'user' : 'ai'
    prefillBannerVisible.value = true
    await nextTick()
    const lesion = lesionManager.activeLesion.value
    if (lesion && (lesion.lesionMaskDataUrl || lesion.skinMaskDataUrl)) {
      await maskEditorRef.value?.loadMaskLayers(lesion.skinMaskDataUrl, lesion.lesionMaskDataUrl)
    }
    message.success('已重新带入用户标注，画布蒙层已覆盖')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '获取用户标注失败')
  } finally {
    reimporting.value = false
  }
}

// ── 组装标注 payload（暂存与提交共用） ──
function buildAnnotationsPayload(): AdminAnnotationItem[] {
  const annotations: AdminAnnotationItem[] = lesionManager.lesions.value.map((lesion, i) => ({
    source: 'admin' as const,
    region_index: i,
    body_site: lesion.bodySite,
    is_vitiligo: lesion.isVitiligo,
    vitiligo_type: lesion.vitiligoType,
    vitiligo_stage: lesion.vitiligoStage,
    area_percentage: lesion.areaPercentage,
    depigmentation_level: lesion.depigmentationLevel,
    region_contour: null,
    region_bbox: null,
    mask_data: lesion.lesionMaskDataUrl,
    skin_mask_data: lesion.skinMaskDataUrl,
    confidence: null,
    notes: lesion.notes,
  }))

  // Always include current canvas data for the active lesion
  const lesionUrl = maskEditorRef.value?.getLesionDataUrl?.() || ''
  const skinUrl = maskEditorRef.value?.getSkinDataUrl?.() || ''
  if (annotations.length === 0) {
    annotations.push({
      source: 'admin', region_index: 0,
      body_site: form.body_site, is_vitiligo: form.is_vitiligo,
      vitiligo_type: form.vitiligo_type, vitiligo_stage: form.vitiligo_stage,
      area_percentage: form.area_percentage,
      depigmentation_level: form.depigmentation_level,
      region_contour: null, region_bbox: null,
      mask_data: lesionUrl || null,
      skin_mask_data: skinUrl || null,
      confidence: null, notes: form.notes,
    })
  } else if (lesionUrl && lesionUrl.length > 200) {
    // Update active lesion's mask from canvas
    const activeIdx = lesionManager.activeIndex.value
    if (annotations[activeIdx]) {
      annotations[activeIdx].mask_data = lesionUrl
      annotations[activeIdx].skin_mask_data = skinUrl
    }
  }
  return annotations
}

// ── 暂存（草稿：保持「待标注」状态） ──
async function handleSaveDraft() {
  savingDraft.value = true
  try {
    await request.post(`/vasi/admin/image-labels/${labelId.value}/label`, {
      body_site: form.body_site,
      is_vitiligo: form.is_vitiligo,
      vitiligo_type: form.vitiligo_type,
      vitiligo_stage: form.vitiligo_stage,
      area_percentage: form.area_percentage,
      vasi_score: form.vasi_score,
      depigmentation_level: form.depigmentation_level,
      notes: form.notes,
      training_eligible: form.training_eligible,
      annotations: buildAnnotationsPayload(),
      annotated_image: maskEditorRef.value?.getAnnotatedImageDataUrl?.() || null,
      draft_mode: true,
    })
    message.success('已暂存（状态保持「待标注」，可稍后继续）')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '暂存失败')
  } finally {
    savingDraft.value = false
  }
}

// ── 提交标注（正式提交 → 返回列表） ──
async function handleSubmit() {
  // 管理员未手填面积时，用画布计算的白斑面积自动填充
  if (form.area_percentage == null) {
    const auto = maskEditorRef.value?.getAreaPercent?.()
    if (auto != null && auto > 0) {
      form.area_percentage = Math.round(auto * 10) / 10
    }
  }
  saving.value = true
  try {
    await request.post(`/vasi/admin/image-labels/${labelId.value}/label`, {
      body_site: form.body_site,
      is_vitiligo: form.is_vitiligo,
      vitiligo_type: form.vitiligo_type,
      vitiligo_stage: form.vitiligo_stage,
      area_percentage: form.area_percentage,
      vasi_score: form.vasi_score,
      depigmentation_level: form.depigmentation_level,
      notes: form.notes,
      training_eligible: form.training_eligible,
      annotations: buildAnnotationsPayload(),
      annotated_image: maskEditorRef.value?.getAnnotatedImageDataUrl?.() || null,
    })
    message.success('标注已提交')
    await exitWorkspace()
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '提交失败')
  } finally {
    saving.value = false
  }
}

// ── 退出工作区：退出全屏 + 返回列表 ──
async function exitWorkspace() {
  if (document.fullscreenElement) {
    try { await document.exitFullscreen() } catch { /* ignore */ }
  }
  router.push({ name: 'ImageLabeling' })
}

// ── Handle lesion switch → reload canvas layers ──
async function handleLesionChanged(_index: number) {
  const lesion = lesionManager.activeLesion.value
  if (!lesion) return
  await nextTick()
  await maskEditorRef.value?.loadMaskLayers(
    lesion.skinMaskDataUrl,
    lesion.lesionMaskDataUrl,
  )
}

// ── Handle canvas confirm (sync active lesion's mask) ──
function handleCanvasConfirm(payload: { skinMaskDataUrl: string; lesionMaskDataUrl: string }) {
  lesionManager.updateActiveLesionMask(payload.skinMaskDataUrl, payload.lesionMaskDataUrl)
}

onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  loadImageData()
  tryAutoFullscreen()
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  if (reimportConfirmTimer) clearTimeout(reimportConfirmTimer)
  if (document.fullscreenElement) {
    try { document.exitFullscreen() } catch { /* ignore */ }
  }
})
</script>

<template>
  <div ref="workspaceRootRef" class="workspace-root">
    <!-- Top bar（单行压缩） -->
    <div class="top-bar">
      <button class="top-btn ghost" title="退出工作区" @click="exitWorkspace">
        <i class="ri-arrow-left-line"></i> 退出
      </button>
      <span class="top-title">图片打标 #{{ labelId }}</span>
      <span v-if="form.body_site" class="top-chip">{{ form.body_site }}</span>
      <span v-if="imageHash" class="top-chip muted" :title="imageHash">{{ imageHash.slice(0, 8) }}</span>

      <div class="top-actions">
        <button
          v-if="!isFullscreen"
          class="top-btn ghost"
          title="进入全屏"
          @click="toggleWorkspaceFullscreen"
        >
          <i class="ri-fullscreen-line"></i> 全屏
        </button>
        <button
          :disabled="aiPretraining"
          class="top-btn ai"
          @click="handleAiPretrain"
        >
          <i class="ri-robot-2-line" :class="{ 'ri-spin': aiPretraining }"></i>
          AI 预标注
        </button>
        <button
          v-if="hasUserData"
          :disabled="reimporting"
          class="top-btn ghost"
          :class="{ warn: reimportConfirming }"
          :title="reimportConfirming ? '再次点击确认：将用用户填涂覆盖当前画布' : '重新以用户在 SubSkin 的填涂作为蒙层（会覆盖当前画布）'"
          @click="handleReimportClick"
        >
          <i :class="reimporting ? 'ri-loader-4-line ri-spin' : 'ri-user-follow-line'"></i>
          {{ reimportConfirming ? '再点一次确认覆盖' : '重新带入用户标注' }}
        </button>
        <button
          :disabled="savingDraft || saving"
          class="top-btn draft"
          title="保存进度，状态保持「待标注」"
          @click="handleSaveDraft"
        >
          <i :class="savingDraft ? 'ri-loader-4-line ri-spin' : 'ri-save-line'"></i>
          暂存
        </button>
        <button
          :disabled="saving || savingDraft"
          class="top-btn primary"
          @click="handleSubmit"
        >
          <i class="ri-check-line"></i>
          提交标注
        </button>
      </div>
    </div>

    <!-- 预填提示条 -->
    <div v-if="prefillSource && prefillBannerVisible" class="prefill-banner">
      <i :class="prefillSource === 'user' ? 'ri-user-line' : 'ri-robot-2-line'"></i>
      已带入{{ prefillSource === 'user' ? '用户' : 'AI' }}标注（蒙层与表单已预填），确认无误可直接提交标注
      <button class="prefill-close" @click="prefillBannerVisible = false"><i class="ri-close-line"></i></button>
    </div>

    <!-- Main content -->
    <div v-if="loading" class="loading-wrap">
      <div class="spinner"></div>
    </div>

    <div v-else class="main-area">
      <!-- Canvas（最大化） -->
      <div class="canvas-wrap">
        <MaskEditorAdmin
          ref="maskEditorRef"
          :image-url="imageUrl"
          :editable="true"
          :tools="workspaceTools"
          @confirm="handleCanvasConfirm"
        />
      </div>

      <!-- Right panel（可折叠） -->
      <div class="right-panel" :class="{ collapsed: panelCollapsed }">
        <button class="panel-toggle" :title="panelCollapsed ? '展开面板' : '收起面板'" @click="panelCollapsed = !panelCollapsed">
          <i :class="panelCollapsed ? 'ri-arrow-left-s-line' : 'ri-arrow-right-s-line'"></i>
        </button>

        <div v-show="!panelCollapsed" class="panel-content">
          <!-- Lesion panel -->
          <div class="panel-card">
            <LesionPanel :manager="lesionManager" @lesion-changed="handleLesionChanged" />
          </div>

          <!-- Classification form -->
          <div class="panel-card">
            <div class="panel-card-title">分类信息</div>

            <div class="form-col">
              <select v-model="form.body_site" :style="selectStyle">
                <option :value="null">选择身体部位</option>
                <option v-for="opt in bodySiteOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>

              <div class="toggle-group">
                <button :style="toggleBtnStyle(form.is_vitiligo === true, '#f59e0b')" @click="form.is_vitiligo = true">是白癜风</button>
                <button :style="toggleBtnStyle(form.is_vitiligo === false, '#10b981')" @click="form.is_vitiligo = false">非白癜风</button>
              </div>

              <select v-if="form.is_vitiligo" v-model="form.vitiligo_type" :style="selectStyle">
                <option :value="null">选择分型</option>
                <option v-for="opt in vitiligoTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>

              <select v-if="form.is_vitiligo" v-model="form.vitiligo_stage" :style="selectStyle">
                <option :value="null">选择阶段</option>
                <option v-for="opt in stageOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>

              <div class="grid-2">
                <input
                  v-model.number="form.area_percentage"
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  placeholder="面积%（占整图）"
                  title="白斑面积占整张照片的百分比；留空时提交会按蒙层自动计算"
                  :style="inputStyle"
                />
                <input v-model.number="form.vasi_score" type="number" min="0" step="0.01" placeholder="VASI 评分" :style="inputStyle" />
              </div>

              <input v-model.number="form.depigmentation_level" type="number" min="0" max="1" step="0.05" placeholder="脱色程度 (0-1)" :style="inputStyle" />

              <textarea v-model="form.notes" rows="2" placeholder="备注说明" :style="{ ...inputStyle, resize: 'vertical' }"></textarea>

              <label class="training-toggle">
                <input v-model="form.training_eligible" type="checkbox" style="accent-color: #6366f1;" />
                <i class="ri-database-2-line"></i> 作为训练数据
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes spin { to { transform: rotate(360deg); } }
.ri-spin { animation: spin 1s linear infinite; }

.workspace-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0f172a;
  color: #e2e8f0;
}

/* ── Top bar ── */
.top-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  background: #1e293b;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  flex-shrink: 0;
}
.top-title { font-size: 14px; font-weight: 600; white-space: nowrap; }
.top-chip {
  font-size: 11px;
  color: #94a3b8;
  background: rgba(148, 163, 184, 0.1);
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.top-chip.muted { color: #475569; font-family: monospace; }
.top-actions { margin-left: auto; display: flex; gap: 6px; }

.top-btn {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  border: none;
  white-space: nowrap;
}
.top-btn:disabled { cursor: not-allowed; opacity: 0.6; }
.top-btn.ghost {
  background: transparent;
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.2);
}
.top-btn.warn {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.45);
}
.top-btn.ai {
  background: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
  border: 1px solid rgba(59, 130, 246, 0.4);
}
.top-btn.draft {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}
.top-btn.primary {
  background: #6366f1;
  color: #fff;
  font-weight: 600;
  padding: 6px 20px;
}

/* ── 预填提示条 ── */
.prefill-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(16, 185, 129, 0.08);
  border-bottom: 1px solid rgba(16, 185, 129, 0.2);
  color: #6ee7b7;
  font-size: 12px;
  flex-shrink: 0;
}
.prefill-close {
  margin-left: auto;
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 2px;
  display: flex;
}

/* ── Loading ── */
.loading-wrap { flex: 1; display: flex; align-items: center; justify-content: center; }
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(148, 163, 184, 0.2);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ── Main ── */
.main-area {
  flex: 1;
  display: flex;
  gap: 10px;
  padding: 10px;
  min-height: 0;
  overflow: hidden;
}
.canvas-wrap {
  flex: 1;
  min-width: 0;
  background: #1e293b;
  border-radius: 8px;
  overflow: hidden;
}

/* ── Right panel（可折叠：340px ↔ 26px 窄条） ── */
.right-panel {
  position: relative;
  width: 340px;
  flex-shrink: 0;
  transition: width 0.2s ease;
}
.right-panel.collapsed { width: 26px; }

.panel-toggle {
  position: absolute;
  top: 50%;
  left: -10px;
  transform: translateY(-50%);
  z-index: 10;
  width: 20px;
  height: 48px;
  background: #1e293b;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 6px;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}
.panel-toggle:hover { color: #a5b4fc; border-color: rgba(99, 102, 241, 0.4); }

.right-panel.collapsed .panel-toggle {
  left: 3px;
  top: 16px;
  transform: none;
}

.panel-content {
  width: 340px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  overflow-x: hidden;
}
.panel-card {
  background: #1e293b;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.12);
}
.panel-card-title {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.form-col { display: flex; flex-direction: column; gap: 8px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.toggle-group {
  display: flex;
  gap: 4px;
  padding: 2px;
  background: #0f172a;
  border-radius: 6px;
}
.training-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #cbd5e1;
  cursor: pointer;
  padding: 6px 8px;
  background: #0f172a;
  border-radius: 6px;
}
</style>

<script lang="ts">
const selectStyle = {
  width: '100%', padding: '6px 8px',
  background: '#0f172a', color: '#e2e8f0',
  border: '1px solid rgba(148,163,184,0.2)',
  borderRadius: '6px', fontSize: '12px',
}

const inputStyle = {
  width: '100%', padding: '6px 8px',
  background: '#0f172a', color: '#e2e8f0',
  border: '1px solid rgba(148,163,184,0.2)',
  borderRadius: '6px', fontSize: '12px',
}

function toggleBtnStyle(active: boolean, color: string) {
  return {
    flex: '1', padding: '6px 8px', borderRadius: '4px', fontSize: '12px',
    transition: 'all 0.15s', cursor: 'pointer', border: 'none',
    background: active ? color : 'transparent',
    color: active ? '#fff' : '#94a3b8',
    fontWeight: active ? 600 : 400,
  }
}
</script>
