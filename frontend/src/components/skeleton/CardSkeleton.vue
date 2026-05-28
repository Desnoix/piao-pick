<script setup lang="ts">
/**
 * Card skeleton: grid of card placeholders with header, body, and footer.
 * 卡片骨架: 卡片网格占位，含标题、描述、底部操作区。
 */
import { NSkeleton } from 'naive-ui'

defineProps<{
  /** 卡片数量 / Number of cards, default 4 */
  count?: number
}>()
</script>

<template>
  <div class="card-skeleton-grid">
    <div v-for="n in count ?? 4" :key="n" class="card-skeleton">
      <!-- Header: title + status tag -->
      <div class="card-skeleton__header">
        <NSkeleton width="140px" height="16px" :sharp="false" />
        <NSkeleton width="48px" height="20px" round />
      </div>

      <!-- Body: description text (2 lines) -->
      <div class="card-skeleton__body">
        <NSkeleton text :repeat="2" />
      </div>

      <!-- Footer: action buttons -->
      <div class="card-skeleton__footer">
        <NSkeleton width="64px" height="28px" round />
        <NSkeleton width="64px" height="28px" round />
      </div>
    </div>
  </div>
</template>

<style scoped>
.card-skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.card-skeleton {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-elevated);
}

.card-skeleton__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-skeleton__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-skeleton__footer {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
</style>
