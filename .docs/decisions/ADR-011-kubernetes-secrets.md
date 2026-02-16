# ADR-011: Kubernetes Secrets for Secret Management

## Status

**Status:** Accepted
**Date:** 2026-02-14
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

The U-Vote platform requires a mechanism for managing sensitive configuration data — database credentials, JWT signing keys, API tokens, and encryption keys — across six microservices running in a Kubernetes cluster. These secrets must be injected into pods at runtime without being hardcoded in source code, Docker images, or Kubernetes manifests committed to version control.

### Background

During early prototyping (Weeks 1–3), secrets were embedded directly in Python source files and Docker environment variables defined in `docker-compose.yml`. This approach was flagged during a security review in Week 4 as a critical vulnerability: credentials were visible in plaintext in the Git history, Docker image layers, and container inspection output. The team evaluated four approaches to secret management, ranging from simple environment variable injection to dedicated secret management platforms.

The project runs on a local Kind cluster (1 control-plane + 2 worker nodes) for development and demonstration. There is no cloud provider KMS or managed secret store available. The cluster is ephemeral — it is destroyed and recreated regularly during development via `deploy_platform.py`.

### Requirements

- **R1:** Secrets must not appear in source code, Git history, or Docker image layers
- **R2:** Each microservice must receive only the secrets it needs (least-privilege)
- **R3:** Secrets must be injectable as environment variables in pod containers
- **R4:** Secret creation and rotation must be automatable via deployment scripts
- **R5:** The solution must work on a local Kind cluster without external dependencies
- **R6:** Secrets must be manageable without additional infrastructure components
- **R7:** The solution must integrate with the existing `deploy_platform.py` deployment workflow
- **R8:** Secret values must be changeable without rebuilding Docker images

### Constraints

- **C1:** Local Kind cluster — no cloud KMS, no managed secret stores
- **C2:** Single-developer project — operational overhead must be minimal
- **C3:** 16GB RAM on development machine — cannot run heavy infrastructure components
- **C4:** Ephemeral cluster lifecycle — secrets must be recreatable programmatically
- **C5:** Academic project — production-grade secret management is a Stage 2 goal

---

## Options Considered

### Option 1: Hardcoded Environment Variables

**Description:**
Define secrets directly in Kubernetes Deployment manifests using `env` fields with plaintext values, or pass them via `docker-compose.yml` environment sections. This is the simplest possible approach — no additional tooling or abstraction.

**Pros:**
- Zero setup required
- Immediately visible in manifests (easy debugging)
- No learning curve
- Works identically in Docker Compose and Kubernetes

**Cons:**
- Secrets stored in plaintext in version-controlled YAML files
- Visible in Git history permanently (even if later removed)
- No access control — anyone with repo access sees all secrets
- Cannot rotate secrets without modifying and redeploying manifests
- Violates OWASP secret management guidelines
- No audit trail for secret access

**Evaluation:**
Hardcoded environment variables fail R1 entirely. Secrets in Git history are a permanent exposure. This approach was used during prototyping and is explicitly being replaced.

### Option 2: Kubernetes Secrets (Native) — Chosen

**Description:**
Use Kubernetes' built-in Secret resource to store sensitive data as base64-encoded key-value pairs in etcd. Secrets are created via `kubectl create secret` or declaratively via manifests (excluded from Git). Pods reference secrets via `envFrom` or individual `env.valueFrom.secretKeyRef` fields. The `deploy_platform.py` script creates secrets programmatically during cluster setup.

**Pros:**
- Native to Kubernetes — no additional software to install or maintain
- RBAC controls which ServiceAccounts can access which Secrets
- Mounted as environment variables or files in pods
- Can be created and rotated programmatically via kubectl or Python kubernetes client
- Secrets are stored in etcd (cluster storage), not in application manifests
- Supported by all Kubernetes tooling (kubectl, Lens, k9s)
- Namespace-scoped — natural isolation boundary

**Cons:**
- Base64 encoding is not encryption — anyone with etcd access can decode secrets
- etcd is not encrypted at rest by default in Kind clusters
- No built-in secret rotation or expiry mechanism
- No audit log for secret reads (requires enabling audit logging separately)
- Secrets visible to cluster admins via `kubectl get secret -o yaml`

**Evaluation:**
Kubernetes Secrets satisfy R1–R8 for the MVP scope. The base64 encoding limitation is acceptable for a local development cluster where the threat model does not include etcd compromise. RBAC provides sufficient access control for the project's scale.

### Option 3: HashiCorp Vault

