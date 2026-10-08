import { onBeforeUnmount, ref } from 'vue'
import { getComparisonCapabilities } from '@/api/skin_report'
export function useManualComparisonSupport() {
  const supported = ref(false), loading = ref(false), checked = ref(false)
  let generation = 0
  async function load() {
    const current = ++generation
    loading.value = true
    try {
      const data = await getComparisonCapabilities()
      if (current === generation) supported.value = data.manual_alignment === true && data.version === 'manual-similarity-v1'
    } catch { if (current === generation) supported.value = false }
    finally { if (current === generation) { loading.value = false; checked.value = true } }
  }
  onBeforeUnmount(() => { generation++ })
  return { supported, loading, checked, load }
}
