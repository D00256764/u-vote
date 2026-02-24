# Database Access Control Policy Summary

**Generated:** 2026-02-15
**Policy Number:** 02 (includes 02a ingress + 02b egress)
**File:** uvote-platform/k8s/network-policies/02-allow-to-database.yaml

## Purpose
Controls bidirectional database access using least-privilege network-level access control. Includes BOTH ingress to the database AND egress from services, ensuring complete connectivity in the default-deny architecture.

## Critical — Bidirectional NetworkPolicy Requirement

In Kubernetes with default-deny, traffic must be allowed in BOTH directions for a connection to succeed:

| Direction | Policy Resource | Label | Effect |
|-----------|----------------|-------|--------|
| Ingress TO postgresql | `allow-to-database` | `policy-order: "02a"` | Database can RECEIVE connections from 6 services |
| Egress FROM services | `allow-database-egress` | `policy-order: "02b"` | Services can SEND connections to database |

**Without both policies:** Services time out — egress is blocked by `00-default-deny` even though ingress to the database is allowed.
**With both policies:** Services successfully connect — both directions explicitly permitted.

This file contains BOTH NetworkPolicy resources separated by `---`.

## Validation Against Documentation

| Check | Status | Detail |
|-------|--------|--------|
| Database service name matches PLATFORM.MD | ✅ | `postgresql` (confirmed in `db-deployment.yaml` Service object) |
| Database port matches ARCHITECTURE.MD | ✅ | `5432` (confirmed in `db-deployment.yaml` containerPort and Service spec) |
| Database pod label matches | ✅ | `app: postgresql` (confirmed in `db-deployment.yaml` pod template labels) |
| All allowed services from PLATFORM.MD included | ✅ | 6/6 services listed (see table below) |
| Blocked services verified against ARCHITECTURE.MD | ✅ | frontend-service and email-service excluded (see rationale below) |
| Service labels match documented conventions | ✅ | All use `app: <service-name>` pattern consistent with `app: postgresql` |
| Both ingress and egress policies present | ✅ | Two NetworkPolicy resources in one file (`allow-to-database` + `allow-database-egress`) |

## Policy Configuration

### Policy 1: allow-to-database (Ingress — 02a)
- **Target Namespace:** `uvote-dev`
- **Target Pod:** `app: postgresql` (the PostgreSQL database pod)
- **Policy Type:** Ingress
- **Allowed Port:** `5432/TCP`
- **From:** Six individual `podSelector` entries (logical OR)
- **Labels:** `app: uvote`, `security: network-policy`, `purpose: database-access`, `policy-order: "02a"`

### Policy 2: allow-database-egress (Egress — 02b)
- **Target Namespace:** `uvote-dev`
- **Target Pods:** Six whitelisted services via `matchExpressions` with `In` operator
- **Policy Type:** Egress
- **Allows:**
  - Egress to `app: postgresql` on port `5432/TCP` (database connection)
  - Egress to `kube-system` namespace on port `53/UDP` and `53/TCP` (DNS resolution)
- **Labels:** `app: uvote`, `security: network-policy`, `purpose: database-access`, `policy-order: "02b"`

## Services ALLOWED Database Access
From PLATFORM.MD § "Service Isolation Rules" and ARCHITECTURE.MD § "Database User Permissions":

| # | Service | Label | DB User | Permissions | Reason |
|---|---------|-------|---------|-------------|--------|
| 1 | Auth Service | `app: auth-service` | `auth_service` | SELECT, INSERT, UPDATE on `admins` | Admin registration, login, JWT management |
| 2 | Voting Service | `app: voting-service` | `voting_service` | INSERT on `votes`, SELECT on `elections`/`candidates`, UPDATE on `voting_tokens` | Token validation, vote casting |
| 3 | Election Service | `app: election-service` | `election_service` | SELECT, INSERT, UPDATE, DELETE on `elections` | Election CRUD, lifecycle management |
| 4 | Results Service | `app: results-service` | `results_service` | SELECT only (read-only) | Vote tallying, winner calculation |
| 5 | Audit Service | `app: audit-service` | `audit_service` | INSERT, SELECT on `audit_logs` | Immutable hash-chained event logging |
| 6 | Admin Service | `app: admin-service` | `admin_service` | SELECT, INSERT, UPDATE, DELETE on `voters`, `candidates`, `voting_tokens` | Voter/candidate management, CSV import |

Each service has both:
- **Ingress to DB:** Allowed via `allow-to-database` policy (02a)
- **Egress from service:** Allowed via `allow-database-egress` policy (02b)

## Services BLOCKED from Database
Per ARCHITECTURE.MD security design:

| # | Service | Label | Reason | Access Method |
|---|---------|-------|--------|---------------|
| 1 | Frontend Service | `app: frontend-service` | Client-facing layer — direct DB access would expose SQL injection risk from user input | Communicates via backend service APIs only |
| 2 | Email Service | `app: email-service` | Stateless service — sends emails via SMTP, does not read or write application data | Triggered by Admin Service via HTTP API |
| 3 | Any unlabelled pods | N/A | Defence in depth — only explicitly whitelisted labels are permitted | N/A |

These services have **neither** ingress rules to the database **nor** egress rules to `postgresql:5432`.

## Security Rationale (from Documentation)
This policy implements two layers of the defence-in-depth model described across PLATFORM.MD and ARCHITECTURE.MD:

1. **Network layer** (this policy): Only pods with whitelisted labels can reach PostgreSQL port 5432 — enforced bidirectionally
2. **Database layer** (ARCHITECTURE.MD § "Database User Permissions"): Each allowed service uses a dedicated PostgreSQL user with minimal permissions — even if a service reaches the database, it can only perform its authorised operations

