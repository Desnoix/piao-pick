<script setup lang="ts">
import { computed } from 'vue'
import { NTag } from 'naive-ui'
import { FACTOR_LABELS } from '../../utils/constants'

/**
 * 因子覆盖率展示卡片。
 * Factor coverage display card.
 */

export interface CoverageData {
  strategy_name: string
  total_factors: number
  available_factors: string[]
  stub_factors: string[]
  coverage_rate: number
  configured_weights: Record<string, number>
  effective_weights: Record<string, number>
  weight_drift: Record<string, number>
}

const props = defineProps<{ data: CoverageData }>()

const hasDrift = computed(() => Object.values(props.data.weight_drift).some((d) => d !== 0))

const allFactors = computed(() => Object.keys(props.data.configured_weights).sort())

const coveragePercent = computed(() => (props.data.coverage_rate * 100).toFixed(1))

const coverageClass = computed(() => {
  const r = props.data.coverage_rate
  if (r >= 0.9) return 'coverage-good'
  if (r >= 0.6) return 'coverage-warn'
  return 'coverage-danger'
})

function factorLabel(id: string): string {
  return FACTOR_LABELS[id] || id
}

function driftClass(d: number): string {
  if (d > 0.01) return 'drift-up'
  if (d < -0.01) return 'drift-down'
  return ''
}

function formatDrift(d: number): string {
  if (Math.abs(d) < 0.001) return '—'
  const pct = (d * 100).toFixed(1)
  return d > 0 ? `+${pct}%` : `${pct}%`
}
</script>

<template>
  <div class="factors-coverage-card" :class="coverageClass">
    <!-- Header: icon + rate -->
    <div class="factors-coverage__header">
      <span class="factors-coverage__label">因子覆盖率</span>
      <span class="factors-coverage__rate data-mono">
        {{ coveragePercent }}%
        <span class="factors-coverage__count">
          ({{ data.available_factors.length }}/{{ data.total_factors }} 可用)
        </span>
      </span>
    </div>

    <!-- Stub factors warning -->
    <div v-if="data.stub_factors.length > 0" class="factors-coverage__stubs">
      <div class="factors-coverage__stub-label">以下因子暂无数据（权重已重新分配）：</div>
      <div v-for="f in data.stub_factors" :key="f" class="factors-coverage__stub-item">
        <span class="factors-coverage__stub-name">{{ factorLabel(f) }}</span>
        <span class="factors-coverage__stub-weight data-mono">
          配置 {{ (data.configured_weights[f] * 100).toFixed(0) }}% → 实际 0%
        </span>
      </div>
    </div>

    <!-- Weight drift table -->
    <div v-if="hasDrift" class="factors-coverage__drift">
      <table class="drift-table">
        <thead>
          <tr>
            <th>因子</th>
            <th>配置权重</th>
            <th>实际权重</th>
            <th>漂移</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in allFactors" :key="f" :class="{ 'drift-row': data.weight_drift[f] !== 0 }">
            <td>{{ factorLabel(f) }}</td>
            <td class="data-mono">{{ (data.configured_weights[f] * 100).toFixed(1) }}%</td>
            <td class="data-mono">{{ (data.effective_weights[f] * 100).toFixed(1) }}%</td>
            <td class="data-mono" :class="driftClass(data.weight_drift[f])">
              {{ formatDrift(data.weight_drift[f]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.factors-coverage-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px 18px;
  margin: 12px 0;
  font-size: 13px;
  background: var(--color-surface);
  transition: border-color var(--duration-fast) var(--ease-standard);
}

.coverage-good {
  border-left: 3px solid var(--color-success);
}

.coverage-warn {
  border-left: 3px solid var(--color-warning);
}

.coverage-danger {
  border-left: 3px solid var(--color-error);
}

/* Header */
.factors-coverage__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.factors-coverage__label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.factors-coverage__rate {
  font-size: 14px;
  color: var(--color-text-primary);
}

.factors-coverage__count {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 400;
}

/* Stub list */
.factors-coverage__stubs {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border-muted);
}

.factors-coverage__stub-label {
  color: var(--color-error);
  font-size: 12px;
  margin-bottom: 6px;
  font-weight: 500;
}

.factors-coverage__stub-item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 2px 0;
  font-size: 12px;
}

.factors-coverage__stub-name {
  color: var(--color-text-secondary);
}

.factors-coverage__stub-weight {
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

/* Drift table */
.factors-coverage__drift {
  margin-top: 12px;
  overflow-x: auto;
}

.drift-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.drift-table th,
.drift-table td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--color-border-muted);
  text-align: right;
  white-space: nowrap;
}

.drift-table th:first-child,
.drift-table td:first-child {
  text-align: left;
}

.drift-table th {
  color: var(--color-text-muted);
  font-weight: 500;
  font-size: 11px;
  letter-spacing: 0.03em;
}

.drift-row {
  background: rgba(245, 158, 11, 0.04);
}

.drift-up {
  color: var(--color-error);
  font-weight: 600;
}

.drift-down {
  color: var(--color-text-muted);
}
</style>
