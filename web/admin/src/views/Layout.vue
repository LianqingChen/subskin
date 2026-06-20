<template>
  <n-layout has-sider style="height: 100vh">
    <!-- Desktop sidebar -->
    <n-layout-sider
      v-show="!isMobile"
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="240"
      :collapsed="collapsed"
      show-trigger
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <div class="logo">
        <i class="ri-shield-keyhole-line" />
        <span v-show="!collapsed">SubSkin</span>
      </div>
      <n-menu
        :collapsed="collapsed"
        :collapsed-width="64"
        :collapsed-icon-size="22"
        :options="menuOptions"
        :value="activeKey"
        @update:value="handleMenuSelect"
      />
    </n-layout-sider>

    <!-- Mobile drawer - custom overlay (Naive UI n-drawer portal buggy on mobile) -->
    <div v-if="mobileDrawerOpen" class="mobile-drawer-overlay" @click="mobileDrawerOpen = false">
      <div class="mobile-drawer" @click.stop>
        <div class="drawer-header">
          <i class="ri-shield-keyhole-line" />
          <span>SubSkin 管理后台</span>
        </div>
        <div class="drawer-menu">
          <div
            v-for="item in menuItems"
            :key="item.key"
            class="drawer-menu-item"
            :class="{ active: activeKey === item.key }"
            @click="handleMenuSelectMobile(item.key)"
          >
            <i :class="item.iconClass" />
            <span>{{ item.label }}</span>
          </div>
        </div>
      </div>
    </div>

    <n-layout>
      <n-layout-header bordered class="layout-header">
        <div class="header-left">
          <h2>SubSkin 管理后台</h2>
        </div>
        <div class="header-right">
          <n-dropdown :options="userOptions" @select="handleUserAction">
            <div class="user-info">
              <n-avatar round size="small" :style="{ backgroundColor: '#6366f1' }">
                {{ userInitials }}
              </n-avatar>
              <span class="username">{{ authStore.user?.username || '管理员' }}</span>
              <i class="ri-arrow-down-s-line" />
            </div>
          </n-dropdown>
        </div>
      </n-layout-header>
      <n-layout-content class="layout-content">
        <router-view />
      </n-layout-content>

      <!-- Mobile bottom nav -->
      <div v-if="isMobile" class="mobile-bottom-nav">
        <div
          v-for="item in bottomNavItems"
          :key="item.key"
          class="bottom-nav-item"
          :class="{ active: activeKey === item.key }"
          @click="handleMenuSelect(item.key)"
        >
          <i :class="item.icon" />
          <span>{{ item.label }}</span>
        </div>
      </div>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NIcon } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const collapsed = ref(false)
const mobileDrawerOpen = ref(false)
const isMobile = ref(false)

const activeKey = computed(() => route.name as string)

const userInitials = computed(() => {
  const name = authStore.user?.username || 'A'
  return name.charAt(0).toUpperCase()
})

function renderIcon(iconClass: string) {
  return () => h(NIcon, null, { default: () => h('i', { class: iconClass }) })
}

const menuItems = [
  { label: '数据监控', key: 'Dashboard', iconClass: 'ri-dashboard-line' },
  { label: '内容生成', key: 'ContentGen', iconClass: 'ri-article-line' },
  { label: '风控管理', key: 'Moderation', iconClass: 'ri-shield-check-line' },
  { label: '用户管理', key: 'UserManagement', iconClass: 'ri-user-settings-line' },
  { label: 'LLM配置', key: 'LLMConfig', iconClass: 'ri-cpu-line' },
  { label: '图片打标', key: 'ImageLabeling', iconClass: 'ri-image-line' },
  { label: '训练数据', key: 'TrainingDashboard', iconClass: 'ri-database-2-line' },
  { label: '系统监控', key: 'SystemMonitor', iconClass: 'ri-server-line' },
]

const menuOptions = menuItems.map(item => ({
  label: item.label,
  key: item.key,
  icon: renderIcon(item.iconClass),
}))

const bottomNavItems = [
  { key: 'Dashboard', label: '监控', icon: 'ri-dashboard-line' },
  { key: 'Moderation', label: '风控', icon: 'ri-shield-check-line' },
  { key: 'ImageLabeling', label: '打标', icon: 'ri-image-line' },
  { key: 'LLMConfig', label: 'LLM', icon: 'ri-cpu-line' },
  { key: 'more', label: '更多', icon: 'ri-menu-line' },
]

function handleMenuSelect(key: string) {
  if (key === 'more') {
    mobileDrawerOpen.value = true
    return
  }
  const map: Record<string, string> = {
    Dashboard: '/dashboard',
    UserManagement: '/users',
    Moderation: '/moderation',
    ContentGen: '/content-gen',
    LLMConfig: '/llm-config',
    ImageLabeling: '/image-labeling',
    TrainingDashboard: '/training',
    SystemMonitor: '/system-monitor'
  }
  router.push(map[key] || '/')
}

function handleMenuSelectMobile(key: string) {
  handleMenuSelect(key)
  mobileDrawerOpen.value = false
}

const userOptions = [
  { label: '退出登录', key: 'logout' }
]

function handleUserAction(key: string) {
  if (key === 'logout') {
    authStore.logout()
  }
}

function checkMobile() {
  isMobile.value = window.innerWidth <= 768
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 700;
  color: #f8fafc;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo i {
  font-size: 28px;
  color: #6366f1;
}

.layout-header {
  height: 64px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(15, 23, 42, 0.8);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #f8fafc;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.2s;
}

.user-info:hover {
  background: rgba(255, 255, 255, 0.06);
}

.username {
  color: #e2e8f0;
  font-size: 14px;
}

.layout-content {
  padding: 24px;
  background: #0f172a;
  overflow-x: auto;
  padding-bottom: calc(24px + env(safe-area-inset-bottom, 0px));
}

@media (max-width: 768px) {
  .layout-header {
    padding: 0 12px;
  }

  .header-left h2 {
    font-size: 15px;
  }

  .username {
    display: none;
  }

  .layout-content {
    padding: 12px;
    padding-bottom: calc(72px + env(safe-area-inset-bottom, 0px));
  }
}

.mobile-bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: calc(60px + env(safe-area-inset-bottom, 0px));
  background: #1e293b;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  display: flex;
  align-items: flex-start;
  justify-content: space-around;
  z-index: 1000;
  padding-top: 6px;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}

.bottom-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 4px 8px;
  cursor: pointer;
  color: #64748b;
  transition: color 0.15s;
  -webkit-tap-highlight-color: transparent;
}

.bottom-nav-item i {
  font-size: 20px;
  line-height: 1;
}

.bottom-nav-item span {
  font-size: 10px;
  line-height: 1;
}

.bottom-nav-item.active {
  color: #6366f1;
}

.bottom-nav-item:active {
  color: #818cf8;
}

/* ── Mobile drawer ── */
.mobile-drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
}
.mobile-drawer {
  width: 260px;
  max-width: 80vw;
  height: 100%;
  background: #1e293b;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.drawer-header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #f8fafc;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}
.drawer-header i {
  font-size: 24px;
  color: #6366f1;
}
.drawer-menu {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.drawer-menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  font-size: 15px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s;
  -webkit-tap-highlight-color: transparent;
}
.drawer-menu-item i {
  font-size: 20px;
  width: 24px;
  text-align: center;
}
.drawer-menu-item:active {
  background: rgba(99, 102, 241, 0.15);
  color: #c7d2fe;
}
.drawer-menu-item.active {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  font-weight: 600;
}
</style>
