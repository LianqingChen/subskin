/**
 * VASI Assessment Vue Component
 * 
 * Main component for VASI assessment flow including image upload,
 * body site selection, and assessment submission.
 */
<script setup>
import { ref, computed } from 'vue'
import { createAssessment, BODY_SITES } from '../utils/vasi-api.js'

const selectedFile = ref(null)
const previewUrl = ref(null)
const selectedBodySite = ref('face')
const isSubmitting = ref(false)
const errorMessage = ref('')
const assessmentResult = ref(null)
const isDragging = ref(false)

const bodySites = computed(() => Object.entries(BODY_SITES).map(([key, value]) => ({
  value: key,
  label: value.label,
  icon: value.icon
})))

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (file) {
    validateAndSetFile(file)
  }
}

function handleDragOver(event) {
  event.preventDefault()
  isDragging.value = true
}

function handleDragLeave(event) {
  event.preventDefault()
  isDragging.value = false
}

function handleDrop(event) {
  event.preventDefault()
  isDragging.value = false
  
  const file = event.dataTransfer.files[0]
  if (file) {
    validateAndSetFile(file)
  }
}

function validateAndSetFile(file) {
  const validTypes = ['image/jpeg', 'image/png', 'image/webp']
  
  if (!validTypes.includes(file.type)) {
    errorMessage.value = '请上传 JPG、PNG 或 WebP 格式的图片'
    return
  }
  
  if (file.size > 10 * 1024 * 1024) {
    errorMessage.value = '图片大小不能超过 10MB'
    return
  }
  
  selectedFile.value = file
  previewUrl.value = URL.createObjectURL(file)
  errorMessage.value = ''
  
  assessmentResult.value = null
}

async function submitAssessment() {
  if (!selectedFile.value) {
    errorMessage.value = '请先上传图片'
    return
  }
  
  isSubmitting.value = true
  errorMessage.value = ''
  
  try {
    const result = await createAssessment(selectedFile.value, selectedBodySite.value)
    assessmentResult.value = result
  } catch (error) {
    errorMessage.value = error.message || '评估失败，请稍后重试'
  } finally {
    isSubmitting.value = false
  }
}

function resetAssessment() {
  selectedFile.value = null
  previewUrl.value = null
  assessmentResult.value = null
  errorMessage.value = ''
}

function goToReport() {
  if (assessmentResult.value && assessmentResult.value.id) {
    window.location.href = `/vasi/report?id=${assessmentResult.value.id}`
  }
}
</script>

<template>
  <div class="vasi-assessment">
    <div class="upload-section" v-if="!assessmentResult">
      <h2 class="section-title">📸 上传白斑照片</h2>
      
      <div 
        class="upload-area"
        :class="{ 'is-dragging': isDragging, 'has-preview': previewUrl }"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
      >
        <div v-if="!previewUrl" class="upload-placeholder">
          <div class="upload-icon">📷</div>
          <p class="upload-text">点击或拖拽图片到此处上传</p>
          <p class="upload-hint">支持 JPG、PNG、WebP 格式，最大 10MB</p>
          <input 
            type="file" 
            accept="image/jpeg,image/png,image/webp"
            @change="handleFileSelect"
            class="file-input"
          >
        </div>
        
        <div v-else class="image-preview">
          <img :src="previewUrl" alt="白斑照片预览" />
          <button @click="resetAssessment" class="remove-button" title="移除图片">
            ✕
          </button>
        </div>
      </div>
      
      <div class="body-site-section">
        <h3 class="subsection-title">🎯 选择评估部位</h3>
        <div class="body-site-grid">
          <button
            v-for="site in bodySites"
            :key="site.value"
            @click="selectedBodySite = site.value"
            :class="['body-site-button', { 'is-selected': selectedBodySite === site.value }]"
          >
            <span class="site-icon">{{ site.icon }}</span>
            <span class="site-label">{{ site.label }}</span>
          </button>
        </div>
      </div>
      
      <div class="error-message" v-if="errorMessage">
        ⚠️ {{ errorMessage }}
      </div>
      
      <button 
        @click="submitAssessment"
        :disabled="!selectedFile || isSubmitting"
        class="submit-button"
      >
        <span v-if="isSubmitting" class="loading-spinner"></span>
        {{ isSubmitting ? '评估中...' : '开始评估' }}
      </button>
      
      <div class="free-notice">
        <span class="notice-icon">💚</span>
        <span class="notice-text">永久免费 · 无使用次数限制</span>
      </div>
    </div>
    
    <div class="result-section" v-else>
      <div class="success-card">
        <div class="success-icon">✅</div>
        <h2 class="success-title">评估完成</h2>
        
        <div class="result-summary">
          <div class="result-item">
            <span class="result-label">VASI 评分</span>
            <span class="result-value primary">{{ assessmentResult.vasi_score }}</span>
          </div>
          <div class="result-item">
            <span class="result-label">评估部位</span>
            <span class="result-value">{{ BODY_SITES[selectedBodySite].label }}</span>
          </div>
        </div>
        
        <div class="action-buttons">
          <button @click="goToReport" class="action-button primary">
            查看详细报告 →
          </button>
          <button @click="resetAssessment" class="action-button secondary">
            继续评估
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vasi-assessment {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}

