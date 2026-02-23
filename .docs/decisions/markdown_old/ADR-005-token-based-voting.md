# ADR-005: Token-Based Voter Authentication

## Status

**Status:** Accepted
**Date:** 2026-02-11
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

Voters in small-scale elections (student councils, NGO boards, community groups) are one-time users who need to cast a single vote and may never use the system again. The authentication mechanism must balance security (only legitimate voters can vote, each voter votes once) with usability (minimum friction to complete the voting action). Forced account creation, password management, or multi-step verification would cause voter abandonment in the target user groups.

### Background

The project proposal identifies identity fraud as one of three critical barriers to election integrity. Three specific fraud categories were researched:

1. **Impersonation:** Attacker votes using a legitimate voter's identity
2. **Synthetic identity fraud:** Fake voters created with fabricated credentials
3. **Account takeover:** Attacker gains access to a real voter's existing account

Traditional password-based authentication is vulnerable to all three — credentials can be phished, shared, or brute-forced. For one-time voters who will never log in again, passwords add friction without proportional security benefit.

### Requirements

- **R1:** Each voter must be uniquely identifiable (prevent duplicate voting)
- **R2:** Only voters registered by the admin can vote (prevent unauthorised access)
- **R3:** Tokens must be cryptographically secure (not guessable or predictable)
- **R4:** Tokens must be single-use (prevent vote replay)
- **R5:** Tokens must expire after a reasonable period (prevent indefinite access)
- **R6:** Minimum user friction (ideally 1 click to begin voting)
- **R7:** No voter account creation required
- **R8:** Compatible with multi-factor identity verification (DOB check)

### Constraints

- **C1:** Target users have diverse digital literacy (students to elderly residents)
- **C2:** Voters access the system via email links on mobile devices
- **C3:** No budget for SMS-based OTP (per-message costs)
- **C4:** System must work without OAuth provider dependencies (self-contained)

---

## Options Considered

### Option 1: Password-Based (Create Account)

**Description:**
Voters register accounts with email and password, then log in to vote.

**Pros:**
- Traditional, well-understood authentication model
- Voters can log in again to verify their vote
- Strong authentication (knowledge factor)

**Cons:**
- High friction: register → verify email → set password → log in → vote (5+ steps)
- Voters must remember credentials for a one-time action
- Password reset flow needed (additional complexity)
- Credential stuffing vulnerability (reused passwords)
- Most voters would abandon before completing registration
- No protection against shared credentials

**Evaluation:**
Fails R6 (minimum friction) and R7 (no account creation). Research on voter behaviour in online elections shows that each additional step reduces participation by 10–15%. A 5-step process would result in significant voter drop-off.

### Option 2: OAuth 2.0 (Sign in with Google/Microsoft)

**Description:**
Delegate authentication to an external identity provider (Google, Microsoft, GitHub).

**Pros:**
- Low friction for users with existing Google/Microsoft accounts
- Strong authentication (delegated to trusted provider)
- No password management needed

**Cons:**
- Excludes users without Google/Microsoft accounts
- Privacy concerns (third-party tracking of voting behaviour)
- Requires internet access to OAuth provider during voting
- External dependency (OAuth provider outage blocks voting)
- Cannot restrict to only registered voters (anyone with Google account could attempt to vote)
- Does not satisfy C4 (self-contained system)

**Evaluation:**
Fails C4 (self-contained) and creates a single point of failure (external provider). Also fails to restrict access to registered voters only — additional voter-list validation would be needed after OAuth login.

### Option 3: OTP via SMS/Email

**Description:**
System sends a one-time password (OTP) to the voter's registered email or phone number. Voter enters OTP to authenticate.

**Pros:**
- Moderate friction (receive OTP → enter OTP → vote)
- No permanent credentials to manage
- Proves control of registered communication channel

**Cons:**
- SMS costs money per message (C3 constraint)
- Email OTP delivery can be delayed (spam filters, server queues)
- OTP entry is an additional step that can fail (typos, expiry)
- Requires the voter to switch between email and browser
- Email OTP is essentially a less convenient version of a clickable link

**Evaluation:**
Meets R1–R5 but scores lower on R6 (minimum friction). If the voter must receive a code and manually enter it, why not just make the code part of a clickable URL? This insight led to Option 4.

### Option 4: Cryptographic Token URLs (One-Time Links) — Chosen

**Description:**
The admin imports voters (via CSV). The system generates a unique cryptographic token for each voter and sends an email containing a voting URL: `https://evote.com/vote?token=<256-bit-token>`. The voter clicks the link, is presented with the ballot, and votes. The token is invalidated after use.

**Pros:**
- Minimum possible friction: click email link → see ballot → vote → done (1 click to start)
- No account creation, no password, no OTP entry
- Cryptographically secure (256-bit tokens = 2^256 possibilities)
- Single-use enforcement (token marked as used in database)
- Time-limited (7-day expiry prevents indefinite access)
- Only registered voters receive tokens (admin controls voter list)
- Compatible with MFA (DOB verification after token validation)
- Self-contained (no external OAuth providers)
- Works on any device with email access

**Cons:**
- Email delivery depends on SMTP reliability
- Token URL in email could be forwarded to another person
- No voter-initiated password recovery (token must be reissued by admin)
- Voter cannot independently verify their vote after casting (mitigated by receipt tokens)

**Evaluation:**
Meets all requirements (R1–R8) and all constraints (C1–C4). The email forwarding risk is mitigated by MFA (DOB verification) — even if a token is forwarded, the recipient must know the voter's date of birth to proceed.

