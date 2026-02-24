## Secure Voting System — Platform Report (Expanded)

Author: [Your Name]
Date: 24 February 2026

Purpose: This document is the primary "platform" deliverable required by the assessment (Weight: 25%). It documents source control, repository structure, pipeline design, testing automation, release and deployment processes, environment definitions (servers, storage, network, security), resource requirements and migration strategy.

---

## 1. Source control strategy

1.1 Branching model

- `main` (protected): production-ready artifacts; releases and tags are pushed here.
- `develop` (integration): CI merges and integration tests occur here before release.
- Feature branches: `feature/<name>` for new work. Pull Requests (PRs) required with at least one reviewer.
- Hotfix branches: `hotfix/<id>` for emergency fixes, merged to `main` and `develop`.

1.2 Commit and PR policy

- Signed commits recommended; conventional commits format encouraged (feat/fix/docs/chore).
- PR template includes checklist: tests, lint, security scan, migration notes, ADR references.

1.3 Repository organization

Top-level structure (selected):

```
/
  README.md
  docker-compose.yml
  database/init.sql
  docs/
  auth-service/
  election-service/
  voting-service/
  frontend-service/
  results-service/
  shared/
  samples/sample-voters.csv
```

- Each service is its own folder with Dockerfile, requirements.txt and tests/ directory. Shared code in `shared/` is published as a local package and pinned in each service requirements.

1.4 Registries & artefacts

- Container registry: use GitHub Container Registry or Docker Hub. CI pipeline builds images and pushes tags `ghcr.io/<org>/secure-vote/<service>:<version>`.
- Images for Kind local runs are loaded via `kind load docker-image` in the CI deploy step or `imagePullPolicy: Never` for local development.

## 2. Pipeline design (CI/CD)

2.1 Goals

- Automate builds, tests, linting and security scans on PRs
- Produce signed, versioned container images on merge
- Deploy to staging (Kind or cloud dev cluster) automatically on merge to `develop`
- Manual gated deploy to production from `main` with approvals

2.2 Stages (GitHub Actions example)

1) PR / push pipeline (on feature branches)
- Steps: checkout, python setup, dependency install (pip), flake8/black, unit tests, static security scans (bandit), build test Docker image (local), run small integration tests using ephemeral Postgres container

2) Merge to develop (integration)
- Steps: run matrix builds for each service in parallel, build & push `:staging` images, run full integration tests against Kind cluster, run e2e script, if green notify Slack

3) Release (main)
- Steps: tag release, build images with semver tag, push to registry, create GitHub release notes, trigger production deploy workflow (manual approval required)

4) Deploy workflows
- Staging: automatic on `develop` — deploy via `kubectl apply` or Helm chart to Kind/Dev cluster
- Production: manual approval step, then deploy to cloud K8s (GKE/EKS/AKS) via GitHub Action with kubeconfig stored in secrets

2.3 Example GitHub Actions matrix (conceptual)

YAML: build-test matrix that runs services in parallel and aggregates results (stored in artifacts). See `ci/workflows/` (to be added) for concrete YAMLs.

2.4 Secrets in CI

- Pipeline uses repository secrets for registry credentials, K8s kubeconfig, and production KMS credentials (never in code). For extra security, use GitHub Actions environment protection and required reviewers.

## 3. Testing strategy and automation

3.1 Test pyramid

- Unit tests (fast): run in PR pipeline (pytest)
- Integration tests: run against ephemeral Postgres in CI or ephemeral Kind cluster
- E2E tests: run in staging cluster using Playwright or selenium-like flows for UI and `httpx` scripts for API flows
- Load tests: scheduled runs or manual triggers using `wrk` / `locust` for capacity planning

3.2 Test harness and fixtures

- Use `pytest` and `pytest-asyncio` for async tests. Provide fixtures for local DB as test containers (testcontainers-python) or in-memory test databases.

3.3 Automation details

- Tests must run in isolated containers with deterministic seeds for token generation when needed. Use environment variable `TEST_MODE=true` to enable test-only behaviours (shorter token expiry etc.).

## 4. Release and deployment processes

4.1 Build artifacts

- Container images for each service: include small base image (python:3.11-slim), pinned requirements.txt, pre-compiled Pydantic models where possible.

4.2 Tagging and semantic versioning

- Use semantic versioning: `<major>.<minor>.<patch>`.
- On release: tag Git commit, build images with tag and `latest`, push to registry, attach release notes.

4.3 Deployment strategies

- Staging: Rolling updates with zero-downtime (k8s Deployment with `maxUnavailable: 0`, `maxSurge: 1`)
- Production: Canary or blue-green recommended for real elections — for MVP we provide rolling updates and recommend canary via Argo Rollouts in production.

