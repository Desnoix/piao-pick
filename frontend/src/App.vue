<script setup lang="ts">
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NNotificationProvider,
  NLoadingBarProvider,
} from 'naive-ui'
import { computed, onMounted, ref, watch, type Component, markRaw } from 'vue'
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
  PhList,
} from '@phosphor-icons/vue'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()

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

const pageTitle = computed(() => {
  const path = route.path
  if (path === '/' || path === '/dashboard') return '概览'
  if (path === '/selection') return '选股'
  if (path === '/strategy/list') return '策略管理'
  if (path === '/strategy/compare') return '策略对比'
  if (path.startsWith('/strategy/')) return '策略编辑'
  if (path.startsWith('/stock/')) return '个股详情'
  if (path === '/backtest') return '回测'
  if (path.startsWith('/backtest/')) return '回测结果'
  if (path === '/data/status') return '数据状态'
  if (path === '/settings') return '设置'
  return ''
})

const mobileMenuOpen = ref(false)

// Auto-close drawer on route change
watch(
  () => route.path,
  () => {
    mobileMenuOpen.value = false
  }
)

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
            <!-- Mobile backdrop overlay -->
            <div v-if="mobileMenuOpen" class="mobile-backdrop" @click="mobileMenuOpen = false" />

            <div class="app-shell">
              <!-- Icon Rail / Mobile Drawer -->
              <aside class="rail" :class="{ 'rail--open': mobileMenuOpen }" aria-label="主导航">
                <!-- Brand -->
                <div class="rail__brand">
                  <PhChartLineUp :size="22" weight="bold" class="rail__brand-icon" />
                  <span class="rail__brand-text">飘票选股</span>
                </div>

                <!-- Nav -->
                <nav class="rail__nav">
                  <button
                    v-for="item in navItems"
                    :key="item.path"
                    class="rail__item"
                    :class="{ 'rail__item--active': isNavItemActive(item) }"
                    :aria-label="item.label"
                    @click="navigateTo(item.path)"
                  >
                    <component
                      :is="item.icon"
                      :size="20"
                      :weight="isNavItemActive(item) ? 'fill' : 'regular'"
                      class="rail__item-icon"
                    />
                    <span class="rail__item-label">{{ item.label }}</span>
                  </button>
                </nav>
              </aside>

              <!-- Main area -->
              <div class="main-area">
                <!-- Desktop header -->
                <header class="app-header app-header--desktop">
                  <h1 class="app-header__title">{{ pageTitle }}</h1>

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

                <!-- Mobile header (hamburger + title + theme) -->
                <header class="mobile-header">
                  <button
                    class="mobile-menu-btn"
                    aria-label="打开菜单"
                    @click="mobileMenuOpen = !mobileMenuOpen"
                  >
                    <PhList :size="22" weight="bold" />
                  </button>
                  <h1 class="mobile-header__title">{{ pageTitle }}</h1>
                  <button
                    class="mobile-theme-btn"
                    :aria-label="appStore.isDark ? '切换到浅色模式' : '切换到深色模式'"
                    @click="appStore.toggleTheme"
                  >
                    <PhMoon v-if="!appStore.isDark" :size="18" weight="regular" />
                    <PhSun v-else :size="18" weight="regular" />
                  </button>
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

/* ============================================================
   Icon Rail — 60px fixed, expands to 220px on hover (overlay)
   The rail itself stays 60px in flex layout; a ::before backdrop
   expands behind nav items, which overflow visibly to the right.
   ============================================================ */

.rail {
  position: relative;
  z-index: 50;
  width: 60px;
  min-width: 60px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: visible;
  user-select: none;
}

/* Expanding backdrop panel — provides background for overflow items */
.rail::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 60px;
  background: var(--color-surface-elevated);
  border-right: 1px solid var(--color-glass-border, var(--color-border));
  transition:
    width 0.3s cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 0.3s ease;
  z-index: 0;
}

.rail:hover::before {
  width: 220px;
  box-shadow: 8px 0 32px -8px rgba(0, 0, 0, 0.5);
}

/* ---- Brand area ---- */
.rail__brand {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  height: 52px;
  padding: 0 20px;
  flex-shrink: 0;
}

.rail__brand-icon {
  color: var(--color-accent);
  flex-shrink: 0;
}

.rail__brand-text {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-text-primary);
  white-space: nowrap;
  opacity: 0;
  transition: opacity 0.15s ease 0.1s;
}

.rail:hover .rail__brand-text {
  opacity: 1;
}

/* ---- Nav ---- */
.rail__nav {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 0;
  overflow: visible;
}

/* Nav item — base width equals rail width (60px) */
.rail__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  height: 40px;
  width: 60px;
  padding: 0 20px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  text-align: left;
  transition:
    width 0.3s cubic-bezier(0.16, 1, 0.3, 1),
    background-color 0.15s ease,
    color 0.15s ease;
}

.rail:hover .rail__item {
  width: 204px;
}

.rail__item:hover {
  background: var(--color-surface-inset);
  color: var(--color-text-primary);
}

