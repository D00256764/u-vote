"""
Auth Service - Authentication, identity verification, and ballot-token issuance.

Responsibilities:
  1. Organiser authentication (register / login / JWT verification)
  2. Voting-token validation (is this email link still valid?)
  3. Voter identity verification (DOB-based MFA)
  4. Blind ballot-token issuance (anonymity bridge)

The critical anonymity contract:
  - After MFA passes, this service marks voter.has_voted = TRUE
  - It issues a blind ballot_token into the blind_tokens table
  - It does NOT record which voter received which ballot_token
  - The voting-service uses the ballot_token to cast an encrypted ballot
  - Nobody can link voter identity to vote choice

Runs on port 5001 (internal only, not browser-exposed).
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta

from fastapi import FastAPI, HTTPException
from jose import jwt, JWTError

# -- Shared imports -----------------------------------------------------------
current_dir = os.path.dirname(__file__)
for p in [
    os.path.join(current_dir, '..', 'shared'),
    os.path.join(current_dir, 'shared'),
    '/app/shared',
]:
    p_abs = os.path.abspath(p)
    if os.path.isdir(p_abs):
        sys.path.insert(0, p_abs)
        break

from database import Database
from security import (
    hash_password, verify_password,
    generate_blind_ballot_token, generate_election_key,
)
from schemas import (
    RegisterRequest, LoginRequest, TokenVerifyRequest,
    AuthResponse, TokenVerifyResponse, BallotTokenResponse,
    HealthResponse, ErrorResponse,
)

logger = logging.getLogger("auth-service")

# -- Config -------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
DEFAULT_ORG_ID = int(os.getenv("DEFAULT_ORG_ID", "1"))


# -- Lifespan -----------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await Database.get_pool()
    yield
    await Database.close()


app = FastAPI(
    title="Auth Service",
    description="Authentication, identity verification, and ballot-token issuance",
    lifespan=lifespan,
)


# ==========================================================================
# Organiser endpoints
# ==========================================================================

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "healthy", "service": "auth"}


@app.post("/register", response_model=AuthResponse, status_code=201)
async def register(data: RegisterRequest):
    """Register a new organiser."""
    pw_hash = hash_password(data.password)
    org_id = data.org_id or DEFAULT_ORG_ID

    try:
        async with Database.transaction() as conn:
            row = await conn.fetchrow(
                "INSERT INTO organisers (org_id, email, password_hash) "
                "VALUES ($1, $2, $3) RETURNING id",
                org_id, data.email, pw_hash,
            )
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Email already registered")
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Organiser registered successfully", "organiser_id": row["id"]}


@app.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest):
    """Authenticate organiser and return JWT."""
    async with Database.connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash FROM organisers WHERE email = $1",
            data.email,
        )

    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode(
        {
            "organiser_id": row["id"],
            "email": data.email,
            "exp": datetime.utcnow() + timedelta(hours=24),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    return {"token": token, "organiser_id": row["id"]}


@app.post("/verify", response_model=TokenVerifyResponse)
async def verify_token(data: TokenVerifyRequest):
    """Verify a JWT token."""
    try:
        payload = jwt.decode(data.token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "valid": True,
            "organiser_id": payload["organiser_id"],
            "email": payload["email"],
        }
    except JWTError as e:
        msg = "Token expired" if "expired" in str(e).lower() else "Invalid token"
        raise HTTPException(status_code=401, detail=msg)


# ==========================================================================
# Voting-token validation  (was in voter-service)
# ==========================================================================

@app.get("/tokens/{token}/validate", response_model=TokenVerifyResponse)
async def validate_voting_token(token: str):
    """Validate an identity-linked voting token (from the voter's email)."""
    async with Database.connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT vt.id, vt.voter_id, vt.election_id, vt.is_used,
                   vt.expires_at, e.status
            FROM voting_tokens vt
            JOIN elections e ON e.id = vt.election_id
            WHERE vt.token = $1
            """,
            token,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Invalid token")
    if row["is_used"]:
        raise HTTPException(status_code=400, detail="Token already used")
    if datetime.now() > row["expires_at"]:
        raise HTTPException(status_code=400, detail="Token expired")
    if row["status"] != "open":
        raise HTTPException(status_code=400, detail="Election is not open")

    return {
        "valid": True,
        "election_id": row["election_id"],
        "voter_id": row["voter_id"],
    }


# ==========================================================================
# MFA (DOB verification) — was in voter-service
# ==========================================================================

@app.post("/mfa/verify", status_code=200)
async def verify_identity(token: str, date_of_birth: str):
    """Verify voter identity by comparing submitted DOB to stored value."""
    try:
        submitted_dob = date.fromisoformat(date_of_birth)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format (expected YYYY-MM-DD)"
        )

    async with Database.transaction() as conn:
        row = await conn.fetchrow(
            """
            SELECT v.id AS voter_id, v.date_of_birth, v.has_voted,
                   vt.is_used, vt.expires_at, e.status, vt.election_id
            FROM voting_tokens vt
            JOIN voters v ON v.id = vt.voter_id
            JOIN elections e ON e.id = vt.election_id
            WHERE vt.token = $1
            """,
            token,
        )

        if not row:
            raise HTTPException(status_code=404, detail="Invalid token")
        if row["is_used"]:
            raise HTTPException(status_code=400, detail="Token already used")
        if datetime.now() > row["expires_at"]:
            raise HTTPException(status_code=400, detail="Token expired")
        if row["status"] != "open":
            raise HTTPException(status_code=400, detail="Election is not open")
        if row["has_voted"]:
            raise HTTPException(status_code=400, detail="You have already voted")

        if row["date_of_birth"] != submitted_dob:
            raise HTTPException(
                status_code=403,
                detail="Date of birth does not match our records",
            )

        # Record MFA verification
        existing = await conn.fetchrow(
            "SELECT id FROM voter_mfa WHERE token = $1", token
        )
        if not existing:
            await conn.execute(
                "INSERT INTO voter_mfa (token) VALUES ($1)", token
            )

    return {"verified": True}


@app.get("/mfa/status")
async def mfa_status(token: str):
    """Check if a voting token has passed MFA."""
    async with Database.connection() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM voter_mfa WHERE token = $1", token
        )
    return {"mfa_verified": row is not None}


# ==========================================================================
# Blind ballot-token issuance  (the anonymity bridge)
#
# Called by voting-service AFTER MFA passes.
# This is the most security-critical endpoint in the system.
# ==========================================================================

@app.post("/ballot-token/issue", response_model=BallotTokenResponse)
async def issue_ballot_token(token: str):
    """Issue an anonymous ballot token after MFA verification.

    Contract:
      1. Validates the voting_token and checks MFA was completed
      2. Marks voter.has_voted = TRUE (accountability)
      3. Marks voting_token.is_used = TRUE (prevent reuse)
      4. Generates a blind ballot_token and inserts into blind_tokens
         with ONLY election_id (no voter_id)
      5. Returns the ballot_token to the caller

    After this function returns, there is NO record linking
    the voter_id to the ballot_token. The anonymity gap is closed.
    """
    async with Database.transaction() as conn:
        # Validate voting token
        vt_row = await conn.fetchrow(
            """
            SELECT vt.id, vt.voter_id, vt.election_id, vt.is_used, vt.expires_at,
                   e.status
            FROM voting_tokens vt
            JOIN elections e ON e.id = vt.election_id
            WHERE vt.token = $1
            FOR UPDATE
            """,
            token,
        )

        if not vt_row:
            raise HTTPException(status_code=404, detail="Invalid token")
        if vt_row["is_used"]:
            raise HTTPException(status_code=400, detail="Token already used")
        if datetime.now() > vt_row["expires_at"]:
            raise HTTPException(status_code=400, detail="Token expired")
        if vt_row["status"] != "open":
            raise HTTPException(status_code=400, detail="Election is not open")

        # Check MFA was completed
        mfa_row = await conn.fetchrow(
            "SELECT id FROM voter_mfa WHERE token = $1", token
        )
        if not mfa_row:
            raise HTTPException(
                status_code=403, detail="Identity verification required first"
            )

        # Check voter hasn't already voted
        voter = await conn.fetchrow(
            "SELECT has_voted FROM voters WHERE id = $1 FOR UPDATE",
            vt_row["voter_id"],
        )
        if voter and voter["has_voted"]:
            raise HTTPException(status_code=400, detail="Already voted")

        # -- THE ANONYMITY BRIDGE --
        # Step 1: Mark voter as having voted (accountability)
        await conn.execute(
            "UPDATE voters SET has_voted = TRUE WHERE id = $1",
            vt_row["voter_id"],
        )

        # Step 2: Mark voting token as used
        await conn.execute(
            "UPDATE voting_tokens SET is_used = TRUE, used_at = CURRENT_TIMESTAMP "
            "WHERE id = $1",
            vt_row["id"],
        )

        # Step 3: Generate blind ballot token (NO voter_id stored)
        ballot_token = generate_blind_ballot_token()
        await conn.execute(
            "INSERT INTO blind_tokens (ballot_token, election_id) VALUES ($1, $2)",
            ballot_token, vt_row["election_id"],
        )

        # Step 4: Audit log (system actor, no voter_id exposed)
        await conn.execute(
            """
            INSERT INTO audit_log (event_type, election_id, actor_type, detail)
            VALUES ('ballot_token_issued', $1, 'system',
                    '{"note": "blind token issued, voter identity separated"}'::jsonb)
            """,
            vt_row["election_id"],
        )

    return {
        "ballot_token": ballot_token,
        "election_id": vt_row["election_id"],
    }
