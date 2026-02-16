# ADR-002: PostgreSQL Database

## Status

**Status:** Accepted
**Date:** 2026-02-10
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

The U-Vote system requires a database that can guarantee ballot integrity through ACID transactions, provide native encryption primitives for ballot confidentiality, and enforce audit log immutability at the database level. The database must support per-service access control to align with the microservices architecture, where each service should only access the tables relevant to its function.

### Background

Early prototyping in Week 1 used SQLite for rapid iteration. While SQLite was effective for single-developer testing, it became immediately apparent that its file-level locking model would not support concurrent ballot submissions from multiple voters during an active election. Additionally, the project's security requirements (encrypted ballots, immutable audit logs, role-based access) demanded a database with server-grade security features.

The election domain has strict data integrity requirements. A lost or duplicated vote is a critical failure — unlike an e-commerce system where a retry is acceptable, a double-counted ballot undermines the legitimacy of the entire election. This elevates ACID compliance from a "nice to have" to a hard requirement.

### Requirements

- **R1:** Full ACID transaction support with serialisable isolation for ballot submission
- **R2:** Native encryption functions for ballot confidentiality (encrypt at rest within the database)
- **R3:** Database-level triggers for audit log immutability enforcement
- **R4:** Per-service user roles with granular privilege control (SELECT, INSERT, UPDATE per table)
- **R5:** Asynchronous driver support for Python (asyncpg or equivalent)
- **R6:** Connection pooling with configurable min/max connections
- **R7:** JSONB or equivalent for flexible election configuration storage
- **R8:** Containerisable with persistent volume support in Kubernetes
- **R9:** Mature tooling for backup, restore, and schema migration

### Constraints

- **C1:** Must support asyncpg for integration with FastAPI async handlers (see ADR-001)
- **C2:** Must run within a Kind cluster with PersistentVolumeClaim storage
- **C3:** Single database instance (no clustering) — project scope does not justify multi-node setup
- **C4:** Student budget — no commercial database licensing

---

## Options Considered

### Option 1: PostgreSQL 15 — Chosen

**Description:**
PostgreSQL is an advanced open-source relational database with over 35 years of active development. Version 15 (released October 2022) includes enhanced logical replication, improved sort performance, and the MERGE command. PostgreSQL is widely regarded as the most feature-rich open-source RDBMS.

**Pros:**
- Full ACID compliance with serialisable transaction isolation
- pgcrypto extension provides `pgp_sym_encrypt`/`pgp_sym_decrypt` for in-database ballot encryption
- PL/pgSQL procedural language enables complex triggers (audit log immutability enforcement)
- Per-user role-based access control with fine-grained privilege management (GRANT/REVOKE per table, per operation)
- JSONB data type for flexible, indexed semi-structured data (election configuration, candidate metadata)
- asyncpg driver (fastest PostgreSQL driver for Python — C-level protocol implementation)
- Excellent Kubernetes ecosystem (official Docker image, well-documented PVC patterns)
- Extensive documentation, massive community, and decades of production battle-testing

**Cons:**
- Higher resource usage than SQLite or MySQL for small workloads (~50MB baseline memory)
- More complex initial setup than SQLite (requires server process, user management)
- pgcrypto requires explicit extension installation (`CREATE EXTENSION pgcrypto`)
- Slightly steeper learning curve for PL/pgSQL triggers compared to application-level logic

**Evaluation:**
PostgreSQL satisfies all requirements (R1–R9) and all constraints (C1–C4). Its pgcrypto extension and PL/pgSQL triggers provide database-level security features that no other considered option matches.

### Option 2: MySQL 8.0

**Description:**
MySQL is the world's most popular open-source relational database, now developed by Oracle. Version 8.0 supports CTEs, window functions, and improved JSON support.

**Pros:**
- Widespread adoption and community support
- Good performance for read-heavy workloads
- InnoDB engine provides ACID compliance
- Familiar from DkIT coursework (used in database modules)
- Mature replication and backup tooling

**Cons:**
- No equivalent to pgcrypto — encryption must be handled at the application layer (AES_ENCRYPT exists but lacks PGP-grade primitives)
- No equivalent to PL/pgSQL triggers with the same expressiveness for audit enforcement
- asyncmy (async MySQL driver) is less mature and performant than asyncpg
- JSON support exists but is less capable than PostgreSQL's JSONB (no GIN indexing on JSON)
- Oracle stewardship raises long-term open-source concerns
- Per-user privilege model is less granular than PostgreSQL's role-based system

**Evaluation:**
MySQL meets R1, R5, R6, R8, and R9 but falls short on R2 (native encryption), R3 (trigger expressiveness), R4 (role granularity), and R7 (JSONB). The encryption gap is the most critical — moving encryption entirely to the application layer would require significant additional code and would not benefit from database-level key management.

### Option 3: MongoDB 7.0

