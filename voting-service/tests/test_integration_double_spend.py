"""
voting-service/tests/test_integration_double_spend.py

Integration test: FOR UPDATE lock prevents concurrent ballot-token double-spend.

Why the mock-based test cannot prove the FOR UPDATE lock works
--------------------------------------------------------------
In test_security_voting.py::test_ballot_token_double_spend_concurrent, AsyncMock
never suspends the event loop between awaits, so asyncio.gather runs the two ASGI
requests sequentially rather than truly concurrently.  The mocked database has no
transactional state — it returns is_used=False for both requests regardless of what
the first request wrote.  Both therefore return "Vote Submitted", and the test is
forced to fail intentionally to document the gap.

What this test proves that the mock test cannot
-----------------------------------------------
With a real asyncpg pool, every ``await conn.fetchrow(...)`` or ``await conn.execute(...)``
involves genuine network I/O to PostgreSQL.  That I/O suspends the current coroutine
and lets the event loop schedule the other request.  Both requests therefore hit the
``SELECT … FOR UPDATE`` on the blind_tokens row at nearly the same time, competing
for the row-level lock.  PostgreSQL grants the lock to one transaction; the other
blocks until the winner commits.  When the loser is finally unblocked it reads
is_used=TRUE and the route returns the error page.

This test asserts exactly one "Vote Submitted" in the two response bodies and
verifies that exactly one row was inserted into encrypted_ballots.

POSTGRES_TEST_URL requirement
------------------------------
Set the environment variable to a DSN for a dedicated test PostgreSQL database
before running this file, e.g.:

    export POSTGRES_TEST_URL="postgresql://user:pass@localhost:5432/uvote_test"

The test database must have the pgcrypto extension available (superuser once):

    CREATE EXTENSION IF NOT EXISTS pgcrypto;

The test creates a private schema (uvote_int_XXXX), applies a minimal table set,
seeds one open election + one ballot token, runs the concurrent scenario, and drops
the schema in a finally block regardless of outcome.  It never modifies any existing
schema objects.
"""

import asyncio
import importlib.util
import os
import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import asyncpg
import httpx
import pytest

# ---------------------------------------------------------------------------
# Environment variable — evaluated at collection time for skipif
# ---------------------------------------------------------------------------
POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")

# ---------------------------------------------------------------------------
# Path setup — voting-service/ and shared/ must be on sys.path.
# Matches conftest.py exactly.
# ---------------------------------------------------------------------------
_here = Path(__file__).resolve()
_voting_dir = _here.parent.parent            # u-vote/voting-service/
_shared_dir = _voting_dir.parent / "shared"  # u-vote/shared/

