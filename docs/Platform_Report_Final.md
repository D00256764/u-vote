# Platform Report — U-Vote (Final)

Project: U-Vote — Secure Online Voting Platform
Author: D00255656
Date: February 2026

## Executive summary

This Platform Report is the assessor-facing artefact describing the operational design and infrastructure for U-Vote. It includes the local Kubernetes proof-of-concept (Kind + Calico), network policy architecture, database platform, CI/CD plan (design only — no implementation in repo), observability, backup/disaster recovery plans, and an operational runbook. The report references ADRs and the investigation log to explain decisions.

## Contents
- 1 Platform architecture overview
- 2 Cluster design and configuration (Kind + Calico)
- 3 Network security (policy mapping & verification)
- 4 Database platform & operational considerations
- 5 CI/CD plan (design only; jobs, triggers, artifact storage)
- 6 Secrets and key management
- 7 Observability, logging and metrics
- 8 Disaster recovery and backup strategy
- 9 Resource sizing, capacity & scaling
- 10 Operational runbook and maintenance tasks
- 11 Appendices (ADRs, manifests, test evidence)

---

## 1 Platform architecture overview

- Kubernetes (Kind used for local development). Key Kind config: `disableDefaultCNI: true`, `podSubnet: 192.168.0.0/16` to allow Calico installation.
- Calico v3.26.1 provides full NetworkPolicy enforcement (ingress & egress) and IPAM.
- Nginx Ingress Controller provides TLS termination and path-based routing.
- PostgreSQL 15 runs as a single authoritative instance for Stage 1, using a PVC-backed volume. Per-service DB users and triggers enforce data integrity.

References: ADR-003 (Kubernetes), ADR-004 (Calico), ADR-002 (PostgreSQL).

## 2 Cluster design and configuration

Kind cluster topology (development):
- 1 control-plane node (uvote-control-plane) — API server, scheduler
- 2 worker nodes (uvote-worker, uvote-worker2) — application pods

Kind configuration snippet (illustrative):
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
  podSubnet: "192.168.0.0/16"
