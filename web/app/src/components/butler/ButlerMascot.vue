<script setup lang="ts">
/**
 * 小白管家动画吉祥物（SVG 伪 3D 毛绒质感）：白色圆身体 + 呼应品牌 Logo 的橙色蝴蝶翅膀。
 * 常驻：呼吸浮动、翅膀扇动、眨眼、眼珠左右环视；
 * 心情：idle 微笑 / happy ^ ^ 开心 / thinking 思考+气泡点 / greeting 挥手+张嘴笑；
 * flying：小范围移动时的飞行姿态（翅膀加速、身体轻晃）。
 */
defineProps<{
  mood?: 'idle' | 'happy' | 'thinking' | 'greeting'
  size?: number
  flying?: boolean
}>()
</script>

<template>
  <div class="butler-mascot" :class="{ 'is-flying': flying }" :style="{ width: (size ?? 56) + 'px', height: (size ?? 56) + 'px' }" aria-hidden="true">
    <svg viewBox="0 0 120 120" class="w-full h-full">
      <defs>
        <radialGradient id="bm-body" cx="36%" cy="28%" r="85%">
          <stop offset="0%" stop-color="#ffffff" />
          <stop offset="55%" stop-color="#f7f8fa" />
          <stop offset="85%" stop-color="#e7ebef" />
          <stop offset="100%" stop-color="#cfd6dd" />
        </radialGradient>
        <radialGradient id="bm-ear" cx="35%" cy="30%" r="80%">
          <stop offset="0%" stop-color="#ffffff" />
          <stop offset="100%" stop-color="#dde2e8" />
        </radialGradient>
        <linearGradient id="bm-wing-l" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#ffc078" />
          <stop offset="100%" stop-color="#ff8c42" />
        </linearGradient>
        <linearGradient id="bm-wing-r" x1="1" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#ffc078" />
          <stop offset="100%" stop-color="#ff8c42" />
        </linearGradient>
        <radialGradient id="bm-cheek" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#ff9d9d" stop-opacity="0.55" />
          <stop offset="100%" stop-color="#ff9d9d" stop-opacity="0" />
        </radialGradient>
      </defs>

      <!-- 思考气泡点（thinking） -->
      <g v-if="mood === 'thinking'" class="bm-dots">
        <circle cx="94" cy="32" r="2.4" fill="#9aa3af" class="bm-dot" />
        <circle cx="102" cy="23" r="3.4" fill="#9aa3af" class="bm-dot bm-dot-2" />
        <circle cx="109" cy="13" r="4.4" fill="#9aa3af" class="bm-dot bm-dot-3" />
      </g>

      <!-- 身体整体：呼吸浮动 / 飞行轻晃 -->
      <g class="bm-bob">
        <!-- 翅膀（呼应 Logo，扇动；飞行时加速） -->
        <g class="bm-wing bm-wing-l">
          <path d="M54 56 C32 26 8 30 11 50 C13 65 32 71 52 69 Z" fill="url(#bm-wing-l)" opacity="0.94" />
          <path d="M53 71 C32 71 13 82 18 95 C23 106 45 97 53 80 Z" fill="url(#bm-wing-l)" opacity="0.78" />
        </g>
        <g class="bm-wing bm-wing-r">
          <path d="M66 56 C88 26 112 30 109 50 C107 65 88 71 68 69 Z" fill="url(#bm-wing-r)" opacity="0.94" />
          <path d="M67 71 C88 71 107 82 102 95 C97 106 75 97 67 80 Z" fill="url(#bm-wing-r)" opacity="0.78" />
        </g>

        <!-- 挥手的小手臂（greeting） -->
        <g class="bm-arm" :class="{ 'bm-arm-wave': mood === 'greeting' }">
          <rect x="88" y="62" width="13" height="7" rx="3.5" fill="#e4e9ee" />
          <circle cx="102" cy="65.5" r="5" fill="#f4f6f9" stroke="#d5dbe2" stroke-width="1.2" />
        </g>

        <!-- 耳朵 -->
        <circle cx="40" cy="34" r="11" fill="url(#bm-ear)" />
        <circle cx="80" cy="34" r="11" fill="url(#bm-ear)" />
        <circle cx="40" cy="34" r="5.5" fill="#ffd9b8" opacity="0.8" />
        <circle cx="80" cy="34" r="5.5" fill="#ffd9b8" opacity="0.8" />

        <!-- 身体 -->
        <ellipse cx="60" cy="66" rx="33" ry="32" fill="url(#bm-body)" />
        <!-- 底部环境光遮蔽 + 右侧轮廓光，增强体积感 -->
        <ellipse cx="60" cy="84" rx="24" ry="12" fill="#3d4451" opacity="0.05" />
        <path d="M84 46 C92 56 92 76 82 88 C90 74 90 58 84 46 Z" fill="#ffffff" opacity="0.7" />
        <!-- 头顶高光 -->
        <ellipse cx="48" cy="47" rx="13" ry="8" fill="#ffffff" opacity="0.6" />

        <!-- 小脚 -->
        <ellipse cx="48" cy="95" rx="7" ry="4.5" fill="#e4e9ee" />
        <ellipse cx="72" cy="95" rx="7" ry="4.5" fill="#e4e9ee" />

        <!-- 脸部 -->
        <g class="bm-face">
          <!-- 眼睛：含眨眼与眼珠环视 -->
          <g v-if="mood !== 'happy'">
            <g class="bm-eye">
              <ellipse cx="48" cy="63" rx="4.6" ry="5" fill="#333a45" />
            </g>
            <g class="bm-eye">
              <ellipse cx="72" cy="63" rx="4.6" ry="5" fill="#333a45" />
            </g>
            <!-- 眼珠高光（整体环视移动） -->
            <g class="bm-glance">
              <circle cx="49.6" cy="61.4" r="1.7" fill="#fff" />
              <circle cx="73.6" cy="61.4" r="1.7" fill="#fff" />
              <circle cx="46.8" cy="64.8" r="0.8" fill="#fff" opacity="0.7" />
              <circle cx="70.8" cy="64.8" r="0.8" fill="#fff" opacity="0.7" />
            </g>
          </g>
          <!-- happy: ^ ^ 眼 -->
          <path v-if="mood === 'happy'" d="M43 64 Q48 57.5 53 64" stroke="#333a45" stroke-width="2.8" fill="none" stroke-linecap="round" />
          <path v-if="mood === 'happy'" d="M67 64 Q72 57.5 77 64" stroke="#333a45" stroke-width="2.8" fill="none" stroke-linecap="round" />

          <!-- 思考眉（上挑） -->
          <path v-if="mood === 'thinking'" d="M43 54 Q48 52 53 54" stroke="#8b939f" stroke-width="1.8" fill="none" stroke-linecap="round" />
          <path v-if="mood === 'thinking'" d="M67 54 Q72 52 77 54" stroke="#8b939f" stroke-width="1.8" fill="none" stroke-linecap="round" />

          <!-- 腮红 -->
          <ellipse cx="41" cy="73" rx="7" ry="4.5" fill="url(#bm-cheek)" />
          <ellipse cx="79" cy="73" rx="7" ry="4.5" fill="url(#bm-cheek)" />

          <!-- 鼻子 -->
          <ellipse cx="60" cy="70" rx="2.6" ry="1.9" fill="#ffb98a" />

          <!-- 嘴：微笑 / 开心张嘴 / 思考 o 型 -->
          <path v-if="mood === 'idle' || mood === 'greeting'" d="M54 75 Q60 81 66 75" stroke="#333a45" stroke-width="2.4" fill="none" stroke-linecap="round" />
          <path v-else-if="mood === 'happy'" d="M52 74 Q60 85 68 74 Z" fill="#ff8c42" stroke="#333a45" stroke-width="1.6" stroke-linejoin="round" />
          <ellipse v-else cx="60" cy="77" rx="3.6" ry="4.4" fill="#ff8c42" opacity="0.9" />
        </g>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.butler-mascot {
  position: relative;
  filter: drop-shadow(0 5px 9px rgba(61, 68, 81, 0.28));
}

