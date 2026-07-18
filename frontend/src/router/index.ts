import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/pages/Home.vue'),
    },
    {
      path: '/reading/:readingId',
      name: 'progress',
      component: () => import('@/pages/Progress.vue'),
    },
    {
      path: '/report/:reportId',
      name: 'report',
      component: () => import('@/pages/Report.vue'),
    },
    // 真爱画像
    {
      path: '/portrait',
      name: 'portrait',
      component: () => import('@/pages/Portrait.vue'),
    },
    {
      path: '/portrait/:portraitId',
      name: 'portrait-progress',
      component: () => import('@/pages/PortraitProgress.vue'),
    },
    {
      path: '/portrait/:portraitId/result',
      name: 'portrait-result',
      component: () => import('@/pages/PortraitResult.vue'),
    },
    // 合盘分析
    {
      path: '/synastry',
      name: 'synastry',
      component: () => import('@/pages/Synastry.vue'),
    },
    {
      path: '/synastry/:synastryId',
      name: 'synastry-progress',
      component: () => import('@/pages/SynastryProgress.vue'),
    },
    {
      path: '/synastry/:synastryId/result',
      name: 'synastry-result',
      component: () => import('@/pages/SynastryResult.vue'),
    },
  ],
})

export default router
