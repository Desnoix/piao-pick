"""
Purged K-Fold 交叉验证

de Prado (2018) 提出的方法。在训练集和测试集的边界处剔除 embargo period 的样本，
防止时间序列中的信息泄漏。

对于月度调仓策略，embargo period 通常设为 1 个月（即一个持仓周期）。
"""

import calendar
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PurgedFold:
    """单个 Purged K-Fold 折"""

    fold_index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    embargo_start: date  # 剔除区间起点 (train_end + 1 天)
    embargo_end: date  # 剔除区间终点 (test_start 或 train 侧)


@dataclass
class PurgedFoldResult:
    """单个 Purged Fold 的结果"""

    fold: PurgedFold
    train_sharpe: float
    test_sharpe: float
    train_annual_return: float
    test_annual_return: float
    test_returns: list[float] = field(default_factory=list)


@dataclass
class PurgedKFoldConfig:
    """Purged K-Fold 配置"""

    n_splits: int = 5  # K 折数
    embargo_months: int = 1  # Embargo 期长度（月）
    purge_mode: str = "boundary"  # "boundary" 剔除训练/测试边界; "full" 剔除整个测试期前后


@dataclass
class PurgedKFoldResult:
    """Purged K-Fold 完整结果"""

    config: PurgedKFoldConfig
    folds: list[PurgedFoldResult]
    mean_train_sharpe: float
    mean_test_sharpe: float
    std_test_sharpe: float
    cv_sharpe: float  # 交叉验证 Sharpe (test 均值)
    cv_sharpe_std: float  # 交叉验证 Sharpe 标准差


class PurgedKFolder:
    """Purged K-Fold 交叉验证器"""

    def __init__(self, config: PurgedKFoldConfig | None = None):
        self.config = config or PurgedKFoldConfig()

    def generate_folds(
        self,
        overall_start: date,
        overall_end: date,
    ) -> list[PurgedFold]:
        """
        生成 Purged K-Fold 的时间窗口划分。

        与标准 K-Fold 的区别：
        1. 按时间顺序等分（不随机打乱）
        2. 在相邻折的边界处插入 embargo period

        Args:
            overall_start: 总起始日期
            overall_end: 总截止日期

        Returns:
            PurgedFold 列表
        """
        K = self.config.n_splits
        embargo = self.config.embargo_months

        # 将总区间按月等分为 K 段
        total_months = _months_between(overall_start, overall_end)
        if total_months < K * 2:
            logger.warning(f"PurgedKFolder: total_months={total_months} too small for K={K}")
            return []

        segment_months = total_months // K
        boundaries: list[date] = [overall_start]
        for i in range(1, K):
            boundaries.append(_add_months(overall_start, segment_months * i))
        boundaries.append(overall_end)

        folds: list[PurgedFold] = []

        for k in range(K):
            test_start = boundaries[k]
            test_end = boundaries[k + 1]

            # 训练集: 其他所有段
            # 对于第一段: 训练集 = [test_end + embargo, overall_end] 不可行
            # Purged K-Fold 中，每个 test fold 对应一个互补的 train set
            # 但需要剔除 test fold 前后的 embargo
            if k == 0:
                # 第一折做测试集，剩余做训练集
                train_start = boundaries[1]  # test_end 之后
                # 加入 embargo
                train_start = _add_months(train_start, embargo)
                train_end = overall_end
            elif k == K - 1:
                # 最后一折做测试集
                train_start = overall_start
                train_end = _add_months(test_start, -embargo)
            else:
                # 中间折: 训练集为前后两段拼接
                # 此处简化为取前段 (overall_start ~ test_start - embargo)
                train_start = overall_start
                train_end = _add_months(test_start, -embargo)

            embargo_start = test_start
            embargo_end_date = _add_months(test_start, -embargo) if embargo > 0 else test_start

            if train_end <= train_start:
                logger.warning(f"PurgedKFolder fold {k}: train_end <= train_start after embargo, skipping")
                continue

            folds.append(
                PurgedFold(
                    fold_index=k,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    embargo_start=embargo_end_date,
                    embargo_end=embargo_start,
                )
            )

        logger.info(f"PurgedKFolder: generated {len(folds)} folds (K={K}, embargo={embargo}m)")
        return folds

    def run(
        self,
        strategy_name: str,
        overall_start: date,
        overall_end: date,
        run_backtest_fn: Callable[[str, str, str], dict],
    ) -> PurgedKFoldResult:
        """
        执行 Purged K-Fold 交叉验证。

        Args:
            strategy_name: 策略名称
            overall_start: 数据总起始日期
            overall_end: 数据总截止日期
            run_backtest_fn: callable(strategy_name, start_date, end_date) -> dict

        Returns:
            PurgedKFoldResult
        """
        folds = self.generate_folds(overall_start, overall_end)

        if not folds:
            return PurgedKFoldResult(
                config=self.config,
                folds=[],
                mean_train_sharpe=0.0,
                mean_test_sharpe=0.0,
                std_test_sharpe=0.0,
                cv_sharpe=0.0,
                cv_sharpe_std=0.0,
            )

        results: list[PurgedFoldResult] = []

        for pf in folds:
            logger.info(
                f"PurgedKFolder fold {pf.fold_index}: "
                f"train[{pf.train_start} ~ {pf.train_end}] "
                f"test[{pf.test_start} ~ {pf.test_end}] "
                f"embargo[{pf.embargo_start} ~ {pf.embargo_end}]"
            )

            train_result = run_backtest_fn(
                strategy_name,
                pf.train_start.isoformat(),
                pf.train_end.isoformat(),
            )
            test_result = run_backtest_fn(
                strategy_name,
                pf.test_start.isoformat(),
                pf.test_end.isoformat(),
            )

            train_metrics = train_result.get("metrics", {})
            test_metrics = test_result.get("metrics", {})

            results.append(
                PurgedFoldResult(
                    fold=pf,
                    train_sharpe=train_metrics.get("sharpe_ratio", 0.0),
                    test_sharpe=test_metrics.get("sharpe_ratio", 0.0),
                    train_annual_return=train_metrics.get("annual_return", 0.0),
                    test_annual_return=test_metrics.get("annual_return", 0.0),
                    test_returns=test_result.get("returns", []),
                )
            )

        train_sharpes = [r.train_sharpe for r in results]
        test_sharpes = [r.test_sharpe for r in results]

        return PurgedKFoldResult(
            config=self.config,
            folds=results,
            mean_train_sharpe=round(float(np.mean(train_sharpes)), 3) if train_sharpes else 0.0,
            mean_test_sharpe=round(float(np.mean(test_sharpes)), 3) if test_sharpes else 0.0,
            std_test_sharpe=round(float(np.std(test_sharpes)), 3) if test_sharpes else 0.0,
            cv_sharpe=round(float(np.mean(test_sharpes)), 3) if test_sharpes else 0.0,
            cv_sharpe_std=round(float(np.std(test_sharpes)), 3) if test_sharpes else 0.0,
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
