<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import butterflyMascot from '/butterfly_mascot.png'

interface BodyPart {
  id: string
  label: string
  bodySite: string
  /** 标签所在列：left = 图左侧（文字右对齐），right = 图右侧 */
  side: 'left' | 'right'
  hits: { cx: number; cy: number; rx: number; ry: number }[]
  /** 引导线在身体上的锚点（位于部位外缘，保证连线只穿过空白背景） */
  anchor: { x: number; y: number }
  labelX: number
  labelY: number
}

const props = withDefaults(defineProps<{
  mode?: 'rain' | 'wave'
  showParts?: boolean
  activePart?: string | null
}>(), {
  mode: 'rain',
  showParts: true,
  activePart: null,
})

const emit = defineEmits<{
  'select-part': [bodySite: string]
}>()

const imageAreaRef = ref<HTMLDivElement>()
const isRainMode = computed(() => props.mode === 'rain')
const isWaveMode = computed(() => props.mode === 'wave')

const showRain = ref(false)
const showCurtain = ref(false)
const showPartsInternal = ref(false)
const rainColumns = ref<Array<{ id: number; left: string; duration: number; delay: number; chars: string; fontSize: number; opacity: number }>>([])

const RAIN_CHARS = 'ｦｧｨｩｪｫｬｭｮｯｱｲｳｵｶXML012345λφΩ∑αβδγ'

function randomChar() {
  return RAIN_CHARS[Math.floor(Math.random() * RAIN_CHARS.length)]
}

function genColumn(len: number) {
  let s = ''
  for (let i = 0; i < len; i++) s += randomChar() + '\n'
  return s
}

function generateColumns() {
  const cols: typeof rainColumns.value = []
  for (let i = 0; i < 18; i++) {
    cols.push({
      id: i,
      left: ((i / 18) * 100).toFixed(1) + '%',
      duration: 3 + Math.random() * 3,
      delay: Math.random() * 1.5,
      chars: genColumn(20 + Math.floor(Math.random() * 30)),
      fontSize: 14 + Math.random() * 8,
      opacity: 0.3 + Math.random() * 0.5,
    })
  }
  return cols
}

let rainTimer: ReturnType<typeof setTimeout> | null = null
let curtainTimer: ReturnType<typeof setTimeout> | null = null
let cycleTimer: ReturnType<typeof setTimeout> | null = null

function triggerRain() {
  if (!isRainMode.value) return
  showPartsInternal.value = false
  showCurtain.value = true
  curtainTimer = setTimeout(() => {
    showCurtain.value = false
    rainColumns.value = generateColumns()
    showRain.value = true
    rainTimer = setTimeout(() => {
      showRain.value = false
      rainColumns.value = []
      showPartsInternal.value = props.showParts
      scheduleNext()
    }, 5000)
  }, 600)
}

function scheduleNext() {
  if (!isRainMode.value) return
  cycleTimer = setTimeout(() => triggerRain(), 10000 + Math.random() * 10000)
}

const waveBars = [{ delay: '0s', duration: '2.5s' }]

