<script setup lang="ts">
/**
 * GlobalFooter — 全站统一页脚声明
 * 所有页面底端只放这一句话：本平台不构成医疗建议，所有内容仅供参考。
 * 移动端自带 BottomNav（fixed 54px + safe-area）避让间距。
 */
</script>

<template>
  <footer class="w-full shrink-0">
    <p class="text-center text-xs text-gray-400 dark:text-gray-500 px-4 py-4 border-t border-gray-100 dark:border-gray-800/60">
      本平台不构成医疗建议，所有内容仅供参考。
    </p>
    <!-- 移动端为 fixed BottomNav 留出空间，保证滚动到底时这句话不被导航遮挡 -->
    <div class="h-[calc(54px+env(safe-area-inset-bottom,0px))] md:hidden" aria-hidden="true"></div>
  </footer>
</template>
