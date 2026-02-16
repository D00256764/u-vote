# ADR-004: Calico CNI Networking

## Status

**Status:** Accepted
**Date:** 2026-02-11
**Authors:** D00D00255656256764
**Supersedes:** None

---

## Context

### Problem Statement

The U-Vote Kubernetes cluster requires a Container Network Interface (CNI) plugin that supports the full Kubernetes NetworkPolicy API, including both ingress and egress rules with label-based pod selection and port-level filtering. The zero-trust security model (ADR-010) depends entirely on the CNI's ability to enforce network policies — without enforcement, policies are silently ignored and all pod-to-pod traffic is permitted.

### Background

Kubernetes does not enforce NetworkPolicies by itself. The NetworkPolicy API defines the desired state (which traffic should be allowed/denied), but enforcement is delegated to the CNI plugin. If the CNI does not support NetworkPolicies, the resources are accepted by the API server but have no effect — a dangerous silent failure.

During the initial Kind cluster setup, the default CNI (kindnetd) was used. Testing revealed that NetworkPolicy resources were accepted but not enforced — all pods could still communicate freely despite a default-deny policy being in place.

### Requirements

- **R1:** Full Kubernetes NetworkPolicy API support (ingress + egress)
- **R2:** Label-based pod selection for policy targets
- **R3:** Port-level traffic filtering (TCP, UDP)
- **R4:** Namespace-based policy scoping
- **R5:** Compatibility with Kind clusters (disableDefaultCNI: true)
- **R6:** Reasonable resource overhead (must fit in 16GB RAM alongside 6 services)
- **R7:** Debugging and troubleshooting tools
- **R8:** Mature documentation and community support
- **R9:** Active maintenance with regular releases

### Constraints

- **C1:** Kind cluster with `disableDefaultCNI: true` — the CNI must handle all pod networking
- **C2:** Pod subnet must be `192.168.0.0/16` (standard Calico range for Kind)
- **C3:** Must work with standard Kubernetes NetworkPolicy API (no vendor-specific CRDs required)
- **C4:** Must not require kernel features unavailable in Kind's container runtime

---

## Options Considered

### Option 1: Calico v3.26.1 — Chosen

**Description:**
Calico is an open-source networking and network security solution for containers, VMs, and bare-metal workloads. Developed by Tigera, it uses BGP routing and iptables (or eBPF) for packet processing. Calico supports the full Kubernetes NetworkPolicy API and extends it with Calico-specific GlobalNetworkPolicy CRDs for advanced use cases.

**Pros:**
- Full Kubernetes NetworkPolicy support (ingress + egress)
- Both iptables and eBPF data planes available
- Extensive documentation with Kind-specific guides
- calicoctl CLI for debugging (show IP routes, endpoint status, policy hits)
- Low resource overhead (~200MB for Calico system pods)
- BGP-based routing (efficient, no overlay encapsulation by default)
- Well-tested with Kind clusters
- Regular releases (monthly patch releases, quarterly minor releases)
- Used by major cloud providers (AKS, EKS options)

**Cons:**
- More complex than Flannel (additional operator and CRDs)
- BGP routing can be confusing to troubleshoot initially
- Calico-specific CRDs add complexity if used (we avoid this by using standard API)
- Larger installed footprint than Flannel

**Evaluation:**
Calico meets all requirements (R1–R9). It is the most widely used CNI for NetworkPolicy enforcement and has the strongest Kind compatibility documentation.

### Option 2: Cilium

**Description:**
Cilium is a modern CNI using eBPF (extended Berkeley Packet Filter) for networking, security, and observability. It provides L3/L4 NetworkPolicy support plus advanced L7 policies (HTTP-aware filtering).

**Pros:**
- Full Kubernetes NetworkPolicy support
- eBPF-based (higher performance than iptables)
- L7-aware policies (can filter by HTTP path, headers)
- Hubble observability tool (real-time traffic flow visualisation)
- Growing rapidly in adoption

