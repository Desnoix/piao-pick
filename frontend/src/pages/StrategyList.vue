<script setup lang="ts">
import { h, ref, onMounted, computed } from 'vue'
import { NDataTable, NButton, NSpace, NTag, NSwitch, NAlert, useMessage, useDialog } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import { PhPlus, PhSlidersHorizontal } from '@phosphor-icons/vue'
import { useStrategyStore } from '../stores/strategy'
import { updateStrategy } from '../api/strategies'
import type { Strategy } from '../types/strategy'

const router = useRouter()
const strategyStore = useStrategyStore()
const message = useMessage()
const dialog = useDialog()

const selectedIds = ref<string[]>([])
const fetchError = ref<string | null>(null)

const compareDisabled = computed(() => {
  return selectedIds.value.length < 2 || selectedIds.value.length > 4
})

function handleCompare() {
  if (selectedIds.value.length < 2) return
  const query = selectedIds.value.map((id) => `ids=${id}`).join('&')
  router.push(`/strategy/compare?${query}`)
}

const columns: DataTableColumns<Strategy> = [
  {
    type: 'selection',
  },
  {
    title: '名称',
    key: 'display_name',
    width: 180,
    render(row) {
      return h(
        'a',
        {
          class: 'text-[var(--color-accent)] cursor-pointer hover:underline',
          onClick: () => router.push(`/strategy/${row.id}`),
        },
        row.display_name || row.name || row.id
      )
    },
  },
  {
    title: '类别',
    key: 'category',
    width: 120,
    render(row) {
      return row.category || '-'
    },
  },
  {
    title: '状态',
    key: 'is_active',
    width: 100,
    render(row) {
      return h(NTag, { type: row.is_active ? 'success' : 'default', size: 'small' }, () =>
        row.is_active ? '启用' : '停用'
      )
    },
  },
  {
    title: '优先级',
    key: 'priority',
    width: 80,
    sorter: (a, b) => a.priority - b.priority,
    render(row) {
      return h('span', { class: 'data-mono' }, row.priority)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 280,
    render(row) {
      return h(NSpace, { align: 'center', size: 4 }, () => [
        h(
          NButton,
          {
            size: 'small',
            quaternary: true,
            type: 'primary',
            onClick: () => router.push(`/strategy/${row.id}`),
          },
          () => '编辑'
        ),
        h(
          NButton,
          {
            size: 'small',
            quaternary: true,
            onClick: () => router.push(`/backtest/${row.id}`),
          },
          () => '回测'
        ),
        h(NSwitch, {
          value: row.is_active,
          onUpdateValue: async (val: boolean) => {
            try {
              await updateStrategy(row.id, { is_active: val })
              await strategyStore.fetchStrategies()
              message.success(val ? '已启用' : '已停用')
            } catch {
              message.error('操作失败')
            }
          },
        }),
        h(
          NButton,
          {
            size: 'small',
            type: 'error',
            quaternary: true,
            onClick: () => {
              dialog.warning({
                title: '确认删除',
                content: `确定删除策略 "${row.display_name || row.name}" ?`,
                positiveText: '删除',
                negativeText: '取消',
                onPositiveClick: async () => {
                  try {
                    await strategyStore.removeStrategy(row.id)
                    message.success('已删除')
                  } catch {
                    message.error('删除失败')
                  }
                },
              })
            },
          },
          () => '删除'
        ),
      ])
    },
  },
]

onMounted(async () => {
  try {
    await strategyStore.fetchStrategies()
  } catch (e: any) {
    fetchError.value = e?.response?.data?.detail || e?.message || '加载策略失败'
  }
})
</script>

<template>
  <div class="flex flex-col gap-8">
    <!-- Action bar -->
    <div class="flex items-center gap-2 flex-wrap">
      <button
        class="inline-flex items-center gap-2 rounded-full px-4 py-2 border text-sm transition-all"
        :class="compareDisabled
          ? 'border-[var(--color-border)] text-[var(--color-text-muted)] opacity-50 cursor-not-allowed'
          : 'border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent-muted)] cursor-pointer'"
        :disabled="compareDisabled"
        @click="handleCompare"
      >
        <PhSlidersHorizontal :size="15" weight="duotone" />
        对比 ({{ selectedIds.length }})
      </button>
      <NButton type="primary" @click="router.push('/strategy/new')">
        <template #icon><PhPlus :size="16" /></template>
        新建策略
      </NButton>
    </div>

    <!-- Error alert -->
    <NAlert v-if="fetchError" type="error" closable @close="fetchError = null">
      <div class="flex items-center justify-between">
        <span>{{ fetchError }}</span>
        <NButton size="small" @click="() => { fetchError = null; strategyStore.fetchStrategies().catch((e: any) => { fetchError = e?.response?.data?.detail || e?.message || '加载策略失败' }) }">
          重试
        </NButton>
      </div>
    </NAlert>

    <!-- Strategy table -->
    <div v-if="strategyStore.strategies.length > 0 || strategyStore.loading" class="glass-panel overflow-hidden strategy-table">
      <NDataTable
        :columns="columns"
        :data="strategyStore.strategies"
        :loading="strategyStore.loading"
        :bordered="false"
        :row-key="(row: Strategy) => row.id"
        v-model:checked-row-keys="selectedIds"
        size="small"
        :single-line="false"
      />
    </div>

    <!-- Empty state -->
    <div
      v-if="strategyStore.strategies.length === 0 && !strategyStore.loading && !fetchError"
      class="glass-panel flex flex-col items-center justify-center py-20"
    >
      <PhSlidersHorizontal
        :size="64"
        class="text-[var(--color-text-muted)] opacity-30 mb-5"
        weight="duotone"
      />
      <p class="text-base font-medium text-[var(--color-text-secondary)] mb-2">暂无策略</p>
      <p class="text-sm text-[var(--color-text-muted)] mb-5">创建你的第一个量化策略</p>
      <NButton type="primary" @click="router.push('/strategy/new')">
        <template #icon><PhPlus :size="16" /></template>
        新建策略
      </NButton>
    </div>
  </div>
</template>

<style scoped>
.strategy-table :deep(.n-data-table-thead) {
  background: var(--color-surface-inset) !important;
}

.strategy-table :deep(.n-data-table-th) {
  color: var(--color-text-secondary) !important;
  font-weight: 500;
}

.strategy-table :deep(.n-data-table-tr:hover) td {
  background: var(--color-surface-inset) !important;
}
</style>
