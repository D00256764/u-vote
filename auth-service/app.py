"""
Auth Service — The SOLE database owner for the entire system.

Architecture:
  This is the only service with direct PostgreSQL access.
  All other services (election, voting, frontend) call this
  service's REST API over HTTP.

Endpoint groups:
  1. Organiser auth      — register, login, JWT verify
  2. Election CRUD       — create, list, get, open, close
  3. Voter management    — add single, CSV upload, list, token generation + email
  4. Voting tokens       — validate, MFA verify, MFA status
  5. Ballot tokens       — issue blind ballot token (anonymity bridge)
  6. Vote casting        — submit encrypted ballot (called by voting-service)
  7. Results & audit     — tally, results, audit trail, statistics
  8. Receipt             — verify vote receipt

Runs on port 5001 (internal only, not browser-exposed).
"""

import os
import sys
import csv
import logging
from io import StringIO
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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
    generate_voting_token, generate_token_expiry,
    generate_blind_ballot_token, generate_election_key,
    generate_receipt_token,
)
from email_util import send_voting_token_email
from schemas import (
    RegisterRequest, LoginRequest, TokenVerifyRequest,
    AuthResponse, TokenVerifyResponse, BallotTokenResponse,
    HealthResponse, ErrorResponse, ElectionCreate, VoterAddRequest,
)

logger = logging.getLogger("auth-service")

# -- Config -------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
DEFAULT_ORG_ID = int(os.getenv("DEFAULT_ORG_ID", "1"))


# -- Lifespan -----------------------------------------------------------------
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Ensure DB pool is ready, then run idempotent schema migrations needed by this service.
    await Database.get_pool()
    # Run lightweight, idempotent migrations to add columns introduced during refactor.
    try:
        async with Database.connection() as conn:
            await conn.execute(
                """
                ALTER TABLE voting_tokens ADD COLUMN IF NOT EXISTS email_sent BOOLEAN DEFAULT FALSE;
                ALTER TABLE voting_tokens ADD COLUMN IF NOT EXISTS emails_failed INTEGER DEFAULT 0;
                ALTER TABLE voting_tokens ADD COLUMN IF NOT EXISTS last_email_sent_at TIMESTAMP NULL;
                """
            )
    except Exception as e:
        # Log migration failures but continue — service can still start and we'll surface DB errors on operations.
        logger.error(f"Schema migration failed at startup: {e}")

    yield

    await Database.close()


app = FastAPI(
    title="Auth Service",
    description="Sole database owner — authentication, elections, voting, results",
    lifespan=lifespan,
)


# ==========================================================================
# 1. ORGANISER AUTH
# ==========================================================================

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "healthy", "service": "auth"}


