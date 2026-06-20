<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import butterflyMascot from '/butterfly_mascot.png'

interface BodyPart {
  id: string
  label: string
  bodySite: string
  hits: { cx: number; cy: number; rx: number; ry: number }[]
  anchors: { x: number; y: number }[]
  labelX: number
  labelY: number
}

const props = withDefaults(defineProps<{
  mode?: 'rain' | 'wave'
  showParts?: boolean
  activePart?: string | null
  view?: 'front' | 'back'
  showViewToggle?: boolean
}>(), {
  mode: 'rain',
  showParts: true,
  activePart: null,
  view: 'front',
  showViewToggle: true,
})

const emit = defineEmits<{
  'select-part': [bodySite: string]
  'update:view': [view: 'front' | 'back']
}>()

const currentView = ref<'front' | 'back'>(props.view)
function toggleView() {
  currentView.value = currentView.value === 'front' ? 'back' : 'front'
  emit('update:view', currentView.value)
}

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

const frontParts: BodyPart[] = [
  {"id": "face", "label": "面部", "bodySite": "face", "hits": [{"cx": 760, "cy": 132, "rx": 60, "ry": 60}], "anchors": [{"x": 720, "y": 132}], "labelX": 120, "labelY": 120},
  {"id": "right_hand", "label": "右手", "bodySite": "right_hand", "hits": [{"cx": 365, "cy": 140, "rx": 52, "ry": 50}], "anchors": [{"x": 395, "y": 140}], "labelX": 120, "labelY": 255},
  {"id": "neck", "label": "脖子", "bodySite": "neck", "hits": [{"cx": 700, "cy": 218, "rx": 30, "ry": 22}], "anchors": [{"x": 672, "y": 218}], "labelX": 120, "labelY": 400},
  {"id": "right_arm", "label": "右臂", "bodySite": "right_arm", "hits": [{"cx": 440, "cy": 320, "rx": 55, "ry": 90}], "anchors": [{"x": 425, "y": 300}], "labelX": 120, "labelY": 560},
  {"id": "right_leg", "label": "右腿", "bodySite": "right_leg", "hits": [{"cx": 608, "cy": 806, "rx": 58, "ry": 140}], "anchors": [{"x": 552, "y": 806}], "labelX": 120, "labelY": 780},
  {"id": "right_foot", "label": "右脚", "bodySite": "right_foot", "hits": [{"cx": 606, "cy": 1242, "rx": 64, "ry": 36}], "anchors": [{"x": 544, "y": 1242}], "labelX": 120, "labelY": 1235},
  {"id": "left_hand", "label": "左手", "bodySite": "left_hand", "hits": [{"cx": 816, "cy": 192, "rx": 52, "ry": 48}], "anchors": [{"x": 866, "y": 192}], "labelX": 1280, "labelY": 175},
  {"id": "left_arm", "label": "左臂", "bodySite": "left_arm", "hits": [{"cx": 842, "cy": 282, "rx": 44, "ry": 112}], "anchors": [{"x": 884, "y": 282}], "labelX": 1280, "labelY": 295},
  {"id": "abdomen", "label": "腹部", "bodySite": "abdomen", "hits": [{"cx": 700, "cy": 500, "rx": 95, "ry": 75}], "anchors": [{"x": 804, "y": 500}], "labelX": 1280, "labelY": 425},
  {"id": "chest", "label": "胸部", "bodySite": "chest", "hits": [{"cx": 700, "cy": 380, "rx": 90, "ry": 50}], "anchors": [{"x": 802, "y": 380}], "labelX": 1280, "labelY": 555},
  {"id": "left_leg", "label": "左腿", "bodySite": "left_leg", "hits": [{"cx": 792, "cy": 806, "rx": 58, "ry": 140}], "anchors": [{"x": 848, "y": 806}], "labelX": 1280, "labelY": 800},
  {"id": "left_foot", "label": "左脚", "bodySite": "left_foot", "hits": [{"cx": 794, "cy": 1242, "rx": 64, "ry": 36}], "anchors": [{"x": 856, "y": 1242}], "labelX": 1280, "labelY": 1235}
]

