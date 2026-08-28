"""
Tagging/ownership governance rules.

TAG-001: Resource missing Owner or Environment tag - not a cost finding
by itself, but a governance finding. Untaggable resources are exactly
the ones nobody remembers to clean up, and they're invisible to any
cost-allocation or showback effort.
"""
from app.engine.rules import FinOpsRule, Finding, Severity, Confidence, RemediationType
from app.models.resource import Ec2Instance, EbsVolume

REQUIRED_TAGS = ["Owner", "Environment"]


def _missing_tags(tags: dict[str, str]) -> list[str]:
    # Case-insensitive check - "owner" and "Owner" both count as present.
    lower_keys = {k.lower() for k in tags.keys()}
    return [t for t in REQUIRED_TAGS if t.lower() not in lower_keys]


class MissingOwnershipTagsRule(FinOpsRule):
    rule_id = "TAG-001"
    resource_type = "MULTI"
    description = "Resource missing required Owner and/or Environment tags."

    def evaluate_ec2(self, instances: list[Ec2Instance]) -> list[Finding]:
        findings = []
        for inst in instances:
            missing = _missing_tags(inst.tags)
            if not missing:
                continue

            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    resource_id=inst.instance_id,
                    resource_type="EC2",
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                    remediation_type=RemediationType.TAGGING,
                    condition_description=f"Missing tags: {', '.join(missing)}",
                    evidence={
                        "instance_id": inst.instance_id,
                        "current_tags": inst.tags,
                        "missing_tags": missing,
                        "state": inst.state,
                    },
                    recommendation=(
                        f"Add {', '.join(missing)} tag(s) to enable ownership "
                        "tracking and cost allocation for this resource."
                    ),
                    estimated_monthly_savings_usd=None,
                )
            )
        return findings

    def evaluate_ebs(self, volumes: list[EbsVolume]) -> list[Finding]:
        findings = []
        for vol in volumes:
            missing = _missing_tags(vol.tags)
            if not missing:
                continue

            findings.append(
                Finding(
                    rule_id=self.rule_id,
                    resource_id=vol.volume_id,
                    resource_type="EBS",
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                    remediation_type=RemediationType.TAGGING,
                    condition_description=f"Missing tags: {', '.join(missing)}",
                    evidence={
                        "volume_id": vol.volume_id,
                        "current_tags": vol.tags,
                        "missing_tags": missing,
                    },
                    recommendation=(
                        f"Add {', '.join(missing)} tag(s) to enable ownership "
                        "tracking and cost allocation for this resource."
                    ),
                    estimated_monthly_savings_usd=None,
                )
            )
        return findings

    def evaluate(self, resources: list) -> list[Finding]:
        return []