@app.post("/register", response_model=AuthResponse, status_code=201)
async def register(data: RegisterRequest):
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
    async with Database.connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash FROM organisers WHERE email = $1", data.email,
        )
    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt.encode(
        {"organiser_id": row["id"], "email": data.email,
         "exp": datetime.utcnow() + timedelta(hours=24)},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    return {"token": token, "organiser_id": row["id"]}


@app.post("/verify", response_model=TokenVerifyResponse)
async def verify_token(data: TokenVerifyRequest):
    try:
        payload = jwt.decode(data.token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {"valid": True, "organiser_id": payload["organiser_id"],
                "email": payload["email"]}
    except JWTError as e:
        msg = "Token expired" if "expired" in str(e).lower() else "Invalid token"
        raise HTTPException(status_code=401, detail=msg)


# ==========================================================================
# 2. ELECTION CRUD
# ==========================================================================

@app.get("/elections")
async def list_elections(organiser_id: int):
    async with Database.connection() as conn:
        rows = await conn.fetch(
            """SELECT id, title, description, status, created_at, opened_at, closed_at
               FROM elections WHERE organiser_id = $1 ORDER BY created_at DESC""",
            organiser_id,
        )
    return {"elections": [
        {"id": r["id"], "title": r["title"], "description": r["description"],
         "status": r["status"], "created_at": r["created_at"].isoformat(),
         "opened_at": r["opened_at"].isoformat() if r["opened_at"] else None,
         "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None}
        for r in rows
    ]}


@app.post("/elections", status_code=201)
async def create_election(organiser_id: int, data: ElectionCreate):
    enc_key = generate_election_key()
    async with Database.transaction() as conn:
        org_row = await conn.fetchrow(
            "SELECT org_id FROM organisers WHERE id = $1", organiser_id
        )
        org_id = org_row["org_id"] if org_row else DEFAULT_ORG_ID
        row = await conn.fetchrow(
            """INSERT INTO elections (organiser_id, org_id, title, description, status, encryption_key)
               VALUES ($1, $2, $3, $4, 'draft', $5) RETURNING id""",
            organiser_id, org_id, data.title, data.description, enc_key,
        )
        election_id = row["id"]
        for i, opt in enumerate(data.options):
            if opt.strip():
                await conn.execute(
                    "INSERT INTO election_options (election_id, option_text, display_order) "
                    "VALUES ($1, $2, $3)", election_id, opt.strip(), i,
                )
        await conn.execute(
            """INSERT INTO audit_log (event_type, election_id, actor_type, actor_id, detail)
               VALUES ('election_created', $1, 'organiser', $2,
                       $3::jsonb)""",
            election_id, organiser_id,
            f'{{"title": "{data.title}"}}',
        )
    return {"message": "Election created successfully", "election_id": election_id}


@app.get("/elections/{election_id}")
async def get_election(election_id: int, organiser_id: int | None = None):
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            """SELECT id, title, description, status, created_at,
                      opened_at, closed_at, organiser_id
               FROM elections WHERE id = $1""",
            election_id,
        )
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")
        if organiser_id is not None and election["organiser_id"] != organiser_id:
            raise HTTPException(status_code=403, detail="Access denied")

        options = await conn.fetch(
            "SELECT id, option_text, display_order FROM election_options "
            "WHERE election_id = $1 ORDER BY display_order", election_id,
        )
        voter_count = await conn.fetchval(
            "SELECT COUNT(*) FROM voters WHERE election_id = $1", election_id
        )
        ballot_count = await conn.fetchval(
            "SELECT COUNT(*) FROM encrypted_ballots WHERE election_id = $1", election_id
        )
    return {
        "election": {
            "id": election["id"], "title": election["title"],
            "description": election["description"], "status": election["status"],
            "created_at": election["created_at"].isoformat(),
            "opened_at": election["opened_at"].isoformat() if election["opened_at"] else None,
            "closed_at": election["closed_at"].isoformat() if election["closed_at"] else None,
            "voter_count": voter_count, "vote_count": ballot_count,
        },
        "options": [{"id": o["id"], "text": o["option_text"],
                      "order": o["display_order"]} for o in options],
    }


@app.post("/elections/{election_id}/open")
async def open_election(election_id: int, organiser_id: int):
    async with Database.transaction() as conn:
        result = await conn.execute(
            """UPDATE elections SET status = 'open', opened_at = CURRENT_TIMESTAMP
               WHERE id = $1 AND organiser_id = $2 AND status = 'draft'""",
            election_id, organiser_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=400, detail="Cannot open election")
        await conn.execute(
            """INSERT INTO audit_log (event_type, election_id, actor_type, actor_id, detail)
               VALUES ('election_opened', $1, 'organiser', $2,
                       '{"note":"election opened for voting"}'::jsonb)""",
            election_id, organiser_id,
        )
    return {"message": "Election opened successfully"}


@app.post("/elections/{election_id}/close")
async def close_election(election_id: int, organiser_id: int):
    async with Database.transaction() as conn:
        result = await conn.execute(
            """UPDATE elections SET status = 'closed', closed_at = CURRENT_TIMESTAMP
               WHERE id = $1 AND organiser_id = $2 AND status = 'open'""",
            election_id, organiser_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=400, detail="Cannot close election")
        await conn.execute(
            """INSERT INTO audit_log (event_type, election_id, actor_type, actor_id, detail)
               VALUES ('election_closed', $1, 'organiser', $2,
                       '{"note":"election closed"}'::jsonb)""",
            election_id, organiser_id,
        )
    return {"message": "Election closed successfully"}


# ==========================================================================
# 3. VOTER MANAGEMENT
# ==========================================================================

@app.get("/elections/{election_id}/voters")
async def get_voters(election_id: int):
    async with Database.connection() as conn:
        rows = await conn.fetch(
            """SELECT v.id, v.email, v.date_of_birth, v.has_voted, v.created_at,
                      EXISTS(SELECT 1 FROM voting_tokens WHERE voter_id = v.id) AS has_token
               FROM voters v WHERE v.election_id = $1 ORDER BY v.created_at DESC""",
            election_id,
        )
    return {"voters": [
        {"id": r["id"], "email": r["email"],
         "date_of_birth": r["date_of_birth"].isoformat(),
         "has_voted": r["has_voted"], "has_token": r["has_token"],
         "created_at": r["created_at"].isoformat()}
        for r in rows
    ]}


@app.post("/elections/{election_id}/voters", status_code=201)
async def add_voter(election_id: int, data: VoterAddRequest):
    try:
        dob = date.fromisoformat(data.date_of_birth) if isinstance(data.date_of_birth, str) else data.date_of_birth
        async with Database.transaction() as conn:
            row = await conn.fetchrow(
                "INSERT INTO voters (election_id, email, date_of_birth) "
                "VALUES ($1, $2, $3) RETURNING id",
                election_id, data.email, dob,
            )
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Voter already exists for this election")
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Voter added successfully", "voter_id": row["id"]}


@app.post("/elections/{election_id}/voters/upload", status_code=201)
async def upload_voters(election_id: int, file: UploadFile = File(...)):
    contents = await file.read()
    csv_data = contents.decode("utf-8")
    reader = csv.DictReader(StringIO(csv_data))

    if reader.fieldnames is None or "email" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail='CSV must have an "email" column')
    if "date_of_birth" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail='CSV must have a "date_of_birth" column (YYYY-MM-DD)')

    voters_added = 0
    voters_skipped = 0
    async with Database.transaction() as conn:
        for row in reader:
            email = row.get("email", "").strip()
            dob_str = row.get("date_of_birth", "").strip()
            if not email or not dob_str:
                voters_skipped += 1
                continue
            try:
                dob = date.fromisoformat(dob_str)
                await conn.execute(
                    "INSERT INTO voters (election_id, email, date_of_birth) VALUES ($1, $2, $3)",
                    election_id, email, dob,
                )
                voters_added += 1
            except Exception:
                voters_skipped += 1
    return {"message": "Voters uploaded", "voters_added": voters_added, "voters_skipped": voters_skipped}


