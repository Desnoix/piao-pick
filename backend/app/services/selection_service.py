# -*- coding: utf-8 -*-
"""
选股服务

提供面向 API 的选股运行接口。
包装 SelectionPipeline，处理参数默认值、错误处理。
"""

import logging
from typing import Optional

from app.core.pipeline import SelectionPipeline
from app.core.trading_calendar import get_effective_trading_date

logger = logging.getLogger(__name__)


class SelectionService:
    """选股服务 - API 层的选股运行入口"""

    def __init__(self):
        self.pipeline = SelectionPipeline()

    def run_selection(
        self,
        strategy_name: str,
        trade_date: Optional[str] = None,
    ) -> dict:
        """
        运行选股。

        Args:
            strategy_name: 策略名称（对应 YAML 文件名）
            trade_date: 交易日期 YYYY-MM-DD，默认使用最新有效交易日

        Returns:
            选股结果 dict
        """
        if trade_date is None:
            trade_date = get_effective_trading_date().isoformat()
            logger.info(f"Using effective trading date: {trade_date}")

        return self.pipeline.run(strategy_name=strategy_name, trade_date=trade_date)
