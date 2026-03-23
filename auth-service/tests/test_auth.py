"""
auth-service/tests/test_auth.py — unit tests for auth-service endpoints.

All tests use the mock_db fixture; no Kubernetes cluster or live database
is needed.

Run with:
    python3 -m pytest auth-service/tests/ -v
"""
import base64
import json
from datetime import date, datetime


# =============================================================================
# POST /register
# =============================================================================

def test_register_success(client, mock_db):
    """Returns 201 with organiser_id on valid input."""
    mock_db.fetchrow.return_value = {"id": 2}

    response = client["client"].post(
        "/register",
        json={"email": "new@test.com", "password": "Password123!", "org_id": 1},
    )

    assert response.status_code == 201
    assert "organiser_id" in response.json()


def test_register_duplicate_email(client, mock_db):
    """Returns 409 when email already exists.

    app.py catches any Exception whose str() contains 'unique' and raises 409.
    Simulated by raising a generic Exception with that substring.
    """
    mock_db.fetchrow.side_effect = Exception("unique constraint violation")

    response = client["client"].post(
        "/register",
        json={"email": "admin@uvote.com", "password": "Password123!", "org_id": 1},
    )

    assert response.status_code == 409


def test_register_missing_fields(client):
    """Returns 422 on missing required fields (Pydantic validation)."""
    response = client["client"].post("/register", json={})

    assert response.status_code == 422


# =============================================================================
# POST /login
# =============================================================================

def test_login_success(client, mock_db, seeded_organiser):
    """Returns 200 with a JWT token on valid credentials."""
    mock_db.fetchrow.return_value = seeded_organiser

    response = client["client"].post(
        "/login",
        json={"email": "admin@uvote.com", "password": "admin123"},
    )

    assert response.status_code == 200
    assert "token" in response.json()


def test_login_wrong_password(client, mock_db, seeded_organiser):
    """Returns 401 on wrong password."""
    mock_db.fetchrow.return_value = seeded_organiser

    response = client["client"].post(
        "/login",
        json={"email": "admin@uvote.com", "password": "WrongPass999!"},
    )

    assert response.status_code == 401


def test_login_jwt_payload(client, mock_db, seeded_organiser):
    """JWT payload contains organiser_id, email, and exp fields."""
    mock_db.fetchrow.return_value = seeded_organiser

    response = client["client"].post(
        "/login",
        json={"email": "admin@uvote.com", "password": "admin123"},
    )
    assert response.status_code == 200

    token = response.json()["token"]
    # JWT is three base64url segments separated by dots; payload is index 1.
    payload_segment = token.split(".")[1]
    # Pad to a multiple of 4 bytes for standard base64 decoding.
    payload_segment += "=" * (-len(payload_segment) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_segment))

    assert "organiser_id" in payload
    assert "email" in payload
    assert "exp" in payload


# =============================================================================
# GET /tokens/{token}/validate
# =============================================================================

def test_validate_token_valid(client, mock_db):
    """Returns 200 with valid=True for a valid, unused, open-election token."""
    mock_db.fetchrow.return_value = {
        "id": 1,
        "voter_id": 10,
        "election_id": 5,
        "is_used": False,
        "expires_at": datetime(2030, 1, 1),
        "status": "open",
    }

    response = client["client"].get("/tokens/some-test-token/validate")

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_validate_token_used(client, mock_db):
    """Returns 400 when token has already been used.

    app.py raises HTTPException(400) when row['is_used'] is True.
    """
    mock_db.fetchrow.return_value = {
        "id": 1,
        "voter_id": 10,
        "election_id": 5,
        "is_used": True,
        "expires_at": datetime(2030, 1, 1),
        "status": "open",
    }

    response = client["client"].get("/tokens/some-used-token/validate")

    assert response.status_code == 400


def test_validate_token_not_found(client, mock_db):
    """Returns 404 when token does not exist in the database.

    app.py raises HTTPException(404) when fetchrow returns None.
    """
    mock_db.fetchrow.return_value = None

    response = client["client"].get("/tokens/nonexistent-token/validate")

    assert response.status_code == 404


# =============================================================================
# POST /mfa/verify
# =============================================================================

def test_mfa_verify_correct_dob(client, mock_db):
    """Returns 200 with verified=True on matching date_of_birth.

    Two fetchrow calls occur inside the endpoint:
      1. JOIN query — returns the voter/token/election row
      2. voter_mfa lookup — returns None (not yet verified → will INSERT)
    """
    mock_db.fetchrow.side_effect = [
        {
            "voter_id": 10,
            "date_of_birth": date(1990, 6, 15),
            "has_voted": False,
            "is_used": False,
            "expires_at": datetime(2030, 1, 1),
            "status": "open",
            "election_id": 5,
        },
        None,  # voter_mfa row: not found → INSERT will run
    ]

    response = client["client"].post(
        "/mfa/verify",
        params={"token": "some-token", "date_of_birth": "1990-06-15"},
    )

    assert response.status_code == 200
    assert response.json()["verified"] is True


def test_mfa_verify_wrong_dob(client, mock_db):
    """Returns 401 on wrong date_of_birth.

    BUG-5 fix: app.py was changed from 403 → 401 for DOB mismatch.
    Asserting 401 here ensures that regression is caught.
    """
    mock_db.fetchrow.return_value = {
        "voter_id": 10,
        "date_of_birth": date(1990, 6, 15),
        "has_voted": False,
        "is_used": False,
        "expires_at": datetime(2030, 1, 1),
        "status": "open",
        "election_id": 5,
    }

    response = client["client"].post(
        "/mfa/verify",
        params={"token": "some-token", "date_of_birth": "1900-01-01"},
    )

    assert response.status_code == 401


# =============================================================================
# DB error propagation
# =============================================================================

def test_login_db_error_returns_500(client, mock_db):
    """Unhandled DB errors on login propagate as 500 without leaking details."""
    mock_db.fetchrow.side_effect = Exception("connection refused")

    response = client["client"].post(
        "/login",
        json={"email": "admin@uvote.com", "password": "admin123"},
    )

    assert response.status_code == 500
    assert "connection refused" not in response.text


def test_validate_token_db_error_returns_500(client, mock_db):
    """Unhandled DB errors on token validation return 500."""
    mock_db.fetchrow.side_effect = Exception("asyncpg error")

    response = client["client"].get("/tokens/any-token/validate")

    assert response.status_code == 500
    assert "asyncpg error" not in response.text


def test_mfa_verify_db_error_returns_500(client, mock_db):
    """Unhandled DB errors on MFA verify return 500."""
    mock_db.fetchrow.side_effect = Exception("db error")

    response = client["client"].post(
        "/mfa/verify",
        params={"token": "any-token", "date_of_birth": "1990-01-01"},
    )

    assert response.status_code == 500
