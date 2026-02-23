# ADR-015: Blind Ballot Token Anonymity

## Status

**Status:** Accepted
**Date:** 2026-02-16
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

An election system must simultaneously satisfy two contradictory requirements:

1. **Accountability:** Prove that each voter voted at most once (prevent double-voting)
2. **Anonymity:** Ensure that nobody — not even the server operator — can determine how any voter voted (ballot secrecy)

These requirements are inherently in tension. Accountability requires linking a voter's identity to the act of voting. Anonymity requires severing any link between a voter's identity and their ballot choice. The system must resolve this tension through architectural design.

### Background

The project research paper identifies three categories of identity fraud. The anonymity mechanism must protect against the third category: insider abuse. Even if an administrator has full database access, they should not be able to determine which candidate any specific voter chose.

Traditional online voting systems often fail this test. Systems that store `voter_id` alongside the vote choice provide zero anonymity. Systems that use session tokens linked to voter accounts can be correlated through timing analysis. The challenge is to create a cryptographic gap between identity verification and ballot casting that cannot be bridged after the fact.

### Requirements

- **R1:** Server operator cannot link voter identity to ballot choice
- **R2:** Each voter can vote at most once (double-voting prevented)
- **R3:** Voters can verify their ballot was recorded (receipt)
- **R4:** Votes are encrypted at rest (database compromise doesn't reveal choices)
- **R5:** The anonymity mechanism must work without external infrastructure
- **R6:** Implementation must be understandable and auditable (no black-box cryptography)

### Constraints

- **C1:** Single PostgreSQL database (shared model, ADR-014)
- **C2:** No external cryptographic infrastructure (no HSMs, no distributed key servers)
- **C3:** Must be implementable in Python with standard libraries
- **C4:** Must not significantly impact voting latency (<500ms total)

---

## Options Considered

### Option 1: Voter-Linked Ballots

**Description:**
Store `voter_id` as a foreign key in the votes/ballots table alongside the vote choice.

```sql
CREATE TABLE votes (
    id SERIAL PRIMARY KEY,
    voter_id INTEGER REFERENCES voters(id),  -- IDENTITY LINKED
    candidate_id INTEGER,
    cast_at TIMESTAMP
);
```

**Pros:**
- Simplest implementation
- Easy to audit (can verify who voted for whom)
- Easy to query results

**Cons:**
- Zero anonymity — anyone with database read access can see every voter's choice
- Administrator can determine how each person voted
- Voters may self-censor if they know their vote is not secret
- Fundamentally inappropriate for any election system

**Evaluation:**
Fails R1 completely. This is not an option for any legitimate voting system.

### Option 2: Blind Ballot Tokens — Chosen

**Description:**
Separate the identity verification process from the ballot casting process using a cryptographic intermediary — the "blind ballot token." The protocol works as follows:

```
Phase 1: IDENTITY VERIFICATION (identity-linked)
  1. Voter clicks email link with voting_token
  2. Auth-service validates the token (linked to voter_id)
  3. Voter verifies identity via DOB (MFA)

Phase 2: THE ANONYMITY BRIDGE
  4. Auth-service marks voter.has_voted = TRUE
  5. Auth-service generates a fresh random ballot_token
  6. Auth-service stores ballot_token with ONLY election_id (no voter_id)
  7. Auth-service does NOT record which voter received which ballot_token
  8. Auth-service returns the ballot_token to the voter's browser

Phase 3: ANONYMOUS BALLOT CASTING (identity-separated)
  9. Voter submits vote using the ballot_token (no voting_token, no voter_id)
  10. Voting-service validates the ballot_token
  11. Voting-service encrypts the vote choice with pgp_sym_encrypt
  12. Encrypted ballot stored with NO voter_id, NO ballot_token reference
  13. Voter receives a receipt_token for verification
```

After step 7, there is NO record in the database linking the voter_id to the ballot_token. The auth-service knows that voter X received A ballot token, but not which one. The voting-service knows that ballot_token Y was used to cast a vote, but not which voter used it. The link is severed.

**Pros:**
- Server operator cannot link voter to ballot (even with full DB access)
- Double-voting prevented (voter.has_voted flag + single-use ballot token)
- Receipt tokens allow voters to verify their ballot was recorded
- Encrypted ballots protect against database compromise
- No external infrastructure required
- Auditable implementation (Python + PostgreSQL)
- Based on established cryptographic principle (blind tokens, cf. Chaum 1983)

**Cons:**
- More complex than voter-linked ballots (3-phase protocol)
- If auth-service is compromised at the exact moment of token issuance, an attacker could log the voter-to-ballot mapping (mitigated by the fact that the code explicitly does not create this mapping)
- Voters cannot change their vote after casting (ballot token is used)

**Evaluation:**
Meets all requirements (R1–R6). The key insight is that the ballot_token is generated from `secrets.token_urlsafe(32)` — pure cryptographic randomness not derived from any voter attribute. The auth-service code explicitly avoids recording the mapping.

### Option 3: Homomorphic Encryption

**Description:**
Encrypt each vote such that tallying can be performed on encrypted data without decrypting individual votes.

**Pros:**
- Mathematically strongest anonymity guarantee
- Votes never decrypted individually
- Academic gold standard

**Cons:**
- Extremely complex implementation
- No mature Python libraries for practical homomorphic encryption
- Massive performance overhead (operations on encrypted data are 10,000x slower)
- Would exceed the project timeline for implementation alone
- Difficult to audit (requires deep cryptographic expertise)
- Academic research territory, not production-ready

**Evaluation:**
Fails C3 (implementable with standard libraries), C4 (performance), and R6 (auditable). Homomorphic encryption is the theoretical ideal but is completely impractical for an MVP.

### Option 4: Mixnets (Mix Networks)

**Description:**
Route votes through multiple independent servers that shuffle and re-encrypt them, making it impossible to trace which input corresponds to which output.

**Pros:**
- Strong anonymity (shuffling breaks correlation)
- Used in some national e-voting systems (Switzerland, Estonia)
- Well-studied in academic literature

**Cons:**
- Requires multiple independent servers (trust distributed across operators)
- Complex protocol (re-encryption, shuffling, zero-knowledge proofs)
- Significant infrastructure overhead
- Introduces latency (multiple server hops)
- Overkill for elections with 50–1,000 voters
- Fails C2 (requires external infrastructure)

**Evaluation:**
Fails C2 (no external infrastructure budget). Mixnets are designed for national-scale elections with millions of voters and multiple election authorities — completely inappropriate for student council elections.

---

## Decision

**Chosen Option:** Blind Ballot Tokens (Option 2)

**Rationale:**
Blind ballot tokens achieve strong anonymity (even the server operator cannot link voter to ballot) with moderate implementation complexity and zero external dependencies. The approach is based on the established cryptographic concept of blind tokens (Chaum, 1983) adapted for a practical web voting system.

**Key Factors:**

1. **Irreversible identity-ballot separation (R1):** The critical code in auth-service:
   ```python
   # THE ANONYMITY BRIDGE
   # Step 1: Mark voter as having voted (accountability)
   await conn.execute("UPDATE voters SET has_voted = TRUE WHERE id = $1", voter_id)

   # Step 2: Mark voting token as used
   await conn.execute("UPDATE voting_tokens SET is_used = TRUE WHERE id = $1", token_id)

   # Step 3: Generate blind ballot token (NO voter_id stored)
   ballot_token = generate_blind_ballot_token()  # Pure randomness
   await conn.execute(
       "INSERT INTO blind_tokens (ballot_token, election_id) VALUES ($1, $2)",
       ballot_token, election_id
   )
   # NO INSERT that links voter_id to ballot_token
   ```
   After this transaction commits, the link between voter and ballot is permanently severed.

2. **Double-voting prevention (R2):** The `has_voted` flag on the voters table and the single-use ballot_token prevent any voter from casting more than one ballot.

3. **Encryption at rest (R4):** Votes are encrypted using `pgp_sym_encrypt` in PostgreSQL before storage:
   ```sql
   INSERT INTO encrypted_ballots (election_id, encrypted_vote, ...)
   VALUES ($1, pgp_sym_encrypt($2::text, $3), ...)
   ```
   The encryption key is stored in the elections table and used only during tallying.

4. **Receipt verification (R3):** Each ballot generates a `receipt_token` that voters can use to verify their ballot was recorded. The receipt contains a `ballot_hash` but not the vote choice — verification without revealing the vote.

---

## Consequences

### Positive Consequences

- **Strong anonymity:** Even a DBA with full SELECT access to all tables cannot link a voter to their ballot choice. The `blind_tokens` table has NO `voter_id` column. The `encrypted_ballots` table has NO `voter_id` column.
- **Accountability maintained:** The `voters.has_voted` flag proves who voted; it just cannot prove how they voted.
- **Encryption at rest:** Even if the database is breached, individual vote choices are encrypted.
- **Verifiable:** Receipt tokens allow voters to confirm their ballot was recorded.
- **Auditable code:** The anonymity mechanism is ~50 lines of Python, not a black-box cryptographic library.

### Negative Consequences

- **Irreversible:** Once the ballot is cast, the voter cannot change their vote (the ballot token is consumed). Mitigated by: confirmation step before submission.
- **Trust in auth-service:** The auth-service sees both the voter identity and the ballot token during the issuance moment. A compromised auth-service running modified code could log this mapping. Mitigated by: code review, deployment automation (prevents ad-hoc code changes), audit logging of the issuance event.
- **Single-server limitation:** Unlike mixnets, the anonymity relies on the server not recording the mapping. Mitigated by: open-source code, audit trail, future enhancement to Chaum blind signatures.

### Trade-offs Accepted

- **Blind tokens vs Homomorphic encryption:** Accepted a pragmatic anonymity mechanism over a mathematically perfect one. Blind tokens are implementable in a 2-semester project; homomorphic encryption is not.
- **Trust in code vs Trust in mathematics:** The anonymity guarantee depends on the code not logging the voter-to-ballot mapping. This is a weaker guarantee than mathematical proofs (homomorphic encryption, mixnets), but is auditable and practical.
- **Simplicity vs Strength:** A future enhancement could upgrade to RSA blind signatures (Chaum 1983), where the voter blinds a nonce, the server signs it, and the voter unblinds to obtain a signature the server has never seen in the clear. This would provide mathematical (not just architectural) anonymity.

---

## Implementation Notes

### Technical Details

Database schema enforcing anonymity:
```sql
-- blind_tokens: NO voter_id, NO voting_token reference
CREATE TABLE blind_tokens (
    id           SERIAL PRIMARY KEY,
    ballot_token VARCHAR(255) UNIQUE NOT NULL,
    election_id  INTEGER REFERENCES elections(id),
    is_used      BOOLEAN DEFAULT FALSE,
    issued_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_at      TIMESTAMP
    -- NO voter_id (this is what makes the vote anonymous)
);

-- encrypted_ballots: NO voter_id, NO user_id, NO ballot_token_id
CREATE TABLE encrypted_ballots (
    id             SERIAL PRIMARY KEY,
    election_id    INTEGER REFERENCES elections(id),
    encrypted_vote BYTEA NOT NULL,         -- pgp_sym_encrypt
    ballot_hash    VARCHAR(255) NOT NULL,  -- SHA-256 auto-generated
    previous_hash  VARCHAR(255),           -- Hash chain
    receipt_token  VARCHAR(255) UNIQUE NOT NULL,
    cast_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    -- NO voter_id, NO user_id, NO ballot_token_id
);
```

The anonymity is enforced at the **schema level** — the columns simply do not exist. No application bug can accidentally store the voter-ballot link because there is no column to store it in.

### Configuration

- **Ballot token entropy:** 256 bits (`secrets.token_urlsafe(32)`)
- **Vote encryption:** `pgp_sym_encrypt` (PostgreSQL pgcrypto extension)
- **Encryption key:** Per-election, generated with `secrets.token_urlsafe(32)`
- **Receipt token:** 192 bits (`secrets.token_urlsafe(24)`)
- **Ballot immutability:** BEFORE UPDATE/DELETE trigger raises exception

### Integration Points

- **ADR-002 (PostgreSQL):** pgcrypto extension for encryption
- **ADR-005 (Token Auth):** Voting token initiates the identity verification phase
- **ADR-007 (Audit):** Audit logs record "ballot issued" without linking voter to ballot
- **ADR-013 (Separation):** Auth-service (identity) and voting-service (ballots) are separate services
- **ADR-014 (DB Users):** Voting-service user cannot access voters table

---

## Validation

### Success Criteria

- [x] `blind_tokens` table has NO `voter_id` column
- [x] `encrypted_ballots` table has NO `voter_id` column
- [x] Auth-service code does not log voter-to-ballot-token mapping
- [x] Votes encrypted with `pgp_sym_encrypt` before storage
- [x] Ballot immutability trigger prevents UPDATE/DELETE
- [x] Receipt token allows voter to verify ballot was recorded
- [x] Double-voting prevented by `has_voted` flag and single-use tokens

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Ballot token entropy | ≥128 bits | 256 bits |
| Vote encryption | Yes (at rest) | Yes (pgp_sym_encrypt) |
| Voter-ballot link in DB | None | None (columns don't exist) |
| Ballot immutability | Trigger-enforced | Yes (BEFORE UPDATE/DELETE) |
| Receipt verification | Public endpoint | Yes (GET /receipt/{token}) |

### Review Date

End of Stage 2 (April 2026) — evaluate upgrading to RSA blind signatures for mathematical anonymity guarantee.

---

## References

- [Investigation Log §5.3](../INVESTIGATION-LOG.md#53-vote-anonymity-design-investigation) — Full analysis
- Chaum, D. (1983). "Blind Signatures for Untraceable Payments." Advances in Cryptology.
- [PostgreSQL pgcrypto](https://www.postgresql.org/docs/15/pgcrypto.html) — pgp_sym_encrypt documentation
- [Python secrets module](https://docs.python.org/3/library/secrets.html) — CSPRNG for token generation
- [ADR-005](ADR-005-token-based-voting.md) — Voter token authentication (Phase 1)
- [ADR-007](ADR-007-hash-chain-audit.md) — Audit logging preserves anonymity
- [ADR-013](ADR-013-service-separation-strategy.md) — Auth/voting service separation

## Notes

The anonymity architecture is the most security-critical design decision in the project. The code comments in `auth-service/app.py` (lines 246–342) extensively document the anonymity contract and the "anonymity bridge" protocol. This section should be reviewed carefully during any code changes to the auth-service's ballot-token issuance logic.
