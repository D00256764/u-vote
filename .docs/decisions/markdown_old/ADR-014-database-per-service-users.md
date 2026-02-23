# ADR-014: Per-Service Database Users

## Status

**Status:** Accepted
**Date:** 2026-02-15
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

The microservices architecture (ADR-008) deploys 6 services that access a shared PostgreSQL database (ADR-002). The database access pattern — shared database with shared credentials vs per-service users vs fully separate databases — determines the blast radius if any single service is compromised. A compromised service with full database access could read voter data, modify election results, delete audit logs, or exfiltrate sensitive information.

### Background

The principle of least privilege (PoLP) states that each service should have only the minimum database permissions required for its function. In a shared-credential model, every service has full access to every table — a single compromised service exposes the entire database. Per-service users restrict each service to its domain tables, limiting the damage from a compromise.

### Requirements

- **R1:** Each service can only access tables relevant to its domain
- **R2:** Compromise of one service does not grant access to other domains' data
- **R3:** Read-only services have read-only database access
- **R4:** Immutable tables (audit_log, encrypted_ballots) cannot be modified even by their owning service
- **R5:** Must work with a single PostgreSQL instance (resource constraints)
- **R6:** Credentials managed via Kubernetes Secrets (ADR-011)

### Constraints

- **C1:** Single PostgreSQL instance (cannot run separate databases per service)
- **C2:** 16GB RAM development machine limits database instances
- **C3:** Per-service users add credential management complexity
- **C4:** PostgreSQL's GRANT system is table-level, not row-level (for MVP)

---

## Options Considered

### Option 1: Shared Database, Shared Credentials

**Description:**
All services use a single PostgreSQL user (e.g., `evote_admin`) with full access to all tables.

**Pros:**
- Simplest setup (one user, one password)
- No credential management complexity
- No permission configuration

**Cons:**
- Zero isolation — any compromised service has full database access
- Compromised results-service could modify elections or delete audit logs
- Compromised frontend-service could directly query voter data
- Violates principle of least privilege
- No security benefit from microservice separation at the database layer

**Evaluation:**
Fails R1, R2, R3, R4. Undermines the security benefits of the microservice architecture — if all services share one superuser credential, the database sees no distinction between them.

### Option 2: Per-Service PostgreSQL Users — Chosen

**Description:**
Create a dedicated PostgreSQL user for each service with GRANT statements restricted to the tables and operations that service requires.

**Pros:**
- Each service has minimum necessary permissions
- Compromise of one service limits blast radius
- Read-only services (results) have read-only access
- Audit service can INSERT but not UPDATE/DELETE
- Database-level enforcement (cannot be bypassed by application code)
- Clear documentation of each service's data access

**Cons:**
- More complex credential management (6 users × password)
- Must update GRANTs when schema changes
- All users share one database instance (no physical isolation)
- Table-level granularity (not row-level or column-level)

**Evaluation:**
Meets all requirements (R1–R6). The credential management complexity is handled by Kubernetes Secrets and the deployment automation script.

### Option 3: Fully Separate Databases

**Description:**
Each service has its own PostgreSQL instance with its own schema.

**Pros:**
- Maximum isolation (complete database separation)
- Each service owns its data entirely
- No shared tables, no cross-service queries

**Cons:**
- 6 PostgreSQL instances = ~3GB RAM just for databases
- Distributed transactions needed for cross-service operations
- Data duplication (election metadata needed by multiple services)
- Massively increased operational complexity
- Impractical for a local Kind cluster with 16GB RAM
- Overkill for MVP scope

**Evaluation:**
Fails C1 and C2. Running 6 PostgreSQL pods on a local cluster is impractical and unnecessary. The marginal isolation benefit over per-service users does not justify the resource cost.

---

## Decision

**Chosen Option:** Per-Service PostgreSQL Users (Option 2)

**Rationale:**
Per-service users provide meaningful isolation (each service can only access its domain tables) without the resource overhead of separate databases. This is the standard approach for shared-database microservice architectures and balances security with practicality.

**User Permission Matrix:**

| Service | DB User | Tables Accessible | Permissions |
|---------|---------|------------------|-------------|
| auth-service | `auth_user` | organisers, voting_tokens, voter_mfa, blind_tokens, voters, elections, audit_log | SELECT, INSERT, UPDATE (specific tables) |
| election-service | `election_user` | elections, voters, election_options, voting_tokens, audit_log | SELECT, INSERT, UPDATE, DELETE |
| voting-service | `voting_user` | elections, election_options, encrypted_ballots, vote_receipts, blind_tokens, audit_log | SELECT, INSERT, UPDATE (blind_tokens only) |
| results-service | `results_user` | elections, election_options, encrypted_ballots, tallied_votes | SELECT only (read-only) + INSERT on tallied_votes |
| frontend-service | None | None | No database access (API consumer only) |

**Key Factors:**

1. **Blast radius limitation (R2):** If voting-service is compromised, the attacker can INSERT encrypted ballots but cannot read voter email addresses (voters table not granted), cannot modify elections (elections is SELECT only), and cannot delete audit logs (audit_log has immutability triggers AND the voting_user has INSERT-only access).

