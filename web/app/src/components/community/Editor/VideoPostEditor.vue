<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useDrafts } from '@/composables/useDrafts'
import { communityApi } from '@/api/community'
import type { Category } from '@/types'
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
const categoryId = ref<number | null>(null)
const isAnonymous = ref(false)  // kept for backward compat; always forced to false
const mood = ref('')
const tags = ref<string[]>([])
const categories = ref<Category[]>([])
const publishing = ref(false)
const videoUrl = ref('')
const videoPreviewUrl = ref('')
const uploading = ref(false)
const draftServerId = ref<number | undefined>(undefined)
const draftKey = ref<string>('')

const isValid = computed(() => title.value.trim().length > 0 && content.value.trim().length > 0 && categoryId.value !== null && videoUrl.value.trim().length > 0)

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
    type: 'video',
    title: title.value,
    content: content.value,
    tags: tags.value,
    categoryId: categoryId.value,
    mood: mood.value,
    isAnonymous: isAnonymous.value,
    existingKey: draftKey.value || undefined,
    serverId: draftServerId.value,
  })
  if (!draftKey.value) draftKey.value = key
}

watch([title, content, categoryId, isAnonymous, mood, tags, videoUrl], () => {
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

const handleVideoUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  const file = input.files[0]
  input.value = ''
  if (!file.type.startsWith('video/')) { toast.error('请选择视频文件'); return }
  if (file.size > 100 * 1024 * 1024) { toast.error('视频大小不能超过100MB'); return }
  uploading.value = true
  try {
    const res = await communityApi.uploadFile(file)
    videoUrl.value = res.file_url
  } catch { toast.error('视频上传失败') }
  finally { uploading.value = false }
}

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
    categoryId.value = post.category_id
    isAnonymous.value = post.is_anonymous // always show nickname
    mood.value = post.mood || ''
    tags.value = post.tags.map(t => t.name)
    videoUrl.value = (post as any).video_url || ''
    videoPreviewUrl.value = (post as any).video_thumbnail || ''
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
          categoryId.value = d.categoryId || null
          tags.value = d.tags || []
          mood.value = d.mood || ''
          isAnonymous.value = d.isAnonymous ?? false
          videoUrl.value = d.videoUrl || ''
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
      content: content.value.trim(),
      content_json: undefined,
      category_id: categoryId.value || firstCat?.id || 1,
      post_type: 'video' as const,
      video_url: videoUrl.value,
      tag_names: tags.value,
      is_anonymous: false,
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
      <span class="text-sm font-medium text-gray-900">发视频</span>
      <button @click="handlePublish" class="btn-primary px-5 py-1 rounded-full text-sm font-medium" :disabled="publishing || !isValid">
        {{ publishing ? '发布中...' : (isEdit ? '更新' : '发布') }}
      </button>
    </header>

    <main class="flex-1 overflow-y-auto pb-8">
      <div class="max-w-2xl mx-auto px-4 py-4 space-y-5">
        <div class="space-y-2">
          <label class="text-sm font-medium text-gray-700">上传视频</label>
          <div v-if="videoUrl" class="relative rounded-xl overflow-hidden bg-black">
            <video :src="videoUrl" controls class="w-full max-h-[300px] object-contain" />
          </div>
          <label v-else
            class="block aspect-video rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700 flex flex-col items-center justify-center text-gray-400  hover:text-primary-500 hover:border-primary-300 dark:hover:border-primary-600 cursor-pointer transition-all duration-200 bg-gray-50 "
            :class="{ 'opacity-50 cursor-not-allowed': uploading }">
            <svg class="w-12 h-12 mb-2 text-gray-300 " fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
            <span class="text-sm font-medium">{{ uploading ? '上传中...' : '选择视频' }}</span>
            <span class="text-[11px] text-gray-400  mt-1">支持 MP4, MOV，最大 100MB</span>
            <input type="file" class="hidden" accept="video/*" @change="handleVideoUpload" :disabled="uploading" />
          </label>
        </div>

        <input v-model="title" type="text" placeholder="添加标题..."
          class="w-full text-lg font-medium text-gray-900 placeholder-gray-300 dark:placeholder-gray-600 outline-none bg-transparent border-b border-gray-100 dark:border-gray-700 pb-2 focus:border-primary-400 transition-colors" maxlength="100" />

        <textarea v-model="content" placeholder="描述你的视频..."
          class="w-full min-h-[100px] text-sm text-gray-900 placeholder-gray-300 dark:placeholder-gray-600 outline-none bg-transparent resize-none leading-relaxed" />

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

        <div class="bg-gray-50  border border-gray-200 dark:border-gray-700 rounded-lg p-3 flex items-start gap-2">
          <span class="text-amber-500 text-sm mt-0.5"><i class="ri-error-warning-line"></i></span>
          <p class="text-xs text-gray-500  leading-relaxed">本平台不构成医疗建议，分享内容仅供参考。</p>
        </div>
      </div>
    </main>
  </div>
</template>
