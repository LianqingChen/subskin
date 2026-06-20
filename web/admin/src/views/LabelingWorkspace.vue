<script setup lang="ts">
/**
 * LabelingWorkspace — full-page labeling workspace at /#/image-labeling/:id
 *
 * Layout: [Toolbar] [Canvas (flex-1) | Right Panel (320px)]
 * Right Panel: LesionPanel + Classification Form + Actions
 */

import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import request from '@/api/request'
import MaskEditorAdmin from '@/components/labeling/MaskEditorAdmin.vue'
import LesionPanel from '@/components/labeling/LesionPanel.vue'
import ShortcutPanel from '@/components/labeling/ShortcutPanel.vue'
import { useLesionManager } from '@/composables/useLesionManager'
import type { AdminAnnotationItem } from '@/components/labeling/LabelingEditor.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const labelId = computed(() => Number(route.params.id))
const imageUrl = ref('')
const imageHash = ref<string | null>(null)
const annotatedImageUrl = ref<string | null>(null)
const loading = ref(true)
const saving = ref(false)

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
  training_eligible: true,
})

// ── AI pretrain ──
const aiPretraining = ref(false)

// ── Options ──
const bodySiteOptions = [
  { label: '面部', value: 'face' }, { label: '颈部', value: 'neck' },
  { label: '躯干', value: 'trunk' }, { label: '上肢', value: 'upper_limb' },
  { label: '下肢', value: 'lower_limb' }, { label: '手部', value: 'hand' },
  { label: '足部', value: 'foot' }, { label: '头皮', value: 'scalp' },
  { label: '全身', value: 'whole_body' },
]

const vitiligoTypeOptions = [
  { label: '非节段型', value: 'non_segmental' }, { label: '节段型', value: 'segmental' },
  { label: '混合型', value: 'mixed' }, { label: '未分类型', value: 'unclassified' },
  { label: '非白癜风', value: 'not_vitiligo' },
]

const stageOptions = [
  { label: '进展期', value: 'progressing' }, { label: '稳定期', value: 'stable' },
  { label: '好转期', value: 'improving' }, { label: '不确定', value: 'uncertain' },
]

// ── Load image data ──
async function loadImageData() {
  loading.value = true
  try {
    const token = localStorage.getItem('admin_token') || ''
    imageUrl.value = `/api/vasi/admin/image-labels/${labelId.value}/image?access_token=${encodeURIComponent(token)}`

    // Load detail
    const { data: detail } = await request.get(`/vasi/admin/image-labels/${labelId.value}`)
    if (detail.annotated_image_url) {
      annotatedImageUrl.value = `/api/vasi/admin/image-labels/${labelId.value}/annotated-image?access_token=${encodeURIComponent(token)}`
    }
    if (detail.image_hash) imageHash.value = detail.image_hash

    // Pre-fill form from admin data or AI data
    if (detail.admin_is_vitiligo != null) {
      Object.assign(form, {
        body_site: detail.admin_body_site ?? null,
        is_vitiligo: detail.admin_is_vitiligo ?? true,
        vitiligo_type: detail.admin_vitiligo_type ?? null,
        vitiligo_stage: detail.admin_vitiligo_stage ?? null,
        area_percentage: detail.admin_area_percentage ?? null,
        vasi_score: detail.admin_vasi_score ?? null,
        depigmentation_level: detail.admin_depigmentation_level ?? null,
        notes: detail.admin_notes ?? '',
        training_eligible: detail.training_eligible ?? true,
      })
    } else {
      Object.assign(form, {
        body_site: detail.ai_body_site ?? null,
        is_vitiligo: detail.ai_is_vitiligo ?? true,
        vitiligo_type: detail.ai_vitiligo_type ?? null,
        vitiligo_stage: detail.ai_vitiligo_stage ?? null,
        area_percentage: detail.ai_area_percentage ?? null,
        vasi_score: detail.ai_vasi_score ?? null,
        depigmentation_level: detail.ai_depigmentation_level ?? null,
      })
    }

    // Load existing annotations
    try {
      const { data: annData } = await request.get<{ annotations: AdminAnnotationItem[] }>(
        `/vasi/admin/image-labels/${labelId.value}/annotations`
      )
      if (annData.annotations && annData.annotations.length > 0) {
        lesionManager.loadFromAnnotations(annData.annotations)
      }
    } catch { /* no existing annotations */ }
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '加载图片失败')
  } finally {
    loading.value = false
  }
}

// ── AI Pretrain ──
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
      // Load AI masks into canvas
      await maskEditorRef.value?.loadMaskLayers(
        data.skin_layer_data_url || null,
        data.lesion_layer_data_url || null,
      )
      message.success(`AI 预标注完成, 耗时 ${Math.round((data.duration_ms || 0) / 1000)}s`)
    }
    if (data.body_site && !form.body_site) form.body_site = data.body_site
    if (data.is_vitiligo != null && form.is_vitiligo == null) form.is_vitiligo = data.is_vitiligo
  } catch (err: any) {
    message.error(err?.response?.data?.detail || 'AI 预标注失败')
  } finally {
    aiPretraining.value = false
  }
}

