"""
FastAPI 应用工厂

创建和配置 FastAPI 应用实例，包含 CORS、路由注册、健康检查。
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """应用生命周期管理：启动/停止时执行的初始化/清理逻辑"""
    # 启动时：初始化调度器
    try:
        from app.core.scheduler import SelectionScheduler

        scheduler = SelectionScheduler()
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Scheduler initialized")
    except Exception as e:
        logger.warning(f"Scheduler initialization failed (non-fatal): {e}")
        app.state.scheduler = None

    yield

    # 关闭时：停止调度器
    if hasattr(app.state, "scheduler") and app.state.scheduler:
        app.state.scheduler.stop()
        logger.info("Scheduler stopped")


def create_app(static_dir: Path | None = None) -> FastAPI:
    """
    创建并配置 FastAPI 应用实例。

    Args:
        static_dir: 静态文件目录路径（可选，用于托管前端构建产物）

    Returns:
        配置完成的 FastAPI 应用实例
    """
    config = get_config()

    app = FastAPI(
        title="Piao Pick API",
        description=(
            "A股量化选股系统 API\n\n"
            "## 功能模块\n"
            "- 股票数据：获取行情、因子数据\n"
            "- 策略管理：CRUD 多因子策略\n"
            "- 选股引擎：运行选股、查看结果\n"
            "- 回测系统：策略回测（Phase 4）\n"
            "- 数据同步：手动/自动数据同步"
        ),
        version="1.0.0",
        lifespan=app_lifespan,
    )

    # ============================================================
    # CORS
    # ============================================================
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ============================================================
    # API v1 路由
    # ============================================================
    from app.api.v1 import router as api_v1_router

    app.include_router(api_v1_router)

    # ============================================================
    # 健康检查
    # ============================================================
    @app.get("/api/health", tags=["Health"], summary="健康检查")
    async def health_check():
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
        }

    # ============================================================
    # 静态文件托管（前端 SPA, Phase 3）
    # ============================================================
    if static_dir is None:
        static_dir = Path(__file__).parent.parent / "static"

    if static_dir.exists() and (static_dir / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            """SPA 路由回退：非 API 路由返回 index.html"""
            if full_path == "api" or full_path.startswith("api/"):
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": "not_found",
                        "message": f"API endpoint /{full_path} not found",
                    },
                )
            from fastapi.responses import FileResponse

            return FileResponse(static_dir / "index.html")

    return app


# 默认应用实例（供 uvicorn 直接使用）
app = create_app()
