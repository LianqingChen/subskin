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
        { path: 'planning', name: 'PlanningArchive', component: () => import('@/views/PlanningArchive.vue') },
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
          path: 'hospital-risk',
          name: 'HospitalRisk',
          component: () => import('@/views/HospitalRisk.vue')
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
          path: 'prompt-config',
          name: 'PromptConfig',
          component: () => import('@/views/PromptConfig.vue')
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
          path: 'site-maintenance',
          name: 'SiteMaintenance',
          component: () => import('@/views/SiteMaintenance.vue')
        },
        { path: 'system-monitor', redirect: '/site-maintenance' },
        { path: 'terminal', redirect: '/site-maintenance' }

      ]
    }
  ]
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()
  // Session restore: token persists in localStorage but user is memory-only,
  // so without this a page refresh would bounce a valid session to /login.
  if (authStore.isLoggedIn && !authStore.user) {
    await authStore.fetchUser()
  }
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
