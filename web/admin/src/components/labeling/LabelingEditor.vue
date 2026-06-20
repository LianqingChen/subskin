<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import MaskEditorAdmin from './MaskEditorAdmin.vue'

// ── 类型定义 ──
export interface AdminAnnotationItem {
  source: 'ai' | 'admin'
  region_index: number
  body_site: string | null
  is_vitiligo: boolean | null
  vitiligo_type: string | null
  vitiligo_stage: string | null
  area_percentage: number | null
  depigmentation_level: number | null
  region_contour: string | null  // JSON string
  region_bbox: string | null  // JSON string
  mask_data: string | null  // PNG data URL
  skin_mask_data?: string | null  // skin mask PNG
  confidence: number | null
  notes: string | null
}

export interface LabelingEditorSubmit {
  body_site: string | null
  is_vitiligo: boolean | null
  vitiligo_type: string | null
  vitiligo_stage: string | null
  area_percentage: number | null
  vasi_score: number | null
  depigmentation_level: number | null
  notes: string | null
  training_eligible: boolean | null
  annotations: AdminAnnotationItem[]
  annotated_image?: string | null  // composite: original photo + brush overlays baked in
}

const props = defineProps<{
  imageUrl: string
  imageHash?: string | null
  initialAdminAnnotations?: AdminAnnotationItem[]
  initialAiContours?: AdminContourRegion[]
  initialForm?: Partial<LabelingEditorSubmit>
  // 已有评估信息
  existingAiDetails?: {
    body_site?: string | null
    is_vitiligo?: boolean | null
    vitiligo_type?: string | null
    vitiligo_stage?: string | null
    area_percentage?: number | null
    vasi_score?: number | null
    depigmentation_level?: number | null
  } | null
  // AI 一键预标注回调（由父组件传入：调用 /vasi/assessments 之类的接口）
  aiPretrainAvailable?: boolean
  // 上次暂存/提交的标注合成图 URL（原始照片 + 画笔涂层叠加）
  annotatedImageUrl?: string | null
}>()

const emit = defineEmits<{
  submit: [payload: LabelingEditorSubmit]
  cancel: []
  'save-draft': [payload: LabelingEditorSubmit]
  'ai-pretrain': []
}>()

// ── 模式切换 ──
const mode = ref<'mask'>('mask')
const aiPretraining = ref(false)
const showAnnotatedPreview = ref(false)

// ── 像素填涂状态 ──
const maskEditorRef = ref<InstanceType<typeof MaskEditorAdmin> | null>(null)
const aiMaskSkinUrl = ref<string | null>(null)
const aiMaskLesionUrl = ref<string | null>(null)

// ── 表单状态 ──
const form = reactive({
  body_site: null as string | null,
  is_vitiligo: true as boolean | null,
  vitiligo_type: null as string | null,
  vitiligo_stage: null as string | null,
  area_percentage: null as number | null,
  vasi_score: null as number | null,
  depigmentation_level: null as number | null,
  notes: '' as string | null,
  training_eligible: true,
})

// ── 选项 ──
const bodySiteOptions = [
  { label: '面部', value: 'face' },
  { label: '颈部', value: 'neck' },
  { label: '躯干', value: 'trunk' },
  { label: '上肢', value: 'upper_limb' },
  { label: '下肢', value: 'lower_limb' },
  { label: '手部', value: 'hand' },
  { label: '足部', value: 'foot' },
  { label: '头皮', value: 'scalp' },
  { label: '全身', value: 'whole_body' },
]

const vitiligoTypeOptions = [
  { label: '非节段型', value: 'non_segmental' },
  { label: '节段型', value: 'segmental' },
  { label: '混合型', value: 'mixed' },
  { label: '未分类型', value: 'unclassified' },
  { label: '非白癜风', value: 'not_vitiligo' },
]

const stageOptions = [
  { label: '进展期', value: 'progressing' },
  { label: '稳定期', value: 'stable' },
  { label: '好转期', value: 'improving' },
  { label: '不确定', value: 'uncertain' },
]

// ── 计算属性 ──
const formValid = computed(() => {
  if (form.is_vitiligo === null) return false
  return true
})

