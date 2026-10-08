<script setup lang="ts">
import { confirmPublish } from './publishConfirm'
import { ref, computed, watch, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useDrafts } from '@/composables/useDrafts'
import { useGeolocation } from '@/composables/useGeolocation'
import { communityApi } from '@/api/community'
import { normalizeMoodValue } from '@/utils/mood'
import { vasiApi } from '@/api/vasi'
import type { VasiHistoryItem } from '@/api/vasi'
import type { Category, PostCreateRequest } from '@/types'
import RichEditor from '@/components/community/RichEditor.vue'
import TagSelector from '@/components/community/TagSelector.vue'
import CityPicker from '@/components/community/CityPicker.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const toast = useToast()
const { saveDraftWithSync } = useDrafts()
const geo = useGeolocation()

const isEdit = computed(() => !!route.params.id)
const postId = computed(() => Number(route.params.id) || 0)

const title = ref('')
const content = ref('')
const contentJson = ref('')
const categoryId = ref<number | null>(null)
const isPrivate = ref(false)
const diaryDate = ref(new Date().toISOString().slice(0, 10))  // 记录日期（私密帖，默认今天）
const isAnonymous = ref(false)  // kept for backward compat; always forced to false
const showCity = ref(true)
const showCityPicker = ref(false)
const mood = ref('')
const tags = ref<string[]>([])
const categories = ref<Category[]>([])
const publishing = ref(false)
const claimsWarning = ref<string[]>([])
const draftServerId = ref<number | undefined>(undefined)
const draftKey = ref<string>('')

// ── 结构化治疗分享 ──
const postKind = ref<'normal' | 'treatment'>('normal')
const tMethod = ref('')
const tDuration = ref('')
const tEffectRating = ref(0)
const tCostRange = ref('')
const tSideEffects = ref<string[]>([])
const tVasiIds = ref<number[]>([])
const vasiHistory = ref<VasiHistoryItem[]>([])
const vasiLoading = ref(false)

const DURATION_OPTIONS = ['1个月内', '1-3个月', '3-6个月', '6-12个月', '1年以上']
const COST_OPTIONS = ['500元以下', '500-1000元', '1000-5000元', '5000-1万元', '1万元以上', '不清楚']
const SIDE_EFFECT_OPTIONS = ['无副作用', '红肿', '瘙痒', '色素变化', '皮肤干燥', '起水疱', '恶心不适', '其他']

const isValid = computed(() => title.value.trim().length > 0 && content.value.trim().length > 0 && categoryId.value !== null
  && (postKind.value !== 'treatment' || tMethod.value.trim().length > 0))

const estimatedReadTime = computed(() => {
  const text = content.value.replace(/<[^>]+>/g, '')
  const minutes = Math.max(1, Math.ceil(text.length / 400))
  return minutes
})

