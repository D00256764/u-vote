"""
frontend-service/tests/test_frontend.py — pytest unit tests for frontend-service.

Coverage:
  - Public page rendering: /, /login, /register
  - GET /health
  - Login proxy: success, credential failure, service unreachable
  - Register proxy: success, duplicate email, password mismatch, service unreachable
  - Logout: unauthenticated and authenticated
  - safe_json() helper (unit and integration)
  - Authenticated view: session cookie accepted, session cleared on logout

Architecture notes recorded here for future readers:
  - frontend-service has NO database connection — no DB mock needed.
  - frontend-service has NO session-guarded routes. All protected content
    (election management, results, voter admin) lives on other services.
    The only auth-aware behaviour in this service is:
      * index.html shows "Go to Dashboard" when session["token"] is set
      * /logout clears the session
  - httpx.AsyncClient is module-level, created in lifespan — patched via
    patch("httpx.AsyncClient", return_value=mock_client) in conftest.py.
"""
import json

import httpx
import pytest
from unittest.mock import MagicMock


def mock_auth_response(status_code: int = 200, data: dict | None = None) -> MagicMock:
    """Create a mock httpx Response with configurable status and JSON body."""
    if data is None:
        data = {}
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = data
    m.text = json.dumps(data)
    return m


# ── GET / ─────────────────────────────────────────────────────────────────────

def test_home_page_returns_200(client):
    """GET / returns 200 with an HTML response."""
    r = client["client"].get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_home_page_contains_expected_content(client):
    """
    Landing page contains key UI elements from templates/index.html.

    Strings verified directly in index.html:
      - "Secure Voting System"    (h1 title)
      - "Register as Organiser"   (button / card heading)
      - "Login"                   (button href text)
    """
    r = client["client"].get("/")
    body = r.text
    assert "Secure Voting System" in body
    assert "Register as Organiser" in body
    assert "Login" in body


# ── GET /health ───────────────────────────────────────────────────────────────

def test_health_endpoint_returns_200(client):
    """GET /health returns 200 with the correct service identifier."""
    r = client["client"].get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy", "service": "frontend"}


# ── Unauthenticated behaviour ─────────────────────────────────────────────────

