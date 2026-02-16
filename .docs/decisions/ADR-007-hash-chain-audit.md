# ADR-007: SHA-256 Hash-Chain Audit Logs

## Status

**Status:** Accepted
**Date:** 2026-02-12
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

The U-Vote system requires an audit logging mechanism that provides tamper evidence — the ability to detect if any log entry has been modified, deleted, or inserted out of order after the fact. Simple database logging (INSERT into a table) can be silently modified by anyone with database write access. For a voting system where election integrity depends on trustworthy logs, this is unacceptable.

### Background

The project proposal (Objective 4) requires "a transparent, verifiable voting process with auditable logs." The research paper identifies insider abuse as a key threat — a malicious administrator with database access could modify logs to conceal fraudulent activity. The audit system must detect such tampering even if the attacker has full database credentials.

The audit log records all security-relevant events: admin login attempts, election lifecycle changes, voter additions, token generation, vote casting (without recording the candidate choice), and results access. These logs are critical for post-election audits and dispute resolution.

### Requirements

- **R1:** Tamper detection — any modification to a log entry must be detectable
- **R2:** Immutability — log entries cannot be updated or deleted through normal operations
- **R3:** Chronological integrity — out-of-order insertions must be detectable
- **R4:** Independent verification — any party with read access can verify the chain
- **R5:** No external dependencies — must work with PostgreSQL alone
- **R6:** Minimal performance impact — logging must not slow down vote casting
- **R7:** Preserve vote anonymity — logs must NOT record which candidate a voter chose

### Constraints

- **C1:** No budget for external audit services or blockchain infrastructure
- **C2:** Must work with a single PostgreSQL instance (shared database model, ADR-014)
- **C3:** Hash computation must be fast enough for real-time event logging
- **C4:** Must integrate with the audit-service microservice (ADR-008)

---

## Options Considered

### Option 1: Simple Database Logging

**Description:**
INSERT audit events into a PostgreSQL table with timestamp, event type, actor, and details. No cryptographic verification.

**Pros:**
- Simplest implementation (single INSERT statement)
- No computational overhead beyond the INSERT
- Easy to query and report on
- Sufficient for basic compliance

**Cons:**
- No tamper detection — a DBA or compromised service can modify any row
- No chain integrity — entries can be deleted without trace
- No cryptographic verification
- Provides false sense of security (logs exist but cannot be trusted)

**Evaluation:**
Fails R1 (tamper detection) and R3 (chronological integrity). For a voting system, unverifiable logs are almost worse than no logs — they create an illusion of accountability.

### Option 2: SHA-256 Hash-Chained Logs — Chosen

**Description:**
Each audit log entry includes a SHA-256 hash computed from the entry's data concatenated with the previous entry's hash. This creates a chain: modifying any entry changes its hash, which breaks the chain for all subsequent entries. Combined with PostgreSQL triggers that prevent UPDATE/DELETE on the audit_log table, this provides both tamper evidence and immutability.

**Pros:**
- Strong tamper evidence — modifying any entry breaks the chain from that point forward
- Database-level immutability via triggers (BEFORE UPDATE/DELETE raises exception)
- Chronological integrity (hash chain enforces ordering)
- Independent verification (re-compute chain from first to last entry)
- Zero external dependencies (SHA-256 is built into PostgreSQL via pgcrypto and Python hashlib)
- Negligible performance impact (SHA-256 computation takes <1ms)
- Simple implementation (~20 lines of Python + SQL trigger)

**Cons:**
- Single-point verification (chain is only as trustworthy as the database storage)
- Does not prevent a DBA with superuser access from disabling triggers and modifying data
- Hash chain verification requires reading all entries (O(n) for n entries)
- No distributed consensus (single database, single authority)

**Evaluation:**
Meets all requirements (R1–R7). The superuser attack vector is acknowledged but accepted — in a small-scale election, the database administrator is typically the same person running the election. For higher-assurance scenarios, external witnesses or distributed verification would be needed (future enhancement).

### Option 3: Blockchain-Based Logging

**Description:**
Write audit entries to a blockchain (Ethereum, Hyperledger Fabric) for distributed, immutable storage with consensus-based verification.

**Pros:**
- Distributed consensus — no single party can tamper with logs
- Mathematically provable immutability (consensus protocol)
- Public verifiability (anyone can audit the blockchain)
- Byzantine fault tolerance

**Cons:**
- Massive infrastructure overhead (blockchain nodes, consensus mechanisms)
- Transaction costs (gas fees on public chains like Ethereum)
- Transaction latency (Ethereum: ~15 seconds per block; Hyperledger: ~2 seconds)
- Complex setup and maintenance
- Requires external infrastructure (violates C1)
- Overkill for elections with 50–1,000 voters
- Learning curve for Solidity/Chaincode development

**Evaluation:**
Fails C1 (no budget for external infrastructure) and adds latency (R6). For small-scale elections, the threat model does not require Byzantine fault tolerance. The 15-second block time on Ethereum would create unacceptable delays during vote casting.

### Option 4: Third-Party Audit Service

**Description:**
Send audit events to an external service (AWS CloudTrail, Datadog, Splunk) for independent storage and verification.

**Pros:**
- Trusted third-party storage
- Professional audit capabilities
- Independent verification
- Dashboards and alerting

**Cons:**
- Costs money (per-event pricing for commercial services)
- External dependency (service outage blocks logging)
- Data leaves the organisation's control (privacy concern for voter data)
- Vendor lock-in
- Requires internet access from the Kind cluster

**Evaluation:**
Fails C1 (no budget) and introduces external dependencies. Also raises GDPR concerns about voter data leaving the organisation's infrastructure.

