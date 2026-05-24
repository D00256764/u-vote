"""
election-service/tests/test_security_idor.py — IDOR and cross-service
authorisation security tests.

Attack model:
  Organiser A (organiser_id=1) is authenticated and holds a valid JWT.
  Organiser B (organiser_id=2) owns election_id=102.
  Each test verifies that A cannot read, modify, or erase B's resources.

Services under test:
  election-service  — election CRUD, open/close lifecycle
  admin-service     — voter list, GDPR PII erasure

Neither service is started; all tests use httpx.AsyncClient with
ASGITransport and a fully mocked database (no live cluster required).

Key observation:
  election-service does NOT validate the Authorization: Bearer header.
  Organiser identity is conveyed via the organiser_id query parameter only.
  Tests that send A's JWT as Bearer do so to simulate a realistic attack;
  the service ignores the header.

Run:
    .venv/bin/python -m pytest election-service/tests/test_security_idor.py -v
"""

import importlib.util
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from jose import jwt as jose_jwt

# ── Path and module setup ─────────────────────────────────────────────────────
_ELECTION_DIR = Path(__file__).parent.parent   # u-vote/election-service/
_SHARED_DIR = _ELECTION_DIR.parent / "shared"  # u-vote/shared/

for _p in [str(_SHARED_DIR), str(_ELECTION_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# conftest.py already loads election-service under this name before test collection.
_ELECTION_MODULE = "election_service_app"
_election_app = sys.modules[_ELECTION_MODULE]

# Load admin-service using the same naming convention as its own conftest.py
# (admin-service/tests/conftest.py also uses "admin_service_app").
# The guard prevents double-loading when test suites run together.
_ADMIN_DIR = _ELECTION_DIR.parent / "admin-service"
_ADMIN_MODULE = "admin_service_app"

if _ADMIN_MODULE not in sys.modules:
    for _p in [str(_SHARED_DIR), str(_ADMIN_DIR)]:
        if _p not in sys.path:
            sys.path.insert(0, _p)

    _admin_spec = importlib.util.spec_from_file_location(
        _ADMIN_MODULE, _ADMIN_DIR / "app.py"
    )
    _admin_mod = importlib.util.module_from_spec(_admin_spec)
    sys.modules[_ADMIN_MODULE] = _admin_mod

    # StaticFiles(directory="static") calls os.path.isdir at __init__ time.
    # Bypass it so app.py loads cleanly regardless of CWD.
    with patch.object(os.path, "isdir", return_value=True):
        _admin_spec.loader.exec_module(_admin_mod)

    # Fix Jinja2 loader and StaticFiles to absolute paths (same fix as conftest.py).
    import jinja2 as _jinja2
    _admin_mod.templates.env.loader = _jinja2.FileSystemLoader(
        str(_ADMIN_DIR / "templates")
    )
    from starlette.staticfiles import StaticFiles as _StaticFiles
    for _route in _admin_mod.app.routes:
        if getattr(_route, "name", None) == "static":
            _route.app = _StaticFiles(
                directory=str(_ADMIN_DIR / "static"), check_dir=False
            )
            break

_admin_app = sys.modules[_ADMIN_MODULE]


# ── Constants ─────────────────────────────────────────────────────────────────

# JWT secret: matches auth-service env default (auth-service/app.py line 59).
_JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
_JWT_ALGORITHM = "HS256"

_A_ORGANISER_ID = 1
_B_ORGANISER_ID = 2
_A_ELECTION_ID = 101
_B_ELECTION_ID = 102

# Voting token format: secrets.token_urlsafe(32) — opaque URL-safe string,
# NOT a JWT.  Defined in shared/security.py:generate_voting_token().
_FAKE_VOTING_TOKEN = "FakeVotingToken_urlsafe_32bytes_xxxxxxxxxxx"


def _make_jwt(organiser_id: int, email: str) -> str:
    """Mint a signed organiser JWT matching auth-service's token structure."""
    return jose_jwt.encode(
        {
            "organiser_id": organiser_id,
            "email": email,
            "exp": datetime.utcnow() + timedelta(hours=1),
        },
        _JWT_SECRET,
        algorithm=_JWT_ALGORITHM,
    )


def _b_election_row() -> dict:
    """Minimal DB row for Organiser B's election (owned by B, not A)."""
    return {
        "id": _B_ELECTION_ID,
        "organiser_id": _B_ORGANISER_ID,
        "title": "Organiser B Election",
        "description": "Belongs to B only",
        "status": "draft",
        "created_at": datetime.utcnow(),
        "opened_at": None,
        "closed_at": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idor_get_election_cross_organiser(mock_db):
    """
    IDOR: Organiser A reads Organiser B's election details via the JSON API.

    Attack:
        A holds a valid JWT (organiser_id=1) and discovers B's election_id=102.
        A sends GET /elections/102?organiser_id=1 against election-service.
        If the service returns 200, A can read B's election title, description,
        status, voter count, and vote count — confidential planning data.

    Defence:
        election-service/app.py line 481-482:
            if organiser_id is not None and election["organiser_id"] != organiser_id:
                raise HTTPException(status_code=403, detail="Access denied")
        The check fires because B's election row has organiser_id=2
        while A supplies organiser_id=1.

    NOTE — secondary IDOR not tested here:
        When organiser_id is OMITTED from the query, line 481 is skipped
        entirely and GET /elections/{id} returns 200 for any caller.  That gap
        is outside the scope of this test but should be addressed by moving
        organiser identity into a validated JWT rather than a query param.

    Current status: PASSES — the ownership check exists for this request shape.
    """
    a_jwt = _make_jwt(_A_ORGANISER_ID, "a@test.com")
    mock_db.fetchrow.return_value = _b_election_row()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_election_app.app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            f"/elections/{_B_ELECTION_ID}",
            params={"organiser_id": _A_ORGANISER_ID},
            headers={"Authorization": f"Bearer {a_jwt}"},
        )

    assert resp.status_code == 403, (
        f"Expected 403 when Organiser A (id={_A_ORGANISER_ID}) reads Organiser B's "
        f"election (id={_B_ELECTION_ID}); got {resp.status_code}. "
        f"Response body: {resp.text[:200]}"
    )


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "GET /elections/{id}/voters is in admin-service and has no authentication "
        "or organiser ownership check (admin-service/app.py line 224-250). "
        "Any caller who supplies a valid election_id receives the full voter list "
        "including email and phone_number."
    ),
    strict=True,
)
async def test_idor_get_voter_list_cross_organiser(mock_db):
    """
    IDOR + GDPR: Organiser A reads voter PII for Organiser B's election.

    Attack:
        A holds a valid JWT (organiser_id=1) and knows B's election_id=102.
        A sends GET /elections/102/voters to admin-service with A's JWT as Bearer.
        admin-service/app.py line 224:
            async def get_voters(request: Request, election_id: int):
        There is no authentication dependency, no organiser_id parameter,
        and no ownership check.  The handler fetches voter rows unconditionally
        and returns email and phone_number for every voter in the election.

    Defence expected:
        The endpoint must verify that the caller's JWT organiser_id matches
        the election's organiser_id before returning voter data, and return
        HTTP 403 if the caller does not own the election.

    GDPR concern:
        email and phone_number are personal data under GDPR Article 4(1).
        Disclosing them across organisers constitutes a personal data breach
        (GDPR Article 33) regardless of whether the disclosure was intentional.
        This is both a security vulnerability and a compliance violation.

    Current status: FAILS — the endpoint returns HTTP 200 with all voter PII.
    Marked xfail until an ownership check is implemented.
    """
    a_jwt = _make_jwt(_A_ORGANISER_ID, "a@test.com")
    mock_db.fetch.return_value = [
        {
            "id": 10,
            "email": "voter@b-university.edu",
            "phone_number": "+353871234567",
            "created_at": datetime.utcnow(),
            "has_token": False,
        }
    ]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_admin_app.app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            f"/elections/{_B_ELECTION_ID}/voters",
            headers={"Authorization": f"Bearer {a_jwt}"},
        )

    assert resp.status_code == 403, (
        f"Expected 403 when Organiser A requests voter list for Organiser B's "
        f"election (id={_B_ELECTION_ID}); got {resp.status_code}. "
        f"Voter PII should not be exposed: {resp.text[:200]}"
    )


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "POST /elections/{id}/open and /close return HTTP 400 (from an UPDATE 0 "
        "result when the caller's organiser_id does not match the election row) "
        "instead of HTTP 403.  There is no explicit HTTP-level ownership rejection "
        "before the database call.  validate_csrf_token is patched to isolate the "
        "ownership logic from the CSRF dependency."
    ),
    strict=True,
)
async def test_idor_modify_election_cross_organiser(mock_db):
    """
    IDOR: Organiser A opens and closes Organiser B's election.

    Attack:
        A holds a valid JWT (organiser_id=1) and knows B's election_id=102.
        A sends:
            POST /elections/102/open?organiser_id=1
            POST /elections/102/close?organiser_id=1
        organiser_id is a caller-supplied query parameter; it is not extracted
        from an authenticated JWT.  Passing A's own id (1) does not match B's
        election (organiser_id=2), so the SQL WHERE clause produces UPDATE 0
        and the service returns HTTP 400.

        Critical secondary risk: if A knows B's organiser_id (e.g., via the
        GET /elections/{id} endpoint which returns organiser_id in its response
        when the caller omits the organiser_id query param), A can pass
        organiser_id=2 directly.  With no session-bound identity check, the
        UPDATE would succeed and A would have full control over B's election.

    Defence expected:
        Both endpoints should reject cross-organiser requests with HTTP 403
        based on an authenticated identity (JWT claim or session), before
        any database interaction occurs.

    CSRF bypass:
        validate_csrf_token is patched to return True so the ownership logic
        is exercised without interference from the CSRF dependency.  Both
        requests are made within the same client context to reflect a realistic
        attacker session.

    Current status: FAILS — both endpoints return HTTP 400 (DB-level rejection)
    rather than HTTP 403 (HTTP-level ownership check).
    Marked xfail until an explicit ownership check returning 403 is added.
    """
    a_jwt = _make_jwt(_A_ORGANISER_ID, "a@test.com")
    # Simulate the DB WHERE organiser_id=$2 clause finding no matching row.
    mock_db.execute.return_value = "UPDATE 0"

    with patch.object(_election_app, "validate_csrf_token", return_value=True):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_election_app.app),
            base_url="http://test",
        ) as client:
            open_resp = await client.post(
                f"/elections/{_B_ELECTION_ID}/open",
                params={"organiser_id": _A_ORGANISER_ID},
                headers={"Authorization": f"Bearer {a_jwt}"},
                data={},
            )
            close_resp = await client.post(
                f"/elections/{_B_ELECTION_ID}/close",
                params={"organiser_id": _A_ORGANISER_ID},
                headers={"Authorization": f"Bearer {a_jwt}"},
                data={},
            )

    assert open_resp.status_code == 403, (
        f"Expected 403 for cross-organiser open request; "
        f"got {open_resp.status_code}. Body: {open_resp.text[:200]}"
    )
    assert close_resp.status_code == 403, (
        f"Expected 403 for cross-organiser close request; "
        f"got {close_resp.status_code}. Body: {close_resp.text[:200]}"
    )


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "election-service does not validate the Authorization header at all. "
        "GET /elections returns HTTP 200 for any request that includes a valid "
        "organiser_id query param, regardless of what credential (or none) is "
        "present in Authorization: Bearer."
    ),
    strict=True,
)
async def test_voter_token_cannot_access_organiser_routes(mock_db):
    """
    Credential type confusion: a voting token in Authorization: Bearer
    must be rejected by organiser-management routes.

    Voting token format:
        secrets.token_urlsafe(32) — an opaque 43-character URL-safe string.
        Defined in shared/security.py:generate_voting_token().
        This is NOT a JWT; it has no header, payload, or signature.

    Attack:
        A voter who intercepts their own voting token (from email) presents it
        as Authorization: Bearer on an organiser route.
        If accepted, the voter gains access to organiser-level election data.

    Tested route:
        GET /elections?organiser_id=1 (election-service JSON API, app.py line 199).
        The endpoint takes organiser_id as a required query param and performs
        no Bearer token validation.

    Defence expected:
        election-service endpoints that expose organiser data must extract the
        organiser_id from a validated JWT (not a query param) and return
        HTTP 401 when no valid organiser JWT is present in the Authorization
        header.  Passing a voting token must produce 401, not 200.

    Current status: FAILS — election-service ignores the Authorization header.
    The endpoint returns HTTP 200 because organiser_id=1 is present in the
    query string; the credential type is never checked.
    Marked xfail until JWT validation is enforced at the service boundary.
    """
    mock_db.fetch.return_value = []  # No elections for organiser 1

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_election_app.app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            "/elections",
            params={"organiser_id": _A_ORGANISER_ID},
            headers={"Authorization": f"Bearer {_FAKE_VOTING_TOKEN}"},
        )

    assert resp.status_code == 401, (
        f"Expected 401 Unauthorized when a voting token (not an organiser JWT) "
        f"is sent as Authorization: Bearer on GET /elections; "
        f"got {resp.status_code}. "
        "election-service must differentiate organiser JWTs from voting tokens "
        "and reject the wrong credential type with 401."
    )


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "admin-service DELETE /elections/{id}/voters/pii has no JWT validation "
        "(admin-service/app.py line 167-221).  After the CSRF dependency is "
        "bypassed, any caller can erase voter PII for any closed election without "
        "proving ownership.  Organiser JWTs are not inspected at all."
    ),
    strict=True,
)
async def test_organiser_cannot_access_other_service_admin_routes(mock_db):
    """
    Cross-service privilege escalation: an organiser JWT must not authorise
    GDPR PII erasure operations in admin-service.

    Attack:
        A holds a valid organiser JWT signed with JWT_SECRET
        ("your-secret-key-change-in-production" — the auth-service default).
        A sends DELETE /elections/102/voters/pii to admin-service with the JWT
        as Authorization: Bearer.
        admin-service has no JWT validation and no ownership check on this
        endpoint.  After the CSRF dependency is bypassed, the endpoint proceeds
        to erase voter PII for election 102 (owned by B), returning HTTP 200.

    Defence expected:
        admin-service must require a separate admin-level credential — not an
        organiser JWT — for destructive PII operations.  The endpoint must:
          1. Verify the caller holds a valid admin credential.
          2. Verify the caller's organiser_id matches the election's owner.
        Failing either check must return HTTP 403 before any DB modification.

    CSRF bypass:
        validate_csrf_token is patched to return True to isolate the JWT/ownership
        logic.  This represents the threat model where an attacker uses XSS or
        session fixation to obtain a valid CSRF token.

    Current status: FAILS — admin-service returns HTTP 200 (voter PII erased)
    because neither JWT validation nor organiser ownership is checked.
    Marked xfail until admin-level authentication is enforced.
    """
    a_jwt = _make_jwt(_A_ORGANISER_ID, "a@test.com")
    # Election 102 is closed — the status guard at app.py line 183 passes.
    mock_db.fetchrow.return_value = {"status": "closed"}
    # All execute calls (DELETE voter_mfa, DELETE voting_tokens, UPDATE voters)
    # return None; rows_erased resolves to 0 via the `if result else 0` guard.
    mock_db.execute.return_value = None

    with patch.object(_admin_app, "validate_csrf_token", return_value=True):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_admin_app.app),
            base_url="http://test",
        ) as client:
            resp = await client.delete(
                f"/elections/{_B_ELECTION_ID}/voters/pii",
                headers={"Authorization": f"Bearer {a_jwt}"},
                data={},
            )

    assert resp.status_code == 403, (
        f"Expected 403 when an organiser JWT is used to call "
        f"DELETE /elections/{_B_ELECTION_ID}/voters/pii in admin-service; "
        f"got {resp.status_code}. "
        "Organiser JWTs must not authorise PII erasure — a separate admin "
        "authentication layer is required."
    )
