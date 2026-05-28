"""
Walk-Forward 验证引擎

实现滚动窗口回测，输出 in-sample 与 out-of-sample 收益序列对比。
参数:
  train_window: 训练窗口长度（月）
  test_window: 测试窗口长度（月）
  step: 滑动步长（月）
"""

import calendar
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardWindow:
    """单个 Walk-Forward 窗口的定义"""

    train_start: date
    train_end: date
    test_start: date
    test_end: date


@dataclass
class WalkForwardFoldResult:
    """单个 Walk-Forward 折的结果"""

    window: WalkForwardWindow
    train_sharpe: float
    test_sharpe: float
    train_annual_return: float
    test_annual_return: float
    train_max_drawdown: float
    test_max_drawdown: float
    test_returns: list[float] = field(default_factory=list)
    test_nav: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class WalkForwardConfig:
    """Walk-Forward 配置"""

    train_window_months: int = 36  # 训练窗口: 36 个月 (3 年)
    test_window_months: int = 12  # 测试窗口: 12 个月 (1 年)
    step_months: int = 12  # 滑动步长: 12 个月 (1 年)
    min_train_months: int = 24  # 最小训练窗口: 24 个月


@dataclass
class WalkForwardResult:
    """Walk-Forward 完整结果"""

    config: WalkForwardConfig
    folds: list[WalkForwardFoldResult]
    oos_nav: list[tuple[str, float]]  # 拼接所有 OOS 段的净值
    oos_returns: list[float]  # 所有 OOS 月度收益
    is_sharpe_mean: float  # IS Sharpe 均值
    oos_sharpe_mean: float  # OOS Sharpe 均值
    oos_is_ratio: float  # OOS/IS Sharpe 比值


class WalkForwardEngine:
    """Walk-Forward 验证引擎"""

    def __init__(self, config: WalkForwardConfig | None = None):
        self.config = config or WalkForwardConfig()

    def generate_windows(
        self,
        overall_start: date,
        overall_end: date,
    ) -> list[WalkForwardWindow]:
        """
        根据总区间和配置参数，生成所有 Walk-Forward 窗口。

        Args:
            overall_start: 数据总起始日期
            overall_end: 数据总截止日期

        Returns:
            WalkForwardWindow 列表，按时间顺序排列
        """
        windows: list[WalkForwardWindow] = []
        cfg = self.config

        cursor = _add_months(overall_start, cfg.train_window_months)

        while True:
            train_start = _add_months(cursor, -cfg.train_window_months)
            train_end = cursor
            test_start = cursor
            test_end = _add_months(cursor, cfg.test_window_months)

            if test_end > overall_end:
                break

            actual_train_months = _months_between(train_start, train_end)
            if actual_train_months < cfg.min_train_months:
                cursor = _add_months(cursor, cfg.step_months)
                continue

            windows.append(
                WalkForwardWindow(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )

            cursor = _add_months(cursor, cfg.step_months)

        logger.info(
            f"WalkForward: generated {len(windows)} windows "
            f"(train={cfg.train_window_months}m, test={cfg.test_window_months}m, "
            f"step={cfg.step_months}m)"
        )
        return windows

    def run(
        self,
        strategy_name: str,
        overall_start: date,
        overall_end: date,
        run_backtest_fn: Callable[[str, str, str], dict],
    ) -> WalkForwardResult:
        """
        执行 Walk-Forward 验证。

        Args:
            strategy_name: 策略名称
            overall_start: 数据总起始日期
            overall_end: 数据总截止日期
            run_backtest_fn: callable(strategy_name, start_date, end_date) -> dict
                返回与 BacktestService.run_backtest() 相同格式的字典

        Returns:
            WalkForwardResult 包含所有折的结果和汇总统计
        """
        windows = self.generate_windows(overall_start, overall_end)

        if not windows:
            logger.warning("WalkForward: no valid windows generated")
            return WalkForwardResult(
                config=self.config,
                folds=[],
                oos_nav=[],
                oos_returns=[],
                is_sharpe_mean=0.0,
                oos_sharpe_mean=0.0,
                oos_is_ratio=0.0,
            )

        folds: list[WalkForwardFoldResult] = []
        all_oos_returns: list[float] = []
        all_oos_nav: list[tuple[str, float]] = []

        for i, window in enumerate(windows):
            logger.info(
                f"WalkForward fold {i + 1}/{len(windows)}: "
                f"train[{window.train_start} ~ {window.train_end}] "
                f"test[{window.test_start} ~ {window.test_end}]"
            )

            # In-sample 回测
            train_result = run_backtest_fn(
                strategy_name,
                window.train_start.isoformat(),
                window.train_end.isoformat(),
            )
            train_metrics = train_result.get("metrics", {})

            # Out-of-sample 回测
            test_result = run_backtest_fn(
                strategy_name,
                window.test_start.isoformat(),
                window.test_end.isoformat(),
            )
            test_metrics = test_result.get("metrics", {})
            test_returns = test_result.get("returns", [])
            test_nav = test_result.get("nav_series", [])

            fold = WalkForwardFoldResult(
                window=window,
                train_sharpe=train_metrics.get("sharpe_ratio", 0.0),
                test_sharpe=test_metrics.get("sharpe_ratio", 0.0),
                train_annual_return=train_metrics.get("annual_return", 0.0),
                test_annual_return=test_metrics.get("annual_return", 0.0),
                train_max_drawdown=train_metrics.get("max_drawdown", 0.0),
                test_max_drawdown=test_metrics.get("max_drawdown", 0.0),
                test_returns=test_returns,
                test_nav=test_nav,
            )
            folds.append(fold)
            all_oos_returns.extend(test_returns)
            all_oos_nav.extend(test_nav)

        # 汇总统计
        is_sharpes = [f.train_sharpe for f in folds]
        oos_sharpes = [f.test_sharpe for f in folds]
        is_mean = float(np.mean(is_sharpes)) if is_sharpes else 0.0
        oos_mean = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
        ratio = oos_mean / is_mean if is_mean != 0 else 0.0

        return WalkForwardResult(
            config=self.config,
            folds=folds,
            oos_nav=all_oos_nav,
            oos_returns=all_oos_returns,
            is_sharpe_mean=round(is_mean, 3),
            oos_sharpe_mean=round(oos_mean, 3),
            oos_is_ratio=round(ratio, 3),
        )


def _add_months(d: date, months: int) -> date:
    """日期加减月份"""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _months_between(d1: date, d2: date) -> int:
    """计算两个日期之间的月数差"""
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)
