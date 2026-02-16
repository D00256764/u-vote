"""
Voting Service - The voter-facing web application (Application 2).

This is a SEPARATE application from the admin frontend.
It owns the entire voter experience:
    1. Token validation (via auth-service)
    2. Identity verification / MFA (via auth-service)
    3. Blind ballot-token acquisition (via auth-service)
    4. Ballot presentation (direct DB read)
    5. Encrypted vote submission (direct DB write)
    6. Vote receipt verification

Anonymity architecture:
    - The voter authenticates with their voting_token + DOB
    - Auth-service issues a blind ballot_token (unlinkable to voter)
    - This service encrypts the vote choice with pgp_sym_encrypt
    - The encrypted ballot is stored with NO voter identity
    - The voter receives a receipt_token to verify their ballot was counted

Runs on port 5003, exposed to voters on port 8081.
"""

import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
from security import generate_receipt_token
from schemas import HealthResponse

# -- Service URLs -------------------------------------------------------------
AUTH_SERVICE = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5001")

# -- Async HTTP client --------------------------------------------------------
http_client = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    global http_client
    await Database.get_pool()
    http_client = httpx.AsyncClient(timeout=10.0)
    yield
    await http_client.aclose()
    await Database.close()


app = FastAPI(
    title="Voting Service",
    description="Voter-facing application - identity verification and anonymous vote casting",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# -- Helpers ------------------------------------------------------------------

def safe_json(resp, fallback=None):
    try:
        return resp.json()
    except Exception:
        return fallback or {}


def _error_page(request, error):
    return templates.TemplateResponse("vote_error.html", {
        "request": request, "error": error, "messages": [],
    })


# -- Health -------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "healthy", "service": "voting"}


# -- Receipt verification (public) -------------------------------------------

@app.get("/receipt/{receipt_token}")
async def verify_receipt(receipt_token: str):
    """Public endpoint: verify a vote receipt was recorded."""
    async with Database.connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT vr.receipt_token, vr.ballot_hash, vr.election_id, vr.cast_at,
                   e.title
            FROM vote_receipts vr
            JOIN elections e ON e.id = vr.election_id
            WHERE vr.receipt_token = $1
            """,
            receipt_token,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return {
        "verified": True,
        "receipt_token": row["receipt_token"],
        "ballot_hash": row["ballot_hash"],
        "election_title": row["title"],
        "cast_at": row["cast_at"].isoformat(),
    }


# ==========================================================================
# VOTER-FACING WEB PAGES - the complete voting journey
#
#   GET  /vote/{token}           -> validate token -> show identity form
#   POST /vote/verify-identity   -> verify DOB via auth-service -> get ballot token -> show ballot
#   POST /vote/submit            -> encrypt vote -> store in encrypted_ballots -> show receipt
#   GET  /vote/verify/{receipt}  -> verify receipt page
# ==========================================================================

@app.get("/vote/{token}", response_class=HTMLResponse)
async def vote_landing(request: Request, token: str):
    """Step 1 - Validate voting token and show identity verification form."""

    # Validate token via auth-service
    resp = await http_client.get(f"{AUTH_SERVICE}/tokens/{token}/validate")

    if resp.status_code != 200:
        error = safe_json(resp).get("detail", "Invalid or expired voting link")
        return _error_page(request, error)

    # Check if MFA already completed
    mfa_resp = await http_client.get(
        f"{AUTH_SERVICE}/mfa/status", params={"token": token}
    )
    if mfa_resp.status_code == 200 and safe_json(mfa_resp).get("mfa_verified"):
        # MFA done but ballot token not yet issued - show ballot token step
        election_id = safe_json(resp).get("election_id")
        return await _acquire_ballot_and_show(request, token, election_id)

    return templates.TemplateResponse("verify_identity.html", {
        "request": request, "token": token, "messages": [],
    })


@app.post("/vote/verify-identity", response_class=HTMLResponse)
async def verify_identity(request: Request, token: str = Form(...),
                          date_of_birth: str = Form(...)):
    """Step 2 - Verify DOB via auth-service, acquire ballot token, show ballot."""

    # Verify identity via auth-service
    verify_resp = await http_client.post(
        f"{AUTH_SERVICE}/mfa/verify",
        params={"token": token, "date_of_birth": date_of_birth},
    )

    if verify_resp.status_code != 200:
        error = safe_json(verify_resp).get("detail", "Verification failed")
        return templates.TemplateResponse("verify_identity.html", {
            "request": request,
            "token": token,
            "messages": [{"category": "danger", "message": error}],
        })

    # MFA passed - get election_id
    validate_resp = await http_client.get(
        f"{AUTH_SERVICE}/tokens/{token}/validate"
    )
    if validate_resp.status_code != 200:
        return _error_page(request, "Token validation failed")

    election_id = safe_json(validate_resp).get("election_id")
    return await _acquire_ballot_and_show(request, token, election_id)


@app.post("/vote/submit", response_class=HTMLResponse)
async def submit_vote(request: Request, ballot_token: str = Form(...),
                      option_id: int = Form(...), election_id: int = Form(...)):
    """Step 3 - Cast an encrypted vote using the blind ballot token."""

    async with Database.transaction() as conn:
        # Validate the blind ballot token
        bt_row = await conn.fetchrow(
            """
            SELECT id, election_id, is_used
            FROM blind_tokens
            WHERE ballot_token = $1 AND election_id = $2
            FOR UPDATE
            """,
            ballot_token, election_id,
        )

        if not bt_row:
            return _error_page(request, "Invalid ballot token")
        if bt_row["is_used"]:
            return _error_page(request, "This ballot token has already been used")

        # Verify election is open
        election = await conn.fetchrow(
            "SELECT status, encryption_key FROM elections WHERE id = $1",
            election_id,
        )
        if not election or election["status"] != "open":
            return _error_page(request, "Election is not currently open")

        # Verify option exists
        opt = await conn.fetchrow(
            "SELECT id FROM election_options WHERE id = $1 AND election_id = $2",
            option_id, election_id,
        )
        if not opt:
            return _error_page(request, "Invalid option for this election")

        # Get encryption key
        enc_key = election["encryption_key"]
        if not enc_key:
            return _error_page(request, "Election encryption not configured")

        # Get previous ballot hash for hash chain
        prev = await conn.fetchrow(
            "SELECT ballot_hash FROM encrypted_ballots "
            "WHERE election_id = $1 ORDER BY id DESC LIMIT 1",
            election_id,
        )
        previous_hash = prev["ballot_hash"] if prev else None

        # Generate receipt token
        receipt = generate_receipt_token()

        # Encrypt the vote choice using pgp_sym_encrypt
        # The DB admin sees only ciphertext - cannot determine the choice
        await conn.execute(
            """
            INSERT INTO encrypted_ballots
                (election_id, encrypted_vote, previous_hash, receipt_token)
            VALUES (
                $1,
                pgp_sym_encrypt($2::text, $3),
                $4,
                $5
            )
            """,
            election_id, str(option_id), enc_key, previous_hash, receipt,
        )

        # Create vote receipt (so voter can verify later)
        # We fetch the ballot_hash that was auto-generated by the trigger
        ballot_row = await conn.fetchrow(
            "SELECT ballot_hash FROM encrypted_ballots WHERE receipt_token = $1",
            receipt,
        )
        await conn.execute(
            """
            INSERT INTO vote_receipts (election_id, receipt_token, ballot_hash)
            VALUES ($1, $2, $3)
            """,
            election_id, receipt, ballot_row["ballot_hash"],
        )

        # Mark blind ballot token as used
        await conn.execute(
            "UPDATE blind_tokens SET is_used = TRUE, used_at = CURRENT_TIMESTAMP "
            "WHERE id = $1",
            bt_row["id"],
        )

        # Audit log
        await conn.execute(
            """
            INSERT INTO audit_log (event_type, election_id, actor_type, detail)
            VALUES ('ballot_cast', $1, 'voter',
                    $2::jsonb)
            """,
            election_id,
            f'{{"receipt_token": "{receipt}", "note": "encrypted ballot cast anonymously"}}',
        )

    return templates.TemplateResponse("vote_success.html", {
        "request": request,
        "receipt_token": receipt,
        "ballot_hash": ballot_row["ballot_hash"],
        "messages": [],
    })


@app.get("/vote/verify/{receipt_token}", response_class=HTMLResponse)
async def verify_receipt_page(request: Request, receipt_token: str):
    """Page where a voter can verify their vote receipt."""
    async with Database.connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT vr.receipt_token, vr.ballot_hash, vr.cast_at, e.title
            FROM vote_receipts vr
            JOIN elections e ON e.id = vr.election_id
            WHERE vr.receipt_token = $1
            """,
            receipt_token,
        )

    if not row:
        return _error_page(request, "Receipt not found. Check your receipt token.")

    return templates.TemplateResponse("vote_verified.html", {
        "request": request,
        "receipt_token": row["receipt_token"],
        "ballot_hash": row["ballot_hash"],
        "election_title": row["title"],
        "cast_at": row["cast_at"].isoformat(),
        "messages": [],
    })


