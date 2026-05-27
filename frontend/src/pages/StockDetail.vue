<script setup lang="ts">
import { computed, toRef } from 'vue'
import { NSpin, NAlert, NTag, NSkeleton } from 'naive-ui'
import StockHeader from '../components/common/StockHeader.vue'
import KLineChart from '../components/charts/KLineChart.vue'
import FactorRadar from '../components/charts/FactorRadar.vue'
import FactorHistory from '../components/charts/FactorHistory.vue'
import FinancialTrend from '../components/FinancialTrend.vue'
import { useStockDetail } from '../composables/use-stock-detail'
import { FACTOR_LABELS, FACTOR_CATEGORIES } from '../utils/constants'

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

/** Sorted factor entries for the metrics list, grouped by category */
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

function getBarColor(value: number): string {
  if (value >= 70) return 'bg-up'
  if (value <= 30) return 'bg-down'
  return 'bg-[var(--color-text-muted)]'
}

const lastKline = computed(() => {
  if (klines.value.length === 0) return null
  return klines.value[klines.value.length - 1]
})
</script>

<template>
  <NSpin :show="loading" class="min-h-[60vh]">
    <!-- Breadcrumb navigation -->
    <div class="flex items-center gap-2 text-sm mb-4">
      <router-link to="/" class="text-[var(--color-accent)] hover:underline">选股</router-link>
      <span class="text-[var(--color-text-muted)]">/</span>
      <span class="text-[var(--color-text-secondary)]">{{ stockInfo?.name || ts_code }}</span>
    </div>

    <div v-if="error && !stockInfo" class="mb-4">
      <NAlert type="error" :title="error">
        <button
          class="mt-2 px-3 py-1.5 text-sm rounded-lg bg-[var(--color-surface-inset)] border border-[var(--color-border)] hover:bg-[var(--color-border)] transition-colors"
          @click="reload"
        >
          重新加载
        </button>
      </NAlert>
    </div>

    <div v-if="stockInfo" class="flex flex-col gap-6">
      <!-- Stock Header -->
      <StockHeader
        :name="stockInfo.name || '未知'"
        :ts_code="stockInfo.ts_code"
        :industry="stockInfo.industry"
        :close="lastKline?.close ?? null"
        :pct_change="lastKline?.pct_chg ?? null"
      />

      <!-- Main Grid: K-line (2/3) + Factor sidebar (1/3) -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
        <!-- K-line Chart -->
        <div class="lg:col-span-2 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] p-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">K线走势</h3>
            <NTag v-if="mockKline" size="small" type="warning" :bordered="false">
              示例数据
            </NTag>
          </div>
          <KLineChart :data="klines" />
        </div>

        <!-- Factor Sidebar -->
        <div class="flex flex-col gap-4 lg:gap-6">
          <!-- Factor Radar -->
          <div class="rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] p-5">
            <div class="flex items-center justify-between mb-2">
              <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">因子画像</h3>
              <NTag v-if="mockFactors" size="small" type="warning" :bordered="false">
                示例数据
              </NTag>
            </div>
            <FactorRadar :factors="factorSnapshot" />
          </div>

          <!-- Factor Metrics List -->
          <div class="rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] p-5">
            <h3 class="text-sm font-semibold text-[var(--color-text-primary)] mb-3">因子评分</h3>
            <div v-if="factorEntries.length === 0" class="text-sm text-[var(--color-text-muted)] py-4 text-center">
              暂无因子数据
            </div>
            <div v-else class="flex flex-col gap-1">
              <template v-for="cat in Object.keys(FACTOR_CATEGORIES)" :key="cat">
                <div class="text-xs font-semibold uppercase tracking-wider text-[var(--color-accent)] mt-3 mb-1.5 first:mt-0">
                  {{ categoryLabels[cat] || cat }}
                </div>
                <div
                  v-for="entry in factorEntries.filter((e) => e.category === cat)"
                  :key="entry.key"
                  class="flex items-center gap-2 py-1"
                >
                  <span class="text-xs text-[var(--color-text-secondary)] w-16 shrink-0 truncate">
                    {{ entry.label }}
                  </span>
                  <div class="flex-1 h-1.5 bg-[var(--color-border)] rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full transition-all"
                      :class="getBarColor(entry.value)"
                      :style="{ width: `${entry.value}%` }"
                    />
                  </div>
                  <span class="text-xs font-mono text-[var(--color-text-secondary)] w-8 text-right">
                    {{ entry.value }}
                  </span>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Below Grid: Financial Trend + Factor History -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
        <div class="rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] p-5">
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">财务趋势</h3>
            <NTag size="small" type="warning" :bordered="false">示例数据</NTag>
          </div>
          <FinancialTrend
            :quarters="financialTrend.quarters"
            :rev-growth="financialTrend.revGrowth"
            :ear-growth="financialTrend.earGrowth"
            :gross-margin="financialTrend.grossMargin"
          />
        </div>

        <div class="rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)] p-5">
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">因子历史</h3>
            <NTag v-if="mockFactors" size="small" type="warning" :bordered="false">
              示例数据
            </NTag>
          </div>
          <FactorHistory
            :dates="factorHistory.dates"
            :factors="factorHistory.factors"
          />
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="!loading && !stockInfo && !error"
      class="flex flex-col items-center justify-center py-20"
    >
      <svg class="w-12 h-12 text-[var(--color-text-muted)] mb-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M3 3v18h18" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M7 14l4-4 4 4 5-5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <div class="text-base text-[var(--color-text-secondary)] mb-1">未找到股票数据</div>
      <div class="text-sm text-[var(--color-text-muted)]">请检查股票代码是否正确</div>
    </div>
  </NSpin>
</template>