// 填涂模式下的数据
const maskDataUrl = ref<string | null>(null)
const skinMaskDataUrl = ref<string | null>(null)
const maskAreaPercent = ref(0)

function clearAll() {
  maskDataUrl.value = null
  skinMaskDataUrl.value = null
  maskAreaPercent.value = 0
}

// ── 填涂模式回调 ──
function handleMaskConfirm(payload: { skinMaskDataUrl: string; lesionMaskDataUrl: string }) {
  skinMaskDataUrl.value = payload.skinMaskDataUrl
  maskDataUrl.value = payload.lesionMaskDataUrl
  // 重新读取面积
  if (maskEditorRef.value) {
    maskAreaPercent.value = maskEditorRef.value.getAreaPercent()
    form.area_percentage = Math.round(maskAreaPercent.value * 10) / 10
  }
}

// ── 初始化加载 ──
function loadFromProps() {
  // 表单
  if (props.initialForm) {
    Object.assign(form, {
      body_site: props.initialForm.body_site ?? null,
      is_vitiligo: props.initialForm.is_vitiligo ?? true,
      vitiligo_type: props.initialForm.vitiligo_type ?? null,
      vitiligo_stage: props.initialForm.vitiligo_stage ?? null,
      area_percentage: props.initialForm.area_percentage ?? null,
      vasi_score: props.initialForm.vasi_score ?? null,
      depigmentation_level: props.initialForm.depigmentation_level ?? null,
      notes: props.initialForm.notes ?? '',
      training_eligible: props.initialForm.training_eligible ?? true,
    })
  } else if (props.existingAiDetails) {
    const ai = props.existingAiDetails
    form.body_site = ai.body_site ?? null
    form.is_vitiligo = ai.is_vitiligo ?? true
    form.vitiligo_type = ai.vitiligo_type ?? null
    form.vitiligo_stage = ai.vitiligo_stage ?? null
    form.area_percentage = ai.area_percentage ?? null
    form.vasi_score = ai.vasi_score ?? null
    form.depigmentation_level = ai.depigmentation_level ?? null
  }

  // 已有管理员/用户标注的回显 — 含用户预填充数据
  if (props.initialAdminAnnotations && props.initialAdminAnnotations.length > 0) {
    // ── 回显图层数据 ──
    const maskAnn = props.initialAdminAnnotations.find(a => a.mask_data)
    const skinMaskAnn = props.initialAdminAnnotations.find(a => a.skin_mask_data)

    const lesionUrl = maskAnn?.mask_data || null
    const skinUrl = skinMaskAnn?.skin_mask_data || null

    if (lesionUrl) maskDataUrl.value = lesionUrl
    if (skinUrl) skinMaskDataUrl.value = skinUrl

    // 显式调用 MaskEditorAdmin 加载蒙版图层
    if (lesionUrl || skinUrl) {
      nextTick(() => {
        if (maskEditorRef.value?.loadMaskLayers) {
          console.log('[LabelingEditor] loadFromProps: calling loadMaskLayers')
          maskEditorRef.value.loadMaskLayers(skinUrl, lesionUrl)
        }
      })
    }

    // ── 预填充表单数据（从管理员标注的 annotations 中提取） ──
    // 管理员标注数据优先级 > AI 预估值，无条件覆盖
    // 只有非 null/non-empty 的字段才会覆盖，避免空值冲掉 AI 数据
    const firstAnn = props.initialAdminAnnotations[0]
    if (firstAnn) {
      if (firstAnn.body_site) form.body_site = firstAnn.body_site
      if (firstAnn.is_vitiligo != null) form.is_vitiligo = firstAnn.is_vitiligo
      if (firstAnn.vitiligo_type) form.vitiligo_type = firstAnn.vitiligo_type
      if (firstAnn.vitiligo_stage) form.vitiligo_stage = firstAnn.vitiligo_stage
      if (firstAnn.area_percentage != null) form.area_percentage = firstAnn.area_percentage
      if (firstAnn.depigmentation_level != null) form.depigmentation_level = firstAnn.depigmentation_level
      if (firstAnn.notes) form.notes = firstAnn.notes
    }
  }
}