const MOOD_OPTIONS = [
  { value: '坚持中', icon: 'ri-boxing-line', label: '坚持中' },
  { value: '低落', icon: 'ri-emotion-sad-line', label: '低落' },
  { value: '好转', icon: 'ri-emotion-happy-line', label: '好转' },
  { value: '疑问', icon: 'ri-question-line', label: '疑问' },
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

const loadVasiHistory = async () => {
  if (vasiHistory.value.length > 0 || vasiLoading.value) return
  vasiLoading.value = true
  try {
    const res = await vasiApi.getHistory(20)
    vasiHistory.value = res.items
  } catch { /* 静默失败，不阻断发帖 */ }
  finally { vasiLoading.value = false }
}

watch(postKind, (kind) => {
  if (kind === 'treatment') loadVasiHistory()
})

const toggleSideEffect = (s: string) => {
  const i = tSideEffects.value.indexOf(s)
  if (i >= 0) { tSideEffects.value.splice(i, 1); return }
  if (tSideEffects.value.length < 5) tSideEffects.value.push(s)
}

const toggleVasi = (id: number) => {
  const i = tVasiIds.value.indexOf(id)
  if (i >= 0) { tVasiIds.value.splice(i, 1); return }
  if (tVasiIds.value.length >= 2) tVasiIds.value.shift()
  tVasiIds.value.push(id)
}

const vasiScoreText = (v: VasiHistoryItem): string => {
  const score = v.final_vasi_score ?? v.vasi_score
  return Number(score).toFixed(1)
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
    mood.value = normalizeMoodValue(post.mood)
    tags.value = post.tags.map(t => t.name)
    const ts = post.treatment_share
    if (ts) {
      postKind.value = 'treatment'
      tMethod.value = ts.method || ''
      tDuration.value = ts.duration || ''
      tEffectRating.value = ts.effect_rating || 0
      tCostRange.value = ts.cost_range || ''
      tSideEffects.value = [...(ts.side_effects || [])]
      tVasiIds.value = [...(ts.vasi_assessment_ids || [])]
      loadVasiHistory()
    }
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
          mood.value = normalizeMoodValue(d.mood)
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
  // 公开发布前隐私确认（含 PII 检测提示）
  const decision = await confirmPublish({ title: title.value, content: content.value })
  if (!decision) return
  publishing.value = true
  try {
    const firstCat = categories.value.find(c => c.name === '治疗分享') || categories.value[0]
    const isTreatment = postKind.value === 'treatment'
    const payload: PostCreateRequest = {
      title: title.value.trim(),
      content: content.value,
      content_json: contentJson.value || undefined,
      category_id: categoryId.value || firstCat?.id || 1,
      post_type: isTreatment ? 'treatment' : 'long',
      tag_names: tags.value,
      confirm_pii: decision.confirmPii,
      public_ack: true,
      is_anonymous: false,
      is_private: isPrivate.value,
      diary_date: isPrivate.value ? diaryDate.value : undefined,
      mood: mood.value || undefined,
      city: showCity.value ? (geo.city.value || undefined) : null,
      latitude: showCity.value ? (geo.lat.value ?? undefined) : undefined,
      longitude: showCity.value ? (geo.lng.value ?? undefined) : undefined,
    }
    if (isTreatment) {
      payload.treatment_share = {
        method: tMethod.value.trim(),
        duration: tDuration.value || undefined,
        effect_rating: tEffectRating.value || undefined,
        cost_range: tCostRange.value || undefined,
        side_effects: tSideEffects.value,
        vasi_assessment_ids: tVasiIds.value,
      }
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
  <div class="flex flex-col pb-4">
    <header class="sticky top-14 z-20 h-12 border-b border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
      <div class="mx-auto flex h-full w-full max-w-2xl items-center justify-between px-4">
      <button @click="goBack" class="text-sm text-gray-600  hover:text-gray-900 dark:hover:text-gray-100">取消</button>
      <span class="text-sm font-medium text-gray-900">{{ postKind === 'treatment' ? '分享治疗经验' : '写长文' }}</span>
      <button @click="handlePublish" class="btn-primary px-5 py-1 rounded-full text-sm font-medium" :disabled="publishing || !isValid">
        {{ publishing ? '发布中...' : (isEdit ? '更新' : '发布') }}
      </button>
      </div>
    </header>

    <main class="flex-1 pb-8">
      <!-- 平板/桌面：正文放进白色卡片，与全站卡片风格一致 -->
      <div class="w-full max-w-2xl mx-auto px-4 py-4 space-y-5 md:mt-5 md:rounded-2xl md:border md:border-gray-200/80 md:bg-white md:p-6 md:dark:border-gray-700 md:dark:bg-gray-900">
        <div class="space-y-2">
          <label class="text-sm font-medium text-gray-700">帖子类型</label>
          <div class="flex gap-2">
            <button @click="postKind = 'normal'" type="button"
              class="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm border transition-all"
              :class="postKind === 'normal' ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300 font-medium shadow-sm' : 'border-gray-200 dark:border-gray-600 text-gray-500 hover:border-gray-300'">
              <i class="ri-file-edit-line"></i> 普通分享
            </button>
            <button @click="postKind = 'treatment'" type="button"
              class="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm border transition-all"
              :class="postKind === 'treatment' ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900 dark:text-blue-300 font-medium shadow-sm' : 'border-gray-200 dark:border-gray-600 text-gray-500 hover:border-gray-300'">
              <i class="ri-capsule-line"></i> 治疗经验
            </button>
          </div>
          <p v-if="postKind === 'treatment'" class="text-[11px] text-gray-400">选择治疗经验后，可按模板填写结构化治疗信息，方便白友参考</p>
        </div>

        <input v-model="title" type="text" placeholder="添加标题，让大家看到你的分享..."
          class="w-full text-lg font-medium text-gray-900 placeholder-gray-300 dark:placeholder-gray-600 outline-none bg-transparent border-b border-gray-100 dark:border-gray-700 pb-2 focus:border-primary-400 transition-colors" maxlength="100" />

        <RichEditor v-model="content" v-model:content-json="contentJson" placeholder="分享你的经历、建议或疑问..." class="min-h-[200px]" />

        <div class="text-xs text-gray-400 ">预估阅读 {{ estimatedReadTime }} 分钟</div>

        <!-- 结构化治疗经验表单 -->
        <div v-if="postKind === 'treatment'" class="rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/20 p-4 space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-blue-700 dark:text-blue-300">
            <i class="ri-capsule-line"></i> 治疗信息模板
          </div>

          <div class="space-y-1.5">
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">治疗方案 <span class="text-red-500">*</span></label>
            <textarea v-model="tMethod" rows="2" maxlength="500"
              placeholder="如：308准分子激光每周两次，联合他克莫司软膏外涂..."
              class="w-full text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 outline-none focus:border-blue-400 resize-none"></textarea>
          </div>

          <div class="space-y-1.5">
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">持续周期</label>
            <div class="flex flex-wrap gap-2">
              <button v-for="d in DURATION_OPTIONS" :key="d" @click="tDuration = tDuration === d ? '' : d" type="button"
                class="px-3 py-1.5 rounded-full text-sm border transition-all"
                :class="tDuration === d ? 'border-blue-500 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 shadow-sm' : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-500 hover:border-gray-300'">
                {{ d }}
              </button>
            </div>
          </div>

          <div class="space-y-1.5">
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">效果自评</label>
            <div class="flex items-center gap-1">
              <button v-for="n in 5" :key="n" @click="tEffectRating = tEffectRating === n ? 0 : n" type="button" class="p-0.5"
                :aria-label="`效果自评${n}星`" :aria-pressed="tEffectRating === n">
                <i class="text-xl transition-colors"
                  :class="n <= tEffectRating ? 'ri-star-fill text-amber-400' : 'ri-star-line text-gray-300 dark:text-gray-600'"></i>
              </button>
              <span v-if="tEffectRating > 0" class="text-xs text-gray-400 ml-1">{{ tEffectRating }}/5</span>
            </div>
          </div>

          <div class="space-y-1.5">
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">费用区间</label>
            <div class="flex flex-wrap gap-2">
              <button v-for="c in COST_OPTIONS" :key="c" @click="tCostRange = tCostRange === c ? '' : c" type="button"
                class="px-3 py-1.5 rounded-full text-sm border transition-all"
                :class="tCostRange === c ? 'border-blue-500 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 shadow-sm' : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-500 hover:border-gray-300'">
                {{ c }}
              </button>
            </div>
          </div>

          <div class="space-y-1.5">
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">副作用（可多选）</label>
            <div class="flex flex-wrap gap-2">
              <button v-for="s in SIDE_EFFECT_OPTIONS" :key="s" @click="toggleSideEffect(s)" type="button"
                class="px-3 py-1.5 rounded-full text-sm border transition-all"
                :class="tSideEffects.includes(s) ? 'border-blue-500 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 shadow-sm' : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-500 hover:border-gray-300'">
                {{ s }}
              </button>
            </div>
          </div>

          <div class="space-y-1.5">
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">关联 VASI 评估（可选，最多2条）</label>
            <p class="text-[11px] text-gray-400">选择治疗前后的 VASI 评估记录，展示分数对比，仅存储记录信息</p>
            <div v-if="vasiLoading" class="text-xs text-gray-400 py-2">加载中...</div>
            <div v-else-if="vasiHistory.length === 0" class="text-xs text-gray-400 bg-white dark:bg-gray-800 border border-dashed border-gray-200 dark:border-gray-600 rounded-lg p-3">
              暂无 VASI 评估记录，可先到「记录」页完成一次评估
            </div>
            <div v-else class="grid grid-cols-2 gap-2">
              <button v-for="v in vasiHistory" :key="v.id" @click="toggleVasi(v.id)" type="button"
                class="text-left px-3 py-2 rounded-lg border transition-all"
                :class="tVasiIds.includes(v.id) ? 'border-blue-500 bg-blue-100 dark:bg-blue-900 shadow-sm' : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 hover:border-gray-300'">
                <div class="text-[11px] text-gray-400">{{ (v.assessment_date || '').slice(0, 10) }} · {{ v.body_site }}</div>
                <div class="text-sm font-medium" :class="tVasiIds.includes(v.id) ? 'text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'">
                  VASI {{ vasiScoreText(v) }}
                  <i v-if="tVasiIds.includes(v.id)" class="ri-checkbox-circle-fill text-blue-500 ml-1"></i>
                </div>
              </button>
            </div>
          </div>
        </div>

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
              <i :class="cat.icon" aria-hidden="true"></i> {{ cat.name }}
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

    <CityPicker
      v-if="showCityPicker"
      @select="(city: any) => { geo.setManualCity(city.name); showCityPicker = false }"
      @close="showCityPicker = false"
    />
  </div>
</template>
