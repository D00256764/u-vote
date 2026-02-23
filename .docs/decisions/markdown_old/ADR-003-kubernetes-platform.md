# ADR-003: Kubernetes Platform

## Status

**Status:** Accepted
**Date:** 2026-02-10
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

The U-Vote system requires a container orchestration platform that supports multi-replica deployments, health checking, rolling updates, network policy enforcement, namespace-based environment separation, and secret management. The platform must satisfy the PROJ I8009 module requirement for "operational platform on cloud-native technologies (containers, Kubernetes, or serverless)" and demonstrate DevOps competencies including Infrastructure as Code, resilience, and automated deployment.

### Background

Docker Compose was used during initial development for local multi-service orchestration. While adequate for starting containers together, Compose lacks the production-grade features required by the module brief: network policies for service isolation, health-based traffic routing, rolling update strategies, horizontal pod autoscaling, and namespace-based environment separation.

The module assessment rubric specifically allocates marks for "provisioned infrastructure using Infrastructure as Code" and "resilience evidence — fault tolerance, scaling, recovery from failures," both of which require an orchestration platform beyond Docker Compose.

### Requirements

- **R1:** Multi-replica deployments for high availability (minimum 2 replicas per service)
- **R2:** Health checking (liveness and readiness probes) to detect and recover from failures
- **R3:** Rolling update deployments with zero downtime
- **R4:** Network policy enforcement for zero-trust service isolation
- **R5:** Secret management for database credentials and JWT keys
- **R6:** Namespace-based environment separation (dev, test, prod)
- **R7:** Infrastructure as Code — all configuration in version-controlled YAML
- **R8:** Local development feasibility (must run on 16GB RAM development machine)
- **R9:** Industry relevance for CV and employability

### Constraints

- **C1:** Must run locally — no budget for cloud Kubernetes services (AKS, EKS, GKE) in Stage 1
- **C2:** Development machine has 16GB RAM and 4 CPU cores
- **C3:** Must support Calico CNI for NetworkPolicy enforcement
- **C4:** Two-semester timeline — platform must be operational by end of Semester 1

---

## Options Considered

### Option 1: Kubernetes (Full) — Chosen

**Description:**
Kubernetes is the industry-standard container orchestration platform, originally developed by Google and now maintained by the Cloud Native Computing Foundation (CNCF). It provides declarative configuration, self-healing, horizontal scaling, service discovery, network policies, RBAC, and a rich ecosystem of extensions (Helm, Calico, Prometheus, ArgoCD).

**Pros:**
- Industry standard — used by 96% of organisations adopting container orchestration (CNCF Survey 2023)
- Full feature set: replicas, health probes, rolling updates, network policies, secrets, namespaces
- Rich ecosystem: Helm charts, Calico CNI, Prometheus, ArgoCD, cert-manager
- Directly addresses all module learning outcomes (MLO2, MLO3)
- Multiple local distributions available (Kind, Minikube, K3s)
- Declarative Infrastructure as Code (YAML manifests)
- Extensive documentation and community support

**Cons:**
- Steep learning curve (especially NetworkPolicies, RBAC, StatefulSets)
- Higher resource requirements than Docker Compose
- More complex debugging (multi-layer abstraction: pod → container → service → ingress)
- Initial setup time significant (~2 hours for first cluster with Calico)

**Evaluation:**
Kubernetes meets all requirements (R1–R9). The learning curve is a feature, not a bug — the module explicitly requires demonstrating Kubernetes competency. The resource requirements are manageable with a lightweight local distribution (Kind).

### Option 2: Docker Swarm

**Description:**
Docker Swarm is Docker's built-in orchestration mode. It provides basic clustering, service replication, and load balancing using familiar Docker commands.

**Pros:**
- Simple setup (built into Docker Engine)
- Familiar Docker CLI commands
- Basic service replication and load balancing
- Low resource overhead

