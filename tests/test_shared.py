"""
Unit tests for shared/security.py, shared/schemas.py, and shared/database.py.

Run with:
    python3 -m pytest tests/test_shared.py -v

No running database, cluster, or services required.
"""

import importlib
import os
import re
import sys

import pytest

# Add project root to sys.path so 'shared' is importable as a package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

import shared.security as security_module
from shared.security import (
    generate_blind_ballot_token,
    hash_password,
    verify_password,
)
from shared.schemas import (
    ElectionCreate,
    LoginRequest,
    RegisterRequest,
    TokenVerifyResponse,
)
from shared.database import Database

from pydantic import ValidationError
from unittest.mock import AsyncMock, patch


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_db_pool():
    """Reset the Database singleton before each test to prevent state leakage."""
    Database._pool = None
    yield
    Database._pool = None


# ── Test 1 ────────────────────────────────────────────────────────────────────

def test_blind_ballot_token_length_and_charset():
    """generate_blind_ballot_token() must return exactly 43 URL-safe base64 chars."""
    token = generate_blind_ballot_token()
    assert len(token) == 43, f"Expected 43 chars, got {len(token)}"
    assert re.fullmatch(r'[A-Za-z0-9_\-]+', token), (
        f"Token contains non-URL-safe characters: {token!r}"
    )


# ── Test 2 ────────────────────────────────────────────────────────────────────

def test_ballot_secret_reads_from_env(monkeypatch):
    """_BALLOT_SECRET must pick up BALLOT_TOKEN_SECRET and not fall back to hardcoded default."""
    test_value = "my-test-secret-value"
    hardcoded_default = "ballot-secret-change-in-production"

    monkeypatch.setenv("BALLOT_TOKEN_SECRET", test_value)
    importlib.reload(security_module)

    assert security_module._BALLOT_SECRET == test_value
    assert security_module._BALLOT_SECRET != hardcoded_default

    # Restore module state for other tests.
    monkeypatch.delenv("BALLOT_TOKEN_SECRET", raising=False)
    importlib.reload(security_module)


# ── Test 3 ────────────────────────────────────────────────────────────────────

def test_password_hash_and_verify_roundtrip():
    """hash_password() then verify_password() must succeed for the correct password."""
    hashed = hash_password('correct')
    assert hashed != 'correct', "Hash must not equal plaintext"
    assert isinstance(hashed, str) and len(hashed) > 0
    assert verify_password('correct', hashed) is True
    assert verify_password('wrong', hashed) is False


# ── Test 4 ────────────────────────────────────────────────────────────────────

def test_jwt_encode_decode_roundtrip():
    """jose.jwt encode/decode must preserve organiser_id, email, and exp."""
    from jose import jwt
    from datetime import datetime, timezone

    secret = "test-signing-secret"
    algorithm = "HS256"
    exp_timestamp = int(datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp())
    payload = {
        "organiser_id": 42,
        "email": "organiser@example.com",
        "exp": exp_timestamp,
    }

    token = jwt.encode(payload, secret, algorithm=algorithm)
    decoded = jwt.decode(token, secret, algorithms=[algorithm])

    assert decoded["organiser_id"] == payload["organiser_id"]
    assert decoded["email"] == payload["email"]
    assert decoded["exp"] == payload["exp"]


# ── Test 5 ────────────────────────────────────────────────────────────────────

def test_required_fields_raise_validation_error():
    """ElectionCreate and LoginRequest must raise ValidationError when required fields are omitted."""
    # ElectionCreate requires title and options (min 2 items)
    with pytest.raises(ValidationError):
        ElectionCreate()

    with pytest.raises(ValidationError):
        ElectionCreate(title="My Election")  # options missing

    with pytest.raises(ValidationError):
        ElectionCreate(title="My Election", options=["Only one"])  # options min_length=2

    # LoginRequest requires email and password
    with pytest.raises(ValidationError):
        LoginRequest()

    with pytest.raises(ValidationError):
        LoginRequest(email="user@example.com")  # password missing


# ── Test 6 ────────────────────────────────────────────────────────────────────

def test_email_str_rejects_invalid_formats():
    """RegisterRequest must reject strings that are not valid email addresses."""
    invalid_emails = [
        "not-an-email",
        "missing@",
        "@nodomain.com",
        "spaces in@email.com",
        "",
    ]
    for bad_email in invalid_emails:
        with pytest.raises(ValidationError):
            RegisterRequest(email=bad_email, password="validpassword")


# ── Test 7 ────────────────────────────────────────────────────────────────────

def test_token_verify_response_exact_fields():
    """TokenVerifyResponse must expose exactly {valid, organiser_id, email, error}."""
    # Instantiate with valid data
    instance = TokenVerifyResponse(valid=True, organiser_id=1, email="a@b.com", error=None)
    assert instance.valid is True

    expected_fields = {"valid", "organiser_id", "email", "error"}
    actual_fields = set(TokenVerifyResponse.model_fields.keys())

    assert actual_fields == expected_fields, (
        f"Field mismatch — expected {expected_fields}, got {actual_fields}"
    )
    assert "election_id" not in actual_fields
    assert "voter_id" not in actual_fields


# ── Test 8 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_pool_uses_env_vars(monkeypatch):
    """get_pool() must pass env var values — not defaults — to asyncpg.create_pool."""
    monkeypatch.setenv("DB_HOST", "my-db-host")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "my_database")
    monkeypatch.setenv("DB_USER", "my_user")
    monkeypatch.setenv("DB_PASSWORD", "my_password")

    mock_pool = AsyncMock()
    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool) as mock_create:
        await Database.get_pool()

    mock_create.assert_called_once_with(
        host="my-db-host",
        port=5433,
        database="my_database",
        user="my_user",
        password="my_password",
        min_size=2,
        max_size=20,
    )


# ── Test 9 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_pool_is_singleton():
    """Calling get_pool() twice must not create a second pool (call_count == 1)."""
    mock_pool = AsyncMock()
    with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool) as mock_create:
        pool1 = await Database.get_pool()
        pool2 = await Database.get_pool()

    assert pool1 is pool2, "get_pool() must return the same pool instance on repeated calls"
    assert mock_create.call_count == 1, (
        f"asyncpg.create_pool called {mock_create.call_count} times — expected 1"
    )


# ── Test 10 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_pool_propagates_creation_error():
    """get_pool() must propagate exceptions raised by asyncpg.create_pool."""
    with patch(
        "asyncpg.create_pool",
        new_callable=AsyncMock,
        side_effect=Exception("connection refused"),
    ):
        with pytest.raises(Exception, match="connection refused"):
            await Database.get_pool()

    # Pool must remain None so the next call retries rather than returning a broken pool.
    assert Database._pool is None, "_pool must stay None after a failed create_pool()"
