# 历史K线数据源测试报告

## 测试概览

测试脚本位置：`backend/tests/test_history_datasource.py`

测试标的：sh.600519（贵州茅台）
日期范围：2024-10-01 至 2026-05-27

## 测试结果

| # | 数据源 | 状态 | 行数 | 耗时 | 说明 |
|---|--------|------|------|------|------|
| 1 | AKShare stock_zh_a_hist (East Money) | ❌ FAIL | 0 | 0.33s | 连接被中断，可能是API被限制 |
| 2 | AKShare stock_zh_a_daily (Sina) | ⚠️ SKIP | 0 | 0.31s | 内部错误：无法访问'date'列 |
| 3 | BaoStock query_history_k_data_plus | ✅ OK | 396 | 0.43s | 成功获取396行数据 |
| 4 | HTTP push2his.eastmoney.com | ❌ FAIL | 0 | 0.07s | API返回空数据 |

## 详细说明

### 1. AKShare stock_zh_a_hist (East Money)
- **状态**: FAIL
- **错误**: `RemoteDisconnected: Remote end closed connection without response`
- **原因**: 东方财富API接口在当前网络环境下被拦截或限制
- **影响**: 无法使用AKShare的东方财富源获取历史数据

### 2. AKShare stock_zh_a_daily (Sina)
- **状态**: SKIP
- **错误**: `KeyError: 'date'`
- **原因**: AKShare内部函数在访问数据前就抛出了异常
- **影响**: 该API在当前环境中不可用

### 3. BaoStock query_history_k_data_plus
- **状态**: OK
- **结果**: 成功获取396行历史数据
- **字段**: date, code, open, high, low, close, volume, amount, pctChg
- **代码格式**: sh.600519
- **性能**: 0.43秒（包含登录/登出时间）

### 4. HTTP push2his.eastmoney.com
- **状态**: FAIL
- **响应**: `rt=1, rc=102` (data=None)
- **原因**: API端点可能已更改或失效
- **影响**: 无法直接通过HTTP请求访问东方财富历史数据

## 结论

1. **可用的数据源**: BaoStock (`query_history_k_data_plus`) 是唯一测试成功的数据源
2. **东方财富API**: 无论是通过AKShare还是直接HTTP请求都失败了
3. **新浪API**: AKShare封装的新浪API有内部错误
4. **建议**: 在当前环境下，应使用BaoStock作为主要数据源

## 运行测试

```bash
cd backend
python tests/test_history_datasource.py
```

## 测试配置

- **测试脚本**: `tests/test_history_datasource.py`
- **测试股票**: 600519（贵州茅台）
- **日期范围**: 2024-10-01 至 2026-05-27
- **测试目标**: 验证4个不同历史K线数据接口的可用性

## 依赖

- akshare (已安装 v1.18.63)
- baostock (已安装 v0.9.1)
- pandas
- requests