onMounted(() => {
  loadFromProps()
})

// ⚠️ 关键修复：initialAdminAnnotations 是在组件挂载后才异步加载的
// 必须 watch 它的变化并重新加载，否则填涂数据无法恢复
watch(() => props.initialAdminAnnotations, async (newAnns) => {
  if (newAnns && newAnns.length > 0) {
    console.log('[LabelingEditor] initialAdminAnnotations changed, reloading', {
      count: newAnns.length,
      hasMask: newAnns.some(a => a.mask_data),
      hasSkinMask: newAnns.some(a => a.skin_mask_data),
    })
    // 回显图层数据
    const maskAnn = newAnns.find(a => a.mask_data)
    const skinMaskAnn = newAnns.find(a => a.skin_mask_data)

    const lesionUrl = maskAnn?.mask_data || null
    const skinUrl = skinMaskAnn?.skin_mask_data || null

    if (lesionUrl) {
      maskDataUrl.value = lesionUrl
      console.log('[LabelingEditor] Loaded lesion mask, length:', lesionUrl.length)
    }
    if (skinUrl) {
      skinMaskDataUrl.value = skinUrl
      console.log('[LabelingEditor] Loaded skin mask, length:', skinUrl.length)
    }

    // 显式调用 MaskEditorAdmin 的 loadMaskLayers，不依赖 prop 响应式时序
    if (lesionUrl || skinUrl) {
      await nextTick()
      if (maskEditorRef.value?.loadMaskLayers) {
        console.log('[LabelingEditor] Explicitly calling loadMaskLayers')
        await maskEditorRef.value.loadMaskLayers(skinUrl, lesionUrl)
      } else {
        console.warn('[LabelingEditor] maskEditorRef not ready for loadMaskLayers')
      }
    }

    // 预填充表单数据 — 管理员已保存的标注优先于 AI 预估值
    const firstAnn = newAnns[0]
    if (firstAnn) {
      if (firstAnn.body_site) form.body_site = firstAnn.body_site
      if (firstAnn.is_vitiligo != null) form.is_vitiligo = firstAnn.is_vitiligo
      if (firstAnn.vitiligo_type) form.vitiligo_type = firstAnn.vitiligo_type
      if (firstAnn.vitiligo_stage) form.vitiligo_stage = firstAnn.vitiligo_stage
      if (firstAnn.area_percentage != null) form.area_percentage = firstAnn.area_percentage
      if (firstAnn.depigmentation_level != null) form.depigmentation_level = firstAnn.depigmentation_level
      if (firstAnn.notes) form.notes = firstAnn.notes
    }
  }
}, { deep: true })

// 暴露给父组件追加 AI 预标注（像素蒙版）
function applyAiMask(skinDataUrl: string | null, lesionDataUrl: string | null) {
  if (lesionDataUrl) {
    maskDataUrl.value = lesionDataUrl
  }
  if (skinDataUrl) {
    skinMaskDataUrl.value = skinDataUrl
  }
  aiMaskSkinUrl.value = skinDataUrl
  aiMaskLesionUrl.value = lesionDataUrl
  aiPretraining.value = false
}

function triggerAiPretrain() {
  aiPretraining.value = true
  emit('ai-pretrain')
}

defineExpose({ applyAiMask })

// 父组件可通过 watch 触发 setAiPretraining(false)
watch(() => aiPretraining.value, (val) => {
  if (!val) aiPretraining.value = false
})

