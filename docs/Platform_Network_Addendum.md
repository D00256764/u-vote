# Platform Network & Security Addendum

This addendum collects and summarises the Kubernetes/Calico NetworkPolicy design and verification evidence from `docs/NETWORK-SECURITY.md` and pulls the policy manifests and test evidence together for the Platform report.

## Summary
- Zero-trust, default-deny model implemented in `uvote-dev` namespace.
- 12 NetworkPolicy resources across five files:
  - `00-default-deny.yaml` (1)
  - `01-allow-dns.yaml` (1)
  - `02-allow-to-database.yaml` (2: ingress+egress)
  - `03-allow-from-ingress.yaml` (6: one per exposed service)
  - `04-allow-audit.yaml` (2: ingress+egress)

## Policy Mapping (short)
- Default deny: Applies to all pods (`podSelector: {}`) — both Ingress & Egress.
- DNS allow: `podSelector: {}` egress to `kube-system` port 53 (UDP/TCP).
- Database allow: bidirectional pair — ingress on PostgreSQL pod for six services; egress on app pods for PostgreSQL and DNS.
- Ingress allow: 6 separate policies permitting traffic from `ingress-nginx` namespace to specific service ports.
- Audit allow: bidirectional pair enabling backend services to send to the audit service and audit service to reach DB.

## Test Evidence (condensed)
The project executed 36 network tests covering:
- Baseline (no policies) connectivity
- Default-deny behaviour
- DNS-only recovery
- Database bidirectional allowance
- Ingress-only flows for exposed services
- Audit channel flows

All 36 tests passed. Representative commands used in testing:
- `kubectl exec -n uvote-dev deploy/auth-service -- pg_isready -h postgresql -p 5432`
- `kubectl exec -n uvote-dev deploy/frontend -- nc -zv -w 3 audit-service 8005`
- `curl -s -o /dev/null -w "%{http_code}" https://uvote.local/api/auth/health`

## Maintenance Notes (actions to take)
- When adding any new service requiring DB or audit access, update BOTH the ingress and egress DB/audit policies.
- Keep `policy-order` numeric prefix in filenames for ordering and auditability.
- Keep policy manifests under Git control and re-run the network test suite after changes.

## Files referenced
- `docs/NETWORK-SECURITY.md`
- `docs/ADR-004-calico-networking.md`

---

(Include this file in `docs/Platform_Report_Final.md` under "Network Security" section.)
