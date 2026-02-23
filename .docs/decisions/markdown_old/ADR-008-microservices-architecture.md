# ADR-008: Microservices Architecture

## Status

**Status:** Accepted
**Date:** 2026-02-12
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

The U-Vote system must choose between a monolithic application and a microservices architecture. This decision has cascading effects on deployment complexity, operational overhead, fault isolation, scaling strategy, and — critically — how well the project demonstrates DevOps competencies required by the PROJ I8009 module.

### Background

The initial prototype (Iteration 1, Week 3–4) was a single Flask application handling all functionality. As the system grew to include authentication, election management, voting, results, and audit logging, the monolith became increasingly difficult to reason about. More importantly, deploying a single container to Kubernetes would fail to demonstrate the orchestration features (NetworkPolicies, independent scaling, rolling updates) that the module requires.

The module brief specifically requires: "Build, test and deploy a substantial artefact while demonstrating best practice in modern DevOps" and "Demonstrate a thorough understanding of Development, Configuration Management, CI/CD and Operations including software tools for automation."

### Requirements

- **R1:** Independent deployment — update one component without redeploying everything
- **R2:** Fault isolation — failure in one domain should not crash the entire system
- **R3:** Independent scaling — scale vote-processing independently from admin dashboard
- **R4:** Clear domain boundaries — each component owns its business logic completely
- **R5:** Demonstrate Kubernetes features — pods, services, NetworkPolicies, rolling updates
- **R6:** Support per-service database access control (least privilege)
- **R7:** Manageable complexity — no more services than necessary

### Constraints

- **C1:** Single developer (no team to distribute services across)
- **C2:** Two-semester timeline limits the number of services that can be built
- **C3:** Shared PostgreSQL database (ADR-014) — not true database-per-service
- **C4:** Services must share common code (database connections, security utilities)

---

## Options Considered

### Option 1: Monolithic Application

**Description:**
A single FastAPI application containing all routes, business logic, and templates in one codebase, deployed as a single container.

**Pros:**
- Simplest development (no inter-service communication)
- Single deployment unit (one Dockerfile, one Deployment)
- No network latency between components
- Easier debugging (single process, single log stream)
- Faster initial development

**Cons:**
- Single point of failure — one bug crashes everything
- Cannot scale individual components
- All code deployed together — risky deployments
- Limited demonstration of Kubernetes features
- Cannot apply per-service NetworkPolicies (nothing to isolate)
- Cannot apply per-service database users (single application user)
- Technology lock-in (cannot use different tools per domain)

**Evaluation:**
A monolith deployed as a single Kubernetes pod would technically satisfy "containers" but would not demonstrate NetworkPolicies, rolling updates across services, independent scaling, service discovery, or inter-service communication patterns. This would significantly reduce marks for the DevOps demonstration components.

### Option 2: Microservices Architecture — Chosen

**Description:**
Separate FastAPI services for each business domain: authentication, election management, voting, results, and a frontend service. Each service has its own Dockerfile, Kubernetes Deployment, and Service resource.

