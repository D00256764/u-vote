#!/usr/bin/env bash
# Split staging (NLB :80) and production (NLB :8080) onto separate Envoy listeners.
# Without this, both Service ports target pod :8080 and all VS routes merge — staging wins.
set -euo pipefail

NS=istio-system
DEP=istio-ingressgateway
SVC=istio-ingressgateway

echo "==> Current Service ports"
kubectl get svc "$SVC" -n "$NS" -o jsonpath='{range .spec.ports[*]}{.name}:{.port}->{.targetPort}{"\n"}{end}'

echo "==> Patch Service: :80 -> targetPort 80, :8080 -> targetPort 8080"
kubectl get svc "$SVC" -n "$NS" -o json | python3 -c "
import json, sys
svc = json.load(sys.stdin)
ports = svc['spec']['ports']
by_port = {p['port']: p for p in ports}
# Preserve status/https if present
out = []
for p in ports:
    if p.get('port') == 15021:
        out.append({**p, 'targetPort': p.get('targetPort', 15021)})
    elif p.get('port') == 443:
        out.append({**p, 'targetPort': p.get('targetPort', 8443)})
    elif p.get('port') == 80:
        p['name'] = p.get('name') or 'http-staging'
        p['targetPort'] = 80
        out.append(p)
    elif p.get('port') == 8080:
        p['name'] = p.get('name') or 'http-prod'
        p['targetPort'] = 8080
        out.append(p)
    else:
        out.append(p)
if not any(p.get('port') == 80 for p in out):
    out.insert(0, {'name': 'http-staging', 'port': 80, 'targetPort': 80, 'protocol': 'TCP'})
if not any(p.get('port') == 8080 for p in out):
    out.append({'name': 'http-prod', 'port': 8080, 'targetPort': 8080, 'protocol': 'TCP'})
svc['spec']['ports'] = out
print(json.dumps(svc))
" | kubectl apply -f -

echo "==> Ensure ingress deployment exposes containerPort 80"
kubectl patch deployment "$DEP" -n "$NS" --type=json -p='[
  {"op": "add", "path": "/spec/template/spec/containers/0/ports/-", "value": {
    "containerPort": 80, "protocol": "TCP", "name": "http80"
  }}
]' 2>/dev/null || echo "    (port 80 may already exist)"

echo "==> Restart ingress gateway"
kubectl rollout restart deployment/"$DEP" -n "$NS"
kubectl rollout status deployment/"$DEP" -n "$NS" --timeout=180s

echo "==> Verify Service ports"
kubectl get svc "$SVC" -n "$NS" -o jsonpath='{range .spec.ports[*]}{.name}:{.port}->{.targetPort}{"\n"}{end}'
echo "Done. Re-check: istioctl proxy-config routes deploy/$DEP -n $NS --port 8080"
