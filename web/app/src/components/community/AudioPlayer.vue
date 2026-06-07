<template>
  <div class="bg-gray-50 rounded-lg px-4 py-3 flex items-center gap-3 w-full">
    <button
      @click="togglePlay"
      class="w-10 h-10 rounded-full bg-primary-500 text-white flex items-center justify-center hover:bg-primary-600 transition-colors shrink-0 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
      :aria-label="isPlaying ? 'Pause' : 'Play'"
    >
      <svg v-if="!isPlaying" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5 ml-0.5">
        <path fill-rule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clip-rule="evenodd" />
      </svg>
      <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5">
        <path fill-rule="evenodd" d="M6.75 5.25a.75.75 0 01.75-.75H9a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H7.5a.75.75 0 01-.75-.75V5.25zm7.5 0A.75.75 0 0115 4.5h1.5a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H15a.75.75 0 01-.75-.75V5.25z" clip-rule="evenodd" />
      </svg>
    </button>

    <div
      class="flex-1 h-2 bg-gray-200 rounded-full cursor-pointer relative overflow-hidden"
      @click="seek"
      ref="progressBar"
    >
      <div
        class="absolute top-0 left-0 h-full bg-primary-500 transition-all duration-100 ease-linear"
        :style="{ width: `${progressPercentage}%` }"
      ></div>
    </div>

    <div class="text-xs text-gray-400 shrink-0 font-medium tabular-nums">
      {{ formatTime(currentTime) }} / {{ formatTime(displayDuration) }}
    </div>

    <audio
      ref="audioEl"
      :src="protectedSrc"
      @timeupdate="onTimeUpdate"
      @loadedmetadata="onLoadedMetadata"
      @ended="onEnded"
      preload="metadata"
      class="hidden"
    ></audio>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { toProtectedFileUrl } from '@/utils/file-url'

const props = defineProps({
  src: {
    type: String,
    required: true
  },
  duration: {
    type: Number,
    default: 0
  }
})

const audioEl = ref(null)
const progressBar = ref(null)

const isPlaying = ref(false)
const currentTime = ref(0)
const audioDuration = ref(props.duration)

const displayDuration = computed(() => {
  return audioDuration.value > 0 ? audioDuration.value : props.duration
})

const protectedSrc = computed(() => toProtectedFileUrl(props.src))

const progressPercentage = computed(() => {
  if (displayDuration.value === 0) return 0
  return (currentTime.value / displayDuration.value) * 100
})

const formatTime = (seconds) => {
  if (!seconds || isNaN(seconds)) return '0:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

const togglePlay = () => {
  if (!audioEl.value) return
  
  if (isPlaying.value) {
    audioEl.value.pause()
  } else {
    audioEl.value.play()
  }
  isPlaying.value = !isPlaying.value
}

const onTimeUpdate = () => {
  if (!audioEl.value) return
  currentTime.value = audioEl.value.currentTime
}

const onLoadedMetadata = () => {
  if (!audioEl.value) return
  if (audioEl.value.duration && audioEl.value.duration !== Infinity) {
    audioDuration.value = audioEl.value.duration
  }
}

const onEnded = () => {
  isPlaying.value = false
  currentTime.value = 0
  if (audioEl.value) {
    audioEl.value.currentTime = 0
  }
}

const seek = (event) => {
  if (!progressBar.value || !audioEl.value || displayDuration.value === 0) return
  
  const rect = progressBar.value.getBoundingClientRect()
  const clickX = event.clientX - rect.left
  const percentage = Math.max(0, Math.min(1, clickX / rect.width))
  
  const newTime = percentage * displayDuration.value
  audioEl.value.currentTime = newTime
  currentTime.value = newTime
}

onUnmounted(() => {
  if (audioEl.value) {
    audioEl.value.pause()
    audioEl.value.src = ''
  }
})
</script>
