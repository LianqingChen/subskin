import { onMounted, ref } from 'vue'
import { getSiteStorage, triggerSiteEmbedding } from '@/api/siteMaintenance'
import type { EmbedResult, SiteStorage } from '@/api/siteMaintenance'

export function useSiteMaintenance() {
  const storage = ref<SiteStorage | null>(null)
  const loading = ref(false)
  const embedding = ref(false)
  const result = ref<EmbedResult | null>(null)
  const error = ref('')
  async function refresh() {
    if (loading.value) return
    loading.value = true
    try { storage.value = await getSiteStorage(); error.value = '' }
    catch { error.value = '网站存储状态暂不可用，请稍后重试' }
    finally { loading.value = false }
  }
  async function embed() {
    if (embedding.value) return
    embedding.value = true; result.value = null; error.value = ''
    try { result.value = await triggerSiteEmbedding() }
    catch { error.value = '向量化任务未能完成，请稍后重试' }
    finally { embedding.value = false }
  }
  onMounted(refresh)
  return { storage, loading, embedding, result, error, refresh, embed }
}
