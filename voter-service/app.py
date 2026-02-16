"""
Voter Service — Voter list management, token generation, MFA, and voter-management UI.

This service owns the voter bounded context end-to-end:
    - JSON API endpoints (used by other services)
    - HTML page: manage voters (upload CSV, generate tokens, view list)
    - Direct DB access for voters, voting_tokens, voter_mfa tables

Runs on port 5002, exposed to browsers on port 8083.
"""
import os
import sys
import csv
import logging
from io import StringIO
from contextlib import asynccontextmanager
from datetime import datetime, date

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# ── Shared imports ───────────────────────────────────────────────────────────
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
from security import generate_voting_token, generate_token_expiry
from email_util import send_voting_token_email
from schemas import (
    VoterAddRequest, VoterOut, TokenGenerateRequest,
    GeneratedToken, TokenValidateResponse, HealthResponse, ErrorResponse,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    await Database.get_pool()
    yield
    await Database.close()


app = FastAPI(
    title="Voter Service",
    description="Voter list management, token generation, MFA, and admin UI",
    lifespan=lifespan,
)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "change-me"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def flash(request: Request, message: str, category: str = "info"):
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})


def get_flashed_messages(request: Request) -> list[dict]:
    return request.session.pop("_messages", [])


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "healthy", "service": "voter"}


@app.post("/elections/{election_id}/voters/upload", status_code=201)
async def upload_voters(election_id: int, file: UploadFile = File(...)):
    """Upload voter list from CSV (requires email and date_of_birth columns)."""
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

    return {
        "message": "Voters uploaded successfully",
        "voters_added": voters_added,
        "voters_skipped": voters_skipped,
    }


@app.post("/elections/{election_id}/voters", status_code=201)
async def add_voter(election_id: int, data: VoterAddRequest):
    """Add a single voter."""
    try:
        dob = date.fromisoformat(data.date_of_birth) if isinstance(data.date_of_birth, str) else data.date_of_birth
        async with Database.transaction() as conn:
            row = await conn.fetchrow(
                "INSERT INTO voters (election_id, email, date_of_birth) VALUES ($1, $2, $3) RETURNING id",
                election_id, data.email, dob,
            )
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Voter already exists for this election")
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Voter added successfully", "voter_id": row["id"]}


@app.get("/elections/{election_id}/voters")
async def get_voters(election_id: int):
    """Get all voters for an election."""
    async with Database.connection() as conn:
        rows = await conn.fetch(
            """
            SELECT v.id, v.email, v.date_of_birth, v.created_at,
                   EXISTS(SELECT 1 FROM voting_tokens WHERE voter_id = v.id) AS has_token
            FROM voters v
            WHERE v.election_id = $1
            ORDER BY v.created_at DESC
            """,
            election_id,
        )

    return {
        "voters": [
            {
                "id": r["id"],
                "email": r["email"],
                "date_of_birth": r["date_of_birth"].isoformat(),
                "created_at": r["created_at"].isoformat(),
                "has_token": r["has_token"],
            }
            for r in rows
        ]
    }


@app.post("/elections/{election_id}/tokens/generate", status_code=201)
async def generate_tokens(election_id: int, data: TokenGenerateRequest | None = None):
    """Generate voting tokens for all voters without an active token, then email each voter."""
    import logging
    logger = logging.getLogger(__name__)

    expiry_hours = data.expiry_hours if data else 168

    async with Database.transaction() as conn:
        # Fetch election title for the email subject
        election_row = await conn.fetchrow(
            "SELECT title FROM elections WHERE id = $1", election_id,
        )
        if not election_row:
            raise HTTPException(status_code=404, detail="Election not found")

        election_title = election_row["title"]

        voters = await conn.fetch(
            """
            SELECT v.id FROM voters v
            WHERE v.election_id = $1
              AND NOT EXISTS (
                  SELECT 1 FROM voting_tokens vt
                  WHERE vt.voter_id = v.id AND vt.is_used = FALSE
              )
            """,
            election_id,
        )

        generated_tokens: list[dict] = []

        for voter in voters:
            token = generate_voting_token()
            expires_at = generate_token_expiry(expiry_hours)

            await conn.execute(
                """
                INSERT INTO voting_tokens (token, voter_id, election_id, expires_at)
                VALUES ($1, $2, $3, $4)
                """,
                token, voter["id"], election_id, expires_at,
            )

            email_row = await conn.fetchrow(
                "SELECT email FROM voters WHERE id = $1", voter["id"]
            )

            generated_tokens.append({
                "email": email_row["email"],
                "token": token,
                "expires_at": expires_at.isoformat(),
            })

    # Send emails outside the DB transaction so a mail failure doesn't roll back tokens
    emails_sent = 0
    emails_failed = 0
    for t in generated_tokens:
        try:
            await send_voting_token_email(
                to_email=t["email"],
                token=t["token"],
                election_title=election_title,
                expires_at=t["expires_at"],
            )
            emails_sent += 1
        except Exception as e:
            emails_failed += 1
            logger.error(f"Failed to email {t['email']}: {e}")

    return {
        "message": "Tokens generated and emails sent",
        "tokens_generated": len(generated_tokens),
        "emails_sent": emails_sent,
        "emails_failed": emails_failed,
        "tokens": generated_tokens,
    }


@app.get("/tokens/{token}/validate", response_model=TokenValidateResponse)
async def validate_token(token: str):
    """Validate a voting token."""
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


# ── MFA Endpoints (Date of Birth Verification) ──────────────────────────────

