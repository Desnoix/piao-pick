<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  NInput,
  NButton,
  NSpace,
  NForm,
  NFormItem,
  NSpin,
  NAlert,
  NSelect,
  NSlider,
  NInputNumber,
  NSwitch,
  NCollapse,
  NCollapseItem,
  NTag,
  NCode,
  NDivider,
  NBadge,
  NTooltip,
  useMessage,
  useDialog,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import yaml from 'js-yaml'
import { getStrategy, updateStrategy, createStrategy } from '../api/strategies'
import type {
  StrategyDetail,
  StrategyConfig,
  StrategyCategory,
  FactorWeight,
  FilterRule,
} from '../types/strategy'
import { FACTOR_LABELS, FACTOR_CATEGORIES } from '../utils/constants'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const message = useMessage()
const dialog = useDialog()

const loading = ref(false)
const saving = ref(false)
const strategy = ref<StrategyDetail | null>(null)
const isNew = ref(false)
const parseError = ref('')
const rawMode = ref(false)

const name = ref('')
const displayName = ref('')
const description = ref('')
const category = ref<StrategyCategory | ''>('')
const version = ref('1.0')

const universe = ref({
  exclude_st: true,
  exclude_new_listing_days: 60,
  exclude_suspended: true,
  exclude_bse: true,
  min_market_cap: 0,
  min_daily_amount: 0,
})

const factors = ref<FactorWeight[]>([])
const filters = ref<FilterRule[]>([])
const output = ref({
  max_stocks: 30,
  sort_by: 'composite_score',
  sort_order: 'desc' as 'asc' | 'desc',
})

const rawConfig = ref('')

const categoryOptions = [
  { label: '价值', value: 'value' },
  { label: '动量', value: 'momentum' },
  { label: '质量', value: 'quality' },
  { label: '成长', value: 'growth' },
  { label: '混合', value: 'blended' },
]

const sortOptions = [
  { label: '综合得分', value: 'composite_score' },
  { label: '因子暴露', value: 'factor_exposure' },
  { label: '市值', value: 'market_cap' },
]

const filterTypeOptions = [
  { label: '百分位优选', value: 'percentile_top' },
  { label: '行业分散', value: 'industry_diversify' },
  { label: '最小市值', value: 'market_cap_min' },
]

const allFactorIds = computed(() => {
  const ids = new Set<string>()
  Object.values(FACTOR_CATEGORIES).forEach((cat) => {
    cat.forEach((id) => ids.add(id))
  })
  factors.value.forEach((f) => ids.add(f.id))
  return Array.from(ids)
})

const totalWeight = computed(() => {
  return factors.value.filter((f) => f.enabled).reduce((sum, f) => sum + f.weight, 0)
})

const weightNormalized = computed(() => {
  return Math.abs(totalWeight.value - 100) < 0.01
})

const enabledFactorCount = computed(() => {
  return factors.value.filter((f) => f.enabled).length
})

const yamlPreview = computed(() => {
  try {
    const config = buildConfigObject()
    return yaml.dump(config, { lineWidth: 120, noRefs: true })
  } catch {
    return '# YAML 生成失败'
  }
})

function getFactorLabel(id: string): string {
  return FACTOR_LABELS[id] || id
}

function getFactorCategory(factorId: string): string {
  for (const [cat, ids] of Object.entries(FACTOR_CATEGORIES)) {
    if ((ids as readonly string[]).includes(factorId)) {
      const catLabels: Record<string, string> = {
        value: '价值',
        momentum: '动量',
        quality: '质量',
        size: '规模',
      }
      return catLabels[cat] || cat
    }
  }
  return '其他'
}

