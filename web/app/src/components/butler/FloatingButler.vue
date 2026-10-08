<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useButlerStore } from '@/stores/butler'
import { useChatStore } from '@/stores/chat'
import { BUTLER_SIZE_PX, BUTLER_STYLE_CLASS } from '@/utils/butler'
import ButlerPanel from '@/components/butler/ButlerPanel.vue'
import ButlerCreature3D from '@/components/butler/ButlerCreature3D.vue'
import { useButlerDrag } from '@/composables/useButlerDrag'
import { useButlerRoam } from '@/composables/useButlerRoam'

const butlerStore = useButlerStore()
const chatStore = useChatStore()
const route = useRoute()

const pref = computed(() => butlerStore.preference)
const fabSize = computed(() => BUTLER_SIZE_PX[pref.value.size])
// real=金斑蝶（默认，呼应品牌 Logo）；deer=梅花鹿；均为 Three.js 实时渲染的真 3D 形象
const creature3D = computed<'butterfly' | 'deer'>(() =>
  pref.value.mascot === 'deer' ? 'deer' : 'butterfly',
)

// ── 锚点避让：不同页面的右下角悬浮元素不同，管家锚点随之抬高 ──
const isCommunity = computed(() => route.path === '/community' || route.path.startsWith('/community/'))
const isAssistant = computed(() => route.path === '/')
const anchorClass = computed(() => {
  if (isCommunity.value) return 'anchor-community'
  if (isAssistant.value) return 'anchor-assistant'
  return 'anchor-default'
})

// ── 长按拖动（已拆分为 useButlerDrag）──
const {
  fabEl,
  customPos,
  hasCustomPos,
  isPressing,
  isDragging,
  dragPos,
  suppressClick,
  onFabPointerDown,
  onFabPointerMove,
  onFabPointerUp,
  onFabPointerCancel,
} = useButlerDrag({
  fabSize,
  position: computed(() => pref.value.position),
  onHide: () => butlerStore.hide(),
  onSavePosition: (side) => { void butlerStore.savePreference({ position: side }) },
})

// ── 随机跳跃 + 招呼气泡（已拆分为 useButlerRoam）──
const {
  roam,
  isMoving,
  greetingVisible,
  greetingText,
  scheduleRoam,
  stopRoam,
  startGreetingLoop,
  stopGreetingLoop,
  onGreetingClick,
} = useButlerRoam({
  isOpen: () => butlerStore.isOpen,
  isHidden: () => butlerStore.hidden,
  isLively: () => true,
  hasCustomPos: () => hasCustomPos.value,
  isDragging: () => isDragging.value,
  onOpenPanel: () => butlerStore.open(),
})

// ── 心情：招呼(挥手) > 面板打开(开心) > 回答生成中(思考) > 平静 ──
const isStreaming = computed(() => chatStore.messages.some(m => m.isSkeleton))
const mood = computed<'idle' | 'happy' | 'thinking' | 'greeting'>(() => {
  if (greetingVisible.value) return 'greeting'
  if (butlerStore.isOpen) return 'happy'
  if (isStreaming.value) return 'thinking'
  return 'idle'
})

function onFabClick() {
  if (suppressClick.value) return
  butlerStore.toggle()
}

// 拖动/自由位置模式下由内联 left/top 定位（FAB 中心对齐），锚点模式沿用角落 CSS + 随机跳跃位移
const wrapStyle = computed((): Record<string, string> => {
  if (isDragging.value && dragPos.value) {
    return {
      left: `${dragPos.value.x}px`,
      top: `${dragPos.value.y}px`,
      right: 'auto',
      bottom: 'auto',
      transform: 'translate(-50%, -50%) scale(1.06)',
    }
  }
  if (customPos.value) {
    return {
      left: `${customPos.value.x * 100}%`,
      top: `${customPos.value.y * 100}%`,
      right: 'auto',
      bottom: 'auto',
      transform: 'translate(-50%, -50%)',
    }
  }
  return { transform: `translate3d(${roam.value.x}px, ${roam.value.y}px, 0)` }
})

onMounted(() => {
  butlerStore.loadPreference()
  startGreetingLoop()
  scheduleRoam()
})
onBeforeUnmount(() => {
  stopGreetingLoop()
  stopRoam()
})
</script>

