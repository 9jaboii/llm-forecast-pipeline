# 0002 — Burst-mode AWS deployment, not always-on

## Status
Accepted

## Context
A reference Kubernetes deployment (EKS + a NAT gateway + RDS) costs roughly
$118+/month at the floor before counting nodes or model usage — an EKS
control plane alone is about $73/month and a NAT gateway about $33/month,
both billed per hour whether the cluster is idle or busy. This project's
budget ceiling is $40/month or less.

## Decision
Kubernetes development and iteration (the Helm chart, Argo CD, NetworkPolicies,
Pod Security, CronJobs) happens entirely against a local `kind` cluster
(`deploy/kind/`, `make kind-up` / `make kind-down`) — free, disposable,
unlimited iteration. AWS is used only for short, single-tenant validation
bursts: `terraform apply` → deploy → verify → `terraform destroy`
(`docs/runbooks/aws-sandbox-burst.md`). Between bursts, the daily
ingest/forecast/publish cycle keeps running from a laptop via cron
(guide §07) — free except token cost — so the public track record never
goes stale even while AWS is torn down.

## Reasoning
- The same Helm chart runs unmodified against `kind` or against EKS; only
  the values pointing at Postgres/Bedrock vs local stand-ins differ. Proving
  the GitOps loop locally first means the AWS burst is a validation of
  already-working manifests, not a debugging session that burns cluster-hours.
- GitHub Pages keeps serving the last published snapshot after AWS is torn
  down, and the hash chain still verifies, so tearing down AWS never breaks
  the public-facing track record.
- A burst costs a few dollars for the few hours it runs, not a recurring
  monthly bill — comfortably inside the $40 cap even run several times.

## Consequences
- There's no continuously-running, publicly reachable Kubernetes cluster
  to point at as "the production system" — the production system, in the
  sense of "what actually generates the public track record every day," is
  the cron job, not EKS. This is stated explicitly rather than implied, since
  it's a genuine trade-off, not free.
- Anyone operating this for real, continuous cloud uptime would need to
  revisit this decision (and the budget it's built around).
