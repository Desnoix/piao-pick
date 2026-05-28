"""
===================================
AkshareFetcher - Primary Data Source (Priority 0)
===================================

Data source: East Money via akshare library (ak.stock_zh_a_hist)

Features: Free, no Token required, comprehensive data
Risk: Crawler mechanism susceptible to anti-bot blocking

Anti-ban strategies:
1. Random sleep 2-5 seconds before each request
2. Random User-Agent rotation
3. Exponential backoff retry via tenacity
"""

import logging
import os
import random
import time

import pandas as pd
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import STANDARD_COLUMNS, BaseFetcher, DataFetchError, RateLimitError, _is_etf_code

logger = logging.getLogger(__name__)


# User-Agent pool for random rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def fetch_all_a_share_snapshot() -> pd.DataFrame:
    """
    获取全 A 股实时快照 (带重试和降级)。

    优先使用 ak.stock_zh_a_spot_em() (东方财富, 单次调用, 字段丰富)。
    如果东方财富接口不可用 (重试5次后仍失败)，自动降级到
    ak.stock_zh_a_spot() (新浪财经, 较慢但稳定)。

    Returns:
        DataFrame with all A-share real-time data

    Raises:
        DataFetchError: 两个数据源都失败后
    """
    # 先尝试东方财富 (带重试)
    try:
        df = _fetch_snapshot_eastmoney()
        df["_source"] = "eastmoney"
        return df
    except Exception as e:
        logger.warning(f"[全A股快照] 东方财富接口失败 ({e})，降级到新浪财经...")

    # Fallback 到新浪 (不走 retry 装饰器, 直接调用)
    return _fetch_snapshot_sina_fallback()


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, OSError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _fetch_snapshot_eastmoney() -> pd.DataFrame:
    """东方财富快照 (带指数退避重试, 只重试网络层异常, 最多2次后快速降级)"""
    import akshare as ak

    attempt = getattr(_fetch_snapshot_eastmoney.retry, "statistics", {}).get("attempt_number", 1)
    logger.info(f"[API call] ak.stock_zh_a_spot_em() — 全A股快照 (尝试 {attempt}/5)")

    df = ak.stock_zh_a_spot_em()
    if df is not None and not df.empty:
        logger.info(f"[API response] 全A股快照成功 (东方财富): {len(df)} 只股票")
        return df
    raise DataFetchError("东方财富快照返回空数据")


def _fetch_snapshot_sina_fallback() -> pd.DataFrame:
    """
    新浪快照 fallback — 直接批量请求 hq.sinajs.cn, 不依赖 AKShare 封装。

    流程:
    1. 用 ak.stock_info_a_code_name() 获取全A股代码列表
    2. 每批 50 只, 直接 HTTP 请求 hq.sinajs.cn
    3. 解析返回的 JS 数据, 组装 DataFrame

    比 ak.stock_zh_a_spot() 更稳定, 不受 AKShare 内部 bug 影响。
    """
    import akshare as ak
    import requests

    # Step 1: 获取全 A 股代码列表 (该接口稳定)
    logger.info("[数据准备] 获取全A股代码列表...")
    try:
        code_df = ak.stock_info_a_code_name()
    except Exception as e:
        raise DataFetchError(f"获取股票代码列表失败: {e}") from e

    # 过滤: 只保留A股 (6位数字代码, 排除北交所92/43/8x开头)
    from .base import is_bse_code

    all_codes = code_df["code"].astype(str).tolist()
    all_names = dict(zip(code_df["code"].astype(str), code_df["name"].astype(str)))

    a_share_codes = []
    for code in all_codes:
        if len(code) == 6 and code.isdigit() and not is_bse_code(code):
            a_share_codes.append(code)

    logger.info(f"[数据准备] A股代码: {len(a_share_codes)} 只 (排除北交所)")

    # Step 2: 批量请求 hq.sinajs.cn
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "Referer": "https://finance.sina.com.cn",
    }
    BATCH_SIZE = 50
    all_rows = []
    errors = 0

    for i in range(0, len(a_share_codes), BATCH_SIZE):
        batch = a_share_codes[i : i + BATCH_SIZE]
        # 构建 Sina 代码: 60xxxx -> sh60xxxx, 00xxxx/30xxxx -> sz00xxxx
        sina_codes = []
        for code in batch:
            if code.startswith(("6", "9")):
                sina_codes.append(f"sh{code}")
            else:
                sina_codes.append(f"sz{code}")

        sina_list = ",".join(sina_codes)
        url = f"https://hq.sinajs.cn/list={sina_list}"

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"新浪批量请求返回 {resp.status_code}, batch {i // BATCH_SIZE + 1}")
                errors += 1
                continue

            # 解析返回数据
            for line in resp.text.strip().split("\n"):
                line = line.strip()
                if not line or "=" not in line:
                    continue
                try:
                    row = _parse_sina_line(line, all_names)
                    if row:
                        all_rows.append(row)
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"新浪批量请求失败, batch {i // BATCH_SIZE + 1}: {e}")
            errors += 1

        # 每批之间短暂等待, 避免触发限流
        time.sleep(0.2)

    if not all_rows:
        raise DataFetchError(f"新浪接口未返回任何数据 (errors={errors})")

    df = pd.DataFrame(all_rows)
    df["_source"] = "sina_direct"
    logger.info(f"[API response] 全A股快照成功 (新浪直连): {len(df)} 只股票, errors={errors}")
    return df


