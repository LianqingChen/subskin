<script setup lang="ts">
import { useToast } from '@/composables/useToast'
import { useWechatShare } from '@/composables/useWechatShare'

const props = defineProps<{
  visible: boolean
  post: { id: number; title: string; content: string; [key: string]: unknown }
}>()

const emit = defineEmits<{
  close: []
  'generate-poster': []
}>()

const toast = useToast()
const { isWechat, isReady, setShareData } = useWechatShare()

function closeSheet() {
  emit('close')
}

function shareToWeibo() {
  const url = `${window.location.origin}/community/${props.post.id}`
  const title = props.post.title
  const weiboUrl = `https://service.weibo.com/share/share.php?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}`
  window.open(weiboUrl, '_blank', 'width=800,height=600')
}

async function copyLink() {
  const url = `${window.location.origin}/community/${props.post.id}`
  try {
    await navigator.clipboard.writeText(url)
    toast.success('链接已复制到剪贴板')
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = url
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    toast.success('链接已复制到剪贴板')
  }
}

function shareToWechat() {
  if (isWechat && isReady.value) {
    setShareData({
      title: `${props.post.title} - SubSkin`,
      desc: props.post.content?.slice(0, 100) || props.post.title,
      link: `${window.location.origin}/community/${props.post.id}`,
      imgUrl: `${window.location.origin}/og-image.png`,
    })
    toast.show('请点击右上角「⋯」→「发送给朋友」或「分享到朋友圈」', 'info')
    return
  }
  if (isWechat) {
    toast.show('微信分享初始化中，请稍后重试或点击右上角「⋯」手动分享', 'info')
    return
  }
  if (navigator.share) {
    navigator.share({
      title: `${props.post.title} - SubSkin`,
      text: props.post.content?.slice(0, 100) || props.post.title,
      url: `${window.location.origin}/community/${props.post.id}`,
    }).catch(() => {})
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
      <div v-if="visible" class="fixed inset-0 z-50 flex items-end md:items-center justify-center" @click.self="closeSheet">
        <div class="fixed inset-0 bg-black/50" @click="closeSheet" />
        <div class="relative bg-white w-full md:max-w-md md:rounded-2xl rounded-t-2xl max-h-[80vh] overflow-y-auto z-10">
          <!-- Header -->
          <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h3 class="text-base font-semibold text-gray-900">分享到</h3>
            <button class="text-gray-400 hover:text-gray-600 text-2xl leading-none" @click="closeSheet">&times;</button>
          </div>

          <!-- Share Buttons Grid -->
          <div class="grid grid-cols-4 gap-4 p-5">
            <!-- Poster -->
            <button class="flex flex-col items-center gap-2 group" @click="generatePoster">
              <div class="w-12 h-12 rounded-full bg-blue-500 flex items-center justify-center group-hover:bg-blue-600 transition-colors">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              </div>
              <span class="text-xs text-gray-600 group-hover:text-blue-600">生成海报</span>
            </button>

            <!-- Copy Link -->
            <button class="flex flex-col items-center gap-2 group" @click="copyLink">
              <div class="w-12 h-12 rounded-full bg-gray-500 flex items-center justify-center group-hover:bg-gray-600 transition-colors">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
              </div>
              <span class="text-xs text-gray-600 group-hover:text-gray-700">复制链接</span>
            </button>

            <!-- WeChat -->
            <button class="flex flex-col items-center gap-2 group" @click="shareToWechat">
              <div class="w-12 h-12 rounded-full bg-green-500 flex items-center justify-center group-hover:bg-green-600 transition-colors">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor"><path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.594.594 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.216 0 .163.132.295.295.295a.32.32 0 0 0 .167-.054l1.9-1.106a.594.594 0 0 1 .407-.065c1.925.559 3.553.559 5.476 0a.594.594 0 0 1 .407.065l1.9 1.106a.32.32 0 0 0 .167.054.295.295 0 0 0 .295-.295c0-.075-.03-.146-.048-.216l-.39-1.48a.594.594 0 0 1 .213-.665C15.832 13.733 17 11.742 17 9.53c0-4.055-3.89-7.343-8.309-7.343zM5 8a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm7 0a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/><path d="M22.5 9.5c0-3.31-3.134-6-7-6a8.06 8.06 0 0 0-2.29.332c2.677 1.436 4.49 4.066 4.49 7.168 0 .574-.072 1.132-.2 1.672.194.025.385.038.576.038a.6.6 0 0 1 .41.163l1.236.774a.22.22 0 0 0 .114.037.2.2 0 0 0 .2-.2c0-.05-.02-.1-.033-.148l-.254-.968a.41.41 0 0 1 .147-.458C21.547 11.667 22.5 10.702 22.5 9.5z"/></svg>
              </div>
              <span class="text-xs text-gray-600 group-hover:text-green-600">微信</span>
            </button>

            <!-- Moments -->
            <button class="flex flex-col items-center gap-2 group" @click="shareToMoments">
              <div class="w-12 h-12 rounded-full bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center group-hover:from-green-500 group-hover:to-emerald-700 transition-colors">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><line x1="12" y1="3" x2="12" y2="1"/><line x1="12" y1="23" x2="12" y2="21"/><line x1="3" y1="12" x2="1" y2="12"/><line x1="23" y1="12" x2="21" y2="12"/></svg>
              </div>
              <span class="text-xs text-gray-600 group-hover:text-emerald-600">朋友圈</span>
            </button>

            <!-- Weibo -->
            <button class="flex flex-col items-center gap-2 group" @click="shareToWeibo">
              <div class="w-12 h-12 rounded-full bg-red-500 flex items-center justify-center group-hover:bg-red-600 transition-colors">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor"><path d="M10.098 20.323c-3.977.391-7.414-1.406-7.672-4.02-.259-2.609 2.759-5.047 6.74-5.441 3.979-.394 7.413 1.404 7.671 4.018.259 2.6-2.759 5.049-6.739 5.443zm7.782-10.936c-.391-.117-.656-.195-.453-.703.443-1.106.489-2.062.009-2.745-.913-1.298-3.413-1.229-6.27-.035 0 0-.897.427-.669-.344.441-1.468.374-2.698-.316-3.405-1.586-1.624-5.793.061-9.407 3.758C-1.374 8.447-2.9 12.516-2.9 16.078c0 5.672 7.276 9.122 14.397 9.122 9.344 0 15.565-5.432 15.565-9.736 0-2.601-2.191-4.078-4.082-4.683zM19.69 8.142c1.089-1.229 1.378-2.649.645-3.598-.89-1.152-2.688-1.162-4.014-.18l-.011.007c-.264.19-.313.562-.108.826l.11.136c.191.233.542.276.768.09.911-.567 2.013-.55 2.578.177.39.503.307 1.243-.16 2.068-.143.25-.078.569.165.732l.139.096c.246.168.577.111.748-.13l.002-.003c.136-.19.043-.022-.162.178z"/><circle cx="12" cy="14" r="2"/></svg>
              </div>
              <span class="text-xs text-gray-600 group-hover:text-red-600">微博</span>
            </button>

            <!-- Douyin -->
            <button class="flex flex-col items-center gap-2 group opacity-60" @click="shareToDouyin">
              <div class="w-12 h-12 rounded-full bg-gray-900 flex items-center justify-center">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor"><path d="M16.6 5.82s.51.5 0 0A4.278 4.278 0 0 1 15.54 3h-3.09v12.4a2.592 2.592 0 0 1-2.59 2.5c-1.42 0-2.6-1.16-2.6-2.6 0-1.72 1.66-3.01 3.37-2.48V9.66c-3.37-.47-6.36 2.33-6.36 5.87 0 3.47 2.83 6.14 6.33 6.14 3.53 0 6.38-2.84 6.38-6.38V8.81A7.32 7.32 0 0 0 19.5 10V6.89a4.33 4.33 0 0 1-2.9-1.07z"/></svg>
              </div>
              <span class="text-xs text-gray-400">抖音</span>
            </button>

            <!-- Xiaohongshu -->
            <button class="flex flex-col items-center gap-2 group opacity-60" @click="shareToXiaohongshu">
              <div class="w-12 h-12 rounded-full bg-red-400 flex items-center justify-center">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16v16H4z"/><path d="M9 9h6v6H9z"/><circle cx="12" cy="12" r="2"/></svg>
              </div>
              <span class="text-xs text-gray-400">小红书</span>
            </button>
          </div>

          <!-- Hint -->
          <div class="px-5 pb-5 pt-1">
            <p class="text-xs text-gray-400 text-center">分享内容仅供参考，不构成医疗建议</p>
          </div>

          <!-- Cancel button for mobile -->
          <div class="px-5 pb-6 md:hidden">
            <button class="w-full py-3 text-center text-sm text-gray-500 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors" @click="closeSheet">取消</button>
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