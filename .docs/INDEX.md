# U-Vote Documentation Index

**Project:** U-Vote — Secure Online Voting System
**Student:** D00255656 — BSc (Hons) Computing Systems and Operations, Year 4
**Module:** PROJ I8009 — Project (10 Credits)
**Institution:** Dundalk Institute of Technology (DkIT)
**Stage:** Stage 1 — Design, Prototyping & Platform Deployment (30%)
**Last Updated:** 2026-02-16

---

## 1. Documentation Map

### 1.1 Overview

The U-Vote project documentation is organised into seven primary documents and fifteen Architecture Decision Records (ADRs), totalling approximately **107,000 words** across **17,500+ lines** of technical documentation. Together, they provide a complete record of the project's design rationale, architectural decisions, platform implementation, security controls, and development process.

```
                        ┌──────────────────────────┐
                        │       INDEX.md           │
                        │    (You are here)        │
                        └────────────┬─────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            │                        │                        │
   ┌────────▼────────┐    ┌─────────▼─────────┐    ┌────────▼────────┐
   │   DESIGN &      │    │   PLATFORM &      │    │   PROCESS &     │
   │   DECISIONS     │    │   SECURITY        │    │   EVIDENCE      │
   └────────┬────────┘    └─────────┬─────────┘    └────────┬────────┘
            │                       │                        │
   ┌────────▼────────┐    ┌────────▼─────────┐    ┌────────▼────────┐
   │ ARCHITECTURE.MD │    │   PLATFORM.MD    │    │  BUILD-LOG.md   │
   │ (Application)   │    │ (Infrastructure) │    │ (Dev Journal)   │
   └────────┬────────┘    └────────┬─────────┘    └────────┬────────┘
            │                      │                        │
   ┌────────▼────────┐    ┌────────▼─────────┐    ┌────────▼────────────┐
   │  ADR-INDEX.md   │    │ NETWORK-SECURITY │    │ INVESTIGATION-LOG   │
   │  (15 ADRs)      │    │ .md (Summary)    │    │ .md (Research)      │
   └─────────────────┘    └────────┬─────────┘    └─────────────────────┘
                                   │
                          ┌────────▼─────────────┐
                          │ NETWORK-SECURITY-    │
                          │ COMPREHENSIVE.md     │
                          │ (Full Analysis)      │
                          └──────────────────────┘
```

### 1.2 Document Relationships

| Document | Depends On | Referenced By |
|----------|-----------|---------------|
| **ARCHITECTURE.MD** | — (foundational) | PLATFORM.MD, NETWORK-SECURITY.md, all ADRs, BUILD-LOG.md |
| **PLATFORM.MD** | ARCHITECTURE.MD | NETWORK-SECURITY.md, NETWORK-SECURITY-COMPREHENSIVE.md, BUILD-LOG.md |
| **NETWORK-SECURITY.md** | PLATFORM.MD, ARCHITECTURE.MD | NETWORK-SECURITY-COMPREHENSIVE.md |
| **NETWORK-SECURITY-COMPREHENSIVE.md** | All of the above | — (standalone comprehensive reference) |
| **INVESTIGATION-LOG.md** | — (standalone research) | ADRs, BUILD-LOG.md |
| **BUILD-LOG.md** | All above (chronicles their creation) | — (standalone process record) |
| **ADR-INDEX.md** | ARCHITECTURE.MD, INVESTIGATION-LOG.md | PLATFORM.MD, NETWORK-SECURITY.md |

### 1.3 What to Read First

Start with **ARCHITECTURE.MD** — it provides the application-level overview including services, data models, and security measures. From there, **PLATFORM.MD** covers the infrastructure that runs the application. The remaining documents provide depth in specific areas.

### 1.4 Reading Paths

#### For the Project Evaluator / Examiner

A structured path through the documentation that demonstrates the full scope of work and academic rigour:

