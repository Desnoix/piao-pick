"""
清理快照路径产生的错误时序因子，从 K 线重新计算。

问题背景:
  data_preparation.py 的快照路径使用错误公式计算 ret_60d_vol 和 ret_20d:
  - ret_60d_vol 用 (high - low) / pre_close (日振幅)，而非 60 日年化波动率
  - ret_20d 用 ret_60d / 3.0 (线性近似)，而非 pct_change(20)
  导致数值偏差 10 倍以上，污染 factor_daily 表。

修复方案:
  1. 找出所有 ret_60d_vol < 0.08 的错误记录 (正确年化波动率通常 > 0.15)
  2. 清除错误的时序因子值 (ret_60d_vol, ret_20d, turnover_20d)
  3. 从 K 线数据重新计算时序因子

使用方法:
  cd backend && python scripts/migrate_fix_snapshot_factors.py
"""

import logging
import os
import sys

# 确保可以导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlmodel import select

from app.database import get_db
from app.models.factor import Factor
from app.services.factor_compute_service import FactorComputeService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """执行迁移修复"""
    db = get_db()

    # Step 1: 找出错误记录: ret_60d_vol < 0.08 (日振幅范围)
    # 正确年化波动率通常 > 0.15
    with db.get_session() as session:
        bad_records = session.exec(
            select(Factor).where(
                Factor.ret_60d_vol.isnot(None),
                Factor.ret_60d_vol < 0.08,
            )
        ).all()

    logger.info(f"发现 {len(bad_records)} 条错误的 ret_60d_vol 记录")
    if not bad_records:
        logger.info("无需迁移")
        return

    # Step 2: 将错误时序因子置为 None (保留截面因子)
    cleared = 0
    with db.get_session() as session:
        for record in bad_records:
            record.ret_60d_vol = None
            record.ret_20d = None
            record.turnover_20d = None
            session.add(record)
            cleared += 1
        session.commit()
    logger.info(f"已清除 {cleared} 条错误的时序因子值")

    # Step 3: 从 K 线数据重新计算时序因子
    logger.info("开始从 K 线数据重新计算时序因子...")
    factor_service = FactorComputeService()
    result = factor_service.compute_factors_for_all_stocks()
    logger.info(f"时序因子重算完成: {result['computed']} 成功, {result['failed']} 失败")

    # Step 4: 验证是否还有异常低的 ret_60d_vol
    with db.get_session() as session:
        still_bad = session.exec(
            select(Factor).where(
                Factor.ret_60d_vol.isnot(None),
                Factor.ret_60d_vol < 0.08,
            )
        ).all()
    if still_bad:
        logger.warning(f"仍有 {len(still_bad)} 条记录 ret_60d_vol < 0.08 (K线不足)")
    else:
        logger.info("验证通过")


if __name__ == "__main__":
    migrate()
