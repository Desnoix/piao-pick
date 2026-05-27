<script setup lang="ts">
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NNotificationProvider,
  NLoadingBarProvider,
  NLayout, NLayoutHeader, NLayoutSider, NLayoutContent, NMenu,
} from 'naive-ui'
import { computed, onMounted, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from './stores/app'
import type { MenuOption } from 'naive-ui'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()

// ---- Inline SVG icon renderer for NMenu options ----
function renderIcon(svgPaths: string[]) {
  return () =>
    h(
      'svg',
      {
        xmlns: 'http://www.w3.org/2000/svg',
        viewBox: '0 0 24 24',
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': '1.8',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        width: '18',
        height: '18',
      },
      svgPaths.map((d) => h('path', { d }))
    )
}

const menuOptions = computed<MenuOption[]>(() => [
  {
    label: '选股',
    key: '/',
    icon: renderIcon(['M3 3v18h18', 'M7 14l4-4 4 4 5-5']),
  },
  {
    label: '策略',
    key: '/strategy/list',
    icon: renderIcon([
      'M4 21v-7m0-4V3',
      'M12 21v-9m0-4V3',
      'M20 21v-5m0-4V3',
      'M1 14h6',
      'M9 8h6',
      'M17 16h6',
    ]),
  },
  {
    label: '数据',
    key: '/data/status',
    icon: renderIcon([
      'M4 6c0-1.1 3.6-2 8-2s8 .9 8 2-3.6 2-8 2-8-.9-8-2',
      'M4 6v6c0 1.1 3.6 2 8 2s8-.9 8-2V6',
      'M4 12v6c0 1.1 3.6 2 8 2s8-.9 8-2v-6',
    ]),
  },
])

const handleMenuUpdate = (key: string) => {
  router.push(key)
}

const activeKey = computed(() => {
  const path = route.path
  if (path === '/' || path.startsWith('/stock/')) return '/'
  if (path.startsWith('/strategy')) return '/strategy/list'
  if (path.startsWith('/backtest')) return '/strategy/list'
  if (path.startsWith('/data')) return '/data/status'
  return path
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
    <NLayout has-sider class="min-h-[100dvh]">
      <NLayoutSider
        bordered
        :width="200"
        :collapsed-width="64"
        collapse-mode="width"
        class="select-none app-sider"
      >
        <!-- Brand area -->
        <div class="px-4 pt-4 pb-3 flex flex-col gap-1 border-b border-[var(--color-border,#e5e7eb)]">
          <div class="flex items-center gap-2.5">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              width="22" height="22"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="text-[var(--color-accent,#14B8A6)] shrink-0"
            >
              <path d="M3 3v18h18" />
              <path d="M7 14l4-4 4 4 5-5" />
            </svg>
            <span class="text-[17px] font-bold tracking-tight text-[var(--color-text-primary,#111827)]">
              飘票选股
            </span>
          </div>
          <span class="text-[11px] leading-none text-[var(--color-text-secondary,#6b7280)] pl-[30px]">
            量化选股系统
          </span>
        </div>

        <!-- Navigation (fills available space) -->
        <div class="flex-1 overflow-y-auto py-1">
          <NMenu
            :value="activeKey"
            :options="menuOptions"
            @update:value="handleMenuUpdate"
          />
        </div>

        <!-- Footer -->
        <div class="px-4 py-3 border-t border-[var(--color-border,#e5e7eb)]">
          <span class="text-[10px] tracking-widest text-[var(--color-text-secondary,#9ca3af)]">v0.1.0</span>
        </div>
      </NLayoutSider>

      <NLayout>
        <NLayoutHeader
          class="px-6 h-12 flex items-center justify-between border-b border-[var(--color-border,#e5e7eb)] bg-[var(--color-surface-elevated,#fff)]"
        >
          <span class="text-sm font-medium text-[var(--color-text-primary,#111827)]">
            A股多因子选股系统
          </span>

          <!-- Theme toggle icon button -->
          <button
            class="w-8 h-8 rounded-lg flex items-center justify-center transition-colors border border-[var(--color-border,#e5e7eb)] hover:bg-[var(--color-surface-inset,#f3f4f6)]"
            :aria-label="appStore.isDark ? '切换到浅色模式' : '切换到深色模式'"
            @click="appStore.toggleTheme"
          >
            <!-- Moon icon (visible in light mode -> click to go dark) -->
            <svg
              v-if="!appStore.isDark"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              width="15" height="15"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="text-[var(--color-text-secondary,#6b7280)]"
            >
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
            <!-- Sun icon (visible in dark mode -> click to go light) -->
            <svg
              v-else
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              width="15" height="15"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="text-[var(--color-text-secondary,#94a3b8)]"
            >
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
            </svg>
          </button>
        </NLayoutHeader>

        <NLayoutContent
          class="p-6"
          content-style="min-height: calc(100dvh - 48px);"
        >
          <div id="main-content" class="max-w-[1600px]">
            <router-view v-slot="{ Component }">
              <Transition name="page-fade" mode="out-in">
                <component :is="Component" />
              </Transition>
            </router-view>
          </div>
        </NLayoutContent>
      </NLayout>
    </NLayout>
          </NLoadingBarProvider>
        </NNotificationProvider>
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>

<style scoped>
/* ---------- Sider layout: flex column for brand / nav / footer ---------- */
.app-sider {
  background: var(--color-surface-elevated, #fff);
}

.app-sider :deep(.n-layout-sider-scroll-container) {
  display: flex;
  flex-direction: column;
}

/* ---------- Active menu item ---------- */
:deep(.n-menu-item-content--selected) {
  background-color: var(--color-accent-muted, rgba(20, 184, 166, 0.08)) !important;
  color: var(--color-accent, #14B8A6) !important;
}

:deep(.n-menu-item-content--selected .n-menu-item-content__icon) {
  color: var(--color-accent, #14B8A6) !important;
}

:deep(.n-menu-item-content--selected .n-menu-item-content__label) {
  color: var(--color-accent, #14B8A6) !important;
  font-weight: 600;
}

/* Dark mode overrides for active state */
:global(html.dark) :deep(.n-menu-item-content--selected) {
  background-color: rgba(20, 184, 166, 0.12) !important;
}

/* ---------- Menu icon default colour ---------- */
:deep(.n-menu-item-content__icon) {
  color: var(--color-text-secondary, #6b7280);
}

:global(html.dark) :deep(.n-menu-item-content__icon) {
  color: var(--color-text-secondary, #94a3b8);
}

/* ---------- Menu item hover ---------- */
:deep(.n-menu-item-content:hover) {
  background-color: var(--color-surface-inset, rgba(0, 0, 0, 0.04)) !important;
}

:global(html.dark) :deep(.n-menu-item-content:hover) {
  background-color: rgba(255, 255, 255, 0.06) !important;
}

/* ---------- Remove default NLayoutSider border override (we control it) ---------- */
:deep(.n-layout-sider) {
  background: var(--color-surface-elevated, #fff) !important;
}
</style>
