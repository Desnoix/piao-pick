"""
数据质量评分引擎 + 告警分发 / Data Quality Scoring Engine + Alert Dispatch

四维检测: 完整性 (Completeness), 一致性 (Consistency), 准确性 (Accuracy), 时效性 (Timeliness)。
每项 0-100 分, 整体取均值。严重问题触发 CRITICAL/WARNING/INFO 分级告警。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlmodel import func, select, text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class QualityIssue:
    code: str
    severity: Severity
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    sample: list[str] = field(default_factory=list)


@dataclass
class QualityDimension:
    name: str
    score: float
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def pass_status(self) -> str:
        return "PASS" if self.score >= 80.0 else ("WARN" if self.score >= 60.0 else "FAIL")


@dataclass
class QualityReport:
    trade_date: str
    evaluated_at: str
    overall_score: float
    dimensions: list[QualityDimension]
    summary: str

    def has_critical(self) -> bool:
        return any(i.severity == Severity.CRITICAL for d in self.dimensions for i in d.issues)

    def critical_issues(self) -> list[QualityIssue]:
        return [i for d in self.dimensions for i in d.issues if i.severity == Severity.CRITICAL]


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------


class DataQualityService:
    """四维数据质量评分 / Four-dimension data quality scoring."""

    THRESHOLDS = {
        "completeness_critical": 0.70,
        "completeness_warning": 0.85,
        "consistency_critical": 0.02,
        "consistency_warning": 0.005,
        "accuracy_critical": 0.02,
        "accuracy_warning": 0.005,
        "timeliness_max_hours": 26,
        "timeliness_warn_hours": 6,
    }

    def __init__(self, db: Optional["DatabaseManager"] = None):  # noqa: F821
        from app.database import get_db

        self.db = db or get_db()

    # ---- Public API -------------------------------------------------------

    def evaluate(self, trade_date: str | None = None) -> QualityReport:
        """Run all four quality checks and produce an overall report."""
        if trade_date is None:
            trade_date = self._get_latest_kline_date() or datetime.now().strftime("%Y-%m-%d")

        dims = [
            self._check_completeness(trade_date),
            self._check_consistency(trade_date),
            self._check_accuracy(trade_date),
            self._check_timeliness(trade_date),
        ]

        overall = sum(d.score for d in dims) / len(dims)
        pass_count = sum(1 for d in dims if d.pass_status == "PASS")
        crit_count = sum(1 for d in dims for i in d.issues if i.severity == Severity.CRITICAL)

        if crit_count > 0:
            summary = f"质量异常: {crit_count} 个严重问题, {pass_count}/4 项通过"
        elif pass_count < 4:
            summary = f"质量告警: {4 - pass_count} 项未通过, 整体评分 {overall:.1f}"
        else:
            summary = f"质量正常: 全项通过, 整体评分 {overall:.1f}"

        return QualityReport(
            trade_date=trade_date,
            evaluated_at=datetime.now().isoformat(),
            overall_score=round(overall, 2),
            dimensions=dims,
            summary=summary,
        )

    # ---- Dimension checks -------------------------------------------------

    def _check_completeness(self, trade_date: str) -> QualityDimension:
        """K线覆盖率: kline 当天记录数 / stock_info 非停牌总数."""
        from app.models.kline import Kline
        from app.models.stock_info import StockInfo

        issues: list[QualityIssue] = []
        with self.db.get_session() as session:
            total = (
                session.exec(
                    select(func.count()).select_from(StockInfo).where(StockInfo.is_suspended == False)  # noqa: E712
                ).one()
                or 0
            )
            covered = (
                session.exec(
                    select(func.count(func.distinct(Kline.ts_code))).where(Kline.trade_date == trade_date)
                ).one()
                or 0
            )

        cov = covered / total if total > 0 else 0.0
        score = min(100.0, cov * 110)

        if cov < self.THRESHOLDS["completeness_critical"]:
            issues.append(
                QualityIssue(
                    "MISSING_DATA_CRITICAL",
                    Severity.CRITICAL,
                    f"K线覆盖率仅 {cov * 100:.1f}% ({covered}/{total})",
                    "completeness",
                    round(cov * 100, 2),
                    70.0,
                )
            )
        elif cov < self.THRESHOLDS["completeness_warning"]:
            samples = self._missing_samples(trade_date, 5)
            issues.append(
                QualityIssue(
                    "MISSING_DATA_WARNING",
                    Severity.WARNING,
                    f"K线覆盖率 {cov * 100:.1f}% ({covered}/{total})",
                    "completeness",
                    round(cov * 100, 2),
                    85.0,
                    sample=samples,
                )
            )

        return QualityDimension("completeness", round(score, 2), issues)

    def _check_consistency(self, trade_date: str) -> QualityDimension:
        """检测 (ts_code, trade_date) 重复记录."""
        from app.models.kline import Kline

        issues: list[QualityIssue] = []
        with self.db.get_session() as session:
            dup_stmt = text(
                "SELECT COUNT(*) FROM ("
                "  SELECT ts_code, trade_date, COUNT(*) as cnt"
                "  FROM kline_daily WHERE trade_date = :trade_date"
                "  GROUP BY ts_code, trade_date HAVING cnt > 1"
                ")"
            )
            dup_count = session.exec(dup_stmt, params={"trade_date": trade_date}).one()[0] or 0

            total = (
                session.exec(select(func.count()).select_from(Kline).where(Kline.trade_date == trade_date)).one() or 1
            )

        dup_rate = dup_count / total
        score = max(0.0, 100.0 - dup_rate * 1000)

        if dup_rate > self.THRESHOLDS["consistency_critical"]:
            issues.append(
                QualityIssue(
                    "DUPLICATE_CRITICAL",
                    Severity.CRITICAL,
                    f"重复率 {dup_rate * 100:.2f}% ({dup_count} 条)",
                    "consistency",
                    round(dup_rate * 100, 4),
                    2.0,
                )
            )
        elif dup_rate > self.THRESHOLDS["consistency_warning"]:
            issues.append(
                QualityIssue(
                    "DUPLICATE_WARNING",
                    Severity.WARNING,
                    f"重复率 {dup_rate * 100:.2f}% ({dup_count} 条)",
                    "consistency",
                    round(dup_rate * 100, 4),
                    0.5,
                )
            )

        return QualityDimension("consistency", round(score, 2), issues)

    def _check_accuracy(self, trade_date: str) -> QualityDimension:
        """价格/成交量异常值检测."""
        from app.models.kline import Kline

        with self.db.get_session() as session:
            klines = session.exec(select(Kline).where(Kline.trade_date == trade_date)).all()

        if not klines:
            return QualityDimension(
                "accuracy",
                0.0,
                [
                    QualityIssue(
                        "NO_DATA",
                        Severity.INFO,
                        "该日期无K线数据",
                        "accuracy",
                        0.0,
                        0.0,
                    )
                ],
            )

        anomalies: list[tuple[str, str]] = [
            (k.ts_code, reason) for k in klines if (reason := self._check_kline(k)) is not None
        ]
        error_rate = len(anomalies) / len(klines)
        score = max(0.0, 100.0 - error_rate * 500)
        samples = [code for code, _ in anomalies[:5]]
        issues: list[QualityIssue] = []

        if error_rate > self.THRESHOLDS["accuracy_critical"]:
            issues.append(
                QualityIssue(
                    "ANOMALY_CRITICAL",
                    Severity.CRITICAL,
                    f"异常率 {error_rate * 100:.2f}% ({len(anomalies)}/{len(klines)})",
                    "accuracy",
                    round(error_rate * 100, 2),
                    2.0,
                    sample=samples,
                )
            )
        elif error_rate > self.THRESHOLDS["accuracy_warning"]:
            issues.append(
                QualityIssue(
                    "ANOMALY_WARNING",
                    Severity.WARNING,
                    f"异常率 {error_rate * 100:.2f}%",
                    "accuracy",
                    round(error_rate * 100, 2),
                    0.5,
                    sample=samples,
                )
            )

        return QualityDimension("accuracy", round(score, 2), issues)

    def _check_timeliness(self, trade_date: str) -> QualityDimension:
        """数据新鲜度: stock_info.updated_at 与当前时间差距."""
        from app.models.stock_info import StockInfo

        issues: list[QualityIssue] = []
        with self.db.get_session() as session:
            latest = session.exec(select(func.max(StockInfo.updated_at))).first()

        if not latest:
            return QualityDimension(
                "timeliness",
                50.0,
                [
                    QualityIssue(
                        "NO_UPDATE_TS",
                        Severity.WARNING,
                        "无更新时间戳",
                        "timeliness",
                        float("inf"),
                        6.0,
                    )
                ],
            )

        try:
            update_dt = datetime.fromisoformat(latest)
        except (ValueError, TypeError):
            return QualityDimension("timeliness", 30.0, [])

        delay_h = (datetime.now() - update_dt).total_seconds() / 3600
        score = max(0.0, 100.0 - max(0, delay_h - 24) * 5)
        is_weekday = datetime.now().weekday() < 5

        if delay_h > self.THRESHOLDS["timeliness_max_hours"] and is_weekday:
            issues.append(
                QualityIssue(
                    "STALE_CRITICAL",
                    Severity.CRITICAL,
                    f"延迟 {delay_h:.1f}h, 最近更新: {latest}",
                    "timeliness",
                    round(delay_h, 2),
                    26.0,
                )
            )
        elif delay_h > self.THRESHOLDS["timeliness_warn_hours"] and is_weekday:
            issues.append(
                QualityIssue(
                    "STALE_WARNING",
                    Severity.WARNING,
                    f"延迟 {delay_h:.1f}h",
                    "timeliness",
                    round(delay_h, 2),
                    6.0,
                )
            )

        return QualityDimension("timeliness", round(score, 2), issues)

    # ---- Helpers ----------------------------------------------------------

    def _get_latest_kline_date(self) -> str | None:
        from app.models.kline import Kline

        with self.db.get_session() as session:
            return session.exec(select(Kline.trade_date).order_by(Kline.trade_date.desc()).limit(1)).first()

    def _missing_samples(self, trade_date: str, limit: int) -> list[str]:
        """Return up to `limit` stock codes missing kline on `trade_date`."""
        from app.models.kline import Kline
        from app.models.stock_info import StockInfo

        with self.db.get_session() as session:
            kline_codes_subq = select(Kline.ts_code).where(Kline.trade_date == trade_date)
            return list(
                session.exec(
                    select(StockInfo.ts_code)
                    .where(StockInfo.is_suspended == False)  # noqa: E712
                    .where(~StockInfo.ts_code.in_(kline_codes_subq))  # type: ignore[union-attr]
                    .limit(limit)
                ).all()
            )

    @staticmethod
    def _check_kline(k) -> str | None:  # type: ignore[type-arg]
        """Validate a single Kline record. Return error code or None."""
        if k.close is None or k.close <= 0:
            return "CLOSE_INVALID"
        for name, val in [("open", k.open), ("high", k.high), ("low", k.low)]:
            if val is not None and val <= 0:
                return f"{name.upper()}_INVALID"
        if k.low is not None and k.high is not None and k.low > k.high:
            return "LOW_GT_HIGH"
        if k.open is not None and k.low is not None and k.high is not None:
            if k.open < k.low or k.open > k.high:
                return "OPEN_OUT_OF_RANGE"
        if k.volume is not None and k.volume < 0:
            return "VOLUME_NEGATIVE"
        return None


# ---------------------------------------------------------------------------
# Alert dispatcher
# ---------------------------------------------------------------------------


class AlertDispatcher:
    """Structured log + optional webhook (Slack / 企业微信 / generic)."""

    def __init__(self) -> None:
        from app.config import get_config

        self.config = get_config()
        self.webhook_url: str | None = getattr(self.config, "dq_webhook_url", None)
        self.webhook_type: str = getattr(self.config, "dq_webhook_type", "generic")

    def dispatch(self, report: QualityReport) -> None:
        self._log_report(report)
        if report.has_critical() and self.webhook_url:
            self._send_webhook(report)

    # ---- Structured log ---------------------------------------------------

    def _log_report(self, report: QualityReport) -> None:
        for dim in report.dimensions:
            for issue in dim.issues:
                fn = {
                    Severity.CRITICAL: logger.error,
                    Severity.WARNING: logger.warning,
                    Severity.INFO: logger.info,
                }.get(issue.severity, logger.info)
                extra = f" | 示例: {issue.sample}" if issue.sample else ""
                fn(f"[数据质量:{dim.name}] [{issue.severity.value}] {issue.message}{extra}")

        logger.info(f"[数据质量] 评分: {report.overall_score:.1f} | {report.trade_date} | {report.summary}")

    # ---- Webhook ----------------------------------------------------------

    def _send_webhook(self, report: QualityReport) -> None:
        import httpx

        crit = report.critical_issues()

        if self.webhook_type == "slack":
            payload = {
                "text": f":red_circle: *数据质量严重告警*\n{report.summary}",
                "attachments": [
                    {
                        "color": "#FF0000",
                        "fields": [{"title": i.code, "value": i.message, "short": False} for i in crit[:5]],
                    }
                ],
            }
        elif self.webhook_type == "wechat":
            content = f"数据质量严重告警\n评分: {report.overall_score:.1f}\n{report.summary}\n"
            for i in crit[:3]:
                content += f"* [{i.severity.value}] {i.code}: {i.message}\n"
            payload = {"msgtype": "text", "text": {"content": content}}
        else:
            payload = {
                "source": "piao-pick",
                "level": "CRITICAL",
                "summary": report.summary,
                "overall_score": report.overall_score,
                "trade_date": report.trade_date,
                "issues": [
                    {
                        "code": i.code,
                        "severity": i.severity.value,
                        "message": i.message,
                    }
                    for i in crit
                ],
            }

        try:
            resp = httpx.post(
                self.webhook_url,  # type: ignore[arg-type]
                json=payload,
                timeout=10,
            )
            if resp.status_code in (200, 204):
                logger.info("[数据质量] Webhook 推送成功")
            else:
                logger.warning(f"[数据质量] Webhook 失败: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"[数据质量] Webhook 异常: {e}")
