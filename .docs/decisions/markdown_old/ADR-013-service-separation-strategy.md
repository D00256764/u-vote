# ADR-013: Domain-Driven Service Separation

## Status

**Status:** Accepted
**Date:** 2026-02-14
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

Having decided on a microservices architecture (ADR-008), the next question is how to divide the system into services. The separation strategy determines each service's scope of responsibility, database access requirements, API surface, and failure boundaries. A poorly chosen strategy leads to either too-coarse services (losing microservice benefits) or too-fine services (creating excessive inter-service communication).

### Background

Three separation strategies were researched: by technical layer, by domain (Domain-Driven Design), and by user role. The ideal strategy creates services that are independently deployable, have clear ownership of their data, minimise inter-service dependencies, and align with the security model (per-service database users and network policies).

### Requirements

- **R1:** Each service owns a clear business domain
- **R2:** Minimal inter-service dependencies (low coupling)
- **R3:** Each service can be deployed independently
- **R4:** Service boundaries align with security boundaries (DB users, network policies)
- **R5:** No more services than necessary (manageable for a single developer)

### Constraints

- **C1:** Single developer maintaining all services
- **C2:** Shared PostgreSQL database (ADR-014)
- **C3:** Two-semester timeline
- **C4:** Some shared code required (database, security utilities)

---

## Options Considered

### Option 1: Technical Layer Separation

**Description:**
Separate services by technical function: API gateway, business logic, data access.

```
api-gateway/       → All HTTP routing
business-logic/    → All business rules
data-access/       → All database queries
```

**Pros:**
- Clear technical responsibilities
- Each layer uses a single technology

**Cons:**
- Anti-pattern for microservices (creates tight coupling between layers)
- Any feature change requires modifying all three services
- No domain isolation (all business logic in one service)
- Cannot apply per-domain security policies

**Evaluation:**
This is a distributed monolith — the worst of both worlds. It has the complexity of microservices without the benefits of domain isolation.

### Option 2: Domain-Driven Boundaries — Chosen

**Description:**
Separate services by business domain, following Domain-Driven Design (DDD) bounded context principles.

```
auth-service/       → Authentication (organiser login, voter token validation, MFA, ballot issuance)
election-service/   → Election lifecycle (CRUD, voter management, token generation)
voting-service/     → Voter-facing web app (identity verification, ballot, vote casting)
results-service/    → Results computation (tallying, decryption, winner calculation)
frontend-service/   → Admin web UI (dashboard, election management)
```

**Pros:**
- Each service owns a complete business domain
- Changes are localised (e.g., changing vote tallying only affects results-service)
- Natural alignment with security boundaries (voting-service has different DB needs than auth-service)
- Clear ownership and responsibility
- Independent deployment (update results-service without touching voting-service)

**Cons:**
- Some domains have cross-cutting concerns (audit logging spans all services)
- Voter management partially overlaps election management
- Single developer must maintain all domain knowledge

**Evaluation:**
Meets all requirements (R1–R5). Cross-cutting concerns (audit logging) are handled by a shared audit-service that all services call.

### Option 3: User Role Separation

**Description:**
Separate services by user type: admin service and voter service.

```
admin-service/   → Everything admins do (create elections, manage voters, view results)
voter-service/   → Everything voters do (verify identity, see ballot, cast vote)
```

**Pros:**
- Simple division
- Each service targets one user type
- Only 2 services to maintain

**Cons:**
- Too coarse-grained — admin-service becomes a monolith internally
- Cannot apply fine-grained security (admin-service needs access to all tables)
- Cannot scale voting independently from admin functions
- Limited demonstration of microservice patterns
- No benefit of independent deployment for sub-domains within each service

**Evaluation:**
Fails R1 (clear domain ownership — admin-service would own everything) and R2 (admin-service has maximum coupling with all tables). Two services is too few to demonstrate Kubernetes features effectively.

---

## Decision

**Chosen Option:** Domain-Driven Boundaries (Option 2)

**Rationale:**
Domain-driven separation creates services with clear responsibilities, minimal coupling, and natural alignment with the security model. Each service maps to a bounded context in DDD terminology.

**Service Responsibilities:**

| Service | Domain | Key Tables | External API |
|---------|--------|------------|-------------|
| auth-service | Authentication & Identity | organisers, voting_tokens, voter_mfa, blind_tokens | Organiser login, token validation, MFA, ballot issuance |
| election-service | Election Lifecycle | elections, voters, election_options, voting_tokens | Election CRUD, voter management, token generation |
| voting-service | Vote Casting | encrypted_ballots, vote_receipts, blind_tokens | Voter web UI, identity verification, ballot submission |
| results-service | Results & Tallying | encrypted_ballots, tallied_votes, elections | Results computation, decryption, statistics |
| frontend-service | Admin UI | None (API consumer) | Admin dashboard, election management forms |

