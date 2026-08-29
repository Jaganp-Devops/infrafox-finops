# FinOps Rule Engine

## Design principle

Every rule is a plain Python class implementing a single `evaluate()` method: given real AWS resource data, return zero or more `Finding` objects. No rule calls a mutating AWS API. No rule's output is a free-text guess — every finding carries an `evidence` dictionary containing the exact data that justified it, so a human reviewing the finding can verify it independently rather than trust it blindly.

## The `Finding` model

Every rule produces findings shaped identically:

```python
class Finding(BaseModel):
    rule_id: str
    resource_id: str
    resource_type: str
    severity: Severity          # low | medium | high
    confidence: Confidence      # low | medium | high
    remediation_type: RemediationType
    condition_description: str
    evidence: dict[str, Any]
    recommendation: str
    estimated_monthly_savings_usd: float | None
    detected_at: datetime
```

**Confidence is not decoration.** A rule downgrades confidence honestly when its evidence is incomplete — for example, `EC2-001` reports `low` confidence with no savings estimate when an instance is too new to have accumulated meaningful CloudWatch history, rather than either skipping the resource silently or asserting a conclusion the data doesn't support.

## Rules

### `EC2-001` — Sustained low utilization

**Checks**: instances in `running` state with average CPU utilization below 10% over a 14-day lookback window (via CloudWatch `GetMetricStatistics`).

**Evidence captured**: instance ID, type, average/max CPU, CloudWatch datapoint count, lookback window boundaries, current tags.

**Confidence logic**: `high` if 24+ hourly datapoints exist; `medium` otherwise. `low` confidence (no savings estimate) if CloudWatch has no datapoints at all yet.

**Savings estimate**: assumes scheduling the instance to run ~12h/day instead of 24h/day — a conservative, explicitly-labeled assumption, not a guarantee.

**Real example**: this rule correctly flagged the project's own `infrafox-app` instance at 0.93–1.25% average CPU — a legitimate finding, since the instance genuinely is idle almost all the time outside of active development.

### `EBS-001` — Unattached volume

**Checks**: EBS volumes with no `attached_instance_id`.

**Evidence captured**: volume ID, size, type, age in days, tags.

**Severity**: `medium` if unattached for more than 7 days, `low` otherwise — a volume unattached for an hour during a migration is different from one abandoned for months.

**Savings estimate**: `size_gb × $0.08/GB-month` (gp3 pricing, ap-south-1).

### `EBS-002` — Volume attached to a stopped instance

**Checks**: volumes attached to an instance whose state is `stopped`.

**Why this matters**: EBS volumes bill continuously regardless of whether the attached instance is running — a very common, easy-to-overlook waste pattern. Stopping an instance to save compute cost does not stop the storage cost.

**Confidence**: `medium` — deliberately not `high`, since a recently-stopped instance might be intentionally paused rather than abandoned; this is a prompt for human review, not a delete recommendation.

### `TAG-001` — Missing ownership/environment tags

**Checks**: EC2 instances and EBS volumes missing an `Owner` or `Environment` tag (case-insensitive match).

**Why this matters**: untagged resources are exactly the ones nobody remembers to review or retire, and they're invisible to any cost-allocation or showback effort.

**Real example**: during development, this rule correctly identified a genuinely untagged, orphaned EBS volume left over from earlier account exploration — a real governance gap, not a synthetic test case.

**Remediation type**: `tagging` — never a delete candidate on its own; missing tags are a visibility problem, not evidence of waste by themselves.

### `EIP-001` — Unattached Elastic IP

**Checks**: Elastic IPs with no `associated_instance_id`.

**Why this matters**: unlike most AWS resources, an unattached Elastic IP bills from the moment it's allocated, with zero grace period. This is one of the most unambiguous waste patterns in AWS — there's no legitimate reason for a genuinely unattached EIP to exist for long.

**Savings estimate**: flat rate, `$0.005/hour × 730 hours/month` ≈ $3.65/month per unattached IP.

## Historical tracking (Feature #18)

Findings persist across scans. A finding that stops appearing in a fresh scan — because the underlying resource was fixed, deleted, or re-tagged — is marked `resolved` in the database rather than silently disappearing. This was verified working correctly during development: when a stale, untagged EC2 instance was terminated (with its EBS volume set to `delete_on_termination`), the next scan correctly showed zero findings for that resource, and the historical record shows it as resolved rather than as if it never existed.

## What this rule engine deliberately does not do

- **No automatic remediation.** Every finding ends in a human decision. See `remediation_type` on each finding — even `delete_candidate` findings require a person to act.
- **No AI/LLM in the finding-generation path.** See `docs/ARCHITECTURE.md` for the reasoning.
- **No guaranteed savings claims.** Every savings figure is explicitly labeled an estimate.