**Description:**
MongoDB is a document-oriented NoSQL database that stores data in BSON (Binary JSON) documents. Version 7.0 includes compound wildcard indexes and improved sharding.

**Pros:**
- Flexible schema (no migrations needed for schema changes)
- Native JSON document storage (no ORM needed)
- Horizontal scaling built-in (sharding)
- Good Python driver (motor for async)

**Cons:**
- No ACID transactions across collections by default (multi-document transactions added in v4.0 but with performance penalties)
- No equivalent to pgcrypto — encryption is application-level or requires MongoDB Enterprise (paid)
- No triggers with the same enforcement capability as PL/pgSQL (change streams are reactive, not preventive)
- Document model is a poor fit for relational election data (voters belong to elections, ballots reference candidates — these are inherently relational)
- Per-collection access control is coarser than PostgreSQL's per-table, per-column GRANT model
- BSON overhead for small documents (each document stores field names)

**Evaluation:**
MongoDB fails R1 (ACID without performance penalty), R2 (native encryption without Enterprise), and R3 (preventive triggers). More fundamentally, the election domain is inherently relational — voters are registered for elections, ballots reference candidates, results aggregate votes. Forcing this into a document model adds complexity without benefit.

### Option 4: SQLite 3

**Description:**
SQLite is a serverless, file-based SQL database engine embedded directly into the application process. It requires zero configuration and is the most widely deployed database in the world.

**Pros:**
- Zero configuration (no server process)
- Single file database (trivial backup — copy the file)
- Excellent for prototyping and testing
- No network overhead (in-process)
- Included in Python standard library

**Cons:**
- File-level locking — only one writer at a time (catastrophic for concurrent ballot submission)
- No user/role system (anyone with file access has full control)
- No encryption extension in standard build (SQLCipher exists but is a separate fork)
- No triggers with network-accessible audit enforcement
- No connection pooling (single connection model)
- asyncpg is PostgreSQL-specific — aiosqlite exists but with limited features
- Not suitable for multi-service access (file locking across containers is undefined behaviour)

**Evaluation:**
SQLite fails R1 (concurrent writes), R2 (native encryption), R4 (user roles), R5 (asyncpg), and R6 (connection pooling). It was useful for Week 1 prototyping but is fundamentally unsuitable for a multi-service voting system. The file-locking limitation alone is disqualifying — during an active election, ballot submissions from concurrent voters would serialise into a single-writer queue.

---

## Decision

**Chosen Option:** PostgreSQL 15 (Option 1)

**Rationale:**
PostgreSQL is the only option that satisfies all nine requirements, particularly the three security-critical ones: native ballot encryption via pgcrypto (R2), audit log immutability via PL/pgSQL triggers (R3), and per-service user roles (R4). These features enforce security guarantees at the database layer, which is a stronger security posture than application-level enforcement alone — a compromised service cannot bypass database-level triggers or role restrictions.

**Key Factors:**

1. **Ballot encryption with pgcrypto (R2):** The `pgp_sym_encrypt(ballot_data, key)` function encrypts ballot content within the database using AES-256. This means ballot plaintext never exists in application memory longer than the request lifecycle, and encrypted ballots are stored at rest. Decryption requires the symmetric key, which is only available to the results-service at tally time.

2. **Audit log immutability via PL/pgSQL (R3):** A `BEFORE DELETE OR UPDATE` trigger on the `audit_log` table raises an exception for any attempt to modify or delete audit records. This enforcement is at the database level — even a compromised service with direct SQL access cannot tamper with audit history.

3. **Per-service user roles (R4):** Each microservice connects to PostgreSQL with a dedicated database user that has only the privileges required for its function. The auth-service user can read/write the `users` table but cannot access the `ballots` table. The voting-service user can insert ballots but cannot read them after submission. This implements least-privilege at the data layer.

4. **JSONB for election configuration (R7):** Election settings (candidate ordering, voting rules, custom fields) are stored as JSONB, allowing flexible configuration without schema changes. GIN indexes on JSONB columns enable efficient queries on election metadata.

---

## Consequences

### Positive Consequences

- **Defence in depth:** Security controls at both application and database layers. A compromised service cannot escalate its database privileges or tamper with audit logs.
- **Ballot confidentiality:** pgcrypto encryption ensures that even direct database access (e.g., a backup file) does not reveal ballot contents without the encryption key.
- **Audit integrity:** PL/pgSQL triggers make the audit log append-only at the database level — no application code can delete or modify audit records.
- **Flexible configuration:** JSONB columns allow election settings to evolve without schema migrations, supporting iterative development.
- **Async performance:** asyncpg's C-level protocol implementation provides the fastest possible Python-to-PostgreSQL communication path, complementing FastAPI's async architecture (ADR-001).

### Negative Consequences

