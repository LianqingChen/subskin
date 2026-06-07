<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEncyclopediaArticles, getEncyclopediaArticle } from '@/api/encyclopedia'
import MarkdownRenderer from '@/components/encyclopedia/MarkdownRenderer.vue'
import RevisionEditor from '@/components/encyclopedia/RevisionEditor.vue'
import RevisionHistory from '@/components/encyclopedia/RevisionHistory.vue'
import CommentSection from '@/components/encyclopedia/CommentSection.vue'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const authStore = useAuthStore()

const articles = ref<any[]>([])
const currentArticle = ref<any>(null)
const loading = ref(true)
const activeTab = ref<'content' | 'revisions' | 'comments'>('content')
const showRevisionEditor = ref(false)
const showMobileMenu = ref(false)

const categories = computed(() => {
  return articles.value
})

const currentSlug = computed(() => {
  const path = route.params.slug
  return Array.isArray(path) ? path.join('/') : path || ''
})

async function loadArticles() {
  try {
    articles.value = await getEncyclopediaArticles()
  } catch (e) {
    toast.error('加载百科文章列表失败')
  }
}

async function loadArticle(slug: string) {
  loading.value = true
  try {
    currentArticle.value = await getEncyclopediaArticle(slug)
    activeTab.value = 'content'
    showRevisionEditor.value = false
  } catch (e: any) {
    if (e?.response?.status === 404) {
      toast.error('文章不存在')
    } else {
      toast.error('加载文章失败')
    }
  } finally {
    loading.value = false
  }
}

// Schema.org MedicalScholarlyArticle
const schemaOrgJson = computed(() => {
  if (!currentArticle.value) return JSON.stringify({})
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'MedicalScholarlyArticle',
    headline: currentArticle.value.title,
    about: { '@type': 'MedicalCondition', name: 'Vitiligo (白癜风)' },
    dateModified: currentArticle.value.updated_at,
    articleBody: currentArticle.value.content?.replace(/<[^>]*>/g, '').slice(0, 500),
    publisher: { '@type': 'Organization', name: 'SubSkin' },
  })
})

function handleRevisionSubmitted() {
  toast.success('修订建议已提交，等待审核')
  showRevisionEditor.value = false
  loadArticle(currentSlug.value)
}

onMounted(async () => {
  await loadArticles()
  if (currentSlug.value) {
    loadArticle(currentSlug.value)
  } else {
    loading.value = false
  }
})

watch(currentSlug, (newSlug) => {
  if (newSlug) {
    loadArticle(newSlug)
  } else {
    currentArticle.value = null
    loading.value = false
  }
})
</script>

