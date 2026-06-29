import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { public: true }
    },
    {
      path: '/',
      name: 'Layout',
      component: () => import('@/views/Layout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/Dashboard.vue')
        },
        {
          path: 'users',
          name: 'UserManagement',
          component: () => import('@/views/UserManagement.vue')
        },
        {
          path: 'moderation',
          name: 'Moderation',
          component: () => import('@/views/Moderation.vue')
        },
        {
          path: 'content-gen',
          name: 'ContentGen',
          component: () => import('@/views/ContentGen.vue')
        },
        {
          path: 'llm-config',
          name: 'LLMConfig',
          component: () => import('@/views/LLMConfig.vue')
        },
        {
          path: 'image-labeling',
          name: 'ImageLabeling',
          component: () => import('@/views/ImageLabeling.vue')
        },
        {
          path: 'image-labeling/:id',
          name: 'LabelingWorkspace',
          component: () => import('@/views/LabelingWorkspace.vue'),
          meta: { fullscreen: true }
        },
        {
          path: 'training',
          name: 'TrainingDashboard',
          component: () => import('@/views/TrainingDashboard.vue')
        },
        {
          path: 'system-monitor',
          name: 'SystemMonitor',
          component: () => import('@/views/SystemMonitor.vue')
        }
      ]
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  // Admin SPA is admin-only: a logged-in non-admin must not access any route
  // (even if they reuse a main-app token). Redirect to login with a notice.
  if (!to.meta.public && (!authStore.isLoggedIn || !authStore.user?.is_admin)) {
    next('/login')
  } else if (to.path === '/login' && authStore.isLoggedIn && authStore.user?.is_admin) {
    next('/')
  } else {
    next()
  }
})

export default router
