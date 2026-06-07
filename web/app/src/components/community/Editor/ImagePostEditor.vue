<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useDrafts } from '@/composables/useDrafts'
import { useGeolocation } from '@/composables/useGeolocation'
import { communityApi } from '@/api/community'
import type { Category } from '@/types'
import TagSelector from '@/components/community/TagSelector.vue'
import CityPicker from '@/components/community/CityPicker.vue'
import { toProtectedFileUrl } from '@/utils/file-url'
import RichEditor from '@/components/community/RichEditor.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const toast = useToast()
const { saveDraft: saveDraftToStorage } = useDrafts()
const geo = useGeolocation()

const isEdit = computed(() => !!route.params.id)
const postId = computed(() => Number(route.params.id) || 0)
const draftKey = computed(() => route.query.draftKey as string || '')
const pageTitle = computed(() => isEdit.value ? '编辑帖子' : (draftKey.value ? '编辑草稿' : '发图文'))

const title = ref('')
const content = ref('')
const contentJson = ref('')
const categoryId = ref<number | null>(null)
const isAnonymous = ref(false)  // kept for backward compat; always forced to false
const isPrivate = ref(false)
const mood = ref('')
const tags = ref<string[]>([])
const previewImages = ref<string[]>([])
const categories = ref<Category[]>([])
const publishing = ref(false)
const uploading = ref(false)
const currentDraftKey = ref('')
const draftServerId = ref<number | null>(null)  // server post ID if draft was synced
const showCityPicker = ref(false)
const showCity = ref(true)

const isValid = computed(() => title.value.trim().length > 0 || content.value.trim().length > 0 || previewImages.value.length > 0)

const MOOD_OPTIONS = [
  { value: '💪坚持中', icon: 'ri-boxing-line', label: '坚持中' },
  { value: '😔低落', icon: 'ri-emotion-sad-line', label: '低落' },
  { value: '🎉好转', icon: 'ri-emotion-happy-line', label: '好转' },
  { value: '🤔疑问', icon: 'ri-question-line', label: '疑问' },
]

const protectedFileUrl = (url?: string | null) => toProtectedFileUrl(url)

let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

const autoSaveDraft = () => {
  if (isEdit.value) return
  const key = saveDraftToStorage({
    type: 'image',
    title: title.value,
    content: content.value,
    contentJson: contentJson.value || null,
    images: previewImages.value,
    tags: tags.value,
    categoryId: categoryId.value,
    mood: mood.value,
    isAnonymous: isAnonymous.value,
    isPrivate: isPrivate.value,
    showCity: showCity.value,
    existingKey: currentDraftKey.value || undefined,
  })
  if (!currentDraftKey.value) currentDraftKey.value = key
}

watch([title, content, contentJson, categoryId, isAnonymous, isPrivate, showCity, mood, tags, previewImages], () => {
  if (autoSaveTimer) clearTimeout(autoSaveTimer)
  autoSaveTimer = setTimeout(autoSaveDraft, 1000)
}, { deep: true })

onBeforeUnmount(() => { if (autoSaveTimer) clearTimeout(autoSaveTimer) })

watch([categories], ([cats]) => {
  if (cats.length > 0 && !categoryId.value) {
    const cat = cats.find(c => c.name === '治疗分享') || cats[0]
    categoryId.value = cat.id
  }
}, { immediate: true })

const handleImageUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  const files = Array.from(input.files)
  input.value = ''
  for (const file of files) {
    if (!file.type.startsWith('image/')) continue
    if (file.size > 5 * 1024 * 1024) { toast.error('图片大小不能超过5MB'); continue }
    uploading.value = true
    try {
      const res = await communityApi.uploadImage(file)
      previewImages.value.push(res.image_url)
    } catch { toast.error('图片上传失败') }
    finally { uploading.value = false }
  }
}

const removeImage = (index: number) => { previewImages.value.splice(index, 1) }

const loadCategories = async () => {
  try { categories.value = await communityApi.getCategories() }
  catch { toast.error('加载分类失败') }
}

