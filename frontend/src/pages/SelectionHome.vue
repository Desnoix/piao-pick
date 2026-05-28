<script setup lang="ts">
/**
 * Selection home: two-panel layout with strategy run, results table, and factor radar.
 * 选股主页: 左侧结果表格 + 右侧因子雷达面板。
 */
import { ref, h, computed, onMounted, onUnmounted, watch } from 'vue'
import { NDataTable, NSelect, NButton, NInput, NTag, NTooltip, useMessage } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useStrategyStore } from '../stores/strategy'
import { useSelectionStore } from '../stores/selection'
import { runSelection, getPrepareStatus } from '../api/selection'
import FactorRadar from '../components/charts/FactorRadar.vue'
import TableSkeleton from '../components/skeleton/TableSkeleton.vue'
import { useChartTheme } from '../composables/use-chart-theme'
import {
  formatPrice,
  formatPct,
  getPctColor,
  formatMarketCap,
  formatNumber,
  formatZScore,
  getZScoreColor,
} from '../utils/format'
import { exportSelectionResults } from '../utils/export'
import { PhMagnifyingGlass, PhCursorClick, PhPlay, PhDownloadSimple } from '@phosphor-icons/vue'
import type { SelectionRecord } from '../types/selection'

const router = useRouter()
const strategyStore = useStrategyStore()
const selectionStore = useSelectionStore()
const message = useMessage()
const { theme } = useChartTheme()

const selectedStrategy = ref<string | null>(null)
const selectedStock = ref<SelectionRecord | null>(null)
const running = ref(false)
const preparing = ref(false)
const prepareMessage = ref('')
const searchText = ref('')
const fetchError = ref<string | null>(null)

// Card mode: show card list instead of table on smaller screens
const isCardMode = ref(false)

function updateCardMode() {
  isCardMode.value = window.innerWidth < 1280
}

const filteredResults = computed(() => {
  if (!searchText.value) return selectionStore.results
  const q = searchText.value.toLowerCase()
  return selectionStore.results.filter((r) => r.ts_code.toLowerCase().includes(q))
})

const strategyOptions = computed(() =>
  strategyStore.strategies
    .filter((s) => s.is_active)
    .map((s) => ({
      label: s.display_name || s.name || s.id,
      value: s.id,
    }))
)

const hasStrategies = computed(() => strategyStore.strategies.length > 0)

const currentStrategy = computed(() =>
  strategyStore.strategies.find((s) => s.id === selectedStrategy.value)
)