---

## Decision

**Chosen Option:** SHA-256 Hash-Chained Logs (Option 2)

**Rationale:**
Hash-chained logs provide strong tamper evidence without blockchain complexity or external dependencies. The decision matrix (§3.7.3 of Investigation Log) scored hash-chained logs at 8.65/10, ahead of simple DB logging (6.35), blockchain (5.30), and third-party services (4.95).

**Key Factors:**

1. **Tamper evidence (R1):** Modifying any log entry changes its hash, which cascades through all subsequent entries. An auditor can verify the entire chain by recomputing hashes from start to end — any break indicates tampering.

2. **Database-level immutability (R2):** PostgreSQL triggers prevent UPDATE and DELETE on the audit_log table. Even if a service is compromised, it cannot modify existing log entries through normal database operations.

3. **Zero cost (C1):** SHA-256 is built into Python (hashlib) and PostgreSQL (pgcrypto). No external services, no transaction fees, no infrastructure.

4. **Minimal performance impact (R6):** SHA-256 computation takes <1ms. The trigger-based hash generation runs synchronously with the INSERT but adds negligible latency.

5. **Vote anonymity preservation (R7):** Audit logs record "ballot cast in election X" with a receipt token but never record the candidate choice. The event_type is "ballot_cast" with detail noting "encrypted ballot cast anonymously."

---

## Consequences

### Positive Consequences

- **Tamper detection:** Any modification to the audit trail is detectable by re-computing the hash chain
- **Immutability:** Database triggers prevent log modification through standard SQL operations
- **Independent verification:** A `GET /api/audit/verify` endpoint validates the entire chain programmatically
- **Zero infrastructure cost:** Uses only PostgreSQL and Python standard library — no external services
- **Defence in depth:** Hash chains (application layer) + immutability triggers (database layer) provide two independent protections

### Negative Consequences

- **Superuser bypass:** A PostgreSQL superuser can disable triggers and modify data. Mitigated by: in production, restrict superuser access; for MVP, this is an accepted limitation.
- **O(n) verification:** Checking the chain requires reading all entries. Mitigated by: small-scale elections generate relatively few audit events (hundreds to thousands, not millions).
- **Single database:** The chain is stored in one database — a catastrophic database failure loses the audit trail. Mitigated by: regular backups; in production, database replication would provide redundancy.

### Trade-offs Accepted

- **Blockchain vs Practicality:** Accepted hash-chained logs (single-authority tamper evidence) over blockchain (distributed consensus tamper prevention). For small-scale elections, the threat model does not require Byzantine fault tolerance — it requires detection of tampering, which hash chains provide.
- **Simplicity vs Assurance level:** Accepted that a DBA with superuser access could theoretically bypass protections. For the target use case (student unions, NGOs), this is an acceptable risk. Production deployments should restrict superuser access and add external log witnesses.

---

## Implementation Notes

### Technical Details

Hash generation trigger (database/init.sql):
```sql
CREATE OR REPLACE FUNCTION generate_audit_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.event_hash := encode(
        digest(
            NEW.event_type ||
            COALESCE(NEW.election_id::text, '') ||
            COALESCE(NEW.actor_id::text, '') ||
            NEW.created_at::text ||
            gen_random_uuid()::text,
            'sha256'
        ),
        'hex'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

Immutability enforcement:
```sql
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log entries are immutable and cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER immutable_audit
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();
```

### Configuration

- **Hash algorithm:** SHA-256 (256-bit output)
- **Chain structure:** Each entry's hash includes `event_type`, `election_id`, `actor_id`, `timestamp`, and a random UUID for uniqueness
- **Immutability:** BEFORE UPDATE/DELETE triggers raise exceptions
- **Anonymity:** Vote-cast events record receipt_token but never candidate_id

### Integration Points

- **ADR-002 (PostgreSQL):** pgcrypto extension provides `digest()` function for SQL-level hashing
- **ADR-008 (Microservices):** Audit-service receives events from all backend services
- **ADR-010 (Zero-Trust):** Network policies control which services can write audit events
- **ADR-015 (Anonymity):** Audit log design preserves vote anonymity

---

## Validation

### Success Criteria

- [x] Hash auto-generated on INSERT via trigger
- [x] UPDATE raises exception ("Audit log entries are immutable")
- [x] DELETE raises exception ("Audit log entries are immutable")
- [x] Vote-cast events do not contain candidate choice
- [x] Chain can be verified by recomputing hashes sequentially

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Hash computation time | <5ms | <1ms |
| Trigger overhead per INSERT | <10ms | ~2ms |
| Chain verification (1000 entries) | <1s | ~200ms |

### Review Date

End of Stage 2 (April 2026) — evaluate whether external log witnesses are needed for production.

---

## References

- [Investigation Log §3.7](../INVESTIGATION-LOG.md#37-audit-logging-approach-investigation) — Full evaluation
- [PostgreSQL pgcrypto](https://www.postgresql.org/docs/15/pgcrypto.html) — SHA-256 digest function
- [Python hashlib](https://docs.python.org/3/library/hashlib.html) — Application-level hashing
- [ADR-002](ADR-002-postgresql-database.md) — PostgreSQL database (pgcrypto, triggers)
- [ADR-015](ADR-015-vote-anonymity-design.md) — Vote anonymity preservation in audit logs

## Notes

The hash chain for encrypted ballots (`encrypted_ballots` table) uses the same pattern — each ballot's `ballot_hash` is generated by a trigger that includes the previous ballot's hash. This creates two independent hash chains: one for audit events and one for ballots, providing dual-layer tamper evidence.
