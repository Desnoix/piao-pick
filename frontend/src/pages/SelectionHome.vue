<script setup lang="ts">
/**
 * Selection home: two-panel layout with strategy run, results table, and factor radar.
 * 选股主页: 左侧结果表格 + 右侧因子雷达面板。
 */
import { ref, h, computed, onMounted, watch } from 'vue'
import {
  NDataTable,
  NSelect,
  NButton,
  NInput,
  NTag,
  useMessage,
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useStrategyStore } from '../stores/strategy'
import { useSelectionStore } from '../stores/selection'
import { runSelection } from '../api/selection'
import FactorRadar from '../components/charts/FactorRadar.vue'
import { useChartTheme } from '../composables/use-chart-theme'
import { PhMagnifyingGlass, PhCursorClick, PhPlay } from '@phosphor-icons/vue'
import type { SelectionRecord } from '../types/selection'

const router = useRouter()
const strategyStore = useStrategyStore()
const selectionStore = useSelectionStore()
const message = useMessage()
const { theme } = useChartTheme()

const selectedStrategy = ref<string | null>(null)
const selectedStock = ref<SelectionRecord | null>(null)
const running = ref(false)
const searchText = ref('')

const filteredResults = computed(() => {
  if (!searchText.value) return selectionStore.results
  const q = searchText.value.toLowerCase()
  return selectionStore.results.filter((r) =>
    r.ts_code.toLowerCase().includes(q)
  )
})

const strategyOptions = computed(() =>
  strategyStore.strategies
    .filter((s) => s.is_active)
    .map((s) => ({
      label: s.display_name || s.name || s.id,
      value: s.id,
    }))
)