const loadDraftByKey = () => {
  if (!draftKey.value) return false
  const raw = localStorage.getItem(draftKey.value)
  if (!raw) return false
  try {
    const d = JSON.parse(raw)
    title.value = d.title || ''
    content.value = d.content || ''
    contentJson.value = d.contentJson || ''
    categoryId.value = d.categoryId || null
    tags.value = d.tags || []
    previewImages.value = d.images || d.previewImages || []
    mood.value = d.mood || ''
    isAnonymous.value = d.isAnonymous ?? false
    isPrivate.value = d.isPrivate ?? false
    showCity.value = d.showCity ?? true
    currentDraftKey.value = draftKey.value
    draftServerId.value = d.serverId ?? null
    toast.show('已恢复草稿', 'info')
    return true
  } catch { return false }
}

const loadPost = async () => {
  if (!isEdit.value) return
  try {
    const post = await communityApi.getPost(postId.value)
    title.value = post.title
    content.value = post.content
    contentJson.value = post.content_json || ''
    categoryId.value = post.category_id
    isAnonymous.value = post.is_anonymous // always show nickname
    isPrivate.value = post.is_private
    mood.value = post.mood || ''
    tags.value = post.tags.map(t => t.name)
    previewImages.value = post.images.map(img => img.image_url)
  } catch {
    toast.error('加载帖子失败')
    router.push('/community')
  }
}

onMounted(async () => {
  if (!authStore.isLoggedIn) { toast.warning('请先登录'); router.push('/community'); return }
  await geo.requestCity()
  await loadCategories()
  if (isEdit.value) {
    await loadPost()
  } else if (draftKey.value) {
    loadDraftByKey()
  } else {
    autoSaveDraft()
  }
})

const goBack = () => {
  if (window.history.length > 1) router.back()
  else router.push('/community')
}

const handlePublish = async () => {
  if (!title.value.trim() && !content.value.trim() && !previewImages.value.length) return
  publishing.value = true
  try {
    const firstCat = categories.value.find(c => c.name === '治疗分享') || categories.value[0]
    const payload = {
      title: title.value.trim() || '无标题',
      content: content.value.trim(),
      content_json: contentJson.value || undefined,
      category_id: categoryId.value || firstCat?.id || 1,
      post_type: 'image' as const,
      images: previewImages.value,
      tag_names: tags.value,
      is_anonymous: false,
      is_private: isPrivate.value,
      mood: mood.value || undefined,
      city: showCity.value ? (geo.city.value || undefined) : null,
      latitude: showCity.value ? (geo.lat.value ?? undefined) : undefined,
      longitude: showCity.value ? (geo.lng.value ?? undefined) : undefined,
    }
    let result
    if (isEdit.value) {
      result = await communityApi.updatePost(postId.value, payload)
      toast.success('更新成功')
      router.replace(`/community/${result.id}`)
    } else if (draftServerId.value) {
      // Draft was synced to server — update existing private post instead of creating a duplicate
      payload.is_private = false  // Explicitly make public
      result = await communityApi.updatePost(draftServerId.value, payload)
      toast.success('发布成功')
      if (currentDraftKey.value) localStorage.removeItem(currentDraftKey.value)
      router.push(`/community/${result.id}`)
    } else {
      result = await communityApi.createPost(payload)
      toast.success('发布成功')
      if (currentDraftKey.value) localStorage.removeItem(currentDraftKey.value)
      router.replace(`/community/${result.id}`)
    }
  } catch (error: any) {
    toast.error(error.response?.data?.detail || '发布失败')
  } finally {
    publishing.value = false
  }
}

