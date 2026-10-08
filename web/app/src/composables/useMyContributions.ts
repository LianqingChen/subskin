import { onScopeDispose, ref, watch } from 'vue'
import { getContributionEvents, getMyContributions, syncContributionCredits } from '@/api/contribution-overview'
import { useAuthStore } from '@/stores/auth'
import type { ContributionEvent, MyContributions } from '@/types/contribution'

export function useMyContributions() {
  const auth = useAuthStore()
  const summary = ref<MyContributions | null>(null)
  const events = ref<ContributionEvent[]>([])
  const totalEvents = ref(0)
  const loading = ref(false)
  const error = ref(false)
  const syncError = ref(false)
  const eventsError = ref(false)
  const loadingEvents = ref(false)
  let request = 0
  async function load() {
    const version = ++request
    summary.value = null
    events.value = []
    totalEvents.value = 0
    error.value = false
    eventsError.value = false
    syncError.value = false
    loadingEvents.value = false
    if (!auth.isLoggedIn) { loading.value = false; return }
    loading.value = true
    try { await syncContributionCredits() }
    catch { if (version === request) syncError.value = true }
    if (version !== request) return
    const results = await Promise.allSettled([getMyContributions(), getContributionEvents()])
    if (version !== request) return
    const [mine, history] = results
    error.value = mine.status === 'rejected'
    summary.value = mine.status === 'fulfilled' ? mine.value : null
    eventsError.value = history.status === 'rejected'
    if (history.status === 'fulfilled') {
      events.value = history.value.items
      totalEvents.value = history.value.total
    }
    loading.value = false
  }
  async function moreEvents() {
    if (!auth.isLoggedIn || loadingEvents.value) return
    const version = request
    loadingEvents.value = true
    eventsError.value = false
    try {
      const response = await getContributionEvents(events.value.length)
      if (version !== request) return
      const ids = new Set(events.value.map(x => x.id))
      events.value.push(...response.items.filter(x => !ids.has(x.id)))
      totalEvents.value = response.total
    } catch { if (version === request) eventsError.value = true }
    finally { if (version === request) loadingEvents.value = false }
  }
  watch(() => [auth.isLoggedIn, auth.user?.id], load, { immediate: true })
  onScopeDispose(() => { request++ })
  return { summary, events, totalEvents, loading, error, syncError, eventsError, loadingEvents, load, moreEvents }
}