**Pros:**
- Independent deployment (update auth-service without touching voting-service)
- Fault isolation (voting-service failure doesn't affect results-service)
- Independent scaling (scale voting-service during active elections)
- Demonstrates Kubernetes features (pods, services, NetworkPolicies, rolling updates)
- Clear domain boundaries improve maintainability
- Per-service database users enforce least privilege
- Per-service NetworkPolicies enforce zero-trust
- Directly addresses module requirements for DevOps practices

**Cons:**
- Higher initial complexity (multiple Dockerfiles, manifests, services)
- Inter-service communication overhead (HTTP calls between services)
- Distributed system debugging is harder (multiple log streams)
- Shared library management (`shared/` directory copied into each image)
- More infrastructure to maintain (6 Deployments, 6 Services, NetworkPolicies)

**Evaluation:**
Meets all requirements (R1–R7). The additional complexity is justified by the significantly richer DevOps demonstration and the security benefits of service isolation.

### Option 3: Serverless Functions

**Description:**
Deploy each endpoint as a serverless function (AWS Lambda, Azure Functions, Google Cloud Functions).

**Pros:**
- Zero infrastructure management
- Automatic scaling
- Pay-per-execution pricing

**Cons:**
- Cold start latency (1–5 seconds) — unacceptable for voting UX
- Vendor lock-in to specific cloud provider
- Complex local development (requires emulators)
- Not aligned with Kubernetes learning objectives
- No NetworkPolicy equivalent
- Difficult to maintain consistent database connections

**Evaluation:**
Fails R5 (demonstrate Kubernetes features) and introduces cold-start latency that violates the <500ms response time requirement. Serverless is optimised for sporadic, event-driven workloads — not a web application with sustained traffic during elections.

### Option 4: Modular Monolith

**Description:**
A single deployment with internal module boundaries — shared codebase but logically separated modules.

**Pros:**
- Cleaner than a flat monolith
- Simpler deployment than microservices
- Can evolve into microservices later
- No inter-service communication overhead

**Cons:**
- Single deployment unit — same deployment risks as monolith
- Doesn't demonstrate Kubernetes service features
- Cannot apply per-service NetworkPolicies
- Cannot apply per-service database users
- Limited DevOps demonstration value

**Evaluation:**
A modular monolith is a pragmatic middle ground for larger teams, but for this project it provides insufficient demonstration of Kubernetes capabilities. The module assessment explicitly rewards DevOps practices that require multiple independently deployed services.

---

## Decision

**Chosen Option:** Microservices Architecture (Option 2) with 6 services

**Rationale:**
Microservices directly enable demonstration of Kubernetes features (pods, services, NetworkPolicies, rolling updates, independent scaling) that are required by the module. The additional development complexity is justified by the significantly richer DevOps demonstration opportunity.

**Services defined:**

| Service | Port | Domain | Responsibility |
|---------|------|--------|---------------|
| auth-service | 5001 | Authentication | Organiser auth, JWT, token validation, MFA, blind ballot issuance |
| election-service | 5002 | Elections | Election CRUD, lifecycle, voter management, token generation |
| voting-service | 5003 | Voting | Voter-facing web app, identity verification, ballot submission |
| results-service | 5004 | Results | Vote tallying, winner calculation, decryption |
| frontend-service | 5000 | Admin UI | Admin dashboard, election management interface |
| voter-service | 5002 | Voter Mgmt | Voter list management, CSV import (merged with election in current impl) |

**Key Factors:**

1. **Module alignment (R5):** A monolith deployed as one pod would score poorly on "demonstrate best practice in modern DevOps." Microservices enable demonstration of service discovery, NetworkPolicies, rolling updates, independent scaling, and fault isolation.

2. **Security (R6):** Per-service database users (ADR-014) and per-service NetworkPolicies (ADR-010) are only possible with separate services. A monolith uses a single database user with full access.

3. **Fault isolation (R2):** If the results-service crashes during an active election, voters can still cast ballots via the voting-service. In a monolith, a crash affects everything.

4. **Manageable scope (R7):** Six services is large enough to demonstrate microservice patterns but small enough for a single developer to maintain over two semesters.

---

## Consequences

### Positive Consequences

- **Rich DevOps demonstration:** NetworkPolicies, rolling updates, health probes, independent scaling all operational
- **Security isolation:** Each service has its own database user and network access permissions
- **Fault tolerance:** Individual service failures are isolated
- **Clear ownership:** Each service's codebase is focused on a single domain
- **Deployment flexibility:** Services can be updated, scaled, or rolled back independently

### Negative Consequences

- **Development overhead:** 6 Dockerfiles, 6 Deployment manifests, 6 Service manifests, shared library management. Mitigated by: consistent structure across services, shared Dockerfile patterns, deployment automation script.
- **Inter-service latency:** HTTP calls between services add ~5–10ms per call. Mitigated by: minimising cross-service calls; most operations complete within a single service.
- **Debugging complexity:** Distributed tracing needed to follow a request across services. Mitigated by: structured logging, health endpoints, Kubernetes events and logs.

### Trade-offs Accepted

- **Complexity vs DevOps Value:** Accepted the operational complexity of 6 services in exchange for comprehensive DevOps demonstration. A single developer managing 6 services is more work, but the learning and demonstration value is substantial.
- **Latency vs Isolation:** Accepted ~5–10ms inter-service call overhead in exchange for service-level fault isolation and security boundaries. For an election with 1,000 voters, this latency is imperceptible.

---

## Implementation Notes

### Technical Details

Each service follows a consistent structure:
```
service-name/
├── app.py             # FastAPI application
├── Dockerfile         # Container image definition
├── requirements.txt   # Python dependencies
├── static/css/        # CSS stylesheets (if frontend-facing)
└── templates/         # Jinja2 templates (if frontend-facing)
```

Shared code is in `shared/`:
```
shared/
├── database.py        # Async connection pool (asyncpg)
├── security.py        # Hashing, token generation, encryption
└── schemas.py         # Pydantic request/response models
```

### Configuration

- **Communication pattern:** Synchronous HTTP (service-to-service via httpx.AsyncClient)
- **Service discovery:** Kubernetes DNS (e.g., `http://auth-service:5001`)
- **Shared library:** Copied into each Docker image at build time
- **Health probes:** `GET /health` on each service

### Integration Points

- **ADR-003 (Kubernetes):** Each service is a Kubernetes Deployment + Service
- **ADR-010 (Zero-Trust):** NetworkPolicies control inter-service communication
- **ADR-013 (Separation):** Domain-driven boundaries define service responsibilities
- **ADR-014 (DB Users):** Each service uses a dedicated PostgreSQL user

---

## Validation

### Success Criteria

- [x] All 6 services start independently and respond to health checks
- [x] Services communicate via HTTP with Kubernetes service DNS
- [x] NetworkPolicies enforce service isolation
- [x] Rolling updates deploy without downtime
- [x] Individual service failure does not crash other services

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Services | 6 | 6 (auth, election, voting, results, frontend, voter) |
| Independent deployments | Yes | Yes (per-service Dockerfile) |
| Inter-service latency | <50ms | ~10ms (within Kind cluster) |
| Health endpoint coverage | 100% | 100% (all services have /health) |

### Review Date

End of Stage 2 (April 2026) — assess whether service count is optimal or needs consolidation/expansion.

---

## References

- [Investigation Log §4.1](../INVESTIGATION-LOG.md#41-microservices-vs-monolith) — Full analysis
- [Investigation Log §4.2](../INVESTIGATION-LOG.md#42-service-separation-strategy) — Service boundaries
- [Martin Fowler — Microservices](https://martinfowler.com/articles/microservices.html)
- [ADR-003](ADR-003-kubernetes-platform.md) — Kubernetes platform
- [ADR-010](ADR-010-network-policy-zero-trust.md) — Network security between services
- [ADR-013](ADR-013-service-separation-strategy.md) — Domain-driven service boundaries
- [ADR-014](ADR-014-database-per-service-users.md) — Per-service database users

## Notes

The voter-service and election-service functionality is partially merged in the current implementation. As the system matures, these may be fully separated or consolidated depending on development velocity and operational experience.
