# Architecture

## Design principles

Every decision in this project was made against four constraints, in this priority order: **cost, reliability, security, operability**. Cost optimization never comes at the expense of the other three — the point of a FinOps project is demonstrating that tradeoff being made deliberately, not cutting corners.

## System diagram

```
Internet
   │
infrafox.duckdns.org (HTTPS, Let's Encrypt cert)
   │
Nginx (native systemd service, not containerized)
   ├── / ────────────► /var/www/infrafox (static React build)
   └── /api/ ────────► proxy_pass → localhost:8000
                              │
                    FastAPI backend (Docker container, network_mode: host)
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        boto3 (IAM role   PostgreSQL      Structured
        via IMDSv2)      (Docker container, JSON logs
              │           localhost:5432)
              ▼
   AWS Cost Explorer, EC2, CloudWatch,
   Resource Groups Tagging API (read-only)
```

Single EC2 instance, single Availability Zone, single region (ap-south-1). No load balancer, no auto-scaling group, no multi-AZ failover.

## Why single-instance, not highly available

This is a personal FinOps tool scanning one AWS account, not a customer-facing SaaS product. The failure mode of "the instance is briefly down" is a non-event — findings are recomputed on the next scan, nothing is lost, and there's no SLA to violate. Spending budget on multi-AZ redundancy here would be optimizing for a requirement that doesn't exist, which is itself a FinOps anti-pattern the platform is designed to catch in *other* infrastructure.

## Why Terraform state is local, not a remote backend (S3 + DynamoDB)

A remote backend adds real value once multiple people or CI systems need to safely coordinate applies against the same state. For a single developer, it adds setup cost (an S3 bucket + DynamoDB table, both billable, however small) with no corresponding benefit. This tradeoff is revisited honestly in `docs/incidents.md` — local state caused a real recovery incident during development, which is the actual cost of this choice, made visible rather than hidden.

## Why no NAT Gateway

NAT Gateways cost ~$32+/month in data processing and hourly charges just to give a private subnet outbound internet access. This project's single instance sits in a **public subnet** with a tightly-scoped Security Group instead — the security boundary comes from firewall rules, not network topology. For a single-instance architecture, this achieves equivalent security at zero cost.

## Why no Elastic IP

An Elastic IP is free while attached to a running instance, but bills the moment it's unattached (e.g., during a stop/start cycle) — exactly the kind of waste pattern this platform's own `EIP-001` rule is built to detect. Rather than risk that trap, the instance runs without one; DuckDNS is kept in sync via a cron job (`scripts/duckdns-update.sh`) that pushes the current public IP on every boot and every 5 minutes thereafter. This is also more realistic FinOps practice: avoiding unattached-EIP waste rather than architecting around a static IP dependency.

## Why containerize the backend + database but not Nginx

Nginx's TLS setup (via Certbot) was working reliably before containerization was considered. Moving it into Docker would mean re-solving certificate renewal, ACME challenge routing, and volume-mounting `/etc/letsencrypt` across a container boundary — real complexity with no corresponding benefit at this scale. The stronger pattern for a single-VM deployment is a stable, native reverse-proxy/TLS-termination layer with disposable, replaceable application containers behind it. That's what this project does: Nginx stays native and stable; backend and Postgres are containers that can be rebuilt and redeployed independently via CI/CD without touching TLS at all.

## Why `network_mode: host` for the backend container

The backend needs to reach the EC2 instance metadata service (`169.254.169.254`) to pick up IAM role credentials via IMDSv2 — this is what lets boto3 authenticate to AWS with zero static credentials anywhere in the system. Docker's default bridge networking isolates containers from that link-local address by default. `network_mode: host` gives the container the same network view as the host process, which is what makes credential auto-discovery work exactly as it would for a native (non-containerized) process. The tradeoff — losing Docker's inter-container network isolation — is acceptable at this scale: Postgres is reached via `localhost:5432` instead of a Docker service name, with no loss of functionality.

## Why PostgreSQL over RDS

A containerized Postgres instance runs on infrastructure you're already paying for (the EC2 instance itself) — effectively free beyond a small amount of EBS storage. The cheapest RDS instance (`db.t3.micro`) starts around $15–30+/month on its own, which would roughly double this project's total infrastructure cost for a workload — periodic FinOps scans against a single AWS account — that doesn't need managed high-availability, automated failover, or read replicas.

## Why SQLite was the initial choice, then migrated to Postgres

SQLite required zero setup and let the persistence layer (Phase 3) be built and validated quickly with no external dependency. Once the architecture was proven correct, migrating to containerized Postgres (Phase 5) was a deliberate, low-risk step — enabled by keeping all database access behind SQLAlchemy from the start, so the migration required only a `DATABASE_URL` change and one driver dependency (`psycopg2-binary`), not a rewrite.

## Why a custom IAM policy instead of AWS's managed `ReadOnlyAccess`

`ReadOnlyAccess` is broad — read access to nearly every AWS service, most of which this platform never touches (SES, Route53, dozens of others). The custom policy in `iam.tf` grants exactly the `Describe*`/`Get*`/`List*` actions the FinOps engine actually calls, nothing more. This is a meaningfully smaller blast radius if the instance or its credentials were ever compromised, and it's a more defensible answer in a security review than "I attached the AWS-managed policy."

## Why the rule engine is deterministic, not LLM-based

The core value proposition is trustworthy, evidence-backed findings. An LLM in the critical path introduces the possibility of hallucinated evidence or inconsistent conclusions on the same input — unacceptable for a tool whose entire purpose is being trusted enough to act on. The rule engine is plain, auditable Python: given the same AWS data, it produces the same findings, every time. An optional LLM explanation layer (Phase 7, not yet built) would sit *on top of* verified findings to translate them into prose — never as the source of truth for what's true.
