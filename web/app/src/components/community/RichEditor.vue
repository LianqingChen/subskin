<template>
  <div class="border border-gray-200 dark:border-gray-600 rounded-lg overflow-hidden flex flex-col bg-white">
    <!-- Toolbar -->
    <div v-if="editor" class="bg-gray-50 border-b border-gray-200 dark:border-gray-600 p-2 flex flex-wrap items-center gap-1 sticky top-0 z-10">
      <!-- Text Formatting -->
      <div class="flex items-center gap-1">
        <button
          type="button"
          @click="editor.chain().focus().toggleBold().run()"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('bold') }
          ]"
          title="加粗"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 12a4 4 0 0 0 0-8H6v8"/><path d="M15 20a4 4 0 0 0 0-8H6v8Z"/></svg>
        </button>
        <button
          type="button"
          @click="editor.chain().focus().toggleItalic().run()"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('italic') }
          ]"
          title="斜体"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="4" x2="10" y2="4"/><line x1="14" y1="20" x2="5" y2="20"/><line x1="15" y1="4" x2="9" y2="20"/></svg>
        </button>
        <button
          type="button"
          @click="editor.chain().focus().toggleUnderline().run()"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('underline') }
          ]"
          title="下划线"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4v6a6 6 0 0 0 12 0V4"/><line x1="4" y1="20" x2="20" y2="20"/></svg>
        </button>
        <button
          type="button"
          @click="editor.chain().focus().toggleStrike().run()"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('strike') }
          ]"
          title="删除线"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4H9a3 3 0 0 0-2.83 4"/><path d="M14 12a4 4 0 0 1 0 8H6"/><line x1="4" y1="12" x2="20" y2="12"/></svg>
        </button>
      </div>

      <div class="w-px h-5 bg-gray-300  mx-1"></div>

      <!-- Headings -->
      <div class="flex items-center gap-1">
        <button
          type="button"
          @click="editor.chain().focus().toggleHeading({ level: 1 }).run()"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors font-bold text-xs',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('heading', { level: 1 }) }
          ]"
          title="标题 1"
        >
          H1
        </button>
        <button
          type="button"
          @click="editor.chain().focus().toggleHeading({ level: 2 }).run()"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors font-bold text-xs',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('heading', { level: 2 }) }
          ]"
          title="标题 2"
        >
          H2
        </button>
        <button
          type="button"
          @click="editor.chain().focus().toggleHeading({ level: 3 }).run()"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors font-bold text-xs',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('heading', { level: 3 }) }
          ]"
          title="标题 3"
        >
          H3
        </button>
      </div>

      <div class="w-px h-5 bg-gray-300  mx-1"></div>

      <!-- Lists -->
      <div class="flex items-center gap-1">
        <button
          type="button"
          @click="editor.chain().focus().toggleBulletList().run()"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('bulletList') }
          ]"
          title="无序列表"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
        </button>
        <button
          type="button"
          @click="editor.chain().focus().toggleOrderedList().run()"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('orderedList') }
          ]"
          title="有序列表"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="10" y1="6" x2="21" y2="6"/><line x1="10" y1="12" x2="21" y2="12"/><line x1="10" y1="18" x2="21" y2="18"/><path d="M4 6h1v4"/><path d="M4 10h2"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/></svg>
        </button>
      </div>

      <div class="w-px h-5 bg-gray-300  mx-1"></div>

      <!-- Blocks -->
      <div class="flex items-center gap-1">
        <button
          type="button"
          @click="editor.chain().focus().toggleBlockquote().run()"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('blockquote') }
          ]"
          title="引用"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/></svg>
        </button>
        <button
          type="button"
          @click="editor.chain().focus().setHorizontalRule().run()"
          class="p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          title="分割线"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
      </div>

      <div class="w-px h-5 bg-gray-300  mx-1"></div>

      <!-- Media & Links -->
      <div class="flex items-center gap-1">
        <button
          type="button"
          @click="setLink"
          :class="[
            'p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors',
            { 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300 hover:bg-primary-200 dark:hover:bg-primary-800': editor.isActive('link') }
          ]"
          title="插入链接"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
        </button>
        
        <!-- Image upload -->
        <div class="relative">
          <input 
            type="file" 
            ref="imageInput" 
            class="hidden" 
            accept="image/*" 
            @change="handleImageUpload" 
          />
          <button
            type="button"
            @click="($refs.imageInput as HTMLInputElement).click()"
            class="p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            :disabled="uploadingType === 'image'"
            title="插入图片"
          >
            <svg v-if="uploadingType !== 'image'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            <svg v-else class="animate-spin w-4 h-4 text-primary-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          </button>
        </div>

        <!-- Audio upload -->
        <div class="relative">
          <input
            type="file"
            ref="audioInput"
            class="hidden"
            accept="audio/*"
            @change="handleAudioUpload"
          />
          <button
            type="button"
            @click="($refs.audioInput as HTMLInputElement).click()"
            class="p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            :disabled="uploadingType === 'audio'"
            title="插入音频"
          >
            <svg v-if="uploadingType !== 'audio'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
            <svg v-else class="animate-spin w-4 h-4 text-primary-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          </button>
        </div>

        <!-- Video upload -->
        <div class="relative">
          <input
            type="file"
            ref="videoInput"
            class="hidden"
            accept="video/*"
            @change="handleVideoUpload"
          />
          <button
            type="button"
            @click="($refs.videoInput as HTMLInputElement).click()"
            class="p-1.5 rounded text-gray-600  hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            :disabled="uploadingType === 'video'"
            title="插入视频"
          >
            <svg v-if="uploadingType !== 'video'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
            <svg v-else class="animate-spin w-4 h-4 text-primary-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Editor Content -->
    <editor-content :editor="editor" class="p-4 min-h-[200px] prose prose-sm dark:prose-invert max-w-none focus:outline-none flex-1" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import { Node, mergeAttributes } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import Underline from '@tiptap/extension-underline'