const columns: DataTableColumns<SelectionRecord> = [
  {
    title: '#',
    key: 'rank',
    width: 60,
    fixed: 'left',
    sortOrder: 'ascend',
    sorter: (a, b) => a.rank - b.rank,
    render(row) {
      return h('span', { class: 'data-mono text-[var(--color-text-secondary)]' }, row.rank)
    },
  },
  {
    title: '代码',
    key: 'ts_code',
    width: 120,
    fixed: 'left',
    render(row) {
      return h(
        'a',
        {
          class: 'data-mono text-[var(--color-accent)] cursor-pointer hover:underline',
          onClick: (e: Event) => {
            e.stopPropagation()
            router.push(`/stock/${row.ts_code}`)
          },
        },
        row.ts_code
      )
    },
  },
  {
    title: '名称',
    key: 'name',
    width: 100,
    render(row) {
      return h('span', { class: 'text-sm text-[var(--color-text-secondary)]' }, row.name || '-')
    },
  },
  {
    title: '行业',
    key: 'industry',
    width: 100,
    render(row) {
      return h('span', { class: 'text-xs text-[var(--color-text-muted)]' }, row.industry || '-')
    },
  },
  {
    title: '最新价',
    key: 'close',
    width: 100,
    align: 'right',
    sorter: (a, b) => (a.close ?? 0) - (b.close ?? 0),
    render(row) {
      const colorClass = getPctColor(row.pct_change)
      return h(
        'span',
        { class: `data-mono text-sm font-medium ${colorClass}` },
        formatPrice(row.close)
      )
    },
  },
  {
    title: '涨跌幅',
    key: 'pct_change',
    width: 110,
    align: 'right',
    sorter: (a, b) => (a.pct_change ?? 0) - (b.pct_change ?? 0),
    render(row) {
      const colorClass = getPctColor(row.pct_change)
      return h(
        'span',
        { class: `data-mono text-sm font-medium ${colorClass}` },
        formatPct(row.pct_change)
      )
    },
  },
  {
    title: 'PE',
    key: 'pe_ttm',
    width: 90,
    align: 'right',
    sorter: (a, b) => (a.pe_ttm ?? 0) - (b.pe_ttm ?? 0),
    render(row) {
      return h(
        'span',
        { class: 'data-mono text-sm text-[var(--color-text-secondary)]' },
        formatNumber(row.pe_ttm)
      )
    },
  },
  {
    title: 'PB',
    key: 'pb',
    width: 90,
    align: 'right',
    sorter: (a, b) => (a.pb ?? 0) - (b.pb ?? 0),
    render(row) {
      return h(
        'span',
        { class: 'data-mono text-sm text-[var(--color-text-secondary)]' },
        formatNumber(row.pb)
      )
    },
  },
  {
    title: '总市值',
    key: 'market_cap',
    width: 120,
    align: 'right',
    sorter: (a, b) => (a.market_cap ?? 0) - (b.market_cap ?? 0),
    render(row) {
      return h(
        'span',
        { class: 'data-mono text-sm text-[var(--color-text-secondary)]' },
        formatMarketCap(row.market_cap)
      )
    },
  },
  {
    title: '评分',
    key: 'composite_score',
    width: 100,
    align: 'right',
    sorter: (a, b) => a.composite_score - b.composite_score,
    render(row) {
      return h(
        'span',
        {
          class: `data-mono font-medium ${getZScoreColor(row.composite_score)}`,
          title: `加权 Z-Score: ${formatZScore(row.composite_score)}\n典型范围 [-3, +3]，0 为均值`,
        },
        formatZScore(row.composite_score)
      )
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 90,
    fixed: 'right',
    render(row) {
      const type = row.status === 'OK' ? 'success' : 'warning'
      return h(NTag, { type, size: 'small', round: true, bordered: false }, () => row.status)
    },
  },
]

async function handleRun() {
  if (!selectedStrategy.value) {
    message.warning('请先选择策略')
    return
  }
  running.value = true
  preparing.value = false
  prepareMessage.value = ''

  const maxPolls = 30
  const pollIntervalMs = 3000

  try {
    const res = await runSelection({
      strategy_id: selectedStrategy.value,
    })

    const count = res?.final_count ?? res?.results?.length ?? 0
    const universe = res?.universe_count ?? 0
    if (universe === 0) {
      message.warning('没有可用的因子数据, 请到数据页面手动同步')
    } else if (count === 0) {
      message.warning(`从 ${universe} 只股票中未选出候选, 请检查策略配置`)
    } else {
      message.success(`选股完成: 从 ${universe} 只股票中选出 ${count} 只`)
    }
    await selectionStore.fetchResults(selectedStrategy.value ?? undefined)
  } catch (e: any) {
    const status = e?.response?.status
    const data = e?.response?.data

    if (status === 202 || data?.status === 'preparing') {
      const tradeDate: string = data?.trade_date ?? ''
      preparing.value = true
      prepareMessage.value = '正在准备全市场数据...'

      for (let i = 0; i < maxPolls; i++) {
        await new Promise((r) => setTimeout(r, pollIntervalMs))
        prepareMessage.value = `正在准备数据... (${((i + 1) * pollIntervalMs) / 1000}s)`

        try {
          const ps = await getPrepareStatus(tradeDate)
          if (ps.status === 'done') {
            preparing.value = false
            prepareMessage.value = ''
            message.info('数据准备完成, 正在执行选股...')
            await handleRun()
            return
          }
          if (ps.status === 'failed') {
            preparing.value = false
            prepareMessage.value = ''
            message.error(`数据准备失败: ${ps.error || '未知错误'}`)
            return
          }
        } catch (pollErr) {
          console.warn('轮询状态失败, 继续等待:', pollErr)
        }
      }

      preparing.value = false
      prepareMessage.value = ''
      message.error('数据准备超时 (超过 90 秒), 请稍后重试')
    }
  } finally {
    if (!preparing.value) {
      running.value = false
    }
  }
}

const today = new Date().toLocaleDateString('zh-CN')

function handleExport() {
  if (filteredResults.value.length === 0) {
    message.warning('没有可导出的数据')
    return
  }

  const strategyName =
    currentStrategy.value?.display_name || currentStrategy.value?.name || 'unknown'
  const tradeDate = selectionStore.results[0]?.trade_date || 'unknown'

  exportSelectionResults(filteredResults.value, strategyName, tradeDate)
  message.success(`已导出 ${filteredResults.value.length} 条记录`)
}

function handleRowClick(row: SelectionRecord) {
  selectedStock.value = row
}

function handleCardClick(item: SelectionRecord) {
  handleRowClick(item)
  router.push(`/stock/${item.ts_code}`)
}

function rowClassName(row: SelectionRecord) {
  const base = 'cursor-pointer transition-colors'
  if (row === selectedStock.value) return `${base} row--selected`
  return base
}

onMounted(async () => {
  updateCardMode()
  window.addEventListener('resize', updateCardMode)

  fetchError.value = null
  try {
    await strategyStore.fetchStrategies({ silent: true })
  } catch (e: any) {
    fetchError.value = e?.response?.data?.detail || e?.message || '无法连接后端, 请检查网络'
    return
  }
  if (strategyStore.strategies.length > 0) {
    selectedStrategy.value = strategyStore.strategies[0].id
    await selectionStore.fetchResults(selectedStrategy.value)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', updateCardMode)
})

watch(selectedStrategy, async (val) => {
  if (val) {
    try {
      await selectionStore.fetchResults(val)
    } catch (e: any) {
      // 忽略请求取消错误（来自 client.ts 的请求去重机制）
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return
      console.error('Failed to fetch selection results:', e)
    }
  }
})

async function onRetry() {
  fetchError.value = null
  try {
    await strategyStore.fetchStrategies({ silent: true })
  } catch (e: any) {
    fetchError.value = e?.response?.data?.detail || e?.message || '无法连接后端, 请检查网络'
    return
  }
  if (strategyStore.strategies.length > 0) {
    selectedStrategy.value = strategyStore.strategies[0].id
    try {
      await selectionStore.fetchResults(selectedStrategy.value)
    } catch (e: any) {
      // 忽略请求取消错误
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return
      fetchError.value = e?.response?.data?.detail || e?.message || '无法加载选股结果'
    }
  }
}
</script>

<template>
  <div class="selection-workspace">
    <!-- Error banner: left-border pattern -->
    <div v-if="fetchError" class="error-banner">
      <div class="error-bar" />
      <div class="error-body">
        <p class="error-msg">{{ fetchError }}</p>
        <NButton size="small" @click="onRetry">重新加载</NButton>
      </div>
    </div>

    <!-- Strategy empty state -->
    <div v-else-if="!hasStrategies && !strategyStore.loading" class="strategy-empty">
      <div class="strategy-empty-icon">
        <PhCursorClick :size="64" class="text-[var(--color-text-muted)]" />
      </div>
      <h2 class="strategy-empty-title">暂无活跃策略</h2>
      <p class="strategy-empty-desc">创建策略后开始选股</p>
      <NButton @click="router.push('/strategy/list')">管理策略</NButton>
    </div>

    <!-- Main workspace -->
    <template v-else>
      <!-- Workspace header -->
      <header class="workspace-header">
        <div class="header-main">
          <div class="header-identity">
            <span class="header-label">当前策略</span>
            <h2 class="header-title">
              {{ currentStrategy?.display_name || currentStrategy?.name || '选择策略' }}
            </h2>
          </div>
          <div class="header-controls">
            <NSelect
              v-model:value="selectedStrategy"
              :options="strategyOptions"
              placeholder="选择策略"
              class="w-52"
            />
            <NButton type="primary" :loading="running" :disabled="preparing" @click="handleRun">
              <template #icon>
                <PhPlay :size="16" weight="fill" />
              </template>
              {{ preparing ? prepareMessage : '运行选股' }}
            </NButton>
          </div>
        </div>
        <div class="header-meta">
          <span>{{ today }}</span>
          <span class="meta-sep" />
          <span
            v-if="searchText && filteredResults.length !== selectionStore.results.length"
            class="meta-count"
          >
            筛选:
            <strong>{{ filteredResults.length }}</strong>
            / {{ selectionStore.results.length }} 只
          </span>
          <span v-else class="meta-count">{{ selectionStore.results.length }} 只候选</span>
        </div>
      </header>

      <!-- Loading indicator: skeleton -->
      <div v-if="selectionStore.loading && selectionStore.results.length === 0" class="table-frame">
        <TableSkeleton :columns="6" :rows="10" />
      </div>

      <!-- Two-panel workspace -->
      <div class="workspace-panels">
        <!-- Left: table area -->
        <div class="panel-table">
          <div class="search-row">
            <NInput
              v-model:value="searchText"
              placeholder="搜索股票代码..."
              clearable
              size="small"
              class="search-input"
            >
              <template #prefix>
                <PhMagnifyingGlass :size="14" class="text-[var(--color-text-muted)]" />
              </template>
            </NInput>
            <NButton
              size="small"
              secondary
              :disabled="filteredResults.length === 0"
              @click="handleExport"
            >
              <template #icon>
                <PhDownloadSimple :size="14" />
              </template>
              导出 CSV
            </NButton>
          </div>
          <!-- Card mode (small screens) -->
          <div v-if="isCardMode" class="card-list">
            <div
              v-for="item in filteredResults"
              :key="item.ts_code"
              class="stock-card"
              :class="{ 'stock-card--selected': item === selectedStock }"
              @click="handleCardClick(item)"
            >
              <div class="stock-card__header">
                <div class="stock-card__identity">
                  <span class="stock-card__rank">#{{ item.rank }}</span>
                  <div>
                    <div class="stock-card__name">{{ item.name || '-' }}</div>
                    <div class="stock-card__code">{{ item.ts_code }}</div>
                  </div>
                </div>
                <div class="stock-card__score">
                  <span
                    class="stock-card__score-value"
                    :class="getZScoreColor(item.composite_score)"
                  >
                    {{ formatZScore(item.composite_score) }}
                  </span>
                  <span class="stock-card__score-label">综合因子</span>
                </div>
              </div>
              <div class="stock-card__metrics">
                <div class="stock-card__metric">
                  <span class="stock-card__metric-label">行业</span>
                  <span class="stock-card__metric-value">{{ item.industry || '-' }}</span>
                </div>
                <div class="stock-card__metric">
                  <span class="stock-card__metric-label">最新价</span>
                  <span
                    class="stock-card__metric-value font-medium"
                    :class="getPctColor(item.pct_change)"
                  >
                    {{ formatPrice(item.close) }}
                  </span>
                </div>
                <div class="stock-card__metric">
                  <span class="stock-card__metric-label">涨跌幅</span>
                  <span
                    class="stock-card__metric-value font-medium"
                    :class="getPctColor(item.pct_change)"
                  >
                    {{ formatPct(item.pct_change) }}
                  </span>
                </div>
                <div class="stock-card__metric">
                  <span class="stock-card__metric-label">PE</span>
                  <span class="stock-card__metric-value">{{ formatNumber(item.pe_ttm) }}</span>
                </div>
                <div class="stock-card__metric">
                  <span class="stock-card__metric-label">PB</span>
                  <span class="stock-card__metric-value">{{ formatNumber(item.pb) }}</span>
                </div>
                <div class="stock-card__metric">
                  <span class="stock-card__metric-label">总市值</span>
                  <span class="stock-card__metric-value">
                    {{ formatMarketCap(item.market_cap) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Table mode (desktop) -->
          <div v-else class="table-frame">
            <NDataTable
              :columns="columns"
              :data="filteredResults"
              :loading="selectionStore.loading"
              :virtual-scroll="true"
              :max-height="580"
              :scroll-x="1080"
              :row-key="(row: SelectionRecord) => row.ts_code"
              :row-class-name="rowClassName"
              @row-click="handleRowClick"
              size="small"
              striped
            />
          </div>
        </div>

        <!-- Right: factor detail panel -->
        <aside class="panel-detail">
          <template v-if="selectedStock">
            <div class="detail-section-label">因子画像</div>
            <div class="detail-stock-header">
              <div class="stock-id-row">
                <span class="stock-code">{{ selectedStock.ts_code }}</span>
                <NTag size="small" :bordered="false" type="info">#{{ selectedStock.rank }}</NTag>
              </div>
              <div class="stock-score-row">
                <NTooltip trigger="hover">
                  <template #trigger>
                    <span
                      class="score-big cursor-help"
                      :class="getZScoreColor(selectedStock.composite_score)"
                    >
                      {{ formatZScore(selectedStock.composite_score) }}
                    </span>
                  </template>
                  加权 Z-Score (跨期可比)
                </NTooltip>
                <span class="score-sigma">(σ)</span>
                <span class="score-date">{{ selectedStock.trade_date }}</span>
              </div>
            </div>
            <div class="detail-chart">
              <FactorRadar
                v-if="
                  selectedStock.factor_snapshot && Object.keys(selectedStock.factor_snapshot).length
                "
                :factors="selectedStock.factor_snapshot"
                :theme="theme"
              />
            </div>
            <NButton
              type="primary"
              ghost
              class="detail-cta w-full"
              @click="router.push(`/stock/${selectedStock.ts_code}`)"
            >
              查看详情
            </NButton>
          </template>

          <template v-else>
            <!-- Strategy context -->
            <div v-if="currentStrategy" class="detail-strategy-context">
              <div class="detail-ctx-label">当前策略</div>
              <div class="detail-ctx-name">
                {{ currentStrategy.display_name || currentStrategy.name }}
              </div>
              <div class="detail-ctx-meta">
                <span>{{ currentStrategy.category }}</span>
                <span v-if="currentStrategy.is_active" class="text-[var(--color-success,#22c55e)]">
                  活跃
                </span>
              </div>
            </div>

            <!-- Radar placeholder (inline SVG) -->
            <div class="detail-empty-visual">
              <div class="radar-ghost">
                <svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle
                    cx="60"
                    cy="60"
                    r="54"
                    stroke="currentColor"
                    stroke-dasharray="4 4"
                    opacity="0.5"
                  />
                  <circle
                    cx="60"
                    cy="60"
                    r="36"
                    stroke="currentColor"
                    stroke-dasharray="3 3"
                    opacity="0.35"
                  />
                  <circle cx="60" cy="60" r="18" stroke="currentColor" opacity="0.25" />
                  <line
                    x1="60"
                    y1="6"
                    x2="60"
                    y2="114"
                    stroke="currentColor"
                    stroke-dasharray="3 5"
                    opacity="0.3"
                  />
                  <line
                    x1="6"
                    y1="60"
                    x2="114"
                    y2="60"
                    stroke="currentColor"
                    stroke-dasharray="3 5"
                    opacity="0.3"
                  />
                  <line
                    x1="22"
                    y1="22"
                    x2="98"
                    y2="98"
                    stroke="currentColor"
                    stroke-dasharray="3 5"
                    opacity="0.2"
                  />
                  <line
                    x1="98"
                    y1="22"
                    x2="22"
                    y2="98"
                    stroke="currentColor"
                    stroke-dasharray="3 5"
                    opacity="0.2"
                  />
                </svg>
              </div>
              <p class="detail-empty-text">点击表格行查看因子画像</p>
            </div>
          </template>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* ===== Root layout ===== */
.selection-workspace {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ===== Error Banner ===== */
.error-banner {
  display: flex;
  border-radius: 8px;
  overflow: hidden;
  background: var(--color-surface-elevated);
  border: 1px solid rgba(239, 68, 68, 0.15);
}
.error-bar {
  width: 4px;
  flex-shrink: 0;
  background: var(--color-error);
}
.error-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.04);
}
.error-msg {
  font-size: 13px;
  color: var(--color-error);
  margin: 0;
  line-height: 1.5;
}

/* ===== Strategy Empty State ===== */
.strategy-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 32px;
  text-align: center;
}
.strategy-empty-icon {
  width: 100px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--color-surface-inset);
  margin-bottom: 28px;
  opacity: 0.5;
}
.strategy-empty-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0 0 8px;
  letter-spacing: -0.02em;
}
.strategy-empty-desc {
  font-size: 14px;
  color: var(--color-text-muted);
  margin: 0 0 28px;
}

