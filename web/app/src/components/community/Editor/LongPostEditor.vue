<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useDrafts } from '@/composables/useDrafts'
import { communityApi } from '@/api/community'
import type { Category } from '@/types'
import RichEditor from '@/components/community/RichEditor.vue'
import TagSelector from '@/components/community/TagSelector.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const toast = useToast()
const { saveDraftWithSync } = useDrafts()

const isEdit = computed(() => !!route.params.id)
const postId = computed(() => Number(route.params.id) || 0)

const title = ref('')
const content = ref('')
const contentJson = ref('')
const categoryId = ref<number | null>(null)
const isPrivate = ref(false)
const isAnonymous = ref(false)  // kept for backward compat; always forced to false
const mood = ref('')
const tags = ref<string[]>([])
const categories = ref<Category[]>([])
const publishing = ref(false)
const claimsWarning = ref<string[]>([])
const draftServerId = ref<number | undefined>(undefined)
const draftKey = ref<string>('')

const isValid = computed(() => title.value.trim().length > 0 && content.value.trim().length > 0 && categoryId.value !== null)

const estimatedReadTime = computed(() => {
  const text = content.value.replace(/<[^>]+>/g, '')
  const minutes = Math.max(1, Math.ceil(text.length / 400))
  return minutes
})

const MOOD_OPTIONS = [
  { value: '💪坚持中', icon: 'ri-boxing-line', label: '坚持中' },
  { value: '😔低落', icon: 'ri-emotion-sad-line', label: '低落' },
  { value: '🎉好转', icon: 'ri-emotion-happy-line', label: '好转' },
  { value: '🤔疑问', icon: 'ri-question-line', label: '疑问' },
]

let draftTimer: ReturnType<typeof setTimeout> | null = null

const autoSaveDraft = async () => {
  if (isEdit.value) return
  if (!title.value.trim() && !content.value.trim()) return
  const key = await saveDraftWithSync({
    type: 'long',
    title: title.value,
    content: content.value,
    contentJson: contentJson.value || null,
    tags: tags.value,
    categoryId: categoryId.value,
    mood: mood.value,
    isPrivate: isPrivate.value,
    isAnonymous: isAnonymous.value,
    existingKey: draftKey.value || undefined,
    serverId: draftServerId.value,
  })
  if (!draftKey.value) draftKey.value = key
}

watch([title, content, contentJson, categoryId, isPrivate, isAnonymous, mood, tags], () => {
  if (draftTimer) clearTimeout(draftTimer)
  draftTimer = setTimeout(autoSaveDraft, 2000)
}, { deep: true })

onBeforeUnmount(() => { if (draftTimer) clearTimeout(draftTimer) })

watch([categories], ([cats]) => {
  if (cats.length > 0 && !categoryId.value) {
    const cat = cats.find(c => c.name === '治疗分享') || cats[0]
    categoryId.value = cat.id
  }
}, { immediate: true })

let claimsTimer: ReturnType<typeof setTimeout> | null = null
watch([title, content], () => {
  if (claimsTimer) clearTimeout(claimsTimer)
  claimsTimer = setTimeout(async () => {
    if (!title.value.trim() && !content.value.trim()) { claimsWarning.value = []; return }
    try {
      const res = await communityApi.checkClaims(title.value, content.value)
      claimsWarning.value = res.words || []
    } catch { claimsWarning.value = [] }
  }, 800)
})

const loadCategories = async () => {
  try { categories.value = await communityApi.getCategories() }
  catch { toast.error('加载分类失败') }
}

const loadPost = async () => {
  if (!isEdit.value) return
  try {
    const post = await communityApi.getPost(postId.value)
    title.value = post.title
    content.value = post.content
    contentJson.value = post.content_json || ''
    categoryId.value = post.category_id
    isPrivate.value = post.is_private
    isAnonymous.value = post.is_anonymous // always show nickname,
    mood.value = post.mood || ''
    tags.value = post.tags.map(t => t.name)
  } catch {
    toast.error('加载帖子失败')
    router.push('/community')
  }
}

onMounted(async () => {
  if (!authStore.isLoggedIn) { toast.warning('请先登录'); router.push('/community'); return }
  await loadCategories()
  if (isEdit.value) {
    await loadPost()
  } else {
    const dk = route.query.draftKey as string
    if (dk) {
      try {
        const raw = localStorage.getItem(dk)
        if (raw) {
        const d = JSON.parse(raw)
        title.value = d.title || ''
        content.value = d.content || ''
        contentJson.value = d.contentJson || ''
        categoryId.value = d.categoryId || null
          tags.value = d.tags || []
          mood.value = d.mood || ''
          isPrivate.value = d.isPrivate ?? false
          isAnonymous.value = d.isAnonymous ?? false
          draftKey.value = dk
          draftServerId.value = d.serverId
          if (title.value || content.value) toast.show('已恢复草稿', 'info')
        }
      } catch {}
    }
  }
})

const goBack = () => {
  if (window.history.length > 1) router.back()
  else router.push('/community')
}

