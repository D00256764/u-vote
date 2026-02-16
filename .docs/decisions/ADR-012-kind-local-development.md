# ADR-012: Kind for Local Development

## Status

**Status:** Accepted
**Date:** 2026-02-14
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

After selecting Kubernetes as the orchestration platform (ADR-003), a local Kubernetes distribution must be chosen for development and Stage 1 demonstrations. The distribution must support multi-node clusters, custom CNI plugins (specifically Calico for network policies), port forwarding for host access, and fast cluster creation/deletion during iterative development.

### Background

Cloud-managed Kubernetes (AKS, EKS, GKE) is not feasible for Stage 1 due to budget constraints. The development environment is a single machine with 16GB RAM and 4 CPU cores running Ubuntu 22.04. The chosen distribution must run efficiently within these resource constraints while providing a realistic multi-node Kubernetes experience.

### Requirements

- **R1:** Multi-node cluster support (1 control-plane + 2 workers minimum)
- **R2:** Custom CNI support (`disableDefaultCNI: true` for Calico)
- **R3:** Port forwarding from host to cluster (HTTP/HTTPS access)
- **R4:** Fast cluster creation and deletion (<5 minutes)
- **R5:** Low resource overhead (must share 16GB RAM with development tools)
- **R6:** Docker-compatible (uses Docker as container runtime)
- **R7:** Active maintenance and community support

### Constraints

- **C1:** 16GB RAM total on development machine
- **C2:** 4 CPU cores available
- **C3:** Must support Calico v3.26.1 CNI
- **C4:** Must support standard `kubectl` commands

---

## Options Considered

### Option 1: Kind (Kubernetes IN Docker) — Chosen

**Description:**
Kind runs Kubernetes clusters using Docker containers as nodes. Each Kubernetes node is a Docker container running systemd and containerd. Developed by the Kubernetes SIG Testing group, originally for testing Kubernetes itself.

**Pros:**
- Multi-node clusters (configurable via YAML)
- `disableDefaultCNI: true` support (essential for Calico)
- Fast cluster creation (~60 seconds for 3 nodes)
- Fast cluster deletion (~10 seconds)
- Low resource overhead (~500MB per node)
- Port mapping from host to control-plane node
- Official Kubernetes SIG project (well-maintained)
- Excellent documentation including Calico guides
- `kind load docker-image` for loading local images

**Cons:**
- Nodes are Docker containers (not VMs) — some kernel-level features differ
- No built-in dashboard or add-on manager
- Networking between nodes uses Docker's bridge network (not bare-metal BGP)

**Evaluation:**
Meets all requirements (R1–R7). The Docker container abstraction is sufficient for development and demonstration purposes.

### Option 2: Minikube

**Description:**
Minikube runs a single-node Kubernetes cluster in a VM (VirtualBox, HyperKit) or Docker container.

**Pros:**
- Built-in add-on manager (dashboard, metrics-server, ingress)
- Supports multiple drivers (VM, Docker, bare-metal)
- Wide documentation coverage

**Cons:**
- Single-node by default (multi-node is experimental)
- Custom CNI support requires specific driver configuration
- Heavier resource usage when using VM driver (~2GB per node)
- Slower cluster creation (~2–3 minutes)
- Single-node limits realism of network policies across nodes

**Evaluation:**
Minikube's single-node default fails R1. While multi-node mode exists, it is experimental and less documented than Kind's stable multi-node support. The inability to demonstrate pod scheduling across worker nodes reduces the realism of the platform demonstration.

### Option 3: K3s

**Description:**
K3s is a lightweight Kubernetes distribution by Rancher (now SUSE). It replaces etcd with SQLite and bundles components into a single binary.

**Pros:**
- Very lightweight (~512MB RAM for single node)
- Production-ready (used in edge computing and IoT)
- Fast startup
- Built-in Traefik ingress controller

**Cons:**
- Custom CNI requires removing the default Flannel and installing Calico manually
- Uses containerd directly (not Docker) — different image loading workflow
- Less documented for Kind-style local development
- Multi-node requires separate server + agent processes
- Built-in Traefik conflicts if using Nginx Ingress

**Evaluation:**
K3s is production-capable but its Flannel default requires manual removal before Calico installation (additional complexity). The non-Docker container runtime means `docker build` images must be imported differently than Kind's `kind load` command.

### Option 4: Docker Desktop Kubernetes

**Description:**
Kubernetes built into Docker Desktop (macOS, Windows, Linux).

**Pros:**
- Zero additional installation (bundled with Docker Desktop)
- Single-click enable/disable

**Cons:**
- Single-node only (fails R1)
- Cannot disable default CNI (fails R2)
- Limited configuration options
- Commercial licence requirements for organisations >250 employees
- No multi-node support

**Evaluation:**
Fails R1 (multi-node) and R2 (custom CNI). Fundamentally inadequate for demonstrating network policy enforcement across nodes.

---

