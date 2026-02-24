"""
Voting Service — The voter-facing web application (Application 2).

This is a SEPARATE application from the admin frontend.
It owns the entire voter experience:
    1. Token validation (via auth-service)
    2. Identity verification / MFA (via auth-service)
    3. Blind ballot-token acquisition (via auth-service)
    4. Ballot presentation (via auth-service)
    5. Vote submission (via auth-service)
    6. Vote receipt verification (via auth-service)

NO DIRECT DATABASE ACCESS — all data flows through auth-service REST API.

Anonymity architecture:
    - The voter authenticates with their voting_token + DOB
    - Auth-service issues a blind ballot_token (unlinkable to voter)
    - Auth-service encrypts the vote choice with pgp_sym_encrypt
    - The encrypted ballot is stored with NO voter identity
    - The voter receives a receipt_token to verify their ballot was counted

Runs on port 5003, exposed to voters on port 8081.
"""

import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# -- Service URLs -------------------------------------------------------------
AUTH_SERVICE = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5001")

# -- Async HTTP client --------------------------------------------------------
http_client = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=10.0)
    yield
    await http_client.aclose()


app = FastAPI(
    title="Voting Service",
    description="Voter-facing application — identity verification and anonymous vote casting",
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

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "voting"}


# -- Receipt verification (public API) ---------------------------------------

@app.get("/receipt/{receipt_token}")
async def verify_receipt_api(receipt_token: str):
    """Public JSON endpoint: verify a vote receipt was recorded."""
    resp = await http_client.get(f"{AUTH_SERVICE}/receipt/{receipt_token}")
    if resp.status_code != 200:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Receipt not found")
    return safe_json(resp)


# ==========================================================================
# VOTER-FACING WEB PAGES — the complete voting journey
#
#   GET  /vote/{token}           -> validate token -> show identity form
#   POST /vote/verify-identity   -> verify DOB -> get ballot token -> show ballot
#   POST /vote/submit            -> cast vote via auth-service -> show receipt
#   GET  /vote/verify/{receipt}  -> verify receipt page
# ==========================================================================

@app.get("/vote/{token}", response_class=HTMLResponse)
async def vote_landing(request: Request, token: str):
    """Step 1 — Validate voting token and show identity verification form."""

    resp = await http_client.get(f"{AUTH_SERVICE}/tokens/{token}/validate")
    if resp.status_code != 200:
        error = safe_json(resp).get("detail", "Invalid or expired voting link")
        return _error_page(request, error)

    # Check if MFA already completed
    mfa_resp = await http_client.get(
        f"{AUTH_SERVICE}/mfa/status", params={"token": token}
    )
    if mfa_resp.status_code == 200 and safe_json(mfa_resp).get("mfa_verified"):
        election_id = safe_json(resp).get("election_id")
        return await _acquire_ballot_and_show(request, token, election_id)

    return templates.TemplateResponse("verify_identity.html", {
        "request": request, "token": token, "messages": [],
    })


@app.post("/vote/verify-identity", response_class=HTMLResponse)
async def verify_identity(request: Request, token: str = Form(...),
                          date_of_birth: str = Form(...)):
    """Step 2 — Verify DOB via auth-service, acquire ballot token, show ballot."""

    verify_resp = await http_client.post(
        f"{AUTH_SERVICE}/mfa/verify",
        params={"token": token, "date_of_birth": date_of_birth},
    )
    if verify_resp.status_code != 200:
        error = safe_json(verify_resp).get("detail", "Verification failed")
        return templates.TemplateResponse("verify_identity.html", {
            "request": request, "token": token,
            "messages": [{"category": "danger", "message": error}],
        })

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
    """Step 3 — Cast vote via auth-service (which encrypts + stores it)."""

    resp = await http_client.post(
        f"{AUTH_SERVICE}/vote/cast",
        data={
            "ballot_token": ballot_token,
            "option_id": str(option_id),
            "election_id": str(election_id),
        },
    )

    if resp.status_code != 200:
        error = safe_json(resp).get("detail", "Vote submission failed")
        return _error_page(request, error)

    data = safe_json(resp)
    # Try to fetch results (will only succeed if election is closed)
    results_data = None
    try:
        res_resp = await http_client.get(f"{AUTH_SERVICE}/elections/{election_id}/results")
        if res_resp.status_code == 200:
            results_data = safe_json(res_resp)
    except Exception:
        # Ignore errors — results are optional and may not be available yet
        results_data = None

    return templates.TemplateResponse("vote_success.html", {
        "request": request,
        "receipt_token": data["receipt_token"],
        "ballot_hash": data["ballot_hash"],
        "results": results_data,
        "messages": [],
    })


@app.get("/vote/verify/{receipt_token}", response_class=HTMLResponse)
async def verify_receipt_page(request: Request, receipt_token: str):
    """Page where a voter can verify their vote receipt."""

    resp = await http_client.get(f"{AUTH_SERVICE}/receipt/{receipt_token}")
    if resp.status_code != 200:
        return _error_page(request, "Receipt not found. Check your receipt token.")

    data = safe_json(resp)
    return templates.TemplateResponse("vote_verified.html", {
        "request": request,
        "receipt_token": data["receipt_token"],
        "ballot_hash": data["ballot_hash"],
        "election_title": data["election_title"],
        "cast_at": data["cast_at"],
        "messages": [],
    })


# -- Internal helpers ---------------------------------------------------------

async def _acquire_ballot_and_show(request, token, election_id):
    """Issue a blind ballot token via auth-service and show the ballot."""

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

    # Fetch election + options from auth-service (NOT DB)
    ballot_resp = await http_client.get(f"{AUTH_SERVICE}/elections/{eid}/ballot")
    if ballot_resp.status_code != 200:
        return _error_page(request, "Election not found")

    ballot_data = safe_json(ballot_resp)
    return templates.TemplateResponse("vote.html", {
        "request": request,
        "ballot_token": ballot_token,
        "election": ballot_data["election"],
        "options": ballot_data["options"],
        "messages": [],
    })
