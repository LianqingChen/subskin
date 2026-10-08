<script setup lang="ts">
/**
 * MaskEditor 工具栏 — 普通模式（页内轻量单行条）与全屏模式（沉浸双行工具面板）双形态。
 *
 * 工具：智能选斑（边缘感知魔法棒）/ 白斑笔 / 皮肤笔 / 橡皮 + 边缘吸附。
 * 全屏形态把常用操作做成整行大按钮分段控件，撤销/重做/吸附/缩放整行铺开，
 * 保证全屏标注时单手即可操作（触控目标 ≥44px）。
 * 画笔/橡皮粗细统一由 BrushSizeControl（点击弹出竖向滑杆）承载，不占横向空间。
 */
import BrushSizeControl from '@/components/tracker/BrushSizeControl.vue'

export type MaskTool = 'magic-wand' | 'skin-brush' | 'lesion-brush' | 'eraser' | 'exclude'

const props = defineProps<{
  tool: MaskTool
  brushSize: number
  canUndo: boolean
  canRedo: boolean
  fullscreen: boolean
  /** 魔法棒容差 0-100 */
  wandTolerance: number
  /** 是否正在执行边缘吸附 */
  snapping?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:tool', tool: MaskTool): void
  (e: 'update:brushSize', size: number): void
  (e: 'update:wandTolerance', value: number): void
  (e: 'undo'): void
  (e: 'redo'): void
  (e: 'snapEdges'): void
  (e: 'clearLesion'): void
  (e: 'zoomIn'): void
  (e: 'zoomOut'): void
  (e: 'zoomFit'): void
}>()

const TOOLS: ReadonlyArray<{ id: MaskTool; icon: string; label: string; title: string; activeCls: string; idleCls: string }> = [
  { id: 'magic-wand', icon: 'ri-magic-line', label: '智能选斑', title: '智能选斑：点一下白斑自动圈出范围（边缘感知）', activeCls: 'bg-primary-500 text-white shadow-sm', idleCls: 'text-primary-600 dark:text-primary-300' },
  { id: 'lesion-brush', icon: 'ri-virus-line', label: '补遗漏', title: '浅色区域画笔，不改变皮肤范围', activeCls: 'bg-primary-600 text-white shadow-sm', idleCls: 'text-primary-700 dark:text-primary-300' },
  { id: 'skin-brush', icon: 'ri-hand-heart-line', label: '皮肤', title: '核对可见皮肤范围', activeCls: 'bg-blue-500 text-white shadow-sm', idleCls: 'text-blue-600 dark:text-blue-300' },
  { id: 'exclude', icon: 'ri-forbid-line', label: '排除', title: '排除背景或遮挡：同时擦除两层', activeCls: 'bg-gray-500 text-white shadow-sm', idleCls: 'text-gray-600 dark:text-gray-300' },
  { id: 'eraser', icon: 'ri-eraser-line', label: '去误圈', title: '仅擦除浅色标注，保留皮肤范围', activeCls: 'bg-gray-500 text-white shadow-sm', idleCls: 'text-gray-600 dark:text-gray-300' },
]

function setTool(tool: MaskTool) {
  emit('update:tool', tool)
}

function onBrushSize(size: number) {
  emit('update:brushSize', size)
}

const wandActive = () => props.tool === 'magic-wand'
</script>

