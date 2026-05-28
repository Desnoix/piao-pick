"""
过拟合防护服务

编排 Walk-Forward、Purged K-Fold、PBO、DSR 四大模块，
对外提供统一的过拟合检测接口。
"""

import logging
from datetime import date, datetime

from app.core.backtest.dsr import DSRResult, compute_dsr
from app.core.backtest.pbo import PBOCalculator, PBOConfig, PBOResult
from app.core.backtest.purged_kfold import (
    PurgedKFoldConfig,
    PurgedKFolder,
    PurgedKFoldResult,
)
from app.core.backtest.walk_forward import (
    WalkForwardConfig,
    WalkForwardEngine,
    WalkForwardResult,
)
from app.services.backtest_service import BacktestService

logger = logging.getLogger(__name__)


class OverfitService:
    """过拟合防护服务"""

    def __init__(self):
        self.backtest_service = BacktestService()

    def _make_backtest_fn(self):
        """创建回测回调函数"""
        svc = self.backtest_service

        def backtest_fn(strategy_name: str, start: str, end: str) -> dict:
            return svc.run_backtest(strategy_name, start, end)

        return backtest_fn

    def run_walk_forward(
        self,
        strategy_name: str,
        overall_start: str,
        overall_end: str,
        train_window_months: int = 36,
        test_window_months: int = 12,
        step_months: int = 12,
    ) -> dict:
        """
        执行 Walk-Forward 验证。

        Returns:
            dict with walk_forward results (serializable)
        """
        config = WalkForwardConfig(
            train_window_months=train_window_months,
            test_window_months=test_window_months,
            step_months=step_months,
        )
        engine = WalkForwardEngine(config)
        backtest_fn = self._make_backtest_fn()

        start_date = _parse_date(overall_start)
        end_date = _parse_date(overall_end)

        result = engine.run(strategy_name, start_date, end_date, backtest_fn)
        return _serialize_wf_result(result)

    def run_purged_kfold(
        self,
        strategy_name: str,
        overall_start: str,
        overall_end: str,
        n_splits: int = 5,
        embargo_months: int = 1,
    ) -> dict:
        """
        执行 Purged K-Fold 交叉验证。

        Returns:
            dict with purged kfold results (serializable)
        """
        config = PurgedKFoldConfig(n_splits=n_splits, embargo_months=embargo_months)
        folder = PurgedKFolder(config)
        backtest_fn = self._make_backtest_fn()

        start_date = _parse_date(overall_start)
        end_date = _parse_date(overall_end)

        result = folder.run(strategy_name, start_date, end_date, backtest_fn)
        return _serialize_pkf_result(result)

    def run_pbo(
        self,
        strategy_name: str,
        overall_start: str,
        overall_end: str,
        n_sub_periods: int = 16,
        parameter_variants: list[dict] | None = None,
    ) -> dict:
        """
        计算 PBO (过拟合概率)。

        Returns:
            dict with PBO results (serializable)
        """
        config = PBOConfig(n_sub_periods=n_sub_periods)
        calculator = PBOCalculator(config)
        backtest_fn = self._make_backtest_fn()

        start_date = _parse_date(overall_start)
        end_date = _parse_date(overall_end)

        result = calculator.compute(strategy_name, start_date, end_date, backtest_fn, parameter_variants)
        return _serialize_pbo_result(result)

    def run_dsr(
        self,
        observed_sharpe: float,
        n_trials: int,
        n_observation_years: float,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
    ) -> dict:
        """
        计算 DSR (校正夏普比率)。

        Returns:
            dict with DSR results (serializable)
        """
        result = compute_dsr(
            observed_sharpe=observed_sharpe,
            n_trials=n_trials,
            n_observation_years=n_observation_years,
            skewness=skewness,
            kurtosis=kurtosis,
        )
        return _serialize_dsr_result(result)

    def run_full_overfit_check(
        self,
        strategy_name: str,
        overall_start: str,
        overall_end: str,
        n_trials: int = 1,
        n_sub_periods: int = 8,
    ) -> dict:
        """
        运行完整的过拟合检测套件。

        依次执行 Walk-Forward + Purged K-Fold + PBO + DSR，
        返回综合报告。

        Args:
            strategy_name: 策略名称
            overall_start: 数据起始日期
            overall_end: 数据截止日期
            n_trials: 策略尝试次数 (用于 DSR)
            n_sub_periods: PBO 子区间数

        Returns:
            dict with all overfit check results
        """
        backtest_fn = self._make_backtest_fn()
        start_date = _parse_date(overall_start)
        end_date = _parse_date(overall_end)

        # Walk-Forward
        wf_config = WalkForwardConfig()
        wf_engine = WalkForwardEngine(wf_config)
        wf_result = wf_engine.run(strategy_name, start_date, end_date, backtest_fn)

        # Purged K-Fold
        pkf_config = PurgedKFoldConfig(n_splits=5)
        pkf_folder = PurgedKFolder(pkf_config)
        pkf_result = pkf_folder.run(strategy_name, start_date, end_date, backtest_fn)

        # PBO
        pbo_config = PBOConfig(n_sub_periods=n_sub_periods)
        pbo_calc = PBOCalculator(pbo_config)
        pbo_result = pbo_calc.compute(strategy_name, start_date, end_date, backtest_fn)

        # DSR
        # 先跑一次全量回测获取 Sharpe
        full_result = self.backtest_service.run_backtest(strategy_name, overall_start, overall_end)
        full_sharpe = full_result.get("metrics", {}).get("sharpe_ratio", 0.0)
        total_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        years = total_months / 12.0

        # 从 returns 计算偏度和峰度
        returns = full_result.get("returns", [])
        if len(returns) > 3:
            import scipy.stats as sp_stats

            skew = float(sp_stats.skew(returns))
            kurt = float(sp_stats.kurtosis(returns)) + 3.0  # scipy 返回 excess kurtosis
        else:
            skew, kurt = 0.0, 3.0

        dsr_result = compute_dsr(
            observed_sharpe=full_sharpe,
            n_trials=n_trials,
            n_observation_years=years,
            skewness=skew,
            kurtosis=kurt,
        )

        # 综合评分
        overfit_score = _compute_overfit_score(wf_result, pkf_result, pbo_result, dsr_result)

        return {
            "strategy_name": strategy_name,
            "overall_start": overall_start,
            "overall_end": overall_end,
            "walk_forward": _serialize_wf_result(wf_result),
            "purged_kfold": _serialize_pkf_result(pkf_result),
            "pbo": _serialize_pbo_result(pbo_result),
            "dsr": _serialize_dsr_result(dsr_result),
            "overfit_score": overfit_score,
            "verdict": _verdict(overfit_score),
        }


