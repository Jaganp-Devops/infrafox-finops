"""
EC2 utilization-based FinOps rules.

EC2-001: Low average CPU utilization sustained over the lookback window
while the instance runs continuously - a rightsizing/scheduling
candidate. This rule intentionally downgrades confidence when
CloudWatch data is missing or thin, rather than silently skipping or
falsely flagging.
"""
from app.engine.rules import FinOpsRule, Finding, Severity, Confidence, RemediationType
from app.models.resource import Ec2Instance, UtilizationSample

# Rough on-demand hourly pricing for allowed instance types in ap-south-1.
# Used only to estimate potential savings, never presented as guaranteed.
HOURLY_USD_BY_TYPE = {
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    "c7i-flex.large": 0.0848,
    "m7i-flex.large": 0.1008,
}

LOW_CPU_THRESHOLD_PERCENT = 10.0


class LowUtilizationRule(FinOpsRule):
    rule_id = "EC2-001"
    resource_type = "EC2"
    description = "Instance running continuously with sustained low average CPU utilization."

    def evaluate_with_utilization(
        self,
        instances: list[Ec2Instance],
        utilization_by_instance: dict[str, UtilizationSample | None],
    ) -> list[Finding]:
        findings = []

        for inst in instances:
            if inst.state != "running":
                continue

            sample = utilization_by_instance.get(inst.instance_id)

            if sample is None:
                # No CloudWatch data yet - too new, or metrics not populated.
                # Still worth surfacing, but with low confidence and no
                # savings estimate, since we have no evidence to size it.
                findings.append(
                    Finding(
                        rule_id=self.rule_id,
                        resource_id=inst.instance_id,
                        resource_type="EC2",
                        severity=Severity.LOW,
                        confidence=Confidence.LOW,
                        remediation_type=RemediationType.MANUAL_REVIEW,
                        condition_description="No CloudWatch utilization data available yet",
                        evidence={
                            "instance_id": inst.instance_id,
                            "instance_type": inst.instance_type,
                            "state": inst.state,
                            "tags": inst.tags,
                        },
                        recommendation=(
                            "Insufficient utilization history to assess. "
                            "Re-check after the instance has run long enough "
                            "to accumulate CloudWatch metrics."
                        ),
                        estimated_monthly_savings_usd=None,
                    )
                )
                continue

            if sample.average >= LOW_CPU_THRESHOLD_PERCENT:
                continue

            hourly_rate = HOURLY_USD_BY_TYPE.get(inst.instance_type)
            # Estimate: potential savings if scheduled to run ~12h/day instead
            # of 24h/day, a conservative and clearly-labeled assumption.
            estimated_savings = (
                round(hourly_rate * 12 * 30, 2) if hourly_rate is not None else None
            )

            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    resource_id=inst.instance_id,
                    resource_type="EC2",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH if sample.datapoint_count >= 24 else Confidence.MEDIUM,
                    remediation_type=RemediationType.SCHEDULE_CHANGE,
                    condition_description=(
                        f"Average CPU {sample.average}% over {sample.datapoint_count} "
                        f"hourly datapoints, running continuously"
                    ),
                    evidence={
                        "instance_id": inst.instance_id,
                        "instance_type": inst.instance_type,
                        "average_cpu_percent": sample.average,
                        "max_cpu_percent": sample.maximum,
                        "datapoint_count": sample.datapoint_count,
                        "lookback_period_start": sample.period_start.isoformat(),
                        "lookback_period_end": sample.period_end.isoformat(),
                        "tags": inst.tags,
                    },
                    recommendation=(
                        "Consider scheduling this instance to stop outside "
                        "active hours, or evaluate rightsizing to a smaller "
                        "instance type. This is an estimate, not a guarantee - "
                        "verify actual usage patterns before acting."
                    ),
                    estimated_monthly_savings_usd=estimated_savings,
                )
            )

        return findings

    def evaluate(self, resources: list) -> list[Finding]:
        return []
