"""
数据源设置 API

GET  /api/v1/settings/data-sources  — 获取所有数据源配置
PUT  /api/v1/settings/data-sources  — 更新数据源配置
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.settings_store import get_settings_store

logger = logging.getLogger(__name__)

router = APIRouter()


class DataSourceConfig(BaseModel):
    jqdata_token: str = ""
    jqdata_password: str = ""


class DataSourceResponse(BaseModel):
    jqdata_token: str
    jqdata_password: str
    jqdata_configured: bool  # True if both token and password are set


@router.get("/data-sources", response_model=DataSourceResponse, summary="获取数据源配置")
async def get_data_sources():
    """获取所有数据源配置信息（密码返回脱敏值）。"""
    store = get_settings_store()
    token = store.get("jqdata_token")
    password = store.get("jqdata_password")
    configured = bool(token and password)

    # 密码脱敏：已配置则只显示最后2位
    masked_token = token[:6] + "****" + token[-2:] if len(token) > 8 else token
    masked_password = "****" if password else ""

    return DataSourceResponse(
        jqdata_token=masked_token,
        jqdata_password=masked_password,
        jqdata_configured=configured,
    )


@router.put("/data-sources", summary="更新数据源配置")
async def update_data_sources(config: DataSourceConfig):
    """更新数据源配置。传入完整值，空字符串表示不修改对应字段。"""
    store = get_settings_store()
    updates = {}
    if config.jqdata_token:
        updates["jqdata_token"] = config.jqdata_token
    if config.jqdata_password:
        updates["jqdata_password"] = config.jqdata_password
    if updates:
        store.update(updates)
        logger.info(f"Data source config updated: {list(updates.keys())}")
    return {"status": "ok", "updated": list(updates.keys())}