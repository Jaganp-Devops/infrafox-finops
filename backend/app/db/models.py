"""
SQLAlchemy ORM models - the persisted shape of scans and findings.
Distinct from the Pydantic models in app/models/ (API/domain shape) by
design: the DB schema and the API contract are allowed to evolve
independently.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id = Column(String, primary_key=True, default=_uuid)
    scan_id = Column(String, unique=True, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=False)
    duration_seconds = Column(Float, nullable=False)
    resources_scanned = Column(Integer, nullable=False)
    findings_count = Column(Integer, nullable=False)
    failed_checks = Column(JSON, default=list)

    findings = relationship("FindingRecord", back_populates="scan_run", cascade="all, delete-orphan")


class FindingRecord(Base):
    __tablename__ = "findings"

    id = Column(String, primary_key=True, default=_uuid)
    scan_run_id = Column(String, ForeignKey("scan_runs.id"), nullable=False, index=True)

    rule_id = Column(String, nullable=False, index=True)
    resource_id = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    confidence = Column(String, nullable=False)
    remediation_type = Column(String, nullable=False)
    condition_description = Column(String, nullable=False)
    evidence = Column(JSON, nullable=False)
    recommendation = Column(String, nullable=False)
    estimated_monthly_savings_usd = Column(Float, nullable=True)
    detected_at = Column(DateTime(timezone=True), nullable=False)

    # Feature #18: historical recommendation tracking. A finding that
    # stops appearing in new scans (e.g. the volume got deleted, as we
    # saw happen live in Phase 2 testing) should be marked resolved, not
    # silently forgotten - this field is what makes that possible.
    status = Column(String, nullable=False, default="open")  # open | acknowledged | resolved
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    scan_run = relationship("ScanRun", back_populates="findings")


class AuditLogEntry(Base):
    """
    Feature #20: audit logging. Records every scan trigger and any future
    remediation action (Phase 5+, human-approved only). This is separate
    from application logs - it's a permanent, queryable record of who/what
    initiated platform actions, not a debugging trace.
    """
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=_uuid)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    action = Column(String, nullable=False)  # e.g. "scan_triggered", "finding_acknowledged"
    actor = Column(String, nullable=False, default="system")  # system | api | username later
    details = Column(JSON, default=dict)

class DailyRunningCost(Base):
    """
    One row per calendar day. Each day, the real EC2 compute cost for
    that day is recorded, along with the running total up to and
    including that day - a genuine, persisted ledger that accumulates
    over time, rather than a value recalculated fresh on every request.
    """
    __tablename__ = "daily_running_costs"

    id = Column(String, primary_key=True, default=_uuid)
    date = Column(String, nullable=False, unique=True, index=True)
    day_cost_usd = Column(Float, nullable=False)
    running_total_usd = Column(Float, nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
