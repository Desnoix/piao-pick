"""
数据质量 API 端点 / Data Quality API Endpoints

- GET  /latest  — 最近一次评分详情
- POST /run     — 手动触发质量巡检
"""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/latest", summary="获取最新数据质量报告")
async def get_latest_quality():
    """Return the most recent quality report from in-memory cache."""
    from app.tasks.data_quality_monitor import format_report_for_api, get_latest_report

    report = get_latest_report()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="尚未执行质量检查, 请手动触发 POST /data-quality/run",
        )
    return format_report_for_api(report)


@router.post("/run", summary="手动触发质量巡检")
async def trigger_quality_check(trade_date: str | None = None):
    """Run a quality check on demand and return the summary.

    Args:
        trade_date: Optional YYYY-MM-DD. Auto-detect if omitted.
    """
    from app.tasks.data_quality_monitor import run_quality_check

    return run_quality_check(trade_date=trade_date)
