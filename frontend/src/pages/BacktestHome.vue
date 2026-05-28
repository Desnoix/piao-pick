<script setup lang="ts">
/**
 * Backtest home: past backtest results table.
 * 回测主页: 展示历史回测结果表格。
 */
import { h, ref, onMounted } from 'vue'
import { NDataTable, NButton } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import { PhClockCounterClockwise, PhChartLineUp } from '@phosphor-icons/vue'
import { listBacktestResults } from '../api/backtest'
import TableSkeleton from '../components/skeleton/TableSkeleton.vue'
import type { BacktestResult } from '../types/backtest'

const router = useRouter()

const results = ref<BacktestResult[]>([])
const loading = ref(false)

function formatPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '-'
  const sign = v > 0 ? '+' : ''
  return `${sign}${(v * 100).toFixed(2)}%`
}

function pctClass(v: number | null | undefined): string {
  if (v === null || v === undefined) return ''
  return v >= 0 ? 'text-up' : 'text-down'
}

function formatDrawdown(v: number | null | undefined): string {
  if (v === null || v === undefined) return '-'
  const abs = Math.abs(v)
  return `-${(abs * 100).toFixed(2)}%`
}

function drawdownClass(v: number | null | undefined): string {
  if (v === null || v === undefined) return ''
  return 'text-down'
}

function formatSharpe(v: number | null | undefined): string {
  if (v === null || v === undefined) return '-'
  return v.toFixed(2)
}

const columns: DataTableColumns<BacktestResult> = [
  {
    title: '策略ID',
    key: 'strategy_id',
    width: 160,
    render(row) {
      return h(
        'a',
        {
          class: 'data-mono text-[var(--color-accent)] cursor-pointer hover:underline',
          onClick: (e: Event) => {
            e.stopPropagation()
            router.push(`/backtest/${row.strategy_id}`)
          },
        },
        row.strategy_id
      )
    },
  },
  {
    title: '区间',
    key: 'period',
    width: 200,
    render(row) {
      return h(
        'span',
        { class: 'text-xs text-[var(--color-text-secondary)]' },
        `${row.start_date} ~ ${row.end_date}`
      )
    },
  },
  {
    title: '总收益',
    key: 'total_return',
    width: 110,
    sorter: (a, b) => (a.total_return ?? 0) - (b.total_return ?? 0),
    render(row) {
      return h(
        'span',
        { class: `data-mono font-medium ${pctClass(row.total_return)}` },
        formatPct(row.total_return)
      )
    },
  },
  {
    title: '年化收益',
    key: 'annual_return',
    width: 110,
    sorter: (a, b) => (a.annual_return ?? 0) - (b.annual_return ?? 0),
    render(row) {
      return h(
        'span',
        { class: `data-mono font-medium ${pctClass(row.annual_return)}` },
        formatPct(row.annual_return)
      )
    },
  },
  {
    title: '最大回撤',
    key: 'max_drawdown',
    width: 110,
    sorter: (a, b) => (a.max_drawdown ?? 0) - (b.max_drawdown ?? 0),
    render(row) {
      return h(
        'span',
        { class: `data-mono font-medium ${drawdownClass(row.max_drawdown)}` },
        formatDrawdown(row.max_drawdown)
      )
    },
  },
  {
    title: '夏普比率',
    key: 'sharpe_ratio',
    width: 100,
    sorter: (a, b) => (a.sharpe_ratio ?? 0) - (b.sharpe_ratio ?? 0),
    render(row) {
      return h(
        'span',
        { class: 'data-mono text-[var(--color-text-primary)]' },
        formatSharpe(row.sharpe_ratio)
      )
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render(row) {
      return h(
        NButton,
        {
          size: 'small',
          type: 'primary',
          ghost: true,
          onClick: () => router.push(`/backtest/${row.strategy_id}`),
        },
        () => '查看详情'
      )
    },
  },
]

async function fetchResults() {
  loading.value = true
  try {
    results.value = await listBacktestResults()
  } catch (err: any) {
    // 忽略请求取消错误（来自 client.ts 的请求去重机制）
    if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
    console.error('Failed to fetch backtest results:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchResults()
})
</script>

<template>
  <div class="flex flex-col gap-8">
    <!-- Section header -->
    <div class="flex flex-col gap-0.5">
      <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
        历史回测
      </span>
      <span class="text-lg font-semibold text-[var(--color-text-primary)]">回测结果</span>
    </div>

    <!-- Loading: skeleton -->
    <div v-if="loading" class="glass-panel overflow-hidden">
      <TableSkeleton :columns="7" :rows="5" />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="results.length === 0"
      class="glass-panel flex flex-col items-center justify-center py-20"
    >
      <PhChartLineUp
        :size="64"
        class="mb-5 text-[var(--color-text-muted)] opacity-30"
        weight="duotone"
      />
      <p class="mb-2 text-base font-medium text-[var(--color-text-secondary)]">暂无回测记录</p>
      <p class="mb-5 text-sm text-[var(--color-text-muted)]">选择策略运行回测，查看历史表现</p>
      <NButton type="primary" ghost @click="router.push('/strategy/list')">前往策略管理</NButton>
    </div>

    <!-- Results table -->
    <div v-else class="glass-panel backtest-table overflow-hidden">
      <NDataTable
        :columns="columns"
        :data="results"
        :bordered="false"
        :row-key="(row: BacktestResult) => row.strategy_id + row.start_date + row.end_date"
        size="small"
        :single-line="false"
      />
    </div>
  </div>
</template>

<style scoped>
.backtest-table :deep(.n-data-table-thead) {
  background: var(--color-surface-inset) !important;
}

.backtest-table :deep(.n-data-table-th) {
  color: var(--color-text-secondary) !important;
  font-weight: 500;
}

.backtest-table :deep(.n-data-table-tr:hover) td {
  background: var(--color-surface-inset) !important;
}
</style>
