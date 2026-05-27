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
    redirect: '/strategy/list',
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
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
