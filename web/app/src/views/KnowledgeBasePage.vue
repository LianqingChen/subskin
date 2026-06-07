<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { communityApi } from '@/api/community'
import { toProtectedFileUrl } from '@/utils/file-url'
import type { Post, Collection, CollectionItem } from '@/types'

const router = useRouter()
const authStore = useAuthStore()
const toast = useToast()

const activeTab = ref<'bookmarks' | 'collections'>('bookmarks')

// Bookmarks state
const bookmarks = ref<Post[]>([])
const loadingBookmarks = ref(false)

// Collections state
const collections = ref<Collection[]>([])
const loadingCollections = ref(false)
const expandedCollectionId = ref<number | null>(null)
const collectionItems = ref<Record<number, CollectionItem[]>>({})
const loadingItems = ref<Record<number, boolean>>({})

// Modal state
const showCollectionModal = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const collectionForm = ref({
  name: '',
  description: '',
  icon: 'ri-folder-3-line',
  is_public: false
})

const ICON_OPTIONS = ['ri-folder-3-line', 'ri-capsule-line', 'ri-flask-line', 'ri-microscope-line', 'ri-restaurant-line', 'ri-heart-2-line', 'ri-newspaper-line', 'ri-lightbulb-line', 'ri-file-edit-line', 'ri-focus-3-line', 'ri-star-line']

onMounted(async () => {
  if (!authStore.isLoggedIn) {
    toast.warning('请先登录以访问知识库')
    router.push('/')
    return
  }
  await loadBookmarks()
  await loadCollections()
})

async function loadBookmarks() {
  loadingBookmarks.value = true
  try {
    const res = await communityApi.getBookmarks(50, 0)
    bookmarks.value = res.items
  } catch (err) {
    console.error('Failed to load bookmarks:', err)
    toast.error('加载收藏失败')
  } finally {
    loadingBookmarks.value = false
  }
}

async function loadCollections() {
  loadingCollections.value = true
  try {
    const res = await communityApi.getCollections()
    collections.value = res.items
  } catch (err) {
    console.error('Failed to load collections:', err)
    toast.error('加载收藏夹失败')
  } finally {
    loadingCollections.value = false
  }
}

async function toggleCollectionExpand(collectionId: number) {
  if (expandedCollectionId.value === collectionId) {
    expandedCollectionId.value = null
    return
  }
  expandedCollectionId.value = collectionId
  if (!collectionItems.value[collectionId]) {
    await loadCollectionItems(collectionId)
  }
}

async function loadCollectionItems(collectionId: number) {
  loadingItems.value[collectionId] = true
  try {
    const res = await communityApi.getCollectionItems(collectionId, 50, 0)
    collectionItems.value[collectionId] = res.items
  } catch (err) {
    console.error('Failed to load collection items:', err)
    toast.error('加载收藏夹内容失败')
  } finally {
    loadingItems.value[collectionId] = false
  }
}

async function handleToggleBookmark(postId: number) {
  try {
    const res = await communityApi.toggleBookmark(postId)
    if (!res.bookmarked) {
      bookmarks.value = bookmarks.value.filter(p => p.id !== postId)
      toast.success('已取消收藏')
    }
  } catch (err) {
    console.error('Failed to toggle bookmark:', err)
    toast.error('操作失败')
  }
}

function openCreateModal() {
  isEditing.value = false
  editingId.value = null
  collectionForm.value = {
    name: '',
    description: '',
    icon: 'ri-folder-3-line',
    is_public: false
  }
  showCollectionModal.value = true
}

function openEditModal(collection: Collection) {
  isEditing.value = true
  editingId.value = collection.id
  collectionForm.value = {
    name: collection.name,
    description: collection.description || '',
    icon: collection.icon || 'ri-folder-3-line',
    is_public: collection.is_public
  }
  showCollectionModal.value = true
}

async function saveCollection() {
  if (!collectionForm.value.name.trim()) {
    toast.warning('请输入收藏夹名称')
    return
  }
  try {
    if (isEditing.value && editingId.value) {
      await communityApi.updateCollection(editingId.value, {
        name: collectionForm.value.name.trim(),
        description: collectionForm.value.description.trim() || undefined,
        icon: collectionForm.value.icon,
        is_public: collectionForm.value.is_public
      })
      toast.success('更新成功')
    } else {
      await communityApi.createCollection({
        name: collectionForm.value.name.trim(),
        description: collectionForm.value.description.trim() || undefined,
        icon: collectionForm.value.icon,
        is_public: collectionForm.value.is_public
      })
      toast.success('创建成功')
    }
    showCollectionModal.value = false
    await loadCollections()
  } catch (err) {
    console.error('Failed to save collection:', err)
    toast.error('保存失败')
  }
}

async function deleteCollection(id: number) {
  if (!confirm('确定要删除这个收藏夹吗？其中的文章不会被删除。')) return
  try {
    await communityApi.deleteCollection(id)
    toast.success('删除成功')
    if (expandedCollectionId.value === id) {
      expandedCollectionId.value = null
    }
    await loadCollections()
  } catch (err) {
    console.error('Failed to delete collection:', err)
    toast.error('删除失败')
  }
}