2. **Read-only enforcement (R3):** The results-service has SELECT-only access. Even if compromised, it cannot modify any data — it can only read.

3. **Frontend isolation (R1):** The frontend-service has NO database user. It communicates entirely through backend service APIs. Combined with the NetworkPolicy that blocks frontend → PostgreSQL traffic (ADR-010), this provides two layers of defence against SQL injection through the most exposed service.

4. **Defence in depth:** Per-service DB users (this ADR) + NetworkPolicies (ADR-010) + immutability triggers (ADR-007) create three independent security layers. Each operates even if the others fail.

---

## Consequences

### Positive Consequences

- **Least-privilege access:** Each service has minimum necessary permissions — no service has superuser access
- **Blast radius limitation:** Compromise of one service cannot access other domains' data
- **Defence in depth:** Database permissions complement network policies and application-level controls
- **Documentation value:** The permission matrix explicitly documents what each service can do — valuable for security audits

### Negative Consequences

- **Credential management:** 6 database users with separate passwords must be created and stored as Kubernetes Secrets. Mitigated by: deployment script automates user creation; Kubernetes Secrets manage credentials.
- **Schema evolution:** Adding a new table requires deciding which users need access and updating GRANT statements. Mitigated by: permission matrix documented here and in ARCHITECTURE.MD.
- **Shared instance limitations:** All users share the same PostgreSQL instance — a database-level attack (e.g., resource exhaustion) affects all services. Mitigated by: connection pool limits per service; production would use connection limits per user.

### Trade-offs Accepted

- **Per-service users vs Separate databases:** Accepted shared database with per-service users over fully separate databases. The resource cost of 6 PostgreSQL instances is prohibitive for local development. Per-service users provide 80% of the security benefit at 10% of the resource cost.
- **Table-level vs Row-level security:** Accepted table-level GRANT over PostgreSQL Row-Level Security (RLS). RLS would provide finer-grained control (e.g., election-service can only see elections it created) but adds significant complexity. Table-level GRANTs are sufficient for the MVP.

---

## Implementation Notes

### Technical Details

User creation (in schema.sql or deployment script):
```sql
-- Auth service: can read/write auth-related tables
CREATE USER auth_user WITH PASSWORD '<from-secret>';
GRANT SELECT, INSERT, UPDATE ON organisers TO auth_user;
GRANT SELECT ON voters, elections TO auth_user;
GRANT SELECT, UPDATE ON voting_tokens TO auth_user;
GRANT SELECT, INSERT ON voter_mfa, blind_tokens TO auth_user;
GRANT INSERT ON audit_log TO auth_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO auth_user;

-- Results service: read-only for tallying
CREATE USER results_user WITH PASSWORD '<from-secret>';
GRANT SELECT ON elections, election_options, encrypted_ballots TO results_user;
GRANT SELECT, INSERT ON tallied_votes TO results_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO results_user;
```

### Configuration

- **Credentials:** Stored as Kubernetes Secrets, mounted as environment variables
- **Connection pool:** Each service has its own asyncpg pool (min=2, max=20)
- **User creation:** Automated in deployment script (`deploy_platform.py`)

### Integration Points

- **ADR-002 (PostgreSQL):** Per-service users are PostgreSQL roles with GRANT statements
- **ADR-008 (Microservices):** Each service uses its dedicated database user
- **ADR-010 (Zero-Trust):** NetworkPolicies restrict which services can reach PostgreSQL
- **ADR-011 (Secrets):** Database credentials stored as Kubernetes Secrets
- **ADR-013 (Separation):** Service domain boundaries align with database access boundaries

---

## Validation

### Success Criteria

- [x] Each service uses a dedicated PostgreSQL user
- [x] Frontend-service has no database access
- [x] Results-service has read-only access (SELECT only on data tables)
- [x] Immutability triggers prevent modification of audit_log and encrypted_ballots
- [x] Credentials stored as Kubernetes Secrets (not in source code)

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| DB users created | 5 (one per DB-accessing service) | 5 |
| Frontend DB access | None | None (no user, no network path) |
| Read-only services | 1 (results) | 1 |
| Tables with immutability triggers | 2 (audit_log, encrypted_ballots) | 2 |

### Review Date

End of Stage 2 (April 2026) — evaluate whether Row-Level Security (RLS) should be added for multi-tenant isolation.

---

## References

- [Investigation Log §4.4](../INVESTIGATION-LOG.md#44-shared-database-vs-database-per-service) — Full analysis
- [PostgreSQL GRANT Documentation](https://www.postgresql.org/docs/15/sql-grant.html)
- [OWASP Principle of Least Privilege](https://owasp.org/www-community/Access_Control)
- [ADR-002](ADR-002-postgresql-database.md) — PostgreSQL database selection
- [ADR-010](ADR-010-network-policy-zero-trust.md) — Network policies complement DB permissions
- [ADR-011](ADR-011-kubernetes-secrets.md) — Credential storage

## Notes

The `deploy_platform.py` script creates database users with generated passwords and stores them as Kubernetes Secrets during deployment. This ensures credentials are never hardcoded in source files. The schema.sql file contains `CREATE USER` statements with placeholder passwords that are overridden during deployment.
