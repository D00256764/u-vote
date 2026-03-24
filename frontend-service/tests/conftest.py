"""
frontend-service/tests/conftest.py — fixtures for frontend-service unit tests.

All tests run against a fully mocked httpx client.
No live Kubernetes cluster or database is required.

Run with:
    .venv/bin/python -m pytest frontend-service/tests/ -v
"""
import base64
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import prometheus_client
from prometheus_client import CollectorRegistry

import pytest

# Patch REGISTRY.register to be idempotent so that multiple service test suites
# can run in the same pytest process without crashing on duplicate metric names.
# prometheus_fastapi_instrumentator registers metrics at TestClient startup
# (middleware stack build), not at import time, so this must be a permanent
# module-level patch rather than a context manager around exec_module.
if not getattr(prometheus_client.REGISTRY, "_uvote_test_patched", False):
    _orig_registry_register = prometheus_client.REGISTRY.register

    def _idempotent_register(collector, _orig=_orig_registry_register):
        try:
            _orig(collector)
        except ValueError:
            pass  # Duplicate metric name — already registered by another service

    prometheus_client.REGISTRY.register = _idempotent_register
    prometheus_client.REGISTRY._uvote_test_patched = True

# ---------------------------------------------------------------------------
# CWD must be frontend-service/ so that:
#   app.mount("/static", StaticFiles(directory="static"), ...)
#   templates = Jinja2Templates(directory="templates")
# both resolve correctly when app.py is imported at fixture time.
# ---------------------------------------------------------------------------
_frontend_dir = Path(__file__).parent.parent   # u-vote/frontend-service/
_shared_dir = _frontend_dir.parent / "shared"  # u-vote/shared/

# Set SESSION_SECRET before app.py is imported so SessionMiddleware uses
# the same secret we use when signing test session cookies below.
os.environ["SESSION_SECRET"] = "test-secret"

for _p in [str(_shared_dir), str(_frontend_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load app.py under a unique module name to avoid sys.modules['app']
# collision when multiple service test suites run in the same process.
_SERVICE_MODULE_NAME = "frontend_service_app"
_APP_PATH = Path(__file__).parent.parent / "app.py"

if _SERVICE_MODULE_NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_SERVICE_MODULE_NAME, _APP_PATH)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_SERVICE_MODULE_NAME] = _module
    # StaticFiles(directory="static") calls os.path.isdir at __init__ time.
    # Bypass the check so app.py imports cleanly regardless of CWD; the route
    # is replaced with an absolute-path StaticFiles immediately below.
    with patch.object(os.path, "isdir", return_value=True):
        _spec.loader.exec_module(_module)

_app_module = sys.modules[_SERVICE_MODULE_NAME]

# Jinja2Templates stores "templates" as a relative path, which breaks when
# os.chdir() from another service conftest changes CWD during a combined run.
# Replace the FileSystemLoader with one that uses an absolute path so template
# rendering works regardless of CWD at request time.
import jinja2 as _jinja2
_app_module.templates.env.loader = _jinja2.FileSystemLoader(
    str(_frontend_dir / "templates")
)

# Replace relative static path with an absolute-path StaticFiles so the
# mount works regardless of CWD at request time.
from starlette.staticfiles import StaticFiles as _StaticFiles
for _route in _app_module.app.routes:
    if getattr(_route, "name", None) == "static":
        _route.app = _StaticFiles(
            directory=str(_frontend_dir / "static"),
            check_dir=False,
        )
        break


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

@pytest.fixture(autouse=True)
def _set_app_in_sys_modules():
    """
    Set sys.modules["app"] to this service's module for the duration of each
    test so that bare `import app` statements inside test functions resolve to
    the correct service module rather than whatever was last registered by
    another service's conftest.
    Restores the previous value after each test.
    """
    previous = sys.modules.get("app")
    sys.modules["app"] = _app_module
    yield
    if previous is None:
        sys.modules.pop("app", None)
    else:
        sys.modules["app"] = previous


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

    with TestClient(_app_module.app, raise_server_exceptions=False) as c:
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

    with TestClient(_app_module.app, raise_server_exceptions=False) as c:
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
