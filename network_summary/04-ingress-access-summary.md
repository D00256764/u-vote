# Ingress Controller Access Policy Summary

**Generated:** 2026-02-15
**Policy Number:** 03
**File:** uvote-platform/k8s/network-policies/03-allow-from-ingress.yaml

## Purpose
Allows the Nginx Ingress Controller to route external traffic to application services, implementing the API Gateway pattern documented in PLATFORM.MD and ARCHITECTURE.MD. This is the single entry point for all external access to the U-Vote platform.

## Validation Against Documentation

| Check | Status | Detail |
|-------|--------|--------|
| Ingress namespace matches PLATFORM.MD | ✅ | `ingress-nginx` (confirmed in PLATFORM.MD § "Namespaces" table and Helm install instructions) |
| All exposed services from ARCHITECTURE.MD included | ✅ | 6/6 services with ingress routes listed (see table below) |
| Service ports match ARCHITECTURE.MD | ✅ | All ports verified against ARCHITECTURE.MD § "Service Descriptions" |
| Internal-only services excluded | ✅ | audit-service (8005), email-service (8007), postgresql (5432) are NOT exposed |
| Labels match documented conventions | ✅ | All use `app: <service-name>` pattern |
| Routing rules match ARCHITECTURE.MD | ✅ | All 6 routes from § "Nginx Ingress Controller" are covered |

## Policy Configuration
- **Target Namespace:** `uvote-dev`
- **Source Namespace:** `ingress-nginx`
- **Policy Type:** Ingress (to application services from ingress controller)
- **Source Selector:** `kubernetes.io/metadata.name: ingress-nginx` (auto-applied namespace label)
- **Design:** Separate NetworkPolicy per service (6 policies in one file)
- **Labels:** `app: uvote`, `security: network-policy`, `purpose: ingress-access`, `policy-order: "03"`

## Services EXPOSED via Ingress
From ARCHITECTURE.MD § "Nginx Ingress Controller (API Gateway)" routing rules:

| # | Service | Label | Port | Ingress Route | Purpose |
|---|---------|-------|------|---------------|---------|
| 1 | Frontend Service | `app: frontend-service` | 3000 | `/` | User interface — Jinja2 templates, static assets |
| 2 | Auth Service | `app: auth-service` | 8001 | `/api/auth` | Admin registration, login, JWT tokens |
| 3 | Election Service | `app: election-service` | 8002 | `/api/elections` | Election CRUD, lifecycle management |
| 4 | Voting Service | `app: voting-service` | 8003 | `/api/voting` | Token validation, ballot display, vote casting |
| 5 | Results Service | `app: results-service` | 8004 | `/api/results` | Vote tallying, winner calculation |
| 6 | Admin Service | `app: admin-service` | 8006 | `/api/admin` | Voter/candidate management, CSV import |

Each service has its own NetworkPolicy resource:
- `allow-from-ingress-to-frontend`
- `allow-from-ingress-to-auth`
- `allow-from-ingress-to-election`
- `allow-from-ingress-to-voting`
- `allow-from-ingress-to-results`
- `allow-from-ingress-to-admin`

## Services NOT EXPOSED (Internal Only)
Per ARCHITECTURE.MD security design:

| # | Service | Port | Reason | Access Method |
|---|---------|------|--------|---------------|
| 1 | Audit Service | 8005 | Internal logging only — exposing it would allow external actors to write arbitrary audit logs, breaking the integrity model | Via HTTP API calls from other services within the cluster |
| 2 | Email Service | 8007 | Triggered internally — uses SMTP for outbound email, not HTTP from clients | Called by admin-service via internal HTTP |
| 3 | PostgreSQL | 5432 | Database never externally accessible — controlled by policy 02 | Via policy 02 from 6 whitelisted services |

## API Gateway Pattern (from Documentation)
From PLATFORM.MD § "Ingress Controller" and ARCHITECTURE.MD § "Nginx Ingress Controller":

```
External Users / Browsers
        │
   Port 80/443
        │
        ▼
┌─────────────────────────┐
│  Nginx Ingress Controller│  (ingress-nginx namespace)
│                          │
│  - TLS termination       │
│  - Request routing       │
│  - Rate limiting         │
└────────────┬─────────────┘
             │
    ┌────────┼────────┬────────┬────────┬────────┐
    │        │        │        │        │        │
    ▼        ▼        ▼        ▼        ▼        ▼
 Frontend  Auth   Election  Voting  Results  Admin
  :3000   :8001    :8002    :8003    :8004   :8006
```

- **Single entry point** for all external traffic
- Services are **NOT** directly accessible from outside the cluster
- All external requests flow: Internet → Ingress Controller → Service
- Internal services (audit, email, database) have no ingress route

## Bidirectional Note
Since the ingress controller runs in a **different namespace** (`ingress-nginx`), we can only control the **ingress side** from our namespace (`uvote-dev`). The egress side (ingress controller sending traffic out to services) is managed within the `ingress-nginx` namespace — by default, most ingress controller deployments do not apply restrictive egress policies, so the controller can reach services in other namespaces.

