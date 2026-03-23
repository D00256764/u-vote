"""
frontend-service/tests/conftest.py — fixtures for frontend-service unit tests.

All tests run against a fully mocked httpx client.
No live Kubernetes cluster or database is required.

Run with:
    .venv/bin/python -m pytest frontend-service/tests/ -v
"""
import base64
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# CWD must be frontend-service/ so that:
#   app.mount("/static", StaticFiles(directory="static"), ...)
#   templates = Jinja2Templates(directory="templates")
# both resolve correctly when app.py is imported at fixture time.
# ---------------------------------------------------------------------------
_frontend_dir = Path(__file__).parent.parent   # u-vote/frontend-service/
_shared_dir = _frontend_dir.parent / "shared"  # u-vote/shared/

os.chdir(str(_frontend_dir))

# Set SESSION_SECRET before app.py is imported so SessionMiddleware uses
# the same secret we use when signing test session cookies below.
os.environ["SESSION_SECRET"] = "test-secret"

for _p in [str(_shared_dir), str(_frontend_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Helpers (not fixtures)
# ---------------------------------------------------------------------------

def mock_auth_response(status_code: int = 200, data: dict | None = None) -> MagicMock:
    """
    Create a mock httpx Response object with configurable status and JSON body.

    Usage in tests:
        mock_auth.post.return_value = mock_auth_response(200, {"token": "...", "organiser_id": 1})
        mock_auth.post.return_value = mock_auth_response(401, {"detail": "Invalid credentials"})
    """
    if data is None:
        data = {}
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = data
    m.text = json.dumps(data)
    return m


def _make_session_cookie(session_data: dict, secret: str = "test-secret") -> str:
    """
    Sign a session dict into a Starlette SessionMiddleware-compatible cookie.

    Starlette encodes sessions as:
        TimestampSigner(secret_key).sign(base64url(json(session_data)))

    The signed bytes are decoded to a str so they can be passed to
    c.cookies.set().
    """
    from itsdangerous import TimestampSigner

    payload = base64.b64encode(json.dumps(session_data).encode("utf-8"))
    signer = TimestampSigner(secret)
    return signer.sign(payload).decode("utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_auth():
    """
    Patches httpx.AsyncClient so the module-level http_client in
    frontend-service/app.py is replaced with an AsyncMock when the
    TestClient lifespan runs during startup.

    frontend-service uses a module-level client (assigned in lifespan),
    so tests configure the mock directly before issuing requests:

        mock_auth.post.return_value = mock_auth_response(200, {...})
        mock_auth.post.side_effect = httpx.ConnectError("refused")

    Yields the mock AsyncClient instance.
    """
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()
    with patch("httpx.AsyncClient", return_value=mock_client):
        yield mock_client


@pytest.fixture
def client(mock_auth):
    """
    FastAPI TestClient with the httpx client fully patched via mock_auth.
    No session cookie is pre-injected — requests are unauthenticated by default.

    Returns:
        {"client": TestClient, "auth": mock_auth}

    mock_auth is the same AsyncMock yielded by the mock_auth fixture — tests
    may configure either reference interchangeably.
    """
    from starlette.testclient import TestClient
    import app as frontend_app  # frontend-service/app.py

    with TestClient(frontend_app.app, raise_server_exceptions=False) as c:
        yield {"client": c, "auth": mock_auth}


@pytest.fixture
def authed_client(mock_auth):
    """
    FastAPI TestClient with a session established via POST /login.

    Approach: POST /login with a mocked auth-service 200 response so that
    app.py runs request.session["token"] = ... and the SessionMiddleware
    writes a signed Set-Cookie on the 303 response.  The TestClient stores
    that cookie with domain="testserver" automatically, so all subsequent
    requests include it — and /logout's Set-Cookie properly replaces it.

    This is preferred over manually signing a cookie with c.cookies.set()
    because the TestClient's httpx cookie jar stores server-issued cookies
    by domain, ensuring Set-Cookie responses can update them later.

    Session contains:
        token:        "test.jwt.token"
        organiser_id: 1

    Returns:
        {"client": TestClient, "auth": mock_auth}
    """
    from starlette.testclient import TestClient
    import app as frontend_app  # frontend-service/app.py

    with TestClient(frontend_app.app, raise_server_exceptions=False) as c:
        mock_auth.post.return_value = mock_auth_response(
            200, {"token": "test.jwt.token", "organiser_id": 1}
        )
        # POST /login → 303 redirect (not followed). The 303 response carries
        # Set-Cookie: session=<signed payload>; the TestClient stores it for
        # domain=testserver so subsequent requests include it.
        c.post(
            "/login",
            data={"email": "admin@uvote.com", "password": "admin123"},
            follow_redirects=False,
        )
        yield {"client": c, "auth": mock_auth}