@app.post("/elections/{election_id}/tokens/generate", status_code=201)
async def generate_tokens(election_id: int):
    async with Database.transaction() as conn:
        election_row = await conn.fetchrow(
            "SELECT title FROM elections WHERE id = $1", election_id
        )
        if not election_row:
            raise HTTPException(status_code=404, detail="Election not found")
        election_title = election_row["title"]

        voters = await conn.fetch(
            """SELECT v.id FROM voters v WHERE v.election_id = $1
               AND NOT EXISTS (
                   SELECT 1 FROM voting_tokens vt
                   WHERE vt.voter_id = v.id AND vt.is_used = FALSE
               )""",
            election_id,
        )
        generated_tokens = []
        for voter in voters:
            token = generate_voting_token()
            expires_at = generate_token_expiry(168)
            await conn.execute(
                "INSERT INTO voting_tokens (token, voter_id, election_id, expires_at) "
                "VALUES ($1, $2, $3, $4)",
                token, voter["id"], election_id, expires_at,
            )
            email_row = await conn.fetchrow(
                "SELECT email FROM voters WHERE id = $1", voter["id"]
            )
            generated_tokens.append({
                "email": email_row["email"], "token": token,
                "expires_at": expires_at.isoformat(),
            })

    # Send emails outside DB transaction and record send status per-token
    emails_sent = 0
    emails_failed = 0
    for t in generated_tokens:
        try:
            await send_voting_token_email(
                to_email=t["email"], token=t["token"],
                election_title=election_title, expires_at=t["expires_at"],
            )
            emails_sent += 1
            # mark token as emailed
            async with Database.connection() as conn:
                await conn.execute(
                    "UPDATE voting_tokens SET email_sent = TRUE, last_email_sent_at = CURRENT_TIMESTAMP WHERE token = $1",
                    t["token"],
                )
        except Exception as e:
            emails_failed += 1
            logger.error(f"Failed to email {t['email']}: {e}")
            async with Database.connection() as conn:
                await conn.execute(
                    "UPDATE voting_tokens SET emails_failed = COALESCE(emails_failed,0) + 1 WHERE token = $1",
                    t["token"],
                )

    return {
        "message": "Tokens generated and emails sent",
        "tokens_generated": len(generated_tokens),
        "emails_sent": emails_sent, "emails_failed": emails_failed,
    }


