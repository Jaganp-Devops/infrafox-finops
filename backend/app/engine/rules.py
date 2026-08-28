"""
Core FinOps rule engine types. A "rule" is a deterministic, explainable
check against real AWS data - never a guess, never hard-coded advice.
Every finding a rule produces must carry the evidence that justifies it.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Confidence(str, Enum):
    LOW = "low"       # incomplete data, e.g. no CloudWatch datapoints yet
    MEDIUM = "medium"
    HIGH = "high"      # full data coverage supports the finding


class RemediationType(str, Enum):
    MANUAL_REVIEW = "manual_review"
    SCHEDULE_CHANGE = "schedule_change"
    RIGHTSIZING = "rightsizing"
    DELETE_CANDIDATE = "delete_candidate"
    TAGGING = "tagging"


class Finding(BaseModel):
    """
    A single output of a rule being evaluated against a single resource.
    This is the atomic unit the dashboard/API surfaces later - every
    field here exists because a rule engine that says 'this is waste'
    without saying why is not trustworthy enough to act on.
    """
    rule_id: str
    resource_id: str
    resource_type: str
    severity: Severity
    confidence: Confidence
    remediation_type: RemediationType
    condition_description: str
    evidence: dict[str, Any]
    recommendation: str
    estimated_monthly_savings_usd: float | None = None
    detected_at: datetime = datetime.now(timezone.utc)


class FinOpsRule:
    """
    Base class every rule implements. Rules are deliberately simple,
    synchronous, and side-effect-free: given resource data, return zero
    or more Findings. No rule ever calls a mutating AWS API.
    """
    rule_id: str = "UNSET"
    resource_type: str = "UNSET"
    description: str = ""

    def evaluate(self, resources: list) -> list[Finding]:
        raise NotImplementedError