const backParts: BodyPart[] = [
  {"id": "face", "label": "后脑", "bodySite": "face", "hits": [{"cx": 700, "cy": 132, "rx": 60, "ry": 60}], "anchors": [{"x": 660, "y": 132}], "labelX": 120, "labelY": 120},
  {"id": "left_hand", "label": "左手", "bodySite": "left_hand", "hits": [{"cx": 365, "cy": 140, "rx": 52, "ry": 50}], "anchors": [{"x": 395, "y": 140}], "labelX": 120, "labelY": 255},
  {"id": "neck", "label": "颈后", "bodySite": "neck", "hits": [{"cx": 700, "cy": 218, "rx": 30, "ry": 22}], "anchors": [{"x": 672, "y": 218}], "labelX": 120, "labelY": 400},
  {"id": "left_arm", "label": "左臂", "bodySite": "left_arm", "hits": [{"cx": 440, "cy": 320, "rx": 55, "ry": 90}], "anchors": [{"x": 425, "y": 300}], "labelX": 120, "labelY": 560},
  {"id": "left_leg", "label": "左腿", "bodySite": "left_leg", "hits": [{"cx": 608, "cy": 806, "rx": 58, "ry": 140}], "anchors": [{"x": 552, "y": 806}], "labelX": 120, "labelY": 780},
  {"id": "left_foot", "label": "左脚", "bodySite": "left_foot", "hits": [{"cx": 606, "cy": 1242, "rx": 64, "ry": 36}], "anchors": [{"x": 544, "y": 1242}], "labelX": 120, "labelY": 1235},
  {"id": "right_hand", "label": "右手", "bodySite": "right_hand", "hits": [{"cx": 816, "cy": 192, "rx": 52, "ry": 48}], "anchors": [{"x": 866, "y": 192}], "labelX": 1280, "labelY": 175},
  {"id": "right_arm", "label": "右臂", "bodySite": "right_arm", "hits": [{"cx": 842, "cy": 282, "rx": 44, "ry": 112}], "anchors": [{"x": 884, "y": 282}], "labelX": 1280, "labelY": 295},
  {"id": "upper_back", "label": "上背部", "bodySite": "upper_back", "hits": [{"cx": 700, "cy": 410, "rx": 95, "ry": 60}], "anchors": [{"x": 804, "y": 410}], "labelX": 1280, "labelY": 425},
  {"id": "lower_back", "label": "下背部", "bodySite": "lower_back", "hits": [{"cx": 700, "cy": 580, "rx": 90, "ry": 60}], "anchors": [{"x": 802, "y": 580}], "labelX": 1280, "labelY": 555},
  {"id": "right_leg", "label": "右腿", "bodySite": "right_leg", "hits": [{"cx": 792, "cy": 806, "rx": 58, "ry": 140}], "anchors": [{"x": 848, "y": 806}], "labelX": 1280, "labelY": 800},
  {"id": "right_foot", "label": "右脚", "bodySite": "right_foot", "hits": [{"cx": 794, "cy": 1242, "rx": 64, "ry": 36}], "anchors": [{"x": 856, "y": 1242}], "labelX": 1280, "labelY": 1235}
]

const visibleParts = computed(() => currentView.value === 'back' ? backParts : frontParts)

function onPartClick(part: BodyPart) {
  emit('select-part', part.bodySite)
}

let onTouchStart: (() => void) | null = null
let onTouchEnd: (() => void) | null = null

onMounted(() => {
  const el = imageAreaRef.value
  if (!el) return
  onTouchStart = () => nextTick()
  onTouchEnd = () => nextTick()
  el.addEventListener('touchstart', onTouchStart, { passive: true })
  el.addEventListener('touchend', onTouchEnd, { passive: true })
  el.addEventListener('touchcancel', onTouchEnd, { passive: true })
  showPartsInternal.value = props.showParts
})

defineExpose({ triggerRain })

