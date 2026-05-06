import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'assistant',
      component: () => import('@/views/ChatAssistantPage.vue'),
    },
    {
      path: '/assessment',
      name: 'assessment',
      component: () => import('@/views/AssessmentPage.vue'),
    },
    {
      path: '/voice-call',
      name: 'voice-call',
      component: () => import('@/views/VoiceCallPage.vue'),
    },
    {
      path: '/chat',
      redirect: '/',
    },
    {
      path: '/tracker',
      redirect: '/assessment',
    },
    {
      path: '/photo-guide',
      name: 'photo-guide',
      component: () => import('@/views/PhotoGuidePage.vue'),
    },
    {
      path: '/tracker/report/:id',
      name: 'report-detail',
      component: () => import('@/views/ReportDetailPage.vue'),
    },
    {
      path: '/report',
      name: 'report',
      component: () => import('@/views/ReportPage.vue'),
    },
    {
      path: '/report/compare',
      name: 'ReportCompare',
      component: () => import('@/views/ReportComparePage.vue'),
      meta: { title: '报告对比' }
    },
    {
      path: '/community',
      name: 'community',
      component: () => import('@/views/CommunityPage.vue'),
    },
    {
      path: '/community/new',
      name: 'community-new',
      component: () => import('@/views/CommunityEditorPage.vue'),
    },
    {
      path: '/community/drafts',
      name: 'community-drafts',
      component: () => import('@/views/DraftsPage.vue'),
    },
    {
      path: '/community/:id/edit',
      name: 'community-edit',
      component: () => import('@/views/CommunityEditorPage.vue'),
    },
    {
      path: '/community/:id',
      name: 'post-detail',
      component: () => import('@/views/PostDetailPage.vue'),
    },
    {
      path: '/collection/:slug',
      name: 'collection-share',
      component: () => import('@/views/CollectionSharePage.vue'),
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/ProfilePage.vue'),
    },
    {
      path: '/user/:userId',
      name: 'user-profile',
      component: () => import('@/views/UserProfilePage.vue'),
    },
    {
      path: '/encyclopedia',
      name: 'encyclopedia',
      component: () => import('@/views/EncyclopediaNewPage.vue'),
      meta: { title: '小白百科' },
    },
    {
      path: '/encyclopedia/:slug(.*)*',
      name: 'encyclopedia-article',
      component: () => import('@/views/EncyclopediaNewPage.vue'),
      meta: { title: '小白百科' },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardPage.vue'),
    },
    {
      path: '/privacy',
      name: 'privacy',
      component: () => import('@/views/PrivacyPolicyPage.vue'),
    },
    {
      path: '/terms',
      name: 'terms',
      component: () => import('@/views/TermsOfServicePage.vue'),
    },
    {
      path: '/messages',
      name: 'messages',
      component: () => import('@/views/MessagesPage.vue'),
    },
    {
      path: '/chat/:id',
      name: 'chat-room',
      component: () => import('@/views/ChatRoomPage.vue'),
    },
    {
      path: '/contacts',
      name: 'contacts',
      component: () => import('@/views/ContactsPage.vue'),
    },
    {
      path: '/group/:id',
      name: 'group-info',
      component: () => import('@/views/GroupInfoPage.vue'),
    },
  ],
  scrollBehavior(to, _from, savedPosition) {
    if (to.hash) {
      return { el: to.hash, behavior: 'smooth' }
    }
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

router.afterEach((to) => {
  import('@/composables/useTracking').then(({ trackPageView }) => {
    trackPageView(to.path)
  })
})

export default router