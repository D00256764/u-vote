# E-Vote Platform Infrastructure

## Overview

This is the Kubernetes-based infrastructure platform for the E-Vote secure online voting system. This README covers the **MVP prototype deployment** using local Kubernetes with Calico networking.

**Current Status:** MVP Prototype  
**Deployment Target:** Local development (Kind cluster)  
**Security Focus:** Network isolation, database security, secure defaults

---

## Technology Stack (MVP)

| Component | Technology | Purpose |
|-----------|----------|---------|
| Container Orchestration | Kubernetes (Kind) | Service deployment and management |
| Networking | Calico | Network policies and service isolation |
| Database | PostgreSQL 15 | Persistent data storage |
| Ingress | Nginx Ingress Controller | External access and routing |
| Secrets | Kubernetes Secrets | Credential management |

### Planned for Future (Post-MVP)
- **Monitoring:** Prometheus + Grafana
- **Logging:** ELK Stack / Loki
- **CI/CD:** GitHub Actions + ArgoCD
- **IaC:** Terraform for cloud deployment
- **Cloud:** Azure AKS / AWS EKS

---

## Prerequisites

### Required Tools
- **Docker** (v20.10+)
- **kubectl** (v1.27+)
- **Kind** (v0.20.0+)
- **Helm** (v3.12+)

### System Requirements
- **CPU:** 4 cores minimum
- **RAM:** 8GB minimum (16GB recommended)
- **Disk:** 20GB free space
- **OS:** Linux, macOS, or Windows with WSL2

### Installation

**Linux:**
```bash
# Install Kind
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

---

## Quick Start

### One-Command Setup
```bash
# Clone the repository
git clone <repo-url>
cd evote-platform

# Run setup script
./scripts/setup-mvp.sh
```

This script will:
1. Create Kind cluster with 3 nodes
2. Install Calico CNI
3. Create namespaces (dev, test, prod)
4. Deploy PostgreSQL
5. Apply network policies
6. Install Nginx Ingress Controller

### Verify Installation
```bash
# Check cluster is running
kubectl get nodes

# Should show:
# NAME                  STATUS   ROLES           AGE   VERSION
# evote-control-plane   Ready    control-plane   2m    v1.27.0
# evote-worker          Ready    <none>          2m    v1.27.0
# evote-worker2         Ready    <none>          2m    v1.27.0

# Check Calico pods
kubectl get pods -n calico-system

# All pods should be Running

# Check application namespace
kubectl get all -n evote-dev

# Should show PostgreSQL pod and service
```

---

## Infrastructure Components

### 1. Kubernetes Cluster (Kind)

**Configuration:** `kind-config.yaml`
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: evote
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

**Features:**
- Multi-node cluster (1 control-plane, 2 workers)
- Port forwarding for HTTP/HTTPS
- Calico-compatible networking

### 2. Calico Networking

**Purpose:**
- Container Network Interface (CNI)
- Network policy enforcement
- Service-to-service isolation

**Components:**
- Calico Operator
- Calico CNI plugin
- Network policy controller

**Network Policies Applied:**
- Default deny all traffic
- Allow DNS resolution
- Service-specific ingress/egress rules
- Database access restrictions

### 3. Namespaces

| Namespace | Purpose |
|-----------|---------|
| `evote-dev` | Development environment |
| `evote-test` | Testing environment |
| `evote-prod` | Production environment |
| `ingress-nginx` | Ingress controller |
| `calico-system` | Calico components |

### 4. Storage

**PostgreSQL Persistent Volume:**
- Size: 5Gi (expandable)
- Access Mode: ReadWriteOnce
- Storage Class: standard (Kind default)

**Location:** `k8s/database/db-pvc.yaml`

### 5. Ingress Controller

**Nginx Ingress Controller:**
- Handles external HTTP/HTTPS traffic
- Routes requests to services
- TLS termination (future)

**Access:** `http://localhost` (after deployment)

### 6. Secrets Management

**Current Approach:**
- Kubernetes Secrets (base64 encoded)
- Stored in `k8s/secrets/` (NOT committed to Git)

**Secrets Created:**
- `db-credentials`: PostgreSQL admin password
- `db-service-credentials`: Per-service DB passwords
- `jwt-secret`: JWT signing key (for admin auth)
- `smtp-credentials`: Email service credentials

**Future:** HashiCorp Vault integration

---

## Detailed Setup Instructions

### Step 1: Create Kubernetes Cluster
```bash
# Create cluster
kind create cluster --config kind-config.yaml --name evote

# Set kubectl context
kubectl cluster-info --context kind-evote
```

### Step 2: Install Calico
```bash
# Install Calico operator
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/tigera-operator.yaml

# Install Calico custom resources
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/custom-resources.yaml

# Wait for Calico to be ready
kubectl wait --for=condition=Ready pods --all -n calico-system --timeout=300s
```

### Step 3: Create Namespaces
```bash
kubectl apply -f k8s/namespaces/namespaces.yaml
```