nodes:
- role: control-plane
- role: worker
- role: worker
```

Calico installation notes:
- Install calico manifests per ADR-004. Wait for `calico-node` DaemonSet and `calico-kube-controllers` Deployment to be Ready before applying policies.
- Verify with `kubectl -n kube-system get pods | grep calico` and `calicoctl` policy inspection if available.

Ingress and external access:
- Host ports 80/443 mapped to control-plane for ingress-nginx NodePort/LoadBalancer emulation. Use TLS in production; in dev TLS may be simplified.

## 3 Network security — policy mapping & verification

Summary: Zero-trust model using 12 NetworkPolicy resources across five YAML files (00–04). See `docs/Platform_Network_Addendum.md` for the full mapping, policy YAML references and the 36 test cases executed with PASS results.

Key operational practices:
- Apply policies in order: default deny → DNS allow → DB access → Ingress allow → Audit allow. The `policy-order` labels in each manifest enforce human-friendly ordering.
- Maintain label hygiene: service `app:` labels must match selectors used in policies.
- Use `calicoctl` to troubleshoot policy hits and endpoint status in development.

Verification checklist (post-deploy):
- Confirm default-deny blocks inter-pod traffic when alone.
- Apply DNS policy and confirm CoreDNS resolution works from pods.
- Apply DB policies and confirm only six services can connect to PostgreSQL.
- Apply ingress policies and confirm ingress-nginx can reach the six exposed services.
- Run network test suite (example commands in `docs/Platform_Network_Addendum.md`).

## 4 Database platform & operational considerations

PostgreSQL configuration (Stage 1):
- PostgreSQL 15 running in-cluster with PVC (1Gi minimum for dev).
- Extensions: `pgcrypto` for in-DB encryption and hash functions.
- Connection pooling via `asyncpg` with min=2, max=20 (tune for load).

Security and role management:
- Six dedicated DB users (auth_service, voting_service, election_service, results_service, audit_service, admin_service) with precise GRANTs.
- Immutable `votes` table enforced by BEFORE UPDATE/DELETE trigger.
- Audit log triggers to prevent modification of `audit_logs`.

Backup and restore strategy (Stage 1 — dev):
- Scheduled `pg_dump` of critical tables nightly to an off-host location (e.g., local backup directory or cloud storage when available).
- For production: configure WAL archiving and point-in-time recovery (PITR).

Operational run steps for DB upgrade/migration:
- Use migration tool (Alembic recommended for Stage 2) for DDL changes; pre-flight scripts to validate existing data and new schema.

## 5 CI/CD plan (design only)

Goal: Provide a secure, reproducible pipeline for building, testing and deploying microservices across environments (dev → staging → prod). This is a design and plan only — no workflow implementation is included in the repo per instructions.

Pipeline stages (recommended):

1) Pull Request (PR) validation — triggered on PR to `develop`/`main`:
	- Jobs: lint (ruff/flake8), unit tests (pytest), typecheck (mypy optional), security static analysis (bandit), dependency scan (safety).
	- Artifacts: test reports, coverage reports uploaded to artifact storage.

2) Build & CI image (on merge to `develop`):
	- Jobs: build container image for changed services (use path-filtering), run integration tests in ephemeral Kind cluster (lightweight), run contract tests (OpenAPI validator), produce versioned image tags (e.g., `ghcr.io/<org>/service:sha-<short>`).
	- Artifacts: built images (pushed to registry), test reports.

3) Staging deployment (manual or automatic on successful CI):
	- Jobs: deploy manifests to staging namespace (apply k8s manifests or use Helm), run smoke tests and end-to-end tests, perform performance sanity checks.

4) Production promotion (manual approval required):
	- Jobs: tag images for production, apply manifests to production namespace, run post-deploy smoke tests, enable monitoring alarms.

Security considerations for CI/CD:
- Store secrets (registry credentials, DB credentials) in the chosen secrets manager (GitHub Secrets for CI, or Vault for production). Use short-lived tokens where possible.
- Sign container images (cosign) and verify signatures in the cluster image policy admission.
- Enforce least-privilege for CI runners (no persistent cluster credentials in pipeline; use ephemeral service accounts with limited scopes).

Required infrastructure and integrations:
- Container registry (GitHub Container Registry or private registry)
- Artifact storage for test reports and docx if required
- CI runner privileges scoped by role (deployment service account tokens)
- Optionally: ArgoCD or Flux for GitOps-driven continuous deployment in production

Example CI job matrix (PR validation):
- Lint & format
- Unit tests (matrix: python 3.11)
- Security scan

Rollout strategy:
- Use Kubernetes rolling updates and readiness probes to ensure zero-downtime deploys.
- Implement health checks (`/health`) and use pre-stop hooks to drain connections gracefully.

Promotion gating:
- Require successful integration tests and manual approval for production entry.

Auditability:
- All pipeline runs linked to commits and PRs; store signed provenance metadata with images.

### 5.1 Release policy, versioning and container registry

Release policy and semantic versioning:
- Adopt semantic versioning (MAJOR.MINOR.PATCH) for service releases. CI produces build metadata including commit SHA and a timestamped tag (e.g., `v1.2.3+sha.ab12cd`).
- Release channels: `canary` (optional automated quick deploy to staging), `staging` (integration verification), `production` (manual promotion).

Container registry and image provenance:
- Use a secured container registry (GitHub Container Registry / GHCR or private registry). Images are pushed with the tag schema: `ghcr.io/<org>/<service>:v<MAJOR.MINOR.PATCH>-sha-<short>`.
- Sign images with `cosign` and store the signatures alongside images. Configure an image policy admission controller (e.g., Cosign Kritis or in-cluster ImagePolicy) to verify signatures before pulling into production.

Artifacts storage:
- CI stores build artifacts (test reports, coverage, documentation `.docx`) in ephemeral artifact storage attached to the CI provider. Long-term retention should use an S3-compatible blob store if required for evidence retention.

### 5.2 Promotion & branching policy

Branching model:
- `main` — production-ready branch; protected; direct pushes disabled.
- `develop` — integration branch for merged features; CI builds and deploys to `staging`.
- `feature/*` — short-lived feature branches created per ticket, merged to `develop` by PR.

Promotion policy:
- Pull request -> `develop`: PR validation (lint, unit tests) required.
- Merge `develop` -> `main`: requires passing integration tests and manual approval (production deployment trigger). Releases are tagged on `main` and images are promoted by retagging signed images.

Feature flags:
- Use lightweight feature flagging (unleash/config flags) for controlled rollouts; flags stored in a central configuration and evaluated in service startup or per-request.


## 6 Secrets & key management

Stage 1 (current): Kubernetes Secrets for DB credentials and app keys. Secrets are base64-encoded and stored in cluster; access limited to pods via RBAC and namespace scoping.

Stage 2 (recommended production): Use a dedicated secrets manager (HashiCorp Vault or cloud KMS) and integrate using Kubernetes CSI driver or External Secrets operator to inject secrets dynamically and enable rotation.

Key rotation strategy:
- Rotate DB user passwords on a scheduled cadence; update Secret and perform controlled restart of the affected pods.
- Use short-lived tokens for CI and service accounts.

## 6.1 Environments: storage, node structure, network policy and security

Environment definitions and separation:
- Dev (Kind local): single-cluster local developer environment. Lightweight storage (hostPath or local PV), no external SLA. NetworkPolicies present but may be permissive for developer convenience.
- Staging: cloud/VM-backed cluster that mirrors production configuration (Calico, ingress, monitoring). Use separate namespaces for services and separate DB instance to avoid production contamination.
- Production: hardened cluster(s) with strict network policies, private container registry access, and centralized secrets manager.

Storage policy:
- Dev: PVCs with small capacities (1Gi) and hostPath optional. Backups optional.
- Staging/Prod: use cloud/block storage with encryption at rest enabled. Backups stored off-cluster in an S3-compatible store with lifecycle policies.

Node structure and workload assignment:
- Control plane nodes separated from worker nodes. Worker node pools for system workloads (monitoring, logging) and application workloads.
- Dedicated DB node pool recommended for production: isolate storage I/O heavy workloads.

Network & firewall policy:
- Ingress firewall: only ports 80/443 publicly reachable; all other ports blocked at the cloud provider level.
- Egress firewall: restrict outbound traffic from application pods to whitelisted endpoints (e.g., mail provider IP ranges, external auth providers). Use Calico egress policies for enforcement.

Resource requirements and workload assignment:
- Assign resource requests/limits per deployment (see §9). Stateful workloads (Postgres) pinned to dedicated node pool. Stateless services placed on autoscaling pool.


## 7 Observability, logging and metrics

Planned observability stack (Stage 2):
- Metrics: Prometheus scraping application exporters and kube-state metrics.
- Dashboards: Grafana with dashboards for request latency, vote throughput, token consumption rate, pod health.
- Logs: Loki (or ELK) for log aggregation; all services log to stdout/stderr in structured JSON.
- Tracing: OpenTelemetry instrumentation for critical flows (vote submission path).

Operational alerts:
- Configure alerts for high error rate on voting endpoints, DB connection saturation, audit verification failures, and CPU/memory saturation.

## 7.1 Deployment strategies, database splitting and user migration

Deployment strategies:
- Blue/Green: maintain parallel production environments (blue/green) and switch traffic at the ingress to minimize downtime for major changes.
- Rolling updates: default strategy with readiness and liveness probes for minor releases.

Database strategies (split & migration):
- Single logical database (current Stage 1) with per-service roles for least privilege.
- For larger scale or multi-tenant requirements, consider splitting into:
	- Primary write DB for votes and audit logs (high integrity, append-only)
	- Read-replicas or separate analytics DB for heavy-read workloads and reporting
	- Separate metadata DB for administration and user profiles (isolates heavy writes/updates from vote path)

User migration and schema changes:
- Online migrations: use backward-compatible DDL patterns (additive changes, columns with defaults). Deploy code that can work with both old and new schemas, then run a migration job to populate new fields, and finally remove legacy code.
- Batching & throttling: run migration tasks using Kubernetes Jobs with controlled concurrency to avoid overloading DB.


## 8 Disaster recovery & backups

Backup policy (production recommendation):
- Full backups daily; WAL archiving enabled for PITR. Backup retention policy aligned with legal and regulatory requirements.

Restore exercises:
- Documented restore procedure: provision a new DB pod with restored PV, run schema migrations, run integrity checks (hash chain verification) before promoting DB.

## 9 Resource sizing, capacity & scaling

Development (Kind): fits on 16GB host with modest limits per pod. Production sizing recommendations (rough starting points):
- Auth service: 0.5–1 vCPU, 512–1024 MiB RAM
- Voting service: scale horizontally under load; 1–2 vCPU per replica, 1–2 GiB RAM
- PostgreSQL: dedicated node with 4+ vCPU and 8–16 GiB RAM for modest workloads; use managed DB for production scale

Use HorizontalPodAutoscaler (HPA) based on CPU and custom metrics (request queue length or latency) for critical services.

## 9.1 Testing strategy (unit, API, system, security, performance)

Test environment and coverage:
- Unit tests: run in CI on PRs for each service; cover business logic and validators.
- API (integration) tests: run in ephemeral Kind cluster created by CI or in the staging cluster; include OpenAPI contract validation.
- System / E2E tests: run against staging with real-like data; tests include CSV import, token generation, vote casting, and result aggregation.
- Security tests: static analysis (bandit), dependency scanning (safety), and runtime checks for injection/fuzzing. Network policy tests executed as part of staging verification.
- Non-functional tests: performance/load tests (k6 or locust) executed in an isolated performance environment with mirrored dataset sizes for calibration.

Test data and fixtures:
- Use synthetic voters and elections datasets for load tests. Mask any real PII. Use fixtures stored in `tests/fixtures/` and generated via reproducible scripts.

Test promotion gating:
- A deployment to staging requires passing unit and integration tests; production promotion requires passing E2E and performance smoke tests plus manual approval.


## 10 Operational runbook and maintenance tasks

Daily checks:
- Verify all pods are Ready and no CrashLoopBackOffs
- Confirm Calico pod health and `calicoctl` shows expected endpoints
- Check DB replication and backup job completion (dev backups)

Incident response (high-level):
1. Triage: identify root cause using logs/metrics.
2. Isolate: cordon/drain affected nodes if necessary.
3. Remediate: roll back deployment or scale pods.
4. Recover: restore from backup if data corruption.
5. Post-mortem: capture lessons and update runbook.

## 11 Appendices

- ADR excerpts (ADR-001 to ADR-004) and references to the Investigation Log
- Full NetworkPolicy manifests located in `deploy/networkpolicies/` (or `docs/NETWORK-SECURITY.md`)
- Test evidence summary (network policy tests, integration tests)

---

End of Platform Report (this file). The CI/CD plan is intentionally a design document; no implementation is included in the repository per submission instructions. For conversion instructions see `docs/Conversion_Instructions.md`.
