<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { vasiFeedbackApi, type FeedbackPrompt } from '@/api/vasi'

const props = defineProps<{
  assessmentId: number
}>()

const emit = defineEmits<{
  'dismiss': []
}>()

const prompt = ref<FeedbackPrompt | null>(null)
const loading = ref(true)
const submitted = ref(false)
const stayStart = ref(Date.now())

async function loadPrompt() {
  try {
    prompt.value = await vasiFeedbackApi.getPrompt(props.assessmentId)
  } catch {
    prompt.value = null
  } finally {
    loading.value = false
  }
}

async function handleOption(option: string) {
  if (!props.assessmentId) return
  try {
    await vasiFeedbackApi.submitActiveQuery(props.assessmentId, option)
    submitted.value = true
  } catch {
    // Silently fail — feedback is non-critical
  }
}

function dismiss() {
  recordStay()
  emit('dismiss')
}

function recordStay() {
  const duration = (Date.now() - stayStart.value) / 1000
  if (duration > 5 && props.assessmentId) {
    vasiFeedbackApi.recordStay(props.assessmentId, duration).catch(() => {})
  }
}

onMounted(() => {
  stayStart.value = Date.now()
  loadPrompt()
})

onUnmounted(() => {
  recordStay()
})
</script>

<template>
  <div
    v-if="!loading && prompt?.should_ask && !submitted"
    class="feedback-prompt animate-slide-up"
  >
    <div class="flex items-start gap-3">
      <div class="mt-0.5 shrink-0">
        <i class="ri-lightbulb-line text-amber-500 text-xl"></i>
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium text-gray-800">
          {{ prompt.title }}
        </p>
        <p class="text-xs text-gray-500  mt-0.5">
          {{ prompt.question }}
        </p>
        <div class="flex flex-wrap gap-2 mt-2.5">
          <button
            v-for="option in prompt.options"
            :key="option"
            class="px-3 py-1.5 text-xs font-medium rounded-full border transition-colors"
            :class="[
              'border-gray-200 dark:border-gray-700',
              'text-gray-600 ',
              'hover:bg-primary-50 hover:text-primary-600 hover:border-primary-200',
              'dark:hover:bg-primary-900/30 dark:hover:text-primary-300 dark:hover:border-primary-700',
            ]"
            @click="handleOption(option)"
          >
            {{ option }}
          </button>
          <button
            class="px-3 py-1.5 text-xs text-gray-400 hover:text-gray-500  dark:hover:text-gray-400"
            @click="dismiss"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  </div>

  <div
    v-else-if="submitted"
    class="feedback-prompt bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
  >
    <div class="flex items-center gap-2 text-sm text-green-700 dark:text-green-300">
      <i class="ri-check-line"></i>
      感谢你的反馈，这将帮助我们改进AI识别精度
    </div>
  </div>
</template>

<style scoped>
.feedback-prompt {
  @apply bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-3.5 mt-3;
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