| Order | Document | Why | Time |
|-------|----------|-----|------|
| 1 | **INDEX.md** (this file) | Orientation — understand what exists and how it connects | 5 min |
| 2 | **INVESTIGATION-LOG.md** | Evidence of research process — technology evaluation, trade-off analysis | 20 min |
| 3 | **ADR-INDEX.md** → key ADRs | Formal decision records — demonstrates structured decision-making | 15 min |
| 4 | **ARCHITECTURE.MD** | Application design — services, data flow, security model | 15 min |
| 5 | **PLATFORM.MD** | Infrastructure design — Kubernetes, networking, deployment, observability | 30 min |
| 6 | **NETWORK-SECURITY.md** | Network security summary — zero-trust model, policies, testing | 15 min |
| 7 | **BUILD-LOG.md** | Development process — weekly progress, decisions made, metrics | 20 min |
| 8 | **NETWORK-SECURITY-COMPREHENSIVE.md** | Deep reference (skim) — threat model, compliance, full policy analysis | 15 min (skim) |

**Estimated total reading time:** ~2.5 hours for full review, ~1 hour for highlights.

#### For a Technical Reviewer / DevOps Engineer

Focus on implementation details:

| Order | Document | Focus Sections |
|-------|----------|---------------|
| 1 | **PLATFORM.MD** | Cluster architecture, deployment strategy, CI/CD pipeline design |
| 2 | **NETWORK-SECURITY-COMPREHENSIVE.md** | Network policies (Section 4), threat model (Section 7), testing (Section 8) |
| 3 | **ARCHITECTURE.MD** | Service descriptions, database schema, API endpoints |
| 4 | ADR-003, ADR-004, ADR-010, ADR-014 | Key infrastructure decisions — Kubernetes, Calico, zero-trust, DB users |

#### For a Future Developer / Maintainer

Understand how to work with and extend the system:

| Order | Document | Focus Sections |
|-------|----------|---------------|
| 1 | **ARCHITECTURE.MD** | Full document — service ports, data flow, voting process |
| 2 | **PLATFORM.MD** | Quick Start, deployment scripts, environment variables, troubleshooting |
| 3 | **NETWORK-SECURITY.md** | Section 11 (Operational Considerations) — adding services, troubleshooting |
| 4 | **ADR-INDEX.md** | All ADRs — understand why decisions were made before changing them |

#### For a Security Auditor

| Order | Document | Focus Sections |
|-------|----------|---------------|
| 1 | **NETWORK-SECURITY-COMPREHENSIVE.md** | Full document — policies, threat model, compliance, testing |
| 2 | **PLATFORM.MD** | Section 9 (Security Architecture) |
| 3 | **ARCHITECTURE.MD** | Database permissions, audit service, security measures |
| 4 | ADR-005, ADR-006, ADR-007, ADR-010, ADR-015 | Security-related decisions |

---

## 2. Document Status Matrix

| # | Document | Type | Lines | Words | Status | Last Updated | Completeness |
|---|----------|------|------:|------:|--------|--------------|:------------:|
| 1 | [ARCHITECTURE.MD](ARCHITECTURE.MD) | Application Design | 1,354 | 4,592 | Complete | 2026-02-15 | 100% |
| 2 | [PLATFORM.MD](PLATFORM.MD) | Infrastructure Design | 3,046 | 14,898 | Complete | 2026-02-16 | 100% |
| 3 | [NETWORK-SECURITY.md](NETWORK-SECURITY.md) | Security Summary | 828 | 6,535 | Complete | 2026-02-15 | 100% |
| 4 | [NETWORK-SECURITY-COMPREHENSIVE.md](NETWORK-SECURITY-COMPREHENSIVE.md) | Security Deep Dive | 5,845 | 39,290 | Complete | 2026-02-16 | 100% |
| 5 | [INVESTIGATION-LOG.md](INVESTIGATION-LOG.md) | Research Evidence | 2,027 | 13,985 | Complete | 2026-02-16 | 100% |
| 6 | [BUILD-LOG.md](BUILD-LOG.md) | Development Journal | 2,641 | 15,567 | Complete | 2026-02-16 | 100% |
| 7 | [decisions/ADR-INDEX.md](decisions/ADR-INDEX.md) | Decision Index | 64 | 421 | Complete | 2026-02-16 | 100% |
| 8 | [decisions/ADR-001 through ADR-015](decisions/) | Decision Records | 4,038 | 25,330 | Complete | 2026-02-16 | 100% |

