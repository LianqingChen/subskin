<script setup lang="ts">
import PhotoMaskCanvas from './PhotoMaskCanvas.vue'
defineProps<{ image: string; skin?: string | null; lesion?: string | null; proposal?: string | null; excluded?: string | null; uncertain?: string | null; referenceOnly?: boolean }>()
</script>
<template>
  <PhotoMaskCanvas :image="image" :skin="skin" :lesion="lesion" :candidate="uncertain || (referenceOnly ? proposal : null)" />
</template>
