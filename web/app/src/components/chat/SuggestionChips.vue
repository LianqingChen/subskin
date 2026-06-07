<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  suggestions: string[]
}>()

const emit = defineEmits<{
  select: [text: string]
}>()

const hotCount = 3
const laneCount = 2

interface LaneItem {
  text: string
  isHot: boolean
}

/**
 * Split suggestions into lanes (round-robin distribution),
 * then triple each lane's items for seamless infinite CSS marquee loop.
 *
 * Using 3x content with translateX(-33.333%) ensures the track is always
 * wider than the container, eliminating visual gaps.
 */
const lanes = computed<LaneItem[][]>(() => {
  if (props.suggestions.length === 0) return []

  return Array.from({ length: laneCount }, (_, laneIdx) => {
    // Round-robin: lane 0 gets indices 0,2,4... lane 1 gets 1,3,5...
    const questions: string[] = []
    for (let i = laneIdx; i < props.suggestions.length; i += laneCount) {
      questions.push(props.suggestions[i])
    }

    const enriched = questions.map((text) => ({
      text,
      isHot: props.suggestions.indexOf(text) < hotCount,
    }))

    // 3x duplication: sufficient width for seamless marquee on any screen
    return [...enriched, ...enriched, ...enriched]
  })
})

// Speed per lane: slow enough to read, fast enough to feel like danmaku
// Track moves ~33.3% of its width per cycle. With ~1700px track, that's ~570px.
// At 14s: 570/14 ≈ 41 px/s → ~14s to cross screen ✓ easily readable
// At 17s: 570/17 ≈ 34 px/s → ~17s to cross ✓ relaxed reading
const laneSpeeds = [14, 17]

// Small negative delays to stagger lanes on load
const laneDelays = [-4, -1]

function handleSelect(text: string) {
  emit('select', text)
}
</script>

<template>
  <!-- Empty state: render nothing when no suggestions -->
  <div v-if="lanes.length === 0"></div>

  <div
    v-else
    class="danmaku-container w-full overflow-hidden py-3 select-none"
    aria-label="推荐问题"
  >
    <!-- Pause all lanes on container hover -->
    <div
      v-for="(lane, laneIdx) in lanes"
      :key="laneIdx"
      class="danmaku-lane relative h-10 overflow-hidden"
      :class="{ 'mt-3': laneIdx > 0 }"
    >
      <!-- Scrolling track: 3x content for seamless marquee loop -->
      <div
        class="danmaku-track flex items-center gap-3 w-max"
        :style="{
          animation: `subskin-danmaku-marquee ${laneSpeeds[laneIdx]}s linear ${laneDelays[laneIdx]}s infinite`,
        }"
      >
        <button
          v-for="(item, idx) in lane"
          :key="`${laneIdx}-${idx}`"
          class="danmaku-chip inline-flex items-center px-3.5 py-2 rounded-full text-sm border whitespace-nowrap
                 cursor-pointer shrink-0 transition-colors duration-150 min-h-[44px]"
          :class="[
            item.isHot
              ? 'border-red-200/80 bg-red-50/90 text-gray-700 dark:border-red-700/60 dark:bg-red-900/40 dark:text-red-200 hover:!border-red-400 hover:!bg-red-100 dark:hover:!border-red-500 dark:hover:!bg-red-900/60 font-medium shadow-sm'
              : 'border-gray-200/80 dark:border-gray-600/60 text-gray-600  bg-white/80  hover:!border-primary-400 hover:!text-primary-600 dark:hover:!text-primary-400 hover:!bg-primary-50/90 dark:hover:!bg-primary-900/40 shadow-sm',
          ]"
          @click.stop="handleSelect(item.text)"
        >
          <!-- Hot indicator: RemixIcon fire icon -->
          <span v-if="item.isHot" class="text-red-500 mr-1 flex items-center">
            <i class="ri-fire-line text-[15px]"></i>
          </span>
          {{ item.text }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Component-scoped styles */
</style>

<style>
/* Pause ALL lanes when hovering anywhere in the container */
.danmaku-container:hover .danmaku-track {
  animation-play-state: paused;
}

/*
 * CSS marquee: track contains 3x content (original + 2 duplicates).
 * Moving from translateX(0) to translateX(-33.333%) slides by exactly
 * one copy-width, bringing the next duplicate into the same position.
 * 3x ensures the track is always wider than the container — no gaps.
 */
@keyframes subskin-danmaku-marquee {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-33.333%);
  }
}
</style>
