<script setup lang="ts">
/**
 * Stock detail page: K-line, factor radar, factor metrics, financial trend, factor history.
 * 个股详情页: K线、因子雷达、因子评分、财务趋势、因子历史。
 */
import { computed, toRef } from 'vue'
import { NSpin, NAlert, NTag, NButton } from 'naive-ui'
import StockHeader from '../components/common/StockHeader.vue'
import KLineChart from '../components/charts/KLineChart.vue'
import FactorRadar from '../components/charts/FactorRadar.vue'
import FactorHistory from '../components/charts/FactorHistory.vue'
import FinancialTrend from '../components/FinancialTrend.vue'
import { useStockDetail } from '../composables/use-stock-detail'
import { useChartTheme } from '../composables/use-chart-theme'
import { FACTOR_LABELS, FACTOR_CATEGORIES } from '../utils/constants'
import { PhHouse, PhArrowLeft } from '@phosphor-icons/vue'

const props = defineProps<{
  ts_code: string
}>()

const {
  stockInfo,
  klines,
  factorSnapshot,
  factorHistory,
  financialTrend,
  mockKline,
  mockFactors,
  loading,
  error,
  reload,
} = useStockDetail(toRef(props, 'ts_code'))

const { theme } = useChartTheme()

/** Sorted factor entries grouped by category */
const factorEntries = computed(() => {
  const snapshot = factorSnapshot.value
  const entries: { key: string; label: string; value: number; category: string }[] = []
  for (const [cat, keys] of Object.entries(FACTOR_CATEGORIES)) {
    for (const key of keys) {
      if (key in snapshot) {
        entries.push({
          key,
          label: FACTOR_LABELS[key] || key,
          value: Math.round(snapshot[key]),
          category: cat,
        })
      }
    }
  }
  return entries
})

const categoryLabels: Record<string, string> = {
  value: '估值',
  momentum: '动量',
  quality: '质量',
  size: '规模',
}

function getBarStyle(value: number): string {
  if (value >= 70) return 'background-color: var(--color-accent);'
  if (value <= 30) return 'background-color: var(--color-text-muted);'
  return 'background-color: var(--color-primary);'
}

const lastKline = computed(() => {
  if (klines.value.length === 0) return null
  return klines.value[klines.value.length - 1]
})
</script>

<template>
  <NSpin :show="loading" class="min-h-[60vh]">
    <!-- Back navigation -->
    <router-link
      v-if="stockInfo"
      to="/selection"
      class="inline-flex items-center gap-1.5 text-[13px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors mb-2"
    >
      <PhArrowLeft :size="14" />
      <span>返回选股</span>
    </router-link>

    <!-- Error state: left-border pattern -->
    <div v-if="error && !stockInfo" class="error-banner mb-6">
      <div class="error-bar"></div>
      <div class="error-body">
        <p class="error-msg">{{ error }}</p>
        <NButton size="small" @click="reload">重新加载</NButton>
      </div>
    </div>

    <div v-if="stockInfo" class="flex flex-col gap-8">
      <!-- Stock Header -->
      <StockHeader
        :name="stockInfo.name || '未知'"
        :ts_code="stockInfo.ts_code"
        :industry="stockInfo.industry"
        :close="lastKline?.close ?? null"
        :pct_change="lastKline?.pct_chg ?? null"
      />

      <!-- Main Grid: K-line (2/3) + Factor sidebar (1/3) -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- K-line Chart -->
        <div class="lg:col-span-2 flex flex-col gap-2.5">
          <div class="flex items-center justify-between px-1">
            <span class="section-label">价格走势</span>
            <span v-if="mockKline" class="mock-tag">示例数据</span>
          </div>
          <div class="glass-panel p-5">
            <KLineChart :data="klines" />
          </div>
        </div>

        <!-- Factor Sidebar -->
        <div class="flex flex-col gap-6">
          <!-- Factor Radar -->
          <div class="flex flex-col gap-2.5">
            <div class="flex items-center justify-between px-1">
              <span class="section-label">因子画像</span>
              <span v-if="mockFactors" class="mock-tag">示例数据</span>
            </div>
            <div class="glass-panel p-5">
              <FactorRadar :factors="factorSnapshot" :theme="theme" />
            </div>
          </div>

          <!-- Factor Metrics List -->
          <div class="flex flex-col gap-2.5">
            <span class="section-label px-1">因子评分</span>
            <div class="glass-panel p-5">
              <div
                v-if="factorEntries.length === 0"
                class="text-sm text-[var(--color-text-muted)] py-6 text-center"
              >
                暂无因子数据
              </div>
              <div v-else class="flex flex-col">
                <template v-for="cat in Object.keys(FACTOR_CATEGORIES)" :key="cat">
                  <div class="flex items-center gap-2 mt-3 mb-2 first:mt-0">
                    <span class="category-badge">
                      {{ categoryLabels[cat] || cat }}
                    </span>
                  </div>
                  <div
                    v-for="entry in factorEntries.filter((e) => e.category === cat)"
                    :key="entry.key"
                    class="factor-row"
                  >
                    <span class="factor-label">
                      {{ entry.label }}
                    </span>
                    <div class="factor-bar-track">
                      <div
                        class="factor-bar-fill"
                        :style="[getBarStyle(entry.value), { width: `${entry.value}%` }]"
                      />
                    </div>
                    <span class="factor-value">
                      {{ entry.value }}
                    </span>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Lower Grid: Financial Trend + Factor History -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="flex flex-col gap-2.5">
          <div class="flex items-center justify-between px-1">
            <span class="section-label">财务趋势</span>
            <span class="mock-tag">示例数据</span>
          </div>
          <div class="glass-panel p-5">
            <FinancialTrend
              :quarters="financialTrend.quarters"
              :rev-growth="financialTrend.revGrowth"
              :ear-growth="financialTrend.earGrowth"
              :gross-margin="financialTrend.grossMargin"
            />
          </div>
        </div>

        <div class="flex flex-col gap-2.5">
          <div class="flex items-center justify-between px-1">
            <span class="section-label">因子历史</span>
            <span v-if="mockFactors" class="mock-tag">示例数据</span>
          </div>
          <div class="glass-panel p-5">
            <FactorHistory
              :dates="factorHistory.dates"
              :factors="factorHistory.factors"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="!loading && !stockInfo && !error"
      class="flex flex-col items-center justify-center py-20"
    >
      <div class="empty-icon-ring">
        <PhArrowLeft :size="22" class="text-[var(--color-text-muted)]" />
      </div>
      <div class="text-sm text-[var(--color-text-secondary)] mb-1">
        未找到股票数据
      </div>
      <div class="text-xs text-[var(--color-text-muted)]">
        请检查股票代码是否正确
      </div>
    </div>
  </NSpin>
</template>

<style scoped>
.section-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}

.mock-tag {
  font-size: 10px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--color-warning);
  background: rgba(245, 158, 11, 0.08);
  letter-spacing: 0.02em;
}

/* Error banner: left-border accent pattern */
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

/* Factor category badge */
.category-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  background: var(--color-accent-muted);
  color: var(--color-accent);
}

/* Factor row: subtle divider between entries */
.factor-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid var(--color-glass-highlight);
}
.factor-row:last-child {
  border-bottom: none;
}
.factor-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  width: 60px;
  flex-shrink: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.factor-bar-track {
  flex: 1;
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}
.factor-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.factor-value {
  font-size: 12px;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-secondary);
  width: 28px;
  text-align: right;
  flex-shrink: 0;
}

/* Empty state icon ring */
.empty-icon-ring {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--color-surface-inset);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  opacity: 0.4;
}
</style>
