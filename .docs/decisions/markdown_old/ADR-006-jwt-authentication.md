# ADR-006: JWT Authentication with bcrypt Password Hashing

## Status

**Status:** Accepted
**Date:** 2026-02-11
**Authors:** D00255656
**Supersedes:** None

---

## Context

### Problem Statement

The U-Vote system requires a robust authentication mechanism for admin users who create and manage elections. The authentication solution must work reliably across 6 independent microservices (auth:5001, voter/admin:5002, voting:5003, results:5004, election:5005, frontend:5000) without introducing a centralised session store that becomes a single point of failure. Voters authenticate via unique one-time tokens distributed by admins, but admin authentication demands a persistent identity model with password-based login.

### Background

During initial prototyping (Weeks 1–3), a basic session-cookie mechanism was trialled using FastAPI's Starlette session middleware. This approach required sticky sessions or a shared session store (Redis) to function across microservices — when the auth-service validated a session, the election-service had no way to verify that session without querying the same store. In the Kind Kubernetes cluster, pods restart frequently during development, and sessions were lost on every restart.

The system requires two distinct authentication flows: (1) admin authentication for election management, and (2) voter authentication via unique access tokens for ballot submission. This ADR addresses the admin authentication flow.

### Requirements

- **R1:** Stateless authentication that any service can validate independently
- **R2:** Secure password storage resistant to brute-force and rainbow table attacks
- **R3:** Token expiration to limit the window of compromise if a token is stolen
- **R4:** Refresh capability to avoid forcing admins to re-login during active election management
- **R5:** Compatibility with FastAPI's dependency injection for route protection
- **R6:** No external infrastructure dependencies (no Redis, no external identity provider)
- **R7:** Auditable — authentication events must be logged to the hash-chain audit system
- **R8:** Support for role-based claims (admin vs future roles)

### Constraints

- **C1:** Must work across all 6 microservices without shared state
- **C2:** Must run in resource-constrained Kind cluster (limited memory per pod)
- **C3:** Single developer — solution must be simple to implement and maintain
- **C4:** Must integrate with existing shared/security.py library
- **C5:** No budget for third-party identity providers (Auth0, Okta)

---

## Options Considered

### Option 1: Session Cookies with Shared Store (Redis)

**Description:**
Traditional server-side session management where a session ID is stored in an HTTP-only cookie, and session data is maintained in a shared Redis instance accessible by all services.

**Pros:**
- Immediate session revocation (delete from Redis)
- Familiar pattern from DkIT coursework (Flask sessions)
- HTTP-only cookies provide XSS protection by default
- Session data can store arbitrary user context

**Cons:**
- Requires Redis deployment — adds operational complexity and a single point of failure
- Redis pod consumes ~50MB memory in a resource-constrained Kind cluster
- All services must have network access to Redis — widens the network policy surface
- Session fixation and CSRF attacks require additional mitigations
- Sticky sessions or shared store required for multi-pod deployments

**Evaluation:**
Session cookies introduce a hard dependency on Redis for cross-service validation. This directly violates R6 (no external infrastructure) and increases the network attack surface. Redis becomes a single point of failure — if Redis is down, no admin can authenticate to any service.

### Option 2: JWT with HS256 and bcrypt — Chosen

**Description:**
JSON Web Tokens (RFC 7519) signed with HMAC-SHA256 using a shared secret. Admin passwords are hashed with bcrypt (cost factor 12) before storage. Access tokens expire after 1 hour; refresh tokens expire after 24 hours. Any service with the shared secret can validate tokens independently.

**Pros:**
- Stateless — no shared session store needed, any service validates independently
- Self-contained tokens carry claims (user ID, role, expiration)
- Well-supported by PyJWT library (mature, audited)
- bcrypt with cost 12 provides strong password hashing (~250ms per hash)
- Short-lived tokens (1hr) limit the damage window if compromised
- Integrates cleanly with FastAPI dependency injection
- Zero additional infrastructure (no Redis, no external IdP)

**Cons:**
- No immediate token revocation without a blacklist mechanism
- Shared secret must be distributed to all services (via Kubernetes Secret)
- Token size (~800 bytes) larger than session cookie (~32 bytes)
- HS256 uses symmetric key — compromised secret affects all services
- bcrypt cost 12 adds ~250ms latency to login (acceptable for admin-only flow)

**Evaluation:**
JWT with HS256 satisfies all requirements (R1–R8) without introducing external dependencies. The inability to immediately revoke tokens is the primary trade-off, mitigated by short expiration times. For a small-scale election system with a limited number of admin users, the revocation limitation is acceptable.

