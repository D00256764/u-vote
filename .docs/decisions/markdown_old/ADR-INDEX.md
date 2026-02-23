# Architecture Decision Records — Index

**Project:** U-Vote — Secure Online Voting System
**Author:** D00255656
**Module:** PROJ I8009 — Project
**Institution:** Dundalk Institute of Technology (DkIT)

---

## Decision Log

| ADR | Title | Status | Date | Category |
|-----|-------|--------|------|----------|
| [ADR-001](ADR-001-python-fastapi-backend.md) | Python FastAPI Backend | Accepted | 2025-09-15 | Backend Framework |
| [ADR-002](ADR-002-postgresql-database.md) | PostgreSQL Database | Accepted | 2025-09-18 | Database |
| [ADR-003](ADR-003-kubernetes-platform.md) | Kubernetes Platform | Accepted | 2025-09-22 | Infrastructure |
| [ADR-004](ADR-004-calico-networking.md) | Calico CNI Networking | Accepted | 2025-09-25 | Networking |
| [ADR-005](ADR-005-token-based-voting.md) | Token-Based Voter Authentication | Accepted | 2025-10-01 | Authentication |
| [ADR-006](ADR-006-jwt-authentication.md) | JWT Admin Authentication | Accepted | 2025-10-03 | Authentication |
| [ADR-007](ADR-007-hash-chain-audit.md) | SHA-256 Hash-Chain Audit Logs | Accepted | 2025-10-08 | Security |
| [ADR-008](ADR-008-microservices-architecture.md) | Microservices Architecture | Accepted | 2025-10-12 | Architecture |
| [ADR-009](ADR-009-server-side-rendering.md) | Server-Side Rendering (Jinja2) | Accepted | 2025-10-15 | Frontend |
| [ADR-010](ADR-010-network-policy-zero-trust.md) | Zero-Trust Network Policies | Accepted | 2025-10-20 | Security |
| [ADR-011](ADR-011-kubernetes-secrets.md) | Kubernetes Secrets Management | Accepted | 2025-10-25 | Security |
| [ADR-012](ADR-012-kind-local-development.md) | Kind for Local Development | Accepted | 2025-09-22 | Infrastructure |
| [ADR-013](ADR-013-service-separation-strategy.md) | Domain-Driven Service Separation | Accepted | 2025-10-12 | Architecture |
| [ADR-014](ADR-014-database-per-service-users.md) | Per-Service Database Users | Accepted | 2025-10-28 | Database |
| [ADR-015](ADR-015-vote-anonymity-design.md) | Blind Ballot Token Anonymity | Accepted | 2025-11-01 | Security |

## Status Legend

| Status | Meaning |
|--------|---------|
| **Accepted** | Decision has been made and implemented |
| **Proposed** | Decision is under consideration |
| **Deprecated** | Decision has been replaced by a newer ADR |
| **Superseded** | Decision has been replaced (see superseding ADR) |

## Categories

- **Architecture:** System-level design patterns and service structure
- **Authentication:** How users prove their identity
- **Backend Framework:** Server-side technology choices
- **Database:** Data storage and access patterns
- **Frontend:** User interface rendering approach
- **Infrastructure:** Deployment platform and orchestration
- **Networking:** Network configuration and CNI
- **Security:** Security controls and threat mitigations

## ADR Format

Each ADR follows the standard format:
1. **Status** — Current state of the decision
2. **Context** — Problem statement, background, requirements, constraints
3. **Options Considered** — Each option with pros, cons, evaluation
4. **Decision** — Chosen option with rationale and key factors
5. **Consequences** — Positive/negative outcomes and trade-offs
6. **Implementation Notes** — Technical details and configuration
7. **Validation** — Success criteria and metrics
8. **References** — Related documents and resources

---

**Last Updated:** 2026-02-16