// ── 部位标定（坐标系 = butterfly_mascot.png 原图像素 1280×1280）──
// viewBox 与图片同为正方形，object-contain 与 SVG meet 的 letterbox 完全一致，
// 任何容器形状下标注都不漂移。坐标基于图像素轮廓逐部位标定（2026-08 校准）：
// 锚点取部位朝向标签一侧的外缘，引导线为水平直线、只穿过空白背景，互不交叉。
// 背部在正面图上不可见，取躯干左侧（腰侧）作近似锚点；头部取头顶（头皮），
// 面部取五官区，两者命中区在额头重叠时面部优先。
// 数组顺序即命中优先级（后者覆盖前者）：手部与面部/手臂命中区重叠，故手部最后渲染。
// 右侧标签 labelX=1032：为选中后的「 ✓」对号预留宽度（标签2字+空格+对号 ≤ 3.5em，
// 配合 labelFont 封顶 64，总宽 ≤ 224，不超出 1280 画布被裁剪）。
const frontParts: BodyPart[] = [
  { id: 'head', label: '头部', bodySite: 'head', side: 'right',
    hits: [{ cx: 665, cy: 70, rx: 78, ry: 42 }], anchor: { x: 738, y: 78 }, labelX: 1032, labelY: 70 },
  { id: 'face', label: '面部', bodySite: 'face', side: 'right',
    hits: [{ cx: 672, cy: 138, rx: 80, ry: 52 }], anchor: { x: 750, y: 140 }, labelX: 1032, labelY: 140 },
  { id: 'neck', label: '脖子', bodySite: 'neck', side: 'left',
    hits: [{ cx: 648, cy: 185, rx: 34, ry: 22 }], anchor: { x: 612, y: 190 }, labelX: 185, labelY: 190 },
  { id: 'right_arm', label: '右臂', bodySite: 'right_arm', side: 'left',
    hits: [{ cx: 400, cy: 262, rx: 78, ry: 48 }, { cx: 282, cy: 230, rx: 52, ry: 82 }],
    anchor: { x: 252, y: 285 }, labelX: 185, labelY: 275 },
  { id: 'chest', label: '胸部', bodySite: 'chest', side: 'left',
    hits: [{ cx: 642, cy: 292, rx: 102, ry: 88 }], anchor: { x: 534, y: 360 }, labelX: 185, labelY: 345 },
  { id: 'back', label: '背部', bodySite: 'back', side: 'left',
    hits: [{ cx: 487, cy: 470, rx: 28, ry: 60 }], anchor: { x: 508, y: 470 }, labelX: 185, labelY: 470 },
  { id: 'abdomen', label: '腹部', bodySite: 'abdomen', side: 'right',
    hits: [{ cx: 618, cy: 478, rx: 98, ry: 92 }], anchor: { x: 730, y: 470 }, labelX: 1032, labelY: 470 },
  { id: 'left_arm', label: '左臂', bodySite: 'left_arm', side: 'right',
    hits: [{ cx: 762, cy: 298, rx: 62, ry: 100 }], anchor: { x: 832, y: 368 }, labelX: 1032, labelY: 368 },
  { id: 'right_leg', label: '右腿', bodySite: 'right_leg', side: 'left',
    hits: [{ cx: 530, cy: 685, rx: 62, ry: 95 }, { cx: 498, cy: 925, rx: 66, ry: 135 }],
    anchor: { x: 443, y: 930 }, labelX: 185, labelY: 930 },
  { id: 'left_leg', label: '左腿', bodySite: 'left_leg', side: 'right',
    hits: [{ cx: 646, cy: 695, rx: 62, ry: 105 }, { cx: 658, cy: 940, rx: 64, ry: 130 }],
    anchor: { x: 718, y: 930 }, labelX: 1032, labelY: 930 },
  { id: 'right_foot', label: '右脚', bodySite: 'right_foot', side: 'left',
    hits: [{ cx: 462, cy: 1148, rx: 100, ry: 80 }], anchor: { x: 362, y: 1180 }, labelX: 185, labelY: 1180 },
  { id: 'left_foot', label: '左脚', bodySite: 'left_foot', side: 'right',
    hits: [{ cx: 672, cy: 1148, rx: 100, ry: 78 }], anchor: { x: 768, y: 1180 }, labelX: 1032, labelY: 1180 },
  { id: 'right_hand', label: '右手', bodySite: 'right_hand', side: 'left',
    hits: [{ cx: 258, cy: 88, rx: 68, ry: 78 }], anchor: { x: 218, y: 85 }, labelX: 185, labelY: 85 },
  { id: 'left_hand', label: '左手', bodySite: 'left_hand', side: 'right',
    hits: [{ cx: 654, cy: 148, rx: 66, ry: 60 }], anchor: { x: 718, y: 185 }, labelX: 1032, labelY: 230 },
]

const visibleParts = computed(() => frontParts)

function onPartClick(part: BodyPart) {
  emit('select-part', part.bodySite)
}

let onTouchStart: (() => void) | null = null
let onTouchEnd: (() => void) | null = null

// ── 部位标签随渲染尺寸自适应 ──
// 小人整体随容器缩放，若标签字号固定在 viewBox 坐标系里，小人变小时标签会跟着变小到看不清。
// 这里按实际渲染尺寸把标签锁定在 15-22px（渲染值），换算回 1280 坐标系。
const svgRef = ref<SVGSVGElement | null>(null)
const renderedSize = ref(320)
let resizeObserver: ResizeObserver | null = null

