# DNS Allow Policy Summary

**Generated:** 2026-02-15
**Policy Number:** 01
**File:** uvote-platform/k8s/network-policies/01-allow-dns.yaml

## Purpose
Allows DNS resolution for all pods in the `uvote-dev` namespace by permitting egress traffic to kube-dns (CoreDNS) in `kube-system` on port 53. This restores service discovery after the default-deny policy blocks all traffic.

## Validation Against Documentation

| Check | Status | Detail |
|-------|--------|--------|
| Namespace matches PLATFORM.MD | ✅ | `uvote-dev` (confirmed in `uvote-platform/k8s/namespaces/namespaces.yaml`) |
| DNS requirement documented | ✅ | PLATFORM.MD § "Network Policy Model" lists "Allow DNS resolution" as an explicit allow rule |
| Supports service-to-service communication | ✅ | All 8+ services in ARCHITECTURE.MD resolve each other and `postgresql` by DNS name |
| File naming matches PLATFORM.MD | ✅ | `01-allow-dns.yaml` listed in PLATFORM.MD § "Files" |

## Policy Configuration
- **Target Namespace:** `uvote-dev`
- **Pod Selector:** `{}` (applies to all pods in the namespace)
- **Policy Type:** Egress only
- **Egress Rules:**
  - **To:** `kube-system` namespace (via `namespaceSelector` matching `kubernetes.io/metadata.name: kube-system`)
  - **Ports:** `53/UDP`, `53/TCP`
- **Labels:** `app: uvote`, `security: network-policy`, `purpose: dns`, `policy-order: "01"`

## Why This Policy is Critical
From ARCHITECTURE.MD, the following services rely on DNS to resolve dependencies:

| Service | Resolves |
|---------|----------|
| Frontend (port 3000) | auth-service, election-service, voting-service, results-service, admin-service |
| Auth Service (port 8001) | postgresql |
| Voting Service (port 8003) | postgresql, audit-service |
| Election Service (port 8002) | postgresql, audit-service |
| Results Service (port 8004) | postgresql |
| Audit Service (port 8005) | postgresql |
| Admin Service (port 8006) | postgresql, email-service, audit-service |
| Email Service (port 8007) | SMTP host (external) |

Without DNS, none of these service-to-service connections can be established because pods cannot translate service names (e.g., `postgresql`) into cluster IPs.

## Expected Impact
After applying this policy (with `00-default-deny.yaml` already active):
- ✅ DNS resolution will **WORK** — pods can resolve internal service names
- ✅ `nslookup postgresql` from any pod will return the ClusterIP
- ✅ `nslookup kubernetes` will resolve the API server
- ❌ Database connections still **BLOCKED** — DNS resolves the name but egress to port 5432 is not yet permitted
- ❌ Service-to-service HTTP still **BLOCKED** — no ingress/egress rules for service ports
- ❌ External connections still **BLOCKED** — only DNS egress to kube-system is allowed

## Deployment Commands
```bash
# Apply the DNS allow policy
kubectl apply -f uvote-platform/k8s/network-policies/01-allow-dns.yaml

# Verify the policy was created
kubectl get networkpolicy -n uvote-dev

# Inspect policy details
kubectl describe networkpolicy allow-dns -n uvote-dev
```

## Testing Commands
```bash
# Should SUCCEED (DNS resolution restored):
kubectl exec -n uvote-dev test-netshoot -- nslookup postgresql
kubectl exec -n uvote-dev test-netshoot -- nslookup postgresql.uvote-dev.svc.cluster.local
kubectl exec -n uvote-dev test-netshoot -- nslookup kubernetes

# Should still FAIL (no database egress policy yet):
kubectl exec -n uvote-dev test-allowed-db -- nc -zv postgresql 5432 -w 3
kubectl exec -n uvote-dev test-blocked-db -- nc -zv postgresql 5432 -w 3

# Should FAIL (external egress not permitted):
kubectl exec -n uvote-dev test-netshoot -- nc -zv google.com 443 -w 3
```

## Test Results
- [ ] Internal DNS resolution (`postgresql`): WORKS ✅
- [ ] Internal DNS resolution (`kubernetes`): WORKS ✅
- [ ] FQDN resolution (`postgresql.uvote-dev.svc.cluster.local`): WORKS ✅
- [ ] Database TCP connection: STILL BLOCKED ✅ (expected — no port 5432 egress rule)
- [ ] External connectivity: BLOCKED ✅ (expected — only DNS egress to kube-system allowed)

## Next Steps
Apply `02-allow-to-database.yaml` to enable TCP egress on port 5432 from whitelisted service pods (auth-service, voting-service, election-service, results-service, audit-service, admin-service) to the PostgreSQL pod.

## Policies Applied So Far
| Order | File | Status | Effect |
|-------|------|--------|--------|
| 00 | `00-default-deny.yaml` | ✅ Applied | Deny all ingress + egress |
| 01 | `01-allow-dns.yaml` | ✅ Applied | Allow egress to kube-dns port 53 |
| 02 | `02-allow-to-database.yaml` | ⬜ Pending | Allow whitelisted services → PostgreSQL |
| 03 | `03-allow-from-ingress.yaml` | ⬜ Pending | Allow Ingress Controller → services |
| 04 | `04-allow-audit.yaml` | ⬜ Pending | Allow services → Audit Service |

## Documentation References
- **PLATFORM.MD § "Network Policy Model"** — lists "Allow DNS resolution" as an explicit rule in the default-deny architecture
- **PLATFORM.MD § "Files"** — `01-allow-dns.yaml` is the second network policy file
- **PLATFORM.MD § "Calico Networking"** — "Network policy enforcement" requires DNS for service discovery
- **ARCHITECTURE.MD § "Architecture Diagram"** — shows all services communicating via named endpoints that require DNS
- **ARCHITECTURE.MD § "Deployment" § "Environment Variables"** — `DB_HOST=postgresql` confirms services use DNS names, not IPs

## Notes
- The `namespaceSelector` uses the built-in label `kubernetes.io/metadata.name: kube-system` which is automatically applied by Kubernetes to all namespaces. This avoids needing to manually label the `kube-system` namespace.
- Both UDP and TCP on port 53 are allowed. UDP handles standard queries; TCP is needed when DNS responses exceed 512 bytes (common with larger service meshes) and for DNSSEC.
- This policy only allows egress *to* kube-dns. It does not open any ingress ports on the application pods, maintaining the zero-trust posture for inbound traffic.
- External DNS resolution (e.g., `nslookup google.com`) may or may not work depending on CoreDNS upstream configuration. The policy permits reaching CoreDNS, but CoreDNS itself needs external egress to resolve non-cluster domains. For U-Vote's purposes, only internal DNS is required.
