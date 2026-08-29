# COST-SAFETY.md

This document exists because the original project constraint was a $200 AWS credit budget, and because "Free Tier" does not mean "free" — several services here can create unexpected charges if misconfigured. Everything billable in this project is listed below, with exact teardown steps.

## Every AWS resource that costs money

| Resource | Est. cost | Notes |
|---|---|---|
| EC2 `t3.small` (ap-south-1) | ~$0.0208/hr (~$15/mo if run 24/7) | The only resource with meaningful cost. Stop it (don't terminate) during extended idle periods to pay $0 compute. |
| EBS gp3 volume, 20GB | ~$1.60/mo | Root volume, bills whether the instance is running or stopped. |
| S3 (if used) | ~$0.023/GB-mo | Not used in current MVP. |
| SNS (budget alert emails) | Free | Well under the 1,000 free notifications/month. |
| AWS Budgets | Free | First 2 budgets are free. |
| Cost Explorer API calls | Effectively free | Negligible at this project's call volume. |
| CloudTrail (if enabled) | Free for first trail | Management events only. |

**Everything else in this project — VPC, subnet, Internet Gateway, route table, Security Group, IAM roles/policies — is free.** No NAT Gateway, no Load Balancer, no RDS, no EKS, no OpenSearch, no ElastiCache anywhere in this architecture, by design.

## Realistic monthly ceiling

`t3.small` run continuously (~$15) + EBS (~$1.60) + everything else (~$0) = **under $20/month**, even with zero cost-saving discipline. A $200 credit balance covers roughly 10 months of careless 24/7 usage.

## How to check current spend

```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '30 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --region ap-south-1
```

Or via the platform's own API (the honest, dogfooding way):

```bash
curl -s https://infrafox.duckdns.org/api/v1/costs/summary
```

Or the AWS Console: Billing → Cost Explorer.

## AWS Budgets configuration

A monthly budget is configured via Terraform (`budgets.tf`) at **$100/month**, with alerts firing at:

- 50% actual spend
- 80% actual spend
- 100% actual spend
- 100% **forecasted** spend (catches a trajectory problem before it happens, not just after)

All four notify the account email via SNS. **Important**: after `terraform apply` creates or updates the SNS subscription, AWS sends a confirmation email — alerts will not deliver until that's clicked.

## How to stop paying for compute (without losing anything)

```bash
aws ec2 stop-instances --instance-ids i-009e5637f5e6b6cb2 --region ap-south-1
```

This stops billing for the EC2 instance's compute time immediately. The EBS volume keeps billing at ~$1.60/mo regardless — that's unavoidable short of deleting the volume entirely, which would destroy the Docker containers, Postgres data, and app state.

To restart:

```bash
aws ec2 start-instances --instance-ids i-009e5637f5e6b6cb2 --region ap-south-1
```

**Note**: since this project deliberately does not use an Elastic IP (see `docs/ARCHITECTURE.md` for why), the public IP will likely change on restart. The DuckDNS cron job (`scripts/duckdns-update.sh`, runs on boot and every 5 minutes) will re-point `infrafox.duckdns.org` automatically within a few minutes of the instance coming back up.

## Full teardown (permanent deletion)

Only do this if the project is genuinely being retired.

```bash
cd ~/infrafox-finops
terraform destroy
```

This removes every Terraform-managed resource: EC2 instance (and its EBS volume, since `delete_on_termination = true`), VPC, subnet, security group, IAM role/policy, budget, SNS topic.

**Verify deletion**:

```bash
aws ec2 describe-instances --region ap-south-1 --filters "Name=tag:Project,Values=infrafox"
```

Should return an empty result once teardown is complete.

Separately, manually delete:
- The DuckDNS domain record (via duckdns.org, if no longer needed)
- The GitHub repository secrets (`EC2_HOST`, `EC2_USER`, `EC2_SSH_PRIVATE_KEY`, `POSTGRES_PASSWORD`) — these become meaningless once the instance is gone, but should be removed rather than left stale
- Any GitHub Personal Access Tokens created specifically for this project (`https://github.com/settings/tokens`)

## What can create unexpected charges if you're not careful

- **Leaving an Elastic IP allocated but unattached** — this project doesn't use one, but if you ever add one manually, an unattached EIP bills continuously (this is literally what the platform's own `EIP-001` rule detects).
- **Forgetting a stopped instance still has a billing EBS volume** — covered above.
- **Running `terraform apply` from a machine with stale/incorrect state** — during development, a state-sync issue nearly caused an unnecessary instance replacement. See `docs/incidents.md` for the full story and how it was caught before any damage occurred.
- **CloudWatch detailed monitoring** — this project uses only the free 5-minute-granularity metrics. Enabling detailed (1-minute) monitoring on an instance incurs per-metric charges; nothing in this codebase turns that on.

## Cleanup checklist (before declaring the project "done" or handing off credits)

- [ ] `terraform destroy` run and verified empty
- [ ] DuckDNS domain released or repointed
- [ ] GitHub repository secrets deleted
- [ ] GitHub Personal Access Tokens revoked
- [ ] Confirm final AWS bill via Cost Explorer matches expectations
- [ ] Confirm no orphaned EBS snapshots, unattached volumes, or unattached Elastic IPs remain (`aws ec2 describe-volumes`, `aws ec2 describe-addresses`)