4.4 Database migrations

- Use Alembic for schema migrations. Migration steps are applied in a controlled job in the pipeline before application deployment. Migrations must be backward-compatible or use two-step deploys (expand/contract pattern).

4.5 Rollback strategy

- Application rollback: revert Deployment to previous ReplicaSet via `kubectl rollout undo` and monitor health checks.
- DB rollback: avoid destructive down migrations; if necessary, follow documented archive-and-restore procedure.

## 5. Environments (servers, storage, network, security)

5.1 Local dev

- Developer machine (macOS with zsh) runs Docker Desktop and Kind. Use `docker compose up --build` for quick runs.

5.2 Staging (cloud or local K8s)

- Kind cluster or small cloud K8s cluster with 3 nodes (control-plane + 2 workers). Managed Postgres (if cloud) or StatefulSet with PVC.

5.3 Production (recommended)

- Cloud-managed Kubernetes (GKE/EKS/AKS) using multiple availability zones, managed Postgres (RDS/CloudSQL) with read replicas, object storage for backups (S3/GCS).

5.4 Storage and volumes

- Postgres: provisioned IOPS SSD volumes, nightly backups to object store.
- Logs: centralised logging (ELK/Cloud Logging) — forward stdout from pods via Fluentd or sidecar.

5.5 Network & security

- Ingress via managed LB with TLS termination (Let's Encrypt or managed certs)
- Calico NetworkPolicies deny-by-default; only allowed service-to-service flows permitted
- Pod security contexts: non-root, no privilege escalation

## 6. Resource requirements and sizing

6.1 Development machine (minimum)

- 16GB RAM, 4 cores, 50GB disk — sufficient for Kind with small clusters for local testing.

6.2 Staging cluster minimal (3-node)

- Node size: e.g., 2 vCPU, 8GB RAM per worker; 3 nodes provide basic HA. Postgres as managed RDS instance (db.t3.medium or equivalent) with 50GB SSD.

6.3 Production sizing (example estimate for 10k voters)

- API services: horizontally scaled with autoscaling; baseline 3 replicas per service (pod requests: 250m CPU, 512Mi RAM)
- Postgres primary: 4 vCPU, 16GB RAM (provisioned IOPS) — with read replicas for analytics
- Ingress/Load balancer: autoscaling, TLS termination

6.4 Capacity planning notes

- Connection pool sizing: limit total DB connections = (max_pods * pool_size) < Postgres max_connections. Use PgBouncer if needed.

## 7. Migration strategy

7.1 From dev -> staging -> prod

- Promote images via tags (`:staging` -> `:prod`) rather than rebuilding for prod; ensures identical artefacts across environments.

7.2 DB migrations

- Use Alembic migrations. Migrations scheduled in pipeline before app deploy. For backwards-incompatible schema changes, use expand/contract pattern: add new column → write app code writing both old and new → backfill data → switch reads to new column → remove old column in a safe window.

7.3 Secrets migration and rotation

- Use KMS to create and rotate keys. For secrets stored in K8s, use sealed-secrets or external KMS provider in production.

7.4 Rollout for production election data

- Deploy in a maintenance window; snapshot DB before opening an election. Provide a manual runbook for restore and rollback.

## 8. Observability and incident response

8.1 Health & metrics

- `/health` and `/metrics` endpoints for each service. Prometheus scrapes metrics; Grafana dashboards for latency and token issuance rates.

8.2 Logging

- Structured JSON logs to stdout; Fluentd collector forwards to ELK/Cloud Logging. Audit logs stored immutably in Postgres and exported to object storage periodically.

8.3 Alerting

- Alerts on increased 5xx rate, DB replica lag > threshold, token validation failure spikes.

8.4 Runbook

- Provide documented runbooks for common incidents: DB failover, cluster node failure, mass-mail failure, Cron job failure.

## 9. Security & compliance operations

- Regular dependency vulnerability scanning (GitHub Dependabot or Snyk)
- Container image signing and SBOM generation
- Regular backups and DR tests

## 10. Appendix: Example GitHub Actions (sketch)

1) `ci/build-and-test.yml` (PR workflow) — runs unit tests and linters
2) `ci/integration-deploy.yml` — builds, pushes staging images and deploys to Kind
3) `ci/release.yml` — tag-based release workflow for production

Detailed YAMLs to be added to `ci/workflows/` with secrets and environment constraints.

## 11. Next steps & deliverables for assessment

- Produce Word (.docx) versions of Product and Platform reports and place under `docs/word/`.
- Add CI workflows to `ci/workflows/` and a small demo pipeline for assessors to run.
- Provide runbook PDFs and a short demo video showing the token workflow end-to-end (optional but recommended).

---

End of Platform Report (Expanded)
