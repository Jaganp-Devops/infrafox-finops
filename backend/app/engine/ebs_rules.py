"""
EBS-related FinOps rules.

EBS-001: Unattached volume - pure waste, billing with zero use.
EBS-002: Volume attached to a stopped instance - the instance isn't
         running, but the volume still bills 24/7. Very common,
         very easy to overlook pattern.
"""
from datetime import datetime, timezone

from app.engine.rules import Confidence, Finding, FinOpsRule, RemediationType, Severity
from app.models.resource import EbsVolume, Ec2Instance

# gp3 pricing in ap-south-1 (Mumbai), approximate, per GB-month.
# Kept as a constant here rather than hardcoded inline so it's one place
# to update if AWS pricing changes.
GP3_USD_PER_GB_MONTH = 0.08


class UnattachedVolumeRule(FinOpsRule):
    rule_id = "EBS-001"
    resource_type = "EBS"
    description = "Unattached EBS volume - billed but not in use by any instance."

    def evaluate(self, resources: list[EbsVolume]) -> list[Finding]:
        findings = []
        for vol in resources:
            if vol.attached_instance_id is not None:
                continue

            age_days = (datetime.now(timezone.utc) - vol.create_time).days
            monthly_cost = round(vol.size_gb * GP3_USD_PER_GB_MONTH, 2)

            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    resource_id=vol.volume_id,
                    resource_type="EBS",
                    severity=Severity.MEDIUM if age_days > 7 else Severity.LOW,
                    confidence=Confidence.HIGH,
                    remediation_type=RemediationType.DELETE_CANDIDATE,
                    condition_description=f"Volume unattached for {age_days} days",
                    evidence={
                        "volume_id": vol.volume_id,
                        "size_gb": vol.size_gb,
                        "volume_type": vol.volume_type,
                        "age_days": age_days,
                        "tags": vol.tags,
                    },
                    recommendation=(
                        "Review this volume and delete it if no longer needed. "
                        "Unattached volumes provide no value while continuing to bill."
                    ),
                    estimated_monthly_savings_usd=monthly_cost,
                )
            )
        return findings


class StaleAttachmentRule(FinOpsRule):
    rule_id = "EBS-002"
    resource_type = "EBS"
    description = "Volume attached to an instance that has been stopped for an extended period."

    STOPPED_THRESHOLD_DAYS = 3

    def evaluate_with_instances(
        self, volumes: list[EbsVolume], instances: list[Ec2Instance]
    ) -> list[Finding]:
        findings = []
        instances_by_id = {i.instance_id: i for i in instances}

        for vol in volumes:
            if vol.attached_instance_id is None:
                continue

            instance = instances_by_id.get(vol.attached_instance_id)
            if instance is None or instance.state != "stopped":
                continue

            monthly_cost = round(vol.size_gb * GP3_USD_PER_GB_MONTH, 2)

            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    resource_id=vol.volume_id,
                    resource_type="EBS",
                    severity=Severity.LOW,
                    confidence=Confidence.MEDIUM,
                    remediation_type=RemediationType.MANUAL_REVIEW,
                    condition_description=(
                        f"Volume attached to stopped instance {instance.instance_id}"
                    ),
                    evidence={
                        "volume_id": vol.volume_id,
                        "size_gb": vol.size_gb,
                        "attached_instance_id": instance.instance_id,
                        "instance_state": instance.state,
                        "instance_tags": instance.tags,
                        "volume_tags": vol.tags,
                    },
                    recommendation=(
                        "Instance is stopped but its EBS volume still bills. "
                        "Confirm whether the instance is still needed; if not, "
                        "terminate it (which will also remove the volume if "
                        "delete_on_termination is set) or snapshot and delete."
                    ),
                    estimated_monthly_savings_usd=monthly_cost,
                )
            )
        return findings

    def evaluate(self, resources: list) -> list[Finding]:
        # Not used directly - this rule needs both volumes and instances,
        # so evaluate_with_instances() is called explicitly by the runner.
        return []
