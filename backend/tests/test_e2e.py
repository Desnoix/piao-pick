# -*- coding: utf-8 -*-
"""端到端测试: 数据准备 -> 选股"""
import sys
import logging
sys.path.insert(0, '.')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.services.data_preparation import DataPreparationService

print("=" * 60)
print("STEP 1: 全市场数据准备 (通过 Sina fallback)")
print("=" * 60)

prep = DataPreparationService()
result = prep.prepare()
print(f"\n结果: {result}")

if result.get('synced', 0) > 0:
    print(f"\n[OK] 成功同步 {result['synced']} 条K线, "
          f"{result['factor_count']} 条因子, "
          f"数据源: {result.get('source', 'unknown')}")
    
    print("\n" + "=" * 60)
    print("STEP 2: 运行选股 (value_lowvol 策略)")
    print("=" * 60)
    
    from app.services.selection_service import SelectionService
    svc = SelectionService()
    sel_result = svc.run_selection(
        strategy_name='value_lowvol',
        trade_date=result['trade_date'],
    )
    
    print(f"\n选股结果:")
    print(f"  策略: {sel_result.get('strategy_name')}")
    print(f"  日期: {sel_result.get('trade_date')}")
    print(f"  股票池: {sel_result.get('universe_count')} 只")
    print(f"  输出: {sel_result.get('final_count')} 只")
    
    if sel_result.get('results'):
        print(f"\n  Top 5 候选:")
        for r in sel_result['results'][:5]:
            print(f"    #{r.get('rank', '?')} {r.get('ts_code')} "
                  f"score={r.get('composite_score', 0):.2f} "
                  f"name={r.get('name', '?')}")
    else:
        print("  (无候选股票)")
else:
    print(f"\n[FAIL] 数据准备失败: {result.get('error', 'unknown')}")