/* ===== Workspace Header ===== */
.workspace-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.header-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.header-identity {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.header-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}
.header-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0;
  letter-spacing: -0.025em;
  line-height: 1.2;
}
.header-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.header-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--color-text-muted);
}
.meta-sep {
  display: inline-block;
  width: 1px;
  height: 12px;
  background: var(--color-border-muted);
  vertical-align: middle;
}
.meta-count {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.meta-count strong {
  color: var(--color-text-primary);
  font-weight: 600;
}

/* ===== Workspace Panels ===== */
.workspace-panels {
  display: flex;
  gap: 0;
  min-height: 600px;
}

/* ===== Left: Table Panel ===== */
.panel-table {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.search-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.search-input {
  flex: 1;
  max-width: 240px;
}
.search-input :deep(.n-input) {
  --n-border: 1px solid var(--color-border) !important;
  --n-border-hover: 1px solid var(--color-border-muted) !important;
}
.table-frame {
  background: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}

/* ===== Table: selected row ===== */
.row--selected td {
  background: var(--color-accent-muted) !important;
}
.row--selected td:first-child {
  box-shadow: inset 2px 0 0 var(--color-accent);
}

/* ===== Table: row hover ===== */
:deep(.n-data-table-tr:hover) td {
  background: var(--color-surface-inset) !important;
}
:deep(.n-data-table-tr) {
  cursor: pointer;
  transition: background-color 0.1s ease;
}

/* ===== Table: header ===== */
:deep(.n-data-table-thead) {
  background: var(--color-surface-inset) !important;
}
:deep(.n-data-table-th) {
  color: var(--color-text-secondary) !important;
  font-weight: 500 !important;
  font-size: 12px !important;
  letter-spacing: 0.02em;
}

/* ===== Right: Detail Panel ===== */
.panel-detail {
  width: 380px;
  flex-shrink: 0;
  border-left: 1px solid var(--color-border);
  padding-left: 24px;
  display: flex;
  flex-direction: column;
}
.detail-section-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
  margin-bottom: 16px;
  padding-top: 2px;
}
.detail-stock-header {
  margin-bottom: 20px;
}
.stock-id-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.stock-code {
  font-size: 18px;
  font-weight: 700;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-primary);
}
.stock-score-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.score-big {
  font-size: 32px;
  font-weight: 700;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-primary);
  letter-spacing: -0.03em;
  line-height: 1;
}
.score-sigma {
  font-size: 14px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}