### Step 4: Deploy Database
```bash
# Create secrets
kubectl apply -f k8s/database/db-secret.yaml

# Deploy PostgreSQL
kubectl apply -f k8s/database/db-pvc.yaml
kubectl apply -f k8s/database/db-deployment.yaml

# Wait for database to be ready
kubectl wait --for=condition=Ready pod -l app=postgresql -n evote-dev --timeout=120s

# Initialize schema
kubectl exec -it -n evote-dev $(kubectl get pod -n evote-dev -l app=postgresql -o jsonpath='{.items[0].metadata.name}') -- \
  psql -U evote_admin -d evote -f /docker-entrypoint-initdb.d/schema.sql
```

### Step 5: Apply Network Policies
```bash
kubectl apply -f k8s/network-policies/
```

### Step 6: Install Nginx Ingress
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace
```

### Step 7: Deploy Application Services
```bash
# Deploy all services
kubectl apply -f k8s/services/

# Verify all pods are running
kubectl get pods -n evote-dev
```

---

## Network Security Architecture

### Network Policy Model
```
┌─────────────────────────────────────────────────┐
│  Default: DENY ALL traffic                     │
└─────────────────────────────────────────────────┘
                      ↓
         ┌────────────────────────┐
         │  Explicit ALLOW rules  │
         └────────────────────────┘
                      ↓
    ┌─────────────────┬──────────────────┐
    │                 │                  │
┌───▼────┐    ┌──────▼─────┐    ┌──────▼─────┐
│Frontend│    │  Services  │    │  Database  │
│  Can:  │    │   Can:     │    │   Can:     │
│  None  │    │ - DNS      │    │ - Ingress  │
│ (static│    │ - Database │    │   from     │
│  files)│    │ - Audit    │    │   services │
└────────┘    └────────────┘    └────────────┘
```

### Service Isolation Rules

**Database Access:**
```yaml
# Only these services can reach PostgreSQL:
- auth-service
- voting-service
- election-service
- results-service
- audit-service
- admin-service

# All others: BLOCKED
```

**External Access:**
```yaml
# Only Ingress Controller can receive external traffic
# Services are NOT directly accessible from outside
```

### Files

- `k8s/network-policies/00-default-deny.yaml` - Block all by default
- `k8s/network-policies/01-allow-dns.yaml` - DNS resolution
- `k8s/network-policies/02-allow-to-database.yaml` - Service → DB
- `k8s/network-policies/03-allow-from-ingress.yaml` - Ingress → Services
- `k8s/network-policies/04-allow-audit.yaml` - Services → Audit

---

## Database Management

### Access Database

**From outside cluster:**
```bash
# Port-forward to access locally
kubectl port-forward -n evote-dev svc/postgresql 5432:5432

# Connect with psql
psql -h localhost -U evote_admin -d evote
```

**From inside cluster:**
```bash
kubectl exec -it -n evote-dev <pod-name> -- psql -U evote_admin -d evote
```

### Database Users & Permissions

| Service | DB User | Permissions |
|---------|---------|-------------|
| Auth Service | `auth_service` | SELECT, INSERT, UPDATE on `admins` |
| Voting Service | `voting_service` | INSERT on `votes`, SELECT on `elections`, `candidates`, UPDATE on `voting_tokens` |
| Election Service | `election_service` | ALL on `elections`, `candidates` |
| Results Service | `results_service` | SELECT only (read-only) |
| Audit Service | `audit_service` | INSERT, SELECT on `audit_logs` |
| Admin Service | `admin_service` | SELECT, INSERT, UPDATE, DELETE on `voters`, `candidates`, `voting_tokens` |

### Backup & Restore

**Backup:**
```bash
kubectl exec -n evote-dev <postgresql-pod> -- \
  pg_dump -U evote_admin evote > backup_$(date +%Y%m%d).sql
```

**Restore:**
```bash
kubectl exec -i -n evote-dev <postgresql-pod> -- \
  psql -U evote_admin evote < backup_20260211.sql
```

---

## Troubleshooting

### Common Issues

**1. Pods stuck in Pending state**
```bash
# Check node resources
kubectl describe nodes

# Check PVC status
kubectl get pvc -n evote-dev

# Solution: May need to increase Kind node resources
```

**2. Database connection failures**
```bash
# Check database pod logs
kubectl logs -n evote-dev -l app=postgresql

# Check service is reachable
kubectl exec -n evote-dev <app-pod> -- nc -zv postgresql 5432

# Solution: Verify network policies allow connection
```

**3. Network policy blocking traffic**
```bash
# Check which policies apply to pod
kubectl describe pod <pod-name> -n evote-dev

# Test connectivity
kubectl exec -n evote-dev <pod-name> -- curl <target-service>:8001

# Solution: Add explicit allow rule in network policy
```

**4. Calico not working**
```bash
# Check Calico pods
kubectl get pods -n calico-system

