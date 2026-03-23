"""
admin-service/tests/test_admin.py — pytest unit tests for admin-service.

Coverage:
  - GET /health
  - POST /elections/{id}/voters          (add single voter)
  - POST /elections/{id}/voters/upload   (CSV bulk upload)
  - POST /elections/{id}/tokens/generate (token generation + email)
  - POST /mfa/verify                     (DOB verification)
  - DB error propagation (non-unique exceptions → 500)

Architecture notes:
  - admin-service imports Database from the shared 'database' module.
  - send_voting_token_email is imported into app.py's namespace and
    patched at "app.send_voting_token_email".
  - generate_tokens uses Database.transaction(), so fetchrow, fetch, and
    execute all route through the same mock_conn inside the transaction.
  - mfa/verify takes token and date_of_birth as QUERY PARAMETERS.
  - upload_voters multipart field name is "file".
"""
import re
from datetime import date, datetime, timedelta
from unittest.mock import call, patch

import pytest


# ── GET /health ───────────────────────────────────────────────────────────────

def test_health_returns_admin(client):
    """Health endpoint returns service: admin (CV-7 fixed the old 'voter' value)."""
    r = client["client"].get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy", "service": "admin"}


# ── POST /elections/{id}/voters ───────────────────────────────────────────────

def test_add_voter_success(client, mock_db):
    """Returns 201 with voter_id on valid input."""
    # app.py: conn.fetchrow(INSERT ... RETURNING id) → {"id": 1}
    mock_db.fetchrow.return_value = {"id": 1}

    r = client["client"].post(
        "/elections/1/voters",
        json={"email": "voter@test.com", "date_of_birth": "1990-06-15"},
    )
    assert r.status_code == 201
    data = r.json()
    assert "voter_id" in data
    assert data["voter_id"] == 1


def test_add_voter_duplicate_email_returns_409(client, mock_db):
    """
    Returns 409 when voter email already exists in the election.

    app.py catches broad Exception and checks 'unique' in str(e).lower().
    The raw exception message must not be leaked in the response body.
    """
    mock_db.fetchrow.side_effect = Exception("unique constraint violation")

    r = client["client"].post(
        "/elections/1/voters",
        json={"email": "voter@test.com", "date_of_birth": "1990-06-15"},
    )
    assert r.status_code == 409
    body = r.json()
    # FastAPI returns {"detail": "Voter already exists for this election"}
    assert "unique constraint violation" not in str(body).lower()
    assert "detail" in body


def test_add_voter_missing_fields_returns_422(client, mock_db):
    """Returns 422 when required fields (email, date_of_birth) are absent."""
    r = client["client"].post("/elections/1/voters", json={})
    assert r.status_code == 422


def test_add_voter_missing_email_returns_422(client, mock_db):
    """Returns 422 when email is absent."""
    r = client["client"].post(
        "/elections/1/voters",
        json={"date_of_birth": "1990-06-15"},
    )
    assert r.status_code == 422


def test_add_voter_invalid_date_returns_500(client, mock_db):
    """
    DOCUMENTS A REAL BUG: date_of_birth is typed as 'str' in VoterAddRequest,
    so pydantic accepts "not-a-date" without error.  Inside the handler the
    date.fromisoformat() call is inside the try/except block, so the resulting
    ValueError is caught and re-raised as HTTP 500 instead of 422.

    The fix would be to move date parsing outside the try block or add explicit
    ValueError handling that returns 422.
    """
    r = client["client"].post(
        "/elections/1/voters",
        json={"email": "voter@test.com", "date_of_birth": "not-a-date"},
    )
    assert r.status_code == 500


def test_add_voter_db_error_returns_500(client, mock_db):
    """Unhandled DB errors (non-unique exception text) propagate as HTTP 500."""
    mock_db.fetchrow.side_effect = Exception("connection lost")

    r = client["client"].post(
        "/elections/1/voters",
        json={"email": "voter@test.com", "date_of_birth": "1990-06-15"},
    )
    assert r.status_code == 500


# ── POST /elections/{id}/voters/upload ───────────────────────────────────────

