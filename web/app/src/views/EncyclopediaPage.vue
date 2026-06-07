<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const iframeRef = ref<HTMLIFrameElement | null>(null)
const loading = ref(true)
const retryCount = ref(0)
const maxRetries = 2

const sidebarCollapsed = ref(false)
const activeSection = ref('overview')

const sections = [
  { key: 'overview', label: '百科首页', icon: 'ri-book-2-line', path: '/encyclopedia' },
  { key: 'causes', label: '病因与机制', icon: 'ri-dna-line', path: '/encyclopedia/causes' },
  { key: 'types', label: '分型分类', icon: 'ri-file-list-3-line', path: '/encyclopedia/types' },
  { key: 'treatment', label: '治疗方法', icon: 'ri-capsule-line', path: '/encyclopedia/treatment' },
  { key: 'drugs', label: '药物研发', icon: 'ri-test-tube-line', path: '/encyclopedia/drugs' },
  { key: 'daily', label: '日常管理', icon: 'ri-heart-pulse-line', path: '/encyclopedia/daily' },
  { key: 'psychology', label: '心理支持', icon: 'ri-mental-health-line', path: '/encyclopedia/psychology' },
  { key: 'glossary', label: '术语词典', icon: 'ri-book-3-line', path: '/encyclopedia/glossary' },
]

const HOME_SRC = '/encyclopedia/encyclopedia/?embedded=1'

const currentSrc = computed(() => {
  const subpath = Array.isArray(route.params.path) ? route.params.path.join('/') : route.params.path || ''
  const path = subpath ? `/${subpath}` : '/encyclopedia/encyclopedia/'
  const bust = retryCount.value > 0 ? `&_v=${retryCount.value}` : ''
  return `${path}?embedded=1${bust}`
})

function onLoad() {
  const iframe = iframeRef.value
  if (!iframe) return

  try {
    const title = iframe.contentDocument?.title || iframe.contentWindow?.document?.title || ''
    if (title && !title.includes('百科全书') && title.includes('白癜风智能助手') && !title.includes('百科')) {
      retryCount.value++
      if (retryCount.value <= maxRetries) {
        loading.value = true
        iframe.src = currentSrc.value
        return
      }
    }
  } catch {
    // cross-origin: VitePress loaded correctly, can't read title (expected)
  }

  loading.value = false
}

function goHome() {
  activeSection.value = 'overview'
  loading.value = true
  if (iframeRef.value) {
    iframeRef.value.src = HOME_SRC
  }
  if (route.path !== '/encyclopedia') {
    router.push('/encyclopedia')
  }
}

function goBack() {
  if (iframeRef.value?.contentWindow) {
    try {
      iframeRef.value.contentWindow.history.back()
    } catch {
      window.history.back()
    }
  }
}

function goForward() {
  if (iframeRef.value?.contentWindow) {
    try {
      iframeRef.value.contentWindow.history.forward()
    } catch {
      window.history.forward()
    }
  }
}

defineExpose({ goBack, goForward })
</script>

<template>
  <div class="flex h-[calc(100dvh-3.5rem)]">
    <!-- Sidebar (desktop only) -->
    <aside v-if="!sidebarCollapsed" class="hidden md:flex w-52 flex-shrink-0 flex-col gap-1 border-r border-gray-100 dark:border-gray-800 pr-4 py-2 bg-white">
      <div class="p-3">
        <h2 class="text-sm font-semibold text-gray-900"><i class="ri-book-2-line mr-1"></i>白白百科</h2>
      </div>
      <nav class="flex-1 overflow-y-auto">
        <router-link
          v-for="section in sections.filter(s => s.key !== 'overview')"
          :key="section.key"
          :to="section.path"
          class="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors block no-underline"
          :class="activeSection === section.key
            ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
            : 'text-gray-600  hover:bg-gray-50'"
          @click="activeSection = section.key"
        >
          <i :class="section.icon" class="mr-1"></i>{{ section.label }}
        </router-link>
        <button
          class="w-full text-left px-3 py-2 rounded-lg text-sm transition-colors block"
          :class="activeSection === 'overview'
            ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
            : 'text-gray-600  hover:bg-gray-50'"
          @click="goHome"
        >
          <i class="ri-book-2-line mr-1"></i>百科首页
        </button>
      </nav>
      <!-- Collapse button -->
      <button
        class="flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        @click="sidebarCollapsed = true"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
        </svg>
        收起侧边栏
      </button>
    </aside>

    <!-- Toggle button when collapsed -->
    <div v-else class="hidden md:flex flex-col bg-white">
      <button
        @click="sidebarCollapsed = false"
        class="w-6 h-12 flex items-center justify-center bg-white border border-gray-200 dark:border-gray-700 rounded-r-lg shadow-sm text-gray-400 hover:text-primary-500 transition-colors mt-4 -mr-3 z-10"
        title="展开侧边栏"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>

    <!-- Main content: iframe wrapper -->
    <div class="flex-1 min-w-0 flex flex-col">
      <!-- Mobile navigation bar -->
      <div class="md:hidden flex items-center gap-2 px-3 py-2 border-b border-gray-100 dark:border-gray-800 bg-white">
        <button
          type="button"
          class="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/30 min-h-[44px]"
          @click="goHome"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9.293 2.293a1 1 0 011.414 0l7 7A1 1 0 0117 11h-1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-4a1 1 0 00-1-1H9a1 1 0 00-1 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-6H3a1 1 0 01-.707-1.707l7-7z" clip-rule="evenodd" />
          </svg>
          百科首页
        </button>
        <div class="flex-1"></div>
        <template v-if="true">
          <button
            type="button"
            class="flex items-center justify-center w-9 h-9 rounded-lg text-gray-500  hover:bg-gray-100 transition-colors"
            title="上一页"
            @click="goBack"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          </button>
          <button
            type="button"
            class="flex items-center justify-center w-9 h-9 rounded-lg text-gray-500  hover:bg-gray-100 transition-colors"
            title="下一页"
            @click="goForward"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
            </svg>
          </button>
        </template>
      </div>
      <!-- Encyclopedia iframe content -->
      <div class="encyclopedia-wrapper">
        <div v-if="loading" class="encyclopedia-loading">
          <div class="loading-spinner"></div>
          <span class="loading-text">加载百科...</span>
        </div>
        <iframe
          ref="iframeRef"
          :src="currentSrc"
          class="encyclopedia-iframe"
          :class="{ 'iframe-loaded': !loading }"
          frameborder="0"
          allow="clipboard-write"
          @load="onLoad"
          title="白白百科"
        ></iframe>
      </div>
    </div>
  </div>
</template>

<style scoped>
.encyclopedia-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.encyclopedia-iframe {
  width: 100%;
  height: 100%;
  border: none;
  flex: 1;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.encyclopedia-iframe.iframe-loaded {
  opacity: 1;
}

.encyclopedia-loading {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: var(--color-bg, #f9fafb);
  z-index: 10;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border, #e5e7eb);
  border-top-color: var(--color-primary-500, #26A69A);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-text {
  font-size: 14px;
  color: var(--color-text-muted, #9ca3af);
}

html.dark .encyclopedia-loading {
  background: var(--color-bg-dark, #0f172a);
}

html.dark .loading-spinner {
  border-color: var(--color-border-dark, #374151);
  border-top-color: var(--color-primary-400, #5EC4BA);
}

html.dark .loading-text {
  color: var(--color-text-muted-dark, #6b7280);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>