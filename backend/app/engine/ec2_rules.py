"""
EC2 utilization-based FinOps rules.

EC2-001: Low average CPU utilization sustained over the lookback window
while the instance runs continuously - a rightsizing/scheduling
candidate. This rule intentionally downgrades confidence when
CloudWatch data is missing or thin, rather than silently skipping or
falsely flagging.
"""
from app.engine.rules import Confidence, Finding, FinOpsRule, RemediationType, Severity
from app.models.resource import Ec2Instance, UtilizationSample
from app.aws.pricing import get_ec2_hourly_price, PricingError
from app.aws.cloudwatch_metrics import get_ec2_cpu_utilization_today

# Fallback rates, used only if the live Pricing API call fails.
# Kept as a safety net, not the primary source of truth anymore.
HOURLY_USD_BY_TYPE = {
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    "c7i-flex.large": 0.0848,
    "m7i-flex.large": 0.1008,
}

LOW_CPU_THRESHOLD_PERCENT = 10.0
LOOKBACK_DAYS = 7


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

            try:
                hourly_rate = get_ec2_hourly_price(inst.instance_type, region="ap-south-1")
            except PricingError:
                hourly_rate = None

            if hourly_rate is None:
                hourly_rate = HOURLY_USD_BY_TYPE.get(inst.instance_type)

            honest_avg_hours_per_day = round(sample.datapoint_count / LOOKBACK_DAYS, 1)

            today_cost = (
                round(hourly_rate * honest_avg_hours_per_day, 2)
                if hourly_rate is not None else None
            )
            usage_this_month = (
                round(hourly_rate * honest_avg_hours_per_day * 31, 2)
                if hourly_rate is not None else None
            )
            total_current_month = (
                round(hourly_rate * 24 * 31, 2)
                if hourly_rate is not None else None
            )

            try:
                today_cpu = get_ec2_cpu_utilization_today(inst.instance_id)
            except Exception:
                today_cpu = None

            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    resource_id=inst.instance_id,
                    resource_type="EC2",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH if sample.datapoint_count >= 24 else Confidence.MEDIUM,
                    remediation_type=RemediationType.SCHEDULE_CHANGE,
                    condition_description=(
                        f"Average CPU: {sample.average}% (calculated over {LOOKBACK_DAYS} days) | "
                        f"Today avg CPU: {today_cpu if today_cpu is not None else 'N/A'}% | "
                        f"Avg runtime: {honest_avg_hours_per_day}h/day (calculated over {LOOKBACK_DAYS} days)"
                    ),
                    evidence={
                        "instance_id": inst.instance_id,
                        "instance_type": inst.instance_type,
                        "average_cpu_percent": sample.average,
                        "today_avg_cpu_percent": today_cpu,
                        "max_cpu_percent": sample.maximum,
                        "datapoint_count": sample.datapoint_count,
                        "honest_avg_hours_per_day": honest_avg_hours_per_day,
                        "hourly_rate_usd": hourly_rate,
                        "today_cost_usd": today_cost,
                        "usage_this_month_usd": usage_this_month,
                        "total_current_month_usd": total_current_month,
                        "lookback_period_start": sample.period_start.isoformat(),
                        "lookback_period_end": sample.period_end.isoformat(),
                        "tags": inst.tags,
                    },
                    recommendation=(
                        f"Today cost: ${today_cost} | "
                        f"Usage for this month: ${usage_this_month} | "
                        f"Total for current month: ${total_current_month}"
                    ),
                    estimated_monthly_savings_usd=total_current_month,
                )
            )

        return findings

    def evaluate(self, resources: list) -> list[Finding]:
        return []