.score-date {
  font-size: 12px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.detail-chart {
  flex: 1;
  min-height: 0;
}
.detail-cta {
  margin-top: 20px;
}

/* ===== Detail: empty state ===== */
.detail-strategy-context {
  padding-bottom: 20px;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 24px;
}
.detail-ctx-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
  margin-bottom: 6px;
}
.detail-ctx-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.detail-ctx-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-text-muted);
}
.detail-empty-visual {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 48px 0;
}
.radar-ghost {
  width: 140px;
  height: 140px;
  color: var(--color-border-muted);
  margin-bottom: 20px;
}
.radar-ghost svg {
  width: 100%;
  height: 100%;
}
.detail-empty-text {
  font-size: 13px;
  color: var(--color-text-muted);
  margin: 0;
  opacity: 0.7;
}

/* ===== Card list (mobile mode) ===== */
.card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 70vh;
  overflow-y: auto;
  padding: 2px;
}

.stock-card {
  background: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    border-color 0.15s ease;
}

.stock-card:active {
  background: var(--color-surface-inset);
}

.stock-card--selected {
  border-color: var(--color-accent);
  background: var(--color-accent-muted);
}

.stock-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}

.stock-card__identity {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stock-card__rank {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-accent);
  background: var(--color-accent-muted);
  padding: 2px 8px;
  border-radius: 6px;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.stock-card__name {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.3;
}

.stock-card__code {
  font-size: 12px;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-muted);
  margin-top: 1px;
}

