"""
Admin Frontend Service — Auth gateway for election organisers (Application 1).

This is the entry point for organisers. It handles ONLY:
    - Landing page
    - Organiser registration (delegates to auth-service)
    - Organiser login (delegates to auth-service)
    - Logout

After login, the organiser is redirected to the Election Service dashboard.
Each downstream service (election, voter, results) owns its own UI pages.

Runs on port 5000, exposed to browsers on port 8080.
"""
import os
import sys
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# ── Shared imports ────────────────────────────────────────────────────────────
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
logger = logging.getLogger('frontend-service')

from csrf import generate_csrf_token, validate_csrf_token

# ── Service URLs ─────────────────────────────────────────────────────────────
AUTH_SERVICE = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5001")

# After login, redirect organiser to the Election Service dashboard
ELECTION_DASHBOARD = os.getenv("ELECTION_DASHBOARD_URL", "http://localhost:5005/dashboard")

# ── Shared async HTTP client ────────────────────────────────────────────────
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=10.0)
    yield
    await http_client.aclose()


app = FastAPI(title="Secure Voting System — Admin", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "change-me"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
BASE_URL = os.getenv("BASE_URL", "http://localhost")
templates.env.globals["base_url"] = BASE_URL

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

def flash(request: Request, message: str, category: str = "info"):
    """Append a flash message to the session (read once on next page load)."""
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})


def get_flashed_messages(request: Request) -> list[dict]:
    """Pop and return all flash messages."""
    return request.session.pop("_messages", [])


def safe_json(resp: httpx.Response, fallback: dict | None = None) -> dict:
    """Safely parse JSON from a response, returning fallback on failure."""
    try:
        return resp.json()
    except Exception:
        return fallback or {}


async def check_csrf(request: Request):
    form = await request.form()
    submitted_token = form.get("csrf_token")
    if not validate_csrf_token(request.session, submitted_token):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "frontend"}


# ── Public pages ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    logger.info('Request received: %s %s', request.method, request.url.path)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "messages": get_flashed_messages(request),
    })


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    logger.info('Request received: %s %s', request.method, request.url.path)
    return templates.TemplateResponse("register.html", {
        "request": request,
        "messages": get_flashed_messages(request),
        "csrf_token": generate_csrf_token(request.session),
    })


@app.post("/register", response_class=HTMLResponse, dependencies=[Depends(check_csrf)])
async def register(request: Request, email: str = Form(...), password: str = Form(...),
                   confirm_password: str = Form(...)):
    logger.info('Request received: %s %s', request.method, request.url.path)

    def _register_page(msg, cat="danger"):
        flash(request, msg, cat)
        return templates.TemplateResponse("register.html", {
            "request": request,
            "messages": get_flashed_messages(request),
            "csrf_token": generate_csrf_token(request.session),
        })

    if password != confirm_password:
        return _register_page("Passwords do not match")

    import re
    if len(password) < 8:
        return _register_page("Password must be at least 8 characters")
    if not re.search(r'[A-Z]', password):
        return _register_page("Password must contain at least one uppercase letter")
    if not re.search(r'[a-z]', password):
        return _register_page("Password must contain at least one lowercase letter")
    if not re.search(r'[0-9]', password):
        return _register_page("Password must contain at least one number")

    try:
        resp = await http_client.post(f"{AUTH_SERVICE}/register", json={
            "email": email, "password": password,
        })
    except httpx.RequestError as e:
        logger.error('External service call failed: %s %s — %s',
                     'POST', AUTH_SERVICE + '/register', e)
        return _register_page("Service unavailable")

    if resp.status_code == 201:
        flash(request, "Registration successful! Please log in.", "success")
        return RedirectResponse(url="/login", status_code=303)

    return _register_page(safe_json(resp).get("detail", "Registration failed"))


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    logger.info('Request received: %s %s', request.method, request.url.path)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "messages": get_flashed_messages(request),
        "csrf_token": generate_csrf_token(request.session),
    })


@app.post("/login", response_class=HTMLResponse, dependencies=[Depends(check_csrf)])
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    logger.info('Request received: %s %s', request.method, request.url.path)

    def _login_page(msg, cat="danger"):
        flash(request, msg, cat)
        return templates.TemplateResponse("login.html", {
            "request": request,
            "messages": get_flashed_messages(request),
            "csrf_token": generate_csrf_token(request.session),
        })

    try:
        resp = await http_client.post(f"{AUTH_SERVICE}/login", json={
            "email": email, "password": password,
        })
    except httpx.RequestError as e:
        logger.error('External service call failed: %s %s — %s',
                     'POST', AUTH_SERVICE + '/login', e)
        return _login_page("Service unavailable")

    if resp.status_code == 200:
        data = safe_json(resp)
        request.session["token"] = data["token"]
        request.session["organiser_id"] = data["organiser_id"]
        flash(request, "Login successful!", "success")
        # Redirect to Election Service dashboard, passing organiser_id so the
        # downstream service can store it in its own session.
        oid = data["organiser_id"]
        token = data["token"]
        return RedirectResponse(
            url=f"{ELECTION_DASHBOARD}?organiser_id={oid}&token={token}",
            status_code=303,
        )

    logger.warning('Auth failure: %s', safe_json(resp).get("detail", "Login failed"))
    return _login_page(safe_json(resp).get("detail", "Login failed"))


@app.get("/logout")
async def logout(request: Request):
    logger.info('Request received: %s %s', request.method, request.url.path)
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
