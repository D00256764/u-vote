"""
tests/test_security_csrf.py — CSRF protection integration tests.

Verifies that state-changing POST endpoints reject requests without a valid
CSRF token (HTTP 403) and accept requests that include a correctly generated
token matching the session.

Uses httpx.AsyncClient with ASGITransport — no live cluster required.
"""
import base64
import importlib.util
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import prometheus_client
import pytest
import httpx
from httpx import ASGITransport

# ---------------------------------------------------------------------------
# Env setup — must happen before any service app is imported so that
# SessionMiddleware and the CSRF serializer pick up the test secret.
# ---------------------------------------------------------------------------
os.environ["SESSION_SECRET"] = "test-secret-key"
os.environ["SECRET_KEY"] = "test-secret-key"

# ---------------------------------------------------------------------------
# Idempotent Prometheus REGISTRY patch (mirrors per-service conftests)
# ---------------------------------------------------------------------------
if not getattr(prometheus_client.REGISTRY, "_uvote_test_patched", False):
    _orig_registry_register = prometheus_client.REGISTRY.register

    def _idempotent_register(collector, _orig=_orig_registry_register):
        try:
            _orig(collector)
        except ValueError:
            pass

    prometheus_client.REGISTRY.register = _idempotent_register
    prometheus_client.REGISTRY._uvote_test_patched = True

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_tests_dir = Path(__file__).parent
_project_root = _tests_dir.parent
_shared_dir = _project_root / "shared"
_election_dir = _project_root / "election-service"
_voting_dir = _project_root / "voting-service"

for _p in [str(_shared_dir), str(_election_dir), str(_voting_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Load election-service app (same importlib/sys.modules pattern as conftest)
# ---------------------------------------------------------------------------
_ELECTION_MODULE_NAME = "election_service_app"
_ELECTION_APP_PATH = _election_dir / "app.py"

if _ELECTION_MODULE_NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_ELECTION_MODULE_NAME, _ELECTION_APP_PATH)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_ELECTION_MODULE_NAME] = _module
    with patch.object(os.path, "isdir", return_value=True):
        _spec.loader.exec_module(_module)

_election_module = sys.modules[_ELECTION_MODULE_NAME]

import jinja2 as _jinja2
_election_module.templates.env.loader = _jinja2.FileSystemLoader(
    str(_election_dir / "templates")
)

from starlette.staticfiles import StaticFiles as _StaticFiles
for _route in _election_module.app.routes:
    if getattr(_route, "name", None) == "static":
        _route.app = _StaticFiles(directory=str(_election_dir / "static"), check_dir=False)
        break

# ---------------------------------------------------------------------------
# Load voting-service app
# ---------------------------------------------------------------------------
_VOTING_MODULE_NAME = "voting_service_app"
_VOTING_APP_PATH = _voting_dir / "app.py"

if _VOTING_MODULE_NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_VOTING_MODULE_NAME, _VOTING_APP_PATH)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_VOTING_MODULE_NAME] = _module
    with patch.object(os.path, "isdir", return_value=True):
        _spec.loader.exec_module(_module)

_voting_module = sys.modules[_VOTING_MODULE_NAME]

_voting_module.templates.env.loader = _jinja2.FileSystemLoader(
    str(_voting_dir / "templates")
)

for _route in _voting_module.app.routes:
    if getattr(_route, "name", None) == "static":
        _route.app = _StaticFiles(directory=str(_voting_dir / "static"), check_dir=False)
        break


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_conn():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value=None)
    return conn


def _make_session_cookie(data: dict, secret: str = "test-secret-key") -> str:
    """Build a Starlette-compatible signed session cookie value.

    Starlette's SessionMiddleware signs JSON→urlsafe-b64 with
    itsdangerous.TimestampSigner(secret, salt="cookie-session").
    """
    from itsdangerous import TimestampSigner

    json_bytes = json.dumps(data).encode("utf-8")
    b64_data = base64.urlsafe_b64encode(json_bytes).rstrip(b"=")
    signer = TimestampSigner(secret, salt="cookie-session")
    return signer.sign(b64_data).decode("utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csrf_election_create_rejected_without_token():
    """POST /elections/create with a valid session but no csrf_token → 403."""
    mock_conn = _make_mock_conn()

    @asynccontextmanager
    async def _fake_cm(*_, **__):
        yield mock_conn

    with (
        patch("database.Database.get_pool", new_callable=AsyncMock),
        patch("database.Database.connection", _fake_cm),
        patch("database.Database.transaction", _fake_cm),
        patch("database.Database.close", new_callable=AsyncMock),
    ):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=_election_module.app),
            base_url="http://test",
        ) as ac:
            response = await ac.post(
                "/elections/create",
                data={
                    "title": "Test Election",
                    "description": "A test",
                    "options[]": ["Option A", "Option B"],
                    "scheduled_open_at": "2026-06-01T10:00",
                    "scheduled_close_at": "2026-06-02T10:00",
                    # csrf_token intentionally omitted
                },
            )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_csrf_vote_submit_rejected_without_token():
    """POST /vote/submit with a valid session cookie but no csrf_token → 403."""
    mock_conn = _make_mock_conn()
    mock_http = AsyncMock()
    mock_http.aclose = AsyncMock()

    # A session cookie is present but contains no csrf_token
    session_cookie = _make_session_cookie({})

    @asynccontextmanager
    async def _fake_cm(*_, **__):
        yield mock_conn

    with (
        patch("database.Database.get_pool", new_callable=AsyncMock),
        patch("database.Database.connection", _fake_cm),
        patch("database.Database.transaction", _fake_cm),
        patch("database.Database.close", new_callable=AsyncMock),
        patch("httpx.AsyncClient", return_value=mock_http),
    ):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=_voting_module.app),
            base_url="http://test",
            cookies={"session": session_cookie},
        ) as ac:
            response = await ac.post(
                "/vote/submit",
                data={
                    "ballot_token": "some-ballot-token",
                    "option_id": "1",
                    "election_id": "1",
                    # csrf_token intentionally omitted
                },
            )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_csrf_valid_token_accepted():
    """POST /elections/create with a valid session + matching csrf_token → 200 or 302."""
    mock_conn = _make_mock_conn()
    # Stub the INSERT … RETURNING id for election creation
    mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
    mock_conn.execute = AsyncMock(return_value=None)

    # Build session with login credentials so _require_login passes
    session_data: dict = {"token": "fake-jwt-token", "organiser_id": 1}

    # generate_csrf_token mutates session_data in-place, adding "csrf_token"
    from csrf import generate_csrf_token
    csrf_token = generate_csrf_token(session_data)

    # Encode the session (now containing the csrf_token) into a signed cookie
    session_cookie = _make_session_cookie(session_data)

    @asynccontextmanager
    async def _fake_cm(*_, **__):
        yield mock_conn

    with (
        patch("database.Database.get_pool", new_callable=AsyncMock),
        patch("database.Database.connection", _fake_cm),
        patch("database.Database.transaction", _fake_cm),
        patch("database.Database.close", new_callable=AsyncMock),
    ):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=_election_module.app),
            base_url="http://test",
            cookies={"session": session_cookie},
        ) as ac:
            response = await ac.post(
                "/elections/create",
                data={
                    "title": "Test Election",
                    "description": "A test",
                    "options[]": ["Option A", "Option B"],
                    "scheduled_open_at": "2026-06-01T10:00",
                    "scheduled_close_at": "2026-06-02T10:00",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )

    assert response.status_code in (200, 302)