// ── 提交 ──
function buildAnnotations(): AdminAnnotationItem[] {
  // Always capture from canvas directly (bypass any stale internal state)
  const lesionDataUrl = maskEditorRef.value?.getLesionDataUrl?.() || ''
  const skinDataUrl = maskEditorRef.value?.getSkinDataUrl?.() || ''

  // Update internal state from canvas
  if (lesionDataUrl) maskDataUrl.value = lesionDataUrl
  if (skinDataUrl) skinMaskDataUrl.value = skinDataUrl

  const hasLesion = lesionDataUrl.length > 200   // real PNG data URL is much longer
  const hasSkin = skinDataUrl.length > 200

  console.log('[buildAnnotations] Canvas data:', {
    lesionLen: lesionDataUrl.length,
    skinLen: skinDataUrl.length,
    hasLesion,
    hasSkin,
  })

  // ⚠️ FIX: Always return at least one annotation with form data,
  // even when no mask is drawn on canvas.
  // Previously returned [] when no mask → annotation info (body_site,
  // is_vitiligo, vitiligo_type, etc.) was saved to ImageLabel.admin_*
  // columns but NOT to ImageLabelAnnotation records. On reload, the
  // form only reads from annotations → admin's metadata was lost.
  if (!hasLesion && !hasSkin) {
    console.warn('[buildAnnotations] No valid mask data from canvas — saving annotation metadata only. Lesion URL head:', lesionDataUrl.substring(0, 80))
  }

  return [{
    source: 'admin',
    region_index: 0,
    body_site: form.body_site,
    is_vitiligo: form.is_vitiligo,
    vitiligo_type: form.vitiligo_type,
    vitiligo_stage: form.vitiligo_stage,
    area_percentage: form.area_percentage,
    depigmentation_level: form.depigmentation_level,
    region_contour: null,
    region_bbox: null,
    mask_data: lesionDataUrl || null,
    skin_mask_data: skinDataUrl || null,
    confidence: null,
    notes: form.notes || null,
  }]
}

function handleSubmit() {
  if (!formValid.value) return
  // 直接从画布获取最新的填涂数据
  const currentLesionUrl = maskEditorRef.value?.getLesionDataUrl?.() || ''
  const currentSkinUrl = maskEditorRef.value?.getSkinDataUrl?.() || ''
  const currentAreaPercent = maskEditorRef.value?.getAreaPercent?.() || 0
  if (currentLesionUrl && currentLesionUrl.length > 100) {
    maskDataUrl.value = currentLesionUrl
  }
  if (currentSkinUrl && currentSkinUrl.length > 100) {
    skinMaskDataUrl.value = currentSkinUrl
  }
  if (currentAreaPercent > 0 && form.area_percentage == null) {
    form.area_percentage = Math.round(currentAreaPercent * 10) / 10
  }
  // Generate annotated composite if in mask mode
  const annotatedImage = maskEditorRef.value?.getAnnotatedImageDataUrl?.() || null

  const payload: LabelingEditorSubmit = {
    body_site: form.body_site,
    is_vitiligo: form.is_vitiligo,
    vitiligo_type: form.vitiligo_type,
    vitiligo_stage: form.vitiligo_stage,
    area_percentage: form.area_percentage,
    vasi_score: form.vasi_score,
    depigmentation_level: form.depigmentation_level,
    notes: form.notes,
    training_eligible: form.training_eligible,
    annotations: buildAnnotations(),
    annotated_image: annotatedImage,
  }
  emit('submit', payload)
}

// ── 键盘快捷键 ──
function onKeyDown(e: KeyboardEvent) {
  // 排除在输入框内
  const target = e.target as HTMLElement
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
    return
  }
  if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
    e.preventDefault()
    undo()
  } else if ((e.metaKey || e.ctrlKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
    e.preventDefault()
    redo()
  } else if (e.key === 'Escape') {
    handleCancel()
  }
}

function handleCancel() {
  emit('cancel')
}

