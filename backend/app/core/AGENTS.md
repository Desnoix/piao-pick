# backend/app/core — 量化引擎

多因子选股的领域逻辑。三个子系统: 因子计算、策略执行、回测。

## 结构

```
core/
├── factor/              # 12 个因子，分 5 个类别
│   ├── base.py          # FactorPipeline: winsorize → z_score → align → composite_score
│   ├── value.py         # PE, PB, PS, FCF 收益率
│   ├── momentum.py      # 20日/60日收益率, 波动率
│   ├── quality.py       # ROE, 毛利率
│   ├── growth.py        # 营收/利润增速
│   └── size.py          # 市值
├── strategy/            # 策略加载 + 执行
│   ├── loader.py        # StrategyLoader: 从 backend/strategies/ 读取 YAML
│   ├── executor.py      # StrategyExecutor: 股票池过滤 → 因子处理 → 排名
│   └── filters.py       # PercentileTop, IndustryDiversify 等
├── backtest/            # 回测引擎
│   ├── engine.py        # 月度调仓, 等权持仓
│   ├── metrics.py       # 夏普比率, 最大回撤, Calmar, 胜率
│   └── ic_analysis.py   # IC/ICIR 因子有效性指标
├── pipeline.py          # SelectionPipeline: 中央调度 (策略→因子→执行→保存)
├── scheduler.py         # 基于 APScheduler 的每日定时选股触发器
└── trading_calendar.py  # 交易日历 (exchange-calendars 库), trade_date 解析
```

## 在哪里找什么

| 任务 | 位置 | 说明 |
|------|------|------|
| 新增因子 | `factor/<类别>.py` | 遵循现有模式: 计算 → 返回 Series |
| 修改因子处理 | `factor/base.py::FactorPipeline` | Winsorize(±3σ) → fillna → z_score → direction |
| 新增过滤器类型 | `strategy/filters.py` | 添加类，在 executor 中注册 |
| 修改回测 | `backtest/engine.py` | 月度调仓, 等权持仓 |
| 风险指标 | `backtest/metrics.py` | 夏普, 最大回撤, Calmar, 年化收益 |
| 因子有效性 | `backtest/ic_analysis.py` | IC (秩相关), ICIR |
| 运行完整选股 | `pipeline.py::SelectionPipeline.run()` | 7 步流程，带进度回调 |

## 约定

- **因子类别**: value (PE/PB/PS/FCF)、momentum (收益/波动率)、quality (ROE/毛利率)、growth (营收/利润)、size (市值)。每个类别一个文件。
- **FactorPipeline 类** (`factor/base.py`): 提供 `process()` 和 `composite_score()` — 管线步骤顺序详见根目录 AGENTS.md。
- **策略执行流程**: 股票池过滤 → 原始因子快照 → 因子处理 → 综合评分 → 排名 → 应用输出过滤 → 返回 Top N。
- **交易日期解析**: 使用 `trading_calendar.get_effective_trading_date()` 将周末/节假日解析为最近有效交易日。
- **方向语义**: `direction: negative` 表示原始值越低越好 (如 PE)。管线取负使所有因子变为"越大越好"后排名。

## 反模式

- 禁止在任何计算中使用 `trade_date` 之后的数据 — 这是前视偏差。
- 禁止在 executor 中硬编码因子名称 — 始终从策略 YAML 配置读取。
- 禁止在未理解统计影响的情况下修改 `FactorPipeline.process()` 步骤顺序。
- 禁止跳过 `winsorize` — 极端值 (离群点) 会主导 z-score 标准化。
- **交易日历 fail-open**: 当 `exchange-calendars` 超出范围 (当前截至约 2025-12-31) 时，`get_effective_trading_date()` 对所有日期返回 True (交易日)。涉及未来日期需谨慎测试。
- **生存偏差缺口**: 回测尚未包含退市股 — 技术文档中已承认此局限。
- **未知过滤器类型**: YAML 配置中的未知类型仅记录警告并静默跳过 — 生产部署前须校验过滤器名称。
