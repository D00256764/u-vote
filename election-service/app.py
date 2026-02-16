"""
Election Service — Election CRUD, lifecycle management, and admin UI pages.

This service owns the election bounded context end-to-end:
    - JSON API endpoints (used by other services)
    - HTML pages: dashboard, create election, election detail
    - Direct DB access for its own tables

Runs on port 5005, exposed to browsers on port 8082.
"""
import os
import sys
from contextlib import asynccontextmanager

import httpx
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

from database import Database
from schemas import ElectionCreate, ElectionOut, ElectionOptionOut, HealthResponse

# ── Service URLs (for JWT verification) ──────────────────────────────────────
AUTH_SERVICE = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5001")

# ── Async HTTP client ────────────────────────────────────────────────────────
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    global http_client
    await Database.get_pool()
    http_client = httpx.AsyncClient(timeout=10.0)
    yield
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
    return {"status": "healthy", "service": "election"}


@app.get("/elections")
async def list_elections(organizer_id: int):
    """List all elections for an organizer."""
    async with Database.connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, description, status, created_at, opened_at, closed_at
            FROM elections
            WHERE organizer_id = $1
            ORDER BY created_at DESC
            """,
            organizer_id,
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
async def create_election(organizer_id: int, data: ElectionCreate):
    """Create a new election with options."""
    async with Database.transaction() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO elections (organizer_id, title, description, status)
            VALUES ($1, $2, $3, 'draft')
            RETURNING id
            """,
            organizer_id, data.title, data.description,
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


@app.get("/elections/{election_id}")
async def get_election(election_id: int, organizer_id: int | None = None):
    """Get election details, options, voter count, and vote count."""
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            """
            SELECT id, title, description, status, created_at,
                   opened_at, closed_at, organizer_id
            FROM elections WHERE id = $1
            """,
            election_id,
        )

        if not election:
            raise HTTPException(status_code=404, detail="Election not found")

        if organizer_id is not None and election["organizer_id"] != organizer_id:
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
            "SELECT COUNT(*) FROM votes WHERE election_id = $1", election_id
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
async def open_election(election_id: int, organizer_id: int):
    """Open a draft election for voting."""
    async with Database.transaction() as conn:
        result = await conn.execute(
            """
            UPDATE elections
            SET status = 'open', opened_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND organizer_id = $2 AND status = 'draft'
            """,
            election_id, organizer_id,
        )

    if result == "UPDATE 0":
        raise HTTPException(
            status_code=400,
            detail="Election not found, not yours, or not in draft status",
        )

    return {"message": "Election opened successfully"}


@app.post("/elections/{election_id}/close")
async def close_election(election_id: int, organizer_id: int):
    """Close an open election."""
    async with Database.transaction() as conn:
        result = await conn.execute(
            """
            UPDATE elections
            SET status = 'closed', closed_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND organizer_id = $2 AND status = 'open'
            """,
            election_id, organizer_id,
        )

    if result == "UPDATE 0":
        raise HTTPException(
            status_code=400,
            detail="Election not found, not yours, or not in open status",
        )

    return {"message": "Election closed successfully"}


# ══════════════════════════════════════════════════════════════════════════════
# HTML PAGES — served directly by this service (service-owned templates)
# ══════════════════════════════════════════════════════════════════════════════

