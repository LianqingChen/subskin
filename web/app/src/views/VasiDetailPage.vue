<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { vasiApi } from '@/api/vasi'
import type { VasiAssessmentResponse } from '@/api/vasi'
import { PART_LABELS } from '@/constants/bodySites'
import { useToast } from '@/composables/useToast'
import { usePrivacyStore } from '@/stores/privacy'
import { getScoreInterpretation, getStageDescription } from '@/composables/useVasiAssessment'
import MaskEditor from '@/components/tracker/MaskEditor.vue'
import { toProtectedFileUrl } from '@/utils/file-url'
import { useDrafts } from '@/composables/useDrafts'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const privacyStore = usePrivacyStore()

const assessmentId = computed(() => Number(route.params.id))
const loading = ref(true)
const notFound = ref(false)
const data = ref<VasiAssessmentResponse | null>(null)
const editMode = ref(false)
const isSubmittingContour = ref(false)

async function load() {
  loading.value = true
  notFound.value = false
  try {
    data.value = await vasiApi.getAssessment(assessmentId.value)
  } catch {
    notFound.value = true
  } finally {
    loading.value = false
  }
}

async function handleTwoLayerConfirm(skinMaskDataUrl: string, lesionMaskDataUrl: string) {
  if (!data.value) return
  isSubmittingContour.value = true
  try {
    const result = await vasiApi.submitTwoLayerMask(data.value.id, skinMaskDataUrl, lesionMaskDataUrl)
    if (result.diff_summary.modified) {
      toast.show(
        `图层已记录。AI与手动标注差异距离: ${(result.diff_summary.avg_point_distance ?? 0).toFixed(3)}，将用于提升模型准确率`,
        'info',
        5000,
      )
    } else {
      toast.success('图层确认完成，与 AI 识别结果一致！')
    }
    editMode.value = false
    await load()
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || '图层提交失败')
  } finally {
    isSubmittingContour.value = false
  }
}

const partLabel = computed(() => (data.value ? PART_LABELS[data.value.body_site] || data.value.body_site : ''))
const displayScore = computed(() => (data.value?.final_vasi_score != null ? data.value.final_vasi_score : (data.value?.vasi_score ?? 0)))
const displayArea = computed(() => (data.value?.final_area_percentage != null ? data.value.final_area_percentage : (data.value?.area_percentage ?? 0)))
const isCorrected = computed(() => !!data.value?.is_user_corrected)
const interp = computed(() => (data.value ? getScoreInterpretation(displayScore.value) : null))

const authedImageUrl = computed(() => toProtectedFileUrl(data.value?.image_url))

function formatDate(d: string) {
  return d?.slice(0, 10) || ''
}

const { saveDraftWithSync } = useDrafts()

const isPublishing = ref(false)

