"""
election-service/tests/conftest.py — fixtures for election-service unit tests.

All tests run against a fully mocked database; no live cluster is required.

Run with:
    .venv/bin/python -m pytest election-service/tests/ -v
"""
import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# CWD must be election-service/ so that StaticFiles(directory="static") and
# Jinja2Templates(directory="templates") resolve correctly at import time.
# Both directories exist under u-vote/election-service/.
# ---------------------------------------------------------------------------
_election_dir = Path(__file__).parent.parent   # u-vote/election-service/
_shared_dir = _election_dir.parent / "shared"  # u-vote/shared/

# SESSION_SECRET must be set before app.py is imported, because the
# FastAPI app constructs SessionMiddleware at module level:
#   app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "change-me"))
# Forcing the value (not setdefault) ensures the test value is used even if
# the variable is already set in the shell environment.
os.environ["SESSION_SECRET"] = "test-secret-key"

for _p in [str(_shared_dir), str(_election_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load app.py under a unique module name to avoid sys.modules['app']
# collision when multiple service test suites run in the same process.
_SERVICE_MODULE_NAME = "election_service_app"
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
    str(_election_dir / "templates")
)

# Replace relative static path with an absolute-path StaticFiles so the
# mount works regardless of CWD at request time.
from starlette.staticfiles import StaticFiles as _StaticFiles
for _route in _app_module.app.routes:
    if getattr(_route, "name", None) == "static":
        _route.app = _StaticFiles(
            directory=str(_election_dir / "static"),
            check_dir=False,
        )
        break


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_conn():
    """
    Raw AsyncMock connection with all asyncpg-style DB methods pre-configured.
    Default return values are safe no-ops; individual tests override them.

    Methods used in election-service/app.py:
        fetch       — list_elections, dashboard_page, election_detail_page
        fetchrow    — create_election, get_election, create_election_form,
                      election_detail_page
        fetchval    — get_election (voter_count, vote_count),
                      election_detail_page (same)
        execute     — create_election (option inserts), open_election,
                      close_election, open/close_election_form,
                      create_election_form (option inserts)

    Note: executemany is NOT used anywhere in election-service/app.py.
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
    election-service/app.py never attempts a real database connection.

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
def client(mock_db):
    """
    FastAPI TestClient with the database fully patched via mock_db.

    election-service creates an httpx.AsyncClient in its lifespan (for
    potential future outbound calls to auth-service) but does not call it
    in any current endpoint. httpx.AsyncClient() does not open a network
    connection on instantiation, so it runs cleanly without mocking.

    The lifespan startup (Database.get_pool) and shutdown (Database.close)
    are both mocked so the TestClient starts and stops without a real DB.

    Returns a dict:
        {"client": TestClient instance, "conn": mock_conn}

    mock_db and client["conn"] are the same AsyncMock object — tests may
    configure either reference interchangeably.
    """
    from starlette.testclient import TestClient

    with TestClient(_app_module.app, raise_server_exceptions=False) as c:
        yield {"client": c, "conn": mock_db}


@pytest.fixture
def draft_election_row():
    """A dict representing a DB row for a draft election."""
    return {
        "id": 1,
        "organiser_id": 1,
        "org_id": 1,
        "title": "Test Election 2026",
        "description": "A test election",
        "status": "draft",
        "encryption_key": "test-key-hex-32-bytes",
        "created_at": datetime.utcnow(),
        "opened_at": None,
        "closed_at": None,
    }


@pytest.fixture
def open_election_row():
    """A dict representing a DB row for an open election."""
    return {
        "id": 1,
        "organiser_id": 1,
        "org_id": 1,
        "title": "Test Election 2026",
        "description": "A test election",
        "status": "open",
        "encryption_key": "test-key-hex-32-bytes",
        "created_at": datetime.utcnow(),
        "opened_at": datetime.utcnow(),
        "closed_at": None,
    }


@pytest.fixture
def election_options_rows():
    """A list of three option dicts representing election_options rows."""
    return [
        {"id": 1, "election_id": 1, "option_text": "Option A",
         "display_order": 1, "created_at": datetime.utcnow()},
        {"id": 2, "election_id": 1, "option_text": "Option B",
         "display_order": 2, "created_at": datetime.utcnow()},
        {"id": 3, "election_id": 1, "option_text": "Option C",
         "display_order": 3, "created_at": datetime.utcnow()},
    ]