**Cons:**
- No NetworkPolicy support — critical disqualifier for zero-trust security
- Limited health check options (no readiness probes, no startup probes)
- No namespace isolation
- Declining industry adoption (Docker Inc. shifted focus to Docker Desktop)
- No equivalent of Helm charts for package management
- Limited rolling update strategies
- Would not demonstrate Kubernetes competency required by module

**Evaluation:**
Docker Swarm fails requirements R4 (network policies) and R6 (namespaces). These are non-negotiable for the project's security model and environment separation strategy. Swarm is also declining in industry relevance, reducing its CV value.

### Option 3: Docker Compose Only

**Description:**
Docker Compose orchestrates multi-container applications using a single `docker-compose.yml` file. Already used during development.

**Pros:**
- Simplest setup (already in use)
- Near-zero learning curve
- Minimal resource overhead
- Excellent for local development

**Cons:**
- No orchestration features: no replicas, no health checks, no rolling updates
- No network policies (all containers share a flat network)
- No namespace isolation
- No secret management (values in plaintext in YAML or .env files)
- Does not satisfy module requirements for cloud-native platform
- No Industry as Code beyond the Compose file itself

**Evaluation:**
Docker Compose is a development tool, not an operational platform. It fails requirements R1, R2, R3, R4, R5, R6, and R9. Submitting Docker Compose as the "operational platform" would not satisfy the module brief.

### Option 4: HashiCorp Nomad

**Description:**
Nomad is a lightweight orchestrator by HashiCorp that can schedule containers, VMs, and standalone binaries.

**Pros:**
- Simpler than Kubernetes (fewer concepts to learn)
- Multi-purpose (containers + other workloads)
- Good integration with HashiCorp ecosystem (Vault, Consul)
- Lower resource requirements than Kubernetes

**Cons:**
- Smaller community and ecosystem than Kubernetes
- No native NetworkPolicy equivalent (requires Consul Connect for service mesh)
- Less industry adoption (Kubernetes dominates)
- Limited documentation for voting system use cases
- Would require learning Nomad's HCL configuration language
- Less relevant for employer expectations

**Evaluation:**
Nomad meets some requirements but lacks native network policy support (R4) and has significantly less industry relevance (R9) than Kubernetes. The smaller ecosystem means fewer ready-made solutions for monitoring, logging, and CI/CD integration.

---

## Decision

**Chosen Option:** Kubernetes (Option 1)

**Rationale:**
Kubernetes is the only option that satisfies all nine requirements. The decision matrix (§3.3.3 of Investigation Log) scored Kubernetes at 9.55/10, far ahead of Docker Swarm (4.35), Compose (2.55), and Nomad (5.80).

**Key Factors:**

1. **Module alignment (R7, R9):** The module brief explicitly requires "operational platform on cloud-native technologies (containers, Kubernetes, or serverless)." Kubernetes is the canonical implementation of this requirement.

2. **Network policy enforcement (R4):** The zero-trust security model (ADR-010) requires Kubernetes NetworkPolicies enforced by Calico. No other evaluated platform provides this capability natively.

3. **Feature completeness (R1–R6):** Replicas, health probes, rolling updates, secrets, and namespaces are all first-class Kubernetes features. No workarounds or third-party add-ons needed.

4. **Industry standard (R9):** 96% of organisations using container orchestration use Kubernetes. This competency is directly relevant for employment after graduation.

5. **Ecosystem richness:** Helm for package management, Calico for networking, Prometheus for monitoring (Stage 2), ArgoCD for GitOps (Stage 2) — all integrate natively with Kubernetes.

---

## Consequences

### Positive Consequences

- **Full DevOps demonstration:** Kubernetes enables demonstration of all module-required DevOps practices: IaC, CI/CD, resilience, scaling, network security, secrets management
- **Production-ready architecture:** The same manifests (with minor modifications) can deploy to cloud Kubernetes services (AKS, EKS) for production
- **Rich feature set:** Health probes detect failing services, rolling updates provide zero-downtime deployments, replicas provide fault tolerance
- **NetworkPolicy support:** Enables the zero-trust security model that is central to the project's security architecture