const handleSaveDraft = async () => {
  saveDraftToStorage({
    type: 'image',
    title: title.value,
    content: content.value,
    contentJson: contentJson.value || null,
    images: previewImages.value,
    tags: tags.value,
    categoryId: categoryId.value,
    mood: mood.value,
    isAnonymous: isAnonymous.value,
    isPrivate: isPrivate.value,
    existingKey: currentDraftKey.value || undefined,
  })

  if (isEdit.value) {
    try {
      await communityApi.deletePost(postId.value)
    } catch {
      toast.error('存草稿失败')
      return
    }
  }

  toast.success('已存为草稿')
  router.replace('/community')
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <header class="h-12 bg-white border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-4 sticky top-0 z-30">
      <button @click="goBack" class="text-sm text-gray-600  hover:text-gray-900 dark:hover:text-gray-100">取消</button>
      <span class="text-sm font-medium text-gray-900">{{ pageTitle }}</span>
      <div class="flex items-center gap-2">
        <button @click="handleSaveDraft" class="text-sm text-gray-500  hover:text-primary-600 dark:hover:text-primary-400" :disabled="publishing">存草稿</button>
        <button @click="handlePublish" class="btn-primary px-4 py-1 rounded-full text-sm font-medium" :disabled="publishing || !isValid">
          {{ publishing ? '发布中...' : (isEdit ? '更新' : '发布') }}
        </button>
      </div>
    </header>

    <main class="flex-1 overflow-y-auto pb-8">
      <div class="max-w-2xl mx-auto px-4 py-4 space-y-5">
        <div class="space-y-2">
          <label class="text-sm font-medium text-gray-700">添加图片</label>
          <div class="grid grid-cols-3 sm:grid-cols-4 gap-2">
            <div v-for="(img, index) in previewImages" :key="index"
              class="relative aspect-square rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 group shadow-sm">
              <img :src="protectedFileUrl(img)" class="w-full h-full object-cover" />
              <button @click="removeImage(index)"
                class="absolute top-1.5 right-1.5 w-6 h-6 bg-black/40 backdrop-blur-sm text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
              </button>
              <span v-if="index === 0" class="absolute bottom-1.5 left-1.5 text-[9px] bg-primary-500/90 backdrop-blur-sm text-white px-2 py-0.5 rounded-md font-medium">封面</span>
            </div>
            <label v-if="previewImages.length < 9"
              class="aspect-square rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700 flex flex-col items-center justify-center text-gray-400  hover:text-primary-500 hover:border-primary-300 dark:hover:border-primary-600 cursor-pointer transition-all duration-200 bg-gray-50  hover:bg-primary-50/50 dark:hover:bg-primary-900/10"
              :class="{ 'opacity-50 cursor-not-allowed': uploading }">
              <svg class="w-8 h-8 mb-1.5 text-gray-300 " fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 4v16m8-8H4"/></svg>
              <span class="text-[11px] font-medium">{{ uploading ? '上传中' : '添加图片' }}</span>
              <input type="file" class="hidden" accept="image/*" multiple @change="handleImageUpload" :disabled="uploading" />
            </label>
          </div>
          <p class="text-[11px] text-gray-400 ">第一张图将作为封面，最多9张</p>
        </div>

        <input v-model="title" type="text" placeholder="添加标题，让大家看到你的分享..."
          class="w-full text-lg font-medium text-gray-900 placeholder-gray-300 dark:placeholder-gray-600 outline-none bg-transparent border-b border-gray-100 dark:border-gray-700 pb-2 focus:border-primary-400 transition-colors" maxlength="100" />

        <RichEditor v-model="content" v-model:content-json="contentJson" placeholder="描述你的图片..." class="min-h-[150px]" />

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

        <div class="flex items-center justify-between py-2">
          <div class="flex-1">
            <span class="text-sm font-medium text-gray-700"><i class="ri-map-pin-line"></i> 显示城市</span>
            <p class="text-[11px] text-gray-400 ">{{ showCity && geo.city.value ? geo.city.value : '不显示城市' }}</p>
          </div>
          <div class="flex items-center gap-2">
            <label class="relative inline-flex items-center cursor-pointer">
              <input v-model="showCity" type="checkbox" class="sr-only peer">
              <div class="w-10 h-5 rounded-full bg-gray-200 peer-focus:outline-none peer peer-checked:bg-primary-500 peer-checked:after:translate-x-full after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all"></div>
            </label>
            <button v-if="showCity" @click="showCityPicker = true" class="text-[11px] text-primary-600 dark:text-primary-400 hover:underline whitespace-nowrap">
              {{ geo.city.value ? '切换' : '选择' }}
            </button>
          </div>
        </div>

        <div class="bg-gray-50  border border-gray-200 dark:border-gray-700 rounded-lg p-3 flex items-start gap-2">
          <span class="text-amber-500 text-sm mt-0.5"><i class="ri-error-warning-line"></i></span>
          <p class="text-xs text-gray-500  leading-relaxed">本平台不构成医疗建议，分享内容仅供参考。</p>
        </div>
      </div>
    </main>

    <CityPicker
      v-if="showCityPicker"
      @select="(city: any) => { geo.setManualCity(city.name); showCityPicker = false }"
      @close="showCityPicker = false"
    />
  </div>
</template>