def test_logout_without_session_redirects_to_home(client):
    """
    GET /logout without a session still redirects to / (303).

    frontend-service clears the session and redirects unconditionally —
    there is no "must be logged in" guard on /logout.
    """
    r = client["client"].get("/logout", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_register_password_mismatch_returns_error(client):
    """
    POST /register with mismatched passwords is rejected locally (no
    auth-service call) and re-renders the form with an error message.
    """
    r = client["client"].post(
        "/register",
        data={
            "email": "test@uvote.com",
            "password": "pass1234",
            "confirm_password": "different",
        },
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "Passwords do not match" in r.text


# ── GET /login ────────────────────────────────────────────────────────────────

def test_login_page_returns_200(client):
    """GET /login returns 200 with the login form."""
    r = client["client"].get("/login")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # Strings from templates/login.html
    assert "Organiser Login" in r.text
    assert 'name="email"' in r.text
    assert 'name="password"' in r.text


# ── POST /login ───────────────────────────────────────────────────────────────

def test_login_success_redirects_to_election_dashboard(client):
    """
    POST /login proxies credentials to auth-service and, on a 200 response,
    redirects to the election dashboard URL with organiser_id and token
    appended as query parameters.
    """
    client["auth"].post.return_value = mock_auth_response(
        200, {"token": "test.jwt.token", "organiser_id": 1}
    )
    r = client["client"].post(
        "/login",
        data={"email": "admin@uvote.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    location = r.headers["location"]
    # ELECTION_DASHBOARD defaults to http://localhost:8082/dashboard
    assert "token=test.jwt.token" in location
    assert "organiser_id=1" in location


def test_login_failure_renders_login_form_with_error(client):
    """
    POST /login with wrong credentials renders the login form with the
    error detail returned by auth-service.
    """
    client["auth"].post.return_value = mock_auth_response(
        401, {"detail": "Invalid credentials"}
    )
    r = client["client"].post(
        "/login",
        data={"email": "admin@uvote.com", "password": "wrongpass"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "Invalid credentials" in r.text


def test_login_auth_service_unreachable_shows_error(client):
    """
    When auth-service is unreachable during POST /login, app.py catches
    httpx.RequestError and flashes "Service unavailable", then re-renders
    the login form with status 200.

    httpx.ConnectError is a subclass of httpx.RequestError and is caught
    by the except block in app.py.
    """
    client["auth"].post.side_effect = httpx.ConnectError("connection refused")
    r = client["client"].post(
        "/login",
        data={"email": "admin@uvote.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "Service unavailable" in r.text


def test_login_sets_organiser_id_in_redirect(client):
    """
    A successful POST /login embeds the organiser_id from auth-service in
    the redirect URL, confirming the session data is read and forwarded.
    """
    client["auth"].post.return_value = mock_auth_response(
        200, {"token": "tok.abc.xyz", "organiser_id": 42}
    )
    r = client["client"].post(
        "/login",
        data={"email": "admin@uvote.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "organiser_id=42" in r.headers["location"]
    assert "token=tok.abc.xyz" in r.headers["location"]


# ── GET /register ─────────────────────────────────────────────────────────────

def test_register_page_returns_200(client):
    """GET /register returns 200 with the registration form."""
    r = client["client"].get("/register")
    assert r.status_code == 200
    # Strings from templates/register.html
    assert "Register as Organiser" in r.text
    assert 'name="email"' in r.text
    assert 'name="confirm_password"' in r.text


# ── POST /register ────────────────────────────────────────────────────────────

def test_register_success_redirects_to_login(client):
    """
    POST /register on 201 from auth-service flashes a success message and
    redirects to /login (303).
    """
    client["auth"].post.return_value = mock_auth_response(201, {})
    r = client["client"].post(
        "/register",
        data={
            "email": "new@uvote.com",
            "password": "pass1234",
            "confirm_password": "pass1234",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_register_duplicate_email_renders_error(client):
    """
    POST /register on 409 from auth-service re-renders the form with
    the detail message returned by auth-service.
    """
    client["auth"].post.return_value = mock_auth_response(
        409, {"detail": "Email already registered"}
    )
    r = client["client"].post(
        "/register",
        data={
            "email": "dup@uvote.com",
            "password": "pass1234",
            "confirm_password": "pass1234",
        },
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "Email already registered" in r.text


def test_register_service_unreachable_shows_error(client):
    """
    When auth-service is unreachable during POST /register, app.py catches
    httpx.RequestError and flashes "Service unavailable".
    """
    client["auth"].post.side_effect = httpx.ConnectError("refused")
    r = client["client"].post(
        "/register",
        data={
            "email": "new@uvote.com",
            "password": "pass1234",
            "confirm_password": "pass1234",
        },
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "Service unavailable" in r.text


# ── safe_json() ───────────────────────────────────────────────────────────────

def test_safe_json_returns_empty_dict_on_invalid_json(client):
    """safe_json() returns {} when the response's .json() raises an exception."""
    import app as frontend_app

    bad_resp = MagicMock()
    bad_resp.json.side_effect = ValueError("Expecting value")
    result = frontend_app.safe_json(bad_resp)
    assert result == {}


def test_safe_json_returns_caller_supplied_fallback(client):
    """safe_json() returns the explicit fallback dict when JSON parsing fails."""
    import app as frontend_app

    bad_resp = MagicMock()
    bad_resp.json.side_effect = ValueError("Expecting value")
    result = frontend_app.safe_json(bad_resp, fallback={"error": True})
    assert result == {"error": True}


def test_safe_json_returns_parsed_dict_on_valid_json(client):
    """safe_json() returns the parsed dict when .json() succeeds."""
    import app as frontend_app

    good_resp = MagicMock()
    good_resp.json.return_value = {"token": "abc", "organiser_id": 1}
    result = frontend_app.safe_json(good_resp)
    assert result == {"token": "abc", "organiser_id": 1}


def test_safe_json_malformed_body_on_200_causes_500(client):
    """
    DOCUMENTS A REAL BUG: when auth-service responds 200 but with a
    non-JSON body, safe_json() returns {} and the subsequent
        request.session["token"] = data["token"]
    raises KeyError → unhandled 500.

    app.py does not guard against safe_json() returning {} in the 200
    branch of the login handler. With raise_server_exceptions=False the
    TestClient captures this as a 500 response rather than raising.
    """
    bad_response = MagicMock()
    bad_response.status_code = 200
    bad_response.json.side_effect = ValueError("not valid JSON")
    client["auth"].post.return_value = bad_response

    r = client["client"].post(
        "/login",
        data={"email": "admin@uvote.com", "password": "admin123"},
    )
    # KeyError on data["token"] propagates as 500 — this is a real bug.
    assert r.status_code == 500


# ── Authenticated views ───────────────────────────────────────────────────────

def test_authenticated_index_shows_dashboard_link(authed_client):
    """
    When a valid session cookie (token + organiser_id) is present, the
    index page renders the 'Go to Dashboard' link instead of the
    Register/Login buttons.

    Verified against the conditional block in templates/index.html:
        {% if request.session.get('token') %}
            <a href="/dashboard">Go to Dashboard</a>
        {% else %}
            <a href="/register">Register as Organiser</a>
            <a href="/login">Login</a>
        {% endif %}
    """
    r = authed_client["client"].get("/")
    assert r.status_code == 200
    assert "Go to Dashboard" in r.text
    assert "Register as Organiser" not in r.text


def test_logout_clears_session_and_shows_public_view(authed_client):
    """
    GET /logout clears the session cookie and redirects to /.
    After the redirect, the index page shows the unauthenticated view
    (Register/Login buttons, no 'Go to Dashboard').
    """
    # follow_redirects=True: TestClient processes the Set-Cookie from /logout
    # before following the redirect to /, so the session is gone by then.
    r = authed_client["client"].get("/logout", follow_redirects=True)
    assert r.status_code == 200
    assert "Register as Organiser" in r.text
    assert "Go to Dashboard" not in r.text
