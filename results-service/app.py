"""
Results Service — Result tallying, audit trails, and results UI page.

This service owns the results bounded context end-to-end:
    - JSON API endpoints (used by other services)
    - HTML page: election results with charts
    - Direct DB access (read-only) for votes, elections, options

Runs on port 5004, exposed to browsers on port 8084.
All endpoints are read-only; results only available after election closes.
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
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

import logging

from database import Database
from schemas import HealthResponse

logger = logging.getLogger("results-service")

# ── Auth-service URL for token verification ──────────────────────────────────
AUTH_SERVICE = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5001")

# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):
    await Database.get_pool()
    yield
    await Database.close()


app = FastAPI(
    title="Results Service",
    description="Election result tallying, audit trails, and results UI",
    lifespan=lifespan,
)

# ── Middleware & templating ──────────────────────────────────────────────────
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


# ── Flash helpers ────────────────────────────────────────────────────────────

def flash(request: Request, message: str, category: str = "info"):
    request.session.setdefault("flash", []).append({"message": message, "category": category})


def get_flashed_messages(request: Request):
    return request.session.pop("flash", [])


def _require_login(request: Request):
    """Check session for organiser JWT. Redirect to auth gateway if missing."""
    if "token" not in request.session:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)
    return None


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "healthy", "service": "results"}


@app.get("/elections/{election_id}/results")
async def get_results(election_id: int):
    """Get election results (only after election closes)."""
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            "SELECT id, title, status, closed_at FROM elections WHERE id = $1",
            election_id,
        )

        if not election:
            raise HTTPException(status_code=404, detail="Election not found")
        if election["status"] != "closed":
            raise HTTPException(
                status_code=403,
                detail="Election must be closed to view results",
            )

        results = await conn.fetch(
            """
            SELECT eo.id, eo.option_text, eo.display_order,
                   COUNT(v.id) AS vote_count
            FROM election_options eo
            LEFT JOIN votes v ON v.option_id = eo.id
            WHERE eo.election_id = $1
            GROUP BY eo.id, eo.option_text, eo.display_order
            ORDER BY vote_count DESC, eo.display_order
            """,
            election_id,
        )

        total_votes = await conn.fetchval(
            "SELECT COUNT(*) FROM votes WHERE election_id = $1", election_id
        )
        total_voters = await conn.fetchval(
            "SELECT COUNT(*) FROM voters WHERE election_id = $1", election_id
        )

    results_data = []
    for r in results:
        pct = (r["vote_count"] / total_votes * 100) if total_votes > 0 else 0
        results_data.append({
            "option_id": r["id"],
            "option_text": r["option_text"],
            "vote_count": r["vote_count"],
            "percentage": round(pct, 2),
        })

    return {
        "election": {
            "id": election["id"],
            "title": election["title"],
            "status": election["status"],
            "closed_at": election["closed_at"].isoformat() if election["closed_at"] else None,
        },
        "summary": {
            "total_votes": total_votes,
            "total_voters": total_voters,
            "turnout_percentage": round(total_votes / total_voters * 100, 2) if total_voters > 0 else 0,
        },
        "results": results_data,
    }


@app.get("/elections/{election_id}/audit")
async def get_audit_trail(election_id: int):
    """Get audit information — vote hashes and hash-chain verification."""
    async with Database.connection() as conn:
        status_row = await conn.fetchrow(
            "SELECT status FROM elections WHERE id = $1", election_id
        )

        if not status_row:
            raise HTTPException(status_code=404, detail="Election not found")
        if status_row["status"] != "closed":
            raise HTTPException(
                status_code=403,
                detail="Audit trail only available for closed elections",
            )

        votes = await conn.fetch(
            """
            SELECT id, vote_hash, previous_hash, cast_at
            FROM votes
            WHERE election_id = $1
            ORDER BY id ASC
            """,
            election_id,
        )

    audit_data = []
    hash_chain_valid = True

    for i, vote in enumerate(votes):
        if i > 0:
            expected = votes[i - 1]["vote_hash"]
            if vote["previous_hash"] != expected:
                hash_chain_valid = False

        audit_data.append({
            "vote_id": vote["id"],
            "vote_hash": vote["vote_hash"],
            "previous_hash": vote["previous_hash"],
            "cast_at": vote["cast_at"].isoformat(),
            "sequence": i + 1,
        })

    return {
        "election_id": election_id,
        "total_votes": len(votes),
        "hash_chain_valid": hash_chain_valid,
        "audit_trail": audit_data,
    }


@app.get("/elections/{election_id}/statistics")
async def get_statistics(election_id: int):
    """Get detailed statistics about the election."""
    async with Database.connection() as conn:
        election = await conn.fetchrow(
            """
            SELECT title, status, created_at, opened_at, closed_at
            FROM elections WHERE id = $1
            """,
            election_id,
        )

        if not election:
            raise HTTPException(status_code=404, detail="Election not found")

        total_votes = await conn.fetchval(
            "SELECT COUNT(*) FROM votes WHERE election_id = $1", election_id
        )
        total_voters = await conn.fetchval(
            "SELECT COUNT(*) FROM voters WHERE election_id = $1", election_id
        )

        token_stats = await conn.fetchrow(
            """
            SELECT COUNT(*) AS total_tokens,
                   SUM(CASE WHEN is_used THEN 1 ELSE 0 END) AS used_tokens
            FROM voting_tokens
            WHERE election_id = $1
            """,
            election_id,
        )

        vote_timeline = []
        if election["status"] == "closed":
            timeline = await conn.fetch(
                """
                SELECT DATE_TRUNC('hour', cast_at) AS hour, COUNT(*) AS vote_count
                FROM votes
                WHERE election_id = $1
                GROUP BY hour
                ORDER BY hour
                """,
                election_id,
            )
            vote_timeline = [
                {"hour": row["hour"].isoformat(), "count": row["vote_count"]}
                for row in timeline
            ]

    return {
        "election": {
            "title": election["title"],
            "status": election["status"],
            "created_at": election["created_at"].isoformat(),
            "opened_at": election["opened_at"].isoformat() if election["opened_at"] else None,
            "closed_at": election["closed_at"].isoformat() if election["closed_at"] else None,
        },
        "statistics": {
            "total_voters": total_voters,
            "total_tokens": token_stats["total_tokens"] or 0,
            "used_tokens": token_stats["used_tokens"] or 0,
            "total_votes": total_votes,
            "turnout_rate": round(total_votes / total_voters * 100, 2) if total_voters > 0 else 0,
        },
        "vote_timeline": vote_timeline,
    }


# ── Web (HTML) routes ────────────────────────────────────────────────────────
# These render the results page directly in this service.

ELECTION_SERVICE = os.getenv("ELECTION_SERVICE_URL", "http://localhost:8082")


@app.get("/elections/{election_id}/results/view", response_class=HTMLResponse)
async def results_page(request: Request, election_id: int):
    """Render the results page for a closed election."""
    redirect = _require_login(request)
    if redirect:
        return redirect

    # Reuse the JSON helpers — call internal functions directly
    try:
        results_data = await get_results(election_id)
    except HTTPException as exc:
        flash(request, exc.detail, "error")
        return RedirectResponse(
            f"{ELECTION_SERVICE}/elections/{election_id}/detail",
            status_code=302,
        )

    # Also grab statistics
    try:
        stats_data = await get_statistics(election_id)
    except HTTPException:
        stats_data = None

    # Also grab audit trail
    try:
        audit_data = await get_audit_trail(election_id)
    except HTTPException:
        audit_data = None

    return templates.TemplateResponse("results.html", {
        "request": request,
        "election": results_data["election"],
        "summary": results_data["summary"],
        "results": results_data["results"],
        "statistics": stats_data["statistics"] if stats_data else None,
        "vote_timeline": stats_data.get("vote_timeline", []) if stats_data else [],
        "audit": audit_data if audit_data else None,
        "messages": get_flashed_messages(request),
    })
