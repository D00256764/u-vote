#!/usr/bin/env bash
# Reset FEATURE_QUICK_SETUP to false on production after a demo run.
# Run from the repo root on the main branch.
set -euo pipefail

OVERLAY="uvote-platform/k8s/overlays/production/feature-flag-patch.yaml"

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "Error: must be on main branch (currently on $(git branch --show-current))"
  exit 1
fi

git pull --rebase origin main

CURRENT=$(grep 'value:' "$OVERLAY" | awk '{print $2}' | tr -d '"')
if [[ "$CURRENT" == "false" ]]; then
  echo "Already false — nothing to reset."
  exit 0
fi

sed -i '' 's/value: "true"/value: "false"/' "$OVERLAY"

git add "$OVERLAY"
git commit -m "chore(prod): reset FEATURE_QUICK_SETUP=false for demo repeat"
git push origin main

echo ""
echo "Pushed. ArgoCD will sync production in ~3 min."
echo "Quick Setup Guide will disappear from prod once election-service restarts."
echo ""
echo "To watch: kubectl rollout status deploy/election-service -n uvote-prod"
