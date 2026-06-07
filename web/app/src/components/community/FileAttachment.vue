<template>
  <div v-if="attachments && attachments.length > 0" class="space-y-2">
    <a
      v-for="attachment in sortedAttachments"
      :key="attachment.id"
      :href="fileHref(attachment.file_url)"
      target="_blank"
      rel="noopener noreferrer"
      class="flex items-center gap-3 px-4 py-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer no-underline"
      :title="attachment.file_name"
    >
      <!-- Icon -->
      <div class="flex-shrink-0">
        <!-- Document Icon -->
        <svg v-if="isDocument(attachment.file_type)" class="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
        </svg>
        <!-- Image Icon -->
        <svg v-else-if="isImage(attachment.file_type)" class="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
        </svg>
        <!-- Generic File Icon -->
        <svg v-else class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"></path>
        </svg>
      </div>

      <!-- File Name -->
      <div class="text-sm text-gray-700 truncate flex-1">
        {{ attachment.file_name }}
      </div>

      <!-- File Size -->
      <div class="text-xs text-gray-400 flex-shrink-0">
        {{ formatFileSize(attachment.file_size) }}
      </div>
    </a>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { toProtectedFileUrl } from '@/utils/file-url'

const props = defineProps({
  attachments: {
    type: Array,
    default: () => []
  }
});

const sortedAttachments = computed(() => {
  if (!props.attachments) return [];
  return [...props.attachments].sort((a, b) => (a.order || 0) - (b.order || 0));
});

const fileHref = (url) => toProtectedFileUrl(url)

const isDocument = (fileType) => {
  if (!fileType) return false;
  const type = fileType.toLowerCase();
  return type.includes('pdf') || 
         type.includes('doc') || 
         type.includes('txt') || 
         type.includes('xls') || 
         type.includes('ppt') ||
         type.includes('csv');
};

const isImage = (fileType) => {
  if (!fileType) return false;
  const type = fileType.toLowerCase();
  return type.includes('image') || 
         type.includes('jpg') || 
         type.includes('jpeg') || 
         type.includes('png') || 
         type.includes('gif') || 
         type.includes('svg') ||
         type.includes('webp');
};

const formatFileSize = (bytes) => {
  if (bytes === 0 || !bytes) return '0 B';
  
  const k = 1024;
  
  if (bytes < k) {
    return bytes + ' B';
  } else if (bytes < k * k) {
    return parseFloat((bytes / k).toFixed(1)) + ' KB';
  } else if (bytes < k * k * k) {
    return parseFloat((bytes / (k * k)).toFixed(1)) + ' MB';
  } else {
    return parseFloat((bytes / (k * k * k)).toFixed(1)) + ' GB';
  }
};
</script>
