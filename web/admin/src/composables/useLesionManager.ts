/**
 * useLesionManager — manages multiple lesions per image.
 *
 * Each lesion has:
 *   - Unique ID (region_index)
 *   - Canvas mask layers (skin + lesion)
 *   - Classification form data
 *   - Area stats
 *
 * The active lesion's canvas layers are what MaskEditorAdmin renders.
 * Switching lesions swaps the displayed layers.
 */

import { ref, computed } from 'vue'
import type { AdminAnnotationItem } from '@/components/labeling/LabelingEditor.vue'

export interface LesionData {
  regionIndex: number
  label: string           // e.g. "白斑 #1"
  skinMaskDataUrl: string | null   // PNG data URL
  lesionMaskDataUrl: string | null // PNG data URL
  bodySite: string | null
  isVitiligo: boolean | null
  vitiligoType: string | null
  vitiligoStage: string | null
  areaPercentage: number | null
  depigmentationLevel: number | null
  notes: string | null
  active: boolean
}

export function useLesionManager() {
  const lesions = ref<LesionData[]>([])
  const activeIndex = ref(0)
  let nextId = 1

  const activeLesion = computed(() => lesions.value[activeIndex.value] || null)
  const lesionCount = computed(() => lesions.value.length)

  function addLesion(label?: string): LesionData {
    const lesion: LesionData = {
      regionIndex: nextId++,
      label: label || `白斑 #${lesions.value.length + 1}`,
      skinMaskDataUrl: null,
      lesionMaskDataUrl: null,
      bodySite: null,
      isVitiligo: true,
      vitiligoType: null,
      vitiligoStage: null,
      areaPercentage: null,
      depigmentationLevel: null,
      notes: null,
      active: false,
    }
    lesions.value.push(lesion)
    // Auto-switch to the new lesion
    activeIndex.value = lesions.value.length - 1
    return lesion
  }

  function removeLesion(index: number) {
    if (lesions.value.length <= 1) {
      // Don't remove the last lesion — clear it instead
      lesions.value[0] = createEmptyLesion(0)
      activeIndex.value = 0
      return
    }
    lesions.value.splice(index, 1)
    if (activeIndex.value >= lesions.value.length) {
      activeIndex.value = lesions.value.length - 1
    }
  }

  function switchToLesion(index: number) {
    if (index >= 0 && index < lesions.value.length) {
      // Deactivate current
      if (activeLesion.value) activeLesion.value.active = false
      activeIndex.value = index
      if (activeLesion.value) activeLesion.value.active = true
    }
  }

  function updateActiveLesionMask(skinDataUrl: string | null, lesionDataUrl: string | null) {
    const lesion = activeLesion.value
    if (!lesion) return
    if (skinDataUrl) lesion.skinMaskDataUrl = skinDataUrl
    if (lesionDataUrl) lesion.lesionMaskDataUrl = lesionDataUrl
  }

  function reset() {
    lesions.value = [createEmptyLesion(0)]
    activeIndex.value = 0
    nextId = 1
  }

  function createEmptyLesion(index: number): LesionData {
    return {
      regionIndex: index,
      label: `白斑 #${index + 1}`,
      skinMaskDataUrl: null,
      lesionMaskDataUrl: null,
      bodySite: null,
      isVitiligo: true,
      vitiligoType: null,
      vitiligoStage: null,
      areaPercentage: null,
      depigmentationLevel: null,
      notes: null,
      active: index === 0,
    }
  }

  /** Populate from existing admin annotations (e.g., from backend) */
  function loadFromAnnotations(annotations: AdminAnnotationItem[]) {
    reset()
    if (annotations.length === 0) return

    lesions.value = annotations.map((ann, i) => ({
      regionIndex: ann.region_index ?? i,
      label: `白斑 #${i + 1}`,
      skinMaskDataUrl: ann.skin_mask_data ?? null,
      lesionMaskDataUrl: ann.mask_data ?? null,
      bodySite: ann.body_site ?? null,
      isVitiligo: ann.is_vitiligo ?? true,
      vitiligoType: ann.vitiligo_type ?? null,
      vitiligoStage: ann.vitiligo_stage ?? null,
      areaPercentage: ann.area_percentage ?? null,
      depigmentationLevel: ann.depigmentation_level ?? null,
      notes: ann.notes ?? null,
      active: i === 0,
    }))
    nextId = annotations.length
    activeIndex.value = 0
  }

  return {
    lesions,
    activeIndex,
    activeLesion,
    lesionCount,
    addLesion,
    removeLesion,
    switchToLesion,
    updateActiveLesionMask,
    loadFromAnnotations,
    reset,
  }
}
