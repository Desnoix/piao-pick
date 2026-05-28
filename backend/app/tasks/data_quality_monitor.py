"""
数据质量巡检任务 / Data Quality Monitor Task

每小时执行一次, 运行四维质量检测, 缓存最新报告供 API 读取。
"""

import logging
import threading

logger = logging.getLogger(__name__)

# In-memory cache — shared across threads
_latest_report: object = None
_lock = threading.Lock()


def get_latest_report() -> object | None:
    """Return the most recent QualityReport (or None)."""
    with _lock:
        return _latest_report


def run_quality_check(trade_date: str | None = None) -> dict:
    """Execute four-dimension quality check and return summary dict.

    Args:
        trade_date: Target date (YYYY-MM-DD). Auto-detected if None.

    Returns:
        Summary dict with success flag, overall_score, dimension breakdown.
    """
    global _latest_report
    logger.info(f"[质量巡检] 开始, trade_date={trade_date or 'auto'}")

    try:
        from app.services.data_quality_service import AlertDispatcher, DataQualityService

        report = DataQualityService().evaluate(trade_date=trade_date)
        AlertDispatcher().dispatch(report)

        with _lock:
            _latest_report = report

        return {
            "success": True,
            "trade_date": report.trade_date,
            "overall_score": report.overall_score,
            "dimensions": {
                d.name: {
                    "score": d.score,
                    "status": d.pass_status,
                    "issue_count": len(d.issues),
                }
                for d in report.dimensions
            },
            "has_critical": report.has_critical(),
            "summary": report.summary,
        }
    except Exception as e:
        logger.error(f"[质量巡检] 失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def format_report_for_api(report: object) -> dict:
    """Convert a QualityReport into a JSON-serialisable dict for API responses.

    Args:
        report: A QualityReport instance (or None).

    Returns:
        Serialisable dict or an error envelope if report is None.
    """
    if report is None:
        return {"error": "no_report", "message": "尚未执行质量检查"}

    # Type-narrow: report is QualityReport at runtime
    return {
        "trade_date": report.trade_date,  # type: ignore[attr-defined]
        "evaluated_at": report.evaluated_at,  # type: ignore[attr-defined]
        "overall_score": report.overall_score,  # type: ignore[attr-defined]
        "summary": report.summary,  # type: ignore[attr-defined]
        "has_critical": report.has_critical(),  # type: ignore[attr-defined]
        "dimensions": [
            {
                "name": d.name,
                "score": d.score,
                "status": d.pass_status,
                "issues": [
                    {
                        "code": i.code,
                        "severity": i.severity.value,
                        "message": i.message,
                        "metric_value": i.metric_value,
                        "threshold": i.threshold,
                        "sample": i.sample,
                    }
                    for i in d.issues
                ],
            }
            for d in report.dimensions  # type: ignore[attr-defined]
        ],
    }
