# 0003 — Security model

## Status
Accepted

## Context
This is a public repository calling three external APIs and, eventually,
running in a shared-nothing AWS account. It needs a security posture that
survives being read by strangers from day one, not retrofitted later.

## Decision
1. **Secrets never enter the repository.** Local keys live in a git-ignored
   `.env`; in AWS there is no model API key at all (Bedrock uses an IAM
   role via Pod Identity) and RDS generates and stores its own password in
   Secrets Manager.
2. **Account-specific details stay out of public view.** Account IDs,
   ARNs, and IPs go in git-ignored files (`*.tfvars`, `backend.hcl`,
   `deploy/argocd/application.yaml`) or GitHub Environment secrets — never
   in committed files, commit messages, PR descriptions, or issues.
3. **Least privilege.** Each IAM role does exactly one job:
   `forecaster-app` calls one Bedrock model and reads one secret and two S3
   prefixes; `forecaster-github-build` can push to one ECR repository;
   `forecaster-github-pages` can only read `snapshots/*` in one bucket.
4. **AI assistants get the same rules, enforced, not requested.**
   `.claude/settings.json` denies reads of `.env`/`*.tfvars`/`backend.hcl`/
   state/credential directories, requires approval before `git push`,
   `terraform apply/destroy`, or mutating `kubectl` commands, and disables
   commit/PR attribution trailers. `CLAUDE.md` states the same rules in
   plain language. See `.claude/settings.json` and `CLAUDE.md` for the
   actual mechanism — this ADR records the intent.
5. **Headlines are untrusted input.** GDELT headlines reach the forecasting
   prompt as data only (`forecast_prompt.sanitize_headline` strips control
   characters and delimiter tags before the text is ever inserted into the
   prompt), and the model's output is parsed for exactly one number
   (`forecast_prompt.parse_probability`) — nothing the model writes is
   ever executed or treated as an instruction.
6. **Verify continuously.** `make scan` (gitleaks) runs before every commit
   and in CI; CI also runs `pip-audit`, a license check, and `terraform
   fmt`/`validate`/`helm lint` on every push.

## Consequences
- Every manual step in `docs/runbooks/` that touches a secret or an
  account-specific value is called out as something the human does in their
  own terminal, not something delegated to an assistant.
- Rotation is cheap: compromising any one role or key doesn't expose
  anything outside its narrow scope.