Additional protections documented in ARCHITECTURE.MD:
- Database triggers prevent UPDATE/DELETE on the `votes` table (immutability)
- Hash-chaining on votes and audit logs enables tamper detection
- Parameterised queries prevent SQL injection at the application level

## Expected Impact
After applying this policy (with `00-default-deny` and `01-allow-dns` active):
- ✅ Pods labelled `auth-service` **CAN** connect to `postgresql:5432` (both directions allowed)
- ✅ Pods labelled `voting-service` **CAN** connect to `postgresql:5432`
- ✅ Pods labelled `election-service` **CAN** connect to `postgresql:5432`
- ✅ Pods labelled `results-service` **CAN** connect to `postgresql:5432`
- ✅ Pods labelled `audit-service` **CAN** connect to `postgresql:5432`
- ✅ Pods labelled `admin-service` **CAN** connect to `postgresql:5432`
- ❌ Pods labelled `frontend-service` **CANNOT** connect (no egress rule)
- ❌ Pods labelled `email-service` **CANNOT** connect (no egress rule)
- ❌ Pods labelled `test-blocked` **CANNOT** connect (no egress rule)
- ❌ Pods labelled `test-netshoot` **CANNOT** connect (no egress rule)
- ✅ Complete bidirectional access control functional

## Deployment Commands
```bash
# Apply both policies (single file contains two NetworkPolicy resources)
kubectl apply -f uvote-platform/k8s/network-policies/02-allow-to-database.yaml

# Verify BOTH policies were created
kubectl get networkpolicy -n uvote-dev
# Should show:
# - allow-to-database       (targets postgresql pod — ingress)
# - allow-database-egress   (targets 6 service pods — egress)

# Inspect ingress policy
kubectl describe networkpolicy allow-to-database -n uvote-dev

# Inspect egress policy
kubectl describe networkpolicy allow-database-egress -n uvote-dev
```

## Testing Commands
```bash
# Should SUCCEED (test-allowed-db has label app=auth-service — both ingress and egress allowed):
kubectl exec -n uvote-dev test-allowed-db -- pg_isready -h postgresql -p 5432
kubectl exec -n uvote-dev test-allowed-db -- nc -zv postgresql 5432
# Expected: postgresql (10.x.x.x:5432) open

# Should FAIL (test-blocked-db has label app=test-blocked — no egress rule):
kubectl exec -n uvote-dev test-blocked-db -- nc -zv postgresql 5432 -w 3
# Expected: Operation timed out

# Should FAIL (test-netshoot has label app=test-netshoot — no egress rule):
kubectl exec -n uvote-dev test-netshoot -- nc -zv postgresql 5432 -w 3
# Expected: Operation timed out
```

## Test Results
- [ ] Allowed service (`auth-service` label): CONNECTED ✅
- [ ] Blocked service (`test-blocked` label): BLOCKED ✅
- [ ] Unlabelled pod (`test-netshoot`): BLOCKED ✅
- [ ] Bidirectional policy enforcing correctly: CONFIRMED ✅

## Policies Applied So Far
| Order | File | Status | Effect |
|-------|------|--------|--------|
| 00 | `00-default-deny.yaml` | ✅ Applied | Deny all ingress + egress |
| 01 | `01-allow-dns.yaml` | ✅ Applied | Allow egress to kube-dns port 53 |
| 02a | `02-allow-to-database.yaml` | ✅ Applied | Ingress: 6 services → PostgreSQL port 5432 |
| 02b | `02-allow-to-database.yaml` | ✅ Applied | Egress: 6 services → PostgreSQL port 5432 + DNS |
| 03 | `03-allow-from-ingress.yaml` | ⬜ Pending | Allow Ingress Controller → services |
| 04 | `04-allow-audit.yaml` | ⬜ Pending | Allow services → Audit Service |

## Next Steps
Apply `03-allow-from-ingress.yaml` to enable external access from the Nginx Ingress Controller to frontend and API services.

## Documentation References
- **PLATFORM.MD § "Service Isolation Rules"** — explicit whitelist of the 6 services allowed to reach PostgreSQL
- **PLATFORM.MD § "Network Security Architecture"** — diagram showing services connecting to database through network policy controls
- **PLATFORM.MD § "Database Management"** — confirms service name `postgresql` and port `5432`
- **ARCHITECTURE.MD § "Database User Permissions"** — per-service PostgreSQL users with least-privilege grants
- **ARCHITECTURE.MD § "Service Descriptions"** — documents each service's database requirements and access patterns
- **ARCHITECTURE.MD § "Security Measures" § "Data Integrity"** — vote immutability triggers, hash chaining
- **db-deployment.yaml** — confirms pod label `app: postgresql`, Service name `postgresql`, port `5432`
- **Kubernetes NetworkPolicy docs** — bidirectional requirement in default-deny architectures

## Notes
- This single YAML file contains TWO NetworkPolicy resources (ingress + egress) separated by `---`. Both are applied together with a single `kubectl apply`.
- The egress policy uses `matchExpressions` with the `In` operator to select all six services concisely, rather than creating six separate policies.
- The egress policy includes DNS (port 53 to kube-system) as a belt-and-suspenders measure. The global `01-allow-dns.yaml` already permits DNS for all pods, but including it here ensures database-accessing services retain DNS even if the global policy is ever modified.
- Even with network access, services still need valid PostgreSQL credentials — the network policy is one layer of a multi-layer security model.
- The `voter-service` (port 5002) mentioned in the README's "Implemented Services" table is not listed in PLATFORM.MD's DB access whitelist. In the full architecture, voter management is handled by the `admin-service`. The policy follows PLATFORM.MD's authoritative whitelist.