def test_upload_voters_csv_success(client, mock_db):
    """
    Returns 201 (not 200 — route declares status_code=201) with
    voters_added and voters_skipped counts on a well-formed CSV.
    """
    csv_content = (
        b"email,date_of_birth\n"
        b"voter1@test.com,1990-01-01\n"
        b"voter2@test.com,1991-02-02\n"
    )
    r = client["client"].post(
        "/elections/1/voters/upload",
        files={"file": ("voters.csv", csv_content, "text/csv")},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["voters_added"] == 2
    assert data["voters_skipped"] == 0


def test_upload_voters_csv_skips_duplicates(client, mock_db):
    """
    Silently skips rows that cause a unique constraint violation;
    voters_added and voters_skipped counts are accurate.
    """
    # First execute succeeds, second raises unique constraint
    mock_db.execute.side_effect = [None, Exception("unique constraint violation")]

    csv_content = (
        b"email,date_of_birth\n"
        b"voter1@test.com,1990-01-01\n"
        b"voter2@test.com,1991-02-02\n"
    )
    r = client["client"].post(
        "/elections/1/voters/upload",
        files={"file": ("voters.csv", csv_content, "text/csv")},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["voters_added"] == 1
    assert data["voters_skipped"] == 1


def test_upload_voters_csv_skips_invalid_rows(client, mock_db):
    """
    Rows with a missing email or date_of_birth are silently skipped
    (the app checks for empty strings before calling conn.execute).
    """
    csv_content = (
        b"email,date_of_birth\n"
        b"voter1@test.com,1990-01-01\n"
        b",1991-02-02\n"          # empty email → skipped
    )
    r = client["client"].post(
        "/elections/1/voters/upload",
        files={"file": ("voters.csv", csv_content, "text/csv")},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["voters_added"] == 1
    assert data["voters_skipped"] == 1


def test_upload_voters_csv_missing_email_column_returns_400(client, mock_db):
    """Returns 400 when the CSV has no 'email' column header."""
    csv_content = b"name,date_of_birth\nAlice,1990-01-01\n"
    r = client["client"].post(
        "/elections/1/voters/upload",
        files={"file": ("voters.csv", csv_content, "text/csv")},
    )
    assert r.status_code == 400
    assert "email" in r.json()["detail"].lower()


def test_upload_voters_csv_missing_dob_column_returns_400(client, mock_db):
    """Returns 400 when the CSV has no 'date_of_birth' column header."""
    csv_content = b"email\nvoter@test.com\n"
    r = client["client"].post(
        "/elections/1/voters/upload",
        files={"file": ("voters.csv", csv_content, "text/csv")},
    )
    assert r.status_code == 400
    assert "date_of_birth" in r.json()["detail"].lower()


# ── POST /elections/{id}/tokens/generate ─────────────────────────────────────

def _setup_generate_tokens(mock_db, *, voter_email="voter@test.com", voter_id=1):
    """
    Configure mock_db for a generate_tokens request with one voter.

    Call order inside generate_tokens (all under one Database.transaction):
        1. fetchrow → election title row
        2. fetch    → [{"id": voter_id}]  (voters without active tokens)
        3. execute  → None                (INSERT voting_token)
        4. fetchrow → {"email": voter_email} (voter email for the token dict)
    """
    mock_db.fetchrow.side_effect = [
        {"title": "Test Election 2026"},   # 1st: SELECT title FROM elections
        {"email": voter_email},            # 2nd: SELECT email FROM voters
    ]
    mock_db.fetch.return_value = [{"id": voter_id}]
    mock_db.execute.return_value = None


def test_generate_tokens_success(client, mock_db, mock_email):
    """Returns 200 with correct tokens_generated / emails_sent / emails_failed counts."""
    _setup_generate_tokens(mock_db)

    r = client["client"].post("/elections/1/tokens/generate")
    assert r.status_code == 200
    data = r.json()
    assert data["tokens_generated"] == 1
    assert data["emails_sent"] == 1
    assert data["emails_failed"] == 0
    assert mock_email.called


def test_generate_tokens_election_not_found_returns_404(client, mock_db, mock_email):
    """Returns 404 when the election_id does not exist."""
    mock_db.fetchrow.return_value = None  # SELECT title returns nothing

    r = client["client"].post("/elections/99/tokens/generate")
    assert r.status_code == 404


def test_generate_tokens_no_voters_returns_empty(client, mock_db, mock_email):
    """Returns 200 with tokens_generated=0 when all voters already have tokens."""
    mock_db.fetchrow.return_value = {"title": "Test Election 2026"}
    mock_db.fetch.return_value = []  # no voters without active tokens

    r = client["client"].post("/elections/1/tokens/generate")
    assert r.status_code == 200
    data = r.json()
    assert data["tokens_generated"] == 0
    assert data["emails_sent"] == 0
    assert not mock_email.called


def test_generate_tokens_email_failure_is_nonfatal(client, mock_db, mock_email):
    """
    Email failures increment emails_failed but the overall request still
    succeeds (200).  The token was already written to the DB before the email
    attempt, so tokens_generated still reflects the INSERT.
    """
    _setup_generate_tokens(mock_db)
    mock_email.side_effect = Exception("SMTP connection refused")

    r = client["client"].post("/elections/1/tokens/generate")
    assert r.status_code == 200
    data = r.json()
    assert data["tokens_generated"] == 1
    assert data["emails_sent"] == 0
    assert data["emails_failed"] == 1


def test_generate_tokens_email_failure_logs_error(client, mock_db, mock_email):
    """
    logger.error() is called with 'Failed to send email' when email sending
    raises an exception.  Verified by patching app.logger inside the test.
    """
    _setup_generate_tokens(mock_db)
    mock_email.side_effect = Exception("SMTP timeout")

    with patch("app.logger") as mock_logger:
        r = client["client"].post("/elections/1/tokens/generate")

    assert r.status_code == 200
    assert mock_logger.error.called
    # app.py: logger.error('Failed to send email: %s', e)
    first_call = mock_logger.error.call_args
    assert "Failed to send email" in first_call.args[0]


def test_generate_tokens_token_format(client, mock_db, mock_email):
    """
    Generated token uses secrets.token_urlsafe(32) which produces exactly
    43 URL-safe base64 characters (A-Z, a-z, 0-9, -, _).
    The token is captured from the kwargs passed to send_voting_token_email.
    """
    _setup_generate_tokens(mock_db)

    r = client["client"].post("/elections/1/tokens/generate")
    assert r.status_code == 200
    assert mock_email.called

    token = mock_email.call_args.kwargs["token"]
    assert len(token) == 43, f"Expected 43 chars, got {len(token)}: {token!r}"
    assert re.fullmatch(r"[A-Za-z0-9_\-]+", token), (
        f"Token contains non-URL-safe characters: {token!r}"
    )


def test_generate_tokens_expiry_is_7_days(client, mock_db, mock_email):
    """
    Generated token expires 7 days (168 hours) from now.

    expires_at is captured from the positional args of the INSERT execute call:
        conn.execute(sql, token, voter_id, election_id, expires_at)
                                                         ^-- index [4]
    """
    _setup_generate_tokens(mock_db)

    before = datetime.now()
    r = client["client"].post("/elections/1/tokens/generate")
    after = datetime.now()

    assert r.status_code == 200

    # args: (sql, token, voter_id, election_id, expires_at)
    expires_at = mock_db.execute.call_args.args[4]
    assert isinstance(expires_at, datetime)

    expected_low  = before + timedelta(hours=168) - timedelta(seconds=10)
    expected_high = after  + timedelta(hours=168) + timedelta(seconds=10)
    assert expected_low <= expires_at <= expected_high, (
        f"expires_at {expires_at!r} not within 10s of now + 7 days"
    )


def test_generate_tokens_email_called_with_correct_kwargs(client, mock_db, mock_email):
    """
    send_voting_token_email is called with to_email, token, election_title,
    and expires_at keyword arguments matching what is stored in the DB.
    """
    _setup_generate_tokens(mock_db, voter_email="voter@test.com")

    r = client["client"].post("/elections/1/tokens/generate")
    assert r.status_code == 200

    kwargs = mock_email.call_args.kwargs
    assert kwargs["to_email"] == "voter@test.com"
    assert kwargs["election_title"] == "Test Election 2026"
    assert "token" in kwargs
    assert "expires_at" in kwargs


def test_generate_tokens_db_error_returns_500(client, mock_db, mock_email):
    """
    Unhandled DB errors (no try/except in generate_tokens) propagate as
    HTTP 500.  There is no catch-all around the transaction block.
    """
    mock_db.fetchrow.return_value = {"title": "Test Election 2026"}
    mock_db.fetch.side_effect = Exception("db connection lost")

    r = client["client"].post("/elections/1/tokens/generate")
    assert r.status_code == 500


# ── POST /mfa/verify ──────────────────────────────────────────────────────────

def _mfa_token_row(dob=date(1990, 6, 15), is_used=False, status="open"):
    """
    Returns the combined row shape returned by the JOIN query in verify_identity:
        SELECT v.date_of_birth, vt.is_used, vt.expires_at, e.status
        FROM voting_tokens vt
        JOIN voters v ON v.id = vt.voter_id
        JOIN elections e ON e.id = vt.election_id
        WHERE vt.token = $1
    """
    return {
        "date_of_birth": dob,
        "is_used": is_used,
        "expires_at": datetime.now() + timedelta(days=7),
        "status": status,
    }


def test_mfa_verify_correct_dob(client, mock_db):
    """Returns 200 {"verified": True} when date_of_birth matches."""
    # 1st fetchrow: token+voter+election join row
    # 2nd fetchrow: existing MFA check (None = not yet verified → INSERT runs)
    mock_db.fetchrow.side_effect = [_mfa_token_row(), None]

    r = client["client"].post(
        "/mfa/verify?token=test-token&date_of_birth=1990-06-15"
    )
    assert r.status_code == 200
    assert r.json() == {"verified": True}


def test_mfa_verify_wrong_dob_returns_403(client, mock_db):
    """Returns 403 when submitted date_of_birth does not match stored value."""
    mock_db.fetchrow.return_value = _mfa_token_row(dob=date(1990, 6, 15))

    r = client["client"].post(
        "/mfa/verify?token=test-token&date_of_birth=1900-01-01"
    )
    assert r.status_code == 403
    assert "date of birth" in r.json()["detail"].lower()


def test_mfa_verify_token_not_found_returns_404(client, mock_db):
    """Returns 404 when the token does not exist in voting_tokens."""
    mock_db.fetchrow.return_value = None

    r = client["client"].post(
        "/mfa/verify?token=nonexistent&date_of_birth=1990-06-15"
    )
    assert r.status_code == 404


def test_mfa_verify_used_token_returns_400(client, mock_db):
    """Returns 400 when the token has already been used."""
    mock_db.fetchrow.return_value = _mfa_token_row(is_used=True)

    r = client["client"].post(
        "/mfa/verify?token=used-token&date_of_birth=1990-06-15"
    )
    assert r.status_code == 400
    assert "already used" in r.json()["detail"].lower()


def test_mfa_verify_closed_election_returns_400(client, mock_db):
    """Returns 400 when the election is not open."""
    mock_db.fetchrow.return_value = _mfa_token_row(status="closed")

    r = client["client"].post(
        "/mfa/verify?token=test-token&date_of_birth=1990-06-15"
    )
    assert r.status_code == 400
    assert "not open" in r.json()["detail"].lower()


def test_mfa_verify_invalid_date_format_returns_400(client, mock_db):
    """Returns 400 when date_of_birth is not a valid ISO date string."""
    r = client["client"].post(
        "/mfa/verify?token=test-token&date_of_birth=not-a-date"
    )
    assert r.status_code == 400
    assert "Invalid date format" in r.json()["detail"]


def test_mfa_verify_already_verified_does_not_duplicate(client, mock_db):
    """
    When a voter has already completed MFA (existing voter_mfa row found),
    the handler skips the INSERT and still returns {"verified": True}.
    """
    existing_mfa_row = {"id": 99}
    mock_db.fetchrow.side_effect = [_mfa_token_row(), existing_mfa_row]

    r = client["client"].post(
        "/mfa/verify?token=test-token&date_of_birth=1990-06-15"
    )
    assert r.status_code == 200
    assert r.json() == {"verified": True}
    # execute (INSERT voter_mfa) must NOT have been called
    mock_db.execute.assert_not_called()


# ── GET /tokens/{token}/validate ─────────────────────────────────────────────

def test_validate_token_valid(client, mock_db):
    """Returns 200 with valid=True for an unused, non-expired, open-election token."""
    mock_db.fetchrow.return_value = {
        "id": 1,
        "voter_id": 1,
        "election_id": 1,
        "is_used": False,
        "expires_at": datetime.now() + timedelta(days=7),
        "status": "open",
    }
    r = client["client"].get("/tokens/test-token/validate")
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert data["election_id"] == 1
    assert data["voter_id"] == 1


def test_validate_token_not_found_returns_404(client, mock_db):
    """Returns 404 for an unrecognised token."""
    mock_db.fetchrow.return_value = None
    r = client["client"].get("/tokens/bad-token/validate")
    assert r.status_code == 404


def test_validate_token_used_returns_400(client, mock_db):
    """Returns 400 when the token has already been used."""
    mock_db.fetchrow.return_value = {
        "id": 1, "voter_id": 1, "election_id": 1,
        "is_used": True,
        "expires_at": datetime.now() + timedelta(days=7),
        "status": "open",
    }
    r = client["client"].get("/tokens/used-token/validate")
    assert r.status_code == 400
    assert "already used" in r.json()["detail"].lower()


def test_validate_token_expired_returns_400(client, mock_db):
    """Returns 400 when the token has passed its expires_at timestamp."""
    mock_db.fetchrow.return_value = {
        "id": 1, "voter_id": 1, "election_id": 1,
        "is_used": False,
        "expires_at": datetime.now() - timedelta(seconds=1),
        "status": "open",
    }
    r = client["client"].get("/tokens/expired-token/validate")
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()
