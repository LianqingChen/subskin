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
      path: '/contribution',
      name: 'contribution',
      component: () => import('@/views/ContributionPage.vue'),
      meta: { title: '同行' },
    },
    {
      path: '/care',
      name: 'care',
      component: () => import('@/views/CarePage.vue'),
      meta: { title: '调养' },
    },
    {
      path: '/care/:id',
      name: 'care-product',
      component: () => import('@/views/CareProductPage.vue'),
      meta: { title: '商品详情' },
    },
    {
      path: '/discover/science',
      name: 'discover-science',
      component: () => import('@/views/DiscoverSciencePage.vue'),
      meta: { title: '科普' },
    },
    {
      path: '/discover/picks',
      name: 'discover-picks',
      component: () => import('@/views/DiscoverPicksPage.vue'),
      meta: { title: '种草' },
    },
    {
      path: '/hospitals',
      name: 'hospitals',
      component: () => import('@/views/HospitalsPage.vue'),
      meta: { title: '就医经验' },
    },
    {
      path: '/hospitals/treatments',
      name: 'hospital-treatments',
      component: () => import('@/views/HospitalTreatmentsPage.vue'),
      meta: { title: '治疗知识' },
    },
    {
      path: '/hospitals/rules',
      name: 'hospital-rules',
      component: () => import('@/views/HospitalRulesPage.vue'),
      meta: { title: '就医经验社区公约' },
    },
    {
      path: '/hospitals/appeal',
      name: 'hospital-appeal',
      component: () => import('@/views/HospitalAppealPage.vue'),
      meta: { title: '评价申诉' },
    },
    {
      path: '/hospitals/:key',
      name: 'hospital-detail',
      component: () => import('@/views/HospitalDetailPage.vue'),
      meta: { title: '医院详情' },
    },
    {
      path: '/assessment',
      name: 'assessment',
      component: () => import('@/views/AssessmentPage.vue'),
      beforeEnter: to => ['exam', 'report'].includes(String(to.query.tab)) ? { name: 'assessment-exam' } : true,
    },
    {
      path: '/assessment/exam',
      name: 'assessment-exam',
      component: () => import('@/views/AssessmentExamPage.vue'),
      meta: { title: '体检解读' },
    },
    {
      path: '/assessment/vasi/:id',
      name: 'vasi-detail',
      component: () => import('@/views/VasiDetailPage.vue'),
    },
    {
      path: '/assessment/compare',
      name: 'vasi-compare',
      component: () => import('@/views/VasiComparePage.vue'),
    },
    {
      path: '/assessment/photo-compare',
      name: 'assessment-photo-compare',
      component: () => import('@/views/QuickPhotoComparePage.vue'),
      meta: { title: '白斑对比' },
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
      // 原「报告」顶层模块已移除：白斑对比在测评页评估历史，报告详情走 /community/reports/:id
      path: '/report',
      redirect: '/assessment',
    },
    {
      path: '/diary',
      redirect: '/community',
    },
    // 白斑对比/报告详情沿用 /community/reports/*；列表入口 = 测评页评估历史
    {
      path: '/community/reports',
      redirect: '/assessment',
    },
    {
      path: '/community/reports/new',
      name: 'skin-report-new',
      component: () => import('@/views/SkinReportCreatePage.vue'),
      meta: { title: '生成报告' },
    },
    {
      path: '/community/reports/:id',
      name: 'skin-report-view',
      component: () => import('@/views/SkinReportViewPage.vue'),
      meta: { title: '白斑变化报告' },
    },
    // 兼容旧 /diary/reports/* 链接
    { path: '/diary/reports', redirect: '/assessment' },
    { path: '/diary/reports/new', redirect: '/community/reports/new' },
    { path: '/diary/reports/:id', redirect: (to: any) => `/community/reports/${to.params.id}` },
    {
      path: '/share/report/:token',
      name: 'skin-report-shared',
      component: () => import('@/views/SkinReportSharedPage.vue'),
      meta: { title: '白斑变化报告', public: true },
    },
    {
      path: '/assessment/report-compare',
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
      path: '/profile/data',
      name: 'profile-data',
      component: () => import('@/views/DataContributionPage.vue'),
    },
    {
      path: '/user/:userId',
      name: 'user-profile',
      component: () => import('@/views/UserProfilePage.vue'),
    },
    {
      // 小白百科已下线：百科内容已融入智能问答/小白管家，访问旧链接统一回首页
      path: '/encyclopedia',
      redirect: '/',
    },
    {
      path: '/encyclopedia/:slug(.*)*',
      redirect: '/',
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
      path: '/:catchAll(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundPage.vue'),
      meta: { title: '页面不存在' },
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
