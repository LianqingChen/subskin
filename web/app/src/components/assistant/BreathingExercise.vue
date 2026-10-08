<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { communityApi } from '@/api/community'
import { useToast } from '@/composables/useToast'
import { useBreathingSound, soundLabels, type SoundType } from '@/composables/useBreathingSound'
import sageImg from '/butler/meditation_sage.webp'

const emit = defineEmits<{ close: [] }>()
const toast = useToast()
const sound = useBreathingSound()

// 盒式呼吸变体：吸气 4s → 屏息 4s → 呼气 6s → 屏息 4s
const phases = [
  { label: '吸气', duration: 4, hint: '用鼻子慢慢吸气', ringStart: 0.82, ringEnd: 1.18, figStart: 0.97, figEnd: 1.05 },
  { label: '屏息', duration: 4, hint: '轻柔屏住呼吸', ringStart: 1.18, ringEnd: 1.18, figStart: 1.05, figEnd: 1.05 },
  { label: '呼气', duration: 6, hint: '用嘴巴缓缓呼气', ringStart: 1.18, ringEnd: 0.82, figStart: 1.05, figEnd: 0.97 },
  { label: '屏息', duration: 4, hint: '放松，保持平静', ringStart: 0.82, ringEnd: 0.82, figStart: 0.97, figEnd: 0.97 },
]

const encouragements = [
  '每一次呼吸，都是一次与自己的温柔相处。',
  '你刚刚为自己的心灵留出了一段宁静时光。这份自我关怀，会让你的内心更加强大。',
  '正念不在于时间长短，而在于你是否真正地与自己同在。',
  '停下来，深呼吸，你已经做得很好了。',
  '呼吸是你随身携带的平静之源，随时随地都可以回到这份安宁中。',
  '给自己一个暂停，是为了更好地前行。',
  '这一刻的宁静，是你给自己最好的礼物。',
  '在呼吸之间，找到属于自己的节奏。',
]

type State = 'active' | 'completed'
const state = ref<State>('active')
const phaseIndex = ref(0)
const cycleCount = ref(1)
const secondsLeft = ref(phases[0].duration)
const ringScale = ref(phases[0].ringStart)
const figScale = ref(phases[0].figStart)
const isActive = ref(true)
const totalSeconds = ref(0)
const sharing = ref(false)

let phaseStartTime = 0
let rafId = 0
let startTime = 0

const phase = computed(() => phases[phaseIndex.value])
const encouragement = computed(() => encouragements[Math.floor(Math.random() * encouragements.length)])

const elapsed = computed(() => {
  const m = Math.floor(totalSeconds.value / 60)
  const s = totalSeconds.value % 60
  return m > 0 ? `${m} 分 ${s} 秒` : `${s} 秒`
})

const ringStyle = computed(() => ({
  transform: `scale(${ringScale.value})`,
}))
const figureStyle = computed(() => ({
  transform: `scale(${figScale.value})`,
}))

function animate() {
  const elapsedSec = (performance.now() - phaseStartTime) / 1000
  const p = phases[phaseIndex.value]
  const progress = Math.min(elapsedSec / p.duration, 1)

  ringScale.value = p.ringStart + (p.ringEnd - p.ringStart) * progress
  figScale.value = p.figStart + (p.figEnd - p.figStart) * progress
  secondsLeft.value = Math.ceil(p.duration - elapsedSec)
  totalSeconds.value = Math.floor((performance.now() - startTime) / 1000)

  if (progress >= 1) {
    phaseStartTime = performance.now()
    phaseIndex.value = (phaseIndex.value + 1) % phases.length
    if (phaseIndex.value === 0) cycleCount.value++
    sound.cuePhase(phaseIndex.value)
  }

  if (isActive.value) rafId = requestAnimationFrame(animate)
}

function finish() {
  isActive.value = false
  if (rafId) cancelAnimationFrame(rafId)
  totalSeconds.value = Math.floor((performance.now() - startTime) / 1000)
  state.value = 'completed'
}

async function share() {
  if (sharing.value) return
  sharing.value = true
  try {
    const content = `<p>完成了 ${cycleCount.value} 轮正念呼吸练习，用时 ${elapsed.value}。</p><blockquote><p>${encouragement.value}</p></blockquote>`
    await communityApi.createPost({
      title: '正念呼吸练习记录',
      content,
      category_id: 3,
      post_type: 'long',
      mood: '坚持中',
    })
    toast.success('已分享到社区')
    emit('close')
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || '分享失败，请重试')
  } finally {
    sharing.value = false
  }
}

onMounted(() => {
  startTime = performance.now()
  phaseStartTime = performance.now()
  rafId = requestAnimationFrame(animate)
})

onUnmounted(() => {
  isActive.value = false
  if (rafId) cancelAnimationFrame(rafId)
  sound.cleanup()
})
</script>

