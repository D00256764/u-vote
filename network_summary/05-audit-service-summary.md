# Audit Service Access Policy Summary

**Generated:** 2026-02-15
**Policy Number:** 04 (includes 04a ingress + 04b egress)
**File:** uvote-platform/k8s/network-policies/04-allow-audit.yaml

## Purpose
Enables bidirectional audit logging between all backend services and the centralised audit-service. Ensures the security-critical, hash-chained audit trail documented in ARCHITECTURE.MD is maintained while preserving zero-trust network isolation.

## Critical — Bidirectional NetworkPolicy Requirement

In Kubernetes with default-deny, audit traffic must be allowed in BOTH directions:

| Direction | Policy Resource | Label | Effect |
|-----------|----------------|-------|--------|
| Ingress TO audit-service | `allow-to-audit` | `policy-order: "04a"` | Audit service can RECEIVE log events from 6 backend services |
| Egress FROM services | `allow-audit-egress` | `policy-order: "04b"` | Services can SEND log events to audit service |

**Without both policies:** Services cannot deliver audit logs — the security audit trail breaks.
**With both policies:** Complete, immutable audit trail maintained.

This file contains BOTH NetworkPolicy resources separated by `---`.

## Validation Against Documentation

| Check | Status | Detail |
|-------|--------|--------|
| Audit service name matches ARCHITECTURE.MD | ✅ | `audit-service` (§ "Audit Service", port 8005) |
| Audit service port matches ARCHITECTURE.MD | ✅ | `8005` (§ "Audit Service" header: "Port 8005") |
| Audit service label matches | ✅ | `app: audit-service` (consistent with `app: <service-name>` convention) |
| All services that log included | ✅ | 6/6 backend services: auth, voting, election, results, admin, email |
| Traffic flow matches documented architecture | ✅ | One-way: services → audit-service (audit does not call back) |
| Both ingress and egress policies present | ✅ | Two NetworkPolicy resources in one file |
| Frontend excluded correctly | ✅ | Frontend uses backend APIs; audit logging handled by backend services |

## Policy Configuration

### Policy 1: allow-to-audit (Ingress — 04a)
- **Target Namespace:** `uvote-dev`
- **Target Pod:** `app: audit-service`
- **Policy Type:** Ingress
- **Allowed Port:** `8005/TCP`
- **From:** Six backend service pods (individual `podSelector` entries, logical OR)
- **Labels:** `app: uvote`, `security: network-policy`, `purpose: audit-logging`, `policy-order: "04a"`

### Policy 2: allow-audit-egress (Egress — 04b)
- **Target Namespace:** `uvote-dev`
- **Target Pods:** Six backend services via `matchExpressions` with `In` operator
- **Policy Type:** Egress
- **Allows:**
  - Egress to `app: audit-service` on port `8005/TCP` (audit event submission)
  - Egress to `kube-system` namespace on port `53/UDP` and `53/TCP` (DNS resolution)
- **Labels:** `app: uvote`, `security: network-policy`, `purpose: audit-logging`, `policy-order: "04b"`

## Services Sending Audit Logs
From ARCHITECTURE.MD § "Events Logged":

| # | Service | Label | Events Logged |
|---|---------|-------|---------------|
| 1 | Auth Service | `app: auth-service` | Admin login attempts (success/failure), admin registration |
| 2 | Voting Service | `app: voting-service` | Vote cast (user + election, NOT candidate choice), token validation |
| 3 | Election Service | `app: election-service` | Election created, updated, activated, closed |
| 4 | Results Service | `app: results-service` | Results viewed (by admin or voter) |
| 5 | Admin Service | `app: admin-service` | Voter/candidate added/removed, token generated, CSV import |
| 6 | Email Service | `app: email-service` | Voting invitation sent, results notification sent, delivery tracking |

Each service has:
- **Egress to audit:** Allowed via `allow-audit-egress` policy (04b)
- **Ingress at audit-service:** Allowed via `allow-to-audit` policy (04a)

## Services NOT Sending Audit Logs Directly

| # | Service | Reason |
|---|---------|--------|
| 1 | Frontend Service | Communicates via backend APIs — audit logging is handled by the backend service that processes each request |
| 2 | PostgreSQL | Database receives audit writes; does not generate audit events itself |

## Audit Architecture (from Documentation)

```
auth-service ─────┐
voting-service ───┤
election-service ──┤
results-service ───┼──→ audit-service:8005 ──→ postgresql:5432
admin-service ────┤     (POST /api/audit/log)   (INSERT into audit_logs)
email-service ────┘

Traffic flow: ONE-WAY (services → audit → database)
Audit service does NOT initiate connections back to services.
```

### Audit-Service Database Access
The audit-service needs to persist logs to PostgreSQL:
- ✅ Already permitted by policy 02a (`allow-to-database` — ingress to DB)
- ✅ Already permitted by policy 02b (`allow-database-egress` — egress from audit-service)
- ✅ DB user: `audit_service` with INSERT, SELECT on `audit_logs`

## Security Requirements (from ARCHITECTURE.MD)
- **Append-only:** Audit logs cannot be modified or deleted (database triggers enforce immutability)
- **Hash-chained:** Each log entry includes a SHA-256 hash of the previous entry, enabling tamper detection
- **Vote anonymity preserved:** Audit logs record "voter X used token in election Y" but do NOT record candidate choice
- **Comprehensive coverage:** Every security-relevant action across all services is logged
- **Verification endpoint:** `GET /api/audit/verify` can check the entire hash chain for tampering

