<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { communityApi } from '@/api/community'
import { useToast } from '@/composables/useToast'
import { useBreathingSound, soundLabels, type SoundType } from '@/composables/useBreathingSound'

const emit = defineEmits<{ close: [] }>()
const toast = useToast()
const sound = useBreathingSound()

const phases = [
  { label: '吸气', duration: 4, color: '#81c784', glow: 'rgba(129,199,132,0.35)', hint: '用鼻子慢慢吸气', startScale: 0.8, endScale: 1.2 },
  { label: '屏息', duration: 4, color: '#64b5f6', glow: 'rgba(100,181,246,0.35)', hint: '轻柔屏住呼吸', startScale: 1.2, endScale: 1.2 },
  { label: '呼气', duration: 6, color: '#ce93d8', glow: 'rgba(206,147,216,0.35)', hint: '用嘴巴缓缓呼气', startScale: 1.2, endScale: 0.8 },
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
const scale = ref(phases[0].startScale)
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

const circleStyle = computed(() => ({
  width: '140px',
  height: '140px',
  borderRadius: '50%',
  background: phase.value.color,
  boxShadow: `0 0 40px ${phase.value.glow}, 0 0 80px ${phase.value.glow}`,
  transform: `scale(${scale.value})`,
  transition: 'background 0.6s ease, box-shadow 0.6s ease',
}))

function animate() {
  const elapsedSec = (performance.now() - phaseStartTime) / 1000
  const p = phases[phaseIndex.value]
  const progress = Math.min(elapsedSec / p.duration, 1)

  scale.value = p.startScale + (p.endScale - p.startScale) * progress
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
      title: '🧘 正念呼吸练习记录',
      content,
      category_id: 3,
      post_type: 'long',
      mood: '💪坚持中',
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
  <div class="bg-gradient-to-b from-purple-50/90 to-indigo-50/90 rounded-2xl p-5 mt-3 border border-purple-100/60 space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <span class="text-sm font-medium text-purple-700">🧘 正念呼吸</span>
      <div class="flex items-center gap-1">
        <!-- Sound selector -->
        <div class="relative">
          <button
            class="flex items-center gap-1 px-2 py-1 text-xs rounded-lg transition-colors"
            :class="sound.current.value === 'none' ? 'text-purple-400 bg-purple-50 hover:bg-purple-100' : 'text-purple-600 bg-purple-100 hover:bg-purple-200'"
            @click="sound.showDropdown.value = !sound.showDropdown.value"
          >
            <span class="text-xs">{{ sound.current.value === 'none' ? '🔇' : '🔊' }}</span>
            <span>{{ soundLabels[sound.current.value as SoundType] }}</span>
            <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9" /></svg>
          </button>
          <div v-if="sound.showDropdown.value" class="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10 min-w-[100px]">
            <button
              v-for="(label, type) in soundLabels" :key="type"
              class="w-full text-left px-3 py-1.5 text-xs text-gray-600 hover:bg-purple-50 hover:text-purple-600 transition-colors flex items-center gap-1.5"
              :class="{ 'bg-purple-50 text-purple-600 font-medium': sound.current.value === type }"
              @click="sound.setSound(type as SoundType)"
            >
              <span v-if="sound.current.value === type">✓</span>
              <span v-else class="w-3.5" />
              {{ label }}
            </button>
          </div>
        </div>
        <button
          class="w-6 h-6 rounded-full flex items-center justify-center text-purple-400 hover:bg-purple-100 hover:text-purple-600 transition-colors"
          aria-label="关闭"
          @click="emit('close')"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Active state: breathing circle -->
    <template v-if="state === 'active'">
      <div class="flex justify-center py-2">
        <div class="flex items-center justify-center" :style="circleStyle">
          <div class="text-center select-none">
            <div class="text-xl font-semibold text-white drop-shadow-sm">{{ phase.label }}</div>
            <div class="text-3xl font-bold text-white drop-shadow-sm tabular-nums">{{ secondsLeft }}</div>
          </div>
        </div>
      </div>
      <p class="text-center text-xs text-purple-500">{{ phase.hint }}</p>
      <div class="text-center text-xs text-purple-400">第 {{ cycleCount }} 轮</div>
      <button
        class="w-full py-2.5 bg-white/80 text-purple-600 text-sm rounded-xl border border-purple-200 hover:bg-purple-50 transition-colors active:scale-[0.98]"
        @click="finish"
      >结束练习</button>
    </template>

    <!-- Completed state: summary + share -->
    <template v-else>
      <div class="text-center py-2 space-y-3">
        <div class="text-2xl">✨</div>
        <p class="text-sm font-medium text-purple-700">练习完成</p>
        <div class="text-xs text-purple-500 space-y-0.5">
          <p>完成了 <span class="font-semibold text-purple-600">{{ cycleCount }}</span> 轮正念呼吸</p>
          <p>用时 <span class="font-semibold text-purple-600">{{ elapsed }}</span></p>
        </div>
        <p class="text-xs text-purple-400 italic leading-relaxed max-w-xs mx-auto">"{{ encouragement }}"</p>
      </div>
      <button
        class="w-full py-2.5 bg-purple-500 text-white text-sm rounded-xl hover:bg-purple-600 transition-colors active:scale-[0.98] disabled:opacity-50"
        :disabled="sharing"
        @click="share"
      >{{ sharing ? '分享中...' : '分享到社区' }}</button>
      <button
        class="w-full py-2 bg-white/60 text-purple-500 text-xs rounded-xl hover:bg-white transition-colors"
        @click="emit('close')"
      >关闭</button>
    </template>
  </div>
</template>