async function shareToFeed() {
  if (!data.value || isPublishing.value) return
  isPublishing.value = true

  try {
    const d = data.value
    const today = new Date().toISOString().split('T')[0]

    const htmlContent =
      `<p>VASI评估结果：</p>` +
      `<ul>` +
      `<li>评估部位：${PART_LABELS[d.body_site] || d.body_site}</li>` +
      `<li>VASI评分：${displayScore.value}</li>` +
      `<li>白斑占该部位：${displayArea.value}%</li>` +
      `<li>病情阶段：${d.stage}</li>` +
      `<li>分型：${d.classification || '未分型'}</li>` +
      `</ul>` +
      `<p></p><p>分享感受：</p>`

    const images: string[] = []
    if (d.image_url) images.push(d.image_url)

    const draftKey = await saveDraftWithSync({
      type: 'image',
      title: `${today} 评估分享`,
      content: htmlContent,
      images,
      categoryId: null,
      mood: '',
      isPrivate: true,
    })

    toast.success('已生成草稿')
    await router.push({ path: '/community/new', query: { type: 'image', draftKey } })
  } catch (e) {
    console.error('shareToFeed error:', e)
    toast.error('发布失败，请重试')
  } finally {
    isPublishing.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="min-h-dvh bg-[#F5F7FA] pb-20 md:pb-8">
    <header class="sticky top-0 z-30 bg-[#F5F7FA]/80  backdrop-blur border-b border-gray-200 dark:border-gray-700">
      <div class="max-w-6xl mx-auto flex items-center gap-3 px-4 h-12">
        <button @click="router.back()" class="p-1 -ml-1 text-gray-600 hover:text-gray-900 dark:hover:text-gray-100">
          <i class="ri-arrow-left-s-line text-xl"></i>
        </button>
        <h1 class="text-base font-semibold text-gray-900 truncate flex-1">VASI 评估详情</h1>
        <button
          v-if="data"
          class="text-[11px] px-2.5 py-1 rounded-md bg-primary-500 text-white hover:bg-primary-600 transition-colors whitespace-nowrap"
          :disabled="isPublishing"
          @click="shareToFeed"
        >
          <i class="ri-send-plane-line text-[10px] mr-0.5"></i>发布
        </button>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-4">
      <div v-if="loading" class="text-center py-16 text-gray-400 ">
        <div class="text-4xl mb-3 animate-pulse"><i class="ri-microscope-line"></i></div>
        <p>加载中...</p>
      </div>

      <div v-else-if="notFound || !data" class="text-center py-16 text-gray-400 ">
        <div class="text-4xl mb-3"><i class="ri-file-damage-line"></i></div>
        <p>评估记录不存在或已被删除</p>
        <button @click="router.push('/tracker')" class="mt-4 text-sm text-primary-500 hover:underline">返回小白追踪</button>
      </div>

      <template v-else>
        <!-- Mobile: results first, photo below. Desktop: side by side -->
        <div class="flex flex-col lg:flex-row gap-6 lg:items-start">
          <!-- Assessment Results (appears FIRST on mobile via order-1, second on desktop via lg:order-2) -->
          <div class="w-full lg:w-1/2 flex flex-col gap-4 order-1 lg:order-2">
            <div
              class="card p-4 border-l-4"
              :class="{
                'border-green-500': displayScore < 10,
                'border-amber-500': displayScore >= 10 && displayScore < 25,
                'border-orange-500': displayScore >= 25 && displayScore < 50,
                'border-red-500': displayScore >= 50,
              }"
            >
              <div class="flex items-center justify-between mb-3">
                <h3 class="text-base font-semibold text-gray-900">
                  <i class="ri-clipboard-line"></i> 评估结果
                </h3>
                <span
                  v-if="isCorrected"
                  class="text-[10px] px-2 py-0.5 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300"
                  title="已基于您修正的轮廓重新计算"
                ><i class="ri-edit-2-line mr-0.5"></i>已校准</span>
              </div>
              <div class="grid grid-cols-2 gap-2">
                <div class="bg-gray-50 rounded-lg p-3 text-center">
                  <div class="text-xl font-bold" :class="interp?.color">
                    {{ privacyStore.privacyMode ? displayScore : '**' }}
                  </div>
                  <div class="text-xs text-gray-500 ">VASI 评分</div>
                  <div v-if="isCorrected" class="text-[10px] text-gray-400 mt-0.5">
                    AI 初判: {{ privacyStore.privacyMode ? data.vasi_score : '**' }}
                  </div>
                </div>
                <div class="bg-gray-50 rounded-lg p-3 text-center">
                  <div class="text-xl font-bold" :class="interp?.color">{{ interp?.level }}</div>
                  <div class="text-xs text-gray-500 ">严重程度</div>
                </div>
                <div class="bg-gray-50 rounded-lg p-3 text-center">
                  <div class="text-xl font-bold text-gray-700">
                    {{ privacyStore.privacyMode ? displayArea + '%' : '**%' }}
                  </div>
                  <div class="text-xs text-gray-500 " title="白斑面积 ÷ 该部位皮肤区域面积">白斑占该部位</div>
                  <div v-if="isCorrected" class="text-[10px] text-gray-400 mt-0.5">
                    AI 初判: {{ privacyStore.privacyMode ? data.area_percentage + '%' : '**%' }}
                  </div>
                </div>
                <div class="bg-gray-50 rounded-lg p-3 text-center">
                  <div
                    class="text-xl font-bold"
                    :class="data.stage === '好转' ? 'text-green-600' : (data.stage === '扩散' || data.stage === '进展期') ? 'text-red-600' : 'text-amber-600'"
                  >{{ data.stage }}</div>
                  <div class="text-xs text-gray-500 ">病情阶段</div>
                </div>
              </div>
              <div v-if="data.classification" class="mt-3 text-sm text-gray-600">
                <i class="ri-price-tag-3-line mr-1 text-primary-500"></i>
                <span class="font-medium">分型：</span>{{ data.classification }}白癜风
                <span class="text-[10px] text-gray-400  ml-1">（仅供参考）</span>
              </div>
            </div>

            <div v-if="interp" class="card p-4 space-y-3">
              <div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
                <h4 class="text-sm font-medium text-blue-700 dark:text-blue-300 mb-1">
                  <i class="ri-microscope-line"></i> 评分含义
                </h4>
                <p class="text-sm text-blue-600 dark:text-blue-400 leading-relaxed">{{ interp.description }}</p>
              </div>
              <div class="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
                <h4 class="text-sm font-medium text-purple-700 dark:text-purple-300 mb-1">
                  <i class="ri-bar-chart-2-line"></i> 阶段说明
                </h4>
                <p class="text-sm text-purple-600 dark:text-purple-400 leading-relaxed">{{ getStageDescription(data.stage) }}</p>
              </div>
            </div>

            <p class="text-xs text-gray-400  text-center">
              <i class="ri-error-warning-line"></i> 以上解读仅供参考，不构成医疗诊断建议
            </p>
          </div>

          <!-- Photo Section (appears SECOND on mobile via order-2, first on desktop via lg:order-1) -->
          <div class="w-full lg:w-1/2 flex flex-col gap-4 order-2 lg:order-1">
            <div class="card p-4">
              <div class="flex items-center justify-between">
                <div>
                  <h2 class="font-semibold text-gray-900">{{ partLabel }}测评</h2>
                  <p class="text-xs text-gray-400  mt-0.5">{{ formatDate(data.assessment_date) }}</p>
                </div>
                <button
                  v-if="!editMode && authedImageUrl"
                  class="text-xs px-3 py-1.5 rounded-lg border border-primary-300 dark:border-primary-600 text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-colors"
                  @click="editMode = true"
                >
                  <i class="ri-edit-line mr-1"></i>修正图层
                </button>
                <span
                  v-if="editMode"
                  class="text-xs text-gray-400 "
                >编辑模式</span>
              </div>
            </div>

            <div class="card p-3">
               <MaskEditor
                 v-if="editMode && authedImageUrl"
                 :image-url="authedImageUrl"
                 :initial-skin-layer-url="data.skin_layer_data_url ?? null"
                 :initial-lesion-layer-url="data.lesion_layer_data_url ?? null"
                 :editable="true"
                 @confirm="(p) => handleTwoLayerConfirm(p.skinMaskDataUrl, p.lesionMaskDataUrl)"
                 @cancel="editMode = false"
               />
               <div v-else-if="authedImageUrl" class="relative">
                 <img
                   :src="authedImageUrl"
                   alt="评估照片"
                   class="w-full rounded-xl"
                   :class="{ 'blur-lg': !privacyStore.privacyMode }"
                 />
                 <p v-if="!data.contours?.length && !data.skin_layer_data_url" class="text-xs text-gray-400  mt-2 text-center">
                   本次评估未生成轮廓数据
                 </p>
               </div>
               <div v-else class="aspect-square flex items-center justify-center text-gray-300 ">
                 <i class="ri-image-line text-5xl"></i>
               </div>
               <div v-if="editMode && isSubmittingContour" class="mt-3 flex items-center gap-2 text-sm text-primary-500">
                 <i class="ri-loader-4-line animate-spin"></i> 提交中...
               </div>
               <div v-if="editMode && !isSubmittingContour" class="mt-3 flex items-center justify-end gap-2">
                 <button
                   class="text-xs px-3 py-1.5 rounded-lg text-gray-500  hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
                   @click="editMode = false"
                 >取消</button>
               </div>
             </div>
          </div>
        </div>
      </template>
    </main>
  </div>
</template>
