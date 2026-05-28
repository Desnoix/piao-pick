/**
 * Vitest setup file / 测试初始化文件
 *
 * Mocks heavy or browser-dependent libraries so unit tests
 * can run in jsdom without errors.
 */
import { beforeAll, vi } from 'vitest'
import { h } from 'vue'

// Generic stub that renders slot content and is queryable
const stub: any = (props: any, { slots }: any) => {
  const children = slots?.default?.()
  return h('div', { 'data-stub': true, ...props }, children)
}

// Render a button-like stub so we can click and check text
const NButtonStub: any = (props: any, { slots }: any) => {
  const children = slots?.default?.() || slots?.icon?.()
  return h(
    'button',
    {
      'data-testid': 'n-button',
      disabled: props?.disabled,
      ...(props?.onClick ? { onClick: props.onClick } : {}),
    },
    children
  )
}

const NSelectStub: any = (props: any) =>
  h(
    'select',
    {
      'data-testid': 'n-select',
      value: props?.value ?? '',
      disabled: props?.disabled,
      onChange: (e: Event) => {
        const val = (e.target as HTMLSelectElement).value
        // v-model:value compiles to onUpdate:value prop
        if (typeof props?.['onUpdate:value'] === 'function') {
          props['onUpdate:value'](val)
        }
      },
    },
    [
      ...(props?.options || []).map((opt: any) =>
        h('option', { value: opt.value, selected: opt.value === props?.value }, opt.label)
      ),
    ]
  )

const NInputStub: any = (props: any, { slots }: any) =>
  h('input', {
    'data-testid': 'n-input',
    value: props?.value ?? '',
    placeholder: props?.placeholder,
    disabled: props?.disabled,
    onInput: (e: Event) => {
      const val = (e.target as HTMLInputElement).value
      if (typeof props?.['onUpdate:value'] === 'function') {
        props['onUpdate:value'](val)
      }
    },
  })

const NDataTableStub: any = (props: any) =>
  h('div', {
    'data-testid': 'n-data-table',
    'data-loading': props?.loading,
    'data-row-count': props?.data?.length ?? 0,
  })

const NTagStub: any = (props: any, { slots }: any) =>
  h('span', { 'data-testid': 'n-tag', 'data-type': props?.type, class: props?.class }, slots?.default?.())

const NTooltipStub: any = (_props: any, { slots }: any) =>
  h('div', { 'data-testid': 'n-tooltip' }, slots?.trigger?.())

const NSkeletonStub: any = (props: any) =>
  h('div', { 'data-testid': 'n-skeleton', style: { width: props?.width, height: props?.height } })

const NSpinStub: any = (props: any, { slots }: any) => {
  const children = slots?.default?.()
  if (props?.show) {
    return h('div', { 'data-testid': 'n-spin', 'data-show': true }, children)
  }
  return h('div', { 'data-testid': 'n-spin', 'data-show': false }, children)
}

const NDatePickerStub: any = (props: any) =>
  h('input', {
    'data-testid': 'n-date-picker',
    type: 'date',
    value: props?.value,
  })

const NStatisticStub: any = (props: any, { slots }: any) =>
  h('div', { 'data-testid': 'n-statistic' }, [
    h('span', { 'data-testid': 'stat-label' }, props?.label),
    h('span', { 'data-testid': 'stat-value' }, slots?.default?.()),
  ])

const NAlertStub: any = (props: any, { slots }: any) =>
  h('div', { 'data-testid': 'n-alert', 'data-type': props?.type }, slots?.default?.())

// Mock Naive UI components that cause issues in jsdom
vi.mock('naive-ui', () => ({
  NButton: NButtonStub,
  NInput: NInputStub,
  NForm: stub,
  NFormItem: stub,
  NSelect: NSelectStub,
  NDataTable: NDataTableStub,
  NModal: stub,
  NCard: stub,
  NSpace: stub,
  NTag: NTagStub,
  NBadge: stub,
  NTooltip: NTooltipStub,
  NSkeleton: NSkeletonStub,
  NSpin: NSpinStub,
  NDatePicker: NDatePickerStub,
  NStatistic: NStatisticStub,
  NAlert: NAlertStub,
  NConfigProvider: stub,
  useMessage: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
  darkTheme: { name: 'dark' },
}))

// Mock ECharts (heavy library)
vi.mock('echarts', () => ({
  init: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  }),
}))

// Mock echarts/core used by StockDetail
vi.mock('echarts/core', () => ({
  connect: vi.fn(),
  use: vi.fn(),
}))

// Mock IntersectionObserver (not available in jsdom)
class MockIntersectionObserver {
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()
}

beforeAll(() => {
  Object.defineProperty(window, 'IntersectionObserver', {
    value: MockIntersectionObserver,
    configurable: true,
    writable: true,
  })
})