**Cons:**
- Higher resource requirements (~400MB for Cilium system pods)
- Requires kernel ≥ 5.4 for full eBPF feature set
- More complex debugging (eBPF maps are less intuitive than iptables rules)
- Kind compatibility requires specific configuration steps
- Newer, with less documented edge cases in Kind environments
- L7 features add complexity not needed for this project

**Evaluation:**
Cilium meets requirements R1–R4 and R9 but scores lower on R5 (Kind compatibility requires extra configuration), R6 (higher resource overhead), and R7 (eBPF debugging is more complex than iptables). The L7 features are unnecessary — the project's network policies operate at L3/L4 only.

### Option 3: Flannel

**Description:**
Flannel is a simple overlay network for Kubernetes that provides pod-to-pod connectivity using VXLAN tunnels.

**Pros:**
- Simple setup (single DaemonSet)
- Low resource overhead (~50MB)
- Reliable basic networking
- Excellent Kind compatibility

**Cons:**
- **No NetworkPolicy support** — critical disqualifier
- Policies are silently ignored (accepted by API server but not enforced)
- Only provides L3 connectivity (no security features)
- Would require a secondary controller (e.g., Calico for policies only) adding complexity

**Evaluation:**
Flannel fails requirement R1 (NetworkPolicy support). This is a hard disqualifier — without policy enforcement, the zero-trust security model (ADR-010) is impossible. Flannel was actually tested first (before Calico) and the lack of policy enforcement was discovered when default-deny policies had no effect.

### Option 4: Weave Net

**Description:**
Weave Net provides a mesh network with automatic discovery and built-in encryption between nodes.

**Pros:**
- Mesh networking with automatic peer discovery
- Built-in traffic encryption (optional)
- Basic NetworkPolicy support
- No external dependencies

**Cons:**
- Weaveworks (the company) ceased operations in February 2024
- Uncertain maintenance and future releases
- Higher overhead than Calico (mesh gossip protocol)
- NetworkPolicy support is basic (some edge cases not handled)
- Documentation is no longer being updated
- Risk of abandoned project

**Evaluation:**
Weave Net was eliminated primarily due to R9 (active maintenance). The company behind it ceased operations in 2024, making it a risky choice for a project that will continue into 2026. Basic NetworkPolicy support also raises concerns about edge case handling.

---

## Decision

**Chosen Option:** Calico v3.26.1 (Option 1)

**Rationale:**
Calico provides the best combination of full NetworkPolicy support, Kind compatibility, documentation quality, and debugging tools. The decision matrix (§3.4.3 of Investigation Log) scored Calico at 9.40/10, ahead of Cilium (7.95), Weave Net (5.90), and Flannel (5.55).

**Key Factors:**

1. **Full NetworkPolicy enforcement (R1):** Calico enforces both ingress and egress policies using iptables rules in the Linux kernel. This was validated experimentally — after applying a default-deny policy, all pod-to-pod traffic was blocked as expected (§3.4.4 of Investigation Log).

2. **Kind compatibility (R5):** Calico has first-class documentation for Kind clusters. The configuration is straightforward: set `disableDefaultCNI: true` in Kind config, install the Calico operator and CRDs, wait for pods to be ready.

3. **Debugging tools (R7):** `calicoctl` provides policy inspection, endpoint status, and IP route information. This proved invaluable during the development of the 12 NetworkPolicy resources (ADR-010).

4. **Standard API usage (C3):** All U-Vote network policies use the standard `networking.k8s.io/v1` API, not Calico-specific CRDs. This means the policies are portable to any CNI that supports the standard API (e.g., Cilium if migrated in future).

5. **Proven in production:** Calico is used in Azure AKS, Amazon EKS, and Google GKE. Skills learned here are directly transferable to production cloud deployments.

---

## Consequences

### Positive Consequences

- **Zero-trust enabled:** Calico enforcement makes the default-deny + explicit-allow security model operational. Without Calico, the 12 NetworkPolicy resources would be decorative YAML with no security effect.
- **Standard API portability:** Using `networking.k8s.io/v1` (not Calico CRDs) means policies work with any compliant CNI. Migration to Cilium in future requires zero policy changes.
- **Debugging capability:** `calicoctl` and iptables inspection enable systematic troubleshooting of blocked/allowed traffic flows.
- **Production path:** Same CNI can be used on cloud Kubernetes (AKS with Calico, EKS with Calico) — no migration needed.

