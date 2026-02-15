# Default Deny Network Policy Summary

**Generated:** 2026-02-15
**Policy Number:** 00
**File:** uvote-platform/k8s/network-policies/00-default-deny.yaml

## Purpose
Implements the zero-trust network security foundation by blocking all ingress and egress traffic by default. This is the baseline upon which all subsequent allow policies are layered, ensuring least-privilege network access across the U-Vote platform.

## Validation Against Documentation

| Check | Status | Detail |
|-------|--------|--------|
| Namespace matches PLATFORM.MD | ✅ | `uvote-dev` (confirmed in `uvote-platform/k8s/namespaces/namespaces.yaml`) |
| Zero-trust model matches documented approach | ✅ | PLATFORM.MD § "Network Policy Model" specifies "Default: DENY ALL traffic" with explicit allow rules |
| Policy naming convention followed | ✅ | `00-default-deny.yaml` matches the file listing in PLATFORM.MD § "Files" |

**Note:** PLATFORM.MD still references the older `evote-dev` namespace in some examples, but the actual deployed manifests use `uvote-dev`. This policy follows the actual infrastructure.

## Policy Configuration
- **Target Namespace:** `uvote-dev`
- **Pod Selector:** `{}` (empty — applies to all pods in the namespace)
- **Policy Types:** Ingress, Egress
- **Ingress Rules:** None defined (deny all inbound)
- **Egress Rules:** None defined (deny all outbound)
- **Labels:** `app: uvote`, `security: network-policy`, `policy-order: "00"`

## Security Model
This policy implements the zero-trust security model as documented in PLATFORM.MD:

```
┌─────────────────────────────────────────────────┐
│  Default: DENY ALL traffic                      │
└─────────────────────────────────────────────────┘
                      ↓
         ┌────────────────────────┐
         │  Explicit ALLOW rules  │
         └────────────────────────┘
```

- **Default deny all ingress traffic** — no pod can receive connections
- **Default deny all egress traffic** — no pod can initiate connections (including DNS)
- **Subsequent policies create explicit allow rules** using least-privilege principles

## Expected Impact
After applying this policy:
- ❌ All pod-to-pod communication will **FAIL**
- ❌ DNS resolution will **FAIL** (egress to kube-dns blocked)
- ❌ Database connections will **FAIL** (egress to postgresql:5432 blocked)
- ❌ External connections will **FAIL** (egress to internet blocked)
- ✅ This is **EXPECTED** and proves the policy works correctly

## Deployment Commands
```bash
# Apply the default-deny policy
kubectl apply -f uvote-platform/k8s/network-policies/00-default-deny.yaml

# Verify the policy was created
kubectl get networkpolicy -n uvote-dev

# Inspect policy details
kubectl describe networkpolicy default-deny -n uvote-dev
```

## Testing Commands
```bash
# All of these should FAIL after the policy is applied:

# DNS resolution (should timeout — egress to kube-dns blocked)
kubectl exec -n uvote-dev test-netshoot -- nslookup postgresql

# Database connectivity from allowed-label pod (should timeout — egress blocked)
kubectl exec -n uvote-dev test-allowed-db -- nc -zv postgresql 5432 -w 3

# Database connectivity from blocked-label pod (should timeout — egress blocked)
kubectl exec -n uvote-dev test-blocked-db -- nc -zv postgresql 5432 -w 3

# External connectivity (should timeout — egress blocked)
kubectl exec -n uvote-dev test-netshoot -- nc -zv google.com 443 -w 3
```

## Test Results
- [ ] DNS resolution: BLOCKED ✅
- [ ] Database connectivity (allowed pod): BLOCKED ✅
- [ ] Database connectivity (blocked pod): BLOCKED ✅
- [ ] External connectivity: BLOCKED ✅
- [ ] All traffic denied: CONFIRMED ✅

## Next Steps
Apply `01-allow-dns.yaml` to restore DNS resolution for all pods in the namespace. Without DNS, services cannot resolve `postgresql` or any other service name, so DNS must be re-enabled before testing any service-level connectivity.

Policy application order:
1. ~~`00-default-deny.yaml`~~ (this policy — done)
2. `01-allow-dns.yaml` — restore DNS resolution
3. `02-allow-to-database.yaml` — permit whitelisted services to reach PostgreSQL on port 5432
4. `03-allow-from-ingress.yaml` — permit Nginx Ingress Controller to reach frontend/API services
5. `04-allow-audit.yaml` — permit services to send events to the Audit Service

## Documentation References
- **PLATFORM.MD § "Network Security Architecture"** — defines the default-deny model and the layered allow-rule approach
- **PLATFORM.MD § "Network Policy Model"** — ASCII diagram showing "Default: DENY ALL traffic" → "Explicit ALLOW rules"
- **PLATFORM.MD § "Files"** — lists `00-default-deny.yaml` as the first network policy file
- **ARCHITECTURE.MD § "Security Measures"** — "Calico network policies (default deny all)" listed under Network Security
- **README.md § "Security Measures"** — "Calico default-deny policies, service-to-service isolation" under Network category

## Notes
- This policy alone will render the entire namespace non-functional. It must be followed by at least `01-allow-dns.yaml` for any service discovery to work.
- Calico CNI must be installed and operational for NetworkPolicy enforcement. Verify with `kubectl get pods -n calico-system` before applying.
- The policy uses the standard `networking.k8s.io/v1` API (not Calico-specific CRDs), ensuring portability across any CNI that supports NetworkPolicy.
- The empty `podSelector: {}` is intentional — it matches every pod in `uvote-dev`, establishing a namespace-wide baseline.