<template>
  <!-- 隐藏模式：屏幕边缘"偷看"，半个脸+灵动的眼睛，点击唤回 -->
  <Transition name="butler-peek">
    <button
      v-if="butlerStore.hidden && butlerStore.isFabVisible"
      type="button"
      class="butler-peek"
      :class="pref.position === 'left' ? 'peek-left' : 'peek-right'"
      aria-label="小白管家在边缘偷看，点击唤回"
      data-track-id="butler_peek"
      @click="butlerStore.unhide(true)"
    >
      <ButlerCreature3D :creature="creature3D" :size="64" />
    </button>
  </Transition>

  <div
    v-if="butlerStore.isFabVisible && !butlerStore.hidden"
    :class="[
      'butler-wrap group',
      anchorClass,
      pref.position === 'left' ? 'pos-left' : 'pos-right',
      { 'pos-free': hasCustomPos, 'is-pressing': isPressing, 'is-dragging': isDragging },
    ]"
    :style="wrapStyle"
  >
    <!-- 招呼气泡 -->
    <Transition name="butler-bubble">
      <button v-if="greetingVisible && !butlerStore.isOpen && !isDragging" type="button" class="butler-bubble" data-track-id="butler_greeting_bubble" @click="onGreetingClick">
        {{ greetingText }}
      </button>
    </Transition>

    <!-- 漂浮按钮 -->
    <div class="butler-fab-outer" :class="{ 'is-moving': isMoving }">
      <div v-if="isDragging" class="drag-hint">松手放置 · 拖到边缘隐藏</div>
      <button
        ref="fabEl"
        type="button"
        :class="['butler-fab', BUTLER_STYLE_CLASS[pref.style]]"
        :style="{ width: fabSize + 'px', height: fabSize + 'px' }"
        aria-label="打开小白管家（长按可拖动到任意位置，拖到屏幕边缘隐藏）"
        title="小白管家（长按可拖动）"
        data-track-id="butler_fab"
        @click="onFabClick"
        @pointerdown="onFabPointerDown"
        @pointermove="onFabPointerMove"
        @pointerup="onFabPointerUp"
        @pointercancel="onFabPointerCancel"
        @contextmenu.prevent
      >
        <ButlerCreature3D
          :creature="creature3D"
          :size="fabSize"
          :mood="mood"
          :flying="isMoving"
          :dragging="isDragging"
        />
      </button>
      <!-- 桌面 hover 显示的隐藏按钮 -->
      <button
        type="button"
        class="butler-hide-btn"
        aria-label="隐藏小白管家"
        title="隐藏小白管家（在边缘偷看）"
        @click.stop="butlerStore.hide()"
      >
        <i class="ri-eye-off-line"></i>
      </button>
    </div>
  </div>
  <ButlerPanel />
</template>

<style scoped>
/* ── 锚点（避让各页面右下角悬浮元素） ── */
.butler-wrap {
  position: fixed;
  z-index: 60;
  bottom: calc(54px + env(safe-area-inset-bottom, 0px) + 12px);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  transition: transform 0.85s cubic-bezier(0.34, 1.3, 0.5, 1);
  will-change: transform;
}
.butler-wrap.pos-right { right: 16px; }
.butler-wrap.pos-left { right: auto; left: 16px; align-items: flex-start; }
/* 自由位置模式（用户拖动后）：中心对齐气泡与按钮 */
.butler-wrap.pos-free { align-items: center; }
/* 长按待拖动 / 拖动中状态 */
.butler-wrap.is-pressing .butler-fab { transform: scale(1.06); }
.butler-wrap.is-dragging {
  z-index: 80;
  transition: none;
  align-items: center;
  will-change: left, top, transform;
}
.butler-wrap.is-dragging .butler-fab { transform: none; cursor: grabbing; }

/* 问答页：底部有输入栏+发送按钮，锚点抬到输入栏上方 */
.butler-wrap.anchor-assistant { bottom: calc(54px + env(safe-area-inset-bottom, 0px) + 92px); }
/* 白友圈：右下角有"新增帖子"按钮（48px + 24px 间隙） */
.butler-wrap.anchor-community { bottom: calc(54px + env(safe-area-inset-bottom, 0px) + 84px); }