<template>
  <div
    class="z-30 backdrop-blur-md px-3 py-2"
    :class="fullscreen
      ? 'shrink-0 bg-gray-900/95 border-t border-white/10 pb-[env(safe-area-inset-bottom)]'
      : 'sticky bottom-0 left-0 right-0 bg-white/95 dark:bg-gray-900/95 border-t border-gray-200/50 dark:border-gray-700/50 pb-[env(safe-area-inset-bottom)]'"
  >
    <!-- 智能选斑容差：仅在魔法棒激活时出现，避免占用日常标注空间 -->
    <div v-if="wandActive()" class="mb-2 flex items-center gap-2">
      <i class="ri-magic-line text-sm" :class="fullscreen ? 'text-primary-300' : 'text-primary-500'" aria-hidden="true"></i>
      <label :for="`wand-tol-${fullscreen ? 'fs' : 'inline'}`" class="text-[11px] whitespace-nowrap" :class="fullscreen ? 'text-gray-300' : 'text-gray-500 dark:text-gray-400'">选取范围</label>
      <input
        :id="`wand-tol-${fullscreen ? 'fs' : 'inline'}`"
        type="range"
        min="5"
        max="70"
        step="5"
        class="flex-1 min-w-0 accent-primary-500"
        :value="wandTolerance"
        @input="emit('update:wandTolerance', Number(($event.target as HTMLInputElement).value))"
      />
      <span class="text-[11px] tabular-nums w-8 text-right" :class="fullscreen ? 'text-gray-300' : 'text-gray-500 dark:text-gray-400'">{{ wandTolerance }}</span>
    </div>

    <!-- 普通模式：紧凑单行 -->
    <div v-if="!fullscreen" class="flex flex-wrap items-center gap-1.5">
      <div class="flex items-center gap-1 p-1 rounded-xl bg-gray-100 dark:bg-gray-700">
        <button
          v-for="t in TOOLS"
          :key="t.id"
          type="button"
          class="w-11 h-11 rounded-lg text-sm font-medium transition-colors flex items-center justify-center"
          :class="t.id === tool ? t.activeCls : t.idleCls"
          :title="t.title"
          :aria-label="t.title"
          @click="setTool(t.id)"
        >
          <i :class="t.icon"></i>
        </button>
      </div>

      <!-- 画笔粗细：点击弹出竖向调节 -->
      <BrushSizeControl :brush-size="brushSize" :fullscreen="fullscreen" @update:brush-size="onBrushSize" />

      <button
        type="button"
        class="w-11 h-11 rounded-lg flex items-center justify-center text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30"
        :disabled="!canUndo"
        title="撤销"
        aria-label="撤销"
        @click="emit('undo')"
      >
        <i class="ri-arrow-go-back-line text-lg"></i>
      </button>
      <button
        type="button"
        class="w-11 h-11 rounded-lg flex items-center justify-center text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30"
        :disabled="!canRedo"
        title="重做"
        aria-label="重做"
        @click="emit('redo')"
      >
        <i class="ri-arrow-go-forward-line text-lg"></i>
      </button>

      <button
        type="button"
        class="ml-auto h-11 px-3 rounded-lg flex items-center gap-1.5 text-xs font-medium bg-primary-50 text-primary-700 hover:bg-primary-100 dark:bg-primary-900/40 dark:text-primary-300 disabled:opacity-40"
        :disabled="snapping"
        title="尝试贴合照片色差边缘，需要核对"
        aria-label="自动吸附白斑边缘"
        @click="emit('snapEdges')"
      >
        <i class="ri-focus-3-line text-base" :class="snapping ? 'animate-spin' : ''"></i>
        <span class="hidden sm:inline">{{ snapping ? '吸附中' : '边缘吸附' }}</span>
      </button>
      <button
        type="button"
        class="w-11 h-11 rounded-lg flex items-center justify-center text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700"
        title="清空白斑层"
        aria-label="清空白斑层"
        @click="emit('clearLesion')"
      >
        <i class="ri-delete-back-2-line text-lg"></i>
      </button>
    </div>

    <!-- 全屏模式：双行沉浸面板 -->
    <div v-else class="flex flex-col gap-2">
      <!-- 第一行：工具大按钮分段控件 -->
      <div class="flex items-center gap-1.5">
        <button
          v-for="t in TOOLS"
          :key="t.id"
          type="button"
          class="h-11 flex-1 rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-1.5"
          :class="t.id === tool ? t.activeCls : 'text-gray-300 bg-white/10 hover:bg-white/15'"
          :aria-label="t.title"
          @click="setTool(t.id)"
        >
          <i :class="t.icon" class="text-base"></i>
          <span>{{ t.label }}</span>
        </button>
      </div>

      <!-- 第二行：粗细 + 撤销/重做 + 吸附/清空 + 缩放 -->
      <div class="flex flex-wrap items-center gap-1.5">
        <BrushSizeControl :brush-size="brushSize" :fullscreen="fullscreen" @update:brush-size="onBrushSize" />

        <button
          type="button"
          class="h-11 px-3 rounded-lg flex items-center gap-1.5 text-sm text-gray-200 bg-white/10 hover:bg-white/15 disabled:opacity-30"
          :disabled="snapping"
          aria-label="自动吸附白斑边缘"
          @click="emit('snapEdges')"
        >
          <i class="ri-focus-3-line text-base" :class="snapping ? 'animate-spin' : ''"></i>
          {{ snapping ? '吸附中' : '边缘吸附' }}
        </button>
        <button
          type="button"
          class="w-11 h-11 rounded-lg flex items-center justify-center text-gray-200 hover:bg-white/10"
          title="清空白斑层"
          aria-label="清空白斑层"
          @click="emit('clearLesion')"
        >
          <i class="ri-delete-back-2-line text-lg"></i>
        </button>

        <div class="flex items-center gap-1 ml-auto">
          <button
            type="button"
            class="w-11 h-11 rounded-lg flex items-center justify-center text-gray-200 hover:bg-white/10 disabled:opacity-30"
            :disabled="!canUndo" title="撤销" aria-label="撤销" @click="emit('undo')"
          >
            <i class="ri-arrow-go-back-line text-lg"></i>
          </button>
          <button
            type="button"
            class="w-11 h-11 rounded-lg flex items-center justify-center text-gray-200 hover:bg-white/10 disabled:opacity-30"
            :disabled="!canRedo" title="重做" aria-label="重做" @click="emit('redo')"
          >
            <i class="ri-arrow-go-forward-line text-lg"></i>
          </button>
          <button
            type="button"
            class="w-11 h-11 rounded-lg flex items-center justify-center text-gray-200 hover:bg-white/10"
            title="缩小" aria-label="缩小" @click="emit('zoomOut')"
          >
            <i class="ri-zoom-out-line text-lg"></i>
          </button>
          <button
            type="button"
            class="w-11 h-11 rounded-lg flex items-center justify-center text-gray-200 hover:bg-white/10"
            title="适应屏幕" aria-label="适应屏幕" @click="emit('zoomFit')"
          >
            <i class="ri-aspect-ratio-line text-lg"></i>
          </button>
          <button
            type="button"
            class="w-11 h-11 rounded-lg flex items-center justify-center text-gray-200 hover:bg-white/10"
            title="放大" aria-label="放大" @click="emit('zoomIn')"
          >
            <i class="ri-zoom-in-line text-lg"></i>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
