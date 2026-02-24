"""
Election Service — Admin dashboard for election organisers (Application 1B).

This service owns the organiser UI for:
    - Dashboard (list elections)
    - Create election
    - Election detail (with voter count, vote count)
    - Open / close election
    - Voter management (add single, CSV upload, list, generate tokens)
    - View results (after election is closed)
    - Audit trail

NO DIRECT DATABASE ACCESS — all data flows through auth-service REST API.

Runs on port 5002, exposed to browsers on port 8082.
"""

import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# ── Service URLs ─────────────────────────────────────────────────────────────
AUTH_SERVICE = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5001")

# ── Async HTTP client ───────────────────────────────────────────────────────
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=30.0)
    yield
    await http_client.aclose()


app = FastAPI(title="Election Service", lifespan=lifespan)
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


def safe_json(resp: httpx.Response, fallback=None) -> dict:
    try:
        return resp.json()
    except Exception:
        return fallback or {}


def get_organiser_id(request: Request) -> int | None:
    return request.session.get("organiser_id")


def require_login(request: Request):
    oid = get_organiser_id(request)
    if not oid:
        return None
    return oid


# ── Dashboard entry (handles redirect from frontend-service) ────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, organiser_id: int | None = None,
                    token: str | None = None):
    # If redirected from frontend-service with query params, store in session
    if organiser_id and token:
        request.session["organiser_id"] = organiser_id
        request.session["token"] = token

    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    resp = await http_client.get(
        f"{AUTH_SERVICE}/elections", params={"organiser_id": oid}
    )
    elections = safe_json(resp).get("elections", [])

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "elections": elections,
        "messages": get_flashed_messages(request),
    })


# ── Create Election ─────────────────────────────────────────────────────────

@app.get("/elections/create", response_class=HTMLResponse)
async def create_election_page(request: Request):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)
    return templates.TemplateResponse("create_election.html", {
        "request": request, "messages": get_flashed_messages(request),
    })


@app.post("/elections/create", response_class=HTMLResponse)
async def create_election(request: Request, title: str = Form(...),
                          description: str = Form(""),):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    form = await request.form()
    options = form.getlist("options[]")
    options = [o for o in options if o.strip()]

    if len(options) < 2:
        flash(request, "At least 2 options are required", "danger")
        return templates.TemplateResponse("create_election.html", {
            "request": request, "messages": get_flashed_messages(request),
        })

    resp = await http_client.post(
        f"{AUTH_SERVICE}/elections",
        params={"organiser_id": oid},
        json={"title": title, "description": description, "options": options},
    )

    if resp.status_code == 201:
        eid = safe_json(resp).get("election_id")
        flash(request, "Election created successfully!", "success")
        return RedirectResponse(url=f"/elections/{eid}/detail", status_code=303)

    flash(request, safe_json(resp).get("detail", "Failed to create election"), "danger")
    return templates.TemplateResponse("create_election.html", {
        "request": request, "messages": get_flashed_messages(request),
    })


# ── Election Detail ─────────────────────────────────────────────────────────

@app.get("/elections/{election_id}/detail", response_class=HTMLResponse)
async def election_detail(request: Request, election_id: int):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    resp = await http_client.get(
        f"{AUTH_SERVICE}/elections/{election_id}",
        params={"organiser_id": oid},
    )
    if resp.status_code != 200:
        flash(request, safe_json(resp).get("detail", "Election not found"), "danger")
        return RedirectResponse(url="/dashboard", status_code=303)

    data = safe_json(resp)
    return templates.TemplateResponse("election_detail.html", {
        "request": request,
        "election": data["election"],
        "options": data["options"],
        "messages": get_flashed_messages(request),
    })


# ── Open / Close Election ───────────────────────────────────────────────────

@app.post("/elections/{election_id}/open/confirm")
async def open_election(request: Request, election_id: int):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    resp = await http_client.post(
        f"{AUTH_SERVICE}/elections/{election_id}/open",
        params={"organiser_id": oid},
    )
    if resp.status_code == 200:
        flash(request, "Election opened for voting!", "success")
    else:
        flash(request, safe_json(resp).get("detail", "Cannot open election"), "danger")
    return RedirectResponse(url=f"/elections/{election_id}/detail", status_code=303)


@app.post("/elections/{election_id}/close/confirm")
async def close_election(request: Request, election_id: int):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    resp = await http_client.post(
        f"{AUTH_SERVICE}/elections/{election_id}/close",
        params={"organiser_id": oid},
    )
    if resp.status_code == 200:
        flash(request, "Election closed.", "success")
    else:
        flash(request, safe_json(resp).get("detail", "Cannot close election"), "danger")
    return RedirectResponse(url=f"/elections/{election_id}/detail", status_code=303)


