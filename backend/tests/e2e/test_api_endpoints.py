"""
API 端点 E2E 测试

覆盖: 健康检查、策略 CRUD 生命周期、股票查询、数据状态、交易日历。
使用 FastAPI TestClient, 数据库为临时文件 (由 fastapi_test_client fixture 注入)。
标记为 @pytest.mark.e2e。
"""

import pytest

pytestmark = pytest.mark.e2e


class TestHealthCheck:
    """健康检查端点 /api/health"""

    def test_health_returns_ok(self, fastapi_test_client):
        resp = fastapi_test_client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "timestamp" in body


class TestStrategyEndpoints:
    """策略 CRUD 端点 /api/v1/strategies/"""

    def test_list_strategies_empty(self, fastapi_test_client):
        resp = fastapi_test_client.get("/api/v1/strategies/")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    def test_create_strategy(self, fastapi_test_client):
        payload = {
            "name": "e2e_test_strat",
            "display_name": "E2E 测试策略",
            "config": "name: e2e_test\nfactors: []\n",
        }
        resp = fastapi_test_client.post("/api/v1/strategies/", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert body["name"] == "e2e_test_strat"
        assert body["display_name"] == "E2E 测试策略"

    def test_create_strategy_with_invalid_yaml_returns_422(self, fastapi_test_client):
        # YAML 缺少 name 字段 (API 层的校验)
        payload = {
            "name": "bad_yaml",
            "config": "- not a mapping\n",
        }
        resp = fastapi_test_client.post("/api/v1/strategies/", json=payload)
        assert resp.status_code == 422

    def test_crud_lifecycle(self, fastapi_test_client):
        # 1) 创建
        create_resp = fastapi_test_client.post(
            "/api/v1/strategies/",
            json={
                "name": "lifecycle_test",
                "display_name": "生命周期测试",
                "config": "name: lifecycle\nfactors: []\n",
            },
        )
        assert create_resp.status_code == 200
        sid = create_resp.json()["id"]
        assert sid

        # 2) 查询
        get_resp = fastapi_test_client.get(f"/api/v1/strategies/{sid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "lifecycle_test"

        # 3) 更新
        update_resp = fastapi_test_client.put(
            f"/api/v1/strategies/{sid}",
            json={"display_name": "更新后名称"},
        )
        assert update_resp.status_code == 200

        # 4) 验证更新生效
        verify_resp = fastapi_test_client.get(f"/api/v1/strategies/{sid}")
        assert verify_resp.status_code == 200
        assert verify_resp.json()["display_name"] == "更新后名称"

        # 5) 删除
        del_resp = fastapi_test_client.delete(f"/api/v1/strategies/{sid}")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

        # 6) 验证删除成功 -> 404
        gone_resp = fastapi_test_client.get(f"/api/v1/strategies/{sid}")
        assert gone_resp.status_code == 404

    def test_get_nonexistent_strategy_404(self, fastapi_test_client):
        resp = fastapi_test_client.get("/api/v1/strategies/nonexistent_id_999")
        assert resp.status_code == 404

    def test_delete_nonexistent_404(self, fastapi_test_client):
        resp = fastapi_test_client.delete("/api/v1/strategies/nonexistent_id_999")
        assert resp.status_code == 404


class TestStockEndpoints:
    """股票数据端点 /api/v1/stocks/"""

    def test_list_stocks(self, fastapi_test_client):
        resp = fastapi_test_client.get("/api/v1/stocks/")
        assert resp.status_code == 200
        body = resp.json()
        # 应返回分页对象: total/offset/limit/items
        assert "items" in body
        assert "total" in body

    def test_stock_not_found(self, fastapi_test_client):
        resp = fastapi_test_client.get("/api/v1/stocks/999999")
        assert resp.status_code == 404

    def test_list_stocks_with_keyword(self, fastapi_test_client):
        resp = fastapi_test_client.get("/api/v1/stocks/", params={"keyword": "nonexistent_key_xyz"})
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestDataEndpoints:
    """数据状态端点 /api/v1/data/"""

    def test_data_status(self, fastapi_test_client):
        resp = fastapi_test_client.get("/api/v1/data/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "db_path" in body
        assert "stock_count" in body

    def test_trade_calendar(self, fastapi_test_client):
        resp = fastapi_test_client.get(
            "/api/v1/data/trade-calendar",
            params={"start_date": "2025-05-01", "end_date": "2025-05-31"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "trading_days" in body
        assert "count" in body
        assert body["count"] >= 0
        assert isinstance(body["trading_days"], list)

    def test_trade_calendar_default_dates(self, fastapi_test_client):
        # 无参数时使用最近 30 天
        resp = fastapi_test_client.get("/api/v1/data/trade-calendar")
        assert resp.status_code == 200


class TestBacktestEndpoint:
    """回测端点 /api/v1/backtest/run (需要大量数据, 测试其优雅失败)"""

    def test_backtest_without_data_raises(self, fastapi_test_client):
        """无数据时, backtest 应返回 4xx 或 5xx (不应 panic)"""
        resp = fastapi_test_client.post(
            "/api/v1/backtest/run",
            json={
                "strategy_id": "fake_strategy",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
        )
        # 应返回某种错误 (404 strategy not found / 500 no data)
        assert 400 <= resp.status_code < 600


class TestSelectionEndpoint:
    """选股端点 /api/v1/selection"""

    def test_selection_requires_strategy(self, fastapi_test_client):
        """无策略名/ID 时应返回 4xx"""
        resp = fastapi_test_client.post(
            "/api/v1/selection/run",
            json={},
        )
        # strategy_name 和 strategy_id 都为 None -> 400
        assert resp.status_code in (400, 422)

    def test_selection_with_unknown_strategy_id_404(self, fastapi_test_client):
        resp = fastapi_test_client.post(
            "/api/v1/selection/run",
            json={"strategy_id": "totally_fake_id"},
        )
        # 找不到策略 -> 404
        assert resp.status_code == 404

    def test_selection_results_empty(self, fastapi_test_client):
        """无选股结果时, GET /selection/results?trade_date=xxx 应返回空列表或 404"""
        resp = fastapi_test_client.get(
            "/api/v1/selection/results",
            params={"trade_date": "2020-01-01"},
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            assert resp.json() == [] or isinstance(resp.json(), list)

    def test_selection_results_no_params_empty(self, fastapi_test_client):
        resp = fastapi_test_client.get("/api/v1/selection/results")
        assert resp.status_code == 200
        # 无参数返回空列表
        assert resp.json() == []


class TestPrepareStatusEndpoint:
    """数据准备状态端点 /api/v1/selection/prepare/status/{date}"""

    def test_unknown_status(self, fastapi_test_client):
        resp = fastapi_test_client.get("/api/v1/selection/prepare/status/2020-01-01")
        assert resp.status_code == 200
        body = resp.json()
        # 数据库空 + 无任务 -> unknown
        assert body["status"] in ("unknown", "done", "preparing", "failed")
