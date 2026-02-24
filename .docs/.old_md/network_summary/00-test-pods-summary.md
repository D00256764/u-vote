# Test Pods Generation Summary

**Generated:** 2026-02-15
**Component:** Test Pod Infrastructure
**File:** uvote-platform/k8s/network-policies/test-pods.yaml

## Purpose
Test pods for validating Calico network policies before and after application. These pods simulate both authorised and unauthorised services attempting to reach the PostgreSQL database, verifying that the default-deny model and explicit allow rules work as intended.

## Validation Against Documentation

| Check | Status | Detail |
|-------|--------|--------|
| Namespace matches namespaces.yaml | ✅ | `uvote-dev` (confirmed in `uvote-platform/k8s/namespaces/namespaces.yaml`) |
| Database service name matches | ✅ | `postgresql` (confirmed in `uvote-platform/k8s/database/db-deployment.yaml`, Service object name) |
| Labels match ARCHITECTURE.MD | ✅ | `auth-service` is listed as an allowed DB accessor in PLATFORM.MD Section "Service Isolation Rules" |
| Port numbers verified | ✅ | PostgreSQL on port `5432` (confirmed in db-deployment.yaml Service spec) |

**Documentation discrepancy noted:** PLATFORM.MD and ARCHITECTURE.MD still reference the older `evote-dev` namespace and `evote` naming convention, but the actual deployed manifests (`namespaces.yaml`, `db-deployment.yaml`) use `uvote-dev`. The test pods follow the actual infrastructure, not the outdated documentation references.

### Allowed Database Access Labels (from PLATFORM.MD)
- `auth-service`
- `voting-service`
- `election-service`
- `results-service`
- `audit-service`
- `admin-service`

## Test Pods Created

### 1. test-allowed-db
- **Purpose:** Verify that services with whitelisted labels CAN reach PostgreSQL
- **Label:** `app: auth-service`
- **Simulates:** The Auth Service (port 8001) — one of six services permitted database access
- **Image:** `postgres:15-alpine` (includes `pg_isready` and `psql` for connectivity testing)

### 2. test-blocked-db
- **Purpose:** Verify that services with non-whitelisted labels CANNOT reach PostgreSQL
- **Label:** `app: test-blocked`
- **Expected behaviour:** Connection to `postgresql:5432` should be DENIED (timeout or refused) when network policies are active
- **Image:** `postgres:15-alpine`

### 3. test-netshoot
- **Purpose:** General network diagnostics and troubleshooting
- **Label:** `app: test-netshoot`
- **Tools available:** `curl`, `nc` (netcat), `nslookup`, `dig`, `tcpdump`, `iperf`, `ping`, `traceroute`, `mtr`, `ip`, `ss`, `nmap`, `httpie`, and more
- **Image:** `nicolaka/netshoot:latest`

## Key Configuration Details
- **Namespace:** `uvote-dev`
- **Images used:** `postgres:15-alpine`, `nicolaka/netshoot:latest`
- **Restart policy:** `Always`
- **Additional label:** `purpose: network-policy-testing` (on all pods, for easy cleanup with `kubectl delete pods -l purpose=network-policy-testing -n uvote-dev`)

## Deployment Commands
```bash
# Deploy test pods
kubectl apply -f uvote-platform/k8s/network-policies/test-pods.yaml

# Wait for pods to be ready
kubectl wait --for=condition=Ready pod -l purpose=network-policy-testing -n uvote-dev --timeout=60s

# Verify pods are running
kubectl get pods -n uvote-dev -l purpose=network-policy-testing
```

## Testing Commands

### DNS Resolution
```bash
# Verify DNS resolves the database service
kubectl exec -n uvote-dev test-netshoot -- nslookup postgresql

# Full FQDN resolution
kubectl exec -n uvote-dev test-netshoot -- nslookup postgresql.uvote-dev.svc.cluster.local
```

### Database Connectivity — Allowed (auth-service label)
```bash
# pg_isready check (should SUCCEED when policies allow auth-service)
kubectl exec -n uvote-dev test-allowed-db -- pg_isready -h postgresql -p 5432

# TCP connectivity check
kubectl exec -n uvote-dev test-allowed-db -- nc -zv postgresql 5432
```

### Database Connectivity — Blocked (test-blocked label)
```bash
# pg_isready check (should FAIL/TIMEOUT when policies are active)
kubectl exec -n uvote-dev test-blocked-db -- pg_isready -h postgresql -p 5432

# TCP connectivity check with 3-second timeout
kubectl exec -n uvote-dev test-blocked-db -- nc -zv postgresql 5432 -w 3
```

### Service-to-Service Connectivity (from netshoot)
```bash
# Test connectivity to database
kubectl exec -n uvote-dev test-netshoot -- nc -zv postgresql 5432 -w 3

# Test connectivity to auth-service (if deployed)
kubectl exec -n uvote-dev test-netshoot -- curl -s --connect-timeout 3 http://auth-service:8001/health
```

## Expected Baseline Behaviour (Before Network Policies)
- All connectivity tests: **SHOULD SUCCEED** (no restrictions in place)
- DNS resolution: **SHOULD WORK** (Kubernetes CoreDNS resolves service names)
- Database connections: **SHOULD WORK** from all three pods

## Expected Behaviour (After Network Policies Applied)
- `test-allowed-db` → `postgresql:5432`: **SHOULD SUCCEED** (auth-service is whitelisted)
- `test-blocked-db` → `postgresql:5432`: **SHOULD FAIL** (test-blocked is not whitelisted)
- `test-netshoot` → `postgresql:5432`: **SHOULD FAIL** (test-netshoot is not whitelisted)
- DNS resolution from all pods: **SHOULD WORK** (01-allow-dns.yaml permits DNS)

## Cleanup
```bash
# Remove all test pods
kubectl delete -f uvote-platform/k8s/network-policies/test-pods.yaml

# Or remove by label
kubectl delete pods -l purpose=network-policy-testing -n uvote-dev
```

## Notes
- These pods are for testing only and should not be left running in production environments
- The `purpose: network-policy-testing` label enables targeted cleanup without affecting real workloads
- `test-allowed-db` uses the `auth-service` label — if the real auth-service is also deployed, both pods will match the same network policy rules, which is the intended test behaviour
- The netshoot pod has no database-access label and should be blocked by network policies, making it useful for confirming the default-deny stance

## Documentation References
- **PLATFORM.MD:** "Network Security Architecture" section — defines the default-deny model and service isolation rules listing the six services allowed database access
- **PLATFORM.MD:** "Database Management" section — confirms `postgresql` service name and port `5432`
- **ARCHITECTURE.MD:** "Service Descriptions" section — confirms service names and port assignments (auth-service on 8001, voting-service on 8003, etc.)
- **namespaces.yaml:** Confirms `uvote-dev` as the development namespace
- **db-deployment.yaml:** Confirms `postgresql` Deployment and Service with label `app: postgresql` on port `5432`
