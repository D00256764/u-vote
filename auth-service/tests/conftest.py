"""
auth-service/tests/conftest.py — fixtures for auth-service unit tests.

All tests run against a fully mocked database; no live cluster is required.
"""
import importlib.util
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup — auth-service/ and shared/ must be importable before any
# service code is imported.
# ---------------------------------------------------------------------------
_auth_dir = Path(__file__).parent.parent          # u-vote/auth-service/
_shared_dir = _auth_dir.parent / "shared"         # u-vote/shared/

for _p in [str(_shared_dir), str(_auth_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load app.py under a unique module name to avoid sys.modules['app']
# collision when multiple service test suites run in the same process.
_SERVICE_MODULE_NAME = "auth_service_app"
_APP_PATH = Path(__file__).parent.parent / "app.py"

if _SERVICE_MODULE_NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_SERVICE_MODULE_NAME, _APP_PATH)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_SERVICE_MODULE_NAME] = _module
    _spec.loader.exec_module(_module)

_app_module = sys.modules[_SERVICE_MODULE_NAME]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
    auth-service/app.py never attempts a real database connection.

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

    The lifespan startup (Database.get_pool) and shutdown (Database.close)
    are both mocked, so the TestClient starts and stops cleanly without a
    real database.

    Returns a dict:
        {"client": TestClient instance, "conn": mock_conn}

    mock_db and client["conn"] are the same AsyncMock object — tests may
    configure either reference interchangeably.
    """
    from starlette.testclient import TestClient

    with TestClient(_app_module.app, raise_server_exceptions=False) as c:
        yield {"client": c, "conn": mock_db}


@pytest.fixture
def seeded_organiser():
    """
    A pre-hashed organiser record matching what asyncpg would return for a
    SELECT from the organisers table.

    The bcrypt hash is generated dynamically (not hardcoded) so it is always
    valid for the corresponding plaintext password "admin123".
    """
    from security import hash_password

    return {
        "id": 1,
        "email": "admin@uvote.com",
        "password_hash": hash_password("admin123"),
        "org_id": 1,
        "role": "admin",
    }
