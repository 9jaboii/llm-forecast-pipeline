# 0004 — Tenant isolation: no shared control plane, no shared data plane

## Status
Accepted

## Context
This project is positioned as something an enterprise could run entirely
inside its own AWS account, not a hosted service operated on customers'
behalf. "No data or activity leaves your VPC" is only a credible claim if
it's a property the system enforces, not a sentence in a README.

## Decision
- This ships as a Terraform/Helm module. There is no vendor-operated
  control plane anywhere — `infra/terraform/` and `deploy/helm/forecaster/`
  are run by whoever deploys them, inside their own AWS account, with their
  own IAM roles. Nothing in this repository calls home to any service
  operated by the people who wrote it.
- The local `kind` cluster used for development (ADR 0002) and the AWS
  account used for the sandbox validation burst are both just stand-ins for
  "a deployer's own environment" — not shared infrastructure.
- The only outbound network calls anywhere in the system are the three in
  the integration map: Manifold Markets, GDELT, and Bedrock/Anthropic —
  always made directly from the deployer's own VPC/account, never through
  an intermediary.
- This is partly enforced by a default-deny egress `NetworkPolicy`
  (`deploy/helm/forecaster/templates/networkpolicy.yaml`): no egress at all
  except DNS, the in-namespace Postgres, and port 443 — no raw TCP to
  arbitrary ports, no plaintext HTTP. Verify it directly with
  `kubectl -n forecaster describe networkpolicy`, not on faith. Be precise
  about what this does and doesn't prove: plain Kubernetes `NetworkPolicy`
  filters on IP/CIDR and port, not hostname, so it cannot by itself
  restrict egress to exactly `api.manifold.markets` / `api.gdeltproject.org`
  / the Anthropic/Bedrock endpoints — any HTTPS destination is technically
  reachable at the network layer. The "only these three APIs" half of the
  claim rests on there being no other code path in this (open source, so
  checkable) repository that makes an outbound call — a code-review
  guarantee, not a network one. A stricter, hostname-aware version would
  need a CNI with DNS/FQDN-based policies (e.g. Cilium); see
  `docs/runbooks/local-k8s.md` for what's actually running and why that
  wasn't pulled in for this project's scope.

## Reasoning
Enterprise buyers evaluating an AI system often weigh data residency and
blast-radius containment as heavily as raw capability — a system that
cannot technically see or exfiltrate a customer's data is a materially
easier approval than one that merely promises not to. Encoding the
guarantee as a cluster-enforced network policy, rather than a design
intention, makes it something a security reviewer can verify in minutes.

## Consequences
- Any new integration (a new data source, a new notification channel, a
  different model provider) must update the egress allowlist explicitly —
  the default is deny, so a forgotten `NetworkPolicy` change fails closed
  (the new call is blocked) rather than failing open (silently reaching an
  unreviewed destination).
- This project cannot add centralized telemetry, update checks, or a
  "phone home" feature without first revisiting this decision.