function parseYamlConfig(yamlStr: string) {
  try {
    const parsed = yaml.load(yamlStr) as Record<string, unknown>
    if (!parsed || typeof parsed !== 'object') {
      throw new Error('无效的 YAML 配置')
    }

    if (parsed.name) name.value = String(parsed.name)
    if (parsed.display_name) displayName.value = String(parsed.display_name)
    if (parsed.description) description.value = String(parsed.description)
    if (parsed.category) category.value = parsed.category as StrategyCategory
    if (parsed.version) version.value = String(parsed.version)

    if (parsed.universe && typeof parsed.universe === 'object') {
      const u = parsed.universe as Record<string, unknown>
      universe.value.exclude_st = Boolean(u.exclude_st ?? true)
      universe.value.exclude_new_listing_days = Number(u.exclude_new_listing_days ?? 60)
      universe.value.exclude_suspended = Boolean(u.exclude_suspended ?? true)
      universe.value.exclude_bse = Boolean(u.exclude_bse ?? true)
      universe.value.min_market_cap = Number(u.min_market_cap ?? 0)
      universe.value.min_daily_amount = Number(u.min_daily_amount ?? 0)
    }

    if (Array.isArray(parsed.factors)) {
      const parsedFactorMap = new Map<string, FactorWeight>()
      parsed.factors.forEach((f: Record<string, unknown>) => {
        if (f.id) {
          parsedFactorMap.set(String(f.id), {
            id: String(f.id),
            weight: Number(f.weight ?? 0),
            direction: (f.direction as 'positive' | 'negative') || 'positive',
            enabled: true,
          })
        }
      })

      const merged: FactorWeight[] = []
      const seen = new Set<string>()

      parsedFactorMap.forEach((f) => {
        merged.push(f)
        seen.add(f.id)
      })

      allFactorIds.value.forEach((id) => {
        if (!seen.has(id)) {
          merged.push({ id, weight: 0, direction: 'positive', enabled: false })
        }
      })

      factors.value = merged
    } else {
      initDefaultFactors()
    }

    if (Array.isArray(parsed.filters)) {
      filters.value = parsed.filters.map((f: Record<string, unknown>) => ({
        type: String(f.type || ''),
        value: f.value !== undefined ? Number(f.value) : undefined,
        max_per_industry: f.max_per_industry !== undefined ? Number(f.max_per_industry) : undefined,
      }))
    }

    if (parsed.output && typeof parsed.output === 'object') {
      const o = parsed.output as Record<string, unknown>
      output.value.max_stocks = Number(o.max_stocks ?? 30)
      output.value.sort_by = String(o.sort_by ?? 'composite_score')
      output.value.sort_order = (o.sort_order as 'asc' | 'desc') || 'desc'
    }

    parseError.value = ''
  } catch (e: unknown) {
    const err = e as Error
    parseError.value = `YAML 解析失败: ${err.message}`
    rawMode.value = true
  }
}

function initDefaultFactors() {
  const defaults: FactorWeight[] = allFactorIds.value.map((id) => ({
    id,
    weight: 0,
    direction: 'positive',
    enabled: false,
  }))
  factors.value = defaults
}

function buildConfigObject(): StrategyConfig {
  const activeFactors: FactorWeight[] = factors.value
    .filter((f) => f.enabled)
    .map((f) => ({
      id: f.id,
      weight: f.weight,
      direction: f.direction,
      enabled: f.enabled,
    }))

  const configFilters: FilterRule[] = filters.value
    .filter((f) => f.type)
    .map((f) => {
      const rule: FilterRule = { type: f.type }
      if (f.value !== undefined) rule.value = f.value
      if (f.max_per_industry !== undefined) rule.max_per_industry = f.max_per_industry
      return rule
    })

  return {
    name: name.value,
    display_name: displayName.value,
    description: description.value,
    category: category.value || 'blended',
    version: version.value,
    default_active: true,
    default_priority: 50,
    universe: { ...universe.value },
    factors: activeFactors,
    filters: configFilters,
    output: { ...output.value },
  }
}

function serializeConfig(): string {
  const config = buildConfigObject()
  return yaml.dump(config, { lineWidth: 120, noRefs: true })
}

function normalizeWeights() {
  const enabled = factors.value.filter((f) => f.enabled)
  if (enabled.length === 0) return
  const total = enabled.reduce((sum, f) => sum + f.weight, 0)
  if (total === 0) {
    const equalWeight = Math.round(100 / enabled.length)
    enabled.forEach((f) => {
      f.weight = equalWeight
    })
    const diff = 100 - equalWeight * enabled.length
    if (diff > 0 && enabled.length > 0) {
      enabled[0].weight += diff
    }
    return
  }
  const scale = 100 / total
  enabled.forEach((f) => {
    f.weight = Math.round(f.weight * scale)
  })
  const newTotal = enabled.reduce((sum, f) => sum + f.weight, 0)
  if (newTotal !== 100 && enabled.length > 0) {
    enabled[0].weight += 100 - newTotal
  }
}

function addFilter() {
  filters.value.push({ type: 'percentile_top', value: 30 })
}

function removeFilter(index: number) {
  filters.value.splice(index, 1)
}

function toggleFactor(factorId: string, enabled: boolean) {
  const f = factors.value.find((x) => x.id === factorId)
  if (f) {
    f.enabled = enabled
    if (enabled && f.weight === 0) {
      f.weight = 10
    }
  }
}