@media (min-width: 768px) {
  .butler-wrap { bottom: 24px; }
  .butler-wrap.pos-right { right: 24px; }
  /* 桌面端左侧有侧边栏，靠左时从侧边栏右侧起算 */
  .butler-wrap.pos-left { left: calc(var(--app-sidebar-w) + 24px); }
  .butler-wrap.anchor-assistant { bottom: 108px; }
  .butler-wrap.anchor-community { bottom: 148px; }
}

.butler-fab-outer {
  position: relative;
}
.butler-fab-outer.is-moving {
  animation: bm-travel 0.95s cubic-bezier(0.34, 1.2, 0.5, 1);
}
@keyframes bm-travel {
  0% { transform: translateY(0) scaleY(1); }
  25% { transform: translateY(-14px) scaleY(1.05); }
  50% { transform: translateY(2px) scaleY(0.94) scaleX(1.05); }
  70% { transform: translateY(-7px); }
  100% { transform: translateY(0) scaleY(1); }
}

.butler-fab {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
  transition: transform 0.15s ease;
  border: none;
  background: #fff;
  padding: 0;
  cursor: pointer;
}
.butler-fab:active {
  transform: scale(0.9);
}
.butler-fab:hover {
  transform: translateY(-2px);
}
/* 长按拖动需要接管触摸手势：禁用触摸滚动/双击缩放/长按系统菜单 */
.butler-fab {
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}

/* 拖动提示气泡（跟随按钮上方） */
.drag-hint {
  position: absolute;
  top: -38px;
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
  padding: 5px 10px;
  border-radius: 10px;
  background: rgba(17, 24, 39, 0.85);
  color: #fff;
  font-size: 11px;
  line-height: 1;
  pointer-events: none;
  z-index: 1;
}

/* 写实/图片形象：轻微漂浮呼吸感 */
.butler-fab-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  animation: img-float 3.4s ease-in-out infinite;
}
@keyframes img-float {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-1.5px) rotate(1.2deg); }
}
@media (prefers-reduced-motion: reduce) {
  .butler-fab-img { animation: none; }
}

/* 边缘偷看时的图片形象 */
.butler-peek-img {
  width: 64px;
  height: 64px;
  object-fit: cover;
  animation: img-float 3.4s ease-in-out infinite;
}

/* 隐藏按钮：hover 时浮现 */
.butler-hide-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 22px;
  height: 22px;
  border-radius: 9999px;
  background: #374151;
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease, transform 0.15s ease;
  cursor: pointer;
  border: 1.5px solid #fff;
}
.group:hover .butler-hide-btn {
  opacity: 1;
  pointer-events: auto;
}
.butler-hide-btn:hover {
  transform: scale(1.12);
  background: #111827;
}

/* ── 边缘偷看模式 ── */
.butler-peek {
  position: fixed;
  z-index: 60;
  top: 42vh;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  transition: transform 0.2s ease;
}
.butler-peek.peek-right { right: 0; transform: translateX(52%); }
.butler-peek.peek-left { left: var(--app-sidebar-w); transform: translateX(-52%); }
.butler-peek:hover {
  transform: translateX(38%);
}
.butler-peek.peek-left:hover {
  transform: translateX(-38%);
}
.butler-peek-enter-active,
.butler-peek-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.butler-peek-enter-from,
.butler-peek-leave-to {
  opacity: 0;
}
.butler-peek-enter-from.peek-right,
.butler-peek-leave-to.peek-right {
  transform: translateX(105%);
}
.butler-peek-enter-from.peek-left,
.butler-peek-leave-to.peek-left {
  transform: translateX(-105%);
}

/* 招呼气泡 */
.butler-bubble {
  max-width: 200px;
  padding: 8px 12px;
  border-radius: 14px 14px 14px 4px;
  background: #fff;
  border: 1px solid var(--color-primary-100, #d1e7e4);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  font-size: 12px;
  color: #374151;
  text-align: left;
  cursor: pointer;
  animation: bubble-pop 0.3s ease;
}
:global(.dark) .butler-bubble {
  background: #1f2937;
  color: #e5e7eb;
  border-color: #374151;
}
@keyframes bubble-pop {
  from { transform: translateY(6px) scale(0.9); opacity: 0; }
  to { transform: translateY(0) scale(1); opacity: 1; }
}

.butler-bubble-enter-active,
.butler-bubble-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.butler-bubble-enter-from,
.butler-bubble-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
