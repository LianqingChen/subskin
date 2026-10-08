import { onBeforeUnmount, ref } from 'vue'

export function useStoryPeelMotion() {
  const progress = ref(0), moving = ref(false)
  let frame = 0
  function stop() { cancelAnimationFrame(frame); moving.value = false }
  function set(value: number) { stop(); progress.value = Math.max(0, Math.min(1, value)) }
  function animate(target: number) {
    stop()
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { set(target); return }
    const from = progress.value, start = performance.now(), duration = Math.max(220, Math.abs(target - from) * 1200)
    moving.value = true
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      progress.value = from + (target - from) * (t * t * (3 - 2 * t))
      if (t < 1) frame = requestAnimationFrame(step)
      else moving.value = false
    }
    frame = requestAnimationFrame(step)
  }
  function toggle() { animate(progress.value >= .5 ? 0 : 1) }
  onBeforeUnmount(stop)
  return { progress, moving, set, animate, toggle }
}
