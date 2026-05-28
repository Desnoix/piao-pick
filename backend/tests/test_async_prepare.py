"""
验证: 数据准备期间事件循环不被阻塞

测试方法:
1. 清除某日因子数据
2. 触发 POST /selection/run (应返回 202)
3. 同时发送 GET /api/health (应在 1 秒内响应)
4. 轮询 GET /selection/prepare/status/{date} 直到 done
"""


async def main():
    import asyncio
    import time
    import httpx

    BASE = "http://localhost:8000"
    async with httpx.AsyncClient(timeout=10.0) as client:
        trade_date = "2025-05-26"

        print(f"[1] POST /api/v1/selection/run (date={trade_date})")
        t0 = time.time()
        resp = await client.post(
            f"{BASE}/api/v1/selection/run",
            json={"strategy_name": "value_lowvol", "trade_date": trade_date},
        )
        elapsed = time.time() - t0
        print(f"    响应码: {resp.status_code}, 耗时: {elapsed:.2f}s")

        if resp.status_code == 202:
            print("    [OK] 收到 202, 数据准备异步执行中")
        else:
            print(f"    响应体: {resp.json()}")
            return

        print("\n[2] 验证事件循环未被阻塞...")
        t0 = time.time()
        health = await client.get(f"{BASE}/api/health")
        elapsed = time.time() - t0
        status = "OK" if health.status_code == 200 and elapsed < 1.0 else "FAIL"
        print(f"    GET /api/health: {health.status_code}, 耗时: {elapsed:.2f}s [{status}]")

        print("\n[3] 并发测试: 同时发送 5 个 health 请求...")
        tasks = [client.get(f"{BASE}/api/health") for _ in range(5)]
        t0 = time.time()
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - t0
        all_ok = all(r.status_code == 200 for r in results)
        status = "OK" if all_ok and elapsed < 2.0 else "FAIL"
        print(f"    5 个并发请求完成, 总耗时: {elapsed:.2f}s [{status}]")

        print("\n[4] 轮询数据准备状态...")
        for i in range(20):
            await asyncio.sleep(3)
            resp = await client.get(f"{BASE}/api/v1/selection/prepare/status/{trade_date}")
            data = resp.json()
            current = data.get("status", "unknown")
            print(f"    轮询 #{i + 1}: status={current}")
            if current == "done":
                print("    [OK] 数据准备完成")
                break
            if current == "failed":
                print(f"    [FAIL] 数据准备失败: {data.get('error')}")
                break
        else:
            print("    [WARN] 超过最大轮询次数")


if __name__ == "__main__":
    asyncio.run(main())