def _compute_overfit_score(
    wf: WalkForwardResult,
    pkf: PurgedKFoldResult,
    pbo: PBOResult,
    dsr: DSRResult,
) -> dict:
    """
    综合评分。将四个维度的信号汇总为一个 0-100 的过拟合风险分数。

    评分规则:
    - Walk-Forward: OOS/IS Sharpe 比值 < 0.5 → 高风险
    - Purged K-Fold: CV Sharpe 标准差大 → 不稳定
    - PBO: > 0.5 → 高风险
    - DSR: 不显著 → 高风险

    Returns:
        dict with score (0-100, 越高越危险) and details
    """
    risks: list[float] = []

    # Walk-Forward 风险
    if wf.is_sharpe_mean > 0:
        wf_risk = max(0.0, 1.0 - wf.oos_is_ratio)
    else:
        wf_risk = 1.0 if wf.folds else 0.0
    risks.append(wf_risk)

    # PBO 风险
    risks.append(pbo.pbo)

    # DSR 风险 (不显著 → 1.0, 显著 → 0.0)
    dsr_risk = 0.0 if dsr.is_significant else 1.0
    risks.append(dsr_risk)

    # K-Fold 变异系数风险
    if pkf.cv_sharpe != 0:
        cv_risk = min(1.0, pkf.cv_sharpe_std / abs(pkf.cv_sharpe))
    else:
        cv_risk = 1.0 if pkf.folds else 0.0
    risks.append(cv_risk)

    score = sum(risks) / len(risks) * 100.0

    return {
        "score": round(score, 1),
        "wf_risk": round(wf_risk, 3),
        "pbo_risk": round(pbo.pbo, 3),
        "dsr_risk": round(dsr_risk, 3),
        "cv_risk": round(cv_risk, 3),
    }