/* 呼吸浮动（飞行时改为左右轻晃） */
.bm-bob {
  animation: bm-bob 3.2s ease-in-out infinite;
  transform-box: fill-box;
  transform-origin: center bottom;
}
.is-flying .bm-bob {
  animation: bm-fly 0.9s ease-in-out infinite;
  transform-origin: center;
}
@keyframes bm-bob {
  0%, 100% { transform: translateY(0) scaleY(1); }
  50% { transform: translateY(-2.5px) scaleY(1.02); }
}
@keyframes bm-fly {
  0%, 100% { transform: rotate(-5deg) translateY(0); }
  50% { transform: rotate(5deg) translateY(-3px); }
}

/* 翅膀扇动（飞行时加速） */
.bm-wing {
  transform-box: fill-box;
  animation: bm-flap 2.6s ease-in-out infinite;
}
.is-flying .bm-wing {
  animation-duration: 0.32s;
}
.bm-wing-l { transform-origin: right center; }
.bm-wing-r { transform-origin: left center; }
@keyframes bm-flap {
  0%, 100% { transform: scaleX(1); }
  50% { transform: scaleX(0.7); }
}

/* 眨眼 */
.bm-eye {
  animation: bm-blink 4.4s infinite;
  transform-box: fill-box;
  transform-origin: center;
}
@keyframes bm-blink {
  0%, 91%, 100% { transform: scaleY(1); }
  94%, 96% { transform: scaleY(0.08); }
}

/* 眼珠环视：左看 → 回中 → 右上看 → 回中 */
.bm-glance {
  animation: bm-glance 9s ease-in-out infinite;
}
@keyframes bm-glance {
  0%, 18% { transform: translate(0, 0); }
  24%, 40% { transform: translate(-2.2px, 0.4px); }
  46%, 60% { transform: translate(0, 0); }
  66%, 82% { transform: translate(2px, -1.4px); }
  88%, 100% { transform: translate(0, 0); }
}

/* 挥手 */
.bm-arm {
  transform-box: fill-box;
  transform-origin: left center;
  transition: transform 0.2s ease;
}
.bm-arm-wave {
  animation: bm-wave 0.9s ease-in-out infinite;
}
@keyframes bm-wave {
  0%, 100% { transform: rotate(0deg); }
  30% { transform: rotate(-38deg); }
  60% { transform: rotate(-14deg); }
}

/* 思考气泡点跳动 */
.bm-dot {
  animation: bm-dot-jump 1.2s ease-in-out infinite;
  transform-box: fill-box;
}
.bm-dot-2 { animation-delay: 0.15s; }
.bm-dot-3 { animation-delay: 0.3s; }
@keyframes bm-dot-jump {
  0%, 100% { transform: translateY(0); opacity: 0.5; }
  50% { transform: translateY(-3px); opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .bm-bob, .bm-wing, .bm-eye, .bm-glance, .bm-arm-wave, .bm-dot { animation: none; }
}
</style>
