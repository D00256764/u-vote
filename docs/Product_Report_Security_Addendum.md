# Product Security Addendum

This addendum extracts the product-facing security assurances for the Product report. It is designed to give assessors the key security controls, threat mitigations, and test evidence in a concise form.

## Key Product Security Guarantees
- Vote immutability: DB triggers prevent UPDATE/DELETE on `votes` table.
- Audit tamper detection: `audit_logs` are hash-chained using SHA-256; entries are append-only.
- Identity-ballot separation: voting tokens separate voter identity from vote records; votes do not record `voter_id`.
- Per-service least-privilege DB users: six dedicated users with table-level and operation-level grants.
- Zero-trust network posture: default-deny network policy (Kubernetes) enforced by Calico.

## How the user-facing product is protected
- Voters authenticate only via single-use cryptographic tokens that are consumed atomically in the DB transaction that inserts the vote.
- Admins authenticate via JWTs with expiry; administrative actions are audited.
- Voting process returns a confirmation hash to the voter (receipt) enabling later verification without exposing voter identity.

## Test summary (product-impacting)
- Vote insertion and token consumption atomicity validated via integration tests that simulate concurrent token use.
- Hash chain verification tests run to confirm tamper detection logic.
- Network policy tests ensure that the frontend (public) cannot access the database directly.

## References
- `docs/NETWORK-SECURITY.md`
- `docs/ADR-002-PostgreSQL-Database.md`
- `docs/INVESTIGATION-LOG.md`

(Reference this addendum in `docs/Product_Report_Final.md` under "Security and Integrity".)