@app.post("/elections/{election_id}/tokens/resend")
async def resend_tokens(election_id: int, organiser_id: int):
    """Resend voting tokens for an election.

    Security measures:
    - Requires organiser_id and verifies ownership of the election.
    - Enforces a short cooldown (10 minutes) between resends for the same election.
    - Writes an audit_log entry recording who requested the resend and results.

    Note: This intentionally resends tokens even if they were previously sent.
    """
    # Verify election exists and belongs to organiser_id
    async with Database.connection() as conn:
        election_row = await conn.fetchrow(
            "SELECT title, organiser_id FROM elections WHERE id = $1", election_id
        )
        if not election_row:
            raise HTTPException(status_code=404, detail="Election not found")
        if election_row["organiser_id"] != organiser_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Cooldown: check audit_log for recent tokens_resent for this election
        last_resend = await conn.fetchrow(
            "SELECT created_at FROM audit_log WHERE election_id = $1 AND event_type = 'tokens_resent' ORDER BY created_at DESC LIMIT 1",
            election_id,
        )
        if last_resend:
            from datetime import datetime, timedelta

            if isinstance(last_resend["created_at"], datetime):
                cutoff = datetime.utcnow() - timedelta(minutes=10)
                if last_resend["created_at"] > cutoff:
                    raise HTTPException(status_code=429, detail="Resend cooldown active. Try again later.")

        rows = await conn.fetch(
            """SELECT vt.token, v.email
               FROM voting_tokens vt
               JOIN voters v ON v.id = vt.voter_id
               WHERE vt.election_id = $1 AND vt.is_used = FALSE
                 AND (vt.email_sent = FALSE OR COALESCE(vt.emails_failed, 0) > 0)""",
            election_id,
        )

    if not rows:
        return {"message": "No unused tokens found for this election",
                "tokens_found": 0, "emails_sent": 0, "emails_failed": 0}

    emails_sent = 0
    emails_failed = 0
    election_title = election_row["title"]
    for r in rows:
        try:
            await send_voting_token_email(
                to_email=r["email"], token=r["token"],
                election_title=election_title, expires_at="N/A",
            )
            emails_sent += 1
        except Exception as e:
            emails_failed += 1
            logger.error(f"Failed to resend token to {r['email']}: {e}")
        else:
            # Mark token as emailed and update timestamp so we track resend attempts
            try:
                async with Database.connection() as conn:
                    await conn.execute(
                        "UPDATE voting_tokens SET email_sent = TRUE, last_email_sent_at = CURRENT_TIMESTAMP WHERE token = $1",
                        r["token"],
                    )
            except Exception as ee:
                # Log but don't fail the whole operation if the DB update fails
                logger.error(f"Failed to update send status for token {r['token']}: {ee}")

    # Record audit entry
    async with Database.connection() as conn:
        await conn.execute(
            "INSERT INTO audit_log (event_type, election_id, actor_type, actor_id, detail) VALUES ('tokens_resent', $1, 'organiser', $2, $3::jsonb)",
            election_id, organiser_id, f'{{"sent": {emails_sent}, "failed": {emails_failed}}}',
        )

    return {
        "message": "Resend complete",
        "tokens_found": len(rows), "emails_sent": emails_sent, "emails_failed": emails_failed,
    }


# ==========================================================================
# 4. VOTING TOKEN VALIDATION & MFA
# ==========================================================================

