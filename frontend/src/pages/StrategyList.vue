<script setup lang="ts">
import { h, ref, onMounted, computed } from 'vue'
import { NDataTable, NButton, NSpace, NTag, NSwitch, useMessage, useDialog } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useStrategyStore } from '../stores/strategy'
import { updateStrategy } from '../api/strategies'
import type { Strategy } from '../types/strategy'

const router = useRouter()
const strategyStore = useStrategyStore()
const message = useMessage()
const dialog = useDialog()

const selectedIds = ref<string[]>([])

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
          class: 'text-blue-500 cursor-pointer hover:underline',
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
      return h('span', { class: 'font-mono' }, row.priority)
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

onMounted(() => {
  strategyStore.fetchStrategies()
})
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h2 class="text-xl font-bold text-[var(--color-text-primary)]">策略管理</h2>
        <p class="text-sm text-[var(--color-text-secondary)] mt-1">管理和回测你的量化策略</p>
      </div>
      <NSpace>
        <NButton
          :type="compareDisabled ? 'default' : 'warning'"
          :disabled="compareDisabled"
          @click="handleCompare"
        >
          对比 ({{ selectedIds.length }})
        </NButton>
        <NButton type="primary" @click="router.push('/strategy/new')">
          新建策略
        </NButton>
      </NSpace>
    </div>
    <div class="rounded-lg border border-[var(--color-border)] overflow-hidden">
      <NDataTable
        :columns="columns"
        :data="strategyStore.strategies"
        :loading="strategyStore.loading"
        :row-key="(row: Strategy) => row.id"
        v-model:checked-row-keys="selectedIds"
        size="small"
        striped
      />
    </div>
  </div>
</template>