### Negative Consequences

- **Installation complexity:** Calico requires disabling the default CNI and installing operator + CRDs (2 kubectl apply commands + wait). Mitigated by: automating installation in `setup_k8s_platform.py` script.
- **Resource overhead:** Calico system pods consume ~200MB RAM across the cluster. Mitigated by: this is a small fraction of the 16GB available.
- **Learning curve:** Understanding BGP routing and iptables rules for debugging. Mitigated by: only standard NetworkPolicy knowledge is required for day-to-day use; BGP/iptables knowledge is only needed for deep debugging.

### Trade-offs Accepted

- **Calico vs Cilium:** Accepted Calico's iptables-based enforcement (slightly lower performance) over Cilium's eBPF (higher performance) because Calico has better Kind compatibility and simpler debugging. The performance difference is irrelevant at the project's scale.
- **Resource overhead vs Features:** Accepted ~200MB additional RAM for full NetworkPolicy enforcement over Flannel's lower footprint with no policy support. Security is non-negotiable.

---

## Implementation Notes

### Technical Details

Installation sequence:
```bash
# 1. Install Calico operator
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/tigera-operator.yaml

# 2. Install Calico custom resources
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/custom-resources.yaml

# 3. Wait for Calico to be ready
kubectl wait --for=condition=Ready pods --all -n calico-system --timeout=300s
```

### Configuration

- **Data plane:** iptables (default for Kind)
- **IPAM:** Calico IPAM with `192.168.0.0/16` CIDR
- **Encapsulation:** VXLAN (required for Kind, as BGP is not available between Docker containers)
- **NetworkPolicy API:** Standard `networking.k8s.io/v1` only (no Calico CRDs used)

### Integration Points

- **ADR-003 (Kubernetes):** Calico is installed on the Kind cluster
- **ADR-010 (Zero-Trust):** Calico enforces the 12 NetworkPolicy resources
- **ADR-012 (Kind):** Kind cluster configured with `disableDefaultCNI: true` for Calico

---

## Validation

### Success Criteria

- [x] All Calico system pods in Running state (`kubectl get pods -n calico-system`)
- [x] Default-deny policy blocks all traffic (validated with test pods)
- [x] Allow-DNS policy restores DNS resolution
- [x] Allow-to-database policy permits only whitelisted services
- [x] Unlabelled pods remain blocked from database
- [x] Network policies compose correctly (12 policies, no conflicts)

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Calico pod startup time | <60s | ~30s |
| Calico system RAM usage | <500MB | ~200MB |
| Policy enforcement latency | <1ms per packet | Sub-millisecond |
| Total NetworkPolicy resources | ≥10 | 12 |

### Review Date

End of Stage 2 (April 2026) — evaluate whether to migrate to Cilium for eBPF performance benefits in production.

---

## References

- [Investigation Log §3.4](../INVESTIGATION-LOG.md#34-cni-plugin-investigation) — Full evaluation details
- [Calico Documentation](https://docs.tigera.io/calico/latest/)
- [Calico Kind Quickstart](https://docs.tigera.io/calico/latest/getting-started/kubernetes/kind)
- [Kubernetes NetworkPolicy Documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [NETWORK-SECURITY.md](../NETWORK-SECURITY.md) — Detailed network policy specification and testing
- [ADR-003](ADR-003-kubernetes-platform.md) — Kubernetes platform selection
- [ADR-010](ADR-010-network-policy-zero-trust.md) — Zero-trust network model

## Notes

Flannel was initially installed and tested. The discovery that it silently ignores NetworkPolicies was a valuable lesson documented in §6.2.4 of the Investigation Log ("Failed: Flannel CNI for Simplicity"). This experience informed the decision to prioritise CNIs with verified NetworkPolicy enforcement.
