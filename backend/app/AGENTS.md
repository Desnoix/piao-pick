# backend/app — FastAPI 应用

piao-pick 后端应用包。分层架构: API → Services → Repositories → Models。

## 结构

```
app/
├── main.py              # 应用工厂: create_app() + lifespan (调度器初始化/停止)
├── config.py            # 配置单例，从 .env 加载 (dataclass + get_config())
├── database.py          # DatabaseManager 单例 (SQLite + SQLModel)
├── logging_config.py    # 结构化日志配置
├── api/v1/              # REST 端点 (6 个路由: stocks, strategies, selection, backtest, data_status, history_sync)
├── core/                # 领域逻辑 → 详见 core/AGENTS.md
├── services/            # 编排层 (5 个服务)
├── repositories/        # 数据访问层 (6 个仓库: stock, factor, strategy, selection, backtest, history_sync)
├── models/              # SQLModel ORM (6 个模型 → 6 张表)
└── schemas/             # Pydantic 请求/响应校验
```

## 在哪里找什么

| 任务 | 位置 | 说明 |
|------|------|------|
| 新增端点 | `api/v1/` | 添加文件，在 `router.py` 中注册前缀+标签 |
| 新增业务逻辑 | `services/` | 编排 repos + core 模块 |
| 新增数据库查询 | `repositories/` | SQLModel 查询，每个领域一个 repo |
| Schema 变更 | `models/` + `schemas/` | SQLModel = ORM+Pydantic 合体 |
| 应用启动 | `main.py::app_lifespan` | 调度器初始化，关闭时清理 |
| CORS 配置 | `config.py::Config.cors_origins` | 逗号分隔，默认: localhost:5173,3000 |

## 约定

- **分层隔离**: API 路由解析请求 → 委托给 services → services 使用 repos 操作数据库 → repos 返回 ORM 模型或 DataFrame。
- **SQLModel 双重用途**: `models/` 中的模型同时作为 SQLAlchemy 表和 Pydantic schema。`schemas/` 中是 API 专用校验。
- **路由聚合**: `api/v1/router.py` 导入所有子路由并统一应用 `/api/v1` 前缀。
- **进度回调**: 长时间运行操作 (选股、回测) 接受可选 `progress_callback(percent, message)` 用于 SSE/流式传输。
- **DataFrame 返回**: 仓库 (Repository) 对批量数据常返回 `pd.DataFrame`，CRUD 操作返回 ORM 模型。
- **UUID 主键**: 策略 ID 使用 `uuid.uuid4()` 字符串格式。
- **时间戳格式**: ISO 8601 字符串 (`datetime.now().isoformat()`)。
- **文件头**: 每个 `.py` 文件以 `# -*- coding: utf-8 -*-` + docstring 开头。
- **Docstring 风格**: Google 风格 (`Args:`、`Returns:`)，非 NumPy/Sphinx。
- **模块级日志**: 每个模块使用 `logger = logging.getLogger(__name__)`。
- **延迟导入**: 重量级模块 (`akshare`、服务类) 在函数内部导入，避免循环引用 / 加快启动。
- **手动数据库会话**: Repo 中通过 `self.db.get_session()` 逐方法获取 — 无 FastAPI `Depends()` 注入。始终使用 `with self.db.get_session() as session:` 上下文管理器。

## 反模式

- 禁止在 `database.py` 模块顶层导入 ORM 模型 — 在 `_init_tables()` 中使用延迟导入以避免循环引用。
- 禁止在 API 路由中绕过 service 层 — 业务逻辑走 services，数据访问走 repos。
- 禁止从 API 路由返回原始 SQLAlchemy 对象 — 转为字典或 Pydantic schema。
- 因子计算属于 `core/factor/`，不在 services 或 repos 中。
- **已废弃**: selection API/pipeline 中的 `strategy_id` 参数 — 使用 `strategy_name` 替代。仅为向后兼容保留。
- `_is_bse_code()` 在 `core/strategy/executor.py` 和 `data_provider/base.py` 中重复实现，前缀逻辑略有差异 — 修改北交所检测时须统一。