**Key Factors:**

1. **Security alignment (R4):** Each service's database access is limited to its domain tables. The auth-service cannot read encrypted ballots. The results-service cannot modify elections. This maps directly to per-service PostgreSQL users (ADR-014).

2. **Failure isolation (R2):** If the results-service crashes during an active election, voters can still cast ballots via voting-service. If the auth-service is slow, election management via frontend-service is unaffected.

3. **The anonymity boundary:** The critical separation is between auth-service (which knows voter identity) and voting-service (which handles anonymous ballots). This architectural boundary enforces vote anonymity — even at the code level, the voting-service never has access to voter identity information.

---

## Consequences

### Positive Consequences

- **Clear domain ownership:** Each service has a well-defined scope — new developers (or the same developer months later) can quickly understand each service's purpose
- **Security boundaries:** Service separation enables per-service DB users and network policies
- **Anonymity enforcement:** The separation between auth (identity) and voting (ballots) is architectural, not just logical
- **Independent evolution:** Each service can be refactored, optimised, or replaced without affecting others

### Negative Consequences

- **Cross-domain queries:** Some operations span domains (e.g., showing election results requires election metadata + vote tallies). Mitigated by: the results-service has read access to both elections and encrypted_ballots tables.
- **Shared code management:** Common database and security utilities must be shared. Mitigated by: `shared/` directory copied into each Docker image at build time.
- **Domain overlap:** Voter management partially overlaps election management. Mitigated by: election-service handles voter CRUD as part of election setup; auth-service handles voter authentication.

### Trade-offs Accepted

- **Domain purity vs Practicality:** Some services access tables from adjacent domains (e.g., auth-service reads voters table for MFA). This is a pragmatic compromise — strict DDD would require inter-service API calls for every cross-domain data access, adding latency and complexity.
- **Service count vs Manageability:** 5 services is enough to demonstrate microservice patterns but small enough for a single developer. Could expand to 8+ services (adding dedicated audit, email, admin services) in Stage 2.

---

## Implementation Notes

### Technical Details

Service communication patterns:
- **voting-service → auth-service:** HTTP (token validation, MFA, ballot token issuance)
- **frontend-service → auth-service:** HTTP (organiser login/registration)
- **frontend-service → election-service:** HTTP (election CRUD)
- **All services → audit_log table:** Direct DB insert (audit logging)

### Configuration

Each service defines its domain via:
1. **Dockerfile:** Independent image
2. **Kubernetes Deployment:** Independent scaling and health probes
3. **Kubernetes Service:** Independent ClusterIP for discovery
4. **NetworkPolicy:** Independent ingress/egress rules
5. **Database user:** Independent PostgreSQL credentials

### Integration Points

- **ADR-008 (Microservices):** This ADR defines how the microservices are separated
- **ADR-014 (DB Users):** Per-service database users align with service domains
- **ADR-010 (Zero-Trust):** NetworkPolicies align with service boundaries
- **ADR-015 (Anonymity):** Auth/voting separation enforces identity-ballot boundary

---

## Validation

### Success Criteria

- [x] Each service has a single, clear domain responsibility
- [x] Services can be deployed independently
- [x] Security policies (DB users, NetworkPolicies) align with service boundaries
- [x] Anonymity boundary maintained between auth and voting services
- [x] Cross-service communication is minimal (most operations within a single service)

### Review Date

End of Stage 2 (April 2026) — evaluate whether service boundaries should be adjusted based on development experience.

---

## References

- [Investigation Log §4.2](../INVESTIGATION-LOG.md#42-service-separation-strategy) — Full analysis
- [Eric Evans — Domain-Driven Design](https://www.domainlanguage.com/ddd/)
- [ADR-008](ADR-008-microservices-architecture.md) — Microservices architecture decision
- [ADR-014](ADR-014-database-per-service-users.md) — Per-service database access
- [ADR-015](ADR-015-vote-anonymity-design.md) — Anonymity boundary

## Notes

The auth-service has the broadest scope in the current design, handling organiser authentication, voter token validation, MFA verification, and blind ballot token issuance. In a future iteration, this could be split into an organiser-auth-service and a voter-identity-service, but the current scope is manageable.