If the `ingress-nginx` namespace also has default-deny policies, an egress policy would need to be applied there separately. This is outside the scope of the `uvote-dev` namespace policies.

## Expected Impact
After applying this policy:
- ✅ Ingress controller **CAN** reach all 6 exposed services on their specific ports
- ✅ Direct external access to services: **BLOCKED** (only via ingress)
- ✅ Internal services (audit, email, DB) remain **internal-only**
- ✅ Each service only accepts traffic on its specific port from ingress
- ⚠️ Full end-to-end functionality requires:
  - Ingress controller installed (`helm install ingress-nginx`)
  - Ingress resources created (routing rules in `k8s/ingress/`)
  - Application services deployed
  - DNS/host configuration for external access

## Deployment Commands
```bash
# Apply all 6 ingress access policies (single file)
kubectl apply -f uvote-platform/k8s/network-policies/03-allow-from-ingress.yaml

# Verify all policies were created (should show 6 new policies)
kubectl get networkpolicy -n uvote-dev -l purpose=ingress-access
# Expected:
# allow-from-ingress-to-frontend
# allow-from-ingress-to-auth
# allow-from-ingress-to-election
# allow-from-ingress-to-voting
# allow-from-ingress-to-results
# allow-from-ingress-to-admin

# Inspect a specific policy
kubectl describe networkpolicy allow-from-ingress-to-frontend -n uvote-dev
```

## Testing Commands
```bash
# Verify ingress controller namespace exists
kubectl get namespace ingress-nginx
# Expected: ingress-nginx namespace exists

# Check ingress controller pods are running
kubectl get pods -n ingress-nginx
# Expected: ingress-nginx-controller pods Running

# Verify all policies created with correct labels
kubectl get networkpolicy -n uvote-dev -l policy-order=03
# Expected: 6 policies listed

# Inspect individual policy details
kubectl describe networkpolicy allow-from-ingress-to-auth -n uvote-dev
# Expected: Ingress rule allowing from ingress-nginx namespace on port 8001

# Note: Full end-to-end testing requires services to be deployed
# and Ingress resources configured. The policies are ready for when
# services come online.
```

## Test Results
- [ ] All 6 policies created successfully: ✅
- [ ] Ingress rules for all exposed services present: ✅
- [ ] Internal services (audit, email, DB) not exposed: ✅
- [ ] Correct ports per service: ✅
- [ ] Ingress controller can reach services: ⚠️ (requires service deployment)
- [ ] Full end-to-end testing: ⬜ (requires service deployment + ingress resources)

## Policies Applied So Far
| Order | File | Policies | Status | Effect |
|-------|------|----------|--------|--------|
| 00 | `00-default-deny.yaml` | 1 | ✅ Applied | Deny all ingress + egress |
| 01 | `01-allow-dns.yaml` | 1 | ✅ Applied | Allow egress to kube-dns port 53 |
| 02a | `02-allow-to-database.yaml` | 1 | ✅ Applied | Ingress: 6 services → PostgreSQL port 5432 |
| 02b | `02-allow-to-database.yaml` | 1 | ✅ Applied | Egress: 6 services → PostgreSQL + DNS |
| 03 | `03-allow-from-ingress.yaml` | 6 | ✅ Applied | Ingress: Ingress Controller → 6 services |
| 04 | `04-allow-audit.yaml` | - | ⬜ Pending | Bidirectional: Services ↔ Audit Service |

**Total NetworkPolicy resources:** 10 (across 4 files)

## Next Steps
Apply `04-allow-audit.yaml` to enable bidirectional audit logging between services and the Audit Service.

## Documentation References
- **PLATFORM.MD § "Ingress Controller"** — Nginx Ingress Controller installation and configuration
- **PLATFORM.MD § "Namespaces"** — `ingress-nginx` namespace listed in the namespace table
- **PLATFORM.MD § "Network Security Architecture" → "External Access"** — "Only Ingress Controller can receive external traffic; services are NOT directly accessible from outside"
- **PLATFORM.MD § "Architecture Diagram"** — shows ingress controller as single entry point between external users and services
- **ARCHITECTURE.MD § "Nginx Ingress Controller (API Gateway)"** — routing rules mapping paths to services and ports
- **ARCHITECTURE.MD § "Service Descriptions"** — port numbers and purposes for each service

## Notes
- **Separate policies per service:** Each exposed service has its own NetworkPolicy. This is more verbose than a single policy with multiple rules but provides granular control — individual services can be disabled by deleting their specific policy without affecting others.
- **Port specificity:** Each policy allows only the exact port for that service (e.g., auth-service only allows 8001, not any port). This prevents the ingress controller from being used to probe other ports on a service pod.
- **Label-based filtering:** The `target-service` label on each policy makes it easy to find policies for a specific service: `kubectl get networkpolicy -l target-service=auth-service -n uvote-dev`.
- **No egress policy needed in uvote-dev:** The ingress controller's egress is managed in its own namespace. We only need to open the ingress door on our side.
- **No audit or email exposure:** These services are intentionally internal-only. The audit service receives events from other services via internal HTTP calls (covered by policy 04). The email service is triggered by admin-service and sends mail via SMTP (outbound), not inbound HTTP.