@app.get("/tokens/{token}/validate")
async def validate_voting_token(token: str):
    async with Database.connection() as conn:
        row = await conn.fetchrow(
            """SELECT vt.id, vt.voter_id, vt.election_id, vt.is_used,
                      vt.expires_at, e.status
               FROM voting_tokens vt
               JOIN elections e ON e.id = vt.election_id
               WHERE vt.token = $1""",
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
    return {"valid": True, "election_id": row["election_id"], "voter_id": row["voter_id"]}


@app.post("/mfa/verify", status_code=200)
async def verify_identity(token: str, date_of_birth: str):
    try:
        submitted_dob = date.fromisoformat(date_of_birth)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (expected YYYY-MM-DD)")

    async with Database.transaction() as conn:
        row = await conn.fetchrow(
            """SELECT v.id AS voter_id, v.date_of_birth, v.has_voted,
                      vt.is_used, vt.expires_at, e.status, vt.election_id
               FROM voting_tokens vt
               JOIN voters v ON v.id = vt.voter_id
               JOIN elections e ON e.id = vt.election_id
               WHERE vt.token = $1""",
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
            raise HTTPException(status_code=403, detail="Date of birth does not match our records")

        existing = await conn.fetchrow("SELECT id FROM voter_mfa WHERE token = $1", token)
        if not existing:
            await conn.execute("INSERT INTO voter_mfa (token) VALUES ($1)", token)
    return {"verified": True}


@app.get("/mfa/status")
async def mfa_status(token: str):
    async with Database.connection() as conn:
        row = await conn.fetchrow("SELECT id FROM voter_mfa WHERE token = $1", token)
    return {"mfa_verified": row is not None}


# ==========================================================================
# 5. BLIND BALLOT-TOKEN ISSUANCE (anonymity bridge)
# ==========================================================================

@app.post("/ballot-token/issue", response_model=BallotTokenResponse)
async def issue_ballot_token(token: str):
    async with Database.transaction() as conn:
        vt_row = await conn.fetchrow(
            """SELECT vt.id, vt.voter_id, vt.election_id, vt.is_used, vt.expires_at, e.status
               FROM voting_tokens vt JOIN elections e ON e.id = vt.election_id
               WHERE vt.token = $1 FOR UPDATE""",
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

        mfa_row = await conn.fetchrow("SELECT id FROM voter_mfa WHERE token = $1", token)
        if not mfa_row:
            raise HTTPException(status_code=403, detail="Identity verification required first")

        voter = await conn.fetchrow(
            "SELECT has_voted FROM voters WHERE id = $1 FOR UPDATE", vt_row["voter_id"]
        )
        if voter and voter["has_voted"]:
            raise HTTPException(status_code=400, detail="Already voted")

        # -- THE ANONYMITY BRIDGE --
        await conn.execute("UPDATE voters SET has_voted = TRUE WHERE id = $1", vt_row["voter_id"])
        await conn.execute(
            "UPDATE voting_tokens SET is_used = TRUE, used_at = CURRENT_TIMESTAMP WHERE id = $1",
            vt_row["id"],
        )
        ballot_token = generate_blind_ballot_token()
        await conn.execute(
            "INSERT INTO blind_tokens (ballot_token, election_id) VALUES ($1, $2)",
            ballot_token, vt_row["election_id"],
        )
        await conn.execute(
            """INSERT INTO audit_log (event_type, election_id, actor_type, detail)
               VALUES ('ballot_token_issued', $1, 'system',
                       '{"note": "blind token issued, voter identity separated"}'::jsonb)""",
            vt_row["election_id"],
        )
    return {"ballot_token": ballot_token, "election_id": vt_row["election_id"]}


# ==========================================================================
# 6. VOTE CASTING (called by voting-service)
# ==========================================================================

@app.get("/elections/{election_id}/ballot")
async def get_ballot(election_id: int):
    """Return election info + options for the ballot page."""
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            "SELECT id, title, description, status FROM elections WHERE id = $1",
            election_id,
        )
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")
        options = await conn.fetch(
            "SELECT id, option_text, display_order FROM election_options "
            "WHERE election_id = $1 ORDER BY display_order, id", election_id,
        )
    return {
        "election": {"id": election["id"], "title": election["title"],
                      "description": election["description"],
                      "status": election["status"]},
        "options": [{"id": o["id"], "text": o["option_text"],
                      "order": o["display_order"]} for o in options],
    }


@app.post("/vote/cast")
async def cast_vote(ballot_token: str = Form(...), option_id: int = Form(...),
                    election_id: int = Form(...)):
    """Cast an encrypted vote. Only auth-service touches the DB."""
    async with Database.transaction() as conn:
        bt_row = await conn.fetchrow(
            "SELECT id, election_id, is_used FROM blind_tokens "
            "WHERE ballot_token = $1 AND election_id = $2 FOR UPDATE",
            ballot_token, election_id,
        )
        if not bt_row:
            raise HTTPException(status_code=400, detail="Invalid ballot token")
        if bt_row["is_used"]:
            raise HTTPException(status_code=400, detail="This ballot token has already been used")

        election = await conn.fetchrow(
            "SELECT status, encryption_key FROM elections WHERE id = $1", election_id
        )
        if not election or election["status"] != "open":
            raise HTTPException(status_code=400, detail="Election is not currently open")

        opt = await conn.fetchrow(
            "SELECT id FROM election_options WHERE id = $1 AND election_id = $2",
            option_id, election_id,
        )
        if not opt:
            raise HTTPException(status_code=400, detail="Invalid option for this election")

        enc_key = election["encryption_key"]
        if not enc_key:
            raise HTTPException(status_code=400, detail="Election encryption not configured")

        prev = await conn.fetchrow(
            "SELECT ballot_hash FROM encrypted_ballots "
            "WHERE election_id = $1 ORDER BY id DESC LIMIT 1", election_id,
        )
        previous_hash = prev["ballot_hash"] if prev else None
        receipt = generate_receipt_token()

        await conn.execute(
            """INSERT INTO encrypted_ballots (election_id, encrypted_vote, previous_hash, receipt_token)
               VALUES ($1, pgp_sym_encrypt($2::text, $3), $4, $5)""",
            election_id, str(option_id), enc_key, previous_hash, receipt,
        )
        ballot_row = await conn.fetchrow(
            "SELECT ballot_hash FROM encrypted_ballots WHERE receipt_token = $1", receipt
        )
        await conn.execute(
            "INSERT INTO vote_receipts (election_id, receipt_token, ballot_hash) VALUES ($1, $2, $3)",
            election_id, receipt, ballot_row["ballot_hash"],
        )
        await conn.execute(
            "UPDATE blind_tokens SET is_used = TRUE, used_at = CURRENT_TIMESTAMP WHERE id = $1",
            bt_row["id"],
        )
        await conn.execute(
            """INSERT INTO audit_log (event_type, election_id, actor_type, detail)
               VALUES ('ballot_cast', $1, 'voter',
                       $2::jsonb)""",
            election_id,
            f'{{"receipt_token": "{receipt}", "note": "encrypted ballot cast anonymously"}}',
        )

    return {"receipt_token": receipt, "ballot_hash": ballot_row["ballot_hash"]}


# ==========================================================================
# 7. RESULTS & AUDIT
# ==========================================================================

@app.get("/elections/{election_id}/results")
async def get_results(election_id: int):
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            "SELECT id, title, status, closed_at FROM elections WHERE id = $1", election_id
        )
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")
        if election["status"] != "closed":
            raise HTTPException(status_code=403, detail="Election must be closed to view results")

        enc_key_row = await conn.fetchrow(
            "SELECT encryption_key FROM elections WHERE id = $1", election_id
        )
        enc_key = enc_key_row["encryption_key"]

        # Decrypt ballots and count
        results = await conn.fetch(
            """SELECT pgp_sym_decrypt(encrypted_vote, $1) AS option_id_str
               FROM encrypted_ballots WHERE election_id = $2""",
            enc_key, election_id,
        )
        # Tally
        tally = {}
        for r in results:
            oid = int(r["option_id_str"])
            tally[oid] = tally.get(oid, 0) + 1
        total_votes = sum(tally.values())

        options = await conn.fetch(
            "SELECT id, option_text, display_order FROM election_options "
            "WHERE election_id = $1 ORDER BY display_order", election_id,
        )
        total_voters = await conn.fetchval(
            "SELECT COUNT(*) FROM voters WHERE election_id = $1", election_id
        )

    results_data = []
    for o in options:
        count = tally.get(o["id"], 0)
        pct = round(count / total_votes * 100, 2) if total_votes > 0 else 0
        results_data.append({
            "option_id": o["id"], "option_text": o["option_text"],
            "vote_count": count, "percentage": pct,
        })
    results_data.sort(key=lambda x: x["vote_count"], reverse=True)

    return {
        "election": {
            "id": election["id"], "title": election["title"],
            "status": election["status"],
            "closed_at": election["closed_at"].isoformat() if election["closed_at"] else None,
        },
        "summary": {
            "total_votes": total_votes, "total_voters": total_voters,
            "turnout_percentage": round(total_votes / total_voters * 100, 2) if total_voters > 0 else 0,
        },
        "results": results_data,
    }


@app.get("/elections/{election_id}/audit")
async def get_audit_trail(election_id: int):
    async with Database.connection() as conn:
        status_row = await conn.fetchrow(
            "SELECT status FROM elections WHERE id = $1", election_id
        )
        if not status_row:
            raise HTTPException(status_code=404, detail="Election not found")
        if status_row["status"] != "closed":
            raise HTTPException(status_code=403, detail="Audit trail only available for closed elections")

        ballots = await conn.fetch(
            """SELECT id, ballot_hash, previous_hash, cast_at
               FROM encrypted_ballots WHERE election_id = $1 ORDER BY id ASC""",
            election_id,
        )

    audit_data = []
    hash_chain_valid = True
    for i, b in enumerate(ballots):
        if i > 0 and b["previous_hash"] != ballots[i - 1]["ballot_hash"]:
            hash_chain_valid = False
        audit_data.append({
            "ballot_id": b["id"], "ballot_hash": b["ballot_hash"],
            "previous_hash": b["previous_hash"],
            "cast_at": b["cast_at"].isoformat(), "sequence": i + 1,
        })
    return {
        "election_id": election_id, "total_ballots": len(ballots),
        "hash_chain_valid": hash_chain_valid, "audit_trail": audit_data,
    }


@app.get("/elections/{election_id}/statistics")
async def get_statistics(election_id: int):
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            "SELECT title, status, created_at, opened_at, closed_at FROM elections WHERE id = $1",
            election_id,
        )
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")
        total_ballots = await conn.fetchval(
            "SELECT COUNT(*) FROM encrypted_ballots WHERE election_id = $1", election_id
        )
        total_voters = await conn.fetchval(
            "SELECT COUNT(*) FROM voters WHERE election_id = $1", election_id
        )
        token_stats = await conn.fetchrow(
            """SELECT COUNT(*) AS total_tokens,
                      SUM(CASE WHEN is_used THEN 1 ELSE 0 END) AS used_tokens
               FROM voting_tokens WHERE election_id = $1""",
            election_id,
        )
    return {
        "election": {
            "title": election["title"], "status": election["status"],
            "created_at": election["created_at"].isoformat(),
            "opened_at": election["opened_at"].isoformat() if election["opened_at"] else None,
            "closed_at": election["closed_at"].isoformat() if election["closed_at"] else None,
        },
        "statistics": {
            "total_voters": total_voters,
            "total_tokens": token_stats["total_tokens"] or 0,
            "used_tokens": token_stats["used_tokens"] or 0,
            "total_votes": total_ballots,
            "turnout_rate": round(total_ballots / total_voters * 100, 2) if total_voters > 0 else 0,
        },
    }


# ==========================================================================
# 8. RECEIPT VERIFICATION
# ==========================================================================

@app.get("/receipt/{receipt_token}")
async def verify_receipt(receipt_token: str):
    async with Database.connection() as conn:
        row = await conn.fetchrow(
            """SELECT vr.receipt_token, vr.ballot_hash, vr.election_id, vr.cast_at, e.title
               FROM vote_receipts vr JOIN elections e ON e.id = vr.election_id
               WHERE vr.receipt_token = $1""",
            receipt_token,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {
        "verified": True, "receipt_token": row["receipt_token"],
        "ballot_hash": row["ballot_hash"], "election_title": row["title"],
        "cast_at": row["cast_at"].isoformat(),
    }