# ── Voter Management ────────────────────────────────────────────────────────

@app.get("/elections/{election_id}/voters", response_class=HTMLResponse)
async def manage_voters(request: Request, election_id: int):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    # Get election title
    election_resp = await http_client.get(
        f"{AUTH_SERVICE}/elections/{election_id}",
        params={"organiser_id": oid},
    )
    if election_resp.status_code != 200:
        flash(request, "Election not found", "danger")
        return RedirectResponse(url="/dashboard", status_code=303)
    election_data = safe_json(election_resp)

    # Get voters
    voter_resp = await http_client.get(f"{AUTH_SERVICE}/elections/{election_id}/voters")
    voters = safe_json(voter_resp).get("voters", [])

    return templates.TemplateResponse("manage_voters.html", {
        "request": request,
        "election_id": election_id,
        "election_title": election_data["election"]["title"],
        "voters": voters,
        "messages": get_flashed_messages(request),
    })


@app.post("/elections/{election_id}/voters/upload/form")
async def upload_voters_form(request: Request, election_id: int,
                             file: UploadFile = File(...)):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    contents = await file.read()
    resp = await http_client.post(
        f"{AUTH_SERVICE}/elections/{election_id}/voters/upload",
        files={"file": (file.filename, contents, file.content_type or "text/csv")},
    )
    data = safe_json(resp)
    if resp.status_code == 201:
        flash(request,
              f"Uploaded: {data.get('voters_added', 0)} added, "
              f"{data.get('voters_skipped', 0)} skipped", "success")
    else:
        flash(request, data.get("detail", "Upload failed"), "danger")

    return RedirectResponse(url=f"/elections/{election_id}/voters", status_code=303)


@app.post("/elections/{election_id}/tokens/generate/form")
async def generate_tokens_form(request: Request, election_id: int):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    resp = await http_client.post(
        f"{AUTH_SERVICE}/elections/{election_id}/tokens/generate"
    )
    data = safe_json(resp)
    if resp.status_code == 201:
        flash(request,
              f"Generated {data.get('tokens_generated', 0)} tokens. "
              f"Emails sent: {data.get('emails_sent', 0)}, "
              f"failed: {data.get('emails_failed', 0)}", "success")
    else:
        flash(request, data.get("detail", "Token generation failed"), "danger")

    return RedirectResponse(url=f"/elections/{election_id}/voters", status_code=303)


@app.post("/elections/{election_id}/tokens/resend/form")
async def resend_tokens_form(request: Request, election_id: int):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    resp = await http_client.post(
        f"{AUTH_SERVICE}/elections/{election_id}/tokens/resend",
        params={"organiser_id": oid},
    )
    data = safe_json(resp)
    if resp.status_code == 200:
        flash(request,
              f"Resend complete: tokens found {data.get('tokens_found',0)}. "
              f"Emails sent: {data.get('emails_sent',0)}, failed: {data.get('emails_failed',0)}",
              "success")
    else:
        flash(request, data.get("detail", "Resend failed"), "danger")

    return RedirectResponse(url=f"/elections/{election_id}/voters", status_code=303)


# ── Results ──────────────────────────────────────────────────────────────────

@app.get("/elections/{election_id}/results", response_class=HTMLResponse)
async def view_results(request: Request, election_id: int):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    resp = await http_client.get(f"{AUTH_SERVICE}/elections/{election_id}/results")
    if resp.status_code != 200:
        flash(request, safe_json(resp).get("detail", "Cannot view results"), "danger")
        return RedirectResponse(url=f"/elections/{election_id}/detail", status_code=303)

    data = safe_json(resp)
    return templates.TemplateResponse("results.html", {
        "request": request, "data": data,
        "messages": get_flashed_messages(request),
    })


# ── Audit Trail ──────────────────────────────────────────────────────────────

@app.get("/elections/{election_id}/audit", response_class=HTMLResponse)
async def view_audit(request: Request, election_id: int):
    oid = require_login(request)
    if not oid:
        return RedirectResponse(url="http://localhost:8080/login", status_code=303)

    resp = await http_client.get(f"{AUTH_SERVICE}/elections/{election_id}/audit")
    if resp.status_code != 200:
        flash(request, safe_json(resp).get("detail", "Cannot view audit trail"), "danger")
        return RedirectResponse(url=f"/elections/{election_id}/detail", status_code=303)

    data = safe_json(resp)
    # Also get election info for title
    election_resp = await http_client.get(
        f"{AUTH_SERVICE}/elections/{election_id}",
        params={"organiser_id": oid},
    )
    election_data = safe_json(election_resp)

    return templates.TemplateResponse("audit.html", {
        "request": request, "audit": data,
        "election": election_data.get("election", {}),
        "messages": get_flashed_messages(request),
    })


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "election"}
