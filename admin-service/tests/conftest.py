"""
admin-service/tests/conftest.py — fixtures for admin-service unit tests.

admin-service has two external dependencies to mock:
  1. shared Database class — all DB reads/writes via asyncpg pool
  2. send_voting_token_email — async SMTP call in generate_tokens handler

No live database, SMTP server, or Kubernetes cluster is required.

Run with:
    .venv/bin/python -m pytest admin-service/tests/ -v
"""
import os
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# CWD must be admin-service/ so that:
#   app.mount("/static", StaticFiles(directory="static"), ...)
#   templates = Jinja2Templates(directory="templates")
# both resolve correctly when app.py is imported at fixture time.
# ---------------------------------------------------------------------------
_admin_dir = Path(__file__).parent.parent   # u-vote/admin-service/
_shared_dir = _admin_dir.parent / "shared"  # u-vote/shared/

os.chdir(str(_admin_dir))

for _p in [str(_shared_dir), str(_admin_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


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
    with patch("app.send_voting_token_email", new_callable=AsyncMock) as mock:
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
    import app as admin_app  # admin-service/app.py

    with TestClient(admin_app.app, raise_server_exceptions=False) as c:
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
