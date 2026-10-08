<script setup lang="ts">
/** Four views of the same pair; quantification is independent of visual display. */
import { computed, ref, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import ComparisonQuantification from './ComparisonQuantification.vue'
import type { PairAlign, PairMetrics } from '@/api/skin_report'
import { toProtectedFileUrl } from '@/utils/file-url'
import BeforeAfterSlider from '@/components/common/BeforeAfterSlider.vue'
import ReportManualAlignment from './ReportManualAlignment.vue'

const props = defineProps<{
  beforeUrl: string
  afterUrl: string
  align?: PairAlign | null
  metrics?: PairMetrics | null
  beforeLabel?: string
  afterLabel?: string
}>()

type ViewMode = 'side' | 'slider' | 'ghost' | 'anim'
const editingAlignment = ref(false)

// Current reports keep duplicate evidence nested; archived reports may use the top-level flag.
const duplicate = computed(() => props.metrics?.duplicate === true || props.metrics?.evidence?.duplicate === true)
const legacyPositionGate = computed(() => [props.align?.note, props.metrics?.capture_note, ...(props.metrics?.reasons || [])].some(note => note?.includes('请选择同一观察位置的连续记录')))

const aligned = computed(
  () => !duplicate.value && !!props.align?.aligned && !!props.align?.aligned_after_url,
)
// 配准产物存于受保护的 /uploads/ 路径，需附加文件访问 token
const alignedAfterUrl = computed(
  () => aligned.value ? toProtectedFileUrl(props.align?.aligned_after_url) || props.afterUrl : props.afterUrl,
)
const heatmapUrl = computed(() => toProtectedFileUrl(props.align?.heatmap_url))
const alignmentLabel = computed(() => !aligned.value ? '原图' : props.align?.source === 'manual' ? '手动对齐' : '已对齐')

const alignmentNote = computed(() => {
  if (duplicate.value) return '两张照片内容重复，不能用于判断随时间变化。请选择两次不同拍摄的记录。'
  if (aligned.value) return ''
  return '当前按原图对照，可切换视图或手动调整。'
})

const view = ref<ViewMode>('anim')
const ghostOpacity = ref(55)
const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
const animPlaying = ref(!reducedMotion.value)
watch(reducedMotion, reduced => { if (reduced) animPlaying.value = false })
watch(() => [props.beforeUrl, props.afterUrl, props.beforeLabel, props.afterLabel], () => {
  view.value = 'anim'
  animPlaying.value = !reducedMotion.value
})
const viewTabs: { key: ViewMode; label: string; icon: string }[] = [
  { key: 'anim', label: '动画', icon: 'ri-play-circle-line' },
  { key: 'ghost', label: '叠影', icon: 'ri-contrast-drop-2-line' },
  { key: 'slider', label: '滑块', icon: 'ri-arrow-left-right-line' },
  { key: 'side', label: '并排', icon: 'ri-layout-column-line' },
]

function switchView(key: ViewMode) {
  view.value = key
  if (key === 'anim') animPlaying.value = !reducedMotion.value
}

// ── 变化要点 ──
interface ChangeChip {
  icon: string
  text: string
  cls: string
}

const changeChips = computed<ChangeChip[]>(() => {
  const pm = props.metrics
  const chips: ChangeChip[] = []
  if (!pm || duplicate.value || pm.comparison_status !== 'measured') return chips

  const good = 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
  const bad = 'bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300'
  const flat = 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'

  if (pm.size_change_percent != null) {
    const shrink = pm.size_change_percent < 0
    chips.push({
      icon: shrink ? 'ri-zoom-out-line' : 'ri-zoom-in-line',
      text: `面积 ${shrink ? '' : '+'}${pm.size_change_percent}%`,
      cls: shrink ? good : bad,
    })
  }
  if (pm.melanin_score_a != null && pm.melanin_score_b != null) {
    const up = pm.melanin_change != null && pm.melanin_change > 0
    chips.push({
      icon: 'ri-drop-line',
      text: `复色指数 ${pm.melanin_score_a} → ${pm.melanin_score_b}`,
      cls: up ? good : flat,
    })
  }
  const colorMap: Record<string, string> = {
    repigment: '照片颜色变深',
    darker: '照片颜色变深',
    lighter: '颜色变淡',
    whiter: '颜色更白',
    same: '颜色相近',
  }
  if (pm.color_change && colorMap[pm.color_change]) {
    chips.push({
      icon: 'ri-palette-line',
      text: colorMap[pm.color_change],
      cls: pm.color_change === 'repigment' ? good : pm.color_change === 'whiter' ? bad : flat,
    })
  }
  const borderMap: Record<string, string> = {
    inward: '轮廓范围减少',
    outward: '轮廓范围增加',
    stable: '边缘稳定',
  }
  if (pm.border_change && borderMap[pm.border_change]) {
    chips.push({
      icon: 'ri-scan-2-line',
      text: borderMap[pm.border_change],
      cls: pm.border_change === 'inward' ? good : pm.border_change === 'outward' ? bad : flat,
    })
  }
  const sig = pm.melanin_signals || {}
  if (sig.edge_inward) chips.push({ icon: 'ri-shrink-line', text: '边缘出现色素带', cls: good })
  if ((sig.follicular_repigmentation ?? 0) >= 2)
    chips.push({ icon: 'ri-sparkling-line', text: '点状复色明显', cls: good })
  if ((sig.island_repigmentation ?? 0) >= 2)
    chips.push({ icon: 'ri-blur-on-line', text: '色素岛扩大融合', cls: good })

  return chips
})
</script>

<template>
  <div class="cv">
    <ReportManualAlignment v-if="!duplicate" :before-url="beforeUrl" :after-url="afterUrl" :before-label="beforeLabel" :after-label="afterLabel" @editing="editingAlignment = $event" />
    <p v-if="editingAlignment" data-html2canvas-ignore="true" class="text-sm font-medium text-gray-600 dark:text-gray-300 print:hidden">上次分析结果（尚未更新）</p>
    <!-- 视图切换 -->
    <div class="cv__tabs" role="tablist" aria-label="对比视图切换">
      <button
        v-for="t in viewTabs"
        :key="t.key"
        type="button"
        class="cv__tab"
        :class="{ 'cv__tab--active': view === t.key }"
        role="tab"
        :aria-label="t.label"
        :aria-selected="view === t.key"
        @click="switchView(t.key)"
      >
        <i :class="t.icon" aria-hidden="true"></i>
        {{ t.label }}
      </button>
    </div>

    <!-- 并排 -->
    <div v-if="view === 'side'" class="cv__side">
      <figure class="cv__fig">
        <img :src="beforeUrl" alt="前" loading="lazy" />
        <figcaption>前</figcaption>
      </figure>
      <figure class="cv__fig">
        <img :src="afterUrl" alt="后" loading="lazy" />
        <figcaption>后</figcaption>
      </figure>
    </div>

    <!-- 滑块（配准后） -->
    <BeforeAfterSlider
      v-else-if="view === 'slider'"
      :before-url="beforeUrl"
      :after-url="alignedAfterUrl"
      before-label="前"
      after-label="后"
      alt="白斑前后滑块对比"
      image-fit="contain"
    />

    <!-- 叠影（配准后，透明度可调） -->
    <div v-else-if="view === 'ghost'" class="cv__ghost">
      <div class="cv__ghost-stage">
        <img :src="beforeUrl" alt="前" loading="lazy" />
        <img
          class="cv__ghost-top"
          :src="alignedAfterUrl"
          alt="后"
          :style="{ opacity: ghostOpacity / 100 }"
          loading="lazy"
        />
      </div>
      <label class="cv__ghost-ctl">
        <span class="cv__ghost-tag">前</span>
        <input v-model.number="ghostOpacity" type="range" min="0" max="100" step="1" aria-label="叠影透明度" />
        <span class="cv__ghost-tag cv__ghost-tag--after">后</span>
      </label>
    </div>

    <!-- 动画（自动渐变） -->
    <div v-else-if="view === 'anim'" class="cv__anim">
      <div class="cv__ghost-stage" :class="{ 'cv__anim--paused': !animPlaying }">
        <img :src="beforeUrl" alt="前" loading="lazy" />
        <img class="cv__ghost-top cv__anim-top" :src="alignedAfterUrl" alt="后" loading="lazy" />
      </div>
      <div class="cv__anim-ctl">
        <button type="button" class="cv__anim-btn" @click="animPlaying = !animPlaying">
          <i :class="animPlaying ? 'ri-pause-circle-line' : 'ri-play-circle-line'"></i>
          {{ animPlaying ? '暂停' : '播放' }}
        </button>
        <span class="cv__anim-hint">
          <i class="ri-time-line"></i>
          前 ⇄ 后 · {{ alignmentLabel }}
        </span>
      </div>
    </div>

    <!-- 缺少对齐产物并不等于拍摄角度不同，按服务证据说明原因。 -->
    <p v-if="!aligned && !editingAlignment" class="cv__align-note">
      <i class="ri-information-line"></i>
      {{ alignmentNote }}
    </p>

    <ComparisonQuantification :metrics="metrics" />

    <!-- 变化热力图（白斑掩膜差分；门禁不通过时后端不出图） -->
    <div v-if="!duplicate && align?.heatmap_url" class="cv__heat">
      <div class="cv__heat-head">
        <i class="ri-fire-line"></i> 变化热力图
      </div>
      <img :src="heatmapUrl" alt="白斑变化热力图" loading="lazy" class="cv__heat-img" />
      <div class="cv__heat-legend">
        <span class="cv__legend cv__legend--good">
          <i></i> 轮廓范围减少（照片观察）<template v-if="align.classes?.repigmented_px">· {{ align.classes.repigmented_px }}px</template>
        </span>
        <span class="cv__legend cv__legend--bad">
          <i></i> 轮廓范围增加（照片观察）<template v-if="align.classes?.expanded_px">· {{ align.classes.expanded_px }}px</template>
        </span>
      </div>
      <p class="cv__heat-note">
        <i class="ri-information-line"></i> 仅比对两图皮肤内的白斑区域，衣物与背景不参与；照片条件差异较大时自动隐藏此图
      </p>
    </div>
    <p v-else-if="aligned && align?.note" class="cv__heat-note">
      <i class="ri-information-line"></i> 变化热力图未生成：{{ align.note }}
    </p>

    <!-- 变化要点 -->
    <div v-if="!duplicate && !legacyPositionGate && (changeChips.length || metrics)" class="cv__points">
      <div v-if="changeChips.length" class="cv__chips">
        <span v-for="(c, i) in changeChips" :key="i" class="cv__chip" :class="c.cls">
          <i :class="c.icon"></i> {{ c.text }}
        </span>
      </div>
      <p v-if="metrics?.change_interval_percent?.length === 2" class="cv__note">边界敏感性范围：{{ metrics.change_interval_percent[0] }}% 至 {{ metrics.change_interval_percent[1] }}%。此范围反映轮廓误差，不是临床置信区间。</p>
      <p v-if="metrics?.color_reason" class="cv__note">{{ metrics.color_reason }}</p>
      <p v-if="metrics?.summary" class="cv__summary">{{ metrics.summary }}</p>
      <p v-if="metrics?.capture_note" class="cv__note">
        <i class="ri-information-line"></i> {{ metrics.capture_note }}
      </p>
      <p v-if="metrics?.comparison_status !== 'measured'" class="cv__note cv__note--warn">
        <i class="ri-error-warning-line"></i>
        {{ metrics?.comparison_status === 'visual_only' ? '以上为图像观察，未输出未经验证的变化百分比。' : '本次未通过变化测量校验，不显示面积或颜色的变化结论。' }}
      </p>
    </div>
  </div>
</template>

<style scoped src="./ComparisonViews.css"></style>
