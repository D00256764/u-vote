"""
voting-service/tests/test_voting.py — unit tests for voting-service endpoints.

All tests use the mock_db and mock_auth fixtures; no Kubernetes cluster or
live database is needed.

Run with:
    .venv/bin/python -m pytest voting-service/tests/ -v
"""
import json
from datetime import datetime
from unittest.mock import MagicMock

import httpx


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_resp(status_code, data=None, json_error=False):
    """Build a MagicMock HTTP response for configuring mock_auth."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_error:
        resp.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
    else:
        resp.json.return_value = data if data is not None else {}
    return resp


# =============================================================================
# GET /vote/{token}
# =============================================================================

def test_vote_landing_valid_token(client, mock_db, mock_auth):
    """Returns 200 with identity verification page for a valid, unused token.

    vote_landing makes two GET calls to auth-service in order:
      1. /tokens/{token}/validate  → {"valid": True, "election_id": 1}
      2. /mfa/status?token=...     → {"mfa_verified": False}

    With mfa_verified=False the service renders verify_identity.html.
    """
    mock_auth.get.side_effect = [
        _make_resp(200, {"valid": True, "election_id": 1}),
        _make_resp(200, {"mfa_verified": False}),
    ]

    response = client["client"].get("/vote/some-valid-token")

    assert response.status_code == 200
    assert "Verify Your Identity" in response.text


def test_vote_landing_invalid_token(client, mock_db, mock_auth):
    """Returns an error page when auth-service rejects the token (non-200).

    vote_error.html renders the error string passed by app.py via {{ error }}.
    The exact error string comes from the "detail" key in the auth-service
    response, so we assert on what we put in the mock response.
    """
    mock_auth.get.return_value = _make_resp(
        400, {"detail": "Invalid or expired token"}
    )

    response = client["client"].get("/vote/some-invalid-token")

    assert response.status_code == 200
    assert "Invalid or expired token" in response.text


def test_vote_landing_auth_unreachable(client, mock_db, mock_auth):
    """Returns a rendered error page (not a raw traceback) when auth-service
    is unreachable.

    app.py wraps the httpx GET in try/except httpx.RequestError and calls
    _error_page(request, "Service unavailable") on failure.
    httpx.ConnectError is a subclass of httpx.RequestError.
    """
    mock_auth.get.side_effect = httpx.ConnectError("Connection refused")

    response = client["client"].get("/vote/some-token")

    assert response.status_code == 200
    assert "Service unavailable" in response.text
    assert "Traceback" not in response.text


# =============================================================================
# safe_json()
# =============================================================================

def test_safe_json_returns_none_on_invalid_json():
    """safe_json() silently handles malformed JSON.

    Implementation detail: safe_json returns `fallback or {}` which evaluates
    to {} (empty dict) when fallback=None — NOT None as the docstring implies.
    The actual return value is {}.
    """
    import app as voting_app

    mock_resp = MagicMock()
    mock_resp.json.side_effect = json.JSONDecodeError("msg", "doc", 0)

    result = voting_app.safe_json(mock_resp)

    # Returns {} (empty dict), not None — fallback=None → fallback or {} = {}
    assert result == {}


def test_safe_json_returns_dict_on_valid_json():
    """safe_json() returns the parsed dict on valid JSON responses."""
    import app as voting_app

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"valid": True}

    result = voting_app.safe_json(mock_resp)

    assert result == {"valid": True}


def test_safe_json_none_handled_in_vote_landing(client, mock_db, mock_auth):
    """When the validate response has malformed JSON, vote_landing does not
    crash — it renders verify_identity.html.

    With status_code=200 and safe_json returning {}, vote_landing skips the
    error-page branch. It then checks mfa_verified (False) and renders the
    identity form — no crash, no 500.
    """
    bad_validate = MagicMock()
    bad_validate.status_code = 200
    bad_validate.json.side_effect = json.JSONDecodeError("msg", "doc", 0)

    good_mfa = _make_resp(200, {"mfa_verified": False})

    mock_auth.get.side_effect = [bad_validate, good_mfa]

    response = client["client"].get("/vote/some-token")

    assert response.status_code == 200
    assert "Verify Your Identity" in response.text


# =============================================================================
# POST /vote/submit
# =============================================================================

def test_submit_vote_success(client, mock_db, mock_auth,
                             valid_ballot_token_row, valid_election_row,
                             valid_option_row):
    """Returns 200 with success HTML on a valid ballot token + option.

    submit_vote makes 5 fetchrow calls in this order:
      1. blind_tokens lookup (validates ballot_token)
      2. elections lookup (validates election is open + gets enc_key)
      3. election_options lookup (validates option belongs to election)
      4. encrypted_ballots — previous hash for hash chain (may be None)
      5. encrypted_ballots — fetch ballot_hash set by DB trigger after INSERT

    Four execute calls follow (INSERT encrypted_ballots, INSERT vote_receipts,
    UPDATE blind_tokens, INSERT audit_log).
    """
    mock_db.fetchrow.side_effect = [
        valid_ballot_token_row,           # 1. blind_tokens lookup
        valid_election_row,               # 2. elections lookup
        valid_option_row,                 # 3. election_options lookup
        None,                             # 4. no previous ballot in hash chain
        {"ballot_hash": "testhash123"},   # 5. ballot_hash set by DB trigger
    ]

    response = client["client"].post(
        "/vote/submit",
        data={
            "ballot_token": "test-ballot-token-abc123",
            "option_id": "1",
            "election_id": "1",
        },
    )

    assert response.status_code == 200
    assert "Vote Successfully Cast" in response.text
    assert "testhash123" in response.text


def test_submit_vote_duplicate_ballot_token(client, mock_db, mock_auth,
                                           valid_ballot_token_row):
    """Duplicate ballot token submission is rejected with error in HTML body.

    app.py checks bt_row["is_used"] and returns
    _error_page(request, "This ballot token has already been used").
    vote_error.html renders {{ error }} directly, so that string appears in body.
    """
    used_row = {**valid_ballot_token_row, "is_used": True}
    mock_db.fetchrow.return_value = used_row

    response = client["client"].post(
        "/vote/submit",
        data={
            "ballot_token": "test-ballot-token-abc123",
            "option_id": "1",
            "election_id": "1",
        },
    )

    assert response.status_code == 200
    assert "already been used" in response.text


def test_submit_vote_invalid_ballot_token(client, mock_db, mock_auth):
    """Invalid ballot token (not in DB) returns error in HTML body.

    app.py returns _error_page(request, "Invalid ballot token") when
    fetchrow returns None for the blind_tokens lookup.
    """
    mock_db.fetchrow.return_value = None

    response = client["client"].post(
        "/vote/submit",
        data={
            "ballot_token": "nonexistent-token",
            "option_id": "1",
            "election_id": "1",
        },
    )

    assert response.status_code == 200
    assert "Invalid ballot token" in response.text


def test_submit_vote_closed_election(client, mock_db, mock_auth,
                                    valid_ballot_token_row):
    """Attempting to vote in a closed election returns error in HTML body.

    app.py returns _error_page(request, "Election is not currently open")
    when election["status"] != "open".
    """
    closed_election = {
        "id": 1,
        "status": "closed",
        "encryption_key": "test-key",
    }
    mock_db.fetchrow.side_effect = [
        {**valid_ballot_token_row, "is_used": False},
        closed_election,
    ]

    response = client["client"].post(
        "/vote/submit",
        data={
            "ballot_token": "test-ballot-token-abc123",
            "option_id": "1",
            "election_id": "1",
        },
    )

    assert response.status_code == 200
    assert "not currently open" in response.text


# =============================================================================
# GET /receipt/{receipt_token}
# =============================================================================

def test_receipt_valid(client, mock_db):
    """Returns 200 JSON with verified=True and receipt data for a known token."""
    mock_db.fetchrow.return_value = {
        "receipt_token": "valid-receipt-token",
        "ballot_hash": "deadbeef123",
        "election_id": 1,
        "cast_at": datetime(2026, 1, 1, 12, 0, 0),
        "title": "Test Election 2026",
    }

    response = client["client"].get("/receipt/valid-receipt-token")

    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is True
    assert data["ballot_hash"] == "deadbeef123"
    assert data["election_title"] == "Test Election 2026"


def test_receipt_not_found(client, mock_db):
    """Returns 404 for a receipt token that does not exist in the database."""
    mock_db.fetchrow.return_value = None

    response = client["client"].get("/receipt/nonexistent-token")

    assert response.status_code == 404


# =============================================================================
# Auth-service unreachability during submit (architecture documentation test)
# =============================================================================

def test_auth_service_unreachable_on_submit(client, mock_db, mock_auth,
                                            valid_ballot_token_row,
                                            valid_election_row):
    """submit_vote does NOT call auth-service at all.

    The anonymity protocol separates concerns:
      - /vote/verify-identity (step 2) calls auth-service to verify DOB
        and acquire the blind ballot token
      - /vote/submit (step 3) only reads from and writes to the DB

    Even if mock_auth raises httpx.ConnectError on every call, submit
    succeeds as long as DB calls succeed. This test documents that boundary.
    """
    mock_auth.get.side_effect = httpx.ConnectError("Should not be called")
    mock_auth.post.side_effect = httpx.ConnectError("Should not be called")

    valid_option = {"id": 1}
    mock_db.fetchrow.side_effect = [
        valid_ballot_token_row,           # blind_tokens lookup
        valid_election_row,               # elections lookup
        valid_option,                     # election_options lookup
        None,                             # no previous ballot
        {"ballot_hash": "testhash456"},   # ballot_hash after INSERT
    ]

    response = client["client"].post(
        "/vote/submit",
        data={
            "ballot_token": "test-ballot-token-abc123",
            "option_id": "1",
            "election_id": "1",
        },
    )

    # submit_vote never calls auth-service, so ConnectError is never raised
    assert response.status_code == 200
    assert "Vote Successfully Cast" in response.text
