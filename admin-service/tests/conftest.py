"""
admin-service/tests/conftest.py — fixtures for admin-service unit tests.

admin-service has two external dependencies to mock:
  1. shared Database class — all DB reads/writes via asyncpg pool
  2. send_voting_token_email — async SMTP call in generate_tokens handler

No live database, SMTP server, or Kubernetes cluster is required.

Run with:
    .venv/bin/python -m pytest admin-service/tests/ -v
"""
import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
# CWD must be admin-service/ so that:
#   app.mount("/static", StaticFiles(directory="static"), ...)
#   templates = Jinja2Templates(directory="templates")
# both resolve correctly when app.py is imported at fixture time.
# ---------------------------------------------------------------------------
_admin_dir = Path(__file__).parent.parent   # u-vote/admin-service/
_shared_dir = _admin_dir.parent / "shared"  # u-vote/shared/

for _p in [str(_shared_dir), str(_admin_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load app.py under a unique module name to avoid sys.modules['app']
# collision when multiple service test suites run in the same process.
_SERVICE_MODULE_NAME = "admin_service_app"
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
    str(_admin_dir / "templates")
)

# Replace relative static path with an absolute-path StaticFiles so the
# mount works regardless of CWD at request time.
from starlette.staticfiles import StaticFiles as _StaticFiles
for _route in _app_module.app.routes:
    if getattr(_route, "name", None) == "static":
        _route.app = _StaticFiles(
            directory=str(_admin_dir / "static"),
            check_dir=False,
        )
        break

# Alias under "app" so that patch("app.logger") in test_admin.py targets the
# same module object as _app_module.  All other services use unique names and
# do not reference sys.modules["app"], so this alias is safe.
sys.modules["app"] = _app_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _set_app_in_sys_modules():
    """
    Set sys.modules["app"] to this service's module for the duration of each
    test so that patch("app.X") calls in test_admin.py target the correct
    module object.
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
def mock_conn():
    """
    Raw AsyncMock connection with all asyncpg-style DB methods pre-configured.
    Default return values are safe no-ops; individual tests override them.
    """
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def mock_db(mock_conn):
    """
    Patches Database.get_pool / connection / transaction / close so that
    admin-service/app.py never attempts a real database connection.

    app.py imports: from database import Database
    All patches target the Database class in the shared 'database' module.

    Both Database.connection() and Database.transaction() are replaced with
    async context managers that yield mock_conn, allowing tests to configure
    mock_conn.fetchrow.return_value etc. before issuing requests.

    Yields mock_conn so callers can configure it directly.
    """

    @asynccontextmanager
    async def fake_cm(*args, **kwargs):
        yield mock_conn

    with (
        patch("database.Database.get_pool", new_callable=AsyncMock),
        patch("database.Database.connection", fake_cm),
        patch("database.Database.transaction", fake_cm),
        patch("database.Database.close", new_callable=AsyncMock),
    ):
        yield mock_conn


@pytest.fixture
def mock_email():
    """
    Patches send_voting_token_email at the path where app.py imports it:
        from email_util import send_voting_token_email
    The patch target is 'app.send_voting_token_email' (the binding in the
    app module's namespace).

    Default: AsyncMock returning None (success).
    Tests configure side_effect to simulate SMTP failures.

    Yields the mock so tests can inspect call_args or set side_effect.
    """
    with patch("admin_service_app.send_voting_token_email", new_callable=AsyncMock) as mock:
        mock.return_value = None
        yield mock


@pytest.fixture
def client(mock_db, mock_email):
    """
    FastAPI TestClient with both the database and email fully patched.

    The lifespan startup (Database.get_pool) and shutdown (Database.close)
    are mocked so the TestClient starts and stops without a real database.
    send_voting_token_email is patched so no real SMTP calls are made.

    Returns:
        {
            "client": TestClient,
            "conn":   mock_conn  (same object as mock_db),
            "email":  mock_email,
        }
    """
    from starlette.testclient import TestClient

    with TestClient(_app_module.app, raise_server_exceptions=False) as c:
        yield {"client": c, "conn": mock_db, "email": mock_email}


@pytest.fixture
def voter_row():
    """A dict representing a DB row for a voter in the voters table."""
    return {
        "id": 1,
        "election_id": 1,
        "email": "voter@test.com",
        "date_of_birth": date(1990, 6, 15),
        "has_voted": False,
        "created_at": datetime.utcnow(),
    }


@pytest.fixture
def voting_token_row():
    """A dict representing a DB row for an unused voting token."""
    return {
        "id": 1,
        "token": "test-token-urlsafe-43chars-xxxxxxxxxxxxxxxxxxx",
        "voter_id": 1,
        "election_id": 1,
        "is_used": False,
        "expires_at": datetime.utcnow() + timedelta(days=7),
        "used_at": None,
        "created_at": datetime.utcnow(),
    }


@pytest.fixture
def election_row():
    """A dict representing a DB row for an open election."""
    return {
        "id": 1,
        "title": "Test Election 2026",
        "status": "open",
        "organiser_id": 1,
        "org_id": 1,
    }
