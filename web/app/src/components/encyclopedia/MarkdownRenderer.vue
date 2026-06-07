<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import MarkdownItAnchor from 'markdown-it-anchor'

const props = defineProps<{
  content: string
}>()

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
})

md.use(MarkdownItAnchor, {
  permalink: true,
  permalinkBefore: true,
  permalinkSymbol: '#',
})

const renderedHtml = computed(() => {
  return md.render(props.content)
})
</script>

<template>
  <div
    class="encyclopedia-content prose prose-gray dark:prose-invert max-w-none
           prose-headings:font-bold prose-headings:text-gray-900 dark:prose-headings:text-gray-100
           prose-h1:text-2xl sm:prose-h1:text-3xl prose-h1:mb-4 prose-h1:mt-8
           prose-h2:text-xl sm:prose-h2:text-2xl prose-h2:mb-3 prose-h2:mt-8
           prose-h3:text-lg prose-h3:mb-2 prose-h3:mt-6
           prose-p:text-gray-700 dark:prose-p:text-gray-300 prose-p:leading-relaxed
           prose-a:text-primary-600 dark:prose-a:text-primary-400 prose-a:no-underline hover:prose-a:underline
           prose-strong:text-gray-900 dark:prose-strong:text-gray-100
           prose-code:text-primary-700 dark:prose-code:text-primary-300 prose-code:bg-primary-50 dark:prose-code:bg-primary-900/30 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded
           prose-pre:bg-gray-900 dark:prose-pre:bg-gray-800 prose-pre:text-gray-100
           prose-blockquote:border-l-primary-500 prose-blockquote:bg-primary-50/50 dark:prose-blockquote:bg-primary-900/10
           prose-img:rounded-xl prose-img:shadow-md
           prose-table:border-collapse prose-th:bg-gray-50 dark:prose-th:bg-gray-800
           prose-li:text-gray-700 dark:prose-li:text-gray-300"
    v-html="renderedHtml"
  />
</template>

<style scoped>
.encyclopedia-content :deep(.vp-code) {
  @apply text-primary-700 dark:text-primary-300 bg-primary-50 px-1.5 py-0.5 rounded;
}
@media (dark) {
  .encyclopedia-content :deep(.vp-code) {
    background-color: color-mix(in srgb, var(--color-primary-900) 30%, transparent);
  }
}
.dark .encyclopedia-content :deep(.vp-code) {
  background-color: color-mix(in srgb, var(--color-primary-900) 30%, transparent);
}

.encyclopedia-content :deep(.custom-block) {
  @apply rounded-lg p-4 mb-4 border-l-4;
}

.encyclopedia-content :deep(.custom-block.info) {
  @apply bg-blue-50 dark:bg-blue-900/20 border-blue-500 text-blue-900 dark:text-blue-100;
}

.encyclopedia-content :deep(.custom-block.warning) {
  @apply bg-yellow-50 dark:bg-yellow-900/20 border-yellow-500 text-yellow-900 dark:text-yellow-100;
}

.encyclopedia-content :deep(.custom-block.danger) {
  @apply bg-red-50 dark:bg-red-900/20 border-red-500 text-red-900 dark:text-red-100;
}

.encyclopedia-content :deep(.custom-block-tip) {
  @apply bg-green-50 dark:bg-green-900/20 border-green-500 text-green-900 dark:text-green-100;
}
</style>
