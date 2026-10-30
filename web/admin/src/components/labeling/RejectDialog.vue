<template>
  <n-modal :show="show" preset="card" title="标记为不可用" style="max-width: 440px" @update:show="emit('update:show', $event)">
    <p class="desc">整张图无法用于标注或训练时选择原因。含可识别信息（证件、姓名、手机号等）请立即标记并停止处理。</p>
    <n-checkbox-group v-model:value="picked">
      <div class="grid"><n-checkbox v-for="r in reasons" :key="r" :value="r" :label="REASON_LABEL[r] ?? r" /></div>
    </n-checkbox-group>
    <template #footer>
      <div class="footer">
        <n-button @click="emit('update:show', false)">取消</n-button>
        <n-button type="error" :disabled="!picked.length" @click="emit('confirm', picked)">确认不可用</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { REASON_LABEL } from '@/types/labeling'

const props = defineProps<{ show: boolean; reasons: string[] }>()
const emit = defineEmits<{ (e: 'update:show', v: boolean): void; (e: 'confirm', reasons: string[]): void }>()
const picked = ref<string[]>([])
watch(() => props.show, (open) => { if (open) picked.value = [] })
</script>

<style scoped>
.desc { font-size: 13px; color: #94a3b8; margin: 0 0 12px; line-height: 1.6; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.footer { display: flex; justify-content: flex-end; gap: 8px; }
</style>
