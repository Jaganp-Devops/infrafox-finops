"""
Persistence operations. Keeps SQLAlchemy query logic out of the API
layer and out of the rule engine - the engine stays AWS-only and
side-effect-free, this module is the only place scan results get written
to or read from the database.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db.models import ScanRun, FindingRecord, AuditLogEntry
from app.engine.runner import ScanResult
from app.engine.rules import Finding

logger = logging.getLogger(__name__)


def save_scan_result(db: Session, result: ScanResult) -> ScanRun:
    """
    Persists a completed scan and its findings. Also implements the
    "resolve stale findings" logic: any (rule_id, resource_id) pair that
    was open in the previous scan but does not appear in this one is
    marked resolved - covering exactly the case seen live in testing,
    where a terminated instance's volume findings correctly disappeared.
    """
    scan_run = ScanRun(
        scan_id=result.scan_id,
        started_at=result.started_at,
        finished_at=result.finished_at,
        duration_seconds=result.duration_seconds,
        resources_scanned=result.resources_scanned,
        findings_count=result.findings_count,
        failed_checks=result.failed_checks,
    )
    db.add(scan_run)
    db.flush()  # get scan_run.id without committing yet

    current_keys: set[tuple[str, str]] = set()
    for f in result.findings:
        current_keys.add((f.rule_id, f.resource_id))
        db.add(
            FindingRecord(
                scan_run_id=scan_run.id,
                rule_id=f.rule_id,
                resource_id=f.resource_id,
                resource_type=f.resource_type,
                severity=f.severity.value,
                confidence=f.confidence.value,
                remediation_type=f.remediation_type.value,
                condition_description=f.condition_description,
                evidence=f.evidence,
                recommendation=f.recommendation,
                estimated_monthly_savings_usd=f.estimated_monthly_savings_usd,
                detected_at=f.detected_at,
                status="open",
            )
        )

    _resolve_stale_findings(db, current_keys)

    db.add(
        AuditLogEntry(
            action="scan_completed",
            actor="system",
            details={
                "scan_id": result.scan_id,
                "findings_count": result.findings_count,
                "failed_checks_count": len(result.failed_checks),
            },
        )
    )

    db.commit()
    db.refresh(scan_run)
    return scan_run


def _resolve_stale_findings(db: Session, current_keys: set[tuple[str, str]]) -> None:
    """
    Marks findings resolved if their (rule_id, resource_id) pair no
    longer appears in the latest scan. Only considers findings that are
    still 'open' or 'acknowledged' - already-resolved ones are untouched.
    """
    open_findings = (
        db.query(FindingRecord)
        .filter(FindingRecord.status.in_(["open", "acknowledged"]))
        .all()
    )

    resolved_count = 0
    for finding in open_findings:
        key = (finding.rule_id, finding.resource_id)
        if key not in current_keys:
            finding.status = "resolved"
            finding.resolved_at = datetime.now(timezone.utc)
            resolved_count += 1

    if resolved_count:
        logger.info(
            "findings_auto_resolved",
            extra={"extra_fields": {"resolved_count": resolved_count}},
        )


def get_latest_scan(db: Session) -> ScanRun | None:
    return db.query(ScanRun).order_by(ScanRun.started_at.desc()).first()


def get_scan_history(db: Session, limit: int = 20) -> list[ScanRun]:
    return db.query(ScanRun).order_by(ScanRun.started_at.desc()).limit(limit).all()


def get_open_findings(db: Session) -> list[FindingRecord]:
    return (
        db.query(FindingRecord)
        .filter(FindingRecord.status == "open")
        .order_by(FindingRecord.detected_at.desc())
        .all()
    )


def get_finding_history(db: Session, resource_id: str) -> list[FindingRecord]:
    """All findings, across all scans, for a single resource - the drill-down view."""
    return (
        db.query(FindingRecord)
        .filter(FindingRecord.resource_id == resource_id)
        .order_by(FindingRecord.detected_at.desc())
        .all()
    )
