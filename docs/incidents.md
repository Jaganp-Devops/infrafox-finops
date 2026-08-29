# Incidents & Troubleshooting

Real problems encountered during development, how they were diagnosed, and how they were resolved. Kept honest and specific rather than generic, because the actual debugging process is more informative than a sanitized list of hypothetical failure modes.

---

## Incident 1: Terraform state drift after a partially-failed apply

### What happened

While adding a new Security Group rule (to allow GitHub Actions runners to reach the instance via SSH), `terraform apply` failed partway through with `DuplicateRecordException` and `EntityAlreadyExists` errors on the IAM role, IAM policy, and AWS Budget. Investigation showed the local Terraform state file was missing several resources that were, in fact, already running correctly in AWS — including the IAM role, policy, instance profile, budget, and (most seriously) the EC2 instance itself.

### Root cause

Terraform state for this project is local, not a remote backend (a deliberate cost-saving decision — see `docs/ARCHITECTURE.md`). At some point, state had drifted out of sync with reality — likely from an earlier interrupted apply. When `apply` ran again, Terraform believed it needed to *create* resources that already existed, and its `-/+ destroy and then create replacement` plan for the EC2 instance would have **destroyed the live, running production instance** — deleting the running Docker containers and Postgres data — because state pointed the instance at a newly (and accidentally) created duplicate VPC/subnet rather than the one the real instance actually lived in.

### Detection

The plan output was read carefully before applying (`terraform plan` is never skipped in this project) and the `-/+ destroy and then create replacement` line on `aws_instance.infrafox`, combined with a `subnet_id` change marked `# forces replacement`, was the signal to stop immediately rather than apply.

### Diagnosis

```bash
aws ec2 describe-instances --instance-ids <id> --query "[SubnetId,VpcId,SecurityGroups]"
```

confirmed the real subnet/VPC/security group IDs the running instance actually used — which did not match what Terraform's state believed.

### Recovery

1. `terraform state rm` on the incorrect (accidentally duplicated) VPC, subnet, security group, IGW, route table, and route table association — this only removes Terraform's *bookkeeping*, not the real AWS resources.
2. `terraform import` each resource again, this time using the **real** IDs confirmed via `aws ec2 describe-*` calls, not the ones state had drifted to.
3. `terraform plan` re-run and verified as `0 to add, 2 to change, 0 to destroy` before applying — the "2 to change" being safe, cosmetic tag reconciliation, not resource replacement.

### Outcome

State fully recovered with zero downtime and zero data loss. The live instance, its IP, and all running containers were untouched throughout.

### Prevention going forward

- Always read `terraform plan` output completely before `apply` — especially watching for `-/+` (replace) rather than `~` (update in-place)
- For a project with more than one contributor or automation touching Terraform, a remote state backend (S3 + DynamoDB lock table) would prevent this class of drift entirely — noted as a production extension in `docs/roadmap.md`

---

## Incident 2: Mixed-content error blocking the dashboard after containerization

### What happened

After switching the frontend's API base URL to a relative path (`/api`, intended to be proxied through Nginx), the live dashboard failed with `Failed to fetch` in the browser, later revealed via DevTools Console as:

```
Mixed Content: The page at 'https://infrafox.duckdns.org/' was loaded over HTTPS,
but requested an insecure resource 'http://<ec2-ip>:8000/...'
```

### Root cause

Two independent bugs stacked:

1. `client.js` used `const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://<ip>:8000"`. Setting `VITE_API_BASE_URL=""` (empty string) doesn't prevent the fallback — JavaScript's `||` treats an empty string as falsy, so the hardcoded HTTP URL was silently used every time regardless of the intended empty-string override.
2. Separately, once fixed, the **newly built** JS bundle was correct, but the **deployed** files in Nginx's serving directory (`/var/www/infrafox`) still referenced an older, stale bundle — because the deploy step (copying `dist/` to the web root) had been interrupted partway through an earlier session and never re-run.

### Diagnosis

- Browser DevTools → Network tab, inspecting the actual failing request's full URL (not just its short label), revealed the hardcoded IP:port
- `grep -o "3.109.152.62:8000" dist/assets/*.js` confirmed whether the *built* bundle still contained the hardcoded URL
- Comparing filenames in `dist/assets/` vs. `/var/www/infrafox/assets/` revealed the deployed files were older than the latest build

### Fix

1. Changed the fallback operator from `||` to `??` (nullish coalescing) — `??` only falls back on `null`/`undefined`, correctly respecting an intentional empty string
2. Rebuilt cleanly (`rm -rf dist node_modules/.vite && npm run build`) and redeployed, this time wiping the old assets directory first (`sudo rm -rf /var/www/infrafox/assets`) so a stale file could never be referenced by an outdated `index.html`

### Prevention going forward

Built `frontend/deploy.sh` — a single script that rebuilds, wipes old assets, copies the new build, and fixes permissions in one atomic sequence, specifically so this two-step "forgot to actually deploy the fix" failure mode can't recur. This same logic is now also encoded in the CI/CD pipeline's `deploy` job, so manual deploys are no longer the only path to production.

---

## Incident 3: EC2 `GroupDescription` rejecting non-ASCII characters

### What happened

`terraform apply` failed on the very first attempt to create the Security Group:

```
InvalidParameterValue: Value (InfraFox EC2 security group — restricted SSH...)
for parameter GroupDescription is invalid. Character sets beyond ASCII are not supported.
```

### Root cause

The Security Group's `description` field contained an em dash (`—`), a non-ASCII character. AWS's EC2 API strictly validates this specific field as ASCII-only — a constraint not obvious from Terraform's own validation, since `terraform validate` passed cleanly (it only checks HCL syntax, not AWS API-side field constraints).

### Fix

Replaced the em dash with a plain hyphen. Since the same em-dash habit appeared in code comments throughout the project (harmless there, since comments are never sent to AWS), the fix was scoped precisely to the one field AWS actually validates, rather than a blanket find-and-replace across files where it didn't matter.

### Prevention going forward

`terraform plan` output is checked for AWS-side validation errors on every new resource, not just HCL syntax errors from `validate` — the two checks catch different classes of problems.

---

## Incident 4: `ruff` linting caught real timezone bugs

### What happened

Adding `ruff` to the CI pipeline surfaced 37 findings on a first run against previously "working" code — including two genuine bugs (`DTZ011`): `date.today()` calls that implicitly used the server's local timezone rather than UTC, inconsistent with the rest of the codebase's explicit UTC handling.

### Fix

Both occurrences changed to `datetime.now(timezone.utc).date()`. 28 of the remaining 37 findings were mechanical (import ordering, `Optional[str]` → `str | None` syntax modernization) and auto-fixed via `ruff check --fix`. The remaining 8 were reviewed individually and determined to be correct, intentional patterns (FastAPI's `Depends()` in argument defaults; broad `except Exception` in health-check endpoints) — documented explicitly in `backend/ruff.toml` with reasoning, rather than silently suppressed.

### Why this matters

A linter catching a real, if minor, correctness bug on first run — rather than just style nitpicks — is a genuine argument for running static analysis early, not as an afterthought before a demo.
