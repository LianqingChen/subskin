<script setup lang="ts">
import { ref } from 'vue'
import { submitRevision } from '@/api/encyclopedia'
import { useToast } from '@/composables/useToast'

const props = defineProps<{
  article: {
    id: number
    slug: string
    title: string
    content: string
  }
}>()

const emit = defineEmits<{
  submitted: []
  cancel: []
}>()

const toast = useToast()
const submitting = ref(false)
const formData = ref({
  title: props.article.title,
  content: props.article.content,
  change_summary: '',
})

async function handleSubmit() {
  if (!formData.value.change_summary.trim()) {
    toast.error('请填写修订说明')
    return
  }
  if (formData.value.content.length < 10) {
    toast.error('内容太短')
    return
  }

  submitting.value = true
  try {
    await submitRevision(props.article.slug, {
      title: formData.value.title,
      content: formData.value.content,
      change_summary: formData.value.change_summary,
    })
    emit('submitted')
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="bg-white rounded-xl border border-gray-200 dark:border-gray-700 p-6">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-gray-900"><i class="ri-edit-line mr-1"></i>提交修订建议</h3>
      <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" @click="emit('cancel')">
        <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>

    <div class="space-y-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">修订说明 *</label>
        <input
          v-model="formData.change_summary"
          type="text"
          class="input-field"
          placeholder="请简要说明您修改了哪些内容..."
          maxlength="500"
        />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">文章标题</label>
        <input
          v-model="formData.title"
          type="text"
          class="input-field"
          placeholder="文章标题"
        />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">
          内容 (Markdown) *
          <span class="text-xs text-gray-500 ml-2">{{ formData.content.length }} 字符</span>
        </label>
        <textarea
          v-model="formData.content"
          class="input-field font-mono text-sm"
          rows="12"
          placeholder="请输入修订后的 Markdown 内容..."
        />
        <p class="text-xs text-gray-500  mt-1">
          <i class="ri-lightbulb-line mr-1"></i>支持 Markdown 语法，修订内容将提交给审核员审核
        </p>
      </div>

      <div class="flex gap-3 pt-2">
        <button class="btn-primary" :disabled="submitting" @click="handleSubmit">
          {{ submitting ? '提交中...' : '提交修订' }}
        </button>
        <button class="btn-secondary" @click="emit('cancel')">取消</button>
      </div>
    </div>
  </div>
</template>
