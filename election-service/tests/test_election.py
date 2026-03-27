"""
election-service/tests/test_election.py — pytest unit tests for election-service.

All tests use a fully mocked database (mock_db fixture from conftest.py).
No live Kubernetes cluster or database is required.

Run with:
    .venv/bin/python -m pytest election-service/tests/ -v

Architecture notes:
    - election-service has NO try/except blocks — DB errors propagate as raw 500s.
    - Both JSON API endpoints and HTML form endpoints exist.
    - organiser_id (GB spelling) is used throughout app.py.
    - open_election / close_election use conn.execute and check for "UPDATE 0".
    - HTML form endpoints require a valid Starlette session cookie.
"""
import base64
import json

from itsdangerous import TimestampSigner


# ---------------------------------------------------------------------------
# Session cookie helper
# ---------------------------------------------------------------------------

def make_session_cookie(session_data: dict, secret_key: str = "test-secret-key") -> str:
    """Build a signed Starlette session cookie.

    SessionMiddleware signs cookies as:
        TimestampSigner(secret_key).sign(base64(json(session_data)))

    We reproduce this here so HTML form endpoint tests can inject a valid
    session without needing a live server or a prior login request.
    """
    data = base64.b64encode(json.dumps(session_data).encode("utf-8"))
    signer = TimestampSigner(secret_key)
    return signer.sign(data).decode("utf-8")


# Session data used by all HTML form tests.
ORGANISER_SESSION = {"token": "test-token", "organiser_id": 1}


# ===========================================================================
# POST /elections — JSON API
# ===========================================================================

