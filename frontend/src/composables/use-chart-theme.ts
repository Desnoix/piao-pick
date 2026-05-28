import { computed } from 'vue'
import { useAppStore } from '../stores/app'

/**
 * ECharts theme-aware composable for dark/light mode sync.
 * Returns computed theme options that react to appStore.isDark changes.
 * 返回与深色/亮色模式同步的 ECharts 主题配置。
 */
export function useChartTheme() {
  const appStore = useAppStore()

  const theme = computed(() => {
    const isDark = appStore.isDark
    return {
      backgroundColor: 'transparent',
      textStyle: { color: isDark ? '#94A3B8' : '#475569' },
      title: { textStyle: { color: isDark ? '#F1F5F9' : '#0F172A' } },
      tooltip: {
        backgroundColor: isDark ? '#1E293B' : '#FFFFFF',
        borderColor: isDark ? '#334155' : '#E2E8F0',
        textStyle: { color: isDark ? '#F1F5F9' : '#0F172A', fontSize: 12 },
      },
      axisLine: { lineStyle: { color: isDark ? '#334155' : '#E2E8F0' } },
      axisLabel: { color: isDark ? '#94A3B8' : '#475569' },
      splitLine: { lineStyle: { color: isDark ? '#1E293B' : '#F1F5F9' } },
      legend: { textStyle: { color: isDark ? '#94A3B8' : '#475569' } },
      color: ['#06B6D4', '#3B82F6', '#8B5CF6', '#F59E0B', '#EC4899', '#EF4444', '#22C55E'],
    }
  })

  return { theme, isDark: computed(() => appStore.isDark) }
}
