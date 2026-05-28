"""
基本面数据服务 — 从 AKShare 获取财务数据。
Fundamental data service: fetch financial data from AKShare.

数据来源 (Data sources):
- ak.stock_financial_analysis_indicator(): ROE, 毛利率
- ak.stock_yjbb_em(): 营收/利润同比增长率, ROE
- ak.stock_cash_flow_sheet_by_report_em(): 自由现金流
- ak.stock_institute_hold_detail(): 机构持仓变动
"""

from __future__ import annotations

import logging
import time

import pandas as pd

logger = logging.getLogger(__name__)

# AKShare 调用间隔 (秒) — 遵守频率限制
# AKShare call interval (seconds) — respect rate limits
_CALL_INTERVAL = 0.5
_BATCH_CALL_INTERVAL = 3.0


class FundamentalService:
    """
    基本面数据获取服务。
    Fundamental data fetching service with in-memory cache.
    """

    def __init__(self) -> None:
        self._cache: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------
    # 营收/利润同比增长率 + ROE (批量接口 — stock_yjbb_em)
    # Revenue/Earnings YoY growth + ROE (batch API)
    # ------------------------------------------------------------------
    def fetch_yjbb_batch(self, report_date: str) -> pd.DataFrame | None:
        """
        批量获取全市场业绩报表 (营收/净利润同比增长率, ROE)。
        Batch fetch earnings report for all stocks.

        主接口: ak.stock_yjbb_em(date="20231231")
        此接口一次返回全市场数据，无需逐股调用。

        Args:
            report_date: 报告期 "YYYYMMDD" (如 "20231231")

        Returns:
            DataFrame with columns:
            [ts_code, rev_growth_yoy, ear_growth_yoy, roe, ...]
            None if fetch fails.
        """
        cache_key = f"yjbb:{report_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            import akshare as ak

            df = ak.stock_yjbb_em(date=report_date)
            if df is None or df.empty:
                return None

            result = pd.DataFrame()
            # 股票代码列
            code_col = next(
                (c for c in df.columns if "股票代码" in str(c) or "代码" in str(c)),
                df.columns[0],
            )
            result["ts_code"] = df[code_col].astype(str).str.zfill(6)

            # 营业收入同比增长 (%)
            rev_col = next(
                (c for c in df.columns if "营业收入同比" in str(c)),
                None,
            )
            if rev_col:
                result["rev_growth_yoy"] = pd.to_numeric(df[rev_col], errors="coerce")

            # 净利润同比增长 (%)
            ear_col = next(
                (c for c in df.columns if "净利润同比" in str(c)),
                None,
            )
            if ear_col:
                result["ear_growth_yoy"] = pd.to_numeric(df[ear_col], errors="coerce")

            # 加权 ROE
            roe_col = next(
                (c for c in df.columns if "加权roe" in str(c).lower() or "ROE" in str(c)),
                None,
            )
            if roe_col:
                result["roe"] = pd.to_numeric(df[roe_col], errors="coerce")

            self._cache[cache_key] = result
            return result

        except Exception as e:
            logger.error("stock_yjbb_em failed for %s: %s", report_date, e)
            return None

    # ------------------------------------------------------------------
    # ROE & 毛利率 (单股接口 — stock_financial_analysis_indicator)
    # ROE & Gross Margin (per-stock API)
    # ------------------------------------------------------------------
    def fetch_financial_indicators(self, stock_code: str) -> pd.DataFrame | None:
        """
        获取单只股票的财务分析指标 (ROE, 毛利率等)。
        Fetch financial analysis indicators for a single stock.

        主接口: ak.stock_financial_analysis_indicator(symbol)

        Args:
            stock_code: 标准化股票代码 (6位数字)

        Returns:
            DataFrame with columns: [report_date, roe, gross_margin, ...]
            None if fetch fails.
        """
        cache_key = f"fi:{stock_code}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            import akshare as ak

            time.sleep(_CALL_INTERVAL)

            df = ak.stock_financial_analysis_indicator(symbol=stock_code)
            if df is not None and not df.empty:
                result = pd.DataFrame()
                result["report_date"] = pd.to_datetime(df.iloc[:, 0])
                # 净资产收益率 (%)
                roe_col = next(
                    (c for c in df.columns if "净资产收益率" in str(c)),
                    None,
                )
                if roe_col:
                    result["roe"] = pd.to_numeric(df[roe_col], errors="coerce")

                # 销售毛利率 (%)
                gm_col = next(
                    (c for c in df.columns if "销售毛利率" in str(c)),
                    None,
                )
                if gm_col:
                    result["gross_margin"] = pd.to_numeric(df[gm_col], errors="coerce")

                self._cache[cache_key] = result
                return result

        except Exception as e:
            logger.warning(
                "stock_financial_analysis_indicator failed for %s: %s",
                stock_code,
                e,
            )

        return None

    # ------------------------------------------------------------------
    # 自由现金流 (单股接口 — stock_cash_flow_sheet_by_report_em)
    # Free cash flow (per-stock API)
    # ------------------------------------------------------------------
    def fetch_cash_flow(self, stock_code: str) -> pd.DataFrame | None:
        """
        获取单只股票的现金流量表数据。
        Fetch cash flow statement for a single stock.

        主接口: ak.stock_cash_flow_sheet_by_report_em(symbol)

        Returns:
            DataFrame with columns: [report_date, operating_cashflow, capex]
        """
        cache_key = f"cf:{stock_code}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            import akshare as ak

            time.sleep(_CALL_INTERVAL)

            df = ak.stock_cash_flow_sheet_by_report_em(symbol=stock_code)
            if df is None or df.empty:
                return None

            result = pd.DataFrame()
            # 报告期
            date_col = next(
                (c for c in df.columns if "REPORT_DATE" in str(c).upper() or "报告" in str(c)),
                df.columns[0],
            )
            result["report_date"] = pd.to_datetime(df[date_col])

            # 经营活动现金流净额
            ops_col = next(
                (c for c in df.columns if "经营活动" in str(c) and "净额" in str(c)),
                None,
            )
            if ops_col:
                result["operating_cashflow"] = pd.to_numeric(df[ops_col], errors="coerce")

            # 购建固定资产等支付的现金 (资本开支)
            capex_col = next(
                (c for c in df.columns if "购建" in str(c) and "支付" in str(c)),
                None,
            )
            if capex_col:
                result["capex"] = pd.to_numeric(df[capex_col], errors="coerce")

            self._cache[cache_key] = result
            return result

        except Exception as e:
            logger.warning("cash flow fetch failed for %s: %s", stock_code, e)
            return None

    # ------------------------------------------------------------------
    # 机构持仓变动 (单股接口 — stock_institute_hold_detail)
    # Institutional holding change (per-stock API)
    # ------------------------------------------------------------------
    def fetch_inst_holdings(self, stock_code: str, quarter: str) -> pd.DataFrame | None:
        """
        获取基金持仓明细数据。
        Fetch fund holding details.

        风险: 此接口覆盖率较低，部分股票可能无数据。
        获取失败时返回 None，因子计算降级为空 Series。

        Args:
            stock_code: 股票代码
            quarter: 季度如 "20234" (2023Q4)

        Returns:
            DataFrame with holding ratio data, or None.
        """
        try:
            import akshare as ak

            time.sleep(_BATCH_CALL_INTERVAL)

            df = ak.stock_institute_hold_detail(stock=stock_code, quarter=quarter)
            if df is None or df.empty:
                return None

            # 汇总持仓比例
            ratio_col = next(
                (c for c in df.columns if "占流通股" in str(c) or "持仓" in str(c)),
                None,
            )
            if ratio_col:
                total_ratio = pd.to_numeric(df[ratio_col], errors="coerce").sum()
                return pd.DataFrame(
                    [
                        {
                            "ts_code": stock_code,
                            "quarter": quarter,
                            "inst_ratio": total_ratio,
                        }
                    ]
                )
            return None

        except Exception as e:
            logger.warning("inst_holdings failed for %s: %s", stock_code, e)
            return None

    def clear_cache(self) -> None:
        """清除内存缓存。"""
        self._cache.clear()
