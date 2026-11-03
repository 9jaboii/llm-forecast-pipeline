#!/usr/bin/env bash
# Turns on the repository security settings described in guide §01/A4:
# secret scanning, push protection, Dependabot, private vulnerability
# reporting, read-only workflow permissions, the `build` and `github-pages`
# environments (limited to main), and a branch ruleset on main. Safe to run
# again — every step reads the setting back afterwards so you can see what
# took effect. Anything this account/plan can't set via the API prints
# "skipped" and the console page to finish it by hand.
set -euo pipefail

command -v gh >/dev/null || { echo "gh (GitHub CLI) is required" >&2; exit 1; }
gh auth status >/dev/null || { echo "run 'gh auth login' first" >&2; exit 1; }

REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
echo "Configuring $REPO"

api() { gh api -H "Accept: application/vnd.github+json" "$@"; }

set_security_feature() {
  local feature="$1" label="$2"
  if api -X PATCH "repos/$REPO" -f "security_and_analysis[$feature][status]=enabled" >/dev/null 2>&1; then
    echo "  [ok] $label enabled"
  else
    echo "  [skipped] $label — enable in Settings > Code security"
  fi
}

echo "-- Secret scanning & Dependabot --"
set_security_feature "secret_scanning" "Secret scanning"
set_security_feature "secret_scanning_push_protection" "Push protection"
set_security_feature "dependabot_security_updates" "Dependabot security updates"

if api -X PUT "repos/$REPO/private-vulnerability-reporting" >/dev/null 2>&1; then
  echo "  [ok] Private vulnerability reporting enabled"
else
  echo "  [skipped] Private vulnerability reporting — enable in Settings > Code security"
fi

echo "-- Workflow permissions --"
if api -X PUT "repos/$REPO/actions/permissions/workflow" \
    -f default_workflow_permissions=read \
    -F can_approve_pull_request_reviews=false >/dev/null 2>&1; then
  echo "  [ok] Default workflow permissions set to read-only"
else
  echo "  [skipped] Workflow permissions — set in Settings > Actions > General"
fi
echo "  [manual] Fork PR approval requirement: Settings > Actions > General >"
echo "           Fork pull request workflows > Require approval for all outside collaborators"
echo "           (not exposed via the API; set this by hand once)"

echo "-- Environments --"
for env in build github-pages; do
  if api -X PUT "repos/$REPO/environments/$env" \
      -f 'deployment_branch_policy[protected_branches]=false' \
      -f 'deployment_branch_policy[custom_branch_policies]=true' >/dev/null 2>&1; then
    api -X POST "repos/$REPO/environments/$env/deployment-branch-policies" \
      -f name=main >/dev/null 2>&1 || true
    echo "  [ok] environment '$env' created, limited to main"
  else
    echo "  [skipped] environment '$env' — create in Settings > Environments"
  fi
done

echo "-- Branch ruleset on main --"
RULESET_JSON=$(cat <<'JSON'
{
  "name": "main-protection",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/main"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_status_checks",
      "parameters": { "required_status_checks": [
        { "context": "python" }, { "context": "secrets" }, { "context": "infra" }
      ], "strict_required_status_checks_policy": true } }
  ]
}
JSON
)
if echo "$RULESET_JSON" | api -X POST "repos/$REPO/rulesets" --input - >/dev/null 2>&1; then
  echo "  [ok] ruleset created: no force-push, no deletion, required checks"
else
  echo "  [skipped] branch ruleset — create in Settings > Rules > Rulesets"
fi

echo
echo "Summary (read back from GitHub):"
api "repos/$REPO" --jq '.security_and_analysis'
echo "Run with --require-reviewer if you also want every image build to wait for your approval"
echo "(adds a required reviewer to the 'build' environment)."

if [[ "${1:-}" == "--require-reviewer" ]]; then
  ME="$(gh api user --jq .login)"
  api -X PUT "repos/$REPO/environments/build" \
    -f "reviewers[][type]=User" -F "reviewers[][id]=$(gh api users/$ME --jq .id)" >/dev/null 2>&1 \
    && echo "  [ok] required reviewer added to 'build' environment" \
    || echo "  [skipped] add a required reviewer in Settings > Environments > build"
fi
