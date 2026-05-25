#!/usr/bin/env bash
# Recreate a broken frontend Rollout (InvalidSpec: missing image) after git fix is pushed.
set -euo pipefail

NS=uvote-dev
ROLLOUT=frontend-service

echo "==> Deleting Rollout $ROLLOUT in $NS (pods will be recreated by Argo CD)"
kubectl delete rollout "$ROLLOUT" -n "$NS" --wait=true 2>/dev/null || true

echo "==> Sync uvote-staging (apply Argo CD Application manifest first if needed)"
kubectl patch application uvote-staging -n argocd --type=merge \
  -p '{"operation":{"sync":{"revision":"HEAD"}}}' 2>/dev/null || \
  echo "    Run: argocd app sync uvote-staging"

echo "==> Wait for Rollout"
kubectl wait --for=condition=Available "rollout/$ROLLOUT" -n "$NS" --timeout=300s 2>/dev/null || \
  kubectl get rollout "$ROLLOUT" -n "$NS"

kubectl get pods -n "$NS" -l app=frontend-service
