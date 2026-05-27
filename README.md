# 飘票选股系统

A股多因子量化选股系统 -- 从全市场 5000+ 只股票中，按可量化的多因子规则，筛选出候选股票池。

## 功能特性

**数据采集**
- 实时行情快照：东方财富 / 新浪财经双数据源，自动 fallback
- 历史K线拉取：批量同步全 A 股日线数据，断点续传 + 智能限速
- 交易日历管理：自动识别交易日，支持手动/定时同步

**多因子选股**
- 12 个内置因子：估值 (PE/PB/PS/FCF)、动量 (20日/60日)、质量 (ROE/毛利率)、成长 (营收/利润增速)、规模 (市值)
- 时序因子计算：MA 均线、20 日动量、60 日波动率、20 日均换手率
- 因子处理管线：Winsorize 极值处理 + Z-Score 标准化 + 方向对齐
- YAML 驱动策略配置，不改代码即可调整因子权重和过滤规则

**策略回测**
- 月度调仓回测引擎，等权持仓模式
- 核心指标：年化收益、夏普比率、最大回撤、Calmar、月度胜率、IC/ICIR
- 净值曲线对比、年度热力图、月度收益分布

**可视化**
- 6 个功能页面：选股主页、策略管理、策略编辑、策略对比、个股详情、数据状态
- ECharts 图表：K 线图、因子雷达图、净值曲线、行业分布、收益热力图
- 暗/亮双主题，Geist 字体，A 股配色 (红涨绿跌)

## 技术栈

| 层 | 技术 |
|---|---|
| **后端** | Python 3.11+ / FastAPI / pandas + numpy / scipy / statsmodels |
| **数据源** | AKShare (东方财富) + 新浪财经直连 (hq.sinajs.cn) |
| **前端** | Vue 3 + TypeScript + Vite / Naive UI + TailwindCSS v4 / ECharts |
| **数据库** | SQLite (零部署，单文件) |
| **部署** | Docker Compose |

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+ (前端)

### 1. 安装依赖

```bash
# 后端
cd backend
pip install -r ../requirements.txt

# 前端
cd frontend
npm install
```

### 2. 初始化数据库

```bash
cd backend
python scripts/init_db.py
```

自动创建 6 张表 (`stock_info`, `kline_daily`, `factor_daily`, `strategies`, `selection_results`, `history_sync_tasks`)，并加载内置策略。

**重要**：如果你是从旧版本升级，请务必重新运行 `python scripts/init_db.py` 来确保数据库 schema 是最新的。该脚本是幂等的，可以安全地多次运行。它会：
- 创建所有必要的表（如果不存在）
- 应用最新的 schema 迁移（如添加 `turnover_rate` 列）
- 加载示例策略到数据库（如果不存在）

运行成功后会看到类似输出：
```
[INFO] init_db: Database tables created successfully
[INFO] init_db: Applying migration: add turnover_rate column...
[INFO] init_db: ✓ Added turnover_rate column
[INFO] init_db: Loaded 2 strategies from ./strategies
[INFO] init_db: Database initialization complete!
```

### 3. 启动服务

```bash
# 后端 (端口 8000)
cd backend
uvicorn app.main:app --reload

# 前端 (端口 5173, 自动代理到后端)
cd frontend
npm run dev
```

访问 `http://localhost:5173`

### 4. 首次使用流程

```
Step 1: 运行选股 (自动拉取当日快照)
        → 自动获取全市场 5000+ 只股票实时数据
        → 执行选股策略，输出 Top 候选

Step 2: 拉取历史数据 (数据状态页, 仅需一次)
        → 逐个同步各股历史 K 线 (30-60 分钟)

Step 3: 计算时序因子 (数据状态页, 仅需一次)
        → 基于 K 线计算 20 日动量、60 日波动率等 (2-5 分钟)

Step 4: 重新运行选股
        → 包含截面因子 + 时序因子的完整评分
```

## 项目结构

