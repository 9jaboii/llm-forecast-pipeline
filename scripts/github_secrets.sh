#!/usr/bin/env bash
# Pipes terraform outputs straight into `gh secret set` for the `build` and
# `github-pages` environments (guide §10, 2.2 and 3.2). Values never appear
# on screen, in a file, or in an AI assistant's context — run this script
# rather than asking anything to "look up" a role ARN. Requires
# infra/terraform/env to already be applied.
set -euo pipefail

command -v gh >/dev/null || { echo "gh (GitHub CLI) is required" >&2; exit 1; }
command -v terraform >/dev/null || { echo "terraform is required" >&2; exit 1; }

TF_DIR="${TF_DIR:-infra/terraform/env}"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

tf_output() { terraform -chdir="$TF_DIR" output -raw "$1"; }

echo "Reading terraform outputs from $TF_DIR ..."
REGION="$(tf_output region 2>/dev/null || echo us-east-1)"
BUILD_ROLE_ARN="$(tf_output github_build_role_arn)"
PAGES_ROLE_ARN="$(tf_output github_pages_role_arn)"
TRACK_RECORD_BUCKET="$(tf_output track_record_bucket)"

echo "-- build environment secrets --"
gh secret set AWS_BUILD_ROLE_ARN --env build --repo "$REPO" --body "$BUILD_ROLE_ARN"
gh secret set AWS_REGION --env build --repo "$REPO" --body "$REGION"
echo "  [ok] AWS_BUILD_ROLE_ARN, AWS_REGION set on 'build'"

echo "-- github-pages environment secrets --"
gh secret set AWS_PAGES_ROLE_ARN --env github-pages --repo "$REPO" --body "$PAGES_ROLE_ARN"
gh secret set AWS_REGION --env github-pages --repo "$REPO" --body "$REGION"
gh secret set TRACK_RECORD_BUCKET --env github-pages --repo "$REPO" --body "$TRACK_RECORD_BUCKET"
echo "  [ok] AWS_PAGES_ROLE_ARN, AWS_REGION, TRACK_RECORD_BUCKET set on 'github-pages'"

echo
echo "Done. Nothing above printed a secret value — verify names only:"
gh secret list --env build --repo "$REPO"
gh secret list --env github-pages --repo "$REPO"
