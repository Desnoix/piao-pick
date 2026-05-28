"""
回测 API 端点

- POST /run              运行回测
- GET  /available-dates  获取可用日期范围
- GET  /{strategy_name}  获取策略最近回测结果 (stub)
"""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# -- Request / Response schemas --


class BacktestRunRequest(BaseModel):
    strategy_id: str
    start_date: str
    end_date: str
    initial_capital: float = 1000000.0
    commission_rate: float = 0.0003  # 单边佣金 (万三)
    stamp_tax: float = 0.0005  # 卖出印花税 (万五, 2023-08-28 减半后)
    slippage: float = 0.001  # 单边滑点 (千一)


class BacktestRunResponse(BaseModel):
    strategy_name: str
    start_date: str
    end_date: str
    period: dict
    metrics: dict
    nav_series: list
    benchmark_nav: list | None = None  # [(date, nav)] 归一化后的基准净值
    returns: list
    turnover_history: list


class AvailableDatesResponse(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    trade_date_count: int = 0


# -- Endpoints --


@router.post("/run", summary="运行回测", response_model=BacktestRunResponse)
async def run_backtest(req: BacktestRunRequest):
    """
    运行月度调仓回测。

    使用 BacktestService 执行完整的回测流程：
    1. 获取交易日历
    2. 按月调仓选股
    3. 计算等权持仓收益
    4. 计算风险指标 (Sharpe, MaxDD, Calmar, etc.)
    """
    from app.services.backtest_service import BacktestService

    try:
        service = BacktestService()
        result = service.run_backtest(
            strategy_name=req.strategy_id,
            start_date=req.start_date,
            end_date=req.end_date,
            commission_rate=req.commission_rate,
            stamp_tax=req.stamp_tax,
            slippage=req.slippage,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Backtest failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backtest execution error: {e}")


@router.get("/available-dates", summary="获取可用回测日期范围", response_model=AvailableDatesResponse)
async def get_available_dates():
    """
    返回行情数据中可用的日期范围。

    用于前端回测表单的日期选择器限制。
    """
    from app.services.backtest_service import BacktestService

    try:
        service = BacktestService()
        return service.get_available_dates()
    except Exception as e:
        logger.exception(f"Failed to get available dates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results", summary="获取回测结果列表")
async def list_backtest_results(
    strategy_id: str | None = Query(None, description="策略 ID"),
):
    """获取历史回测结果列表"""
    from app.database import get_db
    from app.repositories import BacktestRepository

    repo = BacktestRepository(get_db())
    results = repo.list_backtests(strategy_id=strategy_id)
    return results


@router.get("/{strategy_name}", summary="获取策略最近回测结果")
async def get_last_backtest(strategy_name: str):
    """
    获取某策略最近一次回测结果 (stub)。

    当前返回空结果，未来可从 BacktestRepository 查询持久化的回测记录。
    """
    from app.database import get_db
    from app.repositories import BacktestRepository

    repo = BacktestRepository(get_db())
    results = repo.list_backtests(strategy_id=strategy_name)

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No backtest results found for strategy: {strategy_name}",
        )

    return results[-1]


# -- Overfitting Detection Endpoints --


class OverfitCheckRequest(BaseModel):
    strategy_name: str
    overall_start: str
    overall_end: str
    n_trials: int = 1
    n_sub_periods: int = 8


class WalkForwardRequest(BaseModel):
    strategy_name: str
    overall_start: str
    overall_end: str
    train_window_months: int = 36
    test_window_months: int = 12
    step_months: int = 12


class PurgedKFoldRequest(BaseModel):
    strategy_name: str
    overall_start: str
    overall_end: str
    n_splits: int = 5
    embargo_months: int = 1


class PBORequest(BaseModel):
    strategy_name: str
    overall_start: str
    overall_end: str
    n_sub_periods: int = 8


class DSRRequest(BaseModel):
    observed_sharpe: float
    n_trials: int
    n_observation_years: float
    skewness: float = 0.0
    kurtosis: float = 3.0


@router.post("/walk-forward", summary="执行 Walk-Forward 验证")
async def run_walk_forward(req: WalkForwardRequest):
    """执行 Walk-Forward 滚动窗口验证，输出 IS/OOS Sharpe 对比"""
    from app.services.overfit_service import OverfitService

    try:
        svc = OverfitService()
        result = svc.run_walk_forward(
            req.strategy_name,
            req.overall_start,
            req.overall_end,
            req.train_window_months,
            req.test_window_months,
            req.step_months,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Walk-forward failed: {e}")
        raise HTTPException(status_code=500, detail=f"Walk-forward error: {e}")


@router.post("/purged-kfold", summary="执行 Purged K-Fold 交叉验证")
async def run_purged_kfold(req: PurgedKFoldRequest):
    """执行 Purged K-Fold 交叉验证（含 embargo 期隔离）"""
    from app.services.overfit_service import OverfitService

    try:
        svc = OverfitService()
        result = svc.run_purged_kfold(
            req.strategy_name,
            req.overall_start,
            req.overall_end,
            req.n_splits,
            req.embargo_months,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Purged K-Fold failed: {e}")
        raise HTTPException(status_code=500, detail=f"Purged K-Fold error: {e}")


@router.post("/pbo", summary="计算 PBO 过拟合概率")
async def run_pbo(req: PBORequest):
    """计算 PBO (Probability of Backtest Overfitting)"""
    from app.services.overfit_service import OverfitService

    try:
        svc = OverfitService()
        result = svc.run_pbo(
            req.strategy_name,
            req.overall_start,
            req.overall_end,
            req.n_sub_periods,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"PBO computation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PBO error: {e}")


@router.post("/dsr", summary="计算 DSR 校正夏普比率")
async def run_dsr(req: DSRRequest):
    """计算 DSR (Deflated Sharpe Ratio)，校正多重检验偏差"""
    from app.services.overfit_service import OverfitService

    try:
        svc = OverfitService()
        result = svc.run_dsr(
            req.observed_sharpe,
            req.n_trials,
            req.n_observation_years,
            req.skewness,
            req.kurtosis,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"DSR computation failed: {e}")
        raise HTTPException(status_code=500, detail=f"DSR error: {e}")


@router.post("/overfit-check", summary="运行完整过拟合检测套件")
async def run_overfit_check(req: OverfitCheckRequest):
    """
    运行完整过拟合检测套件。
    包含 Walk-Forward + Purged K-Fold + PBO + DSR，
    输出综合评分和结论。
    """
    from app.services.overfit_service import OverfitService

    try:
        svc = OverfitService()
        result = svc.run_full_overfit_check(
            req.strategy_name,
            req.overall_start,
            req.overall_end,
            req.n_trials,
            req.n_sub_periods,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Overfit check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Overfit check error: {e}")
