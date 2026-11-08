import { computed, onMounted, onScopeDispose, ref, type Ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

/**
 * 知识中枢数据加载：404/501（后端未部署或无内容）按"空"处理，其余失败显示错误并可重试。
 * fetcher 收到 preview 标记（仅管理员为 true）。
 */
export function useKnowledgeResource<T>(fetcher: (preview: boolean) => Promise<T>, autoload = true) {
  const auth = useAuthStore()
  const preview = computed(() => !!auth.user?.is_admin)
  const data: Ref<T | null> = ref(null)
  const loading = ref(false)
  const error = ref(false)
  const missing = ref(false)
  let request = 0
  async function load() {
    const version = ++request
    loading.value = true
    error.value = false
    missing.value = false
    try {
      const result = await fetcher(preview.value)
      if (version !== request) return
      data.value = result
    } catch (e) {
      if (version !== request) return
      data.value = null
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 404 || status === 501) missing.value = true
      else error.value = true
    } finally {
      if (version === request) loading.value = false
    }
  }
  if (autoload) onMounted(load)
  onScopeDispose(() => { request++ })
  return { data, loading, error, missing, load, preview }
}
