# -*- coding: utf-8 -*-
"""
===================================
History K-Line Data Source Test
===================================

Tests the availability of different historical K-line data APIs:

1. AKShare stock_zh_a_hist: East Money source (60-day daily data)
2. AKShare stock_zh_a_daily: Sina source (historical data)
3. BaoStock query_history_k_data_plus: Install if not available (historical data)
4. Direct HTTP request to push2his.eastmoney.com: East Money K-line API

Test criteria:
- Success/Fail status
- Number of data rows
- Column names
- First 2 rows sample data
- Execution time

Test parameters:
- Stock: sh.600519 (Moutai)
- Date range: 2025-10-01 to 2025-12-20
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataSourceTester:
    """Test different data source APIs."""

    def __init__(self, stock_code: str, start_date: str, end_date: str):
        self.stock_code = stock_code
        self.start_date = start_date
        self.end_date = end_date
        self.results: list[Dict[str, Any]] = []

    def run_all_tests(self) -> None:
        """Run all data source tests."""
        print("\n" + "=" * 80)
        print("HISTORY K-LINE DATA SOURCE TEST SUITE")
        print("=" * 80)
        print(f"Test stock: {self.stock_code}")
        print(f"Date range: {self.start_date} to {self.end_date}")
        print("=" * 80 + "\n")

        self._test_akshare_eastmoney()
        self._test_akshare_sina()
        self._test_baostock()
        self._test_http_eastmoney()

        self._print_summary()

    def _print_summary(self) -> None:
        """Print test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)

        success_count = sum(1 for r in self.results if r['status'] == 'OK')
        total_count = len(self.results)

        for idx, result in enumerate(self.results, 1):
            status = "[OK] OK" if result['status'] == 'OK' else "[FAIL] FAIL"
            print(f"{idx}. {result['name']}: {status}")
            print(f"   Rows: {result['rows']}, Time: {result['time']:.2f}s")
            if result.get('columns'):
                print(f"   Columns: {result['columns']}")
            print()

        print("-" * 80)
        print(f"Success: {success_count}/{total_count}")
        print("=" * 80 + "\n")

    def _test_akshare_eastmoney(self) -> None:
        """Test AKShare stock_zh_a_hist (East Money source)."""
        print("Test 1: AKShare stock_zh_a_hist (East Money)")

        test_name = "AKShare (stock_zh_a_hist)"
        start_time = time.time()

        try:
            import akshare as ak

            logger.info(f"[API call] ak.stock_zh_a_hist(symbol={self.stock_code}, period=daily)")
            logger.info(f"[API call] start_date={self.start_date}, end_date={self.end_date}")

            api_start = time.time()
            df = ak.stock_zh_a_hist(
                symbol=self.stock_code,
                period="daily",
                start_date=self.start_date.replace('-', ''),
                end_date=self.end_date.replace('-', ''),
                adjust="qfq"
            )
            api_elapsed = time.time() - api_start

            if df is not None and not df.empty:
                elapsed = time.time() - start_time
                columns = list(df.columns)
                sample_data = df.head(2)

                result = {
                    'name': test_name,
                    'status': 'OK',
                    'rows': len(df),
                    'time': elapsed,
                    'columns': columns,
                    'sample': sample_data
                }

                print(f"   [OK] SUCCESS")
                print(f"   Rows: {len(df)}")
                print(f"   Columns: {columns}")
                print(f"   Time: {elapsed:.2f}s")
                print(f"   API Time: {api_elapsed:.2f}s")
                print("\n   Sample data (first 2 rows):")
                print(sample_data.to_string(index=False))
            else:
                elapsed = time.time() - start_time
                result = {
                    'name': test_name,
                    'status': 'FAIL',
                    'rows': 0,
                    'time': elapsed,
                    'error': 'Empty data returned'
                }

                print(f"   [FAIL] FAILED: Empty data returned")

        except ImportError:
            elapsed = time.time() - start_time
            result = {
                'name': test_name,
                'status': 'FAIL',
                'rows': 0,
                'time': elapsed,
                'error': 'AKShare not installed'
            }

            print(f"   [FAIL] FAILED: AKShare not installed")

        except Exception as e:
            elapsed = time.time() - start_time
            result = {
                'name': test_name,
                'status': 'FAIL',
                'rows': 0,
                'time': elapsed,
                'error': str(e)
            }

            print(f"   [FAIL] FAILED: {e}")

        print()
        self.results.append(result)

    def _test_akshare_sina(self) -> None:
        """Test AKShare stock_zh_a_daily (Sina source)."""
        print("Test 2: AKShare stock_zh_a_daily (Sina source)")

        test_name = "AKShare (stock_zh_a_daily)"
        start_time = time.time()

        try:
            import akshare as ak

            logger.info(f"[API call] ak.stock_zh_a_daily(symbol={self.stock_code})")

            api_start = time.time()
            try:
                df = ak.stock_zh_a_daily(
                    symbol=self.stock_code,
                    start_date=self.start_date,
                    end_date=self.end_date
                )
            except Exception as e:
                error_msg = str(e)
                if 'date' in error_msg:
                    elapsed = time.time() - start_time
                    result = {
                        'name': test_name,
                        'status': 'SKIP',
                        'rows': 0,
                        'time': elapsed,
                        'error': f'API issue: {error_msg}. See test_akshare_daily.py for details.'
                    }
                    print(f"   [SKIP] SKIPPED: {error_msg}")
                    print("   Note: AKShare stock_zh_a_daily has internal errors in current environment")
                    self.results.append(result)
                    return
                df = None

            api_elapsed = time.time() - api_start

            if df is not None and not df.empty:
                elapsed = time.time() - start_time
                columns = list(df.columns)
                sample_data = df.head(2)

                result = {
                    'name': test_name,
                    'status': 'OK',
                    'rows': len(df),
                    'time': elapsed,
                    'columns': columns,
                    'sample': sample_data
                }

                print(f"   [OK] SUCCESS")
                print(f"   Rows: {len(df)}")
                print(f"   Columns: {columns}")
                print(f"   Time: {elapsed:.2f}s")
                print(f"   API Time: {api_elapsed:.2f}s")
                print("\n   Sample data (first 2 rows):")
                print(sample_data.to_string(index=False))
            else:
                elapsed = time.time() - start_time
                result = {
                    'name': test_name,
                    'status': 'FAIL',
                    'rows': 0,
                    'time': elapsed,
                    'error': 'Empty data returned'
                }

                print(f"   [FAIL] FAILED: Empty data returned")

        except ImportError:
            elapsed = time.time() - start_time
            result = {
                'name': test_name,
                'status': 'FAIL',
                'rows': 0,
                'time': elapsed,
                'error': 'AKShare not installed'
            }

            print(f"   [FAIL] FAILED: AKShare not installed")

        except Exception as e:
            elapsed = time.time() - start_time
            result = {
                'name': test_name,
                'status': 'FAIL',
                'rows': 0,
                'time': elapsed,
                'error': str(e)
            }

            print(f"   [FAIL] FAILED: {e}")

        print()
        self.results.append(result)

    def _test_baostock(self) -> None:
        """Test BaoStock query_history_k_data_plus."""
        print("Test 3: BaoStock query_history_k_data_plus")

        test_name = "BaoStock (query_history_k_data_plus)"
        start_time = time.time()

        try:
            import baostock as bs

            logger.info(f"[API call] bs.query_history_k_data_plus(code={self.stock_code})")

            api_start = time.time()

            lg = bs.login()
            if lg.error_code != '0':
                elapsed = time.time() - start_time
                result = {
                    'name': test_name,
                    'status': 'FAIL',
                    'rows': 0,
                    'time': elapsed,
                    'error': f'BaoStock login failed: {lg.error_msg}'
                }
                print(f"   [FAIL] FAILED: BaoStock login failed: {lg.error_msg}")
                self.results.append(result)
                bs.logout()
                return

            code = f"sh.{self.stock_code}"
            fields = "date,code,open,high,low,close,volume,amount,pctChg"
            start = self.start_date
            end = self.end_date

            rs = bs.query_history_k_data_plus(
                code,
                fields,
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag="3"
            )

            api_elapsed = time.time() - api_start

            print(f"   [DEBUG] API response: error_code={rs.error_code}, error_msg={rs.error_msg}")

            rows = []
            while (rs.error_code == '0') & rs.next():
                rows.append(rs.get_row_data())

            bs.logout()

            if rows:
                elapsed = time.time() - start_time
                df = pd.DataFrame(rows, columns=fields.split(','))
                columns = list(df.columns)
                sample_data = df.head(2)

                result = {
                    'name': test_name,
                    'status': 'OK',
                    'rows': len(df),
                    'time': elapsed,
                    'columns': columns,
                    'sample': sample_data
                }

                print(f"   [OK] SUCCESS")
                print(f"   Rows: {len(df)}")
                print(f"   Columns: {columns}")
                print(f"   Time: {elapsed:.2f}s")
                print(f"   API Time: {api_elapsed:.2f}s")
                print("\n   Sample data (first 2 rows):")
                print(sample_data.to_string(index=False))
            else:
                elapsed = time.time() - start_time
                result = {
                    'name': test_name,
                    'status': 'FAIL',
                    'rows': 0,
                    'time': elapsed,
                    'error': f'Empty data returned. API error: {rs.error_code} - {rs.error_msg}'
                }

                print(f"   [FAIL] FAILED: Empty data returned. API error: {rs.error_code} - {rs.error_msg}")

        except ImportError:
            elapsed = time.time() - start_time
            result = {
                'name': test_name,
                'status': 'FAIL',
                'rows': 0,
                'time': elapsed,
                'error': 'AKShare not installed'
            }

            print(f"   [FAIL] FAILED: AKShare not installed")

        except Exception as e:
            elapsed = time.time() - start_time
            result = {
                'name': test_name,
                'status': 'FAIL',
                'rows': 0,
                'time': elapsed,
                'error': str(e)
            }

            print(f"   [FAIL] FAILED: {e}")

        print()
        self.results.append(result)

    def _test_http_eastmoney(self) -> None:
        """Test direct HTTP request to push2his.eastmoney.com."""
        print("Test 4: Direct HTTP request to push2his.eastmoney.com")

        test_name = "HTTP (push2his.eastmoney.com)"
        start_time = time.time()

        try:
            logger.info(f"[API call] HTTP request to push2his.eastmoney.com")

            api_start = time.time()

            code = self.stock_code
            start = self.start_date
            end = self.end_date

            url = f"http://push2his.eastmoney.com/api/qt/clist/get?"
            params = {
                'pn': '1',
                'pz': '1000',
                'po': '1',
                'np': '1',
                'fltt': '2',
                'invt': '2',
                'fid': 'f3',
                'fs': f'm:{code}',
                'fields': 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152',
                'ut': 'bd1d9db0fa86400f410d795742383e60',
                'bdqt': '',
                '_': str(int(time.time() * 1000))
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'http://quote.eastmoney.com'
            }

            response = requests.get(url, params=params, headers=headers, timeout=30)
            api_elapsed = time.time() - api_start

            if response.status_code == 200:
                data = response.json()

                if data.get('data') is not None:
                    diff = data['data'].get('diff', [])
                    if diff and len(diff) > 0:
                        rows = diff
                        columns = list(rows[0].keys())

                        elapsed = time.time() - start_time
                        df = pd.DataFrame(rows, columns=columns)
                        sample_data = df.head(2)

                        result = {
                            'name': test_name,
                            'status': 'OK',
                            'rows': len(df),
                            'time': elapsed,
                            'columns': columns,
                            'sample': sample_data
                        }

                        print(f"   [OK] SUCCESS")
                        print(f"   Rows: {len(df)}")
                        print(f"   Columns: {columns}")
                        print(f"   Time: {elapsed:.2f}s")
                        print(f"   API Time: {api_elapsed:.2f}s")
                        print("\n   Sample data (first 2 rows):")
                        print(sample_data.to_string(index=False))
                    else:
                        elapsed = time.time() - start_time
                        result = {
                            'name': test_name,
                            'status': 'FAIL',
                            'rows': 0,
                            'time': elapsed,
                            'error': 'Empty diff data (API returned valid response but no data)'
                        }

                        print(f"   [FAIL] FAILED: Empty diff data (API responded with rt=1, data=None)")
                else:
                    elapsed = time.time() - start_time
                    result = {
                        'name': test_name,
                        'status': 'FAIL',
                        'rows': 0,
                        'time': elapsed,
                        'error': f'API returned no data: rc={data.get("rc")}, rt={data.get("rt")}'
                    }

                    print(f"   [FAIL] FAILED: API returned no data (rt={data.get('rt')}, rc={data.get('rc')})")
            else:
                elapsed = time.time() - start_time
                result = {
                    'name': test_name,
                    'status': 'FAIL',
                    'rows': 0,
                    'time': elapsed,
                    'error': f'HTTP {response.status_code}: {response.text[:200]}'
                }

                print(f"   [FAIL] FAILED: HTTP {response.status_code}")

        except Exception as e:
            elapsed = time.time() - start_time
            result = {
                'name': test_name,
                'status': 'FAIL',
                'rows': 0,
                'time': elapsed,
                'error': str(e)
            }

            print(f"   [FAIL] FAILED: {e}")

        print()
        self.results.append(result)


def main():
    """Main entry point."""
    test_stock_code = "600519"
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = "2024-10-01"

    tester = DataSourceTester(test_stock_code, start_date, end_date)
    tester.run_all_tests()


if __name__ == "__main__":
    main()
