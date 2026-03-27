"""
results-service/tests/conftest.py — fixtures for results-service unit tests.

results-service has ONE external dependency to mock:
  The shared Database class — all DB reads via asyncpg pool.

No live database, SMTP server, or Kubernetes cluster is required.

DB methods used by results-service/app.py:
  fetchrow — election lookup (get_results, get_audit_trail, get_statistics)
             token_stats aggregate (get_statistics)
  fetch    — tallied results join (get_results)
             encrypted_ballots audit (get_audit_trail)
             vote timeline (get_statistics, closed elections only)
  fetchval — COUNT queries: total_votes, total_voters (get_results, get_statistics)

Run with:
    .venv/bin/python -m pytest results-service/tests/ -v
"""
import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import prometheus_client

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
# CWD must be results-service/ so that:
#   app.mount("/static", StaticFiles(directory="static"), ...)
#   templates = Jinja2Templates(directory="templates")
# both resolve correctly when app.py is imported at fixture time.
# ---------------------------------------------------------------------------
_results_dir = Path(__file__).parent.parent   # u-vote/results-service/
_shared_dir = _results_dir.parent / "shared"  # u-vote/shared/

os.chdir(str(_results_dir))

# SESSION_SECRET must be set before app.py is imported so SessionMiddleware
# uses a deterministic value rather than the default "change-me-in-production".
os.environ["SESSION_SECRET"] = "test-secret-key"

for _p in [str(_shared_dir), str(_results_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load app.py under a unique module name to avoid sys.modules['app']
# collision when multiple service test suites run in the same process.
_SERVICE_MODULE_NAME = "results_service_app"
_APP_PATH = _results_dir / "app.py"

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
    Raw AsyncMock connection with all asyncpg-style DB methods used in
    results-service/app.py pre-configured.

    Methods used: fetchrow, fetch, fetchval.
    execute is NOT used — results-service is read-only via the API layer.

    Default return values are safe no-ops; individual tests override them.
    """
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def mock_db(mock_conn):
    """
    Patches Database.get_pool / connection / transaction / close so that
    results-service/app.py never attempts a real database connection.

    app.py imports: from database import Database
    Patches target the Database class in the shared 'database' module.

    Database.connection() is replaced with an async context manager that
    yields mock_conn, allowing tests to configure mock_conn.fetchrow etc.
    before issuing requests.

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
    are mocked so the TestClient starts and stops without a real database.

    Returns:
        {
            "client": TestClient,
            "conn":   mock_conn  (same object as mock_db),
        }
    """
    from starlette.testclient import TestClient

    with TestClient(_app_module.app, raise_server_exceptions=False) as c:
        yield {"client": c, "conn": mock_db}


@pytest.fixture
def closed_election_row():
    """A dict representing a DB row for a closed election."""
    return {
        "id": 1,
        "title": "Test Election 2026",
        "description": "A test election",
        "status": "closed",
        "organiser_id": 1,
        "org_id": 1,
        "encryption_key": "test-key-hex-32-bytes-xxxxxxxxxxxx",
        "created_at": datetime.utcnow() - timedelta(days=3),
        "opened_at": datetime.utcnow() - timedelta(days=2),
        "closed_at": datetime.utcnow() - timedelta(days=1),
    }


@pytest.fixture
def open_election_row():
    """A dict representing a DB row for an open (not yet closed) election."""
    return {
        "id": 1,
        "title": "Test Election 2026",
        "description": "A test election",
        "status": "open",
        "organiser_id": 1,
        "org_id": 1,
        "encryption_key": "test-key-hex-32-bytes-xxxxxxxxxxxx",
        "created_at": datetime.utcnow() - timedelta(days=1),
        "opened_at": datetime.utcnow() - timedelta(hours=12),
        "closed_at": None,
    }


@pytest.fixture
def election_options_rows():
    """A list of three option dicts matching the election_options table."""
    return [
        {"id": 1, "election_id": 1, "option_text": "Alice Johnson",
         "display_order": 1},
        {"id": 2, "election_id": 1, "option_text": "Bob Smith",
         "display_order": 2},
        {"id": 3, "election_id": 1, "option_text": "Carol White",
         "display_order": 3},
    ]


@pytest.fixture
def tallied_votes_rows():
    """
    Rows returned by the get_results LEFT JOIN query:

        SELECT eo.id, eo.option_text, eo.display_order,
               COALESCE(tv.vote_count, 0) AS vote_count
        FROM election_options eo
        LEFT JOIN tallied_votes tv ON tv.option_id = eo.id
        WHERE eo.election_id = $1
        ORDER BY vote_count DESC, eo.display_order

    Pre-sorted as the DB would return them (Alice first with most votes).
    """
    return [
        {"id": 1, "option_text": "Alice Johnson", "display_order": 1,
         "vote_count": 10},
        {"id": 2, "option_text": "Bob Smith",     "display_order": 2,
         "vote_count": 5},
        {"id": 3, "option_text": "Carol White",   "display_order": 3,
         "vote_count": 3},
    ]


@pytest.fixture
def audit_rows():
    """
    Rows returned by the get_audit_trail query:

        SELECT id, ballot_hash AS vote_hash, previous_hash, cast_at
        FROM encrypted_ballots
        WHERE election_id = $1
        ORDER BY id ASC

    Note: 'ballot_hash' is aliased to 'vote_hash' in the SQL, so the
    key in the returned row dict must be 'vote_hash', not 'ballot_hash'.

    Two entries with a valid hash chain:
      entry[1].previous_hash == entry[0].vote_hash → hash_chain_valid=True
    """
    return [
        {
            "id": 1,
            "vote_hash": "aabbcc" * 10,
            "previous_hash": None,
            "cast_at": datetime.utcnow() - timedelta(hours=2),
        },
        {
            "id": 2,
            "vote_hash": "ddeeff" * 10,
            "previous_hash": "aabbcc" * 10,
            "cast_at": datetime.utcnow() - timedelta(hours=1),
        },
    ]