- **Operational complexity:** PostgreSQL requires server process management, user creation, and extension installation — more operational overhead than SQLite.
- **Resource consumption:** ~50MB baseline memory per instance. Acceptable for the Kind cluster but more than SQLite's zero overhead.
- **Single point of failure:** One PostgreSQL instance serves all six microservices. If the database fails, all services fail. Mitigated by Kubernetes health probes and PVC-backed storage (data survives pod restarts).
- **Key management:** pgcrypto's symmetric encryption requires secure key distribution. The encryption key is stored as a Kubernetes Secret and injected as an environment variable — a compromise of the Secret compromises ballot confidentiality.

### Trade-offs Accepted

- **Complexity vs Security:** Accepted more complex database setup (users, roles, triggers, extensions) in exchange for database-level security enforcement. The additional setup is a one-time cost; the security benefits persist for the project's lifetime.
- **Resource usage vs Features:** Accepted ~50MB memory overhead in exchange for pgcrypto, PL/pgSQL, JSONB, and role-based access. SQLite would use less memory but provide none of these features.

---

## Implementation Notes

### Technical Details

The PostgreSQL instance runs as a single pod in the Kubernetes cluster with a PersistentVolumeClaim for data durability. The schema is initialised from `schema.sql` on first startup.

**Connection pool configuration (shared/database.py):**

```python
import asyncpg

class Database:
    _pool = None

    @classmethod
    async def get_pool(cls):
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=os.getenv("DB_HOST", "postgres-service"),
                port=int(os.getenv("DB_PORT", 5432)),
                database=os.getenv("DB_NAME", "uvote"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                min_size=2,
                max_size=20,
                command_timeout=30
            )
        return cls._pool
```

**Audit log immutability trigger (schema.sql):**

```sql
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log records cannot be modified or deleted';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_immutability
    BEFORE DELETE OR UPDATE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();
```

**Ballot encryption example:**

```sql
INSERT INTO ballots (election_id, voter_token_hash, encrypted_ballot)
VALUES (
    $1,
    $2,
    pgp_sym_encrypt($3::text, current_setting('app.encryption_key'))
);
```

### Configuration

- **PostgreSQL version:** 15 (official Docker image: `postgres:15`)
- **Extensions:** pgcrypto (`CREATE EXTENSION IF NOT EXISTS pgcrypto`)
- **Connection pool:** min_size=2, max_size=20, command_timeout=30s
- **Storage:** PersistentVolumeClaim (1Gi, ReadWriteOnce)

### Integration Points

- **All services:** Via shared/database.py asyncpg connection pool (ADR-001)
- **Auth service:** Users table (INSERT, SELECT, UPDATE) via `auth_user` role
- **Voting service:** Ballots table (INSERT only) via `voting_user` role
- **Results service:** Ballots table (SELECT with pgp_sym_decrypt) via `results_user` role
- **Election service:** Elections table (full CRUD) via `election_user` role
- **Kubernetes:** PostgreSQL Deployment + Service + PVC manifests (ADR-003)
- **Secrets:** DB credentials and encryption key stored as Kubernetes Secrets (ADR-003)

---

## Validation

### Success Criteria

- [x] PostgreSQL 15 running in Kind cluster with PVC-backed storage
- [x] pgcrypto extension installed and `pgp_sym_encrypt`/`pgp_sym_decrypt` functional
- [x] Audit log trigger prevents UPDATE and DELETE operations
- [x] Per-service database users created with least-privilege GRANT statements
- [x] asyncpg connection pool (min=2, max=20) operational across all services
- [x] JSONB columns used for election configuration with GIN indexes
- [x] Data survives pod restart (PVC persistence verified)

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Connection pool utilisation | <80% at peak | ~35% |
| Query latency (simple SELECT) | <10ms | ~3ms |
| Ballot encryption overhead | <20ms per ballot | ~8ms |
| Audit trigger enforcement | 100% block rate | 100% |
| Storage usage (1,000 voters) | <100MB | ~45MB |

### Review Date

End of Stage 2 (April 2026) — assess whether single-instance PostgreSQL meets scaling requirements or whether connection pooling with PgBouncer is needed.

---

## References

- [Investigation Log §3.2](../INVESTIGATION-LOG.md#32-database-investigation) — Full evaluation details
- [PostgreSQL 15 Documentation](https://www.postgresql.org/docs/15/)
- [pgcrypto Documentation](https://www.postgresql.org/docs/15/pgcrypto.html)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [ADR-001](ADR-001-python-fastapi-backend.md) — FastAPI backend (asyncpg dependency)
- [ADR-003](ADR-003-kubernetes-platform.md) — Kubernetes platform (PVC, Secrets)
- [ADR-005](ADR-005-token-based-voting.md) — Token-based voting (ballot storage)

## Notes

The migration from SQLite to PostgreSQL occurred in Week 2 (Iteration 1). The schema.sql file contains all table definitions, triggers, indexes, and per-service user GRANT statements. Schema changes are applied manually via `psql` during development — a formal migration tool (Alembic) may be introduced in Stage 2 if schema churn increases.