def test_create_election_success(client, mock_db):
    """Returns 201 with election_id on valid input.

    create_election call order:
        1. conn.fetchrow  — INSERT INTO elections ... RETURNING id
        2. conn.execute   — INSERT INTO election_options (one per option)
    """
    mock_db.fetchrow.return_value = {"id": 1}
    # conn.execute default (None) is fine for option inserts

    tc = client["client"]
    resp = tc.post(
        "/elections?organiser_id=1",
        json={
            "title": "Test Election",
            "description": "Desc",
            "options": ["Option A", "Option B", "Option C"],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "election_id" in body
    assert body["election_id"] == 1


def test_create_election_missing_title(client, mock_db):
    """Returns 422 on missing required title field.

    ElectionCreate.title has min_length=1 and is required — Pydantic rejects
    the request before it reaches the DB.
    """
    tc = client["client"]
    resp = tc.post(
        "/elections?organiser_id=1",
        json={"description": "Desc", "options": ["Option A", "Option B"]},
    )
    assert resp.status_code == 422


def test_create_election_too_few_options(client, mock_db):
    """Returns 422 if fewer than 2 options provided.

    ElectionCreate.options has min_length=2 (shared/schemas.py). A single
    option fails Pydantic validation before reaching the DB.
    """
    tc = client["client"]
    resp = tc.post(
        "/elections?organiser_id=1",
        json={"title": "Test Election", "options": ["Only One"]},
    )
    assert resp.status_code == 422


# ===========================================================================
# GET /elections — JSON API
# ===========================================================================

def test_list_elections_returns_list(client, mock_db, draft_election_row):
    """Returns list of elections for an organiser."""
    mock_db.fetch.return_value = [draft_election_row]

    tc = client["client"]
    resp = tc.get("/elections?organiser_id=1")
    assert resp.status_code == 200
    body = resp.json()
    assert "elections" in body
    assert isinstance(body["elections"], list)
    assert len(body["elections"]) == 1
    assert body["elections"][0]["id"] == 1
    assert body["elections"][0]["status"] == "draft"


def test_list_elections_empty(client, mock_db):
    """Returns empty list when organiser has no elections."""
    mock_db.fetch.return_value = []

    tc = client["client"]
    resp = tc.get("/elections?organiser_id=1")
    assert resp.status_code == 200
    assert resp.json()["elections"] == []


def test_list_elections_no_organiser_id(client, mock_db):
    """Returns 422 when organiser_id query param is missing.

    organiser_id is a required (non-optional) int query parameter on
    list_elections — FastAPI rejects missing params with 422.
    """
    tc = client["client"]
    resp = tc.get("/elections")
    assert resp.status_code == 422


# ===========================================================================
# GET /elections/{id} — JSON API
# ===========================================================================

def test_get_election_found(client, mock_db, draft_election_row, election_options_rows):
    """Returns election detail with options for a valid id.

    get_election call order:
        1. conn.fetchrow  — SELECT election WHERE id=$1
        2. conn.fetch     — SELECT options WHERE election_id=$1
        3. conn.fetchval  — COUNT(*) FROM voters
        4. conn.fetchval  — COUNT(*) FROM encrypted_ballots
    """
    mock_db.fetchrow.return_value = draft_election_row
    mock_db.fetch.return_value = election_options_rows
    mock_db.fetchval.return_value = 0  # both voter_count and vote_count

    tc = client["client"]
    resp = tc.get("/elections/1")
    assert resp.status_code == 200
    body = resp.json()
    assert "election" in body
    assert "options" in body
    assert body["election"]["id"] == 1
    assert body["election"]["status"] == "draft"
    assert len(body["options"]) == 3
    assert body["options"][0]["text"] == "Option A"


def test_get_election_not_found(client, mock_db):
    """Returns 404 for non-existent election."""
    mock_db.fetchrow.return_value = None

    tc = client["client"]
    resp = tc.get("/elections/999")
    assert resp.status_code == 404


def test_get_election_ownership_check(client, mock_db, draft_election_row):
    """Returns 403 when organiser_id is provided but does not match the election.

    get_election checks (app.py line 167):
        if organiser_id is not None and election["organiser_id"] != organiser_id:
            raise HTTPException(status_code=403, detail="Access denied")

    draft_election_row has organiser_id=1; requesting with organiser_id=99 → 403.
    """
    mock_db.fetchrow.return_value = draft_election_row  # organiser_id=1

    tc = client["client"]
    resp = tc.get("/elections/1?organiser_id=99")
    assert resp.status_code == 403


# ===========================================================================
# POST /elections/{id}/open — JSON API
# ===========================================================================

def test_open_election_success(client, mock_db):
    """Returns 200 when election transitions from draft to open.

    open_election uses conn.execute for an UPDATE WHERE status='draft'.
    It checks: if result == "UPDATE 0": raise 400.
    Default execute.return_value is None → None != "UPDATE 0" → success (200).
    """
    # Default execute.return_value = None → success path
    tc = client["client"]
    resp = tc.post("/elections/1/open?organiser_id=1")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Election opened successfully"


def test_open_election_already_open(client, mock_db):
    """Returns 400 when election is not in draft status.

    The UPDATE WHERE status='draft' matches 0 rows when the election is already
    open or closed → execute returns 'UPDATE 0' → open_election raises 400.
    """
    mock_db.execute.return_value = "UPDATE 0"

    tc = client["client"]
    resp = tc.post("/elections/1/open?organiser_id=1")
    assert resp.status_code == 400


def test_open_election_not_found(client, mock_db):
    """Returns 400 when election does not exist.

    open_election uses a single UPDATE (no prior SELECT), so a missing election
    also returns 'UPDATE 0' → 400. The detail distinguishes this as
    "not found, not yours, or not in draft status".
    """
    mock_db.execute.return_value = "UPDATE 0"

    tc = client["client"]
    resp = tc.post("/elections/999/open?organiser_id=1")
    assert resp.status_code == 400


# ===========================================================================
# POST /elections/{id}/close — JSON API
# ===========================================================================

def test_close_election_success(client, mock_db, open_election_row):
    """Returns 200 when election transitions from open to closed.

    close_election uses conn.execute for an UPDATE WHERE status='open'.
    Default execute.return_value is None → success (200).
    """
    # Default execute.return_value = None → success path
    tc = client["client"]
    resp = tc.post("/elections/1/close?organiser_id=1")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Election closed successfully"


def test_close_election_already_closed(client, mock_db):
    """Returns 400 when election is not in open status.

    The UPDATE WHERE status='open' matches 0 rows → execute returns 'UPDATE 0'
    → close_election raises HTTPException(400).
    """
    mock_db.execute.return_value = "UPDATE 0"

    tc = client["client"]
    resp = tc.post("/elections/1/close?organiser_id=1")
    assert resp.status_code == 400


# ===========================================================================
# DB error propagation — election-service has NO try/except blocks
# ===========================================================================

def test_list_elections_db_error_returns_500(client, mock_db):
    """Unhandled DB errors on list elections propagate as raw 500.

    election-service has no try/except. conn.fetch raising an exception
    propagates to FastAPI's default error handler → 500 Internal Server Error.
    With raise_server_exceptions=False, the TestClient captures the 500
    rather than re-raising the exception in the test process.

    Response body: FastAPI wraps unhandled errors as a generic 500 JSON
    without the original exception message (no detail field exposed).
    """
    mock_db.fetch.side_effect = Exception("db connection lost")

    tc = client["client"]
    resp = tc.get("/elections?organiser_id=1")
    assert resp.status_code == 500


def test_create_election_db_error_returns_500(client, mock_db):
    """Unhandled DB errors on create election propagate as raw 500.

    create_election uses Database.transaction() (also mocked). Raising from
    conn.fetchrow propagates before the INSERT completes → 500.
    """
    mock_db.fetchrow.side_effect = Exception("db error")

    tc = client["client"]
    resp = tc.post(
        "/elections?organiser_id=1",
        json={"title": "Test", "description": "Desc", "options": ["A", "B"]},
    )
    assert resp.status_code == 500


def test_get_election_db_error_returns_500(client, mock_db):
    """Unhandled DB errors on get election propagate as raw 500."""
    mock_db.fetchrow.side_effect = Exception("db error")

    tc = client["client"]
    resp = tc.get("/elections/1")
    assert resp.status_code == 500


# ===========================================================================
# HTML form endpoint tests
# ===========================================================================

def test_create_election_form_success(client, mock_db):
    """HTML form POST creates election and redirects (303) on success.

    Endpoint: POST /elections/create

    This endpoint is separate from the JSON API POST /elections — it reads
    multipart/form-data and uses request.session["organiser_id"] for the INSERT.

    _require_login checks request.session["token"]; a signed Starlette session
    cookie is injected manually using itsdangerous (same signing method as
    SessionMiddleware with SESSION_SECRET="test-secret-key").

    On success: flashes "Election created successfully!" and returns a
    303 redirect to /elections/{id}.
    """
    mock_db.fetchrow.return_value = {"id": 1}
    # conn.execute default (None) is fine for option inserts

    session_cookie = make_session_cookie(ORGANISER_SESSION)
    tc = client["client"]
    resp = tc.post(
        "/elections/create",
        data={
            "title": "Form Election",
            "description": "A form test",
            "options[]": ["Option A", "Option B"],
        },
        cookies={"session": session_cookie},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/elections/1" in resp.headers.get("location", "")


def test_create_election_form_missing_title(client, mock_db):
    """HTML form POST with missing title renders flash error (status 200).

    create_election_form now validates title before any DB call.
    A missing or blank title flashes "Election title is required" and
    re-renders the create form — no DB INSERT is attempted.
    """
    session_cookie = make_session_cookie(ORGANISER_SESSION)
    tc = client["client"]
    resp = tc.post(
        "/elections/create",
        data={"description": "No title here", "options[]": ["Option A", "Option B"]},
        cookies={"session": session_cookie},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Election title is required" in resp.text


def test_create_election_form_too_few_options(client, mock_db):
    """HTML form POST with fewer than 2 valid options renders flash error.

    create_election_form validates that at least 2 non-blank options are
    provided before any DB call. Submitting only 1 option flashes
    "At least 2 election options are required" and re-renders the form.
    """
    session_cookie = make_session_cookie(ORGANISER_SESSION)
    tc = client["client"]
    resp = tc.post(
        "/elections/create",
        data={"title": "Test Election", "options[]": ["Option A"]},
        cookies={"session": session_cookie},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "At least 2 election options are required" in resp.text
