<script setup lang="ts">
import { computed } from 'vue'
import { useToast } from '@/composables/useToast'
import { useWechatShare } from '@/composables/useWechatShare'
import { copyTextToClipboard } from '@/utils/clipboard'
import type { Post } from '@/types'

const props = defineProps<{
  visible: boolean
  title?: string
  description?: string
  url?: string
  post?: Post | null
}>()

const emit = defineEmits<{
  close: []
  'generate-poster': []
  shared: []
}>()

const toast = useToast()
const { isWechat, isReady, setShareData } = useWechatShare()

// When post is provided, derive url/title/description from it
const shareUrl = computed(() => props.post
  ? `${window.location.origin}/community/${props.post.id}`
  : props.url || window.location.href)
const shareTitle = computed(() => props.post ? props.post.title : (props.title || 'SubSkin'))
const shareDesc = computed(() => props.post
  ? (props.post.content?.slice(0, 100) || props.post.title)
  : (props.description || props.title || 'SubSkin'))

function closeSheet() {
  emit('close')
}

function shareToWeibo() {
  const weiboUrl = `https://service.weibo.com/share/share.php?url=${encodeURIComponent(shareUrl.value)}&title=${encodeURIComponent(shareTitle.value)}`
  window.open(weiboUrl, '_blank', 'width=800,height=600')
  emit('shared')
}

async function copyLink() {
  try {
    if (await copyTextToClipboard(shareUrl.value)) {
      toast.success('链接已复制到剪贴板')
      emit('shared')
      return
    }
    throw new Error('copy failed')
  } catch {
    toast.error('复制失败，请手动复制')
  }
}

function shareToWechat() {
  if (isWechat && isReady.value) {
    setShareData({
      title: shareTitle.value,
      desc: shareDesc.value,
      link: shareUrl.value,
      imgUrl: `${window.location.origin}/og-image.png`,
    })
    toast.show('请点击右上角「⋯」→「发送给朋友」或「分享到朋友圈」', 'info')
    emit('shared')
    return
  }
  if (isWechat) {
    toast.show('微信分享初始化中，请稍后重试或点击右上角「⋯」手动分享', 'info')
    return
  }
  if (navigator.share) {
    navigator.share({
      title: shareTitle.value,
      text: shareDesc.value,
      url: shareUrl.value,
    }).then(() => emit('shared')).catch(() => {})
  } else {
    copyLink()
  }
}

function shareToMoments() {
  shareToWechat()
}

function generatePoster() {
  emit('generate-poster')
}

function shareToDouyin() {
  toast.show('请保存海报后分享到抖音', 'info')
}