/** 标签字号（viewBox 单位）：目标渲染 15-22px，封顶 64 保证「标签+对号」不超出画布 */
const labelFont = computed(() => {
  const px = Math.min(22, Math.max(15, renderedSize.value * 0.05))
  return Math.min(64, Math.round((px * 1280) / Math.max(1, renderedSize.value)))
})
/** 标签白描边宽度 */
const labelHalo = computed(() => Math.max(5, Math.round(labelFont.value * 0.15)))
/** 引导虚线宽度 */
const lineStroke = computed(() => Math.max(2, Math.round(labelFont.value * 0.05)))
/** 锚点圆半径 */
const anchorR = computed(() => Math.max(7, Math.round(labelFont.value * 0.17)))
/** 引导线与标签的间距 */
const labelGap = computed(() => Math.max(10, Math.round(labelFont.value * 0.22)))
/** 引导线指向标签的竖直中心（相对基线上移） */
const labelMidOffset = computed(() => Math.round(labelFont.value * 0.32))

onMounted(() => {
  const el = imageAreaRef.value
  if (!el) return
  onTouchStart = () => nextTick()
  onTouchEnd = () => nextTick()
  el.addEventListener('touchstart', onTouchStart, { passive: true })
  el.addEventListener('touchend', onTouchEnd, { passive: true })
  el.addEventListener('touchcancel', onTouchEnd, { passive: true })
  showPartsInternal.value = props.showParts
  if (svgRef.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect
      if (r) renderedSize.value = Math.max(120, Math.floor(Math.min(r.width, r.height)))
    })
    resizeObserver.observe(svgRef.value)
  }
})

defineExpose({ triggerRain })

onUnmounted(() => {
  if (rainTimer) clearTimeout(rainTimer)
  if (curtainTimer) clearTimeout(curtainTimer)
  if (cycleTimer) clearTimeout(cycleTimer)
  resizeObserver?.disconnect()
  nextTick()
  const el = imageAreaRef.value
  if (el) {
    if (onTouchStart) el.removeEventListener('touchstart', onTouchStart)
    if (onTouchEnd) {
      el.removeEventListener('touchend', onTouchEnd)
      el.removeEventListener('touchcancel', onTouchEnd)
    }
  }
})
</script>