**Description:**
HashiCorp Vault is a dedicated secret management platform that provides encryption at rest, dynamic secret generation, lease-based access, and comprehensive audit logging. It can be deployed as a Kubernetes pod and integrated via the Vault Agent Injector sidecar or CSI driver.

**Pros:**
- Encryption at rest and in transit
- Dynamic secrets with automatic rotation and TTL
- Comprehensive audit logging (who accessed what, when)
- Fine-grained access policies (per-path, per-identity)
- Industry standard for production secret management
- Supports secret versioning and rollback

**Cons:**
- Significant operational overhead — requires running Vault server pods, unsealing, and configuration
- Consumes 256–512MB RAM for the Vault server alone
- Requires learning HCL policy language
- Vault Agent Injector adds a sidecar to every pod (increased resource usage)
- Complex bootstrapping — chicken-and-egg problem for initial unsealing
- Overkill for a local development environment with 6 services

**Evaluation:**
Vault is the gold standard for secret management but introduces substantial infrastructure overhead. Running Vault in a Kind cluster with 16GB RAM leaves insufficient resources for the application services. Vault is planned for Stage 2 when the project targets a production-like environment.

### Option 4: Bitnami Sealed Secrets

**Description:**
Sealed Secrets encrypts Kubernetes Secrets client-side using a public key, producing a `SealedSecret` custom resource that is safe to commit to Git. The Sealed Secrets controller running in the cluster decrypts them back into standard Kubernetes Secrets using its private key.

**Pros:**
- Encrypted secrets safe to commit to Git (GitOps compatible)
- Decrypts to standard Kubernetes Secrets (no application changes)
- Lower overhead than Vault (single controller pod)
- Supports secret rotation via re-encryption

**Cons:**
- Requires installing the Sealed Secrets controller (additional component)
- Private key management — if the controller's key is lost, all secrets are unrecoverable
- Ephemeral Kind cluster means the controller's key changes on every cluster recreation
- Re-sealing required whenever the cluster is recreated (breaks automation flow)
- Adds complexity for marginal benefit in a local-only environment
- Secrets are still base64 in etcd once decrypted (same as native Secrets)

**Evaluation:**
Sealed Secrets solves the "secrets in Git" problem but introduces key management complexity that conflicts with the ephemeral Kind cluster lifecycle. Since secrets are generated by `deploy_platform.py` on every cluster creation, the Git-safe storage benefit is minimal — secrets are never committed to Git regardless.

---

## Decision

**Chosen Option:** Kubernetes Secrets (Option 2)

**Rationale:**
Kubernetes Secrets provide the optimal balance between security and simplicity for the MVP phase. Since the Kind cluster is ephemeral and local, the primary threat is accidental secret exposure in source code or Git history — not etcd compromise. Kubernetes Secrets eliminate this threat by storing secrets outside the codebase entirely, while requiring zero additional infrastructure.

The `deploy_platform.py` script generates fresh secrets on every cluster creation, so there is no persistent secret state to protect across cluster lifecycles. This makes the ephemeral nature of Kind clusters an advantage rather than a limitation — secrets are naturally rotated on every deployment.

**Key Factors:**

1. **Native to Kubernetes (R5, R6):** No additional software to install, configure, or maintain. Kubernetes Secrets are a core API resource available in every cluster, including Kind.

2. **Programmatic creation (R4, R7):** `deploy_platform.py` uses `kubectl create secret generic` to generate secrets during cluster setup. Each service receives a dedicated Secret object containing only its required credentials.

3. **Least-privilege mounting (R2):** Each Deployment manifest references only the specific Secret keys required by that service via `env.valueFrom.secretKeyRef`. The auth-service receives JWT keys; the voting-service receives database credentials and encryption keys; the results-service receives only read-only database credentials.

4. **Zero infrastructure overhead (C2, C3):** Unlike Vault (256–512MB) or Sealed Secrets (additional controller pod), native Secrets consume no additional cluster resources.

5. **Sufficient for threat model (C5):** The local Kind cluster is not exposed to external networks. The threat model focuses on preventing accidental secret leakage to Git, not defending against etcd compromise or insider attacks.

---

## Consequences

### Positive Consequences

- **Simplicity:** Secret management adds zero operational overhead to the development workflow. Developers run `deploy_platform.py` and secrets are provisioned automatically.
- **Automation:** Fresh secrets are generated on every cluster creation, providing natural rotation without explicit rotation mechanisms.
- **Portability:** Kubernetes Secrets are a standard API — the approach works identically on any Kubernetes distribution (Kind, EKS, GKE, AKS).
- **No vendor lock-in:** Migrating to Vault or Sealed Secrets in Stage 2 requires only changing how secrets are created, not how they are consumed (pods still read environment variables).

