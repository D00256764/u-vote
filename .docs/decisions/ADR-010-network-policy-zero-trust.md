# ADR-010: Zero-Trust Network Policies

## Status

**Status:** Accepted
**Date:** 2026-02-13
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

The microservices architecture (ADR-008) deploys 6+ services and a PostgreSQL database within a single Kubernetes namespace. Without network policies, any pod can communicate with any other pod — a compromised service could directly access the database, impersonate other services, or exfiltrate data to external hosts. A network security model is needed to restrict communication to only the paths required by the application architecture.

### Background

The project research paper identifies lateral movement as a key threat: "Once an attacker compromises a single service, they can freely access all other services and the database unless network-level restrictions are in place." Traditional perimeter security (firewalling the cluster boundary) does not protect against compromised internal pods.

The NIST Zero Trust Architecture (SP 800-207) principle states: "No implicit trust is granted to assets or user accounts based solely on their physical or network location." Applied to Kubernetes, this means no pod-to-pod communication is allowed by default.

### Requirements

- **R1:** Default deny all traffic — no implicit trust between any pods
- **R2:** Explicit allow rules for each required communication path
- **R3:** Per-service granularity — policies target individual services by label
- **R4:** Bidirectional enforcement — both ingress and egress controlled
- **R5:** Database access restricted to authorised services only
- **R6:** Frontend blocked from database (SQL injection defence-in-depth)
- **R7:** Internal services (audit, email) not externally accessible
- **R8:** DNS resolution must work for service discovery
- **R9:** Policies must be declarative YAML (Infrastructure as Code)

### Constraints

- **C1:** Must use standard Kubernetes NetworkPolicy API (portable across CNIs)
- **C2:** Calico CNI enforces policies (ADR-004)
- **C3:** Single namespace (uvote-dev) for MVP
- **C4:** Must not block required traffic — silent failures are dangerous

---

## Options Considered

### Option 1: Default Allow with Explicit Deny

**Description:**
Allow all traffic by default. Create deny rules for known-bad paths.

**Pros:**
- No policies needed initially — everything works immediately
- Deny rules added as threats are identified

**Cons:**
- Any new pod has full network access by default
- Unknown threats are not mitigated
- A compromised pod can reach all services and the database
- Reactive rather than proactive security
- Easy to miss deny rules for new attack vectors

**Evaluation:**
Fails R1 (default deny) and provides weak security. A "default allow" model trusts all pods — exactly the assumption that zero-trust architecture rejects.

### Option 2: Perimeter Security Only

**Description:**
Protect the cluster boundary (ingress/egress to external networks) but allow unrestricted internal traffic.

**Pros:**
- Simple to implement (single ingress controller, no internal policies)
- Familiar model from traditional infrastructure

**Cons:**
- No internal traffic restrictions
- Assumes internal network is trusted (castle-and-moat model)
- A compromised internal pod has unrestricted access
- No lateral movement prevention
- Does not satisfy zero-trust requirement

**Evaluation:**
Fails R1, R2, R5, R6, R7. Perimeter-only security is the model that zero-trust architecture was designed to replace.

### Option 3: Zero-Trust with Calico NetworkPolicies — Chosen

**Description:**
Default deny all traffic. Explicitly allow only required communication paths using Kubernetes NetworkPolicy resources. Each allowed path is documented, justified, and tested.

**Pros:**
- Strongest security posture achievable without a service mesh
- Each communication path is explicitly declared and auditable
- Per-service granularity via label selectors
- Bidirectional enforcement (ingress + egress)
- Standard Kubernetes API (portable)
- Infrastructure as Code (YAML files in version control)
- Progressive deployment — policies applied and tested incrementally

**Cons:**
- Higher initial complexity (12 policies across 5 files)
- Must understand bidirectional requirement (egress + ingress for each connection)
- Label mismatches cause silent failures (debugging required)
- Adding new services requires updating multiple policy files

**Evaluation:**
Meets all requirements (R1–R9). The complexity is manageable with good documentation and systematic testing.

### Option 4: Service Mesh (Istio)

**Description:**
Full service mesh with automatic mTLS, L7 traffic policies, circuit breaking, and observability via sidecar proxies.

**Pros:**
- Automatic mTLS between all services (encrypted + authenticated)
- L7 traffic management (HTTP-aware policies)
- Circuit breaking and retry logic
- Built-in observability (distributed tracing, metrics)

**Cons:**
- Massive resource overhead — sidecar proxy (~100MB) on every pod
- For 6 services × 2 replicas = 12 sidecars × 100MB = 1.2GB just for proxies
- Very high complexity (Istio has a steeper learning curve than Kubernetes itself)
- Adds latency (~5ms per hop through sidecar)
- Overkill for 6 services in a local cluster
- Would consume the entire Stage 1 timeline just for mesh setup

**Evaluation:**
Istio provides superior features but at prohibitive cost (resource overhead, complexity, time investment). The L3/L4 network policies provided by Calico are sufficient for the project's threat model. mTLS is noted as a future enhancement.

---

## Decision

**Chosen Option:** Zero-Trust with Calico NetworkPolicies (Option 3)

**Rationale:**
Zero-trust network policies provide the strongest security posture achievable without a service mesh, using standard Kubernetes APIs that are portable and declarative.

**Implemented Policy Architecture:**

