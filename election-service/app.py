"""
Election Service — Election CRUD, lifecycle management, and admin UI pages.

This service owns the election bounded context end-to-end:
    - JSON API endpoints (used by other services)
    - HTML pages: dashboard, create election, election detail
    - Direct DB access for its own tables

Runs on port 5005, exposed to browsers on port 8082.
"""
import os
import secrets
import sys
import logging
from contextlib import asynccontextmanager

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Request, Form
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

from logging_config import configure_logging
configure_logging()
logger = logging.getLogger('election-service')

from database import Database
from schemas import ElectionCreate, ElectionOut, ElectionOptionOut, HealthResponse

# ── Service URLs ─────────────────────────────────────────────────────────────
AUTH_SERVICE = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5001")
ADMIN_SERVICE = os.getenv("ADMIN_SERVICE_URL", "http://admin-service:5002")

# ── Async HTTP client ────────────────────────────────────────────────────────
http_client: httpx.AsyncClient | None = None


scheduler = AsyncIOScheduler()


async def auto_manage_elections():
    """Open/close elections automatically when their scheduled time arrives."""
    try:
        async with Database.connection() as conn:
            # Open any draft elections whose scheduled_open_at has passed
            to_open = await conn.fetch(
                """
                SELECT id FROM elections
                WHERE status = 'draft'
                  AND scheduled_open_at IS NOT NULL
                  AND scheduled_open_at <= NOW()
                """
            )
            for row in to_open:
                await conn.execute(
                    "UPDATE elections SET status = 'open', opened_at = CURRENT_TIMESTAMP WHERE id = $1",
                    row["id"],
                )
                logger.info("Scheduler: auto-opened election %s", row["id"])
                # Auto-send voting tokens to all voters for this election
                try:
                    resp = await http_client.post(
                        f"{ADMIN_SERVICE}/elections/{row['id']}/tokens/generate",
                        json={"expiry_hours": 168},
                    )
                    data = resp.json()
                    logger.info(
                        "Scheduler: sent tokens for election %s — %s generated, %s emails sent",
                        row["id"], data.get("tokens_generated", 0), data.get("emails_sent", 0),
                    )
                except Exception as e:
                    logger.error("Scheduler: failed to send tokens for election %s: %s", row["id"], e)

            # Close any open elections whose scheduled_close_at has passed
            to_close = await conn.fetch(
                """
                SELECT id FROM elections
                WHERE status = 'open'
                  AND scheduled_close_at IS NOT NULL
                  AND scheduled_close_at <= NOW()
                """
            )
            for row in to_close:
                await conn.execute(
                    "UPDATE elections SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = $1",
                    row["id"],
                )
                await _tally_votes(conn, row["id"])
                logger.info("Scheduler: auto-closed election %s", row["id"])
    except Exception as e:
        logger.error("Scheduler error in auto_manage_elections: %s", e)


@asynccontextmanager
async def lifespan(application: FastAPI):
    global http_client
    await Database.get_pool()
    http_client = httpx.AsyncClient(timeout=10.0)
    scheduler.add_job(auto_manage_elections, "interval", seconds=20, id="auto_manage")
    scheduler.start()
    logger.info("Election scheduler started (20s interval)")
    yield
    scheduler.shutdown(wait=False)
    await http_client.aclose()
    await Database.close()


