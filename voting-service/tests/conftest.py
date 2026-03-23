"""
voting-service/tests/conftest.py — fixtures for voting-service unit tests.

All tests run against a fully mocked database and auth-service HTTP client.
No live Kubernetes cluster or database is required.

Run with:
    .venv/bin/python -m pytest voting-service/tests/ -v
"""
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# CWD must be voting-service/ so that StaticFiles(directory="static") and
# Jinja2Templates(directory="templates") resolve correctly at import time.
# Both directories exist under u-vote/voting-service/.
# ---------------------------------------------------------------------------
_voting_dir = Path(__file__).parent.parent   # u-vote/voting-service/
_shared_dir = _voting_dir.parent / "shared"  # u-vote/shared/

os.chdir(str(_voting_dir))

for _p in [str(_shared_dir), str(_voting_dir)]:
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
    import app as voting_app  # voting-service/app.py

    with TestClient(voting_app.app, raise_server_exceptions=False) as c:
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
