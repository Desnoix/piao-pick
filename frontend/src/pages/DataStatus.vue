<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  NButton,
  NDataTable,
  NSpace,
  NAlert,
  NSpin,
  NProgress,
  NDatePicker,
  NSelect,
  NTag,
  NDivider,
  useMessage,
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
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

// 历史同步相关
const historySyncing = ref(false)
const historySyncTask = ref<HistorySyncProgress | null>(null)
const historyStartDate = ref<number>(Date.now() - 365 * 24 * 60 * 60 * 1000) // 1年前
const historyEndDate = ref<number>(Date.now())
const adjustType = ref('qfq')
let pollTimer: number | null = null

// 因子计算相关
const factorComputing = ref(false)
const factorResult = ref<{ computed: number; failed: number; total: number } | null>(null)

const statusRows = ref<Array<{ key: string; value: string }>>([])

const statusColumns: DataTableColumns<{ key: string; value: string }> = [
  { title: '指标', key: 'key', width: 200 },
  { title: '值', key: 'value' },
]

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

    // Load calendar
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
  } catch (e: any) {
    message.error('加载状态失败')
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
  } catch (e: any) {
    message.error('同步请求失败')
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
    
    // 启动轮询
    startPolling()
  } catch (e: any) {
    const detail = e?.response?.data?.detail || '启动历史同步失败'
    message.error(detail)
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
      
      // 任务完成或失败时停止轮询
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
  // 页面加载时检查是否有正在运行的任务
  try {
    const status = await getHistorySyncStatus()
    if (status && isHistorySyncActiveStatus(status.status)) {
      historySyncTask.value = status
      startPolling()
    }
  } catch (e) {
    // 忽略
  }
}

function isHistorySyncActiveStatus(st: string): boolean {
  return st === 'pending' || st === 'running'
}