function handleSaveDraft() {
  console.log('[LabelingEditor] handleSaveDraft called')

  // buildAnnotations now reads directly from the canvas, ensuring fresh data
  const annotations = buildAnnotations()

  // Update area from canvas
  const currentAreaPercent = maskEditorRef.value?.getAreaPercent?.() || 0
  if (currentAreaPercent > 0 && form.area_percentage == null) {
    form.area_percentage = Math.round(currentAreaPercent * 10) / 10
  }

  console.log('[LabelingEditor] Built annotations:', {
    count: annotations.length,
    hasMask: annotations.some(a => a.mask_data && a.mask_data.length > 200),
    maskLen: annotations[0]?.mask_data?.length,
    hasSkinMask: annotations.some(a => a.skin_mask_data && a.skin_mask_data.length > 200),
    skinLen: annotations[0]?.skin_mask_data?.length,
  })

  // 生成标注合成图（原始照片 + 画笔涂层叠加）
  let annotatedImage = null
  try {
    if (maskEditorRef.value?.getAnnotatedImageDataUrl) {
      annotatedImage = maskEditorRef.value.getAnnotatedImageDataUrl()
      console.log('[LabelingEditor] Captured annotated image, length:', annotatedImage?.length || 0)
    }
  } catch(e) {
    console.warn('[LabelingEditor] Failed to capture annotated image:', e)
  }

  const payload: LabelingEditorSubmit = {
    body_site: form.body_site,
    is_vitiligo: form.is_vitiligo,
    vitiligo_type: form.vitiligo_type,
    vitiligo_stage: form.vitiligo_stage,
    area_percentage: form.area_percentage,
    vasi_score: form.vasi_score,
    depigmentation_level: form.depigmentation_level,
    notes: form.notes,
    training_eligible: form.training_eligible,
    annotations: annotations,
    annotated_image: annotatedImage,
  }
  emit('save-draft', payload)
  console.log('[LabelingEditor] Emitted save-draft')
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 16px; color: #e2e8f0; height: 100%; min-height: 0;">
    <!-- 顶部工具栏 -->
    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 12px; background: #1e293b; border-radius: 8px; border: 1px solid rgba(148,163,184,0.15);">
      <!-- 像素填涂工具 -->
      <div style="display: flex; align-items: center; gap: 6px; padding: 4px 12px; background: #6366f1; color: #fff; border-radius: 8px; font-size: 12px; font-weight: 500;">
        <i class="ri-brush-line"></i>像素填涂
      </div>

      <div style="height: 24px; width: 1px; background: rgba(148,163,184,0.2); margin: 0 4px;"></div>

      <button class="tool-btn" title="清空标注" @click="clearAll">
        <i class="ri-delete-bin-line"></i>
      </button>

      <div style="height: 24px; width: 1px; background: rgba(148,163,184,0.2); margin: 0 4px;"></div>

      <!-- AI 一键预标注 -->
      <button
        v-if="aiPretrainAvailable"
        :disabled="aiPretraining"
        style="padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 500; background: rgba(59,130,246,0.2); color: #93c5fd; border: 1px solid rgba(59,130,246,0.4); display: flex; align-items: center; gap: 4px;"
        @click="triggerAiPretrain"
      >
        <i class="ri-robot-2-line" :class="aiPretraining ? 'ri-spin' : ''"></i>
        {{ aiPretraining ? 'AI 推理中…' : 'AI 一键预标注' }}
      </button>

      <div style="margin-left: auto; font-size: 11px; color: #94a3b8; display: flex; align-items: center; gap: 10px;">
        <!-- 上次暂存的合成图预览 -->
        <button
          v-if="annotatedImageUrl"
          :style="{
            display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px',
            borderRadius: '6px', fontSize: '11px', border: '1px solid rgba(245,158,11,0.3)',
            background: showAnnotatedPreview ? 'rgba(245,158,11,0.2)' : 'transparent',
            color: showAnnotatedPreview ? '#fbbf24' : '#94a3b8', cursor: 'pointer',
          }"
          title="点击预览/隐藏上次暂存结果"
          @click="showAnnotatedPreview = !showAnnotatedPreview"
        >
          <i class="ri-image-edit-line"></i>
          {{ showAnnotatedPreview ? '隐藏' : '上次暂存' }}
        </button>
        <span v-if="maskDataUrl">
          <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #f59e0b; margin-right: 4px;"></span>
          已填涂: {{ maskAreaPercent.toFixed(1) }}%
        </span>
        <span v-if="aiPretraining" style="color: #93c5fd;">
          <i class="ri-robot-2-line ri-spin" style="margin-right: 4px;"></i>AI 推理中…
        </span>
      </div>
    </div>

    <!-- 上次暂存的标注合成图预览（原始照片 + 画笔涂层叠加） -->
    <div
      v-if="showAnnotatedPreview && annotatedImageUrl"
      style="padding: 8px 12px; background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.25); border-radius: 8px; display: flex; align-items: center; gap: 10px; flex-shrink: 0;"
    >
      <i class="ri-image-edit-line" style="color: #fbbf24; font-size: 16px;"></i>
      <span style="font-size: 11px; color: #fbbf24; font-weight: 500;">上次暂存结果</span>
      <span style="font-size: 10px; color: #94a3b8;">此图展示上次保存时的填涂效果，可在此基础上继续编辑</span>
      <img
        :src="annotatedImageUrl"
        style="max-height: 120px; max-width: 200px; border-radius: 4px; border: 1px solid rgba(148,163,184,0.2); margin-left: auto; object-fit: contain;"
        alt="上次暂存结果预览"
      />
    </div>

    <!-- 主体: 画布 + 表单 -->
    <div style="display: flex; gap: 16px; min-height: 0; flex: 1;">
      <!-- 左侧: 画布 -->
      <div style="background: #0f172a; border-radius: 8px; overflow: hidden; flex: 1; min-height: 500px; position: relative;">
        <MaskEditorAdmin
          ref="maskEditorRef"
          :image-url="imageUrl"
          :editable="true"
          :initial-lesion-layer-url="maskDataUrl || aiMaskLesionUrl"
          :initial-skin-layer-url="skinMaskDataUrl || aiMaskSkinUrl"
          @confirm="handleMaskConfirm"
        />
      </div>

      <!-- 右侧: 表单 -->
      <div style="display: flex; flex-direction: column; gap: 12px; width: 320px; flex-shrink: 0; max-height: 80vh; overflow-y: auto; padding-right: 4px;">
        <div style="background: #1e293b; border-radius: 8px; padding: 14px; border: 1px solid rgba(148,163,184,0.15);">
          <div style="font-size: 12px; color: #94a3b8; margin-bottom: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
            标注信息
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px;">
            <div>
              <label style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">身体部位</label>
              <select v-model="form.body_site" style="width: 100%; padding: 6px 8px; background: #0f172a; color: #e2e8f0; border: 1px solid rgba(148,163,184,0.2); border-radius: 6px; font-size: 12px;">
                <option :value="null">未选择</option>
                <option v-for="opt in bodySiteOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>

            <div>
              <label style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">是否为白癜风</label>
              <div style="display: flex; gap: 4px; padding: 2px; background: #0f172a; border-radius: 6px;">
                <button
                  style="flex: 1; padding: 6px 10px; border-radius: 4px; font-size: 12px; transition: all 0.15s;"
                  :style="form.is_vitiligo === true ? { background: '#f59e0b', color: '#fff' } : { color: '#94a3b8' }"
                  @click="form.is_vitiligo = true"
                >是</button>
                <button
                  style="flex: 1; padding: 6px 10px; border-radius: 4px; font-size: 12px; transition: all 0.15s;"
                  :style="form.is_vitiligo === false ? { background: '#10b981', color: '#fff' } : { color: '#94a3b8' }"
                  @click="form.is_vitiligo = false"
                >否</button>
              </div>
            </div>

            <div v-if="form.is_vitiligo">
              <label style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">分型</label>
              <select v-model="form.vitiligo_type" style="width: 100%; padding: 6px 8px; background: #0f172a; color: #e2e8f0; border: 1px solid rgba(148,163,184,0.2); border-radius: 6px; font-size: 12px;">
                <option :value="null">未选择</option>
                <option v-for="opt in vitiligoTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>

            <div v-if="form.is_vitiligo">
              <label style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">病情阶段</label>
              <select v-model="form.vitiligo_stage" style="width: 100%; padding: 6px 8px; background: #0f172a; color: #e2e8f0; border: 1px solid rgba(148,163,184,0.2); border-radius: 6px; font-size: 12px;">
                <option :value="null">未选择</option>
                <option v-for="opt in stageOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
              <div>
                <label style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">面积 %</label>
                <input
                  v-model.number="form.area_percentage"
                  type="number"
                  min="0" max="100" step="0.1"
                  style="width: 100%; padding: 6px 8px; background: #0f172a; color: #e2e8f0; border: 1px solid rgba(148,163,184,0.2); border-radius: 6px; font-size: 12px;"
                />
              </div>
              <div>
                <label style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">VASI</label>
                <input
                  v-model.number="form.vasi_score"
                  type="number"
                  min="0" step="0.01"
                  style="width: 100%; padding: 6px 8px; background: #0f172a; color: #e2e8f0; border: 1px solid rgba(148,163,184,0.2); border-radius: 6px; font-size: 12px;"
                />
              </div>
            </div>

            <div>
              <label style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">脱色程度 (0-1)</label>
              <input
                v-model.number="form.depigmentation_level"
                type="number"
                min="0" max="1" step="0.05"
                style="width: 100%; padding: 6px 8px; background: #0f172a; color: #e2e8f0; border: 1px solid rgba(148,163,184,0.2); border-radius: 6px; font-size: 12px;"
              />
            </div>

            <div>
              <label style="font-size: 11px; color: #94a3b8; display: block; margin-bottom: 4px;">备注</label>
              <textarea
                v-model="form.notes"
                rows="2"
                placeholder="如：边界清晰、近期扩散等"
                style="width: 100%; padding: 6px 8px; background: #0f172a; color: #e2e8f0; border: 1px solid rgba(148,163,184,0.2); border-radius: 6px; font-size: 12px; resize: vertical;"
              ></textarea>
            </div>

            <div style="display: flex; align-items: center; gap: 6px; padding: 8px; background: #0f172a; border-radius: 6px; border: 1px solid rgba(148,163,184,0.15);">
              <input
                id="training-eligible"
                v-model="form.training_eligible"
                type="checkbox"
                style="accent-color: #6366f1;"
              />
              <label for="training-eligible" style="font-size: 12px; color: #cbd5e1; cursor: pointer;">
                <i class="ri-database-2-line" style="margin-right: 4px;"></i>作为训练数据
              </label>
            </div>
          </div>
        </div>

        <!-- 底部按钮 -->
        <div style="display: flex; gap: 8px; margin-top: auto;">
          <button
            style="flex: 1; padding: 10px; border-radius: 6px; background: rgba(148,163,184,0.1); color: #cbd5e1; font-size: 13px; font-weight: 500;"
            @click="handleCancel"
          >取消</button>
          <button
            style="flex: 1; padding: 10px; border-radius: 6px; background: rgba(245,158,11,0.15); color: #fbbf24; font-size: 13px; font-weight: 500; border: 1px solid rgba(245,158,11,0.3);"
            @click="handleSaveDraft"
          >
            <i class="ri-save-line" style="margin-right: 4px;"></i>暂存
          </button>
          <button
            :disabled="!formValid"
            style="flex: 2; padding: 10px; border-radius: 6px; background: #6366f1; color: #fff; font-size: 13px; font-weight: 600; transition: all 0.15s;"
            :style="!formValid ? { opacity: 0.4, cursor: 'not-allowed' } : { cursor: 'pointer' }"
            @click="handleSubmit"
          >
            <i class="ri-check-line" style="margin-right: 4px;"></i>提交
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* All interactive buttons get pointer cursor */
button {
  cursor: pointer;
  transition: all 0.15s ease;
}
button:disabled {
  cursor: not-allowed;
}

/* Bottom action buttons hover states */
button[style*="rgba(148,163,184,0.1)"]:hover {
  background: rgba(148,163,184,0.2) !important;
}
button[style*="rgba(245,158,11,0.15)"]:hover {
  background: rgba(245,158,11,0.25) !important;
}
button[style*="#6366f1"]:hover:not(:disabled) {
  background: #5558e6 !important;
}

.tool-btn {
  padding: 6px 10px;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  font-size: 13px;
  transition: all 0.15s;
  border: 1px solid transparent;
  cursor: pointer;
}
.tool-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.15);
  color: #c7d2fe;
  border-color: rgba(99, 102, 241, 0.3);
}
.tool-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Form select/input elements */
select, input[type="number"], textarea {
  cursor: pointer;
}

/* Checkbox label */
label[for] {
  cursor: pointer;
}

.ri-spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
