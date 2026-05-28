"""P2-4 验证: 10 并发写入全部成功, 无 database is locked。"""

import os
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import DatabaseManager
from app.models import StockInfo


def main():
    DatabaseManager.reset_instance()
    tmp = tempfile.mktemp(suffix=".db", prefix="p2_4_test_")
    db = DatabaseManager(db_path=tmp)

    # 验证 WAL 模式已启用
    import sqlite3

    conn = sqlite3.connect(tmp)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal", f"WAL 未启用, 实际 journal_mode={mode}"
    print(f"[OK] journal_mode = {mode}")

    N = 10
    results = {"ok": 0, "fail": 0}
    lock = threading.Lock()
    errors = []

    def worker(i: int):
        stock = StockInfo(
            ts_code=f"{600000 + i:06d}",
            name=f"TestStock{i}",
            industry="TEST",
        )
        from app.repositories.stock_repo import StockRepository

        repo = StockRepository(db)
        repo.upsert_stock_info(stock)
        return i

    with ThreadPoolExecutor(max_workers=N) as pool:
        futures = [pool.submit(worker, i) for i in range(N)]
        for f in as_completed(futures):
            try:
                f.result()
                with lock:
                    results["ok"] += 1
            except Exception as e:
                with lock:
                    results["fail"] += 1
                errors.append(str(e))

    print(f"[RESULT] success={results['ok']}  fail={results['fail']}")
    if errors:
        print("[ERRORS]")
        for e in errors:
            print(f"  {e}")
    try:
        os.remove(tmp)
    except OSError:
        pass

    if results["fail"] > 0:
        sys.exit(1)
    print("[PASS] 并发写入全部成功, 锁重试机制生效")


if __name__ == "__main__":
    main()
