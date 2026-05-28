import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../pages/Dashboard.vue'),
  },
  {
    path: '/dashboard',
    redirect: '/',
  },
  {
    path: '/selection',
    name: 'SelectionHome',
    component: () => import('../pages/SelectionHome.vue'),
  },
  {
    path: '/strategy/list',
    name: 'StrategyList',
    component: () => import('../pages/StrategyList.vue'),
  },
  {
    path: '/strategy/compare',
    name: 'StrategyCompare',
    component: () => import('../pages/StrategyCompare.vue'),
  },
  {
    path: '/strategy/:id',
    name: 'StrategyEdit',
    component: () => import('../pages/StrategyEdit.vue'),
    props: true,
  },
  {
    path: '/stock/:ts_code',
    name: 'StockDetail',
    component: () => import('../pages/StockDetail.vue'),
    props: true,
  },
  {
    path: '/backtest',
    name: 'BacktestHome',
    component: () => import('../pages/BacktestHome.vue'),
  },
  {
    path: '/backtest/:strategyId',
    name: 'BacktestResult',
    component: () => import('../pages/BacktestResult.vue'),
    props: true,
  },
  {
    path: '/data/status',
    name: 'DataStatus',
    component: () => import('../pages/DataStatus.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../pages/Settings.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../pages/NotFound.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由导航错误处理
// 典型场景: 部署后旧 chunk 404, 用户点到已删除的页面路由
router.onError((error, to) => {
  const message = error.message || ''
  const isChunkError =
    message.includes('Failed to fetch dynamically imported module') ||
    message.includes('Loading chunk') ||
    message.includes('Loading CSS chunk')

  if (isChunkError) {
    console.warn('[Router] chunk 加载失败, 可能由部署更新导致, 自动刷新:', to.fullPath)
    // chunk 失效时自动刷新以获取最新资源
    window.location.href = to.fullPath
  } else {
    console.error('[Router] 导航错误:', error)
  }
})

export default router