<template>
  <div class="min-h-[calc(100dvh-3.5rem)] bg-[#F5F7FA] ">
      <!-- Mobile Drawer -->
      <div
        v-if="showMobileMenu"
        class="md:hidden fixed inset-0 z-40 bg-black/40"
        @click="showMobileMenu = false"
      ></div>
      <aside
        v-if="showMobileMenu"
        class="md:hidden fixed left-0 top-0 bottom-0 z-50 w-64 flex-shrink-0 flex flex-col border-r border-gray-200 dark:border-gray-800 bg-[#F5F7FA] shadow-xl"
      >
        <div class="p-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <div>
            <h2 class="text-sm font-semibold text-gray-900"><i class="ri-book-2-line mr-1"></i>白白百科</h2>
            <p class="text-xs text-gray-500  mt-0.5">白癜风知识百科库</p>
          </div>
          <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" @click="showMobileMenu = false">
            <i class="ri-close-line text-xl"></i>
          </button>
        </div>
        <nav class="flex-1 overflow-y-auto py-2">
          <div v-for="cat in categories" :key="cat.category" class="mb-2">
            <div class="px-4 py-1.5 text-xs font-medium text-gray-500  uppercase tracking-wider">
              <i :class="cat.icon" class="mr-1"></i>{{ cat.category }}
            </div>
            <router-link
              v-for="article in cat.articles"
              :key="article.slug"
              :to="`/encyclopedia/${article.slug}`"
              class="block px-4 py-2 text-sm transition-colors"
              :class="currentSlug === article.slug
                ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300 font-medium'
                : 'text-gray-600  hover:bg-gray-50'"
              @click="showMobileMenu = false"
            >
              {{ article.title }}
            </router-link>
          </div>
        </nav>
      </aside>

      <!-- Main Content -->
      <div class="flex-1 min-w-0 flex flex-col">
        <!-- Top category tabs (desktop: horizontal scrollable, mobile: hamburger) -->
        <div class="flex items-center gap-2 px-4 py-2 border-b border-gray-200 dark:border-gray-800 bg-[#F5F7FA] overflow-x-auto no-scrollbar">
          <!-- Mobile hamburger for full catalog -->
          <button
            class="md:hidden flex items-center gap-1 px-2 py-1.5 rounded-lg text-sm text-gray-600  hover:bg-gray-100 flex-shrink-0"
            @click="showMobileMenu = true"
          >
            <i class="ri-menu-line text-lg"></i>
            目录
          </button>
          <!-- Desktop: horizontal category tabs -->
          <template v-for="cat in categories" :key="cat.category">
            <button
              v-for="article in cat.articles"
              :key="article.slug"
              class="hidden md:block flex-shrink-0 px-3 py-1.5 rounded-lg text-sm transition-colors whitespace-nowrap"
              :class="currentSlug === article.slug
                ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium'
                : 'text-gray-600  hover:bg-gray-50'"
              @click="router.push(`/encyclopedia/${article.slug}`)"
            >
              {{ article.title }}
            </button>
          </template>
          <div class="flex-1 min-w-0"></div>
          <button
            class="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/30 flex-shrink-0"
            @click="router.push('/encyclopedia')"
          >
            <i class="ri-book-2-line mr-1"></i>百科首页
          </button>
        </div>

        <!-- Loading State -->
        <div v-if="loading" class="flex-1 flex items-center justify-center">
          <div class="text-center">
            <div class="w-8 h-8 border-2 border-primary-200 border-t-primary-500 rounded-full animate-spin mx-auto"></div>
            <p class="text-sm text-gray-500  mt-3">加载中...</p>
          </div>
        </div>

        <!-- Article Content -->
        <div v-else-if="currentArticle" class="flex-1 overflow-y-auto">
          <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <!-- Article Header -->
            <div class="mb-6">
              <h1 class="text-2xl sm:text-3xl font-bold text-gray-900">
                {{ currentArticle.title }}
              </h1>
              <div class="flex items-center gap-3 mt-3 text-sm text-gray-500 ">
                <span>{{ currentArticle.category }}</span>
                <span>·</span>
                <span>{{ currentArticle.view_count }} 次阅读</span>
                <span v-if="currentArticle.updated_at">
                  · 更新于 {{ new Date(currentArticle.updated_at).toLocaleDateString('zh-CN') }}
                </span>
              </div>
            </div>

            <!-- Toolbar -->
            <div class="flex items-center gap-2 mb-6 pb-4 border-b border-gray-200 dark:border-gray-800">
              <button
                class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
                :class="activeTab === 'content'
                  ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300'
                  : 'text-gray-600  hover:bg-gray-100'"
                @click="activeTab = 'content'; showRevisionEditor = false"
              >
                <i class="ri-file-text-line mr-1"></i>正文
              </button>
              <button
                class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
                :class="activeTab === 'revisions'
                  ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300'
                  : 'text-gray-600  hover:bg-gray-100'"
                @click="activeTab = 'revisions'"
              >
                <i class="ri-history-line mr-1"></i>修订历史 ({{ currentArticle.revision_count || 0 }})
              </button>
              <button
                class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
                :class="activeTab === 'comments'
                  ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300'
                  : 'text-gray-600  hover:bg-gray-100'"
                @click="activeTab = 'comments'"
              >
                <i class="ri-chat-3-line mr-1"></i>讨论
              </button>
              <div class="flex-1"></div>
              <button
                v-if="authStore.isLoggedIn && activeTab === 'content' && !showRevisionEditor"
                class="btn-primary px-3 py-1.5 text-sm"
                @click="showRevisionEditor = true"
              >
                <i class="ri-edit-line mr-1"></i>提交修订
              </button>
            </div>

            <!-- Content Tab -->
            <div v-if="activeTab === 'content'">
              <div v-if="showRevisionEditor" class="mb-6">
                <RevisionEditor
                  :article="currentArticle"
                  @submitted="handleRevisionSubmitted"
                  @cancel="showRevisionEditor = false"
                />
              </div>
              <MarkdownRenderer :content="currentArticle.content" />
            </div>

            <!-- Revisions Tab -->
            <div v-if="activeTab === 'revisions'">
              <RevisionHistory :article-slug="currentSlug" />
            </div>

            <!-- Comments Tab -->
            <div v-if="activeTab === 'comments'">
              <CommentSection :article-slug="currentSlug" />
            </div>
          </div>
        </div>

        <!-- Index Page (no article selected) -->
        <div v-else class="flex-1 overflow-y-auto">
          <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <div class="mb-8">
              <h1 class="text-2xl sm:text-3xl font-bold text-gray-900"><i class="ri-book-2-line mr-2"></i>白白百科</h1>
              <p class="text-gray-500  mt-2">白癜风知识百科库，由病友和医生共同维护</p>
            </div>
            <div v-for="cat in categories" :key="cat.category" class="mb-8">
              <h2 class="section-title mb-4"><i :class="cat.icon" class="mr-2"></i>{{ cat.category }}</h2>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <router-link
                  v-for="article in cat.articles"
                  :key="article.slug"
                  :to="`/encyclopedia/${article.slug}`"
                  class="card p-4 hover:shadow-md transition-shadow"
                >
                  <h3 class="text-sm font-semibold text-gray-900 mb-1">{{ article.title }}</h3>
                  <p v-if="article.summary" class="text-xs text-gray-500  line-clamp-2">{{ article.summary }}</p>
                </router-link>
              </div>
            </div>
          </div>
        </div>
      </div>
  </div>
  <component :is="'script'" type="application/ld+json" v-text="schemaOrgJson" />
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
