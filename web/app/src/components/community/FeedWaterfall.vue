<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Post } from '@/types'
import ImagePostCard from '@/components/community/PostCard/ImagePostCard.vue'
import TextPostCard from '@/components/community/PostCard/TextPostCard.vue'
import LongPostCard from '@/components/community/PostCard/LongPostCard.vue'

/**
 * 瀑布流：按列分配（放进当前最矮的一列），不用 CSS columns。
 * 已分配的卡片位置固定，无限加载只给新卡片找列，已有卡片不跳动；
 * 列数按容器实际宽度计算（桌面端已扣除侧边栏）。
 */
const props = defineProps<{
  posts: Post[]
}>()

const emit = defineEmits<{
  (e: 'like-click', postId: number): void
  (e: 'follow-change', followed: boolean, userId: number): void
}>()

function getPostType(post: Post): string {
  if (post.post_type) return post.post_type
  if (post.video_url) return 'video'
  if (post.images && post.images.length > 0) return 'image'
  const textLen = (post.content_preview || post.content.replace(/<[^>]+>/g, '')).length
  if (textLen > 200) return 'long'
  return 'text'
}

function onLikeClick(postId: number) {
  emit('like-click', postId)
}

function onFollowChange(followed: boolean, userId: number) {
  emit('follow-change', followed, userId)
}

const rootEl = ref<HTMLElement | null>(null)
const columnEls: HTMLElement[] = []
function setColumnEl(el: unknown, index: number) {
  if (el instanceof HTMLElement) columnEls[index] = el
}
const columnCount = ref(2)
/** 每列的帖子 id，渲染时再映射回最新的 post 对象（点赞等状态变化无需重排） */
const columns = ref<number[][]>([[], []])
let placedIds: number[] = []

/** 按容器宽度定列数：手机 2 列，平板/小桌面 3 列，常规桌面 4 列，大屏 5 列 */
function columnsForWidth(width: number): number {
  if (width < 680) return 2
  if (width < 960) return 3
  if (width < 1240) return 4
  return 5
}

/** 估算卡片相对高度（以列宽为 1），仅用于同一轮内尚未渲染的卡片 */
function estimateHeight(post: Post): number {
  const type = getPostType(post)
  if (type === 'image' || type === 'video') return 4 / 3 + 0.42
  if (type === 'long') return 0.95
  return 0.6
}

const columnPosts = computed(() => {
  const map = new Map(props.posts.map((p) => [p.id, p]))
  return columns.value.map((col) => col.map((id) => map.get(id)).filter((p): p is Post => !!p))
})

function distribute(reset: boolean) {
  const count = columnCount.value
  if (reset) {
    columns.value = Array.from({ length: count }, () => [])
    placedIds = []
  }
  const pending = props.posts.slice(placedIds.length)
  if (!pending.length) return
  const colWidth = columnEls[0]?.offsetWidth || 1
  // 已渲染的列用真实高度，还没渲染的估算
  const heights = Array.from({ length: count }, (_, i) => (reset ? 0 : (columnEls[i]?.offsetHeight ?? 0) / colWidth))
  const next = columns.value.map((col) => col.slice())
  for (const post of pending) {
    let target = 0
    for (let i = 1; i < count; i++) if (heights[i] < heights[target] - 0.01) target = i
    next[target].push(post.id)
    heights[target] += estimateHeight(post)
    placedIds.push(post.id)
  }
  columns.value = next
}

/** 新列表是否只是在旧列表末尾追加（否则整体重排：切换 Tab、筛选、截断等） */
function isAppend(list: Post[]): boolean {
  if (list.length < placedIds.length) return false
  for (let i = 0; i < placedIds.length; i++) if (list[i].id !== placedIds[i]) return false
  return true
}

watch(() => props.posts.map((p) => p.id), async () => {
  const append = isAppend(props.posts)
  if (append) await nextTick()
  distribute(!append)
}, { immediate: true })

let observer: ResizeObserver | null = null
function updateColumnCount() {
  const width = rootEl.value?.clientWidth ?? 0
  if (!width) return
  const count = columnsForWidth(width)
  if (count !== columnCount.value) {
    columnCount.value = count
    distribute(true)
  }
}

onMounted(() => {
  updateColumnCount()
  if (typeof ResizeObserver !== 'undefined' && rootEl.value) {
    observer = new ResizeObserver(updateColumnCount)
    observer.observe(rootEl.value)
  } else {
    window.addEventListener('resize', updateColumnCount)
  }
})

onBeforeUnmount(() => {
  observer?.disconnect()
  window.removeEventListener('resize', updateColumnCount)
})
</script>

<template>
  <div ref="rootEl" class="flex items-start gap-3 lg:gap-4 min-w-0">
    <div v-for="(col, ci) in columnPosts" :key="ci" :ref="(el) => setColumnEl(el, ci)" class="flex min-w-0 flex-1 flex-col gap-3 lg:gap-4">
      <template v-for="post in col" :key="post.id">
        <ImagePostCard v-if="getPostType(post) === 'image' || getPostType(post) === 'video'" :post="post" @like-click="onLikeClick" @follow-change="onFollowChange" />
        <TextPostCard v-else-if="getPostType(post) === 'text'" :post="post" @like-click="onLikeClick" @follow-change="onFollowChange" />
        <LongPostCard v-else :post="post" @like-click="onLikeClick" @follow-change="onFollowChange" />
      </template>
    </div>
  </div>
</template>
