#!/usr/bin/env python3
"""Check current data status"""
import sys
sys.path.insert(0, '.')

from app.database import get_db
from sqlmodel import select, func
from app.models import StockInfo, Kline, Factor

db = get_db()
with db.get_session() as s:
    stock_count = s.exec(select(func.count()).select_from(StockInfo)).one()
    kline_count = s.exec(select(func.count()).select_from(Kline)).one()
    factor_count = s.exec(select(func.count()).select_from(Factor)).one()
    
    # 查询每只股票的K线行数分布
    stmt = select(Kline.ts_code, func.count()).group_by(Kline.ts_code)
    stock_kline_counts = s.exec(stmt).all()
    
    print(f'股票数量: {stock_count}')
    print(f'K线总数: {kline_count}')
    print(f'因子总数: {factor_count}')
    
    # 统计K线行数分布
    count_dist = {}
    for code, count in stock_kline_counts:
        bucket = count
        count_dist[bucket] = count_dist.get(bucket, 0) + 1
    
    print(f'\nK线行数分布:')
    for rows, num_stocks in sorted(count_dist.items()):
        print(f'  {rows} 行: {num_stocks} 只股票')
    
    # 查询有20+行数据的股票数量
    stmt2 = select(func.count()).select_from(
        s.exec(select(Kline.ts_code).group_by(Kline.ts_code).having(func.count() >= 20))
    )
    stocks_with_20plus = s.exec(stmt2).one()
    
    print(f'\n有 20+ 行K线数据的股票: {stocks_with_20plus if not isinstance(stocks_with_20plus, tuple) else stocks_with_20plus[0]}')
    print(f'可以计算因子的股票: {stocks_with_20plus if not isinstance(stocks_with_20plus, tuple) else stocks_with_20plus[0]} / {stock_count} ({stocks_with_20plus/stock_count*100:.1f}%)')