import { useToast } from '@/composables/useToast'
import { communityApi } from '@/api/community'

// ── Custom Tiptap Node: Audio ──
const Audio = Node.create({
  name: 'audio',
  group: 'block',
  atom: true,
  addAttributes() {
    return {
      src: { default: null },
      duration: { default: 0 },
    }
  },
  parseHTML() {
    return [{ tag: 'div[data-audio]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return [
      'div',
      mergeAttributes({ 'data-audio': '', class: 'rich-editor-audio' }),
      [
        'audio',
        {
          src: HTMLAttributes.src,
          controls: '',
          preload: 'metadata',
          class: 'w-full rounded-lg',
        },
      ],
    ]
  },
})

// ── Custom Tiptap Node: Video ──
const Video = Node.create({
  name: 'video',
  group: 'block',
  atom: true,
  addAttributes() {
    return {
      src: { default: null },
    }
  },
  parseHTML() {
    return [{ tag: 'div[data-video]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return [
      'div',
      mergeAttributes({ 'data-video': '', class: 'rich-editor-video' }),
      [
        'video',
        {
          src: HTMLAttributes.src,
          controls: '',
          preload: 'metadata',
          playsinline: '',
          class: 'w-full rounded-lg',
        },
      ],
    ]
  },
})

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: '分享你的经历和建议...'
  }
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'update:contentJson', value: string): void
}>()

const toast = useToast()
const imageInput = ref<HTMLInputElement | null>(null)
const audioInput = ref<HTMLInputElement | null>(null)
const videoInput = ref<HTMLInputElement | null>(null)
const uploadingType = ref<'image' | 'audio' | 'video' | null>(null)

const editor = useEditor({
  content: props.modelValue,
  extensions: [
    StarterKit,
    Underline,
    Image.configure({
      inline: true,
      allowBase64: true,
    }),
    Link.configure({
      openOnClick: false,
      HTMLAttributes: {
        class: 'text-primary-600 underline hover:text-primary-800',
      },
    }),
    Placeholder.configure({
      placeholder: props.placeholder,
      emptyEditorClass: 'is-editor-empty',
    }),
    Audio,
    Video,
  ],
  editorProps: {
    attributes: {
      class: 'focus:outline-none min-h-[200px] text-sm',
    },
  },
  onUpdate: ({ editor }) => {
    emit('update:modelValue', editor.getHTML())
    emit('update:contentJson', JSON.stringify(editor.getJSON()))
  },
})

watch(() => props.modelValue, (value) => {
  if (!editor.value) return
  const isSame = editor.value.getHTML() === value
  if (isSame) {
    return
  }
  editor.value.commands.setContent(value, { emitUpdate: false })
})

onBeforeUnmount(() => {
  if (editor.value) {
    editor.value.destroy()
  }
})

defineExpose({
  getJSON: () => editor.value?.getJSON(),
  getHTML: () => editor.value?.getHTML(),
})

const setLink = () => {
  if (!editor.value) return
  const previousUrl = editor.value.getAttributes('link').href
  const url = window.prompt('URL', previousUrl)

  if (url === null) return

  if (url === '') {
    editor.value.chain().focus().extendMarkRange('link').unsetLink().run()
    return
  }

  editor.value.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
}

const handleImageUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''

  if (!file.type.startsWith('image/')) {
    toast.error('请上传图片文件')
    return
  }

  if (file.size > 5 * 1024 * 1024) {
    toast.error('图片大小不能超过 5MB')
    return
  }

  uploadingType.value = 'image'

  try {
    const response = await communityApi.uploadImage(file)
    if (response?.image_url && editor.value) {
      editor.value.chain().focus().setImage({ src: response.image_url }).run()
    } else {
      throw new Error('上传失败，未获取到图片地址')
    }
  } catch (error: any) {
    console.error('Image upload error:', error)
    toast.error(error?.message || '图片上传失败，请重试')
  } finally {
    uploadingType.value = null
  }
}

const handleAudioUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''

  if (!file.type.startsWith('audio/')) {
    toast.error('请上传音频文件')
    return
  }

  if (file.size > 20 * 1024 * 1024) {
    toast.error('音频大小不能超过 20MB')
    return
  }

  uploadingType.value = 'audio'

  try {
    const response = await communityApi.uploadAudio(file)
    if (response?.audio_url && editor.value) {
      editor.value.chain().focus().insertContent({
        type: 'audio',
        attrs: { src: response.audio_url, duration: response.duration || 0 },
      }).run()
    } else {
      throw new Error('上传失败，未获取到音频地址')
    }
  } catch (error: any) {
    console.error('Audio upload error:', error)
    toast.error(error?.message || '音频上传失败，请重试')
  } finally {
    uploadingType.value = null
  }
}

const handleVideoUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''

  if (!file.type.startsWith('video/')) {
    toast.error('请上传视频文件')
    return
  }

  if (file.size > 50 * 1024 * 1024) {
    toast.error('视频大小不能超过 50MB')
    return
  }

  uploadingType.value = 'video'

  try {
    const response = await communityApi.uploadFile(file)
    if (response?.file_url && editor.value) {
      editor.value.chain().focus().insertContent({
        type: 'video',
        attrs: { src: response.file_url },
      }).run()
    } else {
      throw new Error('上传失败，未获取到视频地址')
    }
  } catch (error: any) {
    console.error('Video upload error:', error)
    toast.error(error?.message || '视频上传失败，请重试')
  } finally {
    uploadingType.value = null
  }
}
</script>

<style>
/* Placeholder styling */
.tiptap p.is-editor-empty:first-child::before {
  color: #9ca3af;
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}

/* Headings */
.tiptap h1 {
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1.3;
  margin-top: 1.5rem;
  margin-bottom: 0.5rem;
  color: inherit;
}

.tiptap h2 {
  font-size: 1.375rem;
  font-weight: 600;
  line-height: 1.35;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
  color: inherit;
}

.tiptap h3 {
  font-size: 1.125rem;
  font-weight: 600;
  line-height: 1.4;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  color: inherit;
}

/* Paragraphs */
.tiptap p {
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}

/* Lists */
.tiptap ul {
  list-style-type: disc;
  padding-left: 1.5rem;
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}

.tiptap ol {
  list-style-type: decimal;
  padding-left: 1.5rem;
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}

.tiptap li {
  margin-top: 0.25rem;
  margin-bottom: 0.25rem;
}

.tiptap li p {
  margin: 0;
}

/* Blockquote */
.tiptap blockquote {
  border-left: 3px solid #26A69A;
  padding-left: 1rem;
  margin-left: 0;
  margin-right: 0;
  margin-top: 0.75rem;
  margin-bottom: 0.75rem;
  font-style: italic;
  color: #6b7280;
}

.dark .tiptap blockquote {
  color: #9ca3af;
}

/* Code */
.tiptap code {
  background-color: #f3f4f6;
  border-radius: 0.25rem;
  padding: 0.125rem 0.375rem;
  font-size: 0.875em;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.dark .tiptap code {
  background-color: #374151;
}

.tiptap pre {
  background-color: #1f2937;
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  margin-top: 0.75rem;
  margin-bottom: 0.75rem;
  overflow-x: auto;
}

.tiptap pre code {
  background: none;
  padding: 0;
  color: #e5e7eb;
  font-size: 0.875rem;
}

/* Horizontal rule */
.tiptap hr {
  border: none;
  border-top: 2px solid #e5e7eb;
  margin-top: 1rem;
  margin-bottom: 1rem;
}

.dark .tiptap hr {
  border-top-color: #4b5563;
}

/* Bold, Italic, Strike */
.tiptap strong {
  font-weight: 700;
}

.tiptap em {
  font-style: italic;
}

.tiptap s {
  text-decoration: line-through;
}

/* Links */
.tiptap a {
  color: #26A69A;
  text-decoration: underline;
  cursor: pointer;
}

.tiptap a:hover {
  color: #00897B;
}

/* Images */
.tiptap img {
  max-width: 100%;
  height: auto;
  border-radius: 0.5rem;
  margin-top: 1rem;
  margin-bottom: 1rem;
}

.tiptap img.ProseMirror-selectednode {
  outline: 2px solid #26A69A;
}

/* Audio node styling */
.tiptap .rich-editor-audio {
  margin: 1rem 0;
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 0.5rem;
  border: 1px solid #e5e7eb;
}

.dark .tiptap .rich-editor-audio {
  background: #1f2937;
  border-color: #374151;
}

.tiptap .rich-editor-audio audio {
  width: 100%;
  height: 40px;
}

.tiptap .rich-editor-audio.ProseMirror-selectednode {
  outline: 2px solid #26A69A;
  border-radius: 0.5rem;
}

/* Video node styling */
.tiptap .rich-editor-video {
  margin: 1rem 0;
  border-radius: 0.5rem;
  overflow: hidden;
}

.tiptap .rich-editor-video video {
  width: 100%;
  border-radius: 0.5rem;
}

.tiptap .rich-editor-video.ProseMirror-selectednode {
  outline: 2px solid #26A69A;
  border-radius: 0.5rem;
}
</style>