**Totals:** ~19,843 lines / ~120,618 words across all markdown documentation.

### Document Descriptions

| Document | Purpose |
|----------|---------|
| **ARCHITECTURE.MD** | Defines the application-level architecture: microservice descriptions, ports, API endpoints, data models, voting flow, database schema, service interactions, and security measures. The foundational design document. |
| **PLATFORM.MD** | Comprehensive infrastructure specification: Kubernetes cluster architecture (Kind, 3 nodes), Calico CNI, namespace strategy, database platform (PostgreSQL 15), CI/CD pipeline design, environment strategy, deployment automation, observability, security architecture, operational procedures, SLOs, scalability, disaster recovery, and IaC approach. |
| **NETWORK-SECURITY.md** | Focused network security document covering the zero-trust model, all 12 NetworkPolicy resources, service communication matrix, testing results, security analysis, defence in depth, and operational considerations. Concise reference for the network security implementation. |
| **NETWORK-SECURITY-COMPREHENSIVE.md** | Exhaustive network security analysis: executive summary, defence-in-depth strategy, security zones, Calico architecture, complete policy-by-policy analysis with full YAML, per-service security analysis, database security (SQL grants, triggers), STRIDE threat model (15 threats + compromised service scenarios), compliance mapping (CIS, OWASP, NIST), operational security, and future enhancements. |
| **INVESTIGATION-LOG.md** | Evidence of the design decision process: requirements analysis, technology investigation (comparing alternatives), architecture pattern evaluation, security approach research, prototyping process, risk analysis, and trade-offs accepted. Demonstrates academic rigour in decision-making. |
| **BUILD-LOG.md** | Week-by-week development journal: project timeline, development methodology, detailed entries for each sprint (decisions, implementation, challenges, outcomes), cumulative metrics, technical debt log, and learning journey. |
| **ADR-INDEX.md** | Master index of all 15 Architecture Decision Records with status, date, and category. |
| **ADR-001 to ADR-015** | Individual decision records following a structured format: Status, Context, Options Considered (with pros/cons), Decision (with rationale), Consequences, Implementation Notes, Validation criteria, and References. |

---

## 3. Cross-Reference Matrix

This matrix shows which documents reference or depend on which other documents.

```
                    ARCH  PLAT  NET-S  NET-C  INV   BUILD  ADR-I  ADRs
ARCHITECTURE.MD      —     ←      ←      ←     ←      ←      ←     ←
PLATFORM.MD          →     —      ←      ←     .      ←      .     .
NETWORK-SECURITY     →     →      —      ←     .      .      .     .
NET-SEC-COMPREH.     →     →      →      —     .      .      .     .
INVESTIGATION-LOG    .     .      .      .     —      ←      .     →
BUILD-LOG.md         →     →      →      .     →      —      .     .
ADR-INDEX.md         .     .      .      .     .      .      —     →
ADRs (001-015)       →     .      .      .     →      .      ←     —

→ = references (row document references column document)
← = referenced by (row document is referenced by column document)
.  = no direct reference
```

### Key Cross-References

| Reference Path | Context |
|---------------|---------|
| ARCHITECTURE.MD → PLATFORM.MD | Service ports, database configuration, deployment targets |
| PLATFORM.MD → ARCHITECTURE.MD | Service descriptions, API endpoints, security requirements |
| NETWORK-SECURITY*.md → PLATFORM.MD | Network policy model, service isolation rules, Calico setup |
| NETWORK-SECURITY*.md → ARCHITECTURE.MD | Service names/ports, database permissions, audit events |
| BUILD-LOG.md → all others | Chronicles the creation of each document and implementation |
| INVESTIGATION-LOG.md → ADRs | Research feeds into formal decision records |
| ADRs → ARCHITECTURE.MD | Decisions shape the application architecture |

---