### Option 3: OAuth 2.0 with External Identity Provider

**Description:**
Delegate authentication to an external OAuth 2.0 provider (e.g., Auth0, Google Identity Platform) using the Authorization Code flow. Services validate tokens against the provider's JWKS endpoint.

**Pros:**
- Industry-standard protocol with extensive security review
- Offloads identity management complexity
- Supports MFA, social login, and SSO out of the box
- RS256 asymmetric signing (public key verification, no shared secret)
- Token revocation via provider dashboard

**Cons:**
- External dependency — requires internet access and provider availability
- Free tiers have limitations (Auth0: 7,000 monthly active users)
- Additional network egress from Kind cluster to external provider
- OAuth 2.0 flows are complex to implement correctly (PKCE, state parameter, nonce)
- Adds latency for token validation (JWKS endpoint call or caching)
- Violates C5 (no budget) if free tier limits are exceeded
- Overkill for a system with a small number of admin users

**Evaluation:**
OAuth 2.0 is the industry standard for production systems, but it introduces external dependencies, network requirements, and complexity disproportionate to the project's scale. A single-developer student project with a handful of admin users does not benefit from federated identity management.

### Option 4: SAML 2.0 (Security Assertion Markup Language)

**Description:**
Enterprise single sign-on protocol using XML-based assertions. Requires a SAML Identity Provider (IdP) such as Active Directory Federation Services or Keycloak.

**Pros:**
- Enterprise-grade SSO standard
- Strong integration with institutional identity systems (DkIT AD)
- Mature, well-understood security model
- XML signatures provide strong assertion integrity

**Cons:**
- Requires a SAML IdP deployment (Keycloak: ~512MB memory, complex configuration)
- XML processing is verbose and error-prone in Python
- SAML libraries for Python (python3-saml) are poorly maintained
- Dramatically over-engineered for a student project with 1–3 admin users
- Slow authentication flow (multiple redirects)
- No benefit without institutional IdP integration

**Evaluation:**
SAML is designed for enterprise SSO across organisational boundaries. Deploying a SAML IdP for a small election system is excessive. The operational overhead (Keycloak deployment, certificate management, metadata exchange) far outweighs any benefit.

---

## Decision

**Chosen Option:** JWT with HS256 and bcrypt (Option 2)

**Rationale:**
JWT provides stateless, cross-service authentication without introducing infrastructure dependencies. In a microservices architecture where any of the 6 services may need to verify admin identity, the ability to validate a token using only a shared secret — without calling another service or querying a shared store — is the decisive advantage. bcrypt with cost factor 12 provides password hashing that resists brute-force attacks while keeping login latency under 300ms.

**Key Factors:**

1. **Stateless cross-service validation (R1):** The auth-service issues a JWT containing the admin's user ID and role. Any other service (election, voting, results) can validate this token using the shared HS256 secret without making a network call. This eliminates the auth-service as a runtime dependency for token validation.

2. **bcrypt cost factor 12 (R2):** At cost 12, bcrypt takes approximately 250ms to hash a password. This makes brute-force attacks computationally expensive (~4 hashes/second per core) while keeping admin login responsive. Rainbow table attacks are prevented by bcrypt's built-in salt.

3. **Short-lived tokens with refresh (R3, R4):** Access tokens expire after 1 hour, limiting the window during which a stolen token can be used. Refresh tokens (24-hour expiry) allow admins to maintain sessions during extended election management without re-entering credentials.

4. **Zero infrastructure overhead (R6):** No Redis, no external IdP, no SAML server. The JWT secret is distributed via a Kubernetes Secret mounted as an environment variable. This keeps the deployment simple and the attack surface minimal.

5. **FastAPI integration (R5):** PyJWT integrates cleanly with FastAPI's `Depends()` mechanism, providing a reusable dependency that extracts and validates the JWT from the Authorization header.

---

## Consequences

### Positive Consequences

- **Service independence:** Each microservice validates JWTs locally using the shared secret. No service-to-service calls are needed for authentication, reducing latency and eliminating the auth-service as a single point of failure for token validation.
- **Simplified deployment:** No Redis or external IdP to deploy, configure, or monitor. Fewer moving parts in the Kind cluster.
- **Password security:** bcrypt cost 12 ensures admin passwords are stored securely. Even if the database is compromised, password recovery is computationally infeasible.
- **Audit integration:** JWT claims (user ID, role) are extracted and included in hash-chain audit log entries, providing a clear audit trail of which admin performed which action.
- **Predictable resource usage:** JWT validation is a CPU-only operation (~0.1ms per validation). No memory allocated for session storage.

