<script setup lang="ts">
/**
 * Chart skeleton: rectangular placeholder with optional axis decoration lines.
 * 图表骨架: 矩形占位 + 可选坐标轴装饰线。
 */
import { NSkeleton } from 'naive-ui'

defineProps<{
  /** 宽度 / Width, default '100%' */
  width?: string
  /** 高度 / Height, default '240px' */
  height?: string
  /** 显示坐标轴装饰 / Show axis decoration lines, default true */
  showAxis?: boolean
}>()
</script>

<template>
  <div class="chart-skeleton" :style="{ width: width ?? '100%' }">
    <!-- Chart title placeholder -->
    <NSkeleton width="120px" height="12px" :sharp="false" class="mb-3" />

    <!-- Main rectangle + optional axis lines -->
    <div class="chart-skeleton__body" :style="{ height: height ?? '240px' }">
      <NSkeleton :width="width ?? '100%'" :height="height ?? '240px'" round />

      <!-- Axis decoration -->
      <template v-if="showAxis !== false">
        <div class="chart-skeleton__axis-x" />
        <div class="chart-skeleton__axis-y" />
      </template>
    </div>
  </div>
</template>

<style scoped>
.chart-skeleton {
  display: flex;
  flex-direction: column;
}

.chart-skeleton__body {
  position: relative;
}

.chart-skeleton__axis-x {
  position: absolute;
  bottom: 12px;
  left: 32px;
  right: 12px;
  height: 1px;
  background: var(--color-border-muted);
}

.chart-skeleton__axis-y {
  position: absolute;
  top: 12px;
  bottom: 32px;
  left: 32px;
  width: 1px;
  background: var(--color-border-muted);
}
</style>