## Expected Impact
After applying this policy:
- ✅ All 6 backend services **CAN** send log events to `audit-service:8005`
- ✅ audit-service **CAN** persist logs to `postgresql:5432` (via policy 02)
- ✅ Complete, immutable audit trail maintained
- ✅ Frontend audit coverage handled indirectly via backend services
- ✅ Full zero-trust network policy set now deployed

## Deployment Commands
```bash
# Apply both policies (single file contains two NetworkPolicy resources)
kubectl apply -f uvote-platform/k8s/network-policies/04-allow-audit.yaml

# Verify BOTH policies were created
kubectl get networkpolicy -n uvote-dev -l purpose=audit-logging
# Expected:
# - allow-to-audit        (targets audit-service pod — ingress)
# - allow-audit-egress    (targets 6 service pods — egress)

# Inspect ingress policy
kubectl describe networkpolicy allow-to-audit -n uvote-dev

# Inspect egress policy
kubectl describe networkpolicy allow-audit-egress -n uvote-dev
```

## Testing Commands
```bash
# Verify all network policies are deployed
kubectl get networkpolicy -n uvote-dev
# Expected: 12 NetworkPolicy resources total (see full list below)

# Count all policies
kubectl get networkpolicy -n uvote-dev --no-headers | wc -l
# Expected: 12

# Verify audit policies specifically
kubectl get networkpolicy -n uvote-dev -l purpose=audit-logging
# Expected: 2 policies (allow-to-audit + allow-audit-egress)

# Note: Full end-to-end testing requires audit-service and
# other services to be deployed as containers.
```

## Test Results
- [ ] Ingress policy (`allow-to-audit`) created: ✅
- [ ] Egress policy (`allow-audit-egress`) created: ✅
- [ ] All network policies deployed: ✅
- [ ] Services can send to audit: ⚠️ (requires service deployment)
- [ ] Audit can write to database: ✅ (via policy 02)

## Network Policy Implementation Complete

All network policies are now deployed. The zero-trust security model from PLATFORM.MD is fully implemented:

| Order | Policy Name | File | Type | Effect |
|-------|-------------|------|------|--------|
| 00 | `default-deny` | `00-default-deny.yaml` | Ingress + Egress | Zero-trust foundation — deny all |
| 01 | `allow-dns` | `01-allow-dns.yaml` | Egress | Service discovery — DNS port 53 |
| 02a | `allow-to-database` | `02-allow-to-database.yaml` | Ingress | 6 services → PostgreSQL:5432 |
| 02b | `allow-database-egress` | `02-allow-to-database.yaml` | Egress | 6 services → PostgreSQL:5432 + DNS |
| 03 | `allow-from-ingress-to-frontend` | `03-allow-from-ingress.yaml` | Ingress | ingress-nginx → frontend:3000 |
| 03 | `allow-from-ingress-to-auth` | `03-allow-from-ingress.yaml` | Ingress | ingress-nginx → auth:8001 |
| 03 | `allow-from-ingress-to-election` | `03-allow-from-ingress.yaml` | Ingress | ingress-nginx → election:8002 |
| 03 | `allow-from-ingress-to-voting` | `03-allow-from-ingress.yaml` | Ingress | ingress-nginx → voting:8003 |
| 03 | `allow-from-ingress-to-results` | `03-allow-from-ingress.yaml` | Ingress | ingress-nginx → results:8004 |
| 03 | `allow-from-ingress-to-admin` | `03-allow-from-ingress.yaml` | Ingress | ingress-nginx → admin:8006 |
| 04a | `allow-to-audit` | `04-allow-audit.yaml` | Ingress | 6 services → audit:8005 |
| 04b | `allow-audit-egress` | `04-allow-audit.yaml` | Egress | 6 services → audit:8005 + DNS |

**Total: 12 NetworkPolicy resources across 5 files**

## Next Steps
1. ✅ Network policies complete — zero-trust model fully implemented
2. ⬜ Deploy application services (Docker images → Kind cluster)
3. ⬜ Create Ingress resources for routing (`k8s/ingress/evote-ingress.yaml`)
4. ⬜ End-to-end testing with real services
5. ⬜ Validate audit trail integrity with hash-chain verification
6. ⬜ Document for Stage 2 deliverable (platform demo)

## Documentation References
- **PLATFORM.MD § "Files"** — lists `04-allow-audit.yaml` as "Services → Audit"
- **PLATFORM.MD § "Network Security Architecture"** — defines the layered allow-rule model
- **ARCHITECTURE.MD § "Audit Service"** — port 8005, API endpoints, hash-chaining algorithm
- **ARCHITECTURE.MD § "Events Logged"** — comprehensive list of audit events per service
- **ARCHITECTURE.MD § "Security Measures"** — audit log immutability, hash chains, tamper detection
- **ARCHITECTURE.MD § "Database User Permissions"** — `audit_service` user with INSERT, SELECT on `audit_logs`

## Notes
- This single YAML file contains TWO NetworkPolicy resources (ingress + egress) separated by `---`.
- Traffic is one-way: services send events to audit-service; audit-service does NOT call back.
- The egress policy includes DNS (port 53 to kube-system) as a belt-and-suspenders measure alongside the global `01-allow-dns.yaml`.
- The `email-service` is included as an audit event sender (delivery tracking) even though it doesn't have database access — it only needs to reach audit-service, not postgresql directly.
- The `frontend-service` is excluded from direct audit access. Audit logging for user actions is handled by whichever backend service processes the request (auth-service for logins, voting-service for votes, etc.).
- Audit-service database access is already covered by policy 02 (both ingress to DB and egress from audit-service).
- With all 5 policy files applied, the U-Vote namespace has a complete zero-trust network posture: deny everything by default, allow only what is explicitly documented and required.