.stock-card__score {
  text-align: right;
  flex-shrink: 0;
}

.stock-card__score-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.stock-card__score-label {
  display: block;
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.stock-card__metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
}

.stock-card__metric {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.stock-card__metric-label {
  font-size: 11px;
  color: var(--color-text-muted);
}

.stock-card__metric-value {
  font-size: 13px;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-primary);
}

/* ===== Responsive: stack panels below 768px ===== */
@media (max-width: 1023px) {
  .workspace-panels {
    flex-direction: column;
  }
  .panel-detail {
    width: 100%;
    border-left: none;
    border-top: 1px solid var(--color-border);
    padding-left: 0;
    padding-top: 24px;
    margin-top: 24px;
  }
  .search-row {
    flex-wrap: wrap;
  }
  .search-input {
    flex: 1;
    min-width: 160px;
  }
  .header-main {
    flex-direction: column;
    align-items: stretch;
  }
  .header-controls {
    width: 100%;
    height: 44px;
  }
  .header-controls :deep(.n-select) {
    flex: 1;
  }
  .header-controls :deep(.n-button) {
    height: 44px;
  }
}

@media (max-width: 768px) {
  .workspace-header {
    gap: 8px;
  }
  .header-title {
    font-size: 20px;
  }
  .card-list {
    max-height: none;
  }
}

/* Touch: disable hover sticky on touch devices */
@media (hover: none) {
  .stock-card:hover {
    background: var(--color-surface-elevated);
  }
  .stock-card--selected:hover {
    background: var(--color-accent-muted);
  }
}
</style>
