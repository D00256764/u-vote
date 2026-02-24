# U-Vote Platform Infrastructure — Comprehensive Documentation

**Version:** 1.0 (Stage 1 Deliverable)
**Author:** D00256764 — BSc Computing Systems & Operations, Year 4
**Institution:** Dundalk Institute of Technology (DkIT)
**Module:** PROJ I8009 — Project (10 credits)
**Date:** February 2026
**Status:** Stage 1 — Design, Prototyping & Platform Deployment (30%)

---

## Table of Contents

- [1. Executive Summary](#1-executive-summary)
- [2. Platform Architecture](#2-platform-architecture)
- [3. Infrastructure Design](#3-infrastructure-design)
- [4. Database Platform](#4-database-platform)
- [5. CI/CD Pipeline Design](#5-cicd-pipeline-design)
- [6. Environment Strategy](#6-environment-strategy)
- [7. Deployment Strategy](#7-deployment-strategy)
- [8. Observability Platform](#8-observability-platform)
- [9. Security Architecture](#9-security-architecture)
- [10. Operational Procedures](#10-operational-procedures)
- [11. Service Level Objectives](#11-service-level-objectives)
- [12. Scalability and Performance](#12-scalability-and-performance)
- [13. Disaster Recovery and Business Continuity](#13-disaster-recovery-and-business-continuity)
- [14. Infrastructure as Code](#14-infrastructure-as-code)
- [15. Future Enhancements](#15-future-enhancements)
- [16. Appendices](#16-appendices)

---

## 1. Executive Summary

### 1.1 Platform Overview

U-Vote is a secure, transparent, and inclusive online voting platform designed for small-scale democratic processes — student union elections, NGO board votes, local council decisions, and similar contexts where trust, accessibility, and auditability are critical. The platform is deployed on Kubernetes with Calico network policies enforcing a zero-trust security model, and uses PostgreSQL 15 for persistent data storage with cryptographic integrity controls.

This document provides a comprehensive specification of the U-Vote platform infrastructure: the Kubernetes cluster architecture, network security model, database platform, deployment strategy, CI/CD pipeline design, observability approach, operational procedures, and future roadmap. It serves as the Stage 1 deliverable for the PROJ I8009 module, demonstrating DevOps maturity across infrastructure as code, automated deployment, security engineering, and operational readiness.

### 1.2 Technology Stack Summary

| Layer | Technology | Justification |
|-------|-----------|---------------|
| **Container Orchestration** | Kubernetes (Kind for dev) | Industry-standard orchestration; declarative desired-state model; self-healing; rolling updates |
| **Container Runtime** | Docker | Mature ecosystem; OCI-compliant images; integrated build toolchain |
| **Container Networking** | Calico CNI (v3.26.1) | Full NetworkPolicy support (ingress + egress); low overhead; Kind-compatible; portable standard API |
| **Backend Framework** | Python 3.11 + FastAPI + Uvicorn | Async I/O for concurrent requests; automatic OpenAPI docs; Pydantic validation; strong typing |
| **Frontend** | FastAPI + Jinja2 (SSR) | Server-side rendering for accessibility; no client-side JavaScript framework dependency; WCAG AA compliance |
| **Database** | PostgreSQL 15 | ACID compliance; pgcrypto for encryption; triggers for immutability; mature replication support |
| **Async DB Driver** | asyncpg | Non-blocking PostgreSQL access; connection pooling; native prepared statements |
| **Ingress** | Nginx Ingress Controller | TLS termination; path-based routing; rate limiting; Helm-based installation |
| **Secrets** | Kubernetes Secrets | Namespace-scoped; base64-encoded; integrated with pod environment injection |
| **Password Hashing** | bcrypt (cost 12) via passlib | Industry-standard adaptive hashing; configurable work factor; resistant to GPU attacks |
| **Token Signing** | JWT HS256 | Stateless authentication; 24-hour expiry; compact token format |
| **Cryptographic Tokens** | Python `secrets.token_urlsafe(32)` | 256-bit entropy; URL-safe encoding; CSPRNG-backed |

### 1.3 Key Architectural Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Microservices over monolith** | Independent deployment and scaling; fault isolation; team-parallel development | Higher operational complexity; distributed system challenges |
| **Calico over Flannel** | Flannel has zero NetworkPolicy support; Calico enforces both ingress and egress rules | Slightly more complex installation |
| **Kind over Minikube** | Multi-node clusters; Calico compatibility; port mappings for ingress; Docker-native | Not suitable for production (dev/test only) |
| **Default-deny networking** | Zero-trust security posture; limits blast radius of any compromised service | Every communication path must be explicitly allowed — more YAML, more testing |
| **asyncpg over psycopg2** | Non-blocking I/O matches FastAPI's async model; native connection pooling | Less familiar to developers accustomed to synchronous ORMs |
| **Server-side rendering over SPA** | Better accessibility (WCAG AA); no JavaScript framework dependency; simpler security model | Less interactive UI; full page reloads on navigation |
| **Token-based voting over passwords** | Zero friction for voters; no password management; cryptographic token entropy | Voters cannot "log back in" to verify their vote (receipt token addresses this) |
| **Hash-chained audit logs** | Tamper detection without external infrastructure; append-only with trigger-enforced immutability | Hash chain verification is O(n) — acceptable for small-scale elections |
| **Identity-ballot separation** | Cryptographic anonymity: blind ballot tokens have no FK to voter; `encrypted_ballots` table has no `voter_id` | Cannot revoke a specific vote after casting without breaking anonymity |

### 1.4 DevOps Maturity Assessment

| Capability | Current Maturity | Evidence |
|-----------|-----------------|----------|
| **Infrastructure as Code** | Established | All Kubernetes manifests version-controlled; declarative YAML for cluster, namespaces, policies, deployments |
| **Automated Deployment** | Established | Python automation scripts for cluster setup (`setup_k8s_platform.py`) and service deployment (`deploy_platform.py`) |
| **Containerisation** | Established | All 6 services containerised with Docker; multi-stage-ready Dockerfiles; shared utilities layer |
| **Network Security** | Advanced | 12 NetworkPolicy resources; zero-trust model; bidirectional enforcement; validated with test pods |
| **Database Security** | Advanced | 6 per-service PostgreSQL users with least-privilege GRANTs; triggers for immutability; hash-chained audit |
| **Secrets Management** | Basic | Kubernetes Secrets; not committed to Git; planned migration to HashiCorp Vault |
| **Monitoring** | Planned | Application health endpoints implemented; Prometheus + Grafana planned for Stage 2 |
| **CI/CD Pipeline** | Designed | Pipeline architecture documented; GitHub Actions + ArgoCD selected; implementation in Stage 2 |
| **Testing** | Established | Comprehensive database test suite (47k lines); network policy validation; health endpoint testing |
| **Documentation** | Advanced | Architecture doc, platform doc, network security doc, deployment automation with logging |

### 1.5 Success Criteria

| Criterion | Target | Status |
|-----------|--------|--------|
| Kind cluster operational with 3 nodes | 1 control-plane + 2 workers | Implemented |
| Calico CNI installed and enforcing policies | All 12 NetworkPolicy resources active | Implemented |
| PostgreSQL deployed with persistent storage | 5Gi PVC, health probes, schema applied | Implemented |
| All 6 service images buildable | Docker build succeeds for each service | Implemented |
| Services deployable to Kubernetes | `kubectl apply` succeeds; pods reach Running state | Implemented |
| Zero-trust network isolation verified | Default-deny + explicit allows tested with diagnostic pods | Implemented |
| Database access controlled per-service | 6 whitelisted services; frontend blocked; validated | Implemented |
| Automated deployment pipeline | Single-command deployment with logging and rollback | Implemented |
| Health endpoints responsive | `/health` returns 200 on all backend services | Implemented |
| Documentation complete for Stage 1 | Architecture, platform, network security, this document | Implemented |

---

## 2. Platform Architecture

### 2.1 Multi-Tier Architecture

The U-Vote platform implements a multi-tier microservices architecture deployed on Kubernetes. The architecture separates concerns across six application services, an API gateway (Nginx Ingress Controller), and a persistent data tier (PostgreSQL 15).

```
                              ┌─────────────────────────┐
                              │     External Users      │
                              │    (Browsers / API)     │
                              └────────────┬────────────┘
                                           │
                                   Ports 80/443
                                           │
┌──────────────────────────────────────────┬┴──────────────────────────────────────────┐
│                              Kind Cluster (3 nodes)                                  │
│                          Calico Network: 192.168.0.0/16                              │
│                                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                    Namespace: ingress-nginx                                     │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────┐   │  │
│  │  │                  Nginx Ingress Controller                                │   │  │
│  │  │  - TLS termination         - Path-based routing                         │   │  │
│  │  │  - Rate limiting           - Request forwarding                         │   │  │
│  │  └───────────────────────────────────┬──────────────────────────────────────┘   │  │
│  └──────────────────────────────────────┼──────────────────────────────────────────┘  │
│                                         │                                             │
│  ┌──────────────────────────────────────┼──────────────────────────────────────────┐  │
│  │                    Namespace: uvote-dev                                         │  │
│  │                                      │                                          │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────┴───┐  ┌──────────┐  ┌──────────┐         │  │
│  │  │ Frontend │  │   Auth   │  │ Election │  │  Voting  │  │ Results  │         │  │
│  │  │ Service  │  │ Service  │  │ Service  │  │ Service  │  │ Service  │         │  │
│  │  │  :5000   │  │  :5001   │  │  :5005   │  │  :5003   │  │  :5004   │         │  │
│  │  │ (2 pods) │  │ (2 pods) │  │ (2 pods) │  │ (2 pods) │  │ (2 pods) │         │  │
│  │  │  NO DB   │  │   DB ✓   │  │   DB ✓   │  │   DB ✓   │  │ DB (RO)  │         │  │
│  │  └──────────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │  │
│  │                      │             │             │             │                │  │
│  │  ┌──────────┐        │             │             │             │                │  │
│  │  │  Admin   │        │             │             │             │                │  │
│  │  │ Service  │        │             │             │             │                │  │
│  │  │  :5002   │        │             │             │             │                │  │
│  │  │ (2 pods) │        │             │             │             │                │  │
│  │  │   DB ✓   │        │             │             │             │                │  │
│  │  └────┬─────┘        │             │             │             │                │  │
│  │       │              │             │             │             │                │  │
│  │       └──────────────┴──────┬──────┴─────────────┴─────────────┘                │  │
│  │                             │                                                   │  │
│  │              Network Policy: allow-to-database (02)                              │  │
│  │                             │                                                   │  │
│  │                     ┌───────▼───────┐                                           │  │
│  │                     │  PostgreSQL   │                                           │  │
│  │                     │    15-alpine  │                                           │  │
│  │                     │    :5432      │                                           │  │
│  │                     │  PVC: 5Gi    │                                           │  │
│  │                     └───────────────┘                                           │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                    Namespace: calico-system                                     │  │
│  │  Calico Operator + CNI Plugin + NetworkPolicy Controller                       │  │
│  └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                       │
│  ┌──────────────────────┐  ┌──────────────────────┐                                  │
│  │ Namespace: uvote-test│  │ Namespace: uvote-prod │  (reserved for future)           │
│  └──────────────────────┘  └──────────────────────┘                                  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Service Registry

| # | Service Name | Image | K8s Deployment | Port | Replicas | DB Access | Health Endpoint |
|---|-------------|-------|----------------|------|----------|-----------|-----------------|
| 1 | auth-service | `auth-service:latest` | `auth-service` | 5001 | 2 | Yes — `auth_service` user | `GET /health` |
| 2 | election-service | `election-service:latest` | `election-service` | 5005 | 2 | Yes — `election_service` user | `GET /health` |
| 3 | frontend-service | `frontend-service:latest` | `frontend-service` | 5000 | 2 | **No** (blocked by policy) | TCP socket probe |
| 4 | results-service | `results-service:latest` | `results-service` | 5004 | 2 | Yes — `results_service` (READ-ONLY) | `GET /health` |
| 5 | voter-service | `voter-service:latest` | `admin-service` | 5002 | 2 | Yes — `admin_service` user | `GET /health` |
| 6 | voting-service | `voting-service:latest` | `voting-service` | 5003 | 2 | Yes — `voting_service` user | `GET /health` |

**Note on naming:** The `voter-service` directory builds the `voter-service:latest` Docker image, but the Kubernetes deployment is named `admin-service` to match the network policy label `app: admin-service`. This mapping is documented in the deployment manifest header and handled by the deployment automation script.

### 2.3 Component Interaction Flows

#### 2.3.1 Admin Election Setup Flow

```
Admin Browser
      │
      ▼
Nginx Ingress Controller
      │
      ├──► Frontend Service (:5000)
      │         │
      │         ├─ GET /           → render home page
      │         ├─ GET /login      → render login form
      │         ├─ POST /login     → proxy to Auth Service
      │         ├─ GET /register   → render registration form
      │         └─ POST /register  → proxy to Auth Service
      │
      ├──► Auth Service (:5001)
      │         │
      │         ├─ POST /register  → INSERT into admins (bcrypt hash)
      │         ├─ POST /login     → validate credentials, return JWT
      │         └─ GET /health     → {"status": "healthy"}
      │
      └──► Election Service (:5005)
                │
                ├─ GET /dashboard          → list elections for admin
                ├─ POST /elections/create   → INSERT into elections
                ├─ POST /elections/{id}/activate  → SET status='active'
                └─ POST /elections/{id}/close     → SET status='closed'
```

#### 2.3.2 Voter Voting Flow

```
Voter receives email with unique URL:
  https://uvote.example.com/vote/{token}

Voter Browser
      │
      ▼
Nginx Ingress Controller
      │
      ▼
Voting Service (:5003)
      │
      ├─ GET /vote/{token}
      │     1. Validate token (not expired, not used)
      │     2. Load election + options from DB
      │     3. Render ballot template
      │
      ├─ POST /vote/{token}
      │     1. Re-validate token
      │     2. Check election status == 'active'
      │     3. Encrypt vote with election key (pgp_sym_encrypt)
      │     4. Generate ballot hash (SHA-256 chain)
      │     5. INSERT into encrypted_ballots
      │     6. Generate receipt token
      │     7. INSERT into vote_receipts
      │     8. Mark voting_token.is_used = TRUE
      │     9. INSERT audit_log entry (no candidate info)
      │    10. Render success page with receipt
      │
      └─ GET /vote/verify/{receipt_token}
            1. Look up receipt in vote_receipts
            2. Verify ballot_hash matches encrypted_ballots
            3. Render verification result
```

#### 2.3.3 Data Flow: Vote Anonymity

```
┌─────────────────────────────────────────────────────────────────────┐
│                     IDENTITY DOMAIN                                 │
│                                                                     │
│  voters table ──► voting_tokens table                               │
│  (email, DOB)      (token, voter_id, election_id)                  │
│                           │                                         │
│                    Token validated                                   │
│                    voter.has_voted = TRUE                           │
│                           │                                         │
│  ══════════════ ANONYMITY BARRIER (no FK between domains) ════════ │
│                           │                                         │
│                    blind_tokens table                               │
│                    (ballot_token, election_id)                      │
│                    NO voter_id, NO voting_token_id                  │
│                           │                                         │
│                     BALLOT DOMAIN                                   │
│                                                                     │
│  encrypted_ballots table                                            │
│  (election_id, encrypted_vote, ballot_hash, receipt_token)         │
│  NO voter_id, NO user_id, NO ballot_token_id                      │
│                                                                     │
│  vote_receipts table                                                │
│  (election_id, receipt_token, ballot_hash)                         │
│  NO voter_id                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.4 Network Topology

The platform's network topology is defined by the Kind cluster configuration and Calico CNI:

```yaml
# uvote-platform/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: uvote
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
  disableDefaultCNI: true      # Calico replaces default CNI
  podSubnet: 192.168.0.0/16   # Calico default pod CIDR
```

| Network Layer | CIDR / Address | Purpose |
|---------------|---------------|---------|
| Pod network | `192.168.0.0/16` | Pod-to-pod communication (Calico-managed) |
| Service network | `10.96.0.0/16` | Kubernetes ClusterIP services (default) |
| Node network | Docker bridge | Kind container networking |
| External access | `localhost:80`, `localhost:443` | Port-mapped from control-plane node |

### 2.5 Security Boundaries

The platform implements four distinct security boundaries:

```
┌─────────────────────────────────────────────────────────────┐
│ BOUNDARY 1: External ↔ Cluster                              │
│ Enforcement: Nginx Ingress Controller + Kind port mappings  │
│ Only ports 80/443 exposed; all traffic routed via Ingress   │
├─────────────────────────────────────────────────────────────┤
│ BOUNDARY 2: Ingress ↔ Application Services                  │
│ Enforcement: NetworkPolicy 03 (allow-from-ingress)          │
│ Only 6 services reachable from ingress-nginx namespace      │
├─────────────────────────────────────────────────────────────┤
│ BOUNDARY 3: Application Services ↔ Database                 │
│ Enforcement: NetworkPolicy 02 (allow-to-database)           │
│ Only 5 backend services reach PostgreSQL; frontend blocked  │
│ + per-service PostgreSQL users with least-privilege GRANTs  │
├─────────────────────────────────────────────────────────────┤
│ BOUNDARY 4: Data Integrity                                  │
│ Enforcement: Database triggers + hash chains                │
│ Encrypted ballots and audit logs are immutable              │
│ SHA-256 hash chains detect tampering                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.6 Scalability Design

Each service deployment specifies 2 replicas with a `RollingUpdate` strategy:

```yaml
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # Allow 1 extra pod during update
      maxUnavailable: 0  # Never reduce below desired count
```

Resource limits per pod:

| Resource | Request | Limit |
|----------|---------|-------|
| Memory | 128Mi | 512Mi |
| CPU | 100m | 1000m |

PostgreSQL resource allocation:

| Resource | Request | Limit |
|----------|---------|-------|
| Memory | 256Mi | 512Mi |
| CPU | 250m | 500m |

**Horizontal Pod Autoscaler (HPA)** is planned for Stage 2, targeting:
- CPU utilisation threshold: 70%
- Min replicas: 2
- Max replicas: 5 (backend services), 3 (frontend)

### 2.7 High Availability Approach

| Component | HA Strategy | Current | Future |
|-----------|------------|---------|--------|
| Application pods | Multiple replicas (2 per service) | Implemented | HPA to scale 2-5 |
| PostgreSQL | Single instance with PVC | Implemented | Streaming replication (primary + read replica) |
| Kind cluster | Multi-node (1 CP + 2 workers) | Implemented | Managed K8s (AKS/EKS) with multi-AZ |
| Ingress | Single controller | Implemented | Multiple replicas with pod anti-affinity |

### 2.8 Disaster Recovery Strategy

| Scenario | Recovery Method | RTO Target | RPO Target |
|----------|----------------|------------|------------|
| Pod crash | Kubernetes self-healing (restart policy) | < 30s | 0 (stateless services) |
| Node failure | Pod rescheduling to healthy worker | < 2 min | 0 (PVC on surviving node) |
| Database corruption | Restore from `pg_dump` backup | < 15 min | Last backup interval |
| Cluster failure | Re-create cluster from IaC + restore DB | < 30 min | Last backup interval |
| Complete data loss | Restore from off-cluster backup | < 1 hour | Last off-site backup |

---

## 3. Infrastructure Design

### 3.1 Kubernetes Cluster Architecture

#### 3.1.1 Control Plane Configuration

The Kind cluster provides a single control-plane node running:
- **kube-apiserver** — API endpoint for all cluster operations
- **etcd** — Distributed key-value store for cluster state
- **kube-scheduler** — Assigns pods to worker nodes based on resource availability
- **kube-controller-manager** — Manages replication controllers, endpoints, service accounts
- **CoreDNS** — Cluster DNS resolution (in `kube-system` namespace)

The control-plane node includes `extraPortMappings` for ports 80 and 443, enabling the Nginx Ingress Controller to receive external HTTP/HTTPS traffic.

#### 3.1.2 Worker Node Specifications

| Property | Value |
|----------|-------|
| Number of workers | 2 |
| Runtime | containerd (Kind default) |
| Kubernetes version | v1.27+ (Kind-bundled) |
| CNI | Calico (default CNI disabled) |
| Pod scheduling | Both workers accept application pods |

#### 3.1.3 Kind-Specific Setup Details

Kind (Kubernetes in Docker) runs each Kubernetes node as a Docker container. This approach provides:

- **Multi-node fidelity** — Simulates real cluster topology with separate control-plane and worker nodes
- **CNI flexibility** — `disableDefaultCNI: true` allows Calico installation for NetworkPolicy enforcement
- **Port mapping** — `extraPortMappings` on the control-plane container forward host ports to the Ingress Controller
- **Image loading** — `kind load docker-image` injects locally-built images directly into cluster nodes (no registry needed)

**Automated cluster creation** is handled by `plat_scripts/setup_k8s_platform.py`:

```python
# Step 1: Create Kind cluster
kind create cluster --config uvote-platform/kind-config.yaml --name uvote

# Step 2: Install Calico CNI
kubectl create -f https://raw.githubusercontent.com/.../tigera-operator.yaml
kubectl create -f https://raw.githubusercontent.com/.../custom-resources.yaml

# Step 3: Wait for Calico readiness
kubectl wait --for=condition=Ready pods --all -n calico-system --timeout=300s
```

#### 3.1.4 Resource Allocation Strategy

Total cluster resource budget (approximate):

| Component | Pods | Memory Request | Memory Limit | CPU Request | CPU Limit |
|-----------|------|---------------|--------------|-------------|-----------|
| auth-service | 2 | 256Mi | 1Gi | 200m | 2000m |
| election-service | 2 | 256Mi | 1Gi | 200m | 2000m |
| frontend-service | 2 | 256Mi | 1Gi | 200m | 2000m |
| results-service | 2 | 256Mi | 1Gi | 200m | 2000m |
| admin-service | 2 | 256Mi | 1Gi | 200m | 2000m |
| voting-service | 2 | 256Mi | 1Gi | 200m | 2000m |
| PostgreSQL | 1 | 256Mi | 512Mi | 250m | 500m |
| **Total** | **13** | **1.79Gi** | **6.5Gi** | **1.45 cores** | **12.5 cores** |

This fits within the recommended 16GB RAM / 4-core system specification with headroom for Calico, CoreDNS, and system pods.

#### 3.1.5 Namespace Design and Isolation

```yaml
# uvote-platform/k8s/namespaces/namespaces.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: uvote-dev
  labels:
    environment: development
---
apiVersion: v1
kind: Namespace
metadata:
  name: uvote-test
  labels:
    environment: testing
---
apiVersion: v1
kind: Namespace
metadata:
  name: uvote-prod
  labels:
    environment: production
```

| Namespace | Purpose | Network Policies | Current Status |
|-----------|---------|-----------------|----------------|
| `uvote-dev` | Development and testing | 12 policies (full zero-trust) | Active |
| `uvote-test` | Integration testing | Planned (mirror of dev) | Reserved |
| `uvote-prod` | Production deployment | Planned (mirror of dev + stricter) | Reserved |
| `ingress-nginx` | Ingress controller | Cross-namespace policy (03) | Active |
| `calico-system` | Calico components | System-managed | Active |
| `kube-system` | Core Kubernetes components | DNS egress target (01) | Active |

#### 3.1.6 RBAC and Service Accounts

Current implementation uses Kind's default RBAC configuration:
- Cluster-admin kubeconfig for deployment operations
- Default service accounts per namespace

**Planned for Stage 2:**
- Dedicated service accounts per service deployment
- Role-based access for CI/CD pipeline (`deploy` role with limited permissions)
- Read-only role for monitoring dashboards

#### 3.1.7 Pod Security

All application pods run with a hardened security context:

```yaml
securityContext:
  runAsNonRoot: true           # Container must run as non-root user
  runAsUser: 1000              # Explicit UID (not root)
  allowPrivilegeEscalation: false  # Prevent setuid/setgid
  readOnlyRootFilesystem: false    # FastAPI/Uvicorn needs temp file writes
```

### 3.2 Network Architecture

#### 3.2.1 Calico CNI Implementation

Calico was selected over Flannel and Cilium for the following reasons:

| Criterion | Calico | Flannel | Cilium |
|-----------|--------|---------|--------|
| NetworkPolicy support | Full (ingress + egress) | **None** | Full |
| Kind compatibility | Excellent | Excellent | Requires extra config |
| Resource overhead | Low | Low | Moderate (eBPF) |
| Setup complexity | Moderate | Simple | Higher |
| Standard API | `networking.k8s.io/v1` | N/A | `networking.k8s.io/v1` + CRDs |

**Flannel was excluded** because it silently ignores NetworkPolicy resources — policies would be accepted by the API server but never enforced, creating a false sense of security.

**Installation process:**

```bash
# Calico Operator (manages Calico lifecycle)
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/tigera-operator.yaml

# Calico Custom Resources (configures Calico with pod CIDR)
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/custom-resources.yaml
```

#### 3.2.2 Pod Networking

| Property | Value |
|----------|-------|
| Pod CIDR | `192.168.0.0/16` |
| IP allocation | Calico IPAM (per-node blocks) |
| Encapsulation | VXLAN (Kind default for Calico) |
| MTU | Auto-detected |

#### 3.2.3 Service Discovery

Kubernetes ClusterIP services provide stable DNS names for inter-service communication:

| Service DNS Name | ClusterIP Port | Target Port | Protocol |
|-----------------|---------------|-------------|----------|
| `auth-service.uvote-dev.svc.cluster.local` | 5001 | 5001 | TCP |
| `election-service.uvote-dev.svc.cluster.local` | 5005 | 5005 | TCP |
| `frontend-service.uvote-dev.svc.cluster.local` | 5000 | 5000 | TCP |
| `results-service.uvote-dev.svc.cluster.local` | 5004 | 5004 | TCP |
| `admin-service.uvote-dev.svc.cluster.local` | 5002 | 5002 | TCP |
| `voting-service.uvote-dev.svc.cluster.local` | 5003 | 5003 | TCP |
| `postgresql.uvote-dev.svc.cluster.local` | 5432 | 5432 | TCP |

Services use short names within the same namespace (e.g., `postgresql` instead of the FQDN). Environment variables inject service URLs:

```yaml
env:
- name: DB_HOST
  value: "postgresql"
- name: AUTH_SERVICE_URL
  value: "http://auth-service:5001"
```

#### 3.2.4 DNS Configuration

CoreDNS runs in `kube-system` and is accessible to all pods via NetworkPolicy 01:

```yaml
# 01-allow-dns.yaml — allows all pods to reach kube-dns
egress:
- to:
  - namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: kube-system
  ports:
  - protocol: UDP
    port: 53
  - protocol: TCP
    port: 53
```

#### 3.2.5 Network Policy Enforcement Model

The network security model follows a layered approach with 12 NetworkPolicy resources across 5 files:

| Order | File | Policies | Purpose |
|-------|------|----------|---------|
| 00 | `00-default-deny.yaml` | 1 | Deny all ingress + egress (zero-trust baseline) |
| 01 | `01-allow-dns.yaml` | 1 | Allow DNS egress to kube-system:53 |
| 02 | `02-allow-to-database.yaml` | 2 | Bidirectional database access for 6 services |
| 03 | `03-allow-from-ingress.yaml` | 6 | Per-service ingress from Nginx Ingress Controller |
| 04 | `04-allow-audit.yaml` | 2 | Bidirectional audit service access for 6 services |

**Service Communication Matrix:**

| Source → Destination | DB :5432 | Audit :8005 | Ingress | DNS :53 |
|---------------------|:--------:|:-----------:|:-------:|:-------:|
| frontend-service | ✗ | ✗ | ✓ | ✓ |
| auth-service | ✓ | ✓ | ✓ | ✓ |
| election-service | ✓ | ✓ | ✓ | ✓ |
| voting-service | ✓ | ✓ | ✓ | ✓ |
| results-service | ✓ | ✓ | ✓ | ✓ |
| admin-service | ✓ | ✓ | ✓ | ✓ |
| postgresql | N/A | ✗ | ✗ | ✓ |
| unlabelled pods | ✗ | ✗ | ✗ | ✓ |

For the complete network security specification, see [NETWORK-SECURITY.md](NETWORK-SECURITY.md).

#### 3.2.6 Ingress Controller Setup

The Nginx Ingress Controller is installed via Helm:

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace
```

It provides the single external entry point for all client traffic, routing requests by path to the appropriate backend service.

### 3.3 Storage Architecture

#### 3.3.1 PersistentVolume Design

PostgreSQL data is persisted using a PersistentVolumeClaim:

```yaml
# uvote-platform/k8s/database/db-pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: uvote-dev
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

| Property | Value |
|----------|-------|
| Claim name | `postgres-pvc` |
| Access mode | `ReadWriteOnce` (single-node) |
| Storage request | 5Gi |
| Storage class | `standard` (Kind default — local path provisioner) |
| Mount path | `/var/lib/postgresql/data` |
| SubPath | `postgres` (prevents lost+found conflicts) |

#### 3.3.2 Volume Provisioning

Kind uses the `local-path-provisioner` by default, which dynamically provisions PersistentVolumes backed by host directories on the Kind container filesystem. This is suitable for development but would be replaced by cloud-managed storage (Azure Disk, AWS EBS) in production.

#### 3.3.3 Database Storage Considerations

For the expected workload (small-scale elections with hundreds to low thousands of voters), 5Gi provides ample storage:

| Table | Estimated Row Size | 1,000 Elections × 1,000 Voters | Storage Estimate |
|-------|-------------------|-------------------------------|-----------------|
| voters | ~200 bytes | 1M rows | ~200MB |
| voting_tokens | ~150 bytes | 1M rows | ~150MB |
| encrypted_ballots | ~500 bytes | 1M rows | ~500MB |
| audit_log | ~300 bytes | 5M rows | ~1.5GB |
| indexes | ~30% of data | — | ~700MB |
| **Total** | | | **~3GB** |

This leaves ~2GB of headroom within the 5Gi PVC.

#### 3.3.4 Backup Strategy

**Current (manual):**

```bash
# Create backup
kubectl exec -n uvote-dev $(kubectl get pod -n uvote-dev -l app=postgresql \
  -o jsonpath='{.items[0].metadata.name}') -- \
  pg_dump -U uvote_admin evote > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
kubectl exec -i -n uvote-dev $(kubectl get pod -n uvote-dev -l app=postgresql \
  -o jsonpath='{.items[0].metadata.name}') -- \
  psql -U uvote_admin evote < backup_20260216.sql
```

**Planned (automated, Stage 2):** CronJob-based automated backups stored to a PVC or cloud storage.

---

## 4. Database Platform

### 4.1 PostgreSQL 15 Configuration

The database is deployed as a Kubernetes Deployment with a single replica:

```yaml
# uvote-platform/k8s/database/db-deployment.yaml (summary)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgresql
  namespace: uvote-dev
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: postgresql
        image: postgres:15-alpine
        env:
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: database
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: postgres-password
        ports:
        - containerPort: 5432
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          exec:
            command: ["pg_isready", "-U", "uvote_admin"]
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "uvote_admin"]
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
          subPath: postgres
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
```

### 4.2 Schema Design

The database schema implements the anonymity protocol through a deliberate absence of foreign keys between the identity and ballot domains. Two schema files exist:

| File | Purpose | Used By |
|------|---------|---------|
| `database/init.sql` | Docker Compose local development (extended schema with blind tokens, encrypted ballots) | `docker-compose.yml` |
| `uvote-platform/k8s/database/schema.sql` | Kubernetes deployment (simplified schema for current MVP services) | `setup_k8s_platform.py` |

**Core tables (K8s schema):**

| Table | Purpose | Immutable | Hash-Chained |
|-------|---------|-----------|--------------|
| `admins` | Election administrators | No | No |
| `elections` | Election metadata and lifecycle | No | No |
| `candidates` | Candidates per election | No | No |
| `voters` | Registered voters per election | No | No |
| `voting_tokens` | One-time voting URLs | No | No |
| `votes` | Anonymous vote records | **Yes** (trigger) | **Yes** (SHA-256) |
| `audit_logs` | Security event log | **Yes** (trigger) | **Yes** (SHA-256) |

**Immutability triggers:**

```sql
-- Votes are immutable: prevent UPDATE and DELETE
CREATE OR REPLACE FUNCTION prevent_vote_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Votes cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_vote_update
    BEFORE UPDATE ON votes
    FOR EACH ROW EXECUTE FUNCTION prevent_vote_modification();

CREATE TRIGGER prevent_vote_delete
    BEFORE DELETE ON votes
    FOR EACH ROW EXECUTE FUNCTION prevent_vote_modification();
```

**Automatic hash chain generation:**

```sql
-- SHA-256 hash chain for vote integrity
CREATE OR REPLACE FUNCTION generate_vote_hash()
RETURNS TRIGGER AS $$
DECLARE
    prev_hash VARCHAR(64);
BEGIN
    SELECT vote_hash INTO prev_hash
    FROM votes
    WHERE election_id = NEW.election_id
    ORDER BY cast_at DESC LIMIT 1;

    NEW.previous_hash := COALESCE(prev_hash, REPEAT('0', 64));

    NEW.vote_hash := encode(
        digest(
            NEW.election_id::text ||
            NEW.candidate_id::text ||
            NEW.cast_at::text ||
            NEW.previous_hash,
            'sha256'
        ), 'hex'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### 4.3 Per-Service Database Users

Each service uses a dedicated PostgreSQL user with least-privilege permissions:

| Service | DB User | Permissions |
|---------|---------|-------------|
| Auth | `auth_service` | SELECT, INSERT, UPDATE on `admins` |
| Voting | `voting_service` | INSERT on `votes`; SELECT on `elections`, `candidates`; UPDATE on `voting_tokens` |
| Election | `election_service` | SELECT, INSERT, UPDATE, DELETE on `elections` |
| Results | `results_service` | **SELECT only** on `votes`, `elections`, `candidates` (read-only) |
| Audit | `audit_service` | INSERT, SELECT on `audit_logs` |
| Admin | `admin_service` | SELECT, INSERT, UPDATE, DELETE on `voters`, `candidates`, `voting_tokens` |

This ensures that even if a service is compromised, the attacker can only perform operations authorised for that service's database user.

### 4.4 Connection Pooling

The shared `database.py` module implements async connection pooling with asyncpg:

```python
# shared/database.py
class Database:
    _pool: asyncpg.Pool | None = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=os.getenv("DB_HOST", "postgres"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "voting_db"),
                user=os.getenv("DB_USER", "voting_user"),
                password=os.getenv("DB_PASSWORD", "voting_pass"),
                min_size=2,
                max_size=20,
            )
        return cls._pool
```

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `min_size` | 2 | Maintain warm connections for low-latency first requests |
| `max_size` | 20 | Upper bound per pod; 12 pods × 20 = 240 max connections |

### 4.5 Indexes

Performance-critical indexes are defined in the schema:

```sql
CREATE INDEX idx_votes_election ON votes(election_id);
CREATE INDEX idx_votes_candidate ON votes(candidate_id);
CREATE INDEX idx_tokens_token ON voting_tokens(token);
CREATE INDEX idx_tokens_election ON voting_tokens(election_id);
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_event ON audit_logs(event_type);
CREATE INDEX idx_elections_status ON elections(status);
```

### 4.6 Database Testing

A comprehensive test suite (`plat_scripts/test_db.py`, 47k lines) validates:

1. **Infrastructure** — Pod health, connectivity
2. **Schema** — Tables, indexes, foreign key constraints
3. **Data** — Sample/seed data validation
4. **Security** — Vote immutability triggers, least-privilege users
5. **Performance** — Index existence, optional bulk-insert load test

Run with:
```bash
python3 plat_scripts/test_db.py          # Standard run
python3 plat_scripts/test_db.py --quick  # Fast subset
python3 plat_scripts/test_db.py --load   # Include load test
```

---

## 5. CI/CD Pipeline Design

### 5.1 Continuous Integration

#### 5.1.1 Source Control Strategy

| Property | Value |
|----------|-------|
| Platform | GitHub |
| Repository | `D00256764/u-vote` (private) |
| Default branch | `main` |
| Branch strategy | Feature branching (`feature/*`, `bugfix/*`) |
| Merge method | Pull request with review |
| Commit convention | Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`) |

#### 5.1.2 Build Pipeline Stages

The CI pipeline (GitHub Actions) executes the following stages on every push and pull request:

```
┌──────────────────────────────────────────────────────────────┐
│                    CI Pipeline Stages                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. CHECKOUT                                                 │
│     └─ Clone repository at commit SHA                        │
│                                                              │
│  2. DEPENDENCY MANAGEMENT                                    │
│     ├─ Install Python 3.11                                   │
│     ├─ pip install -r requirements.txt (per service)         │
│     └─ Cache dependencies for faster builds                  │
│                                                              │
│  3. LINT & CODE QUALITY                                      │
│     ├─ flake8 (PEP 8 compliance)                            │
│     ├─ mypy (type checking)                                 │
│     └─ bandit (security linting)                            │
│                                                              │
│  4. UNIT TESTING                                             │
│     ├─ pytest (per service)                                  │
│     ├─ Coverage threshold: 80%                              │
│     └─ Fail on coverage regression                          │
│                                                              │
│  5. INTEGRATION TESTING                                      │
│     ├─ Docker Compose service spin-up                       │
│     ├─ API endpoint tests (FastAPI TestClient)              │
│     └─ Database interaction tests                           │
│                                                              │
│  6. SECURITY SCANNING                                        │
│     ├─ Trivy (container image vulnerability scan)           │
│     ├─ Safety (Python dependency vulnerabilities)           │
│     └─ OWASP ZAP (DAST — planned)                          │
│                                                              │
│  7. CONTAINER IMAGE BUILD                                    │
│     ├─ docker build for each service                        │
│     ├─ Tag: <service>:<commit-sha>                          │
│     ├─ Tag: <service>:latest (on main branch only)          │
│     └─ Multi-platform build (amd64)                         │
│                                                              │
│  8. IMAGE PUSH (main branch only)                           │
│     └─ Push to container registry (GitHub Container         │
│        Registry or Docker Hub)                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 5.1.3 Quality Gates

| Gate | Threshold | Action on Failure |
|------|-----------|-------------------|
| Lint (flake8) | Zero errors | Block merge |
| Type check (mypy) | Zero errors | Block merge |
| Unit test coverage | >= 80% | Block merge |
| Security scan (bandit) | No high-severity findings | Block merge |
| Image vulnerability scan | No critical CVEs | Block merge |
| Build success | All 6 images build | Block merge |

#### 5.1.4 Container Image Strategy

| Property | Value |
|----------|-------|
| Base image | `python:3.11-slim` |
| Tag format | `<service>:<git-sha-short>` and `<service>:latest` |
| Registry | GitHub Container Registry (`ghcr.io/d00256764/`) — planned |
| Current (dev) | Local build + `kind load docker-image` |

### 5.2 Continuous Delivery/Deployment

#### 5.2.1 Deployment Pipeline Stages

```
┌──────────────────────────────────────────────────────────────┐
│                    CD Pipeline Stages                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. ARTIFACT RETRIEVAL                                       │
│     └─ Pull validated images from container registry         │
│                                                              │
│  2. ENVIRONMENT CONFIGURATION                                │
│     ├─ Select target namespace (dev/test/prod)              │
│     ├─ Inject environment-specific secrets                  │
│     └─ Validate manifest syntax (kube-score / kubeval)      │
│                                                              │
│  3. DATABASE MIGRATION                                       │
│     ├─ Apply schema changes (if any)                        │
│     ├─ Run migration scripts                                │
│     └─ Validate schema post-migration                       │
│                                                              │
│  4. SERVICE DEPLOYMENT                                       │
│     ├─ kubectl apply -f (deployment + service manifests)    │
│     ├─ Rolling update (maxSurge=1, maxUnavailable=0)        │
│     └─ Wait for rollout complete                            │
│                                                              │
│  5. SMOKE TESTS                                              │
│     ├─ Health endpoint verification (/health → 200)         │
│     ├─ Database connectivity check                          │
│     └─ Network policy validation                            │
│                                                              │
│  6. APPROVAL GATE (prod only)                               │
│     └─ Manual approval required before prod deployment      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 5.2.2 Environment Promotion Workflow

```
Feature Branch → main → uvote-dev (auto) → uvote-test (auto) → uvote-prod (manual approval)
```

| Environment | Trigger | Approval | Tests |
|-------------|---------|----------|-------|
| `uvote-dev` | Push to `main` | Automatic | Smoke tests |
| `uvote-test` | Successful dev deployment | Automatic | Integration + performance tests |
| `uvote-prod` | Successful test deployment | **Manual approval** | Full regression suite |

#### 5.2.3 Deployment Strategies

**Current: Rolling Update**

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1        # One extra pod created before old one terminates
    maxUnavailable: 0  # Zero downtime — always maintain minimum replicas
```

**Planned: Blue/Green Deployment**

```
                    ┌──────────────┐
                    │   Ingress    │
                    │  Controller  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐          ┌─────▼─────┐
        │   BLUE    │          │   GREEN   │
        │ (current) │          │  (new)    │
        │  v1.2.0   │          │  v1.3.0   │
        └───────────┘          └───────────┘

1. Deploy new version to GREEN
2. Run smoke tests against GREEN
3. Switch Ingress to point to GREEN
4. Monitor for errors
5. If errors → switch back to BLUE (instant rollback)
6. If stable → delete BLUE
```

**Planned: Canary Release**

```
Traffic split:
  90% → Current version (stable)
  10% → New version (canary)

Monitor canary for 15 minutes:
  - Error rate < 0.1%
  - P95 latency < 500ms
  - No CrashLoopBackOff

If healthy → gradually increase to 100%
If unhealthy → rollback canary to 0%
```

#### 5.2.4 Rollback Procedures

The deployment script supports automated rollback:

```bash
# Rollback all services
python3 plat_scripts/deploy_platform.py --rollback

# Kubernetes native rollback for a specific deployment
kubectl rollout undo deployment/auth-service -n uvote-dev

# Rollback to a specific revision
kubectl rollout undo deployment/auth-service -n uvote-dev --to-revision=2
```

### 5.3 Pipeline Tools and Justification

#### 5.3.1 CI/CD Platform: GitHub Actions

| Criterion | GitHub Actions | GitLab CI | Jenkins |
|-----------|---------------|-----------|---------|
| Repository integration | Native (same platform) | Native (GitLab only) | External plugin |
| Configuration | YAML in `.github/workflows/` | `.gitlab-ci.yml` | Jenkinsfile (Groovy) |
| Free tier | 2,000 min/month | 400 min/month | Self-hosted (no limit) |
| Docker support | Built-in (docker actions) | Built-in (DinD/Kaniko) | Plugin-based |
| Kubernetes integration | `kubectl` action | Built-in cluster agent | Plugin-based |
| Community actions | 18,000+ marketplace | Fewer templates | Extensive plugins |
| Learning curve | Low | Low | Medium-High |

**Decision:** GitHub Actions was selected because the project is hosted on GitHub, providing native integration without additional infrastructure. The free tier (2,000 minutes/month) is sufficient for this project's build frequency.

#### 5.3.2 GitOps: ArgoCD (Planned)

ArgoCD will be used for GitOps-based continuous deployment in Stage 2:

```
Git Repository (source of truth)
       │
       ▼
ArgoCD Controller (watches repo)
       │
       ├─ Detects manifest changes
       ├─ Compares with live cluster state
       ├─ Syncs (applies) changes automatically
       └─ Reports sync status
```

**Justification:**
- Declarative deployment model matches Kubernetes manifests
- Automatic drift detection (alerts if cluster state diverges from Git)
- Built-in rollback via Git revert
- Web UI for deployment visibility

---

## 6. Environment Strategy

### 6.1 Development Environment

**Local setup using Kind + Docker Compose:**

| Component | Configuration |
|-----------|--------------|
| Cluster | Kind (3 nodes: 1 CP + 2 workers) |
| CNI | Calico v3.26.1 |
| Database | PostgreSQL 15-alpine (in-cluster) |
| Images | Locally built, loaded via `kind load docker-image` |
| Namespace | `uvote-dev` |
| Ingress | Nginx Ingress Controller (Helm) |
| Secrets | Auto-generated by deployment script |

**Quick start:**

```bash
# Infrastructure setup (one-time)
python3 plat_scripts/setup_k8s_platform.py

# Service deployment
python3 plat_scripts/deploy_platform.py

# Or with Docker Compose (no Kubernetes)
docker-compose up --build
```

**Docker Compose alternative** provides a simplified development experience without Kubernetes:

```yaml
# docker-compose.yml — 7 services
services:
  postgres:       # PostgreSQL 15-alpine
  auth-service:   # Port 5001
  voter-service:  # Port 5002
  voting-service: # Port 5003
  results-service: # Port 5004
  election-service: # Port 5005
  frontend-service: # Port 8080 → 5000
```

All services depend on PostgreSQL health check (`pg_isready`) before starting.

### 6.2 Test Environment

| Component | Configuration |
|-----------|--------------|
| Namespace | `uvote-test` (reserved) |
| Data | Test fixtures seeded via schema.sql |
| Tests | Database integration (`test_db.py`), network policy validation, health endpoint checks |
| Isolation | Separate namespace with identical network policies |

### 6.3 Production Environment (Target)

| Component | Target Configuration |
|-----------|---------------------|
| Cluster | Azure AKS or AWS EKS (managed Kubernetes) |
| Nodes | 3+ worker nodes across availability zones |
| Database | Managed PostgreSQL (Azure Database / RDS) with automated backups |
| Storage | Cloud-managed persistent disks (Premium SSD) |
| Ingress | Cloud load balancer + Nginx Ingress + cert-manager for TLS |
| Secrets | HashiCorp Vault |
| Monitoring | Prometheus + Grafana |
| Logging | Loki or ELK Stack |

---

## 7. Deployment Strategy

### 7.1 Release Versioning

The project follows Semantic Versioning (SemVer):

```
MAJOR.MINOR.PATCH

Examples:
  1.0.0 — Initial release
  1.1.0 — New feature (e.g., CSV voter import)
  1.1.1 — Bug fix (e.g., token expiry calculation)
  2.0.0 — Breaking change (e.g., schema migration)
```

### 7.2 Deployment Automation

The deployment process is fully automated by `plat_scripts/deploy_platform.py`:

```
Phase 1: Pre-flight Checks
  ├─ Verify Kind cluster exists and is running
  ├─ Verify kubectl context is correct
  ├─ Verify Docker daemon is running
  ├─ Verify namespace uvote-dev exists
  ├─ Verify PostgreSQL is running and healthy
  └─ Check for existing deployments (warn if present)

Phase 2: Docker Image Building
  ├─ Build 6 service images from Dockerfiles
  ├─ Capture build output and report sizes
  └─ Track success/failure per image

Phase 3: Load Images into Kind
  ├─ kind load docker-image for each image
  └─ Verify images available in cluster

Phase 4: Secret Management
  ├─ Check existing secrets (db-credentials, jwt-secret, flask-secret)
  ├─ Create missing secrets with secure random values
  └─ Never overwrite existing secrets

Phase 5: Service Deployment
  ├─ Deploy backend services (kubectl apply -f)
  └─ Deploy frontend service (after backends)

Phase 6: Health Verification
  ├─ Wait for all pods to reach Running state (timeout: 5min)
  ├─ Verify all containers ready
  └─ Detect CrashLoopBackOff / ImagePullBackOff errors

Phase 7: Network Policy Testing
  ├─ Test database connectivity from backend services (should succeed)
  ├─ Test database connectivity from frontend (should fail — expected)
  └─ Test DNS resolution

Phase 8: Health Endpoint Testing
  ├─ Test /health endpoint on each service
  └─ Verify HTTP 200 responses

Phase 9: Results Summary
  ├─ Report pass/fail counts for all phases
  ├─ Log total deployment time
  └─ Provide next steps
```

**Command-line options:**

```bash
python3 plat_scripts/deploy_platform.py [OPTIONS]

  --cluster-name TEXT   Kind cluster name (default: uvote)
  --namespace TEXT       Kubernetes namespace (default: uvote-dev)
  --skip-build          Skip Docker image building
  --skip-tests          Skip network and health tests
  --services TEXT        Deploy specific services (comma-separated)
  --timeout INTEGER     Pod ready timeout in seconds (default: 300)
  --verbose             Enable debug logging
  --rollback            Rollback deployment (delete services)
  --dry-run             Show what would be done without executing
```

### 7.3 Zero-Downtime Deployment

Zero-downtime deployment is achieved through:

1. **Rolling updates** — `maxUnavailable: 0` ensures the current replica count is always maintained
2. **Readiness probes** — New pods receive traffic only after passing health checks
3. **Liveness probes** — Unhealthy pods are automatically restarted

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 5001
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3

livenessProbe:
  httpGet:
    path: /health
    port: 5001
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### 7.4 Deployment Checklist

```
PRE-DEPLOYMENT:
  [ ] All CI checks pass (lint, tests, security scan)
  [ ] Docker images built successfully
  [ ] Database migration tested in dev
  [ ] Secrets updated if needed
  [ ] Rollback plan documented

DEPLOYMENT:
  [ ] Run deploy_platform.py with --dry-run first
  [ ] Execute deployment
  [ ] Verify all pods reach Running state
  [ ] Verify health endpoints return 200
  [ ] Verify network policy enforcement
  [ ] Check pod logs for errors

POST-DEPLOYMENT:
  [ ] Smoke test critical flows (login, vote, results)
  [ ] Monitor error rates for 15 minutes
  [ ] Update deployment log
  [ ] Notify stakeholders
```

---

## 8. Observability Platform

### 8.1 Logging

#### 8.1.1 Current Implementation

**Application logging:** FastAPI services use Python's built-in logging, captured by Kubernetes and accessible via `kubectl logs`.

**Deployment logging:** The `deploy_platform.py` script generates timestamped log files:

```
[2026-02-16 22:30:15] [INFO] Starting U-Vote platform deployment
[2026-02-16 22:30:16] [INFO] Phase 1: Pre-flight Checks
[2026-02-16 22:30:16] [SUCCESS] ✓ Kind cluster 'uvote' is running
```

Log levels: `[INFO]`, `[SUCCESS]`, `[WARNING]`, `[ERROR]`, `[DEBUG]`

**Audit logging:** Application-level audit events are stored in the `audit_logs` database table with SHA-256 hash chains for tamper detection.

#### 8.1.2 Planned: Centralised Logging (Stage 2)

```
┌─────────────────────────────────────────────────────────────┐
│                    Logging Architecture                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Application Pods ──► stdout/stderr                          │
│         │                                                    │
│         ▼                                                    │
│  Promtail (DaemonSet) ──► Loki ──► Grafana                  │
│                                                              │
│  OR                                                          │
│                                                              │
│  Filebeat (DaemonSet) ──► Elasticsearch ──► Kibana           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Tool selection: Grafana Loki** is preferred over ELK Stack for:
- Lower resource footprint (no full-text indexing)
- Native Grafana integration (single dashboard for metrics + logs)
- Label-based querying matches Kubernetes pod labels

#### 8.1.3 Log Retention Policy

| Log Type | Retention | Rationale |
|----------|-----------|-----------|
| Application logs | 30 days | Sufficient for debugging; high volume |
| Audit logs | Indefinite (database) | Legal/compliance requirement; immutable |
| Deployment logs | 90 days | Useful for deployment history analysis |
| Security events | 1 year | Incident investigation window |

### 8.2 Monitoring

#### 8.2.1 Current Implementation

**Health endpoints** are implemented on all backend services:

```json
GET /health → {"status": "healthy", "service": "auth"}
```

**Kubernetes probes** provide automatic health monitoring:
- `livenessProbe` — Restarts unresponsive pods (after 30s initial delay, every 10s)
- `readinessProbe` — Removes unhealthy pods from service endpoints (after 10s, every 5s)

**Pod status monitoring:**

```bash
kubectl get pods -n uvote-dev -w  # Watch pod status changes in real-time
```

#### 8.2.2 Planned: Prometheus + Grafana (Stage 2)

```
Application Pods ──► /metrics endpoint (FastAPI prometheus-fastapi-instrumentator)
       │
       ▼
Prometheus (scrapes metrics every 15s)
       │
       ▼
Grafana (dashboards + alerting)
```

**Infrastructure metrics (Prometheus node-exporter):**
- CPU utilisation per node and pod
- Memory usage per node and pod
- Network I/O per pod
- Disk usage on PVC

**Application metrics (custom):**
- Request rate per service per endpoint
- Response time percentiles (p50, p95, p99)
- Error rate per service
- Active connections per database pool

**Business metrics (custom):**
- Elections created per day
- Votes cast per hour (during active elections)
- Token utilisation rate (tokens used / tokens generated)
- Voter participation rate

#### 8.2.3 Alert Definitions (Planned)

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| Pod crash loop | CrashLoopBackOff > 3 restarts | Critical | Page on-call |
| High error rate | 5xx rate > 1% for 5 minutes | Warning | Investigate logs |
| Database connection pool exhausted | Available connections = 0 | Critical | Scale pods or increase pool |
| High memory usage | Pod memory > 80% of limit | Warning | Consider scaling |
| Disk space low | PVC usage > 80% | Warning | Expand PVC |
| Health check failure | /health returns non-200 for 3 checks | Critical | Auto-restart (liveness probe) |

### 8.3 Tracing (Planned)

**Approach:** OpenTelemetry instrumentation for distributed tracing across services.

For a typical voting flow traversing Frontend → Voting Service → PostgreSQL, a trace would capture:
- Total request duration
- Time spent in each service
- Database query execution time
- Network latency between services

---

## 9. Security Architecture

### 9.1 Defence in Depth Strategy

The platform implements four independent security layers:

```
┌────────────────────────────────────────────────────────────┐
│ LAYER 1: NETWORK ISOLATION                                  │
│ Calico NetworkPolicy — 12 resources, zero-trust model      │
│ Frontend cannot reach database; default-deny all            │
├────────────────────────────────────────────────────────────┤
│ LAYER 2: DATABASE ACCESS CONTROL                           │
│ Per-service PostgreSQL users with least-privilege GRANTs   │
│ Results service: SELECT only; Auth service: admins only    │
├────────────────────────────────────────────────────────────┤
│ LAYER 3: APPLICATION SECURITY                              │
│ bcrypt password hashing; JWT authentication; CSRF          │
│ Parameterised queries; input validation (Pydantic)         │
├────────────────────────────────────────────────────────────┤
│ LAYER 4: DATA INTEGRITY                                    │
│ Database triggers prevent vote/audit modification          │
│ SHA-256 hash chains detect tampering                       │
│ Identity-ballot separation preserves anonymity             │
└────────────────────────────────────────────────────────────┘
```

Each layer operates independently — if one layer is bypassed, the others continue to provide protection.

### 9.2 Network Security

The full network security implementation is documented in [NETWORK-SECURITY.md](NETWORK-SECURITY.md). Key points:

- **12 NetworkPolicy resources** across 5 YAML files
- **Default-deny all** (Policy 00) — zero-trust foundation
- **DNS allow** (Policy 01) — enables service name resolution
- **Database access control** (Policy 02) — bidirectional, 6 whitelisted services
- **Ingress access** (Policy 03) — 6 per-service policies from ingress-nginx namespace
- **Audit access** (Policy 04) — bidirectional audit logging for 6 services

### 9.3 Container Security

| Control | Implementation |
|---------|---------------|
| Non-root execution | `runAsNonRoot: true`, `runAsUser: 1000` |
| Privilege escalation prevention | `allowPrivilegeEscalation: false` |
| Base image | `python:3.11-slim` (minimal attack surface) |
| Image pull policy | `imagePullPolicy: Never` (Kind — local images only) |
| Resource limits | Memory and CPU limits prevent resource exhaustion |

### 9.4 Secrets Management

**Current implementation:**

```yaml
# Secrets stored as Kubernetes Secret resources
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: uvote-dev
type: Opaque
stringData:
  username: "uvote_admin"
  password: "<generated>"
  database: "evote"
```

Secrets are:
- Never committed to Git (excluded in `.gitignore`)
- Auto-generated by `deploy_platform.py` using `secrets.token_urlsafe()`
- Injected into pods as environment variables via `secretKeyRef`
- Preserved across deployments (never overwritten if they exist)

**Planned: HashiCorp Vault** — Dynamic secret generation, audit logging of secret access, automatic rotation.

### 9.5 Application Security Controls

| Category | Implementation |
|----------|---------------|
| Password hashing | bcrypt with cost factor 12 (`passlib.context.CryptContext`) |
| Authentication | JWT HS256, 24-hour expiry |
| Token generation | `secrets.token_urlsafe(32)` — 256-bit entropy, CSPRNG |
| SQL injection prevention | Parameterised queries via asyncpg (`$1`, `$2` placeholders) |
| Input validation | Pydantic models for request/response validation |
| Vote anonymity | No voter_id in vote records; blind ballot tokens |
| Audit integrity | Hash-chained logs; database triggers prevent modification |

---

## 10. Operational Procedures

### 10.1 Runbook

#### 10.1.1 Service Startup

```bash
# 1. Start Kind cluster (if not running)
kind get clusters  # Check if 'uvote' exists
# If not: python3 plat_scripts/setup_k8s_platform.py

# 2. Deploy all services
python3 plat_scripts/deploy_platform.py

# 3. Verify
kubectl get pods -n uvote-dev
kubectl get svc -n uvote-dev
```

#### 10.1.2 Service Shutdown

```bash
# Delete application services (preserve database)
python3 plat_scripts/deploy_platform.py --rollback

# Full cluster teardown
kind delete cluster --name uvote
```

#### 10.1.3 Health Check Verification

```bash
# Check all pod statuses
kubectl get pods -n uvote-dev

# Check specific service health
kubectl exec -n uvote-dev deployment/auth-service -- \
  python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5001/health').read())"

# Check database health
kubectl exec -n uvote-dev deployment/postgresql -- pg_isready -U uvote_admin
```

#### 10.1.4 Common Troubleshooting

| Symptom | Diagnosis | Resolution |
|---------|-----------|------------|
| Pod in `CrashLoopBackOff` | `kubectl logs -n uvote-dev <pod>` | Fix application error; check env vars |
| Pod in `ErrImageNeverPull` | Image not loaded into Kind | `kind load docker-image <image> --name uvote` |
| Pod in `Pending` | `kubectl describe pod <pod>` | Check node resources; check PVC binding |
| Service unreachable | `kubectl get endpoints -n uvote-dev` | Check pod readiness; check network policies |
| Database connection timeout | Check network policy 02 | Verify pod label matches whitelist |
| DNS resolution failure | Check network policy 01 | Verify Calico is running; check `kube-dns` |

#### 10.1.5 Database Backup and Restore

```bash
# Backup
POD=$(kubectl get pod -n uvote-dev -l app=postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n uvote-dev $POD -- pg_dump -U uvote_admin evote > backup_$(date +%Y%m%d).sql

# Restore
kubectl exec -i -n uvote-dev $POD -- psql -U uvote_admin evote < backup_20260216.sql
```

### 10.2 Incident Response

#### 10.2.1 Incident Classification

| Severity | Definition | Response Time | Example |
|----------|-----------|---------------|---------|
| P1 — Critical | Voting system completely unavailable during active election | Immediate | All pods down; database unreachable |
| P2 — High | Significant functionality degraded | < 30 min | One service down; slow response times |
| P3 — Medium | Minor functionality affected | < 2 hours | Non-critical service error; log ingestion delayed |
| P4 — Low | Cosmetic or informational | Next business day | UI rendering issue; documentation error |

#### 10.2.2 Post-Mortem Template

```markdown
## Incident Post-Mortem

**Date:** YYYY-MM-DD
**Duration:** HH:MM
**Severity:** P1/P2/P3/P4
**Services Affected:**

### Summary
One-paragraph description of what happened.

### Timeline
- HH:MM — Incident detected (how?)
- HH:MM — Investigation started
- HH:MM — Root cause identified
- HH:MM — Fix applied
- HH:MM — Service restored

### Root Cause
Technical description of why the incident occurred.

### Resolution
What was done to fix the issue.

### Prevention
What changes will prevent recurrence:
- [ ] Action item 1
- [ ] Action item 2

### Lessons Learned
What we learned from this incident.
```

### 10.3 Maintenance Windows

**Zero-downtime update procedure:**

1. Announce maintenance window (even though zero-downtime)
2. Create database backup
3. Deploy new images using rolling update (`deploy_platform.py`)
4. Monitor pod rollout (`kubectl rollout status`)
5. Verify health endpoints
6. Run smoke tests
7. Confirm deployment complete

---

## 11. Service Level Objectives

### 11.1 Availability

| Service | Target SLO | Measurement |
|---------|-----------|-------------|
| Voting Service | 99.9% (during active elections) | Successful requests / total requests |
| Auth Service | 99.5% | Successful authentications / total attempts |
| Results Service | 99.0% | Successful queries / total queries |
| Frontend | 99.5% | Successful page loads / total requests |
| Overall Platform | 99.5% | All services operational / total time |

### 11.2 Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Vote submission latency | < 500ms (p95) | Time from vote POST to confirmation response |
| Page load time | < 2s (p95) | Time from request to full page render |
| Database query time | < 100ms (p95) | Individual query execution time |
| Token validation | < 200ms (p95) | Time to validate voting token |
| Health check response | < 50ms (p95) | /health endpoint response time |

### 11.3 Error Budget

| SLO | Budget (per 30 days) | Equivalent Downtime |
|-----|---------------------|---------------------|
| 99.9% | 0.1% error budget | ~43 minutes/month |
| 99.5% | 0.5% error budget | ~3.6 hours/month |
| 99.0% | 1.0% error budget | ~7.2 hours/month |

### 11.4 Service Level Indicators

| SLI | Calculation | Source |
|-----|-------------|--------|
| Availability | `(successful_requests / total_requests) × 100` | Ingress access logs |
| Latency (p95) | 95th percentile of request duration | Application metrics |
| Error rate | `(5xx_responses / total_responses) × 100` | Application metrics |
| Throughput | Requests per second | Prometheus counter |

---

## 12. Scalability and Performance

### 12.1 Horizontal Scaling Strategy

**Current:** Fixed 2 replicas per service.

**Planned: Horizontal Pod Autoscaler (HPA)**

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: voting-service-hpa
  namespace: uvote-dev
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: voting-service
  minReplicas: 2
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### 12.2 Database Scaling

| Approach | Description | When to Apply |
|----------|-------------|--------------|
| Connection pooling | asyncpg pool (2-20 connections per pod) | Current (implemented) |
| Read replicas | PostgreSQL streaming replication | When read traffic exceeds single instance capacity |
| Vertical scaling | Increase PostgreSQL resource limits | When write performance degrades |
| Partitioning | Partition votes table by election_id | When table size exceeds billions of rows |

### 12.3 Performance Testing Approach

| Test Type | Tool | Scope |
|-----------|------|-------|
| Load testing | Locust or k6 | Simulate 1,000 concurrent voters |
| Stress testing | k6 | Find breaking point (max RPS) |
| Soak testing | k6 | 4-hour sustained load for memory leaks |
| Database performance | `test_db.py --load` | Bulk insert and query benchmarks |

### 12.4 Capacity Planning

For a target deployment supporting 1,000 concurrent voters:

| Component | Sizing | Rationale |
|-----------|--------|-----------|
| Voting Service | 3-5 pods | Highest traffic during voting window |
| Auth Service | 2 pods | Admin-only; low frequency |
| Frontend | 3 pods | Serves all voter page loads |
| PostgreSQL | 1 primary + 1 read replica | Separate read/write paths |
| Total memory | ~4GB (pod requests) | 13+ pods with 256Mi-512Mi each |

---

## 13. Disaster Recovery and Business Continuity

### 13.1 Recovery Objectives

| Metric | Target | Justification |
|--------|--------|---------------|
| **RTO** (Recovery Time Objective) | 30 minutes | Re-deploy from IaC + restore DB backup |
| **RPO** (Recovery Point Objective) | 1 hour | Backup interval for automated backups |

### 13.2 Backup Strategy

| Data | Method | Frequency | Retention | Storage |
|------|--------|-----------|-----------|---------|
| Database (full) | `pg_dump` | Every 4 hours during elections; daily otherwise | 30 days | Off-cluster volume |
| Database (WAL) | PostgreSQL WAL archiving | Continuous | 7 days | Off-cluster volume |
| Kubernetes manifests | Git repository | Every commit | Indefinite | GitHub |
| Secrets | Manual export (encrypted) | On change | Current + 1 previous | Encrypted off-site |

### 13.3 Recovery Procedures

**Scenario: Complete cluster failure**

```bash
# 1. Re-create cluster from IaC
python3 plat_scripts/setup_k8s_platform.py

# 2. Restore database from backup
kubectl exec -i -n uvote-dev $POD -- psql -U uvote_admin evote < latest_backup.sql

# 3. Deploy services
python3 plat_scripts/deploy_platform.py --skip-build  # Use existing images

# 4. Verify
python3 plat_scripts/deploy_platform.py --skip-build --services=""  # Health checks only
```

### 13.4 Backup Verification

Backup integrity should be verified monthly:

1. Restore backup to `uvote-test` namespace
2. Run `test_db.py` against restored database
3. Verify row counts match production
4. Test application connectivity to restored database
5. Document verification results

---

## 14. Infrastructure as Code

### 14.1 IaC Approach

All infrastructure is defined as declarative YAML and Python automation:

| Component | IaC Format | Location |
|-----------|-----------|----------|
| Cluster configuration | Kind YAML | `uvote-platform/kind-config.yaml` |
| Namespaces | Kubernetes YAML | `uvote-platform/k8s/namespaces/namespaces.yaml` |
| Database deployment | Kubernetes YAML | `uvote-platform/k8s/database/*.yaml` |
| Network policies | Kubernetes YAML | `uvote-platform/k8s/network-policies/*.yaml` |
| Service deployments | Kubernetes YAML | `uvote-platform/k8s/services/*.yaml` |
| Database schema | SQL | `uvote-platform/k8s/database/schema.sql` |
| Cluster automation | Python | `plat_scripts/setup_k8s_platform.py` |
| Deployment automation | Python | `plat_scripts/deploy_platform.py` |
| Database testing | Python | `plat_scripts/test_db.py` |
| Container images | Dockerfiles | `<service>/Dockerfile` |
| Local dev orchestration | Docker Compose | `docker-compose.yml` |

### 14.2 Configuration Management

Environment-specific configuration is injected via Kubernetes Secrets and environment variables:

```yaml
env:
- name: DB_HOST
  value: "postgresql"                    # Service name (same across environments)
- name: DB_USER
  valueFrom:
    secretKeyRef:
      name: db-credentials
      key: username                       # Injected from Secret
- name: JWT_SECRET
  valueFrom:
    secretKeyRef:
      name: jwt-secret
      key: secret                         # Per-environment secret
```

### 14.3 Environment Parity

The same Kubernetes manifests are used across environments with namespace-level isolation. Environment-specific values are injected via Secrets, ensuring:

- **Dev** manifests = **Test** manifests = **Prod** manifests (identical YAML)
- Only Secrets and resource limits differ between environments
- Network policies are identical (same zero-trust model everywhere)

### 14.4 Planned: Terraform

For cloud deployment (Stage 2), Terraform will manage:
- AKS/EKS cluster provisioning
- Managed PostgreSQL instance
- Virtual network and subnets
- Load balancer configuration
- DNS records

---

## 15. Future Enhancements

### 15.1 Stage 2 Priorities

| Enhancement | Priority | Effort | Impact |
|-------------|----------|--------|--------|
| GitHub Actions CI pipeline | High | Medium | Automated testing and image building |
| Prometheus + Grafana monitoring | High | Medium | Real-time observability |
| ArgoCD for GitOps | Medium | Medium | Automated deployment from Git |
| Grafana Loki for logging | Medium | Low | Centralised log aggregation |
| HPA for auto-scaling | Medium | Low | Dynamic scaling based on load |
| cert-manager for TLS | Medium | Low | Automated certificate management |

### 15.2 Medium-Term Roadmap

| Enhancement | Description |
|-------------|-------------|
| **HashiCorp Vault** | Dynamic secrets with automatic rotation; audit trail for secret access |
| **mTLS between services** | Mutual TLS for encrypted, authenticated service-to-service communication |
| **Open Policy Agent (OPA)** | Policy-as-code for admission control; validate manifests before deployment |
| **Database read replicas** | PostgreSQL streaming replication for read-heavy results queries |

### 15.3 Long-Term Vision

| Enhancement | Description |
|-------------|-------------|
| **Cloud migration** | Move from Kind to Azure AKS or AWS EKS for production workloads |
| **Multi-region deployment** | Active-active across two regions for high availability |
| **Service mesh (Istio/Linkerd)** | mTLS, traffic management, advanced observability without code changes |
| **Chaos engineering** | Litmus Chaos for resilience testing (pod kill, network partition) |
| **Cost optimisation** | Spot instances for non-critical workloads; right-sizing based on utilisation data |

---

## 16. Appendices

### Appendix A: Configuration Reference

#### A.1 Kind Cluster Configuration

```yaml
# uvote-platform/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: uvote
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
  podSubnet: 192.168.0.0/16
```

#### A.2 Database Deployment

```yaml
# uvote-platform/k8s/database/db-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgresql
  namespace: uvote-dev
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgresql
  template:
    metadata:
      labels:
        app: postgresql
    spec:
      containers:
      - name: postgresql
        image: postgres:15-alpine
        env:
        - name: POSTGRES_DB
          valueFrom: { secretKeyRef: { name: db-credentials, key: database } }
        - name: POSTGRES_USER
          valueFrom: { secretKeyRef: { name: db-credentials, key: username } }
        - name: POSTGRES_PASSWORD
          valueFrom: { secretKeyRef: { name: db-credentials, key: postgres-password } }
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
          subPath: postgres
        resources:
          requests: { memory: "256Mi", cpu: "250m" }
          limits: { memory: "512Mi", cpu: "500m" }
        livenessProbe:
          exec: { command: ["pg_isready", "-U", "uvote_admin"] }
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec: { command: ["pg_isready", "-U", "uvote_admin"] }
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
```

#### A.3 Service Deployment Template

```yaml
# Example: auth-service deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  namespace: uvote-dev
  labels:
    app: auth-service
    tier: backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: auth-service
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: auth-service
        tier: backend
    spec:
      containers:
      - name: auth-service
        image: auth-service:latest
        imagePullPolicy: Never
        ports:
        - containerPort: 5001
        env:
        - name: DB_HOST
          value: "postgresql"
        - name: DB_USER
          valueFrom: { secretKeyRef: { name: db-credentials, key: username } }
        - name: DB_PASSWORD
          valueFrom: { secretKeyRef: { name: db-credentials, key: password } }
        - name: JWT_SECRET
          valueFrom: { secretKeyRef: { name: jwt-secret, key: secret } }
        livenessProbe:
          httpGet: { path: /health, port: 5001 }
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet: { path: /health, port: 5001 }
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests: { memory: "128Mi", cpu: "100m" }
          limits: { memory: "512Mi", cpu: "1000m" }
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          allowPrivilegeEscalation: false
```

#### A.4 Network Policy: Default Deny

```yaml
# uvote-platform/k8s/network-policies/00-default-deny.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: uvote-dev
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

### Appendix B: Command Reference

#### B.1 Cluster Operations

```bash
# Create cluster
kind create cluster --config uvote-platform/kind-config.yaml --name uvote

# Delete cluster
kind delete cluster --name uvote

# List clusters
kind get clusters

# Set kubectl context
kubectl config use-context kind-uvote

# Check nodes
kubectl get nodes -o wide
```

#### B.2 Deployment Operations

```bash
# Full deployment
python3 plat_scripts/deploy_platform.py

# Dry run
python3 plat_scripts/deploy_platform.py --dry-run

# Deploy specific services
python3 plat_scripts/deploy_platform.py --services auth-service,voting-service

# Skip image build (use existing)
python3 plat_scripts/deploy_platform.py --skip-build

# Rollback
python3 plat_scripts/deploy_platform.py --rollback

# Build and load single image
docker build -t auth-service:latest auth-service/
kind load docker-image auth-service:latest --name uvote
```

#### B.3 Monitoring Commands

```bash
# Pod status
kubectl get pods -n uvote-dev -o wide
kubectl get pods -n uvote-dev -w  # Watch mode

# Pod logs
kubectl logs -n uvote-dev -l app=auth-service --tail=100 -f

# Pod details (events, conditions)
kubectl describe pod -n uvote-dev <pod-name>

# Resource usage
kubectl top pods -n uvote-dev
kubectl top nodes

# Network policies
kubectl get networkpolicy -n uvote-dev
kubectl describe networkpolicy allow-to-database -n uvote-dev

# Service endpoints
kubectl get endpoints -n uvote-dev

# Events (sorted by time)
kubectl get events -n uvote-dev --sort-by='.lastTimestamp'
```

#### B.4 Database Operations

```bash
# Get PostgreSQL pod name
POD=$(kubectl get pod -n uvote-dev -l app=postgresql -o jsonpath='{.items[0].metadata.name}')

# Interactive psql session
kubectl exec -it -n uvote-dev $POD -- psql -U uvote_admin -d evote

# Run SQL command
kubectl exec -n uvote-dev $POD -- psql -U uvote_admin -d evote -c "SELECT count(*) FROM votes;"

# Check database health
kubectl exec -n uvote-dev $POD -- pg_isready -U uvote_admin

# Backup
kubectl exec -n uvote-dev $POD -- pg_dump -U uvote_admin evote > backup.sql

# Restore
kubectl exec -i -n uvote-dev $POD -- psql -U uvote_admin evote < backup.sql

# List tables
kubectl exec -n uvote-dev $POD -- psql -U uvote_admin -d evote -c "\dt"

# Check indexes
kubectl exec -n uvote-dev $POD -- psql -U uvote_admin -d evote -c "\di"
```

### Appendix C: Troubleshooting Guide

#### C.1 Common Issues and Solutions

| # | Issue | Diagnosis | Solution |
|---|-------|-----------|----------|
| 1 | Pod `CrashLoopBackOff` | `kubectl logs <pod>` — look for Python import errors or connection failures | Fix app error; check environment variables; verify secrets exist |
| 2 | Pod `ErrImageNeverPull` | Image not loaded into Kind cluster | `kind load docker-image <image>:latest --name uvote` |
| 3 | Pod `Pending` | `kubectl describe pod` — check events for scheduling failures | Check node resources (`kubectl describe nodes`); check PVC binding |
| 4 | Service returns 502/503 | No ready endpoints | Check pod readiness probe; increase `initialDelaySeconds` if app is slow to start |
| 5 | Database connection timeout | Network policy blocking egress | Verify pod label matches policy 02 whitelist; check Calico is running |
| 6 | DNS resolution failure | Network policy blocking DNS | Verify policy 01 applied; check CoreDNS pods in `kube-system` |
| 7 | Secrets not found | Secret not created in correct namespace | `kubectl get secrets -n uvote-dev`; re-run deployment script |
| 8 | PVC stuck in `Pending` | Storage class not available | For Kind: verify `local-path-provisioner` is running |
| 9 | Node `NotReady` | CNI not installed or Calico crash | Check `kubectl get pods -n calico-system`; re-install Calico if needed |
| 10 | Port-forward not working | Service selector doesn't match pod labels | Verify `kubectl get endpoints -n uvote-dev <service-name>` shows pod IPs |

#### C.2 Debug Checklist

```
CLUSTER HEALTH:
  [ ] kubectl get nodes — all Ready?
  [ ] kubectl get pods -n calico-system — all Running?
  [ ] kubectl get pods -n kube-system — CoreDNS running?

NAMESPACE:
  [ ] kubectl get ns uvote-dev — exists?
  [ ] kubectl get networkpolicy -n uvote-dev — 12 policies?

DATABASE:
  [ ] kubectl get pods -n uvote-dev -l app=postgresql — Running?
  [ ] kubectl exec $POD -- pg_isready — accepts connections?
  [ ] kubectl get pvc -n uvote-dev — Bound?

APPLICATION:
  [ ] kubectl get pods -n uvote-dev — all Running and Ready?
  [ ] kubectl get endpoints -n uvote-dev — all have addresses?
  [ ] kubectl logs <pod> — no errors?

NETWORKING:
  [ ] DNS works: kubectl exec <pod> -- python3 -c "import socket; socket.getaddrinfo('postgresql',5432)"
  [ ] DB reachable: kubectl exec <pod> -- python3 -c "import socket; s=socket.socket(); s.connect(('postgresql',5432))"
```

### Appendix D: Resource Requirements

#### D.1 Minimum System Requirements

| Resource | Minimum | Notes |
|----------|---------|-------|
| CPU | 4 cores | Kind cluster + Docker overhead |
| RAM | 8GB | Tight — may require reducing replicas to 1 |
| Disk | 20GB | Kind images + Docker images + PVC |
| OS | Linux, macOS, Windows (WSL2) | Docker must be running |

#### D.2 Recommended System Requirements

| Resource | Recommended | Notes |
|----------|------------|-------|
| CPU | 8 cores | Comfortable with 2 replicas per service |
| RAM | 16GB | Headroom for monitoring tools |
| Disk | 40GB | Room for image caching and database growth |

#### D.3 Production Sizing Guide

| Component | Dev (Kind) | Test (Kind/Cloud) | Production (Cloud) |
|-----------|-----------|-------------------|-------------------|
| Control plane | 1 node | 1 node | 3 nodes (HA) |
| Workers | 2 nodes | 3 nodes | 3-5 nodes (multi-AZ) |
| Service replicas | 2 each | 2 each | 3-5 each (HPA) |
| PostgreSQL | 1 instance | 1 instance | Primary + read replica |
| Storage | 5Gi | 10Gi | 50Gi+ (cloud SSD) |
| Memory (total) | 8-16GB | 16-32GB | 32-64GB |
| CPU (total) | 4-8 cores | 8-16 cores | 16-32 cores |

---

## Document Cross-References

| Document | Location | Content |
|----------|----------|---------|
| **README.md** | Repository root | Project overview, quick start, architecture summary |
| **ARCHITECTURE.MD** | `.docs/ARCHITECTURE.MD` | Service descriptions, API endpoints, database schema, voting flow |
| **PLATFORM.MD** | `.docs/PLATFORM.MD` | Infrastructure overview, setup guide, troubleshooting |
| **NETWORK-SECURITY.md** | `.docs/NETWORK-SECURITY.md` | Complete network policy specification, testing results |
| **This document** | `.docs/PLATFORM-COMPREHENSIVE.md` | Comprehensive platform documentation (this file) |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Calico** | Container Network Interface (CNI) plugin that provides networking and network policy enforcement for Kubernetes |
| **CNI** | Container Network Interface — standard for configuring networking in Linux containers |
| **HPA** | Horizontal Pod Autoscaler — Kubernetes resource that automatically scales pods based on metrics |
| **Kind** | Kubernetes in Docker — tool for running local Kubernetes clusters using Docker containers as nodes |
| **NetworkPolicy** | Kubernetes resource that specifies how pods are allowed to communicate with each other and other endpoints |
| **PVC** | PersistentVolumeClaim — Kubernetes request for storage that is fulfilled by a PersistentVolume |
| **RTO** | Recovery Time Objective — maximum acceptable time to restore service after an outage |
| **RPO** | Recovery Point Objective — maximum acceptable amount of data loss measured in time |
| **SLI** | Service Level Indicator — quantitative measure of an aspect of the level of service provided |
| **SLO** | Service Level Objective — target value for a service level indicator |
| **Zero-trust** | Security model where no implicit trust is granted to any entity, regardless of network location |

---

## Appendix E: Dockerfile Analysis

All six services follow a consistent Dockerfile pattern using `python:3.11-slim` as the base image. This section documents the containerisation approach and its security implications.

### E.1 Standard Dockerfile Template

```dockerfile
# Base image: python:3.11-slim
# - Minimal Debian-based image (~150MB vs ~900MB for full python:3.11)
# - Includes pip, Python standard library
# - Does NOT include gcc, make, or other build tools
FROM python:3.11-slim

WORKDIR /app

# Copy shared utilities first (changes infrequently → better layer caching)
COPY shared /app/shared

# Copy and install service-specific dependencies
COPY <service>/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (changes frequently → last layer)
COPY <service>/app.py .
# Some services also copy templates/ and static/ directories

EXPOSE <port>

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "<port>"]
```

### E.2 Service-Specific Dockerfiles

| Service | Dockerfile Context | Exposed Port | Extra Layers |
|---------|-------------------|--------------|-------------|
| auth-service | `auth-service/` | 5001 | None |
| election-service | `election-service/` | 5005 | `templates/`, `static/` |
| frontend-service | `frontend-service/` | 5000 | `templates/`, `static/css/` |
| results-service | `results-service/` | 5004 | `templates/`, `static/` |
| voter-service | `voter-service/` | 5002 | `templates/`, `static/` |
| voting-service | `voting-service/` | 5003 | `templates/`, `static/` |

### E.3 Build Context

All Dockerfiles use the project root as the build context (`docker build -t <service>:latest .` from the root). This is necessary because the `COPY shared /app/shared` instruction copies the `shared/` directory from the project root into the container.

### E.4 Layer Caching Strategy

```
Layer 1: FROM python:3.11-slim          ← Shared across all services
Layer 2: COPY shared /app/shared        ← Shared; changes rarely
Layer 3: COPY requirements.txt + pip    ← Per-service; changes on dependency update
Layer 4: COPY app.py (+ templates)      ← Per-service; changes on every code change
```

This ordering maximises Docker build cache hits: changing application code (Layer 4) does not invalidate the dependency installation layer (Layer 3).

### E.5 Security Considerations

| Property | Value | Note |
|----------|-------|------|
| Base image | `python:3.11-slim` | Minimal attack surface; fewer packages than full image |
| Non-root execution | Not in Dockerfile (enforced by K8s `securityContext`) | Pod-level enforcement via `runAsUser: 1000` |
| No secrets in image | Credentials injected via environment variables at runtime | Secrets never baked into image layers |
| `--no-cache-dir` | Yes | Reduces image size; prevents pip cache from bloating layers |

### E.6 Shared Utilities Layer

The `shared/` directory contains modules used by all services:

| Module | Purpose | Used By |
|--------|---------|---------|
| `shared/database.py` | Async connection pool manager (asyncpg) | All backend services |
| `shared/security.py` | Password hashing, token generation, hash chains | auth, voting, voter |
| `shared/schemas.py` | Pydantic data models | All services |
| `shared/email_util.py` | SMTP email sending (aiosmtplib) | voter-service |

### E.7 Python Dependencies by Service

| Service | Key Dependencies | Size Impact |
|---------|-----------------|-------------|
| auth-service | fastapi, uvicorn, asyncpg, passlib, pyjwt | ~50MB |
| election-service | fastapi, uvicorn, asyncpg, jinja2, passlib, pyjwt | ~55MB |
| frontend-service | fastapi, uvicorn, jinja2, httpx, itsdangerous | ~45MB |
| results-service | fastapi, uvicorn, asyncpg, jinja2, passlib, pyjwt | ~55MB |
| voter-service | fastapi, uvicorn, asyncpg, jinja2, aiosmtplib, passlib, pyjwt | ~60MB |
| voting-service | fastapi, uvicorn, asyncpg, passlib | ~45MB |

---

## Appendix F: Deployment Automation Detail

### F.1 Platform Setup Script (`setup_k8s_platform.py`)

The infrastructure setup script automates the complete cluster provisioning process:

```
┌──────────────────────────────────────────────────────────┐
│            setup_k8s_platform.py Execution Flow           │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Step 0: Prerequisite Check                              │
│    ├─ docker --version                                   │
│    ├─ kubectl version --client                           │
│    ├─ kind version                                       │
│    └─ helm version                                       │
│                                                          │
│  Step 1: Create Kind Cluster                             │
│    ├─ Check if 'uvote' cluster already exists            │
│    ├─ If exists: prompt to recreate or reuse             │
│    ├─ kind create cluster --config kind-config.yaml      │
│    └─ Verify nodes are Ready                             │
│                                                          │
│  Step 2: Install Calico CNI                              │
│    ├─ kubectl create -f tigera-operator.yaml             │
│    ├─ kubectl create -f custom-resources.yaml            │
│    ├─ Wait 30s initial delay                             │
│    └─ kubectl wait --for=condition=Ready (300s timeout)  │
│                                                          │
│  Step 3: Create Namespaces                               │
│    ├─ kubectl apply -f namespaces.yaml                   │
│    └─ Verify uvote-dev, uvote-test, uvote-prod exist     │
│                                                          │
│  Step 4: Deploy PostgreSQL                               │
│    ├─ kubectl apply -f db-secret.yaml                    │
│    ├─ kubectl apply -f db-pvc.yaml                       │
│    ├─ kubectl apply -f db-deployment.yaml                │
│    └─ kubectl wait --for=condition=Ready (120s timeout)  │
│                                                          │
│  Step 5: Apply Database Schema                           │
│    ├─ Get PostgreSQL pod name                            │
│    ├─ Read schema.sql                                    │
│    ├─ kubectl exec psql < schema.sql                     │
│    └─ Verify tables created (\\dt)                       │
│                                                          │
│  Step 6: Apply Network Policies                          │
│    ├─ kubectl apply -f 00-default-deny.yaml              │
│    ├─ kubectl apply -f 01-allow-dns.yaml                 │
│    ├─ kubectl apply -f 02-allow-to-database.yaml         │
│    ├─ kubectl apply -f 03-allow-from-ingress.yaml        │
│    ├─ kubectl apply -f 04-allow-audit.yaml               │
│    └─ kubectl apply -f test-pods.yaml                    │
│                                                          │
│  Step 7: Install Nginx Ingress Controller                │
│    ├─ helm repo add ingress-nginx                        │
│    ├─ helm install ingress-nginx                         │
│    └─ Wait for controller pod to be Ready                │
│                                                          │
│  Step 8: Verification                                    │
│    ├─ Check all nodes Ready                              │
│    ├─ Check Calico pods Running                          │
│    ├─ Check PostgreSQL Running                           │
│    ├─ Check namespaces exist                             │
│    └─ Print final status summary                         │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**CLI options:**

```bash
python3 plat_scripts/setup_k8s_platform.py [OPTIONS]

  --skip-prereq    Skip prerequisite checks
  --skip-cluster   Skip cluster creation (use existing)
  --skip-calico    Skip Calico installation
  --skip-ingress   Skip ingress controller installation
  --skip-verify    Skip final verification
```

### F.2 Service Deployment Script (`deploy_platform.py`)

The deployment script implements a 9-phase deployment pipeline with:

- **Dual logging** — Coloured console output + plain-text log file (`deploy-{timestamp}.log`)
- **Graceful degradation** — Individual service failures don't abort the entire deployment
- **Dry-run mode** — Shows what would be done without executing mutating commands
- **Rollback support** — `--rollback` flag deletes all deployed services
- **Secret preservation** — Never overwrites existing Kubernetes Secrets
- **Service filtering** — `--services` flag deploys only specified services

**Log format:**
```
[2026-02-16 22:30:15] [INFO] Starting U-Vote platform deployment
[2026-02-16 22:30:16] [SUCCESS] ✓ Kind cluster 'uvote' is running
[2026-02-16 22:30:17] [WARNING] ⚠ Existing deployments found: auth-service
[2026-02-16 22:30:18] [ERROR] ✗ Failed to build election-service
[2026-02-16 22:30:19] [DEBUG] CMD: docker build -t auth-service:latest ...
```

### F.3 Database Test Suite (`test_db.py`)

The comprehensive database test suite (47,000+ lines) validates:

| Category | Tests | Purpose |
|----------|-------|---------|
| Infrastructure | Pod health, connectivity | Verify PostgreSQL is accessible from the cluster |
| Schema | Table existence, column types, constraints | Verify schema.sql was applied correctly |
| Indexes | Index existence, naming | Verify query performance optimisation |
| Foreign keys | Referential integrity | Verify data relationships are enforced |
| Seed data | Sample admin, election, candidates | Verify initial data was loaded |
| Security | Vote immutability triggers | Verify UPDATE/DELETE on votes raises exception |
| Security | Least-privilege users | Verify per-service DB users have correct GRANTs |
| Performance | Bulk insert timing | Optional load test for throughput measurement |

**CLI options:**

```bash
python3 plat_scripts/test_db.py [OPTIONS]

  --quick    Run fast subset of tests
  --load     Include bulk-insert load test
  --pod POD  Specify PostgreSQL pod name
```

---

## Appendix G: Network Policy Validation Results

The following table summarises the network policy test results from diagnostic pod testing:

### G.1 Baseline Tests (No Policies Applied)

| Test | Source Pod | Destination | Expected | Result |
|------|-----------|-------------|----------|--------|
| DNS resolution | test-netshoot | kube-dns:53 | Connected | ✅ Connected |
| Database (allowed label) | test-allowed-db | postgresql:5432 | Connected | ✅ Connected |
| Database (blocked label) | test-blocked-db | postgresql:5432 | Connected | ✅ Connected |
| External (google.com) | test-netshoot | google.com:443 | Connected | ✅ Connected |

### G.2 After Policy 00 (Default Deny)

| Test | Source Pod | Destination | Expected | Result |
|------|-----------|-------------|----------|--------|
| DNS resolution | test-netshoot | kube-dns:53 | ❌ Blocked | ✅ Blocked |
| Database (allowed label) | test-allowed-db | postgresql:5432 | ❌ Blocked | ✅ Blocked |
| Database (blocked label) | test-blocked-db | postgresql:5432 | ❌ Blocked | ✅ Blocked |
| External (google.com) | test-netshoot | google.com:443 | ❌ Blocked | ✅ Blocked |

### G.3 After Policy 01 (DNS Allow)

| Test | Source Pod | Destination | Expected | Result |
|------|-----------|-------------|----------|--------|
| DNS resolution (short) | test-netshoot | postgresql | ✅ Resolves | ✅ Resolves |
| DNS resolution (FQDN) | test-netshoot | postgresql.uvote-dev.svc.cluster.local | ✅ Resolves | ✅ Resolves |
| Database TCP | test-allowed-db | postgresql:5432 | ❌ Blocked | ✅ Blocked |
| External | test-netshoot | google.com:443 | ❌ Blocked | ✅ Blocked |

### G.4 After Policy 02 (Database Access)

| Test | Source Pod | Destination | Expected | Result |
|------|-----------|-------------|----------|--------|
| auth-service label → DB | test-allowed-db | postgresql:5432 | ✅ Connected | ✅ Connected |
| test-blocked label → DB | test-blocked-db | postgresql:5432 | ❌ Blocked | ✅ Blocked |
| unlabelled pod → DB | test-netshoot | postgresql:5432 | ❌ Blocked | ✅ Blocked |

### G.5 Policy Count Verification

```bash
$ kubectl get networkpolicy -n uvote-dev --no-headers | wc -l
12
```

Expected: 12 policies. Actual: 12 policies. ✅

---

## Appendix H: CI/CD Pipeline YAML (Planned)

### H.1 GitHub Actions CI Pipeline

```yaml
# .github/workflows/ci.yml (planned for Stage 2)
name: CI Pipeline

on:
  push:
    branches: [main, 'feature/**']
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    - name: Install linting tools
      run: pip install flake8 mypy bandit
    - name: Run flake8
      run: flake8 --max-line-length 120 --exclude .venv,__pycache__
    - name: Run bandit (security linter)
      run: bandit -r auth-service/ voting-service/ voter-service/ results-service/ election-service/ frontend-service/ shared/ -ll

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        pip install pytest pytest-cov pytest-asyncio
        for svc in auth-service election-service frontend-service results-service voter-service voting-service; do
          pip install -r $svc/requirements.txt
        done
    - name: Run tests with coverage
      run: pytest --cov=. --cov-report=xml --cov-fail-under=80
      env:
        DB_HOST: localhost
        DB_PORT: 5432
        DB_NAME: test_db
        DB_USER: test_user
        DB_PASSWORD: test_pass

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service:
          - auth-service
          - election-service
          - frontend-service
          - results-service
          - voter-service
          - voting-service
    steps:
    - uses: actions/checkout@v4
    - name: Build Docker image
      run: docker build -t ${{ matrix.service }}:${{ github.sha }} -f ${{ matrix.service }}/Dockerfile .
    - name: Tag as latest (main only)
      if: github.ref == 'refs/heads/main'
      run: docker tag ${{ matrix.service }}:${{ github.sha }} ${{ matrix.service }}:latest

  security-scan:
    needs: [build]
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'
        severity: 'CRITICAL,HIGH'
        exit-code: '1'
```

### H.2 GitHub Actions CD Pipeline

```yaml
# .github/workflows/cd.yml (planned for Stage 2)
name: CD Pipeline

on:
  workflow_run:
    workflows: ["CI Pipeline"]
    branches: [main]
    types: [completed]

jobs:
  deploy-dev:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    environment: development
    steps:
    - uses: actions/checkout@v4
    - name: Configure kubectl
      run: |
        kind get kubeconfig --name uvote > kubeconfig
        echo "KUBECONFIG=kubeconfig" >> $GITHUB_ENV
    - name: Deploy to dev
      run: python3 plat_scripts/deploy_platform.py --skip-tests
    - name: Smoke tests
      run: python3 plat_scripts/deploy_platform.py --skip-build --services ""

  deploy-prod:
    needs: [deploy-dev]
    runs-on: ubuntu-latest
    environment:
      name: production
      # Requires manual approval in GitHub environment settings
    steps:
    - uses: actions/checkout@v4
    - name: Deploy to production
      run: echo "Production deployment would happen here"
```

---

## Appendix I: Service Health Endpoint Specifications

### I.1 Backend Services (HTTP Health Check)

All backend services expose a `GET /health` endpoint that returns:

```json
{
  "status": "healthy",
  "service": "<service-name>"
}
```

The Kubernetes deployment uses `httpGet` probes:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: <service-port>
  initialDelaySeconds: 30    # Wait for app startup
  periodSeconds: 10          # Check every 10 seconds
  timeoutSeconds: 5          # Max wait per check
  failureThreshold: 3        # 3 consecutive failures → restart pod

readinessProbe:
  httpGet:
    path: /health
    port: <service-port>
  initialDelaySeconds: 10    # Faster initial check for readiness
  periodSeconds: 5           # Check more frequently
  timeoutSeconds: 3          # Tighter timeout
  failureThreshold: 3        # 3 consecutive failures → remove from endpoints
```

### I.2 Frontend Service (TCP Health Check)

The frontend service does not expose a `/health` endpoint (it serves Jinja2 templates only). The deployment uses `tcpSocket` probes instead:

```yaml
livenessProbe:
  tcpSocket:
    port: 5000               # Check if port is accepting connections
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  tcpSocket:
    port: 5000
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

### I.3 PostgreSQL Health Check

The database uses `exec` probes running `pg_isready`:

```yaml
livenessProbe:
  exec:
    command: ["pg_isready", "-U", "uvote_admin"]
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  exec:
    command: ["pg_isready", "-U", "uvote_admin"]
  initialDelaySeconds: 5
  periodSeconds: 5
```

### I.4 Health Check Summary

| Service | Probe Type | Endpoint / Command | Liveness Delay | Readiness Delay |
|---------|-----------|-------------------|---------------|----------------|
| auth-service | httpGet | `/health:5001` | 30s | 10s |
| election-service | httpGet | `/health:5005` | 30s | 10s |
| frontend-service | tcpSocket | Port 5000 | 30s | 10s |
| results-service | httpGet | `/health:5004` | 30s | 10s |
| admin-service | httpGet | `/health:5002` | 30s | 10s |
| voting-service | httpGet | `/health:5003` | 30s | 10s |
| postgresql | exec | `pg_isready -U uvote_admin` | 30s | 5s |

---

## Appendix J: Docker Compose vs Kubernetes Comparison

The platform supports two deployment modes. This table compares them:

| Feature | Docker Compose | Kubernetes (Kind) |
|---------|---------------|-------------------|
| **Setup command** | `docker-compose up --build` | `python3 plat_scripts/setup_k8s_platform.py` |
| **Node count** | Single machine | 3 (1 CP + 2 workers) |
| **Network isolation** | Docker bridge (no policies) | Calico CNI with 12 NetworkPolicies |
| **Service discovery** | Docker DNS (container names) | Kubernetes CoreDNS (service names) |
| **Database credentials** | Hardcoded in docker-compose.yml | Kubernetes Secrets (auto-generated) |
| **Persistent storage** | Docker volume | PersistentVolumeClaim (5Gi) |
| **Replicas** | 1 per service | 2 per service |
| **Health checks** | Docker healthcheck (PostgreSQL only) | Liveness + readiness probes (all services) |
| **Rolling updates** | Recreate only | Rolling (maxSurge=1, maxUnavailable=0) |
| **Ingress** | Direct port mapping | Nginx Ingress Controller |
| **Security context** | Default (root) | Non-root, no privilege escalation |
| **Resource limits** | None | Memory + CPU limits per pod |
| **Use case** | Local development | Development + staging + production-like |

### Docker Compose Service Mapping

```yaml
# docker-compose.yml — Port mapping to Kubernetes equivalents
services:
  postgres:           # → postgresql deployment (K8s)
    ports: 5432:5432
  auth-service:       # → auth-service deployment (K8s)
    ports: 5001:5001
  voter-service:      # → admin-service deployment (K8s)  ← NOTE: different K8s name
    ports: 5002:5002
  voting-service:     # → voting-service deployment (K8s)
    ports: 5003:5003
  results-service:    # → results-service deployment (K8s)
    ports: 5004:5004
  election-service:   # → election-service deployment (K8s)
    ports: 5005:5005
  frontend-service:   # → frontend-service deployment (K8s)
    ports: 8080:5000  #    External 8080 → internal 5000
```

---

## Appendix K: Shared Module Architecture

### K.1 `shared/database.py` — Async Connection Pool

```python
class Database:
    """Async database connection pool manager using asyncpg.

    Usage pattern in service app.py:

        from shared.database import Database

        @app.on_event("startup")
        async def startup():
            await Database.get_pool()

        @app.on_event("shutdown")
        async def shutdown():
            await Database.close()

        @app.get("/data")
        async def get_data():
            async with Database.connection() as conn:
                rows = await conn.fetch("SELECT * FROM table")
                return rows
    """
    _pool: asyncpg.Pool | None = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=os.getenv("DB_HOST", "postgres"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "voting_db"),
                user=os.getenv("DB_USER", "voting_user"),
                password=os.getenv("DB_PASSWORD", "voting_pass"),
                min_size=2,   # Warm connections
                max_size=20,  # Upper bound
            )
        return cls._pool

    @classmethod
    @asynccontextmanager
    async def connection(cls):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            yield conn

    @classmethod
    @asynccontextmanager
    async def transaction(cls):
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                yield conn
```

### K.2 `shared/security.py` — Cryptographic Utilities

| Function | Purpose | Algorithm |
|----------|---------|-----------|
| `hash_password(password)` | Hash admin password | bcrypt (cost 12) |
| `verify_password(password, hashed)` | Verify admin login | bcrypt verify |
| `generate_voting_token(length=32)` | Create voter email token | `secrets.token_urlsafe(32)` — 256-bit |
| `generate_token_expiry(hours=168)` | Set token expiration | datetime + 7 days |
| `generate_blind_ballot_token()` | Create anonymous ballot token | `secrets.token_urlsafe(32)` |
| `generate_receipt_token()` | Create vote receipt | `secrets.token_urlsafe(24)` |
| `generate_election_key()` | Create encryption passphrase | `secrets.token_urlsafe(32)` |
| `hash_vote(election_id, option_id, timestamp)` | Hash vote record | SHA-256 |
| `create_hash_chain(previous_hash, current_data)` | Chain hashes | SHA-256(prev \|\| current) |

### K.3 Anonymity Protocol

The `security.py` module documents the anonymity protocol:

```
1. Voter authenticates via voting_token + DOB  (identity-linked)
2. Auth-service generates a BLIND ballot_token
   using fresh randomness — NOT derived from voter_id
3. Auth-service marks voter.has_voted = TRUE
   but does NOT store which ballot_token was issued
4. Voter uses ballot_token to cast an encrypted ballot
   (no identity attached to the ballot row)
```

This protocol ensures that even the server operator cannot correlate a voter's identity with their ballot choice, providing end-to-end vote anonymity.

---

## Appendix L: Troubleshooting Runbook

### L.1 Common Deployment Issues

| Symptom | Likely Cause | Resolution |
|---------|-------------|------------|
| Pod stuck in `ImagePullBackOff` | Image not loaded into Kind cluster | `kind load docker-image <image>:latest --name uvote` |
| Pod stuck in `CrashLoopBackOff` | Application startup failure | `kubectl logs -n uvote-dev <pod>` — check DB connection or missing env vars |
| Pod stuck in `Pending` | Insufficient node resources | `kubectl describe pod -n uvote-dev <pod>` — check resource requests vs node capacity |
| Service returns `503 Service Unavailable` | No ready endpoints | `kubectl get endpoints -n uvote-dev <service>` — verify readiness probe passing |
| Cannot connect between services | NetworkPolicy blocking traffic | Verify pod labels match policy selectors; check `kubectl describe networkpolicy -n uvote-dev` |
| Database connection refused | PostgreSQL not ready or secret mismatch | Verify `db-credentials` secret exists; check PostgreSQL pod logs |
| Frontend returns blank page | Static assets not found | Check `readOnlyRootFilesystem` setting; verify Jinja2 template mount |
| Health probe failing | Application not listening on expected port | Compare `containerPort` in manifest with `uvicorn --port` in app.py |

### L.2 Diagnostic Commands

```bash
# Cluster-wide overview
kubectl get all -n uvote-dev

# Check pod events for scheduling/startup issues
kubectl describe pod -n uvote-dev <pod-name>

# Stream logs from all pods of a service
kubectl logs -n uvote-dev -l app=auth-service --tail=100 -f

# Check service endpoint resolution
kubectl get endpoints -n uvote-dev

# Verify network policies are applied
kubectl get networkpolicy -n uvote-dev

# Test DNS resolution from within a pod
kubectl exec -n uvote-dev deployment/auth-service -- \
  python -c "import socket; print(socket.getaddrinfo('postgresql', 5432))"

# Test inter-service connectivity
kubectl exec -n uvote-dev deployment/auth-service -- \
  python -c "
import urllib.request
r = urllib.request.urlopen('http://election-service:5005/health')
print(r.read().decode())
"

# Check resource usage
kubectl top pods -n uvote-dev

# Verify secrets exist
kubectl get secrets -n uvote-dev
```

### L.3 Recovery Procedures

**Database Recovery:**

```bash
# 1. Scale down all services to prevent writes
for svc in auth-service admin-service voting-service election-service results-service frontend-service; do
  kubectl scale deployment/$svc -n uvote-dev --replicas=0
done

# 2. Check PostgreSQL pod status
kubectl get pods -n uvote-dev -l app=postgresql

# 3. If PVC data is intact, restart PostgreSQL
kubectl rollout restart deployment/postgresql -n uvote-dev

# 4. Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgresql -n uvote-dev --timeout=120s

# 5. Scale services back up
for svc in auth-service admin-service voting-service election-service results-service frontend-service; do
  kubectl scale deployment/$svc -n uvote-dev --replicas=2
done
```

**Full Cluster Rebuild:**

```bash
# Use the deployment automation script
python plat_scripts/deploy_platform.py --verbose

# Or step-by-step:
# 1. Recreate Kind cluster
kind delete cluster --name uvote
python plat_scripts/setup_k8s_platform.py

# 2. Build and deploy
python plat_scripts/deploy_platform.py --verbose
```

### L.4 Performance Baseline

Expected resource utilisation under idle/light load:

| Service | CPU (idle) | Memory (idle) | CPU (load) | Memory (load) |
|---------|-----------|---------------|-----------|---------------|
| auth-service | ~5m | ~80Mi | ~100m | ~200Mi |
| election-service | ~5m | ~80Mi | ~100m | ~200Mi |
| frontend-service | ~5m | ~60Mi | ~50m | ~150Mi |
| admin-service | ~5m | ~80Mi | ~100m | ~250Mi |
| voting-service | ~5m | ~80Mi | ~200m | ~300Mi |
| results-service | ~5m | ~80Mi | ~100m | ~200Mi |
| postgresql | ~10m | ~100Mi | ~500m | ~400Mi |

> **Note:** These are estimated baselines for a Kind development cluster. Production workloads will require profiling under realistic election load patterns.