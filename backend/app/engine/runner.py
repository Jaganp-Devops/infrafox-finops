"""
Scan orchestration: fetch all AWS data once, run every rule against it,
collect findings. This is the actual "scan" that Feature #19 (dashboard)
and the audit log will be built on top of.

Deliberately sequential and simple for Phase 2 - no async, no
parallelism yet. Correctness and traceability first; performance
optimization only if it's ever actually needed.
"""
import logging
import time
from datetime import datetime, timezone
from pydantic import BaseModel

from app.aws import ec2_inventory, cloudwatch_metrics
from app.engine.rules import Finding
from app.engine.ebs_rules import UnattachedVolumeRule, StaleAttachmentRule
from app.engine.tag_rules import MissingOwnershipTagsRule
from app.engine.ec2_rules import LowUtilizationRule
from app.engine.eip_rules import UnattachedElasticIpRule

logger = logging.getLogger(__name__)


class ScanResult(BaseModel):
    scan_id: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    resources_scanned: int
    findings_count: int
    failed_checks: list[str]
    findings: list[Finding]


def run_scan() -> ScanResult:
    started_at = datetime.now(timezone.utc)
    start_time = time.monotonic()
    scan_id = started_at.strftime("scan-%Y%m%dT%H%M%SZ")

    findings: list[Finding] = []
    failed_checks: list[str] = []
    resources_scanned = 0

    # --- Data collection phase ---
    try:
        instances = ec2_inventory.list_instances()
        resources_scanned += len(instances)
    except ec2_inventory.Ec2InventoryError as e:
        logger.error("scan_ec2_instances_failed", extra={"extra_fields": {"error": str(e)}})
        failed_checks.append(f"ec2_instances: {e}")
        instances = []

    try:
        volumes = ec2_inventory.list_volumes()
        resources_scanned += len(volumes)
    except ec2_inventory.Ec2InventoryError as e:
        logger.error("scan_ebs_volumes_failed", extra={"extra_fields": {"error": str(e)}})
        failed_checks.append(f"ebs_volumes: {e}")
        volumes = []

    try:
        eips = ec2_inventory.list_elastic_ips()
        resources_scanned += len(eips)
    except ec2_inventory.Ec2InventoryError as e:
        logger.error("scan_eips_failed", extra={"extra_fields": {"error": str(e)}})
        failed_checks.append(f"elastic_ips: {e}")
        eips = []

    # CloudWatch utilization - fetched per running instance, individually
    # fault-tolerant so one bad instance doesn't abort the whole scan.
    utilization_by_instance: dict[str, object] = {}
    for inst in instances:
        if inst.state != "running":
            continue
        try:
            utilization_by_instance[inst.instance_id] = (
                cloudwatch_metrics.get_ec2_cpu_utilization(inst.instance_id)
            )
        except cloudwatch_metrics.CloudWatchError as e:
            logger.error(
                "scan_cloudwatch_failed",
                extra={"extra_fields": {"instance_id": inst.instance_id, "error": str(e)}},
            )
            failed_checks.append(f"cloudwatch:{inst.instance_id}: {e}")
            utilization_by_instance[inst.instance_id] = None

    # --- Rule evaluation phase ---
    findings.extend(UnattachedVolumeRule().evaluate(volumes))
    findings.extend(StaleAttachmentRule().evaluate_with_instances(volumes, instances))
    findings.extend(MissingOwnershipTagsRule().evaluate_ec2(instances))
    findings.extend(MissingOwnershipTagsRule().evaluate_ebs(volumes))
    findings.extend(LowUtilizationRule().evaluate_with_utilization(instances, utilization_by_instance))
    findings.extend(UnattachedElasticIpRule().evaluate(eips))

    finished_at = datetime.now(timezone.utc)
    duration = round(time.monotonic() - start_time, 2)

    logger.info(
        "scan_complete",
        extra={
            "extra_fields": {
                "scan_id": scan_id,
                "duration_seconds": duration,
                "resources_scanned": resources_scanned,
                "findings_count": len(findings),
                "failed_checks_count": len(failed_checks),
            }
        },
    )

    return ScanResult(
        scan_id=scan_id,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration,
        resources_scanned=resources_scanned,
        findings_count=len(findings),
        failed_checks=failed_checks,
        findings=findings,
    )