### Negative Consequences

- **Not encrypted at rest:** Secrets are base64-encoded in etcd, not encrypted. An attacker with etcd access can decode all secrets. Mitigated by the local-only threat model.
- **No audit logging:** Kubernetes does not log secret reads by default. Cannot determine which pods accessed which secrets. Acceptable for a single-developer project.
- **No automatic rotation:** Secrets do not expire or rotate automatically. Mitigated by ephemeral cluster lifecycle (fresh secrets on every `deploy_platform.py` run).
- **Cluster-admin visibility:** Anyone with `kubectl` access to the namespace can read secrets in plaintext via `kubectl get secret -o yaml`. Acceptable for a single-developer project.

### Trade-offs Accepted

- **Security vs Simplicity:** Accepted base64 encoding (not encryption) in exchange for zero additional infrastructure. The local Kind cluster threat model does not warrant the operational cost of Vault.
- **Features vs Overhead:** Accepted the absence of audit logging, dynamic secrets, and automatic rotation in exchange for a solution that requires no additional components, configuration, or maintenance.
- **Current vs Future:** Accepted a solution that is sufficient for Stage 1 (local development) with a clear migration path to Vault for Stage 2 (production).

---

## Implementation Notes

### Technical Details

Secrets are created by `deploy_platform.py` during cluster bootstrapping using `kubectl create secret generic`:

```bash
# Database credentials for each service
kubectl create secret generic auth-db-secret \
  --from-literal=DB_USER=auth_user \
  --from-literal=DB_PASSWORD=$(openssl rand -hex 16) \
  --from-literal=DB_NAME=uvote \
  --from-literal=DB_HOST=postgres-service \
  -n uvote

# JWT signing key for auth-service
kubectl create secret generic jwt-secret \
  --from-literal=JWT_SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=JWT_ALGORITHM=HS256 \
  -n uvote

# Encryption key for voting-service
kubectl create secret generic voting-encryption-secret \
  --from-literal=ENCRYPTION_KEY=$(openssl rand -hex 32) \
  -n uvote
```

### Configuration

Secrets are consumed in Deployment manifests via `envFrom` or individual `env` references:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
spec:
  template:
    spec:
      containers:
      - name: auth-service
        env:
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: auth-db-secret
              key: DB_USER
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: auth-db-secret
              key: DB_PASSWORD
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: jwt-secret
              key: JWT_SECRET_KEY
```

### Integration Points

- **deploy_platform.py:** Creates all Secret objects during cluster setup, before deploying application pods
- **Deployment manifests:** Reference secrets via `secretKeyRef` in `env` blocks
- **Application code:** Reads secrets from environment variables via `os.environ` — no Kubernetes-specific code
- **Network Policies:** Secrets are namespace-scoped; network policies provide an additional layer of isolation between services

---

## Validation

### Success Criteria

- [x] No secrets appear in Git history, source code, or Docker image layers
- [x] Each service receives only its required secrets (least-privilege)
- [x] Secrets are created automatically by `deploy_platform.py`
- [x] Services start successfully and authenticate with their provisioned credentials
- [x] Secret rotation works by destroying and recreating the cluster
- [x] Migration path to Vault is documented for Stage 2

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Secrets in Git history | 0 | 0 |
| Setup time overhead | <5s | ~2s |
| Additional RAM usage | 0MB | 0MB |
| Additional pods | 0 | 0 |
| Services authenticating correctly | 6/6 | 6/6 |

### Review Date

Start of Stage 2 (February 2026) — evaluate migration to HashiCorp Vault for production deployment.

---

## References

- [Kubernetes Secrets Documentation](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Kubernetes RBAC for Secrets](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [HashiCorp Vault on Kubernetes](https://developer.hashicorp.com/vault/docs/platform/k8s)
- [Bitnami Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [ADR-001](ADR-001-python-fastapi-backend.md) — Backend framework (environment variable consumption)
- [ADR-002](ADR-002-postgresql-database.md) — Database choice (credentials managed as secrets)
- [ADR-012](ADR-012-kind-local-development.md) — Kind cluster (ephemeral lifecycle)

## Notes

The migration to HashiCorp Vault in Stage 2 will require: (1) deploying Vault server pods, (2) configuring Kubernetes auth backend, (3) writing Vault policies for each service, and (4) adding Vault Agent Injector annotations to Deployment manifests. Application code will not change — secrets will still be consumed as environment variables. The Vault migration path was validated during Week 6 prototyping by running a single-node Vault dev server alongside the Kind cluster.
