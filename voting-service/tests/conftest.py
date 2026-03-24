"""
voting-service/tests/conftest.py — fixtures for voting-service unit tests.

All tests run against a fully mocked database and auth-service HTTP client.
No live Kubernetes cluster or database is required.

Run with:
    .venv/bin/python -m pytest voting-service/tests/ -v
"""
import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
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
# CWD must be voting-service/ so that StaticFiles(directory="static") and
# Jinja2Templates(directory="templates") resolve correctly at import time.
# Both directories exist under u-vote/voting-service/.
# ---------------------------------------------------------------------------
_voting_dir = Path(__file__).parent.parent   # u-vote/voting-service/
_shared_dir = _voting_dir.parent / "shared"  # u-vote/shared/

for _p in [str(_shared_dir), str(_voting_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load app.py under a unique module name to avoid sys.modules['app']
# collision when multiple service test suites run in the same process.
_SERVICE_MODULE_NAME = "voting_service_app"
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
    str(_voting_dir / "templates")
)

# Replace relative static path with an absolute-path StaticFiles so the
# mount works regardless of CWD at request time.
from starlette.staticfiles import StaticFiles as _StaticFiles
for _route in _app_module.app.routes:
    if getattr(_route, "name", None) == "static":
        _route.app = _StaticFiles(
            directory=str(_voting_dir / "static"),
            check_dir=False,
        )
        break


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _set_app_in_sys_modules():
    """
    Set sys.modules["app"] to this service's module for the duration of each
    test so that bare `import app` statements inside test functions (e.g.
    test_safe_json_*) resolve to the correct service module rather than
    whatever was last registered by another service's conftest.
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
    voting-service/app.py never attempts a real database connection.

    Both Database.connection() and Database.transaction() are replaced with
    async context managers that yield mock_conn.

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
def mock_auth():
    """
    Patches httpx.AsyncClient so the module-level http_client in
    voting-service/app.py is replaced with an AsyncMock when the lifespan
    runs during TestClient startup.

    voting-service uses a module-level client (not a context manager), so
    tests configure the mock directly:
        mock_auth.get.return_value  = MagicMock(status_code=200, ...)
        mock_auth.post.return_value = MagicMock(status_code=200, ...)

    For endpoints that call http_client.get() or .post() multiple times,
    use side_effect with a list of responses.

    Yields the mock AsyncClient instance.
    """
    mock_client = AsyncMock()
    mock_client.aclose = AsyncMock()
    with patch("httpx.AsyncClient", return_value=mock_client):
        yield mock_client


@pytest.fixture
def client(mock_db, mock_auth):
    """
    FastAPI TestClient with the database and auth-service HTTP client fully
    patched via mock_db and mock_auth.

    The lifespan startup (Database.get_pool, httpx.AsyncClient instantiation)
    and shutdown (http_client.aclose, Database.close) are all mocked, so the
    TestClient starts and stops cleanly without a real database or network.

    Returns a dict:
        {"client": TestClient instance, "conn": mock_conn, "auth": mock_auth}

    mock_db and client["conn"] are the same AsyncMock object — tests may
    configure either reference interchangeably.
    """
    from starlette.testclient import TestClient

    with TestClient(_app_module.app, raise_server_exceptions=False) as c:
        yield {"client": c, "conn": mock_db, "auth": mock_auth}


@pytest.fixture
def valid_ballot_token_row():
    """A blind_tokens row representing an unused ballot token."""
    return {
        "id": 1,
        "ballot_token": "test-ballot-token-abc123",
        "election_id": 1,
        "is_used": False,
        "issued_at": datetime.utcnow(),
        "used_at": None,
    }


@pytest.fixture
def valid_election_row():
    """An elections row representing an open election."""
    return {
        "id": 1,
        "status": "open",
        "encryption_key": "test-encryption-key-32-bytes-hex",
        "title": "Test Election 2026",
        "description": "Unit test election",
    }


@pytest.fixture
def valid_option_row():
    """An election_options row."""
    return {
        "id": 1,
        "election_id": 1,
        "option_text": "Option A",
        "display_order": 1,
    }
