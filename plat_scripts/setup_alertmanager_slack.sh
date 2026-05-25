#!/usr/bin/env bash
# Create/update the Slack webhook secret for Alertmanager in staging or production.
#
# Usage:
#   bash plat_scripts/setup_alertmanager_slack.sh 'https://hooks.slack.com/services/...'
#   bash plat_scripts/setup_alertmanager_slack.sh 'https://...' uvote-prod
#
# Then restart Alertmanager and verify:
#   kubectl rollout restart deployment/alertmanager -n uvote-dev
#   kubectl port-forward -n uvote-dev svc/prometheus 9090:9090
#   open http://localhost:9090/alerts
set -euo pipefail

WEBHOOK_URL="${1:-}"
NAMESPACE="${2:-uvote-dev}"

if [[ -z "$WEBHOOK_URL" ]]; then
  echo "Usage: $0 <slack-incoming-webhook-url> [namespace]"
  exit 1
fi

if [[ "$WEBHOOK_URL" != https://hooks.slack.com/* ]]; then
  echo "Warning: URL does not look like a Slack incoming webhook."
fi

kubectl create secret generic alertmanager-slack \
  --namespace="$NAMESPACE" \
  --from-literal=slack_api_url="$WEBHOOK_URL" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secret alertmanager-slack applied in $NAMESPACE"
kubectl rollout restart deployment/alertmanager -n "$NAMESPACE"
kubectl rollout status deployment/alertmanager -n "$NAMESPACE" --timeout=120s
echo ""
echo "Next: confirm Prometheus shows alerts → http://localhost:9090/alerts (port-forward prometheus)"
echo "Trigger a test: scale a service to 0 or wait for UVoteHighErrorRate / UVoteServiceDown rules."
