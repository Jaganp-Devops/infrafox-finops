"""
EIP-001: Unattached Elastic IP - direct waste. AWS bills for Elastic IPs
that are allocated but not associated with a running instance, starting
from minute one. This is one of the most clear-cut waste patterns in
AWS, since there's no ambiguity about whether it's "in use."
"""
from app.engine.rules import Confidence, Finding, FinOpsRule, RemediationType, Severity
from app.models.resource import ElasticIp

# Flat monthly cost for an unattached EIP in most regions, including
# ap-south-1, under the post-Feb-2024 all-IPv4-addresses pricing model.
UNATTACHED_EIP_USD_PER_HOUR = 0.005
HOURS_PER_MONTH = 730


class UnattachedElasticIpRule(FinOpsRule):
    rule_id = "EIP-001"
    resource_type = "EIP"
    description = "Elastic IP allocated but not associated with any instance."

    def evaluate(self, resources: list[ElasticIp]) -> list[Finding]:
        findings = []
        for eip in resources:
            if eip.associated_instance_id is not None:
                continue

            monthly_cost = round(UNATTACHED_EIP_USD_PER_HOUR * HOURS_PER_MONTH, 2)

            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    resource_id=eip.allocation_id,
                    resource_type="EIP",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    remediation_type=RemediationType.DELETE_CANDIDATE,
                    condition_description="Elastic IP not associated with any instance",
                    evidence={
                        "allocation_id": eip.allocation_id,
                        "public_ip": eip.public_ip,
                        "tags": eip.tags,
                    },
                    recommendation=(
                        "Release this Elastic IP if it is no longer needed. "
                        "Unattached EIPs bill continuously with zero functional use."
                    ),
                    estimated_monthly_savings_usd=monthly_cost,
                )
            )
        return findings