### Negative Consequences

- **No immediate revocation:** If an admin's JWT is compromised, it remains valid until expiration (up to 1 hour). Mitigation: short access token lifetime (1hr) limits the exposure window. A token blacklist backed by an in-memory set could be added later if needed.
- **Secret rotation complexity:** Changing the HS256 secret invalidates all outstanding tokens. Mitigation: coordinate secret rotation during maintenance windows when no elections are active.
- **Symmetric key risk:** All services share the same secret. If any service is compromised, the attacker can forge tokens for any admin. Mitigation: Kubernetes NetworkPolicies restrict inter-service communication, and the secret is mounted read-only from a Kubernetes Secret.
- **Token size overhead:** JWT tokens (~800 bytes) are larger than session IDs (~32 bytes). For a system with a small number of admin requests, this is negligible.

### Trade-offs Accepted

- **No immediate revocation vs no Redis dependency:** Accepted the inability to immediately revoke tokens in exchange for eliminating Redis as an infrastructure dependency. The 1-hour access token lifetime provides an acceptable compromise — a compromised token is valid for at most 60 minutes.
- **Symmetric signing vs simplicity:** Accepted HS256 (symmetric) over RS256 (asymmetric) because all services are within the same Kubernetes cluster and trust boundary. RS256 would be preferred if tokens were validated by external third parties.

---

## Implementation Notes

### Technical Details

The authentication flow is implemented in the auth-service (port 5001) with shared utilities in `shared/security.py`:

```python
# shared/security.py — JWT token creation
import jwt
import bcrypt
from datetime import datetime, timedelta

SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_HOURS = 24

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt(rounds=12)
    ).decode('utf-8')
```

FastAPI dependency for route protection:

```python
# auth-service/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
        )
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### Configuration

- **JWT Secret:** Stored in Kubernetes Secret `uvote-jwt-secret`, mounted as `JWT_SECRET_KEY` environment variable
- **bcrypt cost factor:** 12 (hardcoded in `hash_password()`)
- **Access token lifetime:** 60 minutes
- **Refresh token lifetime:** 24 hours
- **Token algorithm:** HS256 (HMAC-SHA256)
- **Password minimum length:** 8 characters (enforced by Pydantic model)

### Integration Points

- **Auth Service (5001):** Issues and refreshes tokens, validates credentials against PostgreSQL
- **Election Service (5005):** Validates JWT to authorise election creation and management
- **Voter/Admin Service (5002):** Validates JWT for voter registration and access token distribution
- **Shared Security (shared/security.py):** Provides `create_access_token()`, `verify_password()`, `hash_password()`
- **Audit System:** JWT claims extracted and included in audit log entries (see ADR-007)
- **Kubernetes Secret:** `uvote-jwt-secret` distributed to all service pods

---

## Validation

### Success Criteria

- [x] Admin login returns a valid JWT accepted by all services
- [x] Invalid or expired tokens return HTTP 401 across all services
- [x] bcrypt-hashed passwords cannot be reversed (verified with hashcat benchmark)
- [x] Refresh token flow extends session without re-authentication
- [x] Authentication events logged to hash-chain audit system
- [x] JWT validation adds <1ms latency per request

### Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Login latency (bcrypt) | <500ms | ~260ms |
| Token validation latency | <5ms | ~0.1ms |
| Token size | <2KB | ~800 bytes |
| bcrypt cost factor | 12 | 12 |
| Access token lifetime | 60 min | 60 min |

### Review Date

End of Stage 2 (April 2026) — evaluate whether token blacklisting is needed based on security audit findings.

---

## References

- [RFC 7519 — JSON Web Tokens](https://tools.ietf.org/html/rfc7519)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [bcrypt — Wikipedia](https://en.wikipedia.org/wiki/Bcrypt)
- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [ADR-001](ADR-001-python-fastapi-backend.md) — FastAPI as the backend framework
- [ADR-007](ADR-007-hash-chain-audit.md) — Audit logging for authentication events
- [ADR-008](ADR-008-microservices-architecture.md) — Microservices architecture requiring cross-service auth

## Notes

The voter authentication flow is separate from admin JWT authentication. Voters receive unique one-time access tokens (UUIDs) generated by the admin via the voter-service. These tokens are not JWTs — they are simple database-backed tokens that are invalidated after a single use. This ADR applies exclusively to the admin authentication flow.

HS256 was chosen over RS256 because all services reside within the same Kubernetes cluster trust boundary. If U-Vote were extended to support external service integrations (e.g., third-party result verification), migrating to RS256 with public key distribution would be advisable.