# Restart Calico if needed
kubectl rollout restart deployment/calico-typha -n calico-system
```

### Debug Checklist

- [ ] All nodes are Ready: `kubectl get nodes`
- [ ] Calico pods Running: `kubectl get pods -n calico-system`
- [ ] Database pod Running: `kubectl get pods -n evote-dev -l app=postgresql`
- [ ] Services have endpoints: `kubectl get endpoints -n evote-dev`
- [ ] Network policies applied: `kubectl get networkpolicies -n evote-dev`
- [ ] Check pod logs: `kubectl logs -n evote-dev <pod-name>`

---

## Architecture Diagram
```
┌────────────────────────────────────────────────────────┐
│                    Kind Cluster                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │           Calico Network (192.168.0.0/16)        │  │
│  │                                                  │  │
│  │  ┌────────────────────────────────────────────┐ │  │
│  │  │  Namespace: evote-dev                      │ │  │
│  │  │                                            │ │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐ │ │  │
│  │  │  │ Frontend │  │  Auth    │  │ Election │ │ │  │
│  │  │  │ Service  │  │ Service  │  │ Service  │ │ │  │
│  │  │  └──────────┘  └──────────┘  └──────────┘ │ │  │
│  │  │                                            │ │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐ │ │  │
│  │  │  │ Voting   │  │ Results  │  │  Audit   │ │ │  │
│  │  │  │ Service  │  │ Service  │  │ Service  │ │ │  │
│  │  │  └──────────┘  └──────────┘  └──────────┘ │ │  │
│  │  │                                            │ │  │
│  │  │  ┌──────────┐  ┌──────────┐               │ │  │
│  │  │  │  Admin   │  │  Email   │               │ │  │
│  │  │  │ Service  │  │ Service  │               │ │  │
│  │  │  └──────────┘  └──────────┘               │ │  │
│  │  │                                            │ │  │
│  │  │         ↓ (Network Policies Control)      │ │  │
│  │  │                                            │ │  │
│  │  │  ┌────────────────────────────────────┐   │ │  │
│  │  │  │      PostgreSQL Database           │   │ │  │
│  │  │  │  (PersistentVolume: 5Gi)           │   │ │  │
│  │  │  └────────────────────────────────────┘   │ │  │
│  │  └────────────────────────────────────────────┘ │  │
│  │                                                  │  │
│  │  ┌────────────────────────────────────────────┐ │  │
│  │  │  Namespace: ingress-nginx                  │ │  │
│  │  │  ┌──────────────────────────────────────┐  │ │  │
│  │  │  │   Nginx Ingress Controller           │  │ │  │
│  │  │  │   (Routes external traffic)          │  │ │  │
│  │  │  └──────────────────────────────────────┘  │ │  │
│  │  └────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
           ↑                                    ↑
    Port 80 (HTTP)                       Port 443 (HTTPS)
           │                                    │
      ┌────▼────────────────────────────────────▼────┐
      │         External Users / Browsers            │
      └─────────────────────────────────────────────┘
```

---

## Project Structure
```
evote-platform/
├── k8s/
│   ├── namespaces/
│   │   └── namespaces.yaml
│   ├── database/
│   │   ├── db-secret.yaml
│   │   ├── db-pvc.yaml
│   │   ├── db-deployment.yaml
│   │   └── schema.sql
│   ├── services/
│   │   ├── auth-service.yaml
│   │   ├── voting-service.yaml
│   │   ├── election-service.yaml
│   │   ├── results-service.yaml
│   │   ├── audit-service.yaml
│   │   ├── admin-service.yaml
│   │   ├── email-service.yaml
│   │   └── frontend.yaml
│   ├── network-policies/
│   │   ├── 00-default-deny.yaml
│   │   ├── 01-allow-dns.yaml
│   │   ├── 02-allow-to-database.yaml
│   │   ├── 03-allow-from-ingress.yaml
│   │   └── 04-allow-audit.yaml
│   └── ingress/
│       └── evote-ingress.yaml
├── scripts/
│   ├── setup-mvp.sh
│   ├── teardown.sh
│   └── deploy-services.sh
├── kind-config.yaml
└── README.md (this file)
```

---

## Future Enhancements (Post-MVP)

### Monitoring & Observability
- [ ] Prometheus for metrics collection
- [ ] Grafana dashboards (system, application, business metrics)
- [ ] AlertManager for alerting
- [ ] Service-level objectives (SLOs)

### Logging
- [ ] ELK Stack / Loki for centralized logging
- [ ] Log aggregation from all services
- [ ] Log retention policies

### CI/CD
- [ ] GitHub Actions for automated builds
- [ ] ArgoCD for GitOps deployments
- [ ] Automated testing in pipeline
- [ ] Blue/Green or Canary deployments

### Infrastructure as Code
- [ ] Terraform for cloud provisioning
- [ ] Deployment to Azure AKS
- [ ] Multi-region setup

### Security Enhancements
- [ ] HashiCorp Vault for secrets
- [ ] mTLS between services
- [ ] Certificate management (cert-manager)
- [ ] Security scanning in CI/CD

---

## Contributing

See application repository for development guidelines.

## License

[Your License]

## Contact

[Your Contact Info]