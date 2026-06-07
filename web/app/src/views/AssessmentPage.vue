<script setup lang="ts">
import { ref } from 'vue'
import DigitalHuman from '@/components/tracker/DigitalHuman.vue'
import AssessmentSection from '@/components/tracker/AssessmentSection.vue'
import BodyPartCamera from '@/components/tracker/BodyPartCamera.vue'
import { useToast } from '@/composables/useToast'

const toast = useToast()

const showCamera = ref(false)
const assessmentRef = ref<InstanceType<typeof AssessmentSection> | null>(null)
const selectedPart = ref<string | null>(null)

function handleBodyPartSelect(bodySite: string) {
  selectedPart.value = bodySite
  assessmentRef.value?.setBodySite(bodySite)
}

function openCamera() {
  if (!selectedPart.value) {
    toast.warning('请先在上方数字人上点击选择评估部位')
    return
  }
  showCamera.value = true
}

function handleCameraCapture(file: File, meta: { hasReferenceCard: boolean }) {
  assessmentRef.value?.handleCameraCapture(file, meta)
  showCamera.value = false
}

function triggerUpload() {
  if (!selectedPart.value) {
    onRequireBodySite()
    return
  }
  assessmentRef.value?.triggerUpload()
}

function onRequireBodySite() {
  toast.warning('请先在上方数字人上点击身体部位')
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
</script>

<template>
  <div class="bg-[#F5F7FA]">
    <!-- Digital Human — fixed, interactive -->
    <div class="fixed top-[6vh] left-0 right-0 z-0 bg-[#FDFCFC]" style="height: 40vh; min-height: 280px">
      <div class="w-full max-w-md mx-auto h-full">
        <DigitalHuman @select-part="handleBodyPartSelect" />
      </div>
    </div>

    <!-- Assessment section — scrollable card -->
    <div data-view-card class="relative z-10 bg-[#F5F7FA] rounded-t-3xl shadow-[0_-8px_30px_rgba(0,0,0,0.08)]"
      style="margin-top: 40vh;">
      <AssessmentSection
        ref="assessmentRef"
        :selected-part="selectedPart"
        :active-part-assessment="null"
        :part-history="[]"
        @take-photo="openCamera"
        @upload-photo="triggerUpload"
        @close-part="selectedPart = null"
        @view-detail="(id) => $router.push(`/tracker/vasi/${id}`)"
        @require-body-site="onRequireBodySite"
      />
    </div>

    <BodyPartCamera
      v-model="showCamera"
      :body-part="selectedPart || ''"
      @captured="handleCameraCapture"
    />
  </div>
</template>