async function removeFromCollection(collectionId: number, postId: number) {
  try {
    await communityApi.removeFromCollection(collectionId, postId)
    toast.success('已移出收藏夹')
    await loadCollectionItems(collectionId)
    await loadCollections() // Update counts
  } catch (err) {
    console.error('Failed to remove from collection:', err)
    toast.error('操作失败')
  }
}

function copyShareLink(slug: string | null) {
  if (!slug) {
    toast.warning('分享链接不可用')
    return
  }
  const url = `${window.location.origin}/collection/${slug}`
  navigator.clipboard.writeText(url).then(() => {
    toast.success('分享链接已复制到剪贴板')
  }).catch(() => {
    toast.error('复制失败，请手动复制')
  })
}

function getCategoryColor(categoryId: number): string {
  const idx = (categoryId - 1) % 7
  const colors = [
    'bg-blue-100 text-blue-700',
    'bg-purple-100 text-purple-700',
    'bg-cyan-100 text-cyan-700',
    'bg-green-100 text-green-700',
    'bg-pink-100 text-pink-700',
    'bg-yellow-100 text-yellow-700',
    'bg-red-100 text-red-700',
  ]
  return colors[idx] || 'bg-gray-100 text-gray-700'
}

function formatTimeAgo(dateStr: string): string {
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 60) return `${Math.max(1, diffMins)}分钟前`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}小时前`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) return `${diffDays}天前`
  return `${Math.floor(diffDays / 30)}月前`
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]+>/g, '')
}

function protectedFileUrl(url?: string | null): string {
  return toProtectedFileUrl(url)
}
</script>

<template>
  <main class="max-w-6xl mx-auto px-4 py-6 space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="section-title"><i class="ri-book-3-line mr-2"></i>我的知识库</h1>
        <p class="section-desc">管理你收藏和整理的知识与经验</p>
      </div>
      <button class="btn-primary text-sm" @click="openCreateModal">
        + 新建收藏夹
      </button>
    </div>

    <!-- Tabs -->
    <div class="flex border-b border-gray-200">
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'bookmarks' ? 'border-primary-500 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
        @click="activeTab = 'bookmarks'"
      >
        🔖 我的收藏
      </button>
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'collections' ? 'border-primary-500 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
        @click="activeTab = 'collections'"
      >
        <i class="ri-folder-3-line mr-1"></i>收藏夹
      </button>
    </div>

    <!-- Bookmarks Tab -->
    <div v-if="activeTab === 'bookmarks'">
      <div v-if="loadingBookmarks" class="text-center py-12 text-gray-400">加载中...</div>
      <div v-else-if="bookmarks.length === 0" class="text-center py-12 text-gray-400">暂无收藏</div>
      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div
          v-for="post in bookmarks"
          :key="post.id"
          class="card-hover p-5 relative group"
        >
          <router-link :to="`/community/${post.id}`" class="no-underline block">
            <div class="flex items-start gap-3">
              <div class="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 text-sm font-medium flex-shrink-0">
                {{ post.author.username.charAt(0) }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-sm font-medium text-gray-900">{{ post.author.username }}</span>
                  <span class="text-xs text-gray-400">{{ formatTimeAgo(post.created_at) }}</span>
                </div>
                <h3 class="font-medium text-gray-900 text-sm leading-snug mb-2 line-clamp-2 pr-6">{{ post.title }}</h3>
                <p class="text-xs text-gray-500 line-clamp-2 mb-3">{{ stripHtml(post.content) }}</p>
                <div v-if="post.images && post.images.length > 0" class="mb-2">
                  <img :src="protectedFileUrl(post.images[0].image_url)" alt="" class="w-16 h-16 rounded-lg object-cover" />
                </div>
                <div class="flex items-center gap-3 text-xs text-gray-400">
                  <span :class="getCategoryColor(post.category_id)" class="px-2 py-0.5 rounded-full">
                    <i :class="post.category.icon" class="mr-0.5"></i> {{ post.category.name }}
                  </span>
                  <span><i class="ri-chat-3-line mr-0.5"></i> {{ post.comment_count }}</span>
                </div>
              </div>
            </div>
          </router-link>
          <button
            @click.prevent="handleToggleBookmark(post.id)"
            class="absolute top-4 right-4 text-red-500 hover:text-red-600 p-1 rounded-full hover:bg-red-50 transition-colors"
            title="取消收藏"
          >
            <i class="ri-heart-3-fill"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- Collections Tab -->
    <div v-if="activeTab === 'collections'">
      <div v-if="loadingCollections" class="text-center py-12 text-gray-400">加载中...</div>
      <div v-else-if="collections.length === 0" class="text-center py-12 text-gray-400">暂无收藏夹</div>
      <div v-else class="space-y-4">
        <div v-for="collection in collections" :key="collection.id" class="card overflow-hidden">
          <!-- Collection Header -->
          <div 
            class="p-5 flex items-center justify-between cursor-pointer hover:bg-gray-50 transition-colors"
            @click="toggleCollectionExpand(collection.id)"
          >
            <div class="flex items-center gap-4">
              <div class="text-3xl"><i :class="collection.icon || 'ri-folder-3-line'"></i></div>
              <div>
                <h3 class="font-medium text-gray-900 flex items-center gap-2">
                  {{ collection.name }}
                  <span v-if="collection.is_public" class="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">公开</span>
                  <span v-else class="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">私密</span>
                </h3>
                <p v-if="collection.description" class="text-sm text-gray-500 mt-0.5">{{ collection.description }}</p>
                <p class="text-xs text-gray-400 mt-1">{{ collection.item_count }} 篇文章 · 更新于 {{ formatTimeAgo(collection.updated_at) }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button 
                v-if="collection.is_public" 
                @click.stop="copyShareLink(collection.share_slug)"
                class="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-full transition-colors"
                 title="复制分享链接"
               >
                 <i class="ri-link"></i>
               </button>
               <button 
                 @click.stop="openEditModal(collection)"
                 class="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-full transition-colors"
                 title="编辑"
               >
                 <i class="ri-edit-line"></i>
               </button>
               <button 
                 @click.stop="deleteCollection(collection.id)"
                 class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-full transition-colors"
                 title="删除"
               >
                 <i class="ri-delete-bin-line"></i>
              </button>
              <span class="text-gray-400 ml-2 transform transition-transform" :class="{ 'rotate-180': expandedCollectionId === collection.id }">
                ▼
              </span>
            </div>
          </div>

          <!-- Collection Items (Expanded) -->
          <div v-if="expandedCollectionId === collection.id" class="border-t border-gray-100 bg-gray-50 p-5">
            <div v-if="loadingItems[collection.id]" class="text-center py-8 text-gray-400 text-sm">加载中...</div>
            <div v-else-if="!collectionItems[collection.id]?.length" class="text-center py-8 text-gray-400 text-sm">收藏夹为空</div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div
                v-for="item in collectionItems[collection.id]"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 p-4 relative group hover:shadow-md transition-shadow"
              >
                <router-link :to="`/community/${item.post.id}`" class="no-underline block">
                  <h4 class="font-medium text-gray-900 text-sm leading-snug mb-2 line-clamp-2 pr-6">{{ item.post.title }}</h4>
                  <p class="text-xs text-gray-500 line-clamp-2 mb-3">{{ stripHtml(item.post.content) }}</p>
                  <div class="flex items-center gap-2 text-xs text-gray-400">
                    <span class="font-medium text-gray-600">{{ item.post.author.username }}</span>
                    <span>·</span>
                    <span :class="getCategoryColor(item.post.category_id)" class="px-2 py-0.5 rounded-full">
                      {{ item.post.category.icon }} {{ item.post.category.name }}
                    </span>
                  </div>
                </router-link>
                <button
                  @click.prevent="removeFromCollection(collection.id, item.post.id)"
                  class="absolute top-3 right-3 text-gray-400 hover:text-red-500 p-1 rounded-full hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
                  title="移出收藏夹"
                >
                  &times;
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create/Edit Collection Modal -->
    <Teleport to="body">
      <div v-if="showCollectionModal" class="fixed inset-0 bg-black/50 z-[100] flex items-center justify-center" @click.self="showCollectionModal = false">
        <div class="bg-white w-full max-w-md rounded-xl shadow-xl overflow-hidden">
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <h2 class="text-lg font-semibold">{{ isEditing ? '编辑收藏夹' : '新建收藏夹' }}</h2>
            <button class="text-gray-400 hover:text-gray-600 text-2xl" @click="showCollectionModal = false">&times;</button>
          </div>
          <div class="p-6 space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">图标</label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="iconOpt in ICON_OPTIONS"
                  :key="iconOpt"
                  class="w-10 h-10 rounded-lg text-xl flex items-center justify-center border transition-colors"
                  :class="collectionForm.icon === iconOpt ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-primary-300'"
                  @click="collectionForm.icon = iconOpt"
                >
                  <i :class="iconOpt"></i>
                </button>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">名称</label>
              <input v-model="collectionForm.name" type="text" placeholder="例如：药物笔记" class="input-field" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">描述（可选）</label>
              <textarea v-model="collectionForm.description" placeholder="简单描述这个收藏夹的用途..." class="input-field min-h-[80px] resize-none"></textarea>
            </div>
            <div class="flex items-center gap-3 pt-2">
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="collectionForm.is_public" class="sr-only peer">
                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-500"></div>
                <span class="ml-3 text-sm font-medium text-gray-700">公开收藏夹</span>
              </label>
              <span class="text-xs text-gray-400">公开后可以通过链接分享给其他人</span>
            </div>
            <div class="pt-4">
              <button class="btn-primary w-full py-2.5" @click="saveCollection">
                {{ isEditing ? '保存修改' : '创建' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