def _parse_sina_line(line: str, name_map: dict) -> dict | None:
    """
    解析新浪行情数据的单行。

    格式: var hq_str_sh600519="贵州茅台,1268.020,1273.380,1257.260,...";
    字段: 名称,今开,昨收,当前价,最高,最低,买一,卖一,成交量,成交额,...
    """
    if '="' not in line:
        return None

    # 提取代码: hq_str_sh600519 -> 600519
    var_part, data_part = line.split('="', 1)
    sina_code = var_part.split("_")[-1]  # sh600519
    code = sina_code[2:]  # 600519

    # 数据以 ;" 结尾
    data_str = data_part.rstrip('";')
    if not data_str:
        return None

    fields = data_str.split(",")
    if len(fields) < 12:
        return None

    # 解析字段
    try:
        current_price = float(fields[3]) if fields[3] else 0
        if current_price <= 0:
            return None

        pre_close = float(fields[2]) if fields[2] else 0
        open_price = float(fields[1]) if fields[1] else 0
        high = float(fields[4]) if fields[4] else 0
        low = float(fields[5]) if fields[5] else 0
        volume = float(fields[8]) if fields[8] else 0
        amount = float(fields[9]) if fields[9] else 0

        pct_chg = ((current_price - pre_close) / pre_close * 100) if pre_close > 0 else 0

        return {
            "代码": code,
            "名称": name_map.get(code, fields[0]),
            "最新价": current_price,
            "涨跌幅": round(pct_chg, 3),
            "涨跌额": current_price - pre_close,
            "今开": open_price,
            "最高": high,
            "最低": low,
            "昨收": pre_close,
            "成交量": volume,
            "成交额": amount,
        }
    except (ValueError, IndexError):
        return None