<template>
  <div class="relative w-full h-full">
    <div
      ref="imageAreaRef"
      class="absolute inset-0"
      :style="{ touchAction: 'none' }"
      data-swipe-ignore
    >
      <div class="w-full h-full">
        <img
          :src="butterflyMascot"
          alt="小金 - 身体部位参考图"
          class="w-full h-full object-contain select-none relative z-10"
          draggable="false"
        />
      </div>

      <div v-if="isWaveMode" :key="1" class="absolute inset-0 pointer-events-none overflow-hidden" :style="{ zIndex: 12 }">
        <div
          v-for="(bar, i) in waveBars"
          :key="'w' + i"
          class="wave-bar"
          :style="{ animationDelay: bar.delay, animationDuration: bar.duration }"
        ></div>
      </div>

      <Transition name="parts-fade">
        <div v-if="showPartsInternal" class="absolute inset-0" :style="{ zIndex: 20, pointerEvents: 'none' }">
          <svg
            ref="svgRef"
            viewBox="0 0 1280 1280"
            class="w-full h-full"
            :style="{ pointerEvents: 'auto' }"
            preserveAspectRatio="xMidYMid meet"
          >
            <g
              v-for="part in visibleParts"
              :key="part.id"
              class="body-part-group"
              role="button"
              tabindex="0"
              :aria-label="part.label"
              @keydown.enter.prevent="onPartClick(part)"
              @keydown.space.prevent="onPartClick(part)"
            >
              <ellipse
                v-for="(hit, hi) in part.hits"
                :key="'hit-' + hi"
                :cx="hit.cx"
                :cy="hit.cy"
                :rx="hit.rx + 20"
                :ry="hit.ry + 20"
                fill="transparent"
                stroke="transparent"
                class="cursor-pointer"
                @click.stop="onPartClick(part)"
              />
              <!-- 引导线：锚点 → 标签，一条水平虚线（锚点取部位外缘，线不穿过身体） -->
              <line
                :x1="part.anchor.x"
                :y1="part.anchor.y"
                :x2="part.side === 'left' ? part.labelX + labelGap : part.labelX - labelGap"
                :y2="part.labelY - labelMidOffset"
                stroke="#26A69A"
                :stroke-width="lineStroke"
                stroke-dasharray="7 5"
                stroke-linecap="round"
                opacity="0.75"
              />
              <circle
                :cx="part.anchor.x"
                :cy="part.anchor.y"
                :r="anchorR"
                fill="#26A69A"
                opacity="0.9"
                class="cursor-pointer"
                @click.stop="onPartClick(part)"
              />
              <text
                :x="part.labelX"
                :y="part.labelY"
                :text-anchor="part.side === 'left' ? 'end' : 'start'"
                fill="#0f9d8f"
                :font-size="labelFont"
                font-family="system-ui, -apple-system, sans-serif"
                font-weight="600"
                stroke="#ffffff"
                :stroke-width="labelHalo"
                stroke-linejoin="round"
                paint-order="stroke"
                class="select-none part-label cursor-pointer"
                :class="{ 'part-label--active': activePart === part.bodySite }"
                @click.stop="onPartClick(part)"
                >{{ part.label }}<tspan v-if="activePart === part.bodySite" class="part-label__check"> ✓</tspan></text>
            </g>
          </svg>
        </div>
      </Transition>

      <div v-if="isRainMode" :key="2" class="absolute top-0 left-0 right-0 pointer-events-none" :style="{ zIndex: 16, height: '2px' }">
        <Transition name="curtain-sweep">
          <div v-if="showCurtain" class="h-full w-full" :style="{ background: 'linear-gradient(90deg, transparent 0%, rgba(38,166,154,0.9) 30%, rgba(38,166,154,0.9) 70%, transparent 100%)', boxShadow: '0 0 12px rgba(38,166,154,0.6), 0 0 30px rgba(38,166,154,0.2)' }"></div>
        </Transition>
      </div>

      <Transition name="rain-fade">
        <div v-if="isRainMode && showRain" class="absolute inset-0 pointer-events-none overflow-hidden" :style="{ zIndex: 15 }">
          <div
            v-for="col in rainColumns"
            :key="col.id"
            class="rain-column"
            :style="{ left: col.left, animationDuration: col.duration + 's', animationDelay: col.delay + 's', fontSize: col.fontSize + 'px', opacity: col.opacity }"
          >{{ col.chars }}</div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.curtain-sweep-enter-active{animation:curtain-slide .5s ease-out forwards}.curtain-sweep-leave-active{transition:opacity .15s ease-in}.curtain-sweep-leave-to{opacity:0}@keyframes curtain-slide{0%{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}.rain-fade-enter-active{transition:opacity .3s ease-out}.rain-fade-leave-active{transition:opacity .4s ease-in}.rain-fade-enter-from,.rain-fade-leave-to{opacity:0}.rain-column{position:absolute;top:-5%;font-family:Courier New,monospace;font-weight:700;color:#26a69a;text-shadow:0 0 6px rgba(38,166,154,.6);white-space:pre;line-height:1.3;animation-name:rain-fall;animation-timing-function:linear;animation-fill-mode:forwards}.rain-column:first-line{color:#fff;text-shadow:0 0 14px rgba(38,166,154,1),0 0 28px rgba(38,166,154,.8)}@keyframes rain-fall{0%{transform:translateY(-5%)}to{transform:translateY(105vh)}}.wave-bar{position:absolute;left:0;right:0;height:6px;background:linear-gradient(90deg,transparent 0%,rgba(38,166,154,.15) 20%,rgba(38,166,154,.5) 45%,rgba(38,166,154,.7) 50%,rgba(38,166,154,.5) 55%,rgba(38,166,154,.15) 80%,transparent 100%);box-shadow:0 0 20px #26a69a66,0 0 40px #26a69a26;animation-name:wave-scan;animation-timing-function:ease-in-out;animation-iteration-count:infinite;animation-direction:alternate;top:-10px}@keyframes wave-scan{0%{top:-2%;opacity:0}5%{opacity:.8}10%{opacity:1}90%{opacity:1}95%{opacity:.5}to{top:102%;opacity:0}}.parts-fade-enter-active{transition:opacity .5s ease-out}.parts-fade-leave-active{transition:opacity .2s ease-in}.parts-fade-enter-from,.parts-fade-leave-to{opacity:0}.body-part-group{transition:opacity .2s;outline:none}.body-part-group:focus-visible{outline:none}.body-part-group:active{opacity:.7}.part-label--active{font-weight:700;filter:drop-shadow(0 0 9px rgba(38,166,154,.95)) drop-shadow(0 0 3px rgba(255,255,255,.7))}.part-label__check{fill:#0d9488;font-weight:700}

</style>