/* Active: tinted bg + gradient accent bar */
.rail__item--active {
  background: rgba(6, 182, 212, 0.08);
  color: var(--color-text-primary);
}

.rail__item--active::after {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 2px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--color-accent), var(--color-accent-hover));
}

.rail__item--active:hover {
  background: rgba(6, 182, 212, 0.12);
}

/* Nav icon — always visible */
.rail__item-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

/* Nav label — fades in on hover */
.rail__item-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  opacity: 0;
  transition: opacity 0.15s ease 0.1s;
}

.rail__item--active .rail__item-label {
  font-weight: 600;
}

.rail:hover .rail__item-label {
  opacity: 1;
}

/* ========== Main Area ========== */
.main-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ========== Desktop Header ========== */
.app-header {
  height: 52px;
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--color-surface-elevated);
  border-bottom: 1px solid var(--color-glass-border, var(--color-border));
}

.app-header__title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--color-text-primary);
  margin: 0;
  line-height: 1;
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
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
  flex-shrink: 0;
}

.header-icon-btn:hover {
  background: var(--color-surface-inset);
  color: var(--color-text-primary);
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

/* ========== Mobile Header ========== */
.mobile-header {
  display: none;
}

.mobile-menu-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: var(--color-text-primary);
  cursor: pointer;
  flex-shrink: 0;
  transition: background-color 0.15s ease;
}

.mobile-menu-btn:hover {
  background: var(--color-surface-inset);
}

.mobile-menu-btn:active {
  background: var(--color-surface-inset);
}

.mobile-header__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
  line-height: 1;
  flex: 1;
  text-align: center;
}

.mobile-theme-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  transition: background-color 0.15s ease;
}

.mobile-theme-btn:hover {
  background: var(--color-surface-inset);
  color: var(--color-text-primary);
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
  min-height: calc(100dvh - 52px - 48px);
}

/* ============================================================
   RESPONSIVE: Mobile & Tablet (< 1024px)
   Rail becomes fixed overlay drawer, mobile header appears
   ============================================================ */
@media (max-width: 1023px) {
  /* Rail: fixed drawer, hidden by default */
  .rail {
    position: fixed;
    top: 0;
    left: 0;
    height: 100dvh;
    min-width: unset;
    width: 220px;
    transform: translateX(-100%);
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    z-index: 60;
    overflow: hidden;
  }

  .rail--open {
    transform: translateX(0);
    box-shadow: 8px 0 32px -8px rgba(0, 0, 0, 0.5);
  }

  /* Fixed backdrop always 220px (no hover expand) */
  .rail::before {
    width: 220px !important;
    box-shadow: none !important;
    transition: none !important;
  }

  .rail:hover::before {
    width: 220px;
    box-shadow: none;
  }

  /* Nav items: full width, labels always visible */
  .rail__item {
    width: 204px !important;
    min-height: 44px;
    transition:
      background-color 0.15s ease,
      color 0.15s ease;
  }

  .rail:hover .rail__item {
    width: 204px;
  }

  .rail__item-label {
    opacity: 1 !important;
    transition: none;
  }

  .rail__item--active .rail__item-label {
    font-weight: 600;
  }

  .rail__brand-text {
    opacity: 1 !important;
    transition: none;
  }

  /* Hide desktop header, show mobile header */
  .app-header--desktop {
    display: none;
  }

  .mobile-header {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 56px;
    min-height: 56px;
    padding: 0 8px;
    background: var(--color-surface-elevated);
    border-bottom: 1px solid var(--color-border);
    position: sticky;
    top: 0;
    z-index: 30;
  }

  /* Responsive content padding */
  .content-area {
    padding: 16px;
  }
}

/* Tablet and above */
@media (min-width: 768px) and (max-width: 1023px) {
  .content-area {
    padding: 20px;
  }
}

/* ============================================================
   TOUCH OPTIMIZATION
   Disable hover effects on touch devices to prevent sticky states
   ============================================================ */
@media (hover: none) {
  .rail__item:hover,
  .header-icon-btn:hover,
  .mobile-menu-btn:hover,
  .mobile-theme-btn:hover {
    background: transparent;
    color: inherit;
  }

  .rail__item--active:hover {
    background: rgba(6, 182, 212, 0.08);
  }

  .rail__item:active,
  .header-icon-btn:active,
  .mobile-menu-btn:active,
  .mobile-theme-btn:active {
    background: var(--color-surface-inset);
  }

  /* Disable hover backdrop expand on touch devices (desktop rail) */
  .rail:hover::before {
    width: 60px;
    box-shadow: none;
  }

  .rail:hover .rail__item {
    width: 60px;
  }

  .rail:hover .rail__item-label,
  .rail:hover .rail__brand-text {
    opacity: 0;
  }
}

/* ============================================================
   MOBILE BACKDROP
   ============================================================ */
.mobile-backdrop {
  display: none;
}

@media (max-width: 1023px) {
  .mobile-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 55;
    backdrop-filter: blur(2px);
  }
}
</style>