for _p in [str(_shared_dir), str(_voting_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Reuse the module already loaded by conftest.py when present; load fresh
# otherwise.  StaticFiles(directory="static") calls os.path.isdir at __init__
# time — patch it to True so app.py imports cleanly regardless of CWD.
_SERVICE_MODULE = "voting_service_app"
if _SERVICE_MODULE not in sys.modules:
    import jinja2 as _jinja2
    from starlette.staticfiles import StaticFiles as _StaticFiles

    _spec = importlib.util.spec_from_file_location(
        _SERVICE_MODULE, _voting_dir / "app.py"
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_SERVICE_MODULE] = _mod
    with patch.object(os.path, "isdir", return_value=True):
        _spec.loader.exec_module(_mod)

    _mod.templates.env.loader = _jinja2.FileSystemLoader(
        str(_voting_dir / "templates")
    )
    for _route in _mod.app.routes:
        if getattr(_route, "name", None) == "static":
            _route.app = _StaticFiles(
                directory=str(_voting_dir / "static"), check_dir=False
            )
            break

_app_module = sys.modules[_SERVICE_MODULE]
app = _app_module.app


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL not set — skipping DB integration test",
)
@pytest.mark.asyncio
async def test_ballot_token_double_spend_real_db():
    """FOR UPDATE lock on blind_tokens serialises concurrent ballot submissions.

    Setup:
      - Creates a private schema (uvote_int_XXXX) to avoid touching any
        existing tables.
      - Applies the minimal table set required by submit_vote() plus the
        auto_ballot_hash trigger (pgcrypto required).
      - Seeds one open election, one election option, and one unused
        blind_tokens row.

    Execution:
      - Patches database.Database.connection / .transaction with real asyncpg
        context managers backed by a two-connection pool.
      - Fires two concurrent POST /vote/submit requests via asyncio.gather.
        With real asyncpg I/O, both coroutines genuinely interleave at each
        await, creating real lock contention on the blind_tokens row.

    Assertion:
      - Exactly one response body contains "Vote Submitted".
      - The other contains "already been used".
      - Exactly one row exists in encrypted_ballots after both requests.
      - If both responses contain "Vote Submitted", the test fails immediately
        with the CRITICAL double-spend message.

    Cleanup:
      - DROP SCHEMA … CASCADE in the finally block removes all tables,
        triggers, and functions in one statement regardless of test outcome.
        (DELETE is intentionally avoided: encrypted_ballots has an immutability
        trigger that rejects per-row DELETE.)
    """
    TEST_SCHEMA = f"uvote_int_{secrets.token_hex(4)}"
    BALLOT_TOKEN = f"test-bt-{secrets.token_hex(8)}"
    ENC_KEY      = "test-pgp-key-for-integration-test"

    admin_conn = None
    pool = None

    try:
        # ------------------------------------------------------------------
        # Administrative connection for schema DDL and seeding
        # ------------------------------------------------------------------
        admin_conn = await asyncpg.connect(POSTGRES_TEST_URL)

        # pgcrypto must exist for pgp_sym_encrypt() and the ballot-hash trigger.
        # CREATE EXTENSION IF NOT EXISTS is a no-op when already present.
        await admin_conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

        # ------------------------------------------------------------------
        # Create isolated test schema
        # ------------------------------------------------------------------
        await admin_conn.execute(f"CREATE SCHEMA {TEST_SCHEMA}")

        # ------------------------------------------------------------------
        # Minimal table set — matches exactly what submit_vote() touches.
        # No foreign-key constraints to keep seeding trivial.
        # ------------------------------------------------------------------

        await admin_conn.execute(f"""
            CREATE TABLE {TEST_SCHEMA}.elections (
                id             SERIAL PRIMARY KEY,
                title          VARCHAR(255) NOT NULL,
                description    TEXT,
                status         VARCHAR(20) DEFAULT 'draft',
                encryption_key TEXT
            )
        """)

        await admin_conn.execute(f"""
            CREATE TABLE {TEST_SCHEMA}.election_options (
                id            SERIAL PRIMARY KEY,
                election_id   INTEGER NOT NULL,
                option_text   VARCHAR(255) NOT NULL,
                display_order INTEGER DEFAULT 0
            )
        """)

        await admin_conn.execute(f"""
            CREATE TABLE {TEST_SCHEMA}.blind_tokens (
                id           SERIAL PRIMARY KEY,
                ballot_token VARCHAR(255) UNIQUE NOT NULL,
                election_id  INTEGER NOT NULL,
                is_used      BOOLEAN DEFAULT FALSE,
                issued_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_at      TIMESTAMP
            )
        """)

        # ballot_hash is NOT NULL; the trigger below sets it on every INSERT.
        # If pgcrypto is unavailable the INSERT will fail with a clear error.
        await admin_conn.execute(f"""
            CREATE TABLE {TEST_SCHEMA}.encrypted_ballots (
                id             SERIAL PRIMARY KEY,
                election_id    INTEGER NOT NULL,
                encrypted_vote BYTEA NOT NULL,
                ballot_hash    VARCHAR(255) NOT NULL,
                previous_hash  VARCHAR(255),
                receipt_token  VARCHAR(255) UNIQUE NOT NULL,
                cast_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await admin_conn.execute(f"""
            CREATE TABLE {TEST_SCHEMA}.vote_receipts (
                id            SERIAL PRIMARY KEY,
                election_id   INTEGER NOT NULL,
                receipt_token VARCHAR(255) UNIQUE NOT NULL,
                ballot_hash   VARCHAR(255) NOT NULL
            )
        """)

        await admin_conn.execute(f"""
            CREATE TABLE {TEST_SCHEMA}.audit_log (
                id            SERIAL PRIMARY KEY,
                event_type    VARCHAR(50) NOT NULL,
                election_id   INTEGER,
                actor_type    VARCHAR(20),
                actor_id      INTEGER,
                detail        JSONB,
                event_hash    VARCHAR(255),
                previous_hash VARCHAR(255),
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Trigger function: auto-compute ballot_hash before INSERT.
        # Uses public.digest() (pgcrypto) explicitly to avoid search_path
        # ambiguity when the function runs inside the test schema.
        await admin_conn.execute(f"""
            CREATE OR REPLACE FUNCTION {TEST_SCHEMA}.generate_ballot_hash()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.ballot_hash := encode(
                    public.digest(
                        NEW.election_id::text
                        || NEW.encrypted_vote::text
                        || NEW.cast_at::text
                        || gen_random_uuid()::text,
                        'sha256'
                    ),
                    'hex'
                );
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)

        await admin_conn.execute(f"""
            CREATE TRIGGER auto_ballot_hash
                BEFORE INSERT ON {TEST_SCHEMA}.encrypted_ballots
                FOR EACH ROW
                EXECUTE FUNCTION {TEST_SCHEMA}.generate_ballot_hash()
        """)

        # ------------------------------------------------------------------
        # Seed: one open election, one option, one unused ballot token
        # ------------------------------------------------------------------
        election_id = await admin_conn.fetchval(
            f"INSERT INTO {TEST_SCHEMA}.elections "
            f"    (title, status, encryption_key) "
            f"VALUES ('Integration Test Election', 'open', $1) "
            f"RETURNING id",
            ENC_KEY,
        )

        option_id = await admin_conn.fetchval(
            f"INSERT INTO {TEST_SCHEMA}.election_options "
            f"    (election_id, option_text, display_order) "
            f"VALUES ($1, 'Option A', 1) "
            f"RETURNING id",
            election_id,
        )

        await admin_conn.execute(
            f"INSERT INTO {TEST_SCHEMA}.blind_tokens "
            f"    (ballot_token, election_id, is_used) "
            f"VALUES ($1, $2, FALSE)",
            BALLOT_TOKEN, election_id,
        )

        # ------------------------------------------------------------------
        # Real asyncpg pool — min_size=2 guarantees both concurrent requests
        # get separate connections so they can genuinely contend on the lock.
        # The init callback sets search_path so the app's unqualified table
        # references (e.g. "blind_tokens") resolve to the test schema.
        # ------------------------------------------------------------------
        async def _init_conn(conn: asyncpg.Connection) -> None:
            await conn.execute(f"SET search_path TO {TEST_SCHEMA}, public")

        pool = await asyncpg.create_pool(
            POSTGRES_TEST_URL,
            init=_init_conn,
            min_size=2,
            max_size=5,
        )

        # ------------------------------------------------------------------
        # Context managers that replace Database.connection / .transaction
        # with real asyncpg connections from the pool.
        # Signature matches fake_cm in conftest.py (*args, **kwargs).
        # ------------------------------------------------------------------
        @asynccontextmanager
        async def real_transaction(*args, **kwargs):
            async with pool.acquire() as conn:
                async with conn.transaction():
                    yield conn

        # ------------------------------------------------------------------
        # Concurrent submission — patch DB, fire two requests simultaneously
        # ------------------------------------------------------------------
        form = {
            "ballot_token": BALLOT_TOKEN,
            "option_id":    str(option_id),
            "election_id":  str(election_id),
        }

        with (
            patch("database.Database.get_pool", new_callable=AsyncMock),
            patch("database.Database.connection", real_transaction),
            patch("database.Database.transaction", real_transaction),
            patch("database.Database.close",      new_callable=AsyncMock),
        ):
            async with (
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://test",
                ) as client1,
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://test",
                ) as client2,
            ):
                resp1, resp2 = await asyncio.gather(
                    client1.post("/vote/submit", data=form),
                    client2.post("/vote/submit", data=form),
                )

        # ------------------------------------------------------------------
        # Assertions
        # ------------------------------------------------------------------
        bodies = [resp1.text, resp2.text]
        success_count = sum(1 for b in bodies if "Vote Submitted" in b)

        # Fail immediately with the CRITICAL message if both votes succeeded.
        assert success_count != 2, (
            "CRITICAL: double-spend vulnerability confirmed — FOR UPDATE lock "
            "did not prevent concurrent duplicate votes"
        )

        # Exactly one must have succeeded; the other must show the used-token error.
        assert success_count == 1, (
            f"Expected exactly 1 successful vote out of 2 concurrent requests; "
            f"got {success_count}.\n"
            f"Response 1 (first 300 chars): {resp1.text[:300]}\n"
            f"Response 2 (first 300 chars): {resp2.text[:300]}"
        )

        rejected_body = next(b for b in bodies if "Vote Submitted" not in b)
        assert "already been used" in rejected_body, (
            "Expected the rejected request to contain 'already been used'; "
            f"got: {rejected_body[:300]}"
        )

        # Verify the database: only one ballot was inserted.
        ballot_count = await admin_conn.fetchval(
            f"SELECT COUNT(*) FROM {TEST_SCHEMA}.encrypted_ballots"
        )
        assert ballot_count == 1, (
            f"Expected exactly 1 row in encrypted_ballots after two concurrent "
            f"submissions; found {ballot_count}.  "
            "The FOR UPDATE lock must prevent double-insertion."
        )

    finally:
        # Drop the entire test schema — this is safe even if setup partially
        # failed (IF EXISTS) and avoids the immutability trigger on
        # encrypted_ballots which blocks per-row DELETE.
        if pool is not None:
            await pool.close()
        if admin_conn is not None:
            try:
                await admin_conn.execute(
                    f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"
                )
            except Exception:
                pass
            await admin_conn.close()
