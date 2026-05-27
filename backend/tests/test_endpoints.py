# -*- coding: utf-8 -*-
"""Quick integration test for all API endpoints"""

import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from fastapi.testclient import TestClient
from app.main import create_app

app = create_app()
client = TestClient(app)

# Health check
resp = client.get("/api/health")
print(f"Health: {resp.status_code} {resp.json()}")
assert resp.status_code == 200
assert resp.json()["status"] == "ok"

# List stocks
resp = client.get("/api/v1/stocks/")
print(f"Stocks: {resp.status_code} total={resp.json().get('total')}")
assert resp.status_code == 200

# List strategies
resp = client.get("/api/v1/strategies/")
print(f"Strategies: {resp.status_code} count={len(resp.json())}")
assert resp.status_code == 200

# Data status
resp = client.get("/api/v1/data/status")
print(f"Status: {resp.status_code} {resp.json()}")
assert resp.status_code == 200

# Trade calendar
resp = client.get("/api/v1/data/trade-calendar?start_date=2026-05-01&end_date=2026-05-31")
print(f"Calendar: {resp.status_code} days={resp.json().get('count')}")
assert resp.status_code == 200
assert resp.json()["count"] > 0

# Backtest (should be 501)
resp = client.post(
    "/api/v1/backtest/run",
    json={"strategy_id": "test", "start_date": "2024-01-01", "end_date": "2024-12-31"},
)
print(f"Backtest: {resp.status_code}")
assert resp.status_code == 501

# Selection run (should return stub response since pipeline is not implemented)
resp = client.post(
    "/api/v1/selection/run",
    json={"strategy_id": "test"},
)
print(f"Selection run: {resp.status_code} {resp.json()}")
assert resp.status_code == 200

# Strategies CRUD
resp = client.post(
    "/api/v1/strategies/",
    json={
        "name": "test_strategy",
        "display_name": "Test",
        "config": "name: test\n",
    },
)
print(f"Create strategy: {resp.status_code}")
assert resp.status_code == 200
created_id = resp.json()["id"]

resp = client.get(f"/api/v1/strategies/{created_id}")
print(f"Get strategy: {resp.status_code}")
assert resp.status_code == 200

resp = client.put(
    f"/api/v1/strategies/{created_id}",
    json={"display_name": "Test Updated"},
)
print(f"Update strategy: {resp.status_code}")
assert resp.status_code == 200

resp = client.delete(f"/api/v1/strategies/{created_id}")
print(f"Delete strategy: {resp.status_code}")
assert resp.status_code == 200

# Stock not found
resp = client.get("/api/v1/stocks/999999.SZ")
print(f"Stock 404: {resp.status_code}")
assert resp.status_code == 404

print("\n=== ALL ENDPOINT TESTS PASSED ===")