## 4. Stage 1 Requirements Mapping

Stage 1 (30% of final grade) requires: **Design, Prototyping & Platform Deployment**.

### 4.1 Deliverable Requirements

| # | Requirement | Primary Document(s) | Supporting Evidence |
|---|-------------|---------------------|---------------------|
| 1 | **System architecture design** | ARCHITECTURE.MD | Service diagrams, data flow, API design, database schema |
| 2 | **Technology selection with rationale** | INVESTIGATION-LOG.md, ADR-001 to ADR-015 | Comparative analysis, trade-off evaluation, formal decision records |
| 3 | **Platform infrastructure** | PLATFORM.MD | Kubernetes cluster (Kind, 3 nodes), Calico CNI, namespace strategy |
| 4 | **Database design** | ARCHITECTURE.MD, PLATFORM.MD | Schema (7 tables), per-service users (6), triggers, indexes |
| 5 | **Security architecture** | NETWORK-SECURITY.md, NETWORK-SECURITY-COMPREHENSIVE.md | Zero-trust model, 12 NetworkPolicy resources, threat model |
| 6 | **Deployment strategy** | PLATFORM.MD | Deployment manifests, automation scripts, rollback procedures |
| 7 | **Development process evidence** | BUILD-LOG.md | Weekly entries, sprint retrospectives, metrics, learning journal |
| 8 | **Research and investigation** | INVESTIGATION-LOG.md | Technology comparisons, architecture patterns, security approaches |
| 9 | **Decision documentation** | ADR-INDEX.md, ADR-001 to ADR-015 | 15 structured decision records with alternatives and rationale |
| 10 | **Testing evidence** | NETWORK-SECURITY.md, NETWORK-SECURITY-COMPREHENSIVE.md | Network policy test results (6 phases), test pod infrastructure |

### 4.2 Assessment Criteria Coverage

| Criterion | Evidence | Documents |
|-----------|----------|-----------|
| **Research & Analysis** | Technology comparisons, alternative evaluation, trade-off analysis | INVESTIGATION-LOG.md, ADRs |
| **Design Quality** | Architecture diagrams, service decomposition, data models, API design | ARCHITECTURE.MD |
| **Technical Depth** | Kubernetes manifests, network policies, database permissions, security controls | PLATFORM.MD, NETWORK-SECURITY-COMPREHENSIVE.md |
| **Security** | Zero-trust architecture, STRIDE threat model, OWASP/CIS/NIST compliance mapping | NETWORK-SECURITY-COMPREHENSIVE.md |
| **Process** | Agile iterations, sprint retrospectives, metrics tracking, learning reflection | BUILD-LOG.md |
| **Documentation Quality** | Structured format, cross-references, diagrams, tables, code examples | All documents |
| **Professional Practice** | ADR methodology, IaC, policy-as-code, progressive testing | ADRs, PLATFORM.MD |

### 4.3 Topic-to-Document Mapping