def _require_login(request: Request):
    """Check session for organiser JWT. Redirect to auth gateway if missing."""
    if "token" not in request.session:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)
    return None


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    # ── Auth hand-off: login redirect sends organizer_id & token as query params ──
    qp_token = request.query_params.get("token")
    qp_oid = request.query_params.get("organizer_id")
    if qp_token and qp_oid:
        try:
            request.session["token"] = qp_token
            request.session["organizer_id"] = int(qp_oid)
        except (ValueError, TypeError):
            pass
        # Strip query params and redirect to clean URL
        return RedirectResponse(url="/dashboard", status_code=303)

    redirect = _require_login(request)
    if redirect:
        return redirect

    organizer_id = request.session["organizer_id"]
    async with Database.connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, description, status, created_at, opened_at, closed_at
            FROM elections WHERE organizer_id = $1 ORDER BY created_at DESC
            """,
            organizer_id,
        )

    elections = [
        {
            "id": r["id"], "title": r["title"], "description": r["description"],
            "status": r["status"], "created_at": r["created_at"].isoformat(),
            "opened_at": r["opened_at"].isoformat() if r["opened_at"] else None,
            "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
        }
        for r in rows
    ]

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "elections": elections,
        "messages": get_flashed_messages(request),
    })


@app.get("/elections/create", response_class=HTMLResponse)
async def create_election_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse("create_election.html", {
        "request": request, "messages": get_flashed_messages(request),
    })


@app.post("/elections/create", response_class=HTMLResponse)
async def create_election_form(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect

    form = await request.form()
    title = form.get("title")
    description = form.get("description", "")
    options = form.getlist("options[]")

    async with Database.transaction() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO elections (organizer_id, title, description, status)
            VALUES ($1, $2, $3, 'draft') RETURNING id
            """,
            request.session["organizer_id"], title, description,
        )
        election_id = row["id"]

        for i, opt in enumerate(options):
            if opt.strip():
                await conn.execute(
                    "INSERT INTO election_options (election_id, option_text, display_order) VALUES ($1, $2, $3)",
                    election_id, opt.strip(), i,
                )

    flash(request, "Election created successfully!", "success")
    return RedirectResponse(url=f"/elections/{election_id}", status_code=303)


@app.get("/elections/{election_id}/detail", response_class=HTMLResponse)
async def election_detail_page(request: Request, election_id: int):
    redirect = _require_login(request)
    if redirect:
        return redirect

    organizer_id = request.session["organizer_id"]
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            """
            SELECT id, title, description, status, created_at,
                   opened_at, closed_at, organizer_id
            FROM elections WHERE id = $1
            """,
            election_id,
        )
        if not election or election["organizer_id"] != organizer_id:
            flash(request, "Election not found or access denied", "danger")
            return RedirectResponse(url="/dashboard", status_code=303)

        options = await conn.fetch(
            "SELECT id, option_text, display_order FROM election_options WHERE election_id = $1 ORDER BY display_order",
            election_id,
        )
        voter_count = await conn.fetchval("SELECT COUNT(*) FROM voters WHERE election_id = $1", election_id)
        vote_count = await conn.fetchval("SELECT COUNT(*) FROM votes WHERE election_id = $1", election_id)

    return templates.TemplateResponse("election_detail.html", {
        "request": request,
        "election": {
            "id": election["id"], "title": election["title"],
            "description": election["description"], "status": election["status"],
            "created_at": election["created_at"].isoformat(),
            "opened_at": election["opened_at"].isoformat() if election["opened_at"] else None,
            "closed_at": election["closed_at"].isoformat() if election["closed_at"] else None,
            "voter_count": voter_count, "vote_count": vote_count,
        },
        "options": [{"id": o["id"], "text": o["option_text"], "order": o["display_order"]} for o in options],
        "messages": get_flashed_messages(request),
    })


@app.post("/elections/{election_id}/open/confirm")
async def open_election_form(request: Request, election_id: int):
    redirect = _require_login(request)
    if redirect:
        return redirect

    organizer_id = request.session["organizer_id"]
    async with Database.transaction() as conn:
        result = await conn.execute(
            "UPDATE elections SET status = 'open', opened_at = CURRENT_TIMESTAMP WHERE id = $1 AND organizer_id = $2 AND status = 'draft'",
            election_id, organizer_id,
        )

    if result == "UPDATE 0":
        flash(request, "Cannot open election", "danger")
    else:
        flash(request, "Election opened successfully!", "success")

    return RedirectResponse(url=f"/elections/{election_id}/detail", status_code=303)


@app.post("/elections/{election_id}/close/confirm")
async def close_election_form(request: Request, election_id: int):
    redirect = _require_login(request)
    if redirect:
        return redirect

    organizer_id = request.session["organizer_id"]
    async with Database.transaction() as conn:
        result = await conn.execute(
            "UPDATE elections SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = $1 AND organizer_id = $2 AND status = 'open'",
            election_id, organizer_id,
        )

    if result == "UPDATE 0":
        flash(request, "Cannot close election", "danger")
    else:
        flash(request, "Election closed successfully!", "success")

    return RedirectResponse(url=f"/elections/{election_id}/detail", status_code=303)