# -- Internal helpers ---------------------------------------------------------

async def _acquire_ballot_and_show(request, token, election_id):
    """Issue a blind ballot token via auth-service and show the ballot."""

    # Ask auth-service to issue a blind ballot token
    issue_resp = await http_client.post(
        f"{AUTH_SERVICE}/ballot-token/issue",
        params={"token": token},
    )

    if issue_resp.status_code != 200:
        error = safe_json(issue_resp).get("detail", "Could not issue ballot token")
        return _error_page(request, error)

    data = safe_json(issue_resp)
    ballot_token = data["ballot_token"]
    eid = data["election_id"]

    # Fetch election + options from DB (this is our bounded context)
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            "SELECT id, title, description FROM elections WHERE id = $1", eid
        )
        options = await conn.fetch(
            """
            SELECT id, option_text, display_order
            FROM election_options WHERE election_id = $1
            ORDER BY display_order, id
            """,
            eid,
        )

    if not election:
        return _error_page(request, "Election not found")

    return templates.TemplateResponse("vote.html", {
        "request": request,
        "ballot_token": ballot_token,
        "election": {
            "id": election["id"],
            "title": election["title"],
            "description": election["description"],
        },
        "options": [
            {"id": o["id"], "text": o["option_text"], "order": o["display_order"]}
            for o in options
        ],
        "messages": [],
    })