```
piao-pick/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理 (.env)
│   │   ├── database.py          # SQLite 连接
│   │   ├── api/v1/
│   │   │   ├── stocks.py        # 股票数据 API
│   │   │   ├── strategies.py    # 策略 CRUD API
│   │   │   ├── selection.py     # 选股执行 API
│   │   │   ├── backtest.py      # 回测 API
│   │   │   ├── data_status.py   # 数据状态 API
│   │   │   └── history_sync.py  # 历史同步 + 因子计算 API
│   │   ├── core/
│   │   │   ├── factor/          # 12 因子计算模块
│   │   │   ├── strategy/        # 策略加载 / 执行 / 过滤器
│   │   │   ├── backtest/        # 回测引擎 / 风险指标
│   │   │   ├── pipeline.py      # SelectionPipeline 中央调度
│   │   │   └── trading_calendar.py
│   │   ├── services/
│   │   │   ├── data_preparation.py        # 全市场快照 (EM→Sina)
│   │   │   ├── historical_data_service.py # 历史数据批量拉取
│   │   │   ├── factor_compute_service.py  # 时序因子计算
│   │   │   ├── selection_service.py       # 选股服务
│   │   │   └── backtest_service.py        # 回测服务
│   │   ├── repositories/        # 数据访问层 (5 个 Repo)
│   │   ├── models/              # ORM 模型 (SQLModel)
│   │   └── schemas/             # Pydantic 验证
│   ├── data_provider/
│   │   ├── base.py              # BaseFetcher + DataFetcherManager
│   │   ├── akshare_fetcher.py   # 东方财富 + 新浪快照
│   │   └── tushare_fetcher.py   # TuShare (备用)
│   ├── strategies/              # YAML 策略文件
│   │   ├── value_lowvol.yaml    # 价值低波
│   │   └── momentum_growth.yaml # 动量成长
│   ├── scripts/
│   │   └── init_db.py
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── pages/               # 6 个页面
│   │   ├── components/          # ECharts 图表 + 通用组件
│   │   ├── api/                 # Axios API 层
│   │   ├── stores/              # Pinia 状态管理
│   │   ├── composables/         # 组合式函数
│   │   └── utils/               # 格式化 + 常量 + Mock 数据
│   └── ...
│
├── .sisyphus/plans/             # 技术方案文档
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

## API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/v1/stocks` | 股票列表 |
| `GET` | `/api/v1/stocks/{code}` | 个股详情 |
| `GET` | `/api/v1/stocks/{code}/kline` | K 线数据 |
| `GET` | `/api/v1/stocks/{code}/factors` | 因子数据 |
| `GET/POST` | `/api/v1/strategies` | 策略 CRUD |
| `POST` | `/api/v1/selection/run` | 运行选股 |
| `GET` | `/api/v1/selection/results` | 选股结果 |
| `POST` | `/api/v1/backtest/run` | 运行回测 |
| `POST` | `/api/v1/data/sync` | 手动同步当日数据 |
| `POST` | `/api/v1/data/history-sync` | 启动历史数据同步 |
| `GET` | `/api/v1/data/history-sync/status` | 历史同步进度 |
| `POST` | `/api/v1/data/factor-compute` | 计算时序因子 |
| `GET` | `/api/v1/data/status` | 数据库状态 |
| `GET` | `/api/v1/data/trade-calendar` | 交易日历 |

完整 API 文档启动后端后访问 `http://localhost:8000/docs` (Swagger UI)。

## 策略配置

策略采用 YAML 声明式配置，存放于 `backend/strategies/`：

```yaml
name: value_lowvol
display_name: 价值低波
category: value

universe:
  exclude_st: true
  exclude_new_listing_days: 60
  exclude_suspended: true
  exclude_bse: true

factors:
  - id: pe_ttm
    weight: 0.20
    direction: negative
  - id: roe_ttm
    weight: 0.20
    direction: positive
  - id: ret_60d_vol
    weight: 0.20
    direction: negative
  # ...

filters:
  - type: percentile_top
    count: 100
  - type: industry_diversify
    max_per_industry: 5

output:
  max_stocks: 30
```

内置 2 个策略：**价值低波** (value_lowvol) 和 **动量成长** (momentum_growth)。可在前端策略编辑器中可视化调整。

## 环境变量

在 `backend/` 目录创建 `.env` 文件：

```ini
# 数据库
DB_PATH=./data/piao_pick.db

# 数据源 (TuShare 可配置后自动启用)
TUSHARE_TOKEN=

# 定时调度
SCHEDULE_ENABLED=false
SCHEDULE_TIME=15:30

# 日志
LOG_LEVEL=INFO
```

## 设计要点

**数据源策略**：借鉴 [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) 的 DataFetcherManager 模式。东方财富 (`push2.eastmoney.com`) 优先 (字段丰富，2 次重试)；被网络拦截时自动降级到新浪财经直连请求 (`hq.sinajs.cn`)，批量 50 只/次。

**未来数据防护**：策略选股和回测引擎严格使用 `trade_date` 作为数据截止点，财报因子引入"数据可得日期"概念。

**数据库**：SQLite 单文件零部署，5 年内数据量 (<1000 万行) 完全够用。未来可迁移到 PostgreSQL + TimescaleDB (SQL 语法 90% 兼容)。

## 设计文档

完整技术架构方案 (v2.0, Momus 审查通过)：[`.sisyphus/plans/technical-plan.md`](.sisyphus/plans/technical-plan.md)

历史版本备份：[`.sisyphus/plans/technical-plan.v1.md`](.sisyphus/plans/technical-plan.v1.md)

## 免责声明

本系统仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。