.section-title {
  font-size: 1.5rem;
  color: var(--sub-der-color-text);
  margin-bottom: 1.5rem;
  text-align: center;
}

.subsection-title {
  font-size: 1.25rem;
  color: var(--subskin-color-text);
  margin-bottom: 1rem;
}

.upload-area {
  border: 2px dashed var(--subskin-color-border);
  border-radius: var(--subskin-radius-lg);
  padding: 3rem;
  text-align: center;
  transition: all 0.3s ease;
  position: relative;
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-area.is-dragging {
  border-color: var(--subskin-color-primary);
  background-color: var(--subskin-color-bg-soft);
}

.upload-area.has-preview {
  padding: 1rem;
}

.upload-placeholder {
  cursor: pointer;
}

.upload-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.upload.upload-text {
  font-size: 1.125rem;
  color: var(--subskin-color-text);
  margin-bottom: 0.5rem;
}

.upload-hint {
  font-size: 0.875rem;
  color: var(--subskin-color-text-muted);
}

.file-input {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}

.image-preview {
  position: relative;
  width: 100%;
  height: 100%;
}

.image-preview img {
  max-width: 100%;
  max-height: 400px;
  border-radius: var(--subskin-dius-md);
  object-fit: contain;
}

.remove-button {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background-color: var(--subskin-color-danger);
  color: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  transition: transform 0.2s ease;
}

.remove-button:hover {
  transform: scale(1.1);
}

.body-site-section {
  margin: 2rem 0;
}

.body-site-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 1rem;
}

.body-site-button {
  padding: 1rem;
  border: 2px solid var(--subskin-color-border);
  border-radius: var(--subskin-radius-md);
  background-color: var(--subskin-color-bg);
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.body-site-button:hover {
  border-color: var(--subskin-color-primary-light);
  background-color: var(--subskin-color-bg-soft);
}

.body-site-button.is-selected {
  border-color: var(--subskin-color-primary);
  background-color: var(--subskin-color-primary-light);
  color: white;
}

.site-icon {
  font-size: 1.5rem;
}

.site-label {
  font-size: 0.875rem;
  font-weight: 500;
}

.error-message {
  background-color: #fef2f2;
  color: var(--subskin-color-danger);
  padding: 1rem;
  border-radius: var(--subskin-radius-md);
  margin: 1rem 0;
  border-left: 4px solid var(--subskin-color-danger);
}

.submit-button {
  width: 100%;
  padding: 1rem;
  background-color: var(--subskin-color-primary);
  color: white;
  border: none;
  border-radius: var(--subskin-radius-md);
  font-size: 1.125rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.submit-button:hover:not(:disabled) {
  background-color: var(--subskin-color-primary-dark);
}

.submit-button:disabled {
  background-color: var(--subskin-color-text-muted);
  cursor: not-allowed;
}

.loading-spinner {
  width: 1.25rem;
  height: 1.25rem;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.free-notice {
  margin-top: 1.5rem;
  text-align: center;
  padding: 1rem;
  background-color: rgba(47, 133, 90, 0.1);
  border-radius: var(--subskin-radius-md);
  color: var(--subskin-color-success);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.notice-icon {
  font-size: 1.25rem;
}

.notice-text {
  font-weight: 500;
}

.success-card {
  background-color: var(--subskin-color-bg);
  border: 2px solid var(--subskin-color-success);
  border-radius: var(--subskin-radius-lg);
  padding: 2rem;
  text-align: center;
}

.success-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.success-title {
  font-size: 1.75rem;
  color: var(--subskin-color-text);
  margin-bottom: 1.5rem;
}

.result-summary {
  display: flex;
  justify-content: center;
  gap: 3rem;
  margin-bottom: 2rem;
  flex-wrap: wrap;
}

.result-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.result-label {
  font-size: 0.875rem;
  color: var(--subskin-color-text-muted);
}

.result-value {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--subskin-color-text);
}

.result-value.primary {
  color: var(--subskin-color-primary);
  font-size: 2rem;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.action-button {
  padding: 0.75rem 1.5rem;
  border-radius: var(--subskin-radius-md);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-button.primary {
  background-color: var(--subskin-color-primary);
  color: white;
  border: none;
}

.action-button.primary:hover {
  background-color: var(--subskin-color-primary-dark);
}

.action-button.secondary {
  background-color: transparent;
  color: var(--subskin-color-text);
  border: 2px solid var(--subskin-color-border);
}

.action-button.secondary:hover {
  border-color: var(--subskin-color-primary);
  color: var(--subskin-color-primary);
}

@media (max-width: 640px) {
  .vasi-assessment {
    padding: 1rem;
  }
  
  .result-summary {
    gap: 1.5rem;
  }
  
  .action-buttons {
    flex-direction: column;
  }
  
  .action-button {
    width: 100%;
  }
}
</style>
