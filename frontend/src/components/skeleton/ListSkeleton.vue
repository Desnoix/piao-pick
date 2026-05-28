<script setup lang="ts">
/**
 * List skeleton: key-value row placeholders for data overview / detail lists.
 * 列表骨架: KV 列表行占位，用于数据概览等场景。
 */
import { NSkeleton } from 'naive-ui'

defineProps<{
  /** 行数 / Number of rows, default 6 */
  rows?: number
}>()
</script>

<template>
  <div class="list-skeleton">
    <div v-for="r in rows ?? 6" :key="r" class="list-skeleton__row">
      <NSkeleton width="80px" height="13px" :sharp="false" />
      <NSkeleton width="160px" height="13px" :sharp="false" />
    </div>
  </div>
</template>

<style scoped>
.list-skeleton {
  display: flex;
  flex-direction: column;
}

.list-skeleton__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--color-border);
}

.list-skeleton__row:last-child {
  border-bottom: none;
}
</style>
