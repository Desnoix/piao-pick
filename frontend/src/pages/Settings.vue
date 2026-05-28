<script setup lang="ts">
/**
 * Settings page: theme toggle, data info, and about section.
 * 设置页面: 主题切换、数据信息、关于系统。
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NSpace, NSpin, NTag } from 'naive-ui'
import { PhPalette, PhDatabase, PhInfo, PhGearSix } from '@phosphor-icons/vue'
import { useAppStore } from '../stores/app'
import { getDataStatus } from '../api/data'
import type { DataStatus } from '../types/api'

const router = useRouter()
const appStore = useAppStore()

const dataStatus = ref<DataStatus | null>(null)
const loadingData = ref(false)

async function fetchDataStatus() {
  loadingData.value = true
  try {
    dataStatus.value = await getDataStatus()
  } catch (err: any) {
    // 忽略请求取消错误（来自 client.ts 的请求去重机制）
    if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
    console.warn('Failed to fetch data status:', err)
    dataStatus.value = null
  } finally {
    loadingData.value = false
  }
}

onMounted(() => {
  fetchDataStatus()
})

function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '-'
  return `${bytes.toFixed(2)} MB`
}

function formatDate(date: string | null | undefined): string {
  if (!date) return '-'
  return date
}
</script>

<template>
  <div class="flex w-full flex-col gap-8 lg:max-w-[720px]">
    <!-- Display -->
    <section>
      <div class="section-header">
        <span class="section-label">显示</span>
        <h3 class="section-title">外观</h3>
      </div>
      <div class="glass-panel">
        <div class="setting-row">
          <div class="setting-info">
            <span class="setting-key">主题模式</span>
            <span class="setting-hint">当前: {{ appStore.isDark ? '深色' : '浅色' }}</span>
          </div>
          <button class="theme-toggle" @click="appStore.toggleTheme()">
            <span class="theme-toggle-track">
              <span
                class="theme-toggle-thumb"
                :class="{ 'theme-toggle-thumb--light': !appStore.isDark }"
              />
            </span>
            <span class="theme-toggle-label">
              {{ appStore.isDark ? '切换到浅色' : '切换到深色' }}
            </span>
          </button>
        </div>
      </div>
    </section>

    <!-- Data -->
    <section>
      <div class="section-header">
        <span class="section-label">数据</span>
        <h3 class="section-title">数据库</h3>
      </div>
      <div class="glass-panel overflow-hidden">
        <NSpin v-if="loadingData" class="flex justify-center py-8" size="small" />

        <div v-else-if="dataStatus" class="kv-list">
          <div class="kv-row">
            <span class="kv-key">路径</span>
            <span class="kv-val data-mono">{{ dataStatus.db_path }}</span>
          </div>
          <div class="kv-row">
            <span class="kv-key">占用空间</span>
            <span class="kv-val data-mono">{{ formatBytes(dataStatus.db_size_mb) }}</span>
          </div>
          <div class="kv-row">
            <span class="kv-key">股票数量</span>
            <span class="kv-val data-mono">{{ dataStatus.stock_count }}</span>
          </div>
          <div class="kv-row">
            <span class="kv-key">K线截至</span>
            <span class="kv-val data-mono">{{ formatDate(dataStatus.latest_kline_date) }}</span>
          </div>
          <div class="kv-row kv-row--last" v-if="dataStatus.latest_factor_date">
            <span class="kv-key">因子截至</span>
            <span class="kv-val data-mono">{{ formatDate(dataStatus.latest_factor_date) }}</span>
          </div>
        </div>

        <div v-else class="py-8 text-center">
          <p class="text-sm text-[var(--color-text-muted)]">无法获取数据状态</p>
        </div>

        <div class="section-footer">
          <NButton type="primary" ghost size="small" @click="router.push('/data/status')">
            打开数据管理
          </NButton>
        </div>
      </div>
    </section>

    <!-- About -->
    <section>
      <div class="section-header">
        <span class="section-label">关于</span>
        <h3 class="section-title">飘票选股</h3>
      </div>
      <div class="glass-panel overflow-hidden">
        <div class="kv-list">
          <div class="kv-row">
            <span class="kv-key">版本</span>
            <span class="kv-val data-mono">v0.1.0</span>
          </div>
          <div class="kv-row">
            <span class="kv-key">描述</span>
            <span class="kv-val">A股多因子量化选股系统</span>
          </div>
          <div class="kv-row kv-row--last">
            <span class="kv-key">技术栈</span>
            <div class="tech-badges">
              <span class="tech-badge">Vue 3</span>
              <span class="tech-badge">FastAPI</span>
              <span class="tech-badge">Naive UI</span>
              <span class="tech-badge">TailwindCSS</span>
              <span class="tech-badge">ECharts</span>
              <span class="tech-badge">SQLite</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* Section hierarchy */
.section-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 12px;
}

.section-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}

.section-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

/* Theme toggle row */
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.setting-key {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.setting-hint {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* Custom toggle switch */
.theme-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px 0;
  min-height: 44px;
}

.theme-toggle-track {
  display: inline-flex;
  align-items: center;
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: var(--color-surface-inset);
  border: 1px solid var(--color-border);
  padding: 2px;
  transition: background-color 0.2s ease;
  flex-shrink: 0;
}

.theme-toggle-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-accent);
  transition: transform 0.2s ease;
  transform: translateX(20px);
}

.theme-toggle-thumb--light {
  transform: translateX(0);
}

.theme-toggle-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: nowrap;
}

/* Key-value list (shared pattern) */
.kv-list {
  display: flex;
  flex-direction: column;
}

.kv-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--color-border);
}

.kv-row--last {
  border-bottom: none;
}

.kv-key {
  font-size: 13px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.kv-val {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  text-align: right;
}

/* Section footer */
.section-footer {
  display: flex;
  justify-content: flex-end;
  padding: 12px 20px;
  border-top: 1px solid var(--color-border);
}

/* Tech badges */
.tech-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.tech-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 9999px;
  border: 1px solid var(--color-border);
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-surface-inset);
  letter-spacing: 0.02em;
  white-space: nowrap;
}

/* ===== Responsive ===== */
@media (max-width: 480px) {
  .kv-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .kv-val {
    text-align: left;
    word-break: break-all;
  }

  .tech-badges {
    justify-content: flex-start;
  }
}

@media (hover: none) {
  .theme-toggle:hover {
    opacity: 1;
  }
  .theme-toggle:active {
    opacity: 0.7;
  }
}
</style>
