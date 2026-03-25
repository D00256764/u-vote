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
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
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

from logging_config import configure_logging
configure_logging()
logger = logging.getLogger('admin-service')

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

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

def flash(request: Request, message: str, category: str = "info"):
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})


def get_flashed_messages(request: Request) -> list[dict]:
    return request.session.pop("_messages", [])


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health(request: Request):
    logger.info('Request received: %s %s', request.method, request.url.path)
    return {"status": "healthy", "service": "admin"}


@app.get("/elections/{election_id}/voters/csv-template")
async def csv_template(election_id: int):
    """Download a blank CSV template for voter upload."""
    content = "email,phone_number\nexample@university.edu,+353871234567\n"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=voters-template.csv"},
    )


@app.post("/elections/{election_id}/voters/upload", status_code=201)
async def upload_voters(request: Request, election_id: int, file: UploadFile = File(...)):
    """Upload voter list from CSV (requires email column; phone_number optional)."""
    logger.info('Request received: %s %s', request.method, request.url.path)
    contents = await file.read()
    csv_data = contents.decode("utf-8")
    reader = csv.DictReader(StringIO(csv_data))

    if reader.fieldnames is None or "email" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail='CSV must have an "email" column')

    voters_added = 0
    voters_skipped = 0

    async with Database.transaction() as conn:
        for row in reader:
            email = row.get("email", "").strip()
            phone = row.get("phone_number", "").strip() or None
            if not email:
                voters_skipped += 1
                continue
            try:
                await conn.execute(
                    "INSERT INTO voters (election_id, email, phone_number) VALUES ($1, $2, $3)",
                    election_id, email, phone,
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
async def add_voter(request: Request, election_id: int, data: VoterAddRequest):
    """Add a single voter."""
    logger.info('Request received: %s %s', request.method, request.url.path)
    try:
        async with Database.transaction() as conn:
            row = await conn.fetchrow(
                "INSERT INTO voters (election_id, email, phone_number) VALUES ($1, $2, $3) RETURNING id",
                election_id, data.email, data.phone_number or None,
            )
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Voter already exists for this election")
        logger.error('Database error in add_voter: %s', e)
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"message": "Voter added successfully", "voter_id": row["id"]}


@app.get("/elections/{election_id}/voters")
async def get_voters(request: Request, election_id: int):
    """Get all voters for an election."""
    logger.info('Request received: %s %s', request.method, request.url.path)
    async with Database.connection() as conn:
        rows = await conn.fetch(
            """
            SELECT v.id, v.email, v.phone_number, v.created_at,
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
                "phone_number": r["phone_number"] or "",
                "created_at": r["created_at"].isoformat(),
                "has_token": r["has_token"],
            }
            for r in rows
        ]
    }


@app.post("/elections/{election_id}/tokens/generate", status_code=200)
async def generate_tokens(request: Request, election_id: int, data: TokenGenerateRequest | None = None):
    """Generate voting tokens for all voters without an active token, then email each voter."""
    logger.info('Request received: %s %s', request.method, request.url.path)
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
            logger.error('Failed to send email: %s', e)

    return {
        "message": "Tokens generated and emails sent",
        "tokens_generated": len(generated_tokens),
        "emails_sent": emails_sent,
        "emails_failed": emails_failed,
        "tokens": generated_tokens,
    }


@app.get("/tokens/{token}/validate", response_model=TokenValidateResponse)
async def validate_token(request: Request, token: str):
    """Validate a voting token."""
    logger.info('Request received: %s %s', request.method, request.url.path)
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


# ══════════════════════════════════════════════════════════════════════════════
# HTML PAGES — served directly by this service (service-owned templates)
# ══════════════════════════════════════════════════════════════════════════════

def _require_login(request: Request):
    if "token" not in request.session:
        return RedirectResponse(url="http://localhost/login", status_code=303)
    return None


@app.get("/elections/{election_id}/voters/manage", response_class=HTMLResponse)
async def manage_voters_page(request: Request, election_id: int):
    """Render the voter management page — owned by this service."""
    logger.info('Request received: %s %s', request.method, request.url.path)
    # Auth handoff: accept token & organiser_id as query params (same pattern as election-service dashboard)
    qp_token = request.query_params.get("token")
    qp_oid = request.query_params.get("organiser_id")
    if qp_token and qp_oid:
        try:
            request.session["token"] = qp_token
            request.session["organiser_id"] = int(qp_oid)
        except (ValueError, TypeError):
            pass
        return RedirectResponse(url=f"/elections/{election_id}/voters/manage", status_code=303)

    redirect = _require_login(request)
    if redirect:
        return redirect

    async with Database.connection() as conn:
        rows = await conn.fetch(
            """
            SELECT v.id, v.email, v.phone_number, v.created_at,
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
            "phone_number": r["phone_number"] or "",
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
    logger.info('Request received: %s %s', request.method, request.url.path)
    redirect = _require_login(request)
    if redirect:
        return redirect

    contents = await file.read()
    csv_data = contents.decode("utf-8")
    reader = csv.DictReader(StringIO(csv_data))

    if reader.fieldnames is None or "email" not in reader.fieldnames:
        flash(request, 'CSV must have an "email" column', "danger")
        return RedirectResponse(url=f"/elections/{election_id}/voters/manage", status_code=303)

    voters_added = 0
    voters_skipped = 0

    async with Database.transaction() as conn:
        for row in reader:
            email = row.get("email", "").strip()
            phone = row.get("phone_number", "").strip() or None
            if not email:
                voters_skipped += 1
                continue
            try:
                await conn.execute(
                    "INSERT INTO voters (election_id, email, phone_number) VALUES ($1, $2, $3)",
                    election_id, email, phone,
                )
                voters_added += 1
            except Exception:
                voters_skipped += 1

    flash(request, f"Uploaded {voters_added} voters (skipped {voters_skipped} duplicates)", "success")

    # If the election is already open, immediately send tokens to the new voters
    if voters_added > 0:
        async with Database.connection() as conn:
            status_row = await conn.fetchrow(
                "SELECT status FROM elections WHERE id = $1", election_id
            )
        if status_row and status_row["status"] == "open":
            await generate_tokens(request, election_id)
            flash(request, "Election is already open — tokens sent to new voters automatically.", "info")

    return RedirectResponse(url=f"/elections/{election_id}/voters/manage", status_code=303)


@app.post("/elections/{election_id}/tokens/generate/form")
async def generate_tokens_form(request: Request, election_id: int):
    """HTML form handler for token generation — redirects back to manage voters page."""
    logger.info('Request received: %s %s', request.method, request.url.path)
    redirect = _require_login(request)
    if redirect:
        return redirect

    async with Database.transaction() as conn:
        election_row = await conn.fetchrow(
            "SELECT title FROM elections WHERE id = $1", election_id,
        )
        if not election_row:
            flash(request, "Election not found", "danger")
            return RedirectResponse(url=f"/elections/{election_id}/voters/manage", status_code=303)

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
            logger.error('Failed to send email: %s', e)

    msg = f"Generated {len(generated_tokens)} tokens — {emails_sent} emails sent"
    if emails_failed:
        msg += f" ({emails_failed} failed)"
    flash(request, msg, "success")

    return RedirectResponse(url=f"/elections/{election_id}/voters/manage", status_code=303)
