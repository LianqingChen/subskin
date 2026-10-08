<script setup lang="ts">
import { useMainNav } from '@/composables/useMainNav'

const { navItems } = useMainNav()
</script>

<template>
  <div class="page-narrow flex flex-1 flex-col items-center justify-center py-16 text-center md:py-24">
    <p class="text-6xl font-bold tracking-tight text-primary-100 dark:text-gray-800 md:text-7xl" aria-hidden="true">404</p>
    <h1 class="mt-4 text-xl font-bold text-gray-900 dark:text-white">页面不存在</h1>
    <p class="mt-2 max-w-sm text-sm leading-relaxed text-gray-500 dark:text-gray-400">
      您访问的页面可能已被移除或地址有误，回到首页继续浏览吧。
    </p>
    <router-link to="/" class="btn-primary mt-6 inline-flex min-h-[44px] items-center gap-1.5 px-6 text-sm no-underline">
      <i class="ri-home-5-line" aria-hidden="true"></i>
      返回首页
    </router-link>

    <!-- 常用入口 -->
    <div class="mt-10 grid w-full max-w-md grid-cols-4 gap-2">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="flex flex-col items-center gap-1.5 rounded-xl py-3 text-xs text-gray-600 no-underline transition-colors hover:bg-white hover:text-primary-700 dark:text-gray-300 dark:hover:bg-gray-800"
      >
        <i :class="item.iconClass" class="text-xl" aria-hidden="true"></i>
        {{ item.label }}
      </router-link>
    </div>
  </div>
</template>