const columns: DataTableColumns<SelectionRecord> = [
  {
    title: '#',
    key: 'rank',
    width: 56,
    sortOrder: 'ascend',
    sorter: (a, b) => a.rank - b.rank,
    render(row) {
      return h(
        'span',
        { class: 'data-mono text-[var(--color-text-secondary)]' },
        row.rank
      )
    },
  },
  {
    title: '代码',
    key: 'ts_code',
    width: 120,
    render(row) {
      return h(
        'a',
        {
          class:
            'data-mono text-[var(--color-accent)] cursor-pointer hover:underline',
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
    title: '评分',
    key: 'composite_score',
    width: 100,
    sorter: (a, b) => a.composite_score - b.composite_score,
    render(row) {
      return h(
        'span',
        { class: 'data-mono font-medium text-[var(--color-text-primary)]' },
        row.composite_score.toFixed(2)
      )
    },
  },
  {
    title: '日期',
    key: 'trade_date',
    width: 110,
    render(row) {
      return h(
        'span',
        { class: 'text-xs text-[var(--color-text-muted)]' },
        row.trade_date
      )
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 80,
    render(row) {
      const type = row.status === 'OK' ? 'success' : 'warning'
      return h(
        NTag,
        { type, size: 'small', round: true, bordered: false },
        () => row.status
      )
    },
  },
]

async function handleRun() {
  if (!selectedStrategy.value) {
    message.warning('请先选择策略')
    return
  }
  running.value = true
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
    const detail = e?.response?.data?.detail || e?.message || '选股失败'
    console.error('Selection error:', e)
    if (detail.includes('数据准备失败') || detail.includes('Connection') || detail.includes('closed')) {
      message.error(
        '数据获取失败, 可能是网络问题或东方财富接口限制。请到数据页面手动重试同步。'
      )
    } else {
      message.error(detail)
    }
  } finally {
    running.value = false
  }
}

const today = new Date().toLocaleDateString('zh-CN')

function handleRowClick(row: SelectionRecord) {
  selectedStock.value = row
}

function rowClassName(row: SelectionRecord) {
  const base = 'cursor-pointer transition-colors'
  if (row === selectedStock.value) return `${base} row--selected`
  return base
}

onMounted(async () => {
  await strategyStore.fetchStrategies()
  if (strategyStore.strategies.length > 0) {
    selectedStrategy.value = strategyStore.strategies[0].id
    await selectionStore.fetchResults(selectedStrategy.value)
  }
})

watch(selectedStrategy, async (val) => {
  if (val) {
    await selectionStore.fetchResults(val)
  }
})
</script>

<template>
  <div class="flex flex-col gap-5">
    <!-- Top action bar -->
    <div class="flex items-center gap-3 flex-wrap">
      <!-- Strategy selector + run button -->
      <div class="flex items-center gap-2">
        <NSelect
          v-model:value="selectedStrategy"
          :options="strategyOptions"
          placeholder="选择策略"
          class="w-56"
        />
        <NButton
          type="primary"
          :loading="running"
          @click="handleRun"
        >
          <template #icon>
            <PhPlay :size="16" weight="fill" />
          </template>
          运行选股
        </NButton>
      </div>

      <!-- Spacer -->
      <div class="flex-1" />

      <!-- Search -->
      <NInput
        v-model:value="searchText"
        placeholder="搜索股票代码..."
        clearable
        size="small"
        class="w-52"
      >
        <template #prefix>
          <PhMagnifyingGlass
            :size="14"
            class="text-[var(--color-text-muted)]"
          />
        </template>
      </NInput>

      <!-- Stats -->
      <div class="flex items-center gap-3 text-sm text-[var(--color-text-secondary)]">
        <span>{{ today }}</span>
        <span
          v-if="searchText && filteredResults.length !== selectionStore.results.length"
          class="data-mono font-medium"
        >
          {{ filteredResults.length }} / {{ selectionStore.results.length }} 只
        </span>
        <span v-else class="data-mono font-medium">
          {{ filteredResults.length }} 只
        </span>
      </div>
    </div>

    <!-- Main content area -->
    <div class="flex gap-5 min-h-[600px]">
      <!-- Table -->
      <div class="flex-1 min-w-0">
        <div class="glass-panel overflow-hidden">
          <NDataTable
            :columns="columns"
            :data="filteredResults"
            :loading="selectionStore.loading"
            :virtual-scroll="true"
            :max-height="580"
            :row-key="(row: SelectionRecord) => row.ts_code"
            :row-class-name="rowClassName"
            @row-click="handleRowClick"
            size="small"
            striped
          />
        </div>
      </div>

      <!-- Right panel -->
      <div class="w-[400px] shrink-0">
        <div class="glass-panel h-full overflow-y-auto">
          <div class="p-5">
            <!-- Selected stock detail -->
            <template v-if="selectedStock">
              <div class="flex items-baseline gap-2 mb-1">
                <span class="text-lg font-bold data-mono text-[var(--color-text-primary)]">
                  {{ selectedStock.ts_code }}
                </span>
                <NTag size="small" :bordered="false" type="info">
                  #{{ selectedStock.rank }}
                </NTag>
              </div>
              <div class="flex items-center gap-2 text-sm text-[var(--color-text-secondary)] mb-5">
                <span>评分</span>
                <span class="data-mono font-semibold text-[var(--color-text-primary)]">
                  {{ selectedStock.composite_score.toFixed(2) }}
                </span>
                <span class="text-[var(--color-text-muted)]">|</span>
                <span>{{ selectedStock.trade_date }}</span>
              </div>

              <!-- Factor radar -->
              <FactorRadar
                v-if="
                  selectedStock.factor_snapshot &&
                  Object.keys(selectedStock.factor_snapshot).length
                "
                :factors="selectedStock.factor_snapshot"
                :theme="theme"
              />

              <NButton
                type="primary"
                ghost
                class="mt-5 w-full"
                @click="router.push(`/stock/${selectedStock.ts_code}`)"
              >
                查看详情
              </NButton>
            </template>

            <!-- Empty state -->
            <template v-else>
              <div class="flex flex-col items-center justify-center h-full text-center py-20">
                <PhCursorClick
                  :size="40"
                  class="text-[var(--color-text-muted)] opacity-40 mb-4"
                />
                <p class="text-sm text-[var(--color-text-secondary)] opacity-50">
                  点击行查看因子画像
                </p>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Selected row: left accent border instead of full background */
.row--selected td {
  background: var(--color-accent-muted) !important;
}
.row--selected td:first-child {
  box-shadow: inset 3px 0 0 var(--color-accent);
}

:deep(.n-data-table-tr:hover) td {
  background: var(--color-surface-inset) !important;
}

:deep(.n-data-table-tr) {
  cursor: pointer;
}

/* Table header styling */
:deep(.n-data-table-thead) {
  background: var(--color-surface-inset) !important;
}
:deep(.n-data-table-th) {
  color: var(--color-text-secondary) !important;
  font-weight: 500;
}
</style>
