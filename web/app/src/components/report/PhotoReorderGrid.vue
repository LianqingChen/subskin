<script setup lang="ts">
/**
 * PhotoReorderGrid — 白斑照片顺序调整网格
 *
 * 长按进入的「调整模式」：按住照片拖到目标位置即可交换顺序，
 * 「完成」保存新顺序、「取消」放弃修改。
 */
import { ref, watch } from 'vue'

export interface ReorderPhotoItem {
  id: number
  imageUrl: string
  siteLabel: string
  dateLabel: string
}

const props = defineProps<{
  items: ReorderPhotoItem[]
}>()

const emit = defineEmits<{
  done: [ids: number[]]
  cancel: []
}>()

const list = ref<ReorderPhotoItem[]>([])
const dragIdx = ref<number | null>(null)

watch(
  () => props.items,
  (v) => {
    list.value = v.map((x) => ({ ...x }))
  },
  { immediate: true },
)

function onPointerDown(e: PointerEvent, idx: number) {
  if (e.button !== 0) return
  dragIdx.value = idx
  const el = e.currentTarget as HTMLElement
  el.setPointerCapture?.(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (dragIdx.value === null) return
  const target = document.elementFromPoint(e.clientX, e.clientY)
  const cell = target?.closest?.('[data-idx]') as HTMLElement | null
  if (!cell) return
  const to = Number(cell.dataset.idx)
  const from = dragIdx.value
  if (Number.isNaN(to) || to === from) return
  const [moved] = list.value.splice(from, 1)
  list.value.splice(to, 0, moved)
  dragIdx.value = to
}

function endDrag() {
  dragIdx.value = null
}

function finish() {
  emit('done', list.value.map((x) => x.id))
}
</script>

<template>
  <div class="prg">
    <div class="prg__bar">
      <button type="button" class="prg__btn" @click="emit('cancel')">取消</button>
      <span class="prg__hint"><i class="ri-drag-move-2-line"></i> 按住照片拖动调整顺序</span>
      <button type="button" class="prg__btn prg__btn--ok" @click="finish">完成</button>
    </div>

    <div class="prg__grid">
      <div
        v-for="(it, i) in list"
        :key="it.id"
        class="prg__item"
        :class="{ 'prg__item--drag': dragIdx === i }"
        :data-idx="i"
        @pointerdown="onPointerDown($event, i)"
        @pointermove="onPointerMove"
        @pointerup="endDrag"
        @pointercancel="endDrag"
      >
        <img :src="it.imageUrl" alt="白斑照片" loading="lazy" />
        <span class="prg__site">{{ it.siteLabel }}</span>
        <span class="prg__date">{{ it.dateLabel }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.prg {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prg__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.prg__hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #64748b;
}

html.dark .prg__hint {
  color: #94a3b8;
}

.prg__btn {
  border: 1px solid #e2e8f0;
  background: white;
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  padding: 8px 16px;
  min-height: 40px;
  border-radius: 10px;
  cursor: pointer;
}

html.dark .prg__btn {
  background: #1e293b;
  border-color: #334155;
  color: #cbd5e1;
}

.prg__btn--ok {
  background: var(--color-primary-500);
  border-color: var(--color-primary-500);
  color: white;
  font-weight: 600;
}

.prg__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.prg__item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 10px;
  overflow: hidden;
  background: #f1f5f9;
  touch-action: none;
  cursor: grab;
  user-select: none;
  transition: transform 0.12s;
}

html.dark .prg__item {
  background: #334155;
}

.prg__item--drag {
  transform: scale(0.96);
  box-shadow: 0 0 0 3px var(--color-primary-500);
  z-index: 5;
}

.prg__item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  pointer-events: none;
}

.prg__site,
.prg__date {
  position: absolute;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.55);
  color: white;
  pointer-events: none;
}

.prg__site {
  bottom: 4px;
  left: 4px;
}

.prg__date {
  top: 4px;
  left: 4px;
}
</style>
