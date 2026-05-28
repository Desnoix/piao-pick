<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { NButton, NDataTable, NProgress, NDatePicker, NSelect, NTag, useMessage } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { PhDatabase, PhArrowsClockwise, PhFunction, PhCalendarBlank } from '@phosphor-icons/vue'
import ListSkeleton from '../components/skeleton/ListSkeleton.vue'
import TableSkeleton from '../components/skeleton/TableSkeleton.vue'
import {
  getDataStatus,
  syncData,
  getTradeCalendar,
  startHistorySync,
  getHistorySyncStatus,
  computeFactors,
  type HistorySyncProgress,
} from '../api/data'
import type { DataStatus, TradeCalendar } from '../types/api'

const message = useMessage()
const loading = ref(false)
const syncing = ref(false)
const status = ref<DataStatus | null>(null)
const calendar = ref<TradeCalendar | null>(null)

const historySyncing = ref(false)
const historySyncTask = ref<HistorySyncProgress | null>(null)
const historyStartDate = ref<number>(Date.now() - 365 * 24 * 60 * 60 * 1000)
const historyEndDate = ref<number>(Date.now())
const adjustType = ref('qfq')
let pollTimer: number | null = null

const factorComputing = ref(false)
const factorResult = ref<{ computed: number; failed: number; total: number } | null>(null)

const statusRows = ref<Array<{ key: string; value: string }>>([])

const calendarColumns: DataTableColumns<{ date: string; isTradeDay: boolean }> = [
  { title: '日期', key: 'date', width: 150 },
  {
    title: '交易日',
    key: 'isTradeDay',
    width: 100,
    render(row) {
      return row.isTradeDay ? '是' : '否'
    },
  },
]

const calendarRows = ref<Array<{ date: string; isTradeDay: boolean }>>([])

const adjustTypeOptions = [
  { label: '前复权', value: 'qfq' },
  { label: '后复权', value: 'hfq' },
  { label: '不复权', value: '' },
]

const historySyncStatus = computed(() => {
  if (!historySyncTask.value) return null
  const t = historySyncTask.value
  return {
    status: t.status,
    percent: t.progress.percent,
    completed: t.progress.completed,
    failed: t.progress.failed,
    total: t.progress.total,
    klines: t.progress.total_klines,
    currentStock: t.progress.current_stock,
  }
})

const isHistorySyncActive = computed(() => {
  const st = historySyncTask.value?.status
  return st === 'pending' || st === 'running'
})

const taskBorderClass = computed(() => {
  if (!historySyncTask.value) return ''
  switch (historySyncTask.value.status) {
    case 'completed':
      return 'border-l-[var(--color-success)] bg-[rgba(34,197,94,0.08)]'
    case 'failed':
      return 'border-l-[var(--color-error)] bg-[rgba(239,68,68,0.08)]'
    default:
      return 'border-l-[var(--color-accent)] bg-[var(--color-accent-muted)]'
  }
})

async function loadStatus() {
  loading.value = true
  try {
    status.value = await getDataStatus()
    statusRows.value = [
      { key: '数据库路径', value: status.value.db_path },
      { key: '数据库大小', value: status.value.db_size_mb ? `${status.value.db_size_mb} MB` : '-' },
      { key: '股票数量', value: String(status.value.stock_count) },
      { key: '最新K线日期', value: status.value.latest_kline_date || '-' },
      { key: '最新因子日期', value: status.value.latest_factor_date || '-' },
    ]

    calendar.value = await getTradeCalendar()
    const tradeSet = new Set(calendar.value.trading_days)
    const rows: { date: string; isTradeDay: boolean }[] = []
    const today = new Date()
    for (let i = -3; i <= 7; i++) {
      const d = new Date(today)
      d.setDate(d.getDate() + i)
      const ds = d.toISOString().split('T')[0]
      rows.push({ date: ds, isTradeDay: tradeSet.has(ds) })
    }
    calendarRows.value = rows
  } catch (err: any) {
    // 忽略请求取消错误（来自 client.ts 的请求去重机制）
    if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
    console.error('Failed to load data status:', err)
  } finally {
    loading.value = false
  }
}