// ── Save ──
async function handleSave() {
  saving.value = true
  try {
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

    const annotatedImage = maskEditorRef.value?.getAnnotatedImageDataUrl?.() || null

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
      annotations,
      annotated_image: annotatedImage,
    })
    message.success('标注已保存!')
  } catch (err: any) {
    message.error(err?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function goBack() {
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
  loadImageData()
})
</script>

<template>
  <div :style="{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0f172a', color: '#e2e8f0' }">
    <!-- Top bar -->
    <div :style="{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px 16px', background: '#1e293b', borderBottom: '1px solid rgba(148,163,184,0.1)', flexShrink: 0 }">
      <button
        :style="{ padding: '6px 10px', borderRadius: '6px', background: 'transparent', color: '#94a3b8', border: '1px solid rgba(148,163,184,0.2)', cursor: 'pointer', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '4px' }"
        @click="goBack"
      >
        <i class="ri-arrow-left-line"></i> 返回
      </button>
      <span :style="{ fontSize: '14px', fontWeight: 600 }">图片打标 #{{ labelId }}</span>
      <span v-if="form.body_site" :style="{ fontSize: '11px', color: '#64748b' }">{{ form.body_site }}</span>

      <div :style="{ marginLeft: 'auto', display: 'flex', gap: '8px' }">
        <button
          :disabled="aiPretraining"
          :style="{ padding: '6px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '4px', background: aiPretraining ? 'rgba(59,130,246,0.1)' : 'rgba(59,130,246,0.2)', color: '#93c5fd', border: '1px solid rgba(59,130,246,0.4)', cursor: aiPretraining ? 'not-allowed' : 'pointer' }"
          @click="handleAiPretrain"
        >
          <i class="ri-robot-2-line" :class="{ 'ri-spin': aiPretraining }"></i>
          AI 预标注
        </button>
        <button
          :disabled="saving"
          :style="{ padding: '6px 14px', borderRadius: '6px', fontSize: '12px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '4px', background: 'rgba(245,158,11,0.15)', color: '#fbbf24', border: '1px solid rgba(245,158,11,0.3)', cursor: 'pointer' }"
          @click="handleSave"
        >
          <i :class="saving ? 'ri-loader-4-line ri-spin' : 'ri-save-line'"></i>
          暂存
        </button>
        <button
          :disabled="saving"
          :style="{ padding: '6px 20px', borderRadius: '6px', fontSize: '12px', fontWeight: 600, background: '#6366f1', color: '#fff', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }"
          @click="handleSave"
        >
          <i class="ri-check-line"></i>
          提交标注
        </button>
      </div>
    </div>

    <!-- Main content -->
    <div v-if="loading" :style="{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }">
      <div :style="{ width: '32px', height: '32px', border: '3px solid rgba(148,163,184,0.2)', borderTopColor: '#6366f1', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }"></div>
    </div>

    <div v-else :style="{ flex: 1, display: 'flex', gap: '12px', padding: '12px', minHeight: 0, overflow: 'hidden' }">
      <!-- Canvas (left) -->
      <div :style="{ flex: 1, minWidth: 0, background: '#1e293b', borderRadius: '8px', overflow: 'hidden' }">
        <MaskEditorAdmin
          ref="maskEditorRef"
          :image-url="imageUrl"
          :editable="true"
          @confirm="handleCanvasConfirm"
        />
      </div>

      <!-- Right panel -->
      <div :style="{ width: '340px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto' }">
        <!-- Lesion panel -->
        <div :style="{ background: '#1e293b', borderRadius: '8px', padding: '12px', border: '1px solid rgba(148,163,184,0.12)' }">
          <LesionPanel :manager="lesionManager" @lesion-changed="handleLesionChanged" />
        </div>

        <!-- Classification form -->
        <div :style="{ background: '#1e293b', borderRadius: '8px', padding: '14px', border: '1px solid rgba(148,163,184,0.12)' }">
          <div :style="{ fontSize: '12px', color: '#94a3b8', marginBottom: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }">
            分类信息
          </div>

          <div :style="{ display: 'flex', flexDirection: 'column', gap: '8px' }">
            <select v-model="form.body_site" :style="selectStyle">
              <option :value="null">选择身体部位</option>
              <option v-for="opt in bodySiteOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>

            <div :style="{ display: 'flex', gap: '4px', padding: '2px', background: '#0f172a', borderRadius: '6px' }">
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

            <div :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }">
              <input v-model.number="form.area_percentage" type="number" min="0" max="100" step="0.1" placeholder="面积 %" :style="inputStyle" />
              <input v-model.number="form.vasi_score" type="number" min="0" step="0.01" placeholder="VASI 评分" :style="inputStyle" />
            </div>

            <input v-model.number="form.depigmentation_level" type="number" min="0" max="1" step="0.05" placeholder="脱色程度 (0-1)" :style="inputStyle" />

            <textarea v-model="form.notes" rows="2" placeholder="备注说明" :style="{ ...inputStyle, resize: 'vertical' }"></textarea>

            <label :style="{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#cbd5e1', cursor: 'pointer', padding: '6px 8px', background: '#0f172a', borderRadius: '6px' }">
              <input v-model="form.training_eligible" type="checkbox" style="accent-color: #6366f1;" />
              <i class="ri-database-2-line"></i> 作为训练数据
            </label>
          </div>
        </div>

        <!-- Shortcuts -->
        <ShortcutPanel />
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes spin { to { transform: rotate(360deg); } }
.ri-spin { animation: spin 1s linear infinite; }
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
