"""
Admin Frontend Service — Auth gateway for election organisers (Application 1A).

This is the entry point for organisers. It handles ONLY:
    - Landing page
    - Organiser registration (delegates to auth-service)
    - Organiser login (delegates to auth-service)
    - Logout

After login, the organiser is redirected to the Election Service dashboard.

NO DIRECT DATABASE ACCESS — auth only via auth-service REST API.

Runs on port 5000, exposed to browsers on port 8080.
"""
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# ── Service URLs ─────────────────────────────────────────────────────────────
AUTH_SERVICE = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5001")

# After login, redirect organiser to the Election Service dashboard
ELECTION_DASHBOARD = os.getenv("ELECTION_DASHBOARD_URL", "http://localhost:8082/dashboard")

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


# ── Helpers ──────────────────────────────────────────────────────────────────

def flash(request: Request, message: str, category: str = "info"):
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})


def get_flashed_messages(request: Request) -> list[dict]:
    return request.session.pop("_messages", [])


def safe_json(resp: httpx.Response, fallback: dict | None = None) -> dict:
    try:
        return resp.json()
    except Exception:
        return fallback or {}


# ── Public pages ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, "messages": get_flashed_messages(request),
    })


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {
        "request": request, "messages": get_flashed_messages(request),
    })


@app.post("/register", response_class=HTMLResponse)
async def register(request: Request, email: str = Form(...), password: str = Form(...),
                   confirm_password: str = Form(...)):
    if password != confirm_password:
        flash(request, "Passwords do not match", "danger")
        return templates.TemplateResponse("register.html", {
            "request": request, "messages": get_flashed_messages(request),
        })

    resp = await http_client.post(f"{AUTH_SERVICE}/register", json={
        "email": email, "password": password,
    })

    if resp.status_code == 201:
        flash(request, "Registration successful! Please log in.", "success")
        return RedirectResponse(url="/login", status_code=303)

    flash(request, safe_json(resp).get("detail", "Registration failed"), "danger")
    return templates.TemplateResponse("register.html", {
        "request": request, "messages": get_flashed_messages(request),
    })


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request, "messages": get_flashed_messages(request),
    })


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    resp = await http_client.post(f"{AUTH_SERVICE}/login", json={
        "email": email, "password": password,
    })

    if resp.status_code == 200:
        data = safe_json(resp)
        request.session["token"] = data["token"]
        request.session["organiser_id"] = data["organiser_id"]
        flash(request, "Login successful!", "success")
        oid = data["organiser_id"]
        token = data["token"]
        return RedirectResponse(
            url=f"{ELECTION_DASHBOARD}?organiser_id={oid}&token={token}",
            status_code=303,
        )

    flash(request, safe_json(resp).get("detail", "Login failed"), "danger")
    return templates.TemplateResponse("login.html", {
        "request": request, "messages": get_flashed_messages(request),
    })


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "frontend"}