const handlePublish = async () => {
  if (!isValid.value) return
  publishing.value = true
  try {
    const firstCat = categories.value.find(c => c.name === '治疗分享') || categories.value[0]
    const payload = {
      title: title.value.trim(),
      content: content.value,
      content_json: contentJson.value || undefined,
      category_id: categoryId.value || firstCat?.id || 1,
      post_type: 'long' as const,
      tag_names: tags.value,
      is_anonymous: false,
      is_private: isPrivate.value,
      mood: mood.value || undefined,
    }
    let result
    if (isEdit.value) {
      result = await communityApi.updatePost(postId.value, payload)
      toast.success('更新成功')
      router.replace(`/community/${result.id}`)
    } else {
      result = await communityApi.createPost(payload)
      toast.success('发布成功')
      if (draftKey.value) localStorage.removeItem(draftKey.value)
      if (draftServerId.value) communityApi.deletePost(draftServerId.value).catch(() => {})
      router.push(`/community/${result.id}`)
    }
  } catch (error: any) {
    toast.error(error.response?.data?.detail || '发布失败')
  } finally {
    publishing.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <header class="h-12 bg-white border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-4 sticky top-0 z-30">
      <button @click="goBack" class="text-sm text-gray-600  hover:text-gray-900 dark:hover:text-gray-100">取消</button>
      <span class="text-sm font-medium text-gray-900">写长文</span>
      <button @click="handlePublish" class="btn-primary px-5 py-1 rounded-full text-sm font-medium" :disabled="publishing || !isValid">
        {{ publishing ? '发布中...' : (isEdit ? '更新' : '发布') }}
      </button>
    </header>

    <main class="flex-1 overflow-y-auto pb-8">
      <div class="max-w-2xl mx-auto px-4 py-4 space-y-5">
        <input v-model="title" type="text" placeholder="添加标题，让大家看到你的分享..."
          class="w-full text-lg font-medium text-gray-900 placeholder-gray-300 dark:placeholder-gray-600 outline-none bg-transparent border-b border-gray-100 dark:border-gray-700 pb-2 focus:border-primary-400 transition-colors" maxlength="100" />

        <RichEditor v-model="content" v-model:content-json="contentJson" placeholder="分享你的经历、建议或疑问..." class="min-h-[200px]" />

        <div class="text-xs text-gray-400 ">预估阅读 {{ estimatedReadTime }} 分钟</div>

        <div class="space-y-2">
          <label class="text-sm font-medium text-gray-700">此刻心情</label>
          <div class="flex flex-wrap gap-2">
            <button v-for="m in MOOD_OPTIONS" :key="m.value" @click="mood = mood === m.value ? '' : m.value" type="button"
              class="px-3 py-1.5 rounded-full text-sm border transition-all"
              :class="mood === m.value ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300 shadow-sm' : 'border-gray-200 dark:border-gray-600 text-gray-500  hover:border-gray-300'">
              <i :class="m.icon" class="mr-0.5"></i> {{ m.label }}
            </button>
          </div>
        </div>

        <div class="space-y-2">
          <label class="text-sm font-medium text-gray-700">分类 <span class="text-red-500">*</span></label>
          <div class="flex flex-wrap gap-2">
            <button v-for="cat in categories" :key="cat.id" @click="categoryId = cat.id" type="button"
              class="px-3 py-1.5 rounded-full text-sm border transition-all"
              :class="categoryId === cat.id ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300 shadow-sm' : 'border-gray-200 dark:border-gray-600 text-gray-500  hover:border-gray-300'">
              {{ cat.icon }} {{ cat.name }}
            </button>
          </div>
        </div>

        <div class="space-y-2">
          <label class="text-sm font-medium text-gray-700">标签</label>
          <TagSelector v-model="tags" :max-tags="5" />
        </div>

        <div class="flex items-center justify-between py-2">
          <div>
            <span class="text-sm font-medium text-gray-700"><i class="ri-lock-line"></i> 仅自己可见</span>
            <p class="text-[11px] text-gray-400 ">仅自己可见，随时可分享到社区</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input v-model="isPrivate" type="checkbox" class="sr-only peer">
            <div class="w-10 h-5 rounded-full bg-gray-200 peer-focus:outline-none peer peer-checked:bg-primary-500 peer-checked:after:translate-x-full after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all"></div>
          </label>
        </div>

        <div v-if="claimsWarning.length > 0" class="bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 rounded-lg p-3 space-y-1">
          <div class="flex items-center gap-2 text-amber-700 dark:text-amber-300">
            <span><i class="ri-error-warning-line"></i></span>
            <span class="text-sm font-medium">检测到可能不准确的表述</span>
          </div>
          <p class="text-xs text-amber-600 dark:text-amber-400">内容中包含「{{ claimsWarning.join('」「') }}」等词，这些表述可能不准确。</p>
        </div>

        <div class="bg-gray-50  border border-gray-200 dark:border-gray-700 rounded-lg p-3 flex items-start gap-2">
          <span class="text-amber-500 text-sm mt-0.5"><i class="ri-error-warning-line"></i></span>
          <p class="text-xs text-gray-500  leading-relaxed">本平台不构成医疗建议，分享内容仅供参考。请勿轻信偏方，治疗请遵医嘱。</p>
        </div>
      </div>
    </main>
  </div>
</template>