class AkshareFetcher(BaseFetcher):
    """
    Akshare data source implementation.

    Priority: 0 (highest)
    Data source: East Money via akshare

    Key strategies:
    - Random sleep 2.0-5.0 seconds before each request
    - Random User-Agent rotation
    - Exponential backoff retry (max 3 attempts)
    """

    name = "AkshareFetcher"
    priority = int(os.getenv("AKSHARE_PRIORITY", "0"))

    def __init__(self, sleep_min: float = 2.0, sleep_max: float = 5.0):
        """
        Initialize AkshareFetcher.

        Args:
            sleep_min: Minimum sleep time (seconds)
            sleep_max: Maximum sleep time (seconds)
        """
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
        self._last_request_time: float | None = None

    def _set_random_user_agent(self) -> None:
        """Set random User-Agent for anti-bot measures."""
        try:
            random_ua = random.choice(USER_AGENTS)
            logger.debug(f"Set User-Agent: {random_ua[:50]}...")
        except Exception as e:
            logger.debug(f"Failed to set User-Agent: {e}")

    def _enforce_rate_limit(self) -> None:
        """
        Enforce rate limiting:
        1. Check interval since last request
        2. If interval is insufficient, add supplementary sleep
        3. Then execute random jitter sleep
        """
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            min_interval = self.sleep_min
            if elapsed < min_interval:
                additional_sleep = min_interval - elapsed
                logger.debug(f"Supplementary sleep {additional_sleep:.2f} seconds")
                time.sleep(additional_sleep)

        # Execute random jitter sleep
        self.random_sleep(self.sleep_min, self.sleep_max)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch raw data from Akshare.

        Routes based on code type:
        - ETF: ak.fund_etf_hist_em()
        - Regular A-share: ak.stock_zh_a_hist()
        """
        if _is_etf_code(stock_code):
            return self._fetch_etf_data(stock_code, start_date, end_date)
        else:
            return self._fetch_stock_data(stock_code, start_date, end_date)

    def _fetch_stock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch regular A-share historical data via ak.stock_zh_a_hist().
        """
        import akshare as ak

        # Anti-ban: random User-Agent
        self._set_random_user_agent()

        # Anti-ban: enforce rate limit
        self._enforce_rate_limit()

        logger.info(f"[API call] ak.stock_zh_a_hist(symbol={stock_code}, ...)")

        try:
            api_start = time.time()

            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq",
            )

            api_elapsed = time.time() - api_start

            if df is not None and not df.empty:
                logger.info(f"[API response] ak.stock_zh_a_hist success: {len(df)} rows, elapsed={api_elapsed:.2f}s")
                return df
            else:
                logger.warning("[API response] ak.stock_zh_a_hist returned empty data")
                return pd.DataFrame()

        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["banned", "blocked", "rate", "limit", "restrict"]):
                raise RateLimitError(f"Akshare may be rate-limited: {e}") from e
            raise DataFetchError(f"Akshare fetch failed: {e}") from e

    def _fetch_etf_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch ETF historical data via ak.fund_etf_hist_em().

        Args:
            stock_code: ETF code, e.g. '512400', '159883'
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format

        Returns:
            ETF historical data DataFrame
        """
        import akshare as ak

        # Anti-ban: random User-Agent
        self._set_random_user_agent()

        # Anti-ban: enforce rate limit
        self._enforce_rate_limit()

        logger.info(
            f"[API call] ak.fund_etf_hist_em(symbol={stock_code}, period=daily, "
            f"start_date={start_date.replace('-', '')}, end_date={end_date.replace('-', '')}, adjust=qfq)"
        )

        try:
            api_start = time.time()

            df = ak.fund_etf_hist_em(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq",
            )

            api_elapsed = time.time() - api_start

            if df is not None and not df.empty:
                logger.info(f"[API response] ak.fund_etf_hist_em success: {len(df)} rows, elapsed={api_elapsed:.2f}s")
                return df
            else:
                logger.warning(f"[API response] ak.fund_etf_hist_em returned empty data, elapsed={api_elapsed:.2f}s")
                return pd.DataFrame()

        except Exception as e:
            error_msg = str(e).lower()

            # Detect anti-bot blocking
            if any(keyword in error_msg for keyword in ["banned", "blocked", "rate", "limit", "restrict"]):
                logger.warning(f"Possible rate-limiting detected: {e}")
                raise RateLimitError(f"Akshare may be rate-limited: {e}") from e

            raise DataFetchError(f"Akshare ETF data fetch failed: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        Normalize Akshare data.

        Akshare returns Chinese column names:
        date(日期), open(开盘), close(收盘), high(最高), low(最低),
        volume(成交量), amount(成交额), pct_chg(涨跌幅), ...

        Maps to standard columns:
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # Column name mapping (Akshare Chinese names -> standard English names)
        column_mapping = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "pct_chg",
        }

        # Rename columns
        df = df.rename(columns=column_mapping)

        # Add stock code column
        df["code"] = stock_code

        # Keep only required columns
        keep_cols = ["code"] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_index_daily_data(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch index historical data via ak.index_zh_a_hist() with retry.

        Uses short jitter sleep instead of full rate limiting (designed for
        web API queries, not batch operations).

        Args:
            index_code: Index code, e.g. '000300'
            start_date: Start date (format flexible, '-' stripped internally)
            end_date: End date (format flexible, '-' stripped internally)

        Returns:
            DataFrame with columns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, ...
        """
        import akshare as ak

        self._set_random_user_agent()
        self.random_sleep(0.3, 1.0)

        logger.info(f"[API call] ak.index_zh_a_hist(symbol={index_code}, ...)")
        api_start = time.time()

        df = ak.index_zh_a_hist(
            symbol=index_code,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )

        api_elapsed = time.time() - api_start

        if df is not None and not df.empty:
            logger.info(f"[API response] ak.index_zh_a_hist success: {len(df)} rows, elapsed={api_elapsed:.2f}s")
            return df

        logger.warning(f"[API response] ak.index_zh_a_hist returned empty data, elapsed={api_elapsed:.2f}s")
        raise DataFetchError(f"[{self.name}] No index data returned for {index_code}")

    def get_index_spot_data(self) -> pd.DataFrame:
        """
        Fetch all index real-time data with East Money + Sina fallback.

        Prioritize ak.stock_zh_index_spot_em() (East Money, comprehensive fields).
        If it fails after retries, automatically fallback to ak.stock_zh_index_spot_sina()
        (Sina, less fields but more stable).

        Returns:
            DataFrame with all index real-time quotes
        """
        try:
            return self._fetch_index_spot_eastmoney()
        except Exception as e:
            logger.warning(f"[Index spot] East Money failed after retries ({e}), falling back to Sina...")
            return self._fetch_index_spot_sina_fallback()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_index_spot_eastmoney(self) -> pd.DataFrame:
        """Fetch index real-time quotes from East Money (with retry)."""
        import akshare as ak

        self._set_random_user_agent()
        logger.info("[API call] ak.stock_zh_index_spot_em()")
        api_start = time.time()

        df = ak.stock_zh_index_spot_em()

        api_elapsed = time.time() - api_start
        if df is not None and not df.empty:
            logger.info(f"[API response] ak.stock_zh_index_spot_em success: {len(df)} rows, elapsed={api_elapsed:.2f}s")
            return df

        logger.warning(f"[API response] ak.stock_zh_index_spot_em returned empty, elapsed={api_elapsed:.2f}s")
        raise DataFetchError(f"[{self.name}] Index spot data returned empty from East Money")

    def _fetch_index_spot_sina_fallback(self) -> pd.DataFrame:
        """
        Fetch index real-time quotes from Sina (fallback, less fields but more stable).

        Uses ak.stock_zh_index_spot_sina() which returns:
        代码 (sh000001 format), 名称, 最新价, 涨跌额, 涨跌幅, 昨收, 今开, 最高, 最低, 成交量, 成交额

        Note: Sina code format includes exchange prefix (sh/sz), which is stripped
        to match East Money's bare code format (000300, 399001, etc.).
        """
        import akshare as ak

        logger.info("[API call] ak.stock_zh_index_spot_sina() (Sina fallback)")
        api_start = time.time()

        try:
            df = ak.stock_zh_index_spot_sina()
        except Exception as e:
            logger.error(f"[API response] ak.stock_zh_index_spot_sina failed: {e}")
            raise DataFetchError(f"[{self.name}] Index spot fallback to Sina also failed: {e}") from e

        api_elapsed = time.time() - api_start
        if df is not None and not df.empty:
            logger.info(f"[API response] ak.stock_zh_index_spot_sina success: {len(df)} rows, elapsed={api_elapsed:.2f}s")

            # Strip exchange prefix from codes (sh000001 -> 000001, sz399001 -> 399001)
            if "代码" in df.columns:
                df["代码"] = df["代码"].astype(str).str.replace(
                    r"^(sh|sz)", "", regex=True
                )

            return df

        logger.warning(f"[API response] ak.stock_zh_index_spot_sina returned empty, elapsed={api_elapsed:.2f}s")
        raise DataFetchError(f"[{self.name}] Index spot data returned empty from Sina")

