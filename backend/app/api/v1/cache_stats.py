# -*- coding: utf-8 -*-
"""缓存统计 API"""

from fastapi import APIRouter

from app.services.cache import get_cache_manager

router = APIRouter()


@router.get("/cache-stats")
def get_cache_stats():
    """返回三级缓存的命中统计指标。"""
    cm = get_cache_manager()
    cm.log_stats()
    return cm.get_stats()


@router.post("/cache-clear")
def clear_cache():
    """清空所有缓存。"""
    cm = get_cache_manager()
    cm.clear_all()
    return {"status": "ok", "message": "All cache cleared"}