### Negative Consequences

- **Learning curve:** Kubernetes concepts (pods, services, deployments, network policies, RBAC, persistent volumes) require significant learning investment. Mitigated by: starting with Kind (simplest local distribution), automating setup with Python scripts, and extensive documentation of every configuration decision.
- **Resource overhead:** Running a 3-node Kind cluster with Calico, 6 services, and PostgreSQL requires ~4–6GB of RAM. Mitigated by: setting resource limits on all pods, using 2 replicas (minimum for HA) rather than 3.
- **Debugging complexity:** Multi-layer abstraction makes troubleshooting harder than Docker Compose. Mitigated by: comprehensive logging, health endpoints on all services, and detailed troubleshooting documentation in PLATFORM.MD.

### Trade-offs Accepted

- **Complexity vs Features:** Accepted Kubernetes' operational complexity in exchange for production-grade features and module alignment. Docker Compose is simpler but fundamentally inadequate for the project requirements.
- **Resource usage vs Realism:** Accepted higher resource usage (4–6GB vs ~1GB for Compose) in exchange for a realistic multi-node cluster that demonstrates real-world deployment patterns.

---

## Implementation Notes

### Technical Details

- **Distribution:** Kind (Kubernetes IN Docker) — see ADR-012 for distribution selection
- **Cluster topology:** 1 control-plane node + 2 worker nodes
- **CNI:** Calico v3.26.1 (custom CNI, default CNI disabled)
- **Namespaces:** `uvote-dev`, `uvote-test`, `uvote-prod`
- **Storage:** PersistentVolumeClaim (5Gi) for PostgreSQL
- **Ingress:** Nginx Ingress Controller via Helm

### Configuration

Kind cluster configuration (`kind-config.yaml`):
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
networking:
  disableDefaultCNI: true      # Required for Calico
  podSubnet: "192.168.0.0/16"  # Calico's default CIDR
```

### Integration Points

- **ADR-004 (Calico):** Calico CNI installed on the Kubernetes cluster for network policy enforcement
- **ADR-010 (Zero-Trust):** 12 NetworkPolicy resources deployed to the cluster
- **ADR-011 (Secrets):** Kubernetes Secrets store database credentials and JWT keys
- **ADR-012 (Kind):** Kind is the specific local Kubernetes distribution

---

## Validation

### Success Criteria

- [x] 3-node Kind cluster operational (1 control-plane, 2 workers)
- [x] Calico CNI installed and all pods healthy
- [x] Namespaces created (uvote-dev, uvote-test, uvote-prod)
- [x] PostgreSQL deployed with persistent storage
- [x] Network policies enforced (tested with diagnostic pods)
- [x] Services deployed and responding to health probes
- [x] Deployment automated via Python scripts

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Cluster creation time | <5 minutes | ~2 minutes (Kind) |
| Full deployment time | <10 minutes | ~5 minutes (scripted) |
| Cluster RAM usage | <8GB | ~4–6GB |
| Node count | 3 | 3 (1 CP + 2 workers) |
| NetworkPolicy count | ≥10 | 12 |

### Review Date

End of Stage 2 (April 2026) — evaluate migration to cloud Kubernetes (AKS/EKS) for production.

---

## References

- [Investigation Log §3.3](../INVESTIGATION-LOG.md#33-container-orchestration-investigation) — Full evaluation details
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Kind Documentation](https://kind.sigs.k8s.io/)
- [CNCF Survey 2023](https://www.cncf.io/reports/cncf-annual-survey-2023/) — Kubernetes adoption statistics
- [ADR-004](ADR-004-calico-networking.md) — CNI plugin selection
- [ADR-010](ADR-010-network-policy-zero-trust.md) — Zero-trust network security model
- [ADR-012](ADR-012-kind-local-development.md) — Local K8s distribution selection

## Notes

Docker Compose remains in the repository (`docker-compose.yml`) for rapid local development without Kubernetes. Developers can use Compose for code iteration and Kubernetes for integration testing and platform demonstrations.
