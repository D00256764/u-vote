"""
tests/test_integration_compose.py — integration tests against the full
Docker Compose stack via the NGINX gateway on port 80.

These tests require all services to be running:
    docker compose up -d

They exercise real HTTP flows end-to-end through NGINX, hitting actual
FastAPI service instances backed by a live PostgreSQL database.

Run with:
    pytest tests/test_integration_compose.py -v
"""
import time
import uuid

import httpx
import pytest

BASE = "http://localhost"  # NGINX gateway


# ---------------------------------------------------------------------------
# Shared client fixture — session cookie jar carried across requests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """httpx client that follows redirects and persists cookies across calls."""
    with httpx.Client(
        base_url=BASE,
        follow_redirects=True,
        timeout=15,
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: wait for NGINX to be responsive (used as a simple readiness gate)
# ---------------------------------------------------------------------------

def _wait_for_nginx(retries: int = 30, delay: float = 2.0):
    for _ in range(retries):
        try:
            r = httpx.get(f"{BASE}/", timeout=3, follow_redirects=True)
            if r.status_code < 500:
                return
        except httpx.RequestError:
            pass
        time.sleep(delay)
    pytest.skip("NGINX gateway not reachable — is docker compose running?")


@pytest.fixture(scope="module", autouse=True)
def require_stack():
    """Skip this entire module if the stack is not up."""
    _wait_for_nginx()


# ---------------------------------------------------------------------------
# 1. Public page reachability (frontend-service via NGINX)
# ---------------------------------------------------------------------------

def test_home_page(client):
    """Landing page served by frontend-service returns 200."""
    r = client.get("/")
    assert r.status_code == 200
    assert "Election" in r.text


def test_login_page(client):
    """Login page is reachable."""
    r = client.get("/login")
    assert r.status_code == 200
    assert "Sign In" in r.text or "Login" in r.text or "login" in r.text.lower()


def test_register_page(client):
    """Register page is reachable."""
    r = client.get("/register")
    assert r.status_code == 200
    assert "Register" in r.text or "register" in r.text.lower()


# ---------------------------------------------------------------------------
# 2. Auth-gated routes redirect to login when no session is present
#    (verifies election-service, admin-service, results-service all running)
# ---------------------------------------------------------------------------

def test_dashboard_requires_login(client):
    """GET /dashboard → redirects to /login (election-service auth gate)."""
    r = client.get("/dashboard")
    assert "/login" in str(r.url)


def test_manage_voters_requires_login(client):
    """GET /elections/1/voters/manage → redirects to /login (admin-service)."""
    r = client.get("/elections/1/voters/manage")
    assert "/login" in str(r.url)


def test_results_requires_login(client):
    """GET /elections/1/results/view → redirects to /login (results-service)."""
    r = client.get("/elections/1/results/view")
    assert "/login" in str(r.url)


# ---------------------------------------------------------------------------
# 3. Voting-service reachable via NGINX
# ---------------------------------------------------------------------------

def test_invalid_vote_token_shows_error(client):
    """
    GET /vote/<garbage> → voting-service validates token → shows error page.
    Confirms voting-service is running and token validation works.
    """
    r = client.get("/vote/not-a-real-token-000")
    assert r.status_code == 200
    # Error page should mention the token is invalid/expired
    assert any(word in r.text.lower() for word in ["invalid", "expired", "error", "not found"])


# ---------------------------------------------------------------------------
# 4. Full organiser register → login → dashboard flow
# ---------------------------------------------------------------------------

def test_register_and_login_flow():
    """
    End-to-end: register a new organiser account, log in, land on dashboard.
    Uses a unique email per test run to avoid conflicts on re-runs.
    """
    email = f"ci_{uuid.uuid4().hex[:8]}@example.com"
    password = "CiTest123!"

    with httpx.Client(
        base_url=BASE,
        follow_redirects=True,
        timeout=15,
    ) as c:
        # ── Register ────────────────────────────────────────────────────────
        r = c.post("/register", data={
            "email": email,
            "password": password,
            "confirm_password": password,
        })
        # Successful registration: frontend returns 303 → GET /login (200)
        assert r.status_code == 200, (
            f"Register expected final status 200 (login page), got {r.status_code}. "
            f"Response body: {r.text[:300]}"
        )
        assert "/login" in str(r.url), (
            f"Register should redirect to /login but ended at {r.url}. "
            f"Body snippet: {r.text[:300]}"
        )

        # ── Login ────────────────────────────────────────────────────────────
        r = c.post("/login", data={"email": email, "password": password})
        # After login the chain is:
        #   frontend → redirect to /dashboard?token=...&organiser_id=...
        #   election-service stores session → redirect to /dashboard
        #   election-service renders dashboard
        assert r.status_code == 200, (
            f"Login expected final status 200 (dashboard), got {r.status_code}. "
            f"Body snippet: {r.text[:300]}"
        )
        assert "/dashboard" in str(r.url), (
            f"Login should end at /dashboard but ended at {r.url}. "
            f"Body snippet: {r.text[:300]}"
        )


# ---------------------------------------------------------------------------
# 5. Health endpoints
# ---------------------------------------------------------------------------

def test_frontend_health_endpoint(client):
    """GET /health returns healthy JSON from frontend-service."""
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["service"] == "frontend"


# ---------------------------------------------------------------------------
# 6. Negative auth cases
# ---------------------------------------------------------------------------

def test_login_wrong_password_stays_at_login(client):
    """POST /login with wrong credentials re-renders the login form."""
    r = client.post("/login", data={
        "email": "nobody@example.com",
        "password": "WrongPass99!",
    })
    assert r.status_code == 200
    assert "/login" in str(r.url)
    assert any(w in r.text.lower() for w in ["invalid", "credentials", "failed"])


def test_register_duplicate_email_shows_error():
    """Registering with an already-registered email shows an error on the form."""
    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    password = "DupTest123!"

    with httpx.Client(base_url=BASE, follow_redirects=True, timeout=15) as c:
        # First registration succeeds → redirects to /login
        r = c.post("/register", data={
            "email": email, "password": password, "confirm_password": password,
        })
        assert "/login" in str(r.url), (
            f"First registration should redirect to /login, got {r.url}. "
            f"Body: {r.text[:300]}"
        )

        # Second registration with same email → error, stays on /register
        r = c.post("/register", data={
            "email": email, "password": password, "confirm_password": password,
        })
        assert r.status_code == 200
        assert "/register" in str(r.url), (
            f"Duplicate registration should stay at /register, got {r.url}"
        )
        assert any(w in r.text.lower() for w in ["already", "registered", "exists"])


# ---------------------------------------------------------------------------
# 7. Full organiser flow: register → login → create election → logout
# ---------------------------------------------------------------------------

def test_full_organiser_flow():
    """
    Register a new organiser, log in, create an election, confirm it renders,
    log out, then verify the dashboard requires login again.
    """
    email = f"flow_{uuid.uuid4().hex[:8]}@example.com"
    password = "FlowTest123!"

    with httpx.Client(base_url=BASE, follow_redirects=True, timeout=15) as c:
        # ── Register ──────────────────────────────────────────────────────
        r = c.post("/register", data={
            "email": email, "password": password, "confirm_password": password,
        })
        assert "/login" in str(r.url), (
            f"Register should redirect to /login, got {r.url}. Body: {r.text[:300]}"
        )

        # ── Login ─────────────────────────────────────────────────────────
        r = c.post("/login", data={"email": email, "password": password})
        assert "/dashboard" in str(r.url), (
            f"Login should land on /dashboard but got {r.url}. Body: {r.text[:300]}"
        )

        # ── Create election ───────────────────────────────────────────────
        r = c.post("/elections/create", data={
            "title": "CI Integration Election",
            "description": "Created by the automated integration test",
            "options[]": ["Option A", "Option B", "Option C"],
            "scheduled_open_at": "2030-06-01T09:00",
            "scheduled_close_at": "2030-06-02T17:00",
        })
        assert r.status_code == 200, (
            f"Create election expected 200, got {r.status_code}. Body: {r.text[:300]}"
        )
        # Successful creation redirects to /elections/{id}/detail
        assert "/elections/" in str(r.url), (
            f"Expected redirect to /elections/{{id}}/detail, got {r.url}"
        )

        # ── Logout ────────────────────────────────────────────────────────
        r = c.get("/logout")
        assert r.status_code == 200
        # /logout clears session and redirects to / (home page)

        # ── Dashboard is now blocked ──────────────────────────────────────
        r = c.get("/dashboard")
        assert "/login" in str(r.url), (
            f"After logout, /dashboard should redirect to /login, got {r.url}"
        )


# ---------------------------------------------------------------------------
# 8. NGINX routing — confirm correct service handles each path prefix
# ---------------------------------------------------------------------------

def test_nginx_routes_elections_to_election_service(client):
    """
    GET /elections/create requires login → election-service handles it
    (not frontend). Confirms NGINX /elections → election-service routing.
    """
    r = client.get("/elections/create")
    # Should redirect to /login (election-service _require_login check)
    assert "/login" in str(r.url)


def test_nginx_routes_vote_to_voting_service(client):
    """
    GET /vote/anything → voting-service. Different response from frontend.
    """
    r = client.get("/vote/test-routing-check-xyz")
    assert r.status_code == 200
    # Voting service error page — not the frontend landing page
    assert "Election Admin" not in r.text or any(
        word in r.text.lower() for word in ["invalid", "error", "token"]
    )