| Policy | File | Type | Purpose |
|--------|------|------|---------|
| default-deny | `00-default-deny.yaml` | Ingress + Egress | Deny all traffic — zero-trust baseline |
| allow-dns | `01-allow-dns.yaml` | Egress | DNS resolution to kube-system:53 |
| allow-to-database (ingress) | `02-allow-to-database.yaml` | Ingress | 6 services → PostgreSQL:5432 |
| allow-database-egress | `02-allow-to-database.yaml` | Egress | Bidirectional for DB connections |
| allow-from-ingress (×6) | `03-allow-from-ingress.yaml` | Ingress | Nginx Ingress → 6 exposed services |
| allow-to-audit (ingress) | `04-allow-audit.yaml` | Ingress | 6 services → audit-service:8005 |
| allow-audit-egress | `04-allow-audit.yaml` | Egress | Bidirectional for audit connections |

**Total: 12 NetworkPolicy resources across 5 YAML files.**

**Key Factors:**

1. **Defence in depth (R5, R6):** Network policies are one layer in a multi-layer security model: network isolation → per-service DB users → parameterised queries → immutability triggers → hash chains. Each layer operates independently.

2. **Lateral movement prevention (R1):** A compromised frontend-service cannot reach the database (no network path exists). A compromised results-service cannot modify elections (read-only DB user + no network path to election-service).

3. **Standard API (C1):** All policies use `networking.k8s.io/v1` — portable to any CNI that supports NetworkPolicies (Calico, Cilium, etc.).

4. **Auditable:** Every policy is version-controlled YAML with clear labels and comments. The full communication matrix is documented in NETWORK-SECURITY.md.

---

## Consequences

### Positive Consequences

- **Comprehensive isolation:** All 12 policies tested and validated (see NETWORK-SECURITY.md §8)
- **SQL injection defence-in-depth:** Frontend-service has no network path to PostgreSQL
- **Data exfiltration prevention:** No general egress — pods cannot reach external hosts
- **Audit trail integrity:** Only authorised services can write to audit-service
- **Documented and reproducible:** All policies are Infrastructure as Code

### Negative Consequences

- **Operational complexity:** 12 policies across 5 files require careful management. Mitigated by: numbered file naming (`00-`, `01-`, etc.), comprehensive comments, and documentation.
- **Bidirectional requirement:** Forgetting egress policies causes silent failures. Mitigated by: documented as a key lesson learned, egress policies always paired with ingress policies in the same file.
- **New service onboarding:** Adding a service requires updating 2–3 policy files. Mitigated by: operational guide in NETWORK-SECURITY.md §11.1.

### Trade-offs Accepted

- **Zero-trust vs Simplicity:** Accepted 12 policies and operational complexity over a simple open network. The security benefit (preventing lateral movement, protecting the database, blocking exfiltration) is significant.
- **NetworkPolicies vs Service Mesh:** Accepted L3/L4 policies (no mTLS, no L7 filtering) over a full service mesh. The resource overhead and complexity of Istio is not justified for 6 services in a local cluster.

---

## Implementation Notes

### Technical Details

Full policy specifications are documented in [NETWORK-SECURITY.md](../NETWORK-SECURITY.md) (829 lines), including:
- Detailed specification of each policy
- Service communication matrix
- Testing methodology and results
- Threat mitigation analysis
- Defence-in-depth layers
- Operational troubleshooting guide

### Configuration

- **Policy API:** `networking.k8s.io/v1` (standard Kubernetes)
- **Enforcement:** Calico CNI (iptables data plane)
- **Namespace:** `uvote-dev`
- **Label convention:** `app: <service-name>` for policy targeting

### Integration Points

- **ADR-003 (Kubernetes):** Policies deployed to the Kind cluster
- **ADR-004 (Calico):** Calico enforces the policies
- **ADR-008 (Microservices):** Each service has label-based policy targeting
- **ADR-014 (DB Users):** Network policies complement per-service database permissions

---

## Validation

### Success Criteria

- [x] Default-deny blocks all traffic (tested with diagnostic pods)
- [x] DNS resolution works after policy 01
- [x] Whitelisted services connect to database; others blocked
- [x] Frontend-service has no path to database
- [x] Ingress controller routes to 6 exposed services
- [x] Internal services (audit, email) not externally accessible
- [x] 12 policies across 5 files — no conflicts

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Total policies | ≥10 | 12 |
| Policy files | ≤6 | 5 |
| Services with DB access | 6 | 6 (auth, election, voting, results, audit, admin) |
| Services blocked from DB | 2 | 2 (frontend, email) |
| Externally exposed services | 6 | 6 (via ingress controller) |

### Review Date

End of Stage 2 (April 2026) — evaluate adding mTLS via service mesh for production.

---

## References

- [Investigation Log §5.1](../INVESTIGATION-LOG.md#51-network-security-model-investigation) — Full evaluation
- [NETWORK-SECURITY.md](../NETWORK-SECURITY.md) — Comprehensive policy documentation (829 lines)
- [NIST SP 800-207 Zero Trust Architecture](https://csrc.nist.gov/publications/detail/sp/800-207/final)
- [Kubernetes NetworkPolicy Documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [ADR-004](ADR-004-calico-networking.md) — Calico CNI enforcement
- [ADR-008](ADR-008-microservices-architecture.md) — Service architecture

## Notes

The key lesson learned during implementation was the bidirectional requirement: in a default-deny architecture, both the sender's egress AND the receiver's ingress must be explicitly allowed. This was discovered when database connections timed out despite a correct ingress policy on PostgreSQL — the sending service's egress was still blocked by default-deny. This is documented in NETWORK-SECURITY.md §10.2.
