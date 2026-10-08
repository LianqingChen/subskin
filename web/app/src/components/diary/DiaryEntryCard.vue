<script setup lang="ts">
/**
 * DiaryEntryCard — 单条日记卡片
 * 展示：日期、原文、AI提取标签（心情/睡眠/用药/压力/患处）
 */
import { ref } from 'vue'
import type { DiaryEntry } from '@/api/diary'
import { parseDate } from '@/utils/date'
import { toProtectedFileUrl } from '@/utils/file-url'
import { PART_LABELS } from '@/constants/bodySites'

defineProps<{
  entry: DiaryEntry
  moodConfig: Record<string, { emoji: string; label: string; color: string }>
  skinConfig: Record<string, { emoji: string; label: string }>
}>()

const emit = defineEmits<{
  delete: [id: number]
}>()

const expanded = ref(false)
const showDeleteConfirm = ref(false)

function formatDate(dateStr: string): string {
  const d = parseDate(dateStr)
  if (!d) return dateStr || ''
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  const month = d.getMonth() + 1
  const day = d.getDate()
  const weekdays = ['日', '一', '二', '三', '四', '五', '六']
  const weekday = weekdays[d.getDay()]
  if (d.getFullYear() === now.getFullYear()) return `${month}月${day}日 周${weekday}`
  return `${d.getFullYear()}年${month}月${day}日`
}

function siteLabel(site: string | null): string {
  if (!site) return ''
  return PART_LABELS[site] || site
}

function protectedUrl(url: string): string {
  return toProtectedFileUrl(url) || url
}

function confirmDelete() {
  showDeleteConfirm.value = true
  setTimeout(() => { showDeleteConfirm.value = false }, 3000)
}
</script>

<template>
  <article class="entry-card" @click="expanded = !expanded">
    <!-- Header row -->
    <div class="entry-card__header">
      <span class="entry-card__date">{{ formatDate(entry.created_at || entry.entry_date) }}</span>
      <div class="entry-card__actions">
        <span v-if="entry.input_type === 'quick'" class="entry-card__badge">快捷</span>
        <button
          class="entry-card__delete"
          @click.stop="showDeleteConfirm ? emit('delete', entry.id) : confirmDelete()"
        >
          <i :class="showDeleteConfirm ? 'ri-check-line' : 'ri-delete-bin-6-line'"></i>
        </button>
      </div>
    </div>

    <!-- Summary or raw text -->
    <p class="entry-card__text" :class="{ 'entry-card__text--collapsed': !expanded }">
      {{ entry.ai_summary || entry.raw_text }}
    </p>
    <p v-if="expanded && entry.ai_summary" class="entry-card__raw">
      {{ entry.raw_text }}
    </p>

    <!-- 白斑照片 -->
    <div v-if="entry.images && entry.images.length > 0" class="entry-card__images">
      <div
        v-for="img in entry.images"
        :key="img.id"
        class="entry-card__image-item"
        @click.stop
      >
        <img :src="protectedUrl(img.image_url)" alt="白斑照片" loading="lazy" />
        <span v-if="img.body_site" class="entry-card__image-site">{{ siteLabel(img.body_site) }}</span>
        <span
          v-if="img.analysis_status === 'pending' || img.analysis_status === 'analyzing'"
          class="entry-card__image-badge entry-card__image-badge--analyzing"
        >
          <i class="ri-loader-4-line"></i>
        </span>
        <span
          v-else-if="img.vasi_assessment_id"
          class="entry-card__image-badge entry-card__image-badge--vasi"
          title="已深度分析"
        >
          <i class="ri-microscope-line"></i>
        </span>
      </div>
    </div>

    <!-- AI tags -->
    <div class="entry-card__tags">
      <span
        v-if="entry.mood && moodConfig[entry.mood]"
        class="entry-card__tag"
        :style="{ borderColor: moodConfig[entry.mood].color + '40', color: moodConfig[entry.mood].color }"
      >
        {{ moodConfig[entry.mood].emoji }} {{ moodConfig[entry.mood].label }}
      </span>

      <span v-if="entry.sleep_quality" class="entry-card__tag entry-card__tag--sleep">
        🛏️ {{ entry.sleep_quality === 'good' ? '睡得好' : entry.sleep_quality === 'fair' ? '一般' : '没睡好' }}
      </span>

      <span v-if="entry.skin_condition && skinConfig[entry.skin_condition]" class="entry-card__tag entry-card__tag--skin">
        {{ skinConfig[entry.skin_condition].emoji }} {{ skinConfig[entry.skin_condition].label }}
      </span>

      <span v-if="entry.medication_taken" class="entry-card__tag entry-card__tag--med">
        💊 用药
      </span>

      <span v-if="entry.stress_level" class="entry-card__tag entry-card__tag--stress">
        📊 压力 {{ entry.stress_level }}/5
      </span>

      <span v-if="entry.diet_notes" class="entry-card__tag entry-card__tag--diet">
        🍽️ 饮食
      </span>
    </div>

    <!-- AI processing indicator -->
    <div v-if="!entry.mood && !entry.ai_summary && entry.input_type !== 'quick'" class="entry-card__processing">
      <i class="ri-sparkling-2-line"></i> AI分析中...
    </div>
  </article>
</template>

<style scoped>
.entry-card {
  background: white;
  border-radius: 14px;
  padding: 14px 16px;
  border: 1px solid #f1f5f9;
  cursor: pointer;
  transition: all 0.2s;
}

html.dark .entry-card {
  background: #1e293b;
  border-color: #334155;
}

.entry-card:active {
  transform: scale(0.99);
}

.entry-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.entry-card__date {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
}

.entry-card__actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.entry-card__badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--color-primary-500) 10%, transparent);
  color: var(--color-primary-600);
  font-weight: 500;
}

.entry-card__delete {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: #cbd5e1;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.entry-card__delete:active {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.entry-card__text {
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
  margin-bottom: 10px;
}

html.dark .entry-card__text {
  color: #e2e8f0;
}

.entry-card__text--collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.entry-card__raw {
  font-size: 13px;
  line-height: 1.5;
  color: #64748b;
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #f8fafc;
  border-radius: 8px;
}

html.dark .entry-card__raw {
  background: #0f172a;
  color: #94a3b8;
}

.entry-card__images {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  margin-bottom: 10px;
}

.entry-card__image-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  background: #f1f5f9;
}

html.dark .entry-card__image-item {
  background: #334155;
}

.entry-card__image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.entry-card__image-site {
  position: absolute;
  bottom: 3px;
  left: 3px;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.55);
  color: white;
}

.entry-card__image-badge {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
}

.entry-card__image-badge--analyzing {
  background: rgba(0, 0, 0, 0.5);
  color: white;
}

.entry-card__image-badge--analyzing i {
  animation: ec-spin 1s linear infinite;
}

.entry-card__image-badge--vasi {
  background: var(--color-primary-500);
  color: white;
}

@keyframes ec-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.entry-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.entry-card__tag {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  color: #64748b;
  background: #f8fafc;
}

html.dark .entry-card__tag {
  background: #0f172a;
  border-color: #334155;
  color: #94a3b8;
}

.entry-card__tag--sleep { border-color: #818cf840; color: #6366f1; }
.entry-card__tag--skin { border-color: #f59e0b40; color: #d97706; }
.entry-card__tag--med { border-color: #10b98140; color: #059669; }
.entry-card__tag--stress { border-color: #ef444440; color: #dc2626; }
.entry-card__tag--diet { border-color: #8b5cf640; color: #7c3aed; }

.entry-card__processing {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-primary-500);
  margin-top: 8px;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