app = FastAPI(
    title="Election Service",
    description="Election creation, lifecycle management, and admin UI",
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
    return {"status": "healthy", "service": "election"}


@app.get("/elections")
async def list_elections(request: Request, organiser_id: int):
    """List all elections for an organiser."""
    logger.info('Request received: %s %s', request.method, request.url.path)
    async with Database.connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, description, status, created_at, opened_at, closed_at
            FROM elections
            WHERE organiser_id = $1
            ORDER BY created_at DESC
            """,
            organiser_id,
        )

    return {
        "elections": [
            {
                "id": r["id"],
                "title": r["title"],
                "description": r["description"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat(),
                "opened_at": r["opened_at"].isoformat() if r["opened_at"] else None,
                "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
            }
            for r in rows
        ]
    }


@app.post("/elections", status_code=201)
async def create_election(request: Request, organiser_id: int, data: ElectionCreate):
    """Create a new election with options."""
    logger.info('Request received: %s %s', request.method, request.url.path)
    async with Database.transaction() as conn:
        enc_key = secrets.token_hex(32)
        row = await conn.fetchrow(
            """
            INSERT INTO elections (organiser_id, title, description, status, encryption_key)
            VALUES ($1, $2, $3, 'draft', $4)
            RETURNING id
            """,
            organiser_id, data.title, data.description, enc_key,
        )
        election_id = row["id"]

        for i, option_text in enumerate(data.options):
            if option_text.strip():
                await conn.execute(
                    """
                    INSERT INTO election_options (election_id, option_text, display_order)
                    VALUES ($1, $2, $3)
                    """,
                    election_id, option_text.strip(), i,
                )

    return {"message": "Election created successfully", "election_id": election_id}


@app.get("/elections/create", response_class=HTMLResponse)
async def create_election_page(request: Request):
    logger.info('Request received: %s %s', request.method, request.url.path)
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse("create_election.html", {
        "request": request, "messages": get_flashed_messages(request),
    })


@app.post("/elections/create", response_class=HTMLResponse)
async def create_election_form(request: Request):
    logger.info('Request received: %s %s', request.method, request.url.path)
    redirect = _require_login(request)
    if redirect:
        return redirect

    from datetime import datetime

    form = await request.form()
    title = form.get("title")
    description = form.get("description", "")
    options = form.getlist("options[]")
    scheduled_open_str = form.get("scheduled_open_at", "").strip()
    scheduled_close_str = form.get("scheduled_close_at", "").strip()

    if not title or not title.strip():
        flash(request, "Election title is required", "error")
        return templates.TemplateResponse(
            "create_election.html",
            {"request": request, "messages": get_flashed_messages(request)},
        )

    valid_options = [o for o in options if o and o.strip()]
    if len(valid_options) < 2:
        flash(request, "At least 2 election options are required", "error")
        return templates.TemplateResponse(
            "create_election.html",
            {"request": request, "messages": get_flashed_messages(request)},
        )

    # Both scheduled times are mandatory
    if not scheduled_open_str or not scheduled_close_str:
        flash(request, "Both open and close times are required", "error")
        return templates.TemplateResponse(
            "create_election.html",
            {"request": request, "messages": get_flashed_messages(request)},
        )

    # Parse datetime-local values (format: "YYYY-MM-DDTHH:MM")
    try:
        scheduled_open_at = datetime.fromisoformat(scheduled_open_str)
        scheduled_close_at = datetime.fromisoformat(scheduled_close_str)
    except ValueError:
        flash(request, "Invalid date format for scheduled times", "error")
        return templates.TemplateResponse(
            "create_election.html",
            {"request": request, "messages": get_flashed_messages(request)},
        )

    if scheduled_close_at <= scheduled_open_at:
        flash(request, "Close time must be after open time", "error")
        return templates.TemplateResponse(
            "create_election.html",
            {"request": request, "messages": get_flashed_messages(request)},
        )

    async with Database.transaction() as conn:
        enc_key = secrets.token_hex(32)
        row = await conn.fetchrow(
            """
            INSERT INTO elections
                (organiser_id, title, description, status, encryption_key,
                 scheduled_open_at, scheduled_close_at)
            VALUES ($1, $2, $3, 'draft', $4, $5, $6) RETURNING id
            """,
            request.session["organiser_id"], title, description, enc_key,
            scheduled_open_at, scheduled_close_at,
        )
        election_id = row["id"]

        for i, opt in enumerate(options):
            if opt.strip():
                await conn.execute(
                    "INSERT INTO election_options (election_id, option_text, display_order) VALUES ($1, $2, $3)",
                    election_id, opt.strip(), i,
                )

    flash(request, "Election created successfully!", "success")
    return RedirectResponse(url=f"/elections/{election_id}/detail", status_code=303)


@app.get("/elections/{election_id}")
async def get_election(request: Request, election_id: int, organiser_id: int | None = None):
    """Get election details, options, voter count, and vote count."""
    logger.info('Request received: %s %s', request.method, request.url.path)
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            """
            SELECT id, title, description, status, created_at,
                   opened_at, closed_at, organiser_id
            FROM elections WHERE id = $1
            """,
            election_id,
        )

        if not election:
            raise HTTPException(status_code=404, detail="Election not found")

        if organiser_id is not None and election["organiser_id"] != organiser_id:
            raise HTTPException(status_code=403, detail="Access denied")

        options = await conn.fetch(
            """
            SELECT id, option_text, display_order
            FROM election_options
            WHERE election_id = $1
            ORDER BY display_order
            """,
            election_id,
        )

        voter_count = await conn.fetchval(
            "SELECT COUNT(*) FROM voters WHERE election_id = $1", election_id
        )
        vote_count = await conn.fetchval(
            "SELECT COUNT(*) FROM encrypted_ballots WHERE election_id = $1", election_id
        )

    return {
        "election": {
            "id": election["id"],
            "title": election["title"],
            "description": election["description"],
            "status": election["status"],
            "created_at": election["created_at"].isoformat(),
            "opened_at": election["opened_at"].isoformat() if election["opened_at"] else None,
            "closed_at": election["closed_at"].isoformat() if election["closed_at"] else None,
            "voter_count": voter_count,
            "vote_count": vote_count,
        },
        "options": [
            {"id": o["id"], "text": o["option_text"], "order": o["display_order"]}
            for o in options
        ],
    }


@app.post("/elections/{election_id}/open")
async def open_election(request: Request, election_id: int, organiser_id: int):
    """Open a draft election for voting."""
    logger.info('Request received: %s %s', request.method, request.url.path)
    async with Database.transaction() as conn:
        result = await conn.execute(
            """
            UPDATE elections
            SET status = 'open', opened_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND organiser_id = $2 AND status = 'draft'
            """,
            election_id, organiser_id,
        )

    if result == "UPDATE 0":
        raise HTTPException(
            status_code=400,
            detail="Election not found, not yours, or not in draft status",
        )

    return {"message": "Election opened successfully"}


@app.post("/elections/{election_id}/close")
async def close_election(request: Request, election_id: int, organiser_id: int):
    """Close an open election."""
    logger.info('Request received: %s %s', request.method, request.url.path)
    async with Database.transaction() as conn:
        result = await conn.execute(
            """
            UPDATE elections
            SET status = 'closed', closed_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND organiser_id = $2 AND status = 'open'
            """,
            election_id, organiser_id,
        )

        if result == "UPDATE 0":
            raise HTTPException(
                status_code=400,
                detail="Election not found, not yours, or not in open status",
            )

        await _tally_votes(conn, election_id)

    return {"message": "Election closed successfully"}


# ── Vote tallying ─────────────────────────────────────────────────────────────

async def _tally_votes(conn, election_id: int):
    """Decrypt and tally votes into tallied_votes when an election closes."""
    await conn.execute("DELETE FROM tallied_votes WHERE election_id = $1", election_id)
    await conn.execute(
        """
        INSERT INTO tallied_votes (election_id, option_id, vote_count)
        SELECT
            eb.election_id,
            pgp_sym_decrypt(eb.encrypted_vote, e.encryption_key)::integer AS option_id,
            COUNT(*) AS vote_count
        FROM encrypted_ballots eb
        JOIN elections e ON e.id = eb.election_id
        WHERE eb.election_id = $1
        GROUP BY eb.election_id,
                 pgp_sym_decrypt(eb.encrypted_vote, e.encryption_key)::integer
        """,
        election_id,
    )


# ══════════════════════════════════════════════════════════════════════════════
# HTML PAGES — served directly by this service (service-owned templates)
# ══════════════════════════════════════════════════════════════════════════════

def _require_login(request: Request):
    """Check session for organiser JWT. Redirect to auth gateway if missing."""
    if "token" not in request.session:
        return RedirectResponse(url="http://localhost/login", status_code=303)
    return None


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    logger.info('Request received: %s %s', request.method, request.url.path)
    # ── Auth hand-off: login redirect sends organiser_id & token as query params ──
    qp_token = request.query_params.get("token")
    qp_oid = request.query_params.get("organiser_id")
    if qp_token and qp_oid:
        try:
            request.session["token"] = qp_token
            request.session["organiser_id"] = int(qp_oid)
        except (ValueError, TypeError):
            pass
        # Strip query params and redirect to clean URL
        return RedirectResponse(url="/dashboard", status_code=303)

    redirect = _require_login(request)
    if redirect:
        return redirect

    organiser_id = request.session["organiser_id"]
    async with Database.connection() as conn:
        organiser = await conn.fetchrow(
            "SELECT email FROM organisers WHERE id = $1", organiser_id
        )
        if organiser:
            request.session["organiser_email"] = organiser["email"]

        rows = await conn.fetch(
            """
            SELECT e.id, e.title, e.description, e.status, e.created_at,
                   e.opened_at, e.closed_at,
                   e.scheduled_open_at, e.scheduled_close_at,
                   COUNT(v.id) AS voter_count
            FROM elections e
            LEFT JOIN voters v ON v.election_id = e.id
            WHERE e.organiser_id = $1
            GROUP BY e.id
            ORDER BY e.created_at DESC
            """,
            organiser_id,
        )

    elections = [
        {
            "id": r["id"], "title": r["title"], "description": r["description"],
            "status": r["status"], "created_at": r["created_at"].isoformat(),
            "opened_at": r["opened_at"].isoformat() if r["opened_at"] else None,
            "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
            "scheduled_open_at": r["scheduled_open_at"].isoformat() if r["scheduled_open_at"] else None,
            "scheduled_close_at": r["scheduled_close_at"].isoformat() if r["scheduled_close_at"] else None,
            "voter_count": r["voter_count"],
        }
        for r in rows
    ]

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "elections": elections,
        "messages": get_flashed_messages(request),
    })



@app.get("/elections/{election_id}/detail", response_class=HTMLResponse)
async def election_detail_page(request: Request, election_id: int):
    logger.info('Request received: %s %s', request.method, request.url.path)
    qp_token = request.query_params.get("token")
    qp_oid = request.query_params.get("organiser_id")
    if qp_token and qp_oid:
        try:
            request.session["token"] = qp_token
            request.session["organiser_id"] = int(qp_oid)
        except (ValueError, TypeError):
            pass
        return RedirectResponse(url=f"/elections/{election_id}/detail", status_code=303)

    redirect = _require_login(request)
    if redirect:
        return redirect

    organiser_id = request.session["organiser_id"]
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            """
            SELECT id, title, description, status, created_at,
                   opened_at, closed_at, organiser_id,
                   scheduled_open_at, scheduled_close_at
            FROM elections WHERE id = $1
            """,
            election_id,
        )
        if not election or election["organiser_id"] != organiser_id:
            flash(request, "Election not found or access denied", "danger")
            return RedirectResponse(url="/dashboard", status_code=303)

        options = await conn.fetch(
            "SELECT id, option_text, display_order FROM election_options WHERE election_id = $1 ORDER BY display_order",
            election_id,
        )
        voter_count = await conn.fetchval("SELECT COUNT(*) FROM voters WHERE election_id = $1", election_id)
        vote_count = await conn.fetchval("SELECT COUNT(*) FROM encrypted_ballots WHERE election_id = $1", election_id)

    return templates.TemplateResponse("election_detail.html", {
        "request": request,
        "election": {
            "id": election["id"], "title": election["title"],
            "description": election["description"], "status": election["status"],
            "created_at": election["created_at"].isoformat(),
            "opened_at": election["opened_at"].isoformat() if election["opened_at"] else None,
            "closed_at": election["closed_at"].isoformat() if election["closed_at"] else None,
            "scheduled_open_at": election["scheduled_open_at"].isoformat() if election["scheduled_open_at"] else None,
            "scheduled_close_at": election["scheduled_close_at"].isoformat() if election["scheduled_close_at"] else None,
            "voter_count": voter_count, "vote_count": vote_count,
        },
        "options": [{"id": o["id"], "text": o["option_text"], "order": o["display_order"]} for o in options],
        "messages": get_flashed_messages(request),
    })


@app.post("/elections/{election_id}/open/confirm")
async def open_election_form(request: Request, election_id: int):
    logger.info('Request received: %s %s', request.method, request.url.path)
    redirect = _require_login(request)
    if redirect:
        return redirect

    organiser_id = request.session["organiser_id"]
    async with Database.transaction() as conn:
        result = await conn.execute(
            "UPDATE elections SET status = 'open', opened_at = CURRENT_TIMESTAMP WHERE id = $1 AND organiser_id = $2 AND status = 'draft'",
            election_id, organiser_id,
        )

    if result == "UPDATE 0":
        flash(request, "Cannot open election", "danger")
    else:
        flash(request, "Election opened successfully!", "success")

    return RedirectResponse(url=f"/elections/{election_id}/detail", status_code=303)


@app.post("/elections/{election_id}/close/confirm")
async def close_election_form(request: Request, election_id: int):
    logger.info('Request received: %s %s', request.method, request.url.path)
    redirect = _require_login(request)
    if redirect:
        return redirect

    organiser_id = request.session["organiser_id"]
    async with Database.transaction() as conn:
        result = await conn.execute(
            "UPDATE elections SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = $1 AND organiser_id = $2 AND status = 'open'",
            election_id, organiser_id,
        )

        if result != "UPDATE 0":
            await _tally_votes(conn, election_id)

    if result == "UPDATE 0":
        flash(request, "Cannot close election", "danger")
    else:
        flash(request, "Election closed successfully!", "success")

    return RedirectResponse(url=f"/elections/{election_id}/detail", status_code=303)