<template>
  <div class="bg-gradient-to-b from-teal-50/90 to-primary-50 rounded-2xl p-5 mt-3 border border-primary-100 space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <span class="text-sm font-medium text-primary-700">正念呼吸</span>
      <div class="flex items-center gap-1">
        <!-- Sound selector -->
        <div class="relative">
          <button
            class="flex items-center gap-1 px-2 py-1 text-xs rounded-lg transition-colors"
            :class="sound.current.value === 'none' ? 'text-primary-400 bg-primary-50 hover:bg-primary-100' : 'text-primary-600 bg-primary-100 hover:bg-primary-200'"
            @click="sound.showDropdown.value = !sound.showDropdown.value"
          >
            <i :class="sound.current.value === 'none' ? 'ri-volume-mute-line' : 'ri-volume-up-line'" class="text-sm"></i>
            <span>{{ soundLabels[sound.current.value as SoundType] }}</span>
            <i class="ri-arrow-down-s-line text-xs"></i>
          </button>
          <div v-if="sound.showDropdown.value" class="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10 min-w-[100px]">
            <button
              v-for="(label, type) in soundLabels" :key="type"
              class="w-full text-left px-3 py-1.5 text-xs text-gray-600 hover:bg-primary-50 hover:text-primary-600 transition-colors flex items-center gap-1.5"
              :class="{ 'bg-primary-50 text-primary-600 font-medium': sound.current.value === type }"
              @click="sound.setSound(type as SoundType)"
            >
              <i v-if="sound.current.value === type" class="ri-check-line text-sm"></i>
              <span v-else class="w-3.5" />
              {{ label }}
            </button>
          </div>
        </div>
        <button
          class="w-7 h-7 rounded-full flex items-center justify-center text-primary-400 hover:bg-primary-100 hover:text-primary-600 transition-colors"
          aria-label="关闭"
          @click="emit('close')"
        >
          <i class="ri-close-line text-lg"></i>
        </button>
      </div>
    </div>

    <!-- Active state: breathing ring + meditating figure -->
    <template v-if="state === 'active'">
      <div class="flex flex-col items-center py-1">
        <div class="relative w-52 h-52 flex items-center justify-center">
          <!-- Breathing ring (aura) -->
          <div class="absolute inset-2 rounded-full border-2 border-primary-300/70" :style="ringStyle">
            <div class="absolute inset-0 rounded-full bg-primary-400/10 blur-xl"></div>
          </div>
          <!-- Meditating sage figure (circular crop) -->
          <div class="relative w-44 h-44 rounded-full overflow-hidden shadow-lg ring-2 ring-primary-200" :style="figureStyle">
            <img :src="sageImg" alt="打坐冥想" class="w-full h-full object-cover" draggable="false" />
          </div>
        </div>
        <div class="mt-1 text-center">
          <div class="text-sm font-semibold text-primary-700">{{ phase.label }}</div>
          <div class="text-3xl font-bold text-primary-600 tabular-nums">{{ secondsLeft }}</div>
        </div>
      </div>
      <p class="text-center text-xs text-primary-600">{{ phase.hint }}</p>
      <div class="text-center text-xs text-primary-400">第 {{ cycleCount }} 轮 · 吸气4秒-屏息4秒-呼气6秒-屏息4秒</div>
      <button
        class="w-full py-2.5 bg-white/80 text-primary-600 text-sm rounded-xl border border-primary-200 hover:bg-primary-50 transition-colors active:scale-[0.98]"
        @click="finish"
      >结束练习</button>
    </template>

    <!-- Completed state: summary + share -->
    <template v-else>
      <div class="text-center py-2 space-y-3">
        <div class="text-3xl text-primary-500"><i class="ri-heart-3-line"></i></div>
        <p class="text-sm font-medium text-primary-700">练习完成</p>
        <div class="text-xs text-primary-600 space-y-0.5">
          <p>完成了 <span class="font-semibold text-primary-600">{{ cycleCount }}</span> 轮正念呼吸</p>
          <p>用时 <span class="font-semibold text-primary-600">{{ elapsed }}</span></p>
        </div>
        <p class="text-xs text-primary-400 italic leading-relaxed max-w-xs mx-auto">"{{ encouragement }}"</p>
      </div>
      <button
        class="w-full py-2.5 bg-primary-500 text-white text-sm rounded-xl hover:bg-primary-600 transition-colors active:scale-[0.98] disabled:opacity-50"
        :disabled="sharing"
        @click="share"
      >{{ sharing ? '分享中...' : '分享到社区' }}</button>
      <button
        class="w-full py-2 bg-white/60 text-primary-500 text-xs rounded-xl hover:bg-white transition-colors"
        @click="emit('close')"
      >关闭</button>
    </template>
  </div>
</template>
