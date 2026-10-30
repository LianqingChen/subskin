<template>
  <main class="training-page" :style="themeStyle">
    <header class="heading"><h1>训练数据</h1><p class="desc">从标注进度到金标准，再到数据集、训练与上线登记</p></header>
    <ProgressSection :progress="progress" :loading="loading" :error="error" @refresh="load" />
    <RgbSegmentationPanel />
  </main>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useThemeVars } from 'naive-ui'
import { useLabelingProgress } from '@/composables/useLabelingProgress'
import ProgressSection from '@/components/training/ProgressSection.vue'
import RgbSegmentationPanel from '@/components/training/RgbSegmentationPanel.vue'

const { progress, loading, error, load } = useLabelingProgress()
const theme = useThemeVars()
const themeStyle = computed(() => ({
  '--tr-panel': theme.value.cardColor, '--tr-text': theme.value.textColor1, '--tr-muted': theme.value.textColor3,
  '--tr-border': theme.value.borderColor, '--tr-accent': theme.value.primaryColorHover, '--tr-accent-bg': theme.value.primaryColor + '18',
}))
</script>
<style scoped>
.training-page { max-width: 1200px; margin: 0 auto; color: var(--tr-text); padding-bottom: 24px; }
.heading { margin-bottom: 20px; }
h1 { font-size: 26px; font-weight: 650; margin: 0; }
.desc { color: var(--tr-muted); font-size: 13px; margin: 6px 0 0; }
@media (max-width: 767px) { h1 { font-size: 22px; } }
</style>
