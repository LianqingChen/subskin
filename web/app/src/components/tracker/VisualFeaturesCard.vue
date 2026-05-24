<script setup lang="ts">
import { ref } from 'vue'
import type { VisualFeatures, VisualFeatureDimension } from '@/api/vasi'

defineProps<{
  visualFeatures: VisualFeatures
}>()

const emit = defineEmits<{
  continue: []
}>()

const showKnowledge = ref(false)

const LEVEL_MAP: Record<string, Record<string, string>> = {
  visibility: { visible: '清晰可见', faint: '隐约可见', subtle: '不明显' },
  color: { pale_white: '淡白', milky_white: '乳白', porcelain_white: '瓷白', pure_white: '纯白' },
  border: { clear: '清晰', partial: '部分清晰', unclear: '模糊' },
  surface: { smooth: '光滑', scaly: '有鳞屑', atrophic: '有萎缩', other: '其他' },
  distribution: { localized: '局部', segmental: '节段性', bilateral: '双侧对称', generalized: '广泛分布' },
}

function levelLabel(dim: string, feat: VisualFeatureDimension): string | null {
  const map = LEVEL_MAP[dim]
  if (!map) return null
  const key = feat.level || feat.texture || feat.pattern
  return key ? map[key] || key : null
}

const dimensions = [
  { key: 'visibility' as const, icon: 'ri-eye-line', label: '可见性' },
  { key: 'color' as const, icon: 'ri-palette-line', label: '颜色' },
  { key: 'border' as const, icon: 'ri-focus-2-line', label: '边缘' },
  { key: 'shape' as const, icon: 'ri-shapes-line', label: '形态' },
  { key: 'surface' as const, icon: 'ri-brush-line', label: '表面' },
  { key: 'distribution' as const, icon: 'ri-map-pin-line', label: '分布' },
]
</script>

<template>
  <div class="card dark:bg-gray-800 overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center gap-2">
      <div class="w-6 h-6 rounded-lg bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center">
        <i class="ri-search-eye-line text-primary-600 dark:text-primary-400 text-xs"></i>
      </div>
      <span class="font-semibold text-sm text-gray-800 dark:text-gray-200">白斑视觉特征分析</span>
      <span class="ml-auto px-1.5 py-0.5 rounded text-[10px] bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400">仅供参考</span>
    </div>

    <!-- Conclusion: similarity_note + recommendation combined -->
    <div v-if="visualFeatures.similarity_note" class="px-4 py-2.5">
      <p class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed flex items-start gap-1.5">
        <i class="ri-information-line text-primary-500 mt-0.5 flex-shrink-0"></i>
        <span>
          {{ visualFeatures.similarity_note }}
          <template v-if="visualFeatures.recommendation">
            {{ visualFeatures.recommendation }}
          </template>
        </span>
      </p>
    </div>

    <!-- 6 Feature Dimensions — compact single-line each -->
    <div class="px-4 py-2.5 space-y-1.5 border-t border-gray-50 dark:border-gray-700/50">
      <div
        v-for="dim in dimensions"
        :key="dim.key"
        class="flex items-center gap-2 text-xs"
      >
        <i :class="[dim.icon, 'text-gray-400 dark:text-gray-500 w-4 text-center flex-shrink-0']"></i>
        <span class="font-medium text-gray-600 dark:text-gray-400 w-10 flex-shrink-0">{{ dim.label }}</span>
        <span
          v-if="levelLabel(dim.key, visualFeatures[dim.key])"
          class="px-1.5 py-px rounded text-[10px] font-medium bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 flex-shrink-0"
        >
          {{ levelLabel(dim.key, visualFeatures[dim.key]) }}
        </span>
        <span class="text-gray-500 dark:text-gray-500 truncate">{{ visualFeatures[dim.key].description }}</span>
      </div>
    </div>

    <!-- Knowledge Card (collapsible) -->
    <div class="px-4 pb-1">
      <button
        class="w-full flex items-center gap-2 py-2 px-2.5 rounded-lg bg-blue-50/50 dark:bg-blue-900/20 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors min-h-[44px]"
        @click="showKnowledge = !showKnowledge"
      >
        <i class="ri-book-open-line text-blue-500 dark:text-blue-400 text-xs"></i>
        <span class="text-xs text-blue-600 dark:text-blue-400">白癜风常见特征（科普参考）</span>
        <i
          :class="[
            'ml-auto text-blue-400 transition-transform duration-200 text-xs',
            showKnowledge ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line',
          ]"
        ></i>
      </button>
      <div
        v-if="showKnowledge"
        class="mt-1.5 px-3 py-2 rounded-lg bg-blue-50/30 dark:bg-blue-900/10 text-xs text-gray-600 dark:text-gray-400 space-y-1 leading-relaxed"
      >
        <p>· 颜色：乳白色或瓷白色，与正常皮肤色差明显</p>
        <p>· 边缘：边界通常清晰，边缘可能有色素加深</p>
        <p>· 表面：通常光滑无鳞屑</p>
        <p>· 形态：圆形、椭圆形或不规则形</p>
        <p>· 分布：可对称分布或沿神经节段分布</p>
        <div class="mt-2 pt-2 border-t border-blue-100 dark:border-blue-800">
          <p class="text-amber-600 dark:text-amber-400 flex items-start gap-1">
            <i class="ri-error-warning-line mt-0.5"></i>
            <span>以上为科普信息，仅供参考。具体诊断需专业医生结合 Wood 灯等检查综合判断。</span>
          </p>
        </div>
      </div>
    </div>

    <!-- Disclaimer -->
    <div class="px-4 py-2.5">
      <p class="text-[10px] text-gray-400 dark:text-gray-500 flex items-start gap-1">
        <i class="ri-shield-check-line mt-0.5 flex-shrink-0"></i>
        <span>以上分析基于照片视觉观察，仅供参考，不构成医疗诊断。</span>
      </p>
    </div>

    <!-- Continue Button -->
    <div class="px-4 pb-4">
      <button
        class="w-full py-3 rounded-xl bg-primary-500 hover:bg-primary-600 active:bg-primary-700 text-white text-sm font-medium transition-colors flex items-center justify-center gap-1.5 min-h-[44px]"
        @click="emit('continue')"
      >
        继续VASI测评
        <i class="ri-arrow-right-line"></i>
      </button>
    </div>
  </div>
</template>
