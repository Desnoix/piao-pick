# 项目知识库

**生成时间:** 2026-05-27
**项目:** piao-pick (飘票选股系统)

## 概述

A股多因子量化选股系统 — 从全市场 5000+ 只股票中，按可量化的多因子策略筛选候选股票池，支持回测与可视化。Python 3.11+/FastAPI 后端 + Vue 3/TypeScript 前端，SQLite 存储，Docker Compose 部署。

## 项目结构

```
piao-pick/
├── backend/                 # FastAPI 应用 + 数据源 + 策略
│   ├── app/                 # 应用包 → 详见 backend/app/AGENTS.md
│   ├── data_provider/       # 可插拔行情数据源 (策略模式 + 自动故障转移)
│   ├── strategies/          # YAML 策略定义 (value_lowvol, momentum_growth)
│   ├── scripts/             # 数据库初始化 + 迁移 (init_db.py 幂等)
│   └── tests/               # E2E + 集成测试 (无测试框架)
├── frontend/                # Vue 3 SPA → 详见 frontend/src/AGENTS.md
│   └── src/
├── .sisyphus/plans/         # 技术架构文档 (technical-plan.md = v2.0 规范)
├── docker-compose.yml       # 仅后端 (端口 8000)
├── pyproject.toml           # Python 构建配置
└── requirements.txt         # 后端依赖锁定
```

## 在哪里找什么

| 任务 | 位置 | 说明 |
|------|------|------|
| 新增 API 端点 | `backend/app/api/v1/` | 在 `router.py` 中注册路由前缀 |
| 新增因子 | `backend/app/core/factor/` | 每个类别一个文件 (value/growth/momentum/quality/size) |
| 新增策略 | `backend/strategies/*.yaml` | 纯 YAML 配置，无需改代码 |
| 新增页面 | `frontend/src/pages/` | 在 `router/index.ts` 中添加路由 |
| 新增图表 | `frontend/src/components/charts/` | 基于 vue-echarts 的 ECharts 封装 |
| 更换数据源 | `backend/data_provider/` | 继承 BaseFetcher，设置 priority |
| 数据库 Schema 变更 | `backend/scripts/` | 新建迁移文件 + 重新运行 init_db.py |
| 配置修改 | `backend/app/config.py` | 从 `.env` 加载的单例 — 参见 `.env.example` |

## 关键架构偏差

- **`data_provider/` 位于 `app/` 外部** — 它是 `app/` 的兄弟目录，不是子包。当 `backend/` 在 `sys.path` 中时，可作为顶层模块导入 (`from data_provider.akshare_fetcher import ...`)。拥有自己的策略模式 (BaseFetcher + DataFetcherManager)，独立于 app/ 架构。
- **策略双源真相**: `backend/strategies/*.yaml` (人类可编辑) 与 SQLite `strategies` 表 (运行时)。`init_db.py` 将 YAML→DB 同步。在数据库中修改策略不会更新 YAML。修改 YAML 后必须重新运行 `init_db.py`。
- **`schemas/` 两层重复**: `app/schemas/` (Pydantic 校验) 和 `app/api/v1/schemas/` (API 特有共享模型如 PaginatedResponse)。加上 SQLModel 模型本身已自带 Pydantic — 三层数据表示。
- **`check_data_status.py` 位于 `backend/` 根目录** — 一个诊断脚本，不在 `scripts/` 和 `app/` 任一位置。

## 约定

- **双语文档**: 所有模块均有中英文 docstring。注释中英文混用。
- **单例模式**: `Config` 和 `DatabaseManager` 使用 `get_instance()` / `get_config()` / `get_db()` — 禁止直接实例化。
- **仓库模式**: API → Services → Repositories → Models。Services 编排，Repos 执行 SQL。
- **策略模式**: `DataFetcherManager` 管理优先级排序的数据源，自动故障转移 (AkshareFetcher P0 → TushareFetcher P1)。
- **因子管线**: Winsorize(±3σ) → fillna(均值) → Z-Score → 方向对齐 → 加权综合分 [0-100]。
- **YAML 驱动策略**: 所有策略配置在 `backend/strategies/*.yaml`。结构: universe → factors → filters → output。
- **A股配色**: 红涨绿跌 (red=涨, green=跌) — 与西方惯例相反。
- **未来数据防护**: 所有策略/回测代码严格以 `trade_date` 作为数据截止点。财报因子引入"数据可得日期"概念。
- **API 前缀**: 所有端点在 `/api/v1/` 下。健康检查在 `/api/health`。
- **前端代理**: Vite 将 `/api` 代理至 `localhost:8000`。SPA 回退为所有非 API 路由返回 `index.html`。

## 反模式 (本项目)

- 禁止直接实例化 `Config()` 或 `DatabaseManager()` — 使用 `get_config()` / `get_db()`。
- 禁止使用带交易所前缀的原始股票代码 (SH600519, 000001.SZ) — 必须先调用 `normalize_stock_code()`。前缀剥离集中在 `data_provider/base.py`。
- 禁止在因子计算中使用 `trade_date` 之后的数据 — 这是前视偏差，会使回测失效。
- 禁止在 Python 中添加策略逻辑 — 使用 `backend/strategies/` 中的 YAML 配置。
- 禁止在 Schema 变更后跳过 `init_db.py` — 它会应用迁移且是幂等的。

## 命令

```bash
# 后端
cd backend && uvicorn app.main:app --reload    # 开发服务器 :8000
cd backend && python scripts/init_db.py        # 初始化/迁移数据库 (幂等)
pip install -r ../requirements.txt             # 安装依赖

# 前端
cd frontend && npm run dev                     # 开发服务器 :5173
cd frontend && npm run build                   # 生产构建
cd frontend && npm install                     # 安装依赖

# Docker
docker-compose up                              # 仅后端 (端口 8000)
```

## 备注

- **无 CI/CD 管线** — 无 GitHub Actions，无代码检查/格式化工具 (无 ESLint、Prettier、Ruff、Mypy)。代码风格纯靠约定。`vue-tsc` 是唯一自动化检查 (`npm run build`)。
- **无 pytest** — 后端测试为纯 Python 脚本 (`python tests/test_*.py`)，非 pytest。无 `conftest.py`，无覆盖率配置。
- SQLite 单文件数据库 (`data/piao_pick.db`) — 满足 5 年数据量 (<1000 万行)。PostgreSQL 迁移路径: 90% SQL 兼容。
- 6 张数据库表: `stock_info`、`kline_daily`、`factor_daily`、`strategies`、`selection_results`、`history_sync_tasks`。
- 未配置股票时的默认值: 600519 (茅台)、000001 (平安)、300750 (宁德时代)。
- 调度器 (`APScheduler`) 用于每日自动选股，默认关闭 (`SCHEDULE_ENABLED=false`)。导入失败非致命 — 应用可在无调度的情况下启动。
- Dockerfile 无 `init_db.py` 步骤 — 首次 `docker-compose up` 前需手动运行。
- `.env` 位于 **项目根目录** (距 `config.py` 上溯 3 级)，不在 `backend/` 中。
- `requirements.txt` 在项目根目录; Dockerfile/README 通过 `../requirements.txt` 从 `backend/` 引用。
- 技术架构文档: `.sisyphus/plans/technical-plan.md` (Momus 审查通过的 v2.0 架构)。
