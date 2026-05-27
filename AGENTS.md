# PROJECT KNOWLEDGE BASE

**Generated:** 2026-05-27
**Project:** piao-pick (飘票选股系统)

## OVERVIEW

A股多因子量化选股系统 — screens 5000+ A-share stocks via configurable multi-factor strategies, runs backtests, and visualizes results. Python 3.11+/FastAPI backend + Vue 3/TypeScript frontend, SQLite storage, Docker Compose deploy.

## STRUCTURE

```
piao-pick/
├── backend/                 # FastAPI app + data providers + strategies
│   ├── app/                 # Application package → see backend/app/AGENTS.md
│   ├── data_provider/       # Pluggable market data sources (Strategy pattern + auto-failover)
│   ├── strategies/          # YAML strategy definitions (value_lowvol, momentum_growth)
│   ├── scripts/             # DB init + migrations (init_db.py is idempotent)
│   └── tests/               # E2E + integration tests (no unit test framework configured)
├── frontend/                # Vue 3 SPA
│   └── src/                 # → see frontend/src/AGENTS.md
├── .sisyphus/plans/         # Architecture docs (technical-plan.md = v2.0 spec)
├── docker-compose.yml       # Backend only (port 8000)
├── pyproject.toml           # Python build config
└── requirements.txt         # Pinned backend deps
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add API endpoint | `backend/app/api/v1/` | Register in `router.py` with prefix |
| New factor | `backend/app/core/factor/` | One file per category (value,growth,momentum,quality,size) |
| New strategy | `backend/strategies/*.yaml` | YAML-only, no code changes needed |
| New page | `frontend/src/pages/` | Add route in `router/index.ts` |
| New chart | `frontend/src/components/charts/` | ECharts via vue-echarts |
| Change data source | `backend/data_provider/` | Subclass BaseFetcher, set priority |
| DB schema change | `backend/scripts/` | New migration file + re-run init_db.py |
| Config change | `backend/app/config.py` | Singleton from `.env` — see `.env.example` |

## CONVENTIONS

- **Bilingual docs**: All modules have English+Chinese docstrings. Comments mix Chinese and English.
- **Singleton pattern**: `Config` and `DatabaseManager` use `get_instance()` / `get_config()` / `get_db()` — never instantiate directly.
- **Repository pattern**: API → Services → Repositories → Models. Services orchestrate, repos do SQL.
- **Strategy pattern**: `DataFetcherManager` manages prioritized fetchers with automatic failover (AkshareFetcher P0 → TushareFetcher P1).
- **Factor pipeline**: Winsorize(±3σ) → fillna(mean) → Z-Score → direction align → weighted composite [0-100].
- **YAML-driven strategies**: All strategy config in `backend/strategies/*.yaml`. Schema: universe → factors → filters → output.
- **A-share coloring**: 红涨绿跌 (red=up, green=down) — opposite of Western convention.
- **Future-data prevention**: All strategy/backtest code uses `trade_date` as data cutoff. Financial factors use "data availability date" concept.
- **API prefix**: All endpoints under `/api/v1/`. Health check at `/api/health`.
- **Frontend proxy**: Vite proxies `/api` → `localhost:8000`. SPA fallback serves `index.html` for non-API routes.

## ANTI-PATTERNS (THIS PROJECT)

- Do NOT instantiate `Config()` or `DatabaseManager()` directly — use `get_config()` / `get_db()`.
- Do NOT use raw exchange-prefixed stock codes (SH600519, 000001.SZ) — always call `normalize_stock_code()` first. Stripping prefixes is centralized in `data_provider/base.py`.
- Do NOT use factor data beyond `trade_date` cutoff — this is look-ahead bias and invalidates backtests.
- Do NOT add strategy logic in Python — use YAML configuration in `backend/strategies/`.
- Do NOT skip `init_db.py` after schema changes — it applies migrations and is idempotent.

## COMMANDS

```bash
# Backend
cd backend && uvicorn app.main:app --reload    # Dev server :8000
cd backend && python scripts/init_db.py        # Init/migrate DB (idempotent)
pip install -r ../requirements.txt             # Install deps

# Frontend
cd frontend && npm run dev                     # Dev server :5173
cd frontend && npm run build                   # Production build
cd frontend && npm install                     # Install deps

# Docker
docker-compose up                              # Backend only (port 8000)
```

## NOTES

- SQLite single-file DB (`data/piao_pick.db`) — sufficient for 5-year data volume (<10M rows). PostgreSQL migration path: 90% SQL compatible.
- 6 DB tables: `stock_info`, `kline_daily`, `factor_daily`, `strategies`, `selection_results`, `history_sync_tasks`.
- Default stocks if none configured: 600519 (Moutai), 000001 (Ping An), 300750 (CATL).
- Scheduler (`APScheduler`) for daily auto-selection, disabled by default (`SCHEDULE_ENABLED=false`).
- Design docs at `.sisyphus/plans/technical-plan.md` (Momus-reviewed v2.0 architecture).