## Decision

**Chosen Option:** Kind (Option 1)

**Rationale:**
Kind is the only local distribution that provides stable multi-node clusters with custom CNI support in a lightweight Docker-based environment.

**Key Factors:**

1. **Multi-node + Custom CNI (R1, R2):** Kind is the only option where both features are stable and well-documented. The `disableDefaultCNI: true` configuration is a first-class Kind feature, not a workaround.

2. **Fast iteration (R4):** Cluster creation in ~60 seconds and deletion in ~10 seconds enables rapid iteration during development. Over the 12-week Stage 1, dozens of cluster create/destroy cycles were performed.

3. **Local image loading (R6):** `kind load docker-image <image>` loads locally-built Docker images directly into Kind nodes without a container registry. This eliminates the need for a registry service and speeds up the build-deploy-test cycle.

4. **Resource efficiency (R5):** 3 Kind nodes consume ~1.5GB RAM total, leaving ~14.5GB for application services and development tools.

---

## Consequences

### Positive Consequences

- **Realistic multi-node environment:** Pods are scheduled across 2 worker nodes, demonstrating real Kubernetes scheduling
- **Calico-compatible:** `disableDefaultCNI: true` works perfectly with Calico operator installation
- **Fast development cycle:** Create cluster → build images → load images → deploy → test → delete cluster in under 5 minutes
- **Portable:** Kind works identically on Linux, macOS, and Windows (WSL2)

### Negative Consequences

- **Not production-grade:** Kind is designed for development and testing, not production workloads. Mitigated by: the same Kubernetes manifests will deploy to AKS/EKS for production (Stage 2).
- **Docker dependency:** Kind requires Docker, which adds its own resource overhead. Mitigated by: Docker is already required for building service images.
- **No built-in dashboard:** Must install Kubernetes Dashboard separately if needed. Mitigated by: `kubectl` CLI provides all necessary information.

### Trade-offs Accepted

- **Kind vs K3s:** Accepted Kind's non-production-grade nature over K3s's production-readiness because Kind has superior multi-node + custom CNI support with simpler setup.
- **Docker containers vs VMs:** Accepted that Kind nodes are Docker containers (not VMs) — some kernel-level features may differ from production. For NetworkPolicy testing and application development, this is not a significant limitation.

---

## Implementation Notes

### Technical Details

Cluster configuration file:
```yaml
# uvote-platform/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
      - containerPort: 443
        hostPort: 443
  - role: worker
  - role: worker
networking:
  disableDefaultCNI: true
  podSubnet: "192.168.0.0/16"
```

Cluster lifecycle commands:
```bash
# Create
kind create cluster --config kind-config.yaml --name evote

# Load images
kind load docker-image auth-service:latest --name evote
kind load docker-image voting-service:latest --name evote

# Delete
kind delete cluster --name evote
```

### Configuration

- **Cluster name:** `evote`
- **Nodes:** 3 (1 control-plane, 2 workers)
- **Pod subnet:** `192.168.0.0/16` (Calico default)
- **Port mappings:** 80 → 80, 443 → 443 (for Ingress)
- **CNI:** Disabled (Calico installed separately)

### Integration Points

- **ADR-003 (Kubernetes):** Kind is the chosen local K8s distribution
- **ADR-004 (Calico):** Calico installed on the Kind cluster
- **ADR-008 (Microservices):** Services deployed to Kind cluster as Deployments

---

## Validation

### Success Criteria

- [x] 3-node cluster created successfully
- [x] Calico CNI installed and operational
- [x] Local Docker images loaded via `kind load`
- [x] Port forwarding works (localhost:80 → Ingress)
- [x] Cluster creation < 2 minutes
- [x] Cluster deletion < 30 seconds
- [x] Resource usage < 2GB for empty cluster

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Cluster creation time | <5 min | ~60 seconds |
| Cluster deletion time | <1 min | ~10 seconds |
| Node RAM (empty cluster) | <2GB | ~1.5GB |
| Image load time (per image) | <30s | ~5–10s |

### Review Date

End of Stage 2 (April 2026) — evaluate migration to cloud K8s (AKS/EKS).

---

## References

- [Investigation Log §3.3.4](../INVESTIGATION-LOG.md#334-local-kubernetes-distribution-selection) — Distribution comparison
- [Kind Documentation](https://kind.sigs.k8s.io/)
- [Kind + Calico Guide](https://docs.tigera.io/calico/latest/getting-started/kubernetes/kind)
- [ADR-003](ADR-003-kubernetes-platform.md) — Kubernetes platform selection
- [ADR-004](ADR-004-calico-networking.md) — Calico CNI

## Notes

The automated setup script (`plat_scripts/setup_k8s_platform.py`) encapsulates the entire cluster setup process: Kind creation, Calico installation, namespace creation, secret deployment, database deployment, and network policy application. This reduces the manual cluster setup from ~30 minutes to ~2 minutes.