def _verdict(overfit_score: dict) -> str:
    """根据综合评分给出结论"""
    s = overfit_score["score"]
    if s >= 75:
        return "高风险: 策略很可能过拟合，不建议实盘使用"
    elif s >= 50:
        return "中风险: 存在过拟合迹象，需要更多样本外验证"
    elif s >= 25:
        return "低风险: 策略表现出较好的样本外稳健性"
    else:
        return "可靠: 多项检验均通过，过拟合风险较低"


def _parse_date(value) -> date:
    """解析日期"""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.fromisoformat(value).date()
    raise TypeError(f"Cannot parse date from {type(value)}: {value}")


def _serialize_wf_result(r: WalkForwardResult) -> dict:
    """序列化 WalkForwardResult"""
    return {
        "config": {
            "train_window_months": r.config.train_window_months,
            "test_window_months": r.config.test_window_months,
            "step_months": r.config.step_months,
        },
        "n_folds": len(r.folds),
        "folds": [
            {
                "train_start": f.window.train_start.isoformat(),
                "train_end": f.window.train_end.isoformat(),
                "test_start": f.window.test_start.isoformat(),
                "test_end": f.window.test_end.isoformat(),
                "train_sharpe": f.train_sharpe,
                "test_sharpe": f.test_sharpe,
                "train_annual_return": f.train_annual_return,
                "test_annual_return": f.test_annual_return,
                "train_max_drawdown": f.train_max_drawdown,
                "test_max_drawdown": f.test_max_drawdown,
            }
            for f in r.folds
        ],
        "is_sharpe_mean": r.is_sharpe_mean,
        "oos_sharpe_mean": r.oos_sharpe_mean,
        "oos_is_ratio": r.oos_is_ratio,
    }


def _serialize_pkf_result(r: PurgedKFoldResult) -> dict:
    """序列化 PurgedKFoldResult"""
    return {
        "config": {
            "n_splits": r.config.n_splits,
            "embargo_months": r.config.embargo_months,
        },
        "n_folds": len(r.folds),
        "folds": [
            {
                "fold_index": f.fold.fold_index,
                "train_start": f.fold.train_start.isoformat(),
                "train_end": f.fold.train_end.isoformat(),
                "test_start": f.fold.test_start.isoformat(),
                "test_end": f.fold.test_end.isoformat(),
                "train_sharpe": f.train_sharpe,
                "test_sharpe": f.test_sharpe,
            }
            for f in r.folds
        ],
        "cv_sharpe": r.cv_sharpe,
        "cv_sharpe_std": r.cv_sharpe_std,
        "mean_train_sharpe": r.mean_train_sharpe,
    }


def _serialize_pbo_result(r: PBOResult) -> dict:
    """序列化 PBOResult"""
    return {
        "pbo": r.pbo,
        "is_sharpe_mean": r.is_sharpe_mean,
        "oos_sharpe_mean": r.oos_sharpe_mean,
        "oos_sharpe_std": r.oos_sharpe_std,
        "n_combinations": r.n_combinations,
        "interpretation": r.pbo_interpretation,
    }


def _serialize_dsr_result(r: DSRResult) -> dict:
    """序列化 DSRResult"""
    return {
        "dsr": r.dsr,
        "expected_max_sharpe": r.expected_max_sharpe,
        "sharpe_std_error": r.sharpe_std_error,
        "p_value": r.p_value,
        "deflated_p_value": r.deflated_p_value,
        "n_trials": r.n_trials,
        "observed_sharpe": r.observed_sharpe,
        "is_significant": r.is_significant,
        "interpretation": r.interpretation,
    }