| Topic | Where to Find It |
|-------|-----------------|
| Why Python/FastAPI? | ADR-001, INVESTIGATION-LOG.md §3.1 |
| Why PostgreSQL? | ADR-002, INVESTIGATION-LOG.md §3.2 |
| Why Kubernetes? | ADR-003, INVESTIGATION-LOG.md §3.3 |
| Why Calico over Flannel/Cilium? | ADR-004, INVESTIGATION-LOG.md §3.4, NETWORK-SECURITY.md §2.3 |
| How does voting work? | ARCHITECTURE.MD §Voting Flow, ADR-005 |
| How is admin auth implemented? | ARCHITECTURE.MD §Auth Service, ADR-006 |
| How do audit logs work? | ARCHITECTURE.MD §Audit Service, ADR-007 |
| Why microservices over monolith? | ADR-008, INVESTIGATION-LOG.md §4 |
| Why SSR over SPA? | ADR-009, INVESTIGATION-LOG.md §3.5 |
| How do network policies work? | NETWORK-SECURITY.md (summary), NETWORK-SECURITY-COMPREHENSIVE.md (full) |
| What are the 12 NetworkPolicies? | NETWORK-SECURITY.md §4, NETWORK-SECURITY-COMPREHENSIVE.md §4 |
| What database permissions exist? | ARCHITECTURE.MD §DB Permissions, NETWORK-SECURITY-COMPREHENSIVE.md §6.3 |
| How is vote anonymity preserved? | ADR-015, ARCHITECTURE.MD §Voting Flow |
| What is the cluster architecture? | PLATFORM.MD §2 (Architecture), §3 (Infrastructure) |
| How are services deployed? | PLATFORM.MD §7 (Deployment Strategy) |
| What CI/CD is planned? | PLATFORM.MD §5 (CI/CD Pipeline Design) |
| What monitoring is planned? | PLATFORM.MD §8 (Observability Platform) |
| What threats are modelled? | NETWORK-SECURITY-COMPREHENSIVE.md §7 (Threat Model) |
| What compliance standards? | NETWORK-SECURITY-COMPREHENSIVE.md §9 (CIS, OWASP, NIST, GDPR) |
| How was the project developed? | BUILD-LOG.md (week-by-week journal) |
| What decisions were made and why? | ADR-INDEX.md → individual ADRs |

---

## 5. File Inventory

### 5.1 Primary Documentation (`.docs/`)

| File | Size | Description |
|------|-----:|-------------|
| `INDEX.md` | — | This file — master documentation index and navigation guide |
| `ARCHITECTURE.MD` | 1,354 lines | Application architecture: services, APIs, data models, security |
| `PLATFORM.MD` | 3,046 lines | Infrastructure specification: Kubernetes, networking, deployment, operations |
| `NETWORK-SECURITY.md` | 828 lines | Network security summary: zero-trust model, policies, testing |
| `NETWORK-SECURITY-COMPREHENSIVE.md` | 5,845 lines | Exhaustive security analysis: threats, compliance, full policy review |
| `INVESTIGATION-LOG.md` | 2,027 lines | Research evidence: technology comparisons, design rationale |
| `BUILD-LOG.md` | 2,641 lines | Development journal: weekly progress, sprint retrospectives |

### 5.2 Architecture Decision Records (`.docs/decisions/`)

| File | Category | Decision |
|------|----------|----------|
| `ADR-INDEX.md` | Index | Master index of all 15 ADRs |
| `ADR-001-python-fastapi-backend.md` | Backend | Python + FastAPI selected over Node.js, Django, Go |
| `ADR-002-postgresql-database.md` | Database | PostgreSQL 15 selected over MySQL, MongoDB, SQLite |
| `ADR-003-kubernetes-platform.md` | Infrastructure | Kubernetes selected over Docker Compose, bare VMs |
| `ADR-004-calico-networking.md` | Networking | Calico CNI selected over Flannel, Cilium |
| `ADR-005-token-based-voting.md` | Authentication | Token-based voting URLs over password-based voter auth |
| `ADR-006-jwt-authentication.md` | Authentication | JWT + bcrypt for admin authentication |
| `ADR-007-hash-chain-audit.md` | Security | SHA-256 hash-chained audit logs for tamper detection |
| `ADR-008-microservices-architecture.md` | Architecture | Microservices over monolith for separation of concerns |
| `ADR-009-server-side-rendering.md` | Frontend | Jinja2 SSR over React/Vue SPA for accessibility |
| `ADR-010-network-policy-zero-trust.md` | Security | Zero-trust default-deny NetworkPolicy model |
| `ADR-011-kubernetes-secrets.md` | Security | Kubernetes Secrets (with Vault migration planned) |
| `ADR-012-kind-local-development.md` | Infrastructure | Kind over Minikube for multi-node local clusters |
| `ADR-013-service-separation-strategy.md` | Architecture | Domain-driven service boundaries |
| `ADR-014-database-per-service-users.md` | Database | Per-service PostgreSQL users with least-privilege |
| `ADR-015-vote-anonymity-design.md` | Security | Blind ballot tokens — no FK between voter and vote |

### 5.3 Reference PDFs (`.docs/`)

