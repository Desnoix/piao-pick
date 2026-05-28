# frontend/src — Vue 3 SPA

量化选股 UI。Vue 3 + TypeScript + Vite，Naive UI 组件库，TailwindCSS v4，ECharts 可视化。

## 结构

```
src/
├── App.vue              # 根组件: NaiveUI Provider + 主题包装
├── main.ts              # 启动入口: 创建 app + 安装插件
├── pages/               # 7 个路由页面 (懒加载)
├── components/
│   ├── charts/          # 7 个 ECharts 组件 (KLine, FactorRadar, NavCurve, Heatmap...)
│   └── common/          # FactorBadge, MetricCard, StockHeader
├── api/                 # Axios 客户端 (baseURL: /api/v1) + 按领域划分的 API 模块
├── stores/              # Pinia: app (主题), selection, strategy
├── composables/         # useStockDetail, useTheme
├── router/              # Vue Router: 7 条路由, 全部懒加载
├── types/               # TypeScript 接口: stock, strategy, selection, backtest, api
└── utils/               # format (货币/百分比), constants (A股规则), mock 数据
```

## 在哪里找什么

| 任务 | 位置 | 说明 |
|------|------|------|
| 新增页面 | `pages/` | 添加 .vue 文件 + 在 `router/index.ts` 中注册路由 |
| 新增图表 | `components/charts/` | 基于 vue-echarts 封装 ECharts 5 |
| API 调用 | `api/` | `client.ts` = Axios 实例, 每个领域一个文件 |
| 状态管理 | `stores/` | Pinia 组合式 API 风格 (`defineStore` + setup 函数) |
| 共享类型 | `types/` | 镜像后端 Pydantic schemas |
| A股格式化 | `utils/format.ts` | 货币 (¥), 百分比, 股票代码补零 |
| 主题切换 | `stores/app.ts` | 暗/亮模式, 持久化到 localStorage |

## 约定

- **仅组合式 API**: 所有组件使用 `<script setup lang="ts">`。禁止 Options API。
- **Pinia stores**: 组合式风格 (`defineStore` + setup 函数)，非 options 风格。
- **相对路径导入**: 使用 `../stores/strategy`、`./client` — 不用 `@/` 别名 (别名已配置但约定不使用)。
- **TS 严格模式带放宽**: `strict: true` 但 `noUnusedLocals: false` 和 `noUnusedParameters: false` — 有意放宽。
- **路由懒加载**: `component: () => import('../pages/X.vue')` 用于所有路由。
- **Naive UI 主题**: `useAppStore().naiveTheme` 提供 `darkTheme` 或 `null`。通过 `<n-config-provider :theme="naiveTheme">` 应用。
- **TailwindCSS v4 (alpha/前沿)**: 通过 `@tailwindcss/vite` 插件。CSS-first 配置 — 无 `tailwind.config.js`。自定义主题 token 定义在 `src/assets/main.css` 的 CSS `@theme` 指令中。
- **ECharts 通过 vue-echarts**: 使用 `<v-chart>` 组件。启用自动 resize。
- **A股配色约定**: 红色 (#ef4444) = 涨, 绿色 (#22c55e) = 跌。与西方市场相反。
- **API 基础 URL**: `/api/v1` (开发环境通过 Vite 代理至 backend:8000)。
- **类型镜像**: `types/` 文件镜像后端 `schemas/`。需手动保持同步。

## 反模式

- 禁止使用 Options API — 项目全部采用组合式 API + `<script setup>`。
- 禁止在组件中直接使用 `axios` — 使用 `api/` 目录中的 API 模块。
- 禁止为股票涨跌硬编码颜色 — 使用 A股约定 (红涨绿跌)。
- 禁止绕过 Pinia stores 管理共享状态 — 组件应从 stores 读取，不要重复发起 API 调用。
- 禁止在参数化路由上遗漏 `props: true` (如 `/stock/:ts_code`)。
- `FinancialTrend.vue` (图表组件) 位于 `components/` 根目录而非 `components/charts/` — 孤儿组件。新图表组件放入 `charts/`。
- `utils/mock.ts` 中的 mock 数据为随机游走生成 (非真实行情数据) — 禁止用于分析/回测。
