<script setup lang="ts">
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NNotificationProvider,
  NLoadingBarProvider,
  NTooltip,
} from 'naive-ui'
import { computed, ref, onMounted, type Component, markRaw } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from './stores/app'
import {
  PhChartLineUp,
  PhFunnel,
  PhSliders,
  PhClockCounterClockwise,
  PhDatabase,
  PhGearSix,
  PhSun,
  PhMoon,
  PhSidebar,
} from '@phosphor-icons/vue'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()
const sidebarCollapsed = ref(false)

interface NavItem {
  label: string
  path: string
  icon: Component
  matchPrefix: string[]
  exactPaths?: string[]
}

const navItems: NavItem[] = [
  {
    label: '概览',
    path: '/',
    icon: markRaw(PhChartLineUp),
    matchPrefix: [],
    exactPaths: ['/', '/dashboard'],
  },
  {
    label: '选股',
    path: '/selection',
    icon: markRaw(PhFunnel),
    matchPrefix: ['/selection', '/stock/'],
  },
  {
    label: '策略',
    path: '/strategy/list',
    icon: markRaw(PhSliders),
    matchPrefix: ['/strategy'],
  },
  {
    label: '回测',
    path: '/backtest',
    icon: markRaw(PhClockCounterClockwise),
    matchPrefix: ['/backtest'],
  },
  {
    label: '数据',
    path: '/data/status',
    icon: markRaw(PhDatabase),
    matchPrefix: ['/data'],
  },
  {
    label: '设置',
    path: '/settings',
    icon: markRaw(PhGearSix),
    matchPrefix: ['/settings'],
  },
]

function isNavItemActive(item: NavItem): boolean {
  const path = route.path
  if (item.exactPaths && item.exactPaths.length > 0) {
    return item.exactPaths.includes(path)
  }
  return item.matchPrefix.some((prefix) => path === prefix || path.startsWith(prefix))
}

function navigateTo(path: string) {
  router.push(path)
}

const breadcrumbs = computed(() => {
  const path = route.path
  if (path === '/dashboard' || path === '/') return ['概览']
  if (path === '/selection') return ['选股']
  if (path === '/strategy/list') return ['策略']
  if (path === '/strategy/compare') return ['策略', '对比']
  if (path.startsWith('/strategy/')) return ['策略', '编辑']
  if (path.startsWith('/stock/')) return ['选股', '个股详情']
  if (path === '/backtest') return ['回测']
  if (path.startsWith('/backtest/')) return ['回测', '结果']
  if (path === '/data/status') return ['数据']
  if (path === '/settings') return ['设置']
  return []
})

onMounted(() => {
  appStore.initTheme()
})
</script>

<template>
  <a href="#main-content" class="skip-link">跳过导航</a>
  <NConfigProvider :theme="appStore.naiveTheme">
    <NMessageProvider>
      <NDialogProvider>
        <NNotificationProvider>
          <NLoadingBarProvider>
            <div class="app-shell">
              <!-- Sidebar -->
              <aside
                class="sidebar"
                :class="{ 'sidebar--collapsed': sidebarCollapsed }"
              >
                <!-- Logo area -->
                <div class="sidebar__brand">
                  <PhChartLineUp
                    :size="22"
                    weight="bold"
                    class="sidebar__logo-icon"
                  />
                  <Transition name="fade-text">
                    <div v-if="!sidebarCollapsed" class="sidebar__brand-text">
                      <span class="sidebar__title">飘票选股</span>
                      <span class="sidebar__subtitle">多因子量化</span>
                    </div>
                  </Transition>
                </div>

                <!-- Nav items -->
                <nav class="sidebar__nav" aria-label="主导航">
                  <template v-for="item in navItems" :key="item.path">
                    <NTooltip
                      v-if="sidebarCollapsed"
                      placement="right"
                      :show-arrow="false"
                    >
                      <template #trigger>
                        <button
                          class="nav-item"
                          :class="{ 'nav-item--active': isNavItemActive(item) }"
                          :aria-label="item.label"
                          @click="navigateTo(item.path)"
                        >
                          <component
                            :is="item.icon"
                            :size="20"
                            :weight="isNavItemActive(item) ? 'fill' : 'regular'"
                          />
                        </button>
                      </template>
                      {{ item.label }}
                    </NTooltip>
                    <button
                      v-else
                      class="nav-item"
                      :class="{ 'nav-item--active': isNavItemActive(item) }"
                      :aria-label="item.label"
                      @click="navigateTo(item.path)"
                    >
                      <component
                        :is="item.icon"
                        :size="20"
                        :weight="isNavItemActive(item) ? 'fill' : 'regular'"
                      />
                      <span class="nav-item__label">{{ item.label }}</span>
                    </button>
                  </template>
                </nav>

                <!-- Footer -->
                <div class="sidebar__footer">
                  <span class="sidebar__version">v0.1.0</span>
                </div>
              </aside>

              <!-- Main area -->
              <div class="main-area">
                <!-- Header -->
                <header class="app-header">
                  <!-- Left: collapse toggle + breadcrumbs -->
                  <div class="app-header__left">
                    <button
                      class="header-icon-btn"
                      aria-label="切换侧边栏"
                      @click="sidebarCollapsed = !sidebarCollapsed"
                    >
                      <PhSidebar :size="18" weight="regular" />
                    </button>
                    <nav class="breadcrumbs" aria-label="面包屑">
                      <template v-for="(crumb, i) in breadcrumbs" :key="i">
                        <span
                          v-if="i > 0"
                          class="breadcrumbs__sep"
                          aria-hidden="true"
                        >/</span>
                        <span class="breadcrumbs__item">{{ crumb }}</span>
                      </template>
                    </nav>
                  </div>

                  <!-- Right: status + theme + avatar -->
                  <div class="app-header__right">
                    <!-- Data sync status -->
                    <div class="sync-indicator">
                      <span class="sync-indicator__dot" />
                      <span class="sync-indicator__text">数据已更新</span>
                    </div>

                    <!-- Theme toggle -->
                    <button
                      class="header-icon-btn"
                      :aria-label="appStore.isDark ? '切换到浅色模式' : '切换到深色模式'"
                      @click="appStore.toggleTheme"
                    >
                      <PhMoon v-if="!appStore.isDark" :size="18" weight="regular" />
                      <PhSun v-else :size="18" weight="regular" />
                    </button>

                    <!-- User avatar placeholder -->
                    <div class="user-avatar" aria-label="用户">QP</div>
                  </div>
                </header>

                <!-- Content -->
                <main class="content-area">
                  <div id="main-content" class="content-inner">
                    <router-view v-slot="{ Component }">
                      <Transition name="page-fade" mode="out-in">
                        <component :is="Component" />
                      </Transition>
                    </router-view>
                  </div>
                </main>
              </div>
            </div>
          </NLoadingBarProvider>
        </NNotificationProvider>
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>

