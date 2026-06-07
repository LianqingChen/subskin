<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useDrafts } from '@/composables/useDrafts'

export type PostType = 'image' | 'video' | 'text' | 'long'

interface PublishOption {
  type: PostType
  icon: string
  title: string
  description: string
  route: string
}

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'select', type: PostType): void
}>()

const router = useRouter()
const isVisible = ref(false)
const isAnimating = ref(false)
const { draftCount, drafts, loadDraftsWithSync } = useDrafts()

const expiringCount = computed(() => drafts.value.filter(d => d.expiringSoon).length)

const publishOptions: PublishOption[] = [
  {
    type: 'image',
    icon: 'ri-camera-line',
    title: '发图文',
    description: '上传照片或拍摄，配文字说明',
    route: '/community/new?type=image',
  },
  {
    type: 'video',
    icon: 'ri-video-line',
    title: '发视频',
    description: '录制或上传短视频',
    route: '/community/new?type=video',
  },
  {
    type: 'text',
    icon: 'ri-edit-line',
    title: '写文字',
    description: '简短的心情、问答、吐槽',
    route: '/community/new?type=text',
  },
  {
    type: 'long',
    icon: 'ri-file-edit-line',
    title: '写长文',
    description: '治疗记录、经验分享',
    route: '/community/new?type=long',
  },
]

function open() {
  isVisible.value = true
  isAnimating.value = true
  loadDraftsWithSync()
  document.body.style.overflow = 'hidden'
  setTimeout(() => { isAnimating.value = false }, 350)
}

function close() {
  isAnimating.value = true
  isVisible.value = false
  setTimeout(() => {
    isAnimating.value = false
    document.body.style.overflow = ''
    emit('update:modelValue', false)
  }, 300)
}

function handleSelect(option: PublishOption) {
  close()
  emit('select', option.type)
  router.push(option.route)
}

function handleBackdropClick(e: MouseEvent) {
  if (e.target === e.currentTarget) close()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isVisible.value) close()
}

watch(() => props.modelValue, (val) => {
  if (val) open()
})

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <Transition name="backdrop">
      <div
        v-if="isVisible"
        class="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm"
        @click="handleBackdropClick"
      />
    </Transition>

    <!-- Bottom Sheet -->
    <Transition name="sheet">
      <div
        v-if="isVisible"
        class="fixed inset-x-0 bottom-0 z-[61] rounded-t-2xl bg-white shadow-2xl"
        :style="{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }"
      >
        <!-- Drag handle -->
        <div class="flex justify-center pt-3 pb-1">
          <div class="w-10 h-1 rounded-full bg-gray-300 " />
        </div>

        <!-- Header -->
        <div class="px-5 pb-3 pt-1">
          <h3 class="text-base font-semibold text-gray-900">选择发布类型</h3>
        </div>

        <!-- Options -->
        <div class="px-3 pb-3 space-y-1">
          <button
            v-for="option in publishOptions"
            :key="option.type"
            class="w-full flex items-center gap-4 px-4 py-3.5 rounded-xl transition-all duration-150 hover:bg-gray-50 dark:hover:bg-gray-300/60 active:bg-gray-100 dark:active:bg-gray-700 text-left"
            @click="handleSelect(option)"
            :data-track-id="`community_create_${option.type}`"
          >
            <!-- Icon circle -->
            <div class="w-11 h-11 rounded-full flex items-center justify-center text-xl flex-shrink-0"
              :class="{
                'bg-primary-50 dark:bg-primary-900/30': option.type === 'image',
                'bg-rose-50 dark:bg-rose-900/30': option.type === 'video',
                'bg-sky-50 dark:bg-sky-900/30': option.type === 'text',
                'bg-amber-50 dark:bg-amber-900/30': option.type === 'long',
              }"
            >
              <i :class="option.icon"></i>
            </div>
            <!-- Text -->
            <div class="flex-1 min-w-0">
              <div class="text-[15px] font-medium text-gray-900">{{ option.title }}</div>
              <div class="text-xs text-gray-500  mt-0.5">{{ option.description }}</div>
            </div>
            <!-- Arrow -->
            <svg class="w-5 h-5 text-gray-300  flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
            </svg>
          </button>
        </div>

        <!-- My Drafts -->
        <div class="px-3 pb-1">
          <div class="h-px bg-gray-100 my-1"></div>
          <button
            class="w-full flex items-center gap-4 px-4 py-3.5 rounded-xl transition-all duration-150 hover:bg-gray-50 dark:hover:bg-gray-300/60 active:bg-gray-100 dark:active:bg-gray-700 text-left"
            @click="close(); router.push('/community/drafts')"
          >
            <div class="w-11 h-11 rounded-full flex items-center justify-center text-xl flex-shrink-0 bg-gray-100">
              <i class="ri-draft-line"></i>
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-[15px] font-medium text-gray-900">我的草稿</div>
              <div class="text-xs text-gray-500  mt-0.5">
                <template v-if="draftCount > 0">{{ draftCount }}篇未发布<span v-if="expiringCount" class="text-amber-500 dark:text-amber-400 ml-1"><i class="ri-time-line"></i>{{ expiringCount }}篇即将过期</span></template>
                <template v-else>暂无草稿</template>
              </div>
            </div>
            <svg class="w-5 h-5 text-gray-300  flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
            </svg>
          </button>
        </div>

        <!-- Cancel -->
        <div class="px-3 pb-4">
          <button
            class="w-full py-3 text-sm font-medium text-gray-500  hover:text-gray-700 dark:hover:text-gray-200 transition-colors rounded-xl hover:bg-gray-50 dark:hover:bg-gray-300/40 active:bg-gray-100 dark:active:bg-gray-700"
            @click="close"
          >
            取消
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Backdrop transition */
.backdrop-enter-active {
  transition: opacity 0.25s ease-out;
}
.backdrop-leave-active {
  transition: opacity 0.2s ease-in;
}
.backdrop-enter-from,
.backdrop-leave-to {
  opacity: 0;
}

/* Sheet transition - spring-like slide up */
.sheet-enter-active {
  transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.sheet-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.sheet-enter-from,
.sheet-leave-to {
  transform: translateY(100%);
}
</style>
