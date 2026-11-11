#!/usr/bin/env bash
# Posts a triage comment on the PR and makes <label> its only triage label.
# Usage: comment.sh <label> <body-file>   (needs GH_TOKEN, GH_REPO, PR)
set -euo pipefail
label=$1
body=$2

declare -A colors=(
  [triage:auto-merge]=0e8a16
  [triage:agent-fixed]=1d76db
  [triage:needs-human]=d93f0b
)
for l in "${!colors[@]}"; do
  gh label create "$l" --color "${colors[$l]}" --force >/dev/null
  if [ "$l" != "$label" ]; then
    gh pr edit "$PR" --remove-label "$l" >/dev/null 2>&1 || true
  fi
done
gh pr edit "$PR" --add-label "$label" >/dev/null
gh pr comment "$PR" --body-file "$body"