<style scoped>
/* ========== App Shell ========== */
.app-shell {
  display: flex;
  height: 100dvh;
  overflow: hidden;
}

/* ========== Sidebar ========== */
.sidebar {
  width: 220px;
  min-width: 220px;
  display: flex;
  flex-direction: column;
  background: var(--color-surface-elevated);
  border-right: 1px solid var(--color-border);
  transition: width 0.2s ease, min-width 0.2s ease;
  overflow: hidden;
  user-select: none;
}

.sidebar--collapsed {
  width: 60px;
  min-width: 60px;
}

/* Brand / Logo */
.sidebar__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
  min-height: 56px;
}

.sidebar--collapsed .sidebar__brand {
  justify-content: center;
  padding: 16px 0;
}

.sidebar__logo-icon {
  color: var(--color-accent);
  flex-shrink: 0;
}

.sidebar__brand-text {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  white-space: nowrap;
}

.sidebar__title {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-text-primary);
  line-height: 1.2;
}

.sidebar__subtitle {
  font-size: 11px;
  color: var(--color-text-muted);
  line-height: 1.2;
  margin-top: 1px;
}

/* Navigation */
.sidebar__nav {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar--collapsed .sidebar__nav {
  align-items: center;
  padding: 8px 0;
}

/* Nav item */
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 12px;
  border-radius: 8px;
  border: none;
  border-left: 3px solid transparent;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  text-align: left;
  transition: background-color 0.15s ease, color 0.15s ease,
    border-color 0.15s ease;
  position: relative;
}

.sidebar--collapsed .nav-item {
  justify-content: center;
  padding: 10px;
  width: 40px;
  border-left: none;
  border-radius: 10px;
}

.nav-item:hover {
  background: var(--color-surface-inset);
  color: var(--color-text-primary);
}

.nav-item--active {
  border-left-color: var(--color-accent);
  background: var(--color-accent-muted);
  color: var(--color-text-primary);
  font-weight: 600;
}

.sidebar--collapsed .nav-item--active {
  border-left: none;
  background: var(--color-accent-muted);
}

.nav-item--active .nav-item__label {
  color: var(--color-text-primary);
}

.nav-item--active:hover {
  background: var(--color-accent-muted);
}

.nav-item__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Footer */
.sidebar__footer {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  text-align: left;
}

.sidebar--collapsed .sidebar__footer {
  text-align: center;
  padding: 12px 0;
}

.sidebar__version {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--color-text-muted);
}

/* ========== Main Area ========== */
.main-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ========== Header ========== */
.app-header {
  height: 48px;
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: var(--color-surface-elevated);
}

.app-header__left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Header icon button */
.header-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
  flex-shrink: 0;
}

.header-icon-btn:hover {
  background: var(--color-surface-inset);
  color: var(--color-text-primary);
}

/* Breadcrumbs */
.breadcrumbs {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  min-width: 0;
  overflow: hidden;
}

.breadcrumbs__item {
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.breadcrumbs__item:last-child {
  color: var(--color-text-primary);
  font-weight: 500;
}

.breadcrumbs__sep {
  color: var(--color-text-muted);
  font-size: 12px;
}

/* Sync status indicator */
.sync-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sync-indicator__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
  flex-shrink: 0;
}

.sync-indicator__text {
  font-size: 12px;
  color: var(--color-text-muted);
  white-space: nowrap;
}

/* User avatar */
.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-accent-muted);
  color: var(--color-accent);
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-family: var(--font-mono);
}

/* ========== Content ========== */
.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: var(--color-surface);
}

.content-inner {
  max-width: 1600px;
  min-height: calc(100dvh - 48px - 48px);
}

/* ========== Transitions ========== */
.fade-text-enter-active,
.fade-text-leave-active {
  transition: opacity 0.15s ease;
}

.fade-text-enter-from,
.fade-text-leave-to {
  opacity: 0;
}
</style>
