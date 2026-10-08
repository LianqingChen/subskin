<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useMainNav } from '@/composables/useMainNav'

const isHidden = ref(false)
const lastScrollY = ref(0)
const scrollThreshold = 80

const { navItems, isNavActive } = useMainNav()
const isActive = (item: { path: string }) => isNavActive(item.path)

function handleScroll() {
  const currentY = window.scrollY
  const delta = currentY - lastScrollY.value
  if (delta > 10 && currentY > scrollThreshold) {
    isHidden.value = true
  } else if (delta < -5 || currentY < scrollThreshold) {
    isHidden.value = false
  }
  lastScrollY.value = currentY
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<template>
  <nav
    class="bottom-nav"
    :class="{ 'bottom-nav--hidden': isHidden }"
    role="navigation"
    aria-label="主导航"
  >
    <router-link
      v-for="item in navItems"
      :key="item.label"
      :to="item.path"
      class="bottom-nav__item"
      :class="{ 'bottom-nav__item--active': isActive(item) }"
      :data-track-id="`bottom_nav_${item.label}`"
    >
      <div class="bottom-nav__icon-wrapper" :class="{ 'bottom-nav__icon-wrapper--active': isActive(item) }">
        <i :class="item.iconClass" class="bottom-nav__icon"></i>
      </div>
      <span class="bottom-nav__label">{{ item.label }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 50;
  display: flex;
  flex-direction: row;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-top: 1px solid rgba(229, 231, 235, 0.9);
  padding-bottom: env(safe-area-inset-bottom, 0px);
  transform: translateY(0);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.bottom-nav--hidden {
  transform: translateY(100%);
}

html.dark .bottom-nav {
  background: rgba(15, 23, 42, 0.94);
  border-top-color: rgba(31, 41, 55, 0.9);
}

.bottom-nav__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 6px 0;
  flex: 1;
  min-height: 54px;
  text-decoration: none;
  color: #94a3b8;
  transition: color 0.2s ease;
  -webkit-tap-highlight-color: transparent;
  position: relative;
}

html.dark .bottom-nav__item {
  color: #64748b;
}

.bottom-nav__item--active {
  color: var(--color-primary-600);
}

html.dark .bottom-nav__item--active {
  color: var(--color-primary-400);
}

.bottom-nav__icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 28px;
  border-radius: 10px;
  transition: all 0.25s ease;
}

.bottom-nav__icon-wrapper--active {
  background: rgba(20, 184, 166, 0.1);
  background: color-mix(in srgb, var(--color-primary-500) 10%, transparent);
}

.bottom-nav__icon {
  font-size: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  transition: transform 0.2s ease, stroke 0.2s ease;
}

.bottom-nav__item:active .bottom-nav__icon {
  transform: scale(0.88);
}

.bottom-nav__item--active .bottom-nav__icon {
  transform: scale(1.04);
}

.bottom-nav__label {
  font-size: 10px;
  font-weight: 500;
  line-height: 1.2;
  letter-spacing: 0.02em;
}

.bottom-nav__item--active .bottom-nav__label {
  font-weight: 600;
}

@media (min-width: 768px) {
  .bottom-nav {
    display: none;
  }
}
</style>