function getStatusType(status: string): 'success' | 'warning' | 'error' | 'info' {
  switch (status) {
    case 'running':
      return 'info'
    case 'completed':
      return 'success'
    case 'failed':
      return 'error'
    case 'pending':
      return 'warning'
    default:
      return 'info'
  }
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
      message.success(
        `因子计算完成: ${result.data.computed} 只成功, ${result.data.failed} 只失败`
      )
      await loadStatus()
    } else {
      message.error('因子计算返回异常')
    }
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '因子计算失败'
    message.error(detail)
    console.error('Factor compute error:', e)
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
  <NSpin :show="loading">
    <div class="flex flex-col gap-6 max-w-4xl">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-xl font-bold text-[var(--color-text-primary)]">数据状态</h2>
          <p class="text-sm text-[var(--color-text-secondary)] mt-1">查看数据库状态和同步数据</p>
        </div>
        <NButton type="primary" :loading="syncing" @click="handleSync">
          手动同步
        </NButton>
      </div>

      <div class="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg p-4">
        <h3 class="text-lg font-bold mb-2 text-[var(--color-text-primary)]">数据库概览</h3>
        <NDataTable
          :columns="statusColumns"
          :data="statusRows"
          size="small"
          :bordered="false"
        />
      </div>

      <NDivider />

      <div class="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg p-4">
        <h3 class="text-lg font-bold mb-2 text-[var(--color-text-primary)]">历史数据同步</h3>
        <p class="text-sm text-[var(--color-text-secondary)] mb-4">
          批量拉取全市场历史K线数据（约需要 30-60 分钟）。支持断点续传，可随时暂停和恢复。
        </p>

        <div class="flex flex-col gap-4">
          <!-- 日期范围选择 -->
          <div class="flex items-center gap-4">
            <div class="flex-1">
              <label class="block text-sm mb-1 text-[var(--color-text-secondary)]">开始日期</label>
              <NDatePicker
                v-model:value="historyStartDate"
                type="date"
                :disabled="isHistorySyncActive"
                clearable
              />
            </div>
            <div class="flex-1">
              <label class="block text-sm mb-1 text-[var(--color-text-secondary)]">结束日期</label>
              <NDatePicker
                v-model:value="historyEndDate"
                type="date"
                :disabled="isHistorySyncActive"
                clearable
              />
            </div>
            <div class="w-40">
              <label class="block text-sm mb-1 text-[var(--color-text-secondary)]">复权类型</label>
              <NSelect
                v-model:value="adjustType"
                :options="adjustTypeOptions"
                :disabled="isHistorySyncActive"
                size="small"
              />
            </div>
            <div class="w-40 pt-6">
              <NButton
                type="primary"
                :loading="historySyncing"
                :disabled="isHistorySyncActive"
                block
                @click="handleHistorySync"
              >
                开始拉取历史数据
              </NButton>
            </div>
          </div>

          <!-- 任务进度 -->
          <NAlert
            v-if="historySyncTask"
            :type="getStatusType(historySyncTask.status)"
            :title="`同步任务: ${getStatusText(historySyncTask.status)}`"
            class="mt-4"
          >
            <div class="space-y-3">
              <NProgress
                type="line"
                :percentage="historySyncStatus?.percent || 0"
                :status="historySyncTask.status === 'failed' ? 'error' : 'default'"
              />

              <div class="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                <div>
                  <span class="text-[var(--color-text-secondary)]">股票总数:</span>
                  <div class="font-mono text-[var(--color-text-primary)]">{{ historySyncTask.progress.total }}</div>
                </div>
                <div>
                  <span class="text-[var(--color-text-secondary)]">已完成:</span>
                  <div class="font-mono text-[var(--color-text-primary)]">{{ historySyncTask.progress.completed }}</div>
                </div>
                <div>
                  <span class="text-[var(--color-text-secondary)]">失败:</span>
                  <div class="font-mono text-red-500">{{ historySyncTask.progress.failed }}</div>
                </div>
                <div>
                  <span class="text-[var(--color-text-secondary)]">K线数:</span>
                  <div class="font-mono text-[var(--color-text-primary)]">{{ historySyncTask.progress.total_klines }}</div>
                </div>
                <div>
                  <span class="text-[var(--color-text-secondary)]">当前:</span>
                  <div class="font-mono truncate text-[var(--color-text-primary)]">
                    <NTag v-if="historySyncTask.progress.current_stock" size="small">
                      {{ historySyncTask.progress.current_stock }}
                    </NTag>
                    <span v-else class="text-[var(--color-text-muted)]">-</span>
                  </div>
                </div>
              </div>

              <div class="text-xs text-[var(--color-text-muted)]">
                任务ID: {{ historySyncTask.task_id }} |
                日期范围: {{ historySyncTask.start_date }} ~ {{ historySyncTask.end_date }} |
                创建: {{ new Date(historySyncTask.created_at).toLocaleString('zh-CN') }}
              </div>
            </div>
          </NAlert>
        </div>
      </div>

      <NDivider />

      <!-- 因子计算 -->
      <div class="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg p-4">
        <h3 class="text-lg font-bold mb-2 text-[var(--color-text-primary)]">时序因子计算</h3>
        <p class="text-sm text-[var(--color-text-secondary)] mb-4">
          基于已拉取的历史K线数据，计算时序因子 (20日动量、60日波动率、20日均换手率)。
          请先完成历史数据同步，再执行因子计算。耗时取决于股票数量。
        </p>

        <NButton
          type="warning"
          :loading="factorComputing"
          @click="handleFactorCompute"
        >
          {{ factorComputing ? '计算中...' : '开始计算因子' }}
        </NButton>

        <NAlert
          v-if="factorResult"
          type="success"
          title="因子计算结果"
          class="mt-4"
        >
          <div class="grid grid-cols-3 gap-3 text-sm">
            <div>
              <span class="text-[var(--color-text-secondary)]">总股票数:</span>
              <div class="font-mono text-[var(--color-text-primary)]">{{ factorResult.total }}</div>
            </div>
            <div>
              <span class="text-[var(--color-text-secondary)]">计算成功:</span>
              <div class="font-mono text-green-500">{{ factorResult.computed }}</div>
            </div>
            <div>
              <span class="text-[var(--color-text-secondary)]">计算失败:</span>
              <div class="font-mono text-red-500">{{ factorResult.failed }}</div>
            </div>
          </div>
        </NAlert>
      </div>

      <NDivider />

      <div class="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg p-4">
        <h3 class="text-lg font-bold mb-2 text-[var(--color-text-primary)]">交易日历</h3>
        <NDataTable
          :columns="calendarColumns"
          :data="calendarRows"
          size="small"
          :bordered="false"
        />
      </div>
    </div>
  </NSpin>
</template>