@app.post("/mfa/verify", status_code=200)
async def verify_identity(token: str, date_of_birth: str):
    """Verify voter identity by checking date of birth against stored value."""
    try:
        submitted_dob = date.fromisoformat(date_of_birth)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (expected YYYY-MM-DD)")

    async with Database.transaction() as conn:
        # Look up the voter linked to this token and compare DOB
        row = await conn.fetchrow(
            """
            SELECT v.date_of_birth, vt.is_used, vt.expires_at, e.status
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

        # Compare dates
        if row["date_of_birth"] != submitted_dob:
            raise HTTPException(status_code=403, detail="Date of birth does not match our records")

        # Check if already verified
        existing = await conn.fetchrow(
            "SELECT id FROM voter_mfa WHERE token = $1", token,
        )
        if not existing:
            await conn.execute(
                "INSERT INTO voter_mfa (token) VALUES ($1)", token,
            )

    return {"verified": True}


@app.get("/mfa/status")
async def mfa_status(token: str):
    """Check if a token has passed MFA (DOB verified)."""
    async with Database.connection() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM voter_mfa WHERE token = $1", token,
        )

    return {"mfa_verified": row is not None}


# ══════════════════════════════════════════════════════════════════════════════
# HTML PAGES — served directly by this service (service-owned templates)
# ══════════════════════════════════════════════════════════════════════════════

def _require_login(request: Request):
    if "token" not in request.session:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)
    return None


@app.get("/elections/{election_id}/voters", response_class=HTMLResponse)
async def manage_voters_page(request: Request, election_id: int):
    """Render the voter management page — owned by this service."""
    redirect = _require_login(request)
    if redirect:
        return redirect

    async with Database.connection() as conn:
        rows = await conn.fetch(
            """
            SELECT v.id, v.email, v.date_of_birth, v.created_at,
                   EXISTS(SELECT 1 FROM voting_tokens WHERE voter_id = v.id) AS has_token
            FROM voters v WHERE v.election_id = $1 ORDER BY v.created_at DESC
            """,
            election_id,
        )

        election_row = await conn.fetchrow(
            "SELECT title FROM elections WHERE id = $1", election_id,
        )

    voters = [
        {
            "id": r["id"], "email": r["email"],
            "date_of_birth": r["date_of_birth"].isoformat(),
            "created_at": r["created_at"].isoformat(),
            "has_token": r["has_token"],
        }
        for r in rows
    ]

    return templates.TemplateResponse("manage_voters.html", {
        "request": request,
        "election_id": election_id,
        "election_title": election_row["title"] if election_row else "",
        "voters": voters,
        "messages": get_flashed_messages(request),
    })


@app.post("/elections/{election_id}/voters/upload/form")
async def upload_voters_form(request: Request, election_id: int, file: UploadFile = File(...)):
    """HTML form handler for CSV upload — redirects back to manage voters page."""
    redirect = _require_login(request)
    if redirect:
        return redirect

    contents = await file.read()
    csv_data = contents.decode("utf-8")
    reader = csv.DictReader(StringIO(csv_data))

    if reader.fieldnames is None or "email" not in reader.fieldnames:
        flash(request, 'CSV must have an "email" column', "danger")
        return RedirectResponse(url=f"/elections/{election_id}/voters", status_code=303)

    if "date_of_birth" not in reader.fieldnames:
        flash(request, 'CSV must have a "date_of_birth" column (YYYY-MM-DD)', "danger")
        return RedirectResponse(url=f"/elections/{election_id}/voters", status_code=303)

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

    flash(request, f"Uploaded {voters_added} voters (skipped {voters_skipped} duplicates)", "success")
    return RedirectResponse(url=f"/elections/{election_id}/voters", status_code=303)


@app.post("/elections/{election_id}/tokens/generate/form")
async def generate_tokens_form(request: Request, election_id: int):
    """HTML form handler for token generation — redirects back to manage voters page."""
    redirect = _require_login(request)
    if redirect:
        return redirect

    async with Database.transaction() as conn:
        election_row = await conn.fetchrow(
            "SELECT title FROM elections WHERE id = $1", election_id,
        )
        if not election_row:
            flash(request, "Election not found", "danger")
            return RedirectResponse(url=f"/elections/{election_id}/voters", status_code=303)

        election_title = election_row["title"]

        voters = await conn.fetch(
            """
            SELECT v.id FROM voters v
            WHERE v.election_id = $1
              AND NOT EXISTS (
                  SELECT 1 FROM voting_tokens vt
                  WHERE vt.voter_id = v.id AND vt.is_used = FALSE
              )
            """,
            election_id,
        )

        generated_tokens: list[dict] = []
        for voter in voters:
            token = generate_voting_token()
            expires_at = generate_token_expiry(168)

            await conn.execute(
                "INSERT INTO voting_tokens (token, voter_id, election_id, expires_at) VALUES ($1, $2, $3, $4)",
                token, voter["id"], election_id, expires_at,
            )

            email_row = await conn.fetchrow("SELECT email FROM voters WHERE id = $1", voter["id"])
            generated_tokens.append({
                "email": email_row["email"], "token": token,
                "expires_at": expires_at.isoformat(),
            })

    emails_sent = 0
    emails_failed = 0
    for t in generated_tokens:
        try:
            await send_voting_token_email(
                to_email=t["email"], token=t["token"],
                election_title=election_title, expires_at=t["expires_at"],
            )
            emails_sent += 1
        except Exception as e:
            emails_failed += 1
            logger.error(f"Failed to email {t['email']}: {e}")

    msg = f"Generated {len(generated_tokens)} tokens — {emails_sent} emails sent"
    if emails_failed:
        msg += f" ({emails_failed} failed)"
    flash(request, msg, "success")

    return RedirectResponse(url=f"/elections/{election_id}/voters", status_code=303)
