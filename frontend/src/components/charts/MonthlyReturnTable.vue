<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '../../stores/app'

const appStore = useAppStore()
const isDark = computed(() => appStore.isDark)

const props = defineProps<{
  years: number[]
  matrix: Record<number, number[]>
}>()

const MONTH_LABELS = [
  '1月',
  '2月',
  '3月',
  '4月',
  '5月',
  '6月',
  '7月',
  '8月',
  '9月',
  '10月',
  '11月',
  '12月',
]

function getCellValue(year: number, month: number): string {
  const row = props.matrix[year]
  if (!row || Number.isNaN(row[month])) return '-'
  return `${row[month].toFixed(1)}%`
}

function getYearTotal(year: number): string {
  const row = props.matrix[year]
  if (!row) return '-'
  const valid = row.filter((v) => !Number.isNaN(v))
  if (valid.length === 0) return '-'
  const total = valid.reduce((a, b) => a + b, 0)
  return `${total.toFixed(1)}%`
}

function cellColor(year: number, month: number): string {
  const row = props.matrix[year]
  if (!row || Number.isNaN(row[month])) return 'transparent'
  const val = row[month]
  const absVal = Math.min(Math.abs(val), 15)
  const intensity = absVal / 15
  if (val > 0) {
    return isDark.value
      ? `rgba(239,68,68,${0.08 + intensity * 0.5})`
      : `rgba(239,68,68,${0.06 + intensity * 0.35})`
  } else {
    return isDark.value
      ? `rgba(34,197,94,${0.08 + intensity * 0.5})`
      : `rgba(34,197,94,${0.06 + intensity * 0.35})`
  }
}

function totalColor(year: number): string {
  const row = props.matrix[year]
  if (!row) return 'transparent'
  const valid = row.filter((v) => !Number.isNaN(v))
  if (valid.length === 0) return 'transparent'
  const total = valid.reduce((a, b) => a + b, 0)
  const absVal = Math.min(Math.abs(total), 40)
  const intensity = absVal / 40
  if (total > 0) {
    return isDark.value
      ? `rgba(239,68,68,${0.1 + intensity * 0.5})`
      : `rgba(239,68,68,${0.08 + intensity * 0.4})`
  } else {
    return isDark.value
      ? `rgba(34,197,94,${0.1 + intensity * 0.5})`
      : `rgba(34,197,94,${0.08 + intensity * 0.4})`
  }
}

const avgMonthlyReturn = computed(() => {
  const all: number[] = []
  for (const year of props.years) {
    const row = props.matrix[year]
    if (!row) continue
    for (const v of row) {
      if (!Number.isNaN(v)) all.push(v)
    }
  }
  if (all.length === 0) return '-'
  const avg = all.reduce((a, b) => a + b, 0) / all.length
  return `${avg.toFixed(2)}%`
})
</script>

<template>
  <div class="w-full overflow-x-auto">
    <table class="w-full border-collapse text-xs">
      <thead>
        <tr>
          <th
            class="border-b border-[var(--color-border-muted)] px-3 py-2 text-left font-medium text-[var(--color-text-muted)]"
          >
            年份
          </th>
          <th
            v-for="label in MONTH_LABELS"
            :key="label"
            class="border-b border-[var(--color-border-muted)] px-2 py-2 text-center font-medium text-[var(--color-text-muted)]"
          >
            {{ label }}
          </th>
          <th
            class="border-b border-[var(--color-border-muted)] px-3 py-2 text-center font-medium text-[var(--color-text-primary)]"
          >
            年度合计
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="year in years"
          :key="year"
          class="border-b border-[var(--color-border-muted)] last:border-0"
        >
          <td class="px-3 py-2 font-mono font-semibold text-[var(--color-text-secondary)]">
            {{ year }}
          </td>
          <td
            v-for="m in 12"
            :key="m"
            class="px-2 py-2 text-center font-mono text-xs transition-colors"
            :style="{ backgroundColor: cellColor(year, m - 1) }"
          >
            <span
              class="font-semibold"
              :class="{
                'text-up': matrix[year]?.[m - 1] > 0,
                'text-down': !Number.isNaN(matrix[year]?.[m - 1]) && matrix[year][m - 1] < 0,
                'text-[var(--color-text-muted)]': Number.isNaN(matrix[year]?.[m - 1]),
              }"
            >
              {{ getCellValue(year, m - 1) }}
            </span>
          </td>
          <td
            class="px-3 py-2 text-center font-mono font-semibold transition-colors"
            :style="{ backgroundColor: totalColor(year) }"
          >
            <span
              :class="{
                'text-up': getYearTotal(year) !== '-' && !getYearTotal(year).startsWith('-'),
                'text-down': getYearTotal(year).startsWith('-'),
                'text-[var(--color-text-muted)]': getYearTotal(year) === '-',
              }"
            >
              {{ getYearTotal(year) }}
            </span>
          </td>
        </tr>
      </tbody>
      <tfoot>
        <tr class="border-t border-[var(--color-border-muted)]">
          <td class="px-3 py-2 font-semibold text-[var(--color-text-muted)]">月均收益</td>
          <td
            colspan="12"
            class="px-2 py-2 text-center font-mono text-xs text-[var(--color-text-muted)]"
          ></td>
          <td
            class="px-3 py-2 text-center font-mono font-semibold text-[var(--color-text-primary)]"
          >
            {{ avgMonthlyReturn }}
          </td>
        </tr>
      </tfoot>
    </table>
  </div>
</template>
