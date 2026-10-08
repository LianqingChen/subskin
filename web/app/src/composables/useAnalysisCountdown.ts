import { computed, onBeforeUnmount, ref, watch } from 'vue'

// Reference window follows the current worker budget; it is not a completion promise.
export const ANALYSIS_REFERENCE_SECONDS = 90
export function useAnalysisCountdown(active: () => boolean) {
  const remaining = ref(ANALYSIS_REFERENCE_SECONDS)
  let startedAt = 0
  let timer: ReturnType<typeof setInterval> | null = null
  function stop() { if (timer !== null) clearInterval(timer); timer = null }
  function update() {
    remaining.value = Math.max(0, ANALYSIS_REFERENCE_SECONDS - Math.floor(Math.max(0, Date.now() - startedAt) / 1000))
    if (remaining.value === 0) stop()
  }
  watch(active, running => {
    stop()
    if (!running) return
    startedAt = Date.now(); remaining.value = ANALYSIS_REFERENCE_SECONDS
    timer = setInterval(update, 1000)
  }, { immediate: true })
  onBeforeUnmount(stop)
  return { remaining, overdue: computed(() => remaining.value === 0) }
}
