<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { communityApi } from '@/api/community'
import type { Collection, CollectionItem } from '@/types'

const route = useRoute()

const loading = ref(true)
const error = ref(false)
const collection = ref<Collection | null>(null)
const items = ref<CollectionItem[]>([])

onMounted(async () => {
  const slug = route.params.slug as string
  if (!slug) {
    error.value = true
    loading.value = false
    return
  }

  try {
    const col = await communityApi.getCollectionBySlug(slug)
    collection.value = col
    
    const res = await communityApi.getCollectionItems(col.id, 100, 0)
    items.value = res.items
  } catch (err) {
    console.error('Failed to load shared collection:', err)
    error.value = true
  } finally {
    loading.value = false
  }
})

function getCategoryColor(categoryId: number): string {
  const idx = (categoryId - 1) % 7
  const colors = [
    'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
    'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
    'bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300',
    'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
    'bg-pink-100 text-pink-700 dark:bg-pink-900 dark:text-pink-300',
    'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
    'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  ]
  return colors[idx] || 'bg-gray-100 text-gray-700'
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]+>/g, '')
}
</script>

<template>
  <div class="min-h-screen bg-[#F5F7FA] pb-12">
    <!-- Brand Header -->
    <header class="bg-[#F5F7FA] border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
      <div class="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <router-link to="/" class="flex items-center gap-2 no-underline">
          <span class="text-xl"><i class="ri-leaf-line"></i></span>
          <span class="font-bold text-gray-900">SubSkin 小白知识库</span>
        </router-link>
        <router-link to="/community" class="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 font-medium">
            返回发现
        </router-link>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-8">
      <div v-if="loading" class="text-center py-20">
        <div class="animate-spin text-4xl mb-4"><i class="ri-leaf-line"></i></div>
        <p class="text-gray-500 ">正在加载知识库...</p>
      </div>

      <div v-else-if="error || !collection" class="text-center py-20 bg-[#F5F7FA] rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700">
        <div class="text-6xl mb-4">📭</div>
        <h2 class="text-xl font-bold text-gray-900 mb-2">知识库不存在或已设为私密</h2>
        <p class="text-gray-500  mb-6">该分享链接可能已失效，或者作者取消了公开分享。</p>
        <router-link to="/community" class="btn-primary inline-block">
          去发现看看
        </router-link>
      </div>

      <div v-else class="space-y-8">
        <!-- Collection Info -->
        <div class="bg-[#F5F7FA] rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 p-8 text-center">
          <div class="text-5xl mb-4">{{ collection.icon || '📂' }}</div>
          <h1 class="text-2xl font-bold text-gray-900 mb-3">{{ collection.name }}</h1>
          <p v-if="collection.description" class="text-gray-600  max-w-2xl mx-auto mb-4">
            {{ collection.description }}
          </p>
          <div class="flex items-center justify-center gap-2 text-sm text-gray-500 ">
            <span class="bg-gray-100 px-2 py-1 rounded-md">{{ collection.item_count }} 篇分享</span>
            <span>·</span>
            <span>由热心小白整理</span>
          </div>
        </div>

        <!-- Items Grid -->
        <div v-if="items.length === 0" class="text-center py-12 text-gray-400 ">
          这个知识库还是空的
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <router-link
            v-for="item in items"
            :key="item.id"
            :to="`/community/${item.post.id}`"
            class="bg-[#F5F7FA] rounded-xl border border-gray-200 dark:border-gray-700 p-5 hover:shadow-md hover:border-primary-300 dark:hover:border-primary-600 transition-all no-underline block group"
          >
            <div class="flex items-start gap-3 mb-3">
              <div class="w-8 h-8 rounded-full bg-primary-50 dark:bg-primary-900 flex items-center justify-center text-primary-700 dark:text-primary-300 text-xs font-medium flex-shrink-0">
                {{ item.post.author.username.charAt(0) }}
              </div>
              <div class="flex-1 min-w-0 pt-1">
                <span class="text-xs font-medium text-gray-600 ">{{ item.post.author.username }}</span>
              </div>
              <span :class="getCategoryColor(item.post.category_id)" class="px-2 py-0.5 rounded-full text-xs whitespace-nowrap">
                {{ item.post.category.icon }} {{ item.post.category.name }}
              </span>
            </div>
            <h3 class="font-medium text-gray-900 text-base leading-snug mb-2 line-clamp-2 group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors">
              {{ item.post.title }}
            </h3>
            <p class="text-sm text-gray-500  line-clamp-3 mb-4">
              {{ stripHtml(item.post.content) }}
            </p>
            <div class="flex items-center gap-4 text-xs text-gray-400 ">
              <span><i class="ri-heart-3-line mr-0.5"></i> {{ item.post.like_count }}</span>
              <span><i class="ri-chat-3-line mr-0.5"></i> {{ item.post.comment_count }}</span>
            </div>
          </router-link>
        </div>

        <!-- Footer CTA -->
        <div class="text-center pt-8 pb-4">
          <p class="text-sm text-gray-400  mb-4"><i class="ri-error-warning-line mr-1"></i>本平台内容仅供参考，不构成医疗建议</p>
          <router-link to="/community" class="btn-primary inline-block">
            加入发现讨论
          </router-link>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