onUnmounted(() => {
  if (rainTimer) clearTimeout(rainTimer)
  if (curtainTimer) clearTimeout(curtainTimer)
  if (cycleTimer) clearTimeout(cycleTimer)
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
  <div class="relative w-full h-full min-h-[280px]" style="aspect-ratio: 1400 / 1500;">
    <div
      ref="imageAreaRef"
      class="relative w-full h-full"
      :style="{ touchAction: 'none' }"
      data-swipe-ignore
    >
      <div class="w-full h-full">
        <img
          :src="butterflyMascot"
          alt="小金 - 身体部位参考图"
          :class="['w-full h-full object-contain select-none relative z-10', { 'scale-x-[-1]': currentView === 'back' }]"
          draggable="false"
        />
      </div>

      <button
        v-if="showViewToggle && showParts"
        type="button"
        class="absolute top-2 right-2 z-30 inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-white/70 dark:bg-gray-800/70 backdrop-blur text-xs font-medium text-primary-700 dark:text-primary-300 hover:bg-white dark:hover:bg-gray-800 transition-colors shadow-sm"
        @click="toggleView"
      >
        <i class="ri-flip-horizontal-line"></i>
        {{ currentView === 'front' ? '正面' : '背面' }}
      </button>

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
            viewBox="0 0 1400 1500"
            class="w-full h-full"
            :style="{ pointerEvents: 'auto', overflow: 'visible' }"
            preserveAspectRatio="xMidYMid meet"
          >
            <defs>
              <filter id="dash-glow">
                <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <g
              v-for="part in visibleParts"
              :key="part.id"
              class="body-part-group"
              :class="{ 'body-part-active': activePart === part.bodySite }"
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
                :rx="hit.rx + 10"
                :ry="hit.ry + 10"
                fill="transparent"
                stroke="transparent"
                class="cursor-pointer"
                @click.stop="onPartClick(part)"
              />
              <g v-for="(anc, ai) in part.anchors" :key="'line-' + ai">
                <line
                  :x1="anc.x"
                  :y1="anc.y"
                  :x2="part.labelX < 700 ? anc.x - 25 : anc.x + 25"
                  :y2="anc.y"
                  :stroke="activePart === part.bodySite ? '#ffffff' : '#26A69A'"
                  stroke-width="2"
                  stroke-dasharray="6 4"
                  stroke-linecap="round"
                  filter="url(#dash-glow)"
                  :opacity="activePart === part.bodySite ? 1 : 0.7"
                />
                <line
                  :x1="part.labelX < 700 ? anc.x - 25 : anc.x + 25"
                  :y1="anc.y"
                  :x2="part.labelX < 700 ? part.labelX + 30 : part.labelX - 30"
                  :y2="part.labelY"
                  :stroke="activePart === part.bodySite ? '#ffffff' : '#26A69A'"
                  stroke-width="2"
                  stroke-dasharray="6 4"
                  stroke-linecap="round"
                  filter="url(#dash-glow)"
                  :opacity="activePart === part.bodySite ? 1 : 0.7"
                />
                <circle
                  :cx="anc.x"
                  :cy="anc.y"
                  :r="activePart === part.bodySite ? 8 : 6"
                  :fill="activePart === part.bodySite ? '#ffffff' : '#26A69A'"
                  opacity="0.9"
                  filter="url(#dash-glow)"
                />
              </g>
              <text
                :x="part.labelX"
                :y="part.labelY"
                :text-anchor="part.labelX < 700 ? 'end' : 'start'"
                :fill="activePart === part.bodySite ? '#ffffff' : '#26A69A'"
                font-size="52"
                font-family="system-ui, -apple-system, sans-serif"
                font-weight="600"
                class="select-none part-label cursor-pointer"
                :style="activePart === part.bodySite ? 'text-shadow: 0 0 12px rgba(38,166,154,0.8), 0 0 24px rgba(38,166,154,0.4);' : 'text-shadow: 0 0 6px rgba(38,166,154,0.35);'"
                @click.stop="onPartClick(part)"
              >{{ part.label }}</text>
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
.curtain-sweep-enter-active{animation:curtain-slide .5s ease-out forwards}.curtain-sweep-leave-active{transition:opacity .15s ease-in}.curtain-sweep-leave-to{opacity:0}@keyframes curtain-slide{0%{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}.rain-fade-enter-active{transition:opacity .3s ease-out}.rain-fade-leave-active{transition:opacity .4s ease-in}.rain-fade-enter-from,.rain-fade-leave-to{opacity:0}.rain-column{position:absolute;top:-5%;font-family:Courier New,monospace;font-weight:700;color:#26a69a;text-shadow:0 0 6px rgba(38,166,154,.6);white-space:pre;line-height:1.3;animation-name:rain-fall;animation-timing-function:linear;animation-fill-mode:forwards}.rain-column:first-line{color:#fff;text-shadow:0 0 14px rgba(38,166,154,1),0 0 28px rgba(38,166,154,.8)}@keyframes rain-fall{0%{transform:translateY(-5%)}to{transform:translateY(105vh)}}.wave-bar{position:absolute;left:0;right:0;height:6px;background:linear-gradient(90deg,transparent 0%,rgba(38,166,154,.15) 20%,rgba(38,166,154,.5) 45%,rgba(38,166,154,.7) 50%,rgba(38,166,154,.5) 55%,rgba(38,166,154,.15) 80%,transparent 100%);box-shadow:0 0 20px #26a69a66,0 0 40px #26a69a26;animation-name:wave-scan;animation-timing-function:ease-in-out;animation-iteration-count:infinite;animation-direction:alternate;top:-10px}@keyframes wave-scan{0%{top:-2%;opacity:0}5%{opacity:.8}10%{opacity:1}90%{opacity:1}95%{opacity:.5}to{top:102%;opacity:0}}.parts-fade-enter-active{transition:opacity .5s ease-out}.parts-fade-leave-active{transition:opacity .2s ease-in}.parts-fade-enter-from,.parts-fade-leave-to{opacity:0}.body-part-group:hover text.part-label{fill:#fff;filter:drop-shadow(0 0 6px rgba(38,166,154,.6))}.body-part-active text.part-label{fill:#fff!important;filter:drop-shadow(0 0 10px rgba(38,166,154,.7))}.body-part-group:hover circle{fill:#fff;r:7}.body-part-active circle{fill:#fff!important}.body-part-group{transition:opacity .2s;outline:none}.body-part-group:focus-visible{outline:none}.body-part-group:focus-visible text.part-label{fill:#fff;filter:drop-shadow(0 0 8px rgba(38,166,154,.8))}.body-part-group:active{opacity:.7}.body-part-active{opacity:1!important}

</style>