function shareToXiaohongshu() {
  toast.show('请保存海报后分享到小红书', 'info')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="visible" class="fixed inset-0 z-[70] flex items-end sm:items-center sm:p-4 justify-center" @click.self="closeSheet">
        <div class="fixed inset-0 bg-black/50 backdrop-blur-[2px]" @click="closeSheet" />
        <div class="relative bg-white dark:bg-gray-900 border border-gray-200/80 dark:border-gray-800 w-full sm:max-w-md sm:rounded-2xl rounded-t-2xl max-h-[80vh] overflow-y-auto z-10 pb-[env(safe-area-inset-bottom,0px)] sm:pb-0 shadow-xl" role="dialog" aria-modal="true">
          <!-- Header -->
          <div class="flex items-center justify-between px-5 py-3.5 border-b border-gray-200/80 dark:border-gray-800">
            <h3 class="text-base font-semibold tracking-tight text-gray-900 dark:text-gray-100">分享到</h3>
            <button type="button" class="w-9 h-9 -mr-1.5 flex items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200 transition-colors" aria-label="关闭分享面板" @click="closeSheet">
              <i class="ri-close-line text-xl" aria-hidden="true"></i>
            </button>
          </div>

          <!-- Share Buttons Grid -->
          <div class="grid grid-cols-4 gap-4 p-5">
            <!-- Poster -->
            <button type="button" class="flex flex-col items-center gap-2 group" @click="generatePoster">
              <div class="w-12 h-12 rounded-2xl bg-primary-600 text-white flex items-center justify-center group-hover:bg-primary-700 transition-colors shadow-xs">
                <i class="ri-image-add-line text-2xl" aria-hidden="true"></i>
              </div>
              <span class="text-xs font-medium text-gray-600 dark:text-gray-300 group-hover:text-primary-600 dark:group-hover:text-primary-400">生成海报</span>
            </button>

            <!-- Copy Link -->
            <button type="button" class="flex flex-col items-center gap-2 group" @click="copyLink">
              <div class="w-12 h-12 rounded-2xl bg-slate-600 text-white flex items-center justify-center group-hover:bg-slate-700 transition-colors shadow-xs">
                <i class="ri-link text-2xl" aria-hidden="true"></i>
              </div>
              <span class="text-xs font-medium text-gray-600 dark:text-gray-300 group-hover:text-gray-800 dark:group-hover:text-gray-100">复制链接</span>
            </button>

            <!-- WeChat -->
            <button type="button" class="flex flex-col items-center gap-2 group" @click="shareToWechat">
              <div class="w-12 h-12 rounded-2xl bg-emerald-500 text-white flex items-center justify-center group-hover:bg-emerald-600 transition-colors shadow-xs">
                <i class="ri-wechat-fill text-2xl" aria-hidden="true"></i>
              </div>
              <span class="text-xs font-medium text-gray-600 dark:text-gray-300 group-hover:text-emerald-600">微信</span>
            </button>

            <!-- Moments -->
            <button type="button" class="flex flex-col items-center gap-2 group" @click="shareToMoments">
              <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-600 text-white flex items-center justify-center group-hover:from-emerald-500 group-hover:to-teal-700 transition-colors shadow-xs">
                <i class="ri-compass-3-line text-2xl" aria-hidden="true"></i>
              </div>
              <span class="text-xs font-medium text-gray-600 dark:text-gray-300 group-hover:text-teal-600">朋友圈</span>
            </button>

            <!-- Weibo -->
            <button type="button" class="flex flex-col items-center gap-2 group" @click="shareToWeibo">
              <div class="w-12 h-12 rounded-2xl bg-rose-500 text-white flex items-center justify-center group-hover:bg-rose-600 transition-colors shadow-xs">
                <i class="ri-weibo-fill text-2xl" aria-hidden="true"></i>
              </div>
              <span class="text-xs font-medium text-gray-600 dark:text-gray-300 group-hover:text-rose-600">微博</span>
            </button>

            <!-- Douyin -->
            <button type="button" class="flex flex-col items-center gap-2 group opacity-70 hover:opacity-100 transition-opacity" @click="shareToDouyin">
              <div class="w-12 h-12 rounded-2xl bg-slate-900 dark:bg-slate-800 text-white flex items-center justify-center shadow-xs">
                <i class="ri-tiktok-fill text-2xl" aria-hidden="true"></i>
              </div>
              <span class="text-xs text-gray-500 dark:text-gray-400">抖音</span>
            </button>

            <!-- Xiaohongshu -->
            <button type="button" class="flex flex-col items-center gap-2 group opacity-70 hover:opacity-100 transition-opacity" @click="shareToXiaohongshu">
              <div class="w-12 h-12 rounded-2xl bg-red-500 text-white flex items-center justify-center shadow-xs">
                <i class="ri-book-mark-line text-2xl" aria-hidden="true"></i>
              </div>
              <span class="text-xs text-gray-500 dark:text-gray-400">小红书</span>
            </button>
          </div>

          <!-- Hint -->
          <div class="px-5 pb-4 pt-1">
            <p class="text-xs text-gray-400 dark:text-gray-500 text-center">分享内容仅供参考，不构成医疗建议</p>
          </div>

          <!-- Cancel button for mobile -->
          <div class="px-5 pb-5 md:hidden">
            <button type="button" class="w-full py-2.5 text-center text-sm font-medium text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded-xl hover:bg-gray-200/70 dark:hover:bg-gray-700 transition-colors" @click="closeSheet">取消</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