---

## Decision

**Chosen Option:** Cryptographic Token URLs (Option 4)

**Rationale:**
Token-based URLs provide the optimal balance of security and usability for one-time voters. The approach eliminates the most common cause of voter drop-off (account creation/password management) while maintaining strong security through cryptographic entropy, single-use enforcement, and time-limited validity.

**Key Factors:**

1. **Minimum friction (R6):** One click from email to ballot. Research from Estonia's i-Voting system and UK parliamentary e-petitions shows that single-click access maximises participation rates.

2. **Cryptographic security (R3):** `secrets.token_urlsafe(32)` generates 256-bit tokens using the OS CSPRNG. At 1 billion guesses per second, the expected time to find a valid token exceeds 10^57 years — far longer than the 7-day validity window.

3. **MFA compatibility (R8):** The token validates the voter's email channel; DOB verification provides a second factor. This two-step process (token + DOB) addresses the impersonation threat without adding user-visible friction.

4. **Identity-ballot separation:** Combined with blind ballot tokens (ADR-015), the voting_token authenticates the voter's identity, but the actual ballot is cast with an anonymous ballot_token that cannot be linked back.

---

## Consequences

### Positive Consequences

- **High participation:** Minimum friction encourages voter turnout, directly addressing the project's goal of inclusive voting
- **No credential management:** System stores no voter passwords — eliminates credential stuffing, password reuse, and password reset flows
- **Strong entropy:** 256-bit tokens are computationally infeasible to brute-force
- **Admin control:** Only voters explicitly added by the admin receive tokens — prevents unauthorised voting
- **Audit trail:** Token usage is logged (timestamp, election) without recording vote choice

### Negative Consequences

- **Email dependency:** Token delivery depends on email infrastructure. Mitigated by: retry logic in email service, admin can resend individual tokens, 7-day validity window accommodates delivery delays.
- **Token forwarding risk:** A voter could forward their email to someone else. Mitigated by: MFA verification (DOB check), single-use enforcement, audit logging.
- **No self-service recovery:** If a voter doesn't receive the email, they must contact the admin for reissuance. Mitigated by: admin dashboard shows token status, one-click resend functionality.

### Trade-offs Accepted

- **Security vs UX:** Chose minimum-friction token URLs over higher-friction password authentication. The security gap is closed by 256-bit entropy + single-use + MFA, making the effective security comparable to or better than password-based systems (no credential reuse, no phishing of permanent credentials).
- **Simplicity vs Feature richness:** Voters cannot self-recover a lost token. Accepted because the admin interface provides easy token reissuance, and the 7-day validity window means most voters will use their token promptly.

---

## Implementation Notes

### Technical Details

Token generation:
```python
# shared/security.py
import secrets
from datetime import datetime, timedelta

def generate_voting_token(length: int = 32) -> str:
    """Generate a 256-bit URL-safe token."""
    return secrets.token_urlsafe(length)

def generate_token_expiry(hours: int = 168) -> datetime:
    """Default: 7 days (168 hours)."""
    return datetime.now() + timedelta(hours=hours)
```

Token validation (auth-service):
```python
@app.get("/tokens/{token}/validate")
async def validate_voting_token(token: str):
    row = await conn.fetchrow(
        "SELECT ... FROM voting_tokens vt "
        "JOIN elections e ON e.id = vt.election_id "
        "WHERE vt.token = $1", token
    )
    # Check: exists, not used, not expired, election is open
```

### Configuration

- **Token length:** 32 bytes = 256 bits of entropy (43 URL-safe characters)
- **Token expiry:** 7 days (configurable via environment variable)
- **Single-use:** `is_used` boolean + `used_at` timestamp in `voting_tokens` table
- **MFA:** DOB verification via `voter_mfa` table after token validation

### Integration Points

- **ADR-006 (JWT):** Admin authentication is separate (JWT for admins, tokens for voters)
- **ADR-015 (Anonymity):** Voting token validates identity; blind ballot token provides anonymity
- **ADR-007 (Audit):** Token usage is logged in `audit_log` table

---

## Validation

### Success Criteria

- [x] Tokens generated with `secrets.token_urlsafe(32)` (256-bit CSPRNG)
- [x] Single-use enforcement (second use returns "Token already used")
- [x] Expiry enforcement (expired tokens return "Token expired")
- [x] Election status check (tokens only valid for "open" elections)
- [x] MFA integration (DOB verification required after token validation)
- [x] Admin can resend tokens for individual voters

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Token entropy | ≥128 bits | 256 bits |
| Click-to-ballot time | <3 seconds | ~1.5 seconds |
| Token validation latency | <100ms | ~25ms |
| False rejection rate | 0% | 0% (deterministic validation) |

### Review Date

End of Stage 2 (April 2026) — assess whether DOB-based MFA is sufficient or additional factors are needed.

---

## References

- [Investigation Log §3.6](../INVESTIGATION-LOG.md#36-authentication-strategy-investigation) — Full evaluation
- [Python secrets module](https://docs.python.org/3/library/secrets.html) — CSPRNG documentation
- Estonian i-Voting System — Token-based invitation model
- [ADR-006](ADR-006-jwt-authentication.md) — Admin authentication (JWT)
- [ADR-015](ADR-015-vote-anonymity-design.md) — Blind ballot token anonymity

## Notes

The original project proposal described "Approach B" (password-based voter accounts) as a future enhancement. This remains a possible evolution if user feedback indicates voters want to log in again to verify their vote. However, the receipt token system (ADR-015) provides verification without requiring accounts.