function updateWeight(factorId: string, weight: number | null) {
  const f = factors.value.find((x) => x.id === factorId)
  if (f && weight !== null) {
    f.weight = weight
  }
}

function updateDirection(factorId: string, direction: 'positive' | 'negative') {
  const f = factors.value.find((x) => x.id === factorId)
  if (f) {
    f.direction = direction
  }
}

async function load() {
  if (props.id === 'new') {
    isNew.value = true
    initDefaultFactors()
    filters.value = [{ type: 'percentile_top', value: 30 }]
    return
  }
  loading.value = true
  try {
    strategy.value = await getStrategy(props.id)
    name.value = strategy.value.name || ''
    displayName.value = strategy.value.display_name || ''
    description.value = strategy.value.description || ''
    category.value = (strategy.value.category as StrategyCategory) || ''
    rawConfig.value = strategy.value.config || ''

    if (!rawMode.value) {
      parseYamlConfig(strategy.value.config || '')
    }
  } catch {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

function handleReset() {
  dialog.warning({
    title: '确认重置',
    content: '确定要重置为上次保存的配置吗? 未保存的更改将丢失。',
    positiveText: '重置',
    negativeText: '取消',
    onPositiveClick: () => {
      if (strategy.value?.config) {
        parseYamlConfig(strategy.value.config)
        rawConfig.value = strategy.value.config
        message.info('已重置')
      }
    },
  })
}

async function save() {
  if (!name.value.trim()) {
    message.warning('请填写策略标识')
    return
  }

  saving.value = true
  try {
    const configStr = rawMode.value ? rawConfig.value : serializeConfig()

    if (isNew.value) {
      await createStrategy({
        name: name.value,
        display_name: displayName.value || undefined,
        description: description.value || undefined,
        category: category.value || undefined,
        config: configStr,
      })
      message.success('已创建')
    } else {
      await updateStrategy(props.id, {
        display_name: displayName.value || undefined,
        description: description.value || undefined,
        category: category.value || undefined,
        config: configStr,
      })
      message.success('已保存')
    }
    router.push('/strategy/list')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    message.error(err?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function toggleRawMode() {
  if (!rawMode.value) {
    rawConfig.value = serializeConfig()
  } else {
    parseYamlConfig(rawConfig.value)
  }
  rawMode.value = !rawMode.value
}

onMounted(load)

watch(
  [factors, universe, filters, output],
  () => {
    if (!rawMode.value) {
      rawConfig.value = serializeConfig()
    }
  },
  { deep: true }
)
</script>

<template>
  <NSpin :show="loading">
    <div class="max-w-[1200px] flex flex-col gap-4">
      <!-- Breadcrumb -->
      <div class="flex items-center gap-2 text-sm">
        <router-link to="/strategy/list" class="text-[var(--color-accent)] hover:underline">策略</router-link>
        <span class="text-[var(--color-text-muted)]">/</span>
        <span class="text-[var(--color-text-secondary)]">{{ isNew ? '新建策略' : displayName || '编辑' }}</span>
      </div>

      <!-- Top Bar -->
      <div class="flex items-center justify-between flex-wrap gap-2">
        <h2 class="text-xl font-bold text-[var(--color-text-primary)]">
          {{ isNew ? '新建策略' : '编辑策略' }}
        </h2>
        <NSpace>
          <NButton size="small" @click="toggleRawMode">
            {{ rawMode ? '可视化编辑' : 'YAML 模式' }}
          </NButton>
          <NButton @click="router.push('/strategy/list')">取消</NButton>
          <NButton v-if="!isNew" @click="handleReset">重置</NButton>
          <NButton type="primary" :loading="saving" @click="save">保存</NButton>
        </NSpace>
      </div>

      <NAlert v-if="parseError" type="error" class="mb-2">
        {{ parseError }}
      </NAlert>

      <!-- Raw YAML Mode -->
      <template v-if="rawMode">
        <NForm label-placement="left" label-width="100">
          <NFormItem v-if="isNew" label="标识">
            <NInput v-model:value="name" placeholder="策略唯一标识 (英文)" />
          </NFormItem>
          <NFormItem label="配置 (YAML)">
            <NInput
              v-model:value="rawConfig"
              type="textarea"
              :rows="30"
              placeholder="策略 YAML 配置"
              class="font-mono"
            />
          </NFormItem>
        </NForm>
      </template>

      <!-- Visual Editor Mode -->
      <template v-else>
        <!-- Basic Info -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <NForm label-placement="left" label-width="80">
            <NFormItem v-if="isNew" label="标识">
              <NInput v-model:value="name" placeholder="策略唯一标识 (英文)" />
            </NFormItem>
            <NFormItem label="名称">
              <NInput v-model:value="displayName" placeholder="显示名称" />
            </NFormItem>
            <NFormItem label="类别">
              <NSelect
                v-model:value="category"
                :options="categoryOptions"
                placeholder="选择类别"
                clearable
              />
            </NFormItem>
          </NForm>
          <NForm label-placement="left" label-width="80">
            <NFormItem label="描述">
              <NInput
                v-model:value="description"
                type="textarea"
                :rows="3"
                placeholder="策略描述"
              />
            </NFormItem>
          </NForm>
        </div>

        <NDivider />

        <!-- Section 1: Universe Filters -->
        <NCollapse :default-expanded-names="['universe']" arrow-placement="left">
          <NCollapseItem title="选股池 (Universe)" name="universe">
            <div class="glass-panel p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="flex flex-col gap-3">
                <div class="flex items-center justify-between">
                  <span class="text-sm text-[var(--color-text-secondary)]">排除 ST 股票</span>
                  <NSwitch v-model:value="universe.exclude_st" />
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-sm text-[var(--color-text-secondary)]">排除停牌股</span>
                  <NSwitch v-model:value="universe.exclude_suspended" />
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-sm text-[var(--color-text-secondary)]">排除北交所</span>
                  <NSwitch v-model:value="universe.exclude_bse" />
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-sm text-[var(--color-text-secondary)]">排除次新股 (上市天数)</span>
                  <NInputNumber
                    v-model:value="universe.exclude_new_listing_days"
                    :min="0"
                    :max="365"
                    size="small"
                    style="width: 120px"
                  />
                </div>
              </div>
              <div class="flex flex-col gap-3">
                <div class="flex items-center justify-between">
                  <span class="text-sm text-[var(--color-text-secondary)]">最小市值 (亿元)</span>
                  <NInputNumber
                    v-model:value="universe.min_market_cap"
                    :min="0"
                    :step="10"
                    size="small"
                    style="width: 160px"
                  />
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-sm text-[var(--color-text-secondary)]">最小日均成交额 (万元)</span>
                  <NInputNumber
                    v-model:value="universe.min_daily_amount"
                    :min="0"
                    :step="100"
                    size="small"
                    style="width: 160px"
                  />
                </div>
              </div>
            </div>
          </NCollapseItem>
        </NCollapse>

        <NDivider />

        <!-- Section 2: Factor Weights -->
        <NCollapse :default-expanded-names="['factors']" arrow-placement="left">
          <NCollapseItem name="factors">
            <template #header>
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-[var(--color-text-primary)]">因子权重</span>
                <NTag size="small" :type="weightNormalized ? 'success' : 'warning'">
                  已启用: {{ enabledFactorCount }} | 总权重: {{ totalWeight }}%
                </NTag>
                <NButton
                  v-if="!weightNormalized && enabledFactorCount > 0"
                  size="tiny"
                  type="primary"
                  @click.stop="normalizeWeights"
                >
                  自动归一
                </NButton>
              </div>
            </template>
            <div class="glass-panel p-4 flex flex-col gap-2">
              <div
                v-for="factor in factors"
                :key="factor.id"
                class="flex items-center gap-3 p-2 rounded border transition-colors"
                :class="[
                  factor.enabled
                    ? 'border-[var(--color-border)] bg-[var(--color-surface-inset)]'
                    : 'border-[var(--color-border-muted)] opacity-40',
                ]"
              >
                <NSwitch
                  :value="factor.enabled"
                  size="small"
                  @update:value="(val: boolean) => toggleFactor(factor.id, val)"
                />
                <div class="w-32 shrink-0">
                  <div class="text-sm font-medium text-[var(--color-text-primary)]">{{ getFactorLabel(factor.id) }}</div>
                  <NTag size="tiny" class="mt-0.5">
                    {{ getFactorCategory(factor.id) }}
                  </NTag>
                </div>
                <NTooltip>
                  <template #trigger>
                    <NTag
                      size="tiny"
                      :type="factor.direction === 'positive' ? 'error' : 'success'"
                      class="shrink-0 cursor-pointer"
                      @click="
                        updateDirection(
                          factor.id,
                          factor.direction === 'positive' ? 'negative' : 'positive'
                        )
                      "
                    >
                      {{ factor.direction === 'positive' ? '正向' : '负向' }}
                    </NTag>
                  </template>
                  点击切换因子方向
                </NTooltip>
                <NSlider
                  :value="factor.weight"
                  :min="0"
                  :max="100"
                  :step="5"
                  :disabled="!factor.enabled"
                  class="flex-1 min-w-[100px]"
                  @update:value="(val: number) => updateWeight(factor.id, val)"
                />
                <NInputNumber
                  :value="factor.weight"
                  :min="0"
                  :max="100"
                  :step="5"
                  :disabled="!factor.enabled"
                  size="small"
                  style="width: 80px"
                  @update:value="(val: number | null) => updateWeight(factor.id, val)"
                />
              </div>
            </div>
          </NCollapseItem>
        </NCollapse>

        <NDivider />

        <!-- Section 3: Filters -->
        <NCollapse :default-expanded-names="['filters']" arrow-placement="left">
          <NCollapseItem title="过滤规则" name="filters">
            <div class="glass-panel p-4 flex flex-col gap-3">
              <div
                v-for="(filter, index) in filters"
                :key="index"
                class="flex items-center gap-3 p-3 rounded border border-[var(--color-border)]"
              >
                <NSelect
                  v-model:value="filter.type"
                  :options="filterTypeOptions"
                  size="small"
                  style="width: 160px"
                />
                <template v-if="filter.type === 'percentile_top'">
                  <span class="text-sm text-[var(--color-text-secondary)]">保留前</span>
                  <NInputNumber
                    v-model:value="filter.value"
                    :min="1"
                    :max="200"
                    size="small"
                    style="width: 100px"
                  />
                  <span class="text-sm text-[var(--color-text-muted)]">只</span>
                </template>
                <template v-else-if="filter.type === 'industry_diversify'">
                  <span class="text-sm text-[var(--color-text-secondary)]">每行业最多</span>
                  <NInputNumber
                    v-model:value="filter.max_per_industry"
                    :min="1"
                    :max="30"
                    size="small"
                    style="width: 100px"
                  />
                  <span class="text-sm text-[var(--color-text-muted)]">只</span>
                </template>
                <template v-else-if="filter.type === 'market_cap_min'">
                  <span class="text-sm text-[var(--color-text-secondary)]">最小市值</span>
                  <NInputNumber
                    v-model:value="filter.value"
                    :min="0"
                    :step="10"
                    size="small"
                    style="width: 140px"
                  />
                  <span class="text-sm text-[var(--color-text-muted)]">亿元</span>
                </template>
                <NButton
                  size="small"
                  type="error"
                  ghost
                  @click="removeFilter(index)"
                >
                  删除
                </NButton>
              </div>
              <NButton size="small" @click="addFilter">添加过滤规则</NButton>
            </div>
          </NCollapseItem>
        </NCollapse>

        <NDivider />

        <!-- Section 4: Output -->
        <NCollapse :default-expanded-names="['output']" arrow-placement="left">
          <NCollapseItem title="输出设置" name="output">
            <div class="glass-panel p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <div class="text-sm mb-1 text-[var(--color-text-secondary)]">最大股票数</div>
                <NInputNumber
                  v-model:value="output.max_stocks"
                  :min="1"
                  :max="500"
                  size="small"
                  class="w-full"
                />
              </div>
              <div>
                <div class="text-sm mb-1 text-[var(--color-text-secondary)]">排序依据</div>
                <NSelect
                  v-model:value="output.sort_by"
                  :options="sortOptions"
                  size="small"
                />
              </div>
              <div>
                <div class="text-sm mb-1 text-[var(--color-text-secondary)]">排序方向</div>
                <NSpace align="center" :size="8">
                  <NTag
                    size="small"
                    :type="output.sort_order === 'desc' ? 'error' : 'default'"
                    class="cursor-pointer"
                    @click="output.sort_order = 'desc'"
                  >
                    降序
                  </NTag>
                  <NTag
                    size="small"
                    :type="output.sort_order === 'asc' ? 'success' : 'default'"
                    class="cursor-pointer"
                    @click="output.sort_order = 'asc'"
                  >
                    升序
                  </NTag>
                </NSpace>
              </div>
            </div>
          </NCollapseItem>
        </NCollapse>

        <NDivider />

        <!-- Section 5: Live YAML Preview -->
        <NCollapse arrow-placement="left">
          <NCollapseItem title="YAML 预览">
            <pre class="text-xs font-mono p-4 bg-[var(--color-surface-inset)] rounded-lg overflow-auto max-h-[400px] whitespace-pre text-[var(--color-text-primary)]">{{ yamlPreview }}</pre>
          </NCollapseItem>
        </NCollapse>
      </template>
    </div>
  </NSpin>
</template>
