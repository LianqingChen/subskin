<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useMainNav } from '@/composables/useMainNav'
import { useContributionOverview } from '@/composables/useContributionOverview'
import HubTabNav, { type HubTab } from '@/components/contribution/hub/HubTabNav.vue'
import MilestoneStrip from '@/components/contribution/hub/MilestoneStrip.vue'

const KnowledgeTab = defineAsyncComponent(() => import('@/components/contribution/hub/KnowledgeTab.vue'))
const FrontierTab = defineAsyncComponent(() => import('@/components/contribution/hub/FrontierTab.vue'))
const BuildTab = defineAsyncComponent(() => import('@/components/contribution/hub/BuildTab.vue'))
const ResearchTab = defineAsyncComponent(() => import('@/components/contribution/hub/ResearchTab.vue'))

const TABS: HubTab[] = ['knowledge', 'frontier', 'build', 'research']
const STORE_KEY = 'subskin.peer.tab'
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { navItems } = useMainNav()
const title = computed(() => navItems.value.find(x => x.path === '/contribution')?.label ?? '同行')
const ov = useContributionOverview()

const isTab = (v: unknown): v is HubTab => typeof v === 'string' && (TABS as string[]).includes(v)
function stored(): HubTab | null {
  try { const v = localStorage.getItem(STORE_KEY); return isTab(v) ? v : null } catch { return null }
}
function initialTab(): HubTab {
  const q = route.query.tab
  if (isTab(q)) return q
  return auth.isLoggedIn ? stored() ?? 'build' : 'knowledge'
}
const tab = ref<HubTab>(initialTab())

function select(next: HubTab) {
  tab.value = next
  if (auth.isLoggedIn) { try { localStorage.setItem(STORE_KEY, next) } catch { /* 隐私模式忽略 */ } }
  if (route.query.tab !== next) void router.replace({ query: { ...route.query, tab: next } })
}
// 浏览器前进/后退或外部深链改变 ?tab= 时同步
watch(() => route.query.tab, (q) => { if (isTab(q) && q !== tab.value) tab.value = q })

let schema: HTMLScriptElement | undefined
onMounted(() => {
  schema = document.createElement('script')
  schema.type = 'application/ld+json'
  schema.textContent = JSON.stringify({ '@context': 'https://schema.org', '@type': 'CollectionPage', name: `${title.value} · 一起看懂白癜风`, description: '带证据等级和来源的白癜风知识卡片、研发进展，以及病友共同积累的有效图片、采纳月份与部位分布。', url: `${location.origin}/contribution` })
  document.head.appendChild(schema)
})
onBeforeUnmount(() => schema?.remove())
</script>

<template>
  <div class="page space-y-4 pb-6 pt-4 text-gray-900 dark:text-gray-100 md:space-y-5 md:pt-6">
    <header>
      <h1 class="text-xl font-semibold max-md:sr-only">{{ title }}<span class="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">一起看懂白癜风</span></h1>
    </header>

    <MilestoneStrip :overview="ov.overview.value" :loading="ov.loading.value" :error="ov.overviewError.value" />

    <div class="md:flex md:items-start md:gap-6">
      <HubTabNav :model-value="tab" :logged-in="auth.isLoggedIn" @update:model-value="select" />
      <div id="hub-panel" role="tabpanel" class="mt-4 min-w-0 flex-1 md:mt-0">
        <KeepAlive>
          <KnowledgeTab v-if="tab === 'knowledge'" />
          <FrontierTab v-else-if="tab === 'frontier'" />
          <BuildTab v-else-if="tab === 'build'" :overview="ov.overview.value" :distribution="ov.distribution.value" :timeline="ov.timeline.value" :loading="ov.loading.value" :overview-error="ov.overviewError.value" :distribution-error="ov.distributionError.value" :timeline-error="ov.timelineError.value" @reload="ov.load" />
          <ResearchTab v-else />
        </KeepAlive>
      </div>
    </div>
  </div>
</template>
