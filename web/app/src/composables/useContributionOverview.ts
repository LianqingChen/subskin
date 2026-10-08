import { onMounted, onScopeDispose, ref } from 'vue'
import { getContributionDistribution, getContributionOverview } from '@/api/contribution-overview'
import type { ContributionDistribution, ContributionOverview } from '@/types/contribution'

export function useContributionOverview() {
  const overview = ref<ContributionOverview | null>(null)
  const distribution = ref<ContributionDistribution | null>(null)
  const loading = ref(false)
  const overviewError = ref(false)
  const distributionError = ref(false)
  let request = 0
  async function load() {
    const version = ++request
    loading.value = true
    const results = await Promise.allSettled([getContributionOverview(), getContributionDistribution()])
    if (version !== request) return
    const [summary, matrix] = results
    overviewError.value = summary.status === 'rejected'
    distributionError.value = matrix.status === 'rejected'
    overview.value = summary.status === 'fulfilled' ? summary.value : null
    distribution.value = matrix.status === 'fulfilled' ? matrix.value : null
    loading.value = false
  }
  onMounted(load)
  onScopeDispose(() => { request++ })
  return { overview, distribution, loading, overviewError, distributionError, load }
}