async function handleSync() {
  syncing.value = true
  try {
    const result = await syncData({})
    if (result.success) {
      message.success(`同步完成: ${result.synced_count} 只股票`)
      await loadStatus()
    } else {
      message.error(`同步失败: ${result.message}`)
    }
  } catch (err: any) {
    // 忽略请求取消错误
    if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
    message.error(err?.response?.data?.detail || err?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

function formatDate(timestamp: number): string {
  const d = new Date(timestamp)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

async function handleHistorySync() {
  if (isHistorySyncActive.value) {
    message.warning('历史同步任务正在运行中')
    return
  }

  historySyncing.value = true
  try {
    const task = await startHistorySync({
      start_date: formatDate(historyStartDate.value),
      end_date: formatDate(historyEndDate.value),
      adjust_type: adjustType.value || undefined,
    })
    historySyncTask.value = task
    message.success(`历史同步任务已启动: ${task.task_id}`)

    startPolling()
  } catch (err: any) {
    // 忽略请求取消错误
    if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
    message.error(err?.response?.data?.detail || err?.message || '启动历史同步失败')
  } finally {
    historySyncing.value = false
  }
}

function startPolling() {
  stopPolling()
  pollHistorySyncStatus()
  pollTimer = window.setInterval(pollHistorySyncStatus, 3000)
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollHistorySyncStatus() {
  try {
    const taskId = historySyncTask.value?.task_id
    const status = await getHistorySyncStatus(taskId)
    if (status) {
      historySyncTask.value = status

      if (status.status === 'completed') {
        stopPolling()
        message.success(
          `历史同步完成: ${status.progress.total_klines} 条K线 ` +
            `(${status.progress.completed} 成功, ${status.progress.failed} 失败)`
        )
        await loadStatus()
      } else if (status.status === 'failed') {
        stopPolling()
        message.error('历史同步任务失败，请查看后端日志')
      }
    }
  } catch (e) {
    console.error('Poll history sync status failed:', e)
  }
}

async function loadCurrentTask() {
  try {
    const status = await getHistorySyncStatus()
    if (status && isHistorySyncActiveStatus(status.status)) {
      historySyncTask.value = status
      startPolling()
    }
  } catch (e) {
    // ignore
  }
}

function isHistorySyncActiveStatus(st: string): boolean {
  return st === 'pending' || st === 'running'
}

function getStatusText(status: string): string {
  switch (status) {
    case 'running':
      return '运行中'
    case 'completed':
      return '已完成'
    case 'failed':
      return '失败'
    case 'pending':
      return '等待中'
    default:
      return status
  }
}

async function handleFactorCompute() {
  if (factorComputing.value) return

  factorComputing.value = true
  factorResult.value = null

  try {
    message.info('开始计算时序因子，请耐心等待...')
    const result = await computeFactors({
      start_date: formatDate(historyStartDate.value),
      end_date: formatDate(historyEndDate.value),
    })

    if (result?.data) {
      factorResult.value = result.data
      message.success(`.factor计算完成: ${result.data.computed} 只成功, ${result.data.failed} 只失败`)
      await loadStatus()
    } else {
      message.error('因子计算返回异常')
    }
  } catch (err: any) {
    // 忽略请求取消错误
    if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
    message.error(err?.response?.data?.detail || err?.message || '因子计算失败')
  } finally {
    factorComputing.value = false
  }
}

onMounted(async () => {
  await loadStatus()
  await loadCurrentTask()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div>
    <div class="flex flex-col gap-8">
      <!-- Operational header: sync action right-aligned -->
      <header class="flex items-center justify-between">
        <span class="text-sm text-[var(--color-text-muted)]">
          {{ status ? `${status.stock_count} 只股票已入库` : '' }}
        </span>
        <NButton type="primary" :loading="syncing" size="small" @click="handleSync">
          <template #icon><PhArrowsClockwise :size="14" /></template>
          同步当日
        </NButton>
      </header>

      <!-- DB Overview -->
      <section>
        <div class="section-header">
          <span class="section-label">数据库</span>
          <h3 class="section-title">概览</h3>
        </div>
        <div class="glass-panel overflow-hidden">
          <ListSkeleton v-if="loading" :rows="5" />
          <div v-else class="kv-grid">
            <div
              v-for="(row, i) in statusRows"
              :key="row.key"
              class="kv-row"
              :class="{ 'kv-row--last': i === statusRows.length - 1 }"
            >
              <span class="kv-key">{{ row.key }}</span>
              <span class="kv-val data-mono">{{ row.value }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- History Sync -->
      <section>
        <div class="section-header">
          <span class="section-label">历史数据</span>
          <h3 class="section-title">K线同步</h3>
        </div>
        <div class="glass-panel">
          <div class="section-body">
            <p class="section-desc">批量拉取全市场历史K线，约 30-60 分钟。支持断点续传。</p>

            <!-- Action bar -->
            <div class="sync-bar">
              <div class="sync-field">
                <label class="field-label">起始</label>
                <NDatePicker
                  v-model:value="historyStartDate"
                  type="date"
                  :disabled="isHistorySyncActive"
                  clearable
                  size="small"
                />
              </div>
              <span class="sync-sep">&mdash;</span>
              <div class="sync-field">
                <label class="field-label">截止</label>
                <NDatePicker
                  v-model:value="historyEndDate"
                  type="date"
                  :disabled="isHistorySyncActive"
                  clearable
                  size="small"
                />
              </div>
              <div class="sync-field sync-field--select">
                <label class="field-label">复权</label>
                <NSelect
                  v-model:value="adjustType"
                  :options="adjustTypeOptions"
                  :disabled="isHistorySyncActive"
                  size="small"
                />
              </div>
              <NButton
                type="primary"
                :loading="historySyncing"
                :disabled="isHistorySyncActive"
                size="small"
                @click="handleHistorySync"
              >
                启动同步
              </NButton>
            </div>
          </div>

          <!-- Task Progress -->
          <div v-if="historySyncTask" class="task-progress" :class="taskBorderClass">
            <div class="task-head">
              <span class="task-status-label">
                {{ getStatusText(historySyncTask.status) }}
              </span>
              <span class="task-pct data-mono">{{ historySyncStatus?.percent || 0 }}%</span>
            </div>

            <NProgress
              type="line"
              :percentage="historySyncStatus?.percent || 0"
              :status="historySyncTask.status === 'failed' ? 'error' : 'default'"
              :show-indicator="false"
            />

            <div class="task-metrics">
              <div class="task-metric">
                <span class="task-metric-label">总数</span>
                <span class="task-metric-val data-mono">{{ historySyncTask.progress.total }}</span>
              </div>
              <div class="task-metric">
                <span class="task-metric-label">完成</span>
                <span class="task-metric-val data-mono">
                  {{ historySyncTask.progress.completed }}
                </span>
              </div>
              <div class="task-metric">
                <span class="task-metric-label">失败</span>
                <span class="task-metric-val data-mono text-[var(--color-error)]">
                  {{ historySyncTask.progress.failed }}
                </span>
              </div>
              <div class="task-metric">
                <span class="task-metric-label">K线</span>
                <span class="task-metric-val data-mono">
                  {{ historySyncTask.progress.total_klines }}
                </span>
              </div>
              <div class="task-metric task-metric--current">
                <span class="task-metric-label">当前</span>
                <NTag
                  v-if="historySyncTask.progress.current_stock"
                  size="small"
                  round
                  :bordered="false"
                >
                  {{ historySyncTask.progress.current_stock }}
                </NTag>
                <span v-else class="task-metric-val text-[var(--color-text-muted)]">&mdash;</span>
              </div>
            </div>

            <div class="task-meta">
              <span class="data-mono">{{ historySyncTask.task_id }}</span>
              <span class="task-meta-sep">/</span>
              <span class="data-mono">
                {{ historySyncTask.start_date }} ~ {{ historySyncTask.end_date }}
              </span>
              <span class="task-meta-sep">/</span>
              <span>{{ new Date(historySyncTask.created_at).toLocaleString('zh-CN') }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Factor Compute -->
      <section>
        <div class="section-header">
          <span class="section-label">因子引擎</span>
          <h3 class="section-title">计算</h3>
        </div>
        <div class="glass-panel section-body">
          <p class="section-desc">
            基于历史K线计算时序因子: 20日动量、60日波动率、20日均换手率。需先完成K线同步。
          </p>

          <div class="factor-action">
            <NButton
              type="warning"
              :loading="factorComputing"
              size="small"
              @click="handleFactorCompute"
            >
              {{ factorComputing ? '计算中...' : '执行因子计算' }}
            </NButton>
          </div>

          <div v-if="factorResult" class="factor-result">
            <div class="factor-result-head">
              <span class="factor-result-label">计算完成</span>
              <NTag size="small" :bordered="false" type="success" round>
                {{ factorResult.computed }} / {{ factorResult.total }}
              </NTag>
            </div>
            <div class="factor-result-grid">
              <div class="factor-stat">
                <span class="factor-stat-val data-mono text-[var(--color-success)]">
                  {{ factorResult.computed }}
                </span>
                <span class="factor-stat-label">成功</span>
              </div>
              <div class="factor-stat">
                <span class="factor-stat-val data-mono text-[var(--color-error)]">
                  {{ factorResult.failed }}
                </span>
                <span class="factor-stat-label">失败</span>
              </div>
              <div class="factor-stat">
                <span class="factor-stat-val data-mono">{{ factorResult.total }}</span>
                <span class="factor-stat-label">总计</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Calendar -->
      <section>
        <div class="section-header">
          <span class="section-label">交易日历</span>
          <h3 class="section-title">近期交易日</h3>
        </div>
        <div class="glass-panel overflow-hidden">
          <TableSkeleton v-if="loading" :columns="2" :rows="10" />
          <NDataTable
            v-else
            :columns="calendarColumns"
            :data="calendarRows"
            size="small"
            :bordered="false"
          />
        </div>
      </section>
    </div>
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

.section-body {
  padding: 20px;
}

.section-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0 0 16px 0;
  line-height: 1.6;
}

/* Key-value grid for DB overview */
.kv-grid {
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
}

.kv-val {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
}

/* History sync action bar */
.sync-bar {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.sync-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 140px;
  flex: 1;
}

.sync-field--select {
  min-width: 120px;
  flex: 0 0 120px;
}

.field-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-muted);
  letter-spacing: 0.04em;
}

.sync-sep {
  color: var(--color-text-muted);
  font-size: 14px;
  padding-bottom: 8px;
  flex-shrink: 0;
}

/* Task progress card */
.task-progress {
  padding: 16px 20px;
  border-left: 3px solid;
  border-top: 1px solid var(--color-border);
}

.task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.task-status-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.task-pct {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.task-metrics {
  display: flex;
  gap: 20px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.task-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.task-metric-label {
  font-size: 11px;
  color: var(--color-text-muted);
}

.task-metric-val {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.task-metric--current {
  margin-left: auto;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 14px;
  font-size: 11px;
  color: var(--color-text-muted);
  flex-wrap: wrap;
}

.task-meta-sep {
  color: var(--color-border-muted);
}

/* Factor compute */
.factor-action {
  display: flex;
  align-items: center;
}

.factor-result {
  margin-top: 16px;
  padding: 14px 16px;
  background: var(--color-surface-inset);
  border-radius: 8px;
}

.factor-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.factor-result-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.factor-result-grid {
  display: flex;
  gap: 24px;
}

.factor-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.factor-stat-val {
  font-size: 18px;
  font-weight: 600;
}

.factor-stat-label {
  font-size: 11px;
  color: var(--color-text-muted);
}

/* Mobile */
@media (max-width: 640px) {
  .sync-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .sync-field,
  .sync-field--select {
    min-width: auto;
    flex: auto;
  }

  .sync-sep {
    display: none;
  }

  .task-metrics {
    gap: 12px;
  }

  .task-metric--current {
    margin-left: 0;
  }

  .factor-result-grid {
    gap: 16px;
  }
}
</style>