| File | Description |
|------|-------------|
| `U-Vote_ A Secure, Accessible Online Voting System for Small-Scale Elections.pdf` | Project proposal document |
| `Module PROJ I8009 Project .pdf` | Module specification and assessment criteria |
| `4th Year Project – Computing Systems and Operations.pdf` | Programme-level project guidelines |

### 5.4 Network Policy Test Evidence (`network_summary/`)

| File | Description |
|------|-------------|
| `00-test-pods-summary.md` | Test pod infrastructure — 3 diagnostic pods for policy validation |
| `01-default-deny-summary.md` | Phase 1 results — all traffic blocked after default-deny |
| `02-allow-dns-summary.md` | Phase 2 results — DNS restored, all else blocked |
| `03-database-access-summary.md` | Phase 3 results — whitelisted services connect, others blocked |
| `04-ingress-access-summary.md` | Phase 4 results — 6 ingress policies created with correct ports |
| `05-audit-service-summary.md` | Phase 5 results — bidirectional audit policies deployed |
| `policy-overview.txt` | Live `kubectl get networkpolicy` output showing all 12 policies |

### 5.5 Infrastructure Files (`uvote-platform/`)

| Path | Description |
|------|-------------|
| `kind-config.yaml` | Kind cluster definition (3 nodes, Calico CNI, port mappings) |
| `k8s/namespaces/namespaces.yaml` | Namespace definitions (uvote-dev, uvote-test, uvote-prod) |
| `k8s/database/db-deployment.yaml` | PostgreSQL 15 deployment + service + probes |
| `k8s/database/db-pvc.yaml` | 5Gi PersistentVolumeClaim for database |
| `k8s/database/db-secret.yaml` | Database credentials (Kubernetes Secret) |
| `k8s/database/schema.sql` | Full schema: 7 tables, indexes, triggers, 6 DB users with GRANTs |
| `k8s/network-policies/00-default-deny.yaml` | Policy 00: deny all ingress + egress |
| `k8s/network-policies/01-allow-dns.yaml` | Policy 01: allow DNS egress to kube-dns |
| `k8s/network-policies/02-allow-to-database.yaml` | Policies 02a+02b: bidirectional database access |
| `k8s/network-policies/03-allow-from-ingress.yaml` | Policies 03: 6 per-service ingress from nginx |
| `k8s/network-policies/04-allow-audit.yaml` | Policies 04a+04b: bidirectional audit access |
| `k8s/network-policies/test-pods.yaml` | 3 diagnostic pods for policy testing |
| `k8s/services/auth-deployment.yaml` | Auth service deployment manifest |
| `k8s/services/election-deployment.yaml` | Election service deployment manifest |
| `k8s/services/frontend-deployment.yaml` | Frontend service deployment manifest |
| `k8s/services/results-deployment.yaml` | Results service deployment manifest |
| `k8s/services/admin-deployment.yaml` | Admin service deployment manifest |
| `k8s/services/voting-deployment.yaml` | Voting service deployment manifest |

---

## 6. Documentation Statistics

| Metric | Value |
|--------|------:|
| Primary documents | 7 |
| Architecture Decision Records | 15 |
| Total markdown files | 23 |
| Total lines (all markdown) | ~19,843 |
| Total words (all markdown) | ~120,618 |
| Network policy YAML files | 6 (including test-pods) |
| Network policy test summaries | 7 |
| ASCII architecture diagrams | 30+ |
| Tables | 100+ |
| Threats modelled (STRIDE) | 15 external + 4 internal scenarios |
| Compliance frameworks mapped | 4 (CIS, OWASP, NIST ZTA, GDPR) |

---

**Document Metadata:**

| Field | Value |
|-------|-------|
| **Document** | INDEX.md — Master Documentation Index |
| **Author** | D00255656 |
| **Project** | U-Vote — Secure Online Voting System |
| **Module** | PROJ I8009 — Project |
| **Stage** | Stage 1 — Design, Prototyping & Platform Deployment (30%) |
| **Created** | 2026-02-16 |
| **Status** | Complete |
