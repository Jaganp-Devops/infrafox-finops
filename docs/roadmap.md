# Roadmap

## What's built (see README for the full current-state summary)

Infrastructure (Terraform), backend + AWS integration, deterministic rule engine, persistence (Postgres), React dashboard, containerization (Docker + Compose), Nginx + HTTPS (Let's Encrypt), DuckDNS automation, and a full CI/CD pipeline (GitHub Actions: lint, test, security scan, build, deploy, health check).

## Deliberately deferred, and why

### Remote Terraform state backend (S3 + DynamoDB)

Would prevent the class of state-drift issue documented in `docs/incidents.md`. Deferred because it adds cost and setup complexity that only pays off with multiple contributors or automated `apply` from CI — neither applies yet. Worth adding the moment either changes.

### CI-driven `terraform apply`

The pipeline currently only *validates* Terraform (`fmt`, `init`, `validate`) — it never runs `plan` or `apply` against real infrastructure, because doing so safely requires the remote state backend above. Applying infrastructure changes remains a deliberate, human-run step.

### Scheduled/automatic remediation

The rule engine only ever recommends; nothing is auto-remediated. A production extension would add an approval workflow: a human reviews a finding, explicitly approves an action (e.g., "stop this instance nightly"), and only then does an automation execute it — with full audit logging. This is a meaningfully larger feature (state machine, notification integration, rollback handling) intentionally out of scope for the MVP's read-only design.

### Multi-account / AWS Organizations support

The current IAM model and Cost Explorer integration assume a single AWS account. Multi-account support would need cross-account IAM role assumption, per-account cost aggregation, and a materially different data model — a real architectural expansion, not a small addition.

### Cost forecasting

AWS Cost Explorer supports forecast APIs; the rule engine doesn't yet use them. Anomaly detection here is currently backward-looking (comparing recent cost to a rolling historical baseline) rather than predictive.

### AWS Compute Optimizer integration

Genuinely useful, but requires 14+ days of steady-state instance metrics to produce meaningful recommendations — most resources in this project's own test account don't run long enough to seed it usefully. The custom `EC2-001` rule fills this gap for now; Compute Optimizer would complement, not replace it, once resources have longer runtime histories to draw on.

### AI/LLM explanation layer

Explicitly optional and secondary per the original project design (see `docs/ARCHITECTURE.md` for the reasoning on why the rule engine itself stays deterministic). A future layer could take verified findings and translate them into natural-language explanations — but never generate the underlying evidence or conclusions itself.

### Slack/email alerting beyond SNS budget notifications

Current alerting is limited to AWS Budgets → SNS → email. Real-time Slack notification on high-severity findings is a natural, low-effort extension once the platform has more than one active user.

### Cost and Usage Report (CUR) + Athena

Cost Explorer's API gives the majority of useful cost insight at zero setup cost. CUR + S3 + Athena/Glue would unlock deeper drill-down (down to individual resource-hours) but represents meaningfully more infrastructure for a personal project's current needs.

## What this list is for

Every item here was a real service or feature evaluated and consciously not built yet — not an oversight. Keeping this list honest is itself consistent with the project's core value: recommendations and decisions backed by stated reasoning, not vibes.
