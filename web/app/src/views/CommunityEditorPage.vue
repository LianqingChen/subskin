<template>
  <TextEditor v-if="postType === 'text'" />
  <ImagePostEditor v-else-if="postType === 'image'" />
  <VideoPostEditor v-else-if="postType === 'video'" />
  <LongPostEditor v-else />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { communityApi } from '@/api/community'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import TextEditor from '@/components/community/Editor/TextEditor.vue'
import LongPostEditor from '@/components/community/Editor/LongPostEditor.vue'
import ImagePostEditor from '@/components/community/Editor/ImagePostEditor.vue'
import VideoPostEditor from '@/components/community/Editor/VideoPostEditor.vue'

const route = useRoute()
// 编辑器草稿 2s 防抖自动保存，整页刷新可能丢掉最后几秒的输入
useUnsavedGuard(() => true)
const editPostType = ref<string | null>(null)

const postType = computed(() => {
  if (editPostType.value) return editPostType.value
  return (route.query.type as string) || 'long'
})

watch(() => route.params.id, async (newId) => {
  if (newId) {
    try {
      await communityApi.getPost(Number(newId))
      editPostType.value = 'image'
    } catch {
      editPostType.value = null
    }
  } else {
    editPostType.value = null
  }
}, { immediate: true })
</script>
